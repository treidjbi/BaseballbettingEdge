from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest

from scripts import build_season_retention_readiness as retention
from scripts import retention_bounded_sql as bounded_sql


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "scripts" / "supabase_retention_exact_coverage.sql"
REPORTER_PATH = ROOT / "scripts" / "build_season_retention_readiness.py"

EVIDENCE_PIN_REASONS = {
    "official_tracked_picks": "official_tracked_pick",
    "accepted_bets": "accepted_bet",
    "sent_notifications": "sent_notification",
    "consumed_locks": "consumed_lock",
    "frozen_alt_v2_rows": "frozen_alt_v2",
    "operator_incidents": "operator_incident",
    "model_review_pins": "model_review",
}


def test_exact_coverage_sql_exists_and_is_read_only():
    assert SQL_PATH.exists()
    sql = SQL_PATH.read_text(encoding="utf-8").lower()
    forbidden = (
        " insert ", " update ", " delete ", " truncate ", " drop ",
        " alter ", " create ", " grant ", " revoke ", " vacuum ",
    )
    assert not any(token in f" {sql} " for token in forbidden)
    assert "retention_execution_closed" in sql
    assert "deletion_approved" in sql


def test_exact_coverage_sql_uses_the_canonical_group_and_ordering_contract():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()
    for field in (
        "slate_date", "provider", "book_key", "normalized_player_name",
        "market_key", "side", "line",
    ):
        assert field in sql
    assert "order by observed_at asc, id asc" in sql
    assert "last_value(american_odds)" in sql
    assert "order by observed_at desc, id desc" not in sql
    assert "lag(american_odds)" in sql
    assert "pg_column_size" in sql


def test_exact_coverage_sql_keeps_one_statement_and_a_narrow_snapshot_projection():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()

    assert sql.count(";") == 1
    assert sql.rstrip().endswith(";")
    assert "ms.*" not in sql
    assert "ms.id as snapshot_id" in sql
    assert "pg_column_size(ms)::bigint as logical_bytes" in sql


def test_exact_coverage_sql_avoids_redundant_full_season_sorts_and_materialization():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()

    assert sql.count("order by observed_at asc, id asc") == 1
    assert "window raw_order as" in sql
    assert sql.count(" as materialized (") <= 1


def test_exact_coverage_sql_anomaly_scan_reuses_narrow_projection_aliases():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()
    anomaly_scan = sql.split("anomaly_counts as (", 1)[1].split(
        "source_anomalies as (", 1
    )[0]

    assert "nullif(trim(book_key), '')" in anomaly_scan
    assert "nullif(trim(bookmaker_key), '')" not in anomaly_scan


def test_exact_coverage_sql_emits_all_blocking_metrics_and_runtime_boundaries():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()
    expected = (
        "raw_snapshot_rows", "raw_logical_bytes", "raw_group_count",
        "compact_group_count", "exact_group_count", "mismatched_group_count",
        "missing_compact_group_count", "unexpected_compact_group_count",
        "duplicate_compact_group_count", "first_seen_mismatch_count",
        "last_seen_mismatch_count", "first_odds_mismatch_count",
        "last_odds_mismatch_count", "min_odds_mismatch_count",
        "max_odds_mismatch_count", "odds_move_count_mismatch_count",
        "snapshot_count_mismatch_count", "coverage_exact",
        "rows_missing_run_id", "rows_missing_run_row",
        "rows_missing_group_key", "provider_run_mismatch_rows",
        "first_run_at", "last_run_at", "failed_run_count", "books_seen",
        "first_snapshot_at", "last_snapshot_at", "last_heartbeat_at",
        "last_message_at", "heartbeat_count",
    )
    for field in expected:
        assert field in sql


def test_exact_coverage_sql_documents_one_linked_cli_read():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()
    assert (
        "npx supabase db query --linked --file "
        "scripts\\supabase_retention_exact_coverage.sql -o json"
    ) in sql


def _coverage(**overrides):
    row = {
        "slate_date": "2026-06-01", "provider": "boltodds",
        "raw_snapshot_rows": 100, "raw_logical_bytes": 50000,
        "raw_group_count": 4, "compact_group_count": 4, "exact_group_count": 4,
        "mismatched_group_count": 0,
        "missing_compact_group_count": 0, "unexpected_compact_group_count": 0,
        "duplicate_compact_group_count": 0,
        "first_seen_mismatch_count": 0, "last_seen_mismatch_count": 0,
        "first_odds_mismatch_count": 0, "last_odds_mismatch_count": 0,
        "min_odds_mismatch_count": 0, "max_odds_mismatch_count": 0,
        "odds_move_count_mismatch_count": 0, "snapshot_count_mismatch_count": 0,
        "first_raw_seen_at": "2026-06-01T16:00:00+00:00",
        "last_raw_seen_at": "2026-06-01T22:00:00+00:00",
        "coverage_exact": True,
    }
    row.update(overrides)
    return row


def _runtime(**overrides):
    row = {
        "provider": "boltodds", "first_run_at": "2026-05-07T16:00:00+00:00",
        "last_run_at": "2026-06-17T17:20:59+00:00", "run_count": 20,
        "completed_run_count": 19, "failed_run_count": 1, "request_count": 40,
        "books_seen": ["fanduel", "betmgm"],
        "first_snapshot_at": "2026-05-07T16:05:00+00:00",
        "last_snapshot_at": "2026-06-16T13:37:44+00:00",
        "snapshot_count": 100, "snapshot_logical_bytes": 50000,
        "last_heartbeat_at": "2026-06-17T17:20:59+00:00",
        "last_message_at": "2026-06-17T17:20:30+00:00", "heartbeat_count": 51900,
    }
    row.update(overrides)
    return row


def _envelope(*, coverage=None, anomalies=None, runtime=None):
    return {
        "audit_version": 1,
        "audit_generated_at": "2026-08-18T18:00:00+00:00",
        "complete": True,
        "retention_execution_closed": True,
        "deletion_approved": False,
        "query_scope": {
            "start_date": "2026-04-28", "end_date": "2026-08-18",
            "providers": ["boltodds"],
        },
        "source_anomalies": anomalies if anomalies is not None else [{
            "provider": "boltodds", "rows_missing_run_id": 0,
            "rows_missing_run_row": 0, "rows_missing_group_key": 0,
            "provider_run_mismatch_rows": 0,
        }],
        "coverage": coverage if coverage is not None else [_coverage()],
        "provider_runtime": runtime if runtime is not None else [_runtime()],
    }


def _v2_envelope():
    providers = ["boltodds", "propline", "the_odds", "therundown"]
    coverage = []
    candidate_runtime = []
    runtime_boundary = []
    for provider in providers:
        first_rows = 100 if provider == "boltodds" else 10
        first_bytes = 50000 if provider == "boltodds" else 100
        second_rows = 0 if provider == "boltodds" else 5
        second_bytes = 0 if provider == "boltodds" else 50
        coverage.extend([
            _coverage(
                slate_date="2026-04-28", provider=provider,
                raw_snapshot_rows=first_rows, raw_logical_bytes=first_bytes,
                raw_group_count=1, compact_group_count=1, exact_group_count=1,
                first_raw_seen_at="2026-04-28T16:00:00+00:00",
                last_raw_seen_at="2026-04-28T22:00:00+00:00",
            ),
            _coverage(
                slate_date="2026-04-29", provider=provider,
                raw_snapshot_rows=second_rows, raw_logical_bytes=second_bytes,
                raw_group_count=int(second_rows > 0),
                compact_group_count=int(second_rows > 0),
                exact_group_count=int(second_rows > 0),
                first_raw_seen_at=(
                    "2026-04-29T16:00:00+00:00" if second_rows else None
                ),
                last_raw_seen_at=(
                    "2026-04-29T22:00:00+00:00" if second_rows else None
                ),
            ),
        ])
        last_snapshot_at = (
            "2026-04-28T22:00:00+00:00"
            if provider == "boltodds"
            else "2026-04-29T22:00:00+00:00"
        )
        heartbeat_count = 2 if provider == "boltodds" else 0
        last_heartbeat_at = (
            "2026-04-29T22:01:00+00:00" if provider == "boltodds" else None
        )
        last_message_at = (
            "2026-04-29T22:00:30+00:00" if provider == "boltodds" else None
        )
        candidate_runtime.append(_runtime(
            provider=provider,
            first_run_at="2026-04-28T15:55:00+00:00",
            last_run_at="2026-04-29T15:55:00+00:00",
            run_count=2, completed_run_count=2, failed_run_count=0,
            request_count=2, books_seen=["fanduel"],
            first_snapshot_at="2026-04-28T16:00:00+00:00",
            last_snapshot_at=last_snapshot_at,
            snapshot_count=first_rows + second_rows,
            snapshot_logical_bytes=first_bytes + second_bytes,
            last_heartbeat_at=last_heartbeat_at,
            last_message_at=last_message_at,
            heartbeat_count=heartbeat_count,
        ))
        if provider == "boltodds":
            current = {
                "run": "2026-06-17T17:22:29+00:00",
                "snapshot": "2026-06-17T17:22:28+00:00",
                "heartbeat": "2026-06-17T17:22:27+00:00",
                "message": "2026-06-17T17:22:26+00:00",
            }
        else:
            current = {
                "run": "2026-05-29T18:00:00+00:00",
                "snapshot": "2026-05-29T18:00:00+00:00",
                "heartbeat": None,
                "message": None,
            }
        runtime_boundary.append({
            "provider": provider,
            "current_latest_run_at": current["run"],
            "current_latest_snapshot_at": current["snapshot"],
            "current_latest_heartbeat_at": current["heartbeat"],
            "current_latest_message_at": current["message"],
            "candidate_latest_run_at": "2026-04-29T15:55:00+00:00",
            "candidate_latest_snapshot_at": last_snapshot_at,
            "candidate_latest_heartbeat_at": last_heartbeat_at,
            "candidate_latest_message_at": last_message_at,
            "post_boltodds_suspension": False,
        })

    expected_ranges = [{
        "provider": provider,
        "start_date": "2026-04-28",
        "end_date": "2026-04-29",
    } for provider in providers]
    completed_ranges = [{
        "provider": provider,
        "start_date": slate_date,
        "end_date": slate_date,
    } for provider in providers for slate_date in ("2026-04-28", "2026-04-29")]
    return {
        "audit_version": 2,
        "audit_generated_at": "2026-05-29T18:00:00+00:00",
        "as_of_date": "2026-05-29",
        "timezone": "America/Phoenix",
        "candidate_scope": {
            "start_date": "2026-04-28", "end_date": "2026-04-29",
            "raw_retention_days": 30, "providers": providers,
        },
        "protected_scope": {
            "start_date": "2026-04-30",
            "reason": "dates inside the raw retention window are excluded",
        },
        "execution": {
            "query_contract_sha256": bounded_sql.query_contract_sha256(),
            "query_contract_version": "supabase-db-query-linked-json-v1",
            "runner_version": "2", "cli_version": "2.48.3",
            "chunk_ladder_days": [1, 3, 7], "soft_elapsed_seconds": 30.0,
            "cooldown_seconds": 30.0, "max_chunk_days": 7,
            "default_max_chunks": 1, "hard_max_chunks": 5,
            "expected_chunk_ranges": expected_ranges,
            "completed_chunk_ranges": completed_ranges,
            "complete": True,
        },
        "coverage": coverage,
        "source_anomalies": [{
            "provider": provider, "rows_missing_run_id": 0,
            "rows_missing_run_row": 0, "rows_missing_group_key": 0,
            "provider_run_mismatch_rows": 0, "slate_date_mismatch_rows": 0,
            "unknown_provider_rows": 0,
        } for provider in providers],
        "candidate_runtime": candidate_runtime,
        "runtime_boundary": runtime_boundary,
        "season_evidence": None,
        "pins": None,
        "complete": True,
        "retention_execution_closed": True,
        "deletion_approved": False,
    }


def _v2_season_evidence():
    evidence = _season_evidence()
    evidence["generated_at"] = "2026-05-29T18:00:00+00:00"
    second = json.loads(json.dumps(evidence["dates"][0]))
    evidence["dates"][0]["slate_date"] = "2026-04-28"
    second["slate_date"] = "2026-04-29"
    evidence["dates"].append(second)
    return evidence


def _v2_pins():
    pins = _pins()
    pins["generated_at"] = "2026-05-29T18:00:00+00:00"
    template = pins["partitions"][0]
    pins["partitions"] = []
    for slate_date in ("2026-04-28", "2026-04-29"):
        for provider in ("boltodds", "propline", "the_odds", "therundown"):
            row = json.loads(json.dumps(template))
            row.update(slate_date=slate_date, provider=provider)
            pins["partitions"].append(row)
    return pins


def _v2_gate_c_manifest():
    manifest = _gate_c_manifest()
    manifest.update(
        generated_at="2026-05-29T18:00:00+00:00",
        loaded_slate_dates=["2026-04-28", "2026-04-29"],
    )
    manifest["source"]["end_date"] = "2026-04-29"
    return manifest


def _make_v2_provider_snapshotless(envelope, provider):
    for row in envelope["coverage"]:
        if row["provider"] != provider:
            continue
        row.update(
            raw_snapshot_rows=0, raw_logical_bytes=0,
            raw_group_count=0, compact_group_count=0, exact_group_count=0,
            first_raw_seen_at=None, last_raw_seen_at=None,
        )
    runtime = next(
        row for row in envelope["candidate_runtime"] if row["provider"] == provider
    )
    runtime.update(
        books_seen=[], first_snapshot_at=None, last_snapshot_at=None,
        snapshot_count=0, snapshot_logical_bytes=0,
    )
    boundary = next(
        row for row in envelope["runtime_boundary"] if row["provider"] == provider
    )
    boundary["candidate_latest_snapshot_at"] = None


def _season_evidence(*, complete=True):
    return {
        "schema_version": 1, "generated_at": "2026-08-18T18:00:00+00:00",
        "dates": [{
            "slate_date": "2026-06-01", "decision_linked": True,
            "evidence_counts": {
                "official_tracked_picks": 2, "accepted_bets": 1,
                "sent_notifications": 1, "consumed_locks": 2,
                "frozen_alt_v2_rows": 0, "operator_incidents": 0,
                "model_review_pins": 0,
            },
            "required_evidence": {
                "results": complete, "bet_timing": complete,
                "checkpoint_market": complete, "close_clv": complete,
                "provider_metadata": complete,
            },
        }],
    }


def _pins(*, reconciled=True, status="preserved", reasons=None):
    pin_reasons = reasons if reasons is not None else [
        EVIDENCE_PIN_REASONS["official_tracked_picks"],
        EVIDENCE_PIN_REASONS["accepted_bets"],
        EVIDENCE_PIN_REASONS["sent_notifications"],
        EVIDENCE_PIN_REASONS["consumed_locks"],
    ]
    return {
        "schema_version": 1, "generated_at": "2026-08-18T18:00:00+00:00",
        "partitions": [{
            "slate_date": "2026-06-01", "provider": "boltodds",
            "reconciled": reconciled,
            "pins": [{
                "reason": reason, "status": status,
                "preserved_artifact": "data/picks_history.json",
            } for reason in pin_reasons],
        }],
    }


def _gate_c_manifest():
    return {
        "artifact": "gate_c_pitcher_k_outcome_dataset",
        "generated_at": "2026-08-18T17:00:00+00:00",
        "loaded_slate_dates": ["2026-06-01"],
        "source": {"start_date": "2026-04-28", "end_date": "2026-06-01"},
        "jsonl_sha256": "a" * 64,
        "summary_sha256": "b" * 64,
        "reconciliation": {"graded_pick_rows": 2, "matched_pick_rows": 2,
                           "unmatched_pick_rows": 0},
        "summary_counts": {"rows_missing_result": 0, "tracked_pick_rows": 2,
                           "context_snapshot_counts": {"official_close": 2}},
    }


def test_load_query_envelope_accepts_supabase_array_wrapper(tmp_path):
    path = tmp_path / "query.json"
    path.write_text(json.dumps([{"retention_exact_coverage": _envelope()}]), encoding="utf-8")
    assert retention.load_query_envelope(str(path))["audit_version"] == 1


def test_load_query_envelope_accepts_direct_v2_object(tmp_path):
    path = tmp_path / "bounded-envelope.json"
    path.write_text(json.dumps(_v2_envelope()), encoding="utf-8")

    loaded = retention.load_query_envelope(str(path))

    assert loaded["audit_version"] == 2
    assert loaded["candidate_scope"]["end_date"] == "2026-04-29"


def test_v1_normalization_preserves_the_existing_envelope_object():
    envelope = _envelope()

    normalized = retention._normalize_envelope_for_decisions(
        envelope, as_of=None,
    )

    assert normalized is envelope


def test_complete_v2_matrix_uses_candidate_cutoff_and_current_runtime_separately():
    envelope = _v2_envelope()
    report = retention.build_readiness_report(
        envelope=envelope, gate_c=_v2_gate_c_manifest(),
        season_evidence=_v2_season_evidence(), pins=_v2_pins(),
        as_of="2026-05-29", raw_retention_days=30,
    )
    closure = retention.build_boltodds_closure(
        envelope=envelope, gate_c=_v2_gate_c_manifest(),
        season_evidence=_v2_season_evidence(), pins=_v2_pins(),
        as_of="2026-05-29",
    )

    assert report["source_date_range"] == {
        "start_date": "2026-04-28", "end_date": "2026-04-29",
    }
    assert report["summary"]["decision_counts"] == {
        "ready_for_retention_review": 8,
    }
    assert closure["status"] == "ready_for_retirement_review"
    assert closure["runtime"]["last_snapshot_at"] == "2026-04-28T22:00:00+00:00"
    assert closure["current_runtime_boundary"]["current_latest_snapshot_at"] == (
        "2026-06-17T17:22:28+00:00"
    )


def test_v2_null_embedded_evidence_never_invents_readiness():
    report = retention.build_readiness_report(
        envelope=_v2_envelope(), gate_c=_v2_gate_c_manifest(),
        season_evidence=None, pins=None,
        as_of="2026-05-29", raw_retention_days=30,
    )

    assert report["summary"]["decision_counts"] == {
        "blocked_outcome_evidence": 8,
    }


def test_v2_report_rejects_a_retention_window_different_from_candidate_scope():
    with pytest.raises(ValueError, match="raw_retention_days.*candidate_scope"):
        retention.build_readiness_report(
            envelope=_v2_envelope(), gate_c=_v2_gate_c_manifest(),
            season_evidence=_v2_season_evidence(), pins=_v2_pins(),
            as_of="2026-05-29", raw_retention_days=14,
        )


def test_v2_requires_the_clean_regime_candidate_start_date():
    envelope = _v2_envelope()
    envelope["candidate_scope"]["start_date"] = "2026-04-29"

    with pytest.raises(ValueError, match="candidate_scope.start_date"):
        retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


@pytest.mark.parametrize("field", ["season_evidence", "pins"])
def test_v2_requires_explicit_top_level_evidence_placeholders(field):
    envelope = _v2_envelope()
    del envelope[field]

    with pytest.raises(ValueError, match=field):
        retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


@pytest.mark.parametrize("mode", ["missing", "duplicate"])
def test_v2_rejects_missing_or_duplicate_matrix_partition(mode):
    envelope = _v2_envelope()
    if mode == "missing":
        envelope["coverage"].pop()
    else:
        envelope["coverage"].append(dict(envelope["coverage"][0]))

    with pytest.raises(ValueError, match="coverage.*matrix|partitions.*unique"):
        retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


def test_v2_rejects_incomplete_execution_metadata():
    envelope = _v2_envelope()
    envelope["execution"]["complete"] = False

    with pytest.raises(ValueError, match="execution.complete"):
        retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


@pytest.mark.parametrize("range_kind", ["expected", "completed"])
def test_v2_rejects_expected_or_completed_range_mismatch(range_kind):
    envelope = _v2_envelope()
    key = f"{range_kind}_chunk_ranges"
    envelope["execution"][key][0]["end_date"] = (
        "2026-04-28" if range_kind == "expected" else "2026-04-29"
    )

    with pytest.raises(ValueError, match=f"{range_kind}.*ranges"):
        retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


def test_v2_rejects_invalid_query_contract_hash():
    envelope = _v2_envelope()
    envelope["execution"]["query_contract_sha256"] = "0" * 64

    with pytest.raises(ValueError, match="query_contract_sha256"):
        retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


@pytest.mark.parametrize("field", ["snapshot_count", "snapshot_logical_bytes"])
def test_v2_rejects_candidate_runtime_row_or_byte_mismatch(field):
    envelope = _v2_envelope()
    envelope["candidate_runtime"][0][field] += 1

    with pytest.raises(ValueError, match="candidate runtime snapshot"):
        retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


@pytest.mark.parametrize(
    "field", ["slate_date_mismatch_rows", "unknown_provider_rows"],
)
def test_v2_new_unattributed_anomalies_block_readiness_and_closure(field):
    envelope = _v2_envelope()
    envelope["source_anomalies"][0][field] = 1

    report = retention.build_readiness_report(
        envelope=envelope, gate_c=_v2_gate_c_manifest(),
        season_evidence=_v2_season_evidence(), pins=_v2_pins(),
        as_of="2026-05-29", raw_retention_days=30,
    )
    closure = retention.build_boltodds_closure(
        envelope=envelope, gate_c=_v2_gate_c_manifest(),
        season_evidence=_v2_season_evidence(), pins=_v2_pins(),
        as_of="2026-05-29",
    )

    boltodds = next(row for row in report["partitions"] if row["provider"] == "boltodds")
    assert boltodds["decision"] == "blocked_compaction"
    assert field in boltodds["reason_codes"]
    assert closure["status"] == "incomplete_evidence"
    assert field in closure["unresolved_evidence_gaps"]


def test_v2_rejects_stale_runtime_boundary_generation_day():
    envelope = _v2_envelope()
    envelope["audit_generated_at"] = "2026-05-29T06:59:59+00:00"

    with pytest.raises(ValueError, match="runtime boundary.*stale"):
        retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


@pytest.mark.parametrize("mode", ["missing", "duplicate"])
def test_v2_rejects_missing_or_duplicate_runtime_boundary_provider(mode):
    envelope = _v2_envelope()
    if mode == "missing":
        envelope["runtime_boundary"].pop()
    else:
        envelope["runtime_boundary"].append(dict(envelope["runtime_boundary"][0]))

    with pytest.raises(ValueError, match="runtime_boundary.*provider"):
        retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


@pytest.mark.parametrize(
    ("current_field", "candidate_field"),
    [
        ("current_latest_run_at", "candidate_latest_run_at"),
        ("current_latest_snapshot_at", "candidate_latest_snapshot_at"),
        ("current_latest_heartbeat_at", "candidate_latest_heartbeat_at"),
        ("current_latest_message_at", "candidate_latest_message_at"),
    ],
)
def test_v2_rejects_current_runtime_maximum_older_than_candidate(
    current_field, candidate_field,
):
    envelope = _v2_envelope()
    boundary = envelope["runtime_boundary"][0]
    boundary[current_field] = "2026-04-27T23:59:59+00:00"
    assert boundary[candidate_field] is not None

    with pytest.raises(ValueError, match="current runtime boundary.*candidate"):
        retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


@pytest.mark.parametrize(
    "field",
    [
        "current_latest_run_at", "current_latest_snapshot_at",
        "current_latest_heartbeat_at", "current_latest_message_at",
    ],
)
def test_v2_boltodds_closure_blocks_each_post_suspension_current_maximum(field):
    envelope = _v2_envelope()
    boundary = envelope["runtime_boundary"][0]
    boundary[field] = "2026-06-17T17:22:30+00:00"
    boundary["post_boltodds_suspension"] = True

    closure = retention.build_boltodds_closure(
        envelope=envelope, gate_c=_v2_gate_c_manifest(),
        season_evidence=_v2_season_evidence(), pins=_v2_pins(),
        as_of="2026-05-29",
    )

    assert closure["status"] == "operational_exception"
    assert "post_suspension_runtime_evidence" in closure["unresolved_evidence_gaps"]


@pytest.mark.parametrize(
    "field",
    [
        "current_latest_run_at", "current_latest_snapshot_at",
        "current_latest_heartbeat_at", "current_latest_message_at",
    ],
)
def test_v2_readiness_blocks_each_post_suspension_boltodds_current_maximum(
    field, tmp_path,
):
    envelope = _v2_envelope()
    boundary = envelope["runtime_boundary"][0]
    boundary[field] = "2026-06-17T17:22:30+00:00"
    boundary["post_boltodds_suspension"] = True

    report = retention.build_readiness_report(
        envelope=envelope, gate_c=_v2_gate_c_manifest(),
        season_evidence=_v2_season_evidence(), pins=_v2_pins(),
        as_of="2026-05-29", raw_retention_days=30,
    )
    boltodds_partitions = [
        row for row in report["partitions"] if row["provider"] == "boltodds"
    ]
    assert {row["decision"] for row in boltodds_partitions} == {"blocked_compaction"}
    assert all(
        row["reason_codes"] == ["post_suspension_runtime_evidence"]
        for row in boltodds_partitions
    )
    assert {
        row["decision"]
        for row in report["partitions"]
        if row["provider"] != "boltodds"
    } == {"ready_for_retention_review"}

    query = tmp_path / "query.json"
    gate_c = tmp_path / "gate-c.json"
    season = tmp_path / "season.json"
    pins = tmp_path / "pins.json"
    output_dir = tmp_path / "readiness"
    query.write_text(json.dumps(envelope), encoding="utf-8")
    gate_c.write_text(json.dumps(_v2_gate_c_manifest()), encoding="utf-8")
    season.write_text(json.dumps(_v2_season_evidence()), encoding="utf-8")
    pins.write_text(json.dumps(_v2_pins()), encoding="utf-8")

    exit_code = retention.main([
        "readiness", "--query-json", str(query),
        "--gate-c-manifest", str(gate_c),
        "--season-evidence", str(season), "--pins", str(pins),
        "--as-of", "2026-05-29", "--output-dir", str(output_dir),
    ])
    written_report = json.loads(
        (output_dir / "season_retention_readiness.json").read_text(encoding="utf-8")
    )

    assert exit_code == 2
    assert all(
        row["decision"] != "ready_for_retention_review"
        and "post_suspension_runtime_evidence" in row["reason_codes"]
        for row in written_report["partitions"]
        if row["provider"] == "boltodds"
    )

    closure = retention.build_boltodds_closure(
        envelope=envelope, gate_c=_v2_gate_c_manifest(),
        season_evidence=_v2_season_evidence(), pins=_v2_pins(),
        as_of="2026-05-29",
    )
    assert closure["status"] == "operational_exception"
    assert closure["current_runtime_boundary"][field] == "2026-06-17T17:22:30+00:00"
    assert "post_suspension_runtime_evidence" in closure["unresolved_evidence_gaps"]


@pytest.mark.parametrize(
    ("field", "value"),
    [("retention_execution_closed", False), ("deletion_approved", True)],
)
def test_v2_rejects_open_execution_or_approved_deletion(field, value):
    envelope = _v2_envelope()
    envelope[field] = value

    with pytest.raises(ValueError, match=field):
        retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


@pytest.mark.parametrize(("label", "locate"), [
    pytest.param("envelope", lambda value: value, id="top-level"),
    pytest.param("candidate_scope", lambda value: value["candidate_scope"], id="candidate-scope"),
    pytest.param("protected_scope", lambda value: value["protected_scope"], id="protected-scope"),
    pytest.param("execution", lambda value: value["execution"], id="execution"),
    pytest.param(
        "execution.expected_chunk_ranges[0]",
        lambda value: value["execution"]["expected_chunk_ranges"][0],
        id="expected-range",
    ),
    pytest.param(
        "execution.completed_chunk_ranges[0]",
        lambda value: value["execution"]["completed_chunk_ranges"][0],
        id="completed-range",
    ),
    pytest.param("coverage[0]", lambda value: value["coverage"][0], id="coverage"),
    pytest.param(
        "source_anomalies[0]", lambda value: value["source_anomalies"][0],
        id="source-anomaly",
    ),
    pytest.param(
        "candidate_runtime[0]", lambda value: value["candidate_runtime"][0],
        id="candidate-runtime",
    ),
    pytest.param(
        "runtime_boundary[0]", lambda value: value["runtime_boundary"][0],
        id="runtime-boundary",
    ),
])
def test_v2_rejects_unknown_keys_at_every_object_tier(label, locate):
    envelope = _v2_envelope()
    locate(envelope)["raw_database_rows"] = "do-not-copy-this-value"

    with pytest.raises(ValueError, match=rf"{re.escape(label)}.*unknown"):
        retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


@pytest.mark.parametrize(("label", "locate", "field"), [
    pytest.param("coverage[1]", lambda value: value["coverage"][1], "first_raw_seen_at", id="coverage-null"),
    pytest.param(
        "candidate_runtime[1]", lambda value: value["candidate_runtime"][1],
        "last_heartbeat_at", id="runtime-null",
    ),
    pytest.param(
        "runtime_boundary[1]", lambda value: value["runtime_boundary"][1],
        "current_latest_message_at", id="boundary-current-null",
    ),
    pytest.param(
        "runtime_boundary[1]", lambda value: value["runtime_boundary"][1],
        "candidate_latest_message_at", id="boundary-candidate-null",
    ),
])
def test_v2_requires_nullable_keys_to_be_present(label, locate, field):
    envelope = _v2_envelope()
    del locate(envelope)[field]

    with pytest.raises(
        ValueError, match=rf"{re.escape(label)}.*missing.*{field}",
    ):
        retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


def test_v2_missing_runtime_boundary_key_uses_controlled_cli_exit(tmp_path, capsys):
    envelope = _v2_envelope()
    del envelope["runtime_boundary"][1]["current_latest_message_at"]
    query = tmp_path / "query.json"
    gate_c = tmp_path / "gate-c.json"
    query.write_text(json.dumps(envelope), encoding="utf-8")
    gate_c.write_text(json.dumps(_v2_gate_c_manifest()), encoding="utf-8")

    exit_code = retention.main([
        "readiness", "--query-json", str(query),
        "--gate-c-manifest", str(gate_c), "--as-of", "2026-05-29",
        "--output-dir", str(tmp_path),
    ])

    assert exit_code == 3
    assert "retention_audit_error" in capsys.readouterr().err
    assert not (tmp_path / "season_retention_readiness.json").exists()
    assert not (tmp_path / "season_retention_readiness.md").exists()


def test_v2_unknown_raw_payload_is_rejected_without_output_leakage(tmp_path, capsys):
    envelope = _v2_envelope()
    secret = "Bearer should-never-appear"
    envelope["runtime_boundary"][0]["raw_payload"] = {"authorization": secret}
    query = tmp_path / "query.json"
    gate_c = tmp_path / "gate-c.json"
    query.write_text(json.dumps(envelope), encoding="utf-8")
    gate_c.write_text(json.dumps(_v2_gate_c_manifest()), encoding="utf-8")

    exit_code = retention.main([
        "boltodds-closure", "--query-json", str(query),
        "--gate-c-manifest", str(gate_c), "--as-of", "2026-05-29",
        "--output-dir", str(tmp_path),
    ])

    captured = capsys.readouterr()
    assert exit_code == 3
    assert secret not in captured.out + captured.err
    assert not (tmp_path / "boltodds_retirement_closure.json").exists()
    assert not (tmp_path / "boltodds_retirement_closure.md").exists()


@pytest.mark.parametrize(("field", "value"), [
    ("first_snapshot_at", "2026-04-28T15:59:59+00:00"),
    ("first_snapshot_at", "2026-04-28T16:00:01+00:00"),
    ("last_snapshot_at", "2026-04-29T21:59:59+00:00"),
    ("last_snapshot_at", "2026-04-29T22:00:01+00:00"),
])
def test_v2_candidate_runtime_snapshot_extrema_must_exactly_match_coverage(field, value):
    envelope = _v2_envelope()
    runtime = envelope["candidate_runtime"][1]
    runtime[field] = value
    if field == "last_snapshot_at":
        envelope["runtime_boundary"][1]["candidate_latest_snapshot_at"] = value

    with pytest.raises(ValueError, match="candidate runtime snapshot timestamps contradict coverage"):
        retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


def test_v2_accepts_snapshotless_provider_with_null_candidate_extrema():
    envelope = _v2_envelope()
    _make_v2_provider_snapshotless(envelope, "the_odds")

    retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


def test_v2_rejects_nonnull_candidate_extremum_for_snapshotless_provider():
    envelope = _v2_envelope()
    _make_v2_provider_snapshotless(envelope, "the_odds")
    envelope["candidate_runtime"][2]["first_snapshot_at"] = "2026-04-28T16:00:00+00:00"

    with pytest.raises(ValueError, match="candidate runtime snapshot"):
        retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


def test_v2_rejects_null_candidate_extremum_for_nonzero_coverage():
    envelope = _v2_envelope()
    envelope["candidate_runtime"][1]["first_snapshot_at"] = None

    with pytest.raises(ValueError, match="candidate runtime snapshot"):
        retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


def test_v2_rejects_post_suspension_boltodds_candidate_snapshot_hidden_by_runtime():
    envelope = _v2_envelope()
    envelope["coverage"][0].update(
        first_raw_seen_at="2026-06-18T16:00:00+00:00",
        last_raw_seen_at="2026-06-18T22:00:00+00:00",
    )

    with pytest.raises(ValueError, match="candidate runtime snapshot timestamps contradict coverage"):
        retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


def test_v2_rejects_under_explained_mismatched_groups():
    envelope = _v2_envelope()
    row = envelope["coverage"][0]
    row.update(
        raw_group_count=2, compact_group_count=2, exact_group_count=0,
        mismatched_group_count=2, first_seen_mismatch_count=1,
        coverage_exact=False,
    )

    with pytest.raises(ValueError, match="mismatched_group_count exceeds explained"):
        retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


def test_v2_accepts_overlapping_mismatch_subtypes_for_one_group():
    envelope = _v2_envelope()
    row = envelope["coverage"][0]
    row.update(
        exact_group_count=0, mismatched_group_count=1,
        first_seen_mismatch_count=1, last_seen_mismatch_count=1,
        coverage_exact=False,
    )

    retention.validate_envelope(envelope, as_of=date.fromisoformat("2026-05-29"))


def test_v2_closure_projects_only_approved_runtime_boundary_fields():
    closure = retention.build_boltodds_closure(
        envelope=_v2_envelope(), gate_c=_v2_gate_c_manifest(),
        season_evidence=_v2_season_evidence(), pins=_v2_pins(),
        as_of="2026-05-29",
    )

    assert set(closure["current_runtime_boundary"]) == {
        "provider", "current_latest_run_at", "current_latest_snapshot_at",
        "current_latest_heartbeat_at", "current_latest_message_at",
        "candidate_latest_run_at", "candidate_latest_snapshot_at",
        "candidate_latest_heartbeat_at", "candidate_latest_message_at",
        "post_boltodds_suspension",
    }


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(audit_version=True),
    lambda value: value.update(complete=False),
    lambda value: value.update(retention_execution_closed=False),
    lambda value: value.update(deletion_approved=True),
    lambda value: value["coverage"][0].update(provider="unknown_provider"),
])
def test_validate_envelope_rejects_untrustworthy_input(mutation):
    envelope = _envelope()
    mutation(envelope)
    with pytest.raises(ValueError):
        retention.validate_envelope(envelope)


def test_validate_envelope_rejects_empty_coverage():
    with pytest.raises(ValueError, match="coverage must not be empty"):
        retention.validate_envelope(_envelope(coverage=[]))


@pytest.mark.parametrize("field", list(_coverage()))
def test_validate_envelope_rejects_truncated_coverage_rows(field):
    row = _coverage()
    del row[field]

    with pytest.raises(ValueError):
        retention.validate_envelope(_envelope(coverage=[row]))


@pytest.mark.parametrize("overrides", [
    {"raw_group_count": 5},
    {"compact_group_count": 5},
    {"raw_snapshot_rows": 3},
    {"mismatched_group_count": 0, "first_seen_mismatch_count": 1},
    {"first_raw_seen_at": "2026-06-01T23:00:00+00:00"},
    {"coverage_exact": False},
    {
        "raw_group_count": 4, "compact_group_count": 3,
        "exact_group_count": 3, "missing_compact_group_count": 1,
        "coverage_exact": True,
    },
])
def test_validate_envelope_rejects_contradictory_coverage_aggregates(overrides):
    with pytest.raises(ValueError):
        retention.validate_envelope(_envelope(coverage=[_coverage(**overrides)]))


@pytest.mark.parametrize("runtime_overrides", [
    {"run_count": 19, "completed_run_count": 19, "failed_run_count": 1},
    {"first_run_at": None},
    {"first_snapshot_at": None},
    {"heartbeat_count": 0, "last_heartbeat_at": "2026-06-17T17:20:59+00:00"},
])
def test_validate_envelope_rejects_contradictory_runtime_aggregates(runtime_overrides):
    with pytest.raises(ValueError):
        retention.validate_envelope(_envelope(runtime=[_runtime(**runtime_overrides)]))


@pytest.mark.parametrize("runtime_overrides", [
    {"snapshot_count": 99},
    {"snapshot_count": 100, "snapshot_logical_bytes": 49999},
    {"first_snapshot_at": "2026-06-01T17:00:00+00:00"},
    {"last_snapshot_at": "2026-06-01T21:00:00+00:00"},
])
def test_validate_envelope_cross_checks_coverage_against_provider_runtime(
    runtime_overrides,
):
    with pytest.raises(ValueError, match="coverage contradicts provider runtime"):
        retention.validate_envelope(_envelope(runtime=[_runtime(**runtime_overrides)]))


def test_validate_envelope_rejects_zero_anomaly_runtime_without_raw_coverage():
    envelope = _envelope()
    envelope["query_scope"]["providers"].append("propline")
    envelope["source_anomalies"].append({
        "provider": "propline", "rows_missing_run_id": 0,
        "rows_missing_run_row": 0, "rows_missing_group_key": 0,
        "provider_run_mismatch_rows": 0,
    })
    envelope["provider_runtime"].append(_runtime(
        provider="propline", snapshot_count=10, snapshot_logical_bytes=5000,
    ))

    with pytest.raises(ValueError, match="coverage contradicts provider runtime"):
        retention.validate_envelope(envelope)


@pytest.mark.parametrize("runtime_overrides", [
    {"snapshot_count": 101},
    {"snapshot_logical_bytes": 50001},
])
def test_validate_envelope_rejects_zero_anomaly_raw_coverage_below_runtime(
    runtime_overrides,
):
    with pytest.raises(ValueError, match="coverage contradicts provider runtime"):
        retention.validate_envelope(_envelope(runtime=[_runtime(**runtime_overrides)]))


def test_validate_envelope_rejects_anomaly_counts_larger_than_provider_runtime():
    anomalies = [{
        "provider": "boltodds", "rows_missing_run_id": 611973,
        "rows_missing_run_row": 0, "rows_missing_group_key": 0,
        "provider_run_mismatch_rows": 0,
    }]

    with pytest.raises(ValueError, match="anomaly count exceeds provider runtime"):
        retention.validate_envelope(_envelope(anomalies=anomalies))


def test_compact_only_partition_is_valid_evidence_but_blocks_compaction():
    coverage = _coverage(
        raw_snapshot_rows=0, raw_logical_bytes=0, raw_group_count=0,
        compact_group_count=1, exact_group_count=0, mismatched_group_count=0,
        unexpected_compact_group_count=1, first_raw_seen_at=None,
        last_raw_seen_at=None, coverage_exact=False,
    )
    runtime = _runtime(
        books_seen=[], first_snapshot_at=None, last_snapshot_at=None,
        snapshot_count=0, snapshot_logical_bytes=0,
    )

    report = retention.build_readiness_report(
        envelope=_envelope(coverage=[coverage], runtime=[runtime]),
        gate_c=_gate_c_manifest(), season_evidence=_season_evidence(), pins=_pins(),
        as_of="2026-08-18", raw_retention_days=30,
    )

    assert report["partitions"][0]["decision"] == "blocked_compaction"
    assert "unexpected_compact_group_count" in report["partitions"][0]["reason_codes"]


def test_provider_anomaly_without_a_coverage_partition_cannot_produce_readiness():
    envelope = _envelope()
    envelope["query_scope"]["providers"].append("propline")
    envelope["source_anomalies"].append({
        "provider": "propline", "rows_missing_run_id": 1,
        "rows_missing_run_row": 0, "rows_missing_group_key": 0,
        "provider_run_mismatch_rows": 0,
    })
    envelope["provider_runtime"].append(_runtime(
        provider="propline", first_run_at=None, last_run_at=None,
        run_count=0, completed_run_count=0, failed_run_count=0,
        request_count=0, books_seen=[], first_snapshot_at=None,
        last_snapshot_at=None, snapshot_count=0, snapshot_logical_bytes=0,
        last_heartbeat_at=None, last_message_at=None, heartbeat_count=0,
    ))

    with pytest.raises(ValueError, match="anomalies without coverage"):
        retention.validate_envelope(envelope)


def test_audit_timestamp_must_be_fresh_for_the_as_of_day_in_phoenix():
    envelope = _envelope()
    envelope["audit_generated_at"] = "2026-08-18T06:59:59+00:00"

    with pytest.raises(ValueError, match="audit_generated_at is stale"):
        retention.build_readiness_report(
            envelope=envelope, gate_c=_gate_c_manifest(),
            season_evidence=_season_evidence(), pins=_pins(),
            as_of="2026-08-18", raw_retention_days=30,
        )


@pytest.mark.parametrize("manifest_name", ["season_evidence", "pins"])
def test_audit_supporting_manifests_must_be_fresh_in_phoenix(manifest_name):
    season_evidence = _season_evidence()
    pins = _pins()
    manifest = season_evidence if manifest_name == "season_evidence" else pins
    manifest["generated_at"] = "2026-08-18T06:59:59+00:00"

    with pytest.raises(ValueError, match=f"{manifest_name}.generated_at is stale"):
        retention.build_readiness_report(
            envelope=_envelope(), gate_c=_gate_c_manifest(),
            season_evidence=season_evidence, pins=pins,
            as_of="2026-08-18", raw_retention_days=30,
        )


def test_gate_c_manifest_cannot_claim_dates_newer_than_its_generation():
    gate_c = _gate_c_manifest()
    gate_c["generated_at"] = "2026-05-31T20:00:00+00:00"

    with pytest.raises(ValueError, match="gate_c.generated_at predates source coverage"):
        retention.build_readiness_report(
            envelope=_envelope(), gate_c=gate_c,
            season_evidence=_season_evidence(), pins=_pins(),
            as_of="2026-08-18", raw_retention_days=30,
        )


def test_stale_query_scope_is_rejected_for_requested_as_of_date():
    envelope = _envelope()
    envelope["query_scope"]["end_date"] = "2026-08-17"
    with pytest.raises(ValueError, match="query scope is stale"):
        retention.build_readiness_report(
            envelope=envelope, gate_c=_gate_c_manifest(),
            season_evidence=_season_evidence(), pins=_pins(),
            as_of="2026-08-18", raw_retention_days=30,
        )


def test_exact_old_partition_with_complete_evidence_is_ready_for_review():
    report = retention.build_readiness_report(
        envelope=_envelope(), gate_c=_gate_c_manifest(),
        season_evidence=_season_evidence(), pins=_pins(),
        as_of="2026-08-18", raw_retention_days=30,
    )
    assert report["partitions"][0]["decision"] == "ready_for_retention_review"
    assert report["retention_execution_closed"] is True
    assert report["deletion_approved"] is False


@pytest.mark.parametrize("field", [
    "missing_compact_group_count", "unexpected_compact_group_count",
    "duplicate_compact_group_count", "first_seen_mismatch_count",
    "last_seen_mismatch_count", "first_odds_mismatch_count",
    "last_odds_mismatch_count", "min_odds_mismatch_count",
    "max_odds_mismatch_count", "odds_move_count_mismatch_count",
    "snapshot_count_mismatch_count",
])
def test_every_compaction_mismatch_blocks(field):
    metric_mismatch = field not in {
        "missing_compact_group_count", "unexpected_compact_group_count",
        "duplicate_compact_group_count",
    }
    overrides = {field: 1, "coverage_exact": False}
    if field == "missing_compact_group_count":
        overrides.update(compact_group_count=3, exact_group_count=3)
    elif field == "unexpected_compact_group_count":
        overrides.update(compact_group_count=5)
    elif metric_mismatch:
        overrides.update(mismatched_group_count=1, exact_group_count=3)
    row = _coverage(**overrides)
    report = retention.build_readiness_report(
        envelope=_envelope(coverage=[row]), gate_c=_gate_c_manifest(),
        season_evidence=_season_evidence(), pins=_pins(),
        as_of="2026-08-18", raw_retention_days=30,
    )
    assert report["partitions"][0]["decision"] == "blocked_compaction"
    assert field in report["partitions"][0]["reason_codes"]


def test_recent_partition_is_not_in_policy_window():
    report = retention.build_readiness_report(
        envelope=_envelope(coverage=[_coverage(slate_date="2026-08-10")]),
        gate_c=_gate_c_manifest(), season_evidence=None, pins=None,
        as_of="2026-08-18", raw_retention_days=30,
    )
    assert report["partitions"][0]["decision"] == "not_in_policy_window"


def test_missing_or_incomplete_outcome_evidence_blocks():
    report = retention.build_readiness_report(
        envelope=_envelope(), gate_c=_gate_c_manifest(),
        season_evidence=_season_evidence(complete=False), pins=_pins(),
        as_of="2026-08-18", raw_retention_days=30,
    )
    assert report["partitions"][0]["decision"] == "blocked_outcome_evidence"


def test_missing_or_unpreserved_pin_evidence_blocks():
    report = retention.build_readiness_report(
        envelope=_envelope(), gate_c=_gate_c_manifest(),
        season_evidence=_season_evidence(), pins=_pins(status="pending"),
        as_of="2026-08-18", raw_retention_days=30,
    )
    assert report["partitions"][0]["decision"] == "blocked_pinned_evidence"


@pytest.mark.parametrize("field", ["schema_version", "generated_at"])
def test_incomplete_season_manifest_contract_cannot_produce_readiness(field):
    season_evidence = _season_evidence()
    del season_evidence[field]
    with pytest.raises(ValueError):
        retention.build_readiness_report(
            envelope=_envelope(), gate_c=_gate_c_manifest(),
            season_evidence=season_evidence, pins=_pins(),
            as_of="2026-08-18", raw_retention_days=30,
        )


def test_decision_linked_false_still_requires_complete_evidence_counts():
    season_evidence = _season_evidence()
    record = season_evidence["dates"][0]
    record["decision_linked"] = False
    del record["evidence_counts"]["accepted_bets"]
    with pytest.raises(ValueError):
        retention.build_readiness_report(
            envelope=_envelope(), gate_c=_gate_c_manifest(),
            season_evidence=season_evidence, pins=_pins(),
            as_of="2026-08-18", raw_retention_days=30,
        )


def test_complete_decision_linked_false_evidence_can_be_ready_for_review():
    season_evidence = _season_evidence()
    record = season_evidence["dates"][0]
    record["decision_linked"] = False
    record["evidence_counts"] = {
        field: 0 for field in EVIDENCE_PIN_REASONS
    }
    del record["required_evidence"]
    report = retention.build_readiness_report(
        envelope=_envelope(), gate_c=_gate_c_manifest(),
        season_evidence=season_evidence, pins=_pins(reasons=[]),
        as_of="2026-08-18", raw_retention_days=30,
    )
    assert report["partitions"][0]["decision"] == "ready_for_retention_review"


@pytest.mark.parametrize("count_field", list(EVIDENCE_PIN_REASONS))
def test_each_positive_evidence_count_contradicts_decision_linked_false(count_field):
    season_evidence = _season_evidence()
    record = season_evidence["dates"][0]
    record["decision_linked"] = False
    record["evidence_counts"] = {
        field: int(field == count_field) for field in EVIDENCE_PIN_REASONS
    }
    del record["required_evidence"]

    with pytest.raises(ValueError, match="decision_linked=false contradicts positive"):
        retention.build_readiness_report(
            envelope=_envelope(), gate_c=_gate_c_manifest(),
            season_evidence=season_evidence, pins=_pins(reasons=[]),
            as_of="2026-08-18", raw_retention_days=30,
        )


@pytest.mark.parametrize("count_field", list(EVIDENCE_PIN_REASONS))
def test_each_positive_evidence_count_requires_outcome_preservation(count_field):
    season_evidence = _season_evidence(complete=False)
    record = season_evidence["dates"][0]
    record["evidence_counts"] = {
        field: int(field == count_field) for field in EVIDENCE_PIN_REASONS
    }

    report = retention.build_readiness_report(
        envelope=_envelope(), gate_c=_gate_c_manifest(),
        season_evidence=season_evidence,
        pins=_pins(reasons=[EVIDENCE_PIN_REASONS[count_field]]),
        as_of="2026-08-18", raw_retention_days=30,
    )

    assert report["partitions"][0]["decision"] == "blocked_outcome_evidence"


@pytest.mark.parametrize("count_field,pin_reason", EVIDENCE_PIN_REASONS.items())
def test_each_positive_evidence_count_requires_matching_preserved_pin(
    count_field, pin_reason,
):
    season_evidence = _season_evidence()
    season_evidence["dates"][0]["evidence_counts"] = {
        field: int(field == count_field) for field in EVIDENCE_PIN_REASONS
    }

    report = retention.build_readiness_report(
        envelope=_envelope(), gate_c=_gate_c_manifest(),
        season_evidence=season_evidence, pins=_pins(reasons=[]),
        as_of="2026-08-18", raw_retention_days=30,
    )

    assert report["partitions"][0]["decision"] == "blocked_pinned_evidence"
    assert f"missing_preserved_pin_{pin_reason}" in report["partitions"][0]["reason_codes"]


@pytest.mark.parametrize("field", ["artifact", "generated_at", "jsonl_sha256", "summary_sha256"])
def test_incomplete_gate_c_manifest_cannot_produce_readiness(field):
    gate_c = _gate_c_manifest()
    del gate_c[field]
    with pytest.raises(ValueError):
        retention.build_readiness_report(
            envelope=_envelope(), gate_c=gate_c,
            season_evidence=_season_evidence(), pins=_pins(),
            as_of="2026-08-18", raw_retention_days=30,
        )


@pytest.mark.parametrize("artifact", [".", "data/.."])
def test_root_resolving_pin_path_cannot_be_preserved(artifact):
    pins = _pins()
    pins["partitions"][0]["pins"][0]["preserved_artifact"] = artifact
    report = retention.build_readiness_report(
        envelope=_envelope(), gate_c=_gate_c_manifest(),
        season_evidence=_season_evidence(), pins=pins,
        as_of="2026-08-18", raw_retention_days=30,
    )
    assert report["partitions"][0]["decision"] == "blocked_pinned_evidence"


@pytest.mark.parametrize("field", ["schema_version", "generated_at"])
def test_incomplete_pin_manifest_contract_cannot_produce_readiness(field):
    pins = _pins()
    del pins[field]
    with pytest.raises(ValueError):
        retention.build_readiness_report(
            envelope=_envelope(), gate_c=_gate_c_manifest(),
            season_evidence=_season_evidence(), pins=pins,
            as_of="2026-08-18", raw_retention_days=30,
        )


def test_pin_without_reason_cannot_produce_readiness():
    pins = _pins()
    del pins["partitions"][0]["pins"][0]["reason"]
    with pytest.raises(ValueError):
        retention.build_readiness_report(
            envelope=_envelope(), gate_c=_gate_c_manifest(),
            season_evidence=_season_evidence(), pins=pins,
            as_of="2026-08-18", raw_retention_days=30,
        )


def test_missing_gate_c_manifest_blocks_outcome_evidence():
    report = retention.build_readiness_report(
        envelope=_envelope(), gate_c=None,
        season_evidence=_season_evidence(), pins=_pins(),
        as_of="2026-08-18", raw_retention_days=30,
    )
    assert report["partitions"][0]["decision"] == "blocked_outcome_evidence"


def test_rendered_readiness_reports_are_closed_and_contain_no_secret_fields(tmp_path):
    report = retention.build_readiness_report(
        envelope=_envelope(), gate_c=_gate_c_manifest(),
        season_evidence=_season_evidence(), pins=_pins(),
        as_of="2026-08-18", raw_retention_days=30,
    )
    report["authorization"] = "Bearer secret"
    report["provider_summaries"][0]["api_key"] = "secret-value"
    paths = retention.write_report_pair(
        report=report, output_dir=tmp_path, stem="season_retention_readiness"
    )
    combined = paths["json"].read_text(encoding="utf-8") + paths["markdown"].read_text(encoding="utf-8")
    lowered = combined.lower()
    assert "deletion status: closed" in lowered
    assert "retention_execution_closed" in combined
    for forbidden in (
        "bearer secret", "secret-value", "api_key", "authorization",
        "delete from", "truncate table", "vacuum full",
    ):
        assert forbidden not in lowered


def test_readiness_main_returns_two_for_blocked_report_and_writes_outputs(tmp_path):
    query = tmp_path / "query.json"
    gate_c = tmp_path / "gate-c.json"
    query.write_text(json.dumps([{"retention_exact_coverage": _envelope(
        coverage=[_coverage(
            compact_group_count=3, exact_group_count=3,
            missing_compact_group_count=1, coverage_exact=False,
        )]
    )}]), encoding="utf-8")
    gate_c.write_text(json.dumps(_gate_c_manifest()), encoding="utf-8")
    exit_code = retention.main([
        "readiness", "--query-json", str(query), "--gate-c-manifest", str(gate_c),
        "--as-of", "2026-08-18", "--output-dir", str(tmp_path),
    ])
    assert exit_code == 2
    assert (tmp_path / "season_retention_readiness.json").exists()
    assert (tmp_path / "season_retention_readiness.md").exists()


def test_readiness_main_returns_zero_only_for_nonblocked_decisions(tmp_path):
    query = tmp_path / "query.json"
    gate_c = tmp_path / "gate-c.json"
    season = tmp_path / "season.json"
    pins = tmp_path / "pins.json"
    query.write_text(json.dumps([{"retention_exact_coverage": _envelope()}]), encoding="utf-8")
    gate_c.write_text(json.dumps(_gate_c_manifest()), encoding="utf-8")
    season.write_text(json.dumps(_season_evidence()), encoding="utf-8")
    pins.write_text(json.dumps(_pins()), encoding="utf-8")
    exit_code = retention.main([
        "readiness", "--query-json", str(query), "--gate-c-manifest", str(gate_c),
        "--season-evidence", str(season), "--pins", str(pins),
        "--as-of", "2026-08-18", "--output-dir", str(tmp_path),
    ])
    assert exit_code == 0


def test_main_returns_three_and_writes_no_report_for_invalid_input(tmp_path):
    query = tmp_path / "query.json"
    query.write_text("[]", encoding="utf-8")
    assert retention.main([
        "readiness", "--query-json", str(query),
        "--gate-c-manifest", str(tmp_path / "missing.json"),
        "--as-of", "2026-08-18", "--output-dir", str(tmp_path),
    ]) == 3
    assert not (tmp_path / "season_retention_readiness.json").exists()


@pytest.mark.parametrize("argv", [
    [],
    ["unknown-command"],
    ["readiness", "--unknown-option"],
])
def test_main_converts_malformed_argparse_invocations_to_exit_three(argv):
    assert retention.main(argv) == 3


def test_main_keeps_argparse_help_as_a_normal_exit():
    assert retention.main(["readiness", "--help"]) == 0


def test_parse_args_uses_repository_defaults_for_gate_c_and_output():
    args = retention.parse_args([
        "readiness", "--query-json", "query.json", "--as-of", "2026-08-18",
    ])

    assert Path(args.gate_c_manifest) == retention.DEFAULT_GATE_C_MANIFEST
    assert Path(args.output_dir) == retention.DEFAULT_OUTPUT_DIR


def test_readiness_markdown_states_closed_execution_and_no_production_authority():
    report = retention.build_readiness_report(
        envelope=_envelope(), gate_c=_gate_c_manifest(),
        season_evidence=_season_evidence(), pins=_pins(),
        as_of="2026-08-18", raw_retention_days=30,
    )

    markdown = retention.render_readiness_markdown(report)

    assert "**Deletion status: CLOSED**" in markdown
    assert "- Retention execution closed: `true`" in markdown
    assert "- Production authority: `none`" in markdown


def test_readiness_markdown_renders_deferred_reason_codes_for_recent_partitions():
    report = retention.build_readiness_report(
        envelope=_envelope(coverage=[_coverage(slate_date="2026-08-17")]),
        gate_c=_gate_c_manifest(), season_evidence=_season_evidence(), pins=_pins(),
        as_of="2026-08-18", raw_retention_days=30,
    )

    markdown = retention.render_readiness_markdown(report)

    assert "not_in_policy_window" in markdown
    assert "missing_season_evidence_date" in markdown
    assert "missing_pin_manifest_partition" in markdown


def test_boltodds_closure_preserves_trial_facts_without_runtime_authority():
    closure = retention.build_boltodds_closure(
        envelope=_envelope(), gate_c=_gate_c_manifest(),
        season_evidence=_season_evidence(), pins=_pins(), as_of="2026-08-18",
    )

    assert closure["provider"] == "boltodds"
    assert closure["documented_suspension_at"] == "2026-06-17T17:22:29+00:00"
    assert closure["runtime"]["last_snapshot_at"] == "2026-06-16T13:37:44+00:00"
    assert closure["runtime"]["books_seen"] == ["betmgm", "fanduel"]
    assert closure["production_authority"] == "none"
    assert closure["runtime_reactivation_approved"] is False
    assert closure["retention_execution_closed"] is True
    assert closure["deletion_approved"] is False
    assert closure["decision_impact_counts"] == {
        "official_tracked_picks": 2,
        "accepted_bets": 1,
        "sent_notifications": 1,
        "consumed_locks": 2,
        "frozen_alt_v2_rows": 0,
        "operator_incidents": 0,
        "model_review_pins": 0,
    }
    assert closure["outcome_preservation_summary"]["complete_dates"] == 1
    assert closure["pin_preservation_summary"]["preserved_pin_count"] == 4
    assert "BoltOdds-covered dates" in closure["production_impact_statement"]
    assert "not provider-causal attribution" in closure["production_impact_evidence_basis"]


def test_boltodds_closure_blocks_on_compaction_gaps_and_missing_preservation_inputs():
    envelope = _envelope(coverage=[_coverage(
        compact_group_count=3, exact_group_count=3,
        missing_compact_group_count=1, coverage_exact=False,
    )])

    closure = retention.build_boltodds_closure(
        envelope=envelope, gate_c=_gate_c_manifest(),
        season_evidence=None, pins=None, as_of="2026-08-18",
    )

    assert closure["status"] == "incomplete_evidence"
    assert "compaction_not_exact" in closure["unresolved_evidence_gaps"]
    assert "season_evidence_manifest_missing" in closure["unresolved_evidence_gaps"]
    assert "pin_manifest_missing" in closure["unresolved_evidence_gaps"]
    assert closure["recommendation"] == "complete_evidence_before_retention_review"


@pytest.mark.parametrize("runtime_field", ["last_snapshot_at", "last_heartbeat_at"])
def test_boltodds_closure_flags_any_post_suspension_runtime(runtime_field):
    runtime = _runtime(**{runtime_field: "2026-06-17T17:22:30+00:00"})

    closure = retention.build_boltodds_closure(
        envelope=_envelope(runtime=[runtime]), gate_c=_gate_c_manifest(),
        season_evidence=_season_evidence(), pins=_pins(), as_of="2026-08-18",
    )

    assert closure["status"] == "operational_exception"
    assert "post_suspension_runtime_evidence" in closure["unresolved_evidence_gaps"]


def test_boltodds_closure_blocks_provider_anomalies_even_when_coverage_is_exact():
    envelope = _envelope(anomalies=[{
        "provider": "boltodds", "rows_missing_run_id": 1,
        "rows_missing_run_row": 0, "rows_missing_group_key": 0,
        "provider_run_mismatch_rows": 0,
    }])

    closure = retention.build_boltodds_closure(
        envelope=envelope, gate_c=_gate_c_manifest(),
        season_evidence=_season_evidence(), pins=_pins(), as_of="2026-08-18",
    )

    assert closure["status"] == "incomplete_evidence"
    assert "rows_missing_run_id" in closure["unresolved_evidence_gaps"]


def test_boltodds_closure_validates_envelope_before_reading_evidence():
    envelope = _envelope()
    envelope["complete"] = False

    with pytest.raises(ValueError, match="complete must be true"):
        retention.build_boltodds_closure(
            envelope=envelope, gate_c=_gate_c_manifest(),
            season_evidence=_season_evidence(), pins=_pins(), as_of="2026-08-18",
        )


def test_boltodds_closure_cli_writes_sanitized_json_and_markdown(tmp_path):
    query = tmp_path / "query.json"
    gate_c = tmp_path / "gate-c.json"
    query.write_text(json.dumps([{"retention_exact_coverage": _envelope()}]), encoding="utf-8")
    gate_c.write_text(json.dumps(_gate_c_manifest()), encoding="utf-8")

    exit_code = retention.main([
        "boltodds-closure", "--query-json", str(query),
        "--gate-c-manifest", str(gate_c), "--as-of", "2026-08-18",
        "--output-dir", str(tmp_path),
    ])

    assert exit_code == 2
    json_path = tmp_path / "boltodds_retirement_closure.json"
    md_path = tmp_path / "boltodds_retirement_closure.md"
    assert json_path.exists() and md_path.exists()
    combined = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
    assert "Deletion status: CLOSED" in combined
    assert "does not authorize BoltOdds runtime reactivation" in combined
    assert "Decision-impact counts" in combined
    assert "Production-impact statement" in combined
    assert "source_payload" not in combined


def test_boltodds_closure_main_returns_zero_for_ready_report(tmp_path):
    query = tmp_path / "query.json"
    gate_c = tmp_path / "gate-c.json"
    season = tmp_path / "season.json"
    pins = tmp_path / "pins.json"
    query.write_text(
        json.dumps([{"retention_exact_coverage": _envelope()}]), encoding="utf-8"
    )
    gate_c.write_text(json.dumps(_gate_c_manifest()), encoding="utf-8")
    season.write_text(json.dumps(_season_evidence()), encoding="utf-8")
    pins.write_text(json.dumps(_pins()), encoding="utf-8")

    exit_code = retention.main([
        "boltodds-closure", "--query-json", str(query),
        "--gate-c-manifest", str(gate_c),
        "--season-evidence", str(season), "--pins", str(pins),
        "--as-of", "2026-08-18", "--output-dir", str(tmp_path),
    ])

    assert exit_code == 0
    report = json.loads(
        (tmp_path / "boltodds_retirement_closure.json").read_text(encoding="utf-8")
    )
    assert report["status"] == "ready_for_retirement_review"


def test_boltodds_closure_main_returns_three_and_writes_no_report_for_invalid_input(
    tmp_path,
):
    query = tmp_path / "query.json"
    gate_c = tmp_path / "gate-c.json"
    query.write_text("[]", encoding="utf-8")
    gate_c.write_text(json.dumps(_gate_c_manifest()), encoding="utf-8")

    exit_code = retention.main([
        "boltodds-closure", "--query-json", str(query),
        "--gate-c-manifest", str(gate_c),
        "--as-of", "2026-08-18", "--output-dir", str(tmp_path),
    ])

    assert exit_code == 3
    assert not (tmp_path / "boltodds_retirement_closure.json").exists()
    assert not (tmp_path / "boltodds_retirement_closure.md").exists()
