-- Read-only Supabase storage guardrail for BBE operations.
--
-- PowerShell:
--   npx supabase db query --linked --file scripts\supabase_storage_guardrail.sql -o json

with database_usage as (
  select
    current_database() as database_name,
    pg_database_size(current_database()) as database_bytes
),
top_tables as (
  select
    relname as table_name,
    n_live_tup::bigint as estimated_rows,
    pg_total_relation_size(relid) as total_bytes,
    pg_relation_size(relid) as table_bytes,
    pg_indexes_size(relid) as index_bytes
  from pg_stat_user_tables
  order by pg_total_relation_size(relid) desc
  limit 20
)
select
  database_usage.database_name,
  database_usage.database_bytes,
  pg_size_pretty(database_usage.database_bytes) as database_size,
  round(database_usage.database_bytes * 100.0 / (8.0 * 1024 * 1024 * 1024), 2) as pct_of_pro_included_8gb,
  coalesce(
    jsonb_agg(
      jsonb_build_object(
        'table_name', top_tables.table_name,
        'estimated_rows', top_tables.estimated_rows,
        'total_bytes', top_tables.total_bytes,
        'total_size', pg_size_pretty(top_tables.total_bytes),
        'table_size', pg_size_pretty(top_tables.table_bytes),
        'index_size', pg_size_pretty(top_tables.index_bytes)
      )
      order by top_tables.total_bytes desc
    ) filter (where top_tables.table_name is not null),
    '[]'::jsonb
  ) as top_tables
from database_usage
left join top_tables on true
group by database_usage.database_name, database_usage.database_bytes;
