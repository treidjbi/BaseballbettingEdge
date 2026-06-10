import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))

from profit_rescue_referee import apply_profit_rescue_to_side, profit_rescue_mode


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
        "quality_actionable_verdict": "FIRE 2u",
        "actionable_verdict": "FIRE 2u",
        "verdict": "FIRE 2u",
        "edge": 0.08,
        "ev": 0.2,
        "adj_ev": 0.2,
    }
    side.update(overrides)
    return side


def test_profit_rescue_mode_defaults_off(monkeypatch):
    monkeypatch.delenv("PROFIT_RESCUE_REFEREE_MODE", raising=False)
    assert profit_rescue_mode() == "off"


def test_profit_rescue_mode_invalid_value_returns_off(monkeypatch):
    monkeypatch.setenv("PROFIT_RESCUE_REFEREE_MODE", "strict")
    assert profit_rescue_mode() == "off"


def test_off_mode_leaves_side_unchanged_without_metadata():
    original = _side(details={"nested": ["keep"]})

    updated = apply_profit_rescue_to_side(_record(), "over", original, mode="off")

    assert updated == original
    assert updated is not original
    assert updated["details"] is not original["details"]
    assert "profit_rescue_referee" not in updated


def test_shadow_mode_records_fire_two_cap_without_changing_verdict():
    updated = apply_profit_rescue_to_side(
        _record(best_over_odds=-125, best_under_odds=105),
        "over",
        _side(),
        mode="shadow",
    )

    assert updated["verdict"] == "FIRE 2u"
    assert updated["actionable_verdict"] == "FIRE 2u"
    assert updated["profit_rescue_referee"]["mode"] == "shadow"
    assert updated["profit_rescue_referee"]["would_cap_to"] == "FIRE 1u"
    assert updated["profit_rescue_referee"]["applied"] is False
    assert "cap_fire_two_to_fire_one" in updated["profit_rescue_referee"]["reasons"]


def test_enforce_mode_caps_fire_two_to_fire_one():
    updated = apply_profit_rescue_to_side(
        _record(best_over_odds=-125, best_under_odds=105),
        "over",
        _side(),
        mode="enforce",
    )

    assert updated["raw_verdict"] == "FIRE 2u"
    assert updated["verdict"] == "FIRE 1u"
    assert updated["actionable_verdict"] == "FIRE 1u"
    assert updated["profit_rescue_referee"]["applied"] is True


def test_enforce_mode_caps_fire_under_to_lean_after_fire_two_cap():
    updated = apply_profit_rescue_to_side(
        _record(best_over_odds=115, best_under_odds=-130),
        "under",
        _side(raw_verdict="FIRE 2u", verdict="FIRE 2u", actionable_verdict="FIRE 2u"),
        mode="enforce",
    )

    assert updated["verdict"] == "LEAN"
    assert updated["actionable_verdict"] == "LEAN"
    assert "cap_fire_under_to_lean" in updated["profit_rescue_referee"]["reasons"]
    assert "cap_fire_two_to_fire_one" in updated["profit_rescue_referee"]["reasons"]


def test_enforce_mode_caps_market_fade_fire_to_lean():
    updated = apply_profit_rescue_to_side(
        _record(best_over_odds=-140, best_under_odds=120),
        "under",
        _side(raw_verdict="FIRE 1u", verdict="FIRE 1u", actionable_verdict="FIRE 1u"),
        mode="enforce",
    )

    assert updated["verdict"] == "LEAN"
    assert updated["profit_rescue_referee"]["relationship"] == "model_fades_favorite"
    assert "cap_market_fade_fire_to_lean" in updated["profit_rescue_referee"]["reasons"]


def test_profit_rescue_never_raises_lean_even_when_model_agrees_with_market():
    updated = apply_profit_rescue_to_side(
        _record(best_over_odds=-140, best_under_odds=120),
        "over",
        _side(raw_verdict="LEAN", verdict="LEAN", actionable_verdict="LEAN"),
        mode="enforce",
    )

    assert updated["verdict"] == "LEAN"
    assert updated["profit_rescue_referee"]["would_cap_to"] == "LEAN"
    assert updated["profit_rescue_referee"]["applied"] is False
