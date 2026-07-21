"""Pure, prospective-only selector for the pregame alternative-pick methodology.

This module deliberately has no network, database, artifact, or runtime writes.
It is a versioned comparison contract and cannot modify official pick behavior.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pipeline.name_utils import normalize

BUNDLE_ID = "pregame_alternative_pick_methodology_v1"
CONSENSUS_SELECTOR_ID = "no_drag_distinct_family_consensus_core_v1"
EXPANSION_SELECTOR_ID = "moderate_edge_quality_reentry_expansion_v1"
MANIFEST_PATH = Path(__file__).with_name("alternative_pick_selector_manifest_v1.json")
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
PHOENIX = ZoneInfo("America/Phoenix")


@dataclass(frozen=True)
class FamilyVote:
    state: Literal["agree", "disagree", "pending"]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class AlternativePickEvaluation:
    eligible: bool
    eligibility_reason_codes: tuple[str, ...]
    selector_fingerprint: str
    family_states: dict[str, FamilyVote]
    family_count: int
    no_drag: bool | None
    lane: Literal["consensus_core", "reentry_expansion"] | None
    selection_status: Literal["selected", "not_selected", "pending"]
    reason_codes: tuple[str, ...]
    normalized_inputs: dict[str, Any]


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def selector_fingerprint() -> str:
    payload = json.dumps(MANIFEST, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256_hex(payload)


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return int(number) if number is not None else None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _enum(value: Any) -> str:
    return _text(value).lower()


def _parse_time(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(f"{text[:-1]}+00:00" if text.endswith("Z") else text)
    except ValueError:
        return None


def _as_utc(value: Any) -> datetime | None:
    parsed = _parse_time(value)
    if parsed is None:
        return None
    return parsed.astimezone(ZoneInfo("UTC")) if parsed.tzinfo else parsed.replace(tzinfo=ZoneInfo("UTC"))


def display_verdict(row: dict[str, Any]) -> str:
    for field in MANIFEST["field_precedence"]["display_verdict"]:
        value = _text(row.get(field))
        if value:
            return value
    return ""


def source_fire_verdict(row: dict[str, Any]) -> str:
    for field in MANIFEST["field_precedence"]["source_fire_verdict"][:2]:
        value = _text(row.get(field))
        if value.upper().startswith("FIRE"):
            return value
    return display_verdict(row)


def adjusted_ev(row: dict[str, Any]) -> float | None:
    # Intentionally preserve Python truthy-or precedence for source compatibility.
    values = [_number(row.get(field)) for field in MANIFEST["field_precedence"]["adjusted_ev"]]
    return values[0] or values[1] or values[2]


def line_bucket(k_line: Any) -> str:
    number = _number(k_line)
    if number is None:
        return "unknown"
    if number <= 3.5:
        return "2.5-3.5"
    if number == 4.5:
        return "4.5"
    if number == 5.5:
        return "5.5"
    if number == 6.5:
        return "6.5"
    return "7.5+"


def timing_bucket(observed_at: Any, game_time: Any) -> str:
    observed, start = _as_utc(observed_at), _as_utc(game_time)
    if observed is None or start is None:
        return "unknown"
    minutes = (start - observed).total_seconds() / 60.0
    if minutes < 0:
        return "post_start"
    if minutes <= 5:
        return "pre_5"
    if minutes <= 15:
        return "pre_15"
    if minutes <= 30:
        return "pre_30"
    if minutes <= 60:
        return "pre_60"
    if minutes <= 120:
        return "pre_120"
    return "early"


def _opportunity_bucket(avg_ip: Any, recent_start_count: Any) -> str:
    innings = _number(avg_ip)
    if innings is None:
        return "unknown"
    if innings < 4.5:
        return "short_leash"
    if innings >= 6.2 and (_integer(recent_start_count) or 0) >= 3:
        return "deep_starter"
    return "normal"


def runtime_opportunity_bucket(avg_ip: Any, recent_start_count: Any) -> str:
    """Return the runtime-safe workload bucket used by research and selection."""
    return _opportunity_bucket(avg_ip, recent_start_count)


def _leash_bucket(pitcher: dict[str, Any], opportunity: str) -> str:
    if bool(pitcher.get("is_opener")) or bool(pitcher.get("starter_mismatch")) or opportunity == "short_leash":
        return "high"
    if (_integer(pitcher.get("last_pitch_count")) or 0) >= 105 or (_integer(pitcher.get("days_since_last_start")) or 99) < 4:
        return "medium"
    return "normal"


def runtime_leash_risk_bucket(*, is_opener: Any, starter_mismatch: Any, avg_ip: Any, last_pitch_count: Any, days_since_last_start: Any) -> str:
    return _leash_bucket({
        "is_opener": is_opener,
        "starter_mismatch": starter_mismatch,
        "avg_ip": avg_ip,
        "last_pitch_count": last_pitch_count,
        "days_since_last_start": days_since_last_start,
    }, _opportunity_bucket(avg_ip, None))


def _archetype(pitcher: dict[str, Any], opportunity: str) -> str:
    if bool(pitcher.get("is_opener")) or bool(pitcher.get("starter_mismatch")):
        return "opener_or_mismatch"
    if opportunity == "short_leash":
        return "short_leash"
    values = [_number(pitcher.get(field)) for field in ("season_k9", "recent_k9", "career_k9")]
    max_k9 = max(value for value in values if value is not None) if any(value is not None for value in values) else None
    if opportunity == "deep_starter" and max_k9 is not None and max_k9 >= 10:
        return "high_k_deep_starter"
    if opportunity == "deep_starter":
        return "deep_starter"
    if max_k9 is not None and max_k9 >= 10:
        return "high_k_standard"
    if max_k9 is not None and max_k9 < 7:
        return "low_k_standard"
    return "standard_starter"


def runtime_pitcher_archetype_bucket(*, is_opener: Any, starter_mismatch: Any, opportunity_bucket: str, season_k9: Any, recent_k9: Any, career_k9: Any) -> str:
    return _archetype({
        "is_opener": is_opener,
        "starter_mismatch": starter_mismatch,
        "season_k9": season_k9,
        "recent_k9": recent_k9,
        "career_k9": career_k9,
    }, opportunity_bucket)


def runtime_model_market_relationship(model_side: Any, market_favorite: Any) -> str:
    model, favorite = _enum(model_side), _enum(market_favorite)
    if model not in {"over", "under"} or favorite not in {"over", "under"}:
        return "unknown"
    return "model_agrees_with_favorite" if model == favorite else "model_fades_favorite"


def _anchor_labels(pick: dict[str, Any]) -> tuple[set[str] | None, bool]:
    raw = pick.get("market_anchor_selector")
    if raw is None:
        return set(), False
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None, True
    if not isinstance(raw, dict) or "labels" not in raw:
        return None, True
    labels = raw.get("labels")
    if not isinstance(labels, (list, tuple, set)):
        return None, True
    return {_enum(value) for value in labels if _text(value)}, False


def derive_runtime_features(*, pitcher: dict[str, Any], pick: dict[str, Any], market_evidence: dict[str, Any], observed_at: Any) -> dict[str, Any]:
    side = _enum(pick.get("side"))
    over_odds, under_odds = _number(pitcher.get("best_over_odds")), _number(pitcher.get("best_under_odds"))
    odds = over_odds if side == "over" else under_odds if side == "under" else None
    favorite = "over" if over_odds is not None and under_odds is not None and over_odds < under_odds else "under" if over_odds is not None and under_odds is not None else "unknown"
    model_side = _enum(pick.get("model_side")) or side
    relationship = _enum(pick.get("model_market_relationship"))
    if not relationship:
        relationship = runtime_model_market_relationship(model_side, favorite)
    opportunity = _enum(pitcher.get("opportunity_bucket")) or _opportunity_bucket(pitcher.get("avg_ip"), pitcher.get("recent_start_count"))
    leash = _enum(pitcher.get("leash_risk_bucket")) or _leash_bucket(pitcher, opportunity)
    edge = _number(pick.get("edge"))
    skepticism = bool(pick.get("large_edge_skepticism_flag"))
    if not skepticism and edge is not None and edge >= 0.06:
        adverse = sum((relationship == "model_fades_favorite", leash in {"medium", "high"}, opportunity == "short_leash", _enum(pick.get("quality_gate_level")) not in {"", "clean", "none"}))
        skepticism = adverse >= 2
    labels, malformed_anchor = _anchor_labels(pick)
    return {
        "side": side, "official_verdict": display_verdict(pick), "source_fire_verdict": source_fire_verdict(pick),
        "k_line": _number(pitcher.get("k_line")), "line_bucket": line_bucket(pitcher.get("k_line")),
        "odds": odds, "price_sign": "minus" if odds is not None and odds < 0 else "plus" if odds is not None and odds > 0 else "unknown",
        "bet_timing_window": timing_bucket(observed_at, pitcher.get("game_time")), "model_market_relationship": relationship,
        "model_no_vig_gap": _number(pick.get("model_no_vig_gap")), "edge": edge, "adjusted_ev": adjusted_ev(pick),
        "quality_gate_level": _enum(pick.get("quality_gate_level")), "opportunity_bucket": opportunity,
        "leash_risk_bucket": leash, "pitcher_archetype_bucket": _archetype(pitcher, opportunity),
        "large_edge_skepticism_flag": skepticism, "anchor_labels": sorted(labels) if labels is not None else None,
        "anchor_metadata_malformed": malformed_anchor,
        "observed_at": _as_utc(observed_at).isoformat() if _as_utc(observed_at) is not None else None,
    }


def strong_base_strict_plus_selective(features: dict[str, Any]) -> FamilyVote:
    required = ("official_verdict", "side", "adjusted_ev", "model_market_relationship", "line_bucket", "leash_risk_bucket", "pitcher_archetype_bucket")
    if any(features.get(field) in {None, "", "unknown"} for field in required):
        return FamilyVote("pending", ("base_inputs_missing",))
    fire = features["official_verdict"].upper().startswith("FIRE")
    lean = features["official_verdict"].upper() == "LEAN"
    ev = features["adjusted_ev"]
    strict = fire and ((features["model_market_relationship"] == "model_agrees_with_favorite" and 0.06 <= ev < 0.17 and features["bet_timing_window"] == "pre_30") or (features["side"] == "over" and 0.06 <= ev < 0.17 and features["leash_risk_bucket"] == "normal"))
    selective = lean and ((features["line_bucket"] == "4.5" and 0 <= ev < 0.06 and features["leash_risk_bucket"] == "normal") or (features["pitcher_archetype_bucket"] == "low_k_standard" and (features["model_no_vig_gap"] or -1) >= 0.02) or (features["line_bucket"] == "2.5-3.5" and features["model_market_relationship"] == "model_fades_favorite" and features["quality_gate_level"] == "capped"))
    return FamilyVote("agree" if strict or selective else "disagree", ("strong_base_strict_runtime_core" if strict else "strong_base_selective_lean" if selective else "base_predicate_false",))


def preclose_strong(features: dict[str, Any], market_evidence: dict[str, Any]) -> FamilyVote:
    ids = market_evidence.get("observation_ids")
    if not isinstance(ids, (list, tuple, set)) or len({str(value) for value in ids if _text(value)}) < 2:
        return FamilyVote("pending", ("preclose_observations_immature",))
    if market_evidence.get("reversal_book_count") is None or market_evidence.get("volatile_book_count") is None:
        return FamilyVote("pending", ("preclose_volatility_missing",))
    first_observed, last_observed, checkpoint = (
        _as_utc(market_evidence.get("first_observed_at")),
        _as_utc(market_evidence.get("last_observed_at")),
        _as_utc(features.get("observed_at")),
    )
    if first_observed is None or last_observed is None or checkpoint is None:
        return FamilyVote("pending", ("preclose_observation_times_missing",))
    if first_observed > last_observed or last_observed > checkpoint:
        return FamilyVote("pending", ("preclose_observation_times_invalid",))
    if _enum(market_evidence.get("freshness_status")) != "fresh":
        return FamilyVote("pending", ("preclose_evidence_stale",))
    score = 0
    toward, away = _integer(market_evidence.get("toward_pick_count")), _integer(market_evidence.get("away_from_pick_count"))
    if toward is None or away is None or _integer(market_evidence.get("book_count")) is None:
        return FamilyVote("pending", ("preclose_counts_missing",))
    score += 3 if toward > away else -2 if away > toward else 0
    edge, ev, gap = features["edge"], features["adjusted_ev"], features["model_no_vig_gap"]
    if edge is None or ev is None or gap is None:
        return FamilyVote("pending", ("preclose_runtime_inputs_missing",))
    score += 3 if edge < .02 else 2 if edge < .04 else 1 if edge < .06 else -2
    score += 2 if ev < .06 else 1 if ev < .17 else -1
    score += 1 if 0 < gap < .04 else -1 if gap >= .04 else 0
    score += 1 if features["price_sign"] == "minus" else -1 if features["price_sign"] == "plus" else 0
    score += 1 if features["quality_gate_level"] in {"", "clean", "none"} else -2 if features["quality_gate_level"] in {"blocked", "severe"} else 0
    score += 1 if features["bet_timing_window"] in {"pre_120", "pre_60", "pre_30"} else -1 if features["bet_timing_window"] in {"pre_5", "post_start"} else 0
    books = _integer(market_evidence.get("book_count")) or 0
    score += 1 if bool(market_evidence.get("broad_confirmation")) or books >= 3 else -1 if books == 1 else 0
    score -= 2 if bool(market_evidence.get("best_is_off_market")) else 0
    reversals, volatility = _integer(market_evidence.get("reversal_book_count")) or 0, _integer(market_evidence.get("volatile_book_count")) or 0
    score += -2 if reversals > 0 or volatility > 1 else 1 if reversals == 0 and volatility == 0 else 0
    score -= 1 if features["side"] == "under" and features["model_market_relationship"] == "model_fades_favorite" else 0
    return FamilyVote("agree" if score >= 5 else "disagree", ("strong_preclose_clv_proxy" if score >= 5 else "preclose_score_below_threshold",))


def moderate_edge_quality_reentry(features: dict[str, Any]) -> FamilyVote:
    required = ("edge", "adjusted_ev", "model_no_vig_gap", "quality_gate_level")
    if any(features.get(field) is None for field in required):
        return FamilyVote("pending", ("reentry_inputs_missing",))
    if not features["source_fire_verdict"].upper().startswith("FIRE"):
        return FamilyVote("disagree", ("source_not_fire",))
    agrees = (.02 <= features["edge"] < .06 and features["adjusted_ev"] < .17 and features["model_no_vig_gap"] >= .04 and features["quality_gate_level"] in {"", "clean", "none"} and not features["large_edge_skepticism_flag"])
    return FamilyVote("agree" if agrees else "disagree", ("moderate_edge_quality_reentry" if agrees else "reentry_predicate_false",))


def _drag(features: dict[str, Any]) -> bool | None:
    if features["edge"] is None or features["model_market_relationship"] == "unknown" or not features["official_verdict"] or not features["side"]:
        return None
    return features["edge"] >= .06 or features["model_market_relationship"] == "model_fades_favorite" or (features["official_verdict"].upper().startswith("FIRE") and features["side"] == "under" and features["model_market_relationship"] == "model_fades_favorite")


def _eligibility(pitcher: dict[str, Any], pick: dict[str, Any], market_evidence: dict[str, Any], slate_date: Any, is_tracked: bool, observed_at: Any, source_payload_sha256: str, source_artifact_byte_sha256: str) -> tuple[str, ...]:
    reasons: list[str] = []
    observed, start = _as_utc(observed_at), _as_utc(pitcher.get("game_time"))
    observed_slate = observed.astimezone(PHOENIX).date().isoformat() if observed is not None else ""
    if _text(slate_date) != observed_slate:
        reasons.append("wrong_phoenix_slate_date")
    tracked = _enum(is_tracked) in {"true", "1", "yes"} if isinstance(is_tracked, str) else bool(is_tracked)
    if not tracked:
        reasons.append("untracked_pick")
    if display_verdict(pick).upper() == "PASS":
        reasons.append("pass_verdict")
    if observed is None or start is None or observed >= start:
        reasons.append("game_started")
    if _enum(market_evidence.get("provider")) not in set(MANIFEST["provider_allow_list"]):
        reasons.append("unsupported_provider")
    if _number(pick.get("official_k_line")) is not None and _number(pick.get("official_k_line")) != _number(pitcher.get("k_line")):
        reasons.append("line_mismatch")
    if pick.get("source_payload_sha256") is not None and pick.get("source_payload_sha256") != source_payload_sha256:
        reasons.append("artifact_hash_mismatch")
    if pick.get("source_artifact_byte_sha256") is not None and pick.get("source_artifact_byte_sha256") != source_artifact_byte_sha256:
        reasons.append("artifact_hash_mismatch")
    if _enum(pick.get("candidate_side")) and _enum(pick.get("candidate_side")) != _enum(pick.get("side")):
        reasons.append("alternate_or_opposite_side_search")
    for field, expected in (
        ("candidate_side", _enum(pick.get("side"))),
        ("candidate_pitcher", normalize(pitcher.get("pitcher") or "")),
        ("candidate_k_line", _number(pitcher.get("k_line"))),
        ("candidate_game_time", _text(pitcher.get("game_time"))),
        ("candidate_source_payload_sha256", source_payload_sha256),
    ):
        actual = market_evidence.get(field)
        if actual is None:
            continue
        normalized_actual = normalize(actual) if field == "candidate_pitcher" else _enum(actual) if field == "candidate_side" else _number(actual) if field == "candidate_k_line" else _text(actual)
        if normalized_actual != expected:
            reasons.append("market_identity_mismatch")
    return tuple(dict.fromkeys(reasons))


def evaluate_alternative_pick(*, pitcher: dict[str, Any], pick: dict[str, Any], market_evidence: dict[str, Any], slate_date: str, is_tracked: bool, source_artifact_path: str, source_payload_sha256: str, source_artifact_byte_sha256: str, observed_at: str) -> AlternativePickEvaluation:
    del source_artifact_path  # Provenance is recorded by Task 2; it is not a selection input.
    features = derive_runtime_features(pitcher=pitcher, pick=pick, market_evidence=market_evidence, observed_at=observed_at)
    eligibility = _eligibility(pitcher, pick, market_evidence, slate_date, is_tracked, observed_at, source_payload_sha256, source_artifact_byte_sha256)
    base = strong_base_strict_plus_selective(features)
    if features["anchor_metadata_malformed"]:
        anchor = FamilyVote("pending", ("anchor_metadata_malformed",))
    elif "market_anchor_strict" in (features["anchor_labels"] or []):
        anchor = FamilyVote("agree", ("market_anchor_strict",))
    elif base.state == "agree" and "market_anchor_core" in (features["anchor_labels"] or []):
        anchor = FamilyVote("agree", ("market_anchor_core_with_base",))
    elif base.state == "pending":
        anchor = FamilyVote("pending", ("base_pending_for_anchor_core",))
    else:
        anchor = FamilyVote("disagree", ("market_anchor_not_matched",))
    raw_preclose = preclose_strong(features, market_evidence)
    if raw_preclose.state == "pending":
        preclose = raw_preclose
    elif base.state == "agree":
        preclose = raw_preclose
    elif base.state == "pending":
        preclose = FamilyVote("pending", ("base_pending_for_preclose",))
    else:
        preclose = FamilyVote("disagree", ("base_not_supported",))
    reentry = moderate_edge_quality_reentry(features)
    families = {"base": base, "anchor": anchor, "preclose": preclose, "reentry": reentry}
    drag = _drag(features)
    strict_anchor = anchor.state == "agree" and "market_anchor_strict" in anchor.reason_codes
    no_drag = None if drag is None or base.state == "pending" or anchor.state == "pending" else (base.state == "agree" or strict_anchor) and not drag
    family_count = sum(vote.state == "agree" for vote in families.values())
    pending = bool(eligibility) or any(vote.state == "pending" for vote in families.values()) or no_drag is None
    lane: Literal["consensus_core", "reentry_expansion"] | None = None
    if not pending and no_drag and family_count >= 2:
        lane = "consensus_core"
    elif not pending and reentry.state == "agree" and not no_drag:
        lane = "reentry_expansion"
    status: Literal["selected", "not_selected", "pending"] = "pending" if pending else "selected" if lane else "not_selected"
    reasons = tuple(dict.fromkeys((*eligibility, *(reason for vote in families.values() for reason in vote.reason_codes))))
    return AlternativePickEvaluation(not eligibility, eligibility, selector_fingerprint(), families, family_count, no_drag, lane, status, reasons, features)


def research_parity_anchors() -> dict[str, float]:
    return {"base": 32.603, "preclose": 5.982, "combined": 38.585}


def prospective_ledger_seed() -> dict[str, float | int]:
    return {"rows": 0, "pnl": 0.0}
