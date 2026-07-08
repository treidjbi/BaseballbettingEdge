alter table public.live_market_display_state
  drop constraint if exists live_market_display_state_provider_check;

alter table public.live_market_display_state
  add constraint live_market_display_state_provider_check
  check (provider in ('propline', 'boltodds', 'therundown', 'therundown_propline'));
