import json

import pytest

from analytics.diagnostics import no_drag_composite_canary_audit as audit


def candidate_row(**overrides):
    row = {
        "is_tracked_pick": True,
        "slate_date": "2026-07-21",
        "normalized_pitcher": "test pitcher",
        "side": "over",
        "result": "win",
        "pick_history_pnl": 1.0,
        "display_verdict": "FIRE 1u",
        "edge": 0.04,
        "locked_adj_ev": 0.10,
        "model_market_relationship": "model_agrees_with_favorite",
        "line_bucket": "4.5",
        "price_sign": "minus",
        "price_bucket": "-100 to -129",
        "bet_timing_window": "pre_30",
        "leash_risk_bucket": "normal",
        "pitcher_archetype_bucket": "standard_starter",
        "model_no_vig_gap": 0.01,
        "quality_gate_level": "clean",
        "batter_handedness_mode": "path_b",
        "lineup_real_split_count": 3,
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    ("overrides", "family"),
    [
        ({}, "strong_base_strict_runtime_core"),
        (
            {
                "display_verdict": "FIRE 1u",
                "model_market_relationship": "model_other",
                "bet_timing_window": "unknown",
            },
            "strong_base_strict_runtime_core",
        ),
        (
            {
                "display_verdict": "LEAN",
                "locked_adj_ev": 0.03,
                "model_market_relationship": "model_other",
            },
            "strong_base_selective_lean",
        ),
        (
            {
                "display_verdict": "LEAN",
                "line_bucket": "5.5",
                "pitcher_archetype_bucket": "low_k_standard",
                "model_no_vig_gap": 0.02,
                "model_market_relationship": "model_other",
            },
            "strong_base_selective_lean",
        ),
        (
            {
                "display_verdict": "PASS",
                "model_market_relationship": "model_other",
                "market_anchor_selector": {"labels": ["market_anchor_strict"]},
            },
            "market_anchor_strict",
        ),
    ],
)
def test_frozen_selector_positive_truth_table(overrides, family):
    evaluation = audit.evaluate_row(candidate_row(**overrides))
    assert evaluation.qualifies is True
    assert family in evaluation.families
    assert evaluation.drag_labels == ()
    assert evaluation.missing_inputs == ()


@pytest.mark.parametrize(
    ("overrides", "drag_label"),
    [
        ({"edge": 0.06}, "cap_high_raw_edge"),
        ({"model_market_relationship": "model_fades_favorite"}, "cap_market_fade"),
        (
            {"side": "under", "model_market_relationship": "model_fades_favorite"},
            "cap_fire_under_market_fade",
        ),
    ],
)
def test_frozen_drag_rules_exclude_rows(overrides, drag_label):
    evaluation = audit.evaluate_row(candidate_row(**overrides))
    assert evaluation.qualifies is False
    assert drag_label in evaluation.drag_labels


def test_selective_low_line_model_fade_is_removed_by_outer_drag():
    evaluation = audit.evaluate_row(candidate_row(
        display_verdict="LEAN",
        line_bucket="2.5-3.5",
        locked_adj_ev=0.03,
        model_market_relationship="model_fades_favorite",
        quality_gate_level="capped",
    ))
    assert "strong_base_selective_lean" in evaluation.families
    assert "cap_market_fade" in evaluation.drag_labels
    assert evaluation.qualifies is False


def test_verdict_precedence_uses_first_non_empty_value():
    row = candidate_row(
        display_verdict="LEAN",
        locked_verdict="FIRE 2u",
        actionable_verdict="PASS",
        locked_adj_ev=0.03,
        model_market_relationship="model_other",
    )
    assert audit.verdict(row) == "LEAN"
    assert audit.evaluate_row(row).families == ("strong_base_selective_lean",)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (-0.001, "ev_negative"),
        (0.0, "ev_unknown"),
        (0.059999, "ev_0_to_6"),
        (0.06, "ev_6_to_17"),
        (0.169999, "ev_6_to_17"),
        (0.17, "ev_17_plus"),
    ],
)
def test_adjusted_ev_boundaries(value, expected):
    assert audit.ev_bucket({"locked_adj_ev": value}) == expected


def test_adjusted_ev_preserves_truthy_or_zero_fallthrough():
    row = {"locked_adj_ev": 0.0, "adj_ev": 0.10, "ev": 0.03}
    assert audit.adjusted_ev(row) == 0.10


def test_market_anchor_labels_accept_object_fallback_and_json_object():
    assert audit.market_anchor_labels({
        "market_anchor_selector": {"labels": ["market_anchor_strict"]},
    }) == {"market_anchor_strict"}
    assert audit.market_anchor_labels({
        "market_anchor_selector_labels": ["market_anchor_strict"],
    }) == {"market_anchor_strict"}
    assert audit.market_anchor_labels({
        "market_anchor_selector": json.dumps({"labels": ["market_anchor_strict"]}),
    }) == {"market_anchor_strict"}


def test_rule_fingerprint_is_pinned():
    assert audit.RULE_FINGERPRINT == "22b03ecea02aa83e9174c24f5f05878823cb67766fe1c75102d34bfe5c3b4aa4"
