"""Build current supported-book market lines from Supabase snapshots."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_infra.current_market_lines import (  # noqa: E402
    build_current_market_lines,
    build_opening_baseline_rows,
)
from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _run_id_filter(run_rows: list[dict[str, Any]]) -> str:
    run_ids = [str(row.get("id")) for row in run_rows if row.get("id")]
    return f"in.({','.join(run_ids)})"


def _fetch_inputs(
    writer: SupabaseMarketWriter,
    slate_date: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    run_rows = writer.select_rows(
        "market_provider_runs",
        {
            "slate_date": f"eq.{slate_date}",
            "provider": "in.(boltodds,propline,the_odds,therundown)",
            "order": "created_at.desc",
            "limit": "250",
        },
    )
    if not run_rows:
        return [], []

    snapshot_rows = _fetch_snapshot_pages(writer, run_rows)
    return snapshot_rows, run_rows


def _fetch_snapshot_pages(
    writer: SupabaseMarketWriter,
    run_rows: list[dict[str, Any]],
    *,
    page_size: int = 10000,
    max_pages: int = 20,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    run_filter = _run_id_filter(run_rows)
    for page in range(max_pages):
        page_rows = writer.select_rows(
            "market_snapshots",
            {
                "run_id": run_filter,
                "order": "observed_at.desc",
                "limit": str(page_size),
                "offset": str(page * page_size),
            },
        )
        rows.extend(page_rows)
        if len(page_rows) < page_size:
            break
    return rows


def run(
    *,
    slate_date: str,
    writer: SupabaseMarketWriter,
    dry_run: bool,
    now_utc: datetime | None = None,
    stale_after_seconds: int = 900,
) -> dict[str, Any]:
    snapshot_rows, run_rows = _fetch_inputs(writer, slate_date)
    current_rows = build_current_market_lines(
        snapshot_rows=snapshot_rows,
        run_rows=run_rows,
        now_utc=now_utc or _now_utc(),
        stale_after_seconds=stale_after_seconds,
    )
    complete_rows = [row for row in current_rows if row["is_complete"]]
    stale_rows = [row for row in current_rows if "stale" in row["quality_flags"]]
    baseline_rows = build_opening_baseline_rows(current_rows)

    written_rows: list[dict[str, Any]] = []
    written_baselines: list[dict[str, Any]] = []
    if not dry_run:
        written_rows = writer.upsert_rows(
            "current_market_lines",
            current_rows,
            on_conflict="slate_date,provider,book_key,normalized_player_name,market_key,line",
        )
        written_baselines = writer.insert_ignore_rows(
            "market_opening_baselines",
            baseline_rows,
            on_conflict="slate_date,normalized_player_name,market_key,book_key,line",
        )

    return {
        "slate_date": slate_date,
        "snapshot_rows": len(snapshot_rows),
        "provider_runs": len(run_rows),
        "current_market_lines": len(current_rows),
        "complete_rows": len(complete_rows),
        "stale_rows": len(stale_rows),
        "opening_baselines": len(baseline_rows),
        "written_rows": len(written_rows),
        "written_baselines": len(written_baselines),
        "dry_run": dry_run,
    }


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="Slate date in YYYY-MM-DD format.")
    parser.add_argument("--dry-run", action="store_true", help="Print counts without writing rows.")
    parser.add_argument(
        "--stale-after-seconds",
        type=int,
        default=900,
        help="Freshness threshold for stale quality flags.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    writer = SupabaseMarketWriter(_env("SUPABASE_URL"), _env("SUPABASE_SERVICE_ROLE_KEY"))
    result = run(
        slate_date=args.date,
        writer=writer,
        dry_run=args.dry_run,
        stale_after_seconds=args.stale_after_seconds,
    )
    action = "dry_run" if args.dry_run else "upsert"
    print(
        "Current market line build "
        f"action={action} date={result['slate_date']} "
        f"provider_runs={result['provider_runs']} "
        f"snapshots={result['snapshot_rows']} "
        f"lines={result['current_market_lines']} "
        f"complete={result['complete_rows']} "
        f"stale={result['stale_rows']} "
        f"opening_baselines={result['opening_baselines']} "
        f"written={result['written_rows']}"
        f" written_baselines={result['written_baselines']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
