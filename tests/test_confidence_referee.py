import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))

from confidence_referee import (
    apply_referee_to_side,
    market_favorite_side,
    referee_mode,
)


def _record(**overrides):
    record = {
        "pitcher": "Example Starter",
        "k_line": 5.5,
        "lambda": 5.95,
        "best_over_odds": -125,
        "best_under_odds": 105,
        "quality_gate_level": "clean",
        "input_quality_flags": [],
    }
    record.update(overrides)
    return record


def _side(**overrides):
    side = {
        "raw_verdict": "FIRE 2u",
        "actionable_verdict": "FIRE 2u",
        "verdict": "FIRE 2u",
        "edge": 0.055,
        "ev": 0.18,
        "adj_ev": 0.18,
    }
    side.update(overrides)
    return side


def test_referee_mode_defaults_off(monkeypatch):
    monkeypatch.delenv("MARKET_FAVORITE_REFEREE_MODE", raising=False)
    assert referee_mode() == "off"


def test_referee_mode_invalid_value_returns_off(monkeypatch):
    monkeypatch.setenv("MARKET_FAVORITE_REFEREE_MODE", "strict")
    assert referee_mode() == "off"


def test_market_favorite_side_uses_current_two_sided_price():
    assert market_favorite_side(-125, 105) == "over"
    assert market_favorite_side(115, -130) == "under"
    assert market_favorite_side(-110, -110) == "tie"
    assert market_favorite_side(None, -110) == "unknown"


def test_off_mode_leaves_side_unchanged_without_metadata():
    original = _side(details={"nested": ["keep"]})

    updated = apply_referee_to_side(_record(), "over", original, mode="off")

    assert updated == original
    assert updated is not original
    assert updated["details"] is not original["details"]
    assert "confidence_referee" not in updated


def test_shadow_mode_adds_metadata_but_does_not_change_verdict():
    updated = apply_referee_to_side(
        _record(**{"lambda": 5.1}, best_over_odds=-130, best_under_odds=120),
        "under",
        _side(edge=0.025, adj_ev=0.11),
        mode="shadow",
    )

    assert updated["verdict"] == "FIRE 2u"
    assert updated["actionable_verdict"] == "FIRE 2u"
    assert updated["confidence_referee"]["mode"] == "shadow"
    assert updated["confidence_referee"]["relationship"] == "model_fades_favorite"
    assert updated["confidence_referee"]["market_favorite_side"] == "over"
    assert updated["confidence_referee"]["selected_side"] == "under"
    assert updated["confidence_referee"]["selected_odds"] == 120
    assert updated["confidence_referee"]["price_sign"] == "plus"
    assert updated["confidence_referee"]["projection_margin_ks"] == 0.4
    assert updated["confidence_referee"]["probability_edge"] == 0.025
    assert updated["confidence_referee"]["would_cap_to"] == "LEAN"
    assert updated["confidence_referee"]["applied"] is False
    assert "price_driven_market_fade" in updated["confidence_referee"]["reasons"]


def test_enforce_mode_caps_price_driven_market_fade_to_lean():
    updated = apply_referee_to_side(
        _record(**{"lambda": 5.1}, best_over_odds=-130, best_under_odds=120),
        "under",
        _side(edge=0.025, adj_ev=0.11),
        mode="enforce",
    )

    assert updated["raw_verdict"] == "FIRE 2u"
    assert updated["verdict"] == "LEAN"
    assert updated["actionable_verdict"] == "LEAN"
    assert updated["confidence_referee"]["applied"] is True
    assert "price_driven_market_fade" in updated["confidence_referee"]["reasons"]


def test_enforce_mode_caps_non_price_driven_fade_fire_two_to_fire_one():
    updated = apply_referee_to_side(
        _record(**{"lambda": 7.0}, k_line=5.5, best_over_odds=115, best_under_odds=-130),
        "over",
        _side(edge=0.08, adj_ev=0.22),
        mode="enforce",
    )

    assert updated["verdict"] == "FIRE 1u"
    assert updated["confidence_referee"]["would_cap_to"] == "FIRE 1u"


def test_referee_never_raises_verdict_on_market_agreement():
    updated = apply_referee_to_side(
        _record(**{"lambda": 6.4}, best_over_odds=-130, best_under_odds=120),
        "over",
        _side(raw_verdict="LEAN", actionable_verdict="LEAN", verdict="LEAN", adj_ev=0.04),
        mode="enforce",
    )

    assert updated["verdict"] == "LEAN"
    assert updated["confidence_referee"]["relationship"] == "model_agrees_with_favorite"
    assert updated["confidence_referee"]["applied"] is False
