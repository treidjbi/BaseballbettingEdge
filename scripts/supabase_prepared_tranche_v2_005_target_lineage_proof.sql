-- SELECT-only proof that separates the blocked preview's observed-day anomaly
-- from the actual TheRundown 2026-07-16 deletion candidate.

with settings as (
  select
    'therundown'::text as provider,
    date '2026-07-16' as target_run_date,
    timestamptz '2026-07-16 00:00:00 America/Phoenix' as observed_start,
    timestamptz '2026-07-17 00:00:00 America/Phoenix' as observed_end
), target_rows as (
  select
    ms.id,
    ms.observed_at,
    mpr.slate_date as run_slate_date,
    lower(trim(mpr.provider)) as provider,
    lower(trim(ms.bookmaker_key)) as book_key,
    trim(ms.normalized_player_name) as normalized_player_name,
    coalesce(nullif(trim(ms.market_key), ''), 'pitcher_strikeouts') as market_key,
    lower(trim(ms.side)) as side,
    ms.line::numeric as line
  from public.market_snapshots ms
  join public.market_provider_runs mpr on mpr.id = ms.run_id
  cross join settings
  where mpr.provider = settings.provider
    and mpr.slate_date = settings.target_run_date
    and ms.provider = settings.provider
), target_lineage as (
  select
    target_rows.*,
    (target_rows.observed_at at time zone 'America/Phoenix')::date
      is distinct from target_rows.run_slate_date as crosses_phoenix_date,
    exists (
      select 1
      from public.compact_market_line_movements cmlm
      where cmlm.slate_date = target_rows.run_slate_date
        and cmlm.provider = target_rows.provider
        and cmlm.book_key = target_rows.book_key
        and cmlm.normalized_player_name = target_rows.normalized_player_name
        and cmlm.market_key = target_rows.market_key
        and cmlm.side = target_rows.side
        and cmlm.line::numeric = target_rows.line
        and jsonb_typeof(cmlm.source_snapshot_ids) = 'array'
        and cmlm.source_snapshot_ids ? target_rows.id::text
        and target_rows.observed_at between cmlm.first_seen_at and cmlm.last_seen_at
    ) as preserved
  from target_rows
), observed_day_foreign_unpreserved as (
  select
    mpr.slate_date as foreign_run_date,
    ms.id,
    ms.observed_at
  from public.market_snapshots ms
  join public.market_provider_runs mpr on mpr.id = ms.run_id
  cross join settings
  where ms.provider = settings.provider
    and ms.observed_at >= settings.observed_start
    and ms.observed_at < settings.observed_end
    and mpr.slate_date is distinct from settings.target_run_date
    and mpr.slate_date is distinct from
        (ms.observed_at at time zone 'America/Phoenix')::date
    and not exists (
      select 1
      from public.compact_market_line_movements cmlm
      where cmlm.slate_date = mpr.slate_date
        and cmlm.provider = lower(trim(mpr.provider))
        and cmlm.book_key = lower(trim(ms.bookmaker_key))
        and cmlm.normalized_player_name = trim(ms.normalized_player_name)
        and cmlm.market_key = coalesce(
          nullif(trim(ms.market_key), ''), 'pitcher_strikeouts'
        )
        and cmlm.side = lower(trim(ms.side))
        and cmlm.line::numeric = ms.line::numeric
        and jsonb_typeof(cmlm.source_snapshot_ids) = 'array'
        and cmlm.source_snapshot_ids ? ms.id::text
        and ms.observed_at between cmlm.first_seen_at and cmlm.last_seen_at
    )
), compact_state as (
  select
    count(*)::bigint as compact_group_count,
    coalesce(sum(cmlm.snapshot_count), 0)::bigint as represented_snapshot_rows
  from public.compact_market_line_movements cmlm
  cross join settings
  where cmlm.provider = settings.provider
    and cmlm.slate_date = settings.target_run_date
)
select
  (select count(*)::bigint from target_lineage) as target_raw_rows,
  (select count(*)::bigint from target_lineage where crosses_phoenix_date)
    as target_cross_date_rows,
  (select count(*)::bigint from target_lineage
    where crosses_phoenix_date and preserved) as target_preserved_cross_date_rows,
  (select count(*)::bigint from target_lineage
    where crosses_phoenix_date and not preserved)
    as target_unpreserved_cross_date_rows,
  compact_state.compact_group_count,
  compact_state.represented_snapshot_rows,
  (select count(*)::bigint from observed_day_foreign_unpreserved)
    as foreign_unpreserved_rows,
  (select array_agg(distinct foreign_run_date order by foreign_run_date)
    from observed_day_foreign_unpreserved) as foreign_run_dates,
  not exists (
    select 1 from observed_day_foreign_unpreserved
    where foreign_run_date = (select target_run_date from settings)
  ) as foreign_rows_excluded_from_target_delete
from compact_state;
