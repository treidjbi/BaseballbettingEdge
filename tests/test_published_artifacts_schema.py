from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260522_published_pipeline_artifacts.sql"
ALLOW_FANGRAPHS_CACHE_MIGRATION = (
    ROOT / "supabase" / "migrations" / "20260605015138_allow_fangraphs_cache_artifact_type.sql"
)


def test_published_pipeline_artifacts_schema_has_required_contract():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "create table if not exists public.published_pipeline_artifacts" in sql
    assert "artifact_key text not null unique" in sql
    assert "artifact_type text not null" in sql
    assert "payload jsonb not null" in sql
    assert "payload_sha256 text not null" in sql
    assert "generated_at timestamptz" in sql
    assert "published_at timestamptz not null default now()" in sql
    assert "source text not null" in sql
    assert "source_run_id text" in sql
    assert "source_commit_sha text" in sql
    assert "metadata jsonb not null default '{}'::jsonb" in sql


def test_published_pipeline_artifact_runs_schema_has_required_contract():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "create table if not exists public.pipeline_artifact_publication_runs" in sql
    assert "run_id text not null unique" in sql
    assert "source text not null" in sql
    assert "run_type text not null" in sql
    assert "slate_date date" in sql
    assert "status text not null" in sql
    assert "artifact_count integer not null default 0" in sql


def test_published_artifact_tables_are_rls_guarded():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "alter table public.published_pipeline_artifacts enable row level security" in sql
    assert "alter table public.pipeline_artifact_publication_runs enable row level security" in sql
    assert "grant select on public.published_pipeline_artifacts to bbe_ops_readonly" in sql
    assert "grant select on public.pipeline_artifact_publication_runs to bbe_ops_readonly" in sql


def test_published_pipeline_artifacts_schema_allows_fangraphs_cache_artifact():
    sql = ALLOW_FANGRAPHS_CACHE_MIGRATION.read_text(encoding="utf-8")

    assert "drop constraint if exists published_pipeline_artifacts_artifact_type_check" in sql
    assert "add constraint published_pipeline_artifacts_artifact_type_check" in sql
    assert "'fangraphs_cache'" in sql
