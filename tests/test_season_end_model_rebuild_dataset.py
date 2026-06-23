from analytics.diagnostics import season_end_model_rebuild_dataset as rebuild


def test_build_row_marks_hindsight_fields_as_not_runtime_safe():
    source = {
        "slate_date": "2026-06-23",
        "pitcher": "Example Starter",
        "side": "over",
        "k_line": 5.5,
        "actual_ks": 7,
        "pnl": 0.91,
        "beat_close_price": True,
        "model_market_relationship": "model_agrees_with_favorite",
        "quality_gate_level": "clean",
    }

    row = rebuild.build_row(source)

    assert row["available_pre_lock"] is True
    assert row["hindsight_labels"]["actual_ks"] == 7
    assert row["hindsight_labels"]["beat_close_price"] is True
    assert "actual_ks" not in row["runtime_features"]
    assert "beat_close_price" not in row["runtime_features"]


def test_season_bucket_preserves_early_mid_late_context():
    assert rebuild.season_bucket("2026-03-28") == "early_season"
    assert rebuild.season_bucket("2026-05-15") == "spring_midseason"
    assert rebuild.season_bucket("2026-07-15") == "summer_midseason"
    assert rebuild.season_bucket("2026-09-10") == "late_season"


def test_summarize_reports_runtime_and_hindsight_coverage():
    rows = [
        {
            "available_pre_lock": True,
            "runtime_features": {"quality_gate_level": "clean"},
            "hindsight_labels": {"beat_close_price": True},
            "season_bucket": "early_season",
        }
    ]

    summary = rebuild.summarize(rows)

    assert summary["rows"] == 1
    assert summary["available_pre_lock_rows"] == 1
    assert summary["season_buckets"] == {"early_season": 1}
    assert summary["hindsight_label_counts"]["beat_close_price"] == 1
