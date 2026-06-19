from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"
LIVE_LAYER_MIGRATION = MIGRATIONS_DIR / "20260506_live_layer_events.sql"
MARKET_EVIDENCE_MIGRATION = MIGRATIONS_DIR / "20260508173221_market_pick_evidence.sql"
MARKET_EVIDENCE_PROVIDER_MIGRATION = (
    MIGRATIONS_DIR / "20260619192355_allow_therundown_market_pick_evidence_provider.sql"
)
SHADOW_CANDIDATE_MIGRATION = MIGRATIONS_DIR / "20260508174842_shadow_notification_candidates.sql"
ACCEPTED_BETS_MIGRATION = MIGRATIONS_DIR / "20260508180728_accepted_bets_log.sql"
LIVE_MARKET_DISPLAY_MIGRATION = MIGRATIONS_DIR / "20260512205206_live_market_display_state.sql"
READONLY_SHADOW_POLICIES_MIGRATION = MIGRATIONS_DIR / "20260512213255_readonly_shadow_table_policies.sql"
PROVIDER_CUTOVER_MIGRATION = MIGRATIONS_DIR / "20260514160903_provider_cutover_market_state.sql"
NOTIFICATION_DIGEST_MIGRATION = MIGRATIONS_DIR / "20260604172500_notification_digest_event_types.sql"
MARKET_STATE_WRITE_GUARDS_MIGRATIONS = [
    MIGRATIONS_DIR / "20260518174018_market_state_write_guards.sql",
    MIGRATIONS_DIR / "20260518174322_market_state_write_guards_tighten_churn.sql",
    MIGRATIONS_DIR / "20260518174819_market_state_write_guards_fail_closed_legacy_selected.sql",
    MIGRATIONS_DIR / "20260518175106_market_state_write_guard_search_path.sql",
    MIGRATIONS_DIR / "20260518175711_market_state_write_guard_ignore_legacy_updates.sql",
    MIGRATIONS_DIR / "20260518180629_market_state_write_guard_block_legacy_selected_marker.sql",
    MIGRATIONS_DIR / "20260518181008_market_state_write_guard_current_throttle_10_min.sql",
    MIGRATIONS_DIR / "20260518181547_market_state_write_guard_block_legacy_decisions.sql",
]
MARKET_STATE_WRITE_GUARD_SEARCH_PATH_MIGRATION = (
    MIGRATIONS_DIR / "20260518175106_market_state_write_guard_search_path.sql"
)

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


def test_supabase_migrations_use_timestamped_versions():
    bad_names = sorted(
        path.name
        for path in MIGRATIONS_DIR.glob("20260518*.sql")
        if not re.match(r"^\d{14}_[a-z0-9_]+\.sql$", path.name)
    )

    assert bad_names == []


def test_local_market_state_guard_migrations_match_live_versions():
    expected_names = {
        "20260518174018_market_state_write_guards.sql",
        "20260518174322_market_state_write_guards_tighten_churn.sql",
        "20260518174819_market_state_write_guards_fail_closed_legacy_selected.sql",
        "20260518175106_market_state_write_guard_search_path.sql",
        "20260518175711_market_state_write_guard_ignore_legacy_updates.sql",
        "20260518180629_market_state_write_guard_block_legacy_selected_marker.sql",
        "20260518181008_market_state_write_guard_current_throttle_10_min.sql",
        "20260518181547_market_state_write_guard_block_legacy_decisions.sql",
        "20260518213238_provider_runtime_hardening.sql",
    }
    actual_names = {path.name for path in MIGRATIONS_DIR.glob("20260518*.sql")}

    assert expected_names <= actual_names


def test_live_layer_migration_file_exists():
    assert LIVE_LAYER_MIGRATION.exists()
    assert MARKET_EVIDENCE_MIGRATION.exists()
    assert MARKET_EVIDENCE_PROVIDER_MIGRATION.exists()
    assert SHADOW_CANDIDATE_MIGRATION.exists()
    assert ACCEPTED_BETS_MIGRATION.exists()
    assert LIVE_MARKET_DISPLAY_MIGRATION.exists()
    assert READONLY_SHADOW_POLICIES_MIGRATION.exists()
    assert NOTIFICATION_DIGEST_MIGRATION.exists()


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


def test_notification_digest_migration_allows_grouped_event_types():
    sql = NOTIFICATION_DIGEST_MIGRATION.read_text(encoding="utf-8")

    for event_type in [
        "start_window_digest",
        "new_fire_pick_digest",
        "pick_upgraded_digest",
        "pick_downgraded_digest",
    ]:
        assert event_type in sql

    assert "drop constraint if exists notification_events_event_type_check" in sql
    assert "add constraint notification_events_event_type_check" in sql


def test_live_layer_provider_migration_allows_active_sources():
    sql = MARKET_EVIDENCE_PROVIDER_MIGRATION.read_text(encoding="utf-8")

    for constraint_name in [
        "market_pick_evidence_provider_check",
        "live_market_display_state_provider_check",
        "shadow_notification_candidates_provider_check",
    ]:
        assert f"drop constraint if exists {constraint_name}" in sql
        assert f"add constraint {constraint_name}" in sql

    assert sql.count("provider in ('propline', 'boltodds', 'therundown')") == 3


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


def test_market_state_write_guards_prevent_duplicate_shadow_churn():
    sql = "\n".join(
        path.read_text(encoding="utf-8")
        for path in MARKET_STATE_WRITE_GUARDS_MIGRATIONS
    )

    assert "create trigger guard_current_market_lines_before_update" in sql
    assert "create trigger guard_official_market_lines_before_insert" in sql
    assert "create trigger guard_official_market_lines_before_update" in sql
    assert "new.ready_for_pipeline = false" in sql
    assert "missing_game_time" in sql
    assert "legacy_selected_contract" in sql
    assert "coalesce(new.arbitration_reasons, '[]'::jsonb) ? 'selected'" in sql
    assert "if tg_op = 'UPDATE' then" in sql
    assert "create trigger suppress_duplicate_provider_arbitration_decision" in sql
    assert "new.decision = 'selected'" in sql
    assert "old.updated_at > now() - interval '10 minutes'" in sql
    assert "existing.inserted_at >= now() - interval '2 minutes'" in sql


def test_market_state_write_guard_functions_pin_search_path():
    sql = MARKET_STATE_WRITE_GUARD_SEARCH_PATH_MIGRATION.read_text(encoding="utf-8")

    for function_name in [
        "append_unique_jsonb_text_values(jsonb, text[])",
        "guard_current_market_lines_before_update()",
        "guard_official_market_lines_before_write()",
        "suppress_duplicate_provider_arbitration_decision()",
        "set_market_state_updated_at()",
    ]:
        assert f"alter function public.{function_name}" in sql

    assert "set search_path = public, pg_temp" in sql
