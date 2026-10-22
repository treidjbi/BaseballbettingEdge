from analytics.diagnostics import profit_rescue_audit as audit


def _row(**overrides):
    row = {
        "slate_date": "2026-06-09",
        "is_tracked_pick": True,
        "result": "loss",
        "side": "over",
        "display_verdict": "FIRE 2u",
        "model_market_relationship": "model_agrees_with_favorite",
        "pick_history_pnl": -1.0,
    }
    row.update(overrides)
    return row


def test_proposed_policy_caps_fire_two_to_fire_one():
    decision = audit.proposed_rescue_decision(_row())

    assert decision["current_verdict"] == "FIRE 2u"
    assert decision["proposed_verdict"] == "FIRE 1u"
    assert decision["action"] == "downgrade_fire_two_to_fire_one"
    assert decision["reasons"] == ["cap_fire_two_to_fire_one"]


def test_proposed_policy_caps_fire_under_to_lean_after_fire_two_cap():
    decision = audit.proposed_rescue_decision(
        _row(side="under", model_market_relationship="model_agrees_with_favorite")
    )

    assert decision["proposed_verdict"] == "LEAN"
    assert decision["action"] == "downgrade_fire_to_lean"
    assert decision["reasons"] == ["cap_fire_two_to_fire_one", "cap_fire_under_to_lean"]


def test_proposed_policy_caps_market_fade_fire_to_lean():
    decision = audit.proposed_rescue_decision(
        _row(
            side="over",
            display_verdict="FIRE 1u",
            model_market_relationship="model_fades_favorite",
        )
    )

    assert decision["proposed_verdict"] == "LEAN"
    assert decision["action"] == "downgrade_fire_to_lean"
    assert decision["reasons"] == ["cap_market_fade_fire_to_lean"]


def test_build_summary_compares_current_and_proposed_fire_exposure():
    rows = [
        _row(slate_date="2026-06-01", result="win", pick_history_pnl=0.91),
        _row(slate_date="2026-06-08", result="loss", pick_history_pnl=-1.0),
        _row(
            slate_date="2026-06-09",
            side="under",
            display_verdict="FIRE 1u",
            result="loss",
            pick_history_pnl=-1.0,
        ),
        _row(
            slate_date="2026-06-09",
            display_verdict="LEAN",
            result="win",
            pick_history_pnl=0.91,
        ),
    ]

    summary = audit.build_summary(rows)

    assert summary["total_rows"] == 4
    assert summary["analysis_rows"] == 4
    assert summary["anchor_date"] == "2026-06-09"
    clean = summary["windows"]["clean_regime"]
    assert clean["current_fire"]["rows"] == 3
    assert clean["proposed_fire"]["rows"] == 2
    assert clean["downgraded_to_lean"]["rows"] == 1
    assert clean["current_fire"]["pnl"] == -1.09
    assert clean["proposed_fire"]["pnl"] == -0.09
    assert summary["by_action"]["downgrade_fire_to_lean"]["rows"] == 1
    assert summary["by_action"]["keep_non_fire"]["rows"] == 1


def test_render_report_states_canary_boundary():
    summary = audit.build_summary([_row()])

    rendered = audit.render_report(summary)

    assert "# Profit Rescue Audit" in rendered
    assert "downgrade-only" in rendered
    assert "PROFIT_RESCUE_REFEREE_MODE" in rendered
    assert "does not change lambda" in rendered
