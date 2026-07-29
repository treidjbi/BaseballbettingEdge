import importlib

import pytest


def _audit_module():
    try:
        return importlib.import_module(
            "analytics.diagnostics.strict_runtime_core_canary_audit"
        )
    except ModuleNotFoundError:
        pytest.fail("strict runtime core audit module is not implemented")


def candidate_row(**overrides):
    row = {
        "is_tracked_pick": True,
        "slate_date": "2026-07-30",
        "normalized_pitcher": "test pitcher",
        "side": "over",
        "result": "win",
        "pick_history_pnl": 0.90,
        "display_verdict": "FIRE 1u",
        "edge": 0.05,
        "locked_adj_ev": 0.10,
        "model_market_relationship": "model_agrees_with_favorite",
        "line_bucket": "5.5",
        "price_sign": "minus",
        "price_bucket": "-100 to -129",
        "quality_gate_level": "clean",
        "bet_timing_window": "pre_30",
        "leash_risk_bucket": "normal",
        "batter_handedness_mode": "path_b",
        "provider_era": "therundown_propline",
        "provider": "therundown+propline",
        "market_agreement_label": "agree",
        "preclose_clv_proxy_label": "strong",
        "final_clv_bucket": "beat_close_price",
    }
    row.update(overrides)
    return row


def test_rule_spec_and_fingerprint_are_frozen_literals():
    audit = _audit_module()

    assert audit.RULE_SPEC == {
        "selector_id": "strict_runtime_core_flat",
        "version": 1,
        "prospective_start": "2026-07-30",
        "verdict": "FIRE*",
        "keep_labels": [
            "keep_fire_market_agreed_moderate_ev",
            "keep_fire_over_moderate_ev_normal_leash",
        ],
        "drag_labels": [
            "cap_fire_under_market_fade",
            "cap_high_raw_edge",
            "cap_market_fade",
        ],
        "post_start_policy": "exclude",
        "outcome_fields_used": [],
        "formula": (
            "FIRE AND (keep_fire_market_agreed_moderate_ev OR "
            "keep_fire_over_moderate_ev_normal_leash) AND NOT "
            "(cap_high_raw_edge OR cap_market_fade OR "
            "cap_fire_under_market_fade)"
        ),
    }
    assert audit.RULE_FINGERPRINT == (
        "6d07a98031a8b26915ad34fc031def76d26519850dc476db723d37f25a8d9905"
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {
            "side": "under",
            "leash_risk_bucket": "short",
            "model_market_relationship": "model_agrees_with_favorite",
        },
    ],
)
def test_eligible_fire_rows_use_one_of_the_two_runtime_safe_keep_labels(overrides):
    audit = _audit_module()

    evaluation = audit.evaluate_row(candidate_row(**overrides))

    assert evaluation.qualifies is True
    assert set(evaluation.keep_labels) & {
        "keep_fire_market_agreed_moderate_ev",
        "keep_fire_over_moderate_ev_normal_leash",
    }
    assert evaluation.drag_labels == ()
    assert evaluation.missing_inputs == ()
    assert evaluation.post_start_leakage is False


@pytest.mark.parametrize(
    ("overrides", "drag_label"),
    [
        ({"edge": 0.06}, "cap_high_raw_edge"),
        (
            {"model_market_relationship": "model_fades_favorite"},
            "cap_market_fade",
        ),
        (
            {"side": "under", "model_market_relationship": "model_fades_favorite"},
            "cap_fire_under_market_fade",
        ),
    ],
)
def test_every_frozen_drag_label_excludes_the_row(overrides, drag_label):
    audit = _audit_module()

    evaluation = audit.evaluate_row(candidate_row(**overrides))

    assert evaluation.qualifies is False
    assert drag_label in evaluation.drag_labels


@pytest.mark.parametrize(
    "overrides",
    [
        {"display_verdict": "LEAN"},
        {"display_verdict": "PASS"},
        {"side": "under", "model_market_relationship": "model_other"},
    ],
)
def test_non_fire_or_no_keep_label_rows_cannot_qualify(overrides):
    audit = _audit_module()
    assert audit.evaluate_row(candidate_row(**overrides)).qualifies is False


def test_selector_is_invariant_to_result_pnl_clv_and_postgame_workload():
    audit = _audit_module()
    base = audit.evaluate_row(candidate_row())
    changed = audit.evaluate_row(
        candidate_row(
            result="loss",
            pick_history_pnl=-9.0,
            final_clv_bucket="worse_close_line",
            actual_workload="short",
            actual_pitch_count=20,
        )
    )

    assert (base.qualifies, base.keep_labels, base.drag_labels) == (
        changed.qualifies,
        changed.keep_labels,
        changed.drag_labels,
    )


def test_missing_prospective_critical_input_fails_closed():
    audit = _audit_module()
    row = candidate_row()
    row.pop("provider")

    evaluation = audit.evaluate_row(row)

    assert evaluation.qualifies is False
    assert "provider|live_display_provider|odds_source" in evaluation.missing_inputs


def test_post_start_keep_over_row_is_detected_and_excluded():
    audit = _audit_module()

    evaluation = audit.evaluate_row(candidate_row(bet_timing_window="post_start"))

    assert evaluation.qualifies is False
    assert evaluation.post_start_leakage is True


def _lock_to_single_historical_row(monkeypatch, audit):
    historical = candidate_row(
        slate_date="2026-07-28",
        normalized_pitcher="historical pitcher",
    )
    score = audit.score([historical])
    monkeypatch.setattr(audit, "LOCKED_HISTORICAL", score)
    monkeypatch.setattr(audit, "LOCKED_CURRENT_PROVIDER", score)
    return historical


def test_build_audit_blocks_duplicate_keys_before_other_gates(monkeypatch):
    audit = _audit_module()
    historical = _lock_to_single_historical_row(monkeypatch, audit)

    summary = audit.build_audit([historical, dict(historical)])

    assert summary["status"] == "blocked_duplicate_keys"
    assert summary["integrity"]["duplicate_keys"] == [
        "2026-07-28|historical pitcher|over"
    ]


def test_build_audit_blocks_locked_baseline_drift():
    audit = _audit_module()

    summary = audit.build_audit([
        candidate_row(
            slate_date="2026-07-28",
            normalized_pitcher="historical pitcher",
        )
    ])

    assert summary["status"] == "blocked_baseline_drift"
    assert summary["reconciliation"]["matches"] is False


def test_build_audit_blocks_prospective_input_gaps(monkeypatch):
    audit = _audit_module()
    historical = _lock_to_single_historical_row(monkeypatch, audit)
    prospective = candidate_row(normalized_pitcher="missing provider")
    prospective.pop("provider")

    summary = audit.build_audit([historical, prospective])

    assert summary["status"] == "blocked_input_gap"
    assert summary["integrity"]["input_gap_rows"] == 1


def test_build_audit_blocks_post_start_leakage(monkeypatch):
    audit = _audit_module()
    historical = _lock_to_single_historical_row(monkeypatch, audit)

    summary = audit.build_audit([
        historical,
        candidate_row(
            normalized_pitcher="late evidence",
            bet_timing_window="post_start",
        ),
    ])

    assert summary["status"] == "blocked_post_start_leakage"
    assert summary["integrity"]["post_start_leakage_rows"] == 1
