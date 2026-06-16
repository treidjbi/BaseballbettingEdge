import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))

from market_anchor_selector import (
    apply_market_anchor_selector_to_side,
    market_anchor_mode,
    market_implied_projection,
    no_vig_side_probability,
)


def _record(**overrides):
    record = {
        "pitcher": "Example Starter",
        "k_line": 5.5,
        "lambda": 6.2,
        "best_over_odds": -130,
        "best_under_odds": 110,
        "quality_gate_level": "clean",
        "opening_odds_source": "preview",
        "days_since_last_start": 5,
        "last_pitch_count": 92,
    }
    record.update(overrides)
    return record


def _side(**overrides):
    side = {
        "verdict": "FIRE 1u",
        "actionable_verdict": "FIRE 1u",
        "raw_verdict": "FIRE 1u",
        "edge": 0.055,
        "ev": 0.09,
        "adj_ev": 0.08,
    }
    side.update(overrides)
    return side


def test_mode_defaults_off_and_invalid_returns_off(monkeypatch):
    monkeypatch.delenv("MARKET_ANCHOR_SELECTOR_MODE", raising=False)
    assert market_anchor_mode() == "off"
    monkeypatch.setenv("MARKET_ANCHOR_SELECTOR_MODE", "bad")
    assert market_anchor_mode() == "off"


def test_no_vig_side_probability_normalizes_two_prices():
    over_prob = no_vig_side_probability(-130, 110, "over")
    under_prob = no_vig_side_probability(-130, 110, "under")
    assert round(over_prob + under_prob, 6) == 1.0
    assert over_prob > under_prob


def test_market_projection_inverts_no_vig_probability():
    projection = market_implied_projection(k_line=4.5, over_probability=0.5)
    assert 4.0 < projection < 5.0
    assert market_implied_projection(k_line=4.5, over_probability=0.62) > projection


def test_shadow_adds_metadata_without_changing_verdict():
    updated = apply_market_anchor_selector_to_side(_record(), "over", _side(), mode="shadow")

    assert updated["verdict"] == "FIRE 1u"
    assert updated["actionable_verdict"] == "FIRE 1u"
    assert updated["market_anchor_selector"]["mode"] == "shadow"
    assert updated["market_anchor_selector"]["applied"] is False
    assert "market_anchor_selector" in updated


def test_strict_label_requires_clean_market_favorite_stable_context():
    updated = apply_market_anchor_selector_to_side(_record(), "over", _side(), mode="shadow")
    labels = updated["market_anchor_selector"]["labels"]

    assert "market_anchor_core" in labels
    assert "market_anchor_strict" in labels

    fragile = apply_market_anchor_selector_to_side(
        _record(days_since_last_start=3),
        "over",
        _side(),
        mode="shadow",
    )
    assert "market_anchor_strict" not in fragile["market_anchor_selector"]["labels"]


def test_enforce_downside_caps_fire_that_fails_strict_only():
    updated = apply_market_anchor_selector_to_side(
        _record(days_since_last_start=3),
        "over",
        _side(verdict="FIRE 2u", actionable_verdict="FIRE 2u", raw_verdict="FIRE 2u"),
        mode="enforce_downside",
    )

    assert updated["verdict"] == "LEAN"
    assert updated["actionable_verdict"] == "LEAN"
    assert updated["raw_verdict"] == "FIRE 2u"
    assert updated["market_anchor_selector"]["applied"] is True
    assert "cap_fire_without_market_anchor_strict" in updated["market_anchor_selector"]["reasons"]


def test_enforce_downside_never_raises_lean():
    updated = apply_market_anchor_selector_to_side(
        _record(),
        "over",
        _side(verdict="LEAN", actionable_verdict="LEAN", raw_verdict="LEAN"),
        mode="enforce_downside",
    )

    assert updated["verdict"] == "LEAN"
    assert updated["actionable_verdict"] == "LEAN"
    assert updated["market_anchor_selector"]["would_verdict"] == "LEAN"
    assert updated["market_anchor_selector"]["applied"] is False
