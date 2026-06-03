import json

from scripts import build_pitcher_k_outcome_dataset as builder


def _row(dataset_key: str, *, slate_date: str = "2026-05-12", tracked: bool = True) -> dict:
    return {
        "dataset_key": dataset_key,
        "slate_date": slate_date,
        "is_tracked_pick": tracked,
        "result": "win",
    }


def test_build_research_artifact_writes_jsonl_summary_and_manifest(tmp_path, monkeypatch):
    rows = [
        _row("2026-05-12:official_close:a:over:5.5"),
        _row("2026-05-12:official_close:a:under:5.5", tracked=False),
    ]

    monkeypatch.setattr(builder.dataset, "build_dataset", lambda **kwargs: rows)
    monkeypatch.setattr(builder.dataset, "validate_dataset_row", lambda row: [])
    monkeypatch.setattr(
        builder.dataset,
        "build_summary",
        lambda rows: {
            "total_rows": len(rows),
            "tracked_pick_rows": sum(1 for row in rows if row["is_tracked_pick"]),
            "duplicate_dataset_keys": 0,
        },
    )
    monkeypatch.setattr(
        builder.dataset,
        "reconcile_picks_history",
        lambda rows, **kwargs: {
            "graded_pick_rows": 1,
            "matched_pick_rows": 1,
            "unmatched_pick_rows": 0,
        },
    )
    monkeypatch.setattr(builder.dataset, "render_summary", lambda summary: "# Summary\n")

    result = builder.build_research_artifact(
        output_dir=tmp_path,
        artifact_source="local",
        start_date="2026-05-12",
        end_date="2026-05-12",
    )

    assert result["manifest"]["row_count"] == 2
    assert result["manifest"]["tracked_pick_rows"] == 1
    assert result["manifest"]["reconciliation"] == {
        "graded_pick_rows": 1,
        "matched_pick_rows": 1,
        "unmatched_pick_rows": 0,
    }
    assert result["manifest"]["source"] == {
        "artifact_source": "local",
        "artifact_api_url": None,
        "start_date": "2026-05-12",
        "end_date": "2026-05-12",
        "production_fill_dates": [],
    }
    assert result["manifest"]["shadow_only"] is True
    assert result["jsonl_path"].name == "pitcher_k_outcome_dataset.jsonl"
    assert result["summary_path"].name == "pitcher_k_outcome_dataset_summary.md"
    assert result["manifest_path"].name == "pitcher_k_outcome_dataset_manifest.json"
    assert (tmp_path / "pitcher_k_outcome_dataset.jsonl").read_text(encoding="utf-8").count("\n") == 2
    manifest = json.loads((tmp_path / "pitcher_k_outcome_dataset_manifest.json").read_text(encoding="utf-8"))
    assert manifest["row_count"] == 2
    assert manifest["jsonl_sha256"]
    assert manifest["summary_sha256"]


def test_build_research_artifact_exits_on_validation_error(tmp_path, monkeypatch):
    rows = [_row("bad")]

    monkeypatch.setattr(builder.dataset, "build_dataset", lambda **kwargs: rows)
    monkeypatch.setattr(builder.dataset, "validate_dataset_row", lambda row: ["bad row"])

    try:
        builder.build_research_artifact(
            output_dir=tmp_path,
            artifact_source="local",
            start_date="2026-05-12",
            end_date="2026-05-12",
        )
    except SystemExit as error:
        assert "Dataset validation failed" in str(error)
    else:
        raise AssertionError("expected validation failure")


def test_hybrid_source_adds_production_only_graded_dates(tmp_path, monkeypatch):
    local_rows = [_row("2026-05-30:official_close:a:over:5.5", slate_date="2026-05-30")]
    production_rows = [_row("2026-06-01:official_close:b:over:5.5", slate_date="2026-06-01")]
    calls = []

    def fake_build_dataset(**kwargs):
        calls.append(kwargs)
        if kwargs.get("artifact_api_url"):
            return production_rows
        return local_rows

    monkeypatch.setattr(builder.dataset, "build_dataset", fake_build_dataset)
    monkeypatch.setattr(builder.dataset, "validate_dataset_row", lambda row: [])
    monkeypatch.setattr(
        builder.dataset,
        "build_summary",
        lambda rows: {
            "total_rows": len(rows),
            "tracked_pick_rows": len(rows),
            "duplicate_dataset_keys": 0,
        },
    )
    monkeypatch.setattr(
        builder.dataset,
        "reconcile_picks_history",
        lambda rows, **kwargs: {
            "graded_pick_rows": len(rows),
            "matched_pick_rows": len(rows),
            "unmatched_pick_rows": 0,
        },
    )
    monkeypatch.setattr(builder.dataset, "render_summary", lambda summary: "# Summary\n")
    monkeypatch.setattr(builder, "_graded_history_dates", lambda **kwargs: ["2026-05-30", "2026-06-01"])

    result = builder.build_research_artifact(
        output_dir=tmp_path,
        artifact_source="hybrid",
        artifact_api_url="https://example.test/.netlify/functions/get-artifact",
        start_date="2026-05-30",
        end_date="2026-06-01",
    )

    assert result["manifest"]["row_count"] == 2
    assert result["manifest"]["source"]["artifact_source"] == "hybrid"
    assert result["manifest"]["source"]["production_fill_dates"] == ["2026-06-01"]
    assert calls[0]["artifact_api_url"] is None
    assert calls[1]["artifact_api_url"] == "https://example.test/.netlify/functions/get-artifact"
    assert calls[1]["start_date"] == "2026-06-01"
    assert calls[1]["end_date"] == "2026-06-01"
