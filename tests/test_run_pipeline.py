import sys, os
import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

from run_pipeline import _game_date_et, _write_dated_archive_only


@pytest.fixture(autouse=True)
def isolate_steam_path(tmp_path, monkeypatch):
    import run_pipeline

    monkeypatch.setattr(run_pipeline, "STEAM_PATH", tmp_path / "steam.json")


def test_run_pipeline_tests_do_not_target_repo_steam_artifact():
    import run_pipeline

    repo_steam_path = (Path.cwd() / "dashboard/data/processed/steam.json").resolve()
    assert run_pipeline.STEAM_PATH.resolve() != repo_steam_path


def test_fetch_batter_stats_cached_falls_back_to_empty_dict_on_fetch_failure():
    import run_pipeline

    run_pipeline._batter_stats_cache = None

    with patch("run_pipeline.fetch_batter_stats", side_effect=RuntimeError("boom")):
        assert run_pipeline.fetch_batter_stats_cached(2026) == {}
        assert run_pipeline.fetch_batter_stats_cached(2026) == {}


def test_apply_quality_gates_to_records_preserves_raw_and_summarizes_flags():
    import run_pipeline

    records = [
        {
            "pitcher": "Opener Pitcher",
            "team": "Arizona Diamondbacks",
            "opp_team": "Los Angeles Dodgers",
            "game_time": "2026-04-29T20:10:00Z",
            "season_k9": 9.0,
            "recent_k9": 9.0,
            "career_k9": 9.0,
            "recent_start_count": 5,
            "lineup_used": True,
            "lineup_count": 9,
            "opening_odds_source": "preview",
            "k_line": 6.5,
            "lambda": 7.2,
            "best_over_odds": -110,
            "best_under_odds": -110,
            "is_opener": True,
            "ev_over": {"verdict": "FIRE 2u", "adj_ev": 0.19, "ev": 0.2},
            "ev_under": {"verdict": "PASS", "adj_ev": -0.04, "ev": -0.03},
        }
    ]

    gated, summary = run_pipeline._apply_quality_gates_to_records(
        records,
        pre_record_skips={"no_target_book": 2},
    )

    assert gated[0]["quality_gate_level"] == "blocked"
    assert gated[0]["ev_over"]["raw_verdict"] == "FIRE 2u"
    assert gated[0]["ev_over"]["verdict"] == "PASS"
    assert gated[0]["ev_over"]["adj_ev"] == 0.0
    assert summary["blocked"] == 1
    assert summary["severe_flags"]["opener"] == 1
    assert summary["pre_record_skips"] == {"no_target_book": 2}


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


def _sample_prop_for(name):
    prop = _sample_prop().copy()
    prop["pitcher"] = name
    return prop


def _sample_props_for_game_count(game_count):
    props = []
    for idx in range(game_count):
        away_team = f"Away Team {idx}"
        home_team = f"Home Team {idx}"
        game_time = f"2026-04-{(idx % 28) + 1:02d}T23:05:00Z"

        away_prop = _sample_prop_for(f"Away Pitcher {idx}")
        away_prop["team"] = away_team
        away_prop["opp_team"] = home_team
        away_prop["game_time"] = game_time
        props.append(away_prop)

        home_prop = _sample_prop_for(f"Home Pitcher {idx}")
        home_prop["team"] = home_team
        home_prop["opp_team"] = away_team
        home_prop["game_time"] = game_time
        props.append(home_prop)

    return props


def _sample_stats():
    return {
        "season_k9": 9.0, "recent_k9": 9.0, "career_k9": 8.0,
        "starts_count": 5, "innings_pitched_season": 30.0,
        "avg_ip_last5": 5.5, "opp_k_rate": 0.227, "opp_games_played": 10,
        "team": "Test Team", "opp_team": "Opp Team",
    }


def _sample_stats_for(team, opp_team):
    stats = _sample_stats().copy()
    stats["team"] = team
    stats["opp_team"] = opp_team
    stats["park_team"] = opp_team
    return stats


def test_collect_data_warnings_warns_when_umpires_return_zero_entries_for_games():
    from run_pipeline import collect_data_warnings

    warnings = collect_data_warnings(
        props=_sample_props_for_game_count(15),
        ump_diagnostics={"hp_count_fetched": 0},
        swstr_warning=None,
        lineup_confirmed_count=30,
        lineup_missing_splits_count=0,
    )

    assert warnings == [
        "fetch_umpires returned 0 entries for 15 scheduled games",
    ]


def test_collect_data_warnings_clean_run_returns_empty_list():
    from run_pipeline import collect_data_warnings

    warnings = collect_data_warnings(
        props=_sample_props_for_game_count(3),
        ump_diagnostics={"hp_count_fetched": 3},
        swstr_warning=None,
        lineup_confirmed_count=6,
        lineup_missing_splits_count=0,
    )

    assert warnings == []


def test_collect_data_warnings_counts_lineup_coverage_in_lineups_not_games():
    from run_pipeline import collect_data_warnings

    warnings = collect_data_warnings(
        props=_sample_props_for_game_count(2),
        ump_diagnostics={"hp_count_fetched": 2},
        swstr_warning=None,
        lineup_confirmed_count=3,
        lineup_missing_splits_count=0,
    )

    assert warnings == [
        "fetch_lineups: confirmed 3/4 opposing lineups (1 still projected)",
    ]


def test_collect_data_warnings_handles_half_covered_lineup_slate():
    from run_pipeline import collect_data_warnings

    warnings = collect_data_warnings(
        props=_sample_props_for_game_count(3),
        ump_diagnostics={"hp_count_fetched": 3},
        swstr_warning=None,
        lineup_confirmed_count=3,
        lineup_missing_splits_count=0,
    )

    assert warnings == [
        "fetch_lineups: confirmed 3/6 opposing lineups (3 still projected)",
    ]


def test_collect_data_warnings_reports_missing_batter_splits_in_lineup_units():
    from run_pipeline import collect_data_warnings

    warnings = collect_data_warnings(
        props=_sample_props_for_game_count(15),
        ump_diagnostics={"hp_count_fetched": 15},
        swstr_warning=None,
        lineup_confirmed_count=30,
        lineup_missing_splits_count=8,
    )

    assert warnings == [
        "fetch_batter_stats missing splits for 8/30 opposing lineups",
    ]


def test_collect_data_warnings_includes_swstr_warning_when_present():
    from run_pipeline import collect_data_warnings

    warnings = collect_data_warnings(
        props=_sample_props_for_game_count(1),
        ump_diagnostics={"hp_count_fetched": 1},
        swstr_warning="fetch_swstr career baseline unavailable, zeroing SwStr delta",
        lineup_confirmed_count=2,
        lineup_missing_splits_count=0,
    )

    assert warnings == [
        "fetch_swstr career baseline unavailable, zeroing SwStr delta",
    ]


def test_collect_data_warnings_falls_back_to_prop_count_when_some_matchups_are_unresolved():
    from run_pipeline import collect_data_warnings

    props = _sample_props_for_game_count(2)
    props[2]["team"] = ""
    props[2]["opp_team"] = ""
    props[3]["team"] = ""
    props[3]["opp_team"] = ""

    warnings = collect_data_warnings(
        props=props,
        ump_diagnostics={"hp_count_fetched": 0},
        swstr_warning=None,
        lineup_confirmed_count=4,
        lineup_missing_splits_count=0,
    )

    assert warnings == [
        "fetch_umpires returned 0 entries for 2 scheduled games",
    ]


def test_collect_data_warnings_uses_lineup_eligible_total_when_provided():
    from run_pipeline import collect_data_warnings

    warnings = collect_data_warnings(
        props=_sample_props_for_game_count(2),
        ump_diagnostics={"hp_count_fetched": 2},
        swstr_warning=None,
        lineup_confirmed_count=0,
        lineup_missing_splits_count=0,
        lineup_total_count=1,
    )

    assert warnings == [
        "fetch_lineups: confirmed 0/1 opposing lineups (1 still projected)",
    ]


def test_run_writes_today_json(tmp_path):
    """run() should always write today.json even if it has 0 pitchers."""
    import run_pipeline
    run_pipeline._batter_stats_cache = None
    out_path = tmp_path / "today.json"

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=[_sample_prop()]), \
         patch("run_pipeline.fetch_stats", return_value=({"Test Pitcher": _sample_stats()}, {})), \
         patch("run_pipeline.fetch_swstr", return_value={"Test Pitcher": {"swstr_pct": 0.110, "career_swstr_pct": None}}), \
         patch("run_pipeline.fetch_umpires", return_value=({"Test Pitcher": 0.0}, {"hp_count_fetched": 0, "pitcher_nonzero_count": 0})), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}), \
         patch("run_pipeline.init_db"), \
         patch("run_pipeline.load_history_into_db"), \
         patch("run_pipeline.get_db", return_value=MagicMock()), \
         patch("run_pipeline.lock_due_picks", return_value=0), \
         patch("run_pipeline.seed_picks", return_value=0), \
         patch("run_pipeline.export_db_to_history"):
        # _write_archive is the sole writer of today.json — don't patch it out.
        run_pipeline.run("2026-04-01")

    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert data["date"] == "2026-04-01"
    assert len(data["pitchers"]) == 1


def test_run_logs_stage_summaries_for_full_run(tmp_path, caplog):
    """Full runs should emit one concise key=value summary per major stage."""
    import logging
    import run_pipeline
    run_pipeline._batter_stats_cache = None
    out_path = tmp_path / "today.json"
    caplog.set_level(logging.INFO)

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=[_sample_prop()]), \
         patch("run_pipeline.fetch_stats", return_value=({"Test Pitcher": _sample_stats()}, {})), \
         patch("run_pipeline.fetch_swstr", return_value={"Test Pitcher": {"swstr_pct": 0.110, "career_swstr_pct": None}}), \
         patch("run_pipeline.fetch_umpires", return_value=({"Test Pitcher": 0.25}, {"hp_count_fetched": 1, "pitcher_nonzero_count": 1})), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}), \
         patch("run_pipeline.init_db"), \
         patch("run_pipeline.load_history_into_db"), \
         patch("run_pipeline.get_db", return_value=MagicMock()), \
         patch("run_pipeline.lock_due_picks", return_value=0), \
         patch("run_pipeline.seed_picks", return_value=0), \
         patch("run_pipeline.export_db_to_history"):
        run_pipeline.run("2026-04-01")

    messages = [record.getMessage() for record in caplog.records]
    assert any(msg.startswith("stage=fetch_odds ms=") and "props=1" in msg for msg in messages)
    assert any(
        msg.startswith("stage=fetch_stats ms=")
        and "requested=1" in msg
        and "resolved=1" in msg
        for msg in messages
    )
    assert any(
        msg.startswith("stage=fetch_swstr ms=")
        and "requested=1" in msg
        and "resolved=1" in msg
        for msg in messages
    )
    assert any(
        msg.startswith("stage=fetch_umpires ms=")
        and "props=1" in msg
        and "nonzero=1" in msg
        for msg in messages
    )
    assert any(
        msg.startswith("stage=build_records ms=")
        and "built=1" in msg
        and "unresolved=0" in msg
        for msg in messages
    )


def test_run_writes_connection_health_and_warns_on_unresolved_props(tmp_path, caplog):
    """Props that survive intake but never become records should be surfaced."""
    import logging
    import run_pipeline
    run_pipeline._batter_stats_cache = None
    out_path = tmp_path / "today.json"
    caplog.set_level(logging.INFO)

    props = [
        {**_sample_prop(), "pitcher": "Resolved Pitcher"},
        {**_sample_prop(), "pitcher": "Missing Stats Pitcher"},
    ]
    stats_map = {
        "Resolved Pitcher": _sample_stats(),
    }

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=props), \
         patch("run_pipeline.fetch_stats", return_value=(stats_map, {})), \
         patch("run_pipeline.fetch_swstr", return_value={"Resolved Pitcher": {"swstr_pct": 0.110, "career_swstr_pct": None}}), \
         patch("run_pipeline.fetch_umpires", return_value=({"Resolved Pitcher": 0.25}, {"hp_count_fetched": 1, "pitcher_nonzero_count": 1})), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}), \
         patch("run_pipeline.init_db"), \
         patch("run_pipeline.load_history_into_db"), \
         patch("run_pipeline.get_db", return_value=MagicMock()), \
         patch("run_pipeline.lock_due_picks", return_value=0), \
         patch("run_pipeline.seed_picks", return_value=0), \
         patch("run_pipeline.export_db_to_history"):
        run_pipeline.run("2026-04-01")

    data = json.loads(out_path.read_text())
    health = data["connection_health"]
    assert health["props_seen"] == 2
    assert health["stats_resolved"] == 1
    assert health["records_built"] == 1
    assert health["unresolved_count"] == 1
    assert health["missing_stats_count"] == 1
    assert health["feature_build_failures_count"] == 0
    assert health["degraded"] is True
    assert health["sample_unresolved_pitchers"] == ["Missing Stats Pitcher"]

    assert any(
        msg == (
            "Slate integrity warning: unresolved_props=1 "
            "missing_stats=1 build_failures=0 ignored_non_starters=0 "
            "sample=Missing Stats Pitcher"
        )
        for msg in (record.getMessage() for record in caplog.records)
    )


def test_run_filters_downstream_feature_fetches_to_stats_resolved_props(tmp_path):
    """Props with no resolved starter stats should be excluded from later
    feature fetches so junk intake does not bloat runtime or lambda inputs."""
    import run_pipeline
    run_pipeline._batter_stats_cache = None
    out_path = tmp_path / "today.json"

    props = [
        {**_sample_prop(), "pitcher": "Resolved Pitcher"},
        {**_sample_prop(), "pitcher": "Unresolved Pitcher"},
    ]
    stats_map = {
        "Resolved Pitcher": _sample_stats(),
    }
    swstr_mock = MagicMock(return_value={"Resolved Pitcher": {"swstr_pct": 0.110, "career_swstr_pct": None}})
    ump_mock = MagicMock(return_value=({"Resolved Pitcher": 0.25}, {"hp_count_fetched": 1, "pitcher_nonzero_count": 1}))

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=props), \
         patch("run_pipeline.fetch_stats", return_value=(stats_map, {})), \
         patch("run_pipeline.fetch_swstr", swstr_mock), \
         patch("run_pipeline.fetch_umpires", ump_mock), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}), \
         patch("run_pipeline.init_db"), \
         patch("run_pipeline.load_history_into_db"), \
         patch("run_pipeline.get_db", return_value=MagicMock()), \
         patch("run_pipeline.lock_due_picks", return_value=0), \
         patch("run_pipeline.seed_picks", return_value=0), \
         patch("run_pipeline.export_db_to_history"):
        run_pipeline.run("2026-04-01")

    swstr_args = swstr_mock.call_args[0]
    assert swstr_args == (2026, ["Resolved Pitcher"])

    ump_props = ump_mock.call_args[0][0]
    assert [prop["pitcher"] for prop in ump_props] == ["Resolved Pitcher"]

    data = json.loads(out_path.read_text())
    assert data["connection_health"]["unresolved_count"] == 1
    assert data["connection_health"]["sample_unresolved_pitchers"] == ["Unresolved Pitcher"]


def test_run_writes_data_warnings_to_today_json(tmp_path):
    import run_pipeline
    run_pipeline._batter_stats_cache = None

    out_path = tmp_path / "today.json"
    props = _sample_props_for_game_count(1)
    stats_map = {
        "Away Pitcher 0": _sample_stats_for("Away Team 0", "Home Team 0"),
        "Home Pitcher 0": _sample_stats_for("Home Team 0", "Away Team 0"),
    }

    def fake_build_pitcher_record(odds, stats, ump_k_adj, **kwargs):
        return {
            "pitcher": odds["pitcher"],
            "team": stats["team"],
            "opp_team": stats["opp_team"],
            "game_time": odds["game_time"],
            "lambda": 4.2,
            "ev_over": {"verdict": "LEAN"},
        }

    def fake_fetch_lineups(date_str, team):
        if team == "Away Team 0":
            return [{"name": "Known Batter", "bats": "R"}]
        return None

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=props), \
         patch("run_pipeline.fetch_stats", return_value=(stats_map, {})), \
         patch("run_pipeline.fetch_swstr", return_value={
             "Away Pitcher 0": {"swstr_pct": 0.110, "career_swstr_pct": None},
             "Home Pitcher 0": {"swstr_pct": 0.109, "career_swstr_pct": None},
             "__meta__": {"current_usable": True, "career_usable": True},
         }), \
         patch("run_pipeline.fetch_umpires", return_value=(
             {"Away Pitcher 0": 0.25, "Home Pitcher 0": 0.25},
             {"hp_count_fetched": 1, "pitcher_nonzero_count": 2},
         )), \
         patch("run_pipeline.build_pitcher_record", side_effect=fake_build_pitcher_record), \
         patch("run_pipeline.fetch_lineups_for_pitcher", side_effect=fake_fetch_lineups), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={"known batter": {"vs_R": 0.2, "vs_L": 0.21}}), \
         patch("run_pipeline.init_db"), \
         patch("run_pipeline.load_history_into_db"), \
         patch("run_pipeline.get_db", return_value=MagicMock()), \
         patch("run_pipeline.lock_due_picks", return_value=0), \
         patch("run_pipeline.seed_picks", return_value=0), \
         patch("run_pipeline.export_db_to_history"), \
         patch("run_pipeline._write_steam"):
        run_pipeline.run("2026-04-01")

    data = json.loads(out_path.read_text())
    assert data["data_warnings"] == [
        "fetch_lineups: confirmed 1/2 opposing lineups (1 still projected)",
    ]


def test_run_fetches_opposing_lineup_for_pitcher_projection(tmp_path):
    import run_pipeline
    run_pipeline._batter_stats_cache = None

    out_path = tmp_path / "today.json"
    prop = _sample_prop_for("Lineup Direction Pitcher")
    stats = _sample_stats_for("Pitcher Team", "Opponent Team")
    requested_lineup_teams = []

    def fake_fetch_lineups(date_str, team):
        requested_lineup_teams.append(team)
        return [{"name": "Opponent Batter", "bats": "R"}]

    def fake_build_pitcher_record(odds, stats, ump_k_adj, *, lineup, batter_stats, **kwargs):
        assert lineup == [{"name": "Opponent Batter", "bats": "R"}]
        return {
            "pitcher": odds["pitcher"],
            "team": stats["team"],
            "opp_team": stats["opp_team"],
            "game_time": odds["game_time"],
            "lambda": 4.2,
            "ev_over": {"verdict": "LEAN"},
        }

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=[prop]), \
         patch("run_pipeline.fetch_stats", return_value=({"Lineup Direction Pitcher": stats}, {})), \
         patch("run_pipeline.fetch_swstr", return_value={
             "Lineup Direction Pitcher": {"swstr_pct": 0.110, "career_swstr_pct": 0.105},
             "__meta__": {"current_usable": True, "career_usable": True},
         }), \
         patch("run_pipeline.fetch_umpires", return_value=(
             {"Lineup Direction Pitcher": 0.25},
             {"hp_count_fetched": 1, "pitcher_nonzero_count": 1},
         )), \
         patch("run_pipeline.fetch_lineups_for_pitcher", side_effect=fake_fetch_lineups), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={"opponent batter": {"vs_R": 0.2, "vs_L": 0.21}}), \
         patch("run_pipeline.build_pitcher_record", side_effect=fake_build_pitcher_record), \
         patch("run_pipeline.init_db"), \
         patch("run_pipeline.load_history_into_db"), \
         patch("run_pipeline.get_db", return_value=MagicMock()), \
         patch("run_pipeline.lock_due_picks", return_value=0), \
         patch("run_pipeline.seed_picks", return_value=0), \
         patch("run_pipeline.export_db_to_history"), \
         patch("run_pipeline._write_steam"):
        run_pipeline.run("2026-04-01")

    assert requested_lineup_teams == ["Opponent Team"]


def test_tracked_picks_from_history_prefers_locked_values(tmp_path, monkeypatch):
    import run_pipeline

    history_path = tmp_path / "picks_history.json"
    history_path.write_text(json.dumps([
        {
            "date": "2026-04-28",
            "pitcher": "Tracked Pitcher",
            "team": "SEA",
            "opp_team": "CLE",
            "side": "over",
            "verdict": "FIRE 1u",
            "raw_verdict": "FIRE 2u",
            "actionable_verdict": "FIRE 1u",
            "quality_gate_level": "capped",
            "input_quality_flags": ["unrated_umpire"],
            "verdict_cap_reason": "1 soft input flag: unrated_umpire",
            "data_maturity": {"umpire": "unknown"},
            "locked_verdict": "FIRE 2u",
            "k_line": 5.5,
            "locked_k_line": 6.5,
            "odds": -105,
            "locked_odds": -118,
            "adj_ev": 0.08,
            "raw_adj_ev": 0.17,
            "locked_adj_ev": 0.17,
            "result": "win",
            "actual_ks": 8,
            "pnl": 1.0,
            "locked_at": "2026-04-28T23:15:00Z",
        },
        {
            "date": "2026-04-29",
            "pitcher": "Other Date",
            "side": "under",
            "verdict": "LEAN",
        },
    ]))
    monkeypatch.setattr(run_pipeline, "HISTORY_PATH", history_path)

    picks = run_pipeline._tracked_picks_from_history("2026-04-28")

    assert picks == [
        {
            "date": "2026-04-28",
            "pitcher": "Tracked Pitcher",
            "team": "SEA",
            "opp_team": "CLE",
            "side": "over",
            "display_side": "OVER",
            "verdict": "FIRE 1u",
            "raw_verdict": "FIRE 2u",
            "actionable_verdict": "FIRE 1u",
            "quality_gate_level": "capped",
            "input_quality_flags": ["unrated_umpire"],
            "verdict_cap_reason": "1 soft input flag: unrated_umpire",
            "data_maturity": {"umpire": "unknown"},
            "locked_verdict": "FIRE 2u",
            "display_verdict": "FIRE 2u",
            "k_line": 5.5,
            "locked_k_line": 6.5,
            "display_k_line": 6.5,
            "odds": -105,
            "locked_odds": -118,
            "display_odds": -118,
            "adj_ev": 0.08,
            "raw_adj_ev": 0.17,
            "locked_adj_ev": 0.17,
            "display_adj_ev": 0.17,
            "edge": None,
            "ev": None,
            "result": "win",
            "actual_ks": 8,
            "pnl": 1.0,
            "locked_at": "2026-04-28T23:15:00Z",
            "status": "locked",
            "game_time": None,
            "data_complete": None,
        },
    ]


def test_enrich_archives_with_tracked_picks_updates_existing_archives(tmp_path, monkeypatch):
    import run_pipeline

    processed_dir = tmp_path / "processed"
    processed_dir.mkdir()
    archive_path = processed_dir / "2026-04-28.json"
    today_path = processed_dir / "today.json"
    archive_path.write_text(json.dumps({
        "date": "2026-04-28",
        "pitchers": [{"pitcher": "Tracked Pitcher", "game_time": "2026-04-28T23:10:00Z"}],
    }))
    today_path.write_text(json.dumps({
        "date": "2026-04-28",
        "pitchers": [{"pitcher": "Tracked Pitcher", "game_time": "2026-04-28T23:10:00Z"}],
    }))
    history_path = tmp_path / "picks_history.json"
    history_path.write_text(json.dumps([
        {
            "date": "2026-04-28",
            "pitcher": "Tracked Pitcher",
            "team": "SEA",
            "opp_team": "CLE",
            "side": "under",
            "verdict": "FIRE 1u",
            "locked_verdict": "FIRE 1u",
            "locked_at": "2026-04-28T23:15:00Z",
        },
    ]))
    monkeypatch.setattr(run_pipeline, "OUTPUT_PATH", today_path)
    monkeypatch.setattr(run_pipeline, "HISTORY_PATH", history_path)

    updated = run_pipeline._enrich_archives_with_tracked_picks()

    assert updated == 2
    archive = json.loads(archive_path.read_text())
    today = json.loads(today_path.read_text())
    assert archive["tracked_picks"][0]["pitcher"] == "Tracked Pitcher"
    assert archive["tracked_picks"][0]["display_side"] == "UNDER"
    assert archive["pitchers"][0]["tracked_picks"][0]["display_verdict"] == "FIRE 1u"
    assert today["tracked_picks"][0]["display_side"] == "UNDER"


def test_run_forwards_resolved_park_factor_to_build_pitcher_record(tmp_path):
    import run_pipeline
    run_pipeline._batter_stats_cache = None

    out_path = tmp_path / "today.json"
    park_factors_path = tmp_path / "park_factors.json"
    park_factors_path.write_text(json.dumps({"_source": {}, "factors": {"SEA": 1.04}}))

    prop = _sample_prop_for("Park Factor Pitcher")
    stats = _sample_stats_for("Seattle Mariners", "Opp Team")
    stats["park_team"] = "Seattle Mariners"
    captured = {}

    def fake_build_pitcher_record(
        odds,
        stats,
        ump_k_adj,
        *,
        park_factor=None,
        swstr_data=None,
        lineup=None,
        batter_stats=None,
    ):
        captured["park_factor"] = park_factor
        return {
            "pitcher": odds["pitcher"],
            "team": stats["team"],
            "game_time": odds["game_time"],
            "lambda": 4.2,
            "ev_over": {"verdict": "LEAN"},
        }

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch.object(run_pipeline, "PARK_FACTORS_PATH", park_factors_path), \
         patch("run_pipeline.fetch_odds", return_value=[prop]), \
         patch("run_pipeline.fetch_stats", return_value=({"Park Factor Pitcher": stats}, {})), \
         patch("run_pipeline.fetch_swstr", return_value={"Park Factor Pitcher": {"swstr_pct": 0.110, "career_swstr_pct": None}}), \
         patch("run_pipeline.fetch_umpires", return_value=({"Park Factor Pitcher": 0.0}, {"hp_count_fetched": 0, "pitcher_nonzero_count": 0})), \
         patch("run_pipeline.build_pitcher_record", side_effect=fake_build_pitcher_record), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}), \
         patch("run_pipeline.init_db"), \
         patch("run_pipeline.load_history_into_db"), \
         patch("run_pipeline.get_db", return_value=MagicMock()), \
         patch("run_pipeline.lock_due_picks", return_value=0), \
         patch("run_pipeline.seed_picks", return_value=0), \
         patch("run_pipeline.export_db_to_history"):
        run_pipeline.run("2026-04-01")

    assert captured["park_factor"] == pytest.approx(1.04)


def test_resolve_park_factor_defaults_to_one_for_unknown_team():
    import run_pipeline

    assert run_pipeline._resolve_park_factor("Unknown Team", {"SEA": 1.04}, "Test Pitcher") == 1.0


def test_resolve_park_factor_defaults_to_one_for_invalid_value():
    import run_pipeline

    assert run_pipeline._resolve_park_factor("Seattle Mariners", {"SEA": float("nan")}, "Test Pitcher") == 1.0


def test_run_park_factor_affects_real_lambda_across_parks(tmp_path):
    import run_pipeline
    run_pipeline._batter_stats_cache = None

    props = [
        _sample_prop_for("Rockies Pitcher"),
        _sample_prop_for("Mariners Pitcher"),
    ]
    stats_map = {
        "Rockies Pitcher": {**_sample_stats_for("Colorado Rockies", "Los Angeles Dodgers"), "park_team": "Colorado Rockies"},
        "Mariners Pitcher": {**_sample_stats_for("Seattle Mariners", "Texas Rangers"), "park_team": "Seattle Mariners"},
    }
    swstr_map = {
        "Rockies Pitcher": {"swstr_pct": 0.110, "career_swstr_pct": None},
        "Mariners Pitcher": {"swstr_pct": 0.110, "career_swstr_pct": None},
        "__meta__": {"current_usable": True, "career_usable": True},
    }
    ump_map = {"Rockies Pitcher": 0.25, "Mariners Pitcher": 0.25}

    out = {}
    def spy_write_output(date_str, records, props_available, ump_diagnostics=None, data_warnings=None, connection_health=None, batter_split_collection=None, quality_gate_summary=None):
        out["records"] = records

    park_factors_path = tmp_path / "park_factors.json"
    park_factors_path.write_text(json.dumps({
        "_source": {},
        "factors": {"COL": 0.96, "SEA": 1.04},
    }))

    with patch.object(run_pipeline, "OUTPUT_PATH", tmp_path / "today.json"), \
         patch.object(run_pipeline, "PARK_FACTORS_PATH", park_factors_path), \
         patch("run_pipeline.fetch_odds", return_value=props), \
         patch("run_pipeline.fetch_stats", return_value=(stats_map, {})), \
         patch("run_pipeline.fetch_swstr", return_value=swstr_map), \
         patch("run_pipeline.fetch_umpires", return_value=(ump_map, {"hp_count_fetched": 2, "pitcher_nonzero_count": 2})), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}), \
         patch("run_pipeline._merge_with_locked_snapshots", side_effect=lambda records, date_str, now: records), \
         patch("run_pipeline._write_output", side_effect=spy_write_output), \
         patch("run_pipeline._write_steam"), \
         patch("run_pipeline.init_db"), \
         patch("run_pipeline.load_history_into_db"), \
         patch("run_pipeline.get_db", return_value=MagicMock()), \
         patch("run_pipeline.lock_due_picks", return_value=0), \
         patch("run_pipeline.seed_picks", return_value=0), \
         patch("run_pipeline.export_db_to_history"):
        run_pipeline.run("2026-04-01")

    by_pitcher = {row["pitcher"]: row for row in out["records"]}
    assert by_pitcher["Rockies Pitcher"]["park_factor"] == pytest.approx(0.96)
    assert by_pitcher["Mariners Pitcher"]["park_factor"] == pytest.approx(1.04)
    assert by_pitcher["Rockies Pitcher"]["raw_lambda"] < by_pitcher["Mariners Pitcher"]["raw_lambda"]


def test_data_complete_false_when_ump_map_all_zero(tmp_path):
    """Regression (Task A3, 2026-04-17): when fetch_umpires returns all-zero
    values (no officials posted yet, or no career_k_rates match), ump_ok
    must be False and data_complete on the written record must be False.

    Before the fix, ump_ok stayed True whenever fetch_umpires didn't raise —
    which meant 447/447 historical picks were marked data_complete=True
    even though ump signal was effectively absent. Going-forward only:
    historical rows are not rewritten (see docs/data-caveats.md).
    """
    import run_pipeline
    run_pipeline._batter_stats_cache = None
    out_path = tmp_path / "today.json"

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=[_sample_prop()]), \
         patch("run_pipeline.fetch_stats", return_value=({"Test Pitcher": _sample_stats()}, {})), \
         patch("run_pipeline.fetch_swstr", return_value={"Test Pitcher": {"swstr_pct": 0.110, "career_swstr_pct": None}}), \
         patch("run_pipeline.fetch_umpires", return_value=({"Test Pitcher": 0.0}, {"hp_count_fetched": 0, "pitcher_nonzero_count": 0})), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}), \
         patch("run_pipeline.init_db"), \
         patch("run_pipeline.load_history_into_db"), \
         patch("run_pipeline.get_db", return_value=MagicMock()), \
         patch("run_pipeline.lock_due_picks", return_value=0), \
         patch("run_pipeline.seed_picks", return_value=0), \
         patch("run_pipeline.export_db_to_history"):
        run_pipeline.run("2026-04-01")

    data = json.loads(out_path.read_text())
    assert len(data["pitchers"]) == 1
    assert data["pitchers"][0]["data_complete"] is False, (
        "Expected data_complete=False when ump_map is all-zero "
        "(no real ump adjustment signal)"
    )


def test_data_complete_true_when_ump_map_has_nonzero(tmp_path):
    """Mirror of the above: when at least one pitcher has a real nonzero
    ump adjustment, ump_ok=True and data_complete=True (assuming other
    inputs are also OK)."""
    import run_pipeline
    run_pipeline._batter_stats_cache = None
    out_path = tmp_path / "today.json"

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=[_sample_prop()]), \
         patch("run_pipeline.fetch_stats", return_value=({"Test Pitcher": _sample_stats()}, {})), \
         patch("run_pipeline.fetch_swstr", return_value={
             "Test Pitcher": {"swstr_pct": 0.110, "career_swstr_pct": 0.105},
             "__meta__": {"current_usable": True, "career_usable": True},
         }), \
         patch("run_pipeline.fetch_umpires", return_value=({"Test Pitcher": 0.25}, {"hp_count_fetched": 1, "pitcher_nonzero_count": 1})), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}), \
         patch("run_pipeline.init_db"), \
         patch("run_pipeline.load_history_into_db"), \
         patch("run_pipeline.get_db", return_value=MagicMock()), \
         patch("run_pipeline.lock_due_picks", return_value=0), \
         patch("run_pipeline.seed_picks", return_value=0), \
         patch("run_pipeline.export_db_to_history"):
        run_pipeline.run("2026-04-01")

    data = json.loads(out_path.read_text())
    assert len(data["pitchers"]) == 1
    assert data["pitchers"][0]["data_complete"] is True


def test_row_data_complete_true_when_pitcher_missing_career_but_transport_is_live():
    from run_pipeline import _row_data_complete

    assert _row_data_complete(
        swstr_meta={"current_usable": True, "career_usable": True},
        swstr_row={"swstr_pct": 0.11, "career_swstr_pct": None},
        ump_k_adj=0.25,
    ) is True


def test_row_data_complete_false_when_swstr_transport_is_globally_unusable():
    from run_pipeline import _row_data_complete

    assert _row_data_complete(
        swstr_meta={"current_usable": True, "career_usable": False},
        swstr_row={"swstr_pct": 0.11, "career_swstr_pct": None},
        ump_k_adj=0.25,
    ) is False


def test_row_data_complete_false_when_pitcher_has_no_real_ump_coverage():
    from run_pipeline import _row_data_complete

    assert _row_data_complete(
        swstr_meta={"current_usable": True, "career_usable": True},
        swstr_row={"swstr_pct": 0.11, "career_swstr_pct": None},
        ump_k_adj=0.0,
    ) is False


def test_row_data_complete_true_when_row_inputs_are_live():
    from run_pipeline import _row_data_complete

    assert _row_data_complete(
        swstr_meta={"current_usable": True, "career_usable": True},
        swstr_row={"swstr_pct": 0.11, "career_swstr_pct": None},
        ump_k_adj=0.25,
    ) is True


def test_data_complete_is_row_specific_for_mixed_slate(tmp_path):
    import run_pipeline
    run_pipeline._batter_stats_cache = None

    props = [
        _sample_prop_for("Covered Pitcher"),
        _sample_prop_for("Missing Coverage Pitcher"),
    ]
    stats_map = {
        "Covered Pitcher": _sample_stats_for("Covered Team", "Opp A"),
        "Missing Coverage Pitcher": _sample_stats_for("Missing Team", "Opp B"),
    }
    swstr_map = {
        "Covered Pitcher": {"swstr_pct": 0.110, "career_swstr_pct": 0.105},
        "Missing Coverage Pitcher": {"swstr_pct": 0.112, "career_swstr_pct": 0.109},
        "__meta__": {"current_usable": True, "career_usable": True},
    }
    ump_map = {
        "Covered Pitcher": 0.25,
        "Missing Coverage Pitcher": 0.0,
    }

    def fake_build_pitcher_record(odds, stats, ump_k_adj, *, swstr_data, lineup, batter_stats, park_factor):
        return {
            "pitcher": odds["pitcher"],
            "team": stats["team"],
            "game_time": odds["game_time"],
            "lambda": 4.2,
            "ev_over": {"verdict": "LEAN"},
            "ump_k_adj": ump_k_adj,
            "swstr_pct": swstr_data["swstr_pct"],
            "career_swstr_pct": swstr_data["career_swstr_pct"],
            "park_factor": park_factor,
        }

    captured = {}
    def spy_write_output(date_str, records, props_available, ump_diagnostics=None, data_warnings=None, connection_health=None, batter_split_collection=None, quality_gate_summary=None):
        captured["date_str"] = date_str
        captured["records"] = records
        captured["props_available"] = props_available
        captured["ump_diagnostics"] = ump_diagnostics
        captured["data_warnings"] = data_warnings
        captured["connection_health"] = connection_health

    with patch.object(run_pipeline, "OUTPUT_PATH", tmp_path / "today.json"), \
         patch("run_pipeline.fetch_odds", return_value=props), \
         patch("run_pipeline.fetch_stats", return_value=(stats_map, {})), \
         patch("run_pipeline.fetch_swstr", return_value=swstr_map), \
         patch("run_pipeline.fetch_umpires", return_value=(ump_map, {"hp_count_fetched": 2, "pitcher_nonzero_count": 1})), \
         patch("run_pipeline.build_pitcher_record", side_effect=fake_build_pitcher_record), \
         patch("run_pipeline._merge_with_locked_snapshots", side_effect=lambda records, date_str, now: records), \
         patch("run_pipeline._write_output", side_effect=spy_write_output), \
         patch("run_pipeline._write_steam"), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}), \
         patch("run_pipeline.init_db"), \
         patch("run_pipeline.load_history_into_db"), \
         patch("run_pipeline.get_db", return_value=MagicMock()), \
         patch("run_pipeline.lock_due_picks", return_value=0), \
         patch("run_pipeline.seed_picks", return_value=0), \
         patch("run_pipeline.export_db_to_history"):
        run_pipeline.run("2026-04-01")

    assert captured["date_str"] == "2026-04-01"
    assert captured["props_available"] is True
    by_pitcher = {row["pitcher"]: row for row in captured["records"]}
    assert by_pitcher["Covered Pitcher"]["data_complete"] is True
    assert by_pitcher["Covered Pitcher"]["umpire_has_rating"] is True
    assert by_pitcher["Missing Coverage Pitcher"]["data_complete"] is False


def test_run_attaches_confirmed_unrated_umpire_metadata(tmp_path):
    import run_pipeline
    run_pipeline._batter_stats_cache = None

    props = [_sample_prop_for("Unrated Ump Pitcher")]
    stats_map = {"Unrated Ump Pitcher": _sample_stats_for("Seattle Mariners", "Minnesota Twins")}
    swstr_map = {
        "Unrated Ump Pitcher": {"swstr_pct": 0.110, "career_swstr_pct": 0.105},
        "__meta__": {"current_usable": True, "career_usable": True},
    }
    ump_diag = {
        "hp_count_fetched": 1,
        "pitcher_nonzero_count": 0,
        "pitcher_with_hp_count": 1,
        "pitcher_rated_count": 0,
        "umpire_by_pitcher": {"Unrated Ump Pitcher": "Dexter Kelley"},
        "rated_umpire_by_pitcher": {"Unrated Ump Pitcher": False},
        "missing_career_rate_umpires": ["Dexter Kelley"],
    }

    def fake_build_pitcher_record(odds, stats, ump_k_adj, *, swstr_data, lineup, batter_stats, park_factor):
        return {
            "pitcher": odds["pitcher"],
            "team": stats["team"],
            "game_time": odds["game_time"],
            "lambda": 4.2,
            "ev_over": {"verdict": "LEAN"},
            "ump_k_adj": ump_k_adj,
            "swstr_pct": swstr_data["swstr_pct"],
            "career_swstr_pct": swstr_data["career_swstr_pct"],
            "park_factor": park_factor,
        }

    captured = {}
    def spy_write_output(date_str, records, props_available, ump_diagnostics=None, data_warnings=None, connection_health=None, batter_split_collection=None, quality_gate_summary=None):
        captured["records"] = records
        captured["ump_diagnostics"] = ump_diagnostics

    with patch.object(run_pipeline, "OUTPUT_PATH", tmp_path / "today.json"), \
         patch("run_pipeline.fetch_odds", return_value=props), \
         patch("run_pipeline.fetch_stats", return_value=(stats_map, {})), \
         patch("run_pipeline.fetch_swstr", return_value=swstr_map), \
         patch("run_pipeline.fetch_umpires", return_value=({"Unrated Ump Pitcher": 0.0}, ump_diag)), \
         patch("run_pipeline.build_pitcher_record", side_effect=fake_build_pitcher_record), \
         patch("run_pipeline._merge_with_locked_snapshots", side_effect=lambda records, date_str, now: records), \
         patch("run_pipeline._write_output", side_effect=spy_write_output), \
         patch("run_pipeline._write_steam"), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}), \
         patch("run_pipeline.reset_db"), \
         patch("run_pipeline.init_db"), \
         patch("run_pipeline.load_history_into_db"), \
         patch("run_pipeline.get_db", return_value=MagicMock()), \
         patch("run_pipeline.lock_due_picks", return_value=0), \
         patch("run_pipeline.seed_picks", return_value=0), \
         patch("run_pipeline.export_db_to_history"):
        run_pipeline.run("2026-04-01")

    record = captured["records"][0]
    assert record["umpire"] == "Dexter Kelley"
    assert record["umpire_has_rating"] is False
    assert record["ump_k_adj"] == 0.0
    assert captured["ump_diagnostics"]["missing_career_rate_umpires"] == ["Dexter Kelley"]


def test_fetch_umpires_receives_props_with_team_populated_from_stats(tmp_path):
    """Regression (re-audit 2026-04-23): fetch_odds emits team='' and opp_team=''
    because TheRundown's participant list has no home/away flag (see commit
    79bf3dc, 2026-04-01). fetch_stats resolves team/opp_team via the MLB
    schedule side loop. The pipeline must backfill those fields onto props
    from stats_map BEFORE calling fetch_umpires — fetch_umpires team-matches
    on prop['team'] / prop['opp_team'] against ABBR_TO_NAME_SUBSTR substrings.
    Without the backfill, every pitcher silently hits ump_k_adj=0.0 and the
    entire umpire signal is dead.

    Dead-signal window before this fix: 2026-04-01 → 2026-04-23 (601/601
    stored picks had ump_k_adj=0). See docs/data-caveats.md."""
    import run_pipeline
    run_pipeline._batter_stats_cache = None
    out_path = tmp_path / "today.json"

    seen_by_fetch_umpires: list[dict] = []
    def spy_fetch_umpires(props, date_str):
        # Snapshot what fetch_umpires sees at call time so we can assert
        # team fields are populated before the function reads them.
        seen_by_fetch_umpires.extend(
            {"pitcher": p["pitcher"],
             "team": p.get("team", ""),
             "opp_team": p.get("opp_team", "")}
            for p in props
        )
        ump_map = {p["pitcher"]: 0.5 for p in props}
        diagnostics = {
            "hp_count_fetched":      len(props),
            "pitcher_nonzero_count": len(ump_map),
        }
        return ump_map, diagnostics

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=[_sample_prop()]), \
         patch("run_pipeline.fetch_stats", return_value=({"Test Pitcher": _sample_stats()}, {})), \
         patch("run_pipeline.fetch_swstr", return_value={"Test Pitcher": {"swstr_pct": 0.110, "career_swstr_pct": None}}), \
         patch("run_pipeline.fetch_umpires", side_effect=spy_fetch_umpires), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}), \
         patch("run_pipeline.init_db"), \
         patch("run_pipeline.load_history_into_db"), \
         patch("run_pipeline.get_db", return_value=MagicMock()), \
         patch("run_pipeline.lock_due_picks", return_value=0), \
         patch("run_pipeline.seed_picks", return_value=0), \
         patch("run_pipeline.export_db_to_history"):
        run_pipeline.run("2026-04-01")

    assert len(seen_by_fetch_umpires) == 1, (
        f"fetch_umpires should have been called once; got {len(seen_by_fetch_umpires)}"
    )
    assert seen_by_fetch_umpires[0]["team"] == "Test Team", (
        f"fetch_umpires received team={seen_by_fetch_umpires[0]['team']!r} — expected "
        f"'Test Team' (the value fetch_stats resolved). Pipeline must backfill "
        f"team/opp_team onto props from stats_map before fetch_umpires runs."
    )
    assert seen_by_fetch_umpires[0]["opp_team"] == "Opp Team", (
        f"fetch_umpires received opp_team={seen_by_fetch_umpires[0]['opp_team']!r} — "
        f"expected 'Opp Team' from stats_map backfill."
    )


def test_run_records_feature_build_failures_in_connection_health(tmp_path):
    import run_pipeline
    run_pipeline._batter_stats_cache = None

    prop = _sample_prop_for("Build Failure Pitcher")
    captured = {}

    def fake_write_output(date_str, records, props_available, **kwargs):
        captured["connection_health"] = kwargs.get("connection_health")

    with patch.object(run_pipeline, "OUTPUT_PATH", tmp_path / "today.json"), \
         patch("run_pipeline.fetch_odds", return_value=[prop]), \
         patch("run_pipeline.fetch_stats", return_value=({"Build Failure Pitcher": _sample_stats()}, {})), \
         patch("run_pipeline.fetch_swstr", return_value={
             "Build Failure Pitcher": {"swstr_pct": 0.110, "career_swstr_pct": 0.105},
             "__meta__": {"current_usable": True, "career_usable": True},
         }), \
         patch("run_pipeline.fetch_umpires", return_value=(
             {"Build Failure Pitcher": 0.25},
             {"hp_count_fetched": 1, "pitcher_nonzero_count": 1},
         )), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}), \
         patch("run_pipeline.build_pitcher_record", side_effect=RuntimeError("bad feature payload")), \
         patch("run_pipeline._write_output", side_effect=fake_write_output), \
         patch("run_pipeline._write_steam"), \
         patch("run_pipeline.init_db"), \
         patch("run_pipeline.load_history_into_db"), \
         patch("run_pipeline.get_db", return_value=MagicMock()), \
         patch("run_pipeline.lock_due_picks", return_value=0), \
         patch("run_pipeline.seed_picks", return_value=0), \
         patch("run_pipeline.export_db_to_history"):
        run_pipeline.run("2026-04-01")

    assert captured["connection_health"]["feature_build_failures_count"] == 1
    assert captured["connection_health"]["missing_stats_count"] == 0


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


def test_run_does_not_write_empty_output_when_odds_fetch_fails(tmp_path):
    """A provider/auth failure is different from a clean empty market response."""
    import run_pipeline
    out_path = tmp_path / "today.json"

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", side_effect=RuntimeError("401 Unauthorized")):
        run_pipeline.run("2026-04-01")

    assert not out_path.exists()


def test_run_calls_lock_due_picks(tmp_path):
    """run() should call lock_due_picks before seeding picks."""
    import run_pipeline
    run_pipeline._batter_stats_cache = None
    out_path = tmp_path / "today.json"
    lock_calls = []
    db_events = []

    def mock_lock(conn, now, lock_window_minutes=30, lock_all_past=False):
        lock_calls.append({"lock_all_past": lock_all_past})
        return 0

    with patch.object(run_pipeline, "OUTPUT_PATH", out_path), \
         patch("run_pipeline.fetch_odds", return_value=[_sample_prop()]), \
         patch("run_pipeline.fetch_stats", return_value=({"Test Pitcher": _sample_stats()}, {})), \
         patch("run_pipeline.fetch_swstr", return_value={"Test Pitcher": {"swstr_pct": 0.110, "career_swstr_pct": None}}), \
         patch("run_pipeline.fetch_umpires", return_value=({"Test Pitcher": 0.0}, {"hp_count_fetched": 0, "pitcher_nonzero_count": 0})), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}), \
         patch("run_pipeline.lock_due_picks", mock_lock), \
         patch("run_pipeline.reset_db", side_effect=lambda: db_events.append("reset")), \
         patch("run_pipeline.init_db", side_effect=lambda: db_events.append("init")), \
         patch("run_pipeline.load_history_into_db", side_effect=lambda: db_events.append("load")), \
         patch("run_pipeline.get_db", return_value=MagicMock()), \
         patch("run_pipeline.seed_picks", return_value=0), \
         patch("run_pipeline.export_db_to_history"), \
         patch("run_pipeline._write_archive"):
        run_pipeline.run("2026-04-01")

    assert len(lock_calls) >= 1
    assert lock_calls[0]["lock_all_past"] is False
    assert db_events == ["reset", "init", "load"]


def test_grading_run_calls_lock_all_past(tmp_path):
    """Grading run should call lock_due_picks(lock_all_past=True)."""
    import run_pipeline
    lock_calls = []

    def mock_lock(conn, now, lock_window_minutes=30, lock_all_past=False):
        lock_calls.append({"lock_all_past": lock_all_past})
        return 0

    with patch("run_pipeline.lock_due_picks", mock_lock), \
         patch("run_pipeline.reset_db"), \
         patch("run_pipeline.init_db"), \
         patch("run_pipeline.load_history_into_db"), \
         patch("run_pipeline.fetch_results_run"), \
         patch("run_pipeline.export_db_to_history"), \
         patch("run_pipeline._enrich_archives_with_tracked_picks"), \
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
    entries = json.loads(index.read_text())["dates"]
    assert any(entry["date"] == "2026-04-12" for entry in entries)


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
         patch("run_pipeline.fetch_stats", return_value=({"Tomorrow Pitcher": _sample_stats()}, {})), \
         patch("run_pipeline.fetch_swstr", return_value={"Tomorrow Pitcher": {"swstr_pct": 0.11, "career_swstr_pct": None}}), \
         patch("run_pipeline.fetch_umpires", return_value=({"Tomorrow Pitcher": 0.0}, {"hp_count_fetched": 0, "pitcher_nonzero_count": 0})), \
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
         patch("run_pipeline.fetch_stats", return_value=({"Tomorrow Pitcher": _sample_stats()}, {})), \
         patch("run_pipeline.fetch_swstr", return_value={"Tomorrow Pitcher": {"swstr_pct": 0.11, "career_swstr_pct": None}}), \
         patch("run_pipeline.fetch_umpires", return_value=({"Tomorrow Pitcher": 0.0}, {"hp_count_fetched": 0, "pitcher_nonzero_count": 0})), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}):
        run_pipeline._run_preview("2026-04-12")

    data = json.loads(today_path.read_text())
    assert data["date"] == "2026-04-11", "today.json date was overwritten by preview run"
    assert data["pitchers"][0]["pitcher"] == "Today Guy", "today.json pitchers were overwritten"


def test_preview_run_uses_neutral_ump_map_when_umpire_fetch_fails(tmp_path):
    """Preview should degrade to neutral umpires instead of crashing."""
    import run_pipeline
    run_pipeline._batter_stats_cache = None
    today_path = tmp_path / "today.json"
    preview_path = tmp_path / "preview_lines.json"

    prop = _sample_prop_for("Tomorrow Pitcher")
    captured = {}

    def fake_build_pitcher_record(odds, stats, ump_k_adj, **kwargs):
        captured["ump_k_adj"] = ump_k_adj
        return {
            "pitcher": odds["pitcher"],
            "team": stats["team"],
            "opp_team": stats["opp_team"],
            "game_time": odds["game_time"],
            "k_line": odds["k_line"],
            "lambda": 4.2,
            "ev_over": {"verdict": "PASS"},
            "ev_under": {"verdict": "PASS"},
        }

    with patch.object(run_pipeline, "OUTPUT_PATH", today_path), \
         patch.object(run_pipeline, "PREVIEW_PATH", preview_path), \
         patch("run_pipeline.fetch_odds", return_value=[prop]), \
         patch("run_pipeline.fetch_stats", return_value=({"Tomorrow Pitcher": _sample_stats()}, {})), \
         patch("run_pipeline.fetch_swstr", return_value={"Tomorrow Pitcher": {"swstr_pct": 0.11, "career_swstr_pct": None}}), \
         patch("run_pipeline.fetch_umpires", side_effect=RuntimeError("ump source down")), \
         patch("run_pipeline.fetch_lineups_for_pitcher", return_value=None), \
         patch("run_pipeline.fetch_batter_stats_cached", return_value={}), \
         patch("run_pipeline.build_pitcher_record", side_effect=fake_build_pitcher_record):
        run_pipeline._run_preview("2026-04-12")

    dated = tmp_path / "2026-04-12.json"
    assert dated.exists()
    assert captured["ump_k_adj"] == 0.0


def test_write_archive_merges_other_date_bucket_into_existing_archive(tmp_path):
    """A run for today's slate can include a cross-midnight ET game from the
    prior date. That must update the matching prior-date row without replacing
    the entire prior-date archive with only the late game."""
    import run_pipeline

    today_path = tmp_path / "today.json"
    prior_archive = tmp_path / "2026-04-27.json"
    prior_archive.write_text(json.dumps({
        "generated_at": "old",
        "date": "2026-04-27",
        "props_available": True,
        "data_warnings": ["old warning"],
        "pitchers": [
            {"pitcher": "Early Pitcher", "game_time": "2026-04-27T23:05:00Z", "lambda": 4.2},
            {"pitcher": "Late Pitcher", "game_time": "2026-04-28T02:10:00Z", "lambda": 5.0},
        ],
        "connection_health": {"records_built": 2},
    }))

    output = {
        "generated_at": "new",
        "date": "2026-04-28",
        "props_available": True,
        "data_warnings": [],
        "pitchers": [
            {"pitcher": "Late Pitcher", "game_time": "2026-04-28T02:10:00Z", "lambda": 5.6},
            {"pitcher": "Today Pitcher", "game_time": "2026-04-28T23:05:00Z", "lambda": 6.1},
        ],
        "connection_health": {"records_built": 2},
    }

    with patch.object(run_pipeline, "OUTPUT_PATH", today_path):
        run_pipeline._write_archive(output, "2026-04-28")

    merged = json.loads(prior_archive.read_text())
    assert merged["generated_at"] == "old"
    assert merged["connection_health"] == {"records_built": 2}
    assert [p["pitcher"] for p in merged["pitchers"]] == ["Early Pitcher", "Late Pitcher"]
    assert merged["pitchers"][1]["lambda"] == 5.6

    today = json.loads(today_path.read_text())
    assert [p["pitcher"] for p in today["pitchers"]] == ["Today Pitcher"]


def _mock_pick(pitcher="Cole", side="over", result="win", actual_ks=8,
               verdict="FIRE 1u", locked_verdict=None,
               k_line=6.5, locked_k_line=None,
               odds=-110, locked_odds=None, pnl=0.9091, date="2026-04-10"):
    return {
        "date": date, "pitcher": pitcher, "side": side,
        "result": result, "actual_ks": actual_ks,
        "verdict": verdict, "locked_verdict": locked_verdict,
        "k_line": k_line, "locked_k_line": locked_k_line,
        "odds": odds, "locked_odds": locked_odds,
        "pnl": pnl,
    }


def test_enrich_archives_with_results_injects_actual_ks_and_result(tmp_path):
    """_enrich_archives_with_results should write actual_ks, per-side result, and
    top-level result object into matching dated archive files."""
    import run_pipeline

    archive_path = tmp_path / "2026-04-10.json"
    archive_path.write_text(json.dumps({
        "date": "2026-04-10",
        "pitchers": [
            {
                "pitcher": "Cole",
                "k_line": 6.5,
                "ev_over":  {"verdict": "FIRE 1u", "adj_ev": 0.05},
                "ev_under": {"verdict": "PASS",    "adj_ev": -0.02},
            },
            {
                "pitcher": "Unmatched Pitcher",  # no graded pick — should be untouched
                "k_line": 5.5,
                "ev_over":  {"verdict": "PASS"},
                "ev_under": {"verdict": "LEAN"},
            },
        ],
    }))

    rows = [_mock_pick()]
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = rows

    # Point OUTPUT_PATH at a file whose parent is tmp_path so base_dir matches.
    with patch.object(run_pipeline, "OUTPUT_PATH", tmp_path / "today.json"), \
         patch("run_pipeline.get_db", return_value=mock_conn):
        run_pipeline._enrich_archives_with_results()

    data = json.loads(archive_path.read_text())
    cole = data["pitchers"][0]
    assert cole["actual_ks"] == 8
    assert cole["ev_over"]["result"] == "win"
    assert "result" not in cole["ev_under"], "PASS side should not be enriched"

    r = cole["result"]
    assert r["final_k"] == 8
    assert r["side_taken"] == "over"
    assert r["outcome"] == "win"
    assert r["line_at_bet"] == 6.5
    assert r["odds_at_bet"] == -110
    assert r["units_risked"] == 1.0
    assert r["units_won"] == pytest.approx(0.9091, abs=1e-4)

    # Unmatched pitcher should be left alone
    other = data["pitchers"][1]
    assert "actual_ks" not in other
    assert "result" not in other["ev_under"]
    assert "result" not in other


def test_enrich_archives_with_results_no_rows_is_noop(tmp_path):
    """When the DB has no graded picks, the function must return cleanly and
    not touch any archives. Also verifies safe DB-read-failure behavior."""
    import run_pipeline

    archive_path = tmp_path / "2026-04-10.json"
    original = {"date": "2026-04-10", "pitchers": [{"pitcher": "Cole", "ev_over": {}}]}
    archive_path.write_text(json.dumps(original))

    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = []

    with patch.object(run_pipeline, "OUTPUT_PATH", tmp_path / "today.json"), \
         patch("run_pipeline.get_db", return_value=mock_conn):
        run_pipeline._enrich_archives_with_results()

    # Archive must be byte-identical when no graded picks exist.
    assert json.loads(archive_path.read_text()) == original


def test_enrich_archives_with_results_skips_missing_archive(tmp_path):
    """Graded picks for a date with no archive file must not raise."""
    import run_pipeline

    rows = [_mock_pick(date="2026-03-01")]
    mock_conn = MagicMock()
    mock_conn.execute.return_value.fetchall.return_value = rows

    with patch.object(run_pipeline, "OUTPUT_PATH", tmp_path / "today.json"), \
         patch("run_pipeline.get_db", return_value=mock_conn):
        # Should not raise even though 2026-03-01.json does not exist.
        run_pipeline._enrich_archives_with_results()


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
         patch("run_pipeline.reset_db"), \
         patch("run_pipeline.init_db"), \
         patch("run_pipeline.load_history_into_db"), \
         patch("run_pipeline.lock_due_picks", return_value=0), \
         patch("run_pipeline.export_db_to_history"), \
         patch("run_pipeline._enrich_archives_with_tracked_picks"), \
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


# ── Tests: _verdict_stake ─────────────────────────────────────────────────────

class TestVerdictStake:
    def test_fire_2u(self):
        from run_pipeline import _verdict_stake
        assert _verdict_stake("FIRE 2u") == 2.0

    def test_fire_1u(self):
        from run_pipeline import _verdict_stake
        assert _verdict_stake("FIRE 1u") == 1.0

    def test_lean_is_zero(self):
        from run_pipeline import _verdict_stake
        assert _verdict_stake("LEAN") == 0.0

    def test_none_is_zero(self):
        from run_pipeline import _verdict_stake
        assert _verdict_stake(None) == 0.0


# ── Tests: _build_result_obj ──────────────────────────────────────────────────

class TestBuildResultObj:
    def test_fire_1u_win_at_minus_110(self):
        from run_pipeline import _build_result_obj
        pick = _mock_pick(verdict="FIRE 1u", result="win", actual_ks=8,
                          k_line=6.5, odds=-110, pnl=100/110)
        r = _build_result_obj(pick)
        assert r["outcome"] == "win"
        assert r["units_risked"] == 1.0
        assert r["units_won"] == pytest.approx(100/110, abs=1e-4)
        assert r["final_k"] == 8
        assert r["side_taken"] == "over"
        assert r["line_at_bet"] == 6.5
        assert r["odds_at_bet"] == -110

    def test_fire_2u_loss(self):
        from run_pipeline import _build_result_obj
        pick = _mock_pick(verdict="FIRE 2u", result="loss", actual_ks=5,
                          k_line=6.5, odds=-120, pnl=-1.0)
        r = _build_result_obj(pick)
        assert r["units_risked"] == 2.0
        assert r["units_won"] == pytest.approx(-2.0, abs=1e-4)
        assert r["outcome"] == "loss"

    def test_lean_units_are_zero(self):
        from run_pipeline import _build_result_obj
        pick = _mock_pick(verdict="LEAN", result="win", actual_ks=7,
                          k_line=5.5, odds=-110, pnl=100/110)
        r = _build_result_obj(pick)
        assert r["units_risked"] == 0.0
        assert r["units_won"] == 0.0
        assert r["outcome"] == "win"

    def test_locked_odds_take_precedence(self):
        from run_pipeline import _build_result_obj
        pick = _mock_pick(verdict="FIRE 1u", result="win", actual_ks=7,
                          k_line=6.5, odds=-110, locked_k_line=6.0, locked_odds=-115, pnl=100/115)
        r = _build_result_obj(pick)
        assert r["line_at_bet"] == 6.0
        assert r["odds_at_bet"] == -115

    def test_locked_verdict_takes_precedence(self):
        from run_pipeline import _build_result_obj
        pick = _mock_pick(verdict="LEAN", locked_verdict="FIRE 2u",
                          result="win", actual_ks=8, k_line=6.5, odds=-110, pnl=100/110)
        r = _build_result_obj(pick)
        assert r["units_risked"] == 2.0


# ── Tests: backfill_result_embeds ─────────────────────────────────────────────

def test_backfill_result_embeds_writes_result_objects(tmp_path):
    """backfill_result_embeds reads picks_history.json and embeds result objects
    into matching archive files."""
    import run_pipeline

    history = [
        {
            "date": "2026-04-10", "pitcher": "Cole", "side": "over",
            "result": "win", "actual_ks": 8,
            "verdict": "FIRE 1u", "locked_verdict": None,
            "k_line": 6.5, "locked_k_line": None,
            "odds": -110, "locked_odds": None, "pnl": 100/110,
        },
    ]
    history_path = tmp_path / "picks_history.json"
    history_path.write_text(json.dumps(history))

    archive_path = tmp_path / "processed" / "2026-04-10.json"
    archive_path.parent.mkdir()
    archive_path.write_text(json.dumps({
        "date": "2026-04-10",
        "pitchers": [
            {"pitcher": "Cole", "k_line": 6.5,
             "ev_over": {"verdict": "FIRE 1u"}, "ev_under": {"verdict": "PASS"}},
        ],
    }))

    with patch.object(run_pipeline, "HISTORY_PATH", history_path), \
         patch.object(run_pipeline, "OUTPUT_PATH", tmp_path / "processed" / "today.json"):
        n = run_pipeline.backfill_result_embeds()

    assert n == 1
    data = json.loads(archive_path.read_text())
    cole = data["pitchers"][0]
    assert cole["actual_ks"] == 8
    assert cole["ev_over"]["result"] == "win"
    r = cole["result"]
    assert r["final_k"] == 8
    assert r["side_taken"] == "over"
    assert r["outcome"] == "win"
    assert r["units_risked"] == 1.0


def test_backfill_result_embeds_skips_void_and_cancelled(tmp_path):
    """void and cancelled picks must not produce a result object."""
    import run_pipeline

    history = [
        {"date": "2026-04-10", "pitcher": "Cole", "side": "over",
         "result": "void", "actual_ks": None,
         "verdict": "FIRE 1u", "locked_verdict": None,
         "k_line": 6.5, "locked_k_line": None,
         "odds": -110, "locked_odds": None, "pnl": 0.0},
    ]
    history_path = tmp_path / "picks_history.json"
    history_path.write_text(json.dumps(history))

    archive_path = tmp_path / "processed" / "2026-04-10.json"
    archive_path.parent.mkdir()
    original = {"date": "2026-04-10", "pitchers": [
        {"pitcher": "Cole", "ev_over": {"verdict": "FIRE 1u"}, "ev_under": {"verdict": "PASS"}}
    ]}
    archive_path.write_text(json.dumps(original))

    with patch.object(run_pipeline, "HISTORY_PATH", history_path), \
         patch.object(run_pipeline, "OUTPUT_PATH", tmp_path / "processed" / "today.json"):
        n = run_pipeline.backfill_result_embeds()

    assert n == 0
    assert json.loads(archive_path.read_text()) == original


def test_backfill_result_embeds_missing_history_is_noop(tmp_path):
    """Missing picks_history.json must return 0 without raising."""
    import run_pipeline

    with patch.object(run_pipeline, "HISTORY_PATH", tmp_path / "nonexistent.json"), \
         patch.object(run_pipeline, "OUTPUT_PATH", tmp_path / "today.json"):
        n = run_pipeline.backfill_result_embeds()

    assert n == 0


def test_backfill_higher_stake_wins_tiebreak(tmp_path):
    """When a pitcher has both over (FIRE 2u win) and under (FIRE 1u loss), the
    result object should reflect the FIRE 2u pick as the primary."""
    import run_pipeline

    history = [
        {"date": "2026-04-10", "pitcher": "Cole", "side": "over",
         "result": "win", "actual_ks": 8,
         "verdict": "FIRE 2u", "locked_verdict": None,
         "k_line": 6.5, "locked_k_line": None, "odds": -120, "locked_odds": None, "pnl": 100/120},
        {"date": "2026-04-10", "pitcher": "Cole", "side": "under",
         "result": "loss", "actual_ks": 8,
         "verdict": "FIRE 1u", "locked_verdict": None,
         "k_line": 6.5, "locked_k_line": None, "odds": -110, "locked_odds": None, "pnl": -1.0},
    ]
    history_path = tmp_path / "picks_history.json"
    history_path.write_text(json.dumps(history))

    archive_path = tmp_path / "processed" / "2026-04-10.json"
    archive_path.parent.mkdir()
    archive_path.write_text(json.dumps({
        "date": "2026-04-10",
        "pitchers": [{"pitcher": "Cole", "k_line": 6.5,
                      "ev_over": {"verdict": "FIRE 2u"}, "ev_under": {"verdict": "FIRE 1u"}}],
    }))

    with patch.object(run_pipeline, "HISTORY_PATH", history_path), \
         patch.object(run_pipeline, "OUTPUT_PATH", tmp_path / "processed" / "today.json"):
        run_pipeline.backfill_result_embeds()

    data = json.loads(archive_path.read_text())
    r = data["pitchers"][0]["result"]
    assert r["side_taken"] == "over"
    assert r["units_risked"] == 2.0
    assert r["outcome"] == "win"


# ── Tests: _write_steam ───────────────────────────────────────────────────────

def _steam_pitcher(name="Gerrit Cole", k_line=7.5,
                   fd_over=-115, fd_under=-105,
                   game_time="2026-04-21T23:10:00Z"):
    return {
        "pitcher": name,
        "k_line": k_line,
        "game_time": game_time,
        "book_odds": {"FanDuel": {"over": fd_over, "under": fd_under}},
    }


def test_write_steam_creates_file_with_one_snapshot(tmp_path):
    """First call on a given date should create steam.json with one snapshot."""
    import run_pipeline

    steam_path = tmp_path / "steam.json"
    with patch.object(run_pipeline, "STEAM_PATH", steam_path):
        run_pipeline._write_steam([_steam_pitcher()], "2026-04-21")

    data = json.loads(steam_path.read_text())
    assert data["date"] == "2026-04-21"
    assert len(data["snapshots"]) == 1
    snap = data["snapshots"][0]
    assert "Gerrit Cole" in snap["pitchers"]
    assert snap["pitchers"]["Gerrit Cole"]["k_line"] == 7.5
    assert snap["pitchers"]["Gerrit Cole"]["FanDuel"]["over"] == -115


def test_write_steam_appends_snapshot_same_day(tmp_path):
    """Subsequent calls on the same day should append, not reset."""
    import run_pipeline

    steam_path = tmp_path / "steam.json"
    with patch.object(run_pipeline, "STEAM_PATH", steam_path):
        run_pipeline._write_steam([_steam_pitcher(fd_over=-115)], "2026-04-21")
        run_pipeline._write_steam([_steam_pitcher(fd_over=-120)], "2026-04-21")

    data = json.loads(steam_path.read_text())
    assert len(data["snapshots"]) == 2
    assert data["snapshots"][0]["pitchers"]["Gerrit Cole"]["FanDuel"]["over"] == -115
    assert data["snapshots"][1]["pitchers"]["Gerrit Cole"]["FanDuel"]["over"] == -120


def test_write_steam_resets_on_new_day(tmp_path):
    """Calling with a different date should reset snapshots to a fresh list."""
    import run_pipeline

    steam_path = tmp_path / "steam.json"
    with patch.object(run_pipeline, "STEAM_PATH", steam_path):
        run_pipeline._write_steam([_steam_pitcher()], "2026-04-20")
        run_pipeline._write_steam([_steam_pitcher()], "2026-04-21")

    data = json.loads(steam_path.read_text())
    assert data["date"] == "2026-04-21"
    assert len(data["snapshots"]) == 1


def test_write_steam_records_archive_dates_for_cross_midnight_et_games(tmp_path):
    """steam.json should advertise the ET archive dates covered by its snapshots."""
    import run_pipeline

    steam_path = tmp_path / "steam.json"
    late_game = _steam_pitcher(
        name="Late Night Pitcher",
        game_time="2026-04-28T00:05:00Z",
    )
    with patch.object(run_pipeline, "STEAM_PATH", steam_path):
        run_pipeline._write_steam([late_game], "2026-04-28")

    data = json.loads(steam_path.read_text())
    assert data["date"] == "2026-04-28"
    assert data["archive_dates"] == ["2026-04-27"]


def test_write_steam_skips_pitchers_without_book_odds(tmp_path):
    """Pitchers with null or empty book_odds must be omitted from the snapshot."""
    import run_pipeline

    steam_path = tmp_path / "steam.json"
    pitchers = [
        {"pitcher": "Cole",    "k_line": 7.5, "book_odds": {"FanDuel": {"over": -115, "under": -105}}},
        {"pitcher": "Webb",    "k_line": 6.5, "book_odds": None},
        {"pitcher": "Fried",   "k_line": 5.5, "book_odds": {}},
    ]
    with patch.object(run_pipeline, "STEAM_PATH", steam_path):
        run_pipeline._write_steam(pitchers, "2026-04-21")

    data = json.loads(steam_path.read_text())
    snap = data["snapshots"][0]["pitchers"]
    assert "Cole"  in snap
    assert "Webb"  not in snap
    assert "Fried" not in snap


def test_write_steam_no_snapshot_when_no_book_odds(tmp_path):
    """If no pitcher has book_odds, no snapshot entry should be appended."""
    import run_pipeline

    steam_path = tmp_path / "steam.json"
    with patch.object(run_pipeline, "STEAM_PATH", steam_path):
        run_pipeline._write_steam([{"pitcher": "Webb", "k_line": 6.5, "book_odds": None}],
                                  "2026-04-21")

    data = json.loads(steam_path.read_text())
    assert data["snapshots"] == []


# ── Tests: _apply_preview_openings + opening_odds_source (Task A2) ────────────

def test_apply_preview_openings_sets_source_preview_on_match():
    """When preview_lines has a matching entry with same k_line, opening_odds_source
    is promoted from 'first_seen' to 'preview' and opening_*_odds are overwritten
    with the 7pm overnight values."""
    import run_pipeline

    props = [{
        "pitcher":            "Gerrit Cole",
        "k_line":             7.5,
        "opening_over_odds":  -112,   # within-day opening from fetch_odds
        "opening_under_odds": -108,
        "opening_odds_source": "first_seen",
    }]
    preview_lines = {
        "Gerrit Cole": {"k_line": 7.5, "over_odds": -120, "under_odds": -100},
    }
    run_pipeline._apply_preview_openings(props, preview_lines)

    assert props[0]["opening_odds_source"] == "preview"
    assert props[0]["opening_over_odds"]  == -120
    assert props[0]["opening_under_odds"] == -100


def test_apply_preview_openings_leaves_source_first_seen_on_kline_shift():
    """If the k_line moved overnight, the 7pm preview opening is stale — we must
    NOT override opening_*_odds AND the source must remain 'first_seen'."""
    import run_pipeline

    props = [{
        "pitcher":            "Gerrit Cole",
        "k_line":             7.5,     # current line
        "opening_over_odds":  -112,
        "opening_under_odds": -108,
        "opening_odds_source": "first_seen",
    }]
    preview_lines = {
        "Gerrit Cole": {"k_line": 6.5,  # preview had a different line
                        "over_odds": -120, "under_odds": -100},
    }
    run_pipeline._apply_preview_openings(props, preview_lines)

    assert props[0]["opening_odds_source"] == "first_seen"
    assert props[0]["opening_over_odds"]  == -112   # unchanged
    assert props[0]["opening_under_odds"] == -108   # unchanged


def test_apply_preview_openings_leaves_source_first_seen_when_no_preview_match():
    """If preview_lines has no entry for this pitcher, source stays first_seen
    and opening_*_odds are untouched."""
    import run_pipeline

    props = [{
        "pitcher":            "Gerrit Cole",
        "k_line":             7.5,
        "opening_over_odds":  -112,
        "opening_under_odds": -108,
        "opening_odds_source": "first_seen",
    }]
    preview_lines = {}  # empty — preview step didn't fire

    run_pipeline._apply_preview_openings(props, preview_lines)

    assert props[0]["opening_odds_source"] == "first_seen"
    assert props[0]["opening_over_odds"]  == -112
    assert props[0]["opening_under_odds"] == -108


# ---------------------------------------------------------------------------
# Task A7: phantom-starter re-stamp. _restamp_starter_mismatch is the single
# authority for the `starter_mismatch` flag post-merge. It handles both
# freshly-built records (whose build_pitcher_record already set the flag
# correctly) AND locked snapshots from earlier runs (which predate any pitcher
# swap and need a fresh check against MLB's current probable).
# ---------------------------------------------------------------------------
def test_restamp_starter_mismatch_flips_locked_snapshot_on_phantom():
    """Locked snapshot with stale starter_mismatch=False gets flipped to True
    when MLB's current probable differs from the record's pitcher."""
    import run_pipeline
    records = [{
        "pitcher": "Chad Patrick",
        "team": "Detroit Tigers",
        "starter_mismatch": False,  # stale — seeded before the swap
    }]
    probables = {"Detroit Tigers": "Zack Littell"}
    run_pipeline._restamp_starter_mismatch(records, probables)
    assert records[0]["starter_mismatch"] is True


def test_restamp_starter_mismatch_stays_false_on_aligned_case():
    """Happy path: MLB probable matches the record's pitcher → flag stays False."""
    import run_pipeline
    records = [{
        "pitcher": "Gerrit Cole",
        "team": "New York Yankees",
        "starter_mismatch": False,
    }]
    probables = {"New York Yankees": "Gerrit Cole"}
    run_pipeline._restamp_starter_mismatch(records, probables)
    assert records[0]["starter_mismatch"] is False


def test_merge_with_locked_snapshots_replaces_scratched_upcoming_pitcher(tmp_path):
    """Pregame starter replacement should evict the stale upcoming card for that
    same game instead of carrying both pitchers forward."""
    import run_pipeline
    from datetime import datetime, timezone

    output_path = tmp_path / "today.json"
    existing = {
        "date": "2026-04-22",
        "pitchers": [{
            "pitcher": "Chad Patrick",
            "team": "Detroit Tigers",
            "opp_team": "Tampa Bay Rays",
            "game_time": "2026-04-22T23:10:00Z",
        }],
    }
    output_path.write_text(json.dumps(existing))

    fresh_records = [{
        "pitcher": "Zack Littell",
        "team": "Detroit Tigers",
        "opp_team": "Tampa Bay Rays",
        "game_time": "2026-04-22T23:10:00Z",
    }]

    with patch.object(run_pipeline, "OUTPUT_PATH", output_path):
        merged = run_pipeline._merge_with_locked_snapshots(
            fresh_records,
            "2026-04-22",
            datetime(2026, 4, 22, 18, 0, tzinfo=timezone.utc),
        )

    names = [p["pitcher"] for p in merged]
    assert names == ["Zack Littell"], (
        "Starter replacement before first pitch should replace the stale card "
        "for that game, not preserve both pitchers"
    )


def test_restamp_starter_mismatch_accent_insensitive():
    """Accented MLB name vs unaccented odds name → no mismatch."""
    import run_pipeline
    records = [{
        "pitcher": "Jose Berrios",
        "team": "Toronto Blue Jays",
        "starter_mismatch": False,
    }]
    probables = {"Toronto Blue Jays": "José Berríos"}
    run_pipeline._restamp_starter_mismatch(records, probables)
    assert records[0]["starter_mismatch"] is False


def test_restamp_starter_mismatch_leaves_flag_alone_when_no_probable():
    """MLB hasn't posted a probable for this team yet (None) — leave the
    existing flag untouched rather than falsely clearing a real mismatch."""
    import run_pipeline
    records = [{
        "pitcher": "Chad Patrick",
        "team": "Detroit Tigers",
        "starter_mismatch": True,  # set correctly upstream
    }]
    probables = {"Detroit Tigers": None}
    run_pipeline._restamp_starter_mismatch(records, probables)
    assert records[0]["starter_mismatch"] is True


def test_restamp_starter_mismatch_skips_team_not_in_map():
    """Team missing from probables_by_team (stale locked record from a past
    date, or MLB API blip) — leave flag untouched."""
    import run_pipeline
    records = [{
        "pitcher": "Shohei Ohtani",
        "team": "Los Angeles Dodgers",
        "starter_mismatch": False,
    }]
    probables = {"New York Yankees": "Gerrit Cole"}  # different team only
    run_pipeline._restamp_starter_mismatch(records, probables)
    assert records[0]["starter_mismatch"] is False  # unchanged


def test_restamp_starter_mismatch_empty_map_noop():
    """fetch_stats fell back to {} (API down) — helper should no-op cleanly."""
    import run_pipeline
    records = [{
        "pitcher": "Chad Patrick",
        "team": "Detroit Tigers",
        "starter_mismatch": False,
    }]
    run_pipeline._restamp_starter_mismatch(records, {})
    assert records[0]["starter_mismatch"] is False


def test_drop_pregame_starter_mismatches_suppresses_only_pregame_cards():
    import run_pipeline

    records = [
        {"pitcher": "Ghost Starter", "starter_mismatch": True, "game_state": "pregame"},
        {"pitcher": "Started Ghost", "starter_mismatch": True, "game_state": "in_progress"},
        {"pitcher": "Real Starter", "starter_mismatch": False, "game_state": "pregame"},
    ]

    kept, dropped = run_pipeline._drop_pregame_starter_mismatches(records)

    assert dropped == 1
    assert [r["pitcher"] for r in kept] == ["Started Ghost", "Real Starter"]


def test_drop_pregame_starter_mismatches_defaults_missing_game_state_to_pregame():
    import run_pipeline

    records = [
        {"pitcher": "Ghost Starter", "starter_mismatch": True},
        {"pitcher": "Real Starter", "starter_mismatch": False},
    ]

    kept, dropped = run_pipeline._drop_pregame_starter_mismatches(records)

    assert dropped == 1
    assert [r["pitcher"] for r in kept] == ["Real Starter"]
