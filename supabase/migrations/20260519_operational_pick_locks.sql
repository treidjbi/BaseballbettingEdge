create table if not exists public.operational_pick_locks (
  id uuid primary key default gen_random_uuid(),
  dedupe_key text not null unique,
  slate_date date not null,
  source text not null default 'live_layer',
  status_at_capture text not null check (status_at_capture in ('due_now', 'missed_lock')),
  observed_at timestamptz not null,
  locked_at timestamptz not null,
  pitcher text not null,
  normalized_pitcher text not null,
  side text not null check (side in ('over', 'under')),
  locked_verdict text not null,
  locked_k_line numeric not null,
  locked_odds integer not null,
  locked_adj_ev numeric,
  locked_book text,
  game_time timestamptz not null,
  should_lock_at timestamptz not null,
  minutes_until_start numeric,
  source_artifact_path text not null,
  source_artifact_sha256 text,
  consumed_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  inserted_at timestamptz not null default now()
);

create index if not exists idx_operational_pick_locks_slate
  on public.operational_pick_locks (slate_date desc, inserted_at desc);

create index if not exists idx_operational_pick_locks_pick
  on public.operational_pick_locks (slate_date desc, normalized_pitcher, side);

alter table public.operational_pick_locks enable row level security;

comment on table public.operational_pick_locks is
  'Gated operational lock intent rows captured by the live layer before first pitch. Consumed by GitHub pipeline only when ENABLE_SUPABASE_LOCK_CONSUMER=true.';

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'bbe_ops_readonly') then
    execute 'grant select on public.operational_pick_locks to bbe_ops_readonly';
    execute 'drop policy if exists bbe_ops_readonly_select_operational_pick_locks on public.operational_pick_locks';
    execute 'create policy bbe_ops_readonly_select_operational_pick_locks on public.operational_pick_locks for select to bbe_ops_readonly using (true)';
  end if;
end $$;
