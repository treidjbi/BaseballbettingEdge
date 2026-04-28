from analytics.diagnostics.e3_projection_audit import (
    filter_rows,
    residual,
    summarize_residuals_by_lambda_bucket,
    summarize_residuals_by_side,
)


def test_residual_is_actual_minus_projection():
    row = {"actual_ks": 7, "lambda": 5.8}

    assert round(residual(row), 2) == 1.20


def test_residual_falls_back_to_applied_lambda():
    row = {"actual_ks": 4, "applied_lambda": 5.25}

    assert round(residual(row), 2) == -1.25


def test_residual_returns_none_when_actual_missing():
    row = {"actual_ks": None, "lambda": 5.8}

    assert residual(row) is None


def test_filter_rows_can_limit_to_clean_graded_window():
    rows = [
        {"date": "2026-04-27", "actual_ks": 7, "applied_lambda": 6.0, "side": "over"},
        {"date": "2026-04-28", "actual_ks": 5, "applied_lambda": 5.5, "side": "under"},
        {"date": "2026-04-29", "actual_ks": None, "applied_lambda": 4.5, "side": "under"},
    ]

    filtered = filter_rows(rows, clean_only=True, graded_only=True)

    assert filtered == [
        {"date": "2026-04-28", "actual_ks": 5, "applied_lambda": 5.5, "side": "under"}
    ]


def test_summarize_residuals_by_lambda_bucket_uses_clean_rows_only():
    rows = [
        {"date": "2026-04-27", "actual_ks": 10, "applied_lambda": 6.3, "side": "over"},
        {"date": "2026-04-28", "actual_ks": 7, "applied_lambda": 6.3, "side": "over"},
        {"date": "2026-04-29", "actual_ks": 5, "applied_lambda": 6.1, "side": "under"},
        {"date": "2026-04-30", "actual_ks": 4, "applied_lambda": 4.4, "side": "under"},
    ]

    summary = summarize_residuals_by_lambda_bucket(rows, clean_only=True)

    assert summary == [
        {
            "bucket": "4.0-4.9",
            "count": 1,
            "mean_residual": -0.4,
            "median_residual": -0.4,
        },
        {
            "bucket": "6.0-6.9",
            "count": 2,
            "mean_residual": -0.2,
            "median_residual": -0.2,
        },
    ]


def test_summarize_residuals_by_side_exposes_over_under_asymmetry():
    rows = [
        {"date": "2026-04-28", "actual_ks": 8, "applied_lambda": 6.0, "side": "over"},
        {"date": "2026-04-29", "actual_ks": 5, "applied_lambda": 6.0, "side": "over"},
        {"date": "2026-04-30", "actual_ks": 3, "applied_lambda": 4.0, "side": "under"},
        {"date": "2026-05-01", "actual_ks": 5, "applied_lambda": 4.0, "side": "under"},
    ]

    summary = summarize_residuals_by_side(rows, clean_only=True)

    assert summary == [
        {
            "side": "over",
            "count": 2,
            "mean_residual": 0.5,
            "median_residual": 0.5,
        },
        {
            "side": "under",
            "count": 2,
            "mean_residual": 0.0,
            "median_residual": 0.0,
        },
    ]
