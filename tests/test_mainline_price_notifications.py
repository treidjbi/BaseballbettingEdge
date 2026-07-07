from datetime import datetime, timezone

from market_infra.mainline_price_notifications import (
    build_mainline_best_price_notification_rows,
)


NOW = datetime(2026, 7, 7, 18, 40, tzinfo=timezone.utc)


def _display_row(**overrides):
    row = {
        "slate_date": "2026-07-07",
        "pitcher": "Jacob Misiorowski",
        "normalized_pitcher": "jacob misiorowski",
        "side": "over",
        "provider": "propline",
        "current_verdict": "FIRE 1u",
        "k_line": 7.5,
        "game_time": "2026-07-07T23:40:00Z",
        "game_state": "pregame",
        "is_locked": False,
        "freshness_status": "fresh",
        "book_rows": [
            {"book": "fanduel", "line": 7.5, "odds": -120},
            {"book": "draftkings", "line": 7.5, "odds": -125},
            {"book": "kalshi", "line": 8.5, "odds": 900},
        ],
        "observed_at": "2026-07-07T18:40:00+00:00",
    }
    row.update(overrides)
    return row


def test_first_observation_is_shadow_only_no_notification():
    result = build_mainline_best_price_notification_rows(
        slate_date="2026-07-07",
        previous_rows=[],
        current_rows=[_display_row()],
        observed_at=NOW,
        min_price_move_cents=10,
        mode="shadow",
    )

    assert result.notification_rows == []
    assert result.summary["mode"] == "shadow"
    assert result.summary["first_seen_count"] == 1
    assert result.shadow_rows[0]["candidate_action"] == "first_seen_shadow"


def test_same_line_best_price_change_emits_even_when_alternate_line_moves():
    result = build_mainline_best_price_notification_rows(
        slate_date="2026-07-07",
        previous_rows=[
            _display_row(
                book_rows=[
                    {"book": "fanduel", "line": 7.5, "odds": -120},
                    {"book": "draftkings", "line": 7.5, "odds": -125},
                    {"book": "kalshi", "line": 8.5, "odds": 900},
                ]
            )
        ],
        current_rows=[
            _display_row(
                book_rows=[
                    {"book": "fanduel", "line": 7.5, "odds": -105},
                    {"book": "draftkings", "line": 7.5, "odds": -125},
                    {"book": "kalshi", "line": 8.5, "odds": 1200},
                ]
            )
        ],
        observed_at=NOW,
        min_price_move_cents=10,
        mode="send",
    )

    assert len(result.notification_rows) == 1
    row = result.notification_rows[0]
    assert row["event_type"] == "mainline_best_price_changed"
    assert row["title"] == "Best Price Better Now"
    assert row["body"] == (
        "Jacob Misiorowski OVER 7.5 best price -120->-105 at fanduel; "
        "same main line, price better"
    )
    assert row["payload"]["previous_best_odds"] == -120
    assert row["payload"]["current_best_odds"] == -105
    assert row["payload"]["price_delta"] == 15
    assert row["payload"]["current_best_book"] == "fanduel"


def test_off_line_alt_book_does_not_drive_best_price():
    result = build_mainline_best_price_notification_rows(
        slate_date="2026-07-07",
        previous_rows=[
            _display_row(
                book_rows=[
                    {"book": "fanduel", "line": 7.5, "odds": -120},
                    {"book": "kalshi", "line": 8.5, "odds": 900},
                ]
            )
        ],
        current_rows=[
            _display_row(
                book_rows=[
                    {"book": "fanduel", "line": 7.5, "odds": -120},
                    {"book": "kalshi", "line": 8.5, "odds": 1200},
                ]
            )
        ],
        observed_at=NOW,
        min_price_move_cents=10,
        mode="send",
    )

    assert result.notification_rows == []
    assert result.summary["unchanged_count"] == 1


def test_stale_locked_and_post_start_rows_are_suppressed():
    stale = _display_row(freshness_status="stale")
    locked = _display_row(is_locked=True)
    post_start = _display_row(game_time="2026-07-07T18:30:00Z")

    result = build_mainline_best_price_notification_rows(
        slate_date="2026-07-07",
        previous_rows=[_display_row()],
        current_rows=[stale, locked, post_start],
        observed_at=NOW,
        min_price_move_cents=10,
        mode="send",
    )

    assert result.notification_rows == []
    assert result.summary["suppressed_stale_count"] == 1
    assert result.summary["suppressed_locked_count"] == 1
    assert result.summary["suppressed_post_start_count"] == 1
