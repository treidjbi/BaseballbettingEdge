"""Read-only row-volume audit for Supabase operational/provider tables."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402


TABLES = [
    "market_snapshots",
    "market_feed_heartbeats",
    "shadow_provider_movement_events",
    "shadow_notification_candidates",
    "shadow_pipeline_runs",
    "shadow_pick_lock_observations",
    "operational_pick_locks",
    "current_market_lines",
    "official_market_lines",
    "compact_market_line_movements",
    "provider_request_usage_daily",
]


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def run(writer: SupabaseMarketWriter) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for table in TABLES:
        rows.append({
            "table": table,
            "rows": writer.count_rows(table, {}),
        })
    return rows


def main(argv: list[str] | None = None) -> int:
    del argv
    writer = SupabaseMarketWriter(_env("SUPABASE_URL"), _env("SUPABASE_SERVICE_ROLE_KEY"))
    for row in run(writer):
        print(f"row_volume table={row['table']} rows={row['rows']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
