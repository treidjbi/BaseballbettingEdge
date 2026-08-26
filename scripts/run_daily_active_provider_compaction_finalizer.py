"""Preview the daily active-provider compact partition finalization."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_infra.supabase_writer import SupabaseMarketWriter
from scripts.repair_compact_market_snapshot_partition import (
    ON_CONFLICT,
    build_partition_preview,
)

PHOENIX = ZoneInfo("America/Phoenix")
ACTIVE_PROVIDERS = ("propline", "therundown")
WRITE_GATE_ENV = "ALLOW_DAILY_ACTIVE_PROVIDER_COMPACTION_WRITE"
WRITE_GATE_VALUE = "D1_ACTIVE_PROVIDERS_COMPACT_ONLY"
DEFAULT_DEADLINE_SECONDS = 480.0


class FinalizerDeadlineExceeded(RuntimeError):
    """Raised when a finalizer operation reaches its bounded deadline."""


class CliArgumentError(SystemExit):
    """Raised for invalid CLI input without writing parser details."""


class _RedactedArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliArgumentError(2)


class _DeadlineBoundWriter:
    def __init__(self, writer: SupabaseMarketWriter, check_deadline: Callable[[], None]):
        self._writer = writer
        self._check_deadline = check_deadline

    def select_rows(self, table: str, params: dict[str, str], **kwargs):
        self._check_deadline()
        return self._writer.select_rows(table, params, **kwargs)

    def upsert_rows(self, table: str, rows: list[dict], on_conflict: str, **kwargs):
        self._check_deadline()
        return self._writer.upsert_rows(table, rows, on_conflict, **kwargs)


def _target_slate_date(now_utc: datetime) -> str:
    if now_utc.tzinfo is None or now_utc.utcoffset() is None:
        raise ValueError("now_utc must be timezone-aware")
    return (now_utc.astimezone(PHOENIX).date() - timedelta(days=1)).isoformat()


PROVIDER_SUMMARY_FIELDS = (
    "provider",
    "slate_date",
    "provider_run_count",
    "heartbeat_row_count",
    "in_window_heartbeat_count",
    "out_of_window_heartbeat_count",
    "raw_snapshot_count",
    "snapshot_in_window_count",
    "snapshot_out_of_window_count",
    "first_source_observed_at",
    "last_source_observed_at",
    "rebuilt_compact_count",
    "existing_compact_count",
    "missing_compact_count",
    "mismatched_compact_count",
    "unexpected_compact_count",
    "rows_to_upsert_count",
    "evidence_blockers",
    "source_state_sha256",
    "preview_sha256",
)

SAFE_TOP_LEVEL_FIELDS = (
    "report_type",
    "mode",
    "target_slate_date",
    "status",
    "preflight_complete",
    "database_write_attempted",
    "database_write_performed",
    "provider_usage_rows_written",
    "deletion_performed",
    "retention_execution_closed",
    "deadline_exceeded",
    "elapsed_seconds",
)

SAFE_PROVIDER_FIELDS = PROVIDER_SUMMARY_FIELDS + (
    "error_type",
    "execution_status",
    "failure_reason",
    "database_write_attempted",
    "database_write_performed",
    "write_row_count",
    "write_error_type",
    "post_write_exact",
)


def _aggregate_provider_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        field: report[field]
        for field in PROVIDER_SUMMARY_FIELDS
        if field in report
    }


def _preflight_failure(
    *,
    provider: str,
    slate_date: str,
    error: Exception,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "slate_date": slate_date,
        "evidence_blockers": ["provider_preview_failed"],
        "error_type": type(error).__name__,
    }


def _failed_execution(
    *,
    provider: str,
    slate_date: str,
    reason: str,
    report: dict[str, Any] | None = None,
    error_type: str | None = None,
    attempted: bool = False,
    performed: bool | None = False,
    write_row_count: int = 0,
) -> dict[str, Any]:
    result = (
        _aggregate_provider_summary(report)
        if report is not None
        else {"provider": provider, "slate_date": slate_date}
    )
    result.update({
        "execution_status": "failed",
        "failure_reason": reason,
        "database_write_attempted": attempted,
        "database_write_performed": performed,
        "write_row_count": write_row_count,
        "post_write_exact": False,
    })
    if error_type is not None:
        result["write_error_type"] = error_type
    return result


def _execution_result(
    *,
    report: dict[str, Any],
    status: str,
    attempted: bool,
    performed: bool | None,
    write_row_count: int,
    write_error_type: str | None,
    post_write_exact: bool,
) -> dict[str, Any]:
    result = _aggregate_provider_summary(report)
    result.update({
        "execution_status": status,
        "database_write_attempted": attempted,
        "database_write_performed": performed,
        "write_row_count": write_row_count,
        "post_write_exact": post_write_exact,
    })
    if write_error_type is not None:
        result["write_error_type"] = write_error_type
    return result


def _execute_provider(
    *,
    provider: str,
    slate_date: str,
    writer: _DeadlineBoundWriter,
    preflight_report: dict[str, Any],
) -> dict[str, Any]:
    fresh_report, fresh_rows = build_partition_preview(
        provider=provider,
        slate_date=slate_date,
        writer=writer,
    )
    if fresh_report["evidence_blockers"]:
        return _failed_execution(
            provider=provider,
            slate_date=slate_date,
            reason="fresh_preflight_blocked",
            report=fresh_report,
        )
    if fresh_report["source_state_sha256"] != preflight_report["source_state_sha256"]:
        return _failed_execution(
            provider=provider,
            slate_date=slate_date,
            reason="source_state_drift",
            report=fresh_report,
        )

    if not fresh_rows:
        return {
            **_aggregate_provider_summary(fresh_report),
            "execution_status": "no_op",
            "database_write_attempted": False,
            "database_write_performed": False,
            "write_row_count": 0,
            "post_write_exact": True,
        }

    write_outcome = "confirmed"
    write_performed: bool | None = True
    write_error_type: str | None = None
    try:
        writer.upsert_rows(
            "compact_market_line_movements",
            fresh_rows,
            on_conflict=ON_CONFLICT,
            attempts=1,
            return_representation=False,
        )
    except requests.RequestException as error:
        write_outcome = "ambiguous"
        write_performed = None
        write_error_type = type(error).__name__

    try:
        post_report, _ = build_partition_preview(
            provider=provider,
            slate_date=slate_date,
            writer=writer,
        )
    except (
        FinalizerDeadlineExceeded,
        requests.RequestException,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        return _failed_execution(
            provider=provider,
            slate_date=slate_date,
            reason="post_write_check_failed",
            report=fresh_report,
            error_type=type(error).__name__,
            attempted=True,
            performed=write_performed,
            write_row_count=len(fresh_rows),
        )
    post_exact = (
        post_report["source_state_sha256"]
        == preflight_report["source_state_sha256"]
        and post_report["missing_compact_count"] == 0
        and post_report["mismatched_compact_count"] == 0
        and post_report["unexpected_compact_count"] == 0
        and not post_report["evidence_blockers"]
    )
    if write_outcome == "ambiguous" and post_exact:
        write_outcome = "confirmed_by_post_state"
    return _execution_result(
        report=post_report,
        status=write_outcome if post_exact else "failed",
        attempted=True,
        performed=write_performed,
        write_row_count=len(fresh_rows),
        write_error_type=write_error_type,
        post_write_exact=post_exact,
    )


def run_finalizer(
    *,
    writer: SupabaseMarketWriter,
    execute: bool = False,
    allow_execute: bool = False,
    now_utc: datetime | None = None,
    monotonic_fn: Callable[[], float] = time.monotonic,
    deadline_seconds: float = DEFAULT_DEADLINE_SECONDS,
) -> dict[str, Any]:
    """Preview or, when separately double-gated, finalize Phoenix D-1."""
    if execute and not allow_execute:
        raise ValueError("daily active-provider compaction write gate is closed")
    if deadline_seconds <= 0:
        raise ValueError("deadline_seconds must be positive")

    resolved_now = now_utc or datetime.now(timezone.utc)
    target_slate_date = _target_slate_date(resolved_now)
    started = monotonic_fn()

    def check_deadline() -> None:
        if monotonic_fn() - started >= deadline_seconds:
            raise FinalizerDeadlineExceeded("daily finalizer deadline exceeded")

    bounded_writer = _DeadlineBoundWriter(writer, check_deadline)
    provider_summaries: list[dict[str, Any]] = []
    preflight_reports: dict[str, dict[str, Any]] = {}
    for provider in ACTIVE_PROVIDERS:
        try:
            check_deadline()
            report, _ = build_partition_preview(
                provider=provider,
                slate_date=target_slate_date,
                writer=bounded_writer,
            )
            preflight_reports[provider] = report
            provider_summaries.append(_aggregate_provider_summary(report))
        except (
            FinalizerDeadlineExceeded,
            requests.RequestException,
            OSError,
            TypeError,
            ValueError,
        ) as error:
            provider_summaries.append(_preflight_failure(
                provider=provider,
                slate_date=target_slate_date,
                error=error,
            ))

    preflight_complete = (
        len(provider_summaries) == len(ACTIVE_PROVIDERS)
        and all(not item.get("evidence_blockers") for item in provider_summaries)
        and all("error_type" not in item for item in provider_summaries)
    )
    status = "success" if preflight_complete else "failed"

    if not execute:
        return {
            "report_type": "daily_active_provider_compaction_finalizer",
            "mode": "preview",
            "target_slate_date": target_slate_date,
            "status": status,
            "preflight_complete": preflight_complete,
            "provider_results": provider_summaries,
            "database_write_attempted": False,
            "database_write_performed": False,
            "provider_usage_rows_written": 0,
            "deletion_performed": False,
            "retention_execution_closed": True,
            "deadline_exceeded": any(
                item.get("error_type") == "FinalizerDeadlineExceeded"
                for item in provider_summaries
            ),
            "elapsed_seconds": round(monotonic_fn() - started, 3),
        }

    if not preflight_complete:
        return {
            "report_type": "daily_active_provider_compaction_finalizer",
            "mode": "execute",
            "target_slate_date": target_slate_date,
            "status": "failed",
            "preflight_complete": False,
            "provider_results": provider_summaries,
            "database_write_attempted": False,
            "database_write_performed": False,
            "provider_usage_rows_written": 0,
            "deletion_performed": False,
            "retention_execution_closed": True,
            "deadline_exceeded": any(
                item.get("error_type") == "FinalizerDeadlineExceeded"
                for item in provider_summaries
            ),
            "elapsed_seconds": round(monotonic_fn() - started, 3),
        }

    provider_results: list[dict[str, Any]] = []
    for index, provider in enumerate(ACTIVE_PROVIDERS):
        try:
            check_deadline()
            result = _execute_provider(
                provider=provider,
                slate_date=target_slate_date,
                writer=bounded_writer,
                preflight_report=preflight_reports[provider],
            )
        except (
            FinalizerDeadlineExceeded,
            requests.RequestException,
            OSError,
            TypeError,
            ValueError,
        ) as error:
            result = _failed_execution(
                provider=provider,
                slate_date=target_slate_date,
                reason="provider_execution_failed",
                error_type=type(error).__name__,
            )
        provider_results.append(result)
        if result["execution_status"] == "failed":
            for remaining in ACTIVE_PROVIDERS[index + 1:]:
                provider_results.append({
                    "provider": remaining,
                    "slate_date": target_slate_date,
                    "execution_status": "not_attempted_after_prior_failure",
                    "failure_reason": "prior_provider_failed",
                    "database_write_attempted": False,
                    "database_write_performed": False,
                    "write_row_count": 0,
                    "post_write_exact": False,
                })
            break

    successful_states = {"no_op", "confirmed", "confirmed_by_post_state"}
    status = (
        "success"
        if len(provider_results) == len(ACTIVE_PROVIDERS)
        and all(
            item["execution_status"] in successful_states
            for item in provider_results
        )
        else "failed"
    )

    attempted_results = [
        item for item in provider_results if item["database_write_attempted"]
    ]
    if any(
        item["database_write_performed"] is None
        for item in attempted_results
    ):
        top_level_write_performed: bool | None = None
    else:
        top_level_write_performed = any(
            item["database_write_performed"] is True
            for item in attempted_results
        )

    return {
        "report_type": "daily_active_provider_compaction_finalizer",
        "mode": "execute",
        "target_slate_date": target_slate_date,
        "status": status,
        "preflight_complete": True,
        "provider_results": provider_results,
        "database_write_attempted": any(
            item["database_write_attempted"] for item in provider_results
        ),
        "database_write_performed": top_level_write_performed,
        "provider_usage_rows_written": 0,
        "deletion_performed": False,
        "retention_execution_closed": True,
        "deadline_exceeded": any(
            item.get("error_type") == "FinalizerDeadlineExceeded"
            or item.get("write_error_type") == "FinalizerDeadlineExceeded"
            for item in provider_results
        ),
        "elapsed_seconds": round(monotonic_fn() - started, 3),
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = _RedactedArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _safe_summary(report: dict[str, Any]) -> dict[str, Any]:
    safe = {key: report[key] for key in SAFE_TOP_LEVEL_FIELDS if key in report}
    safe["provider_results"] = [
        {key: item[key] for key in SAFE_PROVIDER_FIELDS if key in item}
        for item in report.get("provider_results", [])
    ]
    return safe


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(argv if argv is not None else sys.argv[1:])
        allow_execute = os.environ.get(WRITE_GATE_ENV, "") == WRITE_GATE_VALUE
        if args.execute and not allow_execute:
            raise EnvironmentError("daily_active_provider_compaction_write_gate_closed")
        writer = SupabaseMarketWriter(
            _env("SUPABASE_URL"),
            _env("SUPABASE_SERVICE_ROLE_KEY"),
        )
        report = run_finalizer(
            writer=writer,
            execute=args.execute,
            allow_execute=allow_execute,
        )
        print(json.dumps(_safe_summary(report), sort_keys=True, separators=(",", ":")))
        return 0 if report["status"] == "success" else 2
    except requests.RequestException as error:
        print(
            f"daily_compaction_finalizer_request_error:{type(error).__name__}",
            file=sys.stderr,
        )
        return 2
    except FinalizerDeadlineExceeded as error:
        print(
            f"daily_compaction_finalizer_runtime_error:{type(error).__name__}",
            file=sys.stderr,
        )
        return 2
    except (EnvironmentError, OSError, TypeError, ValueError) as error:
        print(
            f"daily_compaction_finalizer_config_error:{type(error).__name__}",
            file=sys.stderr,
        )
        return 3
    except CliArgumentError:
        print("daily_compaction_finalizer_config_error:CliArgumentError", file=sys.stderr)
        return 3
    except Exception:
        print("daily_compaction_finalizer_runtime_error:UnhandledError", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
