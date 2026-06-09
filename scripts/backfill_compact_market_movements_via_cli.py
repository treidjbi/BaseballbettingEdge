"""Backfill compact market movement rows through the linked Supabase CLI.

This script summarizes raw market_snapshots into compact_market_line_movements.
It never deletes raw rows and defaults to dry-run mode.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import tempfile
from datetime import date


def validate_date_range(start_date: str, end_date: str) -> tuple[date, date]:
    start = date.fromisoformat(start_date)
    end = date.fromisoformat(end_date)
    if start > end:
        raise ValueError("start date must be on or before end date")
    return start, end


def _compact_ctes(start_date: str, end_date: str) -> str:
    return f"""
target_runs as (
  select id, slate_date
  from public.market_provider_runs
  where slate_date between date '{start_date}' and date '{end_date}'
    and provider in ('boltodds', 'propline', 'the_odds', 'therundown')
),
raw_rows as (
  select
    target_runs.slate_date::date as slate_date,
    lower(trim(market_snapshots.provider)) as provider,
    lower(trim(market_snapshots.bookmaker_key)) as book_key,
    trim(market_snapshots.normalized_player_name) as normalized_player_name,
    coalesce(
      nullif(trim(market_snapshots.player_name), ''),
      nullif(trim(market_snapshots.normalized_player_name), ''),
      'unknown'
    ) as player_name,
    coalesce(nullif(trim(market_snapshots.market_key), ''), 'pitcher_strikeouts') as market_key,
    lower(trim(market_snapshots.side)) as side,
    market_snapshots.line::numeric as line,
    market_snapshots.observed_at,
    market_snapshots.american_odds::integer as american_odds,
    market_snapshots.id
  from public.market_snapshots
  join target_runs
    on target_runs.id = market_snapshots.run_id
  where market_snapshots.observed_at is not null
    and nullif(trim(market_snapshots.provider), '') is not null
    and nullif(trim(market_snapshots.bookmaker_key), '') is not null
    and nullif(trim(market_snapshots.normalized_player_name), '') is not null
    and lower(trim(market_snapshots.side)) in ('over', 'under')
    and market_snapshots.line is not null
),
windowed_rows as (
  select
    raw_rows.*,
    first_value(american_odds) over (
      partition by slate_date, provider, book_key, normalized_player_name, market_key, side, line
      order by observed_at asc, id asc
      rows between unbounded preceding and unbounded following
    ) as first_odds,
    first_value(american_odds) over (
      partition by slate_date, provider, book_key, normalized_player_name, market_key, side, line
      order by observed_at desc, id desc
      rows between unbounded preceding and unbounded following
    ) as last_odds,
    lag(american_odds) over (
      partition by slate_date, provider, book_key, normalized_player_name, market_key, side, line
      order by observed_at asc, id asc
    ) as previous_odds
  from raw_rows
),
compact_rows as (
  select
    slate_date,
    provider,
    book_key,
    normalized_player_name,
    min(player_name) as player_name,
    market_key,
    side,
    line,
    min(observed_at) as first_seen_at,
    max(observed_at) as last_seen_at,
    min(first_odds) as first_odds,
    min(last_odds) as last_odds,
    min(american_odds) as min_odds,
    max(american_odds) as max_odds,
    count(*) filter (
      where previous_odds is not null
        and american_odds is not null
        and previous_odds <> american_odds
    )::integer as odds_move_count,
    count(*)::integer as snapshot_count,
    jsonb_agg(id order by observed_at asc, id asc) as source_snapshot_ids
  from windowed_rows
  group by
    slate_date,
    provider,
    book_key,
    normalized_player_name,
    market_key,
    side,
    line
)"""


def build_backfill_sql(*, start_date: str, end_date: str, execute: bool) -> str:
    validate_date_range(start_date, end_date)
    ctes = _compact_ctes(start_date, end_date)
    if not execute:
        return f"""
with {ctes}
select
  'dry_run' as mode,
  date '{start_date}' as start_date,
  date '{end_date}' as end_date,
  coalesce(sum(snapshot_count), 0)::bigint as source_raw_rows,
  count(*)::bigint as candidate_compact_rows,
  min(first_seen_at) as first_seen_at,
  max(last_seen_at) as last_seen_at
from compact_rows;
""".strip()

    return f"""
with {ctes},
upserted as (
  insert into public.compact_market_line_movements (
    slate_date,
    provider,
    book_key,
    normalized_player_name,
    player_name,
    market_key,
    side,
    line,
    first_seen_at,
    last_seen_at,
    first_odds,
    last_odds,
    min_odds,
    max_odds,
    odds_move_count,
    snapshot_count,
    source_snapshot_ids,
    updated_at
  )
  select
    slate_date,
    provider,
    book_key,
    normalized_player_name,
    player_name,
    market_key,
    side,
    line,
    first_seen_at,
    last_seen_at,
    first_odds,
    last_odds,
    min_odds,
    max_odds,
    odds_move_count,
    snapshot_count,
    source_snapshot_ids,
    now()
  from compact_rows
  on conflict (slate_date, provider, book_key, normalized_player_name, market_key, side, line)
  do update set
    player_name = excluded.player_name,
    first_seen_at = least(compact_market_line_movements.first_seen_at, excluded.first_seen_at),
    last_seen_at = greatest(compact_market_line_movements.last_seen_at, excluded.last_seen_at),
    first_odds = case
      when excluded.first_seen_at <= compact_market_line_movements.first_seen_at
      then excluded.first_odds
      else compact_market_line_movements.first_odds
    end,
    last_odds = case
      when excluded.last_seen_at >= compact_market_line_movements.last_seen_at
      then excluded.last_odds
      else compact_market_line_movements.last_odds
    end,
    min_odds = case
      when compact_market_line_movements.min_odds is null then excluded.min_odds
      when excluded.min_odds is null then compact_market_line_movements.min_odds
      else least(compact_market_line_movements.min_odds, excluded.min_odds)
    end,
    max_odds = case
      when compact_market_line_movements.max_odds is null then excluded.max_odds
      when excluded.max_odds is null then compact_market_line_movements.max_odds
      else greatest(compact_market_line_movements.max_odds, excluded.max_odds)
    end,
    odds_move_count = greatest(
      compact_market_line_movements.odds_move_count,
      excluded.odds_move_count
    ),
    snapshot_count = greatest(
      compact_market_line_movements.snapshot_count,
      excluded.snapshot_count
    ),
    source_snapshot_ids = excluded.source_snapshot_ids,
    updated_at = now()
  returning 1
)
select
  'execute' as mode,
  date '{start_date}' as start_date,
  date '{end_date}' as end_date,
  (select coalesce(sum(snapshot_count), 0)::bigint from compact_rows) as source_raw_rows,
  (select count(*)::bigint from compact_rows) as candidate_compact_rows,
  count(*)::bigint as upserted_compact_rows
from upserted;
""".strip()


def run_query(sql: str, *, timeout_seconds: int = 180) -> subprocess.CompletedProcess[str]:
    npx = shutil.which("npx") or "npx"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".sql", delete=False) as sql_file:
        sql_file.write(sql)
        sql_file.flush()
        sql_path = sql_file.name
    try:
        return subprocess.run(
            [npx, "supabase", "db", "query", "--linked", "--file", sql_path, "-o", "json"],
            check=False,
            capture_output=True,
            text=True,
            shell=False,
            timeout=timeout_seconds,
        )
    finally:
        os.unlink(sql_path)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", required=True, help="First slate date, YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, help="Last slate date, YYYY-MM-DD.")
    parser.add_argument("--execute", action="store_true", help="Upsert compact rows.")
    parser.add_argument("--print-sql", action="store_true", help="Print SQL without running it.")
    parser.add_argument("--timeout-seconds", type=int, default=180)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    sql = build_backfill_sql(
        start_date=args.start_date,
        end_date=args.end_date,
        execute=args.execute,
    )
    if args.print_sql:
        print(sql)
        return 0

    result = run_query(sql, timeout_seconds=args.timeout_seconds)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr)
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
