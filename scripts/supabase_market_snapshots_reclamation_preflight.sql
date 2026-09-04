-- SELECT-only preflight for post-deletion market_snapshots reclamation.
with relation_state as (
  select
    s.relid,
    s.n_live_tup::bigint as estimated_live_rows,
    s.n_dead_tup::bigint as estimated_dead_rows,
    s.last_vacuum,
    s.last_autovacuum,
    s.vacuum_count,
    s.autovacuum_count,
    pg_relation_size(s.relid) as heap_bytes,
    pg_indexes_size(s.relid) as index_bytes,
    pg_total_relation_size(s.relid) as total_bytes
  from pg_stat_user_tables s
  where s.schemaname = 'public' and s.relname = 'market_snapshots'
), active_sessions as (
  select
    count(*) filter (where state = 'active')::bigint as active_sessions,
    count(*) filter (
      where state = 'active'
        and query ~* '\m(insert|update|delete|truncate|copy|merge)\M'
        and query ilike '%market_snapshots%'
    )::bigint as active_market_snapshot_writers,
    count(*) filter (
      where xact_start is not null
        and xact_start < clock_timestamp() - interval '5 minutes'
    )::bigint as transactions_over_five_minutes
  from pg_stat_activity
  where pid <> pg_backend_pid()
), relation_locks as (
  select
    count(*)::bigint as lock_count,
    count(*) filter (where not granted)::bigint as waiting_lock_count,
    count(*) filter (
      where mode in ('RowExclusiveLock', 'ShareRowExclusiveLock',
                     'ExclusiveLock', 'AccessExclusiveLock')
    )::bigint as writer_or_exclusive_lock_count
  from pg_locks
  where relation = 'public.market_snapshots'::regclass
), settings as (
  select
    current_setting('autovacuum') as autovacuum,
    current_setting('autovacuum_vacuum_scale_factor') as autovacuum_vacuum_scale_factor,
    current_setting('autovacuum_vacuum_threshold') as autovacuum_vacuum_threshold
), db_state as (
  select
    pg_database_size(current_database()) as database_bytes,
    (8::bigint * 1024 * 1024 * 1024) - pg_database_size(current_database())
      as nominal_8gb_headroom_bytes
)
select jsonb_build_object(
  'scope_id', 'market_snapshots_reclamation_preflight_v1',
  'observed_at', clock_timestamp(),
  'database_bytes', db_state.database_bytes,
  'database_size', pg_size_pretty(db_state.database_bytes),
  'pct_of_nominal_8gb', round(db_state.database_bytes * 100.0 / (8.0 * 1024 * 1024 * 1024), 2),
  'nominal_8gb_headroom_bytes', db_state.nominal_8gb_headroom_bytes,
  'nominal_8gb_headroom', pg_size_pretty(db_state.nominal_8gb_headroom_bytes),
  'market_snapshots', jsonb_build_object(
    'estimated_live_rows', relation_state.estimated_live_rows,
    'estimated_dead_rows', relation_state.estimated_dead_rows,
    'heap_bytes', relation_state.heap_bytes,
    'heap_size', pg_size_pretty(relation_state.heap_bytes),
    'index_bytes', relation_state.index_bytes,
    'index_size', pg_size_pretty(relation_state.index_bytes),
    'total_bytes', relation_state.total_bytes,
    'total_size', pg_size_pretty(relation_state.total_bytes),
    'last_vacuum', relation_state.last_vacuum,
    'last_autovacuum', relation_state.last_autovacuum,
    'vacuum_count', relation_state.vacuum_count,
    'autovacuum_count', relation_state.autovacuum_count
  ),
  'activity', jsonb_build_object(
    'active_sessions', active_sessions.active_sessions,
    'active_market_snapshot_writers', active_sessions.active_market_snapshot_writers,
    'transactions_over_five_minutes', active_sessions.transactions_over_five_minutes,
    'relation_lock_count', relation_locks.lock_count,
    'waiting_lock_count', relation_locks.waiting_lock_count,
    'writer_or_exclusive_lock_count', relation_locks.writer_or_exclusive_lock_count
  ),
  'settings', to_jsonb(settings),
  'rewrite_headroom_ratio', round(
    db_state.nominal_8gb_headroom_bytes::numeric / nullif(relation_state.total_bytes, 0), 3
  )
) as market_snapshots_reclamation_preflight
from relation_state cross join active_sessions cross join relation_locks
cross join settings cross join db_state;
