create table if not exists public.shadow_pipeline_runs (
  id uuid primary key default gen_random_uuid(),
  run_key text not null unique,
  slate_date date not null,
  run_source text not null check (run_source in ('live_layer_shadow_timing')),
  observed_at timestamptz not null,
  artifact_generated_at timestamptz,
  source_artifact_path text not null,
  source_artifact_sha256 text,
  artifact_pitcher_count integer not null default 0 check (artifact_pitcher_count >= 0),
  tracked_pick_count integer not null default 0 check (tracked_pick_count >= 0),
  artifact_locked_pick_count integer not null default 0 check (artifact_locked_pick_count >= 0),
  due_now_count integer not null default 0 check (due_now_count >= 0),
  missed_lock_count integer not null default 0 check (missed_lock_count >= 0),
  started_unlocked_count integer not null default 0 check (started_unlocked_count >= 0),
  missing_game_time_count integer not null default 0 check (missing_game_time_count >= 0),
  metadata jsonb not null default '{}'::jsonb,
  inserted_at timestamptz not null default now()
);

create index if not exists idx_shadow_pipeline_runs_slate_observed
  on public.shadow_pipeline_runs (slate_date desc, observed_at desc);

create table if not exists public.shadow_pick_lock_observations (
  id uuid primary key default gen_random_uuid(),
  dedupe_key text not null unique,
  slate_date date not null,
  source_run_key text not null,
  status text not null check (
    status in (
      'not_due',
      'due_now',
      'missed_lock',
      'started_unlocked',
      'artifact_locked',
      'missing_game_time'
    )
  ),
  observed_at timestamptz not null,
  pitcher text not null,
  normalized_pitcher text not null,
  side text not null check (side in ('over', 'under')),
  current_verdict text not null,
  k_line numeric,
  current_odds integer,
  current_book text,
  game_time timestamptz,
  should_lock_at timestamptz,
  artifact_locked_at timestamptz,
  game_state text,
  minutes_until_start numeric,
  source_artifact_path text not null,
  source_artifact_sha256 text,
  metadata jsonb not null default '{}'::jsonb,
  inserted_at timestamptz not null default now()
);

create index if not exists idx_shadow_pick_lock_observations_slate_status
  on public.shadow_pick_lock_observations (slate_date desc, status, observed_at desc);

create index if not exists idx_shadow_pick_lock_observations_pitcher
  on public.shadow_pick_lock_observations (slate_date desc, normalized_pitcher, side);

alter table public.shadow_pipeline_runs enable row level security;
alter table public.shadow_pick_lock_observations enable row level security;

comment on table public.shadow_pipeline_runs is
  'Shadow-only Render live-layer timing summary. Used to compare GitHub artifact freshness and lock timing; not production truth.';

comment on table public.shadow_pick_lock_observations is
  'Shadow-only deduped pick timing observations by status. Used to identify due, missed, and started-unlocked picks without changing official picks or grading.';

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'bbe_ops_readonly') then
    execute 'grant select on public.shadow_pipeline_runs to bbe_ops_readonly';
    execute 'grant select on public.shadow_pick_lock_observations to bbe_ops_readonly';

    execute 'drop policy if exists bbe_ops_readonly_select_shadow_pipeline_runs on public.shadow_pipeline_runs';
    execute 'drop policy if exists bbe_ops_readonly_select_shadow_pick_lock_observations on public.shadow_pick_lock_observations';

    execute 'create policy bbe_ops_readonly_select_shadow_pipeline_runs on public.shadow_pipeline_runs for select to bbe_ops_readonly using (true)';
    execute 'create policy bbe_ops_readonly_select_shadow_pick_lock_observations on public.shadow_pick_lock_observations for select to bbe_ops_readonly using (true)';
  end if;
end $$;
