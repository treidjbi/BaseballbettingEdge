create table if not exists public.live_market_display_state (
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
  market_status text not null check (
    market_status in (
      'market_confirmed_playable',
      'market_confirmed_worse_number',
      'better_number_market_fade',
      'mixed_market',
      'no_clear_signal'
    )
  ),
  actionable_state text not null check (
    actionable_state in ('playable_now', 'number_worse', 'off_market', 'market_fade', 'mixed', 'monitor', 'stale')
  ),
  market_consensus text not null check (
    market_consensus in ('toward_pick', 'away_from_pick', 'mixed', 'none')
  ),
  bet_value_consensus text not null check (
    bet_value_consensus in ('better_now', 'worse_now', 'mixed', 'none')
  ),
  main_line numeric,
  main_line_books text[] not null default '{}',
  best_book text,
  best_line numeric,
  best_odds integer,
  best_is_off_market boolean not null default false,
  off_market_books jsonb not null default '[]'::jsonb,
  book_count integer not null default 0 check (book_count >= 0),
  books_seen text[] not null default '{}',
  book_rows jsonb not null default '[]'::jsonb,
  movement_events jsonb not null default '[]'::jsonb,
  latest_snapshot_at timestamptz not null,
  freshness_seconds integer not null default 0 check (freshness_seconds >= 0),
  freshness_status text not null check (freshness_status in ('fresh', 'stale')),
  broad_confirmation boolean not null default false,
  source_artifact_path text not null,
  source_artifact_sha256 text,
  dedupe_key text not null unique,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (slate_date, normalized_pitcher, side, provider)
);

create index if not exists idx_live_market_display_state_slate
  on public.live_market_display_state (slate_date desc, provider, is_fire, actionable_state, observed_at desc);

create index if not exists idx_live_market_display_state_actionable
  on public.live_market_display_state (slate_date desc, provider, actionable_state, freshness_status, broad_confirmation);

alter table public.live_market_display_state enable row level security;

comment on table public.live_market_display_state is
  'Shadow-only app-ready live market display state. Summarizes provider snapshots into consensus, best book, off-market, and freshness cues without changing picks or sending notifications.';

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'bbe_ops_readonly') then
    execute 'grant select on public.live_market_display_state to bbe_ops_readonly';
    execute 'drop policy if exists bbe_ops_readonly_select_live_market_display_state on public.live_market_display_state';
    execute 'create policy bbe_ops_readonly_select_live_market_display_state on public.live_market_display_state for select to bbe_ops_readonly using (true)';
  end if;
end $$;
