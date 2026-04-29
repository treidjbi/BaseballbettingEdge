"""Pure input-quality gates for pitcher prop records."""

from __future__ import annotations

import copy
import math
from collections import Counter
from typing import Any


VERDICT_ORDER = {
    "PASS": 0,
    "LEAN": 1,
    "FIRE 1u": 2,
    "FIRE 2u": 3,
}

SEVERE_FLAGS = {
    "no_pitcher_k_profile",
    "starter_mismatch",
    "opener",
    "missing_game_time",
    "unresolved_probable",
    "malformed_line_or_odds",
    "invalid_lambda_inputs",
    "missing_team_or_opp_team",
    "no_target_book",
}

SOFT_CAP_FLAGS = {
    "projected_lineup",
    "partial_lineup",
    "unrated_umpire",
    "thin_umpire_sample",
    "missing_career_swstr",
    "neutral_park_fallback",
    "first_seen_opening",
    "thin_recent_start_sample",
    "developing_pitcher_sample",
    "partial_movement_history",
}


def _is_usable_number(value: Any, *, positive: bool = False) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(number):
        return False
    return number > 0 if positive else True


def _is_usable_american_odds(value: Any) -> bool:
    if not _is_usable_number(value):
        return False
    return float(value) != 0


def _add_flag(flags: list[str], flag: str) -> None:
    if flag not in flags:
        flags.append(flag)


def _existing_flags(record: dict) -> list[str]:
    flags = record.get("input_quality_flags") or []
    if not isinstance(flags, list):
        return []

    deduped: list[str] = []
    for flag in flags:
        if isinstance(flag, str):
            _add_flag(deduped, flag)
    return deduped


def _flag_reason(flag: str) -> str:
    return flag.replace("_", " ")


def pitcher_maturity(record: dict) -> tuple[str, list[str]]:
    flags: list[str] = []
    has_profile = any(
        _is_usable_number(record.get(field), positive=True)
        for field in ("season_k9", "recent_k9", "career_k9")
    )
    if not has_profile:
        return "none", ["no_pitcher_k_profile"]

    recent_start_count = record.get("recent_start_count")
    if not _is_usable_number(recent_start_count):
        return "mature", flags

    count = int(float(recent_start_count))
    if 1 <= count <= 2:
        flags.append("thin_recent_start_sample")
        return "thin", flags
    if 3 <= count <= 4:
        flags.append("developing_pitcher_sample")
        return "developing", flags
    return "mature", flags


def umpire_maturity(record: dict) -> tuple[str, list[str]]:
    flags: list[str] = []
    if record.get("umpire") and record.get("umpire_has_rating") is False:
        return "unknown", ["unrated_umpire"]

    rating_games = record.get("umpire_rating_games")
    if rating_games is None:
        return "mature", flags
    if not _is_usable_number(rating_games):
        return "unknown", ["unrated_umpire"]

    games = int(float(rating_games))
    if games < 10:
        flags.append("thin_umpire_sample")
        return "thin", flags
    if games < 50:
        flags.append("thin_umpire_sample")
        return "developing", flags
    return "mature", flags


def lineup_maturity(record: dict) -> tuple[str, list[str]]:
    if record.get("lineup_used") is False:
        return "projected", ["projected_lineup"]

    lineup_count = record.get("lineup_count")
    if _is_usable_number(lineup_count):
        count = int(float(lineup_count))
        if 0 < count < 9:
            return "partial", ["partial_lineup"]
        if count >= 9:
            return "confirmed", []

    if record.get("lineup_used") is True:
        return "confirmed", []
    return "projected", ["projected_lineup"]


def market_maturity(record: dict) -> tuple[str, list[str]]:
    flags: list[str] = []
    if record.get("no_target_book") is True:
        flags.append("no_target_book")
        return "missing", flags

    source = record.get("opening_odds_source")
    if source == "first_seen":
        return "first_seen", ["first_seen_opening"]
    if source == "preview":
        return "preview_open", flags
    if source == "full_movement":
        return "full_movement", flags
    return "missing", flags


def _core_input_flags(record: dict) -> list[str]:
    flags: list[str] = []
    if record.get("is_opener") is True:
        flags.append("opener")
    if record.get("starter_mismatch") is True:
        flags.append("starter_mismatch")
    if record.get("unresolved_probable") is True:
        flags.append("unresolved_probable")
    if not record.get("game_time"):
        flags.append("missing_game_time")
    if not record.get("team") or not record.get("opp_team"):
        flags.append("missing_team_or_opp_team")
    if not _is_usable_number(record.get("lambda"), positive=True):
        flags.append("invalid_lambda_inputs")

    has_line = _is_usable_number(record.get("k_line"), positive=True)
    has_over = _is_usable_american_odds(record.get("best_over_odds"))
    has_under = _is_usable_american_odds(record.get("best_under_odds"))
    if not has_line or not has_over or not has_under:
        flags.append("malformed_line_or_odds")
    if not has_over and not has_under:
        flags.append("no_target_book")
    return flags


def _source_quality_flags(record: dict) -> list[str]:
    flags: list[str] = []
    if record.get("career_swstr_pct") is None and record.get("swstr_pct") is not None:
        flags.append("missing_career_swstr")
    if record.get("park_factor_source") in {"neutral_fallback", "fallback", "unknown"}:
        flags.append("neutral_park_fallback")
    if record.get("partial_movement_history") is True:
        flags.append("partial_movement_history")
    return flags


def evaluate_record_quality(record: dict) -> dict:
    """Return quality metadata without mutating record."""
    flags = _existing_flags(record)

    pitcher_state, pitcher_flags = pitcher_maturity(record)
    umpire_state, umpire_flags = umpire_maturity(record)
    lineup_state, lineup_flags = lineup_maturity(record)
    market_state, market_flags = market_maturity(record)

    for flag in (
        _core_input_flags(record)
        + pitcher_flags
        + umpire_flags
        + lineup_flags
        + market_flags
        + _source_quality_flags(record)
    ):
        _add_flag(flags, flag)

    severe_flags = [flag for flag in flags if flag in SEVERE_FLAGS]
    soft_flags = [flag for flag in flags if flag in SOFT_CAP_FLAGS]

    if severe_flags:
        projection_safe = False
        quality_gate_level = "blocked"
        max_actionable_verdict = "PASS"
        verdict_cap_reason = "blocked by severe input flag: " + ", ".join(severe_flags)
    elif len(soft_flags) == 1:
        projection_safe = True
        quality_gate_level = "capped"
        max_actionable_verdict = "FIRE 1u"
        verdict_cap_reason = f"1 soft input flag: {soft_flags[0]}"
    elif len(soft_flags) >= 2:
        projection_safe = True
        quality_gate_level = "capped"
        max_actionable_verdict = "LEAN"
        verdict_cap_reason = f"{len(soft_flags)} soft input flags: " + ", ".join(soft_flags)
    else:
        projection_safe = True
        quality_gate_level = "clean"
        max_actionable_verdict = "FIRE 2u"
        verdict_cap_reason = ""

    quality_gate_reasons = [_flag_reason(flag) for flag in severe_flags + soft_flags]

    return {
        "input_quality_flags": flags,
        "projection_safe": projection_safe,
        "quality_gate_level": quality_gate_level,
        "quality_gate_reasons": quality_gate_reasons,
        "verdict_cap_reason": verdict_cap_reason,
        "data_maturity": {
            "pitcher": pitcher_state,
            "umpire": umpire_state,
            "lineup": lineup_state,
            "market": market_state,
        },
        "max_actionable_verdict": max_actionable_verdict,
    }


def cap_verdict(raw_verdict: str, max_actionable_verdict: str) -> str:
    raw_order = VERDICT_ORDER.get(raw_verdict, VERDICT_ORDER["PASS"])
    max_order = VERDICT_ORDER.get(max_actionable_verdict, VERDICT_ORDER["PASS"])
    target_order = min(raw_order, max_order)
    for verdict, order in VERDICT_ORDER.items():
        if order == target_order:
            return verdict
    return "PASS"


def _apply_quality_to_side(side: dict, quality: dict) -> dict:
    updated = copy.deepcopy(side)
    raw_verdict = updated.get("raw_verdict", updated.get("verdict", "PASS"))
    raw_adj_ev = updated.get("raw_adj_ev", updated.get("adj_ev", 0.0))
    actionable_verdict = cap_verdict(raw_verdict, quality["max_actionable_verdict"])

    updated["raw_verdict"] = raw_verdict
    updated["raw_adj_ev"] = raw_adj_ev
    updated["actionable_verdict"] = actionable_verdict
    updated["verdict"] = actionable_verdict
    updated["quality_gate_level"] = quality["quality_gate_level"]
    updated["quality_gate_reasons"] = list(quality["quality_gate_reasons"])
    if quality["quality_gate_level"] == "blocked":
        updated["adj_ev"] = 0.0
    return updated


def apply_quality_to_record(record: dict) -> dict:
    """Return a copied record with quality metadata and capped ev_over/ev_under."""
    quality = evaluate_record_quality(record)
    updated = copy.deepcopy(record)
    updated.update(quality)

    for side_key in ("ev_over", "ev_under"):
        side = updated.get(side_key)
        if isinstance(side, dict):
            updated[side_key] = _apply_quality_to_side(side, quality)
    return updated


def summarize_quality_gates(
    records: list[dict], pre_record_skips: dict | None = None
) -> dict:
    level_counts = Counter({"clean": 0, "capped": 0, "blocked": 0})
    severe_counts: Counter[str] = Counter()
    soft_counts: Counter[str] = Counter()

    for record in records:
        level = record.get("quality_gate_level", "clean")
        if level not in level_counts:
            level = "clean"
        level_counts[level] += 1

        for flag in record.get("input_quality_flags") or []:
            if flag in SEVERE_FLAGS:
                severe_counts[flag] += 1
            elif flag in SOFT_CAP_FLAGS:
                soft_counts[flag] += 1

    return {
        "clean": level_counts["clean"],
        "capped": level_counts["capped"],
        "blocked": level_counts["blocked"],
        "severe_flags": dict(severe_counts),
        "soft_flags": dict(soft_counts),
        "pre_record_skips": dict(pre_record_skips or {}),
    }
