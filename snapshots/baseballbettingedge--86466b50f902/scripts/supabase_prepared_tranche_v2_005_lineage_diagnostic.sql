-- SELECT-only diagnosis for the blocked TheRundown 2026-07-16 partition.
-- This query identifies why next-day observations are not preserved by the
-- compact row keyed to the provider run's slate date. It performs no writes.

with mismatch_rows as (
  select
    ms.id as snapshot_id,
    (ms.observed_at at time zone 'America/Phoenix')::date as observed_slate_date,
    mpr.slate_date as run_slate_date,
    lower(trim(mpr.provider)) as provider,
    lower(trim(ms.bookmaker_key)) as book_key,
    trim(ms.normalized_player_name) as normalized_player_name,
    coalesce(nullif(trim(ms.market_key), ''), 'pitcher_strikeouts') as market_key,
    lower(trim(ms.side)) as side,
    ms.line::numeric as line,
    ms.observed_at
  from public.market_snapshots ms
  join public.market_provider_runs mpr on mpr.id = ms.run_id
  where ms.provider = 'therundown'
    and ms.observed_at >= timestamptz '2026-07-16 00:00:00 America/Phoenix'
    and ms.observed_at < timestamptz '2026-07-17 00:00:00 America/Phoenix'
    and mpr.slate_date is distinct from
        (ms.observed_at at time zone 'America/Phoenix')::date
), evaluated as (
  select
    mismatch_rows.*,
    exists (
      select 1
      from public.compact_market_line_movements cmlm
      where cmlm.slate_date = mismatch_rows.run_slate_date
        and cmlm.provider = mismatch_rows.provider
        and cmlm.book_key = mismatch_rows.book_key
        and cmlm.normalized_player_name = mismatch_rows.normalized_player_name
        and cmlm.market_key = mismatch_rows.market_key
        and cmlm.side = mismatch_rows.side
        and cmlm.line::numeric = mismatch_rows.line
    ) as run_group_exists,
    exists (
      select 1
      from public.compact_market_line_movements cmlm
      where cmlm.slate_date = mismatch_rows.run_slate_date
        and cmlm.provider = mismatch_rows.provider
        and cmlm.book_key = mismatch_rows.book_key
        and cmlm.normalized_player_name = mismatch_rows.normalized_player_name
        and cmlm.market_key = mismatch_rows.market_key
        and cmlm.side = mismatch_rows.side
        and cmlm.line::numeric = mismatch_rows.line
        and jsonb_typeof(cmlm.source_snapshot_ids) = 'array'
        and cmlm.source_snapshot_ids ? mismatch_rows.snapshot_id::text
    ) as run_source_id_exists,
    exists (
      select 1
      from public.compact_market_line_movements cmlm
      where cmlm.slate_date = mismatch_rows.run_slate_date
        and cmlm.provider = mismatch_rows.provider
        and cmlm.book_key = mismatch_rows.book_key
        and cmlm.normalized_player_name = mismatch_rows.normalized_player_name
        and cmlm.market_key = mismatch_rows.market_key
        and cmlm.side = mismatch_rows.side
        and cmlm.line::numeric = mismatch_rows.line
        and mismatch_rows.observed_at between cmlm.first_seen_at and cmlm.last_seen_at
    ) as run_time_covered,
    exists (
      select 1
      from public.compact_market_line_movements cmlm
      where cmlm.slate_date = mismatch_rows.observed_slate_date
        and cmlm.provider = mismatch_rows.provider
        and cmlm.book_key = mismatch_rows.book_key
        and cmlm.normalized_player_name = mismatch_rows.normalized_player_name
        and cmlm.market_key = mismatch_rows.market_key
        and cmlm.side = mismatch_rows.side
        and cmlm.line::numeric = mismatch_rows.line
        and jsonb_typeof(cmlm.source_snapshot_ids) = 'array'
        and cmlm.source_snapshot_ids ? mismatch_rows.snapshot_id::text
        and mismatch_rows.observed_at between cmlm.first_seen_at and cmlm.last_seen_at
    ) as observed_date_preserved
  from mismatch_rows
), unpreserved as (
  select *
  from evaluated
  where not (run_source_id_exists and run_time_covered)
)
select
  run_slate_date,
  observed_slate_date,
  book_key,
  normalized_player_name,
  market_key,
  side,
  line,
  count(*)::bigint as unpreserved_rows,
  min(observed_at) as first_unpreserved_at,
  max(observed_at) as last_unpreserved_at,
  bool_and(run_group_exists) as run_group_exists,
  bool_and(run_source_id_exists) as all_source_ids_present,
  bool_and(run_time_covered) as all_timestamps_covered,
  count(*) filter (where not run_source_id_exists)::bigint as missing_source_id_rows,
  count(*) filter (where not run_time_covered)::bigint as outside_time_window_rows,
  count(*) filter (where observed_date_preserved)::bigint as observed_date_preserved_rows
from unpreserved
group by
  run_slate_date,
  observed_slate_date,
  book_key,
  normalized_player_name,
  market_key,
  side,
  line
order by
  run_slate_date,
  book_key,
  normalized_player_name,
  side,
  line;
