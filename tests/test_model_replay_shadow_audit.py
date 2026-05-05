from analytics.diagnostics.model_replay_shadow_audit import (
    build_model_replay_report,
    current_projection,
    projection_residual,
    simple_projection,
    summarize,
)


def test_simple_projection_uses_season_career_and_ip():
    row = {"season_k9": 9.0, "career_k9": 8.0, "avg_ip": 6.0}

    assert simple_projection(row) == 5.733


def test_simple_projection_returns_none_when_inputs_are_missing():
    assert simple_projection({"season_k9": 9.0, "avg_ip": 6.0}) is None


def test_current_projection_prefers_live_lambda_then_schema_fallbacks():
    assert current_projection({"lambda": 5.1, "raw_lambda": 9.9}) == 5.1
    assert current_projection({"raw_lambda": 5.2}) == 5.2
    assert current_projection({"applied_lambda": 5.3}) == 5.3
    assert current_projection({"model_lambda": 5.4}) == 5.4


def test_projection_residual_returns_actual_minus_projection():
    assert projection_residual({"actual_ks": 7}, 5.733) == 1.267


def test_summarize_compares_current_and_simple_clean_graded_rows():
    rows = [
        {
            "date": "2026-04-27",
            "result": "win",
            "actual_ks": 10,
            "lambda": 1.0,
            "season_k9": 12.0,
            "career_k9": 12.0,
            "avg_ip": 6.0,
            "side": "over",
        },
        {
            "date": "2026-04-28",
            "result": "win",
            "actual_ks": 6,
            "raw_lambda": 5.0,
            "season_k9": 9.0,
            "career_k9": 8.0,
            "avg_ip": 6.0,
            "side": "over",
        },
        {
            "date": "2026-04-29",
            "result": "loss",
            "actual_ks": 4,
            "applied_lambda": 5.0,
            "season_k9": 5.0,
            "career_k9": 6.75,
            "avg_ip": 5.0,
            "side": "under",
        },
        {
            "date": "2026-04-30",
            "result": "void",
            "actual_ks": 4,
            "lambda": 10.0,
            "season_k9": 7.0,
            "career_k9": 8.0,
            "avg_ip": 5.0,
            "side": "under",
        },
    ]

    result = summarize(rows)

    assert result["eligible_rows"] == 2
    assert result["current_n"] == 2
    assert result["current_mean_abs_residual"] == 1.0
    assert result["simple_n"] == 2
    assert result["simple_mean_abs_residual"] == 0.55
    assert result["by_side"]["over"]["current_mean_abs_residual"] == 1.0
    assert result["by_side"]["under"]["simple_mean_abs_residual"] == 0.833


def test_report_marks_diagnostic_only_and_decision_rule():
    report = build_model_replay_report(
        {
            "eligible_rows": 1,
            "current_n": 1,
            "current_mean_abs_residual": 1.0,
            "simple_n": 1,
            "simple_mean_abs_residual": 0.5,
            "by_side": {},
        }
    )

    assert "diagnostic only" in report
    assert "does not change live lambda" in report
    assert "only consider simplification if same-window replay beats current residuals" in report
    assert "not if all-history ROI merely looks better" in report
