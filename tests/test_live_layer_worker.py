import json
import sys
from pathlib import Path
from unittest.mock import ANY, Mock, patch

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


def _fire_pitcher(game_time="2026-05-06T22:10:00Z", pitcher="Tarik Skubal"):
    return {
        "pitcher": pitcher,
        "team": "DET",
        "opp_team": "BOS",
        "k_line": 6.5,
        "game_time": game_time,
        "game_state": "scheduled",
        "best_over_odds": -110,
        "best_over_book": "FanDuel",
        "ev_over": {"verdict": "FIRE 1u", "adj_ev": 0.09, "edge": 0.05},
    }


def _previous_fire_state(pitcher, *, game_time):
    return {
        "slate_date": "2026-05-06",
        "pitcher": pitcher,
        "normalized_pitcher": pitcher.lower(),
        "side": "over",
        "current_verdict": "FIRE 1u",
        "previous_verdict": "FIRE 1u",
        "k_line": 6.5,
        "current_odds": -110,
        "current_book": "FanDuel",
        "game_time": game_time,
        "game_state": "scheduled",
        "is_fire": True,
        "is_locked": False,
        "source_artifact_path": "test",
        "source_artifact_sha256": "sha",
        "last_model_seen_at": "2026-05-06T17:50:00+00:00",
        "metadata": {},
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
    writer.insert_ignore_rows.assert_any_call(
        "notification_events",
        result["notification_rows"],
        on_conflict="dedupe_key",
    )
    upsert_tables = [call.args[0] for call in writer.upsert_rows.call_args_list]
    assert upsert_tables == [
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


def test_env_int_invalid_value_falls_back(monkeypatch):
    monkeypatch.setenv("LIVE_TEST_INVALID_INT", "bad")

    assert build_live_events_to_supabase._env_int("LIVE_TEST_INVALID_INT", default=7) == 7


def test_notification_coordinator_default_is_noop_for_reminders(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVE_NOTIFICATION_COORDINATOR_MODE", raising=False)
    monkeypatch.delenv("LIVE_NOTIFICATION_GROUP_START_WINDOWS", raising=False)
    today = _write_artifact(tmp_path, [
        _fire_pitcher(game_time="2026-05-06T18:20:00Z", pitcher="Sandy Alcantara"),
        _fire_pitcher(game_time="2026-05-06T18:24:00Z", pitcher="Spencer Strider"),
    ])
    writer = _writer_with_selects({
        "live_pick_state": [
            _previous_fire_state("Sandy Alcantara", game_time="2026-05-06T18:20:00Z"),
            _previous_fire_state("Spencer Strider", game_time="2026-05-06T18:24:00Z"),
        ],
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

    assert [row["event_type"] for row in result["notification_rows"]] == [
        "game_reminder_due",
        "game_reminder_due",
    ]
    assert result["notification_events"] == 2
    assert result["notification_coordinator"]["mode"] == "off"
    writer.insert_ignore_rows.assert_any_call(
        "notification_events",
        result["notification_rows"],
        on_conflict="dedupe_key",
    )


def test_notification_coordinator_shadow_records_summary_only(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_NOTIFICATION_COORDINATOR_MODE", "shadow")
    monkeypatch.setenv("LIVE_NOTIFICATION_GROUP_START_WINDOWS", "true")
    today = _write_artifact(tmp_path, [
        _fire_pitcher(game_time="2026-05-06T18:20:00Z", pitcher="Sandy Alcantara"),
        _fire_pitcher(game_time="2026-05-06T18:24:00Z", pitcher="Spencer Strider"),
    ])
    writer = _writer_with_selects({
        "live_pick_state": [
            _previous_fire_state("Sandy Alcantara", game_time="2026-05-06T18:20:00Z"),
            _previous_fire_state("Spencer Strider", game_time="2026-05-06T18:24:00Z"),
        ],
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

    assert [row["event_type"] for row in result["notification_rows"]] == [
        "game_reminder_due",
        "game_reminder_due",
    ]
    assert [row["event_type"] for row in result["notification_coordinator_shadow_rows"]] == [
        "start_window_digest"
    ]
    assert result["notification_coordinator"]["input_count"] == 2
    assert result["notification_coordinator"]["grouped_count"] == 1
    assert (
        result["shadow_pipeline_timing"]["pipeline_run_row"]["metadata"]["notification_coordinator"]["mode"]
        == "shadow"
    )


def test_notification_coordinator_grouped_inserts_digest(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_NOTIFICATION_COORDINATOR_MODE", "grouped")
    monkeypatch.setenv("LIVE_NOTIFICATION_GROUP_START_WINDOWS", "true")
    today = _write_artifact(tmp_path, [
        _fire_pitcher(game_time="2026-05-06T18:20:00Z", pitcher="Sandy Alcantara"),
        _fire_pitcher(game_time="2026-05-06T18:24:00Z", pitcher="Spencer Strider"),
    ])
    writer = _writer_with_selects({
        "live_pick_state": [
            _previous_fire_state("Sandy Alcantara", game_time="2026-05-06T18:20:00Z"),
            _previous_fire_state("Spencer Strider", game_time="2026-05-06T18:24:00Z"),
        ],
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

    assert [row["event_type"] for row in result["notification_rows"]] == [
        "start_window_digest"
    ]
    assert result["notification_events"] == 1
    writer.insert_ignore_rows.assert_any_call(
        "notification_events",
        result["notification_rows"],
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


def test_worker_skips_operational_lock_ledger_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("ENABLE_SUPABASE_LOCK_LEDGER", raising=False)
    pitcher = _fire_pitcher(game_time="2026-05-06T18:30:00Z")
    pitcher["tracked_picks"] = [{
        "pitcher": "Tarik Skubal",
        "side": "over",
        "display_verdict": "FIRE 1u",
        "display_k_line": 6.5,
        "display_odds": -110,
        "display_adj_ev": 0.09,
        "locked_at": None,
        "game_time": "2026-05-06T18:30:00Z",
    }]
    today = _write_artifact(tmp_path, [pitcher])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "market_feed_heartbeats": [],
        "game_reminder_state": [],
    })

    with patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["operational_pick_locks"] == {"skipped": True, "reason": "disabled"}
    insert_tables = [call.args[0] for call in writer.insert_ignore_rows.call_args_list]
    assert "operational_pick_locks" not in insert_tables


def test_worker_writes_operational_lock_rows_when_enabled(tmp_path, monkeypatch):
    pitcher = _fire_pitcher(game_time="2026-05-06T18:30:00Z")
    pitcher["tracked_picks"] = [{
        "pitcher": "Tarik Skubal",
        "side": "over",
        "display_verdict": "FIRE 1u",
        "display_k_line": 6.5,
        "display_odds": -110,
        "display_adj_ev": 0.09,
        "locked_at": None,
        "game_time": "2026-05-06T18:30:00Z",
    }]
    today = _write_artifact(tmp_path, [pitcher])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "market_feed_heartbeats": [],
        "game_reminder_state": [],
    })
    monkeypatch.setenv("ENABLE_SUPABASE_LOCK_LEDGER", "true")

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:02:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["operational_pick_locks"]["skipped"] is False
    assert result["operational_pick_locks"]["rows"] == 1
    lock_call = next(
        call
        for call in writer.insert_ignore_rows.call_args_list
        if call.args[0] == "operational_pick_locks"
    )
    assert lock_call.kwargs["on_conflict"] == "dedupe_key"
    lock_rows = lock_call.args[1]
    assert lock_rows[0]["dedupe_key"] == "2026-05-06:tarik skubal:over"
    assert lock_rows[0]["status_at_capture"] == "due_now"


def test_operational_lock_write_dispatches_lock_workflow_for_new_rows(monkeypatch):
    writer = Mock()
    writer.insert_ignore_rows.return_value = [{"dedupe_key": "2026-05-06:tarik skubal:over"}]
    pitcher = _fire_pitcher(game_time="2026-05-06T18:30:00Z")
    pitcher["tracked_picks"] = [{
        "pitcher": "Tarik Skubal",
        "side": "over",
        "display_verdict": "FIRE 1u",
        "display_k_line": 6.5,
        "display_odds": -110,
        "display_adj_ev": 0.09,
        "locked_at": None,
        "game_time": "2026-05-06T18:30:00Z",
    }]
    monkeypatch.setenv("ENABLE_SUPABASE_LOCK_LEDGER", "true")
    monkeypatch.setenv("ENABLE_LOCK_ONLY_WORKFLOW_DISPATCH", "true")

    with patch.object(
        build_live_events_to_supabase,
        "_dispatch_lock_only_workflow",
        return_value={"skipped": False, "status_code": 204},
    ) as dispatch:
        result = build_live_events_to_supabase._write_operational_pick_locks(
            writer=writer,
            slate_date="2026-05-06",
            payload={"pitchers": [pitcher]},
            observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:02:00+00:00"),
            artifact_source="https://example.com/today.json",
            artifact_sha="abc123",
        )

    assert result["rows"] == 1
    assert result["inserted_rows"] == 1
    assert result["dispatch"] == {"skipped": False, "status_code": 204}
    dispatch.assert_called_once_with("2026-05-06", inserted_lock_rows=1)


def test_operational_lock_write_does_not_dispatch_without_new_rows(monkeypatch):
    writer = Mock()
    writer.insert_ignore_rows.return_value = []
    pitcher = _fire_pitcher(game_time="2026-05-06T18:30:00Z")
    pitcher["tracked_picks"] = [{
        "pitcher": "Tarik Skubal",
        "side": "over",
        "display_verdict": "FIRE 1u",
        "display_k_line": 6.5,
        "display_odds": -110,
        "display_adj_ev": 0.09,
        "locked_at": None,
        "game_time": "2026-05-06T18:30:00Z",
    }]
    monkeypatch.setenv("ENABLE_SUPABASE_LOCK_LEDGER", "true")
    monkeypatch.setenv("ENABLE_LOCK_ONLY_WORKFLOW_DISPATCH", "true")

    with patch.object(build_live_events_to_supabase, "_dispatch_lock_only_workflow") as dispatch:
        result = build_live_events_to_supabase._write_operational_pick_locks(
            writer=writer,
            slate_date="2026-05-06",
            payload={"pitchers": [pitcher]},
            observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:02:00+00:00"),
            artifact_source="https://example.com/today.json",
            artifact_sha="abc123",
        )

    assert result["rows"] == 1
    assert result["inserted_rows"] == 0
    assert result["dispatch"] == {"skipped": True, "reason": "no_new_lock_rows"}
    dispatch.assert_not_called()


def test_dispatch_lock_only_workflow_sends_lock_mode_without_logging_token(monkeypatch):
    captured = {}

    class Response:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b""

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setenv("GITHUB_LOCK_DISPATCH_TOKEN", "ghp_secret")
    monkeypatch.setenv("GITHUB_LOCK_DISPATCH_REPO", "treidjbi/BaseballBettingEdge")
    monkeypatch.setattr(build_live_events_to_supabase, "urlopen", fake_urlopen)

    result = build_live_events_to_supabase._dispatch_lock_only_workflow(
        "2026-05-06",
        inserted_lock_rows=2,
    )

    assert result == {"skipped": False, "status_code": 204}
    assert captured["url"] == (
        "https://api.github.com/repos/treidjbi/BaseballBettingEdge/"
        "actions/workflows/pipeline.yml/dispatches"
    )
    assert captured["body"] == {
        "ref": "main",
        "inputs": {"mode": "lock", "date": "2026-05-06"},
    }
    assert captured["headers"]["Authorization"] == "Bearer ghp_secret"
    assert "ghp_secret" not in repr(captured["body"])
    assert captured["timeout"] == 20


def test_dispatch_lock_only_workflow_uses_proxy_when_github_token_missing(monkeypatch):
    captured = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"status":"triggered"}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return Response()

    monkeypatch.delenv("GITHUB_LOCK_DISPATCH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_PAT", raising=False)
    monkeypatch.setenv(
        "LOCK_ONLY_WORKFLOW_DISPATCH_URL",
        "https://baseballbettingedge.netlify.app/.netlify/functions/trigger-pipeline",
    )
    monkeypatch.setattr(build_live_events_to_supabase, "urlopen", fake_urlopen)

    result = build_live_events_to_supabase._dispatch_lock_only_workflow(
        "2026-05-06",
        inserted_lock_rows=2,
    )

    assert result == {"skipped": False, "status_code": 200, "via": "proxy"}
    assert captured["url"] == "https://baseballbettingedge.netlify.app/.netlify/functions/trigger-pipeline"
    assert captured["body"] == {"mode": "lock", "date": "2026-05-06"}
    assert "Authorization" not in captured["headers"]
    assert captured["timeout"] == 20


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
    write_order = [
        (call[0], call.args[0])
        for call in writer.mock_calls
        if call[0] in {"insert_ignore_rows", "upsert_rows"}
    ]
    assert (
        write_order.index(("insert_ignore_rows", "notification_events"))
        < write_order.index(("upsert_rows", "live_pick_state"))
    )


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
                "id": "rundown-old",
                "provider": "therundown",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "betrivers",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "rundown-new",
                "provider": "therundown",
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
    assert {row["provider"] for row in result["market_pick_evidence_rows"]} == {"propline", "therundown"}
    assert {row["provider"] for row in result["live_market_display_rows"]} == {"propline", "therundown"}
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


def test_worker_filters_retired_boltodds_from_active_market_builders(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    calls = []
    writer = Mock()

    def select_rows(table, params):
        calls.append((table, dict(params)))
        if table == "market_feed_heartbeats":
            assert params["provider"] == "in.(propline,therundown)"
            return []
        if table == "market_snapshots":
            assert params["provider"] == "in.(propline,therundown)"
            return [
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
            ]
        return {
            "live_pick_state": [],
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

    assert result["provider_heartbeats"] == 0
    assert result["market_pick_evidence_rows"] == []
    assert result["live_market_display_rows"] == []
    assert ("market_feed_heartbeats", {
        "provider": "in.(propline,therundown)",
        "slate_date": "eq.2026-05-06",
        "order": "observed_at.desc",
        "limit": "25",
    }) in calls


def test_worker_uses_active_provider_heartbeats_for_shadow_market_builders(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_feed_heartbeats": [{
            "provider": "therundown",
            "slate_date": "2026-05-06",
            "observed_at": "2026-05-06T18:10:15+00:00",
            "last_message_at": "2026-05-06T18:10:10+00:00",
            "books_seen": ["fanduel", "betmgm"],
            "metadata": {"event": "flush", "target_books": ["fanduel", "betmgm"]},
        }],
        "market_snapshots": [
            {
                "id": "rundown-fd-old",
                "provider": "therundown",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-06T17:00:00+00:00",
            },
            {
                "id": "rundown-mgm-old",
                "provider": "therundown",
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

    assert result["live_market_display_rows"][0]["freshness_status"] == "stale"
    assert result["live_market_display_rows"][0]["metadata"]["heartbeat_hold"] is False
    assert result["market_pick_evidence_rows"][0]["metadata"]["freshness_status"] == "stale"
    assert result["market_pick_evidence_rows"][0]["metadata"]["heartbeat_hold"] is False
    assert writer.select_rows.call_args_list[1].args[0] == "market_feed_heartbeats"
    assert writer.select_rows.call_args_list[1].args[1]["slate_date"] == "eq.2026-05-06"
    assert writer.select_rows.call_args_list[1].args[1]["provider"] == "in.(propline,therundown)"


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


def test_worker_can_poll_therundown_mainline_before_market_reads(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    calls = []
    table_rows = {
        "live_pick_state": [],
        "market_snapshots": [],
        "game_reminder_state": [],
    }
    writer = Mock()

    def select_rows(table, params):
        calls.append(("select", table))
        return table_rows.get(table, [])

    writer.select_rows.side_effect = select_rows

    def poll_therundown(*args, **kwargs):
        calls.append(("poll", "therundown"))
        return {
            "status": "completed",
            "target_event_count": 2,
            "snapshot_count": 4,
            "datapoints": 199,
        }

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "poll_therundown_mainline_to_supabase",
            side_effect=poll_therundown,
        ) as poll,
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            poll_therundown_mainline=True,
        )

    poll.assert_called_once_with(
        "2026-05-06",
        writer=writer,
        observed_at=ANY,
        raise_on_error=False,
    )
    assert calls.index(("poll", "therundown")) < calls.index(("select", "market_snapshots"))
    assert result["therundown"]["snapshot_count"] == 4
    assert result["therundown"]["datapoints"] == 199


def test_worker_can_process_propline_webhooks_before_market_reads(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    calls = []
    table_rows = {
        "live_pick_state": [],
        "market_snapshots": [],
        "game_reminder_state": [],
    }

    writer = Mock()

    def select_rows(table, params):
        calls.append(("select", table))
        return table_rows.get(table, [])

    writer.select_rows.side_effect = select_rows

    def process_webhooks(*args, **kwargs):
        calls.append(("process", "propline_webhooks"))
        return {
            "deliveries": 2,
            "processed": 2,
            "line_movement_events": 2,
            "unsupported": 0,
        }

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "process_propline_webhook_deliveries",
            side_effect=process_webhooks,
        ) as processor,
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            process_propline_webhooks=True,
        )

    processor.assert_called_once_with(
        supabase_url="https://example.supabase.co",
        service_role_key="secret",
        limit=100,
        received_after=ANY,
        return_movement_rows=False,
    )
    received_after = processor.call_args.kwargs["received_after"]
    assert received_after is not None
    assert calls.index(("process", "propline_webhooks")) < calls.index(("select", "market_snapshots"))
    assert result["propline_webhooks"]["line_movement_events"] == 2


def test_worker_can_send_book_level_propline_webhook_movement_notifications(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "game_reminder_state": [],
    })

    webhook_row = {
        "slate_date": "2026-05-06",
        "normalized_pitcher": "tarik skubal",
        "pitcher": "Tarik Skubal",
        "side": "over",
        "bookmaker_key": "fanduel",
        "previous_line": 6.5,
        "current_line": 5.5,
        "previous_odds": -130,
        "current_odds": -125,
        "movement_direction": "neutral",
        "movement_kind": "line_and_odds",
        "observed_at": "2026-05-06T18:00:00+00:00",
        "dedupe_key": "2026-05-06:propline_webhook:delivery-1",
        "source_snapshot_id": None,
        "metadata": {
            "bookmaker_key_missing": False,
            "prop_line_delivery_id": "delivery-1",
            "prop_line_event_id": "game-1",
            "source": "propline_webhook",
        },
    }
    non_target_webhook_row = {
        **webhook_row,
        "bookmaker_key": "underdog",
        "dedupe_key": "2026-05-06:propline_webhook:delivery-2",
        "metadata": {
            **webhook_row["metadata"],
            "prop_line_delivery_id": "delivery-2",
        },
    }

    def process_webhooks(*args, **kwargs):
        return {
            "deliveries": 1,
            "processed": 1,
            "line_movement_events": 2,
            "unsupported": 0,
            "movement_rows": [webhook_row, non_target_webhook_row],
        }

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "process_propline_webhook_deliveries",
            side_effect=process_webhooks,
        ) as processor,
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
            process_propline_webhooks=True,
            send_propline_webhook_movement_notifications=True,
        )

    assert processor.call_args.kwargs["return_movement_rows"] is True
    assert result["propline_webhook_notification_events"] == 1
    webhook_event = result["propline_webhook_notification_rows"][0]
    assert webhook_event["event_type"] == "line_moved_with_us"
    assert webhook_event["dedupe_key"] == (
        "2026-05-06:line:game-1:fanduel:tarik skubal:over:6.5:-130:5.5:-125"
    )
    assert webhook_event["payload"]["source"] == "propline_webhook"
    assert "movement_rows" not in result["propline_webhooks"]


def test_worker_can_build_shadow_market_lines_after_live_state(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    calls = []
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "market_feed_heartbeats": [],
        "game_reminder_state": [],
        "official_market_lines": [],
        "current_market_lines": [],
        "compact_market_line_movements": [],
    })

    def record_upsert(table, *args, **kwargs):
        calls.append(("upsert", table))
        return []

    def current_build(**kwargs):
        calls.append(("current_lines", kwargs["artifact_source"]))
        return {"current_market_lines": 3, "written_rows": 3}

    def official_build(**kwargs):
        calls.append(("official_lines", kwargs["artifact_source"]))
        return {"official_market_lines": 2, "ready_for_pipeline": 2}

    def compact_build(**kwargs):
        calls.append(("compact", kwargs["slate_date"]))
        return {"compact_rows": 4, "written_rows": 4}

    writer.upsert_rows.side_effect = record_upsert

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
        patch.object(
            build_live_events_to_supabase,
            "build_current_market_lines_to_supabase",
            side_effect=current_build,
        ),
        patch.object(
            build_live_events_to_supabase,
            "build_official_market_lines_to_supabase",
            side_effect=official_build,
        ),
        patch.object(
            build_live_events_to_supabase,
            "compact_market_snapshots_to_supabase",
            side_effect=compact_build,
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            build_market_lines=True,
        )

    artifact_source = result["artifact_source"]
    assert calls.index(("upsert", "live_pick_state")) < calls.index(("current_lines", artifact_source))
    assert calls.index(("current_lines", artifact_source)) < calls.index(("official_lines", artifact_source))
    assert calls.index(("official_lines", artifact_source)) < calls.index(("compact", "2026-05-06"))
    assert result["market_line_build"]["skipped"] is False
    assert result["market_line_build"]["current"]["current_market_lines"] == 3
    assert result["market_line_build"]["official"]["ready_for_pipeline"] == 2
    assert result["market_line_build"]["compact"]["compact_rows"] == 4


def test_worker_skips_shadow_market_line_build_when_official_rows_are_fresh(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "market_feed_heartbeats": [],
        "game_reminder_state": [],
        "official_market_lines": [{"updated_at": "2026-05-06T17:59:30+00:00"}],
        "current_market_lines": [{"updated_at": "2026-05-06T17:59:30+00:00"}],
        "compact_market_line_movements": [{"updated_at": "2026-05-06T17:45:00+00:00"}],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
        patch.object(build_live_events_to_supabase, "build_current_market_lines_to_supabase") as current_build,
        patch.object(build_live_events_to_supabase, "build_official_market_lines_to_supabase") as official_build,
        patch.object(build_live_events_to_supabase, "compact_market_snapshots_to_supabase") as compact_build,
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            build_market_lines=True,
            market_line_min_interval_seconds=600,
            compact_market_min_interval_seconds=1800,
        )

    current_build.assert_not_called()
    official_build.assert_not_called()
    compact_build.assert_not_called()
    assert result["market_line_build"] == {"skipped": True, "reason": "fresh"}


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


def test_worker_continues_when_optional_therundown_poll_times_out(tmp_path):
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
            "poll_therundown_mainline_to_supabase",
            side_effect=requests.ReadTimeout("TheRundown timed out"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            poll_therundown_mainline=True,
        )

    assert result["live_pick_state"] == 1
    assert result["therundown"]["skipped"] is True
    assert result["therundown"]["reason"] == "poll_failed"
    assert "TheRundown timed out" in result["therundown"]["error"]
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
        "line_movement_events",
        "market_pick_evidence",
        "live_market_display_state",
        "shadow_notification_candidates",
        "game_reminder_state",
        "live_pick_state",
        "shadow_pipeline_runs",
    ]
    writer.insert_ignore_rows.assert_any_call(
        "notification_events",
        ANY,
        on_conflict="dedupe_key",
    )


def test_render_entrypoint_uses_propline_env_and_gated_therundown_capture():
    script = Path(build_live_events_to_supabase.__file__).read_text(encoding="utf-8")

    assert "PROPLINE_API_KEY" in script
    assert "poll_propline_to_supabase" in script
    assert "LIVE_CAPTURE_THERUNDOWN_MAINLINE" in script
    assert "poll_therundown_mainline_to_supabase" in script
    assert "fetch_odds(" not in script


def test_render_entrypoint_passes_therundown_flag_only_when_enabled(tmp_path, monkeypatch):
    stale_local = _write_artifact(tmp_path, [])
    remote_payload = {
        "date": "2026-05-07",
        "pitchers": [_fire_pitcher(game_time="2026-05-07T22:10:00Z")],
    }
    run_calls = []

    monkeypatch.setattr(build_live_events_to_supabase, "DEFAULT_ARTIFACT", stale_local)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.setenv("LIVE_CAPTURE_THERUNDOWN_MAINLINE", "true")
    monkeypatch.delenv("PROPLINE_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["build_live_events_to_supabase.py"])
    monkeypatch.setattr(
        build_live_events_to_supabase,
        "_load_artifact",
        lambda path, artifact_url=None: (
            remote_payload,
            "remote-sha",
            build_live_events_to_supabase.DEFAULT_ARTIFACT_URL,
        ),
    )

    def run(**kwargs):
        run_calls.append(kwargs)
        return {
            "live_pick_state": 1,
            "notification_events": 1,
            "line_movement_events": 0,
            "game_reminders": 0,
            "propline": {"skipped": True},
            "therundown": {"status": "completed", "datapoints": 199},
        }

    monkeypatch.setattr(build_live_events_to_supabase, "run", run)

    assert build_live_events_to_supabase.main() == 0

    assert run_calls[0]["poll_therundown_mainline"] is True


def test_render_entrypoint_leaves_therundown_capture_off_by_default(tmp_path, monkeypatch):
    stale_local = _write_artifact(tmp_path, [])
    remote_payload = {
        "date": "2026-05-07",
        "pitchers": [_fire_pitcher(game_time="2026-05-07T22:10:00Z")],
    }
    run_calls = []

    monkeypatch.setattr(build_live_events_to_supabase, "DEFAULT_ARTIFACT", stale_local)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.delenv("LIVE_CAPTURE_THERUNDOWN_MAINLINE", raising=False)
    monkeypatch.delenv("PROPLINE_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["build_live_events_to_supabase.py"])
    monkeypatch.setattr(
        build_live_events_to_supabase,
        "_load_artifact",
        lambda path, artifact_url=None: (
            remote_payload,
            "remote-sha",
            build_live_events_to_supabase.DEFAULT_ARTIFACT_URL,
        ),
    )

    def run(**kwargs):
        run_calls.append(kwargs)
        return {
            "live_pick_state": 1,
            "notification_events": 1,
            "line_movement_events": 0,
            "game_reminders": 0,
            "propline": {"skipped": True},
            "therundown": {"skipped": True},
        }

    monkeypatch.setattr(build_live_events_to_supabase, "run", run)

    assert build_live_events_to_supabase.main() == 0

    assert run_calls[0]["poll_therundown_mainline"] is False


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


def test_default_live_artifact_url_uses_get_artifact():
    assert "baseballbettingedge.netlify.app/.netlify/functions/get-artifact" in (
        build_live_events_to_supabase.DEFAULT_ARTIFACT_URL
    )
    assert "type=today" in build_live_events_to_supabase.DEFAULT_ARTIFACT_URL
    assert "raw.githubusercontent.com" not in build_live_events_to_supabase.DEFAULT_ARTIFACT_URL


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
