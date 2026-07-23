from __future__ import annotations

import os
import json
import shutil
import socket
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
V1_MIGRATION = ROOT / "supabase" / "migrations" / "20260721222627_alternative_pick_selection_state.sql"
V2_MIGRATION = ROOT / "supabase" / "migrations" / "20260722230000_alternative_pick_v2_evaluation_proof.sql"
LEAST_PRIVILEGE_MIGRATION = ROOT / "supabase" / "migrations" / "20260723210000_alternative_pick_selection_least_privilege.sql"


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
        "evaluation_proof #>> '{normalized_inputs,pitcher}' = normalized_pitcher",
        "evaluation_proof #>> '{normalized_inputs,side}' = side",
        "evaluation_proof #>> '{normalized_inputs,game_time}'",
        "evaluation_proof #>> '{normalized_inputs,k_line}'",
        "evaluation_proof #>> '{normalized_inputs,odds}'",
        "evaluation_proof #>> '{normalized_inputs,official_book}'",
        "evaluation_proof #>> '{normalized_inputs,official_verdict}'",
        "evaluation_proof #>> '{artifact,source_artifact_path}' = source_artifact_path",
        "evaluation_proof #>> '{artifact,source_artifact_generated_at}'",
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


def test_followup_migration_resets_service_role_to_exact_write_privileges():
    sql = LEAST_PRIVILEGE_MIGRATION.read_text(encoding="utf-8").lower()

    assert "revoke all privileges on table public.alternative_pick_selection_state from service_role" in sql
    assert "grant select, insert, update on table public.alternative_pick_selection_state to service_role" in sql
    assert "grant select on table public.alternative_pick_selection_state to bbe_ops_readonly" in sql
    assert "grant delete" not in sql


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
create role bbe_ops_readonly;
alter default privileges for role postgres in schema public grant all privileges on tables to service_role;
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
            bootstrap
            + V1_MIGRATION.read_text(encoding="utf-8")
            + V2_MIGRATION.read_text(encoding="utf-8")
            + LEAST_PRIVILEGE_MIGRATION.read_text(encoding="utf-8"),
        )
        assert applied.returncode == 0, applied.stderr
        yield psql, port
    finally:
        subprocess.run(
            [pg_ctl, "-D", str(data), "-m", "fast", "-w", "stop"],
            text=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60,
        )


def test_postgres_followup_migration_removes_default_service_role_delete(isolated_postgres):
    psql, port = isolated_postgres
    verified = _run_psql(
        psql,
        port,
        """
with grants as (
  select privilege_type
  from pg_class c
  cross join lateral aclexplode(coalesce(c.relacl, acldefault('r', c.relowner))) acl
  where c.oid = 'public.alternative_pick_selection_state'::regclass
    and acl.grantee = 'service_role'::regrole
)
select case when
  (select array_agg(privilege_type order by privilege_type) from grants)
    = array['INSERT', 'SELECT', 'UPDATE']::text[]
  and has_table_privilege('service_role', 'public.alternative_pick_selection_state', 'select')
  and has_table_privilege('service_role', 'public.alternative_pick_selection_state', 'insert')
  and has_table_privilege('service_role', 'public.alternative_pick_selection_state', 'update')
  and not has_table_privilege('service_role', 'public.alternative_pick_selection_state', 'delete')
  and has_table_privilege('bbe_ops_readonly', 'public.alternative_pick_selection_state', 'select')
  and not has_table_privilege('anon', 'public.alternative_pick_selection_state', 'select')
  and not has_table_privilege('authenticated', 'public.alternative_pick_selection_state', 'select')
then 'least_privilege_ok' else 'least_privilege_failed' end;
""",
    )

    assert verified.returncode == 0, verified.stderr
    assert "least_privilege_ok" in verified.stdout


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


def test_postgres_jsonb_text_size_constraint_normalizes_large_numbers(isolated_postgres):
    psql, port = isolated_postgres
    inserted = _run_psql(
        psql, port,
        _omitted_proof_insert("pregame_alternative_pick_methodology_v1")
        .replace("game-pregame", "numeric-game-pregame")
        .replace("candidate-pregame", "numeric-candidate-pregame"),
    )
    within = _run_psql(
        psql, port,
        """
update public.alternative_pick_selection_state
set evaluation_proof = '{"padding":1e32750}'::jsonb
where candidate_identity like 'numeric-candidate-%';
""",
    )
    oversized = _run_psql(
        psql, port,
        """
update public.alternative_pick_selection_state
set evaluation_proof = '{"padding":1e32760}'::jsonb
where candidate_identity like 'numeric-candidate-%';
""",
    )

    assert inserted.returncode == 0, inserted.stderr
    assert within.returncode == 0, within.stderr
    assert oversized.returncode != 0
    assert "alternative_pick_selection_state_evaluation_proof_size_check" in oversized.stderr


def _valid_v2_insert() -> str:
    family_states = {
        name: {"state": "pending", "reason_codes": ["fixture_pending"]}
        for name in ("base", "anchor", "preclose", "reentry")
    }
    proof = {
        "schema_version": "v2",
        "bundle_id": "pregame_alternative_pick_methodology_v2",
        "selector_fingerprint": "f" * 64,
        "candidate": {
            "candidate_identity": "c" * 64,
            "slate_date": "2026-07-22",
            "normalized_pitcher": "proof pitcher",
            "side": "over",
            "model_k_line": 6.5,
            "game_time": "2026-07-22T23:00:00+00:00",
            "line_source_provider": "therundown",
            "official_binding_key": "d" * 64,
        },
        "artifact": {
            "source_artifact_path": "dashboard/data/processed/today.json",
            "source_artifact_generated_at": "2026-07-22T20:05:00+00:00",
            "source_artifact_sha256": "a" * 64,
            "source_artifact_byte_sha256": "b" * 64,
        },
        "normalized_inputs": {
            "pitcher": "proof pitcher", "side": "over",
            "game_time": "2026-07-22T23:00:00+00:00", "k_line": 6.5,
            "odds": -120, "official_book": "fanduel",
            "official_verdict": "FIRE 1u",
        },
        "preclose": {
            "decisive_observation_tokens": [],
            "qualifying_observation_count": 0,
            "first_observed_at": None,
            "last_observed_at": None,
            "freshness_status": "pending",
        },
        "decision": {
            "family_states": family_states,
            "family_count": 0,
            "selection_status": "pending",
            "selected_lane": None,
        },
    }
    encoded = json.dumps(proof, separators=(",", ":")).replace("'", "''")
    return f"""
insert into public.alternative_pick_selection_state (
  slate_date, game_identity, candidate_identity, candidate_became_current_at,
  pitcher, normalized_pitcher, team, opp_team, game_time, side, model_k_line,
  provider_posture, bundle_id, selector_id, selector_fingerprint, checkpoint,
  official_odds, official_book, official_verdict,
  selection_status, family_states, family_count, reason_codes,
  source_artifact_path, source_artifact_generated_at,
  source_artifact_sha256, source_artifact_byte_sha256,
  evidence_observation_ids, evidence_observation_count,
  evidence_first_observed_at, evidence_last_observed_at,
  evidence_freshness_status, observed_at, evaluation_proof
) values (
  '2026-07-22', 'proof-game', '{'c' * 64}', '2026-07-22T19:55:00Z',
  'Proof Pitcher', 'proof pitcher', 'ARI', 'LAD', '2026-07-22T23:00:00Z',
  'over', 6.5, 'therundown', 'pregame_alternative_pick_methodology_v2', null,
  '{'f' * 64}', 'provisional', -120, 'fanduel', 'FIRE 1u',
  'pending', '{json.dumps(family_states)}'::jsonb, 0, '[]'::jsonb,
  'dashboard/data/processed/today.json', '2026-07-22T20:05:00Z',
  '{'a' * 64}', '{'b' * 64}', '[]'::jsonb, 0, null, null, 'pending',
  '2026-07-22T20:10:00Z', '{encoded}'::jsonb
);
"""


@pytest.mark.parametrize(
    "mutation",
    (
        "selector_fingerprint = 'e" + "e" * 63 + "'",
        "candidate_identity = 'd" + "d" * 63 + "'",
        "slate_date = '2026-07-23'",
        "normalized_pitcher = 'other pitcher'",
        "side = 'under'",
        "model_k_line = 7.5",
        "game_time = '2026-07-22T23:30:00Z'",
        "official_odds = -115",
        "official_book = 'draftkings'",
        "official_verdict = 'LEAN'",
        "source_artifact_generated_at = '2026-07-22T20:06:00Z'",
        "source_artifact_path = 'dashboard/data/processed/other.json'",
        "source_artifact_sha256 = 'e" + "e" * 63 + "'",
        "source_artifact_byte_sha256 = 'd" + "d" * 63 + "'",
        "family_states = '{}'::jsonb",
        "family_count = 1",
        "evidence_observation_ids = '[\"therundown:other\"]'::jsonb",
        "evidence_observation_count = 1",
        "evidence_first_observed_at = '2026-07-22T20:00:00Z'",
        "evidence_last_observed_at = '2026-07-22T20:01:00Z'",
        "evidence_freshness_status = 'fresh'",
        "selection_status = 'selected'",
        "lane = 'consensus_core'",
        "selector_id = 'no_drag_distinct_family_consensus_core_v2'",
    ),
)
def test_postgres_v2_constraint_binds_candidate_inputs_and_display_row_fields(
    isolated_postgres, mutation,
):
    psql, port = isolated_postgres
    inserted = _run_psql(psql, port, _valid_v2_insert())
    changed = _run_psql(
        psql, port,
        f"update public.alternative_pick_selection_state set {mutation} "
        "where game_identity = 'proof-game';",
    )

    assert inserted.returncode == 0, inserted.stderr
    assert changed.returncode != 0
    assert "alternative_pick_selection_state_v2_evaluation_proof_check" in changed.stderr
    cleanup = _run_psql(
        psql, port,
        "delete from public.alternative_pick_selection_state where game_identity = 'proof-game';",
    )
    assert cleanup.returncode == 0, cleanup.stderr
