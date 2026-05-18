create index if not exists idx_provider_arbitration_decisions_dedupe
  on public.provider_arbitration_decisions (
    slate_date,
    normalized_player_name,
    market_key,
    decision,
    inserted_at desc
  );

create or replace function public.append_unique_jsonb_text_values(existing jsonb, additions text[])
returns jsonb
language sql
immutable
as $$
  select coalesce(jsonb_agg(value order by first_seen), '[]'::jsonb)
  from (
    select value, min(position) as first_seen
    from (
      select value::text, position
      from jsonb_array_elements_text(coalesce(existing, '[]'::jsonb)) with ordinality as existing_values(value, position)
      union all
      select addition, 1000000 + position
      from unnest(additions) with ordinality as addition_values(addition, position)
    ) combined_values
    group by value
  ) unique_values;
$$;

create or replace function public.guard_current_market_lines_before_update()
returns trigger
language plpgsql
as $$
begin
  if nullif(btrim(coalesce(old.game_time, '')), '') is not null
     and nullif(btrim(coalesce(new.game_time, '')), '') is null then
    new.game_time = old.game_time;
    if coalesce(old.raw_payload, '{}'::jsonb) ? 'game_time_source' then
      new.raw_payload = jsonb_set(
        coalesce(new.raw_payload, '{}'::jsonb),
        '{game_time_source}',
        old.raw_payload -> 'game_time_source',
        true
      );
    end if;
  end if;

  if old.updated_at > now() - interval '2 minutes'
     and new.slate_date is not distinct from old.slate_date
     and new.provider is not distinct from old.provider
     and new.book_key is not distinct from old.book_key
     and new.book_name is not distinct from old.book_name
     and new.event_id is not distinct from old.event_id
     and new.provider_event_id is not distinct from old.provider_event_id
     and new.game_time is not distinct from old.game_time
     and new.player_name is not distinct from old.player_name
     and new.normalized_player_name is not distinct from old.normalized_player_name
     and new.market_key is not distinct from old.market_key
     and new.line is not distinct from old.line
     and new.over_odds is not distinct from old.over_odds
     and new.under_odds is not distinct from old.under_odds
     and new.is_complete is not distinct from old.is_complete
     and new.quality_flags is not distinct from old.quality_flags then
    return null;
  end if;

  return new;
end;
$$;

drop trigger if exists guard_current_market_lines_before_update on public.current_market_lines;
create trigger guard_current_market_lines_before_update
  before update on public.current_market_lines
  for each row execute function public.guard_current_market_lines_before_update();

create or replace function public.guard_official_market_lines_before_write()
returns trigger
language plpgsql
as $$
begin
  if tg_op = 'UPDATE'
     and nullif(btrim(coalesce(old.game_time, '')), '') is not null
     and nullif(btrim(coalesce(new.game_time, '')), '') is null then
    new.game_time = old.game_time;
  end if;

  if new.ready_for_pipeline
     and nullif(btrim(coalesce(new.game_time, '')), '') is null then
    new.ready_for_pipeline = false;
    new.quality_flags = public.append_unique_jsonb_text_values(
      new.quality_flags,
      array['not_ready_for_pipeline', 'missing_game_time']
    );
    new.arbitration_reasons = public.append_unique_jsonb_text_values(
      new.arbitration_reasons,
      array['missing_game_time']
    );
  end if;

  if new.ready_for_pipeline
     and new.arbitration_reasons = '["selected"]'::jsonb then
    new.ready_for_pipeline = false;
    new.quality_flags = public.append_unique_jsonb_text_values(
      new.quality_flags,
      array['not_ready_for_pipeline', 'legacy_selected_contract']
    );
    new.arbitration_reasons = public.append_unique_jsonb_text_values(
      new.arbitration_reasons,
      array['legacy_selected_contract']
    );
  end if;

  if tg_op = 'UPDATE'
     and old.updated_at > now() - interval '2 minutes'
     and nullif(btrim(coalesce(new.game_time, '')), '') is null
     and not new.ready_for_pipeline
     and not old.ready_for_pipeline then
    return null;
  end if;

  if tg_op = 'UPDATE'
     and old.updated_at > now() - interval '2 minutes'
     and (to_jsonb(new) - 'updated_at' - 'freshness_seconds')
       = (to_jsonb(old) - 'updated_at' - 'freshness_seconds') then
    return null;
  end if;

  return new;
end;
$$;

drop trigger if exists guard_official_market_lines_before_insert on public.official_market_lines;
create trigger guard_official_market_lines_before_insert
  before insert on public.official_market_lines
  for each row execute function public.guard_official_market_lines_before_write();

drop trigger if exists guard_official_market_lines_before_update on public.official_market_lines;
create trigger guard_official_market_lines_before_update
  before update on public.official_market_lines
  for each row execute function public.guard_official_market_lines_before_write();

create or replace function public.suppress_duplicate_provider_arbitration_decision()
returns trigger
language plpgsql
as $$
begin
  if new.decision = 'selected'
     and new.reasons = '["selected"]'::jsonb
     and exists (
       select 1
       from public.provider_arbitration_decisions existing
       where existing.slate_date = new.slate_date
         and existing.normalized_player_name = new.normalized_player_name
         and existing.market_key = new.market_key
         and existing.decision = new.decision
         and existing.reasons = new.reasons
         and existing.inserted_at >= now() - interval '10 minutes'
       limit 1
     ) then
    return null;
  end if;

  if exists (
    select 1
    from public.provider_arbitration_decisions existing
    where existing.slate_date = new.slate_date
      and existing.normalized_player_name = new.normalized_player_name
      and existing.market_key = new.market_key
      and existing.decision is not distinct from new.decision
      and existing.selected_provider is not distinct from new.selected_provider
      and existing.selected_book_key is not distinct from new.selected_book_key
      and existing.selected_line is not distinct from new.selected_line
      and existing.reasons = new.reasons
      and existing.missing_book_keys = new.missing_book_keys
      and existing.source_line_ids = new.source_line_ids
      and existing.inserted_at >= now() - interval '2 minutes'
    limit 1
  ) then
    return null;
  end if;

  return new;
end;
$$;

drop trigger if exists suppress_duplicate_provider_arbitration_decision on public.provider_arbitration_decisions;
create trigger suppress_duplicate_provider_arbitration_decision
  before insert on public.provider_arbitration_decisions
  for each row execute function public.suppress_duplicate_provider_arbitration_decision();
