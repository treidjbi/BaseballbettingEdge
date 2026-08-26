from datetime import datetime, timezone
import importlib
import json

import pytest


def _module():
    return importlib.import_module(
        "scripts.run_daily_active_provider_compaction_finalizer"
    )


class RecordingWriter:
    def __init__(self):
        self.selects = []
        self.upserts = []
        self.on_upsert = None
        self.upsert_errors = []

    def select_rows(self, table, params, **kwargs):
        self.selects.append((table, dict(params), dict(kwargs)))
        return []

    def upsert_rows(self, table, rows, on_conflict, **kwargs):
        self.upserts.append((table, list(rows), on_conflict, dict(kwargs)))
        if self.on_upsert is not None:
            self.on_upsert(rows)
        if self.upsert_errors:
            error = self.upsert_errors.pop(0)
            if error is not None:
                raise error
        return []


def _report(provider, *, blockers=(), rows_to_upsert=1, source_hash=None):
    return {
        "provider": provider,
        "slate_date": "2026-08-25",
        "provider_run_count": 2,
        "heartbeat_row_count": 3,
        "in_window_heartbeat_count": 3,
        "out_of_window_heartbeat_count": 0,
        "raw_snapshot_count": 100,
        "snapshot_in_window_count": 100,
        "snapshot_out_of_window_count": 0,
        "first_source_observed_at": "2026-08-25T14:00:00Z",
        "last_source_observed_at": "2026-08-26T01:00:00Z",
        "rebuilt_compact_count": 10,
        "existing_compact_count": 9,
        "missing_compact_count": rows_to_upsert,
        "mismatched_compact_count": 0,
        "unexpected_compact_count": 0,
        "rows_to_upsert_count": rows_to_upsert,
        "evidence_blockers": list(blockers),
        "source_state_sha256": source_hash or f"source-{provider}",
        "preview_sha256": f"preview-{provider}",
    }


def test_preview_targets_phoenix_d_minus_one_in_fixed_provider_order(monkeypatch):
    finalizer = _module()
    calls = []
    writer = RecordingWriter()

    def fake_preview(*, provider, slate_date, writer):
        calls.append((provider, slate_date))
        return _report(provider), [{"provider": provider}]

    monkeypatch.setattr(finalizer, "build_partition_preview", fake_preview)
    result = finalizer.run_finalizer(
        writer=writer,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )

    assert calls == [
        ("propline", "2026-08-25"),
        ("therundown", "2026-08-25"),
    ]
    assert result["mode"] == "preview"
    assert result["status"] == "success"
    assert result["database_write_attempted"] is False
    assert result["database_write_performed"] is False
    assert result["deletion_performed"] is False
    assert writer.upserts == []


def test_phoenix_target_is_stable_across_utc_date_boundary():
    finalizer = _module()
    now_utc = datetime(2026, 8, 26, 2, 0, tzinfo=timezone.utc)
    assert finalizer._target_slate_date(now_utc) == "2026-08-24"


def test_preview_allows_would_upserts_but_blocks_unexpected_compacts(monkeypatch):
    finalizer = _module()

    def would_upsert(*, provider, slate_date, writer):
        return _report(provider, rows_to_upsert=4), [
            {"provider": provider, "row": index} for index in range(4)
        ]

    monkeypatch.setattr(finalizer, "build_partition_preview", would_upsert)
    clean = finalizer.run_finalizer(
        writer=RecordingWriter(),
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert clean["status"] == "success"
    assert [row["rows_to_upsert_count"] for row in clean["provider_results"]] == [4, 4]

    def unexpected(*, provider, slate_date, writer):
        report = _report(provider, blockers=("unexpected_compact_rows",))
        report["unexpected_compact_count"] = 1
        return report, []

    monkeypatch.setattr(finalizer, "build_partition_preview", unexpected)
    blocked = finalizer.run_finalizer(
        writer=RecordingWriter(),
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert blocked["status"] == "failed"
    assert blocked["preflight_complete"] is False


def test_first_provider_exception_is_sanitized_and_second_preflight_still_runs(
    monkeypatch,
):
    finalizer = _module()
    calls = []

    def preview(*, provider, slate_date, writer):
        calls.append(provider)
        if provider == "propline":
            raise ValueError("player-and-source-id-must-not-leak")
        return _report(provider), [{"provider": provider}]

    monkeypatch.setattr(finalizer, "build_partition_preview", preview)
    result = finalizer.run_finalizer(
        writer=RecordingWriter(),
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    encoded = json.dumps(result, sort_keys=True)
    assert calls == ["propline", "therundown"]
    assert result["status"] == "failed"
    assert result["provider_results"][0]["error_type"] == "ValueError"
    assert "player-and-source-id-must-not-leak" not in encoded


def test_preview_summary_contains_no_canonical_rows_or_source_ids(monkeypatch):
    finalizer = _module()

    def preview(*, provider, slate_date, writer):
        return _report(provider), [{
            "provider": provider,
            "player_name": "Sensitive Pitcher",
            "source_snapshot_ids": ["sensitive-source-id"],
        }]

    monkeypatch.setattr(finalizer, "build_partition_preview", preview)
    result = finalizer.run_finalizer(
        writer=RecordingWriter(),
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    encoded = json.dumps(result, sort_keys=True)
    assert "Sensitive Pitcher" not in encoded
    assert "sensitive-source-id" not in encoded
    assert "canonical_rows" not in encoded


def test_deadline_bound_writer_refuses_requests_at_or_after_cutoff():
    finalizer = _module()
    underlying = RecordingWriter()

    def expired():
        raise finalizer.FinalizerDeadlineExceeded("daily finalizer deadline exceeded")

    writer = finalizer._DeadlineBoundWriter(underlying, expired)
    with pytest.raises(finalizer.FinalizerDeadlineExceeded):
        writer.select_rows("market_snapshots", {"limit": "1"}, attempts=1)
    with pytest.raises(finalizer.FinalizerDeadlineExceeded):
        writer.upsert_rows(
            "compact_market_line_movements",
            [{"safe": "aggregate"}],
            "slate_date,provider",
            attempts=1,
        )
    assert underlying.selects == []
    assert underlying.upserts == []
