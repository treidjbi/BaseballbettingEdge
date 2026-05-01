create table if not exists public.market_provider_runs (
  id uuid primary key default gen_random_uuid(),
  provider text not null check (provider in ('therundown', 'the_odds', 'propline')),
  mode text not null check (mode in ('manual_probe', 'shadow_poll', 'webhook', 'test')),
  slate_date date,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  status text not null default 'started' check (status in ('started', 'completed', 'failed')),
  request_count integer not null default 0 check (request_count >= 0),
  target_event_count integer not null default 0 check (target_event_count >= 0),
  parsed_pitcher_prop_count integer not null default 0 check (parsed_pitcher_prop_count >= 0),
  books_seen text[] not null default '{}',
  error_message text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.market_events (
  id uuid primary key default gen_random_uuid(),
  provider text not null check (provider in ('therundown', 'the_odds', 'propline')),
  provider_event_id text not null,
  sport_key text not null default 'baseball_mlb',
  slate_date date,
  commence_time timestamptz,
  home_team text,
  away_team text,
  raw_event jsonb not null default '{}'::jsonb,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  unique (provider, provider_event_id)
);

create table if not exists public.market_snapshots (
  id uuid primary key default gen_random_uuid(),
  run_id uuid references public.market_provider_runs(id) on delete set null,
  provider text not null check (provider in ('therundown', 'the_odds', 'propline')),
  provider_event_id text not null,
  sport_key text not null default 'baseball_mlb',
  market_key text not null,
  bookmaker_key text not null,
  bookmaker_title text,
  player_name text not null,
  normalized_player_name text not null,
  side text not null check (side in ('over', 'under')),
  line numeric not null,
  american_odds integer not null,
  observed_at timestamptz not null default now(),
  book_updated_at timestamptz,
  source_payload jsonb not null default '{}'::jsonb,
  dedupe_key text not null unique,
  created_at timestamptz not null default now()
);

create table if not exists public.provider_coverage_audits (
  id uuid primary key default gen_random_uuid(),
  run_id uuid references public.market_provider_runs(id) on delete cascade,
  slate_date date not null,
  provider text not null check (provider in ('therundown', 'the_odds', 'propline')),
  target_books text[] not null default '{}',
  books_seen text[] not null default '{}',
  target_event_count integer not null default 0 check (target_event_count >= 0),
  parsed_pitcher_prop_count integer not null default 0 check (parsed_pitcher_prop_count >= 0),
  complete_pitcher_line_groups integer not null default 0 check (complete_pitcher_line_groups >= 0),
  same_line_overlap_count integer check (same_line_overlap_count >= 0),
  line_conflict_count integer check (line_conflict_count >= 0),
  missing_target_books text[] not null default '{}',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.propline_webhook_deliveries (
  id uuid primary key default gen_random_uuid(),
  prop_line_delivery_id text not null unique,
  prop_line_event text not null,
  prop_line_timestamp timestamptz not null,
  signature_valid boolean not null,
  processed boolean not null default false,
  processing_error text,
  payload jsonb not null,
  received_at timestamptz not null default now()
);

create index if not exists idx_market_snapshots_player_market
  on public.market_snapshots (normalized_player_name, market_key, observed_at desc);

create index if not exists idx_market_snapshots_event_market
  on public.market_snapshots (provider, provider_event_id, market_key, observed_at desc);

create index if not exists idx_market_snapshots_book
  on public.market_snapshots (bookmaker_key, observed_at desc);

create index if not exists idx_provider_coverage_audits_slate
  on public.provider_coverage_audits (slate_date desc, provider);

alter table public.market_provider_runs enable row level security;
alter table public.market_events enable row level security;
alter table public.market_snapshots enable row level security;
alter table public.provider_coverage_audits enable row level security;
alter table public.propline_webhook_deliveries enable row level security;

comment on table public.market_provider_runs is
  'Observation-only market provider runs. Not read by the production pipeline.';

comment on table public.market_snapshots is
  'Normalized player prop odds snapshots for market history, CLV, steam, and provider comparison.';

comment on table public.propline_webhook_deliveries is
  'Raw PropLine webhook inbox with delivery-id dedupe and HMAC validation status.';
