from analytics.diagnostics.market_evidence_shadow_audit import (
    build_report,
    join_evidence_to_results,
    summarize_evidence,
)


def test_join_evidence_to_results_matches_slate_pitcher_side():
    evidence_rows = [{
        "slate_date": "2026-05-08",
        "normalized_pitcher": "kyle bradish",
        "side": "under",
        "provider": "propline",
        "market_consensus": "toward_pick",
        "bet_value_consensus": "worse_now",
    }]
    history_rows = [{
        "date": "2026-05-08",
        "normalized_pitcher": "kyle bradish",
        "side": "under",
        "result": "win",
        "pnl": 0.91,
    }]

    joined = join_evidence_to_results(evidence_rows, history_rows)

    assert joined[0]["result"] == "win"
    assert joined[0]["pnl"] == 0.91


def test_summarize_evidence_buckets_by_provider_market_and_value():
    rows = [
        {
            "provider": "propline",
            "market_consensus": "toward_pick",
            "bet_value_consensus": "worse_now",
            "current_verdict": "FIRE 1u",
            "result": "win",
            "pnl": 0.91,
        },
        {
            "provider": "propline",
            "market_consensus": "toward_pick",
            "bet_value_consensus": "worse_now",
            "current_verdict": "FIRE 1u",
            "result": "loss",
            "pnl": -1.0,
        },
        {
            "provider": "boltodds",
            "market_consensus": "mixed",
            "bet_value_consensus": "mixed",
            "current_verdict": "LEAN",
            "result": None,
            "pnl": None,
        },
    ]

    summary = summarize_evidence(rows)

    assert summary[("propline", "toward_pick", "worse_now")] == {
        "rows": 2,
        "fire_rows": 2,
        "graded": 2,
        "wins": 1,
        "losses": 1,
        "pnl": -0.09,
        "roi": -0.045,
    }
    assert summary[("boltodds", "mixed", "mixed")]["graded"] == 0


def test_build_report_keeps_market_evidence_shadow_only():
    report = build_report([{
        "provider": "propline",
        "market_consensus": "toward_pick",
        "bet_value_consensus": "worse_now",
        "current_verdict": "FIRE 1u",
        "result": "win",
        "pnl": 0.91,
    }])

    assert "# Market Evidence Shadow Audit" in report
    assert "shadow-only" in report
    assert "does not change picks, locks, thresholds, staking, provider order, or notifications" in report
    assert "| `propline` | `toward_pick` | `worse_now` |" in report
