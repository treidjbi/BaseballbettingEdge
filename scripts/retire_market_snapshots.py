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


def run(*, writer: SupabaseMarketWriter, cutoff_iso: str, execute: bool) -> dict[str, Any]:
    snapshot_params = {"observed_at": f"lt.{cutoff_iso}"}
    compact_params = {"updated_at": f"lt.{cutoff_iso}"}
    snapshot_count = writer.count_rows("market_snapshots", snapshot_params)
    compact_count = writer.count_rows("compact_market_line_movements", compact_params)
    eligible = snapshot_count > 0 and compact_count > 0
    deleted = 0

    if execute:
        if not _delete_allowed():
            raise RuntimeError("ALLOW_MARKET_SNAPSHOT_DELETE=true is required for deletion")
        if eligible:
            deleted = writer.delete_rows("market_snapshots", snapshot_params)

    return {
        "snapshot_rows_before_cutoff": snapshot_count,
        "compact_rows_before_cutoff": compact_count,
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
