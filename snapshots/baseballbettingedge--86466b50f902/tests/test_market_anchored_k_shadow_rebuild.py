from analytics.diagnostics import market_anchored_k_shadow_rebuild as lab


def _row(**overrides):
    row = {
        "slate_date": "2026-06-01",
        "context_snapshot": "official_close",
        "normalized_pitcher": "test pitcher",
        "pitcher": "Test Pitcher",
        "side": "over",
        "k_line": 4.5,
        "projected_ks": 5.25,
        "no_vig_side_probability": 0.54,
        "model_no_vig_gap": 0.04,
        "model_market_relationship": "model_agrees_with_favorite",
        "market_favorite_side": "over",
        "quality_gate_level": "clean",
        "opportunity_bucket": "normal",
        "leash_risk_bucket": "normal",
        "line_bucket": "4.5",
        "price_sign": "minus",
        "bet_timing_window": "pre_30",
        "is_tracked_pick": True,
        "display_verdict": "FIRE 1u",
        "raw_verdict": "FIRE 1u",
        "result": "win",
        "actual_ks": 6,
        "pick_history_pnl": 0.91,
    }
    row.update(overrides)
    return row


def test_market_projection_inverts_no_vig_probability():
    projection = lab.market_implied_projection(k_line=4.5, over_probability=0.5)
    assert 4.0 < projection < 5.0

    favorite_over = lab.market_implied_projection(k_line=4.5, over_probability=0.62)
    assert favorite_over > projection


def test_build_markets_pairs_over_and_under_rows():
    rows = [
        _row(side="over", no_vig_side_probability=0.55),
        _row(side="under", no_vig_side_probability=0.45),
    ]

    markets = lab.build_markets(rows)

    assert len(markets) == 1
    assert markets[0]["over_row"]["side"] == "over"
    assert markets[0]["under_row"]["side"] == "under"
    assert markets[0]["over_probability"] == 0.55


def test_market_anchor_projection_shrinks_current_toward_market():
    row = _row(side="over", k_line=5.5, projected_ks=6.8, no_vig_side_probability=0.5)

    anchored = lab.market_anchor_projection(row)

    assert anchored < 6.8
    assert anchored > lab.market_implied_projection(5.5, 0.5)


def test_selector_requires_runtime_safe_market_anchor_support():
    row = _row(
        side="over",
        k_line=4.5,
        projected_ks=5.8,
        no_vig_side_probability=0.52,
        model_no_vig_gap=0.04,
        quality_gate_level="clean",
        model_market_relationship="model_agrees_with_favorite",
        market_favorite_side="over",
    )

    labels = lab.selector_labels(row)

    assert "market_anchor_side_agrees" in labels
    assert "market_anchor_core" in labels
    assert "market_anchor_strict" in labels

    fade = dict(row, model_market_relationship="model_fades_favorite")
    assert "market_anchor_strict" not in lab.selector_labels(fade)


def test_build_summary_scores_projection_and_selector_buckets():
    rows = [
        _row(result="win", actual_ks=6, pick_history_pnl=0.91),
        _row(
            normalized_pitcher="loss pitcher",
            pitcher="Loss Pitcher",
            result="loss",
            actual_ks=3,
            pick_history_pnl=-1.0,
            model_market_relationship="model_fades_favorite",
            market_favorite_side="under",
        ),
    ]

    summary = lab.build_summary(rows)

    assert summary["analysis_rows"] == 2
    assert summary["projection_scoreboard"]["market_anchor"]["rows"] == 2
    assert summary["tracked_selector_scoreboard"]["market_anchor_core"]["rows"] == 2
    assert summary["tracked_selector_scoreboard"]["market_anchor_strict"]["rows"] == 1


def test_render_report_keeps_shadow_boundary_and_read_rule():
    summary = lab.build_summary([_row()])

    rendered = lab.render_report(summary)

    assert "# Market Anchored K Shadow Rebuild" in rendered
    assert "Shadow-only" in rendered
    assert "does not change live" in rendered
    assert "Projection Scoreboard" in rendered
    assert "Tracked-Pick Selector Scoreboard" in rendered
    assert "Read Rule" in rendered
