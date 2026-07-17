alter table public.shadow_notification_candidates
  drop constraint if exists shadow_notification_candidates_provider_check;

alter table public.shadow_notification_candidates
  add constraint shadow_notification_candidates_provider_check
  check (provider in ('propline', 'boltodds', 'therundown', 'therundown_propline'));

alter table public.shadow_notification_candidates
  drop constraint if exists shadow_notification_candidates_candidate_type_check;

alter table public.shadow_notification_candidates
  add constraint shadow_notification_candidates_candidate_type_check
  check (
    candidate_type in (
      'market_confirmed_playable',
      'market_confirmed_worse_number',
      'better_number_market_fade',
      'mixed_market',
      'no_clear_signal',
      'ready_to_bet'
    )
  );
