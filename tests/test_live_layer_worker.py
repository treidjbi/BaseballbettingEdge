import json
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import build_live_events_to_supabase


def _writer_with_selects(table_rows):
    writer = Mock()

    def select_rows(table, params):
        return table_rows.get(table, [])

    writer.select_rows.side_effect = select_rows
    return writer


def _write_artifact(tmp_path, pitchers):
    today = tmp_path / "today.json"
    today.write_text(
        json.dumps({
            "date": "2026-05-06",
            "pitchers": pitchers,
        }),
        encoding="utf-8",
    )
    return today


def _fire_pitcher(game_time="2026-05-06T22:10:00Z"):
    return {
        "pitcher": "Tarik Skubal",
        "team": "DET",
        "opp_team": "BOS",
        "k_line": 6.5,
        "game_time": game_time,
        "game_state": "scheduled",
        "best_over_odds": -110,
        "best_over_book": "FanDuel",
        "ev_over": {"verdict": "FIRE 1u", "adj_ev": 0.09, "edge": 0.05},
    }


def test_worker_writes_state_and_notification_events(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])

    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "game_reminder_state": [],
    })

    with patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["live_pick_state"] == 1
    assert result["notification_events"] == 1
    assert result["line_movement_events"] == 0
    assert result["game_reminders"] == 0
    assert result["state_rows"][0]["source_artifact_sha256"]
    assert Path(result["state_rows"][0]["source_artifact_path"]).name == "today.json"
    writer.upsert_rows.assert_any_call(
        "live_pick_state",
        result["state_rows"],
        on_conflict="slate_date,normalized_pitcher,side",
    )
    writer.upsert_rows.assert_any_call(
        "notification_events",
        result["notification_rows"],
        on_conflict="dedupe_key",
    )
    upsert_tables = [call.args[0] for call in writer.upsert_rows.call_args_list]
    assert upsert_tables == [
        "notification_events",
        "line_movement_events",
        "game_reminder_state",
        "live_pick_state",
    ]


def test_worker_marks_missing_previous_fire_pass_after_notifications(tmp_path):
    today = _write_artifact(tmp_path, [])
    previous = [{
        "slate_date": "2026-05-06",
        "pitcher": "Tarik Skubal",
        "normalized_pitcher": "tarik skubal",
        "side": "over",
        "current_verdict": "FIRE 1u",
        "k_line": 6.5,
        "current_odds": -110,
        "current_book": "FanDuel",
        "game_time": "2026-05-06T22:10:00Z",
        "game_state": "scheduled",
        "is_locked": False,
    }]
    writer = _writer_with_selects({
        "live_pick_state": previous,
        "market_snapshots": [],
        "game_reminder_state": [],
    })

    with patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["notification_events"] == 1
    assert result["live_pick_state"] == 1
    assert result["notification_rows"][0]["event_type"] == "pick_downgraded"
    assert result["state_rows"][0]["current_verdict"] == "PASS"
    upsert_tables = [call.args[0] for call in writer.upsert_rows.call_args_list]
    assert upsert_tables.index("notification_events") < upsert_tables.index("live_pick_state")


def test_worker_writes_line_movement_events_from_snapshot_history(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [
            {
                "id": "snapshot-old",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "snapshot-new",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 5.5,
                "american_odds": -112,
                "observed_at": "2026-05-06T18:00:00+00:00",
            },
        ],
        "game_reminder_state": [],
    })

    with patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["line_movement_events"] == 1
    assert result["line_movement_rows"][0]["source_snapshot_id"] == "snapshot-new"
    writer.upsert_rows.assert_any_call(
        "line_movement_events",
        result["line_movement_rows"],
        on_conflict="dedupe_key",
    )


def test_worker_writes_fire_1u_game_reminder_state(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher(game_time="2026-05-06T18:25:00+00:00")])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["game_reminders"] == 1
    assert result["reminder_rows"][0]["reminder_window"] == "25_min"
    writer.upsert_rows.assert_any_call(
        "game_reminder_state",
        result["reminder_rows"],
        on_conflict="dedupe_key",
    )


def test_worker_upserts_non_empty_tables_in_retry_safe_order(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher(game_time="2026-05-06T18:25:00+00:00")])

    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [
            {
                "id": "snapshot-old",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "snapshot-new",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 5.5,
                "american_odds": -112,
                "observed_at": "2026-05-06T18:00:00+00:00",
            },
        ],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    upsert_tables = [call.args[0] for call in writer.upsert_rows.call_args_list]
    assert upsert_tables == [
        "notification_events",
        "line_movement_events",
        "game_reminder_state",
        "live_pick_state",
    ]
