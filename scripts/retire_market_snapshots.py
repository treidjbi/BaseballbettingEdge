"""Dry-run-first retention guardrails for raw market_snapshots rows."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402


TRUTHY = {"1", "true", "yes", "on"}
GROUP_PAGE_SIZE = 1000
GROUP_MAX_PAGES = 20
RUN_LOOKUP_CHUNK_SIZE = 100


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _delete_allowed() -> bool:
    return os.environ.get("ALLOW_MARKET_SNAPSHOT_DELETE", "").strip().lower() in TRUTHY


def cutoff_iso_from_days(older_than_days: int, *, now: datetime | None = None) -> str:
    if older_than_days <= 0:
        raise ValueError("--older-than-days must be greater than 0")
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    cutoff = current.astimezone(timezone.utc) - timedelta(days=older_than_days)
    return cutoff.isoformat()


def _affected_snapshot_groups(
    writer: SupabaseMarketWriter,
    cutoff_iso: str,
) -> tuple[list[dict[str, str]], bool]:
    raw_groups_by_run_id: dict[str, set[tuple[str, str, str, str, str, str]]] = {}
    uncertain = False
    for page in range(GROUP_MAX_PAGES):
        rows = writer.select_rows(
            "market_snapshots",
            {
                "observed_at": f"lt.{cutoff_iso}",
                "select": "run_id,provider,bookmaker_key,normalized_player_name,market_key,side,line",
                "order": "observed_at.asc",
                "limit": str(GROUP_PAGE_SIZE),
                "offset": str(page * GROUP_PAGE_SIZE),
            },
        )
        for row in rows:
            run_id = str(row.get("run_id") or "").strip()
            group = _raw_snapshot_group_key(row)
            if not run_id or group is None:
                uncertain = True
                continue
            raw_groups_by_run_id.setdefault(run_id, set()).add(group)
        if len(rows) < GROUP_PAGE_SIZE:
            break
    else:
        uncertain = True

    groups: dict[tuple[str, str, str, str, str, str, str], dict[str, str]] = {}
    run_rows_by_id = _fetch_run_rows_by_id(writer, sorted(raw_groups_by_run_id))
    missing_run_ids = set(raw_groups_by_run_id) - set(run_rows_by_id)
    if missing_run_ids:
        uncertain = True

    for run_id, raw_groups in raw_groups_by_run_id.items():
        run_row = run_rows_by_id.get(run_id)
        slate_date = str((run_row or {}).get("slate_date") or "").strip()
        if not slate_date:
            uncertain = True
            continue
        for raw_group in raw_groups:
            provider, book_key, normalized_player, market_key, side, line = raw_group
            groups.setdefault(
                (slate_date, provider, book_key, normalized_player, market_key, side, line),
                {
                    "slate_date": slate_date,
                    "provider": provider,
                    "book_key": book_key,
                    "normalized_player_name": normalized_player,
                    "market_key": market_key,
                    "side": side,
                    "line": line,
                },
            )

    return sorted(
        groups.values(),
        key=lambda row: (
            row["slate_date"],
            row["provider"],
            row["book_key"],
            row["normalized_player_name"],
            row["market_key"],
            row["side"],
            row["line"],
        ),
    ), uncertain


def _raw_snapshot_group_key(row: dict[str, Any]) -> tuple[str, str, str, str, str, str] | None:
    provider = str(row.get("provider") or "").strip().lower()
    book_key = str(row.get("book_key") or row.get("bookmaker_key") or "").strip().lower()
    normalized_player = str(row.get("normalized_player_name") or "").strip()
    market_key = str(row.get("market_key") or "").strip()
    side = str(row.get("side") or "").strip().lower()
    line = _line_key(row.get("line"))
    if not all([provider, book_key, normalized_player, market_key, side, line]):
        return None
    return provider, book_key, normalized_player, market_key, side, line


def _line_key(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _fetch_run_rows_by_id(
    writer: SupabaseMarketWriter,
    run_ids: list[str],
) -> dict[str, dict[str, Any]]:
    rows_by_id: dict[str, dict[str, Any]] = {}
    for start in range(0, len(run_ids), RUN_LOOKUP_CHUNK_SIZE):
        chunk = run_ids[start:start + RUN_LOOKUP_CHUNK_SIZE]
        if not chunk:
            continue
        rows = writer.select_rows(
            "market_provider_runs",
            {
                "id": f"in.({','.join(chunk)})",
                "select": "id,slate_date,provider",
                "limit": str(len(chunk)),
            },
        )
        for row in rows:
            run_id = str(row.get("id") or "").strip()
            if run_id:
                rows_by_id[run_id] = row
    return rows_by_id


def _compact_covers_group(
    writer: SupabaseMarketWriter,
    *,
    group: dict[str, str],
    cutoff_iso: str,
) -> bool:
    rows = writer.select_rows(
        "compact_market_line_movements",
        {
            "slate_date": f"eq.{group['slate_date']}",
            "provider": f"eq.{group['provider']}",
            "book_key": f"eq.{group['book_key']}",
            "normalized_player_name": f"eq.{group['normalized_player_name']}",
            "market_key": f"eq.{group['market_key']}",
            "side": f"eq.{group['side']}",
            "line": f"eq.{group['line']}",
            "last_seen_at": f"lte.{cutoff_iso}",
            "select": "slate_date,provider,book_key,normalized_player_name,market_key,side,line,last_seen_at",
            "limit": "1",
        },
    )
    return bool(rows)


def run(*, writer: SupabaseMarketWriter, cutoff_iso: str, execute: bool) -> dict[str, Any]:
    snapshot_params = {"observed_at": f"lt.{cutoff_iso}"}
    compact_params = {"last_seen_at": f"lte.{cutoff_iso}"}
    snapshot_count = writer.count_rows("market_snapshots", snapshot_params)
    compact_count = writer.count_rows("compact_market_line_movements", compact_params)
    snapshot_groups: list[dict[str, str]] = []
    uncovered_groups: list[dict[str, str]] = []
    coverage_uncertain = False
    if snapshot_count > 0:
        snapshot_groups, coverage_uncertain = _affected_snapshot_groups(writer, cutoff_iso)
        if not snapshot_groups:
            coverage_uncertain = True
        for group in snapshot_groups:
            if not _compact_covers_group(
                writer,
                group=group,
                cutoff_iso=cutoff_iso,
            ):
                uncovered_groups.append(group)

    eligible = (
        snapshot_count > 0
        and compact_count > 0
        and bool(snapshot_groups)
        and not uncovered_groups
        and not coverage_uncertain
    )
    deleted = 0

    if execute:
        if not _delete_allowed():
            raise RuntimeError("ALLOW_MARKET_SNAPSHOT_DELETE=true is required for deletion")
        if eligible:
            deleted = writer.delete_rows("market_snapshots", snapshot_params)

    return {
        "snapshot_rows_before_cutoff": snapshot_count,
        "compact_rows_before_cutoff": compact_count,
        "affected_snapshot_groups": snapshot_groups,
        "uncovered_snapshot_groups": uncovered_groups,
        "coverage_uncertain": coverage_uncertain,
        "eligible_to_delete": eligible,
        "deleted_rows": deleted,
        "execute": execute,
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--older-than-days", required=True, type=int)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    cutoff_iso = cutoff_iso_from_days(args.older_than_days)
    writer = SupabaseMarketWriter(_env("SUPABASE_URL"), _env("SUPABASE_SERVICE_ROLE_KEY"))
    result = run(writer=writer, cutoff_iso=cutoff_iso, execute=args.execute)
    mode = "execute" if args.execute else "dry_run"
    print(
        "market_snapshot_retention "
        f"mode={mode} "
        f"cutoff={cutoff_iso} "
        f"snapshots={result['snapshot_rows_before_cutoff']} "
        f"compact_rows={result['compact_rows_before_cutoff']} "
        f"eligible={result['eligible_to_delete']} "
        f"deleted={result['deleted_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
