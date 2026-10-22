import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "analytics" / "diagnostics"))

from therundown_fetch_audit import (
    build_query_modes,
    summarize_mode,
)


def _event_with_participants(participants):
    return {
        "event_id": "evt-1",
        "event_date": "2026-04-28T23:05:00Z",
        "teams": [
            {"name": "Away", "is_away": True, "is_home": False},
            {"name": "Home", "is_away": False, "is_home": True},
        ],
        "markets": [
            {
                "market_id": 19,
                "name": "pitcher_strikeouts",
                "participants": participants,
            }
        ],
    }


def _participant(name, line_val=4.5, book_id="23"):
    return {
        "id": name.replace(" ", "-"),
        "type": "TYPE_PLAYER",
        "name": name,
        "lines": [
            {
                "value": f"Over {line_val}",
                "prices": {
                    book_id: {
                        "price": -110,
                        "is_main_line": True,
                        "updated_at": "2026-04-28T18:00:00Z",
                    }
                },
            },
            {
                "value": f"Under {line_val}",
                "prices": {
                    book_id: {
                        "price": -110,
                        "is_main_line": True,
                        "updated_at": "2026-04-28T18:00:00Z",
                    }
                },
            },
        ],
    }


def test_build_query_modes_includes_safe_candidate_without_main_line():
    modes = build_query_modes()

    candidate = modes["offset_affiliates"]

    assert candidate["offset"] == "300"
    assert candidate["market_ids"] == "19"
    assert candidate["affiliate_ids"] == "19,22,23,25"
    assert "main_line" not in candidate


def test_summarize_mode_reports_noise_after_probable_resolution():
    events = [
        _event_with_participants([
            _participant("Real Starter", 5.5),
            _participant("Hitter Noise", 0.5),
        ])
    ]

    summary = summarize_mode(
        mode_name="current",
        events=events,
        datapoints=10,
        resolved_pitcher_names={"Real Starter"},
    )

    assert summary["raw_participants"] == 2
    assert summary["parsed_props"] == 1
    assert summary["resolved_pitchers"] == 1
    assert summary["pre_probable_noise"] == 1
    assert summary["books_seen"] == ["23"]
    assert summary["sample_unresolved_names"] == []


def test_summarize_mode_lists_parsed_props_that_do_not_resolve_to_probables():
    events = [
        _event_with_participants([
            _participant("Real Starter", 5.5),
            _participant("Wrong Pitcher", 4.5),
        ])
    ]

    summary = summarize_mode(
        mode_name="offset",
        events=events,
        datapoints=14,
        resolved_pitcher_names={"Real Starter"},
    )

    assert summary["parsed_props"] == 2
    assert summary["resolved_pitchers"] == 1
    assert summary["pre_probable_noise"] == 0
    assert summary["sample_unresolved_names"] == ["Wrong Pitcher"]
