import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))

from quality_gates import (
    apply_quality_to_record,
    cap_verdict,
    evaluate_record_quality,
    summarize_quality_gates,
)


def clean_fire_record():
    return {
        "pitcher": "Example Starter",
        "team": "Arizona Diamondbacks",
        "opp_team": "Los Angeles Dodgers",
        "game_time": "2026-04-29T18:40:00-07:00",
        "season_k9": 9.8,
        "recent_k9": 10.2,
        "career_k9": 8.9,
        "recent_start_count": 5,
        "lineup_used": True,
        "lineup_count": 9,
        "umpire": "Mature Umpire",
        "umpire_has_rating": True,
        "umpire_rating_games": 75,
        "opening_odds_source": "preview",
        "k_line": 6.5,
        "lambda": 7.3,
        "best_over_odds": -105,
        "best_under_odds": -115,
        "ev_over": {"verdict": "FIRE 2u", "adj_ev": 0.19, "ev": 0.21},
        "ev_under": {"verdict": "PASS", "adj_ev": -0.08, "ev": -0.07},
    }


def test_severe_gate_blocks_fire_two_and_preserves_raw_values():
    record = clean_fire_record()
    record["starter_mismatch"] = True

    gated = apply_quality_to_record(record)

    assert gated["projection_safe"] is False
    assert gated["quality_gate_level"] == "blocked"
    assert gated["max_actionable_verdict"] == "PASS"
    assert "starter_mismatch" in gated["input_quality_flags"]
    assert gated["ev_over"]["raw_verdict"] == "FIRE 2u"
    assert gated["ev_over"]["raw_adj_ev"] == 0.19
    assert gated["ev_over"]["verdict"] == "PASS"
    assert gated["ev_over"]["actionable_verdict"] == "PASS"
    assert gated["ev_over"]["adj_ev"] == 0.0


def test_one_soft_flag_caps_fire_two_to_fire_one():
    record = clean_fire_record()
    record["umpire"] = "Unrated Umpire"
    record["umpire_has_rating"] = False

    gated = apply_quality_to_record(record)

    assert gated["projection_safe"] is True
    assert gated["quality_gate_level"] == "capped"
    assert gated["max_actionable_verdict"] == "FIRE 1u"
    assert gated["ev_over"]["raw_verdict"] == "FIRE 2u"
    assert gated["ev_over"]["verdict"] == "FIRE 1u"
    assert gated["ev_over"]["actionable_verdict"] == "FIRE 1u"
    assert gated["ev_over"]["raw_adj_ev"] == 0.19
    assert gated["ev_over"]["adj_ev"] == 0.19


def test_two_soft_flags_cap_fire_two_to_lean():
    record = clean_fire_record()
    record["lineup_used"] = False
    record["opening_odds_source"] = "first_seen"

    gated = apply_quality_to_record(record)

    assert gated["quality_gate_level"] == "capped"
    assert gated["max_actionable_verdict"] == "LEAN"
    assert gated["ev_over"]["verdict"] == "LEAN"
    assert set(gated["input_quality_flags"]) >= {"projected_lineup", "first_seen_opening"}


def test_clean_record_keeps_fire_two():
    gated = apply_quality_to_record(clean_fire_record())

    assert gated["projection_safe"] is True
    assert gated["quality_gate_level"] == "clean"
    assert gated["max_actionable_verdict"] == "FIRE 2u"
    assert gated["input_quality_flags"] == []
    assert gated["ev_over"]["raw_verdict"] == "FIRE 2u"
    assert gated["ev_over"]["verdict"] == "FIRE 2u"
    assert gated["ev_over"]["actionable_verdict"] == "FIRE 2u"


def test_apply_quality_to_record_does_not_mutate_input():
    record = clean_fire_record()
    original = copy.deepcopy(record)

    apply_quality_to_record(record)

    assert record == original


def test_evaluate_record_quality_preserves_unknown_flags_without_caps():
    record = clean_fire_record()
    record["input_quality_flags"] = ["unknown_future_flag"]

    quality = evaluate_record_quality(record)

    assert quality["input_quality_flags"] == ["unknown_future_flag"]
    assert quality["quality_gate_level"] == "clean"
    assert quality["max_actionable_verdict"] == "FIRE 2u"


def test_missing_invalid_core_inputs_create_severe_flags():
    record = clean_fire_record()
    record["lambda"] = None
    record["best_over_odds"] = None
    record["team"] = ""

    quality = evaluate_record_quality(record)

    assert quality["quality_gate_level"] == "blocked"
    assert set(quality["input_quality_flags"]) >= {
        "invalid_lambda_inputs",
        "malformed_line_or_odds",
        "missing_team_or_opp_team",
    }


def test_maturity_states_are_reported_on_gated_record():
    record = clean_fire_record()
    record["recent_start_count"] = 3
    record["umpire_rating_games"] = 25
    record["lineup_count"] = 7
    record["opening_odds_source"] = "first_seen"

    gated = apply_quality_to_record(record)

    assert gated["data_maturity"] == {
        "pitcher": "developing",
        "umpire": "developing",
        "lineup": "partial",
        "market": "first_seen",
    }
    assert set(gated["input_quality_flags"]) >= {
        "developing_pitcher_sample",
        "thin_umpire_sample",
        "partial_lineup",
        "first_seen_opening",
    }


def test_cap_verdict_never_raises_verdict():
    assert cap_verdict("LEAN", "FIRE 2u") == "LEAN"
    assert cap_verdict("FIRE 2u", "FIRE 1u") == "FIRE 1u"
    assert cap_verdict("UNKNOWN", "LEAN") == "PASS"


def test_summarize_quality_gates_counts_levels_and_flag_frequencies():
    clean = apply_quality_to_record(clean_fire_record())

    capped_record = clean_fire_record()
    capped_record["lineup_used"] = False
    capped = apply_quality_to_record(capped_record)

    blocked_record = clean_fire_record()
    blocked_record["is_opener"] = True
    blocked = apply_quality_to_record(blocked_record)

    summary = summarize_quality_gates(
        [clean, capped, blocked],
        pre_record_skips={"no_target_book": 2},
    )

    assert summary["clean"] == 1
    assert summary["capped"] == 1
    assert summary["blocked"] == 1
    assert summary["soft_flags"]["projected_lineup"] == 1
    assert summary["severe_flags"]["opener"] == 1
    assert summary["pre_record_skips"] == {"no_target_book": 2}
