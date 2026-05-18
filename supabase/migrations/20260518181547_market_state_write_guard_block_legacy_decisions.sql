create or replace function public.suppress_duplicate_provider_arbitration_decision()
returns trigger
language plpgsql
as $$
begin
  if new.decision = 'selected'
     and new.reasons = '["selected"]'::jsonb
  then
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

alter function public.suppress_duplicate_provider_arbitration_decision()
  set search_path = public, pg_temp;
