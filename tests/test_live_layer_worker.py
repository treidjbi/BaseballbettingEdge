import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import requests

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

    assert result["live_pick_state"] == 1
    assert result["notification_events"] == 1
    assert result["line_movement_events"] == 0
    assert result["game_reminders"] == 0
    assert result["state_rows"][0]["source_artifact_sha256"]
    assert Path(result["state_rows"][0]["source_artifact_path"]).name == "today.json"
    assert result["shadow_pipeline_timing"]["pipeline_runs"] == 1
    assert result["shadow_pipeline_timing"]["pick_lock_observations"] == 1
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
        "market_pick_evidence",
        "live_market_display_state",
        "shadow_notification_candidates",
        "game_reminder_state",
        "live_pick_state",
        "shadow_pipeline_runs",
    ]
    writer.insert_ignore_rows.assert_any_call(
        "shadow_pick_lock_observations",
        result["shadow_pipeline_timing"]["pick_lock_observation_rows"],
        on_conflict="dedupe_key",
    )


def test_worker_keeps_shadow_timing_failures_from_breaking_live_layer(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "game_reminder_state": [],
    })
    writer.upsert_rows.side_effect = [
        [],
        [],
        [],
        [],
        [],
        [],
        [],
        RuntimeError("shadow table missing"),
    ]

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

    assert result["live_pick_state"] == 1
    assert result["shadow_pipeline_timing"]["skipped"] is True
    assert "shadow table missing" in result["shadow_pipeline_timing"]["error"]


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
                "provider": "propline",
                "provider_event_id": "game-1",
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
                "provider": "propline",
                "provider_event_id": "game-1",
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
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["line_movement_events"] == 1
    assert result["line_movement_rows"][0]["source_snapshot_id"] == "snapshot-new"
    assert result["line_movement_rows"][0]["metadata"]["provider_event_id"] == "game-1"
    writer.upsert_rows.assert_any_call(
        "line_movement_events",
        result["line_movement_rows"],
        on_conflict="dedupe_key",
    )


def test_worker_fetches_market_snapshots_by_recent_run_ids_when_available(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    calls = []
    writer = Mock()

    def select_rows(table, params):
        calls.append((table, dict(params)))
        if table == "live_pick_state":
            return []
        if table == "market_feed_heartbeats":
            return []
        if table == "market_provider_runs":
            return [{"id": "run-1", "provider": "propline", "slate_date": "2026-05-06"}]
        if table == "market_snapshots":
            return [
                {
                    "id": "snapshot-old",
                    "run_id": "run-1",
                    "provider": "propline",
                    "provider_event_id": "game-1",
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
                    "run_id": "run-1",
                    "provider": "propline",
                    "provider_event_id": "game-1",
                    "normalized_player_name": "tarik skubal",
                    "player_name": "Tarik Skubal",
                    "bookmaker_key": "fanduel",
                    "side": "over",
                    "line": 5.5,
                    "american_odds": -112,
                    "observed_at": "2026-05-06T18:00:00+00:00",
                },
            ]
        if table == "game_reminder_state":
            return []
        return []

    writer.select_rows.side_effect = select_rows

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

    snapshot_call = next(call for call in calls if call[0] == "market_snapshots")
    assert snapshot_call[1]["run_id"] == "in.(run-1)"
    assert snapshot_call[1]["observed_at"].startswith("gte.")
    assert snapshot_call[1]["limit"] == "1000"
    assert result["line_movement_events"] == 1


def test_worker_ignores_boltodds_shadow_snapshots_for_notifications(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [
            {
                "id": "bolt-snapshot-old",
                "provider": "boltodds",
                "provider_event_id": "game-1",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "betrivers",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "bolt-snapshot-new",
                "provider": "boltodds",
                "provider_event_id": "game-1",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "betrivers",
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
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["line_movement_events"] == 0
    assert result["line_movement_rows"] == []


def test_worker_writes_market_pick_evidence_for_shadow_providers(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [
            {
                "id": "propline-old",
                "provider": "propline",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "propline-new",
                "provider": "propline",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 5.5,
                "american_odds": -112,
                "observed_at": "2026-05-06T18:00:00+00:00",
            },
            {
                "id": "bolt-old",
                "provider": "boltodds",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "betrivers",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "bolt-new",
                "provider": "boltodds",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "betrivers",
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
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["market_pick_evidence"] == 2
    assert result["live_market_display_state"] == 2
    assert {row["provider"] for row in result["market_pick_evidence_rows"]} == {"propline", "boltodds"}
    assert {row["provider"] for row in result["live_market_display_rows"]} == {"propline", "boltodds"}
    assert {row["actionable_state"] for row in result["live_market_display_rows"]} == {"monitor"}
    writer.upsert_rows.assert_any_call(
        "market_pick_evidence",
        result["market_pick_evidence_rows"],
        on_conflict="slate_date,normalized_pitcher,side,provider",
    )
    writer.upsert_rows.assert_any_call(
        "live_market_display_state",
        result["live_market_display_rows"],
        on_conflict="slate_date,normalized_pitcher,side,provider",
    )
    writer.upsert_rows.assert_any_call(
        "shadow_notification_candidates",
        result["shadow_notification_candidate_rows"],
        on_conflict="dedupe_key",
    )
    assert result["shadow_notification_candidates"] == 2


def test_worker_passes_boltodds_heartbeats_to_shadow_market_builders(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_feed_heartbeats": [{
            "provider": "boltodds",
            "slate_date": "2026-05-06",
            "observed_at": "2026-05-06T18:10:15+00:00",
            "last_message_at": "2026-05-06T18:10:10+00:00",
            "books_seen": ["fanduel", "betmgm"],
            "metadata": {"event": "flush", "target_books": ["fanduel", "betmgm"]},
        }],
        "market_snapshots": [
            {
                "id": "bolt-fd-old",
                "provider": "boltodds",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-06T17:00:00+00:00",
            },
            {
                "id": "bolt-mgm-old",
                "provider": "boltodds",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "betmgm",
                "side": "over",
                "line": 6.5,
                "american_odds": -105,
                "observed_at": "2026-05-06T17:00:00+00:00",
            },
        ],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:10:30+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["live_market_display_rows"][0]["freshness_status"] == "fresh"
    assert result["live_market_display_rows"][0]["metadata"]["heartbeat_hold"] is True
    assert result["market_pick_evidence_rows"][0]["metadata"]["freshness_status"] == "fresh"
    assert result["market_pick_evidence_rows"][0]["metadata"]["heartbeat_hold"] is True
    assert writer.select_rows.call_args_list[1].args[0] == "market_feed_heartbeats"
    assert writer.select_rows.call_args_list[1].args[1]["slate_date"] == "eq.2026-05-06"


def test_worker_keeps_heartbeat_read_failures_from_breaking_live_layer(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = Mock()

    def select_rows(table, params):
        if table == "market_feed_heartbeats":
            raise RuntimeError("heartbeat table unavailable")
        return {
            "live_pick_state": [],
            "market_snapshots": [],
            "game_reminder_state": [],
        }.get(table, [])

    writer.select_rows.side_effect = select_rows

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:10:30+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["live_pick_state"] == 1
    assert result["provider_heartbeats"] == 0


def test_worker_does_not_turn_shadow_candidates_into_notifications(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher(game_time="2026-05-06T18:05:00+00:00")])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [
            {
                "id": "bolt-old",
                "provider": "boltodds",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "bolt-new",
                "provider": "boltodds",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 7.5,
                "american_odds": 120,
                "observed_at": "2026-05-06T17:58:00+00:00",
            },
        ],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T17:58:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["shadow_notification_candidates"] == 1
    assert all(row["event_type"] != "line_moved_with_us" for row in result["notification_rows"])


def test_worker_can_poll_propline_before_building_live_events(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    calls = []
    table_rows = {
        "live_pick_state": [],
        "market_snapshots": [
            {
                "id": "snapshot-old",
                "provider": "propline",
                "provider_event_id": "game-1",
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
                "provider": "propline",
                "provider_event_id": "game-1",
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
    }

    writer = Mock()

    def select_rows(table, params):
        calls.append(("select", table))
        return table_rows.get(table, [])

    writer.select_rows.side_effect = select_rows

    def poll_propline(*args, **kwargs):
        calls.append(("poll", "propline"))
        return {"target_event_count": 1, "snapshot_count": 2}

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "poll_propline_to_supabase",
            side_effect=poll_propline,
        ) as poll,
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            poll_propline=True,
        )

    poll.assert_called_once()
    assert calls.index(("poll", "propline")) < calls.index(("select", "market_snapshots"))
    assert result["propline"]["snapshot_count"] == 2
    assert result["line_movement_events"] == 1


def test_worker_continues_when_optional_propline_poll_times_out(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    calls = []
    writer = Mock()

    def select_rows(table, params):
        calls.append(("select", table))
        return {
            "live_pick_state": [],
            "market_snapshots": [],
            "game_reminder_state": [],
        }.get(table, [])

    writer.select_rows.side_effect = select_rows

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "poll_propline_to_supabase",
            side_effect=requests.ReadTimeout("PropLine timed out"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            poll_propline=True,
        )

    assert result["live_pick_state"] == 1
    assert result["propline"]["skipped"] is True
    assert result["propline"]["reason"] == "poll_failed"
    assert "PropLine timed out" in result["propline"]["error"]
    assert ("select", "market_snapshots") in calls


def test_worker_continues_when_market_snapshot_read_fails(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = Mock()

    def select_rows(table, params):
        if table == "market_snapshots":
            raise RuntimeError("Supabase market_snapshots read failed")
        return {
            "live_pick_state": [],
            "market_feed_heartbeats": [],
            "game_reminder_state": [],
        }.get(table, [])

    writer.select_rows.side_effect = select_rows

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

    assert result["live_pick_state"] == 1
    assert result["notification_events"] == 1
    assert result["line_movement_events"] == 0
    assert result["market_pick_evidence"] == 0
    assert result["live_market_display_state"] == 0
    writer.upsert_rows.assert_any_call(
        "live_pick_state",
        result["state_rows"],
        on_conflict="slate_date,normalized_pitcher,side",
    )


def test_worker_does_not_compare_snapshots_across_provider_events(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [
            {
                "id": "snapshot-old",
                "provider_event_id": "old-game",
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
                "provider_event_id": "new-game",
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

    assert result["line_movement_events"] == 0
    assert result["line_movement_rows"] == []


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
                "provider_event_id": "game-1",
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
                "provider_event_id": "game-1",
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
        "market_pick_evidence",
        "live_market_display_state",
        "shadow_notification_candidates",
        "game_reminder_state",
        "live_pick_state",
        "shadow_pipeline_runs",
    ]


def test_render_entrypoint_uses_propline_env_without_therundown_dependency():
    script = Path(build_live_events_to_supabase.__file__).read_text(encoding="utf-8")

    assert "PROPLINE_API_KEY" in script
    assert "poll_propline_to_supabase" in script
    assert "RUNDOWN_API_KEY" not in script
    assert "fetch_odds(" not in script


def test_load_artifact_prefers_remote_url(tmp_path, monkeypatch):
    local = _write_artifact(tmp_path, [])
    remote_bytes = json.dumps({
        "date": "2026-05-07",
        "pitchers": [_fire_pitcher(game_time="2026-05-07T22:10:00Z")],
    }).encode("utf-8")

    class RemoteResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return remote_bytes

    monkeypatch.setattr(
        build_live_events_to_supabase,
        "urlopen",
        lambda url, timeout: RemoteResponse(),
    )

    payload, artifact_sha, source = build_live_events_to_supabase._load_artifact(
        local,
        artifact_url="https://example.test/today.json",
    )

    assert payload["date"] == "2026-05-07"
    assert artifact_sha
    assert source == "https://example.test/today.json"


def test_load_artifact_falls_back_to_local_when_remote_url_fails(tmp_path, monkeypatch, capsys):
    local = _write_artifact(tmp_path, [_fire_pitcher()])

    def fail_remote(url, timeout):
        raise OSError("network unavailable")

    monkeypatch.setattr(build_live_events_to_supabase, "urlopen", fail_remote)

    payload, artifact_sha, source = build_live_events_to_supabase._load_artifact(
        local,
        artifact_url="https://example.test/today.json",
    )

    assert payload["date"] == "2026-05-06"
    assert artifact_sha
    assert Path(source).name == "today.json"
    assert "remote artifact fetch failed" in capsys.readouterr().err


def test_render_entrypoint_uses_remote_today_artifact_when_no_date_argument(tmp_path, monkeypatch, capsys):
    stale_local = _write_artifact(tmp_path, [])
    remote_payload = {
        "date": "2026-05-07",
        "pitchers": [_fire_pitcher(game_time="2026-05-07T22:10:00Z")],
    }
    run_calls = []

    monkeypatch.setattr(build_live_events_to_supabase, "DEFAULT_ARTIFACT", stale_local)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.delenv("PROPLINE_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["build_live_events_to_supabase.py"])

    def load_artifact(path, artifact_url=None):
        assert path == stale_local
        assert artifact_url == build_live_events_to_supabase.DEFAULT_ARTIFACT_URL
        return remote_payload, "remote-sha", build_live_events_to_supabase.DEFAULT_ARTIFACT_URL

    def run(**kwargs):
        run_calls.append(kwargs)
        return {
            "live_pick_state": 1,
            "notification_events": 1,
            "line_movement_events": 0,
            "game_reminders": 0,
            "propline": {"skipped": True},
        }

    monkeypatch.setattr(build_live_events_to_supabase, "_load_artifact", load_artifact)
    monkeypatch.setattr(build_live_events_to_supabase, "run", run)

    assert build_live_events_to_supabase.main() == 0

    assert run_calls[0]["slate_date"] == "2026-05-07"
    assert run_calls[0]["artifact_url"] == build_live_events_to_supabase.DEFAULT_ARTIFACT_URL
    output = capsys.readouterr().out
    assert "date=2026-05-07" in output
    assert "artifact_source=remote" in output


def test_render_entrypoint_uses_remote_artifact_when_date_argument_matches(tmp_path, monkeypatch, capsys):
    stale_local = _write_artifact(tmp_path, [])
    remote_payload = {
        "date": "2026-05-07",
        "pitchers": [_fire_pitcher(game_time="2026-05-07T22:10:00Z")],
    }
    run_calls = []

    monkeypatch.setattr(build_live_events_to_supabase, "DEFAULT_ARTIFACT", stale_local)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.delenv("PROPLINE_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["build_live_events_to_supabase.py", "2026-05-07"])

    def load_artifact(path, artifact_url=None):
        assert path == stale_local
        assert artifact_url == build_live_events_to_supabase.DEFAULT_ARTIFACT_URL
        return remote_payload, "remote-sha", build_live_events_to_supabase.DEFAULT_ARTIFACT_URL

    def run(**kwargs):
        run_calls.append(kwargs)
        return {
            "live_pick_state": 1,
            "notification_events": 1,
            "line_movement_events": 0,
            "game_reminders": 0,
            "propline": {"skipped": True},
        }

    monkeypatch.setattr(build_live_events_to_supabase, "_load_artifact", load_artifact)
    monkeypatch.setattr(build_live_events_to_supabase, "run", run)

    assert build_live_events_to_supabase.main() == 0

    assert run_calls[0]["slate_date"] == "2026-05-07"
    assert run_calls[0]["artifact_payload"] == remote_payload
    assert run_calls[0]["artifact_url"] == build_live_events_to_supabase.DEFAULT_ARTIFACT_URL
    assert "artifact_source=remote" in capsys.readouterr().out


def test_render_entrypoint_rejects_date_argument_when_remote_artifact_date_differs(tmp_path, monkeypatch, capsys):
    stale_local = _write_artifact(tmp_path, [])
    remote_payload = {"date": "2026-05-07", "pitchers": []}

    monkeypatch.setattr(build_live_events_to_supabase, "DEFAULT_ARTIFACT", stale_local)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.setattr(sys, "argv", ["build_live_events_to_supabase.py", "2026-05-08"])
    monkeypatch.setattr(
        build_live_events_to_supabase,
        "_load_artifact",
        lambda path, artifact_url=None: (
            remote_payload,
            "remote-sha",
            build_live_events_to_supabase.DEFAULT_ARTIFACT_URL,
        ),
    )

    assert build_live_events_to_supabase.main() == 2
    assert "does not match artifact date" in capsys.readouterr().err
