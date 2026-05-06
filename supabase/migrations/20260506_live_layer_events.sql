create table if not exists public.live_pick_state (
  id uuid primary key default gen_random_uuid(),
  slate_date date not null,
  pitcher text not null,
  normalized_pitcher text not null,
  side text not null check (side in ('over', 'under')),
  current_verdict text not null,
  previous_verdict text,
  k_line numeric not null,
  current_odds integer,
  current_book text,
  game_time timestamptz,
  game_state text,
  is_fire boolean not null default false,
  is_locked boolean not null default false,
  source_artifact_path text not null,
  source_artifact_sha256 text,
  last_model_seen_at timestamptz not null default now(),
  last_event_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (slate_date, normalized_pitcher, side)
);

create table if not exists public.line_movement_events (
  id uuid primary key default gen_random_uuid(),
  slate_date date not null,
  normalized_pitcher text not null,
  pitcher text not null,
  side text not null check (side in ('over', 'under')),
  bookmaker_key text not null,
  previous_line numeric,
  current_line numeric not null,
  previous_odds integer,
  current_odds integer not null,
  movement_direction text not null check (
    movement_direction in ('with_model', 'against_model', 'neutral')
  ),
  movement_kind text not null check (
    movement_kind in ('line', 'odds', 'line_and_odds')
  ),
  observed_at timestamptz not null,
  dedupe_key text not null unique,
  source_snapshot_id uuid,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.notification_events (
  id uuid primary key default gen_random_uuid(),
  slate_date date,
  event_type text not null check (
    event_type in (
      'new_fire_pick',
      'pick_upgraded',
      'pick_downgraded',
      'line_moved_with_us',
      'line_moved_against_us',
      'game_reminder_due',
      'webhook_received',
      'source_degraded'
    )
  ),
  severity text not null default 'info' check (severity in ('info', 'watch', 'action')),
  title text not null,
  body text not null,
  url text not null default '/',
  dedupe_key text not null unique,
  payload jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now(),
  sent_at timestamptz,
  send_attempts integer not null default 0 check (send_attempts >= 0),
  last_send_error text,
  created_at timestamptz not null default now()
);

create table if not exists public.game_reminder_state (
  id uuid primary key default gen_random_uuid(),
  slate_date date not null,
  normalized_pitcher text not null,
  side text not null check (side in ('over', 'under')),
  reminder_window text not null check (
    reminder_window in ('75_min', '45_min', '25_min', '10_min')
  ),
  game_time timestamptz not null,
  due_at timestamptz not null,
  fired_at timestamptz,
  dedupe_key text not null unique,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create index if not exists idx_live_pick_state_slate
  on public.live_pick_state (slate_date desc, is_fire, updated_at desc);

create index if not exists idx_line_movement_events_slate
  on public.line_movement_events (slate_date desc, normalized_pitcher, observed_at desc);

create index if not exists idx_notification_events_unsent
  on public.notification_events (sent_at, occurred_at desc)
  where sent_at is null;

create index if not exists idx_game_reminder_state_due
  on public.game_reminder_state (due_at, fired_at)
  where fired_at is null;

alter table public.live_pick_state enable row level security;
alter table public.line_movement_events enable row level security;
alter table public.notification_events enable row level security;
alter table public.game_reminder_state enable row level security;

create or replace view public.live_activity_feed as
select
  id,
  slate_date,
  event_type,
  severity,
  title,
  body,
  url,
  occurred_at,
  payload
from public.notification_events
where occurred_at >= now() - interval '36 hours'
order by occurred_at desc;

comment on table public.live_pick_state is
  'Live-layer sidecar state for current pick status. Not the official grading record.';

comment on table public.line_movement_events is
  'Live-layer sidecar append-only movement facts. Not the official grading record.';

comment on table public.notification_events is
  'Live-layer sidecar durable notification queue. Not the official grading record.';

comment on table public.game_reminder_state is
  'Live-layer sidecar game reminder state. Not the official grading record.';

comment on view public.live_activity_feed is
  'Read-safe recent live-layer sidecar notification feed. Not the official grading record.';
