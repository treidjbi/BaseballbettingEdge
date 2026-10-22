from analytics.diagnostics import bet_selection_edge_synthesis as report


def _row(**overrides):
    row = {
        "slate_date": "2026-05-12",
        "is_tracked_pick": True,
        "result": "win",
        "side": "over",
        "display_verdict": "FIRE 1u",
        "edge": 0.05,
        "adj_ev": 0.08,
        "model_no_vig_gap": 0.05,
        "model_market_relationship": "model_agrees_with_favorite",
        "quality_gate_level": "clean",
        "leash_risk_bucket": "normal",
        "opportunity_bucket": "normal",
        "k_margin_to_line": 0.75,
        "pick_history_pnl": 0.91,
        "beat_close_price": True,
        "beat_close_line": False,
    }
    row.update(overrides)
    return row


def test_edge_and_ev_buckets_match_current_bet_selection_cuts():
    assert report.edge_bucket(_row(edge=0.015)) == "edge_lt_2"
    assert report.edge_bucket(_row(edge=0.035)) == "edge_2_to_4"
    assert report.edge_bucket(_row(edge=0.055)) == "edge_4_to_6"
    assert report.edge_bucket(_row(edge=0.08)) == "edge_6_plus"

    assert report.ev_bucket(_row(adj_ev=0.04)) == "adj_ev_lt_6"
    assert report.ev_bucket(_row(adj_ev=0.12)) == "adj_ev_6_to_17"
    assert report.ev_bucket(_row(adj_ev=0.22)) == "adj_ev_17_plus"


def test_candidate_label_flags_clean_moderate_edge_context():
    row = _row(
        edge=0.05,
        model_no_vig_gap=0.055,
        model_market_relationship="model_agrees_with_favorite",
        quality_gate_level="clean",
        large_edge_skepticism_flag=False,
    )

    assert report.candidate_label(row) == "moderate_edge_clean_context"


def test_candidate_label_flags_high_edge_skepticism_before_clv_support():
    row = _row(
        side="under",
        display_verdict="FIRE 2u",
        edge=0.09,
        model_no_vig_gap=0.01,
        model_market_relationship="model_fades_favorite",
        large_edge_skepticism_flag=True,
        beat_close_price=True,
        price_clv_cents=18,
    )

    assert report.candidate_label(row) == "high_edge_skeptic"


def test_candidate_label_tracks_fire_under_watch():
    row = _row(
        side="under",
        display_verdict="FIRE 1u",
        edge=0.055,
        model_no_vig_gap=0.025,
        model_market_relationship="model_fades_favorite",
        large_edge_skepticism_flag=False,
        beat_close_price=False,
        leash_risk_bucket="high",
    )

    assert report.candidate_label(row) == "fire_under_watch"


def test_build_summary_counts_cross_slices_and_outing_context():
    rows = [
        _row(result="win", pick_history_pnl=0.91, actual_ip=6.0, avg_ip=5.8),
        _row(
            result="loss",
            side="under",
            display_verdict="FIRE 1u",
            edge=0.08,
            model_no_vig_gap=0.01,
            model_market_relationship="model_fades_favorite",
            large_edge_skepticism_flag=True,
            pick_history_pnl=-1.0,
            actual_ip=3.0,
            avg_ip=5.6,
        ),
    ]

    summary = report.build_summary(rows)

    assert summary["total_rows"] == 2
    assert summary["analysis_rows"] == 2
    assert summary["by_candidate_label"]["moderate_edge_clean_context"]["rows"] == 1
    assert summary["by_candidate_label"]["high_edge_skeptic"]["rows"] == 1
    assert summary["by_opportunity_actual"]["normal | normal_outing"]["rows"] == 1
    assert summary["by_opportunity_actual"]["normal | short_outing"]["rows"] == 1


def test_render_report_keeps_research_boundary_and_gate_language():
    summary = report.build_summary([_row()])

    rendered = report.render_report(summary)

    assert "# Bet Selection And Edge Synthesis" in rendered
    assert "Shadow-only" in rendered
    assert "Gate E" in rendered
    assert "Gate F" in rendered
    assert "Candidate Labels" in rendered
