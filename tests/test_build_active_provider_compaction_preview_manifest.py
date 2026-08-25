import json
from pathlib import Path

import pytest

from scripts import build_active_provider_compaction_preview_manifest as manifest_builder


def _coverage(
    provider,
    slate_date,
    *,
    raw_rows=100,
    raw_groups=10,
    compact_groups=10,
    missing=0,
    mismatched=0,
    unexpected=0,
    unpreserved=0,
):
    return {
        "provider": provider,
        "slate_date": slate_date,
        "raw_snapshot_rows": raw_rows,
        "raw_group_count": raw_groups,
        "compact_group_count": compact_groups,
        "missing_compact_group_count": missing,
        "mismatched_group_count": mismatched,
        "unexpected_compact_group_count": unexpected,
        "unpreserved_unexpected_compact_group_count": unpreserved,
        "first_raw_seen_at": f"{slate_date}T14:00:00Z" if raw_rows else None,
        "last_raw_seen_at": f"{slate_date}T23:00:00Z" if raw_rows else None,
    }


def _write_checkpoint(path, provider, coverage, *, contract_hash="contract-hash"):
    path.write_text(
        json.dumps(
            {
                "as_of_date": "2026-08-25",
                "status": "completed",
                "complete": True,
                "validation": "passed",
                "provider": provider,
                "query_contract_sha256": contract_hash,
                "payload": {
                    "audit_generated_at": "2026-08-25T12:00:00Z",
                    "complete": True,
                    "coverage": coverage,
                    "source_anomalies": [],
                },
            }
        ),
        encoding="utf-8",
    )


def _complete_fixture(tmp_path):
    _write_checkpoint(
        tmp_path / "checkpoint-propline.json",
        "propline",
        [
            _coverage("propline", "2026-05-16", missing=2, mismatched=3),
            _coverage(
                "propline",
                "2026-05-17",
                unexpected=24,
                unpreserved=24,
            ),
        ],
    )
    _write_checkpoint(
        tmp_path / "checkpoint-therundown.json",
        "therundown",
        [
            _coverage("therundown", "2026-05-16", raw_rows=200, mismatched=4),
            _coverage("therundown", "2026-05-17", raw_rows=200),
        ],
    )


def test_build_manifest_requires_complete_shared_dates_and_emits_aggregate_only(tmp_path):
    _complete_fixture(tmp_path)

    report = manifest_builder.build_manifest(tmp_path)

    assert report["report_type"] == "active_provider_compaction_preview_manifest"
    assert report["source_query_contract_sha256"] == "contract-hash"
    assert report["source_audit_date"] == "2026-08-25"
    assert report["date_range"] == {
        "start_date": "2026-05-16",
        "end_date": "2026-05-17",
        "dates_per_provider": 2,
    }
    assert report["repair_partition_count"] == 2
    assert report["rows_to_upsert_count"] == 9
    assert report["provider_totals"]["propline"]["repair_partition_count"] == 1
    assert report["provider_totals"]["propline"]["rows_to_upsert_count"] == 5
    assert report["provider_totals"]["therundown"]["repair_partition_count"] == 1
    assert report["provider_totals"]["therundown"]["rows_to_upsert_count"] == 4
    assert report["repair_partitions"][0]["rows_to_upsert_count"] == 5
    assert report["preservation_only_partitions"] == [
        {
            "provider": "propline",
            "slate_date": "2026-05-17",
            "unexpected_compact_group_count": 24,
            "unpreserved_unexpected_compact_group_count": 24,
        }
    ]
    assert report["database_write_performed"] is False
    assert report["deletion_approved"] is False
    assert report["retention_execution_closed"] is True
    rendered = json.dumps(report, sort_keys=True)
    assert "source_snapshot_ids" not in rendered
    assert "run_id" not in rendered


def test_build_manifest_rejects_mixed_query_contracts(tmp_path):
    _complete_fixture(tmp_path)
    second = tmp_path / "checkpoint-therundown.json"
    payload = json.loads(second.read_text(encoding="utf-8"))
    payload["query_contract_sha256"] = "different-contract"
    second.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="one query-contract hash"):
        manifest_builder.build_manifest(tmp_path)


def test_build_manifest_rejects_missing_provider_date(tmp_path):
    _complete_fixture(tmp_path)
    second = tmp_path / "checkpoint-therundown.json"
    payload = json.loads(second.read_text(encoding="utf-8"))
    payload["payload"]["coverage"].pop()
    second.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="same contiguous date coverage"):
        manifest_builder.build_manifest(tmp_path)


def test_write_manifest_refuses_to_overwrite_existing_evidence(tmp_path):
    output = tmp_path / "preview.json"
    output.write_text("preserve me", encoding="utf-8")

    with pytest.raises(FileExistsError, match="refusing to overwrite"):
        manifest_builder.write_manifest(output, {"report_type": "preview"})

    assert output.read_text(encoding="utf-8") == "preserve me"


def test_cli_writes_one_local_manifest_without_supabase_dependency(tmp_path):
    checkpoints = tmp_path / "checkpoints"
    checkpoints.mkdir()
    _complete_fixture(checkpoints)
    output = tmp_path / "preview.json"

    exit_code = manifest_builder.main(
        ["--checkpoint-dir", str(checkpoints), "--output", str(output)]
    )

    assert exit_code == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["repair_partition_count"] == 2
    assert report["database_write_performed"] is False
