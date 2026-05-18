import asyncio
import importlib
import json

import pytest

from scripts import boltodds_ws_worker


class FakeWriter:
    def __init__(self):
        self.upserts = []
        self.inserts = []

    def upsert_rows(self, table, rows, on_conflict):
        self.upserts.append((table, rows, on_conflict))
        return rows

    def insert_rows(self, table, rows):
        if table == "market_provider_runs":
            rows = [
                {
                    **row,
                    "id": row.get("id") or f"run-{len(self.inserts) + index + 1}",
                }
                for index, row in enumerate(rows)
            ]
        self.inserts.append((table, rows))
        return rows


class FakeWebSocket:
    def __init__(self, messages):
        self.messages = list(messages)
        self.sent = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def send(self, message):
        self.sent.append(message)

    async def recv(self):
        next_item = self.messages.pop(0)
        if isinstance(next_item, BaseException):
            raise next_item
        if isinstance(next_item, tuple) and next_item[0] == "sleep":
            await asyncio.sleep(next_item[1])
            return await self.recv()
        return next_item


def _snapshot(player, book, line, side):
    return {
        "provider": "boltodds",
        "bookmaker_key": book,
        "bookmaker_title": book.title(),
        "player_name": player,
        "normalized_player_name": player.lower(),
        "line": line,
        "side": side,
        "american_odds": -110,
        "dedupe_key": f"{player}-{book}-{line}-{side}",
    }


def _configure_worker(monkeypatch, writer, websocket, *, max_messages="0"):
    async def fake_connect(url):
        return websocket

    monkeypatch.setenv("BOLTODDS_API_KEY", "bolt-key")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role")
    monkeypatch.setenv("SLATE_DATE", "2026-05-07")
    monkeypatch.setenv("BOLTODDS_WS_MAX_MESSAGES", max_messages)
    monkeypatch.setattr(
        boltodds_ws_worker,
        "_load_production_artifact",
        lambda slate_date=None, **kwargs: ({"date": "2026-05-07"}, "test-artifact.json"),
    )
    monkeypatch.setattr(
        boltodds_ws_worker,
        "SupabaseMarketWriter",
        lambda supabase_url, service_role_key: writer,
    )
    monkeypatch.setattr(
        boltodds_ws_worker,
        "get_json",
        lambda *args, **kwargs: {},
    )
    monkeypatch.setattr(
        boltodds_ws_worker,
        "build_probe_summary",
        lambda info, markets, target_books, aliases: {
            "starter_ready": True,
            "blocking_reasons": [],
            "selected_markets": ["Pitcher Strikeouts"],
        },
    )
    monkeypatch.setattr(
        boltodds_ws_worker,
        "_connect_websocket",
        fake_connect,
    )
    monkeypatch.setattr(
        boltodds_ws_worker,
        "snapshots_from_boltodds_message",
        lambda *args, **kwargs: [_snapshot("Gerrit Cole", "fanduel", 7.5, "over")],
    )


def test_build_run_rows_uses_shadow_stream_mode():
    row = boltodds_ws_worker.build_run_rows(
        "2026-05-07",
        status="started",
        request_count=2,
        books_seen={"fanduel", "draftkings"},
        metadata={"worker": "test"},
    )

    assert row["provider"] == "boltodds"
    assert row["mode"] == "shadow_stream"
    assert row["slate_date"] == "2026-05-07"
    assert row["status"] == "started"
    assert row["request_count"] == 2
    assert row["books_seen"] == ["draftkings", "fanduel"]
    assert row["metadata"] == {"worker": "test"}
    assert "completed_at" not in row

    completed = boltodds_ws_worker.build_run_rows(
        "2026-05-07",
        status="completed",
        request_count=3,
        books_seen=[],
        metadata={},
    )
    assert completed["completed_at"]


def test_write_snapshot_batch_upserts_snapshots_and_audit():
    writer = FakeWriter()
    production = {
        "pitchers": [
            {
                "pitcher": "Gerrit Cole",
                "k_line": 7.5,
                "book_odds": {"FanDuel": {"over": -110, "under": -110}},
            }
        ]
    }
    snapshots = [
        _snapshot("Gerrit Cole", "fanduel", 7.5, "over"),
        _snapshot("Gerrit Cole", "fanduel", 7.5, "under"),
    ]

    result = boltodds_ws_worker.write_snapshot_batch(
        writer,
        run_id="run-123",
        slate_date="2026-05-07",
        snapshots=snapshots,
        production_payload=production,
        books_seen={"fanduel", "bovada"},
        target_event_count=4,
    )

    assert result == {"snapshot_count": 2, "coverage_audit_written": 1}
    assert all(snapshot["run_id"] == "run-123" for snapshot in snapshots)
    assert writer.upserts == [
        ("market_snapshots", snapshots, "dedupe_key"),
    ]
    assert len(writer.inserts) == 1
    table, rows = writer.inserts[0]
    assert table == "provider_coverage_audits"
    audit = rows[0]
    assert audit["run_id"] == "run-123"
    assert audit["provider"] == "boltodds"
    assert audit["books_seen"] == ["bovada", "fanduel"]
    assert audit["target_event_count"] == 4
    assert audit["parsed_pitcher_prop_count"] == 1
    assert audit["complete_pitcher_line_groups"] == 1
    assert audit["same_line_overlap_count"] == 1
    assert audit["line_conflict_count"] == 0
    assert audit["metadata"]["snapshot_rows"] == 2
    assert audit["metadata"]["worker"] == "scripts/boltodds_ws_worker.py"


def test_write_snapshot_batch_can_skip_coverage_audit_for_throttled_flushes():
    writer = FakeWriter()
    snapshots = [
        _snapshot("Gerrit Cole", "fanduel", 7.5, "over"),
        _snapshot("Gerrit Cole", "fanduel", 7.5, "under"),
    ]

    result = boltodds_ws_worker.write_snapshot_batch(
        writer,
        run_id="run-123",
        slate_date="2026-05-07",
        snapshots=snapshots,
        production_payload=None,
        books_seen={"fanduel"},
        target_event_count=1,
        write_coverage_audit=False,
    )

    assert result == {"snapshot_count": 2, "coverage_audit_written": 0}
    assert writer.upserts == [("market_snapshots", snapshots, "dedupe_key")]
    assert writer.inserts == []


def test_write_snapshot_batch_empty_snapshots_skip_writes():
    writer = FakeWriter()

    result = boltodds_ws_worker.write_snapshot_batch(
        writer,
        run_id="run-empty",
        slate_date="2026-05-07",
        snapshots=[],
        production_payload=None,
        books_seen=set(),
        target_event_count=0,
    )

    assert result == {"snapshot_count": 0, "coverage_audit_written": 0}
    assert writer.upserts == []
    assert writer.inserts == []


def test_periodic_write_helpers_throttle_audit_and_heartbeat_rows():
    assert boltodds_ws_worker._should_write_periodic_row(
        now_monotonic=10.0,
        last_written_monotonic=None,
        interval_seconds=600.0,
    )
    assert not boltodds_ws_worker._should_write_periodic_row(
        now_monotonic=100.0,
        last_written_monotonic=10.0,
        interval_seconds=600.0,
    )
    assert boltodds_ws_worker._should_write_periodic_row(
        now_monotonic=700.0,
        last_written_monotonic=10.0,
        interval_seconds=600.0,
    )


def test_load_production_artifact_prefers_remote_url(tmp_path, monkeypatch):
    local_path = tmp_path / "dashboard" / "data" / "processed"
    local_path.mkdir(parents=True)
    (local_path / "today.json").write_text(
        json.dumps({"date": "2026-05-07"}),
        encoding="utf-8",
    )
    remote_bytes = json.dumps({
        "date": "2026-05-08",
        "pitchers": [{"pitcher": "Gerrit Cole"}],
    }).encode("utf-8")

    class RemoteResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return remote_bytes

    monkeypatch.setattr(
        boltodds_ws_worker,
        "urlopen",
        lambda url, timeout=20: RemoteResponse(),
    )

    payload, source = boltodds_ws_worker._load_production_artifact(
        root=tmp_path,
        artifact_url="https://example.test/today.json",
    )

    assert payload["date"] == "2026-05-08"
    assert source == "https://example.test/today.json"


def test_production_pitcher_names_normalizes_current_artifact_pitchers():
    payload = {
        "pitchers": [
            {"pitcher": "Gerrit Cole"},
            {"pitcher": "Jesús Luzardo"},
            {"pitcher": ""},
            {},
        ]
    }

    assert boltodds_ws_worker._production_pitcher_names(payload) == {
        "gerrit cole",
        "jesus luzardo",
    }


def test_refresh_production_context_rotates_to_new_artifact_date(monkeypatch):
    payloads = [
        ({"date": "2026-05-12", "pitchers": [{"pitcher": "Old Starter"}]}, "today.json"),
        ({"date": "2026-05-13", "pitchers": [{"pitcher": "New Starter"}]}, "today.json"),
    ]

    def fake_loader(*args, **kwargs):
        if payloads:
            return payloads.pop(0)
        return ({"date": "2026-05-13", "pitchers": [{"pitcher": "New Starter"}]}, "today.json")

    monkeypatch.setattr(boltodds_ws_worker, "_load_production_artifact", fake_loader)

    context = boltodds_ws_worker.load_production_context(
        slate_date_override=None,
        artifact_url="https://example.test/today.json",
    )
    refreshed = boltodds_ws_worker.refresh_production_context_if_advanced(
        context,
        slate_date_override=None,
        artifact_url="https://example.test/today.json",
    )

    assert refreshed.slate_date == "2026-05-13"
    assert refreshed.production_pitcher_names == {"new starter"}
    assert refreshed.rotated is True


def test_refresh_production_context_never_rotates_backwards(monkeypatch):
    payloads = [
        ({"date": "2026-05-13", "pitchers": [{"pitcher": "Current Starter"}]}, "today.json"),
        ({"date": "2026-05-12", "pitchers": [{"pitcher": "Old Starter"}]}, "today.json"),
    ]

    def fake_loader(*args, **kwargs):
        if payloads:
            return payloads.pop(0)
        return ({"date": "2026-05-13", "pitchers": [{"pitcher": "New Starter"}]}, "today.json")

    monkeypatch.setattr(boltodds_ws_worker, "_load_production_artifact", fake_loader)

    context = boltodds_ws_worker.load_production_context(
        slate_date_override=None,
        artifact_url="https://example.test/today.json",
    )
    refreshed = boltodds_ws_worker.refresh_production_context_if_advanced(
        context,
        slate_date_override=None,
        artifact_url="https://example.test/today.json",
    )

    assert refreshed is context
    assert refreshed.slate_date == "2026-05-13"
    assert refreshed.production_pitcher_names == {"current starter"}
    assert refreshed.rotated is False


def test_write_heartbeat_inserts_feed_health_row():
    writer = FakeWriter()

    row = boltodds_ws_worker.write_heartbeat(
        writer,
        run_id="run-123",
        slate_date="2026-05-07",
        event="flush",
        observed_at="2026-05-07T15:30:00+00:00",
        books_seen={"fanduel"},
        last_message_at="2026-05-07T15:29:59+00:00",
        metadata={"snapshot_count": 12},
    )

    assert writer.inserts == [
        (
            "market_feed_heartbeats",
            [
                {
                    "provider": "boltodds",
                    "mode": "shadow_stream",
                    "slate_date": "2026-05-07",
                    "run_id": "run-123",
                    "observed_at": "2026-05-07T15:30:00+00:00",
                    "last_message_at": "2026-05-07T15:29:59+00:00",
                    "books_seen": ["fanduel"],
                    "metadata": {
                        "event": "flush",
                        "snapshot_count": 12,
                    },
                }
            ],
        )
    ]
    assert row == writer.inserts[0][1][0]


def test_worker_exports_flush_decision_helper():
    assert boltodds_ws_worker.should_flush_batch(
        pending_count=1,
        batch_size=100,
        last_flush_monotonic=0.0,
        now_monotonic=30.0,
        flush_seconds=30.0,
    )


def test_message_payloads_flattens_boltodds_array_frames():
    raw_message = (
        '[{"action":"socket_connected","plan":"Trial"},'
        '{"timestamp":"2026-05-07T21:08:10+00:00","action":"line_update",'
        '"data":{"sportsbook":"fanduel","info":{"id":"event-1"}}}]'
    )

    payloads = boltodds_ws_worker._message_payloads(raw_message)

    assert [payload["action"] for payload in payloads] == [
        "socket_connected",
        "line_update",
    ]
    assert payloads[1]["data"]["sportsbook"] == "fanduel"


def test_message_payloads_handles_ping_and_malformed_frames():
    assert boltodds_ws_worker._message_payloads("ping") == [{"action": "ping"}]
    assert boltodds_ws_worker._message_payloads("not-json") == []
    assert boltodds_ws_worker._message_payloads('["not-a-dict"]') == []


def test_batch_size_env_prefers_documented_name(monkeypatch):
    monkeypatch.setenv("BOLTODDS_BATCH_SIZE", "7")
    monkeypatch.setenv("BOLTODDS_WS_BATCH_SIZE", "99")

    assert boltodds_ws_worker._batch_size_from_env() == 7


def test_batch_size_env_keeps_legacy_ws_fallback(monkeypatch):
    monkeypatch.delenv("BOLTODDS_BATCH_SIZE", raising=False)
    monkeypatch.setenv("BOLTODDS_WS_BATCH_SIZE", "12")

    assert boltodds_ws_worker._batch_size_from_env() == 12


def test_import_does_not_require_websockets_dependency():
    module = importlib.reload(boltodds_ws_worker)

    assert module.__name__ == "scripts.boltodds_ws_worker"
    source = module.Path(module.__file__).read_text(encoding="utf-8")
    assert "\nimport websockets" not in source
    assert "\nfrom websockets" not in source


def test_live_requirements_pin_websockets_dependency():
    requirements = (boltodds_ws_worker.ROOT / "requirements-live.txt").read_text(
        encoding="utf-8"
    )

    assert "websockets==12.0" in requirements.splitlines()


def test_load_websockets_connect_raises_clear_runtime_error(monkeypatch):
    real_import = __import__

    def fake_import(name, *args, **kwargs):
        if name == "websockets":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", fake_import)

    with pytest.raises(RuntimeError) as exc_info:
        boltodds_ws_worker._load_websockets_connect()

    message = str(exc_info.value)
    assert "websockets is required" in message
    assert "requirements-live.txt" in message


def test_provider_startup_failure_marks_run_failed(monkeypatch):
    writer = FakeWriter()
    monkeypatch.setenv("BOLTODDS_API_KEY", "bolt-key")
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role")
    monkeypatch.setenv("SLATE_DATE", "2026-05-07")
    monkeypatch.setattr(
        boltodds_ws_worker,
        "_load_production_artifact",
        lambda slate_date=None, **kwargs: ({"date": "2026-05-07"}, "test-artifact.json"),
    )
    monkeypatch.setattr(
        boltodds_ws_worker,
        "SupabaseMarketWriter",
        lambda supabase_url, service_role_key: writer,
    )

    def fail_get_json(*args, **kwargs):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr(boltodds_ws_worker, "get_json", fail_get_json)

    with pytest.raises(RuntimeError, match="provider unavailable"):
        asyncio.run(boltodds_ws_worker.run_worker())

    assert writer.inserts[0][0] == "market_provider_runs"
    started = writer.inserts[0][1][0]
    assert started["status"] == "started"
    assert started["slate_date"] == "2026-05-07"
    assert writer.upserts[-1][0] == "market_provider_runs"
    failed = writer.upserts[-1][1][0]
    assert failed["id"] == started["id"]
    assert failed["status"] == "failed"
    assert failed["error_message"] == "provider unavailable"


def test_worker_flushes_pending_snapshots_when_stream_goes_quiet(monkeypatch):
    writer = FakeWriter()
    websocket = FakeWebSocket(
        [
            '{"data":{"sportsbook":"fanduel","info":{"id":"event-1"}}}',
            ("sleep", 0.03),
            RuntimeError("stop"),
        ]
    )
    _configure_worker(monkeypatch, writer, websocket)
    monkeypatch.setenv("BOLTODDS_FLUSH_SECONDS", "0.01")
    monkeypatch.setenv("BOLTODDS_BATCH_SIZE", "100")

    with pytest.raises(RuntimeError, match="stop"):
        asyncio.run(boltodds_ws_worker.run_worker())

    snapshot_upserts = [
        rows
        for table, rows, _conflict in writer.upserts
        if table == "market_snapshots"
    ]
    assert len(snapshot_upserts) == 1
    assert snapshot_upserts[0][0]["run_id"] == writer.inserts[0][1][0]["id"]


def test_worker_rotation_starts_new_run_before_writing_new_slate_snapshots(monkeypatch):
    writer = FakeWriter()
    websocket = FakeWebSocket(
        [
            '{"data":{"sportsbook":"fanduel","info":{"id":"event-1"}}}',
            ("sleep", 0.03),
            '{"data":{"sportsbook":"fanduel","info":{"id":"event-2"}}}',
        ]
    )
    _configure_worker(monkeypatch, writer, websocket, max_messages="2")
    monkeypatch.delenv("SLATE_DATE", raising=False)
    monkeypatch.setenv("BOLTODDS_FLUSH_SECONDS", "0.01")
    monkeypatch.setenv("BOLTODDS_BATCH_SIZE", "100")
    monkeypatch.setenv("BOLTODDS_ARTIFACT_REFRESH_SECONDS", "0.001")
    payloads = [
        ({"date": "2026-05-12", "pitchers": [{"pitcher": "Old Starter"}]}, "today.json"),
        ({"date": "2026-05-13", "pitchers": [{"pitcher": "New Starter"}]}, "today.json"),
    ]

    def fake_loader(*args, **kwargs):
        return payloads.pop(0)

    monkeypatch.setattr(boltodds_ws_worker, "_load_production_artifact", fake_loader)

    result = asyncio.run(boltodds_ws_worker.run_worker())

    run_rows = [
        rows[0]
        for table, rows in writer.inserts
        if table == "market_provider_runs"
    ]
    assert [row["slate_date"] for row in run_rows] == ["2026-05-12", "2026-05-13"]

    snapshot_upserts = [
        rows
        for table, rows, _conflict in writer.upserts
        if table == "market_snapshots"
    ]
    assert len(snapshot_upserts) == 2
    assert snapshot_upserts[0][0]["run_id"] == run_rows[0]["id"]
    assert snapshot_upserts[1][0]["run_id"] == run_rows[1]["id"]
    assert result["run_id"] == run_rows[1]["id"]
    assert result["slate_date"] == "2026-05-13"


def test_final_flush_failure_still_marks_run_failed(monkeypatch):
    writer = FakeWriter()
    websocket = FakeWebSocket(
        ['{"data":{"sportsbook":"fanduel","info":{"id":"event-1"}}}']
    )
    _configure_worker(monkeypatch, writer, websocket, max_messages="1")

    def fail_write_snapshot_batch(*args, **kwargs):
        raise RuntimeError("snapshot write failed")

    monkeypatch.setattr(
        boltodds_ws_worker,
        "write_snapshot_batch",
        fail_write_snapshot_batch,
    )

    with pytest.raises(RuntimeError, match="snapshot write failed"):
        asyncio.run(boltodds_ws_worker.run_worker())

    assert writer.upserts[-1][0] == "market_provider_runs"
    failed = writer.upserts[-1][1][0]
    assert failed["status"] == "failed"
    assert failed["error_message"] == "snapshot write failed"
