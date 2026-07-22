"""Pure, prospective-only contract for alternative pitcher-K pick comparison.

No network, database, artifact, runtime, or official-pick writes occur here.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
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

if MANIFEST.get("bundle_id") != BUNDLE_ID:
    raise ValueError("alternative selector manifest bundle_id does not match exported constant")
if MANIFEST.get("selector_ids", {}).get("consensus_core") != CONSENSUS_SELECTOR_ID:
    raise ValueError("alternative selector manifest consensus selector does not match exported constant")
if MANIFEST.get("selector_ids", {}).get("reentry_expansion") != EXPANSION_SELECTOR_ID:
    raise ValueError("alternative selector manifest expansion selector does not match exported constant")


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
    return sha256_hex(json.dumps(MANIFEST, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


FROZEN_SELECTOR_FINGERPRINT = "f8f7ccf652b8eda4860d07798bc4673920b0b9d727552bc7e2e6547d478b4579"


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _raw_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    value = _number(value)
    return int(value) if value is not None else None


def _text(value: Any) -> str:
    return str(value or "").strip()


def _enum(value: Any) -> str:
    return _text(value).lower()


def _threshold(name: str) -> float:
    return float(MANIFEST["thresholds"][name])


def _weight(name: str) -> int:
    return int(MANIFEST["preclose_score_weights"][name])


def _parse_time(value: Any) -> datetime | None:
    value = _text(value)
    if not value:
        return None
    try:
        return datetime.fromisoformat(f"{value[:-1]}+00:00" if value.endswith("Z") else value)
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


def adjusted_ev_resolution(row: dict[str, Any]) -> tuple[float | None, str | None]:
    """Preserve legacy float(...)-then-truthy-or precedence, including NaN."""
    for field in MANIFEST["field_precedence"]["adjusted_ev"]:
        candidate = _raw_number(row.get(field))
        if candidate:
            return (candidate, None) if math.isfinite(candidate) else (None, f"{field}:non_finite")
    return None, None


def adjusted_ev(row: dict[str, Any]) -> float | None:
    return adjusted_ev_resolution(row)[0]


def line_bucket(k_line: Any) -> str:
    value = _number(k_line)
    if value is None:
        return "unknown"
    if value <= 3.5:
        return "2.5-3.5"
    return {4.5: "4.5", 5.5: "5.5", 6.5: "6.5"}.get(value, "7.5+")


def timing_bucket(observed_at: Any, game_time: Any) -> str:
    observed, start = _as_utc(observed_at), _as_utc(game_time)
    if observed is None or start is None:
        return "unknown"
    minutes = (start - observed).total_seconds() / 60.0
    if minutes < 0:
        return "post_start"
    for max_minutes, label in ((5, "pre_5"), (15, "pre_15"), (30, "pre_30"), (60, "pre_60"), (120, "pre_120")):
        if minutes <= max_minutes:
            return label
    return "early"


def runtime_opportunity_bucket(avg_ip: Any, recent_start_count: Any) -> str:
    innings = _number(avg_ip)
    if innings is None:
        return "unknown"
    if innings < 4.5:
        return "short_leash"
    if innings >= 6.2 and (_integer(recent_start_count) or 0) >= 3:
        return "deep_starter"
    return "normal"


def runtime_leash_risk_bucket(*, is_opener: Any, starter_mismatch: Any, avg_ip: Any, last_pitch_count: Any, days_since_last_start: Any) -> str:
    if bool(is_opener) or bool(starter_mismatch) or runtime_opportunity_bucket(avg_ip, None) == "short_leash":
        return "high"
    if (_integer(last_pitch_count) or 0) >= 105 or (_integer(days_since_last_start) or 99) < 4:
        return "medium"
    return "normal"


def runtime_pitcher_archetype_bucket(*, is_opener: Any, starter_mismatch: Any, opportunity_bucket: str, season_k9: Any, recent_k9: Any, career_k9: Any) -> str:
    if bool(is_opener) or bool(starter_mismatch):
        return "opener_or_mismatch"
    if opportunity_bucket == "short_leash":
        return "short_leash"
    k9s = [value for value in (_number(season_k9), _number(recent_k9), _number(career_k9)) if value is not None]
    high, low = bool(k9s) and max(k9s) >= 10, bool(k9s) and max(k9s) < 7
    if opportunity_bucket == "deep_starter":
        return "high_k_deep_starter" if high else "deep_starter"
    if high:
        return "high_k_standard"
    return "low_k_standard" if low else "standard_starter"


def runtime_model_market_relationship(model_side: Any, market_favorite: Any) -> str:
    model, favorite = _enum(model_side), _enum(market_favorite)
    if model not in {"over", "under"} or favorite not in {"over", "under"}:
        return "unknown"
    return "model_agrees_with_favorite" if model == favorite else "model_fades_favorite"


def runtime_book_count(books_seen: Any) -> int:
    """Normalize the legacy book list/string representation without inference."""
    if isinstance(books_seen, (list, tuple, set)):
        return len(books_seen)
    if isinstance(books_seen, str) and books_seen.strip():
        return len([book for book in books_seen.split(",") if book.strip()])
    return 0


def derive_model_no_vig_gap(*, model_win_prob: Any, over_odds: Any, under_odds: Any, side: Any) -> float | None:
    probability, over, under = _number(model_win_prob), _integer(over_odds), _integer(under_odds)
    side = _enum(side)
    if probability is None or not 0 <= probability <= 1 or over in {None, 0} or under in {None, 0} or side not in {"over", "under"}:
        return None
    over_raw = abs(over) / (abs(over) + 100) if over < 0 else 100 / (over + 100)
    under_raw = abs(under) / (abs(under) + 100) if under < 0 else 100 / (under + 100)
    total = over_raw + under_raw
    if total <= 0:
        return None
    market_probability = (over_raw if side == "over" else under_raw) / total
    return probability - market_probability


def market_anchor_labels(row: dict[str, Any]) -> set[str]:
    raw = row.get("market_anchor_selector")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = None
    nested = raw.get("labels") if isinstance(raw, dict) else []
    flat = row.get("market_anchor_selector_labels") or []
    values = [nested] if isinstance(nested, str) else list(nested or [])
    values += [flat] if isinstance(flat, str) else list(flat or [])
    return {_enum(value) for value in values if _text(value)}


def _anchor_metadata(pick: dict[str, Any]) -> tuple[set[str] | None, bool]:
    raw = pick.get("market_anchor_selector")
    if raw is None:
        return set(), False
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return None, True
    if not isinstance(raw, dict) or not isinstance(raw.get("labels"), (list, tuple, set)):
        return None, True
    return {_enum(value) for value in raw["labels"] if _text(value)}, False


def derive_runtime_features(*, pitcher: dict[str, Any], pick: dict[str, Any], market_evidence: dict[str, Any], observed_at: Any) -> dict[str, Any]:
    side = _enum(pick.get("side"))
    over, under = _integer(pitcher.get("best_over_odds")), _integer(pitcher.get("best_under_odds"))
    odds = over if side == "over" else under if side == "under" else None
    favorite = "over" if over is not None and under is not None and over < under else "under" if over is not None and under is not None else "unknown"
    model_side = _enum(pick.get("model_side")) or side
    relationship = _enum(pick.get("model_market_relationship")) or runtime_model_market_relationship(model_side, favorite)
    opportunity = _enum(pitcher.get("opportunity_bucket")) or runtime_opportunity_bucket(pitcher.get("avg_ip"), pitcher.get("recent_start_count"))
    leash = _enum(pitcher.get("leash_risk_bucket")) or runtime_leash_risk_bucket(is_opener=pitcher.get("is_opener"), starter_mismatch=pitcher.get("starter_mismatch"), avg_ip=pitcher.get("avg_ip"), last_pitch_count=pitcher.get("last_pitch_count"), days_since_last_start=pitcher.get("days_since_last_start"))
    ev, ev_error = adjusted_ev_resolution(pick)
    edge = _number(pick.get("edge"))
    canonical_win_prob = pick.get("win_prob") if pick.get("win_prob") is not None else pick.get("model_win_prob")
    gap = derive_model_no_vig_gap(model_win_prob=canonical_win_prob, over_odds=over, under_odds=under, side=side)
    quality = _enum(pick.get("quality_gate_level"))
    skepticism = bool(pick.get("large_edge_skepticism_flag"))
    if not skepticism and edge is not None and edge >= _threshold("edge_high_skepticism_min"):
        skepticism = sum((relationship == "model_fades_favorite", leash in {"medium", "high"}, opportunity == "short_leash", quality not in {"", "clean", "none"})) >= 2
    labels, malformed = _anchor_metadata(pick)
    checkpoint = _as_utc(observed_at)
    return {
        "side": side, "official_verdict": display_verdict(pick), "source_fire_verdict": source_fire_verdict(pick),
        "pitcher": normalize(pitcher.get("pitcher") or ""), "game_time": _text(pitcher.get("game_time")),
        "k_line": _number(pitcher.get("k_line")), "line_bucket": line_bucket(pitcher.get("k_line")), "odds": odds,
        "official_book": _text(pitcher.get(f"best_{side}_book")) or None,
        "price_sign": "minus" if odds is not None and odds < 0 else "plus" if odds is not None and odds > 0 else "unknown",
        "bet_timing_window": timing_bucket(observed_at, pitcher.get("game_time")), "model_market_relationship": relationship,
        "model_no_vig_gap": gap, "edge": edge, "adjusted_ev": ev, "adjusted_ev_error": ev_error,
        "quality_gate_level": quality, "opportunity_bucket": opportunity, "leash_risk_bucket": leash,
        "pitcher_archetype_bucket": runtime_pitcher_archetype_bucket(is_opener=pitcher.get("is_opener"), starter_mismatch=pitcher.get("starter_mismatch"), opportunity_bucket=opportunity, season_k9=pitcher.get("season_k9"), recent_k9=pitcher.get("recent_k9"), career_k9=pitcher.get("career_k9")),
        "large_edge_skepticism_flag": skepticism, "anchor_labels": sorted(labels) if labels is not None else None,
        "anchor_metadata_malformed": malformed, "observed_at": checkpoint.isoformat() if checkpoint else None,
    }


def _features_missing(features: dict[str, Any], fields: tuple[str, ...]) -> bool:
    return any(features.get(field) in {None, "", "unknown"} for field in fields)


def strong_base_strict_plus_selective(features: dict[str, Any]) -> FamilyVote:
    required = ("official_verdict", "side", "adjusted_ev", "model_market_relationship", "line_bucket", "leash_risk_bucket", "pitcher_archetype_bucket", "model_no_vig_gap", "quality_gate_level", "bet_timing_window")
    if features.get("adjusted_ev_error") or _features_missing(features, required):
        return FamilyVote("pending", (features.get("adjusted_ev_error") or "base_inputs_missing",))
    fire, lean, ev = features["official_verdict"].upper().startswith("FIRE"), features["official_verdict"].upper() == "LEAN", features["adjusted_ev"]
    moderate_ev = _threshold("adjusted_ev_low_max_exclusive") <= ev < _threshold("adjusted_ev_moderate_max_exclusive")
    strict = fire and ((features["model_market_relationship"] == "model_agrees_with_favorite" and moderate_ev and features["bet_timing_window"] == "pre_30") or (features["side"] == "over" and moderate_ev and features["leash_risk_bucket"] == "normal"))
    selective = lean and ((features["line_bucket"] == "4.5" and 0 <= ev < _threshold("adjusted_ev_low_max_exclusive") and features["leash_risk_bucket"] == "normal") or (features["pitcher_archetype_bucket"] == "low_k_standard" and features["model_no_vig_gap"] >= _threshold("no_vig_base_min")) or (features["line_bucket"] == "2.5-3.5" and features["model_market_relationship"] == "model_fades_favorite" and features["quality_gate_level"] == "capped"))
    return FamilyVote("agree" if strict or selective else "disagree", ("strong_base_strict_runtime_core" if strict else "strong_base_selective_lean" if selective else "base_predicate_false",))


def _candidate_identity_vote(features: dict[str, Any], evidence: dict[str, Any], slate_date: str | None) -> FamilyVote | None:
    identity = evidence.get("candidate_identity")
    if not isinstance(identity, dict):
        return FamilyVote("pending", ("preclose_candidate_identity_missing",))
    expected = {"slate_date": slate_date or _text(identity.get("slate_date")), "game_time": features.get("game_time"), "pitcher": features.get("pitcher"), "side": features["side"], "k_line": features["k_line"], "provider": _enum(evidence.get("provider"))}
    if not all(expected.values()):
        return FamilyVote("pending", ("preclose_expected_identity_missing",))
    received = {"slate_date": _text(identity.get("slate_date")), "game_time": _text(identity.get("game_time")), "pitcher": normalize(identity.get("pitcher") or ""), "side": _enum(identity.get("side")), "k_line": _number(identity.get("k_line")), "provider": _enum(identity.get("provider"))}
    if received != expected:
        return FamilyVote("pending", ("preclose_candidate_identity_mismatch",))
    return None


def _preclose_observation_vote(features: dict[str, Any], evidence: dict[str, Any]) -> FamilyVote | None:
    since, checkpoint = _as_utc(evidence.get("candidate_became_current_at")), _as_utc(features.get("observed_at"))
    observations = evidence.get("observations")
    if since is None or checkpoint is None or not isinstance(observations, list):
        return FamilyVote("pending", ("preclose_candidate_window_missing",))
    parsed: list[tuple[str, datetime]] = []
    for observation in observations:
        if not isinstance(observation, dict) or not _text(observation.get("id")) or (at := _as_utc(observation.get("observed_at"))) is None:
            return FamilyVote("pending", ("preclose_observations_malformed",))
        parsed.append((_text(observation["id"]), at))
    ids = {item[0] for item in parsed}
    if len(parsed) < 2 or len(ids) < 2 or ids != {_text(value) for value in evidence.get("observation_ids", []) if _text(value)}:
        return FamilyVote("pending", ("preclose_observations_immature",))
    if any(at < since for _, at in parsed):
        return FamilyVote("pending", ("preclose_observation_before_current_candidate",))
    if any(at > checkpoint for _, at in parsed):
        return FamilyVote("pending", ("preclose_observation_after_checkpoint",))
    first, last = _as_utc(evidence.get("first_observed_at")), _as_utc(evidence.get("last_observed_at"))
    if first is None or last is None:
        return FamilyVote("pending", ("preclose_observation_times_missing",))
    times = [at for _, at in parsed]
    if first != min(times) or last != max(times):
        return FamilyVote("pending", ("preclose_observation_bounds_invalid",))
    return None


def preclose_proxy_score_from_row(row: dict[str, Any]) -> dict[str, Any]:
    """The historical diagnostic scorer; it intentionally has no post-close inputs."""
    score, positive, risks = 0, [], []
    def add(points: int, name: str, target: list[str]) -> None:
        nonlocal score
        score += points; target.append(name)
    edge, ev, gap = _number(row.get("edge")), adjusted_ev(row), _number(row.get("model_no_vig_gap"))
    toward, away = _integer(row.get("toward_pick_count")), _integer(row.get("away_from_pick_count"))
    movement = _enum(row.get("side_price_movement"))
    if movement == "with_side" or (toward is not None and away is not None and toward > away): add(_weight("movement_toward"), "movement_toward_pick", positive)
    if movement == "against_side" or (toward is not None and away is not None and away > toward): add(_weight("movement_away"), "movement_against_pick", risks)
    if edge is not None: add(_weight("edge_low") if edge < _threshold("edge_low_max_exclusive") else _weight("edge_moderate_low") if edge < _threshold("edge_moderate_low_max_exclusive") else _weight("edge_moderate") if edge < _threshold("edge_moderate_max_exclusive") else _weight("edge_high"), "low_edge_market_validation" if edge < _threshold("edge_low_max_exclusive") else "moderate_low_edge_market_validation" if edge < _threshold("edge_moderate_low_max_exclusive") else "moderate_edge_market_validation" if edge < _threshold("edge_moderate_max_exclusive") else "high_edge_clv_risk", positive if edge < _threshold("edge_moderate_max_exclusive") else risks)
    if ev is not None: add(_weight("ev_low") if ev < _threshold("adjusted_ev_low_max_exclusive") else _weight("ev_moderate") if ev < _threshold("adjusted_ev_moderate_max_exclusive") else _weight("ev_high"), "low_ev_market_validation" if ev < _threshold("adjusted_ev_low_max_exclusive") else "moderate_ev_market_validation" if ev < _threshold("adjusted_ev_moderate_max_exclusive") else "high_ev_clv_risk", positive if ev < _threshold("adjusted_ev_moderate_max_exclusive") else risks)
    if gap is not None and 0 < gap < _threshold("no_vig_reentry_min"): add(_weight("thin_no_vig"), "thin_or_price_only_no_vig_gap", positive)
    elif gap is not None and gap >= _threshold("no_vig_reentry_min"): add(_weight("high_no_vig"), "model_edge_not_clv_proxy", risks)
    price = _enum(row.get("price_sign")); quality = _enum(row.get("quality_gate_level")); timing = _enum(row.get("bet_timing_window"))
    if price == "minus": add(_weight("minus_price"), "minus_price_market_support", positive)
    elif price == "plus": add(_weight("plus_price"), "plus_price_clv_risk", risks)
    if quality in {"", "clean", "none"}: add(_weight("clean_quality"), "clean_quality", positive)
    elif quality in {"blocked", "severe"}: add(_weight("blocked_quality"), "blocked_quality", risks)
    if timing in {"pre_120", "pre_60", "pre_30"}: add(_weight("early_timing"), "early_lock_window", positive)
    elif timing in {"pre_5", "post_start"}: add(_weight("late_timing"), "late_timing", risks)
    books = _integer(row.get("book_count"))
    books = books if books is not None else runtime_book_count(row.get("books_seen"))
    if bool(row.get("broad_confirmation")) or books >= 3: add(_weight("multi_book"), "multi_book_support", positive)
    elif books == 1: add(_weight("single_book"), "single_book_support", risks)
    if bool(row.get("best_is_off_market")): add(_weight("off_market"), "off_market_best_book", risks)
    reversal, volatility = _integer(row.get("reversal_book_count")) or 0, _integer(row.get("volatile_book_count")) or 0
    if reversal > 0 or volatility > 1: add(_weight("volatile"), "reversal_or_volatility", risks)
    elif reversal == 0 and volatility == 0: add(_weight("low_volatility"), "low_volatility", positive)
    if _enum(row.get("side")) == "under" and _enum(row.get("model_market_relationship")) == "model_fades_favorite": add(_weight("under_market_fade"), "under_market_fade", risks)
    label = "strong_preclose_clv_proxy" if score >= _threshold("preclose_strong_score_min") else "medium_preclose_clv_proxy" if score >= _threshold("preclose_medium_score_min") else "weak_preclose_clv_proxy"
    return {"score": score, "label": label, "positive_reasons": positive, "risk_reasons": risks}


def preclose_strong(features: dict[str, Any], market_evidence: dict[str, Any], *, slate_date: str | None = None) -> FamilyVote:
    identity = _candidate_identity_vote(features, market_evidence, slate_date)
    if identity: return identity
    observations = _preclose_observation_vote(features, market_evidence)
    if observations: return observations
    if market_evidence.get("reversal_book_count") is None or market_evidence.get("volatile_book_count") is None: return FamilyVote("pending", ("preclose_volatility_missing",))
    if not isinstance(market_evidence.get("best_is_off_market"), bool): return FamilyVote("pending", ("preclose_best_off_market_missing",))
    if _enum(market_evidence.get("freshness_status")) != "fresh": return FamilyVote("pending", ("preclose_evidence_stale",))
    if _features_missing(features, ("edge", "adjusted_ev", "model_no_vig_gap", "price_sign", "quality_gate_level", "bet_timing_window")) or features.get("adjusted_ev_error"): return FamilyVote("pending", (features.get("adjusted_ev_error") or "preclose_runtime_inputs_missing",))
    row = {**market_evidence, **features}
    scored = preclose_proxy_score_from_row(row)
    return FamilyVote("agree" if scored["label"] == "strong_preclose_clv_proxy" else "disagree", (scored["label"],))


def moderate_edge_quality_reentry(features: dict[str, Any]) -> FamilyVote:
    required = ("source_fire_verdict", "side", "model_market_relationship", "quality_gate_level", "edge", "adjusted_ev", "model_no_vig_gap", "large_edge_skepticism_flag")
    if features.get("adjusted_ev_error") or _features_missing(features, required) or features.get("model_market_relationship") == "unknown": return FamilyVote("pending", (features.get("adjusted_ev_error") or "reentry_inputs_missing",))
    if not features["source_fire_verdict"].upper().startswith("FIRE"): return FamilyVote("disagree", ("source_not_fire",))
    agrees = _threshold("edge_low_max_exclusive") <= features["edge"] < _threshold("edge_moderate_max_exclusive") and features["adjusted_ev"] < _threshold("adjusted_ev_moderate_max_exclusive") and features["model_no_vig_gap"] >= _threshold("no_vig_reentry_min") and features["quality_gate_level"] in {"", "clean", "none"} and not features["large_edge_skepticism_flag"]
    return FamilyVote("agree" if agrees else "disagree", ("moderate_edge_quality_reentry" if agrees else "reentry_predicate_false",))


def reentry_candidate_labels(row: dict[str, Any]) -> set[str]:
    source, side, relationship = source_fire_verdict(row), _enum(row.get("side")), _enum(row.get("model_market_relationship"))
    if not source.upper().startswith("FIRE"): return set()
    labels: set[str] = set(); edge, ev, gap = _number(row.get("edge")), adjusted_ev(row), _number(row.get("model_no_vig_gap")); quality = _enum(row.get("quality_gate_level")); workload = _enum(row.get("leash_risk_bucket") or row.get("opportunity_bucket"))
    if source == "FIRE 2u": source = "FIRE 1u"
    proposed_fire = source.upper().startswith("FIRE") and side != "under" and relationship != "model_fades_favorite"
    if proposed_fire: labels.add("retained_fire_control")
    if relationship == "model_agrees_with_favorite" and gap is not None and gap >= _threshold("no_vig_reentry_min"): labels.add("market_aligned_reentry")
    if edge is not None and _threshold("edge_low_max_exclusive") <= edge < _threshold("edge_moderate_max_exclusive") and ev is not None and ev < _threshold("adjusted_ev_moderate_max_exclusive") and gap is not None and gap >= _threshold("no_vig_reentry_min") and quality in {"", "clean", "none"} and not bool(row.get("large_edge_skepticism_flag")): labels.add("moderate_edge_quality_reentry")
    if side == "under" and (gap is None or gap < _threshold("no_vig_base_min") or relationship == "model_fades_favorite" or workload in {"high", "medium", "short_leash"}): labels.add("avoid_fire_under_reentry")
    return labels


def no_drag_predicate(features: dict[str, Any], base: FamilyVote, anchor: FamilyVote) -> bool | None:
    if base.state == "pending" or anchor.state == "pending" or _features_missing(features, ("edge", "model_market_relationship", "official_verdict", "side")): return None
    drag = features["edge"] >= _threshold("edge_high_skepticism_min") or features["model_market_relationship"] == "model_fades_favorite" or (features["official_verdict"].upper().startswith("FIRE") and features["side"] == "under" and features["model_market_relationship"] == "model_fades_favorite")
    strict_anchor = anchor.state == "agree" and "market_anchor_strict" in anchor.reason_codes
    return (base.state == "agree" or strict_anchor) and not drag


def no_drag_diagnostic_predicate(row: dict[str, Any]) -> dict[str, Any]:
    """Source-compatible historical no-drag predicate used by the audit only."""
    selected = display_verdict(row); side = _enum(row.get("side")); relationship = _enum(row.get("model_market_relationship")); edge = _number(row.get("edge")); ev = adjusted_ev(row)
    line = _text(row.get("line_bucket")); leash = _enum(row.get("leash_risk_bucket") or row.get("opportunity_bucket")); quality = _enum(row.get("quality_gate_level")); timing = _text(row.get("bet_timing_window")); archetype = _text(row.get("pitcher_archetype_bucket")); gap = _number(row.get("model_no_vig_gap"))
    drags: list[str] = []
    if edge is not None and edge >= _threshold("edge_high_skepticism_min"): drags.append("cap_high_raw_edge")
    if relationship == "model_fades_favorite": drags.append("cap_market_fade")
    if selected.startswith("FIRE") and side == "under" and relationship == "model_fades_favorite": drags.append("cap_fire_under_market_fade")
    moderate_ev = ev is not None and _threshold("adjusted_ev_low_max_exclusive") <= ev < _threshold("adjusted_ev_moderate_max_exclusive")
    families: list[str] = []
    keep_fire = selected.startswith("FIRE") and ((relationship == "model_agrees_with_favorite" and moderate_ev and timing == "pre_30") or (side == "over" and moderate_ev and leash == "normal"))
    if keep_fire and not drags: families.append("strong_base_strict_runtime_core")
    selective = selected == "LEAN" and ((line == "4.5" and ev is not None and 0 <= ev < _threshold("adjusted_ev_low_max_exclusive") and leash == "normal") or (archetype == "low_k_standard" and gap is not None and gap >= _threshold("no_vig_base_min")) or (line == "2.5-3.5" and relationship == "model_fades_favorite" and quality == "capped"))
    if selective and not {"cap_high_raw_edge", "cap_fire_under_market_fade"}.intersection(drags): families.append("strong_base_selective_lean")
    if "market_anchor_strict" in market_anchor_labels(row): families.append("market_anchor_strict")
    return {"qualifies": bool(families) and not drags, "families": tuple(families), "drag_labels": tuple(drags)}


def _eligible_reasons(*, pitcher: dict[str, Any], pick: dict[str, Any], market_evidence: dict[str, Any], slate_date: str, is_tracked: bool, source_artifact_path: str, source_payload_sha256: str, source_artifact_byte_sha256: str, observed_at: str) -> tuple[str, ...]:
    reasons: list[str] = []; observed, start = _as_utc(observed_at), _as_utc(pitcher.get("game_time")); expected_slate = observed.astimezone(PHOENIX).date().isoformat() if observed else ""
    if _text(slate_date) != expected_slate: reasons.append("wrong_phoenix_slate_date")
    tracked = _enum(is_tracked) in {"true", "1", "yes"} if isinstance(is_tracked, str) else bool(is_tracked)
    if not tracked: reasons.append("untracked_pick")
    if display_verdict(pick).upper() == "PASS": reasons.append("pass_verdict")
    if observed is None or start is None or observed >= start: reasons.append("game_started")
    if source_artifact_path not in MANIFEST["artifact_provenance"]["allowed_current_paths"]: reasons.append("artifact_path_not_current")
    pattern = MANIFEST["artifact_provenance"]["sha256_pattern"]
    if not isinstance(source_payload_sha256, str) or re.fullmatch(pattern, source_payload_sha256) is None: reasons.append("artifact_payload_sha256_invalid")
    if not isinstance(source_artifact_byte_sha256, str) or re.fullmatch(pattern, source_artifact_byte_sha256) is None: reasons.append("artifact_byte_sha256_invalid")
    if _enum(market_evidence.get("provider")) not in set(MANIFEST["provider_allow_list"]): reasons.append("unsupported_provider")
    identity = (pitcher.get("pitcher"), pitcher.get("team"), pitcher.get("opp_team"), pitcher.get("game_time"), pitcher.get("k_line"), pick.get("side"))
    if not all(_text(value) for value in identity) or _number(pitcher.get("k_line")) is None or _enum(pick.get("side")) not in {"over", "under"}: reasons.append("candidate_identity_incomplete")
    if _number(pick.get("official_k_line")) is not None and _number(pick.get("official_k_line")) != _number(pitcher.get("k_line")): reasons.append("line_mismatch")
    for field, value in (("source_artifact_path", source_artifact_path), ("source_payload_sha256", source_payload_sha256), ("source_artifact_byte_sha256", source_artifact_byte_sha256)):
        if pick.get(field) is not None and pick.get(field) != value: reasons.append("artifact_hash_mismatch")
    return tuple(dict.fromkeys(reasons))


def evaluate_alternative_pick(*, pitcher: dict[str, Any], pick: dict[str, Any], market_evidence: dict[str, Any], slate_date: str, is_tracked: bool, source_artifact_path: str, source_payload_sha256: str, source_artifact_byte_sha256: str, observed_at: str) -> AlternativePickEvaluation:
    features = derive_runtime_features(pitcher=pitcher, pick=pick, market_evidence=market_evidence, observed_at=observed_at)
    eligible_reasons = _eligible_reasons(pitcher=pitcher, pick=pick, market_evidence=market_evidence, slate_date=slate_date, is_tracked=is_tracked, source_artifact_path=source_artifact_path, source_payload_sha256=source_payload_sha256, source_artifact_byte_sha256=source_artifact_byte_sha256, observed_at=observed_at)
    base = strong_base_strict_plus_selective(features)
    labels = features["anchor_labels"]
    if features["anchor_metadata_malformed"]: anchor = FamilyVote("pending", ("anchor_metadata_malformed",))
    elif "market_anchor_strict" in (labels or []): anchor = FamilyVote("agree", ("market_anchor_strict",))
    elif base.state == "agree" and "market_anchor_core" in (labels or []): anchor = FamilyVote("agree", ("market_anchor_core_with_base",))
    elif base.state == "pending": anchor = FamilyVote("pending", ("base_pending_for_anchor_core",))
    else: anchor = FamilyVote("disagree", ("market_anchor_not_matched",))
    raw_preclose = preclose_strong(features, market_evidence, slate_date=slate_date)
    preclose = raw_preclose if raw_preclose.state == "pending" or base.state == "agree" else FamilyVote("pending", ("base_pending_for_preclose",)) if base.state == "pending" else FamilyVote("disagree", ("base_not_supported",))
    reentry = moderate_edge_quality_reentry(features); families = {"base": base, "anchor": anchor, "preclose": preclose, "reentry": reentry}
    no_drag = no_drag_predicate(features, base, anchor); count = sum(vote.state == "agree" for vote in families.values())
    pending = bool(eligible_reasons) or any(vote.state == "pending" for vote in families.values()) or no_drag is None
    lane = "consensus_core" if not pending and no_drag and count >= 2 else "reentry_expansion" if not pending and reentry.state == "agree" and not no_drag else None
    status: Literal["selected", "not_selected", "pending"] = "pending" if pending else "selected" if lane else "not_selected"
    reasons = tuple(dict.fromkeys((*eligible_reasons, *(reason for vote in families.values() for reason in vote.reason_codes))))
    return AlternativePickEvaluation(not eligible_reasons, eligible_reasons, selector_fingerprint(), families, count, no_drag, lane, status, reasons, features)


def prospective_ledger_seed() -> dict[str, float | int]:
    return {"rows": 0, "pnl": 0.0}
