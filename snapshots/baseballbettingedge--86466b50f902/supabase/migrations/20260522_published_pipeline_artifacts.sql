create table if not exists public.published_pipeline_artifacts (
  id uuid primary key default gen_random_uuid(),
  artifact_key text not null unique,
  artifact_type text not null check (
    artifact_type in (
      'today',
      'dated_slate',
      'index',
      'steam',
      'performance',
      'params',
      'preview_lines',
      'picks_history'
    )
  ),
  slate_date date,
  payload jsonb not null,
  payload_sha256 text not null,
  generated_at timestamptz,
  source text not null check (
    source in ('github_actions', 'render_pipeline', 'render_live_layer', 'manual_backfill')
  ),
  source_run_id text,
  source_commit_sha text,
  published_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_published_pipeline_artifacts_type_date
  on public.published_pipeline_artifacts (artifact_type, slate_date desc);

create index if not exists idx_published_pipeline_artifacts_published_at
  on public.published_pipeline_artifacts (published_at desc);

create table if not exists public.pipeline_artifact_publication_runs (
  id uuid primary key default gen_random_uuid(),
  run_id text not null unique,
  source text not null check (
    source in ('github_actions', 'render_pipeline', 'render_live_layer', 'manual_backfill')
  ),
  run_type text not null check (
    run_type in ('preview', 'grading', 'full', 'refresh', 'lock', 'manual_backfill')
  ),
  slate_date date,
  status text not null check (status in ('started', 'completed', 'failed')),
  artifact_count integer not null default 0,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  metadata jsonb not null default '{}'::jsonb
);

alter table public.published_pipeline_artifacts enable row level security;
alter table public.pipeline_artifact_publication_runs enable row level security;

comment on table public.published_pipeline_artifacts is
  'Canonical published dashboard JSON payloads during the GitHub artifact-exit migration.';

comment on table public.pipeline_artifact_publication_runs is
  'Publication run ledger for GitHub/Render artifact publishers.';

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'bbe_ops_readonly') then
    execute 'grant select on public.published_pipeline_artifacts to bbe_ops_readonly';
    execute 'grant select on public.pipeline_artifact_publication_runs to bbe_ops_readonly';

    execute 'drop policy if exists bbe_ops_readonly_select_published_pipeline_artifacts on public.published_pipeline_artifacts';
    execute 'create policy bbe_ops_readonly_select_published_pipeline_artifacts on public.published_pipeline_artifacts for select to bbe_ops_readonly using (true)';

    execute 'drop policy if exists bbe_ops_readonly_select_pipeline_artifact_publication_runs on public.pipeline_artifact_publication_runs';
    execute 'create policy bbe_ops_readonly_select_pipeline_artifact_publication_runs on public.pipeline_artifact_publication_runs for select to bbe_ops_readonly using (true)';
  end if;
end $$;
