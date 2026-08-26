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


def run_finalizer(
    *,
    writer: SupabaseMarketWriter,
    execute: bool = False,
    allow_execute: bool = False,
    now_utc: datetime | None = None,
    monotonic_fn: Callable[[], float] = time.monotonic,
    deadline_seconds: float = DEFAULT_DEADLINE_SECONDS,
) -> dict[str, Any]:
    """Preview or fail closed before any daily compact writes are installed."""
    if execute and not allow_execute:
        raise ValueError("daily active-provider compaction write gate is closed")
    if execute:
        raise ValueError(
            "execute mode is disabled until the compact-only executor is installed"
        )
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
    for provider in ACTIVE_PROVIDERS:
        try:
            check_deadline()
            report, _ = build_partition_preview(
                provider=provider,
                slate_date=target_slate_date,
                writer=bounded_writer,
            )
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
