alter function public.append_unique_jsonb_text_values(jsonb, text[])
  set search_path = public, pg_temp;

alter function public.guard_current_market_lines_before_update()
  set search_path = public, pg_temp;

alter function public.guard_official_market_lines_before_write()
  set search_path = public, pg_temp;

alter function public.suppress_duplicate_provider_arbitration_decision()
  set search_path = public, pg_temp;

alter function public.set_market_state_updated_at()
  set search_path = public, pg_temp;
