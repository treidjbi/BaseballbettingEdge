from analytics.diagnostics.actual_opportunity_backfill import (
    build_actual_opportunity_backfill,
    extract_pitcher_opportunity,
)
from analytics.diagnostics.pitcher_k_outcome_dataset import actual_opportunity_lookup_key


def _schedule():
    return {
        "dates": [
            {
                "games": [
                    {
                        "gamePk": 100,
                        "gameDate": "2026-05-12T17:10:00Z",
                        "teams": {
                            "away": {"team": {"name": "New York Yankees"}},
                            "home": {"team": {"name": "Seattle Mariners"}},
                        },
                    },
                    {
                        "gamePk": 101,
                        "gameDate": "2026-05-12T22:40:00Z",
                        "teams": {
                            "away": {"team": {"name": "New York Yankees"}},
                            "home": {"team": {"name": "Seattle Mariners"}},
                        },
                    },
                ]
            }
        ]
    }


def _boxscore():
    return {
        "teams": {
            "away": {"pitchers": [], "players": {}},
            "home": {
                "pitchers": [1, 2],
                "players": {
                    "ID1": {
                        "person": {"fullName": "Bryan Woo"},
                        "stats": {
                            "pitching": {
                                "inningsPitched": "5.2",
                                "numberOfPitches": 91,
                                "battersFaced": 22,
                            }
                        },
                    },
                    "ID2": {
                        "person": {"fullName": "Seattle Reliever"},
                        "stats": {
                            "pitching": {
                                "inningsPitched": "1.1",
                                "numberOfPitches": 19,
                                "battersFaced": 5,
                            }
                        },
                    },
                },
            },
        }
    }


def test_extract_pitcher_opportunity_converts_mlb_fractional_innings():
    result = extract_pitcher_opportunity(_boxscore(), "home", "Bryan Woo")

    assert round(result["actual_ip"], 3) == 5.667
    assert result["actual_pitch_count"] == 91
    assert result["batters_faced"] == 22
    assert result["pitcher_match_type"] == "normalized_name"


def test_build_actual_opportunity_backfill_uses_game_time_to_resolve_doubleheader():
    rows = [
        {
            "slate_date": "2026-05-12",
            "team": "Seattle Mariners",
            "opp_team": "New York Yankees",
            "game_time": "2026-05-12T22:40:00Z",
            "pitcher": "Bryan Woo",
            "side": "over",
        },
        {
            "slate_date": "2026-05-12",
            "team": "Seattle Mariners",
            "opp_team": "New York Yankees",
            "game_time": "2026-05-12T22:40:00Z",
            "pitcher": "Bryan Woo",
            "side": "under",
        },
    ]

    result = build_actual_opportunity_backfill(
        rows,
        schedule_fetcher=lambda date: _schedule(),
        boxscore_fetcher=lambda game_pk: _boxscore(),
    )
    key = actual_opportunity_lookup_key(
        "2026-05-12",
        "Seattle Mariners",
        "New York Yankees",
        "2026-05-12T22:40:00Z",
        "Bryan Woo",
    )

    assert result["summary"]["dataset_rows"] == 2
    assert result["summary"]["unique_opportunity_keys"] == 1
    assert result["summary"]["reconstructed_opportunities"] == 1
    assert result["opportunities"][key]["game_pk"] == 101
    assert result["opportunities"][key]["actual_pitch_count"] == 91
    assert result["opportunities"][key]["actual_opportunity_source"] == "mlb_boxscore_reconstructed"
    assert result["opportunities"][key]["actual_opportunity_runtime_safe"] is False
