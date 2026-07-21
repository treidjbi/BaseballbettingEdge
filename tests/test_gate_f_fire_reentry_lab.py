from analytics.diagnostics import gate_f_fire_reentry_lab as lab


def _row(**overrides):
    row = {
        "slate_date": "2026-05-20",
        "is_tracked_pick": True,
        "result": "win",
        "side": "over",
        "display_verdict": "FIRE 1u",
        "raw_verdict": "FIRE 1u",
        "edge": 0.045,
        "adj_ev": 0.11,
        "model_no_vig_gap": 0.05,
        "model_market_relationship": "model_agrees_with_favorite",
        "quality_gate_level": "clean",
        "line_bucket": "5.5",
        "price_sign": "minus",
        "bet_timing_window": "pre_30",
        "opportunity_bucket": "normal",
        "leash_risk_bucket": "normal",
        "path_b_coverage_bucket": "path_a_or_unknown",
        "provider": "boltodds",
        "market_agreement_label": "market_agrees_with_model",
        "beat_close_price": True,
        "beat_close_line": False,
        "pick_history_pnl": 0.91,
    }
    row.update(overrides)
    return row


def test_profit_rescue_shadow_decision_matches_live_downgrade_policy():
    fire_two = lab.profit_rescue_shadow_decision(_row(display_verdict="FIRE 2u", raw_verdict="FIRE 2u"))
    assert fire_two["proposed_verdict"] == "FIRE 1u"
    assert fire_two["action"] == "downgrade_fire_two_to_fire_one"

    fire_under = lab.profit_rescue_shadow_decision(_row(side="under", display_verdict="FIRE 1u"))
    assert fire_under["proposed_verdict"] == "LEAN"
    assert fire_under["action"] == "downgrade_fire_to_lean"
    assert "cap_fire_under_to_lean" in fire_under["reasons"]

    market_fade = lab.profit_rescue_shadow_decision(
        _row(display_verdict="FIRE 1u", model_market_relationship="model_fades_favorite")
    )
    assert market_fade["proposed_verdict"] == "LEAN"
    assert market_fade["action"] == "downgrade_fire_to_lean"
    assert "cap_market_fade_fire_to_lean" in market_fade["reasons"]


def test_candidate_labels_identify_reentry_and_avoidance_contexts():
    clv_row = _row(beat_close_price=True, beat_close_line=False)
    assert "clv_supported_reentry" in lab.candidate_labels(clv_row)

    market_row = _row(
        beat_close_price=False,
        model_market_relationship="model_agrees_with_favorite",
        model_no_vig_gap=0.07,
    )
    assert "market_aligned_reentry" in lab.candidate_labels(market_row)

    moderate_row = _row(edge=0.035, adj_ev=0.09, quality_gate_level="clean", model_no_vig_gap=0.055)
    assert "moderate_edge_quality_reentry" in lab.candidate_labels(moderate_row)

    avoid_under = _row(
        side="under",
        display_verdict="FIRE 1u",
        beat_close_price=False,
        beat_close_line=False,
        model_no_vig_gap=0.01,
        model_market_relationship="model_fades_favorite",
    )
    assert "avoid_fire_under_reentry" in lab.candidate_labels(avoid_under)


def test_build_summary_marks_runtime_candidate_ready_when_volume_clv_and_recent_hold():
    rows = []
    for idx in range(120):
        rows.append(
            _row(
                slate_date="2026-06-01" if idx < 60 else "2026-06-08",
                result="win" if idx % 3 != 0 else "loss",
                pick_history_pnl=0.91 if idx % 3 != 0 else -1.0,
                beat_close_price=True,
                beat_close_line=idx % 5 == 0,
            )
        )

    summary = lab.build_summary(rows)
    candidate = summary["candidates"]["moderate_edge_quality_reentry"]

    assert candidate["rows"] == 120
    assert candidate["readiness"] == "ready_for_plan"
    assert candidate["retained_fire_rows"] == 120
    assert candidate["capped_to_lean_rows"] == 0
    assert candidate["clv_support_rate"] >= 0.4
    assert candidate["recent"]["pnl"] > 0


def test_clv_supported_reentry_is_process_anchor_not_runtime_selector():
    summary = lab.build_summary([_row(beat_close_price=True) for _idx in range(120)])
    candidate = summary["candidates"]["clv_supported_reentry"]

    assert candidate["kind"] == "process_anchor"
    assert candidate["readiness"] == "process_anchor"


def test_build_summary_flags_negative_slice_as_watch_more():
    rows = []
    for idx in range(90):
        rows.append(
            _row(
                result="win" if idx < 65 else "loss",
                side="over" if idx < 70 else "under",
                pick_history_pnl=0.91 if idx < 65 else -1.0,
                beat_close_price=True,
            )
        )

    summary = lab.build_summary(rows)
    candidate = summary["candidates"]["moderate_edge_quality_reentry"]

    assert candidate["readiness"] == "watch_more"
    assert any(risk["field"] == "side" and risk["bucket"] == "under" for risk in candidate["negative_slices"])


def test_render_report_keeps_shadow_boundary_and_fire_volume_language():
    summary = lab.build_summary([_row()])

    rendered = lab.render_report(summary)

    assert "# Gate F FIRE Re-Entry Selection Lab" in rendered
    assert "Shadow-only" in rendered
    assert "does not change live" in rendered
    assert "zero-FIRE" in rendered
    assert "Candidate Scoreboard" in rendered


def test_source_fire_wrapper_keeps_raw_fire_before_displayed_lean():
    assert lab.source_fire_verdict(_row(display_verdict="LEAN", raw_verdict="FIRE 1u")) == "FIRE 1u"
