-- Read-only Supabase retention readiness report for BBE raw market snapshots.
--
-- PowerShell:
--   npx supabase db query --linked --file scripts\supabase_retention_readiness.sql -o json

with retention_windows(older_than_days) as (
  values (14), (30)
),
target_providers(provider) as (
  values ('boltodds'), ('propline'), ('the_odds'), ('therundown')
),
settings as (
  select
    older_than_days,
    now() - make_interval(days => older_than_days) as cutoff_at,
    5000::integer as sample_row_limit
  from retention_windows
),
database_usage as (
  select
    current_database() as database_name,
    pg_database_size(current_database()) as database_bytes,
    pg_size_pretty(pg_database_size(current_database())) as database_size,
    round(pg_database_size(current_database()) * 100.0 / (8.0 * 1024 * 1024 * 1024), 2)
      as pct_of_pro_included_8gb
),
snapshot_table as (
  select
    pg_total_relation_size('public.market_snapshots'::regclass) as total_bytes,
    pg_size_pretty(pg_total_relation_size('public.market_snapshots'::regclass)) as total_size,
    coalesce(pg_stat_user_tables.n_live_tup::bigint, 0) as estimated_rows
  from pg_stat_user_tables
  where schemaname = 'public'
    and relname = 'market_snapshots'
),
window_rows as (
  select
    settings.older_than_days,
    settings.cutoff_at,
    settings.sample_row_limit,
    count(market_snapshots.*)::bigint as raw_snapshot_rows,
    count(*) filter (
      where market_snapshots.observed_at is not null
        and market_snapshots.run_id is null
    )::bigint as rows_missing_run_id,
    count(*) filter (
      where market_snapshots.observed_at is not null
        and (
          nullif(trim(market_snapshots.provider), '') is null
          or nullif(trim(market_snapshots.bookmaker_key), '') is null
          or nullif(trim(market_snapshots.normalized_player_name), '') is null
          or nullif(trim(market_snapshots.side), '') is null
          or market_snapshots.line is null
        )
    )::bigint as rows_missing_group_key
  from settings
  left join public.market_snapshots
    on market_snapshots.observed_at < settings.cutoff_at
  group by
    settings.older_than_days,
    settings.cutoff_at,
    settings.sample_row_limit
),
sampled_rows as (
  select
    settings.older_than_days,
    settings.cutoff_at,
    settings.sample_row_limit,
    sampled.run_id,
    sampled.run_row_id,
    sampled.slate_date,
    sampled.provider,
    sampled.bookmaker_key,
    sampled.normalized_player_name,
    sampled.market_key,
    sampled.side,
    sampled.line,
    sampled.observed_at
  from settings
  cross join target_providers
  cross join lateral (
    select
      market_snapshots.run_id,
      market_provider_runs.id as run_row_id,
      market_provider_runs.slate_date::text as slate_date,
      market_snapshots.provider,
      market_snapshots.bookmaker_key,
      market_snapshots.normalized_player_name,
      market_snapshots.market_key,
      market_snapshots.side,
      market_snapshots.line,
      market_snapshots.observed_at
    from public.market_snapshots
    left join public.market_provider_runs
      on market_provider_runs.id = market_snapshots.run_id
    where market_snapshots.provider = target_providers.provider
      and market_snapshots.observed_at < settings.cutoff_at
    order by market_snapshots.observed_at desc
    limit 5000
  ) as sampled
),
sample_window_rows as (
  select
    older_than_days,
    count(*)::bigint as sampled_snapshot_rows,
    count(*) filter (
      where run_id is not null
        and run_row_id is null
    )::bigint as sample_rows_missing_run_row,
    count(*) filter (
      where run_row_id is not null
        and nullif(slate_date, '') is null
    )::bigint as sample_rows_missing_slate_date
  from sampled_rows
  group by older_than_days
),
sampled_groups as (
  select
    older_than_days,
    cutoff_at,
    slate_date,
    lower(trim(provider)) as provider,
    lower(trim(bookmaker_key)) as book_key,
    trim(normalized_player_name) as normalized_player_name,
    coalesce(nullif(trim(market_key), ''), 'pitcher_strikeouts') as market_key,
    lower(trim(side)) as side,
    line,
    count(*)::bigint as snapshot_rows,
    min(observed_at) as first_raw_seen_at,
    max(observed_at) as last_raw_seen_at
  from sampled_rows
  where nullif(slate_date, '') is not null
    and nullif(trim(provider), '') is not null
    and nullif(trim(bookmaker_key), '') is not null
    and nullif(trim(normalized_player_name), '') is not null
    and nullif(trim(side), '') is not null
    and line is not null
  group by
    older_than_days,
    cutoff_at,
    slate_date,
    lower(trim(provider)),
    lower(trim(bookmaker_key)),
    trim(normalized_player_name),
    coalesce(nullif(trim(market_key), ''), 'pitcher_strikeouts'),
    lower(trim(side)),
    line
),
coverage as (
  select
    sampled_groups.*,
    bool_or(compact_market_line_movements.slate_date is not null) as compact_covered
  from sampled_groups
  left join public.compact_market_line_movements
    on compact_market_line_movements.slate_date::text = sampled_groups.slate_date
   and compact_market_line_movements.provider = sampled_groups.provider
   and compact_market_line_movements.book_key = sampled_groups.book_key
   and compact_market_line_movements.normalized_player_name = sampled_groups.normalized_player_name
   and compact_market_line_movements.market_key = sampled_groups.market_key
   and compact_market_line_movements.side = sampled_groups.side
   and compact_market_line_movements.line = sampled_groups.line
   and compact_market_line_movements.first_seen_at <= sampled_groups.cutoff_at
  group by
    sampled_groups.older_than_days,
    sampled_groups.cutoff_at,
    sampled_groups.slate_date,
    sampled_groups.provider,
    sampled_groups.book_key,
    sampled_groups.normalized_player_name,
    sampled_groups.market_key,
    sampled_groups.side,
    sampled_groups.line,
    sampled_groups.snapshot_rows,
    sampled_groups.first_raw_seen_at,
    sampled_groups.last_raw_seen_at
),
coverage_summary as (
  select
    window_rows.older_than_days,
    window_rows.cutoff_at,
    window_rows.sample_row_limit,
    window_rows.raw_snapshot_rows,
    window_rows.rows_missing_run_id,
    window_rows.rows_missing_group_key,
    coalesce(sample_window_rows.sampled_snapshot_rows, 0)::bigint as sampled_snapshot_rows,
    coalesce(sample_window_rows.sample_rows_missing_run_row, 0)::bigint as sample_rows_missing_run_row,
    coalesce(sample_window_rows.sample_rows_missing_slate_date, 0)::bigint as sample_rows_missing_slate_date,
    (
      window_rows.rows_missing_run_id
      + window_rows.rows_missing_group_key
      + coalesce(sample_window_rows.sample_rows_missing_run_row, 0)
      + coalesce(sample_window_rows.sample_rows_missing_slate_date, 0)
    )::bigint as coverage_uncertain_rows,
    count(coverage.*)::bigint as sampled_snapshot_groups,
    count(coverage.*) filter (where coverage.compact_covered)::bigint as compact_covered_groups,
    count(coverage.*) filter (where not coverage.compact_covered)::bigint as uncovered_snapshot_groups
  from window_rows
  left join sample_window_rows
    on sample_window_rows.older_than_days = window_rows.older_than_days
  left join coverage
    on coverage.older_than_days = window_rows.older_than_days
  group by
    window_rows.older_than_days,
    window_rows.cutoff_at,
    window_rows.sample_row_limit,
    window_rows.raw_snapshot_rows,
    window_rows.rows_missing_run_id,
    window_rows.rows_missing_group_key,
    sample_window_rows.sampled_snapshot_rows,
    sample_window_rows.sample_rows_missing_run_row,
    sample_window_rows.sample_rows_missing_slate_date
),
readiness as (
  select
    coverage_summary.*,
    false as coverage_exact,
    case
      when snapshot_table.estimated_rows > 0 then
        round(
          (snapshot_table.total_bytes::numeric / snapshot_table.estimated_rows)
          * coverage_summary.raw_snapshot_rows
        )::bigint
      else 0::bigint
    end as estimated_raw_snapshot_bytes,
    false as eligible_for_execute
  from coverage_summary
  cross join snapshot_table
)
select
  jsonb_build_object(
    'generated_at', now(),
    'dry_run_only', true,
    'retention_execution_closed', true,
    'approval_required_for_execute', true,
    'database', (select to_jsonb(database_usage) from database_usage),
    'snapshot_table', (select to_jsonb(snapshot_table) from snapshot_table),
    'windows', (
      select jsonb_agg(
        jsonb_build_object(
          'older_than_days', readiness.older_than_days,
          'cutoff_at', readiness.cutoff_at,
          'raw_snapshot_rows', readiness.raw_snapshot_rows,
          'estimated_raw_snapshot_bytes', readiness.estimated_raw_snapshot_bytes,
          'estimated_raw_snapshot_size', pg_size_pretty(readiness.estimated_raw_snapshot_bytes),
          'coverage_exact', readiness.coverage_exact,
          'sample_row_limit', readiness.sample_row_limit,
          'sampled_snapshot_rows', readiness.sampled_snapshot_rows,
          'sampled_snapshot_groups', readiness.sampled_snapshot_groups,
          'compact_covered_groups', readiness.compact_covered_groups,
          'uncovered_snapshot_groups', readiness.uncovered_snapshot_groups,
          'coverage_uncertain_rows', readiness.coverage_uncertain_rows,
          'rows_missing_run_id', readiness.rows_missing_run_id,
          'rows_missing_group_key', readiness.rows_missing_group_key,
          'sample_rows_missing_run_row', readiness.sample_rows_missing_run_row,
          'sample_rows_missing_slate_date', readiness.sample_rows_missing_slate_date,
          'eligible_for_execute', readiness.eligible_for_execute,
          'sample_uncovered_groups', (
            select coalesce(jsonb_agg(to_jsonb(sample_uncovered)), '[]'::jsonb)
            from (
              select
                coverage.slate_date,
                coverage.provider,
                coverage.book_key,
                coverage.normalized_player_name,
                coverage.market_key,
                coverage.side,
                coverage.line,
                coverage.snapshot_rows,
                coverage.first_raw_seen_at,
                coverage.last_raw_seen_at
              from coverage
              where coverage.older_than_days = readiness.older_than_days
                and not coverage.compact_covered
              order by coverage.snapshot_rows desc, coverage.last_raw_seen_at desc
              limit 10
            ) as sample_uncovered
          )
        )
        order by readiness.older_than_days
      )
      from readiness
    )
  ) as retention_readiness;
