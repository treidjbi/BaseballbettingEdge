from analytics.diagnostics import market_favorite_confidence_referee_shadow_lab as lab


def _row(**overrides):
    row = {
        "dataset_key": "2026-06-01:jane-doe:over:5.5",
        "slate_date": "2026-06-01",
        "context_snapshot": "official_close",
        "is_tracked_pick": True,
        "side": "over",
        "k_line": 5.5,
        "line_bucket": "5.5",
        "price_sign": "minus",
        "market_favorite_side": "over",
        "favorite_gap_no_vig": 0.04,
        "model_side": "over",
        "model_market_relationship": "model_agrees_with_favorite",
        "verdict": "FIRE 1u",
        "quality_gate_level": "clean",
        "bet_timing_window": "pre_30",
        "opportunity_bucket": "normal",
        "leash_risk_bucket": "normal",
        "pitcher_archetype_bucket": "standard_starter",
        "result": "win",
        "actual_ks": 7,
        "pick_history_pnl": 0.91,
        "beat_close_price": True,
    }
    row.update(overrides)
    return row


def test_label_inputs_are_runtime_safe():
    assert "result" not in lab.RUNTIME_SAFE_FIELDS
    assert "actual_ks" not in lab.RUNTIME_SAFE_FIELDS
    assert "pick_history_pnl" not in lab.RUNTIME_SAFE_FIELDS
    assert "beat_close_price" not in lab.RUNTIME_SAFE_FIELDS
    assert "market_favorite_side" in lab.RUNTIME_SAFE_FIELDS
    assert "model_market_relationship" in lab.RUNTIME_SAFE_FIELDS


def test_candidate_flags_identify_market_favorite_agreement():
    flags = lab.candidate_flags(_row())

    assert flags["current_model_tracked"] is True
    assert flags["model_agrees_market_favorite"] is True
    assert flags["model_fades_market_favorite"] is False
    assert flags["over_agrees_market_favorite"] is True
    assert flags["under_agrees_market_favorite"] is False
    assert flags["market_favorite_referee_candidate"] is True


def test_candidate_flags_identify_fade_warning():
    flags = lab.candidate_flags(
        _row(
            side="under",
            model_side="under",
            market_favorite_side="over",
            model_market_relationship="model_fades_favorite",
            quality_gate_level="capped",
            bet_timing_window="pre_15",
        )
    )

    assert flags["model_fades_market_favorite"] is True
    assert flags["market_fade_warning_candidate"] is True


def test_summarize_candidate_counts_wins_pnl_and_roi():
    rows = [
        _row(dataset_key="a", result="win", pick_history_pnl=0.91),
        _row(
            dataset_key="b",
            result="loss",
            pick_history_pnl=-1.0,
            model_side="under",
            market_favorite_side="over",
        ),
    ]

    summary = lab.summarize_candidate("model_agrees_market_favorite", rows)

    assert summary["rows"] == 1
    assert summary["wins"] == 1
    assert summary["losses"] == 0
    assert summary["flat_pnl"] == 0.91
    assert summary["flat_roi"] == 0.91


def test_split_holdout_keeps_late_dates_for_validation():
    rows = [_row(dataset_key=str(day), slate_date=f"2026-05-{day:02d}") for day in range(1, 11)]

    split = lab.split_holdout_rows(rows, train_fraction=0.7, min_validate_dates=3)

    assert split["train_dates"][-1] == "2026-05-07"
    assert split["validate_dates"] == ["2026-05-08", "2026-05-09", "2026-05-10"]
