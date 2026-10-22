from pathlib import Path

from market_infra.published_artifacts import (
    artifact_key,
    artifact_type_from_path,
    build_artifact_row,
    canonical_payload_sha256,
)


def test_artifact_type_from_path_maps_known_outputs():
    assert artifact_type_from_path(Path("dashboard/data/processed/today.json")) == "today"
    assert artifact_type_from_path(Path("dashboard/data/processed/2026-05-22.json")) == "dated_slate"
    assert artifact_type_from_path(Path("dashboard/data/processed/index.json")) == "index"
    assert artifact_type_from_path(Path("dashboard/data/processed/steam.json")) == "steam"
    assert artifact_type_from_path(Path("dashboard/data/performance.json")) == "performance"
    assert artifact_type_from_path(Path("data/params.json")) == "params"
    assert artifact_type_from_path(Path("data/preview_lines.json")) == "preview_lines"
    assert artifact_type_from_path(Path("data/picks_history.json")) == "picks_history"
    assert artifact_type_from_path(Path("data/fangraphs_cache.json")) == "fangraphs_cache"


def test_artifact_key_is_stable():
    assert artifact_key("today", None) == "today"
    assert artifact_key("dated_slate", "2026-05-22") == "dated_slate:2026-05-22"
    assert artifact_key("fangraphs_cache", None) == "fangraphs_cache"


def test_canonical_payload_sha256_ignores_json_key_order():
    left = {"b": 2, "a": 1}
    right = {"a": 1, "b": 2}
    assert canonical_payload_sha256(left) == canonical_payload_sha256(right)


def test_build_artifact_row_extracts_date_and_generated_at(tmp_path):
    path = tmp_path / "dashboard" / "data" / "processed" / "2026-05-22.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"date":"2026-05-22","generated_at":"2026-05-22T15:41:07Z","pitchers":[]}',
        encoding="utf-8",
    )

    row = build_artifact_row(
        root=tmp_path,
        path=path,
        source="github_actions",
        source_run_id="26297280674",
        source_commit_sha="9cd8a02b",
    )

    assert row["artifact_key"] == "dated_slate:2026-05-22"
    assert row["artifact_type"] == "dated_slate"
    assert row["slate_date"] == "2026-05-22"
    assert row["generated_at"] == "2026-05-22T15:41:07Z"
    assert row["source"] == "github_actions"
    assert row["source_run_id"] == "26297280674"
    assert row["source_commit_sha"] == "9cd8a02b"
    assert row["metadata"]["artifact_path"].endswith("dashboard/data/processed/2026-05-22.json")


def test_build_artifact_row_accepts_list_payloads(tmp_path):
    path = tmp_path / "data" / "picks_history.json"
    path.parent.mkdir(parents=True)
    path.write_text('[{"date":"2026-05-22","pitcher":"Example Pitcher"}]', encoding="utf-8")

    row = build_artifact_row(
        root=tmp_path,
        path=path,
        source="github_actions",
        source_run_id="run-1",
        source_commit_sha="sha",
    )

    assert row["artifact_key"] == "picks_history"
    assert row["artifact_type"] == "picks_history"
    assert row["slate_date"] is None
    assert row["generated_at"] is None
