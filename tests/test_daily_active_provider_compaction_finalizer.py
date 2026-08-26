from datetime import datetime, timezone, tzinfo
import importlib
import json

import pytest
import requests


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


class PreviewSequence:
    def __init__(self, responses, events=None):
        self.responses = {
            provider: list(items) for provider, items in responses.items()
        }
        self.events = events if events is not None else []

    def __call__(self, *, provider, slate_date, writer):
        phase, result = self.responses[provider].pop(0)
        self.events.append((phase, provider))
        if isinstance(result, Exception):
            raise result
        report, rows = result
        return dict(report), [dict(row) for row in rows]

    @classmethod
    def exact_write_cycle(cls, events=None):
        responses = {}
        for provider in ("propline", "therundown"):
            pending = _report(provider, rows_to_upsert=1)
            exact = _report(provider, rows_to_upsert=0)
            responses[provider] = [
                ("preflight", (pending, [{"provider": provider}])),
                ("fresh", (pending, [{"provider": provider}])),
                ("post", (exact, [])),
            ]
        return cls(responses, events)


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


def test_target_rejects_tzinfo_with_no_utcoffset():
    finalizer = _module()

    class NoOffsetTZ(tzinfo):
        def utcoffset(self, dt):
            return None

    with pytest.raises(ValueError, match="timezone-aware"):
        finalizer._target_slate_date(
            datetime(2026, 8, 26, 12, tzinfo=NoOffsetTZ())
        )


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


def test_execute_requires_allow_gate_before_any_provider_read(monkeypatch):
    finalizer = _module()
    writer = RecordingWriter()

    try:
        finalizer.run_finalizer(writer=writer, execute=True, allow_execute=False)
    except ValueError as error:
        assert str(error) == "daily active-provider compaction write gate is closed"
    else:
        raise AssertionError("closed execute gate did not fail")

    assert writer.selects == []
    assert writer.upserts == []


def test_execute_preflights_both_providers_before_first_upsert(monkeypatch):
    finalizer = _module()
    events = []
    writer = RecordingWriter()
    sequence = PreviewSequence.exact_write_cycle(events)
    monkeypatch.setattr(finalizer, "build_partition_preview", sequence)
    writer.on_upsert = lambda rows: events.append(("upsert", rows[0]["provider"]))

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )

    first_upsert = next(
        index for index, event in enumerate(events) if event[0] == "upsert"
    )
    assert ("preflight", "propline") in events[:first_upsert]
    assert ("preflight", "therundown") in events[:first_upsert]
    assert result["status"] == "success"


def test_any_preflight_failure_causes_zero_upserts(monkeypatch):
    finalizer = _module()
    writer = RecordingWriter()
    sequence = PreviewSequence({
        "propline": [("preflight", ValueError("sensitive"))],
        "therundown": [
            (
                "preflight",
                (_report("therundown"), [{"provider": "therundown"}]),
            )
        ],
    })
    monkeypatch.setattr(finalizer, "build_partition_preview", sequence)

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert result["status"] == "failed"
    assert result["preflight_complete"] is False
    assert writer.upserts == []


def test_source_drift_before_first_write_causes_zero_upserts(monkeypatch):
    finalizer = _module()
    writer = RecordingWriter()
    sequence = PreviewSequence({
        "propline": [
            (
                "preflight",
                (
                    _report("propline", source_hash="source-a"),
                    [{"provider": "propline"}],
                ),
            ),
            (
                "fresh",
                (
                    _report("propline", source_hash="source-b"),
                    [{"provider": "propline"}],
                ),
            ),
        ],
        "therundown": [
            (
                "preflight",
                (_report("therundown"), [{"provider": "therundown"}]),
            )
        ],
    })
    monkeypatch.setattr(finalizer, "build_partition_preview", sequence)

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert result["provider_results"][0]["failure_reason"] == "source_state_drift"
    assert (
        result["provider_results"][1]["execution_status"]
        == "not_attempted_after_prior_failure"
    )
    assert writer.upserts == []


def test_exact_partitions_are_idempotent_no_ops(monkeypatch):
    finalizer = _module()
    writer = RecordingWriter()
    responses = {}
    for provider in ("propline", "therundown"):
        exact = _report(provider, rows_to_upsert=0)
        responses[provider] = [
            ("preflight", (exact, [])),
            ("fresh", (exact, [])),
        ]
    monkeypatch.setattr(finalizer, "build_partition_preview", PreviewSequence(responses))

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert [row["execution_status"] for row in result["provider_results"]] == [
        "no_op",
        "no_op",
    ]
    assert result["database_write_attempted"] is False
    assert writer.upserts == []


def test_successful_upsert_uses_one_attempt_and_return_minimal(monkeypatch):
    finalizer = _module()
    writer = RecordingWriter()
    monkeypatch.setattr(
        finalizer,
        "build_partition_preview",
        PreviewSequence.exact_write_cycle(),
    )

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert result["status"] == "success"
    assert len(writer.upserts) == 2
    for table, rows, on_conflict, kwargs in writer.upserts:
        assert table == "compact_market_line_movements"
        assert len(rows) == 1
        assert on_conflict == finalizer.ON_CONFLICT
        assert kwargs["attempts"] == 1
        assert kwargs["return_representation"] is False


def test_ambiguous_upsert_is_success_only_when_post_state_is_exact(monkeypatch):
    finalizer = _module()
    writer = RecordingWriter()
    writer.upsert_errors = [requests.Timeout("sensitive-timeout"), None]
    monkeypatch.setattr(
        finalizer,
        "build_partition_preview",
        PreviewSequence.exact_write_cycle(),
    )

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert (
        result["provider_results"][0]["execution_status"]
        == "confirmed_by_post_state"
    )
    assert result["provider_results"][0]["database_write_performed"] is None
    assert "sensitive-timeout" not in json.dumps(result)


def test_ambiguous_inexact_upsert_fails_and_prevents_second_write(monkeypatch):
    finalizer = _module()
    writer = RecordingWriter()
    writer.upsert_errors = [requests.Timeout("ambiguous")]
    pending = _report("propline", rows_to_upsert=1)
    sequence = PreviewSequence({
        "propline": [
            ("preflight", (pending, [{"provider": "propline"}])),
            ("fresh", (pending, [{"provider": "propline"}])),
            ("post", (pending, [{"provider": "propline"}])),
        ],
        "therundown": [
            (
                "preflight",
                (_report("therundown"), [{"provider": "therundown"}]),
            )
        ],
    })
    monkeypatch.setattr(finalizer, "build_partition_preview", sequence)

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert result["status"] == "failed"
    assert result["provider_results"][0]["post_write_exact"] is False
    assert (
        result["provider_results"][1]["execution_status"]
        == "not_attempted_after_prior_failure"
    )
    assert len(writer.upserts) == 1


def test_second_provider_failure_reports_bounded_partial_state(monkeypatch):
    finalizer = _module()
    writer = RecordingWriter()
    writer.upsert_errors = [None, requests.Timeout("ambiguous")]
    propline_pending = _report("propline", rows_to_upsert=1)
    propline_exact = _report("propline", rows_to_upsert=0)
    rundown_pending = _report("therundown", rows_to_upsert=1)
    sequence = PreviewSequence({
        "propline": [
            ("preflight", (propline_pending, [{"provider": "propline"}])),
            ("fresh", (propline_pending, [{"provider": "propline"}])),
            ("post", (propline_exact, [])),
        ],
        "therundown": [
            ("preflight", (rundown_pending, [{"provider": "therundown"}])),
            ("fresh", (rundown_pending, [{"provider": "therundown"}])),
            ("post", (rundown_pending, [{"provider": "therundown"}])),
        ],
    })
    monkeypatch.setattr(finalizer, "build_partition_preview", sequence)

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert result["status"] == "failed"
    assert result["provider_results"][0]["execution_status"] == "confirmed"
    assert result["provider_results"][1]["execution_status"] == "failed"
    assert result["database_write_attempted"] is True


def test_retry_treats_completed_first_provider_as_no_op(monkeypatch):
    finalizer = _module()
    writer = RecordingWriter()
    propline_exact = _report("propline", rows_to_upsert=0)
    rundown_pending = _report("therundown", rows_to_upsert=1)
    rundown_exact = _report("therundown", rows_to_upsert=0)
    sequence = PreviewSequence({
        "propline": [
            ("preflight", (propline_exact, [])),
            ("fresh", (propline_exact, [])),
        ],
        "therundown": [
            ("preflight", (rundown_pending, [{"provider": "therundown"}])),
            ("fresh", (rundown_pending, [{"provider": "therundown"}])),
            ("post", (rundown_exact, [])),
        ],
    })
    monkeypatch.setattr(finalizer, "build_partition_preview", sequence)

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert result["provider_results"][0]["execution_status"] == "no_op"
    assert result["provider_results"][1]["execution_status"] == "confirmed"
    assert len(writer.upserts) == 1
    assert writer.upserts[0][1][0]["provider"] == "therundown"


def test_deadline_expiry_before_upsert_performs_zero_new_writes(monkeypatch):
    finalizer = _module()
    underlying = RecordingWriter()
    sequence = PreviewSequence({
        "propline": [
            (
                "preflight",
                (_report("propline"), [{"provider": "propline"}]),
            ),
            ("fresh", (_report("propline"), [{"provider": "propline"}])),
        ],
        "therundown": [
            (
                "preflight",
                (_report("therundown"), [{"provider": "therundown"}]),
            )
        ],
    })
    monkeypatch.setattr(finalizer, "build_partition_preview", sequence)

    class TickingClock:
        def __init__(self):
            self.value = -1.0

        def __call__(self):
            self.value += 1.0
            return self.value

    result = finalizer.run_finalizer(
        writer=underlying,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
        monotonic_fn=TickingClock(),
        deadline_seconds=3.5,
    )
    assert result["status"] == "failed"
    assert result["deadline_exceeded"] is True
    assert underlying.upserts == []
