"""Exact, token-gated executor for the reviewed active-provider raw scope.

Preview is SELECT-only. Execution handles exactly one approved provider/date
partition and remains unavailable unless every explicit gate is present.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import bounded_retention_audit as audit  # noqa: E402
from scripts import retention_bounded_sql as bounded_sql  # noqa: E402


SCOPE_ID = "prepared_active_provider_scope_v1"
PREVIEW_VERSION = 1
EXECUTION_VERSION = 1
PREPARED_PROVIDERS = ("propline", "therundown")
PREPARED_WINDOWS = (
    (date(2026, 6, 12), date(2026, 6, 30)),
    (date(2026, 7, 2), date(2026, 7, 12)),
    (date(2026, 7, 16), date(2026, 7, 26)),
)
REVIEW_PACKET_GENERATED_AT = datetime(
    2026, 9, 2, 17, 56, 49, tzinfo=timezone.utc,
)
FINAL_HISTORICAL_COMPACT_WRITE_AT = datetime(
    2026, 8, 27, 22, 19, 39, 703533, tzinfo=timezone.utc,
)
APPROVAL_TTL = timedelta(hours=24)
QUERY_TIMEOUT_SECONDS = 120
TRUTHY = {"1", "true", "yes", "on"}
DELETE_TOKEN_ENV = "APPROVED_PREPARED_MARKET_SNAPSHOT_DELETE_TOKEN"
DELETE_ALLOW_ENV = "ALLOW_MARKET_SNAPSHOT_DELETE"

_SOURCE_COUNT_FIELDS = (
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
_ANOMALY_FIELDS = (
    "rows_missing_run_id",
    "rows_missing_run_row",
    "rows_missing_group_key",
    "provider_run_mismatch_rows",
    "slate_date_mismatch_rows",
    "preserved_slate_date_mismatch_rows",
    "unpreserved_slate_date_mismatch_rows",
    "unknown_provider_rows",
)
_FORBIDDEN_MUTATION_SQL = re.compile(
    r"\b(insert|update|truncate|drop|alter|create|grant|revoke|vacuum|"
    r"reindex|merge|call|copy|do)\b",
    re.IGNORECASE,
)

QueryRunner = Callable[..., subprocess.CompletedProcess[str]]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_sha256(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _prepared_dates() -> frozenset[date]:
    values: set[date] = set()
    for start, end in PREPARED_WINDOWS:
        cursor = start
        while cursor <= end:
            values.add(cursor)
            cursor += timedelta(days=1)
    return frozenset(values)


PREPARED_DATES = _prepared_dates()


def validate_scope(provider: str, slate_date: str) -> tuple[str, str]:
    if provider not in PREPARED_PROVIDERS:
        raise ValueError("provider/date is outside the prepared scope")
    try:
        parsed_date = bounded_sql.parse_iso_date(slate_date, "slate_date")
    except ValueError as exc:
        raise ValueError("provider/date is outside the prepared scope") from exc
    if parsed_date not in PREPARED_DATES:
        raise ValueError("provider/date is outside the prepared scope")
    return provider, parsed_date.isoformat()


def parse_timestamp(value: str, label: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a timezone-aware timestamp")
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{label} must be a timezone-aware timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must be a timezone-aware timestamp")
    return parsed.astimezone(timezone.utc)


def _exact_chunk(provider: str, slate_date: str) -> audit.ChunkSpec:
    checked_provider, checked_date = validate_scope(provider, slate_date)
    parsed = date.fromisoformat(checked_date)
    return audit.ChunkSpec(checked_provider, parsed, parsed)


def _validate_exact_payload(
    payload: dict[str, Any], provider: str, slate_date: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    chunk = _exact_chunk(provider, slate_date)
    audit.validate_chunk_payload(payload, chunk)
    coverage = payload["coverage"][0]
    anomalies = payload["source_anomalies"][0]
    if coverage["raw_snapshot_rows"] <= 0:
        raise ValueError("prepared partition has no raw snapshots")
    if (
        coverage["coverage_exact"] is not True
        or coverage["retention_preservation_complete"] is not True
    ):
        raise ValueError("exact compact coverage is required")
    if any(coverage[field] != 0 for field in (
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
    )):
        raise ValueError("exact compact coverage is required")
    if any(anomalies[field] != 0 for field in _ANOMALY_FIELDS):
        raise ValueError("source anomalies block prepared deletion")
    return coverage, anomalies


def extract_source_state(
    payload: dict[str, Any], provider: str, slate_date: str,
) -> dict[str, Any]:
    coverage, anomalies = _validate_exact_payload(payload, provider, slate_date)
    return {
        **{field: coverage[field] for field in _SOURCE_COUNT_FIELDS},
        "first_raw_seen_at": coverage["first_raw_seen_at"],
        "last_raw_seen_at": coverage["last_raw_seen_at"],
        "coverage_exact": True,
        "retention_preservation_complete": True,
        "source_anomalies": {
            field: anomalies[field] for field in _ANOMALY_FIELDS
        },
    }


def _validate_report_source_state(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("preview source state is invalid")
    expected_fields = {
        *_SOURCE_COUNT_FIELDS,
        "first_raw_seen_at",
        "last_raw_seen_at",
        "coverage_exact",
        "retention_preservation_complete",
        "source_anomalies",
    }
    if set(value) != expected_fields:
        raise ValueError("preview source state is invalid")
    for field in _SOURCE_COUNT_FIELDS:
        count = value.get(field)
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError("preview source state is invalid")
    if any(value[field] <= 0 for field in (
        "raw_snapshot_rows",
        "raw_logical_bytes",
        "raw_group_count",
        "compact_group_count",
        "exact_group_count",
    )):
        raise ValueError("preview source state is invalid")
    if not (
        value["raw_group_count"]
        == value["compact_group_count"]
        == value["exact_group_count"]
    ):
        raise ValueError("preview source state is not exact")
    if any(value[field] != 0 for field in _SOURCE_COUNT_FIELDS[5:]):
        raise ValueError("preview source state is not exact")
    if (
        value.get("coverage_exact") is not True
        or value.get("retention_preservation_complete") is not True
    ):
        raise ValueError("preview source state is not exact")
    first_seen = parse_timestamp(
        str(value.get("first_raw_seen_at") or ""), "first_raw_seen_at",
    )
    last_seen = parse_timestamp(
        str(value.get("last_raw_seen_at") or ""), "last_raw_seen_at",
    )
    if last_seen < first_seen:
        raise ValueError("preview source state timestamps are invalid")
    anomalies = value.get("source_anomalies")
    if not isinstance(anomalies, Mapping) or set(anomalies) != set(_ANOMALY_FIELDS):
        raise ValueError("preview source anomalies are invalid")
    if any(
        isinstance(anomalies[field], bool)
        or not isinstance(anomalies[field], int)
        or anomalies[field] != 0
        for field in _ANOMALY_FIELDS
    ):
        raise ValueError("preview source anomalies are invalid")
    return value


def _sql_timestamp(value: str) -> str:
    return parse_timestamp(value, "source timestamp").isoformat()


def build_delete_sql(report: Mapping[str, Any]) -> str:
    provider, slate_date = validate_scope(
        str(report.get("provider") or ""), str(report.get("slate_date") or ""),
    )
    state = _validate_report_source_state(report.get("source_state"))
    first_seen = _sql_timestamp(str(state.get("first_raw_seen_at") or ""))
    last_seen = _sql_timestamp(str(state.get("last_raw_seen_at") or ""))
    raw_rows = state["raw_snapshot_rows"]
    raw_bytes = state["raw_logical_bytes"]
    compact_groups = state["compact_group_count"]
    return f"""with target_runs as materialized (
  select mpr.id
  from public.market_provider_runs mpr
  where mpr.provider = '{provider}'
    and mpr.slate_date = date '{slate_date}'
),
candidate as materialized (
  select ms.id, ms.observed_at, pg_column_size(ms)::bigint as logical_bytes
  from public.market_snapshots ms
  join target_runs on target_runs.id = ms.run_id
  where ms.provider = '{provider}'
),
raw_state as (
  select
    count(*)::bigint as raw_snapshot_rows,
    coalesce(sum(candidate.logical_bytes), 0)::bigint as raw_logical_bytes,
    min(candidate.observed_at) as first_snapshot_at,
    max(candidate.observed_at) as last_snapshot_at
  from candidate
),
compact_state as (
  select
    count(*)::bigint as compact_group_count,
    coalesce(sum(cmlm.snapshot_count), 0)::bigint as represented_snapshot_rows
  from public.compact_market_line_movements cmlm
  where cmlm.provider = '{provider}'
    and cmlm.slate_date = date '{slate_date}'
),
execution_gate as (
  select
    raw_state.raw_snapshot_rows = {raw_rows}
    and raw_state.raw_logical_bytes = {raw_bytes}
    and raw_state.first_snapshot_at is not distinct from timestamptz '{first_seen}'
    and raw_state.last_snapshot_at is not distinct from timestamptz '{last_seen}'
    and compact_state.compact_group_count = {compact_groups}
    and compact_state.represented_snapshot_rows = {raw_rows}
      as source_state_matches,
    raw_state.raw_snapshot_rows as candidate_rows
  from raw_state
  cross join compact_state
),
deleted as (
  delete from public.market_snapshots ms
  using candidate, execution_gate
  where execution_gate.source_state_matches
    and ms.id = candidate.id
  returning ms.id
),
delete_state as (
  select count(*)::bigint as deleted_rows from deleted
)
select jsonb_build_object(
  'provider', '{provider}',
  'slate_date', '{slate_date}',
  'source_state_matches', execution_gate.source_state_matches,
  'candidate_rows', execution_gate.candidate_rows,
  'deleted_rows', delete_state.deleted_rows
) as prepared_market_snapshot_deletion
from execution_gate
cross join delete_state;"""


def assert_delete_sql_contract(sql: str) -> None:
    scrubbed = re.sub(r"--[^\n]*", " ", sql)
    lowered = " ".join(scrubbed.lower().split())
    if sql.count(";") != 1 or not sql.rstrip().endswith(";"):
        raise ValueError("delete SQL must be exactly one statement")
    if not lowered.startswith("with "):
        raise ValueError("delete SQL must begin with a bounded CTE")
    if lowered.count("delete from public.market_snapshots") != 1:
        raise ValueError("delete SQL must target market_snapshots exactly once")
    forbidden = _FORBIDDEN_MUTATION_SQL.search(scrubbed)
    if forbidden:
        raise ValueError(
            f"delete SQL contains prohibited operation: {forbidden.group(1).lower()}"
        )
    if "public.market_provider_runs" not in lowered:
        raise ValueError("delete SQL must bind provider runs")
    if "mpr.provider =" not in lowered or "mpr.slate_date = date" not in lowered:
        raise ValueError("delete SQL must bind one provider and one slate date")


def build_postcheck_sql(report: Mapping[str, Any]) -> str:
    provider, slate_date = validate_scope(
        str(report.get("provider") or ""), str(report.get("slate_date") or ""),
    )
    return f"""with target_runs as (
  select mpr.id
  from public.market_provider_runs mpr
  where mpr.provider = '{provider}'
    and mpr.slate_date = date '{slate_date}'
),
raw_state as (
  select count(ms.id)::bigint as raw_snapshot_rows
  from public.market_snapshots ms
  join target_runs on target_runs.id = ms.run_id
  where ms.provider = '{provider}'
),
compact_state as (
  select
    count(*)::bigint as compact_group_count,
    coalesce(sum(cmlm.snapshot_count), 0)::bigint as represented_snapshot_rows
  from public.compact_market_line_movements cmlm
  where cmlm.provider = '{provider}'
    and cmlm.slate_date = date '{slate_date}'
)
select jsonb_build_object(
  'provider', '{provider}',
  'slate_date', '{slate_date}',
  'raw_snapshot_rows', raw_state.raw_snapshot_rows,
  'compact_group_count', compact_state.compact_group_count,
  'represented_snapshot_rows', compact_state.represented_snapshot_rows
) as prepared_market_snapshot_postcheck
from raw_state
cross join compact_state;"""


def _approval_basis(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "preview_version": report.get("preview_version"),
        "scope_id": report.get("scope_id"),
        "provider": report.get("provider"),
        "slate_date": report.get("slate_date"),
        "source_state": report.get("source_state"),
        "preview_query_contract_sha256": report.get(
            "preview_query_contract_sha256"
        ),
        "rendered_preview_sql_sha256": report.get(
            "rendered_preview_sql_sha256"
        ),
        "delete_sql_sha256": report.get("delete_sql_sha256"),
        "backup_completed_at": report.get("backup_completed_at"),
        "generated_at": report.get("generated_at"),
        "approval_expires_at": report.get("approval_expires_at"),
    }


def build_preview_report(
    payload: dict[str, Any],
    *,
    provider: str,
    slate_date: str,
    backup_completed_at: str,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    checked_provider, checked_date = validate_scope(provider, slate_date)
    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    backup = parse_timestamp(backup_completed_at, "backup_completed_at")
    minimum_backup = max(
        REVIEW_PACKET_GENERATED_AT, FINAL_HISTORICAL_COMPACT_WRITE_AT,
    )
    if backup <= minimum_backup:
        raise ValueError("backup is not newer than the reviewed evidence")
    if backup > generated:
        raise ValueError("backup timestamp cannot be in the future")
    state = extract_source_state(payload, checked_provider, checked_date)
    preview_sql = bounded_sql.build_chunk_sql(
        checked_provider, checked_date, checked_date,
    )
    report: dict[str, Any] = {
        "preview_version": PREVIEW_VERSION,
        "scope_id": SCOPE_ID,
        "provider": checked_provider,
        "slate_date": checked_date,
        "source_state": state,
        "backup_completed_at": backup.isoformat(),
        "generated_at": generated.isoformat(),
        "approval_expires_at": (generated + APPROVAL_TTL).isoformat(),
        "preview_query_contract_sha256": bounded_sql.query_contract_sha256(),
        "rendered_preview_sql_sha256": sha256_text(preview_sql),
        "deletion_approved": False,
        "retention_execution_closed": True,
    }
    report["delete_sql_sha256"] = sha256_text(build_delete_sql(report))
    report["approval_token"] = canonical_sha256(_approval_basis(report))
    return report


def validate_preview_report(
    report: Mapping[str, Any], *, now: datetime | None = None,
) -> None:
    if report.get("preview_version") != PREVIEW_VERSION:
        raise ValueError("preview version is invalid")
    if report.get("scope_id") != SCOPE_ID:
        raise ValueError("preview scope is invalid")
    validate_scope(
        str(report.get("provider") or ""), str(report.get("slate_date") or ""),
    )
    if report.get("deletion_approved") is not False:
        raise ValueError("preview cannot approve deletion")
    if report.get("retention_execution_closed") is not True:
        raise ValueError("preview retention gate is invalid")
    generated = parse_timestamp(str(report.get("generated_at") or ""), "generated_at")
    expires = parse_timestamp(
        str(report.get("approval_expires_at") or ""), "approval_expires_at",
    )
    backup = parse_timestamp(
        str(report.get("backup_completed_at") or ""), "backup_completed_at",
    )
    minimum_backup = max(
        REVIEW_PACKET_GENERATED_AT, FINAL_HISTORICAL_COMPACT_WRITE_AT,
    )
    if backup <= minimum_backup or backup > generated:
        raise ValueError("preview backup evidence is invalid")
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    if generated > current or expires <= current or expires != generated + APPROVAL_TTL:
        raise ValueError("preview approval window is invalid or expired")
    _validate_report_source_state(report.get("source_state"))
    expected_token = canonical_sha256(_approval_basis(report))
    if report.get("approval_token") != expected_token:
        raise ValueError("preview approval token is invalid")
    expected_delete_hash = sha256_text(build_delete_sql(report))
    if report.get("delete_sql_sha256") != expected_delete_hash:
        raise ValueError("preview delete SQL hash is invalid")
    provider = str(report["provider"])
    slate_date = str(report["slate_date"])
    preview_sql = bounded_sql.build_chunk_sql(provider, slate_date, slate_date)
    if report.get("rendered_preview_sql_sha256") != sha256_text(preview_sql):
        raise ValueError("preview SELECT hash is invalid")
    if report.get("preview_query_contract_sha256") != bounded_sql.query_contract_sha256():
        raise ValueError("preview query contract changed")


def _run_cli_query(
    sql: str, *, allow_mutation: bool = False,
) -> subprocess.CompletedProcess[str]:
    if allow_mutation:
        assert_delete_sql_contract(sql)
    else:
        bounded_sql.assert_select_only(sql)
    npx = shutil.which("npx") or shutil.which("npx.cmd") or "npx"
    sql_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sql", delete=False, encoding="utf-8", newline="\n",
        ) as handle:
            handle.write(sql)
            sql_path = handle.name
        return subprocess.run(
            [
                npx,
                "supabase",
                "db",
                "query",
                "--linked",
                "--file",
                sql_path,
                "-o",
                "json",
            ],
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


def _read_preview_payload(
    provider: str,
    slate_date: str,
    query_runner: QueryRunner,
) -> dict[str, Any]:
    sql = bounded_sql.build_chunk_sql(provider, slate_date, slate_date)
    completed = query_runner(sql, allow_mutation=False)
    if completed.returncode != 0:
        raise ValueError("exact preview query failed")
    payload = audit.parse_supabase_object(
        completed.stdout, "retention_bounded_chunk",
    )
    _validate_exact_payload(payload, provider, slate_date)
    return payload


def _read_postcheck(
    report: Mapping[str, Any], query_runner: QueryRunner,
) -> dict[str, Any]:
    completed = query_runner(build_postcheck_sql(report), allow_mutation=False)
    if completed.returncode != 0:
        raise ValueError("postcheck query failed")
    return audit.parse_supabase_object(
        completed.stdout, "prepared_market_snapshot_postcheck",
    )


def _execution_gate_open(
    report: Mapping[str, Any], environment: Mapping[str, str],
) -> bool:
    allowed = str(environment.get(DELETE_ALLOW_ENV, "")).strip().lower() in TRUTHY
    token = str(environment.get(DELETE_TOKEN_ENV, "")).strip()
    return allowed and token == report.get("approval_token")


def execute_approved_partition(
    report: dict[str, Any],
    *,
    query_runner: QueryRunner = _run_cli_query,
    environment: Mapping[str, str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    validate_preview_report(report, now=now)
    selected_environment = environment if environment is not None else os.environ
    if not _execution_gate_open(report, selected_environment):
        raise ValueError("prepared deletion execution gate is closed")

    provider = str(report["provider"])
    slate_date = str(report["slate_date"])
    fresh_payload = _read_preview_payload(provider, slate_date, query_runner)
    fresh_state = extract_source_state(fresh_payload, provider, slate_date)
    if fresh_state != report["source_state"]:
        raise ValueError("prepared deletion source state changed")

    delete_sql = build_delete_sql(report)
    mutation: subprocess.CompletedProcess[str] | None = None
    mutation_error: str | None = None
    mutation_value: dict[str, Any] | None = None
    try:
        mutation = query_runner(delete_sql, allow_mutation=True)
        if mutation.returncode != 0:
            mutation_error = audit.classify_failure(mutation)
        else:
            try:
                mutation_value = audit.parse_supabase_object(
                    mutation.stdout, "prepared_market_snapshot_deletion",
                )
            except ValueError:
                mutation_error = "malformed_result"
    except subprocess.TimeoutExpired:
        mutation_error = "timeout"
    except OSError:
        mutation_error = "subprocess_failed"

    postcheck: dict[str, Any] | None = None
    postcheck_error: str | None = None
    try:
        postcheck = _read_postcheck(report, query_runner)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        postcheck_error = "postcheck_failed"

    expected_rows = report["source_state"]["raw_snapshot_rows"]
    expected_compact = report["source_state"]["compact_group_count"]
    postcheck_confirmed = bool(
        postcheck
        and postcheck.get("provider") == provider
        and postcheck.get("slate_date") == slate_date
        and postcheck.get("raw_snapshot_rows") == 0
        and postcheck.get("compact_group_count") == expected_compact
        and postcheck.get("represented_snapshot_rows") == expected_rows
    )
    result_confirmed = bool(
        mutation_value
        and mutation_value.get("provider") == provider
        and mutation_value.get("slate_date") == slate_date
        and mutation_value.get("source_state_matches") is True
        and mutation_value.get("candidate_rows") == expected_rows
        and mutation_value.get("deleted_rows") == expected_rows
    )

    if mutation_error is not None:
        status = "uncertain_transport"
        deleted_rows: int | None = None
    elif not result_confirmed:
        status = "uncertain_result"
        deleted_rows = (
            mutation_value.get("deleted_rows")
            if isinstance(mutation_value, dict)
            and isinstance(mutation_value.get("deleted_rows"), int)
            else None
        )
    elif not postcheck_confirmed:
        status = "uncertain_postcheck"
        deleted_rows = expected_rows
    else:
        status = "confirmed"
        deleted_rows = expected_rows

    finished = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return {
        "execution_version": EXECUTION_VERSION,
        "scope_id": SCOPE_ID,
        "provider": provider,
        "slate_date": slate_date,
        "approval_token": report["approval_token"],
        "delete_sql_sha256": sha256_text(delete_sql),
        "executed_at": finished.isoformat(),
        "status": status,
        "deleted_rows": deleted_rows,
        "mutation_error": mutation_error,
        "postcheck_error": postcheck_error,
        "postcheck": postcheck,
        "automatic_retry_attempted": False,
        "vacuum_attempted": False,
    }


def _write_new_json(path: Path, value: dict[str, Any]) -> None:
    if path.exists():
        raise ValueError("output path already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    audit.write_json_atomic(path, value)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON document must be an object")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Preview or execute one prepared raw snapshot partition.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    preview = commands.add_parser("preview", help="Run one exact SELECT-only preview")
    preview.add_argument("--provider", required=True)
    preview.add_argument("--slate-date", required=True)
    preview.add_argument("--backup-completed-at", required=True)
    preview.add_argument("--output", required=True, type=Path)
    preview.add_argument("--run-linked-read", action="store_true")

    execute = commands.add_parser("execute", help="Execute one separately approved partition")
    execute.add_argument("--preview-report", required=True, type=Path)
    execute.add_argument("--output", required=True, type=Path)
    execute.add_argument("--run-linked-delete", action="store_true")
    execute.add_argument("--execute", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.command == "preview":
            if not args.run_linked_read:
                raise ValueError("linked read acknowledgement is required")
            provider, slate_date = validate_scope(args.provider, args.slate_date)
            payload = _read_preview_payload(provider, slate_date, _run_cli_query)
            report = build_preview_report(
                payload,
                provider=provider,
                slate_date=slate_date,
                backup_completed_at=args.backup_completed_at,
            )
            _write_new_json(args.output, report)
            print(
                "prepared_market_snapshot_preview "
                f"provider={provider} slate_date={slate_date} "
                f"rows={report['source_state']['raw_snapshot_rows']} "
                f"approval_token={report['approval_token']}"
            )
        else:
            if not args.execute or not args.run_linked_delete:
                raise ValueError("linked delete acknowledgement is required")
            report = _load_json(args.preview_report)
            result = execute_approved_partition(report)
            _write_new_json(args.output, result)
            print(
                "prepared_market_snapshot_execution "
                f"provider={result['provider']} slate_date={result['slate_date']} "
                f"status={result['status']} deleted={result['deleted_rows']}"
            )
            if result["status"] != "confirmed":
                return 3
    except (json.JSONDecodeError, OSError, ValueError):
        print("error: validation_or_execution_failed", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
