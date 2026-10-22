from analytics.diagnostics import next_season_candidate_model_lab as lab


def test_walk_forward_split_respects_time_order():
    rows = [
        {"slate_date": "2026-04-01"},
        {"slate_date": "2026-05-01"},
        {"slate_date": "2026-06-01"},
        {"slate_date": "2026-07-01"},
    ]

    train, test = lab.walk_forward_split(rows, test_start="2026-06-01")

    assert [row["slate_date"] for row in train] == ["2026-04-01", "2026-05-01"]
    assert [row["slate_date"] for row in test] == ["2026-06-01", "2026-07-01"]


def test_score_candidate_rejects_hindsight_runtime_fields():
    rows = [
        {"runtime_features": {"edge": 0.05}, "hindsight_labels": {"result": "win", "pnl": 0.91}},
    ]

    candidate = lab.Candidate(
        name="bad_candidate",
        runtime_fields=("edge", "beat_close_price"),
        selector=lambda row: True,
    )

    result = lab.score_candidate(candidate, rows)

    assert result["status"] == "blocked_hindsight_runtime_field"
    assert result["rows"] == 0


def test_score_candidate_counts_wins_losses_and_pnl():
    rows = [
        {"runtime_features": {"edge": 0.05}, "hindsight_labels": {"result": "win", "pnl": 0.91}},
        {"runtime_features": {"edge": 0.06}, "hindsight_labels": {"result": "loss", "pnl": -1.0}},
    ]

    candidate = lab.Candidate(
        name="edge_positive",
        runtime_fields=("edge",),
        selector=lambda runtime_features: runtime_features.get("edge", 0) > 0,
    )

    result = lab.score_candidate(candidate, rows)

    assert result["status"] == "watch"
    assert result["rows"] == 2
    assert result["wins"] == 1
    assert result["losses"] == 1
    assert result["pnl"] == -0.09


def test_score_candidate_prefers_pick_history_pnl_then_theoretical_pnl():
    rows = [
        {
            "runtime_features": {"edge": 0.05},
            "hindsight_labels": {
                "result": "win",
                "pnl": 999.0,
                "theoretical_pnl": 0.62,
                "pick_history_pnl": 0.91,
            },
        },
        {
            "runtime_features": {"edge": 0.06},
            "hindsight_labels": {
                "result": "win",
                "theoretical_pnl": 1.24,
                "pick_history_pnl": None,
            },
        },
    ]

    candidate = lab.Candidate(
        name="edge_positive",
        runtime_fields=("edge",),
        selector=lambda runtime_features: runtime_features.get("edge", 0) > 0,
    )

    result = lab.score_candidate(candidate, rows)

    assert result["pnl"] == 2.15


def test_selector_receives_runtime_features_without_hindsight_labels():
    seen = {}
    rows = [
        {
            "runtime_features": {"edge": 0.05},
            "hindsight_labels": {"result": "win", "pick_history_pnl": 0.91},
        },
    ]

    def selector(runtime_features):
        seen["has_hindsight_labels"] = "hindsight_labels" in runtime_features
        return runtime_features.get("edge", 0) > 0

    candidate = lab.Candidate(
        name="runtime_only",
        runtime_fields=("edge",),
        selector=selector,
    )

    result = lab.score_candidate(candidate, rows)

    assert result["rows"] == 1
    assert seen["has_hindsight_labels"] is False


def test_score_candidate_returns_train_test_metrics():
    rows = [
        {
            "slate_date": "2026-05-01",
            "runtime_features": {"edge": 0.05},
            "hindsight_labels": {"result": "win", "theoretical_pnl": 0.91},
        },
        {
            "slate_date": "2026-06-01",
            "runtime_features": {"edge": 0.06},
            "hindsight_labels": {"result": "loss", "theoretical_pnl": -1.0},
        },
    ]

    candidate = lab.Candidate(
        name="edge_positive",
        runtime_fields=("edge",),
        selector=lambda runtime_features: runtime_features.get("edge", 0) > 0,
    )

    result = lab.score_candidate_walk_forward(candidate, rows, test_start="2026-06-01")

    assert result["rows"] == 2
    assert result["pnl"] == -0.09
    assert result["train_rows"] == 1
    assert result["train_pnl"] == 0.91
    assert result["test_rows"] == 1
    assert result["test_pnl"] == -1.0
