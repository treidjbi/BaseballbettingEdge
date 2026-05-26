from analytics.diagnostics.pre_post_428_model_review import (
    build_report,
    summarize_market_projection_window,
    summarize_tracked_window,
)


def _pick(**overrides):
    row = {
        "date": "2026-04-27",
        "pitcher": "Test Pitcher",
        "side": "over",
        "result": "win",
        "pnl": 0.91,
        "actual_ks": 6,
        "k_line": 4.5,
        "applied_lambda": 5.2,
        "verdict": "FIRE 1u",
        "odds": -110,
        "edge": 0.05,
        "adj_ev": 0.08,
    }
    row.update(overrides)
    return row


def _market(**overrides):
    row = {
        "date": "2026-04-27",
        "pitcher": "Market Pitcher",
        "actual_ks": 6,
        "k_line": 4.5,
        "lambda": 5.2,
        "ev_over": {"verdict": "FIRE 1u"},
        "ev_under": {"verdict": "PASS"},
    }
    row.update(overrides)
    return row


def test_summarize_tracked_window_scores_picks_projection_and_side_splits():
    rows = [
        _pick(side="over", result="win", pnl=0.91, actual_ks=6, applied_lambda=5.2),
        _pick(side="under", result="loss", pnl=-1.0, actual_ks=6, applied_lambda=3.8),
    ]

    summary = summarize_tracked_window(rows, "2026-04-08", "2026-04-27")

    assert summary["rows"] == 2
    assert summary["wins"] == 1
    assert summary["losses"] == 1
    assert summary["flat_pnl"] == -0.09
    assert summary["flat_roi"] == -0.045
    assert summary["stake_units"] == 2.0
    assert summary["staked_pnl"] == -0.09
    assert summary["staked_roi"] == -0.045
    assert summary["projection_rows"] == 2
    assert summary["side_accuracy"] == 0.5
    assert summary["by_side"]["over"]["flat_pnl"] == 0.91
    assert summary["by_side"]["under"]["flat_pnl"] == -1.0


def test_summarize_market_projection_window_dedupes_pitcher_line_markets():
    markets = [
        _market(pitcher="A", actual_ks=6, **{"lambda": 5.2}),
        _market(pitcher="A", actual_ks=6, **{"lambda": 5.2}),
        _market(pitcher="B", actual_ks=2, k_line=4.5, **{"lambda": 3.9}),
    ]

    summary = summarize_market_projection_window(markets, "2026-04-08", "2026-04-27")

    assert summary["rows"] == 2
    assert summary["side_wins"] == 2
    assert summary["side_accuracy"] == 1.0
    assert summary["mae"] == 1.35


def test_build_report_compares_pre_and_post_without_claiming_live_change():
    pre_pick = _pick(date="2026-04-27", side="over", result="win", pnl=0.91)
    post_pick = _pick(date="2026-04-28", side="under", result="loss", pnl=-1.0)
    pre_market = _market(date="2026-04-27", pitcher="A")
    post_market = _market(date="2026-04-28", pitcher="B", actual_ks=2, **{"lambda": 3.9})

    report = build_report([pre_pick, post_pick], [pre_market, post_market])

    assert "# Pre/Post 2026-04-28 Model Review" in report
    assert "Immediate pre-bump window" in report
    assert "Post-bump clean window" in report
    assert "Flat PnL" in report
    assert "Staked ROI" in report
    assert "Projection Quality" in report
    assert "Bet Selection" in report
    assert "No live threshold, staking, calibration, provider, or dashboard behavior changes" in report
