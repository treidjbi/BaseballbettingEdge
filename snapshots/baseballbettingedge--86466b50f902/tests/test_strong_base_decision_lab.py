from analytics.diagnostics import strong_base_decision_lab as lab


def _row(**overrides):
    row = {
        "slate_date": "2026-06-25",
        "is_tracked_pick": True,
        "result": "win",
        "side": "over",
        "display_verdict": "FIRE 1u",
        "edge": 0.045,
        "adj_ev": 0.11,
        "model_no_vig_gap": 0.05,
        "model_market_relationship": "model_agrees_with_favorite",
        "quality_gate_level": "clean",
        "line_bucket": "4.5",
        "price_sign": "minus",
        "bet_timing_window": "pre_30",
        "leash_risk_bucket": "normal",
        "pitcher_archetype_bucket": "standard_starter",
        "batter_handedness_mode": "path_b",
        "lineup_real_split_count": 3,
        "market_agreement_label": "market_with_model",
        "pick_history_pnl": 0.91,
        "beat_close_price": True,
        "beat_close_line": False,
    }
    row.update(overrides)
    return row


def test_candidate_rules_cover_keep_expand_cap_and_process_anchor_lanes():
    keep_fire = _row()
    assert "keep_fire_market_agreed_moderate_ev" in lab.candidate_labels(keep_fire)
    assert "keep_fire_over_moderate_ev_normal_leash" in lab.candidate_labels(keep_fire)

    lean_expand = _row(display_verdict="LEAN", adj_ev=0.04, beat_close_price=False)
    assert "expand_lean_45_low_ev_normal_leash" in lab.candidate_labels(lean_expand)

    high_edge = _row(edge=0.08, model_market_relationship="model_fades_favorite")
    assert "cap_high_raw_edge" in lab.candidate_labels(high_edge)
    assert "cap_market_fade" in lab.candidate_labels(high_edge)

    clv_anchor = _row(beat_close_price=True)
    assert "evidence_clv_supported" in lab.candidate_labels(clv_anchor)


def test_provider_era_and_path_b_buckets_are_runtime_slice_inputs():
    assert lab.provider_era(_row(slate_date="2026-06-10")) == "pre_current_provider"
    assert lab.provider_era(_row(slate_date="2026-06-20")) == "post_boltodds_retirement"
    assert lab.provider_era(_row(slate_date="2026-06-25")) == "official_therundown_propline"

    assert lab.path_b_coverage_bucket(_row(lineup_real_split_count=2)) == "path_b_real_or_mixed"
    assert lab.path_b_coverage_bucket(_row(lineup_real_split_count=0)) == "path_b_no_real_splits"
    assert lab.path_b_coverage_bucket(
        _row(batter_handedness_mode="path_a", lineup_real_split_count=0)
    ) == "path_a_or_unknown"


def test_build_summary_keeps_positive_clv_separate_from_mass_losses():
    rows = [
        _row(result="win", pick_history_pnl=0.91, beat_close_price=True),
        _row(
            result="loss",
            pick_history_pnl=-1.0,
            beat_close_price=False,
            price_clv_cents=-12,
            model_market_relationship="model_fades_favorite",
            edge=0.08,
        ),
        _row(
            display_verdict="LEAN",
            result="loss",
            pick_history_pnl=-1.0,
            beat_close_price=False,
            price_clv_cents=0,
        ),
    ]

    summary = lab.build_summary(rows)

    assert summary["tracked"]["rows"] == 3
    assert summary["clv"]["beat_close_price"]["rows"] == 1
    assert summary["clv"]["no_or_worse_price_clv"]["rows"] == 2
    assert summary["candidates"]["cap_high_raw_edge"]["rows"] == 1
    assert summary["candidates"]["evidence_clv_supported"]["kind"] == "process_anchor"


def test_candidate_readiness_requires_current_provider_and_recent_support():
    rows = []
    for idx in range(80):
        rows.append(
            _row(
                slate_date="2026-06-25" if idx >= 55 else "2026-06-01",
                result="win" if idx % 3 != 0 else "loss",
                pick_history_pnl=0.91 if idx % 3 != 0 else -1.0,
                beat_close_price=idx % 2 == 0,
            )
        )

    summary = lab.build_summary(rows)
    candidate = summary["candidates"]["keep_fire_market_agreed_moderate_ev"]

    assert candidate["rows"] == 80
    assert candidate["current_provider"]["rows"] == 25
    assert candidate["readiness"] == "ready_for_plan"
    assert candidate["recent"]["pnl"] > 0


def test_negative_mandatory_slice_keeps_candidate_on_watch():
    rows = []
    for idx in range(80):
        rows.append(
            _row(
                result="win" if idx < 52 else "loss",
                side="over" if idx < 60 else "under",
                pick_history_pnl=0.91 if idx < 52 else -1.0,
                beat_close_price=True,
            )
        )

    summary = lab.build_summary(rows)
    candidate = summary["candidates"]["keep_fire_market_agreed_moderate_ev"]

    assert candidate["readiness"] == "watch_more"
    assert any(risk["field"] == "side" and risk["bucket"] == "under" for risk in candidate["negative_slices"])


def test_nontracked_pass_expansion_requires_positive_edge_and_ev():
    pass_win = _row(
        is_tracked_pick=False,
        display_verdict="PASS",
        result="win",
        edge=0.02,
        adj_ev=0.07,
        theoretical_pnl=0.91,
        pick_history_pnl=None,
    )
    pass_loss = _row(
        is_tracked_pick=False,
        display_verdict="PASS",
        result="loss",
        edge=-0.01,
        adj_ev=0.07,
        theoretical_pnl=-1.0,
        pick_history_pnl=None,
    )

    summary = lab.build_summary([pass_win, pass_loss])

    assert summary["pass_expansion"]["positive_edge_ev"]["rows"] == 1
    assert summary["pass_expansion"]["all_nontracked_pass"]["rows"] == 2


def test_render_report_states_policy_is_not_live_behavior():
    summary = lab.build_summary([_row()])

    rendered = lab.render_report(summary)

    assert "# Strong Base Decision Lab" in rendered
    assert "Shadow-only" in rendered
    assert "does not change live" in rendered
    assert "Candidate Policy Draft" in rendered
    assert "Positive CLV vs Mass Losses" in rendered
