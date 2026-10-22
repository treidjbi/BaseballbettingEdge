-- Read-only dependency proof for the prepared active-provider cleanup queue.
--
-- A descending run-date queue is safe to precompute only when no remaining
-- snapshot was observed before its provider run date. Rows observed one day
-- after their run date can affect only a date that executes earlier in a
-- descending queue.

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
target_runs as (
  select mpr.id, mpr.provider, mpr.slate_date
  from public.market_provider_runs mpr
  join prepared_dates on prepared_dates.slate_date = mpr.slate_date
  where mpr.provider in ('propline', 'therundown')
),
offsets as (
  select
    target_runs.provider,
    (
      (ms.observed_at at time zone 'America/Phoenix')::date
      - target_runs.slate_date
    ) as day_offset
  from public.market_snapshots ms
  join target_runs on target_runs.id = ms.run_id
  where ms.provider = target_runs.provider
),
provider_summary as (
  select
    provider,
    count(*)::bigint as remaining_raw_rows,
    count(*) filter (where day_offset < 0)::bigint
      as rows_observed_before_run_date,
    count(*) filter (where day_offset = 0)::bigint
      as rows_observed_on_run_date,
    count(*) filter (where day_offset > 0)::bigint
      as rows_observed_after_run_date,
    min(day_offset)::int as min_day_offset,
    max(day_offset)::int as max_day_offset
  from offsets
  group by provider
)
select jsonb_build_object(
  'proof_version', 1,
  'scope_id', 'prepared_active_provider_descending_order_proof_v1',
  'remaining_raw_rows', coalesce(sum(remaining_raw_rows), 0)::bigint,
  'rows_observed_before_run_date',
    coalesce(sum(rows_observed_before_run_date), 0)::bigint,
  'rows_observed_on_run_date',
    coalesce(sum(rows_observed_on_run_date), 0)::bigint,
  'rows_observed_after_run_date',
    coalesce(sum(rows_observed_after_run_date), 0)::bigint,
  'min_day_offset', min(min_day_offset),
  'max_day_offset', max(max_day_offset),
  'providers', jsonb_agg(
    jsonb_build_object(
      'provider', provider,
      'remaining_raw_rows', remaining_raw_rows,
      'rows_observed_before_run_date', rows_observed_before_run_date,
      'rows_observed_on_run_date', rows_observed_on_run_date,
      'rows_observed_after_run_date', rows_observed_after_run_date,
      'min_day_offset', min_day_offset,
      'max_day_offset', max_day_offset
    )
    order by provider
  )
) as prepared_snapshot_ordering_proof
from provider_summary;
