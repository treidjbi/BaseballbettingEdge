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
                         season_k9=9.0, recent_k9=8.5, career_k9=8.8,
                         side="over"):
    """Insert a closed pick into the test DB. Default side='over' matches original hardcoded value."""
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
        date_str, f"Pitcher-{date_offset_days}", "Team", side, 7.5, verdict,
        adj_ev, adj_ev, raw_lambda, raw_lambda, odds, 1.0,
        result, actual_ks, pnl, fetched,
        season_k9, recent_k9, career_k9, ump_k_adj,
    ))
    conn.commit()
    conn.close()


def _find_row(data, verdict, side):
    """Helper: find a row in data['rows'] by verdict + side."""
    for r in data["rows"]:
        if r["verdict"] == verdict and r["side"] == side:
            return r
    return None


# ── Performance JSON tests ───────────────────────────────────────────────────

class TestPerformanceJson:
    def test_written_even_with_zero_picks(self, tmp_env):
        db, perf, params, cal = tmp_env
        cal.run()
        assert perf.exists()
        data = json.loads(perf.read_text())
        assert "total_picks" in data
        assert data["total_picks"] == 0

    def test_rows_excludes_pass(self, tmp_env):
        db, perf, params, cal = tmp_env
        _insert_closed_pick(db, "win", verdict="PASS")
        _insert_closed_pick(db, "loss", verdict="FIRE 1u", date_offset_days=2)
        cal.run()
        data = json.loads(perf.read_text())
        verdicts_in_rows = [r["verdict"] for r in data["rows"]]
        assert "PASS" not in verdicts_in_rows
        fire1u_over = _find_row(data, "FIRE 1u", "over")
        assert fire1u_over is not None
        assert fire1u_over["picks"] == 1

    def test_win_pct_calculated(self, tmp_env):
        db, perf, params, cal = tmp_env
        for i in range(3):
            _insert_closed_pick(db, "win", verdict="FIRE 1u", date_offset_days=i+1)
        _insert_closed_pick(db, "loss", verdict="FIRE 1u", date_offset_days=4)
        cal.run()
        data = json.loads(perf.read_text())
        tier = _find_row(data, "FIRE 1u", "over")
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


# ── Rows array structure tests ───────────────────────────────────────────────

class TestRowsStructure:
    _EXPECTED_ORDER = [
        ("FIRE 3u", "over"),
        ("FIRE 3u", "under"),
        ("FIRE 2u", "over"),
        ("FIRE 2u", "under"),
        ("FIRE 1u", "over"),
        ("FIRE 1u", "under"),
    ]

    def test_always_six_rows(self, tmp_env):
        db, perf, params, cal = tmp_env
        cal.run()
        data = json.loads(perf.read_text())
        assert len(data["rows"]) == 6

    def test_fixed_row_order(self, tmp_env):
        db, perf, params, cal = tmp_env
        _insert_closed_pick(db, "win", verdict="FIRE 3u", side="under")
        cal.run()
        data = json.loads(perf.read_text())
        actual = [(r["verdict"], r["side"]) for r in data["rows"]]
        assert actual == self._EXPECTED_ORDER

    def test_zero_pick_rows_have_null_stats(self, tmp_env):
        db, perf, params, cal = tmp_env
        cal.run()
        data = json.loads(perf.read_text())
        for r in data["rows"]:
            assert r["picks"] == 0
            assert r["win_pct"] is None
            assert r["roi"] is None
            assert r["avg_ev"] is None

    def test_over_and_under_aggregate_independently(self, tmp_env):
        db, perf, params, cal = tmp_env
        # Insert 2 over wins for FIRE 1u
        _insert_closed_pick(db, "win", verdict="FIRE 1u", side="over", date_offset_days=1)
        _insert_closed_pick(db, "win", verdict="FIRE 1u", side="over", date_offset_days=2)
        # Insert 1 under loss for FIRE 1u
        _insert_closed_pick(db, "loss", verdict="FIRE 1u", side="under", date_offset_days=3)
        cal.run()
        data = json.loads(perf.read_text())
        over_row  = _find_row(data, "FIRE 1u", "over")
        under_row = _find_row(data, "FIRE 1u", "under")
        assert over_row["picks"] == 2
        assert over_row["wins"] == 2
        assert under_row["picks"] == 1
        assert under_row["losses"] == 1
        # No bleed-through between sides
        assert over_row["losses"] == 0
        assert under_row["wins"] == 0

    def test_push_only_bucket(self, tmp_env):
        db, perf, params, cal = tmp_env
        _insert_closed_pick(db, "push", verdict="FIRE 3u", side="over", adj_ev=0.015)
        cal.run()
        data = json.loads(perf.read_text())
        row = _find_row(data, "FIRE 3u", "over")
        assert row["picks"] == 1
        assert row["pushes"] == 1
        assert row["win_pct"] is None          # wins + losses == 0
        assert row["roi"] == 0.0               # pnl=0 for push
        assert row["avg_ev"] is not None       # adj_ev is NOT NULL in schema

    def test_roi_formula_percent_of_stake(self, tmp_env):
        """ROI = (total_pnl / picks) * 100, not raw total_pnl."""
        db, perf, params, cal = tmp_env
        # 1 win at -110 → pnl = 0.87; 1 loss → pnl = -1.0 → total_pnl = -0.13
        _insert_closed_pick(db, "win",  verdict="FIRE 2u", side="over",
                             odds=-110, adj_ev=0.07, date_offset_days=1)
        _insert_closed_pick(db, "loss", verdict="FIRE 2u", side="over",
                             odds=-110, adj_ev=0.07, date_offset_days=2)
        cal.run()
        data = json.loads(perf.read_text())
        row = _find_row(data, "FIRE 2u", "over")
        # Expected: (0.87 + -1.0) / 2 * 100 = -6.5
        assert row["roi"] == pytest.approx(-6.5, abs=0.1)

    def test_win_pct_excludes_pushes_from_denominator(self, tmp_env):
        """win_pct = wins / (wins + losses), not wins / picks."""
        db, perf, params, cal = tmp_env
        _insert_closed_pick(db, "win",  verdict="FIRE 3u", side="under", date_offset_days=1)
        _insert_closed_pick(db, "push", verdict="FIRE 3u", side="under", date_offset_days=2)
        cal.run()
        data = json.loads(perf.read_text())
        row = _find_row(data, "FIRE 3u", "under")
        assert row["picks"] == 2
        assert row["win_pct"] == pytest.approx(1.0, abs=0.01)  # 1 win / (1+0 losses) = 1.0


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
        """Model predicts 8.0, actual is 7 → target bias is -1.0.
        With dampening, a single run moves at most LAMBDA_BIAS_MAX_DELTA in the
        correct direction from the starting value of 0.0."""
        db, perf, params, cal = tmp_env
        self._fill_picks(db, 35, raw_lambda=8.0, actual_ks=7)
        cal.run()
        data = json.loads(params.read_text())
        # Bias must be negative (correct direction) and capped at max delta
        assert data["lambda_bias"] < 0
        assert abs(data["lambda_bias"]) <= cal.LAMBDA_BIAS_MAX_DELTA + 0.001

    def test_lambda_bias_corrects_under_prediction(self, tmp_env):
        """Model predicts 6.0, actual is 7 → target bias is +1.0.
        With dampening, a single run moves at most LAMBDA_BIAS_MAX_DELTA in the
        correct direction from the starting value of 0.0."""
        db, perf, params, cal = tmp_env
        self._fill_picks(db, 35, raw_lambda=6.0, actual_ks=7)
        cal.run()
        data = json.loads(params.read_text())
        # Bias must be positive (correct direction) and capped at max delta
        assert data["lambda_bias"] > 0
        assert data["lambda_bias"] <= cal.LAMBDA_BIAS_MAX_DELTA + 0.001

    def test_params_json_has_required_fields(self, tmp_env):
        db, perf, params, cal = tmp_env
        self._fill_picks(db, 30)
        cal.run()
        data = json.loads(params.read_text())
        for field in ("updated_at", "sample_size",
                      "weight_season_cap", "weight_recent", "ump_scale", "lambda_bias"):
            assert field in data, f"Missing field: {field}"
        assert "ev_thresholds" not in data  # thresholds are static, not calibrated


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
        assert len(result["rows"]) == 6
        assert all(r["picks"] == 0 for r in result["rows"])
        assert result["last_calibrated"] is None


def test_phase2_blend_weights_sum_to_one():
    """After Phase 2 calibration with data where season_k9 is the best predictor,
    weight_season_cap should dominate, and weights should sum to <= 1.0."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
    from calibrate import _calibrate_phase2

    # 60 rows with varied K/9 values; actual_ks correlates most with season_k9
    import random
    random.seed(42)
    picks = []
    for i in range(60):
        s_k9 = 7.0 + (i % 8) * 0.5   # 7.0 to 10.5
        r_k9 = 8.0 + (i % 4) * 0.25   # 8.0 to 8.75
        c_k9 = 7.5 + (i % 5) * 0.3    # 7.5 to 8.7
        # actual_ks strongly tracks season_k9
        actual = round(s_k9 * 0.55)
        picks.append({
            "season_k9": s_k9, "recent_k9": r_k9, "career_k9": c_k9,
            "actual_ks": actual, "ump_k_adj": 0.0, "raw_lambda": 5.0,
        })

    params = {"weight_season_cap": 0.70, "weight_recent": 0.20, "ump_scale": 1.0,
              "lambda_bias": 0.0}
    result = _calibrate_phase2(picks, params)
    ws = result["weight_season_cap"]
    wr = result["weight_recent"]
    # Weights must sum to <= 1.0 (career = 1 - ws - wr)
    assert ws + wr <= 1.0
    assert ws >= 0.05
    assert wr >= 0.05
    # Season weight should be at least as large as recent (season is the better predictor)
    assert ws >= wr


def test_ump_scale_increases_when_correlated():
    """When ump_k_adj strongly correlates with residuals, ump_scale should increase."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
    from calibrate import _calibrate_phase2

    # Create data with strong positive correlation between ump_k_adj and residual
    picks = []
    for i in range(60):
        ump_adj = (i % 5) * 1.0  # 0.0, 1.0, 2.0, 3.0, 4.0
        residual = ump_adj * 2    # perfect positive correlation
        picks.append({
            "season_k9": 9.0, "recent_k9": 8.0, "career_k9": 7.0,
            "ump_k_adj": ump_adj,
            "actual_ks": int(5 + residual),
            "raw_lambda": 5.0,
        })

    params = {"weight_season_cap": 0.70, "weight_recent": 0.20,
              "ump_scale": 1.0, "lambda_bias": 0.0}
    result = _calibrate_phase2(picks, params)
    assert result["ump_scale"] > 1.0  # should have increased


def test_ump_scale_decreases_when_uncorrelated():
    """When ump_k_adj shows no correlation with residuals, ump_scale should decrease."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
    from calibrate import _calibrate_phase2

    picks = []
    for i in range(60):
        ump_adj = 0.1 + (i % 3) * 0.1  # 0.1, 0.2, 0.3 (varied)
        picks.append({
            "season_k9": 9.0, "recent_k9": 8.0, "career_k9": 7.0,
            "ump_k_adj": ump_adj,
            "actual_ks": 5,  # constant actual Ks → zero correlation with ump_k_adj
            "raw_lambda": 5.0,
        })

    params = {"weight_season_cap": 0.70, "weight_recent": 0.20,
              "ump_scale": 1.0, "lambda_bias": 0.0}
    result = _calibrate_phase2(picks, params)
    assert result["ump_scale"] < 1.0  # should have decreased
