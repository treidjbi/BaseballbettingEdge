from analytics.diagnostics.line_movement_shadow_audit import (
    movement_bucket,
    render_markdown,
    summarize_rows,
)


def test_movement_bucket_ignores_non_preview_openings():
    assert (
        movement_bucket({"opening_odds_source": "first_seen", "movement_conf": 0.2})
        == "not_preview"
    )
    assert movement_bucket({"opening_odds_source": None, "movement_conf": 1.0}) == "not_preview"


def test_movement_bucket_classifies_preview_fades():
    assert (
        movement_bucket({"opening_odds_source": "preview", "movement_conf": None})
        == "preview_unknown"
    )
    assert (
        movement_bucket({"opening_odds_source": "preview", "movement_conf": 0.49})
        == "preview_heavy_fade"
    )
    assert (
        movement_bucket({"opening_odds_source": "preview", "movement_conf": 0.5})
        == "preview_some_fade"
    )
    assert (
        movement_bucket({"opening_odds_source": "preview", "movement_conf": 0.75})
        == "preview_minor_fade"
    )
    assert (
        movement_bucket({"opening_odds_source": "preview", "movement_conf": 1.0})
        == "preview_no_fade"
    )


def test_summarize_rows_counts_only_graded_wins_and_losses_by_bucket():
    rows = [
        {
            "opening_odds_source": "preview",
            "movement_conf": 1.0,
            "result": "win",
            "pnl": 0.91,
        },
        {
            "opening_odds_source": "preview",
            "movement_conf": 0.6,
            "result": "loss",
            "pnl": -1.0,
        },
        {
            "opening_odds_source": "first_seen",
            "movement_conf": 1.0,
            "result": "loss",
            "pnl": -1.0,
        },
        {
            "opening_odds_source": "preview",
            "movement_conf": 1.0,
            "result": "void",
            "pnl": 0.0,
        },
        {
            "opening_odds_source": "preview",
            "movement_conf": 0.4,
            "result": "",
            "pnl": 0.0,
        },
    ]

    summary = summarize_rows(rows)

    assert summary["preview_no_fade"] == {
        "graded": 1,
        "wins": 1,
        "losses": 0,
        "pnl": 0.91,
    }
    assert summary["preview_some_fade"] == {
        "graded": 1,
        "wins": 0,
        "losses": 1,
        "pnl": -1.0,
    }
    assert summary["not_preview"] == {
        "graded": 1,
        "wins": 0,
        "losses": 1,
        "pnl": -1.0,
    }
    assert "preview_heavy_fade" not in summary


def test_render_markdown_includes_shadow_only_warning_and_webhook_rule():
    report = render_markdown(
        {
            "preview_no_fade": {
                "graded": 1,
                "wins": 1,
                "losses": 0,
                "pnl": 0.91,
            }
        }
    )

    assert "diagnostic only" in report
    assert "do not change verdicts, EV, calibration, or webhook adoption from this alone" in report
    assert "Do not build webhooks until movement audit shows" in report
