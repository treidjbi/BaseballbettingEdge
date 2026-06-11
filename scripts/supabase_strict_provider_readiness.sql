-- Read-only strict provider readiness report for BBE.
--
-- PowerShell:
--   npx supabase db query --linked --file scripts\supabase_strict_provider_readiness.sql -o json

with settings as (
  select
    now() as checked_at,
    (now() at time zone 'America/Phoenix')::date as phoenix_today,
    ((now() at time zone 'America/Phoenix')::date - interval '1 day')::date as phoenix_yesterday
),
artifact_summary as (
  select
    jsonb_agg(
      jsonb_build_object(
        'artifact_key', artifact_key,
        'artifact_type', artifact_type,
        'slate_date', slate_date,
        'payload_date', payload->>'date',
        'generated_at', generated_at,
        'published_at', published_at,
        'source', source,
        'source_run_id', source_run_id,
        'pitcher_count', jsonb_array_length(coalesce(payload->'pitchers', '[]'::jsonb)),
        'tracked_pick_count', jsonb_array_length(coalesce(payload->'tracked_picks', '[]'::jsonb)),
        'market_source_modes', (
          select coalesce(jsonb_object_agg(mode, rows), '{}'::jsonb)
          from (
            select pitcher->>'market_source_mode' as mode, count(*) as rows
            from jsonb_array_elements(coalesce(published_pipeline_artifacts.payload->'pitchers', '[]'::jsonb)) as pitcher
            group by pitcher->>'market_source_mode'
          ) modes
        ),
        'line_source_providers', (
          select coalesce(jsonb_object_agg(provider, rows), '{}'::jsonb)
          from (
            select pitcher->>'line_source_provider' as provider, count(*) as rows
            from jsonb_array_elements(coalesce(published_pipeline_artifacts.payload->'pitchers', '[]'::jsonb)) as pitcher
            group by pitcher->>'line_source_provider'
          ) providers
        )
      )
      order by artifact_key
    ) as artifacts,
    max(published_at) filter (where artifact_key = 'today') as today_published_at,
    max(generated_at) filter (where artifact_key = 'today') as today_generated_at,
    max(jsonb_array_length(coalesce(payload->'pitchers', '[]'::jsonb))) filter (where artifact_key = 'today') as today_pitcher_count
  from public.published_pipeline_artifacts
  cross join settings
  where artifact_key in (
    'today',
    ('dated_slate:' || settings.phoenix_today::text),
    ('dated_slate:' || settings.phoenix_yesterday::text),
    'steam',
    'preview_lines',
    'performance',
    'params',
    'picks_history',
    'fangraphs_cache'
  )
),
official_line_summary as (
  select
    jsonb_agg(row_to_json(summary) order by summary.slate_date) as rows,
    coalesce(sum(summary.rows) filter (where summary.slate_date = settings.phoenix_today), 0) as today_rows,
    coalesce(sum(summary.ready_rows) filter (where summary.slate_date = settings.phoenix_today), 0) as today_ready_rows,
    coalesce(sum(summary.boltodds_ready_rows) filter (where summary.slate_date = settings.phoenix_today), 0) as today_boltodds_ready_rows
  from settings
  left join lateral (
    select
      slate_date,
      count(*) as rows,
      count(*) filter (where ready_for_pipeline) as ready_rows,
      count(*) filter (where selected_provider = 'boltodds') as boltodds_rows,
      count(*) filter (where ready_for_pipeline and selected_provider = 'boltodds') as boltodds_ready_rows,
      count(*) filter (where selected_provider = 'propline') as propline_rows,
      count(*) filter (where quality_flags ? 'cross_book_line_conflict') as cross_book_line_conflict_rows,
      max(updated_at) as latest_updated_at
    from public.official_market_lines
    where slate_date between settings.phoenix_yesterday and settings.phoenix_today
    group by slate_date
  ) summary on true
  group by settings.phoenix_today
),
current_line_summary as (
  select
    jsonb_agg(row_to_json(summary) order by summary.slate_date, summary.provider) as rows,
    coalesce(sum(summary.complete_rows) filter (where summary.slate_date = settings.phoenix_today and summary.provider = 'boltodds'), 0) as today_boltodds_complete_rows,
    max(summary.latest_updated_at) filter (where summary.slate_date = settings.phoenix_today and summary.provider = 'boltodds') as today_boltodds_latest_updated_at
  from settings
  left join lateral (
    select
      slate_date,
      provider,
      count(*) as rows,
      count(*) filter (where is_complete) as complete_rows,
      max(updated_at) as latest_updated_at
    from public.current_market_lines
    where slate_date between settings.phoenix_yesterday and settings.phoenix_today
    group by slate_date, provider
  ) summary on true
),
latest_coverage_audits as (
  select
    jsonb_agg(row_to_json(audit) order by audit.slate_date, audit.provider) as rows,
    coalesce(sum(audit.parsed_pitcher_prop_count) filter (where audit.slate_date = settings.phoenix_today and audit.provider = 'boltodds'), 0) as today_boltodds_parsed,
    coalesce(sum(audit.complete_pitcher_line_groups) filter (where audit.slate_date = settings.phoenix_today and audit.provider = 'boltodds'), 0) as today_boltodds_complete_groups,
    coalesce(sum(audit.line_conflict_count) filter (where audit.slate_date = settings.phoenix_today), 0) as today_line_conflicts
  from settings
  left join lateral (
    select distinct on (slate_date, provider)
      slate_date,
      provider,
      created_at,
      target_event_count,
      parsed_pitcher_prop_count,
      complete_pitcher_line_groups,
      same_line_overlap_count,
      line_conflict_count,
      missing_target_books,
      metadata->'target_book_group_counts' as target_book_group_counts,
      metadata->'production_book_group_counts' as production_book_group_counts
    from public.provider_coverage_audits
    where slate_date between settings.phoenix_yesterday and settings.phoenix_today
      and provider in ('boltodds', 'propline')
    order by slate_date, provider, created_at desc
  ) audit on true
  group by settings.phoenix_today
),
latest_heartbeats as (
  select
    jsonb_agg(row_to_json(heartbeat) order by heartbeat.provider) as rows,
    max(heartbeat.observed_at) filter (where heartbeat.provider = 'boltodds') as boltodds_observed_at
  from (
    select distinct on (provider)
      provider,
      slate_date,
      mode,
      observed_at,
      last_message_at,
      books_seen,
      metadata
    from public.market_feed_heartbeats
    where provider in ('boltodds', 'propline')
    order by provider, observed_at desc
  ) heartbeat
),
provider_runs as (
  select jsonb_agg(row_to_json(summary) order by summary.slate_date, summary.provider, summary.status) as rows,
         coalesce(sum(summary.failed_rows), 0) as failed_rows
  from settings
  left join lateral (
    select
      slate_date,
      provider,
      status,
      count(*) as rows,
      count(*) filter (where status = 'failed') as failed_rows,
      sum(request_count) as request_count,
      max(parsed_pitcher_prop_count) as max_parsed_pitcher_prop_count,
      max(completed_at) as latest_completed_at,
      max(error_message) filter (where error_message is not null) as sample_error
    from public.market_provider_runs
    where slate_date between settings.phoenix_yesterday and settings.phoenix_today
      and provider in ('boltodds', 'propline')
    group by slate_date, provider, status
  ) summary on true
),
provider_request_usage_daily as (
  select jsonb_agg(row_to_json(usage) order by usage.usage_date, usage.provider) as rows
  from settings
  left join lateral (
    select usage_date, provider, request_count, snapshot_count, updated_at
    from public.provider_request_usage_daily
    where usage_date between settings.phoenix_yesterday and settings.phoenix_today
      and provider in ('boltodds', 'propline')
  ) usage on true
),
operational_pick_locks as (
  select jsonb_agg(row_to_json(summary) order by summary.slate_date) as rows,
         coalesce(sum(summary.unconsumed_due_rows), 0) as unconsumed_due_rows,
         coalesce(sum(summary.duplicate_rows), 0) as duplicate_rows
  from settings
  left join lateral (
    select
      slate_date,
      count(*) as rows,
      count(*) filter (where consumed_at is not null) as consumed_rows,
      count(*) filter (where consumed_at is null and should_lock_at <= now()) as unconsumed_due_rows,
      count(*) - count(distinct dedupe_key) as duplicate_rows,
      max(consumed_at) as latest_consumed_at
    from public.operational_pick_locks
    where slate_date between settings.phoenix_yesterday and settings.phoenix_today
    group by slate_date
  ) summary on true
),
notification_events as (
  select jsonb_agg(row_to_json(summary) order by summary.slate_date, summary.event_type) as rows,
         coalesce(sum(summary.failed_rows), 0) as failed_rows
  from settings
  left join lateral (
    select
      slate_date,
      event_type,
      count(*) as rows,
      count(*) filter (where sent_at is not null) as sent_rows,
      count(*) filter (where last_send_error is not null) as failed_rows,
      max(occurred_at) as latest_occurred_at,
      max(sent_at) as latest_sent_at
    from public.notification_events
    where slate_date between settings.phoenix_yesterday and settings.phoenix_today
    group by slate_date, event_type
  ) summary on true
),
live_market_display_state as (
  select jsonb_agg(row_to_json(summary) order by summary.slate_date, summary.provider, summary.freshness_status) as rows
  from settings
  left join lateral (
    select
      slate_date,
      provider,
      freshness_status,
      actionable_state,
      count(*) as rows,
      max(updated_at) as latest_updated_at
    from public.live_market_display_state
    where slate_date between settings.phoenix_yesterday and settings.phoenix_today
    group by slate_date, provider, freshness_status, actionable_state
  ) summary on true
),
propline_webhook_deliveries as (
  select jsonb_build_object(
    'rows_7d', count(*),
    'signed_rows_7d', count(*) filter (where signature_valid),
    'processed_rows_7d', count(*) filter (where processed),
    'unprocessed_rows_7d', count(*) filter (where not processed),
    'errored_rows_7d', count(*) filter (where processing_error is not null),
    'latest_received_at', max(received_at)
  ) as summary,
  count(*) filter (where not processed) as unprocessed_rows_7d
  from public.propline_webhook_deliveries
  where received_at >= now() - interval '7 days'
),
provider_evidence_context as (
  select
    jsonb_build_object(
      'today_boltodds_ready_rows', official_line_summary.today_boltodds_ready_rows,
      'today_boltodds_complete_rows', current_line_summary.today_boltodds_complete_rows,
      'today_boltodds_latest_current_line_update', current_line_summary.today_boltodds_latest_updated_at,
      'boltodds_latest_heartbeat_at', latest_heartbeats.boltodds_observed_at,
      'boltodds_line_evidence_fresh', (
        official_line_summary.today_boltodds_ready_rows > 0
        and current_line_summary.today_boltodds_complete_rows > 0
        and latest_heartbeats.boltodds_observed_at >= now() - interval '15 minutes'
        and current_line_summary.today_boltodds_latest_updated_at >= now() - interval '30 minutes'
      )
    ) as context,
    (
      official_line_summary.today_boltodds_ready_rows > 0
      and current_line_summary.today_boltodds_complete_rows > 0
      and latest_heartbeats.boltodds_observed_at >= now() - interval '15 minutes'
      and current_line_summary.today_boltodds_latest_updated_at >= now() - interval '30 minutes'
    ) as boltodds_line_evidence_fresh
  from official_line_summary
  cross join current_line_summary
  cross join latest_heartbeats
),
strict_provider_readiness as (
  select
    settings.checked_at,
    array_remove(array[
      case
        when artifact_summary.today_published_at is null then 'today artifact missing'
        when artifact_summary.today_published_at < now() - interval '90 minutes' then 'today artifact older than 90 minutes'
      end,
      case
        when official_line_summary.today_ready_rows < coalesce(artifact_summary.today_pitcher_count, 0) then 'official market lines do not cover every today pitcher'
      end,
      case
        when latest_heartbeats.boltodds_observed_at is null then 'boltodds heartbeat missing'
        when latest_heartbeats.boltodds_observed_at < now() - interval '15 minutes' then 'boltodds heartbeat stale'
      end,
      case
        when operational_pick_locks.unconsumed_due_rows > 0 then 'due lock rows are unconsumed'
      end
    ], null) as blocking_reasons,
    array_remove(array[
      case
        when latest_coverage_audits.today_boltodds_parsed = 0
          and provider_evidence_context.boltodds_line_evidence_fresh
          then 'latest BoltOdds coverage audit parsed zero rows but heartbeat/current/official lines are fresh'
        when latest_coverage_audits.today_boltodds_parsed = 0 then 'latest BoltOdds coverage audit parsed zero rows'
      end,
      case
        when latest_coverage_audits.today_boltodds_complete_groups = 0
          and provider_evidence_context.boltodds_line_evidence_fresh
          then 'latest BoltOdds coverage audit has zero complete groups but heartbeat/current/official lines are fresh'
        when latest_coverage_audits.today_boltodds_complete_groups = 0 then 'latest BoltOdds coverage audit has zero complete groups'
      end,
      case
        when latest_coverage_audits.today_line_conflicts > 0 then 'provider coverage audits include line conflicts'
      end,
      case
        when provider_runs.failed_rows > 0 then 'provider runs include failures'
      end,
      case
        when notification_events.failed_rows > 0 then 'notification events include failed sends'
      end,
      case
        when operational_pick_locks.duplicate_rows > 0 then 'lock ledger has duplicate rows'
      end,
      case
        when propline_webhook_deliveries.unprocessed_rows_7d > 0 then 'recent PropLine webhook rows remain unprocessed'
      end
    ], null) as watch_reasons
  from settings
  cross join artifact_summary
  cross join official_line_summary
  cross join latest_coverage_audits
  cross join latest_heartbeats
  cross join provider_evidence_context
  cross join provider_runs
  cross join operational_pick_locks
  cross join notification_events
  cross join propline_webhook_deliveries
)
select
  'strict_provider_readiness' as report_name,
  strict_provider_readiness.checked_at,
  case
    when cardinality(strict_provider_readiness.blocking_reasons) > 0 then 'not_ready'
    when cardinality(strict_provider_readiness.watch_reasons) > 0 then 'watch'
    else 'ready_for_review'
  end as readiness_status,
  strict_provider_readiness.blocking_reasons,
  strict_provider_readiness.watch_reasons,
  artifact_summary.artifacts as artifact_summary,
  official_line_summary.rows as official_line_summary,
  provider_evidence_context.context as provider_evidence_context,
  current_line_summary.rows as current_line_summary,
  latest_coverage_audits.rows as latest_coverage_audits,
  latest_heartbeats.rows as latest_heartbeats,
  provider_runs.rows as provider_runs,
  provider_request_usage_daily.rows as provider_request_usage_daily,
  operational_pick_locks.rows as operational_pick_locks,
  notification_events.rows as notification_events,
  live_market_display_state.rows as live_market_display_state,
  propline_webhook_deliveries.summary as propline_webhook_deliveries
from strict_provider_readiness
cross join artifact_summary
cross join official_line_summary
cross join provider_evidence_context
cross join current_line_summary
cross join latest_coverage_audits
cross join latest_heartbeats
cross join provider_runs
cross join provider_request_usage_daily
cross join operational_pick_locks
cross join notification_events
cross join live_market_display_state
cross join propline_webhook_deliveries;
