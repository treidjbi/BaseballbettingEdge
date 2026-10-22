from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _migration() -> Path:
    matches = list((ROOT / "supabase" / "migrations").glob("*_alternative_pick_selection_state.sql"))
    assert len(matches) == 1, "Task 2 requires exactly one additive alternative-pick migration"
    return matches[0]


def test_schema_has_bounded_identity_display_evidence_and_frozen_provenance_contract():
    sql = _migration().read_text(encoding="utf-8").lower()
    for fragment in (
        "create table if not exists public.alternative_pick_selection_state",
        "game_identity text not null", "candidate_identity text not null",
        "candidate_became_current_at timestamptz not null",
        "family_states jsonb not null", "reason_codes jsonb not null",
        "source_artifact_sha256 text not null", "lock_artifact_sha256 text", "lock_source_artifact_path text",
        "selector_id text", "selector_fingerprint text not null",
        "evidence_observation_count integer not null", "checkpoint text not null",
        "unique (slate_date, game_identity, normalized_pitcher, side, bundle_id, checkpoint)",
        "checkpoint in ('provisional', 'frozen_pregame')",
        "side in ('over', 'under')", "length(source_artifact_sha256) = 64",
        "length(selector_fingerprint) = 64",
        "length(lock_artifact_sha256) = 64", "evidence_observation_count >= 0",
        "minutes_until_start is null or minutes_until_start >= 0",
        "frozen_at is null and lock_dedupe_key is null",
        "lock_source_artifact_path is null",
        "frozen_at is not null and lock_dedupe_key is not null",
        "lock_source_artifact_path is not null",
    ):
        assert fragment in sql


def test_schema_frozen_link_and_immutability_are_fail_closed_and_pregame_only():
    sql = _migration().read_text(encoding="utf-8").lower()
    for fragment in (
        "create function public.alternative_pick_selection_state_reject_frozen_mutation()",
        "old.checkpoint = 'frozen_pregame' or new.checkpoint = 'frozen_pregame'",
        "before update or delete on public.alternative_pick_selection_state",
        "create function public.alternative_pick_selection_state_validate_frozen_link()",
        "from public.operational_pick_locks as lock_row",
        "lock_row.dedupe_key = new.lock_dedupe_key",
        "lock_row.source_artifact_sha256 = new.lock_artifact_sha256",
        "lock_row.source_artifact_path = new.lock_source_artifact_path",
        "lock_row.locked_odds = new.official_odds",
        "lower(nullif(trim(lock_row.locked_book), '')) is not distinct from lower(nullif(trim(new.official_book), ''))",
        "lock_row.observed_at = new.locked_at", "new.observed_at = new.locked_at",
        "lock_row.metadata ->> 'team'", "lock_row.metadata ->> 'opp_team'",
        "new.frozen_at = new.locked_at", "new.observed_at = new.locked_at", "new.frozen_at >= new.game_time",
        "before insert on public.alternative_pick_selection_state",
    ):
        assert fragment in sql


def test_schema_rls_denies_browser_roles_and_grants_only_service_role_without_delete():
    sql = _migration().read_text(encoding="utf-8").lower()
    assert "alter table public.alternative_pick_selection_state enable row level security" in sql
    assert "revoke all privileges on table public.alternative_pick_selection_state from anon, authenticated" in sql
    assert "grant select, insert, update on table public.alternative_pick_selection_state to service_role" in sql
    assert "grant delete" not in sql
    assert "create policy" not in sql
