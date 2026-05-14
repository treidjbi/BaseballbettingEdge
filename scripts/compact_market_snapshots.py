"""Compact raw provider market snapshots into long-lived movement rows."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_infra.market_snapshot_compaction import compact_snapshot_rows  # noqa: E402
from market_infra.provider_usage import (  # noqa: E402
    build_provider_usage_rows,
    write_provider_usage_rows,
)
from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _run_id_filter(run_rows: list[dict[str, Any]]) -> str:
    run_ids = [str(row.get("id")) for row in run_rows if row.get("id")]
    return f"in.({','.join(run_ids)})"


def _run_id_filter_from_ids(run_ids: list[str]) -> str:
    return f"in.({','.join(run_ids)})"


def _fetch_run_rows(
    writer: SupabaseMarketWriter,
    slate_date: str,
) -> list[dict[str, Any]]:
    run_rows = writer.select_rows(
        "market_provider_runs",
        {
            "slate_date": f"eq.{slate_date}",
            "provider": "in.(boltodds,propline,the_odds,therundown)",
            "order": "created_at.desc",
            "limit": "500",
        },
    )
    return _merge_heartbeat_run_rows(writer, slate_date, run_rows)


def _merge_heartbeat_run_rows(
    writer: SupabaseMarketWriter,
    slate_date: str,
    run_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Include persistent worker runs that are linked to the slate by heartbeat."""
    rows_by_id = {
        str(row.get("id")): dict(row)
        for row in run_rows
        if row.get("id")
    }
    heartbeat_rows = writer.select_rows(
        "market_feed_heartbeats",
        {
            "slate_date": f"eq.{slate_date}",
            "provider": "in.(boltodds,propline,the_odds,therundown)",
            "order": "observed_at.desc",
            "limit": "500",
        },
    )
    heartbeat_run_ids: list[str] = []
    for row in heartbeat_rows:
        run_id = str(row.get("run_id") or "")
        if run_id and run_id not in rows_by_id and run_id not in heartbeat_run_ids:
            heartbeat_run_ids.append(run_id)

    if heartbeat_run_ids:
        extra_rows = writer.select_rows(
            "market_provider_runs",
            {
                "id": _run_id_filter_from_ids(heartbeat_run_ids),
                "order": "created_at.desc",
                "limit": str(len(heartbeat_run_ids)),
            },
        )
        for row in extra_rows:
            run_id = str(row.get("id") or "")
            if not run_id:
                continue
            normalized = dict(row)
            normalized["slate_date"] = slate_date
            rows_by_id[run_id] = normalized

    return list(rows_by_id.values())


def _fetch_snapshot_pages(
    writer: SupabaseMarketWriter,
    run_rows: list[dict[str, Any]],
    *,
    slate_date: str,
    page_size: int = 10000,
    max_pages: int = 20,
) -> list[dict[str, Any]]:
    if not run_rows:
        return []

    rows: list[dict[str, Any]] = []
    run_filter = _run_id_filter(run_rows)
    for page in range(max_pages):
        page_rows = writer.select_rows(
            "market_snapshots",
            {
                "run_id": run_filter,
                "order": "observed_at.asc",
                "limit": str(page_size),
                "offset": str(page * page_size),
            },
        )
        for row in page_rows:
            row.setdefault("slate_date", slate_date)
        rows.extend(page_rows)
        if len(page_rows) < page_size:
            break
    return rows


def run(
    *,
    slate_date: str,
    writer: SupabaseMarketWriter,
    dry_run: bool,
) -> dict[str, Any]:
    run_rows = _fetch_run_rows(writer, slate_date)
    snapshot_rows = _fetch_snapshot_pages(writer, run_rows, slate_date=slate_date)
    compact_rows = compact_snapshot_rows(snapshot_rows)
    provider_usage_rows = build_provider_usage_rows(
        run_rows=run_rows,
        snapshot_rows=snapshot_rows,
        usage_date=slate_date,
    )

    written_rows: list[dict[str, Any]] = []
    written_usage_rows: list[dict[str, Any]] = []
    if not dry_run:
        written_rows = writer.upsert_rows(
            "compact_market_line_movements",
            compact_rows,
            on_conflict="slate_date,provider,book_key,normalized_player_name,market_key,side,line",
        )
        written_usage_rows = write_provider_usage_rows(
            writer,
            provider_usage_rows,
            enforce_propline_budget=(
                os.environ.get("ENFORCE_PROPLINE_DAILY_BUDGET", "false").strip().lower()
                in {"1", "true", "yes", "on"}
            ),
        )

    return {
        "slate_date": slate_date,
        "provider_runs": len(run_rows),
        "snapshot_rows": len(snapshot_rows),
        "compact_rows": len(compact_rows),
        "provider_usage_rows": len(provider_usage_rows),
        "provider_usage_warnings": len(written_usage_rows),
        "written_rows": len(written_rows),
        "dry_run": dry_run,
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="Slate date in YYYY-MM-DD format.")
    parser.add_argument("--dry-run", action="store_true", help="Print counts without writing rows.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    writer = SupabaseMarketWriter(_env("SUPABASE_URL"), _env("SUPABASE_SERVICE_ROLE_KEY"))
    result = run(slate_date=args.date, writer=writer, dry_run=args.dry_run)
    action = "dry_run" if args.dry_run else "upsert"
    print(
        "Market snapshot compaction "
        f"action={action} date={result['slate_date']} "
        f"provider_runs={result['provider_runs']} "
        f"snapshots={result['snapshot_rows']} "
        f"compact_rows={result['compact_rows']} "
        f"provider_usage={result['provider_usage_rows']} "
        f"written={result['written_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
