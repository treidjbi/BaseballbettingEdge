from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
V1_MIGRATION = ROOT / "supabase" / "migrations" / "20260721222627_alternative_pick_selection_state.sql"
V2_MIGRATION = ROOT / "supabase" / "migrations" / "20260722230000_alternative_pick_v2_evaluation_proof.sql"


def _sql() -> str:
    return V2_MIGRATION.read_text(encoding="utf-8").lower()


def test_v1_missing_evaluation_proof_is_defaulted_by_compatibility_trigger():
    sql = _sql()

    for fragment in (
        "create or replace function public.default_alternative_pick_v1_evaluation_proof()",
        "set search_path = ''",
        "if new.bundle_id = 'pregame_alternative_pick_methodology_v1'",
        "and new.evaluation_proof is null then",
        "new.evaluation_proof := '{}'::jsonb",
        "before insert or update on public.alternative_pick_selection_state",
        "alternative_pick_selection_state_default_v1_proof",
    ):
        assert fragment in sql


def test_v2_missing_evaluation_proof_is_rejected_not_defaulted():
    sql = _sql()

    assert "evaluation_proof jsonb not null default '{}'::jsonb" in sql
    assert "if new.bundle_id = 'pregame_alternative_pick_methodology_v2'" not in sql
    assert "bundle_id <> 'pregame_alternative_pick_methodology_v2'" in sql
    assert "evaluation_proof ->> 'schema_version' = 'v2'" in sql
    assert "evaluation_proof ->> 'bundle_id' = bundle_id" in sql


def test_v2_migration_is_additive_bounded_and_v1_compatible():
    sql = _sql()

    assert sql.count("add column if not exists evaluation_proof") == 1
    assert "alternative_pick_selection_state_evaluation_proof_object_check" in sql
    assert "jsonb_typeof(evaluation_proof) = 'object'" in sql
    assert "alternative_pick_selection_state_evaluation_proof_size_check" in sql
    assert "octet_length(evaluation_proof::text) <= 32768" in sql
    assert "alternative_pick_selection_state_v2_evaluation_proof_check" in sql
    for fragment in (
        "evaluation_proof ->> 'selector_fingerprint' = selector_fingerprint",
        "evaluation_proof #>> '{candidate,candidate_identity}' = candidate_identity",
        "evaluation_proof #>> '{candidate,normalized_pitcher}' = normalized_pitcher",
        "evaluation_proof #>> '{candidate,side}' = side",
        "evaluation_proof #>> '{artifact,source_artifact_path}' = source_artifact_path",
        "evaluation_proof #>> '{artifact,source_artifact_sha256}' = source_artifact_sha256",
        "evaluation_proof #>> '{artifact,source_artifact_byte_sha256}' = source_artifact_byte_sha256",
        "evaluation_proof #> '{decision,family_states}' = family_states",
        "evaluation_proof #>> '{decision,selection_status}' = selection_status",
        "evaluation_proof #>> '{decision,selected_lane}' = 'consensus_core'",
        "selector_id = 'no_drag_distinct_family_consensus_core_v2'",
        "evaluation_proof #>> '{decision,selected_lane}' = 'reentry_expansion'",
        "selector_id = 'moderate_edge_quality_reentry_expansion_v2'",
        "evaluation_proof #>> '{decision,selected_lane}' is null and selector_id is null",
    ):
        assert fragment in sql
    assert "drop table" not in sql
    assert "delete from public.alternative_pick_selection_state" not in sql
    assert "update public.alternative_pick_selection_state" not in sql


def test_v2_migration_preserves_unique_rls_grants_and_frozen_triggers():
    v1_sql = V1_MIGRATION.read_text(encoding="utf-8").lower()
    v2_sql = _sql()

    for protected in (
        "unique (slate_date, game_identity, normalized_pitcher, side, bundle_id, checkpoint)",
        "alternative_pick_selection_state_reject_frozen_mutation",
        "alternative_pick_selection_state_validate_frozen_link",
        "enable row level security",
        "revoke all privileges on table public.alternative_pick_selection_state from anon, authenticated",
        "grant select, insert, update on table public.alternative_pick_selection_state to service_role",
    ):
        assert protected in v1_sql
    assert "drop constraint" not in v2_sql
    assert "disable row level security" not in v2_sql
    assert "grant " not in v2_sql
    assert "alternative_pick_selection_state_reject_frozen_mutation" not in v2_sql
    assert "alternative_pick_selection_state_validate_frozen_link" not in v2_sql
    assert v2_sql.count("create trigger") == 1
