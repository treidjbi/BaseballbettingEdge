from __future__ import annotations

import os
import shutil
import socket
import subprocess
from pathlib import Path

import pytest


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
    assert ") is true" in sql


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
        "jsonb_array_length(jsonb_path_query_array(",
        "evaluation_proof #>> '{decision,family_count}'",
        "evaluation_proof #> '{preclose,decisive_observation_tokens}' = evidence_observation_ids",
        "evaluation_proof #>> '{preclose,qualifying_observation_count}'",
        "evaluation_proof #>> '{preclose,first_observed_at}'",
        "evaluation_proof #>> '{preclose,last_observed_at}'",
        "evaluation_proof #>> '{preclose,freshness_status}' = evidence_freshness_status",
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


def _run_psql(psql: str, port: int, sql: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [psql, "-X", "-v", "ON_ERROR_STOP=1", "-h", "127.0.0.1", "-p", str(port), "-U", "postgres", "-d", "postgres"],
        input=sql, text=True, capture_output=True, timeout=30,
    )


@pytest.fixture(scope="module")
def isolated_postgres(tmp_path_factory):
    initdb = shutil.which("initdb")
    pg_ctl = shutil.which("pg_ctl")
    psql = shutil.which("psql")
    if not all((initdb, pg_ctl, psql)):
        pytest.skip("PostgreSQL binaries are required for migration behavior tests")
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        pytest.skip("initdb refuses to run as root")
    root = tmp_path_factory.mktemp("alt_pick_v2_pg")
    data = root / "data"
    log = root / "postgres.log"
    initialized = subprocess.run(
        [initdb, "-D", str(data), "-A", "trust", "--no-locale", "--encoding=UTF8", "-U", "postgres"],
        text=True, capture_output=True, timeout=60,
    )
    assert initialized.returncode == 0, initialized.stderr
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    started = subprocess.run(
        [pg_ctl, "-D", str(data), "-l", str(log), "-o", f"-F -h 127.0.0.1 -p {port}", "-w", "start"],
        text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60,
    )
    assert started.returncode == 0, log.read_text(encoding="utf-8", errors="replace") if log.exists() else "PostgreSQL did not start"
    try:
        bootstrap = """
create role anon;
create role authenticated;
create role service_role;
create table public.operational_pick_locks (
  dedupe_key text, slate_date date, normalized_pitcher text, side text,
  locked_k_line numeric, locked_odds integer, locked_book text,
  game_time timestamptz, status_at_capture text, locked_at timestamptz,
  observed_at timestamptz, should_lock_at timestamptz, minutes_until_start numeric,
  source_artifact_sha256 text, source_artifact_path text, metadata jsonb
);
"""
        applied = _run_psql(
            psql, port,
            bootstrap + V1_MIGRATION.read_text(encoding="utf-8") + V2_MIGRATION.read_text(encoding="utf-8"),
        )
        assert applied.returncode == 0, applied.stderr
        yield psql, port
    finally:
        subprocess.run(
            [pg_ctl, "-D", str(data), "-m", "fast", "-w", "stop"],
            text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60,
        )


def _omitted_proof_insert(bundle_id: str) -> str:
    return f"""
insert into public.alternative_pick_selection_state (
  slate_date, game_identity, candidate_identity, candidate_became_current_at,
  pitcher, normalized_pitcher, team, opp_team, game_time, side, model_k_line,
  provider_posture, bundle_id, selector_fingerprint, checkpoint,
  selection_status, family_states, family_count, reason_codes,
  source_artifact_path, source_artifact_sha256, source_artifact_byte_sha256,
  evidence_observation_ids, evidence_observation_count, evidence_freshness_status,
  observed_at
) values (
  '2026-07-22', 'game-{bundle_id}', 'candidate-{bundle_id}', '2026-07-22T19:55:00Z',
  'Test Pitcher', 'test pitcher', 'ARI', 'LAD', '2026-07-22T23:00:00Z', 'over', 6.5,
  'therundown', '{bundle_id}', '{'f' * 64}', 'provisional',
  'pending', '{{}}'::jsonb, 0, '[]'::jsonb,
  'dashboard/data/processed/today.json', '{'a' * 64}', '{'b' * 64}',
  '[]'::jsonb, 0, 'pending', '2026-07-22T20:10:00Z'
);
"""


def test_v2_omitted_proof_is_rejected_by_postgres_check(isolated_postgres):
    psql, port = isolated_postgres
    v1 = _run_psql(psql, port, _omitted_proof_insert("pregame_alternative_pick_methodology_v1"))
    v2 = _run_psql(psql, port, _omitted_proof_insert("pregame_alternative_pick_methodology_v2"))

    assert v1.returncode == 0, v1.stderr
    assert v2.returncode != 0
    assert "alternative_pick_selection_state_v2_evaluation_proof_check" in v2.stderr
