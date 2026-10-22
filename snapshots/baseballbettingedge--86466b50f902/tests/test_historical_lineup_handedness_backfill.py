from analytics.diagnostics.historical_lineup_handedness_backfill import (
    build_historical_lineup_backfill,
    extract_lineup_handedness,
)
from analytics.diagnostics.pitcher_k_outcome_dataset import lineup_handedness_lookup_key


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
    players = {
        "ID1": {"person": {"fullName": "One", "batSide": {"code": "R"}}},
        "ID2": {"person": {"fullName": "Two", "batSide": {"code": "L"}}},
        "ID3": {"person": {"fullName": "Three", "batSide": {"code": "S"}}},
        "ID4": {"person": {"fullName": "Four", "batSide": {"code": "R"}}},
        "ID5": {"person": {"fullName": "Five", "batSide": {"code": "R"}}},
        "ID6": {"person": {"fullName": "Six", "batSide": {"code": "L"}}},
        "ID7": {"person": {"fullName": "Seven", "batSide": {"code": "R"}}},
        "ID8": {"person": {"fullName": "Eight", "batSide": {"code": "L"}}},
        "ID9": {"person": {"fullName": "Nine", "batSide": {"code": "R"}}},
    }
    return {
        "teams": {
            "away": {"battingOrder": [1, 2, 3, 4, 5, 6, 7, 8, 9], "players": players},
            "home": {"battingOrder": [], "players": {}},
        }
    }


def test_extract_lineup_handedness_counts_batting_order_hands():
    result = extract_lineup_handedness(_boxscore(), "away")

    assert result["lineup_count"] == 9
    assert result["lineup_right_batters"] == 5
    assert result["lineup_left_batters"] == 3
    assert result["lineup_switch_batters"] == 1
    assert result["lineup_bats"] == ["R", "L", "S", "R", "R", "L", "R", "L", "R"]


def test_build_historical_lineup_backfill_uses_game_time_to_resolve_doubleheader():
    rows = [
        {
            "slate_date": "2026-05-12",
            "team": "Seattle Mariners",
            "opp_team": "New York Yankees",
            "game_time": "2026-05-12T22:40:00Z",
            "lineup_count": 9,
        },
        {
            "slate_date": "2026-05-12",
            "team": "Seattle Mariners",
            "opp_team": "New York Yankees",
            "game_time": "2026-05-12T22:40:00Z",
            "lineup_count": 9,
        },
    ]

    result = build_historical_lineup_backfill(
        rows,
        schedule_fetcher=lambda date: _schedule(),
        boxscore_fetcher=lambda game_pk: _boxscore(),
    )
    key = lineup_handedness_lookup_key(
        "2026-05-12",
        "Seattle Mariners",
        "New York Yankees",
        "2026-05-12T22:40:00Z",
    )

    assert result["summary"]["dataset_rows"] == 2
    assert result["summary"]["unique_lineup_keys"] == 1
    assert result["summary"]["reconstructed_lineups"] == 1
    assert result["lineups"][key]["game_pk"] == 101
    assert result["lineups"][key]["lineup_handedness_source"] == "mlb_boxscore_reconstructed"
    assert result["lineups"][key]["lineup_handedness_runtime_safe"] is False
