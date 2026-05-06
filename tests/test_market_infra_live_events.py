from datetime import datetime, timezone

from market_infra.live_events import (
    build_line_movement_events,
    build_pick_change_events,
    build_reminder_events,
)


NOW = datetime(2026, 5, 6, 18, 0, tzinfo=timezone.utc)


def _pick(pitcher="Tarik Skubal", side="over", verdict="FIRE 1u", line=6.5):
    return {
        "pitcher": pitcher,
        "team": "DET",
        "opp_team": "BOS",
        "k_line": line,
        "game_time": "2026-05-06T22:10:00Z",
        "game_state": "scheduled",
        f"ev_{side}": {
            "verdict": verdict,
            "adj_ev": 0.09,
            "edge": 0.05,
        },
        f"best_{side}_odds": -110,
        f"best_{side}_book": "FanDuel",
    }


def test_new_fire_pick_emits_notification_event():
    events, state_rows = build_pick_change_events(
        slate_date="2026-05-06",
        pitchers=[_pick()],
        previous_state={},
        observed_at=NOW,
        source_artifact_path="dashboard/data/processed/today.json",
        source_artifact_sha256="abc",
    )

    assert state_rows[0]["current_verdict"] == "FIRE 1u"
    assert events == [{
        "slate_date": "2026-05-06",
        "event_type": "new_fire_pick",
        "severity": "action",
        "title": "New FIRE Pick",
        "body": "Tarik Skubal FIRE 1u OVER 6.5 Ks at FanDuel",
        "url": "/",
        "dedupe_key": "2026-05-06:new_fire_pick:tarik skubal:over:FIRE 1u:6.5",
        "payload": {
            "pitcher": "Tarik Skubal",
            "side": "over",
            "previous_verdict": None,
            "verdict": "FIRE 1u",
            "k_line": 6.5,
            "book": "FanDuel",
            "odds": -110,
        },
        "occurred_at": NOW.isoformat(),
    }]


def test_lean_to_fire_emits_upgrade_event():
    previous = {
        ("2026-05-06", "tarik skubal", "over"): {
            "current_verdict": "LEAN",
        }
    }

    events, _ = build_pick_change_events(
        slate_date="2026-05-06",
        pitchers=[_pick(verdict="FIRE 2u")],
        previous_state=previous,
        observed_at=NOW,
        source_artifact_path="dashboard/data/processed/today.json",
        source_artifact_sha256="abc",
    )

    assert events[0]["event_type"] == "pick_upgraded"
    assert events[0]["title"] == "Pick Upgraded"
    assert events[0]["payload"]["previous_verdict"] == "LEAN"
    assert events[0]["payload"]["verdict"] == "FIRE 2u"


def test_locked_pick_does_not_emit_upgrade_event():
    pick = _pick(verdict="FIRE 2u")
    pick["game_state"] = "in_progress"
    previous = {
        ("2026-05-06", "tarik skubal", "over"): {
            "current_verdict": "LEAN",
        }
    }

    events, _ = build_pick_change_events(
        slate_date="2026-05-06",
        pitchers=[pick],
        previous_state=previous,
        observed_at=NOW,
        source_artifact_path="dashboard/data/processed/today.json",
        source_artifact_sha256="abc",
    )

    assert events == []


def test_pass_downgrade_replaces_previous_fire_state_without_event():
    previous = {
        ("2026-05-06", "tarik skubal", "over"): {
            "current_verdict": "FIRE 1u",
        }
    }

    events, state_rows = build_pick_change_events(
        slate_date="2026-05-06",
        pitchers=[_pick(verdict="PASS")],
        previous_state=previous,
        observed_at=NOW,
        source_artifact_path="dashboard/data/processed/today.json",
        source_artifact_sha256="abc",
    )

    assert events == []
    assert len(state_rows) == 1
    assert state_rows[0]["current_verdict"] == "PASS"
    assert state_rows[0]["previous_verdict"] == "FIRE 1u"
    assert state_rows[0]["is_fire"] is False


def test_fire_pick_missing_k_line_is_skipped():
    pick = _pick()
    pick.pop("k_line")

    events, state_rows = build_pick_change_events(
        slate_date="2026-05-06",
        pitchers=[pick],
        previous_state={},
        observed_at=NOW,
        source_artifact_path="dashboard/data/processed/today.json",
        source_artifact_sha256="abc",
    )

    assert events == []
    assert state_rows == []


def test_over_line_drop_is_with_model_movement():
    events = build_line_movement_events(
        slate_date="2026-05-06",
        live_picks=[{
            "pitcher": "Tarik Skubal",
            "normalized_pitcher": "tarik skubal",
            "side": "over",
            "current_verdict": "FIRE 1u",
        }],
        previous_snapshots=[{
            "normalized_player_name": "tarik skubal",
            "bookmaker_key": "fanduel",
            "line": 6.5,
            "american_odds": -110,
            "observed_at": "2026-05-06T17:50:00+00:00",
        }],
        current_snapshots=[{
            "id": "snapshot-1",
            "normalized_player_name": "tarik skubal",
            "player_name": "Tarik Skubal",
            "bookmaker_key": "fanduel",
            "line": 5.5,
            "american_odds": -112,
            "observed_at": "2026-05-06T18:00:00+00:00",
        }],
    )

    assert events[0]["event_type"] == "line_moved_with_us"
    assert events[0]["payload"]["movement_direction"] == "with_model"
    assert events[0]["dedupe_key"] == "2026-05-06:line:fanduel:tarik skubal:over:6.5:-110:5.5:-112"


def test_under_line_drop_is_against_model_movement():
    events = build_line_movement_events(
        slate_date="2026-05-06",
        live_picks=[{
            "pitcher": "Tarik Skubal",
            "normalized_pitcher": "tarik skubal",
            "side": "under",
            "current_verdict": "FIRE 1u",
        }],
        previous_snapshots=[{
            "normalized_player_name": "tarik skubal",
            "bookmaker_key": "fanduel",
            "line": 6.5,
            "american_odds": -110,
            "observed_at": "2026-05-06T17:50:00+00:00",
        }],
        current_snapshots=[{
            "id": "snapshot-1",
            "normalized_player_name": "tarik skubal",
            "player_name": "Tarik Skubal",
            "bookmaker_key": "fanduel",
            "line": 5.5,
            "american_odds": -112,
            "observed_at": "2026-05-06T18:00:00+00:00",
        }],
    )

    assert events[0]["event_type"] == "line_moved_against_us"
    assert events[0]["payload"]["movement_direction"] == "against_model"


def test_fire_1u_gets_25_minute_reminder_only():
    events, rows = build_reminder_events(
        slate_date="2026-05-06",
        live_picks=[{
            "pitcher": "Tarik Skubal",
            "normalized_pitcher": "tarik skubal",
            "side": "over",
            "current_verdict": "FIRE 1u",
            "k_line": 6.5,
            "game_time": "2026-05-06T18:25:00+00:00",
            "is_locked": False,
        }],
        existing_reminders=set(),
        observed_at=NOW,
    )

    assert len(events) == 1
    assert len(rows) == 1
    assert rows[0]["reminder_window"] == "25_min"
    assert events[0]["event_type"] == "game_reminder_due"
    assert events[0]["dedupe_key"] == "2026-05-06:reminder:25_min:tarik skubal:over"
