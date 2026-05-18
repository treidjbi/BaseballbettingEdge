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

  if old.updated_at > now() - interval '10 minutes'
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

alter function public.guard_current_market_lines_before_update()
  set search_path = public, pg_temp;
