from analytics.diagnostics import shadow_signal_synthesis_lab as lab


def _row(**overrides):
    row = {
        "slate_date": "2026-07-08",
        "normalized_pitcher": "example starter",
        "pitcher": "Example Starter",
        "side": "over",
        "result": "win",
        "pick_history_pnl": 0.91,
        "is_tracked_pick": True,
        "display_verdict": "FIRE 1u",
        "line_bucket": "5.5",
        "price_bucket": "-130 to -149",
        "price_sign": "minus",
        "edge": 0.04,
        "adj_ev": 0.08,
        "locked_adj_ev": 0.08,
        "model_no_vig_gap": 0.03,
        "model_market_relationship": "model_agrees_with_favorite",
        "bet_timing_window": "pre_30",
        "leash_risk_bucket": "normal",
        "quality_gate_level": "clean",
        "batter_handedness_mode": "path_b",
        "lineup_split_source": "real_split_cache",
        "lineup_real_split_count": 9,
        "side_price_movement": "with_side",
        "book_count": 4,
        "broad_confirmation": True,
        "reversal_book_count": 0,
        "volatile_book_count": 0,
        "market_anchor_selector": {
            "mode": "shadow",
            "labels": ["market_anchor_core", "market_anchor_strict"],
            "would_verdict": "FIRE 1u",
        },
    }
    row.update(overrides)
    return row


def test_market_agreement_rows_are_collapsed_by_pick_key():
    rows = [_row(), _row(normalized_pitcher="second starter", side="under")]
    agreement_rows = [
        {
            "slate_date": "2026-07-08",
            "normalized_pitcher": "example starter",
            "side": "over",
            "movement_agreement_label": "market_with_model",
            "movement_strength_label": "broad_with_model",
            "movement_magnitude_bucket": "line_half_plus",
        },
        {
            "slate_date": "2026-07-08",
            "normalized_pitcher": "example starter",
            "side": "over",
            "movement_agreement_label": "market_no_signal",
            "movement_strength_label": "no_movement_signal",
            "movement_magnitude_bucket": "small_or_none",
        },
        {
            "slate_date": "2026-07-08",
            "normalized_pitcher": "second starter",
            "side": "under",
            "movement_agreement_label": "market_against_model",
            "movement_strength_label": "broad_against_model",
            "movement_magnitude_bucket": "odds_20c_plus",
        },
    ]

    enriched = lab.overlay_market_agreement(rows, agreement_rows)

    assert enriched[0]["market_agreement_signal"] == "market_with_model"
    assert enriched[0]["market_agreement_strength"] == "broad_with_model"
    assert enriched[0]["market_agreement_magnitude"] == "line_half_plus"
    assert enriched[1]["market_agreement_signal"] == "market_against_model"


def test_composite_summary_scores_stacked_runtime_policy():
    rows = [
        _row(pick_history_pnl=0.91),
        _row(normalized_pitcher="lean starter", display_verdict="LEAN", line_bucket="4.5", adj_ev=0.04, locked_adj_ev=0.04, pick_history_pnl=0.83),
        _row(normalized_pitcher="bad starter", result="loss", pick_history_pnl=-1.0, edge=0.09),
    ]
    agreement_rows = [
        {
            "slate_date": "2026-07-08",
            "normalized_pitcher": "example starter",
            "side": "over",
            "movement_agreement_label": "market_with_model",
            "movement_strength_label": "broad_with_model",
            "movement_magnitude_bucket": "line_half_plus",
        }
    ]

    summary = lab.build_summary(rows, market_agreement_rows=agreement_rows)

    policy = summary["composite_policies"]["combined_positive_runtime_watch"]
    assert policy["rows"] == 2
    assert policy["wins"] == 2
    assert policy["pnl"] == 1.74
    assert summary["market_agreement"]["rows"] == 1
    assert summary["market_agreement"]["graded_rows"] == 1


def test_render_report_states_shadow_boundary_and_market_agreement_coverage():
    summary = lab.build_summary([_row()], market_agreement_rows=[])

    report = lab.render_report(summary)

    assert "# Shadow Signal Synthesis Lab" in report
    assert "Shadow-only" in report
    assert "Market Agreement Input" in report
    assert "combined_positive_runtime_watch" in report
    assert "does not change live" in report


def test_render_report_prioritizes_strict_plus_selective_for_unit_accumulation():
    rows = [
        _row(pick_history_pnl=0.91),
        _row(
            normalized_pitcher="lean starter",
            display_verdict="LEAN",
            line_bucket="4.5",
            adj_ev=0.04,
            locked_adj_ev=0.04,
            pick_history_pnl=0.83,
        ),
    ]

    report = lab.render_report(lab.build_summary(rows))

    assert "Unit Accumulation Candidate" in report
    assert "`strict_runtime_core_plus_selective_lean`" in report
    assert "primary lens is total units and seasonal volume" in report
    assert "ROI is a guardrail" in report


def test_load_json_rows_accepts_market_agreement_jsonl(tmp_path):
    path = tmp_path / "market_agreement_tracker.jsonl"
    path.write_text(
        '{"slate_date":"2026-07-08","normalized_pitcher":"example starter","side":"over"}\n'
        '{"slate_date":"2026-07-08","normalized_pitcher":"second starter","side":"under"}\n',
        encoding="utf-8",
    )

    rows = lab.load_json_rows(path)

    assert [row["normalized_pitcher"] for row in rows] == ["example starter", "second starter"]
