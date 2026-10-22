create or replace function public.refresh_shadow_provider_movement_tracking(since_timestamp timestamptz default now() - interval '24 hours')
returns table (
  inserted_or_updated_webhook_events integer,
  inserted_or_updated_snapshot_events integer,
  inserted_or_updated_comparisons integer
)
language plpgsql
security definer
set search_path = public
as $$
declare
  webhook_count integer := 0;
  snapshot_count integer := 0;
  comparison_count integer := 0;
begin
  with upserted as (
    insert into public.shadow_provider_movement_events (
      source,
      provider,
      source_delivery_id,
      slate_date,
      provider_event_id,
      sport_key,
      market_key,
      player_name,
      normalized_player_name,
      side,
      previous_line,
      current_line,
      previous_odds,
      current_odds,
      price_change_pct,
      observed_at,
      received_at,
      provider_latency_seconds,
      raw_payload,
      dedupe_key
    )
    select
      'propline_webhook',
      'propline',
      d.prop_line_delivery_id,
      ((d.payload #>> '{event,commence_time}')::timestamptz)::date,
      d.payload #>> '{event,external_id}',
      d.payload ->> 'sport_key',
      d.payload ->> 'market_key',
      d.payload ->> 'player_name',
      lower(regexp_replace(d.payload ->> 'player_name', '\s*\([^)]*\)\s*$', '')),
      lower(d.payload ->> 'outcome_name'),
      nullif(d.payload #>> '{previous,point}', '')::numeric,
      nullif(d.payload #>> '{current,point}', '')::numeric,
      nullif(d.payload #>> '{previous,price_american}', '')::integer,
      nullif(d.payload #>> '{current,price_american}', '')::integer,
      nullif(d.payload ->> 'price_change_pct', '')::numeric,
      coalesce((d.payload ->> 'timestamp')::timestamptz, d.prop_line_timestamp),
      d.received_at,
      extract(epoch from (d.received_at - d.prop_line_timestamp))::integer,
      d.payload,
      'propline_webhook:' || d.prop_line_delivery_id
    from public.propline_webhook_deliveries d
    where d.signature_valid = true
      and d.prop_line_event = 'line_movement'
      and d.prop_line_timestamp >= since_timestamp
    on conflict (dedupe_key) do update set
      raw_payload = excluded.raw_payload,
      received_at = excluded.received_at,
      provider_latency_seconds = excluded.provider_latency_seconds
    returning 1
  )
  select count(*) into webhook_count from upserted;

  with upserted as (
    insert into public.shadow_provider_movement_events (
      source,
      provider,
      source_snapshot_id,
      source_run_id,
      slate_date,
      provider_event_id,
      sport_key,
      market_key,
      bookmaker_key,
      player_name,
      normalized_player_name,
      side,
      current_line,
      current_odds,
      observed_at,
      raw_payload,
      dedupe_key
    )
    select
      ms.provider || '_snapshot',
      ms.provider,
      ms.id,
      ms.run_id,
      coalesce((ms.game_time::timestamptz)::date, ms.observed_at::date),
      ms.provider_event_id,
      ms.sport_key,
      case when ms.market_key = 'Strikeouts' then 'pitcher_strikeouts' else ms.market_key end,
      ms.bookmaker_key,
      ms.player_name,
      ms.normalized_player_name,
      lower(ms.side),
      ms.line,
      ms.american_odds,
      ms.observed_at,
      jsonb_build_object(
        'source_payload', ms.source_payload,
        'bookmaker_title', ms.bookmaker_title,
        'original_market_key', ms.market_key,
        'dedupe_key', ms.dedupe_key
      ),
      ms.provider || '_snapshot:' || ms.id::text
    from public.market_snapshots ms
    where ms.provider in ('boltodds', 'propline')
      and ms.observed_at >= since_timestamp
      and ms.market_key in ('pitcher_strikeouts', 'Strikeouts')
    on conflict (dedupe_key) do update set
      market_key = excluded.market_key,
      current_line = excluded.current_line,
      current_odds = excluded.current_odds,
      raw_payload = excluded.raw_payload
    returning 1
  )
  select count(*) into snapshot_count from upserted;

  with nearest_boltodds as (
    select
      h.id as primary_event_id,
      b.id as comparison_event_id,
      abs(extract(epoch from (b.observed_at - h.observed_at)))::integer as abs_delta_seconds,
      extract(epoch from (b.observed_at - h.observed_at))::integer as latency_delta_seconds,
      row_number() over (
        partition by h.id
        order by abs(extract(epoch from (b.observed_at - h.observed_at))) asc, b.observed_at asc
      ) as rn
    from public.shadow_provider_movement_events h
    left join public.shadow_provider_movement_events b
      on b.source = 'boltodds_snapshot'
     and b.market_key = h.market_key
     and b.normalized_player_name = h.normalized_player_name
     and b.side = h.side
     and b.observed_at between h.observed_at - interval '90 minutes' and h.observed_at + interval '90 minutes'
    where h.source = 'propline_webhook'
      and h.observed_at >= since_timestamp
  ), comparison_rows as (
    select
      h.slate_date,
      h.market_key,
      h.normalized_player_name,
      h.player_name,
      h.side,
      h.id as primary_event_id,
      b.id as comparison_event_id,
      h.observed_at as primary_observed_at,
      b.observed_at as comparison_observed_at,
      nb.latency_delta_seconds,
      h.current_line as primary_current_line,
      b.current_line as comparison_current_line,
      case when b.id is null then null else h.current_line is not distinct from b.current_line end as same_line,
      h.current_odds as primary_current_odds,
      b.current_odds as comparison_current_odds,
      case when b.current_odds is null or h.current_odds is null then null else b.current_odds - h.current_odds end as odds_delta,
      h.price_change_pct as primary_price_change_pct,
      case
        when b.id is null then 'no_boltodds_match'
        when nb.latency_delta_seconds > 60 then 'propline_webhook_first'
        when nb.latency_delta_seconds < -60 then 'boltodds_first'
        else 'same_minute'
      end as comparison_result,
      case
        when b.id is null then true
        when nb.latency_delta_seconds > 60 then true
        else false
      end as would_reduce_spend_signal,
      jsonb_build_object(
        'abs_delta_seconds', nb.abs_delta_seconds,
        'webhook_delivery_id', h.source_delivery_id,
        'boltodds_snapshot_id', b.source_snapshot_id,
        'webhook_provider_latency_seconds', h.provider_latency_seconds
      ) as metadata,
      'propline_webhook_vs_boltodds:' || h.id::text as dedupe_key
    from public.shadow_provider_movement_events h
    left join nearest_boltodds nb
      on nb.primary_event_id = h.id and nb.rn = 1
    left join public.shadow_provider_movement_events b
      on b.id = nb.comparison_event_id
    where h.source = 'propline_webhook'
      and h.observed_at >= since_timestamp
  ), upserted as (
    insert into public.shadow_movement_source_comparisons (
      slate_date,
      market_key,
      normalized_player_name,
      player_name,
      side,
      primary_source,
      comparison_source,
      primary_event_id,
      comparison_event_id,
      primary_observed_at,
      comparison_observed_at,
      latency_delta_seconds,
      primary_current_line,
      comparison_current_line,
      same_line,
      primary_current_odds,
      comparison_current_odds,
      odds_delta,
      primary_price_change_pct,
      comparison_result,
      would_reduce_spend_signal,
      metadata,
      dedupe_key,
      updated_at
    )
    select
      slate_date,
      market_key,
      normalized_player_name,
      player_name,
      side,
      'propline_webhook',
      'boltodds_snapshot',
      primary_event_id,
      comparison_event_id,
      primary_observed_at,
      comparison_observed_at,
      latency_delta_seconds,
      primary_current_line,
      comparison_current_line,
      same_line,
      primary_current_odds,
      comparison_current_odds,
      odds_delta,
      primary_price_change_pct,
      comparison_result,
      would_reduce_spend_signal,
      metadata,
      dedupe_key,
      now()
    from comparison_rows
    on conflict (dedupe_key) do update set
      comparison_event_id = excluded.comparison_event_id,
      comparison_observed_at = excluded.comparison_observed_at,
      latency_delta_seconds = excluded.latency_delta_seconds,
      comparison_current_line = excluded.comparison_current_line,
      same_line = excluded.same_line,
      comparison_current_odds = excluded.comparison_current_odds,
      odds_delta = excluded.odds_delta,
      comparison_result = excluded.comparison_result,
      would_reduce_spend_signal = excluded.would_reduce_spend_signal,
      metadata = excluded.metadata,
      updated_at = now()
    returning 1
  )
  select count(*) into comparison_count from upserted;

  return query select webhook_count, snapshot_count, comparison_count;
end;
$$;;
