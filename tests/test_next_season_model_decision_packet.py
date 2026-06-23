from analytics.diagnostics import next_season_model_decision_packet as packet


def test_decision_label_requires_sample_and_positive_pnl():
    assert packet.decision_label(rows=149, pnl=20.0, bad_slices=0) == "watch_more"
    assert packet.decision_label(rows=150, pnl=-1.0, bad_slices=0) == "blocked_negative_pnl"
    assert packet.decision_label(rows=150, pnl=10.0, bad_slices=1) == "blocked_bad_slice"
    assert packet.decision_label(rows=150, pnl=10.0, bad_slices=0) == "canary_plan_candidate"


def test_render_names_required_final_decisions():
    rendered = packet.render(
        [
            {
                "candidate": "market_supported_lean",
                "decision": "canary_plan_candidate",
                "rows": 160,
                "pnl": 8.5,
            }
        ]
    )

    assert "market_supported_lean" in rendered
    assert "Allowed offseason decisions" in rendered
    assert "draft_next_season_canary_plan" in rendered
