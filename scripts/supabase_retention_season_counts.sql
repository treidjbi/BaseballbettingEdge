with bounds as (
  select
    date '2026-05-07' as start_date,
    date '2026-06-16' as end_date
),
slate_dates as (
  select generate_series(start_date, end_date, interval '1 day')::date as slate_date
  from bounds
),
accepted as (
  select
    slate_date,
    count(*)::integer as row_count,
    count(*) filter (where accepted_at is not null)::integer as complete_count
  from public.accepted_bets, bounds
  where slate_date between start_date and end_date
  group by slate_date
),
sent as (
  select
    slate_date,
    count(*)::integer as row_count,
    count(*) filter (
      where occurred_at is not null and sent_at is not null
    )::integer as complete_count
  from public.notification_events, bounds
  where slate_date between start_date and end_date
    and sent_at is not null
  group by slate_date
),
consumed as (
  select
    slate_date,
    count(*)::integer as row_count,
    count(*) filter (
      where consumed_at is not null
        and locked_at is not null
        and observed_at is not null
        and nullif(trim(source_artifact_path), '') is not null
    )::integer as complete_count
  from public.operational_pick_locks, bounds
  where slate_date between start_date and end_date
    and consumed_at is not null
  group by slate_date
),
frozen_alt_v2 as (
  select
    slate_date,
    count(*)::integer as row_count,
    count(*) filter (
      where frozen_at is not null
        and locked_at is not null
        and nullif(trim(source_artifact_path), '') is not null
        and jsonb_typeof(evaluation_proof) = 'object'
        and evaluation_proof <> '{}'::jsonb
    )::integer as complete_count
  from public.alternative_pick_selection_state, bounds
  where slate_date between start_date and end_date
    and checkpoint = 'frozen_pregame'
    and bundle_id = 'pregame_alternative_pick_methodology_v2'
  group by slate_date
)
select jsonb_build_object(
  'schema_version', 1,
  'generated_at', now(),
  'scope', jsonb_build_object(
    'start_date', (select start_date from bounds),
    'end_date', (select end_date from bounds),
    'providers', jsonb_build_array('boltodds')
  ),
  'dates', coalesce(
    jsonb_agg(
      jsonb_build_object(
        'slate_date', d.slate_date,
        'accepted_bets', coalesce(a.row_count, 0),
        'accepted_bets_complete', coalesce(a.complete_count, 0),
        'sent_notifications', coalesce(n.row_count, 0),
        'sent_notifications_complete', coalesce(n.complete_count, 0),
        'consumed_locks', coalesce(l.row_count, 0),
        'consumed_locks_complete', coalesce(l.complete_count, 0),
        'frozen_alt_v2_rows', coalesce(v.row_count, 0),
        'frozen_alt_v2_rows_complete', coalesce(v.complete_count, 0)
      ) order by d.slate_date
    ),
    '[]'::jsonb
  )
) as retention_season_counts
from slate_dates d
left join accepted a using (slate_date)
left join sent n using (slate_date)
left join consumed l using (slate_date)
left join frozen_alt_v2 v using (slate_date);
