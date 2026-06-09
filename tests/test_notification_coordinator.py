from datetime import datetime, timezone

from market_infra.notification_coordinator import coordinate_notification_rows


NOW = datetime(2026, 6, 4, 17, 0, tzinfo=timezone.utc).isoformat()


def _event(
    event_type,
    pitcher,
    *,
    game_time="2026-06-04T17:30:00+00:00",
    verdict="FIRE 1u",
    side="over",
):
    normalized = pitcher.lower()
    return {
        "slate_date": "2026-06-04",
        "event_type": event_type,
        "severity": "action",
        "title": "Pick Starts Soon",
        "body": f"{pitcher} {verdict}",
        "url": "/",
        "dedupe_key": f"2026-06-04:{event_type}:{normalized}:{side}",
        "payload": {
            "pitcher": pitcher,
            "normalized_pitcher": normalized,
            "side": side,
            "verdict": verdict,
            "k_line": 5.5,
            "game_time": game_time,
        },
        "occurred_at": NOW,
    }


def _pick_change(event_type, pitcher, *, verdict="FIRE 1u", side="over"):
    row = _event(event_type, pitcher, verdict=verdict, side=side)
    row["title"] = "Pick Changed"
    row["payload"]["previous_verdict"] = "LEAN"
    return row


def _movement(event_type, pitcher):
    return _event(event_type, pitcher)


def test_start_window_digest_groups_same_30_minute_bucket():
    rows = [
        _event("game_reminder_due", "Sandy Alcantara", game_time="2026-06-04T17:30:00+00:00"),
        _event("game_reminder_due", "Spencer Strider", game_time="2026-06-04T17:45:00+00:00", verdict="LEAN"),
        _event("game_reminder_due", "Carlos Rodon", game_time="2026-06-04T18:05:00+00:00"),
    ]

    result = coordinate_notification_rows(
        rows,
        mode="grouped",
        observed_at=NOW,
        group_start_windows=True,
    )

    assert [row["event_type"] for row in result.rows] == [
        "start_window_digest",
        "game_reminder_due",
    ]
    digest = result.rows[0]
    assert digest["slate_date"] == "2026-06-04"
    assert digest["severity"] == "action"
    assert digest["dedupe_key"] == "2026-06-04:start_window_digest:2026-06-04T17:30:00+00:00"
    assert digest["payload"]["source_event_count"] == 2
    assert digest["payload"]["source_dedupe_keys"] == [
        rows[0]["dedupe_key"],
        rows[1]["dedupe_key"],
    ]
    assert digest["payload"]["pitchers"] == ["Sandy Alcantara", "Spencer Strider"]
    assert digest["payload"]["fire_count"] == 1
    assert digest["payload"]["lean_count"] == 1
    assert digest["payload"]["start_window_bucket"] == "2026-06-04T17:30:00+00:00"
    assert digest["title"] == "2 tracked pitchers start by 11:00 AM Phoenix"
    assert result.summary["grouped_count"] == 1


def test_start_window_digest_title_formats_utc_bucket_as_phoenix_time():
    rows = [
        _event("game_reminder_due", "Sandy Alcantara", game_time="2026-06-09T22:30:00+00:00"),
        _event("game_reminder_due", "Spencer Strider", game_time="2026-06-09T22:45:00+00:00"),
    ]

    result = coordinate_notification_rows(
        rows,
        mode="grouped",
        observed_at="2026-06-09T22:00:00+00:00",
        group_start_windows=True,
    )

    digest = result.rows[0]
    assert digest["payload"]["start_window_bucket"] == "2026-06-09T22:30:00+00:00"
    assert digest["title"] == "2 tracked pitchers start by 4:00 PM Phoenix"


def test_shadow_mode_keeps_insert_rows_unchanged_but_reports_digest():
    rows = [
        _event("game_reminder_due", "Sandy Alcantara", game_time="2026-06-04T17:30:00+00:00"),
        _event("game_reminder_due", "Spencer Strider", game_time="2026-06-04T17:45:00+00:00"),
    ]

    result = coordinate_notification_rows(
        rows,
        mode="shadow",
        observed_at=NOW,
        group_start_windows=True,
    )

    assert result.rows == rows
    assert [row["event_type"] for row in result.shadow_rows] == ["start_window_digest"]
    assert result.summary["mode"] == "shadow"
    assert result.summary["grouped_count"] == 1
    assert result.summary["input_count"] == 2
    assert result.summary["output_count"] == 2


def test_off_mode_is_noop():
    rows = [
        _event("game_reminder_due", "Sandy Alcantara", game_time="2026-06-04T17:30:00+00:00"),
        _event("game_reminder_due", "Spencer Strider", game_time="2026-06-04T17:45:00+00:00"),
    ]

    result = coordinate_notification_rows(
        rows,
        mode="off",
        observed_at=NOW,
        group_start_windows=True,
    )

    assert result.rows == rows
    assert result.shadow_rows == []
    assert result.summary == {
        "mode": "off",
        "input_count": 2,
        "output_count": 2,
        "grouped_count": 0,
        "suppressed_source_count": 0,
    }


def test_groups_same_run_pick_upgrades():
    rows = [
        _pick_change("pick_upgraded", "Sandy Alcantara"),
        _pick_change("pick_upgraded", "Spencer Strider"),
    ]

    result = coordinate_notification_rows(
        rows,
        mode="grouped",
        observed_at=NOW,
        group_pick_changes=True,
    )

    assert [row["event_type"] for row in result.rows] == ["pick_upgraded_digest"]
    assert result.rows[0]["payload"]["source_event_count"] == 2
    assert result.rows[0]["payload"]["pitchers"] == ["Sandy Alcantara", "Spencer Strider"]


def test_keeps_upgrade_and_downgrade_separate():
    rows = [
        _pick_change("pick_upgraded", "Sandy Alcantara"),
        _pick_change("pick_downgraded", "Spencer Strider"),
    ]

    result = coordinate_notification_rows(
        rows,
        mode="grouped",
        observed_at=NOW,
        group_pick_changes=True,
    )

    assert result.rows == rows


def test_single_pick_change_passes_through():
    rows = [_pick_change("pick_upgraded", "Sandy Alcantara")]

    result = coordinate_notification_rows(
        rows,
        mode="grouped",
        observed_at=NOW,
        group_pick_changes=True,
    )

    assert result.rows == rows


def test_movement_rows_stay_individual():
    rows = [
        _movement("line_moved_with_us", "Sandy Alcantara"),
        _movement("line_moved_against_us", "Spencer Strider"),
    ]

    result = coordinate_notification_rows(
        rows,
        mode="grouped",
        observed_at=NOW,
        group_pick_changes=True,
        group_start_windows=True,
    )

    assert result.rows == rows
