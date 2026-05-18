from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "supabase" / "migrations" / "20260507_boltodds_shadow_trial.sql"
RUN_ID_INDEX_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260507210435_boltodds_heartbeat_run_id_index.sql"
)
PROVIDER_HARDENING_MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260518_provider_runtime_hardening.sql"
)


def _assert_constraint_values(sql, table, constraint, column, values):
    drop_pattern = (
        rf"alter table public\.{table}\s+"
        rf"drop constraint if exists {constraint};"
    )
    add_pattern = (
        rf"alter table public\.{table}\s+"
        rf"add constraint {constraint}\s+"
        rf"check \(\s*{column} in \((?P<values>[^)]*)\)\s*\);"
    )

    assert re.search(drop_pattern, sql, re.IGNORECASE)

    match = re.search(add_pattern, sql, re.IGNORECASE)
    assert match is not None

    actual_values = set(re.findall(r"'([^']+)'", match.group("values")))
    assert actual_values == set(values)


def test_boltodds_migration_exists():
    assert MIGRATION.exists()


def test_boltodds_migration_extends_provider_checks():
    sql = MIGRATION.read_text(encoding="utf-8")

    for table in [
        "market_provider_runs",
        "market_events",
        "market_snapshots",
        "provider_coverage_audits",
    ]:
        _assert_constraint_values(
            sql,
            table,
            f"{table}_provider_check",
            "provider",
            ["therundown", "the_odds", "propline", "boltodds"],
        )

    _assert_constraint_values(
        sql,
        "market_provider_runs",
        "market_provider_runs_mode_check",
        "mode",
        [
            "manual_probe",
            "shadow_poll",
            "webhook",
            "test",
            "discovery_probe",
            "shadow_stream",
        ],
    )


def test_boltodds_migration_creates_feed_heartbeat_table():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "create table if not exists public.market_feed_heartbeats" in sql
    assert "provider text not null check (provider in ('propline', 'boltodds'))" in sql
    assert "mode text not null check (mode in ('shadow_poll', 'webhook', 'shadow_stream'))" in sql
    assert "slate_date date not null" in sql
    assert "run_id uuid references public.market_provider_runs(id) on delete set null" in sql
    assert "observed_at timestamptz not null" in sql
    assert "last_message_at" in sql
    assert "books_seen" in sql
    assert "metadata jsonb not null default '{}'::jsonb" in sql


def test_boltodds_heartbeat_run_id_index_migration_exists():
    assert RUN_ID_INDEX_MIGRATION.exists()
    sql = RUN_ID_INDEX_MIGRATION.read_text(encoding="utf-8")

    assert "create index if not exists idx_market_feed_heartbeats_run_id" in sql
    assert "on public.market_feed_heartbeats(run_id)" in sql


def test_provider_runtime_hardening_adds_market_read_indexes():
    assert PROVIDER_HARDENING_MIGRATION.exists()
    sql = PROVIDER_HARDENING_MIGRATION.read_text(encoding="utf-8")

    assert "idx_market_snapshots_provider_observed" in sql
    assert "on public.market_snapshots (provider, observed_at desc)" in sql
    assert "idx_market_snapshots_run_observed" in sql
    assert "on public.market_snapshots (run_id, observed_at desc)" in sql
    assert "idx_market_feed_heartbeats_slate_provider_observed" in sql
    assert "on public.market_feed_heartbeats (slate_date, provider, observed_at desc)" in sql
    assert "idx_market_provider_runs_slate_provider_created" in sql
    assert "on public.market_provider_runs (slate_date, provider, created_at desc)" in sql
