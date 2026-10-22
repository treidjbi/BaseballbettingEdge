from __future__ import annotations

import copy
import json
import subprocess
from datetime import datetime, timezone

import pytest

from scripts import bounded_retention_audit as audit
from scripts import retire_prepared_market_snapshots as executor


NOW = datetime(2026, 9, 2, 18, 5, tzinfo=timezone.utc)
BACKUP = "2026-09-02T18:00:00+00:00"


def valid_payload(
    provider: str = "propline",
    slate_date: str = "2026-06-12",
    *,
    raw_snapshot_rows: int = 2,
) -> dict:
    coverage = {
        "slate_date": slate_date,
        "provider": provider,
        "raw_snapshot_rows": raw_snapshot_rows,
        "raw_logical_bytes": raw_snapshot_rows * 10,
        "raw_group_count": 1,
        "compact_group_count": 1,
        "exact_group_count": 1,
        "mismatched_group_count": 0,
        "missing_compact_group_count": 0,
        "unexpected_compact_group_count": 0,
        "preserved_unexpected_compact_group_count": 0,
        "unpreserved_unexpected_compact_group_count": 0,
        "duplicate_compact_group_count": 0,
        "first_seen_mismatch_count": 0,
        "last_seen_mismatch_count": 0,
        "first_odds_mismatch_count": 0,
        "last_odds_mismatch_count": 0,
        "min_odds_mismatch_count": 0,
        "max_odds_mismatch_count": 0,
        "odds_move_count_mismatch_count": 0,
        "snapshot_count_mismatch_count": 0,
        "coverage_exact": True,
        "retention_preservation_complete": True,
        "first_raw_seen_at": f"{slate_date}T12:00:00+00:00",
        "last_raw_seen_at": f"{slate_date}T12:01:00+00:00",
    }
    anomalies = {
        "slate_date": slate_date,
        "provider": provider,
        "rows_missing_run_id": 0,
        "rows_missing_run_row": 0,
        "rows_missing_group_key": 0,
        "provider_run_mismatch_rows": 0,
        "slate_date_mismatch_rows": 0,
        "preserved_slate_date_mismatch_rows": 0,
        "unpreserved_slate_date_mismatch_rows": 0,
        "unknown_provider_rows": 0,
    }
    runtime = {
        "slate_date": slate_date,
        "provider": provider,
        "first_run_at": f"{slate_date}T12:00:00+00:00",
        "last_run_at": f"{slate_date}T12:01:00+00:00",
        "run_count": 1,
        "completed_run_count": 1,
        "failed_run_count": 0,
        "request_count": 1,
        "books_seen": ["fanduel"],
        "first_snapshot_at": f"{slate_date}T12:00:00+00:00",
        "last_snapshot_at": f"{slate_date}T12:01:00+00:00",
        "snapshot_count": raw_snapshot_rows,
        "snapshot_logical_bytes": raw_snapshot_rows * 10,
        "last_heartbeat_at": None,
        "last_message_at": None,
        "heartbeat_count": 0,
    }
    return {
        "chunk_version": 2,
        "audit_generated_at": "2026-09-02T18:04:00+00:00",
        "complete": True,
        "query_scope": {
            "start_date": slate_date,
            "end_date": slate_date,
            "provider": provider,
            "timezone": "America/Phoenix",
        },
        "coverage": [coverage],
        "source_anomalies": [anomalies],
        "candidate_runtime": [runtime],
    }


def completed(column: str, value: dict, *, returncode: int = 0):
    return subprocess.CompletedProcess(
        args=["npx", "supabase"],
        returncode=returncode,
        stdout=json.dumps([{column: value}]),
        stderr="",
    )


def make_report(payload: dict | None = None) -> dict:
    return executor.build_preview_report(
        payload or valid_payload(),
        provider="propline",
        slate_date="2026-06-12",
        backup_completed_at=BACKUP,
        generated_at=NOW,
    )


@pytest.mark.parametrize(
    ("provider", "slate_date"),
    [
        ("boltodds", "2026-06-12"),
        ("propline", "2026-06-11"),
        ("propline", "2026-07-01"),
        ("therundown", "2026-07-15"),
        ("therundown", "2026-07-27"),
    ],
)
def test_validate_scope_rejects_every_unprepared_partition(provider, slate_date):
    with pytest.raises(ValueError, match="outside the prepared scope"):
        executor.validate_scope(provider, slate_date)


def test_validate_scope_accepts_only_one_fixed_provider_date():
    assert executor.validate_scope("propline", "2026-06-12") == (
        "propline",
        "2026-06-12",
    )
    assert executor.validate_scope("therundown", "2026-07-26") == (
        "therundown",
        "2026-07-26",
    )


def test_preview_report_binds_exact_state_and_new_backup():
    report = make_report()

    assert report["scope_id"] == "prepared_active_provider_scope_v1"
    assert report["provider"] == "propline"
    assert report["slate_date"] == "2026-06-12"
    assert report["source_state"]["raw_snapshot_rows"] == 2
    assert report["source_state"]["raw_logical_bytes"] == 20
    assert report["source_state"]["compact_group_count"] == 1
    assert report["backup_completed_at"] == BACKUP
    assert report["deletion_approved"] is False
    assert report["retention_execution_closed"] is True
    assert len(report["approval_token"]) == 64
    assert report["delete_sql_sha256"] == executor.sha256_text(
        executor.build_delete_sql(report)
    )
    executor.validate_preview_report(report, now=NOW)


def test_preview_report_rejects_stale_backup_or_nonexact_coverage():
    with pytest.raises(ValueError, match="backup is not newer"):
        executor.build_preview_report(
            valid_payload(),
            provider="propline",
            slate_date="2026-06-12",
            backup_completed_at="2026-08-28T05:45:45+00:00",
            generated_at=NOW,
        )

    payload = valid_payload()
    coverage = payload["coverage"][0]
    coverage["coverage_exact"] = False
    coverage["retention_preservation_complete"] = False
    coverage["exact_group_count"] = 0
    coverage["mismatched_group_count"] = 1
    coverage["snapshot_count_mismatch_count"] = 1
    with pytest.raises(ValueError, match="exact compact coverage"):
        make_report(payload)


def test_preview_report_accepts_fully_preserved_cross_date_lineage():
    payload = valid_payload()
    payload["source_anomalies"][0].update({
        "slate_date_mismatch_rows": 2,
        "preserved_slate_date_mismatch_rows": 2,
        "unpreserved_slate_date_mismatch_rows": 0,
    })

    report = make_report(payload)

    assert report["source_state"]["source_anomalies"] == {
        "rows_missing_run_id": 0,
        "rows_missing_run_row": 0,
        "rows_missing_group_key": 0,
        "provider_run_mismatch_rows": 0,
        "slate_date_mismatch_rows": 2,
        "preserved_slate_date_mismatch_rows": 2,
        "unpreserved_slate_date_mismatch_rows": 0,
        "unknown_provider_rows": 0,
    }
    executor.validate_preview_report(report, now=NOW)


def test_preview_report_rejects_unpreserved_cross_date_lineage():
    payload = valid_payload()
    payload["source_anomalies"][0].update({
        "slate_date_mismatch_rows": 1,
        "preserved_slate_date_mismatch_rows": 0,
        "unpreserved_slate_date_mismatch_rows": 1,
    })

    with pytest.raises(ValueError, match="source anomalies block"):
        make_report(payload)


def test_delete_sql_is_one_exact_cardinality_gated_partition():
    report = make_report()
    sql = executor.build_delete_sql(report)
    lowered = " ".join(sql.lower().split())

    assert sql.count(";") == 1
    assert lowered.startswith("with ")
    assert lowered.count("delete from public.market_snapshots") == 1
    assert "mpr.provider = 'propline'" in lowered
    assert "mpr.slate_date = date '2026-06-12'" in lowered
    assert "raw_snapshot_rows = 2" in lowered
    assert "raw_logical_bytes = 20" in lowered
    assert "compact_group_count = 1" in lowered
    assert "represented_snapshot_rows = 2" in lowered
    assert "older-than" not in lowered
    assert "current_date" not in lowered
    executor.assert_delete_sql_contract(sql)


@pytest.mark.parametrize(
    "environment",
    [
        {},
        {"ALLOW_MARKET_SNAPSHOT_DELETE": "true"},
        {"APPROVED_PREPARED_MARKET_SNAPSHOT_DELETE_TOKEN": "wrong"},
    ],
)
def test_execute_requires_both_environment_gates_before_any_query(environment):
    calls = []

    with pytest.raises(ValueError, match="execution gate"):
        executor.execute_approved_partition(
            make_report(),
            query_runner=lambda sql, allow_mutation=False: calls.append(
                (sql, allow_mutation)
            ),
            environment=environment,
            now=NOW,
        )

    assert calls == []


@pytest.mark.parametrize(
    "acknowledgements",
    [
        [],
        ["--execute"],
        ["--run-linked-delete"],
    ],
)
def test_execute_cli_requires_both_acknowledgements_before_loading_report(
    acknowledgements, tmp_path
):
    output = tmp_path / "result.json"

    returncode = executor.main(
        [
            "execute",
            "--preview-report",
            str(tmp_path / "missing-preview.json"),
            "--output",
            str(output),
            *acknowledgements,
        ]
    )

    assert returncode == 3
    assert not output.exists()


def test_execute_rechecks_then_removes_one_partition_and_postchecks():
    report = make_report()
    calls: list[tuple[str, bool]] = []

    def runner(sql: str, *, allow_mutation: bool = False):
        calls.append((sql, allow_mutation))
        if allow_mutation:
            return completed(
                "prepared_market_snapshot_deletion",
                {
                    "provider": "propline",
                    "slate_date": "2026-06-12",
                    "source_state_matches": True,
                    "candidate_rows": 2,
                    "deleted_rows": 2,
                },
            )
        if "prepared_market_snapshot_postcheck" in sql:
            return completed(
                "prepared_market_snapshot_postcheck",
                {
                    "provider": "propline",
                    "slate_date": "2026-06-12",
                    "raw_snapshot_rows": 0,
                    "compact_group_count": 1,
                    "represented_snapshot_rows": 2,
                },
            )
        return completed("retention_bounded_chunk", valid_payload())

    result = executor.execute_approved_partition(
        report,
        query_runner=runner,
        environment={
            "ALLOW_MARKET_SNAPSHOT_DELETE": "true",
            "APPROVED_PREPARED_MARKET_SNAPSHOT_DELETE_TOKEN": report[
                "approval_token"
            ],
        },
        now=NOW,
    )

    assert result["status"] == "confirmed"
    assert result["deleted_rows"] == 2
    assert [allow_mutation for _sql, allow_mutation in calls] == [False, True, False]


def test_execute_fails_closed_if_fresh_preview_differs():
    report = make_report()
    changed = valid_payload(raw_snapshot_rows=3)
    calls: list[tuple[str, bool]] = []

    def runner(sql: str, *, allow_mutation: bool = False):
        calls.append((sql, allow_mutation))
        return completed("retention_bounded_chunk", changed)

    with pytest.raises(ValueError, match="source state changed"):
        executor.execute_approved_partition(
            report,
            query_runner=runner,
            environment={
                "ALLOW_MARKET_SNAPSHOT_DELETE": "true",
                "APPROVED_PREPARED_MARKET_SNAPSHOT_DELETE_TOKEN": report[
                    "approval_token"
                ],
            },
            now=NOW,
        )

    assert [allow_mutation for _sql, allow_mutation in calls] == [False]


def test_execute_never_retries_or_claims_success_after_transport_failure():
    report = make_report()
    calls: list[tuple[str, bool]] = []

    def runner(sql: str, *, allow_mutation: bool = False):
        calls.append((sql, allow_mutation))
        if allow_mutation:
            return subprocess.CompletedProcess(
                args=["npx", "supabase"], returncode=1, stdout="", stderr="timeout"
            )
        if "prepared_market_snapshot_postcheck" in sql:
            return completed(
                "prepared_market_snapshot_postcheck",
                {
                    "provider": "propline",
                    "slate_date": "2026-06-12",
                    "raw_snapshot_rows": 2,
                    "compact_group_count": 1,
                    "represented_snapshot_rows": 2,
                },
            )
        return completed("retention_bounded_chunk", valid_payload())

    result = executor.execute_approved_partition(
        report,
        query_runner=runner,
        environment={
            "ALLOW_MARKET_SNAPSHOT_DELETE": "true",
            "APPROVED_PREPARED_MARKET_SNAPSHOT_DELETE_TOKEN": report[
                "approval_token"
            ],
        },
        now=NOW,
    )

    assert result["status"] == "uncertain_transport"
    assert result["deleted_rows"] is None
    assert [allow_mutation for _sql, allow_mutation in calls] == [False, True, False]


def test_preview_report_tampering_breaks_the_approved_token():
    report = make_report()
    tampered = copy.deepcopy(report)
    tampered["source_state"]["raw_snapshot_rows"] = 3

    with pytest.raises(ValueError, match="approval token"):
        executor.validate_preview_report(tampered, now=NOW)


def test_preview_report_expires_after_24_hours():
    report = make_report()

    with pytest.raises(ValueError, match="window is invalid or expired"):
        executor.validate_preview_report(
            report,
            now=datetime(2026, 9, 3, 18, 5, tzinfo=timezone.utc),
        )


def test_result_writer_refuses_to_overwrite_a_partition_ledger(tmp_path):
    output = tmp_path / "result.json"
    executor._write_new_json(output, {"status": "first"})

    with pytest.raises(ValueError, match="already exists"):
        executor._write_new_json(output, {"status": "second"})

    assert json.loads(output.read_text(encoding="utf-8")) == {"status": "first"}
