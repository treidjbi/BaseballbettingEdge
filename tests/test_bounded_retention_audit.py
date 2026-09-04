from __future__ import annotations

import copy
import hashlib
import inspect
import json
import subprocess
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import Mock
from zoneinfo import ZoneInfo

import pytest

from scripts import bounded_retention_audit as audit
from scripts import build_season_retention_readiness as readiness


@pytest.fixture(autouse=True)
def fixed_cli_version(monkeypatch, request):
    monkeypatch.setattr(
        audit, "_phoenix_today", lambda: date(2026, 8, 18), raising=False,
    )
    if request.node.name.startswith("test_resolve_cli_version"):
        return
    monkeypatch.setattr(audit, "resolve_cli_version", Mock(return_value="2.48.3"), raising=False)


def make_checkpoint(
    provider: str,
    start_date: date,
    days: int,
    elapsed_seconds: float,
) -> audit.CheckpointRecord:
    end_date = start_date + timedelta(days=days - 1)
    return audit.CheckpointRecord(
        path=Path(f"checkpoint-{provider}-{start_date}-{end_date}.json"),
        provider=provider,
        start_date=start_date,
        end_date=end_date,
        elapsed_seconds=elapsed_seconds,
        query_contract_sha256="a" * 64,
        rendered_sql_sha256="b" * 64,
        scope_fingerprint="c" * 64,
        cli_version="2.48.3",
        payload={},
    )


def valid_payload(chunk: audit.ChunkSpec) -> dict:
    coverage = []
    anomalies = []
    runtime = []
    cursor = chunk.start_date
    while cursor <= chunk.end_date:
        slate_date = cursor.isoformat()
        coverage.append({
            "slate_date": slate_date,
            "provider": chunk.provider,
            "raw_snapshot_rows": 2,
            "raw_logical_bytes": 20,
            "raw_group_count": 1,
            "compact_group_count": 1,
            "exact_group_count": 1,
            "mismatched_group_count": 0,
            "missing_compact_group_count": 0,
            "unexpected_compact_group_count": 0,
            "preserved_unexpected_compact_group_count": 0,
            "unpreserved_unexpected_compact_group_count": 0,
            "duplicate_compact_group_count": 0,
            "first_seen_mismatch_count": 0,
            "last_seen_mismatch_count": 0,
            "first_odds_mismatch_count": 0,
            "last_odds_mismatch_count": 0,
            "min_odds_mismatch_count": 0,
            "max_odds_mismatch_count": 0,
            "odds_move_count_mismatch_count": 0,
            "snapshot_count_mismatch_count": 0,
            "coverage_exact": True,
            "retention_preservation_complete": True,
            "first_raw_seen_at": "2026-04-28T12:00:00Z",
            "last_raw_seen_at": "2026-04-28T12:01:00Z",
        })
        anomalies.append({
            "slate_date": slate_date,
            "provider": chunk.provider,
            "rows_missing_run_id": 0,
            "rows_missing_run_row": 0,
            "rows_missing_group_key": 0,
            "provider_run_mismatch_rows": 0,
            "slate_date_mismatch_rows": 0,
            "preserved_slate_date_mismatch_rows": 0,
            "unpreserved_slate_date_mismatch_rows": 0,
            "unknown_provider_rows": 0,
        })
        runtime.append({
            "slate_date": slate_date,
            "provider": chunk.provider,
            "first_run_at": "2026-04-28T12:00:00Z",
            "last_run_at": "2026-04-28T12:01:00Z",
            "run_count": 1,
            "completed_run_count": 1,
            "failed_run_count": 0,
            "request_count": 1,
            "books_seen": ["fanduel"],
            "first_snapshot_at": "2026-04-28T12:00:00Z",
            "last_snapshot_at": "2026-04-28T12:01:00Z",
            "snapshot_count": 2,
            "snapshot_logical_bytes": 20,
            "last_heartbeat_at": None,
            "last_message_at": None,
            "heartbeat_count": 0,
        })
        cursor += timedelta(days=1)
    return {
        "chunk_version": 2,
        "audit_generated_at": "2026-08-18T12:00:00Z",
        "complete": True,
        "query_scope": {
            "start_date": chunk.start_date.isoformat(),
            "end_date": chunk.end_date.isoformat(),
            "provider": chunk.provider,
            "timezone": "America/Phoenix",
        },
        "coverage": coverage,
        "source_anomalies": anomalies,
        "candidate_runtime": runtime,
    }


def valid_runtime_payload(scope: audit.AuditScope) -> dict:
    return {
        "runtime_version": 2,
        "generated_at": "2026-08-18T12:00:00Z",
        "candidate_end_date": scope.candidate_end_date.isoformat(),
        "providers": [
            {
                "provider": provider,
                "current_latest_run_at": None,
                "current_latest_snapshot_at": None,
                "current_latest_heartbeat_at": None,
                "current_latest_message_at": None,
                "candidate_latest_run_at": None,
                "candidate_latest_snapshot_at": None,
                "candidate_latest_heartbeat_at": None,
                "candidate_latest_message_at": None,
                "post_boltodds_suspension": False,
            }
            for provider in scope.providers
        ],
    }


def make_zero_partition(payload: dict, index: int = 0) -> None:
    coverage = payload["coverage"][index]
    for field in (
        "raw_snapshot_rows",
        "raw_logical_bytes",
        "raw_group_count",
        "compact_group_count",
        "exact_group_count",
        "mismatched_group_count",
        "missing_compact_group_count",
        "unexpected_compact_group_count",
        "preserved_unexpected_compact_group_count",
        "unpreserved_unexpected_compact_group_count",
        "duplicate_compact_group_count",
        "first_seen_mismatch_count",
        "last_seen_mismatch_count",
        "first_odds_mismatch_count",
        "last_odds_mismatch_count",
        "min_odds_mismatch_count",
        "max_odds_mismatch_count",
        "odds_move_count_mismatch_count",
        "snapshot_count_mismatch_count",
    ):
        coverage[field] = 0
    coverage["first_raw_seen_at"] = None
    coverage["last_raw_seen_at"] = None
    coverage["coverage_exact"] = True
    coverage["retention_preservation_complete"] = True
    runtime = payload["candidate_runtime"][index]
    runtime.update({
        "first_run_at": None,
        "last_run_at": None,
        "run_count": 0,
        "completed_run_count": 0,
        "failed_run_count": 0,
        "request_count": 0,
        "books_seen": [],
        "first_snapshot_at": None,
        "last_snapshot_at": None,
        "snapshot_count": 0,
        "snapshot_logical_bytes": 0,
        "last_heartbeat_at": None,
        "last_message_at": None,
        "heartbeat_count": 0,
    })


@pytest.fixture
def checkpoint_factory():
    def factory(provider: str, days: int, elapsed: float) -> audit.CheckpointRecord:
        return make_checkpoint(provider, date(2026, 4, 28), days, elapsed)

    return factory


def test_build_scope_uses_clean_regime_and_inclusive_thirty_day_cutoff():
    scope = audit.build_scope("2026-08-18")
    assert scope == audit.AuditScope(
        as_of_date=date(2026, 8, 18),
        start_date=date(2026, 4, 28),
        candidate_end_date=date(2026, 7, 19),
        first_protected_date=date(2026, 7, 20),
        raw_retention_days=30,
        providers=("boltodds", "propline", "the_odds", "therundown"),
    )


def test_expected_partitions_has_every_provider_date_in_canonical_order():
    scope = audit.build_scope("2026-05-28")
    assert audit.expected_partitions(scope) == (
        ("boltodds", "2026-04-28"),
        ("propline", "2026-04-28"),
        ("the_odds", "2026-04-28"),
        ("therundown", "2026-04-28"),
    )


@pytest.mark.parametrize(
    ("previous_days", "elapsed", "expected"),
    [
        (1, 29.9, 3),
        (3, 30.0, 7),
        (7, 2.0, 7),
        (1, 30.1, 1),
        (3, 31.0, 1),
        (7, 31.0, 3),
    ],
)
def test_preferred_chunk_days_promotes_fast_and_deescalates_slow(
    checkpoint_factory, previous_days, elapsed, expected,
):
    checkpoints = [checkpoint_factory("boltodds", previous_days, elapsed)]
    assert audit.preferred_chunk_days(checkpoints, "boltodds") == expected


def test_select_next_chunk_starts_each_new_provider_with_one_date():
    scope = audit.build_scope("2026-06-03")
    checkpoints: list[audit.CheckpointRecord] = []

    for provider in scope.providers:
        chunk = audit.select_next_chunk(scope, checkpoints)
        assert chunk == audit.ChunkSpec(provider, scope.start_date, scope.start_date)
        checkpoints.append(
            make_checkpoint(
                provider,
                scope.start_date,
                (scope.candidate_end_date - scope.start_date).days + 1,
                10.0,
            )
        )

    assert audit.select_next_chunk(scope, checkpoints) is None


def test_select_next_chunk_uses_earliest_gap_and_stops_before_existing_range():
    scope = audit.build_scope("2026-06-08")
    checkpoints = [
        make_checkpoint("boltodds", date(2026, 4, 28), 1, 10.0),
        make_checkpoint("boltodds", date(2026, 5, 2), 3, 10.0),
    ]
    assert audit.select_next_chunk(scope, checkpoints) == audit.ChunkSpec(
        "boltodds", date(2026, 4, 29), date(2026, 5, 1),
    )


def test_select_next_chunk_never_overlaps_or_exceeds_seven_dates():
    scope = audit.build_scope("2026-06-20")
    checkpoints = [
        make_checkpoint("boltodds", date(2026, 4, 28), 7, 2.0),
    ]
    chunk = audit.select_next_chunk(scope, checkpoints)
    assert chunk == audit.ChunkSpec("boltodds", date(2026, 5, 5), date(2026, 5, 11))
    assert chunk.days == 7


def test_run_linked_query_uses_fixed_safe_argv_temp_file_and_timeout(monkeypatch):
    completed = subprocess.CompletedProcess([], 0, stdout="[]", stderr="")
    run = Mock(return_value=completed)
    unlinked: list[str] = []
    monkeypatch.setattr(audit.shutil, "which", lambda name: "C:/bin/npx.cmd" if name == "npx" else None)
    monkeypatch.setattr(audit.subprocess, "run", run)
    monkeypatch.setattr(audit.os, "unlink", lambda path: unlinked.append(path))

    result = audit.run_linked_query("select 1;")

    assert result is completed
    argv = run.call_args.args[0]
    assert argv[:5] == ["C:/bin/npx.cmd", "supabase", "db", "query", "--linked"]
    assert argv[5] == "--file"
    assert argv[7:] == ["-o", "json"]
    assert Path(argv[6]).suffix == ".sql"
    assert run.call_args.kwargs == {
        "check": False,
        "capture_output": True,
        "text": True,
        "shell": False,
        "timeout": 120,
    }
    assert unlinked == [argv[6]]
    Path(argv[6]).unlink(missing_ok=True)


def test_run_linked_query_closes_mocked_temp_file_before_subprocess(monkeypatch):
    class FakeSqlFile:
        name = "C:/temp/bounded-audit.sql"
        closed = False
        contents = ""

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            self.closed = True

        def write(self, value):
            self.contents += value

    sql_file = FakeSqlFile()
    named_temp = Mock(return_value=sql_file)
    unlink = Mock()

    def checked_run(argv, **_kwargs):
        assert sql_file.closed is True
        assert sql_file.contents == "select 1;"
        assert argv[6] == sql_file.name
        return subprocess.CompletedProcess(argv, 0, "[]", "")

    monkeypatch.setattr(audit.tempfile, "NamedTemporaryFile", named_temp)
    monkeypatch.setattr(audit.shutil, "which", lambda _name: "npx")
    monkeypatch.setattr(audit.subprocess, "run", checked_run)
    monkeypatch.setattr(audit.os, "unlink", unlink)

    audit.run_linked_query("select 1;")

    assert named_temp.call_args.kwargs == {
        "mode": "w",
        "suffix": ".sql",
        "delete": False,
        "encoding": "utf-8",
        "newline": "\n",
    }
    unlink.assert_called_once_with(sql_file.name)


def test_resolve_cli_version_uses_safe_fixed_local_preflight(monkeypatch):
    completed = subprocess.CompletedProcess([], 0, "2.48.3\n", "")
    run = Mock(return_value=completed)
    monkeypatch.setattr(audit.shutil, "which", lambda name: "C:/bin/npx.cmd" if name == "npx" else None)
    monkeypatch.setattr(audit.subprocess, "run", run)

    assert audit.resolve_cli_version() == "2.48.3"
    assert run.call_args.args[0] == ["C:/bin/npx.cmd", "supabase", "--version"]
    assert run.call_args.kwargs == {
        "check": False,
        "capture_output": True,
        "text": True,
        "shell": False,
        "timeout": audit.CLI_VERSION_TIMEOUT_SECONDS,
    }


@pytest.mark.parametrize(
    "completed",
    [
        subprocess.CompletedProcess([], 1, "", "lookup failed"),
        subprocess.CompletedProcess([], 0, "not-a-version", ""),
        subprocess.CompletedProcess([], 0, "", ""),
    ],
)
def test_resolve_cli_version_fails_closed_on_lookup_or_parse_failure(monkeypatch, completed):
    monkeypatch.setattr(audit.subprocess, "run", Mock(return_value=completed))
    with pytest.raises(audit.AuditFailure, match="subprocess_failed"):
        audit.resolve_cli_version()


def test_parse_supabase_object_requires_one_row_and_object_column():
    assert audit.parse_supabase_object('[{"result": {"complete": true}}]', "result") == {
        "complete": True,
    }
    for stdout in ("[]", "[{}, {}]", '[{"result": "{}"}]'):
        with pytest.raises(ValueError):
            audit.parse_supabase_object(stdout, "result")


def test_parse_supabase_object_accepts_supabase_cli_safety_envelope():
    stdout = json.dumps(
        {
            "boundary": "supabase-query-result",
            "rows": [{"result": {"complete": True}}],
            "warning": "Query results contain untrusted data.",
        }
    )

    assert audit.parse_supabase_object(stdout, "result") == {"complete": True}


def test_validate_chunk_payload_accepts_exact_partitions_and_equations():
    chunk = audit.ChunkSpec("propline", date(2026, 5, 1), date(2026, 5, 3))
    audit.validate_chunk_payload(valid_payload(chunk), chunk)


def test_validate_chunk_accepts_strict_extra_when_canonical_preservation_is_complete():
    chunk = audit.ChunkSpec("boltodds", date(2026, 5, 17), date(2026, 5, 17))
    payload = valid_payload(chunk)
    payload["coverage"][0].update({
        "compact_group_count": 2,
        "unexpected_compact_group_count": 1,
        "preserved_unexpected_compact_group_count": 1,
        "unpreserved_unexpected_compact_group_count": 0,
        "coverage_exact": False,
        "retention_preservation_complete": True,
    })
    audit.validate_chunk_payload(payload, chunk)


@pytest.mark.parametrize(
    "updates",
    [
        {
            "compact_group_count": 2,
            "unexpected_compact_group_count": 1,
        },
        {
            "compact_group_count": 2,
            "unexpected_compact_group_count": 1,
            "preserved_unexpected_compact_group_count": 2,
        },
        {"unpreserved_unexpected_compact_group_count": 1},
        {"retention_preservation_complete": False},
    ],
)
def test_validate_chunk_rejects_preservation_equation_or_boolean_contradiction(updates):
    chunk = audit.ChunkSpec("boltodds", date(2026, 5, 17), date(2026, 5, 17))
    payload = valid_payload(chunk)
    payload["coverage"][0].update(updates)
    with pytest.raises(ValueError, match="preservation"):
        audit.validate_chunk_payload(payload, chunk)


@pytest.mark.parametrize(
    ("target", "injected_key"),
    [
        ("payload", "raw_checkpoint_rows"),
        ("coverage", "raw_checkpoint_rows"),
        ("source_anomalies", "authorization"),
        ("candidate_runtime", "cleanup_sql"),
    ],
)
def test_validate_chunk_payload_rejects_unknown_nested_evidence_fields(
    target, injected_key,
):
    chunk = audit.ChunkSpec("propline", date(2026, 5, 1), date(2026, 5, 1))
    payload = valid_payload(chunk)
    if target == "payload":
        payload[injected_key] = [{"sensitive": True}]
    else:
        payload[target][0][injected_key] = "must-not-flow"
    with pytest.raises(ValueError, match=rf"{target}.*{injected_key}"):
        audit.validate_chunk_payload(payload, chunk)


def test_validate_chunk_payload_accepts_fully_preserved_cross_date_lineage():
    chunk = audit.ChunkSpec("boltodds", date(2026, 4, 28), date(2026, 4, 28))
    payload = valid_payload(chunk)
    payload["source_anomalies"][0].update({
        "slate_date_mismatch_rows": 2,
        "preserved_slate_date_mismatch_rows": 2,
        "unpreserved_slate_date_mismatch_rows": 0,
    })

    audit.validate_chunk_payload(payload, chunk)


def test_validate_chunk_payload_rejects_cross_date_preservation_equation():
    chunk = audit.ChunkSpec("boltodds", date(2026, 4, 28), date(2026, 4, 28))
    payload = valid_payload(chunk)
    payload["source_anomalies"][0].update({
        "slate_date_mismatch_rows": 2,
        "preserved_slate_date_mismatch_rows": 1,
        "unpreserved_slate_date_mismatch_rows": 0,
    })

    with pytest.raises(ValueError, match="cross-date preservation equation"):
        audit.validate_chunk_payload(payload, chunk)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda payload: payload["coverage"].pop(), "coverage partitions"),
        (lambda payload: payload["coverage"][0].update(raw_snapshot_rows=-1), "non-negative integer"),
        (lambda payload: payload["coverage"][0].update(raw_group_count=2), "raw group equation"),
        (lambda payload: payload["coverage"][0].update(coverage_exact=False), "coverage_exact"),
        (lambda payload: payload["candidate_runtime"][0].update(snapshot_count=3), "runtime snapshot"),
    ],
)
def test_validate_chunk_payload_rejects_missing_negative_or_contradictory_aggregates(
    mutate, message,
):
    chunk = audit.ChunkSpec("propline", date(2026, 5, 1), date(2026, 5, 2))
    payload = valid_payload(chunk)
    mutate(payload)
    with pytest.raises(ValueError, match=message):
        audit.validate_chunk_payload(payload, chunk)


def test_validate_chunk_payload_rejects_more_groups_than_snapshots():
    chunk = audit.ChunkSpec("propline", date(2026, 5, 1), date(2026, 5, 1))
    payload = valid_payload(chunk)
    payload["coverage"][0].update({
        "raw_group_count": 3,
        "compact_group_count": 3,
        "exact_group_count": 3,
    })
    with pytest.raises(ValueError, match="raw groups cannot exceed snapshots"):
        audit.validate_chunk_payload(payload, chunk)


def test_validate_chunk_payload_rejects_snapshots_without_raw_groups():
    chunk = audit.ChunkSpec("propline", date(2026, 5, 1), date(2026, 5, 1))
    payload = valid_payload(chunk)
    payload["coverage"][0].update({
        "raw_group_count": 0,
        "compact_group_count": 0,
        "exact_group_count": 0,
    })
    with pytest.raises(ValueError, match="raw row/group zero-state"):
        audit.validate_chunk_payload(payload, chunk)


def test_validate_chunk_payload_rejects_snapshots_without_provider_run():
    chunk = audit.ChunkSpec("propline", date(2026, 5, 1), date(2026, 5, 1))
    payload = valid_payload(chunk)
    payload["candidate_runtime"][0].update({
        "first_run_at": None,
        "last_run_at": None,
        "run_count": 0,
        "completed_run_count": 0,
        "request_count": 0,
    })
    with pytest.raises(ValueError, match="snapshots require a provider run"):
        audit.validate_chunk_payload(payload, chunk)


def test_validate_chunk_payload_rejects_books_without_snapshots():
    chunk = audit.ChunkSpec("propline", date(2026, 5, 1), date(2026, 5, 1))
    payload = valid_payload(chunk)
    make_zero_partition(payload)
    payload["candidate_runtime"][0]["books_seen"] = ["fanduel"]
    with pytest.raises(ValueError, match="books_seen requires snapshots"):
        audit.validate_chunk_payload(payload, chunk)


@pytest.mark.parametrize(
    ("raw_rows", "raw_bytes"),
    [(0, 20), (2, 0)],
)
def test_validate_chunk_payload_rejects_inconsistent_row_byte_zero_state(raw_rows, raw_bytes):
    chunk = audit.ChunkSpec("propline", date(2026, 5, 1), date(2026, 5, 1))
    payload = valid_payload(chunk)
    if raw_rows == 0:
        make_zero_partition(payload)
    payload["coverage"][0]["raw_snapshot_rows"] = raw_rows
    payload["coverage"][0]["raw_logical_bytes"] = raw_bytes
    payload["candidate_runtime"][0]["snapshot_count"] = raw_rows
    payload["candidate_runtime"][0]["snapshot_logical_bytes"] = raw_bytes
    with pytest.raises(ValueError, match="row/byte consistency"):
        audit.validate_chunk_payload(payload, chunk)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda payload: payload["coverage"][0].pop("first_raw_seen_at"),
        lambda payload: payload["coverage"][0].update(first_raw_seen_at=None),
        lambda payload: payload["coverage"][0].update(
            first_raw_seen_at="2026-04-28T12:02:00Z",
            last_raw_seen_at="2026-04-28T12:01:00Z",
        ),
        lambda payload: payload["candidate_runtime"][0].update(first_run_at=None),
        lambda payload: payload["candidate_runtime"][0].update(first_snapshot_at=None),
        lambda payload: payload["candidate_runtime"][0].update(
            first_snapshot_at="not-a-timestamp",
        ),
    ],
)
def test_validate_chunk_payload_rejects_missing_null_or_reversed_required_timestamps(mutation):
    chunk = audit.ChunkSpec("propline", date(2026, 5, 1), date(2026, 5, 1))
    payload = valid_payload(chunk)
    mutation(payload)
    with pytest.raises(ValueError, match="timestamp"):
        audit.validate_chunk_payload(payload, chunk)


def test_nullable_timestamp_accepts_postgres_variable_fraction_precision():
    assert audit._normalize_iso_timestamp(
        "2026-06-14T02:01:02.36986+00:00"
    ) == "2026-06-14T02:01:02.369860+00:00"
    parsed = audit._parse_nullable_timestamp(
        {"observed_at": "2026-06-14T02:01:02.36986+00:00"},
        "observed_at",
    )

    assert parsed is not None
    assert parsed.isoformat() == "2026-06-14T02:01:02.369860+00:00"


def test_validate_chunk_payload_rejects_nonnull_raw_timestamp_for_zero_partition():
    chunk = audit.ChunkSpec("propline", date(2026, 5, 1), date(2026, 5, 1))
    payload = valid_payload(chunk)
    make_zero_partition(payload)
    payload["coverage"][0]["first_raw_seen_at"] = "2026-05-01T12:00:00Z"
    with pytest.raises(ValueError, match="timestamp"):
        audit.validate_chunk_payload(payload, chunk)


@pytest.mark.parametrize("audit_generated_at", [None, "not-a-timestamp", "2026-08-18T12:00:00"])
def test_validate_chunk_payload_requires_timezone_aware_audit_timestamp(audit_generated_at):
    chunk = audit.ChunkSpec("propline", date(2026, 5, 1), date(2026, 5, 1))
    payload = valid_payload(chunk)
    if audit_generated_at is None:
        payload.pop("audit_generated_at")
    else:
        payload["audit_generated_at"] = audit_generated_at
    with pytest.raises(ValueError, match="audit_generated_at"):
        audit.validate_chunk_payload(payload, chunk)


def test_validate_chunk_payload_rejects_message_timestamp_without_heartbeat_rows():
    chunk = audit.ChunkSpec("propline", date(2026, 5, 1), date(2026, 5, 1))
    payload = valid_payload(chunk)
    payload["candidate_runtime"][0]["last_message_at"] = "2026-05-01T12:00:00Z"
    with pytest.raises(ValueError, match="heartbeat timestamp/count"):
        audit.validate_chunk_payload(payload, chunk)


def test_validate_chunk_payload_rejects_requests_without_provider_runs():
    chunk = audit.ChunkSpec("propline", date(2026, 5, 1), date(2026, 5, 1))
    payload = valid_payload(chunk)
    payload["candidate_runtime"][0].update({
        "first_run_at": None,
        "last_run_at": None,
        "run_count": 0,
        "completed_run_count": 0,
        "request_count": 1,
    })
    with pytest.raises(ValueError, match="request count"):
        audit.validate_chunk_payload(payload, chunk)


@pytest.mark.parametrize(
    "books",
    [
        ["fanduel", "fanduel"],
        ["fanduel", "draftkings"],
        ["FanDuel"],
        [" fanduel"],
        [""],
    ],
)
def test_validate_chunk_payload_requires_canonical_unique_books(books):
    chunk = audit.ChunkSpec("propline", date(2026, 5, 1), date(2026, 5, 1))
    payload = valid_payload(chunk)
    payload["candidate_runtime"][0]["books_seen"] = books
    with pytest.raises(ValueError, match="books_seen"):
        audit.validate_chunk_payload(payload, chunk)


def test_write_json_atomic_replaces_only_after_closed_valid_temp_file(tmp_path, monkeypatch):
    target = tmp_path / "checkpoint.json"
    real_replace = audit.os.replace
    observations: list[tuple[Path, Path, dict]] = []

    def checked_replace(source, destination):
        source_path = Path(source)
        with source_path.open("r", encoding="utf-8") as handle:
            parsed = json.load(handle)
        observations.append((source_path, Path(destination), parsed))
        real_replace(source, destination)

    monkeypatch.setattr(audit.os, "replace", checked_replace)
    audit.write_json_atomic(target, {"safe": True})
    assert observations[0][1:] == (target, {"safe": True})
    assert json.loads(target.read_text(encoding="utf-8")) == {"safe": True}


def test_write_json_atomic_never_replaces_after_serialization_failure(tmp_path, monkeypatch):
    replace = Mock()
    monkeypatch.setattr(audit.os, "replace", replace)
    with pytest.raises(TypeError):
        audit.write_json_atomic(tmp_path / "checkpoint.json", {"bad": object()})
    replace.assert_not_called()
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("result_or_error", "expected_code"),
    [
        (subprocess.CompletedProcess([], 1, "", "ERROR 53100"), "postgres_53100"),
        (subprocess.CompletedProcess([], 1, "", "ERROR 57014"), "postgres_57014"),
        (subprocess.CompletedProcess([], 1, "", "ECIRCUITBREAKER"), "pooler_circuit_breaker"),
        (subprocess.CompletedProcess([], 1, "", "authentication failed"), "authentication_error"),
        (subprocess.TimeoutExpired(["npx"], 120), "timeout"),
        (subprocess.CompletedProcess([], 1, "", "other failure"), "subprocess_failed"),
        (subprocess.CompletedProcess([], 0, "", ""), "empty_stdout"),
        (subprocess.CompletedProcess([], 0, "not-json", ""), "malformed_json"),
    ],
)
def test_run_chunks_classifies_failure_once_without_checkpoint(
    tmp_path, monkeypatch, result_or_error, expected_code,
):
    query = Mock()
    if isinstance(result_or_error, BaseException):
        query.side_effect = result_or_error
    else:
        query.return_value = result_or_error
    monkeypatch.setattr(audit, "run_linked_query", query)

    with pytest.raises(audit.AuditFailure) as exc_info:
        audit.run_chunks(audit.build_scope("2026-08-18"), tmp_path)

    assert exc_info.value.code == expected_code
    assert query.call_count == 1
    assert list(tmp_path.glob("checkpoint-*.json")) == []


def test_run_chunks_classifies_validation_failure_once_without_checkpoint(tmp_path, monkeypatch):
    chunk = audit.ChunkSpec("boltodds", date(2026, 4, 28), date(2026, 4, 28))
    payload = valid_payload(chunk)
    payload["coverage"][0]["coverage_exact"] = False
    query = Mock(return_value=subprocess.CompletedProcess(
        [], 0, json.dumps([{"retention_bounded_chunk": payload}]), "",
    ))
    monkeypatch.setattr(audit, "run_linked_query", query)

    with pytest.raises(audit.AuditFailure) as exc_info:
        audit.run_chunks(audit.build_scope("2026-08-18"), tmp_path)

    assert exc_info.value.code == "validation_failed"
    assert query.call_count == 1
    assert list(tmp_path.glob("checkpoint-*.json")) == []


def test_run_chunks_rejects_non_directory_output_before_query(tmp_path, monkeypatch):
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("occupied", encoding="utf-8")
    query = Mock()
    monkeypatch.setattr(audit, "run_linked_query", query)

    with pytest.raises(ValueError, match="output directory"):
        audit.run_chunks(audit.build_scope("2026-08-18"), output_file)

    query.assert_not_called()


@pytest.mark.parametrize("command", ["run", "runtime-boundary"])
@pytest.mark.parametrize("path_shape", ["output_is_file", "file_parent"])
def test_linked_commands_preflight_invalid_output_before_builder_or_query(
    command, path_shape, tmp_path, monkeypatch,
):
    if path_shape == "output_is_file":
        output_dir = tmp_path / "output"
        output_dir.write_text("occupied", encoding="utf-8")
    else:
        file_parent = tmp_path / "file-parent"
        file_parent.write_text("occupied", encoding="utf-8")
        output_dir = file_parent / "missing"
    chunk_builder = Mock()
    runtime_builder = Mock()
    query = Mock()
    monkeypatch.setattr(audit.bounded_sql, "build_chunk_sql", chunk_builder)
    monkeypatch.setattr(audit.bounded_sql, "build_runtime_boundary_sql", runtime_builder)
    monkeypatch.setattr(audit, "run_linked_query", query)
    scope = audit.build_scope("2026-08-18")

    with pytest.raises((OSError, ValueError)):
        if command == "run":
            audit.run_chunks(scope, output_dir)
        else:
            audit.run_runtime_boundary(scope, output_dir)

    chunk_builder.assert_not_called()
    runtime_builder.assert_not_called()
    query.assert_not_called()


@pytest.mark.parametrize("command", ["run", "runtime-boundary"])
def test_linked_commands_atomic_write_probe_failure_prevents_builder_and_query(
    command, tmp_path, monkeypatch,
):
    chunk_builder = Mock()
    runtime_builder = Mock()
    query = Mock()
    monkeypatch.setattr(audit.bounded_sql, "build_chunk_sql", chunk_builder)
    monkeypatch.setattr(audit.bounded_sql, "build_runtime_boundary_sql", runtime_builder)
    monkeypatch.setattr(audit, "run_linked_query", query)
    monkeypatch.setattr(audit, "write_json_atomic", Mock(side_effect=PermissionError("denied")))
    scope = audit.build_scope("2026-08-18")

    with pytest.raises(PermissionError):
        if command == "run":
            audit.run_chunks(scope, tmp_path)
        else:
            audit.run_runtime_boundary(scope, tmp_path)

    chunk_builder.assert_not_called()
    runtime_builder.assert_not_called()
    query.assert_not_called()


@pytest.mark.parametrize("command", ["run", "runtime-boundary"])
def test_cli_version_lookup_failure_prevents_builder_and_query(command, tmp_path, monkeypatch):
    version = Mock(side_effect=audit.AuditFailure("subprocess_failed"))
    chunk_builder = Mock()
    runtime_builder = Mock()
    query = Mock()
    monkeypatch.setattr(audit, "resolve_cli_version", version)
    monkeypatch.setattr(audit.bounded_sql, "build_chunk_sql", chunk_builder)
    monkeypatch.setattr(audit.bounded_sql, "build_runtime_boundary_sql", runtime_builder)
    monkeypatch.setattr(audit, "run_linked_query", query)
    scope = audit.build_scope("2026-08-18")

    with pytest.raises(audit.AuditFailure, match="subprocess_failed"):
        if command == "run":
            audit.run_chunks(scope, tmp_path)
        else:
            audit.run_runtime_boundary(scope, tmp_path)

    version.assert_called_once_with()
    chunk_builder.assert_not_called()
    runtime_builder.assert_not_called()
    query.assert_not_called()


@pytest.mark.parametrize("command", [audit.run_chunks, audit.run_runtime_boundary])
def test_query_capable_functions_reject_cli_version_override(command, tmp_path):
    assert "cli_version" not in inspect.signature(command).parameters
    with pytest.raises(TypeError, match="cli_version"):
        command(audit.build_scope("2026-08-18"), tmp_path, cli_version="9.9.9")


def test_run_chunks_writes_bound_checkpoint_and_exactly_thirty_second_cooldown(
    tmp_path, monkeypatch,
):
    first = audit.ChunkSpec("boltodds", date(2026, 4, 28), date(2026, 4, 28))
    second = audit.ChunkSpec("boltodds", date(2026, 4, 29), date(2026, 5, 1))
    results = [
        subprocess.CompletedProcess(
            [], 0, json.dumps([{"retention_bounded_chunk": valid_payload(first)}]), "",
        ),
        subprocess.CompletedProcess(
            [], 0, json.dumps([{"retention_bounded_chunk": valid_payload(second)}]), "",
        ),
    ]
    query = Mock(side_effect=results)
    version = Mock(return_value="2.48.3")
    sleep = Mock()
    clock = iter((100.0, 110.0, 200.0, 210.0))
    monkeypatch.setattr(audit, "run_linked_query", query)
    monkeypatch.setattr(audit, "resolve_cli_version", version)
    monkeypatch.setattr(audit.time, "sleep", sleep)
    monkeypatch.setattr(audit.time, "perf_counter", lambda: next(clock))

    written = audit.run_chunks(
        audit.build_scope("2026-08-18"), tmp_path, max_chunks=2,
    )

    assert [(item.start_date, item.end_date) for item in written] == [
        (first.start_date, first.end_date),
        (second.start_date, second.end_date),
    ]
    sleep.assert_called_once_with(30.0)
    version.assert_called_once_with()
    files = sorted(tmp_path.glob("checkpoint-*.json"))
    assert len(files) == 2
    saved = json.loads(files[0].read_text(encoding="utf-8"))
    assert saved["audit_version"] == 2
    assert saved["cli_version"] == "2.48.3"
    assert saved["query_contract_version"] == audit.QUERY_CONTRACT_VERSION
    assert saved["providers"] == ["boltodds", "propline", "the_odds", "therundown"]
    assert saved["status"] == "completed"
    assert saved["complete"] is True
    assert saved["sanitized_error"] is None
    assert saved["row_count"] == 1
    assert saved["partition_count"] == 1
    assert saved["query_contract_sha256"] == audit.bounded_sql.query_contract_sha256()
    assert len(saved["rendered_sql_sha256"]) == 64
    assert len(saved["scope_fingerprint"]) == 64
    assert len(saved["result_sha256"]) == 64
    assert saved["payload"] == valid_payload(first)


def test_run_chunks_saves_slow_success_then_stops_without_sleep(tmp_path, monkeypatch):
    chunk = audit.ChunkSpec("boltodds", date(2026, 4, 28), date(2026, 4, 28))
    query = Mock(return_value=subprocess.CompletedProcess(
        [], 0, json.dumps([{"retention_bounded_chunk": valid_payload(chunk)}]), "",
    ))
    sleep = Mock()
    clock = iter((100.0, 130.1))
    monkeypatch.setattr(audit, "run_linked_query", query)
    monkeypatch.setattr(audit.time, "sleep", sleep)
    monkeypatch.setattr(audit.time, "perf_counter", lambda: next(clock))

    written = audit.run_chunks(audit.build_scope("2026-08-18"), tmp_path, max_chunks=5)

    assert len(written) == 1
    assert query.call_count == 1
    sleep.assert_not_called()
    assert len(list(tmp_path.glob("checkpoint-*.json"))) == 1


def test_load_valid_checkpoints_resumes_only_exact_bound_evidence(tmp_path, monkeypatch):
    chunk = audit.ChunkSpec("boltodds", date(2026, 4, 28), date(2026, 4, 28))
    query = Mock(return_value=subprocess.CompletedProcess(
        [], 0, json.dumps([{"retention_bounded_chunk": valid_payload(chunk)}]), "",
    ))
    clock = iter((100.0, 110.0))
    scope = audit.build_scope("2026-08-18")
    monkeypatch.setattr(audit, "run_linked_query", query)
    monkeypatch.setattr(audit.time, "perf_counter", lambda: next(clock))
    audit.run_chunks(scope, tmp_path)

    records = audit.load_valid_checkpoints(tmp_path, scope)

    assert len(records) == 1
    assert records[0].provider == "boltodds"
    assert records[0].start_date == date(2026, 4, 28)
    assert records[0].end_date == date(2026, 4, 28)
    assert audit.select_next_chunk(scope, records) == audit.ChunkSpec(
        "boltodds", date(2026, 4, 29), date(2026, 5, 1),
    )


def test_run_chunks_rejects_runner_version_two_checkpoint_before_query(tmp_path, monkeypatch):
    scope = audit.build_scope("2026-08-18")
    chunk = audit.ChunkSpec("boltodds", date(2026, 4, 28), date(2026, 4, 28))
    sql = audit.bounded_sql.build_chunk_sql(
        chunk.provider, chunk.start_date.isoformat(), chunk.end_date.isoformat(),
    )
    checkpoint = audit._checkpoint_value(
        scope,
        chunk,
        sql,
        valid_payload(chunk),
        audit.datetime(2026, 8, 18, 12, tzinfo=audit.timezone.utc),
        audit.datetime(2026, 8, 18, 12, 10, tzinfo=audit.timezone.utc),
        10.0,
        "2.48.3",
    )
    checkpoint["runner_version"] = "2"
    checkpoint["checkpoint_integrity_sha256"] = audit._checkpoint_integrity_sha256(
        checkpoint,
    )
    audit.write_json_atomic(audit._checkpoint_path(tmp_path, chunk), checkpoint)
    query = Mock()
    monkeypatch.setattr(audit, "run_linked_query", query)

    with pytest.raises(ValueError, match="checkpoint validation failed"):
        audit.run_chunks(scope, tmp_path)

    query.assert_not_called()


def test_checkpoint_integrity_hash_rejects_elapsed_cadence_tamper(tmp_path, monkeypatch):
    chunk = audit.ChunkSpec("boltodds", date(2026, 4, 28), date(2026, 4, 28))
    query = Mock(return_value=subprocess.CompletedProcess(
        [], 0, json.dumps([{"retention_bounded_chunk": valid_payload(chunk)}]), "",
    ))
    clock = iter((100.0, 131.0))
    scope = audit.build_scope("2026-08-18")
    monkeypatch.setattr(audit, "run_linked_query", query)
    monkeypatch.setattr(audit.time, "perf_counter", lambda: next(clock))
    audit.run_chunks(scope, tmp_path)
    path = next(tmp_path.glob("checkpoint-*.json"))
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["elapsed_seconds"] == 31.0
    assert len(saved["checkpoint_integrity_sha256"]) == 64

    saved["elapsed_seconds"] = 1.0
    path.write_text(json.dumps(saved), encoding="utf-8")

    with pytest.raises(ValueError, match="checkpoint integrity"):
        audit.load_valid_checkpoints(tmp_path, scope, cli_version="2.48.3")


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("started_at", "2026-08-18T11:59:59+00:00"),
        ("status", "completed-but-untrusted"),
        ("row_count", 2),
        ("partition_count", 2),
        ("cli_version", "2.48.4"),
        ("result_sha256", "0" * 64),
        ("query_contract_sha256", "1" * 64),
    ],
)
def test_checkpoint_integrity_hash_binds_all_resume_metadata(
    field, replacement, tmp_path, monkeypatch,
):
    chunk = audit.ChunkSpec("boltodds", date(2026, 4, 28), date(2026, 4, 28))
    query = Mock(return_value=subprocess.CompletedProcess(
        [], 0, json.dumps([{"retention_bounded_chunk": valid_payload(chunk)}]), "",
    ))
    clock = iter((100.0, 110.0))
    scope = audit.build_scope("2026-08-18")
    monkeypatch.setattr(audit, "run_linked_query", query)
    monkeypatch.setattr(audit.time, "perf_counter", lambda: next(clock))
    audit.run_chunks(scope, tmp_path)
    path = next(tmp_path.glob("checkpoint-*.json"))
    saved = json.loads(path.read_text(encoding="utf-8"))
    saved[field] = replacement
    path.write_text(json.dumps(saved), encoding="utf-8")

    with pytest.raises(ValueError, match="checkpoint integrity"):
        audit.load_valid_checkpoints(tmp_path, scope, cli_version="2.48.3")


def test_checkpoint_integrity_hash_binds_added_resume_metadata(tmp_path, monkeypatch):
    chunk = audit.ChunkSpec("boltodds", date(2026, 4, 28), date(2026, 4, 28))
    query = Mock(return_value=subprocess.CompletedProcess(
        [], 0, json.dumps([{"retention_bounded_chunk": valid_payload(chunk)}]), "",
    ))
    clock = iter((100.0, 110.0))
    scope = audit.build_scope("2026-08-18")
    monkeypatch.setattr(audit, "run_linked_query", query)
    monkeypatch.setattr(audit.time, "perf_counter", lambda: next(clock))
    audit.run_chunks(scope, tmp_path)
    path = next(tmp_path.glob("checkpoint-*.json"))
    saved = json.loads(path.read_text(encoding="utf-8"))
    saved["unbound_resume_hint"] = "fast"
    path.write_text(json.dumps(saved), encoding="utf-8")

    with pytest.raises(ValueError, match="checkpoint integrity"):
        audit.load_valid_checkpoints(tmp_path, scope, cli_version="2.48.3")


@pytest.mark.parametrize("tamper", ["payload", "scope", "hash", "filename"])
def test_load_valid_checkpoints_rejects_tampered_stale_or_foreign_evidence(
    tmp_path, monkeypatch, tamper,
):
    chunk = audit.ChunkSpec("boltodds", date(2026, 4, 28), date(2026, 4, 28))
    query = Mock(return_value=subprocess.CompletedProcess(
        [], 0, json.dumps([{"retention_bounded_chunk": valid_payload(chunk)}]), "",
    ))
    clock = iter((100.0, 110.0))
    scope = audit.build_scope("2026-08-18")
    monkeypatch.setattr(audit, "run_linked_query", query)
    monkeypatch.setattr(audit.time, "perf_counter", lambda: next(clock))
    audit.run_chunks(scope, tmp_path)
    path = next(tmp_path.glob("checkpoint-*.json"))
    saved = json.loads(path.read_text(encoding="utf-8"))
    if tamper == "payload":
        saved["payload"]["coverage"][0]["raw_snapshot_rows"] = 99
    elif tamper == "scope":
        saved["as_of_date"] = "2026-08-17"
    elif tamper == "hash":
        saved["query_contract_sha256"] = "0" * 64
    else:
        path.rename(tmp_path / "checkpoint-propline-2026-04-28-2026-04-28.json")
        path = tmp_path / "checkpoint-propline-2026-04-28-2026-04-28.json"
    if tamper != "filename":
        path.write_text(json.dumps(saved), encoding="utf-8")

    with pytest.raises(ValueError, match="checkpoint"):
        audit.load_valid_checkpoints(tmp_path, scope)


def test_load_valid_checkpoints_rejects_malformed_json(tmp_path):
    (tmp_path / "checkpoint-boltodds-2026-04-28-2026-04-28.json").write_text(
        "{truncated", encoding="utf-8",
    )
    with pytest.raises(ValueError, match="checkpoint"):
        audit.load_valid_checkpoints(tmp_path, audit.build_scope("2026-08-18"))


def test_run_chunks_fails_closed_on_malformed_resume_without_query(tmp_path, monkeypatch):
    (tmp_path / "checkpoint-boltodds-2026-04-28-2026-04-28.json").write_text(
        "{truncated", encoding="utf-8",
    )
    query = Mock()
    monkeypatch.setattr(audit, "run_linked_query", query)

    with pytest.raises(ValueError, match="checkpoint"):
        audit.run_chunks(audit.build_scope("2026-08-18"), tmp_path)

    query.assert_not_called()


def test_load_valid_checkpoints_rejects_overlapping_ranges(tmp_path, monkeypatch):
    scope = audit.build_scope("2026-08-18")
    chunks = (
        audit.ChunkSpec("boltodds", date(2026, 4, 28), date(2026, 4, 30)),
        audit.ChunkSpec("boltodds", date(2026, 4, 30), date(2026, 5, 1)),
    )
    for index, chunk in enumerate(chunks):
        sql = audit.bounded_sql.build_chunk_sql(
            chunk.provider, chunk.start_date.isoformat(), chunk.end_date.isoformat(),
        )
        value = audit._checkpoint_value(
            scope,
            chunk,
            sql,
            valid_payload(chunk),
            audit.datetime(2026, 8, 18, 12, index, tzinfo=audit.timezone.utc),
            audit.datetime(2026, 8, 18, 12, index, 10, tzinfo=audit.timezone.utc),
            10.0,
            "2.48.3",
        )
        audit.write_json_atomic(audit._checkpoint_path(tmp_path, chunk), value)

    with pytest.raises(ValueError, match="checkpoint validation failed"):
        audit.load_valid_checkpoints(tmp_path, scope)


def test_cli_help_lists_only_bounded_commands_and_no_dangerous_controls(capsys):
    assert audit.main(["--help"]) == 0
    help_text = capsys.readouterr().out
    for command in ("run", "run-chunk", "runtime-boundary", "assemble"):
        assert command in help_text
    for forbidden in (
        "--timeout", "--provider", "--sql", "--execute", "--delete",
        "--backfill", "--vacuum", "--allow-linked-read",
    ):
        assert forbidden not in help_text


@pytest.mark.parametrize("command", ["run", "run-chunk", "runtime-boundary"])
def test_linked_cli_commands_require_explicit_acknowledgement(command, tmp_path, monkeypatch):
    query = Mock()
    monkeypatch.setattr(audit, "run_linked_query", query)
    args = [
        command, "--as-of", "2026-08-18", "--output-dir", str(tmp_path),
    ]
    if command == "run-chunk":
        args.extend([
            "--provider", "boltodds",
            "--start-date", "2026-05-17",
            "--end-date", "2026-05-19",
        ])
    assert audit.main(args) == 3
    query.assert_not_called()


def test_run_cli_requires_extra_acknowledgement_above_one_chunk(tmp_path, monkeypatch):
    run = Mock()
    monkeypatch.setattr(audit, "run_chunks", run)
    assert audit.main([
        "run", "--as-of", "2026-08-18", "--output-dir", str(tmp_path),
        "--run-linked-read", "--max-chunks", "2",
    ]) == 3
    run.assert_not_called()


@pytest.mark.parametrize("value", ["0", "6", "not-a-number"])
def test_run_cli_rejects_chunk_caps_outside_one_to_five(value, tmp_path, monkeypatch):
    run = Mock()
    monkeypatch.setattr(audit, "run_chunks", run)
    assert audit.main([
        "run", "--as-of", "2026-08-18", "--output-dir", str(tmp_path),
        "--run-linked-read", "--max-chunks", value, "--allow-multi-chunk",
    ]) == 3
    run.assert_not_called()


def test_run_cli_routes_only_validated_scope_and_cap(tmp_path, monkeypatch):
    run = Mock(return_value=[])
    monkeypatch.setattr(audit, "run_chunks", run)
    assert audit.main([
        "run", "--as-of", "2026-08-18", "--output-dir", str(tmp_path),
        "--run-linked-read", "--max-chunks", "2", "--allow-multi-chunk",
    ]) == 0
    scope, output_dir = run.call_args.args
    assert scope == audit.build_scope("2026-08-18")
    assert output_dir == tmp_path
    assert run.call_args.kwargs == {"max_chunks": 2}


def test_run_chunk_cli_routes_only_validated_explicit_chunk(tmp_path, monkeypatch):
    run = Mock(return_value=(
        tmp_path / "checkpoint-boltodds-2026-05-17-2026-05-19.json"
    ))
    monkeypatch.setattr(audit, "run_explicit_chunk", run, raising=False)

    assert audit.main([
        "run-chunk", "--as-of", "2026-08-18",
        "--output-dir", str(tmp_path), "--run-linked-read",
        "--provider", "boltodds",
        "--start-date", "2026-05-17", "--end-date", "2026-05-19",
    ]) == 0

    scope, output_dir, chunk = run.call_args.args
    assert scope == audit.build_scope("2026-08-18")
    assert output_dir == tmp_path
    assert chunk == audit.ChunkSpec(
        "boltodds", date(2026, 5, 17), date(2026, 5, 19),
    )


def test_run_chunk_cli_requires_explicit_output_dir_before_execution(
    capsys, monkeypatch,
):
    run = Mock()
    monkeypatch.setattr(audit, "run_explicit_chunk", run, raising=False)

    assert audit.main([
        "run-chunk", "--as-of", "2026-08-18", "--run-linked-read",
        "--provider", "boltodds",
        "--start-date", "2026-05-17", "--end-date", "2026-05-19",
    ]) == 3

    assert "required: --output-dir" in capsys.readouterr().err
    run.assert_not_called()


def test_run_explicit_chunk_writes_one_integrity_valid_checkpoint(
    tmp_path, monkeypatch,
):
    scope = audit.build_scope("2026-08-18")
    chunk = audit.ChunkSpec(
        "boltodds", date(2026, 5, 17), date(2026, 5, 19),
    )
    query = Mock(return_value=subprocess.CompletedProcess(
        [], 0, json.dumps([{"retention_bounded_chunk": valid_payload(chunk)}]), "",
    ))
    clock = iter((100.0, 110.0))
    monkeypatch.setattr(audit, "run_linked_query", query)
    monkeypatch.setattr(audit.time, "perf_counter", lambda: next(clock))

    path = audit.run_explicit_chunk(scope, tmp_path, chunk)

    assert path == (
        tmp_path / "checkpoint-boltodds-2026-05-17-2026-05-19.json"
    )
    records = audit.load_valid_checkpoints(
        tmp_path, scope, cli_version="2.48.3",
    )
    assert len(records) == 1
    assert records[0].path == path
    assert records[0].start_date == date(2026, 5, 17)
    assert records[0].end_date == date(2026, 5, 19)
    assert query.call_count == 1


def test_run_explicit_chunk_rejects_range_outside_scope_before_query(
    tmp_path, monkeypatch,
):
    scope = audit.build_scope("2026-08-18")
    chunk = audit.ChunkSpec(
        "boltodds", date(2026, 7, 19), date(2026, 7, 20),
    )
    query = Mock()
    monkeypatch.setattr(audit, "run_linked_query", query)

    with pytest.raises(ValueError, match="outside the candidate scope"):
        audit.run_explicit_chunk(scope, tmp_path, chunk)

    query.assert_not_called()
    assert list(tmp_path.iterdir()) == []


def test_run_explicit_chunk_rejects_existing_overlap_before_query(
    tmp_path, monkeypatch,
):
    scope = audit.build_scope("2026-08-18")
    chunk = audit.ChunkSpec(
        "boltodds", date(2026, 5, 17), date(2026, 5, 19),
    )
    sql = audit.bounded_sql.build_chunk_sql(
        chunk.provider, chunk.start_date.isoformat(), chunk.end_date.isoformat(),
    )
    checkpoint = audit._checkpoint_value(
        scope,
        chunk,
        sql,
        valid_payload(chunk),
        audit.datetime(2026, 8, 18, 12, tzinfo=audit.timezone.utc),
        audit.datetime(2026, 8, 18, 12, 10, tzinfo=audit.timezone.utc),
        10.0,
        "2.48.3",
    )
    audit.write_json_atomic(audit._checkpoint_path(tmp_path, chunk), checkpoint)
    query = Mock()
    monkeypatch.setattr(audit, "run_linked_query", query)

    with pytest.raises(ValueError, match="overlaps existing checkpoint"):
        audit.run_explicit_chunk(scope, tmp_path, chunk)

    query.assert_not_called()


def test_runtime_boundary_cli_routes_through_separate_acknowledged_read(tmp_path, monkeypatch):
    run = Mock(return_value=tmp_path / "runtime-boundary-2026-08-18.json")
    monkeypatch.setattr(audit, "run_runtime_boundary", run)
    assert audit.main([
        "runtime-boundary", "--as-of", "2026-08-18",
        "--output-dir", str(tmp_path), "--run-linked-read",
    ]) == 0
    run.assert_called_once_with(audit.build_scope("2026-08-18"), tmp_path)


def test_run_runtime_boundary_writes_separate_validated_atomic_evidence(tmp_path, monkeypatch):
    scope = audit.build_scope("2026-08-18")
    payload = valid_runtime_payload(scope)
    query = Mock(return_value=subprocess.CompletedProcess(
        [], 0, json.dumps([{"retention_runtime_boundary": payload}]), "",
    ))
    clock = iter((100.0, 110.0))
    monkeypatch.setattr(audit, "run_linked_query", query)
    monkeypatch.setattr(audit.time, "perf_counter", lambda: next(clock))

    path = audit.run_runtime_boundary(scope, tmp_path)

    assert path == tmp_path / "runtime-boundary-2026-08-18.json"
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["payload"] == payload
    assert saved["elapsed_seconds"] == 10.0
    assert saved["candidate_end_date"] == "2026-07-19"
    assert saved["cli_version"] == "2.48.3"
    assert saved["query_contract_version"] == audit.QUERY_CONTRACT_VERSION
    assert saved["status"] == "completed"
    assert saved["sanitized_error"] is None
    assert len(saved["rendered_sql_sha256"]) == 64
    assert query.call_count == 1


def test_run_runtime_boundary_rejects_noncanonical_provider_order_without_file(
    tmp_path, monkeypatch,
):
    scope = audit.build_scope("2026-08-18")
    payload = valid_runtime_payload(scope)
    payload["providers"].reverse()
    query = Mock(return_value=subprocess.CompletedProcess(
        [], 0, json.dumps([{"retention_runtime_boundary": payload}]), "",
    ))
    monkeypatch.setattr(audit, "run_linked_query", query)

    with pytest.raises(audit.AuditFailure) as exc_info:
        audit.run_runtime_boundary(scope, tmp_path)

    assert exc_info.value.code == "validation_failed"
    assert query.call_count == 1
    assert list(tmp_path.iterdir()) == []


def test_run_runtime_boundary_rejects_stale_phoenix_audit_day_without_file(
    tmp_path, monkeypatch,
):
    scope = audit.build_scope("2026-08-17")
    payload = valid_runtime_payload(scope)
    payload["generated_at"] = "2026-08-17T12:00:00-07:00"
    query = Mock(return_value=subprocess.CompletedProcess(
        [], 0, json.dumps([{"retention_runtime_boundary": payload}]), "",
    ))
    monkeypatch.setattr(audit, "run_linked_query", query)
    monkeypatch.setattr(audit, "_phoenix_today", lambda: date(2026, 8, 18))

    with pytest.raises(audit.AuditFailure) as exc_info:
        audit.run_runtime_boundary(scope, tmp_path)

    assert exc_info.value.code == "validation_failed"
    assert query.call_count == 1
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "field",
    [
        "current_latest_run_at",
        "current_latest_snapshot_at",
        "current_latest_heartbeat_at",
        "current_latest_message_at",
        "candidate_latest_run_at",
        "candidate_latest_snapshot_at",
        "candidate_latest_heartbeat_at",
        "candidate_latest_message_at",
    ],
)
def test_runtime_payload_requires_every_current_and_candidate_boundary(field):
    scope = audit.build_scope("2026-08-18")
    payload = valid_runtime_payload(scope)
    payload["providers"][0].pop(field)
    with pytest.raises(ValueError, match="runtime boundary field"):
        audit._validate_runtime_payload(payload, scope)


@pytest.mark.parametrize(
    ("target", "injected_key"),
    [
        ("payload", "raw_checkpoint_rows"),
        ("provider", "authorization"),
        ("provider", "cleanup_sql"),
    ],
)
def test_runtime_payload_rejects_unknown_nested_evidence_fields(
    target, injected_key,
):
    scope = audit.build_scope("2026-08-18")
    payload = valid_runtime_payload(scope)
    if target == "payload":
        payload[injected_key] = [{"sensitive": True}]
    else:
        payload["providers"][0][injected_key] = "must-not-flow"
    with pytest.raises(ValueError, match=rf"runtime {target}.*{injected_key}"):
        audit._validate_runtime_payload(payload, scope)


@pytest.mark.parametrize(
    "value",
    ["not-a-timestamp", "2026-06-17T17:22:30"],
)
def test_runtime_payload_rejects_malformed_or_naive_boundary_timestamp(value):
    scope = audit.build_scope("2026-08-18")
    payload = valid_runtime_payload(scope)
    payload["providers"][0]["current_latest_run_at"] = value
    with pytest.raises(ValueError, match="runtime boundary timestamp"):
        audit._validate_runtime_payload(payload, scope)


@pytest.mark.parametrize("generated_at", [None, "2026-08-18T12:00:00"])
def test_runtime_payload_requires_timezone_aware_generated_at(generated_at):
    scope = audit.build_scope("2026-08-18")
    payload = valid_runtime_payload(scope)
    if generated_at is None:
        payload.pop("generated_at")
    else:
        payload["generated_at"] = generated_at
    with pytest.raises(ValueError, match="generated_at"):
        audit._validate_runtime_payload(payload, scope)


@pytest.mark.parametrize(
    ("current_field", "candidate_field"),
    [
        ("current_latest_run_at", "candidate_latest_run_at"),
        ("current_latest_snapshot_at", "candidate_latest_snapshot_at"),
        ("current_latest_heartbeat_at", "candidate_latest_heartbeat_at"),
        ("current_latest_message_at", "candidate_latest_message_at"),
    ],
)
def test_runtime_payload_rejects_candidate_boundary_newer_than_current(
    current_field, candidate_field,
):
    scope = audit.build_scope("2026-08-18")
    payload = valid_runtime_payload(scope)
    row = payload["providers"][1]
    row[current_field] = "2026-07-01T12:00:00Z"
    row[candidate_field] = "2026-07-01T12:00:01Z"
    with pytest.raises(ValueError, match="candidate runtime boundary"):
        audit._validate_runtime_payload(payload, scope)


@pytest.mark.parametrize(
    "candidate_field",
    [
        "candidate_latest_run_at",
        "candidate_latest_snapshot_at",
        "candidate_latest_heartbeat_at",
        "candidate_latest_message_at",
    ],
)
def test_runtime_payload_rejects_candidate_boundary_without_current(candidate_field):
    scope = audit.build_scope("2026-08-18")
    payload = valid_runtime_payload(scope)
    payload["providers"][1][candidate_field] = "2026-07-01T12:00:00Z"
    with pytest.raises(ValueError, match="candidate runtime boundary"):
        audit._validate_runtime_payload(payload, scope)


def test_runtime_payload_recomputes_false_boltodds_closure_flag():
    scope = audit.build_scope("2026-08-18")
    payload = valid_runtime_payload(scope)
    payload["providers"][0]["current_latest_snapshot_at"] = "2026-06-17T17:22:30Z"
    payload["providers"][0]["post_boltodds_suspension"] = False
    with pytest.raises(ValueError, match="post_boltodds_suspension"):
        audit._validate_runtime_payload(payload, scope)


def test_runtime_payload_recomputes_true_boltodds_closure_flag():
    scope = audit.build_scope("2026-08-18")
    payload = valid_runtime_payload(scope)
    payload["providers"][0]["post_boltodds_suspension"] = True
    with pytest.raises(ValueError, match="post_boltodds_suspension"):
        audit._validate_runtime_payload(payload, scope)


def test_runtime_payload_rejects_true_closure_flag_for_active_provider():
    scope = audit.build_scope("2026-08-18")
    payload = valid_runtime_payload(scope)
    payload["providers"][1]["post_boltodds_suspension"] = True
    with pytest.raises(ValueError, match="post_boltodds_suspension"):
        audit._validate_runtime_payload(payload, scope)


def test_assemble_cli_is_local_only_and_never_calls_linked_query(tmp_path, monkeypatch):
    runtime_path = tmp_path / "runtime.json"
    runtime_path.write_text("{}", encoding="utf-8")
    assemble = Mock(return_value=None)
    query = Mock()
    monkeypatch.setattr(audit, "assemble_local", assemble)
    monkeypatch.setattr(audit, "run_linked_query", query)
    assert audit.main([
        "assemble", "--as-of", "2026-08-18", "--output-dir", str(tmp_path),
        "--runtime-json", str(runtime_path),
    ]) == 0
    assemble.assert_called_once_with(
        audit.build_scope("2026-08-18"), tmp_path, runtime_path,
    )
    query.assert_not_called()


def test_malformed_cli_arguments_return_three_without_query(monkeypatch):
    query = Mock()
    monkeypatch.setattr(audit, "run_linked_query", query)
    assert audit.main(["run", "--as-of", "2026-08-18", "--timeout", "999"]) == 3
    query.assert_not_called()


def assembly_checkpoint(
    scope: audit.AuditScope,
    provider: str,
    start_date: date,
    end_date: date,
) -> audit.CheckpointRecord:
    chunk = audit.ChunkSpec(provider, start_date, end_date)
    sql = audit.bounded_sql.build_chunk_sql(
        provider, start_date.isoformat(), end_date.isoformat(),
    )
    return audit.CheckpointRecord(
        path=Path(
            f"checkpoint-{provider}-{start_date.isoformat()}-{end_date.isoformat()}.json"
        ),
        provider=provider,
        start_date=start_date,
        end_date=end_date,
        elapsed_seconds=10.0,
        query_contract_sha256=audit.bounded_sql.query_contract_sha256(),
        rendered_sql_sha256=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        scope_fingerprint=audit._scope_fingerprint(scope),
        cli_version="2.48.3",
        payload=valid_payload(chunk),
        candidate_end_date=scope.candidate_end_date,
        provider_allowlist=scope.providers,
        runner_version=audit.RUNNER_VERSION,
        query_contract_version=audit.QUERY_CONTRACT_VERSION,
    )


def complete_checkpoints(scope: audit.AuditScope) -> list[audit.CheckpointRecord]:
    checkpoints: list[audit.CheckpointRecord] = []
    for provider in scope.providers:
        cursor = scope.start_date
        ladder_index = 0
        while cursor <= scope.candidate_end_date:
            chunk_days = audit.CHUNK_LADDER[
                min(ladder_index, len(audit.CHUNK_LADDER) - 1)
            ]
            end_date = min(
                cursor + timedelta(days=chunk_days - 1), scope.candidate_end_date,
            )
            checkpoints.append(assembly_checkpoint(scope, provider, cursor, end_date))
            cursor = end_date + timedelta(days=1)
            ladder_index += 1
    return checkpoints


def runtime_for_checkpoints(
    scope: audit.AuditScope,
    checkpoints: list[audit.CheckpointRecord],
) -> dict:
    payload = {
        "runtime_version": 2,
        "generated_at": datetime(
            scope.as_of_date.year,
            scope.as_of_date.month,
            scope.as_of_date.day,
            12,
            tzinfo=ZoneInfo("America/Phoenix"),
        ).isoformat(),
        "candidate_end_date": scope.candidate_end_date.isoformat(),
        "providers": [],
    }
    for provider in scope.providers:
        provider_records = [item for item in checkpoints if item.provider == provider]
        runtime_rows = [
            row
            for item in provider_records
            for row in item.payload["candidate_runtime"]
        ]
        candidate_run = max(row["last_run_at"] for row in runtime_rows)
        candidate_snapshot = max(row["last_snapshot_at"] for row in runtime_rows)
        candidate_heartbeat = max(
            (row["last_heartbeat_at"] for row in runtime_rows
             if row["last_heartbeat_at"] is not None),
            default=None,
        )
        candidate_message = max(
            (row["last_message_at"] for row in runtime_rows
             if row["last_message_at"] is not None),
            default=None,
        )
        payload["providers"].append({
            "provider": provider,
            "current_latest_run_at": candidate_run,
            "current_latest_snapshot_at": candidate_snapshot,
            "current_latest_heartbeat_at": candidate_heartbeat,
            "current_latest_message_at": candidate_message,
            "candidate_latest_run_at": candidate_run,
            "candidate_latest_snapshot_at": candidate_snapshot,
            "candidate_latest_heartbeat_at": candidate_heartbeat,
            "candidate_latest_message_at": candidate_message,
            "post_boltodds_suspension": False,
        })
    return payload


@pytest.fixture
def two_date_two_provider_checkpoint_set():
    scope = audit.AuditScope(
        as_of_date=date(2026, 5, 29),
        start_date=date(2026, 4, 28),
        candidate_end_date=date(2026, 4, 29),
        first_protected_date=date(2026, 4, 30),
        raw_retention_days=30,
        providers=("boltodds", "propline"),
    )
    checkpoints = [
        assembly_checkpoint(
            scope, provider, scope.start_date, scope.candidate_end_date,
        )
        for provider in scope.providers
    ]
    return scope, checkpoints


def test_aggregate_candidate_rows_requires_exact_complete_matrix(
    two_date_two_provider_checkpoint_set,
):
    scope, checkpoints = two_date_two_provider_checkpoint_set
    with pytest.raises(ValueError, match="partition matrix"):
        audit.aggregate_candidate_rows(checkpoints[:-1], scope)


def test_aggregate_candidate_rows_rejects_duplicate_and_overlapping_ranges(
    two_date_two_provider_checkpoint_set,
):
    scope, checkpoints = two_date_two_provider_checkpoint_set
    with pytest.raises(ValueError, match="overlap"):
        audit.aggregate_candidate_rows([*checkpoints, checkpoints[0]], scope)


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("query_contract_sha256", "0" * 64, "query_contract_sha256"),
        ("scope_fingerprint", "1" * 64, "scope_fingerprint"),
        ("cli_version", "2.48.4", "cli_version"),
        ("rendered_sql_sha256", "2" * 64, "rendered_sql_sha256"),
    ],
)
def test_aggregate_candidate_rows_rejects_mixed_checkpoint_contracts(
    two_date_two_provider_checkpoint_set, field, replacement, message,
):
    scope, checkpoints = two_date_two_provider_checkpoint_set
    checkpoints[1] = replace(checkpoints[1], **{field: replacement})
    with pytest.raises(ValueError, match=message):
        audit.aggregate_candidate_rows(checkpoints, scope)


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("candidate_end_date", date(2026, 4, 28), "candidate cutoff"),
        ("provider_allowlist", ("propline", "boltodds"), "provider allowlist"),
        ("runner_version", "2", "runner_version"),
        ("query_contract_version", "different-contract", "query_contract_version"),
    ],
)
def test_aggregate_candidate_rows_rejects_cutoff_allowlist_or_version_drift(
    two_date_two_provider_checkpoint_set, field, replacement, message,
):
    scope, checkpoints = two_date_two_provider_checkpoint_set
    checkpoints[1] = replace(checkpoints[1], **{field: replacement})
    with pytest.raises(ValueError, match=message):
        audit.aggregate_candidate_rows(checkpoints, scope)


def test_aggregate_candidate_rows_revalidates_candidate_row_and_byte_equations(
    two_date_two_provider_checkpoint_set,
):
    scope, checkpoints = two_date_two_provider_checkpoint_set
    altered = copy.deepcopy(checkpoints[0].payload)
    altered["coverage"][0]["raw_snapshot_rows"] = 3
    checkpoints[0] = replace(checkpoints[0], payload=altered)
    with pytest.raises(ValueError, match="runtime snapshot count"):
        audit.aggregate_candidate_rows(checkpoints, scope)


def test_assembly_accepts_preserved_extra_with_strict_coverage_false(
    two_date_two_provider_checkpoint_set,
):
    scope, checkpoints = two_date_two_provider_checkpoint_set
    altered = copy.deepcopy(checkpoints[0].payload)
    altered["coverage"][0].update({
        "compact_group_count": 2,
        "unexpected_compact_group_count": 1,
        "preserved_unexpected_compact_group_count": 1,
        "unpreserved_unexpected_compact_group_count": 0,
        "coverage_exact": False,
        "retention_preservation_complete": True,
    })
    checkpoints[0] = replace(checkpoints[0], payload=altered)
    assembled = audit.aggregate_candidate_rows(checkpoints, scope)
    assert assembled[0][0]["coverage_exact"] is False
    assert assembled[0][0]["retention_preservation_complete"] is True


def test_assembly_rejects_unpreserved_extra(two_date_two_provider_checkpoint_set):
    scope, checkpoints = two_date_two_provider_checkpoint_set
    altered = copy.deepcopy(checkpoints[0].payload)
    altered["coverage"][0].update({
        "compact_group_count": 2,
        "unexpected_compact_group_count": 1,
        "preserved_unexpected_compact_group_count": 0,
        "unpreserved_unexpected_compact_group_count": 1,
        "coverage_exact": False,
        "retention_preservation_complete": False,
    })
    checkpoints[0] = replace(checkpoints[0], payload=altered)
    with pytest.raises(
        ValueError,
        match="retention_preservation_complete=false blocks completeness",
    ):
        audit.aggregate_candidate_rows(checkpoints, scope)


def test_aggregate_candidate_rows_rejects_unattributed_anomaly(
    two_date_two_provider_checkpoint_set,
):
    scope, checkpoints = two_date_two_provider_checkpoint_set
    for index, checkpoint in enumerate(checkpoints):
        altered = copy.deepcopy(checkpoint.payload)
        altered["source_anomalies"][0]["unknown_provider_rows"] = 1
        checkpoints[index] = replace(checkpoint, payload=altered)
    with pytest.raises(ValueError, match="unknown_provider_rows"):
        audit.aggregate_candidate_rows(checkpoints, scope)


def test_aggregate_candidate_rows_allows_fully_preserved_cross_date_lineage(
    two_date_two_provider_checkpoint_set,
):
    scope, checkpoints = two_date_two_provider_checkpoint_set
    altered = copy.deepcopy(checkpoints[0].payload)
    altered["source_anomalies"][0].update({
        "slate_date_mismatch_rows": 2,
        "preserved_slate_date_mismatch_rows": 2,
        "unpreserved_slate_date_mismatch_rows": 0,
    })
    checkpoints[0] = replace(checkpoints[0], payload=altered)

    _coverage, anomalies, _runtime = audit.aggregate_candidate_rows(checkpoints, scope)

    boltodds = next(row for row in anomalies if row["provider"] == "boltodds")
    assert boltodds["slate_date_mismatch_rows"] == 2
    assert boltodds["preserved_slate_date_mismatch_rows"] == 2
    assert boltodds["unpreserved_slate_date_mismatch_rows"] == 0


def test_aggregate_candidate_rows_rejects_unpreserved_cross_date_lineage(
    two_date_two_provider_checkpoint_set,
):
    scope, checkpoints = two_date_two_provider_checkpoint_set
    altered = copy.deepcopy(checkpoints[0].payload)
    altered["source_anomalies"][0].update({
        "slate_date_mismatch_rows": 1,
        "preserved_slate_date_mismatch_rows": 0,
        "unpreserved_slate_date_mismatch_rows": 1,
    })
    checkpoints[0] = replace(checkpoints[0], payload=altered)

    with pytest.raises(ValueError, match="unpreserved_slate_date_mismatch_rows"):
        audit.aggregate_candidate_rows(checkpoints, scope)


def test_aggregate_candidate_rows_rejects_contradictory_repeated_unknown_totals(
    two_date_two_provider_checkpoint_set,
):
    scope, checkpoints = two_date_two_provider_checkpoint_set
    altered = copy.deepcopy(checkpoints[0].payload)
    altered["source_anomalies"][0]["unknown_provider_rows"] = 1
    checkpoints[0] = replace(checkpoints[0], payload=altered)
    with pytest.raises(ValueError, match="unknown_provider_rows.*identical"):
        audit.aggregate_candidate_rows(checkpoints, scope)


def test_aggregate_candidate_rows_preserves_zero_partitions_and_canonical_order(
    two_date_two_provider_checkpoint_set,
):
    scope, checkpoints = two_date_two_provider_checkpoint_set
    altered = copy.deepcopy(checkpoints[1].payload)
    make_zero_partition(altered, index=1)
    checkpoints[1] = replace(checkpoints[1], payload=altered)

    coverage, anomalies, runtime = audit.aggregate_candidate_rows(checkpoints, scope)

    assert [(row["provider"], row["slate_date"]) for row in coverage] == list(
        audit.expected_partitions(scope)
    )
    assert coverage[-1]["raw_snapshot_rows"] == 0
    assert [row["provider"] for row in anomalies] == list(scope.providers)
    assert [row["provider"] for row in runtime] == list(scope.providers)
    assert runtime[1]["snapshot_count"] == 2
    assert runtime[1]["snapshot_logical_bytes"] == 20


def test_validate_runtime_boundary_requires_current_phoenix_audit_day(
    two_date_two_provider_checkpoint_set,
):
    scope, checkpoints = two_date_two_provider_checkpoint_set
    runtime_boundary = runtime_for_checkpoints(scope, checkpoints)
    runtime_boundary["generated_at"] = "2026-05-28T23:59:59-07:00"
    with pytest.raises(ValueError, match="generated_at.*Phoenix audit day"):
        audit.validate_runtime_boundary(runtime_boundary, scope)


def test_validate_runtime_boundary_rejects_stale_scope_even_when_generation_matches(
    two_date_two_provider_checkpoint_set, monkeypatch,
):
    scope, checkpoints = two_date_two_provider_checkpoint_set
    runtime_boundary = runtime_for_checkpoints(scope, checkpoints)
    monkeypatch.setattr(
        audit, "_phoenix_today", lambda: scope.as_of_date + timedelta(days=1),
        raising=False,
    )
    with pytest.raises(ValueError, match="current Phoenix audit day"):
        audit.validate_runtime_boundary(runtime_boundary, scope)


def test_validate_runtime_boundary_blocks_post_suspension_boltodds_evidence(
    two_date_two_provider_checkpoint_set, monkeypatch,
):
    scope, checkpoints = two_date_two_provider_checkpoint_set
    monkeypatch.setattr(audit, "_phoenix_today", lambda: scope.as_of_date)
    runtime_boundary = runtime_for_checkpoints(scope, checkpoints)
    runtime_boundary["providers"][0].update({
        "current_latest_snapshot_at": "2026-06-17T17:22:30Z",
        "post_boltodds_suspension": True,
    })
    with pytest.raises(ValueError, match="post_boltodds_suspension"):
        audit.validate_runtime_boundary(runtime_boundary, scope)


def test_assemble_v2_separates_candidate_and_current_runtime():
    scope = audit.build_scope("2026-08-18")
    checkpoints = complete_checkpoints(scope)
    runtime_boundary = runtime_for_checkpoints(scope, checkpoints)
    runtime_boundary["providers"][1]["current_latest_snapshot_at"] = (
        "2026-08-18T18:00:00Z"
    )

    envelope = audit.assemble_v2_envelope(
        scope,
        checkpoints,
        runtime_boundary,
        audit_generated_at=datetime(
            2026, 8, 18, 10, 0, tzinfo=ZoneInfo("America/Phoenix"),
        ),
    )

    assert envelope["audit_version"] == 2
    assert envelope["as_of_date"] == "2026-08-18"
    assert envelope["candidate_scope"] == {
        "start_date": "2026-04-28",
        "end_date": "2026-07-19",
        "raw_retention_days": 30,
        "providers": ["boltodds", "propline", "the_odds", "therundown"],
    }
    assert envelope["protected_scope"]["start_date"] == "2026-07-20"
    assert envelope["execution"]["complete"] is True
    assert envelope["execution"]["chunk_ladder_days"] == [1, 3, 7]
    assert envelope["execution"]["soft_elapsed_seconds"] == 30.0
    assert envelope["execution"]["cooldown_seconds"] == 30.0
    assert envelope["execution"]["max_chunk_days"] == 7
    assert envelope["execution"]["default_max_chunks"] == 1
    assert envelope["execution"]["hard_max_chunks"] == 5
    assert len(envelope["execution"]["expected_chunk_ranges"]) == 4
    assert len(envelope["execution"]["completed_chunk_ranges"]) == len(checkpoints)
    assert envelope["complete"] is True
    assert envelope["retention_execution_closed"] is True
    assert envelope["deletion_approved"] is False
    assert envelope["season_evidence"] is None
    assert envelope["pins"] is None
    assert len(envelope["coverage"]) == len(audit.expected_partitions(scope))
    assert envelope["candidate_runtime"][1]["last_snapshot_at"] == (
        "2026-04-28T12:01:00Z"
    )
    assert envelope["runtime_boundary"][1]["current_latest_snapshot_at"] == (
        "2026-08-18T18:00:00Z"
    )
    assert set(envelope["coverage"][0]) == {
        "slate_date", "provider", "raw_snapshot_rows", "raw_logical_bytes",
        "raw_group_count", "compact_group_count", "exact_group_count",
        "mismatched_group_count", "missing_compact_group_count",
        "unexpected_compact_group_count",
        "preserved_unexpected_compact_group_count",
        "unpreserved_unexpected_compact_group_count",
        "duplicate_compact_group_count",
        "first_seen_mismatch_count", "last_seen_mismatch_count",
        "first_odds_mismatch_count", "last_odds_mismatch_count",
        "min_odds_mismatch_count", "max_odds_mismatch_count",
        "odds_move_count_mismatch_count", "snapshot_count_mismatch_count",
        "first_raw_seen_at", "last_raw_seen_at", "coverage_exact",
        "retention_preservation_complete",
    }
    assert set(envelope["source_anomalies"][0]) == {
        "provider", "rows_missing_run_id", "rows_missing_run_row",
        "rows_missing_group_key", "provider_run_mismatch_rows",
        "slate_date_mismatch_rows", "preserved_slate_date_mismatch_rows",
        "unpreserved_slate_date_mismatch_rows", "unknown_provider_rows",
    }
    assert set(envelope["candidate_runtime"][0]) == {
        "provider", "first_run_at", "last_run_at", "run_count",
        "completed_run_count", "failed_run_count", "request_count",
        "books_seen", "first_snapshot_at", "last_snapshot_at",
        "snapshot_count", "snapshot_logical_bytes", "last_heartbeat_at",
        "last_message_at", "heartbeat_count",
    }
    assert set(envelope["runtime_boundary"][0]) == {
        "provider", "current_latest_run_at", "current_latest_snapshot_at",
        "current_latest_heartbeat_at", "current_latest_message_at",
        "candidate_latest_run_at", "candidate_latest_snapshot_at",
        "candidate_latest_heartbeat_at", "candidate_latest_message_at",
        "post_boltodds_suspension",
    }


def test_assemble_v2_rejects_runtime_boundary_provider_injection():
    scope = audit.build_scope("2026-08-18")
    checkpoints = complete_checkpoints(scope)
    runtime_boundary = runtime_for_checkpoints(scope, checkpoints)
    runtime_boundary["providers"][0]["raw_checkpoint_rows"] = [{"secret": True}]
    with pytest.raises(ValueError, match="runtime provider.*raw_checkpoint_rows"):
        audit.assemble_v2_envelope(
            scope,
            checkpoints,
            runtime_boundary,
            audit_generated_at=datetime(
                2026, 8, 18, 10, 0, tzinfo=ZoneInfo("America/Phoenix"),
            ),
        )


def test_assemble_v2_rejects_runtime_candidate_maximum_contradiction(
    two_date_two_provider_checkpoint_set, monkeypatch,
):
    scope, checkpoints = two_date_two_provider_checkpoint_set
    monkeypatch.setattr(audit, "_phoenix_today", lambda: scope.as_of_date)
    runtime_boundary = runtime_for_checkpoints(scope, checkpoints)
    runtime_boundary["providers"][1]["candidate_latest_snapshot_at"] = (
        "2026-04-28T12:00:00Z"
    )
    with pytest.raises(ValueError, match="candidate_latest_snapshot_at"):
        audit.assemble_v2_envelope(
            scope,
            checkpoints,
            runtime_boundary,
            audit_generated_at=datetime(
                2026, 5, 29, 10, 0, tzinfo=ZoneInfo("America/Phoenix"),
            ),
        )


def test_assemble_v2_requires_phoenix_aware_generation_timestamp(
    two_date_two_provider_checkpoint_set,
):
    scope, checkpoints = two_date_two_provider_checkpoint_set
    runtime_boundary = runtime_for_checkpoints(scope, checkpoints)
    with pytest.raises(ValueError, match="audit_generated_at.*Phoenix"):
        audit.assemble_v2_envelope(
            scope,
            checkpoints,
            runtime_boundary,
            audit_generated_at=datetime(2026, 5, 29, 10, 0),
        )


def test_assemble_local_fails_closed_without_complete_matrix(tmp_path):
    runtime_path = tmp_path / "runtime-boundary-2026-08-18.json"
    runtime_path.write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        audit.assemble_local(audit.build_scope("2026-08-18"), tmp_path, runtime_path)
    assert not (tmp_path / "bounded_retention_envelope.json").exists()


def write_complete_local_evidence(
    output_dir: Path,
    scope: audit.AuditScope,
    *,
    include_boltodds_runtime_boundaries: bool = False,
) -> tuple[list[audit.CheckpointRecord], Path]:
    checkpoints = complete_checkpoints(scope)
    if include_boltodds_runtime_boundaries:
        for checkpoint in checkpoints:
            if checkpoint.provider != "boltodds":
                continue
            for row in checkpoint.payload["candidate_runtime"]:
                row.update({
                    "last_heartbeat_at": "2026-04-28T12:01:00Z",
                    "last_message_at": "2026-04-28T12:01:00Z",
                    "heartbeat_count": 1,
                })
    for index, checkpoint in enumerate(checkpoints):
        sql = audit.bounded_sql.build_chunk_sql(
            checkpoint.provider,
            checkpoint.start_date.isoformat(),
            checkpoint.end_date.isoformat(),
        )
        started_at = datetime(
            2026, 8, 18, 12, 0, index, tzinfo=ZoneInfo("America/Phoenix"),
        )
        value = audit._checkpoint_value(
            scope,
            audit.ChunkSpec(
                checkpoint.provider, checkpoint.start_date, checkpoint.end_date,
            ),
            sql,
            checkpoint.payload,
            started_at,
            started_at + timedelta(seconds=10),
            10.0,
            "2.48.3",
        )
        audit.write_json_atomic(
            audit._checkpoint_path(output_dir, audit.ChunkSpec(
                checkpoint.provider, checkpoint.start_date, checkpoint.end_date,
            )),
            value,
        )

    payload = runtime_for_checkpoints(scope, checkpoints)
    sql = audit.bounded_sql.build_runtime_boundary_sql(
        scope.candidate_end_date.isoformat(),
    )
    started_at = datetime(
        2026, 8, 18, 13, 0, tzinfo=ZoneInfo("America/Phoenix"),
    )
    runtime_value = {
        "audit_version": audit.AUDIT_VERSION,
        "runner_version": audit.RUNNER_VERSION,
        "cli_version": "2.48.3",
        "query_contract_version": audit.QUERY_CONTRACT_VERSION,
        "status": "completed",
        "complete": True,
        "sanitized_error": None,
        "timezone": audit.TIMEZONE,
        "as_of_date": scope.as_of_date.isoformat(),
        "start_date": scope.start_date.isoformat(),
        "candidate_end_date": scope.candidate_end_date.isoformat(),
        "first_protected_date": scope.first_protected_date.isoformat(),
        "raw_retention_days": scope.raw_retention_days,
        "providers": list(scope.providers),
        "started_at": started_at.isoformat(),
        "finished_at": (started_at + timedelta(seconds=10)).isoformat(),
        "elapsed_seconds": 10.0,
        "query_contract_sha256": audit.bounded_sql.query_contract_sha256(),
        "rendered_sql_sha256": hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        "scope_fingerprint": audit._scope_fingerprint(scope),
        "result_sha256": audit._canonical_sha256(payload),
        "payload": payload,
    }
    runtime_value["checkpoint_integrity_sha256"] = (
        audit._checkpoint_integrity_sha256(runtime_value)
    )
    runtime_path = output_dir / f"runtime-boundary-{scope.as_of_date.isoformat()}.json"
    audit.write_json_atomic(runtime_path, runtime_value)
    return checkpoints, runtime_path


def test_assemble_local_requires_runtime_boundary_file_with_complete_matrix(tmp_path):
    scope = audit.build_scope("2026-08-18")
    write_complete_local_evidence(tmp_path, scope)
    missing = tmp_path / "runtime-boundary-missing.json"
    with pytest.raises(ValueError, match="runtime boundary evidence is absent"):
        audit.assemble_local(scope, tmp_path, missing)
    assert not (tmp_path / "bounded_retention_envelope.json").exists()


def test_assemble_local_writes_only_sanitized_envelope_without_linked_read(
    tmp_path, monkeypatch,
):
    scope = audit.build_scope("2026-08-18")
    checkpoints, runtime_path = write_complete_local_evidence(tmp_path, scope)
    before = {path.name for path in tmp_path.iterdir()}
    query = Mock()
    monkeypatch.setattr(audit, "run_linked_query", query)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 18, 10, 0, tzinfo=tz)

    monkeypatch.setattr(audit, "datetime", FixedDatetime)

    output_path = audit.assemble_local(scope, tmp_path, runtime_path)

    assert output_path == tmp_path / "bounded_retention_envelope.json"
    query.assert_not_called()
    assert {path.name for path in tmp_path.iterdir()} - before == {
        "bounded_retention_envelope.json",
    }
    envelope = json.loads(output_path.read_text(encoding="utf-8"))
    assert set(envelope) == {
        "audit_version", "audit_generated_at", "as_of_date", "timezone",
        "candidate_scope", "protected_scope", "execution", "coverage",
        "source_anomalies", "candidate_runtime", "runtime_boundary",
        "season_evidence", "pins", "complete", "retention_execution_closed",
        "deletion_approved",
    }
    assert len(envelope["execution"]["completed_chunk_ranges"]) == len(checkpoints)
    assert "payload" not in envelope
    assert "checkpoint_integrity_sha256" not in envelope


def test_fixture_only_cli_workflow_assembles_and_runs_both_closed_reporters(
    tmp_path, monkeypatch,
):
    scope = audit.build_scope("2026-08-18")
    checkpoints, runtime_path = write_complete_local_evidence(
        tmp_path, scope, include_boltodds_runtime_boundaries=True,
    )
    gate_c_path = tmp_path / "gate-c-manifest.json"
    audit.write_json_atomic(gate_c_path, {
        "artifact": "data/research/gate_c/pitcher_k_outcome_dataset.jsonl",
        "generated_at": "2026-08-18T12:00:00-07:00",
        "jsonl_sha256": "1" * 64,
        "summary_sha256": "2" * 64,
        "loaded_slate_dates": [],
        "source": {
            "start_date": scope.start_date.isoformat(),
            "end_date": scope.candidate_end_date.isoformat(),
        },
        "reconciliation": {
            "graded_pick_rows": 0,
            "matched_pick_rows": 0,
            "unmatched_pick_rows": 0,
        },
        "summary_counts": {
            "rows_missing_result": 0,
            "tracked_pick_rows": 0,
            "context_snapshot_counts": {"official_close": 0},
        },
    })
    season_evidence_path = tmp_path / "season-evidence.json"
    audit.write_json_atomic(season_evidence_path, {
        "schema_version": 1,
        "generated_at": "2026-08-18T12:00:00-07:00",
        "dates": [{
            "slate_date": slate_date.isoformat(),
            "decision_linked": False,
            "evidence_counts": {
                "official_tracked_picks": 0,
                "accepted_bets": 0,
                "sent_notifications": 0,
                "consumed_locks": 0,
                "frozen_alt_v2_rows": 0,
                "operator_incidents": 0,
                "model_review_pins": 0,
            },
        } for slate_date in (
            scope.start_date + timedelta(days=offset)
            for offset in range(
                (scope.candidate_end_date - scope.start_date).days + 1
            )
        )],
    })
    linked_query = Mock()
    subprocess_run = Mock()
    monkeypatch.setattr(audit, "run_linked_query", linked_query)
    monkeypatch.setattr(audit.subprocess, "run", subprocess_run)

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 8, 18, 10, 0, tzinfo=tz)

    monkeypatch.setattr(audit, "datetime", FixedDatetime)

    assembly_exit = audit.main([
        "assemble",
        "--as-of", scope.as_of_date.isoformat(),
        "--output-dir", str(tmp_path),
        "--runtime-json", str(runtime_path),
    ])
    envelope_path = tmp_path / "bounded_retention_envelope.json"
    readiness_output = tmp_path / "readiness"
    closure_output = tmp_path / "closure"
    readiness_exit = readiness.main([
        "readiness",
        "--query-json", str(envelope_path),
        "--gate-c-manifest", str(gate_c_path),
        "--season-evidence", str(season_evidence_path),
        "--as-of", scope.as_of_date.isoformat(),
        "--output-dir", str(readiness_output),
    ])
    closure_exit = readiness.main([
        "boltodds-closure",
        "--query-json", str(envelope_path),
        "--gate-c-manifest", str(gate_c_path),
        "--season-evidence", str(season_evidence_path),
        "--as-of", scope.as_of_date.isoformat(),
        "--output-dir", str(closure_output),
    ])

    assert assembly_exit == 0
    assert readiness_exit == 2
    assert closure_exit == 2
    assert 3 not in (assembly_exit, readiness_exit, closure_exit)
    linked_query.assert_not_called()
    subprocess_run.assert_not_called()

    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    readiness_report = json.loads(
        (readiness_output / "season_retention_readiness.json").read_text(
            encoding="utf-8",
        )
    )
    closure_report = json.loads(
        (closure_output / "boltodds_retirement_closure.json").read_text(
            encoding="utf-8",
        )
    )
    for value in (envelope, readiness_report, closure_report):
        assert value["retention_execution_closed"] is True
        assert value["deletion_approved"] is False
        serialized = json.dumps(value, sort_keys=True).lower()
        assert "delete from" not in serialized
        assert "service_role" not in serialized
        assert "source_payload" not in serialized
    assert readiness_report["summary"]["decision_counts"] == {
        "blocked_pinned_evidence": len(audit.expected_partitions(scope)),
    }
    assert {
        tuple(partition["reason_codes"])
        for partition in readiness_report["partitions"]
    } == {("missing_pin_manifest_partition",)}
    assert closure_report["status"] == "incomplete_evidence"
    assert set(closure_report["unresolved_evidence_gaps"]) == {
        "missing_pin_manifest_partition",
        "pin_manifest_missing",
    }
    assert "post_suspension_runtime_evidence" not in json.dumps(
        closure_report, sort_keys=True,
    )
    boltodds_boundary = closure_report["current_runtime_boundary"]
    assert boltodds_boundary["post_boltodds_suspension"] is False
    for field in (
        "current_latest_run_at",
        "current_latest_snapshot_at",
        "current_latest_heartbeat_at",
        "current_latest_message_at",
    ):
        assert boltodds_boundary[field] == "2026-04-28T12:01:00Z"
    assert "payload" not in envelope
    assert {
        checkpoint.end_date.toordinal() - checkpoint.start_date.toordinal() + 1
        for checkpoint in checkpoints
    } >= {1, 3, 7}
