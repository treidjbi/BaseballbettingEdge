-- Independent SELECT-only confirmation for approved tranche-v2-010.
with targets(provider, slate_date, expected_rows, expected_groups) as (
  values
    ('therundown', date '2026-06-30', 25371::bigint, 570::bigint),
    ('propline', date '2026-06-29', 14412::bigint, 194::bigint),
    ('therundown', date '2026-06-29', 21954::bigint, 486::bigint),
    ('propline', date '2026-06-28', 11146::bigint, 210::bigint),
    ('therundown', date '2026-06-28', 14837::bigint, 472::bigint)
), raw_state as (
  select targets.*, count(ms.id)::bigint as raw_snapshot_rows
  from targets left join public.market_provider_runs mpr
    on mpr.provider = targets.provider and mpr.slate_date = targets.slate_date
  left join public.market_snapshots ms
    on ms.run_id = mpr.id and ms.provider = targets.provider
  group by targets.provider, targets.slate_date,
           targets.expected_rows, targets.expected_groups
), compact_state as (
  select targets.provider, targets.slate_date,
         count(cmlm.id)::bigint as compact_group_count,
         coalesce(sum(cmlm.snapshot_count), 0)::bigint as represented_snapshot_rows
  from targets left join public.compact_market_line_movements cmlm
    on cmlm.provider = targets.provider and cmlm.slate_date = targets.slate_date
  group by targets.provider, targets.slate_date
), checks as (
  select raw_state.*, compact_state.compact_group_count,
         compact_state.represented_snapshot_rows,
         raw_snapshot_rows = 0 and compact_group_count = expected_groups
         and represented_snapshot_rows = expected_rows as confirmed
  from raw_state join compact_state using (provider, slate_date)
)
select jsonb_build_object(
  'scope_id', 'prepared_tranche_v2_010_postcheck_v1',
  'all_confirmed', coalesce(bool_and(confirmed), false),
  'deleted_rows', sum(expected_rows),
  'represented_snapshot_rows', sum(represented_snapshot_rows),
  'compact_group_count', sum(compact_group_count),
  'remaining_raw_snapshot_rows', sum(raw_snapshot_rows),
  'partitions', jsonb_agg(jsonb_build_object(
    'provider', provider, 'slate_date', slate_date,
    'expected_rows', expected_rows, 'expected_groups', expected_groups,
    'raw_snapshot_rows', raw_snapshot_rows,
    'compact_group_count', compact_group_count,
    'represented_snapshot_rows', represented_snapshot_rows,
    'confirmed', confirmed
  ) order by slate_date desc, provider)
) as prepared_tranche_postcheck
from checks;
