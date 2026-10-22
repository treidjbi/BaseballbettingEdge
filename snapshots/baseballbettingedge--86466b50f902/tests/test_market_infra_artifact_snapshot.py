import json

import pytest

from market_infra.artifact_snapshot import artifact_kind, artifact_snapshot_row, slate_date_from_path


def test_artifact_kind_classifies_known_json_files():
    assert artifact_kind("dashboard/data/processed/today.json") == "today"
    assert artifact_kind("dashboard/data/processed/2026-05-01.json") == "dated_slate"
    assert artifact_kind("dashboard/data/processed/steam.json") == "steam"
    assert artifact_kind("data/picks_history.json") == "picks_history"
    assert artifact_kind("data/preview_lines.json") == "preview_lines"
    assert artifact_kind("data/params.json") == "params"
    assert artifact_kind("dashboard/data/performance.json") == "performance"
    assert artifact_kind("data/something_else.json") == "other"


def test_slate_date_from_path_only_uses_dated_archives():
    assert slate_date_from_path("dashboard/data/processed/2026-05-01.json") == "2026-05-01"
    assert slate_date_from_path("dashboard/data/processed/today.json") is None


def test_artifact_snapshot_row_preserves_payload_and_hash(tmp_path):
    root = tmp_path
    artifact = root / "dashboard" / "data" / "processed" / "2026-05-01.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(json.dumps({"date": "2026-05-01", "pitchers": []}), encoding="utf-8")

    row = artifact_snapshot_row(
        artifact,
        repo_root=root,
        source_commit="abc123",
        metadata={"capture_reason": "test"},
    )

    assert row["artifact_path"] == "dashboard/data/processed/2026-05-01.json"
    assert row["artifact_kind"] == "dated_slate"
    assert row["slate_date"] == "2026-05-01"
    assert row["source_commit"] == "abc123"
    assert row["size_bytes"] > 0
    assert len(row["content_sha256"]) == 64
    assert row["payload"] == {"date": "2026-05-01", "pitchers": []}
    assert row["metadata"] == {"capture_reason": "test"}


def test_artifact_snapshot_row_rejects_invalid_json(tmp_path):
    artifact = tmp_path / "bad.json"
    artifact.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError):
        artifact_snapshot_row(artifact, repo_root=tmp_path)
