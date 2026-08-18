from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from scripts import retention_bounded_sql as bounded_sql

AUDIT_VERSION = 2
RAW_RETENTION_DAYS = 30
CHUNK_LADDER = (1, 3, 7)
SOFT_ELAPSED_SECONDS = 30.0
COOLDOWN_SECONDS = 30.0
DEFAULT_MAX_CHUNKS = 1
HARD_MAX_CHUNKS = 5
QUERY_TIMEOUT_SECONDS = 120
CLI_VERSION = "supabase-db-query-linked-json-v1"
RUNNER_VERSION = "2"
TIMEZONE = "America/Phoenix"

_COVERAGE_COUNTS = (
    "raw_snapshot_rows",
    "raw_logical_bytes",
    "raw_group_count",
    "compact_group_count",
    "exact_group_count",
    "mismatched_group_count",
    "missing_compact_group_count",
    "unexpected_compact_group_count",
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


def parse_supabase_object(stdout: str, column: str) -> dict[str, Any]:
    if not isinstance(stdout, str) or not stdout.strip():
        raise ValueError("empty stdout")
    try:
        rows = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError("malformed JSON") from exc
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
    if payload.get("chunk_version") != AUDIT_VERSION or payload.get("complete") is not True:
        raise ValueError("chunk payload version or completion status is invalid")
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
        _require_nonnegative_integers(row, _COVERAGE_COUNTS)
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

        anomaly_row = anomalies[slate_date]
        _require_nonnegative_integers(anomaly_row, _ANOMALY_COUNTS)
        runtime_row = runtime[slate_date]
        _require_nonnegative_integers(runtime_row, _RUNTIME_COUNTS)
        if runtime_row["completed_run_count"] + runtime_row["failed_run_count"] > runtime_row["run_count"]:
            raise ValueError("runtime run counts are inconsistent")
        if runtime_row["snapshot_count"] != row["raw_snapshot_rows"]:
            raise ValueError("runtime snapshot count does not match coverage")
        if runtime_row["snapshot_logical_bytes"] != row["raw_logical_bytes"]:
            raise ValueError("runtime snapshot bytes do not match coverage")
        books = runtime_row.get("books_seen")
        if not isinstance(books, list) or any(not isinstance(book, str) for book in books):
            raise ValueError("runtime books_seen must be a string list")


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
) -> dict[str, Any]:
    return {
        "audit_version": AUDIT_VERSION,
        "runner_version": RUNNER_VERSION,
        "cli_version": CLI_VERSION,
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


def run_chunks(
    scope: AuditScope,
    output_dir: Path,
    max_chunks: int = DEFAULT_MAX_CHUNKS,
) -> list[CheckpointRecord]:
    if isinstance(max_chunks, bool) or not isinstance(max_chunks, int) or not 1 <= max_chunks <= HARD_MAX_CHUNKS:
        raise ValueError("max_chunks must be between 1 and 5")
    output_dir = Path(output_dir)
    checkpoints = load_valid_checkpoints(output_dir, scope)
    written: list[CheckpointRecord] = []
    for index in range(max_chunks):
        chunk = select_next_chunk(scope, checkpoints)
        if chunk is None:
            break
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
            payload = parse_supabase_object(completed.stdout, "retention_bounded_chunk")
        except ValueError as exc:
            raise AuditFailure("malformed_json") from exc
        try:
            validate_chunk_payload(payload, chunk)
        except ValueError as exc:
            raise AuditFailure("validation_failed") from exc
        elapsed = time.perf_counter() - started_clock
        finished_at = datetime.now(timezone.utc)
        checkpoint_value = _checkpoint_value(
            scope, chunk, sql, payload, started_at, finished_at, elapsed,
        )
        path = _checkpoint_path(output_dir, chunk)
        write_json_atomic(path, checkpoint_value)
        record = CheckpointRecord(
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
        )
        checkpoints.append(record)
        written.append(record)
        if elapsed > SOFT_ELAPSED_SECONDS:
            break
        if index + 1 < max_chunks and select_next_chunk(scope, checkpoints) is not None:
            time.sleep(COOLDOWN_SECONDS)
    return written


def load_valid_checkpoints(
    output_dir: Path, scope: AuditScope,
) -> list[CheckpointRecord]:
    output_dir = Path(output_dir)
    if not output_dir.exists():
        return []
    if not output_dir.is_dir():
        raise ValueError("output directory must be a directory")
    expected_scope_fields = {
        "audit_version": AUDIT_VERSION,
        "runner_version": RUNNER_VERSION,
        "cli_version": CLI_VERSION,
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
            for field, expected in expected_scope_fields.items():
                if value.get(field) != expected:
                    raise ValueError(f"{field} mismatch")
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
            ))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"checkpoint validation failed: {path.name}") from exc
    return sorted(records, key=lambda item: (
        scope.providers.index(item.provider), item.start_date, item.end_date,
    ))


def _validate_runtime_payload(payload: dict[str, Any], scope: AuditScope) -> None:
    if payload.get("runtime_version") != AUDIT_VERSION:
        raise ValueError("runtime payload version is invalid")
    if payload.get("candidate_end_date") != scope.candidate_end_date.isoformat():
        raise ValueError("runtime candidate cutoff is invalid")
    providers = payload.get("providers")
    if not isinstance(providers, list) or len(providers) != len(scope.providers):
        raise ValueError("runtime providers are incomplete")
    seen: list[str] = []
    for row in providers:
        if not isinstance(row, dict) or row.get("provider") not in scope.providers:
            raise ValueError("runtime provider record is invalid")
        provider = row["provider"]
        if provider in seen:
            raise ValueError("runtime provider record is duplicated")
        seen.append(provider)
        if not isinstance(row.get("post_boltodds_suspension"), bool):
            raise ValueError("runtime closure flag is invalid")
    if tuple(seen) != scope.providers:
        raise ValueError("runtime providers are not in canonical order")


def run_runtime_boundary(scope: AuditScope, output_dir: Path) -> Path:
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
        _validate_runtime_payload(payload, scope)
    except ValueError as exc:
        raise AuditFailure("validation_failed") from exc
    finished_at = datetime.now(timezone.utc)
    value = {
        "audit_version": AUDIT_VERSION,
        "runner_version": RUNNER_VERSION,
        "cli_version": CLI_VERSION,
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
    path = Path(output_dir) / f"runtime-boundary-{scope.as_of_date.isoformat()}.json"
    write_json_atomic(path, value)
    return path


def assemble_local(scope: AuditScope, output_dir: Path, runtime_json: Path) -> None:
    del scope, output_dir, runtime_json
    raise AuditFailure("validation_failed")


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
        if args.command in ("run", "runtime-boundary") and not args.run_linked_read:
            print("error: linked_read_acknowledgement_required", file=sys.stderr)
            return 3
        if args.command == "run":
            if args.max_chunks > DEFAULT_MAX_CHUNKS and not args.allow_multi_chunk:
                print("error: multi_chunk_acknowledgement_required", file=sys.stderr)
                return 3
            run_chunks(scope, args.output_dir, max_chunks=args.max_chunks)
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
