create table if not exists public.accepted_bets (
  id uuid primary key default gen_random_uuid(),
  slate_date date not null,
  pitcher text not null,
  normalized_pitcher text not null,
  side text not null check (side in ('over', 'under')),
  verdict text,
  k_line numeric not null,
  odds integer not null,
  book text not null,
  units numeric not null default 1 check (units > 0),
  game_time timestamptz,
  source text not null default 'dashboard_manual' check (
    source in ('dashboard_manual', 'notification', 'shadow_candidate', 'other')
  ),
  notification_event_id uuid,
  shadow_candidate_id uuid,
  model_snapshot jsonb not null default '{}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  dedupe_key text not null unique,
  accepted_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique (slate_date, normalized_pitcher, side, book, k_line, odds)
);

create index if not exists idx_accepted_bets_slate
  on public.accepted_bets (slate_date desc, accepted_at desc);

create index if not exists idx_accepted_bets_pitcher
  on public.accepted_bets (slate_date desc, normalized_pitcher, side);

alter table public.accepted_bets enable row level security;

comment on table public.accepted_bets is
  'Manual accepted-bet log. Additive analytics sidecar; does not affect picks, grading, staking, providers, or notifications.';;
