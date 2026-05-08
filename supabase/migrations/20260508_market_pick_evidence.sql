create table if not exists public.market_pick_evidence (
  id uuid primary key default gen_random_uuid(),
  slate_date date not null,
  pitcher text not null,
  normalized_pitcher text not null,
  side text not null check (side in ('over', 'under')),
  provider text not null check (provider in ('propline', 'boltodds')),
  current_verdict text not null,
  k_line numeric not null,
  current_odds integer,
  current_book text,
  game_time timestamptz,
  game_state text,
  is_fire boolean not null default false,
  is_locked boolean not null default false,
  observed_at timestamptz not null,
  latest_snapshot_at timestamptz not null,
  snapshot_count integer not null default 0 check (snapshot_count >= 0),
  book_count integer not null default 0 check (book_count >= 0),
  books_seen text[] not null default '{}',
  toward_pick_count integer not null default 0 check (toward_pick_count >= 0),
  away_from_pick_count integer not null default 0 check (away_from_pick_count >= 0),
  better_now_count integer not null default 0 check (better_now_count >= 0),
  worse_now_count integer not null default 0 check (worse_now_count >= 0),
  touching_pick_line_count integer not null default 0 check (touching_pick_line_count >= 0),
  market_consensus text not null default 'none' check (
    market_consensus in ('toward_pick', 'away_from_pick', 'mixed', 'none')
  ),
  bet_value_consensus text not null default 'none' check (
    bet_value_consensus in ('better_now', 'worse_now', 'mixed', 'none')
  ),
  minutes_to_game integer,
  time_window text not null default 'unknown' check (
    time_window in ('post_start', 'pre_5', 'pre_15', 'pre_30', 'pre_60', 'pre_120', 'early', 'unknown')
  ),
  source_artifact_path text not null,
  source_artifact_sha256 text,
  dedupe_key text not null unique,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (slate_date, normalized_pitcher, side, provider)
);

create index if not exists idx_market_pick_evidence_slate
  on public.market_pick_evidence (slate_date desc, provider, is_fire, observed_at desc);

create index if not exists idx_market_pick_evidence_window
  on public.market_pick_evidence (slate_date desc, time_window, market_consensus, bet_value_consensus);

alter table public.market_pick_evidence enable row level security;

comment on table public.market_pick_evidence is
  'Shadow-only per-pick market evidence rollup from live market snapshots. Not the official grading or model record.';
