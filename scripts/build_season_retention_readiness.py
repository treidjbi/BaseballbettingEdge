from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, TextIO
from zoneinfo import ZoneInfo

from scripts import retention_bounded_sql as bounded_sql


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GATE_C_MANIFEST = ROOT / "data/research/gate_c/pitcher_k_outcome_dataset_manifest.json"
DEFAULT_OUTPUT_DIR = ROOT / "analytics/output/retention"
ALLOWED_PROVIDERS = {"boltodds", "propline", "the_odds", "therundown"}
MISMATCH_FIELDS = (
    "missing_compact_group_count", "unexpected_compact_group_count",
    "duplicate_compact_group_count", "first_seen_mismatch_count",
    "last_seen_mismatch_count", "first_odds_mismatch_count",
    "last_odds_mismatch_count", "min_odds_mismatch_count",
    "max_odds_mismatch_count", "odds_move_count_mismatch_count",
    "snapshot_count_mismatch_count",
)
REQUIRED_DECISION_EVIDENCE = (
    "results", "bet_timing", "checkpoint_market", "close_clv", "provider_metadata",
)
BOLTODDS_SUSPENDED_AT = datetime.fromisoformat("2026-06-17T17:22:29+00:00")
PHOENIX_TZ = ZoneInfo("America/Phoenix")
EVIDENCE_PIN_REASONS = {
    "official_tracked_picks": "official_tracked_pick",
    "accepted_bets": "accepted_bet",
    "sent_notifications": "sent_notification",
    "consumed_locks": "consumed_lock",
    "frozen_alt_v2_rows": "frozen_alt_v2",
    "operator_incidents": "operator_incident",
    "model_review_pins": "model_review",
}
EVIDENCE_REQUIRED_FIELDS = {
    "official_tracked_picks": (
        "results", "checkpoint_market", "close_clv", "provider_metadata",
    ),
    "accepted_bets": REQUIRED_DECISION_EVIDENCE,
    "sent_notifications": ("bet_timing", "checkpoint_market", "provider_metadata"),
    "consumed_locks": ("checkpoint_market", "provider_metadata"),
    "frozen_alt_v2_rows": (
        "results", "checkpoint_market", "close_clv", "provider_metadata",
    ),
    "operator_incidents": ("provider_metadata",),
    "model_review_pins": (
        "results", "checkpoint_market", "close_clv", "provider_metadata",
    ),
}
SECRET_KEY = re.compile(
    r"(?:authorization|password|secret|token|api[_-]?key|service[_-]?role)", re.IGNORECASE
)

_COVERAGE_INTEGER_FIELDS = (
    "raw_snapshot_rows", "raw_logical_bytes", "raw_group_count",
    "compact_group_count", "exact_group_count", "mismatched_group_count",
    *MISMATCH_FIELDS,
)
_ANOMALY_INTEGER_FIELDS = (
    "rows_missing_run_id", "rows_missing_run_row", "rows_missing_group_key",
    "provider_run_mismatch_rows",
)
_V2_ANOMALY_INTEGER_FIELDS = (
    *_ANOMALY_INTEGER_FIELDS,
    "slate_date_mismatch_rows",
    "preserved_slate_date_mismatch_rows",
    "unpreserved_slate_date_mismatch_rows",
    "unknown_provider_rows",
)
_V2_BLOCKING_ANOMALY_INTEGER_FIELDS = (
    *_ANOMALY_INTEGER_FIELDS,
    "unpreserved_slate_date_mismatch_rows",
    "unknown_provider_rows",
)
_RUNTIME_INTEGER_FIELDS = (
    "run_count", "completed_run_count", "failed_run_count", "request_count",
    "snapshot_count", "snapshot_logical_bytes", "heartbeat_count",
)
_RUNTIME_TIMESTAMP_FIELDS = (
    "first_run_at", "last_run_at", "first_snapshot_at", "last_snapshot_at",
    "last_heartbeat_at", "last_message_at",
)
_V2_RUNTIME_BOUNDARY_PAIRS = (
    ("current_latest_run_at", "candidate_latest_run_at", "last_run_at"),
    ("current_latest_snapshot_at", "candidate_latest_snapshot_at", "last_snapshot_at"),
    ("current_latest_heartbeat_at", "candidate_latest_heartbeat_at", "last_heartbeat_at"),
    ("current_latest_message_at", "candidate_latest_message_at", "last_message_at"),
)
_V2_CANONICAL_PROVIDERS = ("boltodds", "propline", "the_odds", "therundown")
_V2_TOP_LEVEL_FIELDS = (
    "audit_version", "audit_generated_at", "as_of_date", "timezone",
    "candidate_scope", "protected_scope", "execution", "coverage",
    "source_anomalies", "candidate_runtime", "runtime_boundary",
    "season_evidence", "pins", "complete", "retention_execution_closed",
    "deletion_approved",
)
_V2_CANDIDATE_SCOPE_FIELDS = (
    "start_date", "end_date", "raw_retention_days", "providers",
)
_V2_PROTECTED_SCOPE_FIELDS = ("start_date", "reason")
_V2_EXECUTION_FIELDS = (
    "query_contract_sha256", "query_contract_version", "runner_version",
    "cli_version", "chunk_ladder_days", "soft_elapsed_seconds",
    "cooldown_seconds", "max_chunk_days", "default_max_chunks",
    "hard_max_chunks", "expected_chunk_ranges", "completed_chunk_ranges",
    "complete",
)
_V2_RANGE_FIELDS = ("provider", "start_date", "end_date")
_V2_COVERAGE_FIELDS = (
    "slate_date", "provider", *_COVERAGE_INTEGER_FIELDS,
    "first_raw_seen_at", "last_raw_seen_at", "coverage_exact",
)
_V2_ANOMALY_FIELDS = ("provider", *_V2_ANOMALY_INTEGER_FIELDS)
_V2_CANDIDATE_RUNTIME_FIELDS = (
    "provider", "first_run_at", "last_run_at",
    *_RUNTIME_INTEGER_FIELDS[:4], "books_seen",
    "first_snapshot_at", "last_snapshot_at",
    *_RUNTIME_INTEGER_FIELDS[4:6], "last_heartbeat_at", "last_message_at",
    _RUNTIME_INTEGER_FIELDS[6],
)
_V2_RUNTIME_BOUNDARY_FIELDS = (
    "provider",
    *(
        field
        for current_field, candidate_field, _runtime_field
        in _V2_RUNTIME_BOUNDARY_PAIRS
        for field in (current_field, candidate_field)
    ),
    "post_boltodds_suspension",
)
_SEASON_EVIDENCE_COUNT_FIELDS = (
    "official_tracked_picks", "accepted_bets", "sent_notifications",
    "consumed_locks", "frozen_alt_v2_rows", "operator_incidents",
    "model_review_pins",
)


def load_query_envelope(
    path_or_dash: str, *, stdin: TextIO | None = None,
) -> dict[str, Any]:
    raw = (stdin or sys.stdin).read() if path_or_dash == "-" else Path(path_or_dash).read_text(encoding="utf-8")
    wrapper = json.loads(raw)
    if isinstance(wrapper, dict) and wrapper.get("audit_version") == 2:
        return wrapper
    if not isinstance(wrapper, list) or len(wrapper) != 1 or not isinstance(wrapper[0], dict):
        raise ValueError("Supabase query output must contain exactly one row")
    value = wrapper[0].get("retention_exact_coverage")
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("retention_exact_coverage must be a JSON object")
    return value


def load_json_object(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _require_exact_keys(
    value: dict[str, Any], fields: tuple[str, ...], label: str,
) -> None:
    expected = set(fields)
    missing = sorted(expected - set(value))
    if missing:
        raise ValueError(f"{label} is missing required fields: {', '.join(missing)}")
    unknown = sorted(set(value) - expected)
    if unknown:
        raise ValueError(f"{label} contains unknown fields: {', '.join(unknown)}")


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _require_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{label} must be a boolean")
    return value


def _require_nonnegative_int(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _parse_date(value: Any, label: str) -> date:
    try:
        return date.fromisoformat(_require_string(value, label))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date") from exc


def _parse_timestamp(value: Any, label: str, *, nullable: bool = False) -> datetime | None:
    if value is None and nullable:
        return None
    try:
        parsed = datetime.fromisoformat(_require_string(value, label).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed


def _phoenix_date(timestamp: datetime) -> date:
    return timestamp.astimezone(PHOENIX_TZ).date()


def _require_audit_day_timestamp(
    value: Any, label: str, as_of_date: date,
) -> datetime:
    timestamp = _parse_timestamp(value, label)
    assert timestamp is not None
    if _phoenix_date(timestamp) != as_of_date:
        raise ValueError(f"{label} is stale for requested Phoenix as-of date")
    return timestamp


def _require_provider(value: Any, label: str) -> str:
    provider = _require_string(value, label)
    if provider not in ALLOWED_PROVIDERS:
        raise ValueError(f"{label} is not an allowed provider")
    return provider


def _validate_v1_envelope(
    envelope: dict[str, Any], *, as_of: date | None = None,
) -> None:
    """Validate the original monolithic SQL envelope without changing its rules."""
    envelope = _require_mapping(envelope, "envelope")
    if type(envelope.get("audit_version")) is not int or envelope["audit_version"] != 1:
        raise ValueError("audit_version must be 1")
    if as_of is None:
        _parse_timestamp(envelope.get("audit_generated_at"), "audit_generated_at")
    else:
        _require_audit_day_timestamp(
            envelope.get("audit_generated_at"), "audit_generated_at", as_of,
        )
    if envelope.get("complete") is not True:
        raise ValueError("complete must be true")
    if envelope.get("retention_execution_closed") is not True:
        raise ValueError("retention_execution_closed must be true")
    if envelope.get("deletion_approved") is not False:
        raise ValueError("deletion_approved must be false")

    scope = _require_mapping(envelope.get("query_scope"), "query_scope")
    start_date = _parse_date(scope.get("start_date"), "query_scope.start_date")
    end_date = _parse_date(scope.get("end_date"), "query_scope.end_date")
    if start_date > end_date:
        raise ValueError("query_scope dates are reversed")
    providers = scope.get("providers")
    if not isinstance(providers, list) or not providers:
        raise ValueError("query_scope.providers must be a non-empty list")
    scope_providers = [_require_provider(provider, "query_scope.providers") for provider in providers]
    if len(set(scope_providers)) != len(scope_providers):
        raise ValueError("query_scope.providers must be unique")

    for key in ("coverage", "source_anomalies", "provider_runtime"):
        if not isinstance(envelope.get(key), list):
            raise ValueError(f"{key} must be a list")
    if not envelope["coverage"]:
        raise ValueError("coverage must not be empty")

    anomalies_by_provider: dict[str, dict[str, Any]] = {}
    for index, raw_row in enumerate(envelope["source_anomalies"]):
        row = _require_mapping(raw_row, f"source_anomalies[{index}]")
        provider = _require_provider(row.get("provider"), f"source_anomalies[{index}].provider")
        if provider in anomalies_by_provider:
            raise ValueError("source_anomalies providers must be unique")
        for field in _ANOMALY_INTEGER_FIELDS:
            _require_nonnegative_int(row.get(field), f"source_anomalies[{index}].{field}")
        anomalies_by_provider[provider] = row
    if set(anomalies_by_provider) != set(scope_providers):
        raise ValueError("source_anomalies must contain every query scope provider exactly once")

    runtime_by_provider: dict[str, dict[str, Any]] = {}
    runtime_timestamps_by_provider: dict[str, dict[str, datetime | None]] = {}
    for index, raw_row in enumerate(envelope["provider_runtime"]):
        row = _require_mapping(raw_row, f"provider_runtime[{index}]")
        provider = _require_provider(row.get("provider"), f"provider_runtime[{index}].provider")
        if provider in runtime_by_provider:
            raise ValueError("provider_runtime providers must be unique")
        for field in _RUNTIME_INTEGER_FIELDS:
            _require_nonnegative_int(row.get(field), f"provider_runtime[{index}].{field}")
        books_seen = row.get("books_seen")
        if (
            not isinstance(books_seen, list)
            or not all(isinstance(book, str) and bool(book) for book in books_seen)
            or len(set(books_seen)) != len(books_seen)
        ):
            raise ValueError(f"provider_runtime[{index}].books_seen must be a string list")
        timestamps = {
            field: _parse_timestamp(
                row.get(field), f"provider_runtime[{index}].{field}", nullable=True,
            )
            for field in _RUNTIME_TIMESTAMP_FIELDS
        }
        run_count = row["run_count"]
        if row["completed_run_count"] + row["failed_run_count"] > run_count:
            raise ValueError("provider runtime status counts exceed run_count")
        if run_count == 0:
            if timestamps["first_run_at"] is not None or timestamps["last_run_at"] is not None:
                raise ValueError("provider runtime timestamps contradict run_count")
            if row["request_count"] != 0:
                raise ValueError("provider request_count contradicts run_count")
        elif timestamps["first_run_at"] is None or timestamps["last_run_at"] is None:
            raise ValueError("provider runtime timestamps are incomplete")
        if (
            timestamps["first_run_at"] is not None
            and timestamps["last_run_at"] is not None
            and timestamps["first_run_at"] > timestamps["last_run_at"]
        ):
            raise ValueError("provider runtime timestamps are reversed")

        snapshot_count = row["snapshot_count"]
        if snapshot_count == 0:
            if (
                timestamps["first_snapshot_at"] is not None
                or timestamps["last_snapshot_at"] is not None
                or row["snapshot_logical_bytes"] != 0
            ):
                raise ValueError("provider snapshot fields contradict snapshot_count")
        elif (
            timestamps["first_snapshot_at"] is None
            or timestamps["last_snapshot_at"] is None
            or row["snapshot_logical_bytes"] < snapshot_count
        ):
            raise ValueError("provider snapshot fields are incomplete")
        if (
            timestamps["first_snapshot_at"] is not None
            and timestamps["last_snapshot_at"] is not None
            and timestamps["first_snapshot_at"] > timestamps["last_snapshot_at"]
        ):
            raise ValueError("provider snapshot timestamps are reversed")

        heartbeat_count = row["heartbeat_count"]
        if heartbeat_count == 0:
            if (
                timestamps["last_heartbeat_at"] is not None
                or timestamps["last_message_at"] is not None
            ):
                raise ValueError("provider heartbeat fields contradict heartbeat_count")
        elif timestamps["last_heartbeat_at"] is None:
            raise ValueError("provider heartbeat timestamp is incomplete")
        runtime_by_provider[provider] = row
        runtime_timestamps_by_provider[provider] = timestamps
    if set(runtime_by_provider) != set(scope_providers):
        raise ValueError("provider_runtime must contain every query scope provider exactly once")

    seen_partitions: set[tuple[str, str]] = set()
    coverage_providers: set[str] = set()
    coverage_totals_by_provider: dict[str, dict[str, Any]] = {}
    for index, raw_row in enumerate(envelope["coverage"]):
        row = _require_mapping(raw_row, f"coverage[{index}]")
        slate_date = _parse_date(row.get("slate_date"), f"coverage[{index}].slate_date")
        provider = _require_provider(row.get("provider"), f"coverage[{index}].provider")
        if provider not in scope_providers:
            raise ValueError("coverage provider is outside query scope")
        if not start_date <= slate_date <= end_date:
            raise ValueError("coverage slate_date is outside query scope")
        partition = (slate_date.isoformat(), provider)
        if partition in seen_partitions:
            raise ValueError("coverage provider/date partitions must be unique")
        seen_partitions.add(partition)
        coverage_providers.add(provider)
        for field in _COVERAGE_INTEGER_FIELDS:
            _require_nonnegative_int(row.get(field), f"coverage[{index}].{field}")
        compact_only = row["raw_group_count"] == 0
        first_seen = _parse_timestamp(
            row.get("first_raw_seen_at"), f"coverage[{index}].first_raw_seen_at",
            nullable=compact_only,
        )
        last_seen = _parse_timestamp(
            row.get("last_raw_seen_at"), f"coverage[{index}].last_raw_seen_at",
            nullable=compact_only,
        )
        if first_seen is not None and last_seen is not None and first_seen > last_seen:
            raise ValueError("coverage raw timestamps are reversed")
        if compact_only and (
            row["raw_snapshot_rows"] != 0
            or row["raw_logical_bytes"] != 0
            or first_seen is not None
            or last_seen is not None
        ):
            raise ValueError("compact-only coverage contains contradictory raw evidence")

        if row["raw_group_count"] != (
            row["exact_group_count"]
            + row["mismatched_group_count"]
            + row["missing_compact_group_count"]
        ):
            raise ValueError("raw_group_count contradicts coverage components")
        if row["compact_group_count"] != (
            row["exact_group_count"]
            + row["mismatched_group_count"]
            + row["unexpected_compact_group_count"]
        ):
            raise ValueError("compact_group_count contradicts coverage components")
        if row["raw_snapshot_rows"] < row["raw_group_count"]:
            raise ValueError("raw_snapshot_rows is smaller than raw_group_count")
        if row["raw_logical_bytes"] < row["raw_snapshot_rows"]:
            raise ValueError("raw_logical_bytes is smaller than raw_snapshot_rows")

        metric_mismatches = [row[field] for field in MISMATCH_FIELDS[3:]]
        if any(value > row["mismatched_group_count"] for value in metric_mismatches):
            raise ValueError("field mismatch count exceeds mismatched_group_count")
        if (row["mismatched_group_count"] > 0) != any(metric_mismatches):
            raise ValueError("mismatched_group_count contradicts field mismatches")

        coverage_exact = _require_bool(
            row.get("coverage_exact"), f"coverage[{index}].coverage_exact",
        )
        expected_exact = not any(
            row[field] > 0
            for field in (
                "missing_compact_group_count", "unexpected_compact_group_count",
                "duplicate_compact_group_count", "mismatched_group_count",
            )
        )
        if coverage_exact is not expected_exact:
            raise ValueError("coverage_exact contradicts coverage aggregates")

        if not compact_only:
            provider_totals = coverage_totals_by_provider.setdefault(provider, {
                "raw_snapshot_rows": 0,
                "raw_logical_bytes": 0,
                "first_raw_seen_at": first_seen,
                "last_raw_seen_at": last_seen,
            })
            provider_totals["raw_snapshot_rows"] += row["raw_snapshot_rows"]
            provider_totals["raw_logical_bytes"] += row["raw_logical_bytes"]
            provider_totals["first_raw_seen_at"] = min(
                provider_totals["first_raw_seen_at"], first_seen,
            )
            provider_totals["last_raw_seen_at"] = max(
                provider_totals["last_raw_seen_at"], last_seen,
            )

    orphaned_anomalies = {
        provider
        for provider, row in anomalies_by_provider.items()
        if provider not in coverage_providers
        and any(row[field] > 0 for field in _ANOMALY_INTEGER_FIELDS)
    }
    if orphaned_anomalies:
        raise ValueError("provider anomalies without coverage partitions are unassignable")

    for provider, anomaly_row in anomalies_by_provider.items():
        runtime_snapshot_count = runtime_by_provider[provider]["snapshot_count"]
        if any(
            anomaly_row[field] > runtime_snapshot_count
            for field in _ANOMALY_INTEGER_FIELDS
        ):
            raise ValueError("provider anomaly count exceeds provider runtime snapshots")

    for provider, totals in coverage_totals_by_provider.items():
        runtime = runtime_by_provider[provider]
        timestamps = runtime_timestamps_by_provider[provider]
        if (
            totals["raw_snapshot_rows"] > runtime["snapshot_count"]
            or totals["raw_logical_bytes"] > runtime["snapshot_logical_bytes"]
            or timestamps["first_snapshot_at"] is None
            or timestamps["last_snapshot_at"] is None
            or totals["first_raw_seen_at"] < timestamps["first_snapshot_at"]
            or totals["last_raw_seen_at"] > timestamps["last_snapshot_at"]
        ):
            raise ValueError("coverage contradicts provider runtime snapshot totals")

    for provider, anomaly_row in anomalies_by_provider.items():
        if any(anomaly_row[field] > 0 for field in _ANOMALY_INTEGER_FIELDS):
            continue
        totals = coverage_totals_by_provider.get(provider, {
            "raw_snapshot_rows": 0,
            "raw_logical_bytes": 0,
        })
        runtime = runtime_by_provider[provider]
        if (
            totals["raw_snapshot_rows"] != runtime["snapshot_count"]
            or totals["raw_logical_bytes"] != runtime["snapshot_logical_bytes"]
        ):
            raise ValueError("coverage contradicts provider runtime snapshot totals")


def _validate_v2_runtime_row(
    row: dict[str, Any], *, index: int,
) -> dict[str, datetime | None]:
    label = f"candidate_runtime[{index}]"
    for field in _RUNTIME_INTEGER_FIELDS:
        _require_nonnegative_int(row.get(field), f"{label}.{field}")
    books_seen = row.get("books_seen")
    if (
        not isinstance(books_seen, list)
        or not all(isinstance(book, str) and bool(book) for book in books_seen)
        or books_seen != sorted(set(books_seen))
    ):
        raise ValueError(f"{label}.books_seen must be a canonical string list")
    timestamps = {
        field: _parse_timestamp(row.get(field), f"{label}.{field}", nullable=True)
        for field in _RUNTIME_TIMESTAMP_FIELDS
    }
    run_count = row["run_count"]
    if row["completed_run_count"] + row["failed_run_count"] > run_count:
        raise ValueError("candidate runtime status counts exceed run_count")
    if run_count == 0:
        if (
            timestamps["first_run_at"] is not None
            or timestamps["last_run_at"] is not None
            or row["request_count"] != 0
        ):
            raise ValueError("candidate runtime run fields contradict run_count")
    elif timestamps["first_run_at"] is None or timestamps["last_run_at"] is None:
        raise ValueError("candidate runtime timestamps are incomplete")
    if (
        timestamps["first_run_at"] is not None
        and timestamps["last_run_at"] is not None
        and timestamps["first_run_at"] > timestamps["last_run_at"]
    ):
        raise ValueError("candidate runtime timestamps are reversed")

    snapshot_count = row["snapshot_count"]
    if snapshot_count == 0:
        if (
            timestamps["first_snapshot_at"] is not None
            or timestamps["last_snapshot_at"] is not None
            or row["snapshot_logical_bytes"] != 0
            or books_seen
        ):
            raise ValueError("candidate runtime snapshot fields contradict snapshot_count")
    elif (
        timestamps["first_snapshot_at"] is None
        or timestamps["last_snapshot_at"] is None
        or row["snapshot_logical_bytes"] < snapshot_count
        or run_count == 0
    ):
        raise ValueError("candidate runtime snapshot fields are incomplete")
    if (
        timestamps["first_snapshot_at"] is not None
        and timestamps["last_snapshot_at"] is not None
        and timestamps["first_snapshot_at"] > timestamps["last_snapshot_at"]
    ):
        raise ValueError("candidate runtime snapshot timestamps are reversed")

    heartbeat_count = row["heartbeat_count"]
    if heartbeat_count == 0:
        if (
            timestamps["last_heartbeat_at"] is not None
            or timestamps["last_message_at"] is not None
        ):
            raise ValueError("candidate runtime heartbeat fields contradict heartbeat_count")
    elif timestamps["last_heartbeat_at"] is None:
        raise ValueError("candidate runtime heartbeat timestamp is incomplete")
    return timestamps


def _validate_v2_execution(
    execution: dict[str, Any], *, start_date: date, end_date: date,
    providers: list[str],
) -> None:
    _require_exact_keys(execution, _V2_EXECUTION_FIELDS, "execution")
    if execution.get("complete") is not True:
        raise ValueError("execution.complete must be true")
    if execution.get("query_contract_sha256") != bounded_sql.query_contract_sha256():
        raise ValueError("execution.query_contract_sha256 is invalid")
    expected_scalars = {
        "query_contract_version": "supabase-db-query-linked-json-v1",
        "runner_version": "2",
        "chunk_ladder_days": [1, 3, 7],
        "soft_elapsed_seconds": 30.0,
        "cooldown_seconds": 30.0,
        "max_chunk_days": 7,
        "default_max_chunks": 1,
        "hard_max_chunks": 5,
    }
    for field, expected in expected_scalars.items():
        if execution.get(field) != expected:
            raise ValueError(f"execution.{field} is invalid")
    _require_string(execution.get("cli_version"), "execution.cli_version")

    expected_ranges = execution.get("expected_chunk_ranges")
    if not isinstance(expected_ranges, list):
        raise ValueError("execution.expected_chunk_ranges must be a list")
    for index, value in enumerate(expected_ranges):
        row = _require_mapping(value, f"execution.expected_chunk_ranges[{index}]")
        _require_exact_keys(
            row, _V2_RANGE_FIELDS, f"execution.expected_chunk_ranges[{index}]",
        )
    expected_value = [{
        "provider": provider,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
    } for provider in providers]
    if expected_ranges != expected_value:
        raise ValueError("execution expected chunk ranges contradict candidate scope")

    completed_ranges = execution.get("completed_chunk_ranges")
    if not isinstance(completed_ranges, list) or not completed_ranges:
        raise ValueError("execution completed chunk ranges are incomplete")
    completed_partitions: set[tuple[str, str]] = set()
    for index, value in enumerate(completed_ranges):
        row = _require_mapping(value, f"execution.completed_chunk_ranges[{index}]")
        _require_exact_keys(
            row, _V2_RANGE_FIELDS, f"execution.completed_chunk_ranges[{index}]",
        )
        provider = _require_provider(
            row.get("provider"), f"execution.completed_chunk_ranges[{index}].provider",
        )
        range_start = _parse_date(
            row.get("start_date"), f"execution.completed_chunk_ranges[{index}].start_date",
        )
        range_end = _parse_date(
            row.get("end_date"), f"execution.completed_chunk_ranges[{index}].end_date",
        )
        if (
            provider not in providers
            or range_start > range_end
            or range_start < start_date
            or range_end > end_date
            or (range_end - range_start).days + 1 > 7
        ):
            raise ValueError("execution completed chunk ranges are invalid")
        cursor = range_start
        while cursor <= range_end:
            partition = (provider, cursor.isoformat())
            if partition in completed_partitions:
                raise ValueError("execution completed chunk ranges overlap")
            completed_partitions.add(partition)
            cursor += timedelta(days=1)
    expected_partitions = {
        (provider, cursor.isoformat())
        for provider in providers
        for cursor in (
            start_date + timedelta(days=offset)
            for offset in range((end_date - start_date).days + 1)
        )
    }
    if completed_partitions != expected_partitions:
        raise ValueError("execution completed chunk ranges are incomplete")


def _validate_v2_envelope(
    envelope: dict[str, Any], *, as_of: date | None,
) -> None:
    _require_exact_keys(envelope, _V2_TOP_LEVEL_FIELDS, "envelope")
    if envelope.get("complete") is not True:
        raise ValueError("complete must be true")
    if envelope.get("retention_execution_closed") is not True:
        raise ValueError("retention_execution_closed must be true")
    if envelope.get("deletion_approved") is not False:
        raise ValueError("deletion_approved must be false")
    envelope_as_of = _parse_date(envelope.get("as_of_date"), "as_of_date")
    if as_of is not None and envelope_as_of != as_of:
        raise ValueError("as_of_date does not match requested as-of date")
    effective_as_of = as_of or envelope_as_of
    if envelope.get("timezone") != "America/Phoenix":
        raise ValueError("timezone must be America/Phoenix")
    try:
        _require_audit_day_timestamp(
            envelope.get("audit_generated_at"), "runtime boundary generated_at",
            effective_as_of,
        )
    except ValueError as exc:
        raise ValueError("runtime boundary generated_at is stale") from exc

    scope = _require_mapping(envelope.get("candidate_scope"), "candidate_scope")
    _require_exact_keys(scope, _V2_CANDIDATE_SCOPE_FIELDS, "candidate_scope")
    start_date = _parse_date(scope.get("start_date"), "candidate_scope.start_date")
    end_date = _parse_date(scope.get("end_date"), "candidate_scope.end_date")
    if start_date != date(2026, 4, 28):
        raise ValueError("candidate_scope.start_date must be 2026-04-28")
    if start_date > end_date:
        raise ValueError("candidate_scope dates are reversed")
    if scope.get("raw_retention_days") != 30:
        raise ValueError("candidate_scope.raw_retention_days must be 30")
    providers = scope.get("providers")
    if providers != list(_V2_CANONICAL_PROVIDERS):
        raise ValueError("candidate_scope.providers must match the canonical provider matrix")
    if end_date != effective_as_of - timedelta(days=30):
        raise ValueError("candidate_scope.end_date must equal as_of_date minus 30 days")

    protected = _require_mapping(envelope.get("protected_scope"), "protected_scope")
    _require_exact_keys(protected, _V2_PROTECTED_SCOPE_FIELDS, "protected_scope")
    protected_start = _parse_date(
        protected.get("start_date"), "protected_scope.start_date",
    )
    if protected_start != end_date + timedelta(days=1):
        raise ValueError("protected_scope.start_date must follow candidate cutoff")
    _require_string(protected.get("reason"), "protected_scope.reason")
    for field in ("season_evidence", "pins"):
        if envelope[field] is not None:
            raise ValueError(f"{field} must be null; supply its manifest separately")
    _validate_v2_execution(
        _require_mapping(envelope.get("execution"), "execution"),
        start_date=start_date, end_date=end_date, providers=providers,
    )

    for key in ("coverage", "source_anomalies", "candidate_runtime", "runtime_boundary"):
        if not isinstance(envelope.get(key), list):
            raise ValueError(f"{key} must be a list")

    anomalies_by_provider: dict[str, dict[str, Any]] = {}
    for index, raw_row in enumerate(envelope["source_anomalies"]):
        row = _require_mapping(raw_row, f"source_anomalies[{index}]")
        _require_exact_keys(
            row, _V2_ANOMALY_FIELDS, f"source_anomalies[{index}]",
        )
        provider = _require_provider(row.get("provider"), f"source_anomalies[{index}].provider")
        if provider in anomalies_by_provider:
            raise ValueError("source_anomalies providers must be unique")
        for field in _V2_ANOMALY_INTEGER_FIELDS:
            _require_nonnegative_int(row.get(field), f"source_anomalies[{index}].{field}")
        if row["slate_date_mismatch_rows"] != (
            row["preserved_slate_date_mismatch_rows"]
            + row["unpreserved_slate_date_mismatch_rows"]
        ):
            raise ValueError("cross-date preservation equation is inconsistent")
        anomalies_by_provider[provider] = row
    if list(anomalies_by_provider) != providers:
        raise ValueError("source_anomalies must contain the canonical provider matrix")

    runtime_by_provider: dict[str, dict[str, Any]] = {}
    runtime_timestamps: dict[str, dict[str, datetime | None]] = {}
    for index, raw_row in enumerate(envelope["candidate_runtime"]):
        row = _require_mapping(raw_row, f"candidate_runtime[{index}]")
        _require_exact_keys(
            row, _V2_CANDIDATE_RUNTIME_FIELDS, f"candidate_runtime[{index}]",
        )
        provider = _require_provider(row.get("provider"), f"candidate_runtime[{index}].provider")
        if provider in runtime_by_provider:
            raise ValueError("candidate_runtime providers must be unique")
        runtime_by_provider[provider] = row
        runtime_timestamps[provider] = _validate_v2_runtime_row(row, index=index)
    if list(runtime_by_provider) != providers:
        raise ValueError("candidate_runtime must contain the canonical provider matrix")

    expected_matrix = {
        (provider, (start_date + timedelta(days=offset)).isoformat())
        for provider in providers
        for offset in range((end_date - start_date).days + 1)
    }
    seen_matrix: set[tuple[str, str]] = set()
    totals = {
        provider: {
            "raw_snapshot_rows": 0, "raw_logical_bytes": 0,
            "first_raw_seen_at": None, "last_raw_seen_at": None,
        }
        for provider in providers
    }
    for index, raw_row in enumerate(envelope["coverage"]):
        row = _require_mapping(raw_row, f"coverage[{index}]")
        _require_exact_keys(row, _V2_COVERAGE_FIELDS, f"coverage[{index}]")
        provider = _require_provider(row.get("provider"), f"coverage[{index}].provider")
        slate_date = _parse_date(row.get("slate_date"), f"coverage[{index}].slate_date")
        partition = (provider, slate_date.isoformat())
        if partition in seen_matrix:
            raise ValueError("coverage provider/date partitions must be unique")
        seen_matrix.add(partition)
        for field in _COVERAGE_INTEGER_FIELDS:
            _require_nonnegative_int(row.get(field), f"coverage[{index}].{field}")
        zero_raw = row["raw_group_count"] == 0
        first_seen = _parse_timestamp(
            row.get("first_raw_seen_at"), f"coverage[{index}].first_raw_seen_at",
            nullable=zero_raw,
        )
        last_seen = _parse_timestamp(
            row.get("last_raw_seen_at"), f"coverage[{index}].last_raw_seen_at",
            nullable=zero_raw,
        )
        if zero_raw and (
            row["raw_snapshot_rows"] != 0
            or row["raw_logical_bytes"] != 0
            or first_seen is not None
            or last_seen is not None
        ):
            raise ValueError("zero coverage partition contains contradictory raw evidence")
        if first_seen is not None and last_seen is not None and first_seen > last_seen:
            raise ValueError("coverage raw timestamps are reversed")
        if row["raw_group_count"] != (
            row["exact_group_count"] + row["mismatched_group_count"]
            + row["missing_compact_group_count"]
        ):
            raise ValueError("raw_group_count contradicts coverage components")
        if row["compact_group_count"] != (
            row["exact_group_count"] + row["mismatched_group_count"]
            + row["unexpected_compact_group_count"]
        ):
            raise ValueError("compact_group_count contradicts coverage components")
        if (
            row["raw_snapshot_rows"] < row["raw_group_count"]
            or row["raw_logical_bytes"] < row["raw_snapshot_rows"]
        ):
            raise ValueError("coverage row/byte equations are invalid")
        metric_mismatches = [row[field] for field in MISMATCH_FIELDS[3:]]
        if any(value > row["mismatched_group_count"] for value in metric_mismatches):
            raise ValueError("field mismatch count exceeds mismatched_group_count")
        if row["mismatched_group_count"] > sum(metric_mismatches):
            raise ValueError("mismatched_group_count exceeds explained field mismatches")
        if (row["mismatched_group_count"] > 0) != any(metric_mismatches):
            raise ValueError("mismatched_group_count contradicts field mismatches")
        expected_exact = not any(
            row[field] > 0 for field in (
                "missing_compact_group_count", "unexpected_compact_group_count",
                "duplicate_compact_group_count", "mismatched_group_count",
            )
        )
        if _require_bool(row.get("coverage_exact"), f"coverage[{index}].coverage_exact") is not expected_exact:
            raise ValueError("coverage_exact contradicts coverage aggregates")
        totals[provider]["raw_snapshot_rows"] += row["raw_snapshot_rows"]
        totals[provider]["raw_logical_bytes"] += row["raw_logical_bytes"]
        if first_seen is not None:
            totals[provider]["first_raw_seen_at"] = (
                first_seen
                if totals[provider]["first_raw_seen_at"] is None
                else min(totals[provider]["first_raw_seen_at"], first_seen)
            )
            totals[provider]["last_raw_seen_at"] = (
                last_seen
                if totals[provider]["last_raw_seen_at"] is None
                else max(totals[provider]["last_raw_seen_at"], last_seen)
            )
    if seen_matrix != expected_matrix:
        raise ValueError("coverage partition matrix is incomplete")

    for provider in providers:
        runtime = runtime_by_provider[provider]
        if runtime["snapshot_count"] != totals[provider]["raw_snapshot_rows"]:
            raise ValueError("candidate runtime snapshot rows contradict coverage")
        if runtime["snapshot_logical_bytes"] != totals[provider]["raw_logical_bytes"]:
            raise ValueError("candidate runtime snapshot bytes contradict coverage")
        if (
            runtime_timestamps[provider]["first_snapshot_at"]
            != totals[provider]["first_raw_seen_at"]
            or runtime_timestamps[provider]["last_snapshot_at"]
            != totals[provider]["last_raw_seen_at"]
        ):
            raise ValueError("candidate runtime snapshot timestamps contradict coverage")
        for field in _V2_ANOMALY_INTEGER_FIELDS:
            if anomalies_by_provider[provider][field] > runtime["snapshot_count"]:
                raise ValueError("provider anomaly count exceeds candidate runtime snapshots")

    boundary_by_provider: dict[str, dict[str, Any]] = {}
    for index, raw_row in enumerate(envelope["runtime_boundary"]):
        row = _require_mapping(raw_row, f"runtime_boundary[{index}]")
        _require_exact_keys(
            row, _V2_RUNTIME_BOUNDARY_FIELDS, f"runtime_boundary[{index}]",
        )
        provider = _require_provider(row.get("provider"), f"runtime_boundary[{index}].provider")
        if provider in boundary_by_provider:
            raise ValueError("runtime_boundary provider is duplicated")
        parsed: dict[str, datetime | None] = {}
        for current_field, candidate_field, runtime_field in _V2_RUNTIME_BOUNDARY_PAIRS:
            parsed[current_field] = _parse_timestamp(
                row.get(current_field), f"runtime_boundary[{index}].{current_field}",
                nullable=True,
            )
            parsed[candidate_field] = _parse_timestamp(
                row.get(candidate_field), f"runtime_boundary[{index}].{candidate_field}",
                nullable=True,
            )
            runtime_value = runtime_timestamps[provider][runtime_field]
            if parsed[candidate_field] != runtime_value:
                raise ValueError("runtime boundary candidate maximum contradicts candidate runtime")
            if parsed[candidate_field] is not None and (
                parsed[current_field] is None
                or parsed[current_field] < parsed[candidate_field]
            ):
                raise ValueError("current runtime boundary is older than candidate maximum")
        post_suspension = _require_bool(
            row.get("post_boltodds_suspension"),
            f"runtime_boundary[{index}].post_boltodds_suspension",
        )
        expected_post_suspension = provider == "boltodds" and any(
            parsed[current_field] is not None
            and parsed[current_field] > BOLTODDS_SUSPENDED_AT
            for current_field, _candidate_field, _runtime_field
            in _V2_RUNTIME_BOUNDARY_PAIRS
        )
        if post_suspension is not expected_post_suspension:
            raise ValueError("post_boltodds_suspension contradicts current runtime boundaries")
        boundary_by_provider[provider] = row
    if list(boundary_by_provider) != providers:
        raise ValueError("runtime_boundary provider matrix is incomplete")


def validate_envelope(
    envelope: dict[str, Any], *, as_of: date | None = None,
) -> None:
    """Validate v1 or direct bounded-v2 input before decision normalization."""
    envelope = _require_mapping(envelope, "envelope")
    version = envelope.get("audit_version")
    if type(version) is not int or version not in (1, 2):
        raise ValueError("audit_version must be 1 or 2")
    if version == 1:
        _validate_v1_envelope(envelope, as_of=as_of)
    else:
        _validate_v2_envelope(envelope, as_of=as_of)


def _normalize_envelope_for_decisions(
    envelope: dict[str, Any], *, as_of: date | None,
) -> dict[str, Any]:
    validate_envelope(envelope, as_of=as_of)
    if envelope["audit_version"] == 1:
        return envelope
    normalized = {
        field: envelope[field]
        for field in _V2_TOP_LEVEL_FIELDS
    }
    normalized.update({
        "candidate_scope": {
            field: envelope["candidate_scope"][field]
            for field in _V2_CANDIDATE_SCOPE_FIELDS
        },
        "protected_scope": {
            field: envelope["protected_scope"][field]
            for field in _V2_PROTECTED_SCOPE_FIELDS
        },
        "execution": {
            field: envelope["execution"][field]
            for field in _V2_EXECUTION_FIELDS
        },
        "coverage": [
            {field: row[field] for field in _V2_COVERAGE_FIELDS}
            for row in envelope["coverage"]
        ],
        "source_anomalies": [
            {field: row[field] for field in _V2_ANOMALY_FIELDS}
            for row in envelope["source_anomalies"]
        ],
        "candidate_runtime": [
            {field: row[field] for field in _V2_CANDIDATE_RUNTIME_FIELDS}
            for row in envelope["candidate_runtime"]
        ],
        "runtime_boundary": [
            {field: row[field] for field in _V2_RUNTIME_BOUNDARY_FIELDS}
            for row in envelope["runtime_boundary"]
        ],
        "query_scope": {
            "start_date": envelope["candidate_scope"]["start_date"],
            "end_date": envelope["candidate_scope"]["end_date"],
            "providers": list(envelope["candidate_scope"]["providers"]),
        },
    })
    normalized["provider_runtime"] = normalized["candidate_runtime"]
    return normalized


def _index_season_evidence(
    season_evidence: dict[str, Any] | None, *, as_of: date,
) -> dict[str, dict[str, Any]]:
    if season_evidence is None:
        return {}
    manifest = _require_mapping(season_evidence, "season_evidence")
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ValueError("season_evidence.schema_version must be 1")
    _require_audit_day_timestamp(
        manifest.get("generated_at"), "season_evidence.generated_at", as_of,
    )
    dates = manifest.get("dates")
    if not isinstance(dates, list):
        raise ValueError("season_evidence.dates must be a list")
    indexed: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(dates):
        row = _require_mapping(value, f"season_evidence.dates[{index}]")
        slate_date = _parse_date(row.get("slate_date"), f"season_evidence.dates[{index}].slate_date").isoformat()
        if slate_date in indexed:
            raise ValueError("season_evidence dates must be unique")
        decision_linked = _require_bool(row.get("decision_linked"), f"season_evidence.dates[{index}].decision_linked")
        evidence_counts = _require_mapping(row.get("evidence_counts"), f"season_evidence.dates[{index}].evidence_counts")
        for field in _SEASON_EVIDENCE_COUNT_FIELDS:
            _require_nonnegative_int(evidence_counts.get(field), f"season_evidence.dates[{index}].evidence_counts.{field}")
        derived_decision_linked = any(
            evidence_counts[field] > 0 for field in _SEASON_EVIDENCE_COUNT_FIELDS
        )
        if derived_decision_linked and decision_linked is False:
            raise ValueError(
                "season_evidence decision_linked=false contradicts positive evidence counts"
            )
        required_evidence = row.get("required_evidence")
        if decision_linked or derived_decision_linked:
            required_evidence = _require_mapping(required_evidence, f"season_evidence.dates[{index}].required_evidence")
        if required_evidence is not None:
            required_evidence = _require_mapping(required_evidence, f"season_evidence.dates[{index}].required_evidence")
            for field in REQUIRED_DECISION_EVIDENCE:
                _require_bool(required_evidence.get(field), f"season_evidence.dates[{index}].required_evidence.{field}")
        indexed[slate_date] = row
    return indexed


def _validate_gate_c_manifest(
    gate_c: dict[str, Any] | None, *, as_of: date,
) -> dict[str, Any] | None:
    if gate_c is None:
        return None
    manifest = _require_mapping(gate_c, "gate_c")
    _require_string(manifest.get("artifact"), "gate_c.artifact")
    generated_at = _parse_timestamp(manifest.get("generated_at"), "gate_c.generated_at")
    assert generated_at is not None
    if _phoenix_date(generated_at) > as_of:
        raise ValueError("gate_c.generated_at is newer than requested as-of date")
    for field in ("jsonl_sha256", "summary_sha256"):
        digest = _require_string(manifest.get(field), f"gate_c.{field}")
        if re.fullmatch(r"[0-9A-Fa-f]{64}", digest) is None:
            raise ValueError(f"gate_c.{field} must be a SHA-256 digest")
    loaded_dates = manifest.get("loaded_slate_dates")
    if not isinstance(loaded_dates, list):
        raise ValueError("gate_c.loaded_slate_dates must be a list")
    normalized_dates = [_parse_date(value, "gate_c.loaded_slate_dates").isoformat() for value in loaded_dates]
    if len(set(normalized_dates)) != len(normalized_dates):
        raise ValueError("gate_c.loaded_slate_dates must be unique")
    source = _require_mapping(manifest.get("source"), "gate_c.source")
    source_start = _parse_date(source.get("start_date"), "gate_c.source.start_date")
    source_end = _parse_date(source.get("end_date"), "gate_c.source.end_date")
    if source_start > source_end:
        raise ValueError("gate_c source dates are reversed")
    if any(not source_start <= date.fromisoformat(value) <= source_end for value in normalized_dates):
        raise ValueError("gate_c loaded dates fall outside source coverage")
    if _phoenix_date(generated_at) < source_end:
        raise ValueError("gate_c.generated_at predates source coverage")
    reconciliation = _require_mapping(manifest.get("reconciliation"), "gate_c.reconciliation")
    for field in ("graded_pick_rows", "matched_pick_rows", "unmatched_pick_rows"):
        _require_nonnegative_int(reconciliation.get(field), f"gate_c.reconciliation.{field}")
    summary_counts = _require_mapping(manifest.get("summary_counts"), "gate_c.summary_counts")
    for field in ("rows_missing_result", "tracked_pick_rows"):
        _require_nonnegative_int(summary_counts.get(field), f"gate_c.summary_counts.{field}")
    snapshots = _require_mapping(summary_counts.get("context_snapshot_counts"), "gate_c.summary_counts.context_snapshot_counts")
    _require_nonnegative_int(snapshots.get("official_close"), "gate_c.summary_counts.context_snapshot_counts.official_close")
    return manifest


def _index_pins(
    pins: dict[str, Any] | None, *, as_of: date,
) -> dict[tuple[str, str], dict[str, Any]]:
    if pins is None:
        return {}
    manifest = _require_mapping(pins, "pins")
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ValueError("pins.schema_version must be 1")
    _require_audit_day_timestamp(manifest.get("generated_at"), "pins.generated_at", as_of)
    partitions = manifest.get("partitions")
    if not isinstance(partitions, list):
        raise ValueError("pins.partitions must be a list")
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for index, value in enumerate(partitions):
        row = _require_mapping(value, f"pins.partitions[{index}]")
        slate_date = _parse_date(row.get("slate_date"), f"pins.partitions[{index}].slate_date").isoformat()
        provider = _require_provider(row.get("provider"), f"pins.partitions[{index}].provider")
        key = (slate_date, provider)
        if key in indexed:
            raise ValueError("pin manifest partitions must be unique")
        _require_bool(row.get("reconciled"), f"pins.partitions[{index}].reconciled")
        pin_rows = row.get("pins")
        if not isinstance(pin_rows, list):
            raise ValueError(f"pins.partitions[{index}].pins must be a list")
        for pin_index, pin in enumerate(pin_rows):
            pin = _require_mapping(pin, f"pins.partitions[{index}].pins[{pin_index}]")
            _require_string(pin.get("reason"), f"pins.partitions[{index}].pins[{pin_index}].reason")
            _require_string(pin.get("status"), f"pins.partitions[{index}].pins[{pin_index}].status")
            _require_string(pin.get("preserved_artifact"), f"pins.partitions[{index}].pins[{pin_index}].preserved_artifact")
        indexed[key] = row
    return indexed


def _has_preserved_pins(
    pin_record: dict[str, Any] | None,
    season_record: dict[str, Any] | None,
) -> tuple[bool, list[str]]:
    if pin_record is None:
        return False, ["missing_pin_manifest_partition"]
    reasons: list[str] = []
    preserved_reasons: set[str] = set()
    if pin_record["reconciled"] is not True:
        reasons.append("pin_reconciliation_incomplete")
    for pin in pin_record["pins"]:
        if not isinstance(pin, dict):
            reasons.append("unpreserved_pin_evidence")
            continue
        artifact = pin.get("preserved_artifact")
        is_relative = isinstance(artifact, str) and bool(artifact.strip()) and _is_repo_relative(artifact)
        if pin.get("status") != "preserved" or not is_relative:
            reasons.append("unpreserved_pin_evidence")
        else:
            preserved_reasons.add(str(pin.get("reason")))
    evidence_counts = season_record.get("evidence_counts") if season_record else None
    if isinstance(evidence_counts, dict):
        for count_field, pin_reason in EVIDENCE_PIN_REASONS.items():
            if evidence_counts.get(count_field, 0) > 0 and pin_reason not in preserved_reasons:
                reasons.append(f"missing_preserved_pin_{pin_reason}")
    return not reasons, reasons


def _is_repo_relative(path_value: str) -> bool:
    normalized = path_value.strip().replace("\\", "/")
    return not (
        normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized) is not None
        or any(segment in {".", ".."} for segment in normalized.split("/"))
    )


def _outcome_reason_codes(
    slate_date: str,
    gate_c: dict[str, Any] | None,
    season_record: dict[str, Any] | None,
) -> list[str]:
    if gate_c is None:
        return ["missing_gate_c_manifest"]
    if season_record is None:
        return ["missing_season_evidence_date"]
    evidence_counts = season_record.get("evidence_counts")
    if not isinstance(evidence_counts, dict):
        return ["missing_required_outcome_evidence"]
    derived_decision_linked = any(
        evidence_counts.get(field, 0) > 0 for field in _SEASON_EVIDENCE_COUNT_FIELDS
    )
    if season_record["decision_linked"] is False and not derived_decision_linked:
        return []

    reasons: list[str] = []
    tracked_picks = evidence_counts.get("official_tracked_picks")
    if type(tracked_picks) is not int or tracked_picks < 0:
        return ["missing_required_outcome_evidence"]
    if tracked_picks > 0:
        loaded_dates = gate_c.get("loaded_slate_dates")
        if not isinstance(loaded_dates, list) or slate_date not in loaded_dates:
            reasons.append("gate_c_date_not_loaded")
        reconciliation = gate_c.get("reconciliation")
        if not isinstance(reconciliation, dict) or reconciliation.get("unmatched_pick_rows") != 0:
            reasons.append("gate_c_unmatched_picks")
        summary_counts = gate_c.get("summary_counts")
        if not isinstance(summary_counts, dict) or summary_counts.get("rows_missing_result") != 0:
            reasons.append("gate_c_missing_results")
    required = season_record.get("required_evidence")
    if not isinstance(required, dict):
        reasons.append("missing_required_outcome_evidence")
    else:
        applicable_fields = {
            field
            for count_field, fields in EVIDENCE_REQUIRED_FIELDS.items()
            if evidence_counts.get(count_field, 0) > 0
            for field in fields
        }
        if season_record["decision_linked"] is True and not applicable_fields:
            applicable_fields.update(REQUIRED_DECISION_EVIDENCE)
        for field in sorted(applicable_fields):
            if required.get(field) is not True:
                reasons.append(f"required_evidence_{field}_incomplete")
    return reasons


def _coverage_reason_codes(
    row: dict[str, Any], anomalies: dict[str, Any], *, audit_version: int,
) -> list[str]:
    reasons = [field for field in MISMATCH_FIELDS if row[field] > 0]
    if row["mismatched_group_count"] > 0:
        reasons.append("mismatched_group_count")
    if row["coverage_exact"] is not True:
        reasons.append("coverage_not_exact")
    anomaly_fields = (
        _V2_BLOCKING_ANOMALY_INTEGER_FIELDS
        if audit_version == 2
        else _ANOMALY_INTEGER_FIELDS
    )
    reasons.extend(field for field in anomaly_fields if anomalies[field] > 0)
    return reasons


def build_readiness_report(
    *,
    envelope: dict[str, Any],
    gate_c: dict[str, Any] | None,
    season_evidence: dict[str, Any] | None,
    pins: dict[str, Any] | None,
    as_of: str,
    raw_retention_days: int,
) -> dict[str, Any]:
    """Return evidence-only retention decisions; this function has no execution authority."""
    as_of_date = _parse_date(as_of, "as_of")
    audit_version = envelope.get("audit_version")
    envelope = _normalize_envelope_for_decisions(envelope, as_of=as_of_date)
    gate_c = _validate_gate_c_manifest(gate_c, as_of=as_of_date)
    if type(raw_retention_days) is not int or raw_retention_days <= 0:
        raise ValueError("raw_retention_days must be a positive integer")
    if (
        audit_version == 2
        and raw_retention_days != envelope["candidate_scope"]["raw_retention_days"]
    ):
        raise ValueError("raw_retention_days must match candidate_scope")
    if audit_version == 1 and envelope["query_scope"]["end_date"] != as_of_date.isoformat():
        raise ValueError("query scope is stale for requested as-of date")

    season_by_date = _index_season_evidence(season_evidence, as_of=as_of_date)
    pins_by_partition = _index_pins(pins, as_of=as_of_date)
    anomalies_by_provider = {row["provider"]: row for row in envelope["source_anomalies"]}
    post_suspension_boltodds = audit_version == 2 and next(
        row for row in envelope["runtime_boundary"]
        if row["provider"] == "boltodds"
    )["post_boltodds_suspension"] is True
    partitions: list[dict[str, Any]] = []

    for coverage in envelope["coverage"]:
        slate_date = _parse_date(coverage["slate_date"], "coverage.slate_date")
        provider = coverage["provider"]
        age_days = (as_of_date - slate_date).days
        coverage_reasons = _coverage_reason_codes(
            coverage, anomalies_by_provider[provider], audit_version=audit_version,
        )
        operational_reasons = (
            ["post_suspension_runtime_evidence"]
            if provider == "boltodds" and post_suspension_boltodds
            else []
        )
        outcome_reasons = _outcome_reason_codes(coverage["slate_date"], gate_c, season_by_date.get(coverage["slate_date"]))
        season_record = season_by_date.get(coverage["slate_date"])
        _, pin_reasons = _has_preserved_pins(
            pins_by_partition.get((coverage["slate_date"], provider)), season_record,
        )
        all_reasons = coverage_reasons + operational_reasons + outcome_reasons + pin_reasons
        record = {
            "slate_date": coverage["slate_date"],
            "provider": provider,
            "age_days": age_days,
            "raw_snapshot_rows": coverage["raw_snapshot_rows"],
            "raw_logical_bytes": coverage["raw_logical_bytes"],
            "raw_group_count": coverage["raw_group_count"],
            "exact_group_count": coverage["exact_group_count"],
            "missing_compact_group_count": coverage["missing_compact_group_count"],
            "mismatched_group_count": coverage["mismatched_group_count"],
        }
        if age_days < raw_retention_days:
            record["decision"] = "not_in_policy_window"
            record["deferred_reason_codes"] = all_reasons
        elif coverage_reasons or operational_reasons:
            record["decision"] = "blocked_compaction"
            record["reason_codes"] = all_reasons
        elif outcome_reasons:
            record["decision"] = "blocked_outcome_evidence"
            record["reason_codes"] = all_reasons
        elif pin_reasons:
            record["decision"] = "blocked_pinned_evidence"
            record["reason_codes"] = all_reasons
        else:
            record["decision"] = "ready_for_retention_review"
            record["reason_codes"] = []
        partitions.append(record)

    partitions.sort(key=lambda row: (row["slate_date"], row["provider"]))
    decision_counts: dict[str, int] = {}
    for partition in partitions:
        decision = partition["decision"]
        decision_counts[decision] = decision_counts.get(decision, 0) + 1

    gate_c_summary = gate_c if isinstance(gate_c, dict) else {}
    report = {
        "report_type": "season_retention_readiness",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of_date.isoformat(),
        "raw_retention_days": raw_retention_days,
        "source_date_range": {
            "start_date": envelope["query_scope"]["start_date"],
            "end_date": envelope["query_scope"]["end_date"],
        },
        "gate_c": {
            "jsonl_sha256": gate_c_summary.get("jsonl_sha256"),
            "summary_sha256": gate_c_summary.get("summary_sha256"),
            "loaded_slate_dates": gate_c_summary.get("loaded_slate_dates", []),
        },
        "retention_execution_closed": True,
        "deletion_approved": False,
        "production_authority": "none",
        "summary": {"decision_counts": decision_counts},
        "partitions": partitions,
        "provider_summaries": _provider_summaries(partitions, raw_retention_days),
    }
    if audit_version == 2:
        report["source_anomalies"] = [
            {field: row[field] for field in _V2_ANOMALY_FIELDS}
            for row in envelope["source_anomalies"]
        ]
    return report


def _provider_summaries(
    partitions: list[dict[str, Any]], raw_retention_days: int,
) -> list[dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for partition in partitions:
        if partition["age_days"] < raw_retention_days:
            continue
        summary = summaries.setdefault(partition["provider"], {
            "provider": partition["provider"], "partition_count": 0,
            "raw_snapshot_rows": 0, "raw_logical_bytes": 0, "raw_group_count": 0,
            "exact_group_count": 0, "missing_compact_group_count": 0,
            "mismatched_group_count": 0, "decision_counts": {},
        })
        summary["partition_count"] += 1
        for field in (
            "raw_snapshot_rows", "raw_logical_bytes", "raw_group_count",
            "exact_group_count", "missing_compact_group_count", "mismatched_group_count",
        ):
            summary[field] += partition[field]
        decision = partition["decision"]
        summary["decision_counts"][decision] = summary["decision_counts"].get(decision, 0) + 1
    return [summaries[provider] for provider in sorted(summaries)]


def _boltodds_preservation_summaries(
    *,
    coverage_rows: list[dict[str, Any]],
    gate_c: dict[str, Any] | None,
    season_by_date: dict[str, dict[str, Any]],
    pins_by_partition: dict[tuple[str, str], dict[str, Any]],
) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    decision_counts = {field: 0 for field in _SEASON_EVIDENCE_COUNT_FIELDS}
    outcome_summary = {
        "coverage_dates": len(coverage_rows),
        "manifest_dates": 0,
        "decision_linked_dates": 0,
        "complete_dates": 0,
        "incomplete_dates": 0,
    }
    pin_summary = {
        "coverage_partitions": len(coverage_rows),
        "manifest_partitions": 0,
        "reconciled_partitions": 0,
        "preserved_pin_count": 0,
        "unpreserved_pin_count": 0,
        "missing_required_reason_count": 0,
    }
    for row in coverage_rows:
        slate_date = row["slate_date"]
        season_record = season_by_date.get(slate_date)
        if season_record is not None:
            outcome_summary["manifest_dates"] += 1
            evidence_counts = season_record["evidence_counts"]
            for field in _SEASON_EVIDENCE_COUNT_FIELDS:
                decision_counts[field] += evidence_counts[field]
            if season_record["decision_linked"] or any(evidence_counts.values()):
                outcome_summary["decision_linked_dates"] += 1
        if not _outcome_reason_codes(slate_date, gate_c, season_record):
            outcome_summary["complete_dates"] += 1
        else:
            outcome_summary["incomplete_dates"] += 1

        pin_record = pins_by_partition.get((slate_date, "boltodds"))
        if pin_record is not None:
            pin_summary["manifest_partitions"] += 1
            if pin_record["reconciled"] is True:
                pin_summary["reconciled_partitions"] += 1
            for pin in pin_record["pins"]:
                artifact = pin.get("preserved_artifact")
                if (
                    pin.get("status") == "preserved"
                    and isinstance(artifact, str)
                    and _is_repo_relative(artifact)
                ):
                    pin_summary["preserved_pin_count"] += 1
                else:
                    pin_summary["unpreserved_pin_count"] += 1
        _, pin_reasons = _has_preserved_pins(pin_record, season_record)
        pin_summary["missing_required_reason_count"] += sum(
            reason.startswith("missing_preserved_pin_") for reason in pin_reasons
        )
    return decision_counts, outcome_summary, pin_summary


def build_boltodds_closure(
    *,
    envelope: dict[str, Any],
    gate_c: dict[str, Any] | None,
    season_evidence: dict[str, Any] | None,
    pins: dict[str, Any] | None,
    as_of: str,
) -> dict[str, Any]:
    """Build a closed, evidence-only retirement package for BoltOdds."""
    as_of_date = _parse_date(as_of, "as_of")
    audit_version = envelope.get("audit_version")
    envelope = _normalize_envelope_for_decisions(envelope, as_of=as_of_date)
    gate_c = _validate_gate_c_manifest(gate_c, as_of=as_of_date)
    if audit_version == 1 and envelope["query_scope"]["end_date"] != as_of_date.isoformat():
        raise ValueError("query scope is stale for requested as-of date")

    boltodds_runtime = [
        row for row in envelope["provider_runtime"] if row["provider"] == "boltodds"
    ]
    if len(boltodds_runtime) != 1:
        raise ValueError("provider_runtime must contain exactly one boltodds row")
    runtime_source = boltodds_runtime[0]
    runtime = {
        field: runtime_source.get(field)
        for field in (*_RUNTIME_TIMESTAMP_FIELDS, *_RUNTIME_INTEGER_FIELDS)
    }
    runtime["books_seen"] = sorted(set(runtime_source["books_seen"]))

    coverage_rows = [
        row for row in envelope["coverage"] if row["provider"] == "boltodds"
    ]
    coverage_rows.sort(key=lambda row: row["slate_date"])
    coverage_totals = {
        field: sum(row[field] for row in coverage_rows)
        for field in _COVERAGE_INTEGER_FIELDS
    }
    partitions = [{
        "slate_date": row["slate_date"],
        "raw_snapshot_rows": row["raw_snapshot_rows"],
        "raw_logical_bytes": row["raw_logical_bytes"],
        "raw_group_count": row["raw_group_count"],
        "compact_group_count": row["compact_group_count"],
        "exact_group_count": row["exact_group_count"],
        "mismatched_group_count": row["mismatched_group_count"],
        "coverage_exact": row["coverage_exact"],
    } for row in coverage_rows]

    season_by_date = _index_season_evidence(season_evidence, as_of=as_of_date)
    pins_by_partition = _index_pins(pins, as_of=as_of_date)
    anomalies = next(
        row for row in envelope["source_anomalies"] if row["provider"] == "boltodds"
    )
    gaps: list[str] = []
    if not coverage_rows:
        gaps.append("boltodds_coverage_missing")
    if gate_c is None:
        gaps.append("gate_c_manifest_missing")
    if season_evidence is None:
        gaps.append("season_evidence_manifest_missing")
    if pins is None:
        gaps.append("pin_manifest_missing")
    if any(row["coverage_exact"] is not True for row in coverage_rows):
        gaps.append("compaction_not_exact")
    for field in MISMATCH_FIELDS:
        if coverage_totals[field] > 0:
            gaps.append(field)
    if coverage_totals["mismatched_group_count"] > 0:
        gaps.append("mismatched_group_count")
    anomaly_fields = (
        _V2_BLOCKING_ANOMALY_INTEGER_FIELDS
        if audit_version == 2
        else _ANOMALY_INTEGER_FIELDS
    )
    for field in anomaly_fields:
        if anomalies[field] > 0:
            gaps.append(field)
    for row in coverage_rows:
        gaps.extend(_outcome_reason_codes(
            row["slate_date"], gate_c, season_by_date.get(row["slate_date"]),
        ))
        _, pin_gaps = _has_preserved_pins(
            pins_by_partition.get((row["slate_date"], "boltodds")),
            season_by_date.get(row["slate_date"]),
        )
        gaps.extend(pin_gaps)

    (
        decision_impact_counts,
        outcome_preservation_summary,
        pin_preservation_summary,
    ) = _boltodds_preservation_summaries(
        coverage_rows=coverage_rows,
        gate_c=gate_c,
        season_by_date=season_by_date,
        pins_by_partition=pins_by_partition,
    )
    total_decision_impact = sum(decision_impact_counts.values())
    if season_evidence is None:
        production_impact_statement = (
            "Production decision impact is unresolved because no normalized season-evidence "
            "manifest was supplied. BoltOdds is retired and has no active production authority."
        )
    elif total_decision_impact:
        production_impact_statement = (
            f"Supplied normalized season evidence records {total_decision_impact} aggregate "
            "decision-impact rows on BoltOdds-covered dates. Date overlap does not prove "
            "BoltOdds caused a production decision; BoltOdds is retired and has no active "
            "production authority."
        )
    else:
        production_impact_statement = (
            "Supplied normalized season evidence records zero decision-impact rows on "
            "BoltOdds-covered dates. BoltOdds is retired and has no active production authority."
        )
    production_impact_evidence_basis = (
        "Aggregate normalized season-evidence counts on BoltOdds-covered dates; date overlap "
        "is not provider-causal attribution."
    )

    current_runtime_boundary = None
    if audit_version == 2:
        current_runtime_boundary = next(
            row for row in envelope["runtime_boundary"]
            if row["provider"] == "boltodds"
        )
        post_suspension_runtime = (
            current_runtime_boundary["post_boltodds_suspension"] is True
            or any(
                timestamp is not None and timestamp > BOLTODDS_SUSPENDED_AT
                for timestamp in (
                    _parse_timestamp(
                        current_runtime_boundary[field], f"boltodds.{field}",
                        nullable=True,
                    )
                    for field in (
                        "current_latest_run_at", "current_latest_snapshot_at",
                        "current_latest_heartbeat_at", "current_latest_message_at",
                    )
                )
            )
        )
    else:
        post_suspension_runtime = any(
            timestamp is not None and timestamp > BOLTODDS_SUSPENDED_AT
            for timestamp in (
                _parse_timestamp(runtime_source[field], f"boltodds.{field}", nullable=True)
                for field in ("last_snapshot_at", "last_heartbeat_at")
            )
        )
    if post_suspension_runtime:
        gaps.append("post_suspension_runtime_evidence")
    unresolved_evidence_gaps = sorted(set(gaps))
    if post_suspension_runtime:
        status = "operational_exception"
        recommendation = "investigate_accidental_reactivation"
    elif unresolved_evidence_gaps:
        status = "incomplete_evidence"
        recommendation = "complete_evidence_before_retention_review"
    else:
        status = "ready_for_retirement_review"
        recommendation = "schedule_separate_retention_review"

    report = {
        "report_type": "boltodds_retirement_closure",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of_date.isoformat(),
        "provider": "boltodds",
        "documented_suspension_at": BOLTODDS_SUSPENDED_AT.isoformat(),
        "status": status,
        "recommendation": recommendation,
        "runtime": runtime,
        "coverage_totals": coverage_totals,
        "partitions": partitions,
        "decision_impact_counts": decision_impact_counts,
        "outcome_preservation_summary": outcome_preservation_summary,
        "pin_preservation_summary": pin_preservation_summary,
        "production_impact_statement": production_impact_statement,
        "production_impact_evidence_basis": production_impact_evidence_basis,
        "unresolved_evidence_gaps": unresolved_evidence_gaps,
        "retention_execution_closed": True,
        "deletion_approved": False,
        "production_authority": "none",
        "runtime_reactivation_approved": False,
        "historical_lessons": (
            "BoltOdds evidence is research-only and cannot drive provider order, "
            "official artifacts, picks, models, notifications, locks, UI, or retention execution."
        ),
    }
    if audit_version == 2:
        report["source_anomalies"] = {
            field: anomalies[field]
            for field in _V2_ANOMALY_FIELDS
            if field != "provider"
        }
    if current_runtime_boundary is not None:
        report["current_runtime_boundary"] = {
            field: current_runtime_boundary[field]
            for field in _V2_RUNTIME_BOUNDARY_FIELDS
        }
    return report


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: redact_sensitive(child)
            for key, child in value.items()
            if not SECRET_KEY.search(str(key))
        }
    if isinstance(value, list):
        return [redact_sensitive(child) for child in value]
    return value


def render_boltodds_markdown(report: dict[str, Any]) -> str:
    runtime = report["runtime"]
    totals = report["coverage_totals"]
    lines = [
        "# BoltOdds Retirement Closure",
        "",
        "**Deletion status: CLOSED**",
        "",
        "This package does not authorize BoltOdds runtime reactivation.",
        "",
        f"- Status: `{report['status']}`",
        f"- Documented suspension: `{report['documented_suspension_at']}`",
        f"- Last heartbeat: `{runtime.get('last_heartbeat_at')}`",
        f"- Last snapshot: `{runtime.get('last_snapshot_at')}`",
        f"- Books observed: `{', '.join(runtime.get('books_seen', [])) or 'none'}`",
        f"- Raw rows / logical bytes: `{totals['raw_snapshot_rows']} / {totals['raw_logical_bytes']}`",
        f"- Exact / raw groups: `{totals['exact_group_count']} / {totals['raw_group_count']}`",
        f"- Missing / mismatched groups: `{totals['missing_compact_group_count']} / {totals['mismatched_group_count']}`",
        *(
            [f"- Source anomalies: `{json.dumps(report['source_anomalies'], sort_keys=True)}`"]
            if "source_anomalies" in report
            else []
        ),
        f"- Decision-impact counts: `{json.dumps(report['decision_impact_counts'], sort_keys=True)}`",
        f"- Outcome preservation summary: `{json.dumps(report['outcome_preservation_summary'], sort_keys=True)}`",
        f"- Pin preservation summary: `{json.dumps(report['pin_preservation_summary'], sort_keys=True)}`",
        f"- Production-impact statement: {report['production_impact_statement']}",
        f"- Evidence basis: {report['production_impact_evidence_basis']}",
        f"- Unresolved gaps: `{', '.join(report['unresolved_evidence_gaps']) or 'none'}`",
        f"- Recommendation: `{report['recommendation']}`",
        "",
        "BoltOdds remains historical research evidence only and has no production authority.",
    ]
    return "\n".join(lines)


def render_readiness_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]["decision_counts"]
    source_range = report["source_date_range"]
    gate_c = report["gate_c"]
    loaded_dates = gate_c["loaded_slate_dates"]
    gate_c_dates = (
        f"{min(loaded_dates)} through {max(loaded_dates)}"
        if loaded_dates else "none"
    )
    lines = [
        "# Season Retention Readiness",
        "",
        "**Deletion status: CLOSED**",
        "",
        f"- Retention execution closed: `{str(report['retention_execution_closed']).lower()}`",
        f"- Production authority: `{report['production_authority']}`",
        f"- Generated: `{report['generated_at']}`",
        f"- As of: `{report['as_of']}`",
        f"- Source date range: `{source_range['start_date']} through {source_range['end_date']}`",
        f"- Gate C loaded dates: `{gate_c_dates}`",
        f"- Gate C JSONL SHA-256: `{gate_c['jsonl_sha256']}`",
        f"- Gate C summary SHA-256: `{gate_c['summary_sha256']}`",
        f"- Raw retention candidate window: `{report['raw_retention_days']} days`",
        f"- Decision counts: `{json.dumps(summary, sort_keys=True)}`",
        "",
        "| Slate | Provider | Raw rows | Raw MB | Exact / Raw groups | Missing | Mismatched | Decision | Reasons |",
        "|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in report["partitions"]:
        lines.append(
            "| {slate_date} | {provider} | {raw_snapshot_rows} | {raw_mb:.2f} | "
            "{exact_group_count} / {raw_group_count} | {missing_compact_group_count} | "
            "{mismatched_group_count} | {decision} | {reasons} |".format(
                **row,
                raw_mb=row["raw_logical_bytes"] / 1024 / 1024,
                reasons=", ".join(
                    row.get("reason_codes") or row.get("deferred_reason_codes", ())
                ) or "none",
            )
        )
    lines.extend([
        "",
        "`ready_for_retention_review` is evidence status only and does not authorize deletion.",
    ])
    return "\n".join(lines)


def write_report_pair(
    *, report: dict[str, Any], output_dir: Path, stem: str,
    renderer: Callable[[dict[str, Any]], str] = render_readiness_markdown,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    clean = redact_sensitive(report)
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(
        json.dumps(clean, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(renderer(clean).rstrip() + "\n", encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build closed season-retention evidence reports.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for command in ("readiness", "boltodds-closure"):
        subparser = subcommands.add_parser(command)
        subparser.add_argument("--query-json", required=True)
        subparser.add_argument("--gate-c-manifest", default=DEFAULT_GATE_C_MANIFEST)
        subparser.add_argument("--season-evidence")
        subparser.add_argument("--pins")
        subparser.add_argument("--as-of", required=True)
        subparser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
        if command == "readiness":
            subparser.add_argument("--raw-retention-days", type=int, default=30)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        try:
            args = parse_args(argv)
        except SystemExit as exc:
            return 0 if exc.code == 0 else 3
        envelope = load_query_envelope(args.query_json)
        gate_c = load_json_object(Path(args.gate_c_manifest))
        season_evidence = load_json_object(Path(args.season_evidence)) if args.season_evidence else None
        pins = load_json_object(Path(args.pins)) if args.pins else None
        if args.command == "readiness":
            report = build_readiness_report(
                envelope=envelope, gate_c=gate_c, season_evidence=season_evidence, pins=pins,
                as_of=args.as_of, raw_retention_days=args.raw_retention_days,
            )
            paths = write_report_pair(
                report=report, output_dir=Path(args.output_dir), stem="season_retention_readiness",
            )
        else:
            report = build_boltodds_closure(
                envelope=envelope, gate_c=gate_c, season_evidence=season_evidence,
                pins=pins, as_of=args.as_of,
            )
            paths = write_report_pair(
                report=report, output_dir=Path(args.output_dir),
                stem="boltodds_retirement_closure", renderer=render_boltodds_markdown,
            )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"retention_audit_error: {exc}", file=sys.stderr)
        return 3

    print(f"json={paths['json']}")
    print(f"markdown={paths['markdown']}")
    if args.command == "readiness":
        print(f"decision_counts={json.dumps(report['summary']['decision_counts'], sort_keys=True)}")
        if any(row["decision"].startswith("blocked_") for row in report["partitions"]):
            return 2
        return 0
    print(f"status={report['status']}")
    return 0 if report["status"] == "ready_for_retirement_review" else 2


if __name__ == "__main__":
    raise SystemExit(main())
