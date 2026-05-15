"""Build official provider-arbitrated market lines from current market lines."""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_infra.official_market_lines import (  # noqa: E402
    choose_official_lines,
    retire_missing_official_lines,
)
from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _fetch_current_lines(writer: SupabaseMarketWriter, slate_date: str) -> list[dict[str, Any]]:
    return writer.select_rows(
        "current_market_lines",
        {
            "slate_date": f"eq.{slate_date}",
            "market_key": "eq.pitcher_strikeouts",
            "order": "updated_at.desc",
            "limit": "10000",
        },
    )


def _fetch_existing_official_lines(writer: SupabaseMarketWriter, slate_date: str) -> list[dict[str, Any]]:
    return writer.select_rows(
        "official_market_lines",
        {
            "slate_date": f"eq.{slate_date}",
            "market_key": "eq.pitcher_strikeouts",
            "order": "updated_at.desc",
            "limit": "10000",
        },
    )


def _fetch_provider_heartbeats(writer: SupabaseMarketWriter, slate_date: str) -> list[dict[str, Any]]:
    return writer.select_rows(
        "market_feed_heartbeats",
        {
            "slate_date": f"eq.{slate_date}",
            "provider": "in.(boltodds)",
            "order": "observed_at.desc",
            "limit": "250",
        },
    )


def run(
    *,
    slate_date: str,
    writer: SupabaseMarketWriter,
    dry_run: bool,
    now_utc: datetime | None = None,
    stale_after_seconds: int = 900,
    allow_the_odds_emergency: bool = False,
    boltodds_draftkings_enabled: bool = False,
) -> dict[str, Any]:
    observed_now = now_utc or _now_utc()
    current_rows = _fetch_current_lines(writer, slate_date)
    provider_heartbeats = _fetch_provider_heartbeats(writer, slate_date)
    official_rows, decision_rows = choose_official_lines(
        current_lines=current_rows,
        now_utc=observed_now,
        stale_after_seconds=stale_after_seconds,
        allow_the_odds_emergency=allow_the_odds_emergency,
        boltodds_draftkings_enabled=boltodds_draftkings_enabled,
        provider_heartbeats=provider_heartbeats,
    )
    existing_official_rows = _fetch_existing_official_lines(writer, slate_date)
    retired_rows, retired_decisions = retire_missing_official_lines(
        official_rows=official_rows,
        existing_official_rows=existing_official_rows,
        now_utc=observed_now,
        stale_after_seconds=stale_after_seconds,
    )
    official_rows.extend(retired_rows)
    decision_rows.extend(retired_decisions)
    ready_rows = [row for row in official_rows if row["ready_for_pipeline"]]
    skipped_decisions = [row for row in decision_rows if row["decision"] == "skip"]

    written_official_rows: list[dict[str, Any]] = []
    written_decisions: list[dict[str, Any]] = []
    if not dry_run:
        written_official_rows = writer.upsert_rows(
            "official_market_lines",
            official_rows,
            on_conflict="slate_date,normalized_player_name,market_key",
        )
        written_decisions = writer.insert_rows("provider_arbitration_decisions", decision_rows)

    return {
        "slate_date": slate_date,
        "current_market_lines": len(current_rows),
        "provider_heartbeats": len(provider_heartbeats),
        "official_market_lines": len(official_rows),
        "ready_for_pipeline": len(ready_rows),
        "retired_missing_rows": len(retired_rows),
        "arbitration_decisions": len(decision_rows),
        "skipped_decisions": len(skipped_decisions),
        "written_official_rows": len(written_official_rows),
        "written_decisions": len(written_decisions),
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
        help="Freshness threshold for official-provider arbitration.",
    )
    parser.add_argument(
        "--allow-the-odds-emergency",
        action="store_true",
        help="Allow capped The Odds API FD/DK emergency fallback rows into arbitration.",
    )
    parser.add_argument(
        "--enable-boltodds-draftkings",
        action="store_true",
        help="Prefer fresh BoltOdds DraftKings after authenticated DK coverage is explicitly approved.",
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
        allow_the_odds_emergency=args.allow_the_odds_emergency,
        boltodds_draftkings_enabled=args.enable_boltodds_draftkings,
    )
    action = "dry_run" if args.dry_run else "upsert"
    print(
        "Official market line build "
        f"action={action} date={result['slate_date']} "
        f"current_lines={result['current_market_lines']} "
        f"official_lines={result['official_market_lines']} "
        f"ready={result['ready_for_pipeline']} "
        f"retired_missing={result['retired_missing_rows']} "
        f"decisions={result['arbitration_decisions']} "
        f"skipped={result['skipped_decisions']} "
        f"written_official={result['written_official_rows']} "
        f"written_decisions={result['written_decisions']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
