from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LIVE_LAYER_MIGRATION = ROOT / "supabase" / "migrations" / "20260506_live_layer_events.sql"
MARKET_EVIDENCE_MIGRATION = ROOT / "supabase" / "migrations" / "20260508_market_pick_evidence.sql"
SHADOW_CANDIDATE_MIGRATION = ROOT / "supabase" / "migrations" / "20260508_shadow_notification_candidates.sql"
ACCEPTED_BETS_MIGRATION = ROOT / "supabase" / "migrations" / "20260508_accepted_bets_log.sql"
LIVE_MARKET_DISPLAY_MIGRATION = ROOT / "supabase" / "migrations" / "20260512_live_market_display_state.sql"
READONLY_SHADOW_POLICIES_MIGRATION = ROOT / "supabase" / "migrations" / "20260512_readonly_shadow_table_policies.sql"
PROVIDER_CUTOVER_MIGRATION = ROOT / "supabase" / "migrations" / "20260513_provider_cutover_market_state.sql"

PROVIDER_CUTOVER_TABLES = [
    "current_market_lines",
    "official_market_lines",
    "market_opening_baselines",
    "provider_arbitration_decisions",
    "provider_request_usage_daily",
    "compact_market_line_movements",
]


def _migration_sql() -> str:
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            LIVE_LAYER_MIGRATION,
            MARKET_EVIDENCE_MIGRATION,
            SHADOW_CANDIDATE_MIGRATION,
            ACCEPTED_BETS_MIGRATION,
            LIVE_MARKET_DISPLAY_MIGRATION,
            READONLY_SHADOW_POLICIES_MIGRATION,
        ]
    )


def test_live_layer_migration_file_exists():
    assert LIVE_LAYER_MIGRATION.exists()
    assert MARKET_EVIDENCE_MIGRATION.exists()
    assert SHADOW_CANDIDATE_MIGRATION.exists()
    assert ACCEPTED_BETS_MIGRATION.exists()
    assert LIVE_MARKET_DISPLAY_MIGRATION.exists()
    assert READONLY_SHADOW_POLICIES_MIGRATION.exists()


def test_live_layer_migration_defines_required_tables():
    sql = _migration_sql()

    for table in [
        "live_pick_state",
        "line_movement_events",
        "market_pick_evidence",
        "shadow_notification_candidates",
        "live_market_display_state",
        "notification_events",
        "game_reminder_state",
        "accepted_bets",
    ]:
        assert f"create table if not exists public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql


def test_live_layer_migration_uses_required_uniques_and_view():
    sql = _migration_sql()

    assert "dedupe_key text not null unique" in sql
    assert "unique (slate_date, normalized_pitcher, side)" in sql
    assert "unique (slate_date, normalized_pitcher, side, provider)" in sql
    assert "candidate_action in ('would_send_shadow', 'suppress_shadow')" in sql
    assert "actionable_state in ('playable_now', 'number_worse', 'off_market', 'market_fade', 'mixed', 'monitor', 'stale')" in sql
    assert "source in ('dashboard_manual', 'notification', 'shadow_candidate', 'other')" in sql
    assert "unique (slate_date, normalized_pitcher, side, book, k_line, odds)" in sql
    assert "create or replace view public.live_activity_feed" in sql
    assert "with (security_invoker = true)" in sql


def test_shadow_tables_have_readonly_rls_policies():
    sql = _migration_sql()

    assert "grant select on public.market_pick_evidence to bbe_ops_readonly" in sql
    assert "grant select on public.shadow_notification_candidates to bbe_ops_readonly" in sql
    assert "bbe_ops_readonly_select_market_pick_evidence" in sql
    assert "bbe_ops_readonly_select_shadow_notification_candidates" in sql


def test_provider_cutover_tables_have_rls_and_readonly_policies():
    sql = PROVIDER_CUTOVER_MIGRATION.read_text(encoding="utf-8")

    for table in PROVIDER_CUTOVER_TABLES:
        assert f"create table if not exists public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql
        assert f"grant select on public.{table} to bbe_ops_readonly" in sql
        assert f"drop policy if exists bbe_ops_readonly_select_{table} on public.{table}" in sql
        assert f"create policy bbe_ops_readonly_select_{table} on public.{table} for select to bbe_ops_readonly using (true)" in sql

    assert "if exists (select 1 from pg_roles where rolname = 'bbe_ops_readonly')" in sql
    assert "over_snapshot_id uuid" in sql
    assert "under_snapshot_id uuid" in sql
    assert "source_line_id uuid" in sql
    assert "create or replace function public.set_market_state_updated_at()" in sql
    assert "create trigger set_current_market_lines_updated_at" in sql
