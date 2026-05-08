alter table public.market_pick_evidence
  add column if not exists reversal_book_count integer not null default 0 check (reversal_book_count >= 0),
  add column if not exists volatile_book_count integer not null default 0 check (volatile_book_count >= 0);

create table if not exists public.shadow_notification_candidates (
  id uuid primary key default gen_random_uuid(),
  slate_date date not null,
  pitcher text not null,
  normalized_pitcher text not null,
  side text not null check (side in ('over', 'under')),
  provider text not null check (provider in ('propline', 'boltodds')),
  current_verdict text not null,
  k_line numeric not null,
  candidate_type text not null check (
    candidate_type in (
      'market_confirmed_playable',
      'market_confirmed_worse_number',
      'better_number_market_fade',
      'mixed_market',
      'no_clear_signal'
    )
  ),
  candidate_action text not null check (
    candidate_action in ('would_send_shadow', 'suppress_shadow')
  ),
  playable_state text not null check (
    playable_state in ('playable_now', 'number_worse', 'line_not_seen', 'line_seen')
  ),
  market_consensus text not null check (
    market_consensus in ('toward_pick', 'away_from_pick', 'mixed', 'none')
  ),
  bet_value_consensus text not null check (
    bet_value_consensus in ('better_now', 'worse_now', 'mixed', 'none')
  ),
  time_window text not null check (
    time_window in ('post_start', 'pre_5', 'pre_15', 'pre_30', 'pre_60', 'pre_120', 'early', 'unknown')
  ),
  minutes_to_game integer,
  book_count integer not null default 0 check (book_count >= 0),
  books_seen text[] not null default '{}',
  broad_confirmation boolean not null default false,
  single_book boolean not null default false,
  betrivers_only boolean not null default false,
  reversal_book_count integer not null default 0 check (reversal_book_count >= 0),
  volatile_book_count integer not null default 0 check (volatile_book_count >= 0),
  suppression_reasons text[] not null default '{}',
  evidence_dedupe_key text,
  occurred_at timestamptz not null,
  dedupe_key text not null unique,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_shadow_notification_candidates_slate
  on public.shadow_notification_candidates (slate_date desc, provider, candidate_action, occurred_at desc);

create index if not exists idx_shadow_notification_candidates_quality
  on public.shadow_notification_candidates (slate_date desc, candidate_type, time_window, broad_confirmation);

alter table public.shadow_notification_candidates enable row level security;

comment on table public.shadow_notification_candidates is
  'Shadow-only would-have-sent notification candidates. These rows never trigger real push notifications.';
