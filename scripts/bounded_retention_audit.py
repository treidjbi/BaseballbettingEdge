from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from scripts import retention_bounded_sql as bounded_sql

AUDIT_VERSION = 2
RAW_RETENTION_DAYS = 30
CHUNK_LADDER = (1, 3, 7)
SOFT_ELAPSED_SECONDS = 30.0
COOLDOWN_SECONDS = 30.0
DEFAULT_MAX_CHUNKS = 1
HARD_MAX_CHUNKS = 5
QUERY_TIMEOUT_SECONDS = 120
CLI_VERSION_TIMEOUT_SECONDS = 30
QUERY_CONTRACT_VERSION = "supabase-db-query-linked-json-v1"
RUNNER_VERSION = "3"
TIMEZONE = "America/Phoenix"
_CLI_VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?")

_COVERAGE_COUNTS = (
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
)
_MISMATCH_COUNTS = (
    "first_seen_mismatch_count",
    "last_seen_mismatch_count",
    "first_odds_mismatch_count",
    "last_odds_mismatch_count",
    "min_odds_mismatch_count",
    "max_odds_mismatch_count",
    "odds_move_count_mismatch_count",
    "snapshot_count_mismatch_count",
)
_ANOMALY_COUNTS = (
    "rows_missing_run_id",
    "rows_missing_run_row",
    "rows_missing_group_key",
    "provider_run_mismatch_rows",
    "slate_date_mismatch_rows",
    "preserved_slate_date_mismatch_rows",
    "unpreserved_slate_date_mismatch_rows",
    "unknown_provider_rows",
)
_BLOCKING_ANOMALY_COUNTS = (
    "rows_missing_run_id",
    "rows_missing_run_row",
    "rows_missing_group_key",
    "provider_run_mismatch_rows",
    "unpreserved_slate_date_mismatch_rows",
    "unknown_provider_rows",
)
_RUNTIME_COUNTS = (
    "run_count",
    "completed_run_count",
    "failed_run_count",
    "request_count",
    "snapshot_count",
    "snapshot_logical_bytes",
    "heartbeat_count",
)
_RUNTIME_BOUNDARY_FIELDS = (
    "current_latest_run_at",
    "current_latest_snapshot_at",
    "current_latest_heartbeat_at",
    "current_latest_message_at",
    "candidate_latest_run_at",
    "candidate_latest_snapshot_at",
    "candidate_latest_heartbeat_at",
    "candidate_latest_message_at",
)
_RUNTIME_BOUNDARY_PAIRS = (
    ("current_latest_run_at", "candidate_latest_run_at"),
    ("current_latest_snapshot_at", "candidate_latest_snapshot_at"),
    ("current_latest_heartbeat_at", "candidate_latest_heartbeat_at"),
    ("current_latest_message_at", "candidate_latest_message_at"),
)
_CHUNK_PAYLOAD_FIELDS = (
    "chunk_version",
    "audit_generated_at",
    "complete",
    "query_scope",
    "coverage",
    "source_anomalies",
    "candidate_runtime",
)
_COVERAGE_FIELDS = (
    "slate_date",
    "provider",
    *_COVERAGE_COUNTS,
    "first_raw_seen_at",
    "last_raw_seen_at",
    "coverage_exact",
    "retention_preservation_complete",
)
_ANOMALY_FIELDS = ("slate_date", "provider", *_ANOMALY_COUNTS)
_CANDIDATE_RUNTIME_FIELDS = (
    "slate_date",
    "provider",
    "first_run_at",
    "last_run_at",
    *_RUNTIME_COUNTS[:4],
    "books_seen",
    "first_snapshot_at",
    "last_snapshot_at",
    *_RUNTIME_COUNTS[4:6],
    "last_heartbeat_at",
    "last_message_at",
    _RUNTIME_COUNTS[6],
)
_RUNTIME_PAYLOAD_FIELDS = (
    "runtime_version",
    "generated_at",
    "candidate_end_date",
    "providers",
)
_RUNTIME_PROVIDER_FIELDS = (
    "provider",
    *_RUNTIME_BOUNDARY_FIELDS,
    "post_boltodds_suspension",
)


@dataclass(frozen=True)
class AuditScope:
    as_of_date: date
    start_date: date
    candidate_end_date: date
    first_protected_date: date
    raw_retention_days: int
    providers: tuple[str, ...]


@dataclass(frozen=True)
class ChunkSpec:
    provider: str
    start_date: date
    end_date: date

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1


@dataclass(frozen=True)
class CheckpointRecord:
    path: Path
    provider: str
    start_date: date
    end_date: date
    elapsed_seconds: float
    query_contract_sha256: str
    rendered_sql_sha256: str
    scope_fingerprint: str
    cli_version: str
    payload: dict[str, Any]
    candidate_end_date: date | None = None
    provider_allowlist: tuple[str, ...] | None = None
    runner_version: str | None = None
    query_contract_version: str | None = None


class AuditFailure(RuntimeError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def build_scope(as_of_date: str) -> AuditScope:
    parsed_as_of = bounded_sql.parse_iso_date(as_of_date, "as_of_date")
    candidate_end = parsed_as_of - timedelta(days=RAW_RETENTION_DAYS)
    if candidate_end < bounded_sql.CLEAN_REGIME_START:
        raise ValueError("as_of_date does not include the clean regime")
    return AuditScope(
        as_of_date=parsed_as_of,
        start_date=bounded_sql.CLEAN_REGIME_START,
        candidate_end_date=candidate_end,
        first_protected_date=candidate_end + timedelta(days=1),
        raw_retention_days=RAW_RETENTION_DAYS,
        providers=bounded_sql.ALLOWED_PROVIDERS,
    )


def expected_partitions(scope: AuditScope) -> tuple[tuple[str, str], ...]:
    dates = (
        scope.start_date + timedelta(days=offset)
        for offset in range((scope.candidate_end_date - scope.start_date).days + 1)
    )
    return tuple(
        (provider, slate_date.isoformat())
        for slate_date in dates
        for provider in scope.providers
    )


def preferred_chunk_days(
    checkpoints: list[CheckpointRecord], provider: str,
) -> int:
    provider_checkpoints = [item for item in checkpoints if item.provider == provider]
    if not provider_checkpoints:
        return CHUNK_LADDER[0]
    latest = max(provider_checkpoints, key=lambda item: (item.end_date, item.start_date))
    try:
        ladder_index = CHUNK_LADDER.index(latest.end_date.toordinal() - latest.start_date.toordinal() + 1)
    except ValueError:
        return CHUNK_LADDER[0]
    if latest.elapsed_seconds <= SOFT_ELAPSED_SECONDS:
        return CHUNK_LADDER[min(ladder_index + 1, len(CHUNK_LADDER) - 1)]
    return CHUNK_LADDER[max(ladder_index - 1, 0)]


def select_next_chunk(
    scope: AuditScope, checkpoints: list[CheckpointRecord],
) -> ChunkSpec | None:
    for provider in scope.providers:
        provider_checkpoints = [item for item in checkpoints if item.provider == provider]
        completed = {
            item.start_date + timedelta(days=offset)
            for item in provider_checkpoints
            for offset in range((item.end_date - item.start_date).days + 1)
        }
        next_date = scope.start_date
        while next_date <= scope.candidate_end_date and next_date in completed:
            next_date += timedelta(days=1)
        if next_date > scope.candidate_end_date:
            continue

        preferred_days = preferred_chunk_days(checkpoints, provider)
        end_date = min(
            next_date + timedelta(days=preferred_days - 1),
            scope.candidate_end_date,
        )
        cursor = next_date
        while cursor <= end_date:
            if cursor in completed:
                end_date = cursor - timedelta(days=1)
                break
            cursor += timedelta(days=1)
        return ChunkSpec(provider, next_date, end_date)
    return None


def run_linked_query(sql: str) -> subprocess.CompletedProcess[str]:
    bounded_sql.assert_select_only(sql)
    npx = shutil.which("npx") or shutil.which("npx.cmd") or "npx"
    sql_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".sql",
            delete=False,
            encoding="utf-8",
            newline="\n",
        ) as handle:
            handle.write(sql)
            sql_path = handle.name
        return subprocess.run(
            [npx, "supabase", "db", "query", "--linked", "--file", sql_path, "-o", "json"],
            check=False,
            capture_output=True,
            text=True,
            shell=False,
            timeout=QUERY_TIMEOUT_SECONDS,
        )
    finally:
        if sql_path is not None:
            try:
                os.unlink(sql_path)
            except FileNotFoundError:
                pass


def resolve_cli_version() -> str:
    npx = shutil.which("npx") or shutil.which("npx.cmd") or "npx"
    try:
        completed = subprocess.run(
            [npx, "supabase", "--version"],
            check=False,
            capture_output=True,
            text=True,
            shell=False,
            timeout=CLI_VERSION_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise AuditFailure("timeout") from exc
    except OSError as exc:
        raise AuditFailure("subprocess_failed") from exc
    version = (completed.stdout or "").strip()
    if completed.returncode != 0 or _CLI_VERSION_PATTERN.fullmatch(version) is None:
        raise AuditFailure("subprocess_failed")
    return version


def parse_supabase_object(stdout: str, column: str) -> dict[str, Any]:
    if not isinstance(stdout, str) or not stdout.strip():
        raise ValueError("empty stdout")
    try:
        rows = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("malformed JSON") from exc
    if isinstance(rows, dict):
        rows = rows.get("rows")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError("expected one result row")
    value = rows[0].get(column)
    if not isinstance(value, dict):
        raise ValueError("result column must contain an object")
    return value


def _require_nonnegative_integers(record: dict[str, Any], fields: tuple[str, ...]) -> None:
    for field in fields:
        value = record.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError(f"{field} must be a non-negative integer")


def _reject_unknown_fields(
    record: dict[str, Any],
    allowed_fields: tuple[str, ...],
    label: str,
) -> None:
    unexpected = sorted(set(record) - set(allowed_fields))
    if unexpected:
        raise ValueError(
            f"{label} has unexpected fields: {', '.join(unexpected)}"
        )


def _parse_nullable_timestamp(record: dict[str, Any], field: str) -> datetime | None:
    if field not in record:
        raise ValueError(f"required timestamp field is missing: {field}")
    value = record[field]
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"timestamp field is invalid: {field}")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"timestamp field is invalid: {field}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"timestamp field must be timezone-aware: {field}")
    return parsed


def _validate_timestamp_pair(
    record: dict[str, Any],
    first_field: str,
    last_field: str,
    count: int,
) -> None:
    first = _parse_nullable_timestamp(record, first_field)
    last = _parse_nullable_timestamp(record, last_field)
    if count == 0 and (first is not None or last is not None):
        raise ValueError(f"timestamp pair must be null for zero count: {first_field}")
    if count > 0 and (first is None or last is None):
        raise ValueError(f"timestamp pair is required for nonzero count: {first_field}")
    if first is not None and last is not None and first > last:
        raise ValueError(f"timestamp pair is reversed: {first_field}")


def _records_by_partition(
    payload: dict[str, Any],
    key: str,
    chunk: ChunkSpec,
) -> dict[str, dict[str, Any]]:
    records = payload.get(key)
    if not isinstance(records, list):
        raise ValueError(f"{key} must be a list")
    expected_dates = [
        (chunk.start_date + timedelta(days=offset)).isoformat()
        for offset in range(chunk.days)
    ]
    if len(records) != len(expected_dates):
        raise ValueError(f"{key} partitions do not match requested dates")
    by_date: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError(f"{key} records must be objects")
        slate_date = record.get("slate_date")
        if record.get("provider") != chunk.provider or slate_date not in expected_dates:
            raise ValueError(f"{key} partition is outside the requested scope")
        if slate_date in by_date:
            raise ValueError(f"{key} partitions contain a duplicate")
        by_date[slate_date] = record
    if list(by_date) != expected_dates:
        raise ValueError(f"{key} partitions are not in canonical order")
    return by_date


def validate_chunk_payload(payload: dict[str, Any], chunk: ChunkSpec) -> None:
    if not isinstance(payload, dict):
        raise ValueError("chunk payload must be an object")
    _reject_unknown_fields(payload, _CHUNK_PAYLOAD_FIELDS, "payload")
    if payload.get("chunk_version") != AUDIT_VERSION or payload.get("complete") is not True:
        raise ValueError("chunk payload version or completion status is invalid")
    if _parse_nullable_timestamp(payload, "audit_generated_at") is None:
        raise ValueError("audit_generated_at timestamp is required")
    query_scope = payload.get("query_scope")
    expected_scope = {
        "start_date": chunk.start_date.isoformat(),
        "end_date": chunk.end_date.isoformat(),
        "provider": chunk.provider,
        "timezone": TIMEZONE,
    }
    if query_scope != expected_scope:
        raise ValueError("chunk query scope does not match the request")

    coverage = _records_by_partition(payload, "coverage", chunk)
    anomalies = _records_by_partition(payload, "source_anomalies", chunk)
    runtime = _records_by_partition(payload, "candidate_runtime", chunk)
    for slate_date, row in coverage.items():
        _reject_unknown_fields(row, _COVERAGE_FIELDS, "coverage record")
        _require_nonnegative_integers(row, _COVERAGE_COUNTS)
        if row["raw_group_count"] > row["raw_snapshot_rows"]:
            raise ValueError("raw groups cannot exceed snapshots")
        if (row["raw_snapshot_rows"] == 0) != (row["raw_group_count"] == 0):
            raise ValueError("raw row/group zero-state is inconsistent")
        if (row["raw_snapshot_rows"] == 0) != (row["raw_logical_bytes"] == 0):
            raise ValueError("raw row/byte consistency is invalid")
        _validate_timestamp_pair(
            row,
            "first_raw_seen_at",
            "last_raw_seen_at",
            row["raw_snapshot_rows"],
        )
        if row["raw_group_count"] != (
            row["exact_group_count"]
            + row["mismatched_group_count"]
            + row["missing_compact_group_count"]
        ):
            raise ValueError("raw group equation is inconsistent")
        if row["compact_group_count"] != (
            row["exact_group_count"]
            + row["mismatched_group_count"]
            + row["unexpected_compact_group_count"]
        ):
            raise ValueError("compact group equation is inconsistent")
        if row["unexpected_compact_group_count"] != (
            row["preserved_unexpected_compact_group_count"]
            + row["unpreserved_unexpected_compact_group_count"]
        ):
            raise ValueError("unexpected compact preservation equation is inconsistent")
        if any(row[field] > row["mismatched_group_count"] for field in _MISMATCH_COUNTS):
            raise ValueError("mismatch subtype exceeds mismatched groups")
        if row["mismatched_group_count"] > sum(row[field] for field in _MISMATCH_COUNTS):
            raise ValueError("mismatch groups have no mismatch subtype")
        recomputed_exact = all(
            row[field] == 0
            for field in (
                "mismatched_group_count",
                "missing_compact_group_count",
                "unexpected_compact_group_count",
                "duplicate_compact_group_count",
            )
        )
        if not isinstance(row.get("coverage_exact"), bool) or row["coverage_exact"] != recomputed_exact:
            raise ValueError("coverage_exact does not match blocker counts")
        recomputed_preservation = all(
            row[field] == 0
            for field in (
                "mismatched_group_count",
                "missing_compact_group_count",
                "unpreserved_unexpected_compact_group_count",
                "duplicate_compact_group_count",
            )
        )
        if (
            not isinstance(row.get("retention_preservation_complete"), bool)
            or row["retention_preservation_complete"] != recomputed_preservation
        ):
            raise ValueError(
                "retention preservation completeness does not match blocker counts"
            )

        anomaly_row = anomalies[slate_date]
        _reject_unknown_fields(
            anomaly_row, _ANOMALY_FIELDS, "source_anomalies record",
        )
        _require_nonnegative_integers(anomaly_row, _ANOMALY_COUNTS)
        if anomaly_row["slate_date_mismatch_rows"] != (
            anomaly_row["preserved_slate_date_mismatch_rows"]
            + anomaly_row["unpreserved_slate_date_mismatch_rows"]
        ):
            raise ValueError("cross-date preservation equation is inconsistent")
        runtime_row = runtime[slate_date]
        _reject_unknown_fields(
            runtime_row, _CANDIDATE_RUNTIME_FIELDS, "candidate_runtime record",
        )
        _require_nonnegative_integers(runtime_row, _RUNTIME_COUNTS)
        if runtime_row["completed_run_count"] + runtime_row["failed_run_count"] > runtime_row["run_count"]:
            raise ValueError("runtime run counts are inconsistent")
        if runtime_row["run_count"] == 0 and runtime_row["request_count"] != 0:
            raise ValueError("runtime request count requires a provider run")
        if runtime_row["snapshot_count"] > 0 and runtime_row["run_count"] == 0:
            raise ValueError("runtime snapshots require a provider run")
        if runtime_row["snapshot_count"] != row["raw_snapshot_rows"]:
            raise ValueError("runtime snapshot count does not match coverage")
        if runtime_row["snapshot_logical_bytes"] != row["raw_logical_bytes"]:
            raise ValueError("runtime snapshot bytes do not match coverage")
        _validate_timestamp_pair(
            runtime_row,
            "first_run_at",
            "last_run_at",
            runtime_row["run_count"],
        )
        _validate_timestamp_pair(
            runtime_row,
            "first_snapshot_at",
            "last_snapshot_at",
            runtime_row["snapshot_count"],
        )
        last_heartbeat = _parse_nullable_timestamp(runtime_row, "last_heartbeat_at")
        last_message = _parse_nullable_timestamp(runtime_row, "last_message_at")
        if (
            (runtime_row["heartbeat_count"] == 0) != (last_heartbeat is None)
            or (runtime_row["heartbeat_count"] == 0 and last_message is not None)
        ):
            raise ValueError("heartbeat timestamp/count consistency is invalid")
        books = runtime_row.get("books_seen")
        if (
            not isinstance(books, list)
            or any(
                not isinstance(book, str)
                or not book
                or book != book.strip().lower()
                for book in books
            )
            or books != sorted(set(books))
        ):
            raise ValueError("runtime books_seen must be canonical and unique")
        if runtime_row["snapshot_count"] == 0 and books:
            raise ValueError("runtime books_seen requires snapshots")


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
            encoding="utf-8",
            newline="\n",
        ) as handle:
            temp_path = handle.name
            json.dump(value, handle, sort_keys=True, indent=2, ensure_ascii=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        temp_path = None
    finally:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass


def preflight_output_dir(output_dir: Path) -> Path:
    output_dir = Path(output_dir)
    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError("output directory must be a directory")
    output_dir.mkdir(parents=True, exist_ok=True)
    if not output_dir.is_dir():
        raise ValueError("output directory must be a directory")
    probe_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            dir=output_dir,
            prefix=".bounded-retention-write-probe-",
            suffix=".json",
            delete=False,
            encoding="utf-8",
        ) as handle:
            probe_path = Path(handle.name)
        os.unlink(probe_path)
        write_json_atomic(probe_path, {"probe_version": 1})
        if json.loads(probe_path.read_text(encoding="utf-8")) != {"probe_version": 1}:
            raise ValueError("output directory atomic-write probe failed")
    finally:
        if probe_path is not None:
            try:
                os.unlink(probe_path)
            except FileNotFoundError:
                pass
    return output_dir


def classify_failure(value: object) -> str:
    if isinstance(value, subprocess.TimeoutExpired):
        return "timeout"
    text = ""
    if isinstance(value, subprocess.CompletedProcess):
        text = f"{value.stdout or ''}\n{value.stderr or ''}".lower()
    elif isinstance(value, BaseException):
        text = type(value).__name__.lower()
    if "53100" in text:
        return "postgres_53100"
    if "57014" in text:
        return "postgres_57014"
    if "ecircuitbreaker" in text:
        return "pooler_circuit_breaker"
    if any(token in text for token in ("authentication", "unauthorized", "password", "login")):
        return "authentication_error"
    return "subprocess_failed"


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _checkpoint_integrity_sha256(value: dict[str, Any]) -> str:
    bound_value = dict(value)
    bound_value.pop("checkpoint_integrity_sha256", None)
    return _canonical_sha256(bound_value)


def _scope_fingerprint(scope: AuditScope) -> str:
    return _canonical_sha256({
        "audit_version": AUDIT_VERSION,
        "as_of_date": scope.as_of_date.isoformat(),
        "start_date": scope.start_date.isoformat(),
        "candidate_end_date": scope.candidate_end_date.isoformat(),
        "first_protected_date": scope.first_protected_date.isoformat(),
        "raw_retention_days": scope.raw_retention_days,
        "providers": list(scope.providers),
        "timezone": TIMEZONE,
    })


def _checkpoint_path(output_dir: Path, chunk: ChunkSpec) -> Path:
    return output_dir / (
        f"checkpoint-{chunk.provider}-{chunk.start_date.isoformat()}-"
        f"{chunk.end_date.isoformat()}.json"
    )


def _checkpoint_value(
    scope: AuditScope,
    chunk: ChunkSpec,
    sql: str,
    payload: dict[str, Any],
    started_at: datetime,
    finished_at: datetime,
    elapsed_seconds: float,
    cli_version: str,
) -> dict[str, Any]:
    value = {
        "audit_version": AUDIT_VERSION,
        "runner_version": RUNNER_VERSION,
        "cli_version": cli_version,
        "query_contract_version": QUERY_CONTRACT_VERSION,
        "status": "completed",
        "complete": True,
        "sanitized_error": None,
        "timezone": TIMEZONE,
        "as_of_date": scope.as_of_date.isoformat(),
        "start_date": scope.start_date.isoformat(),
        "candidate_end_date": scope.candidate_end_date.isoformat(),
        "first_protected_date": scope.first_protected_date.isoformat(),
        "raw_retention_days": scope.raw_retention_days,
        "providers": list(scope.providers),
        "provider": chunk.provider,
        "chunk_start_date": chunk.start_date.isoformat(),
        "chunk_end_date": chunk.end_date.isoformat(),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "elapsed_seconds": elapsed_seconds,
        "row_count": chunk.days,
        "partition_count": chunk.days,
        "validation": "passed",
        "query_contract_sha256": bounded_sql.query_contract_sha256(),
        "rendered_sql_sha256": hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        "scope_fingerprint": _scope_fingerprint(scope),
        "result_sha256": _canonical_sha256(payload),
        "payload": payload,
    }
    value["checkpoint_integrity_sha256"] = _checkpoint_integrity_sha256(value)
    return value


def _execute_chunk(
    scope: AuditScope,
    output_dir: Path,
    chunk: ChunkSpec,
    cli_version: str,
) -> CheckpointRecord:
    sql = bounded_sql.build_chunk_sql(
        chunk.provider, chunk.start_date.isoformat(), chunk.end_date.isoformat(),
    )
    started_at = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    try:
        completed = run_linked_query(sql)
    except subprocess.TimeoutExpired as exc:
        raise AuditFailure("timeout") from exc
    except Exception as exc:
        raise AuditFailure(classify_failure(exc)) from exc
    if completed.returncode != 0:
        raise AuditFailure(classify_failure(completed))
    if not completed.stdout or not completed.stdout.strip():
        raise AuditFailure("empty_stdout")
    try:
        payload = parse_supabase_object(
            completed.stdout, "retention_bounded_chunk",
        )
    except ValueError as exc:
        raise AuditFailure("malformed_json") from exc
    try:
        validate_chunk_payload(payload, chunk)
    except ValueError as exc:
        raise AuditFailure("validation_failed") from exc
    elapsed = time.perf_counter() - started_clock
    finished_at = datetime.now(timezone.utc)
    checkpoint_value = _checkpoint_value(
        scope,
        chunk,
        sql,
        payload,
        started_at,
        finished_at,
        elapsed,
        cli_version,
    )
    path = _checkpoint_path(output_dir, chunk)
    write_json_atomic(path, checkpoint_value)
    return CheckpointRecord(
        path=path,
        provider=chunk.provider,
        start_date=chunk.start_date,
        end_date=chunk.end_date,
        elapsed_seconds=elapsed,
        query_contract_sha256=checkpoint_value["query_contract_sha256"],
        rendered_sql_sha256=checkpoint_value["rendered_sql_sha256"],
        scope_fingerprint=checkpoint_value["scope_fingerprint"],
        cli_version=checkpoint_value["cli_version"],
        payload=payload,
        candidate_end_date=scope.candidate_end_date,
        provider_allowlist=scope.providers,
        runner_version=RUNNER_VERSION,
        query_contract_version=QUERY_CONTRACT_VERSION,
    )


def run_chunks(
    scope: AuditScope,
    output_dir: Path,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
) -> list[CheckpointRecord]:
    if isinstance(max_chunks, bool) or not isinstance(max_chunks, int) or not 1 <= max_chunks <= HARD_MAX_CHUNKS:
        raise ValueError("max_chunks must be between 1 and 5")
    output_dir = preflight_output_dir(output_dir)
    resolved_cli_version = resolve_cli_version()
    checkpoints = load_valid_checkpoints(
        output_dir, scope, cli_version=resolved_cli_version,
    )
    written: list[CheckpointRecord] = []
    for index in range(max_chunks):
        chunk = select_next_chunk(scope, checkpoints)
        if chunk is None:
            break
        record = _execute_chunk(
            scope, output_dir, chunk, resolved_cli_version,
        )
        checkpoints.append(record)
        written.append(record)
        if record.elapsed_seconds > SOFT_ELAPSED_SECONDS:
            break
        if index + 1 < max_chunks and select_next_chunk(scope, checkpoints) is not None:
            time.sleep(COOLDOWN_SECONDS)
    return written


def run_explicit_chunk(
    scope: AuditScope,
    output_dir: Path,
    chunk: ChunkSpec,
) -> Path:
    if not isinstance(scope, AuditScope) or not isinstance(chunk, ChunkSpec):
        raise ValueError("scope and chunk must use the audit contracts")
    provider, start, end = bounded_sql.validate_chunk(
        chunk.provider, chunk.start_date.isoformat(), chunk.end_date.isoformat(),
    )
    checked_chunk = ChunkSpec(provider, start, end)
    if (
        checked_chunk.start_date < scope.start_date
        or checked_chunk.end_date > scope.candidate_end_date
    ):
        raise ValueError("explicit chunk is outside the candidate scope")

    output_dir = preflight_output_dir(output_dir)
    resolved_cli_version = resolve_cli_version()
    checkpoints = load_valid_checkpoints(
        output_dir, scope, cli_version=resolved_cli_version,
    )
    for checkpoint in checkpoints:
        if (
            checkpoint.provider == checked_chunk.provider
            and checkpoint.start_date <= checked_chunk.end_date
            and checkpoint.end_date >= checked_chunk.start_date
        ):
            raise ValueError("explicit chunk overlaps existing checkpoint")

    record = _execute_chunk(
        scope, output_dir, checked_chunk, resolved_cli_version,
    )
    return record.path


def load_valid_checkpoints(
    output_dir: Path,
    scope: AuditScope,
    cli_version: str | None = None,
) -> list[CheckpointRecord]:
    output_dir = Path(output_dir)
    if not output_dir.exists():
        return []
    if not output_dir.is_dir():
        raise ValueError("output directory must be a directory")
    expected_scope_fields = {
        "audit_version": AUDIT_VERSION,
        "runner_version": RUNNER_VERSION,
        "query_contract_version": QUERY_CONTRACT_VERSION,
        "status": "completed",
        "complete": True,
        "sanitized_error": None,
        "timezone": TIMEZONE,
        "as_of_date": scope.as_of_date.isoformat(),
        "start_date": scope.start_date.isoformat(),
        "candidate_end_date": scope.candidate_end_date.isoformat(),
        "first_protected_date": scope.first_protected_date.isoformat(),
        "raw_retention_days": scope.raw_retention_days,
        "providers": list(scope.providers),
        "scope_fingerprint": _scope_fingerprint(scope),
        "query_contract_sha256": bounded_sql.query_contract_sha256(),
        "validation": "passed",
    }
    records: list[CheckpointRecord] = []
    occupied: set[tuple[str, date]] = set()
    for path in sorted(output_dir.glob("checkpoint-*.json"), key=lambda item: item.name):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, dict):
                raise ValueError("root is not an object")
            integrity_hash = value.get("checkpoint_integrity_sha256")
            if (
                not isinstance(integrity_hash, str)
                or integrity_hash != _checkpoint_integrity_sha256(value)
            ):
                raise ValueError("checkpoint integrity hash mismatch")
            for field, expected in expected_scope_fields.items():
                if value.get(field) != expected:
                    raise ValueError(f"{field} mismatch")
            stored_cli_version = value.get("cli_version")
            if (
                not isinstance(stored_cli_version, str)
                or _CLI_VERSION_PATTERN.fullmatch(stored_cli_version) is None
                or (cli_version is not None and stored_cli_version != cli_version)
            ):
                raise ValueError("cli_version mismatch")
            provider = bounded_sql.validate_provider(value.get("provider"))
            start = bounded_sql.parse_iso_date(value.get("chunk_start_date"), "chunk_start_date")
            end = bounded_sql.parse_iso_date(value.get("chunk_end_date"), "chunk_end_date")
            bounded_sql.validate_chunk(provider, start.isoformat(), end.isoformat())
            if start < scope.start_date or end > scope.candidate_end_date:
                raise ValueError("range outside scope")
            chunk = ChunkSpec(provider, start, end)
            if path.name != _checkpoint_path(output_dir, chunk).name:
                raise ValueError("filename mismatch")
            if value.get("row_count") != chunk.days or value.get("partition_count") != chunk.days:
                raise ValueError("partition count mismatch")
            elapsed = value.get("elapsed_seconds")
            if (
                isinstance(elapsed, bool)
                or not isinstance(elapsed, (int, float))
                or not math.isfinite(elapsed)
                or elapsed < 0
            ):
                raise ValueError("elapsed time is invalid")
            started_at = datetime.fromisoformat(value.get("started_at"))
            finished_at = datetime.fromisoformat(value.get("finished_at"))
            if (
                started_at.tzinfo is None
                or finished_at.tzinfo is None
                or finished_at < started_at
            ):
                raise ValueError("checkpoint timestamps are invalid")
            sql = bounded_sql.build_chunk_sql(provider, start.isoformat(), end.isoformat())
            rendered_hash = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            if value.get("rendered_sql_sha256") != rendered_hash:
                raise ValueError("rendered SQL hash mismatch")
            payload = value.get("payload")
            if not isinstance(payload, dict):
                raise ValueError("payload is invalid")
            if value.get("result_sha256") != _canonical_sha256(payload):
                raise ValueError("result hash mismatch")
            validate_chunk_payload(payload, chunk)
            for offset in range(chunk.days):
                partition = (provider, start + timedelta(days=offset))
                if partition in occupied:
                    raise ValueError("checkpoint ranges overlap")
                occupied.add(partition)
            records.append(CheckpointRecord(
                path=path,
                provider=provider,
                start_date=start,
                end_date=end,
                elapsed_seconds=float(elapsed),
                query_contract_sha256=value["query_contract_sha256"],
                rendered_sql_sha256=rendered_hash,
                scope_fingerprint=value["scope_fingerprint"],
                cli_version=value["cli_version"],
                payload=payload,
                candidate_end_date=scope.candidate_end_date,
                provider_allowlist=scope.providers,
                runner_version=value["runner_version"],
                query_contract_version=value["query_contract_version"],
            ))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            if "checkpoint integrity" in str(exc):
                raise ValueError(f"checkpoint integrity validation failed: {path.name}") from exc
            raise ValueError(f"checkpoint validation failed: {path.name}") from exc
    return sorted(records, key=lambda item: (
        scope.providers.index(item.provider), item.start_date, item.end_date,
    ))


def _timestamp_extreme(
    values: list[str],
    *,
    latest: bool,
) -> str | None:
    if not values:
        return None
    chooser = max if latest else min
    return chooser(values, key=datetime.fromisoformat)


def aggregate_candidate_rows(
    checkpoints: list[CheckpointRecord],
    scope: AuditScope,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if not isinstance(checkpoints, list):
        raise ValueError("checkpoints must be a list")

    expected = expected_partitions(scope)
    expected_set = set(expected)
    expected_query_hash = bounded_sql.query_contract_sha256()
    expected_scope_fingerprint = _scope_fingerprint(scope)
    shared_cli_version: str | None = None
    occupied: set[tuple[str, str]] = set()
    coverage_by_partition: dict[tuple[str, str], dict[str, Any]] = {}
    anomalies_by_partition: dict[tuple[str, str], dict[str, Any]] = {}
    runtime_by_partition: dict[tuple[str, str], dict[str, Any]] = {}

    for checkpoint in checkpoints:
        if not isinstance(checkpoint, CheckpointRecord):
            raise ValueError("checkpoint record is invalid")
        if checkpoint.query_contract_sha256 != expected_query_hash:
            raise ValueError("query_contract_sha256 mismatch")
        if checkpoint.scope_fingerprint != expected_scope_fingerprint:
            raise ValueError("scope_fingerprint mismatch")
        if checkpoint.candidate_end_date != scope.candidate_end_date:
            raise ValueError("candidate cutoff mismatch")
        if checkpoint.provider_allowlist != scope.providers:
            raise ValueError("provider allowlist mismatch")
        if checkpoint.runner_version != RUNNER_VERSION:
            raise ValueError("runner_version mismatch")
        if checkpoint.query_contract_version != QUERY_CONTRACT_VERSION:
            raise ValueError("query_contract_version mismatch")
        if (
            not isinstance(checkpoint.cli_version, str)
            or _CLI_VERSION_PATTERN.fullmatch(checkpoint.cli_version) is None
        ):
            raise ValueError("cli_version is invalid")
        if shared_cli_version is None:
            shared_cli_version = checkpoint.cli_version
        elif checkpoint.cli_version != shared_cli_version:
            raise ValueError("cli_version mismatch")
        if checkpoint.provider not in scope.providers:
            raise ValueError("checkpoint provider is outside scope")
        bounded_sql.validate_chunk(
            checkpoint.provider,
            checkpoint.start_date.isoformat(),
            checkpoint.end_date.isoformat(),
        )
        if (
            checkpoint.start_date < scope.start_date
            or checkpoint.end_date > scope.candidate_end_date
        ):
            raise ValueError("checkpoint range is outside candidate cutoff")
        chunk = ChunkSpec(
            checkpoint.provider, checkpoint.start_date, checkpoint.end_date,
        )
        sql = bounded_sql.build_chunk_sql(
            checkpoint.provider,
            checkpoint.start_date.isoformat(),
            checkpoint.end_date.isoformat(),
        )
        rendered_hash = hashlib.sha256(sql.encode("utf-8")).hexdigest()
        if checkpoint.rendered_sql_sha256 != rendered_hash:
            raise ValueError("rendered_sql_sha256 mismatch")
        validate_chunk_payload(checkpoint.payload, chunk)

        coverage_rows = {
            row["slate_date"]: row for row in checkpoint.payload["coverage"]
        }
        anomaly_rows = {
            row["slate_date"]: row
            for row in checkpoint.payload["source_anomalies"]
        }
        runtime_rows = {
            row["slate_date"]: row
            for row in checkpoint.payload["candidate_runtime"]
        }
        for offset in range(chunk.days):
            slate_date = (chunk.start_date + timedelta(days=offset)).isoformat()
            partition = (chunk.provider, slate_date)
            if partition in occupied:
                raise ValueError("checkpoint ranges overlap")
            occupied.add(partition)
            coverage_by_partition[partition] = {
                field: coverage_rows[slate_date][field]
                for field in _COVERAGE_FIELDS
            }
            anomalies_by_partition[partition] = dict(anomaly_rows[slate_date])
            runtime_by_partition[partition] = dict(runtime_rows[slate_date])

    if occupied != expected_set:
        raise ValueError("checkpoint partition matrix is incomplete")

    coverage = [coverage_by_partition[partition] for partition in expected]
    for row in coverage:
        if row["retention_preservation_complete"] is not True:
            raise ValueError(
                "retention_preservation_complete=false blocks completeness for "
                f"{row['provider']} {row['slate_date']}"
            )
    repeated_unknown_by_date: dict[str, int] = {}
    for _provider, slate_date in expected:
        unknown_count = anomalies_by_partition[(_provider, slate_date)][
            "unknown_provider_rows"
        ]
        previous = repeated_unknown_by_date.setdefault(slate_date, unknown_count)
        if previous != unknown_count:
            raise ValueError(
                "unknown_provider_rows must be identical across provider chunks"
            )
    deduplicated_unknown_total = sum(repeated_unknown_by_date.values())

    anomalies: list[dict[str, Any]] = []
    candidate_runtime: list[dict[str, Any]] = []
    for provider in scope.providers:
        provider_anomalies = [
            anomalies_by_partition[(provider, slate_date)]
            for partition_provider, slate_date in expected
            if partition_provider == provider
        ]
        anomaly_row = {
            "provider": provider,
            **{
                field: (
                    deduplicated_unknown_total
                    if field == "unknown_provider_rows"
                    else sum(row[field] for row in provider_anomalies)
                )
                for field in _ANOMALY_COUNTS
            },
        }
        if anomaly_row["slate_date_mismatch_rows"] != (
            anomaly_row["preserved_slate_date_mismatch_rows"]
            + anomaly_row["unpreserved_slate_date_mismatch_rows"]
        ):
            raise ValueError("cross-date preservation equation is inconsistent")
        anomalies.append(anomaly_row)

        provider_runtime = [
            runtime_by_partition[(provider, slate_date)]
            for partition_provider, slate_date in expected
            if partition_provider == provider
        ]
        runtime_row = {
            "provider": provider,
            "first_run_at": _timestamp_extreme(
                [row["first_run_at"] for row in provider_runtime if row["first_run_at"]],
                latest=False,
            ),
            "last_run_at": _timestamp_extreme(
                [row["last_run_at"] for row in provider_runtime if row["last_run_at"]],
                latest=True,
            ),
            "run_count": sum(row["run_count"] for row in provider_runtime),
            "completed_run_count": sum(
                row["completed_run_count"] for row in provider_runtime
            ),
            "failed_run_count": sum(
                row["failed_run_count"] for row in provider_runtime
            ),
            "request_count": sum(row["request_count"] for row in provider_runtime),
            "books_seen": sorted({
                book for row in provider_runtime for book in row["books_seen"]
            }),
            "first_snapshot_at": _timestamp_extreme(
                [
                    row["first_snapshot_at"]
                    for row in provider_runtime
                    if row["first_snapshot_at"]
                ],
                latest=False,
            ),
            "last_snapshot_at": _timestamp_extreme(
                [
                    row["last_snapshot_at"]
                    for row in provider_runtime
                    if row["last_snapshot_at"]
                ],
                latest=True,
            ),
            "snapshot_count": sum(
                row["snapshot_count"] for row in provider_runtime
            ),
            "snapshot_logical_bytes": sum(
                row["snapshot_logical_bytes"] for row in provider_runtime
            ),
            "last_heartbeat_at": _timestamp_extreme(
                [
                    row["last_heartbeat_at"]
                    for row in provider_runtime
                    if row["last_heartbeat_at"]
                ],
                latest=True,
            ),
            "last_message_at": _timestamp_extreme(
                [
                    row["last_message_at"]
                    for row in provider_runtime
                    if row["last_message_at"]
                ],
                latest=True,
            ),
            "heartbeat_count": sum(
                row["heartbeat_count"] for row in provider_runtime
            ),
        }
        coverage_rows = [row for row in coverage if row["provider"] == provider]
        if runtime_row["snapshot_count"] != sum(
            row["raw_snapshot_rows"] for row in coverage_rows
        ):
            raise ValueError("candidate runtime snapshot rows contradict coverage")
        if runtime_row["snapshot_logical_bytes"] != sum(
            row["raw_logical_bytes"] for row in coverage_rows
        ):
            raise ValueError("candidate runtime snapshot bytes contradict coverage")
        candidate_runtime.append(runtime_row)

    for row in anomalies:
        for field in _BLOCKING_ANOMALY_COUNTS:
            if row[field] != 0:
                raise ValueError(
                    f"source anomaly blocks completeness: {field}={row[field]}"
                )

    return coverage, anomalies, candidate_runtime


def _validate_runtime_payload(payload: dict[str, Any], scope: AuditScope) -> None:
    if not isinstance(payload, dict):
        raise ValueError("runtime payload must be an object")
    _reject_unknown_fields(payload, _RUNTIME_PAYLOAD_FIELDS, "runtime payload")
    if payload.get("runtime_version") != AUDIT_VERSION:
        raise ValueError("runtime payload version is invalid")
    if _parse_nullable_timestamp(payload, "generated_at") is None:
        raise ValueError("generated_at timestamp is required")
    if payload.get("candidate_end_date") != scope.candidate_end_date.isoformat():
        raise ValueError("runtime candidate cutoff is invalid")
    providers = payload.get("providers")
    if not isinstance(providers, list) or len(providers) != len(scope.providers):
        raise ValueError("runtime providers are incomplete")
    seen: list[str] = []
    for row in providers:
        if not isinstance(row, dict) or row.get("provider") not in scope.providers:
            raise ValueError("runtime provider record is invalid")
        _reject_unknown_fields(
            row, _RUNTIME_PROVIDER_FIELDS, "runtime provider record",
        )
        provider = row["provider"]
        if provider in seen:
            raise ValueError("runtime provider record is duplicated")
        seen.append(provider)
        boundaries: dict[str, datetime | None] = {}
        for field in _RUNTIME_BOUNDARY_FIELDS:
            if field not in row:
                raise ValueError(f"runtime boundary field is missing: {field}")
            value = row[field]
            if value is None:
                boundaries[field] = None
                continue
            if not isinstance(value, str):
                raise ValueError(f"runtime boundary timestamp is invalid: {field}")
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError as exc:
                raise ValueError(f"runtime boundary timestamp is invalid: {field}") from exc
            if parsed.tzinfo is None or parsed.utcoffset() is None:
                raise ValueError(f"runtime boundary timestamp must be timezone-aware: {field}")
            boundaries[field] = parsed
        for current_field, candidate_field in _RUNTIME_BOUNDARY_PAIRS:
            current = boundaries[current_field]
            candidate = boundaries[candidate_field]
            if candidate is not None and (current is None or candidate > current):
                raise ValueError("candidate runtime boundary is outside current evidence")
        actual_closure_flag = row.get("post_boltodds_suspension")
        if not isinstance(actual_closure_flag, bool):
            raise ValueError("runtime closure flag is invalid")
        suspended_at = datetime.fromisoformat(bounded_sql.BOLTODDS_SUSPENDED_AT)
        expected_closure_flag = provider == "boltodds" and any(
            boundaries[field] is not None and boundaries[field] > suspended_at
            for field in (
                "current_latest_run_at",
                "current_latest_snapshot_at",
                "current_latest_heartbeat_at",
                "current_latest_message_at",
            )
        )
        if actual_closure_flag != expected_closure_flag:
            raise ValueError("post_boltodds_suspension contradicts runtime boundaries")
        if expected_closure_flag:
            raise ValueError("post_boltodds_suspension blocks runtime closure")
    if tuple(seen) != scope.providers:
        raise ValueError("runtime providers are not in canonical order")


def _phoenix_today() -> date:
    return datetime.now(ZoneInfo(TIMEZONE)).date()


def validate_runtime_boundary(value: dict[str, Any], scope: AuditScope) -> None:
    if not isinstance(value, dict):
        raise ValueError("runtime boundary must be an object")
    _validate_runtime_payload(value, scope)
    generated_at = _parse_nullable_timestamp(value, "generated_at")
    if generated_at is None:
        raise ValueError("generated_at timestamp is required")
    phoenix_day = generated_at.astimezone(ZoneInfo(TIMEZONE)).date()
    if scope.as_of_date != _phoenix_today() or phoenix_day != scope.as_of_date:
        raise ValueError("generated_at must match the current Phoenix audit day")


def _same_timestamp(left: str | None, right: str | None) -> bool:
    if left is None or right is None:
        return left is right
    return datetime.fromisoformat(left) == datetime.fromisoformat(right)


def assemble_v2_envelope(
    scope: AuditScope,
    checkpoints: list[CheckpointRecord],
    runtime_boundary: dict[str, Any],
    audit_generated_at: datetime,
) -> dict[str, Any]:
    if (
        not isinstance(audit_generated_at, datetime)
        or audit_generated_at.tzinfo is None
        or audit_generated_at.utcoffset() is None
    ):
        raise ValueError("audit_generated_at must be timezone-aware Phoenix time")
    phoenix = ZoneInfo(TIMEZONE)
    phoenix_generated_at = audit_generated_at.astimezone(phoenix)
    if (
        phoenix_generated_at.utcoffset() != audit_generated_at.utcoffset()
        or phoenix_generated_at.date() != scope.as_of_date
    ):
        raise ValueError("audit_generated_at must match the Phoenix audit day")

    coverage, source_anomalies, candidate_runtime = aggregate_candidate_rows(
        checkpoints, scope,
    )
    validate_runtime_boundary(runtime_boundary, scope)
    boundary_by_provider = {
        row["provider"]: row for row in runtime_boundary["providers"]
    }
    runtime_by_provider = {row["provider"]: row for row in candidate_runtime}
    candidate_fields = (
        ("candidate_latest_run_at", "last_run_at"),
        ("candidate_latest_snapshot_at", "last_snapshot_at"),
        ("candidate_latest_heartbeat_at", "last_heartbeat_at"),
        ("candidate_latest_message_at", "last_message_at"),
    )
    for provider in scope.providers:
        boundary_row = boundary_by_provider[provider]
        candidate_row = runtime_by_provider[provider]
        for boundary_field, candidate_field in candidate_fields:
            if not _same_timestamp(
                boundary_row[boundary_field], candidate_row[candidate_field],
            ):
                raise ValueError(
                    f"{boundary_field} does not match candidate runtime"
                )

    expected_chunk_ranges = [
        {
            "provider": provider,
            "start_date": scope.start_date.isoformat(),
            "end_date": scope.candidate_end_date.isoformat(),
        }
        for provider in scope.providers
    ]
    completed_chunk_ranges = [
        {
            "provider": checkpoint.provider,
            "start_date": checkpoint.start_date.isoformat(),
            "end_date": checkpoint.end_date.isoformat(),
        }
        for checkpoint in sorted(
            checkpoints,
            key=lambda item: (
                scope.providers.index(item.provider), item.start_date, item.end_date,
            ),
        )
    ]
    cli_versions = {checkpoint.cli_version for checkpoint in checkpoints}
    if len(cli_versions) != 1:
        raise ValueError("cli_version mismatch")
    execution_contract = {
        "query_contract_sha256": bounded_sql.query_contract_sha256(),
        "query_contract_version": QUERY_CONTRACT_VERSION,
        "runner_version": RUNNER_VERSION,
        "cli_version": next(iter(cli_versions)),
        "chunk_ladder_days": list(CHUNK_LADDER),
        "soft_elapsed_seconds": SOFT_ELAPSED_SECONDS,
        "cooldown_seconds": COOLDOWN_SECONDS,
        "max_chunk_days": max(CHUNK_LADDER),
        "default_max_chunks": DEFAULT_MAX_CHUNKS,
        "hard_max_chunks": HARD_MAX_CHUNKS,
        "expected_chunk_ranges": expected_chunk_ranges,
        "completed_chunk_ranges": completed_chunk_ranges,
        "complete": True,
    }
    return {
        "audit_version": AUDIT_VERSION,
        "audit_generated_at": audit_generated_at.isoformat(),
        "as_of_date": scope.as_of_date.isoformat(),
        "timezone": TIMEZONE,
        "candidate_scope": {
            "start_date": scope.start_date.isoformat(),
            "end_date": scope.candidate_end_date.isoformat(),
            "raw_retention_days": scope.raw_retention_days,
            "providers": list(scope.providers),
        },
        "protected_scope": {
            "start_date": scope.first_protected_date.isoformat(),
            "reason": "dates inside the raw retention window are excluded",
        },
        "execution": execution_contract,
        "coverage": coverage,
        "source_anomalies": source_anomalies,
        "candidate_runtime": candidate_runtime,
        "runtime_boundary": [
            {field: row[field] for field in _RUNTIME_PROVIDER_FIELDS}
            for row in runtime_boundary["providers"]
        ],
        "season_evidence": None,
        "pins": None,
        "complete": True,
        "retention_execution_closed": True,
        "deletion_approved": False,
    }


def run_runtime_boundary(
    scope: AuditScope,
    output_dir: Path,
) -> Path:
    output_dir = preflight_output_dir(output_dir)
    resolved_cli_version = resolve_cli_version()
    sql = bounded_sql.build_runtime_boundary_sql(scope.candidate_end_date.isoformat())
    started_at = datetime.now(timezone.utc)
    started_clock = time.perf_counter()
    try:
        completed = run_linked_query(sql)
    except subprocess.TimeoutExpired as exc:
        raise AuditFailure("timeout") from exc
    except Exception as exc:
        raise AuditFailure(classify_failure(exc)) from exc
    if completed.returncode != 0:
        raise AuditFailure(classify_failure(completed))
    if not completed.stdout or not completed.stdout.strip():
        raise AuditFailure("empty_stdout")
    try:
        payload = parse_supabase_object(completed.stdout, "retention_runtime_boundary")
    except ValueError as exc:
        raise AuditFailure("malformed_json") from exc
    try:
        validate_runtime_boundary(payload, scope)
    except ValueError as exc:
        raise AuditFailure("validation_failed") from exc
    finished_at = datetime.now(timezone.utc)
    value = {
        "audit_version": AUDIT_VERSION,
        "runner_version": RUNNER_VERSION,
        "cli_version": resolved_cli_version,
        "query_contract_version": QUERY_CONTRACT_VERSION,
        "status": "completed",
        "complete": True,
        "sanitized_error": None,
        "timezone": TIMEZONE,
        "as_of_date": scope.as_of_date.isoformat(),
        "start_date": scope.start_date.isoformat(),
        "candidate_end_date": scope.candidate_end_date.isoformat(),
        "first_protected_date": scope.first_protected_date.isoformat(),
        "raw_retention_days": scope.raw_retention_days,
        "providers": list(scope.providers),
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "elapsed_seconds": time.perf_counter() - started_clock,
        "query_contract_sha256": bounded_sql.query_contract_sha256(),
        "rendered_sql_sha256": hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        "scope_fingerprint": _scope_fingerprint(scope),
        "result_sha256": _canonical_sha256(payload),
        "payload": payload,
    }
    value["checkpoint_integrity_sha256"] = _checkpoint_integrity_sha256(value)
    path = output_dir / f"runtime-boundary-{scope.as_of_date.isoformat()}.json"
    write_json_atomic(path, value)
    return path


def _load_runtime_boundary_checkpoint(
    path: Path,
    scope: AuditScope,
    cli_version: str,
) -> dict[str, Any]:
    path = Path(path)
    if not path.is_file():
        raise ValueError("runtime boundary evidence is absent")
    if path.name != f"runtime-boundary-{scope.as_of_date.isoformat()}.json":
        raise ValueError("runtime boundary filename mismatch")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("runtime boundary checkpoint must be an object")
    integrity_hash = value.get("checkpoint_integrity_sha256")
    if (
        not isinstance(integrity_hash, str)
        or integrity_hash != _checkpoint_integrity_sha256(value)
    ):
        raise ValueError("runtime boundary checkpoint integrity mismatch")
    expected_fields = {
        "audit_version": AUDIT_VERSION,
        "runner_version": RUNNER_VERSION,
        "cli_version": cli_version,
        "query_contract_version": QUERY_CONTRACT_VERSION,
        "status": "completed",
        "complete": True,
        "sanitized_error": None,
        "timezone": TIMEZONE,
        "as_of_date": scope.as_of_date.isoformat(),
        "start_date": scope.start_date.isoformat(),
        "candidate_end_date": scope.candidate_end_date.isoformat(),
        "first_protected_date": scope.first_protected_date.isoformat(),
        "raw_retention_days": scope.raw_retention_days,
        "providers": list(scope.providers),
        "query_contract_sha256": bounded_sql.query_contract_sha256(),
        "scope_fingerprint": _scope_fingerprint(scope),
    }
    for field, expected in expected_fields.items():
        if value.get(field) != expected:
            raise ValueError(f"runtime boundary {field} mismatch")
    elapsed = value.get("elapsed_seconds")
    if (
        isinstance(elapsed, bool)
        or not isinstance(elapsed, (int, float))
        or not math.isfinite(elapsed)
        or elapsed < 0
    ):
        raise ValueError("runtime boundary elapsed_seconds is invalid")
    started_at = _parse_nullable_timestamp(value, "started_at")
    finished_at = _parse_nullable_timestamp(value, "finished_at")
    if started_at is None or finished_at is None or finished_at < started_at:
        raise ValueError("runtime boundary checkpoint timestamps are invalid")
    sql = bounded_sql.build_runtime_boundary_sql(scope.candidate_end_date.isoformat())
    rendered_hash = hashlib.sha256(sql.encode("utf-8")).hexdigest()
    if value.get("rendered_sql_sha256") != rendered_hash:
        raise ValueError("runtime boundary rendered_sql_sha256 mismatch")
    payload = value.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("runtime boundary payload is invalid")
    if value.get("result_sha256") != _canonical_sha256(payload):
        raise ValueError("runtime boundary result_sha256 mismatch")
    validate_runtime_boundary(payload, scope)
    return payload


def assemble_local(scope: AuditScope, output_dir: Path, runtime_json: Path) -> Path:
    output_dir = preflight_output_dir(output_dir)
    checkpoints = load_valid_checkpoints(output_dir, scope)
    if not checkpoints:
        raise ValueError("checkpoint matrix is absent")
    cli_versions = {checkpoint.cli_version for checkpoint in checkpoints}
    if len(cli_versions) != 1:
        raise ValueError("cli_version mismatch")
    runtime_boundary = _load_runtime_boundary_checkpoint(
        runtime_json, scope, next(iter(cli_versions)),
    )
    envelope = assemble_v2_envelope(
        scope,
        checkpoints,
        runtime_boundary,
        audit_generated_at=datetime.now(ZoneInfo(TIMEZONE)),
    )
    output_path = output_dir / "bounded_retention_envelope.json"
    write_json_atomic(output_path, envelope)
    return output_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bounded_retention_audit",
        description="Run bounded SELECT-only season-retention audit reads.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="Run bounded historical chunks")
    run.add_argument("--as-of", required=True)
    run.add_argument("--output-dir", type=Path, default=Path("analytics/output/retention"))
    run.add_argument("--run-linked-read", action="store_true")
    run.add_argument("--max-chunks", type=int, choices=range(1, HARD_MAX_CHUNKS + 1), default=DEFAULT_MAX_CHUNKS)
    run.add_argument("--allow-multi-chunk", action="store_true")

    explicit = commands.add_parser(
        "run-chunk", help="Run one explicit bounded historical chunk",
    )
    explicit.add_argument("--as-of", required=True)
    explicit.add_argument("--output-dir", type=Path, required=True)
    explicit.add_argument("--run-linked-read", action="store_true")
    explicit.add_argument("--provider", required=True)
    explicit.add_argument("--start-date", required=True)
    explicit.add_argument("--end-date", required=True)

    runtime = commands.add_parser(
        "runtime-boundary", help="Run the separate bounded runtime read",
    )
    runtime.add_argument("--as-of", required=True)
    runtime.add_argument("--output-dir", type=Path, default=Path("analytics/output/retention"))
    runtime.add_argument("--run-linked-read", action="store_true")

    assemble = commands.add_parser("assemble", help="Assemble validated local evidence")
    assemble.add_argument("--as-of", required=True)
    assemble.add_argument("--output-dir", type=Path, default=Path("analytics/output/retention"))
    assemble.add_argument("--runtime-json", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:
        return 0 if exc.code == 0 else 3
    try:
        scope = build_scope(args.as_of)
        if args.command in ("run", "run-chunk", "runtime-boundary") and not args.run_linked_read:
            print("error: linked_read_acknowledgement_required", file=sys.stderr)
            return 3
        if args.command == "run":
            if args.max_chunks > DEFAULT_MAX_CHUNKS and not args.allow_multi_chunk:
                print("error: multi_chunk_acknowledgement_required", file=sys.stderr)
                return 3
            run_chunks(scope, args.output_dir, max_chunks=args.max_chunks)
        elif args.command == "run-chunk":
            provider, start, end = bounded_sql.validate_chunk(
                args.provider, args.start_date, args.end_date,
            )
            run_explicit_chunk(
                scope, args.output_dir, ChunkSpec(provider, start, end),
            )
        elif args.command == "runtime-boundary":
            run_runtime_boundary(scope, args.output_dir)
        else:
            assemble_local(scope, args.output_dir, args.runtime_json)
    except AuditFailure as exc:
        print(f"error: {exc.code}", file=sys.stderr)
        return 3
    except (OSError, ValueError):
        print("error: validation_failed", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
