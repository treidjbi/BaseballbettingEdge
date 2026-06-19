alter table public.market_pick_evidence
  drop constraint if exists market_pick_evidence_provider_check;

alter table public.market_pick_evidence
  add constraint market_pick_evidence_provider_check
  check (provider in ('propline', 'boltodds', 'therundown'));

alter table public.live_market_display_state
  drop constraint if exists live_market_display_state_provider_check;

alter table public.live_market_display_state
  add constraint live_market_display_state_provider_check
  check (provider in ('propline', 'boltodds', 'therundown'));

alter table public.shadow_notification_candidates
  drop constraint if exists shadow_notification_candidates_provider_check;

alter table public.shadow_notification_candidates
  add constraint shadow_notification_candidates_provider_check
  check (provider in ('propline', 'boltodds', 'therundown'));
