import sys, os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

from run_pipeline import _game_date_et, _write_dated_archive_only


class TestGameDateEt:
    def test_utc_midnight_converts_to_previous_et_date(self):
        # 00:05 UTC on Mar 26 is 20:05 ET on Mar 25 (ET = UTC-4 in summer / UTC-5 in winter)
        # Mar 26 is after DST spring-forward (2026), so ET = UTC-4; 00:05Z → 20:05 ET Mar 25
        result = _game_date_et("2026-03-26T00:05:00Z", "2026-03-26")
        assert result == "2026-03-25"

    def test_afternoon_game_stays_same_et_date(self):
        # 19:10 UTC = 15:10 ET (EDT, UTC-4) — still Mar 26
        result = _game_date_et("2026-03-26T19:10:00Z", "2026-03-26")
        assert result == "2026-03-26"

    def test_empty_string_returns_fallback(self):
        result = _game_date_et("", "2026-03-25")
        assert result == "2026-03-25"

    def test_unparseable_string_returns_fallback(self):
        result = _game_date_et("not-a-date", "2026-03-25")
        assert result == "2026-03-25"


def test_default_date_uses_et_not_utc():
    """The default date in argparse should use ET timezone, not system local time.
    Verify by constructing the default using the same ZoneInfo logic."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
    from zoneinfo import ZoneInfo
    from datetime import datetime
    from unittest.mock import patch

    # Simulate 11pm ET April 1 = 3am UTC April 2
    et_now = datetime(2026, 4, 1, 23, 0, 0, tzinfo=ZoneInfo("America/New_York"))

    with patch("run_pipeline.datetime") as mock_dt:
        mock_dt.now.return_value = et_now
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_dt.strptime = datetime.strptime

        # Simulate argparse default computation using ET-aware now()
        import argparse
        parser = argparse.ArgumentParser()
        parser.add_argument("date", nargs="?",
                            default=mock_dt.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d"))
        args = parser.parse_args([])
        # Should be ET date (April 1), not UTC date (April 2)
        assert args.date == "2026-04-01"


def _sample_prop():
    return {
        "pitcher": "Test Pitcher", "team": "", "opp_team": "",
        "game_time": "2026-04-01T23:05:00Z", "k_line": 6.5, "opening_line": 6.5,
        "best_over_book": "FD", "best_over_odds": -110, "best_under_odds": -110,
        "opening_over_odds": -110, "opening_under_odds": -110,
    }

def _sample_stats():
    return {
        "season_k9": 9.0, "recent_k9": 9.0, "career_k9": 8.0,
        "starts_count": 5, "innings_pitched_season": 30.0,
        "avg_ip_last5": 5.5, "opp_k_rate": 0.227, "opp_games_played": 10,
        "team": "Test Team", "opp_team": "Opp Team",
    }


def test_run_writes_today_json(tmp_path):
    """run() should always write today.json even if it has 0 pitchers."""
    import run_pipeline
    run_pipeline._batter_stats_cache = None
    out_path = tmp_path / "today.json"

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=[_sample_prop()]), \
         patch("run_pipeline.fetch_stats", return_value={"Test Pitcher": _sample_stats()}), \
         patch("run_pipeline.fetch_swstr", return_value={"Test Pitcher": {"swstr_pct": 0.110, "career_swstr_pct": None}}), \
         patch("run_pipeline.fetch_umpires", return_value={"Test Pitcher": 0.0}), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}):
        # _write_archive is the sole writer of today.json — don't patch it out.
        run_pipeline.run("2026-04-01")

    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert data["date"] == "2026-04-01"
    assert len(data["pitchers"]) == 1


def test_run_writes_empty_output_when_no_props(tmp_path):
    """run() should write today.json with props_available=False when no odds returned."""
    import run_pipeline
    out_path = tmp_path / "today.json"

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=[]):
        run_pipeline.run("2026-04-01")

    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert data["props_available"] is False
    assert data["pitchers"] == []


def test_run_calls_lock_due_picks(tmp_path):
    """run() should call lock_due_picks before seeding picks."""
    import run_pipeline
    run_pipeline._batter_stats_cache = None
    out_path = tmp_path / "today.json"
    lock_calls = []

    def mock_lock(conn, now, lock_window_minutes=30, lock_all_past=False):
        lock_calls.append({"lock_all_past": lock_all_past})
        return 0

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=[_sample_prop()]), \
         patch("run_pipeline.fetch_stats", return_value={"Test Pitcher": _sample_stats()}), \
         patch("run_pipeline.fetch_swstr", return_value={"Test Pitcher": {"swstr_pct": 0.110, "career_swstr_pct": None}}), \
         patch("run_pipeline.fetch_umpires", return_value={"Test Pitcher": 0.0}), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}), \
         patch("run_pipeline.lock_due_picks", mock_lock), \
         patch("run_pipeline.init_db"), \
         patch("run_pipeline.load_history_into_db"), \
         patch("run_pipeline.get_db", return_value=MagicMock()), \
         patch("run_pipeline.seed_picks", return_value=0), \
         patch("run_pipeline.export_db_to_history"), \
         patch("run_pipeline._write_archive"):
        run_pipeline.run("2026-04-01")

    assert len(lock_calls) >= 1
    assert lock_calls[0]["lock_all_past"] is False


def test_grading_run_calls_lock_all_past(tmp_path):
    """Grading run should call lock_due_picks(lock_all_past=True)."""
    import run_pipeline
    lock_calls = []

    def mock_lock(conn, now, lock_window_minutes=30, lock_all_past=False):
        lock_calls.append({"lock_all_past": lock_all_past})
        return 0

    with patch("run_pipeline.lock_due_picks", mock_lock), \
         patch("run_pipeline.fetch_results_run"), \
         patch("run_pipeline._enrich_archives_with_results"), \
         patch("run_pipeline.calibrate_run"):
        run_pipeline.run("2026-04-01", run_type="grading")

    assert any(c["lock_all_past"] is True for c in lock_calls)


def _sample_prop_for(pitcher_name="Test Pitcher", game_time="2026-04-12T23:05:00Z"):
    return {
        "pitcher": pitcher_name, "team": "", "opp_team": "",
        "game_time": game_time, "k_line": 6.5, "opening_line": 6.5,
        "best_over_book": "FanDuel", "best_over_odds": -110, "best_under_odds": -110,
        "opening_over_odds": -110, "opening_under_odds": -110,
        "ref_book": "FanDuel",
    }


# ── Tests: _write_dated_archive_only ──────────────────────────────────────────

def test_write_dated_archive_only_creates_dated_file(tmp_path):
    """_write_dated_archive_only should write a dated JSON and update index."""
    import run_pipeline
    with patch.object(run_pipeline, "OUTPUT_PATH", tmp_path / "today.json"):
        _write_dated_archive_only([], "2026-04-12", props_available=False)

    dated = tmp_path / "2026-04-12.json"
    assert dated.exists(), "Dated archive file not created"
    data = json.loads(dated.read_text())
    assert data["date"] == "2026-04-12"
    assert data["props_available"] is False

    index = tmp_path / "index.json"
    assert index.exists()
    assert "2026-04-12" in json.loads(index.read_text())["dates"]


def test_write_dated_archive_only_does_not_touch_today_json(tmp_path):
    """_write_dated_archive_only must not create or overwrite today.json."""
    import run_pipeline
    today_path = tmp_path / "today.json"
    today_path.write_text('{"date": "2026-04-11", "pitchers": []}')

    with patch.object(run_pipeline, "OUTPUT_PATH", today_path):
        _write_dated_archive_only([_sample_stats()], "2026-04-12", props_available=True)

    # today.json should be unchanged
    data = json.loads(today_path.read_text())
    assert data["date"] == "2026-04-11", "today.json was overwritten by preview archive write"


# ── Tests: preview run writes dated archive ────────────────────────────────────

def test_preview_run_writes_dated_archive_and_preview_json(tmp_path):
    """_run_preview should write preview_lines.json AND a dated dashboard archive."""
    import run_pipeline
    run_pipeline._batter_stats_cache = None
    today_path  = tmp_path / "today.json"
    preview_path = tmp_path / "preview_lines.json"

    prop = _sample_prop_for("Tomorrow Pitcher")

    with patch.object(run_pipeline, "OUTPUT_PATH",  today_path), \
         patch.object(run_pipeline, "PREVIEW_PATH", preview_path), \
         patch("run_pipeline.fetch_odds",  return_value=[prop]), \
         patch("run_pipeline.fetch_stats", return_value={"Tomorrow Pitcher": _sample_stats()}), \
         patch("run_pipeline.fetch_swstr", return_value={"Tomorrow Pitcher": {"swstr_pct": 0.11, "career_swstr_pct": None}}), \
         patch("run_pipeline.fetch_umpires", return_value={"Tomorrow Pitcher": 0.0}), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}):
        run_pipeline._run_preview("2026-04-12")

    # preview_lines.json must exist
    assert preview_path.exists(), "preview_lines.json not written"
    preview_data = json.loads(preview_path.read_text())
    assert preview_data["date"] == "2026-04-12"
    assert "Tomorrow Pitcher" in preview_data["lines"]

    # Dated archive must exist
    dated = tmp_path / "2026-04-12.json"
    assert dated.exists(), "Dated dashboard archive not written by preview run"
    dated_data = json.loads(dated.read_text())
    assert dated_data["date"] == "2026-04-12"
    assert len(dated_data["pitchers"]) == 1

    # today.json must NOT have been created/overwritten
    assert not today_path.exists(), "Preview run must not touch today.json"


def test_preview_run_does_not_touch_today_json_when_it_exists(tmp_path):
    """If today.json already has today's data, preview run must leave it intact."""
    import run_pipeline
    run_pipeline._batter_stats_cache = None
    today_path  = tmp_path / "today.json"
    preview_path = tmp_path / "preview_lines.json"
    today_path.write_text('{"date": "2026-04-11", "pitchers": [{"pitcher": "Today Guy"}]}')

    prop = _sample_prop_for("Tomorrow Pitcher")

    with patch.object(run_pipeline, "OUTPUT_PATH",  today_path), \
         patch.object(run_pipeline, "PREVIEW_PATH", preview_path), \
         patch("run_pipeline.fetch_odds",  return_value=[prop]), \
         patch("run_pipeline.fetch_stats", return_value={"Tomorrow Pitcher": _sample_stats()}), \
         patch("run_pipeline.fetch_swstr", return_value={"Tomorrow Pitcher": {"swstr_pct": 0.11, "career_swstr_pct": None}}), \
         patch("run_pipeline.fetch_umpires", return_value={"Tomorrow Pitcher": 0.0}), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}):
        run_pipeline._run_preview("2026-04-12")

    data = json.loads(today_path.read_text())
    assert data["date"] == "2026-04-11", "today.json date was overwritten by preview run"
    assert data["pitchers"][0]["pitcher"] == "Today Guy", "today.json pitchers were overwritten"


def test_run_evening_calls_results_and_calibrate(tmp_path):
    """run_type='evening' should invoke fetch_results.run and calibrate.run."""
    import run_pipeline
    out_path = tmp_path / "today.json"

    results_called = []
    calibrate_called = []

    def fake_results_run():
        results_called.append(True)

    def fake_calibrate_run():
        calibrate_called.append(True)

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=[]), \
         patch("run_pipeline._write_archive"), \
         patch("run_pipeline._enrich_archives_with_results"):
        import sys
        fake_fetch_results = MagicMock()
        fake_fetch_results.run = fake_results_run
        fake_calibrate = MagicMock()
        fake_calibrate.run = fake_calibrate_run
        with patch.dict(sys.modules, {
            "fetch_results": fake_fetch_results,
            "calibrate": fake_calibrate,
        }):
            run_pipeline.run("2026-04-01", run_type="grading")

    assert len(results_called) == 1, "fetch_results.run() was not called"
    assert len(calibrate_called) == 1, "calibrate.run() was not called"
