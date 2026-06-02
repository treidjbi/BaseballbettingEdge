-- Read-only Supabase row-volume and provider-readiness guardrail for BBE ops.
--
-- PowerShell:
--   npx supabase db query --linked --file scripts\supabase_row_volume_guardrail.sql -o json

with target_tables(table_name) as (
  values
    ('market_snapshots'),
    ('market_feed_heartbeats'),
    ('operational_pick_locks'),
    ('line_movement_events'),
    ('current_market_lines'),
    ('official_market_lines'),
    ('provider_request_usage_daily'),
    ('compact_market_line_movements'),
    ('shadow_pipeline_runs'),
    ('shadow_pick_lock_observations'),
    ('notification_events'),
    ('live_market_display_state'),
    ('market_pick_evidence'),
    ('propline_webhook_deliveries'),
    ('published_pipeline_artifacts'),
    ('market_provider_runs'),
    ('provider_coverage_audits')
),
table_stats as (
  select
    target_tables.table_name,
    coalesce(pg_stat_user_tables.n_live_tup::bigint, 0) as estimated_rows,
    coalesce(pg_total_relation_size(to_regclass('public.' || target_tables.table_name)), 0) as total_bytes,
    pg_size_pretty(coalesce(pg_total_relation_size(to_regclass('public.' || target_tables.table_name)), 0)) as total_size
  from target_tables
  left join pg_stat_user_tables
    on pg_stat_user_tables.schemaname = 'public'
   and pg_stat_user_tables.relname = target_tables.table_name
),
database_usage as (
  select
    current_database() as database_name,
    pg_database_size(current_database()) as database_bytes,
    pg_size_pretty(pg_database_size(current_database())) as database_size,
    round(pg_database_size(current_database()) * 100.0 / (8.0 * 1024 * 1024 * 1024), 2)
      as pct_of_pro_included_8gb
),
market_snapshot_retention as (
  select
    count(*) filter (where observed_at < now() - interval '14 days')::bigint as raw_rows_older_14d,
    count(*) filter (where observed_at < now() - interval '30 days')::bigint as raw_rows_older_30d,
    min(observed_at) as oldest_observed_at,
    max(observed_at) as newest_observed_at
  from public.market_snapshots
),
compact_market_retention as (
  select
    count(*)::bigint as compact_rows,
    min(last_seen_at) as oldest_compact_last_seen_at,
    max(last_seen_at) as newest_compact_last_seen_at
  from public.compact_market_line_movements
),
official_ready as (
  select
    slate_date,
    count(*) filter (where ready_for_pipeline)::bigint as ready_for_pipeline,
    count(*)::bigint as total_rows,
    max(updated_at) as latest_updated_at
  from public.official_market_lines
  where slate_date >= current_date - 2
  group by slate_date
),
latest_provider_audits as (
  select distinct on (provider)
    provider,
    slate_date,
    created_at,
    complete_pitcher_line_groups,
    same_line_overlap_count,
    line_conflict_count,
    missing_target_books,
    metadata
  from public.provider_coverage_audits
  where slate_date >= current_date - 2
  order by provider, created_at desc
),
latest_heartbeats as (
  select distinct on (provider)
    provider,
    slate_date,
    observed_at as heartbeat_at,
    last_message_at,
    books_seen,
    metadata
  from public.market_feed_heartbeats
  order by provider, observed_at desc
)
select
  jsonb_build_object(
    'database', (select to_jsonb(database_usage) from database_usage),
    'tables', (
      select jsonb_agg(to_jsonb(table_stats) order by total_bytes desc, table_name)
      from table_stats
    ),
    'market_snapshot_retention', (
      select to_jsonb(market_snapshot_retention)
      from market_snapshot_retention
    ),
    'compact_market_retention', (
      select to_jsonb(compact_market_retention)
      from compact_market_retention
    ),
    'official_ready', (
      select coalesce(jsonb_agg(to_jsonb(official_ready) order by slate_date desc), '[]'::jsonb)
      from official_ready
    ),
    'latest_provider_audits', (
      select coalesce(jsonb_agg(to_jsonb(latest_provider_audits) order by created_at desc), '[]'::jsonb)
      from latest_provider_audits
    ),
    'latest_heartbeats', (
      select coalesce(jsonb_agg(to_jsonb(latest_heartbeats) order by heartbeat_at desc), '[]'::jsonb)
      from latest_heartbeats
    )
  ) as guardrail;
