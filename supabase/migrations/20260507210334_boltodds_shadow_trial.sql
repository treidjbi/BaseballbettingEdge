alter table public.market_provider_runs
  drop constraint if exists market_provider_runs_provider_check;

alter table public.market_provider_runs
  add constraint market_provider_runs_provider_check
  check (provider in ('therundown', 'the_odds', 'propline', 'boltodds'));

alter table public.market_events
  drop constraint if exists market_events_provider_check;

alter table public.market_events
  add constraint market_events_provider_check
  check (provider in ('therundown', 'the_odds', 'propline', 'boltodds'));

alter table public.market_snapshots
  drop constraint if exists market_snapshots_provider_check;

alter table public.market_snapshots
  add constraint market_snapshots_provider_check
  check (provider in ('therundown', 'the_odds', 'propline', 'boltodds'));

alter table public.provider_coverage_audits
  drop constraint if exists provider_coverage_audits_provider_check;

alter table public.provider_coverage_audits
  add constraint provider_coverage_audits_provider_check
  check (provider in ('therundown', 'the_odds', 'propline', 'boltodds'));

alter table public.market_provider_runs
  drop constraint if exists market_provider_runs_mode_check;

alter table public.market_provider_runs
  add constraint market_provider_runs_mode_check
  check (
    mode in (
      'manual_probe',
      'shadow_poll',
      'webhook',
      'test',
      'discovery_probe',
      'shadow_stream'
    )
  );

create table if not exists public.market_feed_heartbeats (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  provider text not null check (provider in ('propline', 'boltodds')),
  mode text not null check (mode in ('shadow_poll', 'webhook', 'shadow_stream')),
  slate_date date not null,
  run_id uuid references public.market_provider_runs(id) on delete set null,
  observed_at timestamptz not null,
  last_message_at timestamptz,
  books_seen text[] not null default '{}',
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_market_feed_heartbeats_provider_observed
  on public.market_feed_heartbeats(provider, observed_at desc);

alter table public.market_feed_heartbeats enable row level security;

comment on table public.market_feed_heartbeats is
  'Shadow-only provider feed heartbeat observations for stream/webhook health. Not read by the production pipeline.';;
