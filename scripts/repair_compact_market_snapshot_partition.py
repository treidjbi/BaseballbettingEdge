"""Preview or explicitly repair one compact market-snapshot provider/date partition."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_infra.market_snapshot_compaction import (  # noqa: E402
    compact_snapshot_rows,
    deduplicate_snapshot_rows,
)
from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402


PROVIDERS = ("boltodds", "propline", "the_odds", "therundown")
ON_CONFLICT = (
    "slate_date,provider,book_key,normalized_player_name,market_key,side,line"
)
KEY_FIELDS = (
    "slate_date",
    "provider",
    "book_key",
    "normalized_player_name",
    "market_key",
    "side",
    "line",
)
VALUE_FIELDS = (
    "player_name",
    "first_seen_at",
    "last_seen_at",
    "first_odds",
    "last_odds",
    "min_odds",
    "max_odds",
    "odds_move_count",
    "snapshot_count",
    "source_snapshot_ids",
)
COMPACT_FIELDS = KEY_FIELDS + VALUE_FIELDS
SELECT_FIELDS = ",".join(COMPACT_FIELDS)
SNAPSHOT_SELECT_FIELDS = ",".join((
    "id",
    "run_id",
    "provider",
    "bookmaker_key",
    "player_name",
    "normalized_player_name",
    "market_key",
    "side",
    "line",
    "american_odds",
    "observed_at",
))
PAGE_SIZE = 1000
MAX_PAGES = 20
PHOENIX = ZoneInfo("America/Phoenix")
EXECUTION_PARTITION = ("boltodds", "2026-06-16")


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _validated_date(value: str) -> str:
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value:
        raise ValueError("date must use YYYY-MM-DD format")
    return value


def _validated_uuid(value: Any, *, label: str) -> str:
    text = str(value or "").strip()
    try:
        parsed = UUID(text)
    except (AttributeError, TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a UUID") from error
    return str(parsed)


def _aware_datetime(value: Any, *, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a timezone-aware timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must be a timezone-aware timestamp")
    return parsed.astimezone(timezone.utc)


def _phoenix_window(slate_date: str) -> tuple[datetime, datetime, str, str]:
    local_start = datetime.combine(date.fromisoformat(slate_date), time.min, tzinfo=PHOENIX)
    local_end = local_start + timedelta(days=1)
    start = local_start.astimezone(timezone.utc)
    end = local_end.astimezone(timezone.utc)
    return (
        start,
        end,
        start.isoformat().replace("+00:00", "Z"),
        end.isoformat().replace("+00:00", "Z"),
    )


def _select_rows(
    writer: SupabaseMarketWriter,
    table: str,
    params: dict[str, str],
) -> list[dict[str, Any]]:
    return writer.select_rows(table, params, attempts=1)


def _fetch_provider_runs(
    writer: SupabaseMarketWriter,
    *,
    provider: str,
    slate_date: str,
) -> list[dict[str, Any]]:
    run_rows = _select_rows(
        writer,
        "market_provider_runs",
        {
            "slate_date": f"eq.{slate_date}",
            "provider": f"eq.{provider}",
            "order": "created_at.asc,id.asc",
            "limit": str(PAGE_SIZE),
        },
    )
    if len(run_rows) >= PAGE_SIZE:
        raise ValueError("provider run query reached its fail-closed row ceiling")

    rows_by_id: dict[str, dict[str, Any]] = {}
    for raw_row in run_rows:
        row = dict(raw_row)
        run_id = _validated_uuid(row.get("id"), label="provider run id")
        if str(row.get("provider") or "").strip().lower() != provider:
            raise ValueError("provider run escaped requested partition")
        if str(row.get("slate_date") or "").strip() != slate_date:
            raise ValueError("provider run date escaped requested partition")
        row["id"] = run_id
        rows_by_id[run_id] = row

    heartbeat_rows = _select_rows(
        writer,
        "market_feed_heartbeats",
        {
            "slate_date": f"eq.{slate_date}",
            "provider": f"eq.{provider}",
            "order": "observed_at.asc,id.asc",
            "limit": str(PAGE_SIZE),
        },
    )
    if len(heartbeat_rows) >= PAGE_SIZE:
        raise ValueError("provider heartbeat query reached its fail-closed row ceiling")

    extra_id_set: set[str] = set()
    window_start, window_end, _, _ = _phoenix_window(slate_date)
    for row in heartbeat_rows:
        if (
            str(row.get("provider") or "").strip().lower() != provider
            or str(row.get("slate_date") or "").strip() != slate_date
        ):
            raise ValueError("heartbeat escaped requested partition")
        observed_at = _aware_datetime(row.get("observed_at"), label="heartbeat observed_at")
        if not window_start <= observed_at < window_end:
            raise ValueError("heartbeat escaped requested Phoenix date")
        if row.get("run_id") is None:
            continue
        run_id = _validated_uuid(row.get("run_id"), label="heartbeat run id")
        if run_id not in rows_by_id:
            extra_id_set.add(run_id)
    extra_ids = sorted(extra_id_set)
    if extra_ids:
        extra_rows = _select_rows(
            writer,
            "market_provider_runs",
            {
                "id": f"in.({','.join(extra_ids)})",
                "provider": f"eq.{provider}",
                "order": "created_at.asc,id.asc",
                "limit": str(len(extra_ids)),
            },
        )
        returned_ids = set()
        for raw_row in extra_rows:
            row = dict(raw_row)
            run_id = _validated_uuid(row.get("id"), label="heartbeat provider run id")
            if run_id not in extra_ids:
                raise ValueError("heartbeat provider run escaped requested partition")
            if str(row.get("provider") or "").strip().lower() != provider:
                raise ValueError("heartbeat provider run escaped requested provider")
            row["id"] = run_id
            rows_by_id[run_id] = row
            returned_ids.add(run_id)
        if returned_ids != set(extra_ids):
            raise ValueError("heartbeat provider run could not be resolved")

    return [rows_by_id[run_id] for run_id in sorted(rows_by_id)]


def _fetch_snapshot_rows(
    writer: SupabaseMarketWriter,
    *,
    provider: str,
    slate_date: str,
    run_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not run_rows:
        return []
    run_ids = [_validated_uuid(row["id"], label="provider run id") for row in run_rows]
    allowed_run_ids = set(run_ids)
    window_start, window_end, window_start_iso, window_end_iso = _phoenix_window(slate_date)
    rows: list[dict[str, Any]] = []
    for page in range(MAX_PAGES):
        page_rows = _select_rows(
            writer,
            "market_snapshots",
            {
                "run_id": f"in.({','.join(run_ids)})",
                "provider": f"eq.{provider}",
                "select": SNAPSHOT_SELECT_FIELDS,
                "and": (
                    f"(observed_at.gte.{window_start_iso},"
                    f"observed_at.lt.{window_end_iso})"
                ),
                "order": "observed_at.asc,id.asc",
                "limit": str(PAGE_SIZE),
                "offset": str(page * PAGE_SIZE),
            },
        )
        for raw_row in page_rows:
            row = dict(raw_row)
            row_provider = str(row.get("provider") or "").strip().lower()
            if row_provider != provider:
                raise ValueError("snapshot provider escaped requested partition")
            row_run_id = _validated_uuid(row.get("run_id"), label="snapshot run id")
            if row_run_id not in allowed_run_ids:
                raise ValueError("snapshot run escaped requested partition")
            observed_at = _aware_datetime(row.get("observed_at"), label="snapshot observed_at")
            if not window_start <= observed_at < window_end:
                raise ValueError("snapshot timestamp escaped requested Phoenix date")
            row_date = str(row.get("slate_date") or "").strip()
            if row_date and row_date != slate_date:
                raise ValueError("snapshot date escaped requested partition")
            row["run_id"] = row_run_id
            row["slate_date"] = slate_date
            rows.append(row)
        if len(page_rows) < PAGE_SIZE:
            return deduplicate_snapshot_rows(rows)
    raise ValueError("snapshot query reached its fail-closed page ceiling")


def _fetch_existing_compacts(
    writer: SupabaseMarketWriter,
    *,
    provider: str,
    slate_date: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for page in range(MAX_PAGES):
        page_rows = _select_rows(
            writer,
            "compact_market_line_movements",
            {
                "select": SELECT_FIELDS,
                "slate_date": f"eq.{slate_date}",
                "provider": f"eq.{provider}",
                "order": (
                    "book_key.asc,normalized_player_name.asc,market_key.asc,"
                    "side.asc,line.asc"
                ),
                "limit": str(PAGE_SIZE),
                "offset": str(page * PAGE_SIZE),
            },
        )
        for raw_row in page_rows:
            row = dict(raw_row)
            if str(row.get("provider") or "").strip().lower() != provider:
                raise ValueError("compact provider escaped requested partition")
            if str(row.get("slate_date") or "").strip() != slate_date:
                raise ValueError("compact date escaped requested partition")
            rows.append(row)
        if len(page_rows) < PAGE_SIZE:
            return rows
    raise ValueError("compact query reached its fail-closed page ceiling")


def _canonical_timestamp(value: Any) -> str:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("compact timestamps must be timezone-aware")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_compact(row: dict[str, Any]) -> dict[str, Any]:
    source_ids = row.get("source_snapshot_ids")
    if not isinstance(source_ids, list):
        raise ValueError("source_snapshot_ids must be an array")
    return {
        "slate_date": str(row.get("slate_date") or "").strip(),
        "provider": str(row.get("provider") or "").strip().lower(),
        "book_key": str(row.get("book_key") or "").strip().lower(),
        "normalized_player_name": str(row.get("normalized_player_name") or "").strip(),
        "market_key": str(row.get("market_key") or "").strip(),
        "side": str(row.get("side") or "").strip().lower(),
        "line": _finite_float(row.get("line"), label="line"),
        "player_name": str(row.get("player_name") or "").strip(),
        "first_seen_at": _canonical_timestamp(row.get("first_seen_at")),
        "last_seen_at": _canonical_timestamp(row.get("last_seen_at")),
        "first_odds": _optional_int(row.get("first_odds"), label="first_odds"),
        "last_odds": _optional_int(row.get("last_odds"), label="last_odds"),
        "min_odds": _optional_int(row.get("min_odds"), label="min_odds"),
        "max_odds": _optional_int(row.get("max_odds"), label="max_odds"),
        "odds_move_count": _strict_int(
            row.get("odds_move_count"), label="odds_move_count", nonnegative=True,
        ),
        "snapshot_count": _strict_int(
            row.get("snapshot_count"), label="snapshot_count", nonnegative=True,
        ),
        "source_snapshot_ids": [str(value) for value in source_ids],
    }


def _finite_float(value: Any, *, label: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a finite number") from error
    if not math.isfinite(number):
        raise ValueError(f"{label} must be a finite number")
    return number


def _strict_int(value: Any, *, label: str, nonnegative: bool = False) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be an integer") from error
    if not math.isfinite(number) or not number.is_integer():
        raise ValueError(f"{label} must be an integer")
    result = int(number)
    if nonnegative and result < 0:
        raise ValueError(f"{label} must be nonnegative")
    return result


def _optional_int(value: Any, *, label: str) -> int | None:
    return None if value is None else _strict_int(value, label=label)


def _key(row: dict[str, Any]) -> tuple[Any, ...]:
    return tuple(row[field] for field in KEY_FIELDS)


def _indexed(rows: list[dict[str, Any]], *, label: str) -> dict[tuple[Any, ...], dict[str, Any]]:
    indexed: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = _key(row)
        if key in indexed:
            raise ValueError(f"duplicate {label} compact key")
        indexed[key] = row
    return indexed


def _rows_sha256(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(
        sorted(rows, key=_key),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _compare_compacts(
    *,
    rebuilt_rows: list[dict[str, Any]],
    existing_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    canonical_rebuilt = [_canonical_compact(row) for row in rebuilt_rows]
    canonical_existing = [_canonical_compact(row) for row in existing_rows]
    rebuilt_by_key = _indexed(canonical_rebuilt, label="rebuilt")
    existing_by_key = _indexed(canonical_existing, label="existing")
    rebuilt_keys = set(rebuilt_by_key)
    existing_keys = set(existing_by_key)
    missing_keys = rebuilt_keys - existing_keys
    unexpected_keys = existing_keys - rebuilt_keys
    mismatched_keys = {
        key for key in rebuilt_keys & existing_keys
        if rebuilt_by_key[key] != existing_by_key[key]
    }
    mismatch_field_counts = {
        field: sum(
            rebuilt_by_key[key][field] != existing_by_key[key][field]
            for key in mismatched_keys
        )
        for field in VALUE_FIELDS
    }
    repair_keys = missing_keys | mismatched_keys
    canonical_rows_to_upsert = [rebuilt_by_key[key] for key in sorted(repair_keys)]
    return {
        "canonical_rebuilt": canonical_rebuilt,
        "canonical_existing": canonical_existing,
        "rows_to_upsert": canonical_rows_to_upsert,
        "missing_compact_count": len(missing_keys),
        "mismatched_compact_count": len(mismatched_keys),
        "unexpected_compact_count": len(unexpected_keys),
        "mismatch_field_counts": mismatch_field_counts,
    }


def _preview_fingerprint(report: dict[str, Any]) -> str:
    fields = {
        "fingerprint_version": 1,
        "provider": report["provider"],
        "slate_date": report["slate_date"],
        "provider_run_count": report["provider_run_count"],
        "raw_snapshot_count": report["raw_snapshot_count"],
        "rebuilt_compact_count": report["rebuilt_compact_count"],
        "existing_compact_count": report["existing_compact_count"],
        "missing_compact_count": report["missing_compact_count"],
        "mismatched_compact_count": report["mismatched_compact_count"],
        "unexpected_compact_count": report["unexpected_compact_count"],
        "rows_to_upsert_count": report["rows_to_upsert_count"],
        "mismatch_field_counts": report["mismatch_field_counts"],
        "rebuilt_compacts_sha256": report["rebuilt_compacts_sha256"],
        "existing_compacts_sha256": report["existing_compacts_sha256"],
        "blockers": report["blockers"],
    }
    payload = json.dumps(fields, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _build_preview(
    *,
    provider: str,
    slate_date: str,
    writer: SupabaseMarketWriter,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    run_rows = _fetch_provider_runs(
        writer,
        provider=provider,
        slate_date=slate_date,
    )
    snapshot_rows = _fetch_snapshot_rows(
        writer,
        provider=provider,
        slate_date=slate_date,
        run_rows=run_rows,
    )
    rebuilt_rows = compact_snapshot_rows(snapshot_rows)
    existing_rows = _fetch_existing_compacts(
        writer,
        provider=provider,
        slate_date=slate_date,
    )
    comparison = _compare_compacts(
        rebuilt_rows=rebuilt_rows,
        existing_rows=existing_rows,
    )
    blockers = []
    if not run_rows:
        blockers.append("no_provider_runs")
    if not snapshot_rows:
        blockers.append("no_raw_snapshots")
    if not rebuilt_rows:
        blockers.append("no_rebuilt_compacts")
    if comparison["unexpected_compact_count"]:
        blockers.append("unexpected_compact_rows")
    if len(snapshot_rows) >= PAGE_SIZE:
        blockers.append("snapshot_pagination_required")
    if len(existing_rows) >= PAGE_SIZE:
        blockers.append("compact_pagination_required")
    if (provider, slate_date) != EXECUTION_PARTITION:
        blockers.append("execution_partition_not_allowlisted")
    if not comparison["rows_to_upsert"]:
        blockers.append("no_changes")

    report = {
        "report_type": "compact_market_snapshot_partition_repair",
        "action": "preview",
        "provider": provider,
        "slate_date": slate_date,
        "provider_run_count": len(run_rows),
        "raw_snapshot_count": len(snapshot_rows),
        "rebuilt_compact_count": len(rebuilt_rows),
        "existing_compact_count": len(existing_rows),
        "missing_compact_count": comparison["missing_compact_count"],
        "mismatched_compact_count": comparison["mismatched_compact_count"],
        "unexpected_compact_count": comparison["unexpected_compact_count"],
        "rows_to_upsert_count": len(comparison["rows_to_upsert"]),
        "mismatch_field_counts": comparison["mismatch_field_counts"],
        "rebuilt_compacts_sha256": _rows_sha256(comparison["canonical_rebuilt"]),
        "existing_compacts_sha256": _rows_sha256(comparison["canonical_existing"]),
        "blockers": blockers,
        "execution_eligible": not blockers,
        "database_write_performed": False,
        "provider_usage_rows_written": 0,
        "deletion_approved": False,
        "retention_execution_closed": True,
    }
    report["preview_sha256"] = _preview_fingerprint(report)
    return report, comparison["rows_to_upsert"]


def run(
    *,
    provider: str,
    slate_date: str,
    writer: SupabaseMarketWriter,
    execute: bool,
    expected_preview_sha256: str | None = None,
    allow_execute: bool = False,
) -> dict[str, Any]:
    normalized_provider = str(provider).strip().lower()
    if normalized_provider not in PROVIDERS:
        raise ValueError(f"provider must be one of: {', '.join(PROVIDERS)}")
    normalized_date = _validated_date(str(slate_date).strip())
    if execute and not allow_execute:
        raise ValueError("ALLOW_COMPACT_MARKET_PARTITION_REPAIR must be true to execute")
    if execute and not expected_preview_sha256:
        raise ValueError("expected preview fingerprint is required to execute")
    if execute and (normalized_provider, normalized_date) != EXECUTION_PARTITION:
        raise ValueError("execution is limited to boltodds 2026-06-16")
    report, rows_to_upsert = _build_preview(
        provider=normalized_provider,
        slate_date=normalized_date,
        writer=writer,
    )
    if not execute:
        return report

    if expected_preview_sha256 != report["preview_sha256"]:
        raise ValueError("current repair preview fingerprint does not match approval")
    if report["unexpected_compact_count"]:
        raise ValueError("unexpected compact rows block repair because deletion is not allowed")
    if not report["execution_eligible"]:
        raise ValueError(
            "repair preview is not execution eligible: " + ",".join(report["blockers"])
        )

    write_error_type: str | None = None
    try:
        written_rows = writer.upsert_rows(
            "compact_market_line_movements",
            rows_to_upsert,
            on_conflict=ON_CONFLICT,
            attempts=1,
        )
        written_count: int | None = len(written_rows)
        write_performed: bool | None = True
        write_outcome = "confirmed"
    except requests.RequestException as error:
        written_count = None
        write_performed = None
        write_outcome = "ambiguous"
        write_error_type = type(error).__name__

    execution_report = {
        **report,
        "action": "execute",
        "database_write_attempted": True,
        "database_write_performed": write_performed,
        "database_write_outcome": write_outcome,
        "written_compact_count": written_count,
        "write_error_type": write_error_type,
    }
    try:
        post_run_rows = _fetch_provider_runs(
            writer,
            provider=normalized_provider,
            slate_date=normalized_date,
        )
        post_snapshot_rows = _fetch_snapshot_rows(
            writer,
            provider=normalized_provider,
            slate_date=normalized_date,
            run_rows=post_run_rows,
        )
        post_rebuilt_rows = compact_snapshot_rows(post_snapshot_rows)
        post_rows = _fetch_existing_compacts(
            writer,
            provider=normalized_provider,
            slate_date=normalized_date,
        )
        post = _compare_compacts(rebuilt_rows=post_rebuilt_rows, existing_rows=post_rows)
        post_rebuilt_sha256 = _rows_sha256(post["canonical_rebuilt"])
        preview_still_current = post_rebuilt_sha256 == report["rebuilt_compacts_sha256"]
        post_exact = preview_still_current and not any((
            post["missing_compact_count"],
            post["mismatched_compact_count"],
            post["unexpected_compact_count"],
        ))
    except (requests.RequestException, OSError, TypeError, ValueError) as error:
        return {
            **execution_report,
            "post_write_check_completed": False,
            "post_write_exact": False,
            "post_write_error_type": type(error).__name__,
        }

    if write_outcome == "ambiguous" and post_exact:
        execution_report["database_write_outcome"] = "confirmed_by_post_state"
    return {
        **execution_report,
        "post_write_check_completed": True,
        "post_write_exact": post_exact,
        "post_write_preview_still_current": preview_still_current,
        "post_write_raw_snapshot_count": len(post_snapshot_rows),
        "post_write_missing_compact_count": post["missing_compact_count"],
        "post_write_mismatched_compact_count": post["mismatched_compact_count"],
        "post_write_unexpected_compact_count": post["unexpected_compact_count"],
        "post_write_rebuilt_compacts_sha256": post_rebuilt_sha256,
        "post_write_compacts_sha256": _rows_sha256(post["canonical_existing"]),
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=PROVIDERS, required=True)
    parser.add_argument("--date", required=True, help="One slate date in YYYY-MM-DD format.")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--expected-preview-sha256")
    return parser.parse_args(argv)


def _report_path(*, action: str, provider: str, slate_date: str, output_dir: Path) -> Path:
    return output_dir / f"{action}-{provider}-{slate_date}.json"


def _preflight_report_path(
    *,
    action: str,
    provider: str,
    slate_date: str,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = _report_path(
        action=action,
        provider=provider,
        slate_date=slate_date,
        output_dir=output_dir,
    )
    if path.exists():
        raise ValueError(f"refusing to overwrite repair evidence: {path}")
    return path


def _write_report(report: dict[str, Any], path: Path) -> Path:
    if path.exists():
        raise ValueError(f"refusing to overwrite repair evidence: {path}")
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(argv or sys.argv[1:])
        if args.execute and not args.expected_preview_sha256:
            raise ValueError("--expected-preview-sha256 is required with --execute")
        allow_execute = _enabled(os.environ.get("ALLOW_COMPACT_MARKET_PARTITION_REPAIR"))
        if args.execute and not allow_execute:
            raise ValueError("ALLOW_COMPACT_MARKET_PARTITION_REPAIR must be true to execute")
        output_path = _preflight_report_path(
            action="execute" if args.execute else "preview",
            provider=args.provider,
            slate_date=_validated_date(args.date),
            output_dir=Path(args.output_dir),
        )
        writer = SupabaseMarketWriter(
            _env("SUPABASE_URL"),
            _env("SUPABASE_SERVICE_ROLE_KEY"),
        )
        report = run(
            provider=args.provider,
            slate_date=args.date,
            writer=writer,
            execute=args.execute,
            expected_preview_sha256=args.expected_preview_sha256,
            allow_execute=allow_execute,
        )
        path = _write_report(report, output_path)
        print(
            "Compact market partition repair "
            f"action={report['action']} provider={report['provider']} "
            f"date={report['slate_date']} rows_to_upsert={report['rows_to_upsert_count']} "
            f"output={path}"
        )
        if report["action"] == "execute" and report["post_write_exact"] is not True:
            return 2
        return 0
    except requests.RequestException as error:
        print(f"supabase_request_failed: {type(error).__name__}", file=sys.stderr)
        return 3
    except (EnvironmentError, OSError, TypeError, ValueError) as error:
        print(f"compact_partition_repair_error: {error}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
