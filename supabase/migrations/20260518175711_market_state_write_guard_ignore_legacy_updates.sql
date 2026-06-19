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
     and new.arbitration_reasons = '["selected"]'::jsonb then
    if tg_op = 'UPDATE' then
      return null;
    end if;
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

alter function public.guard_official_market_lines_before_write()
  set search_path = public, pg_temp;;
