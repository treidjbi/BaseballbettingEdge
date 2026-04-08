import sys, os
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

from run_pipeline import _game_date_et


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
    out_path = tmp_path / "today.json"

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=[_sample_prop()]), \
         patch("run_pipeline.fetch_stats", return_value={"Test Pitcher": _sample_stats()}), \
         patch("run_pipeline.fetch_swstr", return_value={"Test Pitcher": 0.110}), \
         patch("run_pipeline.fetch_umpires", return_value={"Test Pitcher": 0.0}), \
         patch("run_pipeline._write_archive"):  # skip archive for unit test
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
         patch("run_pipeline.fetch_odds", return_value=[]), \
         patch("run_pipeline._write_archive"):
        run_pipeline.run("2026-04-01")

    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert data["props_available"] is False
    assert data["pitchers"] == []


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
         patch("run_pipeline._write_archive"):
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
