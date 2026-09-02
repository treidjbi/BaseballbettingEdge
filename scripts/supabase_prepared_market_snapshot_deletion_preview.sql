-- Read-only review packet for the completed active-provider historical scope.
-- This query cannot remove rows or enable retention execution.

with prepared_dates as (
  select generate_series(
    date '2026-06-12', date '2026-06-30', interval '1 day'
  )::date as slate_date
  union all
  select generate_series(
    date '2026-07-02', date '2026-07-12', interval '1 day'
  )::date
  union all
  select generate_series(
    date '2026-07-16', date '2026-07-26', interval '1 day'
  )::date
),
raw_by_provider as (
  select
    mpr.provider,
    count(distinct mpr.slate_date)::integer as prepared_dates_with_runs,
    count(ms.id)::bigint as raw_snapshot_rows,
    coalesce(sum(pg_column_size(ms)), 0)::bigint as raw_logical_bytes,
    min(ms.observed_at) as first_snapshot_at,
    max(ms.observed_at) as last_snapshot_at
  from public.market_provider_runs mpr
  join prepared_dates pd on pd.slate_date = mpr.slate_date
  join public.market_snapshots ms
    on ms.run_id = mpr.id
   and ms.provider = mpr.provider
  where mpr.provider in ('propline', 'therundown')
  group by mpr.provider
),
compact_by_provider as (
  select
    cmlm.provider,
    count(distinct cmlm.slate_date)::integer as compact_dates,
    count(*)::bigint as compact_groups,
    coalesce(sum(cmlm.snapshot_count), 0)::bigint as represented_snapshot_rows,
    min(cmlm.updated_at) as earliest_compact_update,
    max(cmlm.updated_at) as latest_compact_update
  from public.compact_market_line_movements cmlm
  join prepared_dates pd on pd.slate_date = cmlm.slate_date
  where cmlm.provider in ('propline', 'therundown')
  group by cmlm.provider
),
provider_review as (
  select
    raw.provider,
    raw.prepared_dates_with_runs,
    raw.raw_snapshot_rows,
    raw.raw_logical_bytes,
    raw.first_snapshot_at,
    raw.last_snapshot_at,
    compact.compact_dates,
    compact.compact_groups,
    compact.represented_snapshot_rows,
    compact.earliest_compact_update,
    compact.latest_compact_update,
    (
      raw.prepared_dates_with_runs = 41
      and compact.compact_dates = 41
      and raw.raw_snapshot_rows = compact.represented_snapshot_rows
    ) as representation_count_matches
  from raw_by_provider raw
  join compact_by_provider compact using (provider)
),
review_totals as (
  select
    count(*)::integer as provider_count,
    coalesce(sum(raw_snapshot_rows), 0)::bigint as raw_snapshot_rows,
    coalesce(sum(raw_logical_bytes), 0)::bigint as raw_logical_bytes,
    coalesce(sum(compact_groups), 0)::bigint as compact_groups,
    coalesce(sum(represented_snapshot_rows), 0)::bigint
      as represented_snapshot_rows,
    coalesce(bool_and(representation_count_matches), false)
      as representation_count_matches
  from provider_review
)
select jsonb_build_object(
  'packet_version', 1,
  'scope_id', 'prepared_active_provider_scope_v1',
  'generated_at', statement_timestamp(),
  'scope', jsonb_build_object(
    'providers', jsonb_build_array('propline', 'therundown'),
    'date_windows', jsonb_build_array(
      jsonb_build_object('start_date', '2026-06-12', 'end_date', '2026-06-30'),
      jsonb_build_object('start_date', '2026-07-02', 'end_date', '2026-07-12'),
      jsonb_build_object('start_date', '2026-07-16', 'end_date', '2026-07-26')
    ),
    'prepared_date_count', 41,
    'excluded_fail_closed_partitions', jsonb_build_array(
      jsonb_build_object(
        'provider', 'propline',
        'start_date', '2026-05-14',
        'end_date', '2026-06-11'
      ),
      jsonb_build_object(
        'provider', 'propline',
        'start_date', '2026-07-01',
        'end_date', '2026-07-01'
      ),
      jsonb_build_object(
        'provider', 'therundown',
        'start_date', '2026-07-15',
        'end_date', '2026-07-15'
      )
    )
  ),
  'providers', coalesce(
    (
      select jsonb_agg(to_jsonb(provider_review) order by provider)
      from provider_review
    ),
    '[]'::jsonb
  ),
  'totals', to_jsonb(review_totals),
  'prior_zero_upsert_proof_required', true,
  'current_backup_verification_required', true,
  'retention_execution_closed', true,
  'deletion_approved', false
) as prepared_market_snapshot_deletion_preview
from review_totals;
