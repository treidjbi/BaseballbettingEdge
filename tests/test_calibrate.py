import json, os, sys, sqlite3, tempfile, pytest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

import pytz


@pytest.fixture
def tmp_env(tmp_path):
    """Set up temp DB + output paths, return (db_path, perf_path, params_path, calibrate_module)."""
    db = tmp_path / "results.db"
    perf = tmp_path / "performance.json"
    params = tmp_path / "params.json"

    with patch("calibrate.DB_PATH", db), \
         patch("calibrate.PERFORMANCE_PATH", perf), \
         patch("calibrate.PARAMS_PATH", params):
        # Also init the DB
        import fetch_results
        with patch("fetch_results.DB_PATH", db):
            fetch_results.init_db()
        import calibrate
        yield db, perf, params, calibrate


def _insert_closed_pick(db_path, result, verdict="FIRE 1u", odds=-110,
                         adj_ev=0.04, raw_lambda=7.0, actual_ks=8,
                         date_offset_days=1, ump_k_adj=0.1,
                         season_k9=9.0, recent_k9=8.5, career_k9=8.8):
    date_str = (datetime.now() - timedelta(days=date_offset_days)).strftime("%Y-%m-%d")
    fetched = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    pnl = 0.87 if result == "win" else (-1.0 if result == "loss" else 0.0)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        INSERT INTO picks (date, pitcher, team, side, k_line, verdict, ev, adj_ev,
                           raw_lambda, applied_lambda, odds, movement_conf,
                           result, actual_ks, pnl, fetched_at,
                           season_k9, recent_k9, career_k9, ump_k_adj)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        date_str, f"Pitcher-{date_offset_days}", "Team", "over", 7.5, verdict,
        adj_ev, adj_ev, raw_lambda, raw_lambda, odds, 1.0,
        result, actual_ks, pnl, fetched,
        season_k9, recent_k9, career_k9, ump_k_adj,
    ))
    conn.commit()
    conn.close()


# ── Performance JSON tests ───────────────────────────────────────────────────

class TestPerformanceJson:
    def test_written_even_with_zero_picks(self, tmp_env):
        db, perf, params, cal = tmp_env
        cal.run()
        assert perf.exists()
        data = json.loads(perf.read_text())
        assert "total_picks" in data
        assert data["total_picks"] == 0

    def test_by_verdict_excludes_pass(self, tmp_env):
        db, perf, params, cal = tmp_env
        _insert_closed_pick(db, "win", verdict="PASS")
        _insert_closed_pick(db, "loss", verdict="FIRE 1u", date_offset_days=2)
        cal.run()
        data = json.loads(perf.read_text())
        assert "PASS" not in data["by_verdict"]
        assert "FIRE 1u" in data["by_verdict"]

    def test_win_pct_calculated(self, tmp_env):
        db, perf, params, cal = tmp_env
        for i in range(3):
            _insert_closed_pick(db, "win", verdict="FIRE 1u", date_offset_days=i+1)
        _insert_closed_pick(db, "loss", verdict="FIRE 1u", date_offset_days=4)
        cal.run()
        data = json.loads(perf.read_text())
        tier = data["by_verdict"]["FIRE 1u"]
        assert tier["wins"] == 3
        assert tier["losses"] == 1
        assert abs(tier["win_pct"] - 0.75) < 0.01

    def test_lambda_accuracy_present(self, tmp_env):
        db, perf, params, cal = tmp_env
        _insert_closed_pick(db, "win", raw_lambda=7.0, actual_ks=8)
        cal.run()
        data = json.loads(perf.read_text())
        assert "lambda_accuracy" in data
        assert data["lambda_accuracy"]["avg_predicted"] is not None
        assert data["lambda_accuracy"]["avg_actual"] is not None

    def test_insufficient_picks_shows_not_calibrated(self, tmp_env):
        db, perf, params, cal = tmp_env
        for i in range(5):
            _insert_closed_pick(db, "win", date_offset_days=i+1)
        cal.run()
        data = json.loads(perf.read_text())
        assert data["last_calibrated"] is None

    def test_params_not_written_when_insufficient(self, tmp_env):
        db, perf, params, cal = tmp_env
        cal.run()
        assert not params.exists()


# ── Phase 1 calibration tests ────────────────────────────────────────────────

class TestPhase1Calibration:
    def _fill_picks(self, db, n, raw_lambda=7.0, actual_ks=8, odds=-110,
                    result="win", verdict="FIRE 1u", adj_ev=0.05):
        for i in range(n):
            _insert_closed_pick(db, result, verdict=verdict, odds=odds,
                                 adj_ev=adj_ev, raw_lambda=raw_lambda,
                                 actual_ks=actual_ks, date_offset_days=i+1)

    def test_no_params_written_below_30(self, tmp_env):
        db, perf, params, cal = tmp_env
        self._fill_picks(db, 29)
        cal.run()
        assert not params.exists()

    def test_params_written_at_30(self, tmp_env):
        db, perf, params, cal = tmp_env
        self._fill_picks(db, 30)
        cal.run()
        assert params.exists()

    def test_lambda_bias_corrects_over_prediction(self, tmp_env):
        """Model predicts 8.0, actual is 7 → bias = -1.0."""
        db, perf, params, cal = tmp_env
        self._fill_picks(db, 35, raw_lambda=8.0, actual_ks=7)
        cal.run()
        data = json.loads(params.read_text())
        assert abs(data["lambda_bias"] - (-1.0)) < 0.1

    def test_lambda_bias_corrects_under_prediction(self, tmp_env):
        """Model predicts 6.0, actual is 7 → bias = +1.0."""
        db, perf, params, cal = tmp_env
        self._fill_picks(db, 35, raw_lambda=6.0, actual_ks=7)
        cal.run()
        data = json.loads(params.read_text())
        assert data["lambda_bias"] > 0

    def test_ev_threshold_bounds_enforced(self, tmp_env):
        db, perf, params, cal = tmp_env
        for i in range(40):
            _insert_closed_pick(db, "win", verdict="FIRE 2u", odds=-110,
                                 adj_ev=0.08, raw_lambda=7.0, actual_ks=9,
                                 date_offset_days=i+1)
        cal.run()
        data = json.loads(params.read_text())
        assert data["ev_thresholds"]["fire2"] <= 0.10  # max bound

    def test_params_json_has_required_fields(self, tmp_env):
        db, perf, params, cal = tmp_env
        self._fill_picks(db, 30)
        cal.run()
        data = json.loads(params.read_text())
        for field in ("updated_at", "sample_size", "ev_thresholds",
                      "weight_season_cap", "weight_recent", "ump_scale", "lambda_bias"):
            assert field in data, f"Missing field: {field}"


# ── Phase 2 calibration tests ────────────────────────────────────────────────

class TestPhase2Calibration:
    def test_phase2_not_triggered_below_60(self, tmp_env):
        db, perf, params, cal = tmp_env
        for i in range(59):
            _insert_closed_pick(db, "win" if i % 2 == 0 else "loss",
                                 date_offset_days=i+1)
        cal.run()
        data = json.loads(params.read_text())
        # ump_scale should remain default (not changed by Phase 2)
        assert data["ump_scale"] == 1.0

    def test_ump_scale_bounded(self, tmp_env):
        db, perf, params, cal = tmp_env
        for i in range(65):
            _insert_closed_pick(db, "win" if i % 2 == 0 else "loss",
                                 date_offset_days=i+1)
        # Pre-seed params with low ump_scale
        existing = dict(cal.DEFAULTS)
        existing["ump_scale"] = 0.1
        with open(params, "w") as f:
            json.dump(existing, f)
        cal.run()
        data = json.loads(params.read_text())
        assert data["ump_scale"] >= 0.0
        assert data["ump_scale"] <= 1.5

    def test_build_performance_is_pure(self, tmp_env):
        """build_performance() should not do I/O — takes closed list and optional params, returns dict."""
        db, perf, params, cal = tmp_env
        # Call with no params file existing — should not crash or do I/O
        result = cal.build_performance([], current_params=None)
        assert isinstance(result, dict)
        assert result["total_picks"] == 0
        assert result["by_verdict"] == {}
        assert result["last_calibrated"] is None
