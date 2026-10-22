-- Independent SELECT-only confirmation for the complete approved prepared scope.
with target_dates as (
  select generate_series(date '2026-06-12', date '2026-06-30', interval '1 day')::date as slate_date
  union all
  select generate_series(date '2026-07-02', date '2026-07-12', interval '1 day')::date
  union all
  select generate_series(date '2026-07-16', date '2026-07-26', interval '1 day')::date
), providers(provider) as (
  values ('propline'::text), ('therundown'::text)
), targets as (
  select provider, slate_date from providers cross join target_dates
), raw_state as (
  select targets.provider, targets.slate_date,
         count(ms.id)::bigint as raw_snapshot_rows
  from targets
  left join public.market_provider_runs mpr
    on mpr.provider = targets.provider and mpr.slate_date = targets.slate_date
  left join public.market_snapshots ms
    on ms.run_id = mpr.id and ms.provider = targets.provider
  group by targets.provider, targets.slate_date
), compact_state as (
  select targets.provider, targets.slate_date,
         count(cmlm.id)::bigint as compact_group_count,
         coalesce(sum(cmlm.snapshot_count), 0)::bigint as represented_snapshot_rows
  from targets
  left join public.compact_market_line_movements cmlm
    on cmlm.provider = targets.provider and cmlm.slate_date = targets.slate_date
  group by targets.provider, targets.slate_date
), checks as (
  select raw_state.provider, raw_state.slate_date,
         raw_state.raw_snapshot_rows,
         compact_state.compact_group_count,
         compact_state.represented_snapshot_rows
  from raw_state join compact_state using (provider, slate_date)
)
select jsonb_build_object(
  'scope_id', 'prepared_active_provider_scope_final_postcheck_v1',
  'partition_count', count(*),
  'remaining_raw_snapshot_rows', sum(raw_snapshot_rows),
  'compact_group_count', sum(compact_group_count),
  'represented_snapshot_rows', sum(represented_snapshot_rows),
  'expected_partition_count', 82,
  'expected_compact_group_count', 36507,
  'expected_represented_snapshot_rows', 1816265,
  'all_confirmed', count(*) = 82
    and sum(raw_snapshot_rows) = 0
    and sum(compact_group_count) = 36507
    and sum(represented_snapshot_rows) = 1816265,
  'nonzero_raw_partitions', coalesce(jsonb_agg(jsonb_build_object(
    'provider', provider,
    'slate_date', slate_date,
    'raw_snapshot_rows', raw_snapshot_rows
  ) order by slate_date desc, provider) filter (where raw_snapshot_rows <> 0), '[]'::jsonb)
) as prepared_scope_postcheck
from checks;
