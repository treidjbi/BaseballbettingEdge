create table if not exists public.current_market_lines (
  id bigserial primary key,
  slate_date date not null,
  provider text not null check (provider in ('boltodds', 'propline', 'the_odds', 'therundown')),
  book_key text not null,
  book_name text not null,
  event_id text,
  provider_event_id text,
  player_name text not null,
  normalized_player_name text not null,
  market_key text not null default 'pitcher_strikeouts',
  line numeric not null,
  over_odds integer,
  under_odds integer,
  over_snapshot_id uuid,
  under_snapshot_id uuid,
  first_seen_at timestamptz,
  last_seen_at timestamptz not null,
  source_run_id uuid,
  is_complete boolean not null default false,
  freshness_seconds integer check (freshness_seconds is null or freshness_seconds >= 0),
  quality_flags jsonb not null default '[]'::jsonb,
  raw_payload jsonb not null default '{}'::jsonb,
  inserted_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (slate_date, provider, book_key, normalized_player_name, market_key, line)
);

create index if not exists idx_current_market_lines_slate_provider
  on public.current_market_lines (slate_date, provider, updated_at desc);

create index if not exists idx_current_market_lines_player
  on public.current_market_lines (slate_date, normalized_player_name, market_key);

create table if not exists public.official_market_lines (
  id bigserial primary key,
  slate_date date not null,
  normalized_player_name text not null,
  player_name text not null,
  market_key text not null default 'pitcher_strikeouts',
  ref_book_key text,
  ref_book_name text,
  ref_line numeric,
  ref_over_odds integer,
  ref_under_odds integer,
  selected_provider text check (selected_provider in ('boltodds', 'propline', 'the_odds', 'therundown')),
  selected_source text not null,
  book_odds jsonb not null default '{}'::jsonb,
  provider_coverage jsonb not null default '{}'::jsonb,
  arbitration_reasons jsonb not null default '[]'::jsonb,
  quality_flags jsonb not null default '[]'::jsonb,
  freshness_seconds integer check (freshness_seconds is null or freshness_seconds >= 0),
  stale_after_seconds integer not null default 900 check (stale_after_seconds > 0),
  current_market_line_ids jsonb not null default '[]'::jsonb,
  ready_for_pipeline boolean not null default false,
  inserted_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (slate_date, normalized_player_name, market_key)
);

create index if not exists idx_official_market_lines_slate_ready
  on public.official_market_lines (slate_date, ready_for_pipeline, updated_at desc);

create table if not exists public.market_opening_baselines (
  id bigserial primary key,
  slate_date date not null,
  normalized_player_name text not null,
  player_name text not null,
  market_key text not null default 'pitcher_strikeouts',
  book_key text not null,
  book_name text not null,
  line numeric not null,
  opening_over_odds integer,
  opening_under_odds integer,
  opening_provider text not null check (opening_provider in ('boltodds', 'propline', 'the_odds', 'therundown')),
  opening_source text not null,
  first_seen_at timestamptz not null,
  source_line_id uuid,
  inserted_at timestamptz not null default now(),
  unique (slate_date, normalized_player_name, market_key, book_key, line)
);

create index if not exists idx_market_opening_baselines_slate
  on public.market_opening_baselines (slate_date, normalized_player_name, book_key);

create table if not exists public.provider_arbitration_decisions (
  id bigserial primary key,
  slate_date date not null,
  normalized_player_name text not null,
  market_key text not null default 'pitcher_strikeouts',
  selected_provider text,
  selected_book_key text,
  selected_line numeric,
  decision text not null,
  reasons jsonb not null default '[]'::jsonb,
  candidate_count integer not null default 0 check (candidate_count >= 0),
  stale_candidate_count integer not null default 0 check (stale_candidate_count >= 0),
  missing_book_keys jsonb not null default '[]'::jsonb,
  source_line_ids jsonb not null default '[]'::jsonb,
  inserted_at timestamptz not null default now()
);

create index if not exists idx_provider_arbitration_decisions_slate
  on public.provider_arbitration_decisions (slate_date, inserted_at desc);

create table if not exists public.provider_request_usage_daily (
  usage_date date not null,
  provider text not null,
  request_count integer not null default 0 check (request_count >= 0),
  snapshot_count integer not null default 0 check (snapshot_count >= 0),
  source text not null,
  inserted_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (usage_date, provider, source)
);

create index if not exists idx_provider_request_usage_daily_provider
  on public.provider_request_usage_daily (provider, usage_date desc);

create table if not exists public.compact_market_line_movements (
  id bigserial primary key,
  slate_date date not null,
  provider text not null check (provider in ('boltodds', 'propline', 'the_odds', 'therundown')),
  book_key text not null,
  normalized_player_name text not null,
  player_name text not null,
  market_key text not null default 'pitcher_strikeouts',
  side text not null check (side in ('over', 'under')),
  line numeric not null,
  first_seen_at timestamptz not null,
  last_seen_at timestamptz not null,
  first_odds integer,
  last_odds integer,
  min_odds integer,
  max_odds integer,
  odds_move_count integer not null default 0 check (odds_move_count >= 0),
  snapshot_count integer not null default 0 check (snapshot_count >= 0),
  source_snapshot_ids jsonb not null default '[]'::jsonb,
  inserted_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (slate_date, provider, book_key, normalized_player_name, market_key, side, line)
);

create index if not exists idx_compact_market_line_movements_slate_provider
  on public.compact_market_line_movements (slate_date, provider, book_key, normalized_player_name);

alter table public.current_market_lines enable row level security;
alter table public.official_market_lines enable row level security;
alter table public.market_opening_baselines enable row level security;
alter table public.provider_arbitration_decisions enable row level security;
alter table public.provider_request_usage_daily enable row level security;
alter table public.compact_market_line_movements enable row level security;

comment on table public.current_market_lines is
  'Derived current complete book lines from raw provider snapshots. Input to official market arbitration; not a raw evidence table.';

comment on table public.official_market_lines is
  'Provider-arbitrated official market feed for the GitHub pipeline after cutover. Replaces direct raw provider reads, not model math.';

comment on table public.market_opening_baselines is
  'First usable provider baselines for preview/opening line semantics. Rows are preserved and not overwritten by later refreshes.';

comment on table public.provider_arbitration_decisions is
  'Audit log explaining selected, skipped, stale, missing, and conflicting provider-line decisions.';

comment on table public.provider_request_usage_daily is
  'Daily provider request and snapshot counts used to enforce PropLine and provider-cost guardrails.';

comment on table public.compact_market_line_movements is
  'Compact per-slate/provider/book/player movement summaries retained after raw snapshot history ages out.';

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'bbe_ops_readonly') then
    execute 'grant select on public.current_market_lines to bbe_ops_readonly';
    execute 'grant select on public.official_market_lines to bbe_ops_readonly';
    execute 'grant select on public.market_opening_baselines to bbe_ops_readonly';
    execute 'grant select on public.provider_arbitration_decisions to bbe_ops_readonly';
    execute 'grant select on public.provider_request_usage_daily to bbe_ops_readonly';
    execute 'grant select on public.compact_market_line_movements to bbe_ops_readonly';

    execute 'drop policy if exists bbe_ops_readonly_select_current_market_lines on public.current_market_lines';
    execute 'drop policy if exists bbe_ops_readonly_select_official_market_lines on public.official_market_lines';
    execute 'drop policy if exists bbe_ops_readonly_select_market_opening_baselines on public.market_opening_baselines';
    execute 'drop policy if exists bbe_ops_readonly_select_provider_arbitration_decisions on public.provider_arbitration_decisions';
    execute 'drop policy if exists bbe_ops_readonly_select_provider_request_usage_daily on public.provider_request_usage_daily';
    execute 'drop policy if exists bbe_ops_readonly_select_compact_market_line_movements on public.compact_market_line_movements';

    execute 'create policy bbe_ops_readonly_select_current_market_lines on public.current_market_lines for select to bbe_ops_readonly using (true)';
    execute 'create policy bbe_ops_readonly_select_official_market_lines on public.official_market_lines for select to bbe_ops_readonly using (true)';
    execute 'create policy bbe_ops_readonly_select_market_opening_baselines on public.market_opening_baselines for select to bbe_ops_readonly using (true)';
    execute 'create policy bbe_ops_readonly_select_provider_arbitration_decisions on public.provider_arbitration_decisions for select to bbe_ops_readonly using (true)';
    execute 'create policy bbe_ops_readonly_select_provider_request_usage_daily on public.provider_request_usage_daily for select to bbe_ops_readonly using (true)';
    execute 'create policy bbe_ops_readonly_select_compact_market_line_movements on public.compact_market_line_movements for select to bbe_ops_readonly using (true)';
  end if;
end $$;

create or replace function public.set_market_state_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists set_current_market_lines_updated_at on public.current_market_lines;
create trigger set_current_market_lines_updated_at
  before update on public.current_market_lines
  for each row execute function public.set_market_state_updated_at();

drop trigger if exists set_official_market_lines_updated_at on public.official_market_lines;
create trigger set_official_market_lines_updated_at
  before update on public.official_market_lines
  for each row execute function public.set_market_state_updated_at();

drop trigger if exists set_provider_request_usage_daily_updated_at on public.provider_request_usage_daily;
create trigger set_provider_request_usage_daily_updated_at
  before update on public.provider_request_usage_daily
  for each row execute function public.set_market_state_updated_at();

drop trigger if exists set_compact_market_line_movements_updated_at on public.compact_market_line_movements;
create trigger set_compact_market_line_movements_updated_at
  before update on public.compact_market_line_movements
  for each row execute function public.set_market_state_updated_at();
