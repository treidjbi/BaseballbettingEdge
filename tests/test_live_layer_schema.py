from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "supabase" / "migrations" / "20260506_live_layer_events.sql"


def test_live_layer_migration_file_exists():
    assert MIGRATION.exists()


def test_live_layer_migration_defines_required_tables():
    sql = MIGRATION.read_text(encoding="utf-8")

    for table in [
        "live_pick_state",
        "line_movement_events",
        "notification_events",
        "game_reminder_state",
    ]:
        assert f"create table if not exists public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql


def test_live_layer_migration_uses_required_uniques_and_view():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "dedupe_key text not null unique" in sql
    assert "unique (slate_date, normalized_pitcher, side)" in sql
    assert "create or replace view public.live_activity_feed" in sql
    assert "with (security_invoker = true)" in sql
