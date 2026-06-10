import json

from analytics.diagnostics import workload_no_vig_ev_audit
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
        "market_agreement_tracker_path": "analytics/output/market_agreement_tracker.jsonl",
        "live_market_display_path": "analytics/output/market_agreement_inputs/live_market_display_state.json",
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


def test_main_can_run_workload_no_vig_audit_after_fresh_dataset(tmp_path, monkeypatch):
    calls = []
    monkeypatch.delenv("BBE_ARTIFACT_API_URL", raising=False)

    def fake_build_research_artifact(**kwargs):
        calls.append(("build", kwargs))
        return {
            "manifest": {
                "row_count": 2,
                "tracked_pick_rows": 1,
                "duplicate_dataset_keys": 0,
                "reconciliation": {
                    "graded_pick_rows": 1,
                    "matched_pick_rows": 1,
                },
            },
            "manifest_path": tmp_path / "pitcher_k_outcome_dataset_manifest.json",
        }

    def fake_audit_main(argv):
        calls.append(("audit", argv))
        return 0

    monkeypatch.setattr(builder, "build_research_artifact", fake_build_research_artifact)
    monkeypatch.setattr(workload_no_vig_ev_audit, "main", fake_audit_main)

    builder.main([
        "--artifact-source",
        "hybrid",
        "--output-dir",
        str(tmp_path),
        "--run-workload-no-vig-audit",
    ])

    assert calls == [
        (
            "build",
            {
                "output_dir": tmp_path,
                "artifact_source": "hybrid",
                "artifact_api_url": builder.DEFAULT_ARTIFACT_API_URL,
                "start_date": builder.dataset.CLEAN_WINDOW_START,
                "end_date": None,
                "lineup_handedness_backfill_path": builder.dataset.LINEUP_HANDEDNESS_BACKFILL,
                "actual_opportunity_backfill_path": builder.dataset.ACTUAL_OPPORTUNITY_BACKFILL,
                "market_agreement_tracker_path": builder.dataset.MARKET_AGREEMENT_TRACKER,
                "live_market_display_path": builder.dataset.LIVE_MARKET_DISPLAY,
            },
        ),
        (
            "audit",
            [
                "--input",
                str(tmp_path / "pitcher_k_outcome_dataset.jsonl"),
                "--output",
                str(builder.DEFAULT_WORKLOAD_NO_VIG_AUDIT_OUTPUT),
            ],
        ),
    ]
