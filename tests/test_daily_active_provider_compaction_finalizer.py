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
        "rebuilt_compacts_sha256": f"rebuilt-{provider}",
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
            responses[provider] = [
                ("preflight", (pending, [{"provider": provider}])),
                ("fresh", (pending, [{"provider": provider}])),
            ]
        return cls(responses, events)


def _compact_proof(provider, *, exact=True):
    expected_hash = f"rebuilt-{provider}"
    return {
        "provider": provider,
        "slate_date": "2026-08-25",
        "expected_compact_count": 10,
        "actual_compact_count": 10 if exact else 9,
        "expected_compacts_sha256": expected_hash,
        "actual_compacts_sha256": expected_hash if exact else "different",
        "compact_state_exact": exact,
    }


class CompactVerificationSequence:
    def __init__(self, responses, events=None):
        self.responses = {
            provider: list(items) for provider, items in responses.items()
        }
        self.events = events if events is not None else []

    def __call__(
        self,
        *,
        provider,
        slate_date,
        writer,
        expected_compact_count,
        expected_compacts_sha256,
    ):
        self.events.append(("verify", provider))
        result = self.responses[provider].pop(0)
        if isinstance(result, Exception):
            raise result
        assert expected_compact_count == 10
        assert expected_compacts_sha256 == f"rebuilt-{provider}"
        return dict(result)

    @classmethod
    def exact_write_cycle(cls, events=None):
        return cls(
            {
                provider: [_compact_proof(provider)]
                for provider in ("propline", "therundown")
            },
            events,
        )


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


def test_omitted_slate_date_reports_phoenix_d_minus_one_source():
    finalizer = _module()

    assert finalizer._resolve_target_slate_date(
        now_utc=datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc),
        explicit_slate_date=None,
    ) == ("2026-08-26", "phoenix_d_minus_one")


def test_explicit_slate_date_targets_fixed_providers_and_reports_source(monkeypatch):
    finalizer = _module()
    calls = []

    def fake_preview(*, provider, slate_date, writer):
        calls.append((provider, slate_date))
        report = _report(provider)
        report["slate_date"] = slate_date
        return report, []

    monkeypatch.setattr(finalizer, "build_partition_preview", fake_preview)
    result = finalizer.run_finalizer(
        writer=RecordingWriter(),
        now_utc=datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc),
        slate_date="2026-08-19",
    )

    assert calls == [
        ("propline", "2026-08-19"),
        ("therundown", "2026-08-19"),
    ]
    assert result["target_slate_date"] == "2026-08-19"
    assert result["target_date_source"] == "explicit"
    assert result["database_write_attempted"] is False
    assert result["database_write_performed"] is False


@pytest.mark.parametrize(
    "explicit_slate_date",
    [
        "not-a-date",
        "2026-8-19",
        "2026-04-27",
        "2026-08-27",
        "2026-08-28",
    ],
)
def test_explicit_slate_date_rejects_unsafe_values_before_provider_reads(
    monkeypatch,
    explicit_slate_date,
):
    finalizer = _module()
    calls = []
    monkeypatch.setattr(
        finalizer,
        "build_partition_preview",
        lambda **kwargs: calls.append(kwargs),
    )

    with pytest.raises(ValueError):
        finalizer.run_finalizer(
            writer=RecordingWriter(),
            now_utc=datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc),
            slate_date=explicit_slate_date,
        )

    assert calls == []


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
    monkeypatch.setattr(
        finalizer,
        "verify_compact_partition_exact",
        CompactVerificationSequence.exact_write_cycle(events),
        raising=False,
    )
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
    monkeypatch.setattr(
        finalizer,
        "verify_compact_partition_exact",
        CompactVerificationSequence.exact_write_cycle(),
        raising=False,
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
    monkeypatch.setattr(
        finalizer,
        "verify_compact_partition_exact",
        CompactVerificationSequence.exact_write_cycle(),
        raising=False,
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
        ],
        "therundown": [
            (
                "preflight",
                (_report("therundown"), [{"provider": "therundown"}]),
            )
        ],
    })
    monkeypatch.setattr(finalizer, "build_partition_preview", sequence)
    monkeypatch.setattr(
        finalizer,
        "verify_compact_partition_exact",
        CompactVerificationSequence({
            "propline": [_compact_proof("propline", exact=False)],
        }),
        raising=False,
    )

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
    rundown_pending = _report("therundown", rows_to_upsert=1)
    sequence = PreviewSequence({
        "propline": [
            ("preflight", (propline_pending, [{"provider": "propline"}])),
            ("fresh", (propline_pending, [{"provider": "propline"}])),
        ],
        "therundown": [
            ("preflight", (rundown_pending, [{"provider": "therundown"}])),
            ("fresh", (rundown_pending, [{"provider": "therundown"}])),
        ],
    })
    monkeypatch.setattr(finalizer, "build_partition_preview", sequence)
    monkeypatch.setattr(
        finalizer,
        "verify_compact_partition_exact",
        CompactVerificationSequence({
            "propline": [_compact_proof("propline")],
            "therundown": [_compact_proof("therundown", exact=False)],
        }),
        raising=False,
    )

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
    sequence = PreviewSequence({
        "propline": [
            ("preflight", (propline_exact, [])),
            ("fresh", (propline_exact, [])),
        ],
        "therundown": [
            ("preflight", (rundown_pending, [{"provider": "therundown"}])),
            ("fresh", (rundown_pending, [{"provider": "therundown"}])),
        ],
    })
    monkeypatch.setattr(finalizer, "build_partition_preview", sequence)
    monkeypatch.setattr(
        finalizer,
        "verify_compact_partition_exact",
        CompactVerificationSequence({
            "therundown": [_compact_proof("therundown")],
        }),
        raising=False,
    )

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


def test_preview_crossing_deadline_on_last_read_returns_failed(monkeypatch):
    finalizer = _module()

    class MutableClock:
        value = 0.0

        def __call__(self):
            return self.value

    clock = MutableClock()

    def preview(*, provider, slate_date, writer):
        if provider == "therundown":
            clock.value = 5.0
        return _report(provider), [{"provider": provider}]

    monkeypatch.setattr(finalizer, "build_partition_preview", preview)
    result = finalizer.run_finalizer(
        writer=RecordingWriter(),
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
        monotonic_fn=clock,
        deadline_seconds=5.0,
    )

    assert result["status"] == "failed"
    assert result["deadline_exceeded"] is True
    assert result["database_write_attempted"] is False
    assert result["elapsed_seconds"] == 5.0


def test_execute_crossing_deadline_after_completed_upsert_preserves_write_state(
    monkeypatch,
):
    finalizer = _module()

    class MutableClock:
        value = 0.0

        def __call__(self):
            return self.value

    clock = MutableClock()
    writer = RecordingWriter()
    completed_writes = 0

    def cross_deadline_after_second_write(rows):
        nonlocal completed_writes
        completed_writes += 1
        if completed_writes == 2:
            clock.value = 5.0

    writer.on_upsert = cross_deadline_after_second_write
    monkeypatch.setattr(
        finalizer,
        "build_partition_preview",
        PreviewSequence.exact_write_cycle(),
    )
    monkeypatch.setattr(
        finalizer,
        "verify_compact_partition_exact",
        CompactVerificationSequence.exact_write_cycle(),
        raising=False,
    )

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
        monotonic_fn=clock,
        deadline_seconds=5.0,
    )

    second = result["provider_results"][1]
    assert result["status"] == "failed"
    assert result["deadline_exceeded"] is True
    assert second["execution_status"] == "failed"
    assert second["failure_reason"] == "deadline_exceeded_after_write"
    assert second["database_write_attempted"] is True
    assert second["database_write_performed"] is True
    assert len(writer.upserts) == 2


def test_execute_uses_at_most_two_full_previews_per_provider(monkeypatch):
    finalizer = _module()
    calls = []
    provider_counts = {"propline": 0, "therundown": 0}

    def preview(*, provider, slate_date, writer):
        provider_counts[provider] += 1
        calls.append(provider)
        rows_to_upsert = 0 if provider_counts[provider] == 3 else 1
        return _report(provider, rows_to_upsert=rows_to_upsert), (
            [] if rows_to_upsert == 0 else [{"provider": provider}]
        )

    monkeypatch.setattr(finalizer, "build_partition_preview", preview)
    monkeypatch.setattr(
        finalizer,
        "verify_compact_partition_exact",
        CompactVerificationSequence.exact_write_cycle(),
        raising=False,
    )

    result = finalizer.run_finalizer(
        writer=RecordingWriter(),
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )

    assert result["status"] == "success"
    assert calls == ["propline", "therundown", "propline", "therundown"]


def test_unexpected_preflight_exception_is_sanitized_and_second_read_runs(
    monkeypatch,
):
    finalizer = _module()
    calls = []

    def preview(*, provider, slate_date, writer):
        calls.append(provider)
        if provider == "propline":
            raise RuntimeError("sensitive-preflight-source-id")
        return _report(provider), [{"provider": provider}]

    monkeypatch.setattr(finalizer, "build_partition_preview", preview)
    result = finalizer.run_finalizer(
        writer=RecordingWriter(),
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )

    assert calls == ["propline", "therundown"]
    assert result["status"] == "failed"
    assert result["provider_results"][0]["error_type"] == "RuntimeError"
    assert "sensitive-preflight-source-id" not in json.dumps(result)


def test_unexpected_fresh_read_exception_is_sanitized_before_any_write(monkeypatch):
    finalizer = _module()
    writer = RecordingWriter()
    sequence = PreviewSequence({
        "propline": [
            ("preflight", (_report("propline"), [{"provider": "propline"}])),
            ("fresh", RuntimeError("sensitive-fresh-source-id")),
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

    first, second = result["provider_results"]
    assert result["status"] == "failed"
    assert first["execution_status"] == "failed"
    assert first["failure_reason"] == "fresh_preflight_failed"
    assert first["write_error_type"] == "RuntimeError"
    assert second["execution_status"] == "not_attempted_after_prior_failure"
    assert writer.upserts == []
    assert "sensitive-fresh-source-id" not in json.dumps(result)


def test_unexpected_upsert_exception_is_ambiguous_and_uses_exact_post_state(
    monkeypatch,
):
    finalizer = _module()
    writer = RecordingWriter()
    writer.upsert_errors = [RuntimeError("sensitive-upsert-body"), None]
    monkeypatch.setattr(
        finalizer,
        "build_partition_preview",
        PreviewSequence.exact_write_cycle(),
    )
    monkeypatch.setattr(
        finalizer,
        "verify_compact_partition_exact",
        CompactVerificationSequence.exact_write_cycle(),
    )

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )

    first = result["provider_results"][0]
    assert result["status"] == "success"
    assert first["execution_status"] == "confirmed_by_post_state"
    assert first["database_write_attempted"] is True
    assert first["database_write_performed"] is None
    assert first["write_error_type"] == "RuntimeError"
    assert len(writer.upserts) == 2
    assert "sensitive-upsert-body" not in json.dumps(result)


def test_unexpected_post_check_exception_preserves_known_successful_write(
    monkeypatch,
):
    finalizer = _module()
    writer = RecordingWriter()
    monkeypatch.setattr(
        finalizer,
        "build_partition_preview",
        PreviewSequence.exact_write_cycle(),
    )
    monkeypatch.setattr(
        finalizer,
        "verify_compact_partition_exact",
        CompactVerificationSequence({
            "propline": [RuntimeError("sensitive-post-state-body")],
        }),
    )

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )

    first, second = result["provider_results"]
    assert result["status"] == "failed"
    assert first["execution_status"] == "failed"
    assert first["failure_reason"] == "post_write_check_failed"
    assert first["database_write_attempted"] is True
    assert first["database_write_performed"] is True
    assert first["write_error_type"] == "RuntimeError"
    assert second["execution_status"] == "not_attempted_after_prior_failure"
    assert len(writer.upserts) == 1
    assert "sensitive-post-state-body" not in json.dumps(result)


def test_cli_accepts_no_arbitrary_date_or_provider(monkeypatch):
    finalizer = _module()
    with pytest.raises(SystemExit):
        finalizer._parse_args(["--date", "2026-08-25"])
    with pytest.raises(SystemExit):
        finalizer._parse_args(["--provider", "propline"])


def test_execute_cli_checks_exact_gate_before_loading_credentials(monkeypatch):
    finalizer = _module()
    monkeypatch.delenv(finalizer.WRITE_GATE_ENV, raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    assert finalizer.main(["--execute"]) == 3


def test_preview_cli_prints_one_aggregate_json_line(monkeypatch, capsys):
    finalizer = _module()
    monkeypatch.setattr(finalizer, "SupabaseMarketWriter", lambda *args: object())
    monkeypatch.setattr(
        finalizer,
        "run_finalizer",
        lambda **kwargs: {
            "report_type": "daily_active_provider_compaction_finalizer",
            "mode": "preview",
            "status": "success",
            "provider_results": [],
            "database_write_attempted": False,
            "database_write_performed": False,
            "provider_usage_rows_written": 0,
            "deletion_performed": False,
            "retention_execution_closed": True,
        },
    )
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret-value")

    assert finalizer.main([]) == 0
    captured = capsys.readouterr()
    assert len(captured.out.splitlines()) == 1
    assert json.loads(captured.out)["status"] == "success"
    assert "secret-value" not in captured.out + captured.err


def test_runtime_failure_returns_two_and_prints_no_exception_message(
    monkeypatch,
    capsys,
):
    finalizer = _module()
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret-value")
    monkeypatch.setattr(finalizer, "SupabaseMarketWriter", lambda *args: object())
    monkeypatch.setattr(
        finalizer,
        "run_finalizer",
        lambda **kwargs: {
            "report_type": "daily_active_provider_compaction_finalizer",
            "mode": "preview",
            "target_slate_date": "2026-08-25",
            "status": "failed",
            "preflight_complete": False,
            "provider_results": [{"provider": "propline", "error_type": "ValueError"}],
            "database_write_attempted": False,
            "database_write_performed": False,
            "provider_usage_rows_written": 0,
            "deletion_performed": False,
            "retention_execution_closed": True,
            "elapsed_seconds": 1.0,
        },
    )
    assert finalizer.main([]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out)["status"] == "failed"
    assert "secret-value" not in captured.out + captured.err


def test_configuration_failure_returns_three_with_static_error_code(monkeypatch, capsys):
    finalizer = _module()
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    assert finalizer.main([]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "daily_compaction_finalizer_config_error:OSError"


@pytest.mark.parametrize(
    "value",
    ["", "true", "1", "d1_active_providers_compact_only", "D1_ACTIVE_PROVIDERS"],
)
def test_execute_gate_requires_the_exact_literal_value(monkeypatch, value):
    finalizer = _module()
    monkeypatch.setenv(finalizer.WRITE_GATE_ENV, value)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    assert finalizer.main(["--execute"]) == 3


def test_summary_serialization_rejects_unapproved_top_level_fields():
    finalizer = _module()
    report = {
        "report_type": "daily_active_provider_compaction_finalizer",
        "status": "success",
        "provider_results": [{
            "provider": "propline",
            "execution_status": "no_op",
            "canonical_rows": [{"source_snapshot_ids": ["nested-secret-id"]}],
        }],
        "canonical_rows": [{"source_snapshot_ids": ["secret-id"]}],
        "credentials": "secret-value",
    }
    safe = finalizer._safe_summary(report)
    assert safe == {
        "report_type": "daily_active_provider_compaction_finalizer",
        "status": "success",
        "provider_results": [{
            "provider": "propline",
            "execution_status": "no_op",
        }],
    }
    assert "secret-id" not in json.dumps(safe)
    assert "nested-secret-id" not in json.dumps(safe)
    assert "secret-value" not in json.dumps(safe)


def test_cli_rejection_does_not_echo_sensitive_argument(capsys):
    finalizer = _module()
    sensitive_value = "https://opaque-source.example/token-secret"

    assert finalizer.main(["--date", sensitive_value]) == 3

    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "daily_compaction_finalizer_config_error:CliArgumentError"
    assert sensitive_value not in captured.out + captured.err


def test_unexpected_runtime_error_prints_only_static_redacted_error(monkeypatch, capsys):
    finalizer = _module()
    sensitive_message = "opaque-source-id-and-token"
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret-value")
    monkeypatch.setattr(finalizer, "SupabaseMarketWriter", lambda *args: object())

    def unexpected_failure(**kwargs):
        raise RuntimeError(sensitive_message)

    monkeypatch.setattr(finalizer, "run_finalizer", unexpected_failure)

    assert finalizer.main([]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "daily_compaction_finalizer_runtime_error:UnhandledError"
    assert sensitive_message not in captured.out + captured.err
    assert "secret-value" not in captured.out + captured.err
