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
        selector=lambda row: row["runtime_features"].get("edge", 0) > 0,
    )

    result = lab.score_candidate(candidate, rows)

    assert result["status"] == "watch"
    assert result["rows"] == 2
    assert result["wins"] == 1
    assert result["losses"] == 1
    assert result["pnl"] == -0.09
