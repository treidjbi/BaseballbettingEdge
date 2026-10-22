-- Exact, read-only Supabase retention evidence for BBE market snapshots.
--
-- PowerShell:
--   npx supabase db query --linked --file scripts\supabase_retention_exact_coverage.sql -o json

with
settings as (
  select
    date '2026-04-28' as start_date,
    (now() at time zone 'America/Phoenix')::date as end_date,
    array['boltodds', 'propline', 'the_odds', 'therundown']::text[] as providers
),
target_runs as (
  select lower(trim(provider)) as provider, started_at,
         completed_at, status, request_count
  from public.market_provider_runs, settings
  where slate_date between settings.start_date and settings.end_date
    and lower(trim(provider)) = any(settings.providers)
),
raw_source as materialized (
  select
    ms.id as snapshot_id,
    ms.run_id,
    lower(trim(ms.provider)) as provider,
    lower(trim(ms.bookmaker_key)) as book_key,
    trim(ms.normalized_player_name) as normalized_player_name,
    coalesce(nullif(trim(ms.market_key), ''), 'pitcher_strikeouts') as market_key,
    lower(trim(ms.side)) as side,
    ms.line::numeric as line,
    ms.observed_at,
    ms.american_odds::integer as american_odds,
    mpr.id as run_row_id,
    mpr.slate_date,
    lower(trim(mpr.provider)) as run_provider,
    pg_column_size(ms)::bigint as logical_bytes
  from public.market_snapshots ms
  left join public.market_provider_runs mpr on mpr.id = ms.run_id
  cross join settings
  where coalesce(
          mpr.slate_date,
          (ms.observed_at at time zone 'America/Phoenix')::date
        ) between settings.start_date and settings.end_date
    and lower(trim(ms.provider)) = any(settings.providers)
),
valid_raw as (
  select
    slate_date,
    provider,
    book_key,
    normalized_player_name,
    market_key,
    side,
    line,
    observed_at,
    american_odds,
    snapshot_id as id,
    logical_bytes
  from raw_source
  where run_row_id is not null
    and slate_date is not null
    and provider = run_provider
    and nullif(book_key, '') is not null
    and nullif(normalized_player_name, '') is not null
    and side in ('over', 'under')
    and line is not null
),
windowed_raw as (
  select
    slate_date,
    provider,
    book_key,
    normalized_player_name,
    market_key,
    side,
    line,
    observed_at,
    american_odds,
    logical_bytes,
    first_value(american_odds) over raw_order as first_odds,
    last_value(american_odds) over raw_order as last_odds,
    lag(american_odds) over raw_order as previous_odds
  from valid_raw
  window raw_order as (
      partition by slate_date, provider, book_key, normalized_player_name, market_key, side, line
      order by observed_at asc, id asc
      rows between unbounded preceding and unbounded following
    )
),
raw_groups as (
  select
    slate_date, provider, book_key, normalized_player_name, market_key, side, line,
    min(observed_at) as first_seen_at,
    max(observed_at) as last_seen_at,
    min(first_odds) as first_odds,
    min(last_odds) as last_odds,
    min(american_odds) as min_odds,
    max(american_odds) as max_odds,
    count(*) filter (
      where previous_odds is not null
        and american_odds is distinct from previous_odds
    )::integer as odds_move_count,
    count(*)::integer as snapshot_count,
    sum(logical_bytes)::bigint as raw_logical_bytes
  from windowed_raw
  group by slate_date, provider, book_key, normalized_player_name, market_key, side, line
),
compact_groups as (
  select
    slate_date, lower(trim(provider)) as provider, lower(trim(book_key)) as book_key,
    trim(normalized_player_name) as normalized_player_name,
    coalesce(nullif(trim(market_key), ''), 'pitcher_strikeouts') as market_key,
    lower(trim(side)) as side, line::numeric as line,
    min(first_seen_at) as first_seen_at,
    max(last_seen_at) as last_seen_at,
    min(first_odds) as first_odds,
    min(last_odds) as last_odds,
    min(min_odds) as min_odds,
    max(max_odds) as max_odds,
    max(odds_move_count) as odds_move_count,
    max(snapshot_count) as snapshot_count,
    greatest(count(*) - 1, 0)::integer as compact_duplicate_count
  from public.compact_market_line_movements, settings
  where slate_date between settings.start_date and settings.end_date
    and lower(trim(provider)) = any(settings.providers)
  group by slate_date, lower(trim(provider)), lower(trim(book_key)),
           trim(normalized_player_name),
           coalesce(nullif(trim(market_key), ''), 'pitcher_strikeouts'),
           lower(trim(side)), line::numeric
),
joined_groups as (
  select
    coalesce(r.slate_date, c.slate_date) as slate_date,
    coalesce(r.provider, c.provider) as provider,
    r.slate_date is not null as raw_present,
    c.slate_date is not null as compact_present,
    r.first_seen_at as raw_first_seen_at,
    c.first_seen_at as compact_first_seen_at,
    r.last_seen_at as raw_last_seen_at,
    c.last_seen_at as compact_last_seen_at,
    r.first_odds as raw_first_odds,
    c.first_odds as compact_first_odds,
    r.last_odds as raw_last_odds,
    c.last_odds as compact_last_odds,
    r.min_odds as raw_min_odds,
    c.min_odds as compact_min_odds,
    r.max_odds as raw_max_odds,
    c.max_odds as compact_max_odds,
    r.odds_move_count as raw_odds_move_count,
    c.odds_move_count as compact_odds_move_count,
    r.snapshot_count as raw_snapshot_count,
    c.snapshot_count as compact_snapshot_count,
    coalesce(r.raw_logical_bytes, 0)::bigint as raw_logical_bytes,
    coalesce(c.compact_duplicate_count, 0)::integer as compact_duplicate_count
  from raw_groups r
  full outer join compact_groups c
    on c.slate_date = r.slate_date
   and c.provider = r.provider
   and c.book_key = r.book_key
   and c.normalized_player_name = r.normalized_player_name
   and c.market_key = r.market_key
   and c.side = r.side
   and c.line = r.line
),
coverage_by_partition as (
  select
    slate_date,
    provider,
    coalesce(sum(raw_snapshot_count) filter (where raw_present), 0)::bigint
      as raw_snapshot_rows,
    coalesce(sum(raw_logical_bytes) filter (where raw_present), 0)::bigint
      as raw_logical_bytes,
    count(*) filter (where raw_present)::bigint as raw_group_count,
    count(*) filter (where compact_present)::bigint as compact_group_count,
    count(*) filter (
      where raw_present and compact_present
        and raw_first_seen_at is not distinct from compact_first_seen_at
        and raw_last_seen_at is not distinct from compact_last_seen_at
        and raw_first_odds is not distinct from compact_first_odds
        and raw_last_odds is not distinct from compact_last_odds
        and raw_min_odds is not distinct from compact_min_odds
        and raw_max_odds is not distinct from compact_max_odds
        and raw_odds_move_count is not distinct from compact_odds_move_count
        and raw_snapshot_count is not distinct from compact_snapshot_count
    )::bigint as exact_group_count,
    count(*) filter (
      where raw_present and compact_present
        and (
          raw_first_seen_at is distinct from compact_first_seen_at
          or raw_last_seen_at is distinct from compact_last_seen_at
          or raw_first_odds is distinct from compact_first_odds
          or raw_last_odds is distinct from compact_last_odds
          or raw_min_odds is distinct from compact_min_odds
          or raw_max_odds is distinct from compact_max_odds
          or raw_odds_move_count is distinct from compact_odds_move_count
          or raw_snapshot_count is distinct from compact_snapshot_count
        )
    )::bigint as mismatched_group_count,
    count(*) filter (where raw_present and not compact_present)::bigint
      as missing_compact_group_count,
    count(*) filter (where compact_present and not raw_present)::bigint
      as unexpected_compact_group_count,
    coalesce(sum(compact_duplicate_count), 0)::bigint as duplicate_compact_group_count,
    count(*) filter (
      where raw_present and compact_present
        and raw_first_seen_at is distinct from compact_first_seen_at
    )::bigint as first_seen_mismatch_count,
    count(*) filter (
      where raw_present and compact_present
        and raw_last_seen_at is distinct from compact_last_seen_at
    )::bigint as last_seen_mismatch_count,
    count(*) filter (
      where raw_present and compact_present
        and raw_first_odds is distinct from compact_first_odds
    )::bigint as first_odds_mismatch_count,
    count(*) filter (
      where raw_present and compact_present
        and raw_last_odds is distinct from compact_last_odds
    )::bigint as last_odds_mismatch_count,
    count(*) filter (
      where raw_present and compact_present
        and raw_min_odds is distinct from compact_min_odds
    )::bigint as min_odds_mismatch_count,
    count(*) filter (
      where raw_present and compact_present
        and raw_max_odds is distinct from compact_max_odds
    )::bigint as max_odds_mismatch_count,
    count(*) filter (
      where raw_present and compact_present
        and raw_odds_move_count is distinct from compact_odds_move_count
    )::bigint as odds_move_count_mismatch_count,
    count(*) filter (
      where raw_present and compact_present
        and raw_snapshot_count is distinct from compact_snapshot_count
    )::bigint as snapshot_count_mismatch_count,
    min(raw_first_seen_at) filter (where raw_present) as first_raw_seen_at,
    max(raw_last_seen_at) filter (where raw_present) as last_raw_seen_at
  from joined_groups
  group by slate_date, provider
),
coverage_with_exactness as (
  select
    coverage_by_partition.*,
    (
      missing_compact_group_count = 0
      and unexpected_compact_group_count = 0
      and duplicate_compact_group_count = 0
      and mismatched_group_count = 0
    ) as coverage_exact
  from coverage_by_partition
),
anomaly_counts as (
  select
    lower(trim(provider)) as provider,
    count(*) filter (where run_id is null)::bigint as rows_missing_run_id,
    count(*) filter (where run_id is not null and run_row_id is null)::bigint
      as rows_missing_run_row,
    count(*) filter (
      where nullif(trim(book_key), '') is null
        or nullif(trim(normalized_player_name), '') is null
        or lower(trim(side)) not in ('over', 'under')
        or line is null
    )::bigint as rows_missing_group_key,
    count(*) filter (
      where run_row_id is not null
        and lower(trim(provider)) is distinct from run_provider
    )::bigint as provider_run_mismatch_rows
  from raw_source
  group by lower(trim(provider))
),
source_anomalies as (
  select
    target.provider,
    coalesce(anomaly_counts.rows_missing_run_id, 0)::bigint as rows_missing_run_id,
    coalesce(anomaly_counts.rows_missing_run_row, 0)::bigint as rows_missing_run_row,
    coalesce(anomaly_counts.rows_missing_group_key, 0)::bigint as rows_missing_group_key,
    coalesce(anomaly_counts.provider_run_mismatch_rows, 0)::bigint
      as provider_run_mismatch_rows
  from unnest((select providers from settings)) as target(provider)
  left join anomaly_counts on anomaly_counts.provider = target.provider
),
run_summary as (
  select
    provider,
    min(started_at) as first_run_at,
    max(coalesce(completed_at, started_at)) as last_run_at,
    count(*)::bigint as run_count,
    count(*) filter (where status = 'completed')::bigint as completed_run_count,
    count(*) filter (where status = 'failed')::bigint as failed_run_count,
    coalesce(sum(request_count), 0)::bigint as request_count
  from target_runs
  group by provider
),
book_summary as (
  select
    provider,
    array_agg(distinct book_key order by book_key) as books_seen
  from valid_raw
  group by provider
),
snapshot_summary as (
  select
    lower(trim(provider)) as provider,
    min(observed_at) as first_snapshot_at,
    max(observed_at) as last_snapshot_at,
    count(*)::bigint as snapshot_count,
    coalesce(sum(logical_bytes), 0)::bigint as snapshot_logical_bytes
  from raw_source
  group by lower(trim(provider))
),
heartbeat_summary as (
  select
    lower(trim(h.provider)) as provider,
    max(h.observed_at) as last_heartbeat_at,
    max(h.last_message_at) as last_message_at,
    count(*)::bigint as heartbeat_count
  from public.market_feed_heartbeats h
  cross join settings
  where h.slate_date between settings.start_date and settings.end_date
    and lower(trim(h.provider)) = any(settings.providers)
  group by lower(trim(h.provider))
),
provider_runtime as (
  select
    target.provider,
    run_summary.first_run_at,
    run_summary.last_run_at,
    coalesce(run_summary.run_count, 0)::bigint as run_count,
    coalesce(run_summary.completed_run_count, 0)::bigint as completed_run_count,
    coalesce(run_summary.failed_run_count, 0)::bigint as failed_run_count,
    coalesce(run_summary.request_count, 0)::bigint as request_count,
    coalesce(book_summary.books_seen, '{}'::text[]) as books_seen,
    snapshot_summary.first_snapshot_at,
    snapshot_summary.last_snapshot_at,
    coalesce(snapshot_summary.snapshot_count, 0)::bigint as snapshot_count,
    coalesce(snapshot_summary.snapshot_logical_bytes, 0)::bigint
      as snapshot_logical_bytes,
    heartbeat_summary.last_heartbeat_at,
    heartbeat_summary.last_message_at,
    coalesce(heartbeat_summary.heartbeat_count, 0)::bigint as heartbeat_count
  from unnest((select providers from settings)) as target(provider)
  left join run_summary on run_summary.provider = target.provider
  left join book_summary on book_summary.provider = target.provider
  left join snapshot_summary on snapshot_summary.provider = target.provider
  left join heartbeat_summary on heartbeat_summary.provider = target.provider
)
select jsonb_build_object(
  'audit_version', 1,
  'audit_generated_at', now(),
  'complete', true,
  'retention_execution_closed', true,
  'deletion_approved', false,
  'query_scope', jsonb_build_object(
    'start_date', (select start_date from settings),
    'end_date', (select end_date from settings),
    'providers', (select providers from settings)
  ),
  'source_anomalies', coalesce(
    (select jsonb_agg(to_jsonb(source_anomalies) order by provider) from source_anomalies),
    '[]'::jsonb
  ),
  'coverage', coalesce(
    (select jsonb_agg(to_jsonb(coverage_with_exactness) order by slate_date, provider)
     from coverage_with_exactness),
    '[]'::jsonb
  ),
  'provider_runtime', coalesce(
    (select jsonb_agg(to_jsonb(provider_runtime) order by provider) from provider_runtime),
    '[]'::jsonb
  )
) as retention_exact_coverage;
