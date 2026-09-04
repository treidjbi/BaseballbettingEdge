from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest

from scripts import prepare_prepared_market_snapshot_tranche as tranche
from scripts import retire_prepared_market_snapshots as executor


NOW = datetime(2026, 9, 4, 4, 30, tzinfo=timezone.utc)
BACKUP = "2026-09-03T05:43:13.129Z"
TRANCHE_ID = "tranche-v2-001"


def valid_payload(provider: str, slate_date: str, rows: int = 2) -> dict:
    coverage = {
        "slate_date": slate_date,
        "provider": provider,
        "raw_snapshot_rows": rows,
        "raw_logical_bytes": rows * 10,
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
        "snapshot_count": rows,
        "snapshot_logical_bytes": rows * 10,
        "last_heartbeat_at": None,
        "last_message_at": None,
        "heartbeat_count": 0,
    }
    return {
        "chunk_version": 2,
        "audit_generated_at": NOW.isoformat(),
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


def completed(provider: str, slate_date: str, *, returncode: int = 0):
    return subprocess.CompletedProcess(
        args=["npx", "supabase"],
        returncode=returncode,
        stdout=json.dumps(
            [{"retention_bounded_chunk": valid_payload(provider, slate_date)}]
        ),
        stderr="" if returncode == 0 else "failed",
    )


def test_fixed_queue_excludes_completed_partition_and_covers_remaining_scope():
    queue = tranche.build_queue_manifest(generated_at=NOW)
    partitions = [
        (item["provider"], item["slate_date"])
        for batch in queue["tranches"]
        for item in batch["partitions"]
    ]

    assert len(partitions) == 79
    assert len(set(partitions)) == 79
    assert ("propline", "2026-06-12") not in partitions
    assert ("therundown", "2026-06-12") not in partitions
    assert ("propline", "2026-06-13") not in partitions
    assert partitions[:5] == [
        ("propline", "2026-07-26"),
        ("therundown", "2026-07-26"),
        ("propline", "2026-07-25"),
        ("therundown", "2026-07-25"),
        ("propline", "2026-07-24"),
    ]
    assert partitions[-1] == ("therundown", "2026-06-13")
    assert len(queue["tranches"]) == 16
    assert max(len(batch["partitions"]) for batch in queue["tranches"]) == 5
    assert queue["queue_version"] == 2
    assert queue["queue_order"] == (
        "slate_date_descending_then_propline_before_therundown"
    )
    assert queue["remaining_partition_count"] == 79
    assert queue["deletion_approved"] is False
    assert queue["retention_execution_closed"] is True


def test_queue_requires_the_immutable_confirmed_completion(monkeypatch, tmp_path):
    changed = dict(tranche.CONFIRMED_COMPLETIONS[0])
    changed["result_path"] = str(tmp_path / "missing-result.json")
    monkeypatch.setattr(
        tranche,
        "CONFIRMED_COMPLETIONS",
        (changed, *tranche.CONFIRMED_COMPLETIONS[1:]),
    )

    with pytest.raises(ValueError, match="confirmed completion result"):
        tranche.build_queue_manifest(generated_at=NOW)


def test_descending_order_is_bound_to_live_cross_date_direction_proof():
    proof = tranche.load_ordering_proof()

    tranche.validate_ordering_proof(proof)
    assert proof["remaining_raw_rows"] == 1785407
    assert proof["rows_observed_before_run_date"] == 0
    assert proof["min_day_offset"] == 0
    assert proof["max_day_offset"] == 1
    assert {item["provider"] for item in proof["providers"]} == {
        "propline",
        "therundown",
    }

    changed = json.loads(json.dumps(proof))
    changed["providers"][0]["rows_observed_before_run_date"] = 1
    with pytest.raises(ValueError, match="ordering proof"):
        tranche.validate_ordering_proof(changed)


def test_ordering_proof_sql_is_select_only_and_bounded_to_prepared_scope():
    sql = Path(
        "scripts/supabase_prepared_snapshot_ordering_proof.sql"
    ).read_text(encoding="utf-8")

    executor.bounded_sql.assert_select_only(sql)
    assert "2026-06-12" in sql
    assert "2026-07-26" in sql
    assert "propline" in sql
    assert "therundown" in sql
    assert "observed_before_run_date" in sql


def test_prepare_tranche_queries_every_partition_read_only_before_writing(tmp_path):
    calls: list[tuple[str, str, bool]] = []

    def runner(sql: str, *, allow_mutation: bool = False):
        batch = tranche.expected_tranche(TRANCHE_ID)
        provider, slate_date = batch[len(calls)]
        calls.append((provider, slate_date, allow_mutation))
        return completed(provider, slate_date)

    output_dir = tmp_path / "packet"
    report = tranche.prepare_tranche(
        TRANCHE_ID,
        backup_completed_at=BACKUP,
        output_dir=output_dir,
        query_runner=runner,
        generated_at=NOW,
    )

    assert calls == [
        (provider, slate_date, False)
        for provider, slate_date in tranche.expected_tranche(TRANCHE_ID)
    ]
    assert report["partition_count"] == 5
    assert report["total_raw_snapshot_rows"] == 10
    assert report["total_raw_logical_bytes"] == 100
    assert report["total_compact_groups"] == 5
    assert report["deletion_approved"] is False
    assert report["retention_execution_closed"] is True
    assert report["automatic_execution_enabled"] is False
    assert report["vacuum_allowed"] is False
    assert len(report["approval_token"]) == 64
    assert (output_dir / "tranche-report.json").exists()
    assert len(list(output_dir.glob("preview-*.json"))) == 5
    tranche.validate_tranche_report(report, now=NOW)


def test_prepare_tranche_failure_leaves_no_partial_packet(tmp_path):
    calls = 0

    def runner(sql: str, *, allow_mutation: bool = False):
        nonlocal calls
        provider, slate_date = tranche.expected_tranche(TRANCHE_ID)[calls]
        calls += 1
        if calls == 3:
            return completed(provider, slate_date, returncode=1)
        return completed(provider, slate_date)

    output_dir = tmp_path / "packet"
    with pytest.raises(ValueError, match="exact preview query failed"):
        tranche.prepare_tranche(
            TRANCHE_ID,
            backup_completed_at=BACKUP,
            output_dir=output_dir,
            query_runner=runner,
            generated_at=NOW,
        )

    assert calls == 3
    assert not output_dir.exists()


def test_unknown_tranche_and_existing_output_fail_before_query(tmp_path):
    calls = []
    with pytest.raises(ValueError, match="unknown tranche"):
        tranche.prepare_tranche(
            "tranche-999",
            backup_completed_at=BACKUP,
            output_dir=tmp_path / "packet",
            query_runner=lambda *args, **kwargs: calls.append(args),
            generated_at=NOW,
        )
    assert calls == []

    output_dir = tmp_path / "existing"
    output_dir.mkdir()
    with pytest.raises(ValueError, match="output directory already exists"):
        tranche.prepare_tranche(
            TRANCHE_ID,
            backup_completed_at=BACKUP,
            output_dir=output_dir,
            query_runner=lambda *args, **kwargs: calls.append(args),
            generated_at=NOW,
        )
    assert calls == []


def test_tranche_safety_cap_fails_before_writing(tmp_path):
    call_index = 0

    def runner(sql: str, *, allow_mutation: bool = False):
        nonlocal call_index
        provider, slate_date = tranche.expected_tranche(TRANCHE_ID)[call_index]
        call_index += 1
        rows = tranche.MAX_TRANCHE_RAW_SNAPSHOT_ROWS + 1 if call_index == 1 else 2
        return subprocess.CompletedProcess(
            args=["npx", "supabase"],
            returncode=0,
            stdout=json.dumps(
                [{"retention_bounded_chunk": valid_payload(provider, slate_date, rows)}]
            ),
            stderr="",
        )

    output_dir = tmp_path / "too-large"
    with pytest.raises(ValueError, match="raw row safety cap"):
        tranche.prepare_tranche(
            TRANCHE_ID,
            backup_completed_at=BACKUP,
            output_dir=output_dir,
            query_runner=runner,
            generated_at=NOW,
        )

    assert call_index == 5
    assert not output_dir.exists()


def test_tranche_report_tampering_or_changed_preview_file_fails(tmp_path):
    call_index = 0

    def runner(sql: str, *, allow_mutation: bool = False):
        nonlocal call_index
        provider, slate_date = tranche.expected_tranche(TRANCHE_ID)[call_index]
        call_index += 1
        return completed(provider, slate_date)

    report = tranche.prepare_tranche(
        TRANCHE_ID,
        backup_completed_at=BACKUP,
        output_dir=tmp_path / "packet",
        query_runner=runner,
        generated_at=NOW,
    )
    report["total_raw_snapshot_rows"] = 11
    with pytest.raises(ValueError, match="approval token"):
        tranche.validate_tranche_report(report, now=NOW)

    stored = json.loads((tmp_path / "packet" / "tranche-report.json").read_text())
    preview_path = stored["partitions"][0]["preview_report_path"]
    with open(preview_path, "a", encoding="utf-8") as handle:
        handle.write("\n")
    with pytest.raises(ValueError, match="preview report hash"):
        tranche.validate_tranche_report(stored, now=NOW)


def test_cli_requires_read_acknowledgement_before_query(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        tranche,
        "prepare_tranche",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    result = tranche.main(
        [
            "preview",
            "--tranche-id",
            TRANCHE_ID,
            "--backup-completed-at",
            BACKUP,
            "--output-dir",
            str(tmp_path / "packet"),
        ]
    )

    assert result == 3
    assert calls == []


def test_packet_commands_retain_single_partition_executor_gates(tmp_path):
    call_index = 0

    def runner(sql: str, *, allow_mutation: bool = False):
        nonlocal call_index
        provider, slate_date = tranche.expected_tranche(TRANCHE_ID)[call_index]
        call_index += 1
        return completed(provider, slate_date)

    report = tranche.prepare_tranche(
        TRANCHE_ID,
        backup_completed_at=BACKUP,
        output_dir=tmp_path / "packet",
        query_runner=runner,
        generated_at=NOW,
    )

    assert len(report["proposed_commands"]) == 5
    for item, command in zip(report["partitions"], report["proposed_commands"]):
        preview = json.loads(Path(item["preview_report_path"]).read_text())
        assert executor.DELETE_ALLOW_ENV in command
        assert preview["approval_token"] in command
        assert "--execute" in command
        assert "--run-linked-delete" in command
        assert "vacuum" not in command.lower()
