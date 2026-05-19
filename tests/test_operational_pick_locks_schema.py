from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260519_operational_pick_locks.sql"


def test_operational_pick_locks_schema_has_required_contract():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "create table if not exists public.operational_pick_locks" in sql
    assert "dedupe_key text not null unique" in sql
    assert "slate_date date not null" in sql
    assert "normalized_pitcher text not null" in sql
    assert "side text not null check (side in ('over', 'under'))" in sql
    assert "status_at_capture text not null check (status_at_capture in ('due_now', 'missed_lock'))" in sql
    assert "observed_at timestamptz not null" in sql
    assert "locked_at timestamptz not null" in sql
    assert "game_time timestamptz not null" in sql
    assert "should_lock_at timestamptz not null" in sql
    assert "source_artifact_sha256 text" in sql
    assert "metadata jsonb not null default '{}'::jsonb" in sql


def test_operational_pick_locks_schema_is_rls_guarded():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "alter table public.operational_pick_locks enable row level security" in sql
    assert "if exists (select 1 from pg_roles where rolname = 'bbe_ops_readonly')" in sql
    assert "grant select on public.operational_pick_locks to bbe_ops_readonly" in sql
    assert "drop policy if exists bbe_ops_readonly_select_operational_pick_locks" in sql
    assert "bbe_ops_readonly_select_operational_pick_locks" in sql
    assert (
        "create policy bbe_ops_readonly_select_operational_pick_locks "
        "on public.operational_pick_locks for select to bbe_ops_readonly using (true)"
    ) in sql
