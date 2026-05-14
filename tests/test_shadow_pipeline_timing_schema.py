from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260514_shadow_pipeline_timing.sql"


def test_shadow_pipeline_timing_migration_defines_compact_shadow_tables():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "create table if not exists public.shadow_pipeline_runs" in sql
    assert "create table if not exists public.shadow_pick_lock_observations" in sql
    assert "run_key text not null unique" in sql
    assert "dedupe_key text not null unique" in sql
    assert "status text not null check" in sql
    assert "'missed_lock'" in sql
    assert "'started_unlocked'" in sql


def test_shadow_pipeline_timing_tables_are_rls_guarded_and_readonly_granted():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "alter table public.shadow_pipeline_runs enable row level security" in sql
    assert "alter table public.shadow_pick_lock_observations enable row level security" in sql
    assert "grant select on public.shadow_pipeline_runs to bbe_ops_readonly" in sql
    assert "grant select on public.shadow_pick_lock_observations to bbe_ops_readonly" in sql
    assert "bbe_ops_readonly_select_shadow_pipeline_runs" in sql
    assert "bbe_ops_readonly_select_shadow_pick_lock_observations" in sql
