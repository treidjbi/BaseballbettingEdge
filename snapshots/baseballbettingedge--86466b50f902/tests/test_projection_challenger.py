import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))

from projection_challenger import (
    apply_projection_challenger,
    market_shrink_projection,
    projection_challenger_candidate,
    projection_challenger_mode,
)


def test_projection_challenger_mode_defaults_off(monkeypatch):
    monkeypatch.delenv("MARKET_SHRINK_PROJECTION_MODE", raising=False)

    assert projection_challenger_mode() == "off"


def test_projection_challenger_mode_accepts_shadow_and_enforce(monkeypatch):
    monkeypatch.setenv("MARKET_SHRINK_PROJECTION_MODE", "shadow")
    assert projection_challenger_mode() == "shadow"

    monkeypatch.setenv("MARKET_SHRINK_PROJECTION_MODE", "enforce")
    assert projection_challenger_mode() == "enforce"


def test_projection_challenger_mode_invalid_fails_closed(monkeypatch):
    monkeypatch.setenv("MARKET_SHRINK_PROJECTION_MODE", "yes")

    assert projection_challenger_mode() == "off"


def test_projection_challenger_candidate_defaults_market_shrink_25(monkeypatch):
    monkeypatch.delenv("MARKET_SHRINK_PROJECTION_CANDIDATE", raising=False)

    assert projection_challenger_candidate() == "market_shrink_25"


def test_market_shrink_projection_moves_toward_line():
    projected, weight = market_shrink_projection(7.0, 5.0, "market_shrink_25")

    assert projected == 6.5
    assert weight == 0.25


def test_apply_projection_challenger_shadow_preserves_selected_lambda():
    result = apply_projection_challenger(7.0, 5.0, mode="shadow", candidate="market_shrink_25")

    assert result["applied"] is False
    assert result["current_lambda"] == 7.0
    assert result["would_lambda"] == 6.5
    assert result["selected_lambda"] == 7.0
    assert result["reason"] == "shadow_only"


def test_apply_projection_challenger_enforce_selects_shrunk_lambda():
    result = apply_projection_challenger(7.0, 5.0, mode="enforce", candidate="market_shrink_25")

    assert result["applied"] is True
    assert result["selected_lambda"] == 6.5
    assert result["reason"] == "enforced"


def test_apply_projection_challenger_invalid_candidate_fails_closed():
    result = apply_projection_challenger(7.0, 5.0, mode="enforce", candidate="bad")

    assert result["applied"] is False
    assert result["selected_lambda"] == 7.0
    assert result["reason"] == "invalid_candidate"
