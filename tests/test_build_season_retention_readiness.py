from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_season_retention_readiness as retention


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "scripts" / "supabase_retention_exact_coverage.sql"
REPORTER_PATH = ROOT / "scripts" / "build_season_retention_readiness.py"


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
    assert "order by observed_at desc, id desc" in sql
    assert "lag(american_odds)" in sql
    assert "pg_column_size" in sql


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
        "snapshot_count": 611972, "snapshot_logical_bytes": 461536160,
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


def _pins(*, reconciled=True, status="preserved"):
    return {
        "schema_version": 1, "generated_at": "2026-08-18T18:00:00+00:00",
        "partitions": [{
            "slate_date": "2026-06-01", "provider": "boltodds",
            "reconciled": reconciled,
            "pins": [{
                "reason": "accepted_bet", "status": status,
                "preserved_artifact": "data/picks_history.json",
            }],
        }],
    }


def _gate_c_manifest():
    return {
        "artifact": "gate_c_pitcher_k_outcome_dataset",
        "generated_at": "2026-08-18T17:00:00+00:00",
        "loaded_slate_dates": ["2026-06-01"],
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
    row = _coverage(**{
        field: 1,
        "mismatched_group_count": 1 if metric_mismatch else 0,
        "coverage_exact": False,
    })
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
    del record["required_evidence"]
    report = retention.build_readiness_report(
        envelope=_envelope(), gate_c=_gate_c_manifest(),
        season_evidence=season_evidence, pins=_pins(),
        as_of="2026-08-18", raw_retention_days=30,
    )
    assert report["partitions"][0]["decision"] == "ready_for_retention_review"


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
        coverage=[_coverage(missing_compact_group_count=1, coverage_exact=False)]
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


def test_boltodds_closure_blocks_on_compaction_gaps_and_missing_preservation_inputs():
    envelope = _envelope(coverage=[_coverage(
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
