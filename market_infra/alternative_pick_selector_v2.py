"""Dependency-aware, prospective-only V2 alternative-pick selector.

V2 is a comparison-sidecar contract.  It deliberately evaluates only its
explicit inputs and never reads broad market-pick evidence or postgame fields.
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

from market_infra import alternative_pick_selector as v1
from pipeline.name_utils import normalize


BUNDLE_ID = "pregame_alternative_pick_methodology_v2"
CONSENSUS_SELECTOR_ID = "no_drag_distinct_family_consensus_core_v2"
EXPANSION_SELECTOR_ID = "moderate_edge_quality_reentry_expansion_v2"
MANIFEST_PATH = Path(__file__).with_name("alternative_pick_selector_manifest_v2.json")
MANIFEST = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
FROZEN_SELECTOR_FINGERPRINT = "23bacff0fa923685ae52c5a9cfbadfb9f5902fb64d91759cfe9b4b1169a221c4"
TriBool = bool | None
FAMILY_ORDER = ("base", "anchor", "preclose", "reentry")
PHOENIX = ZoneInfo("America/Phoenix")


if MANIFEST.get("bundle_id") != BUNDLE_ID:
    raise ValueError("alternative selector V2 manifest bundle_id does not match exported constant")
if MANIFEST.get("selector_ids", {}).get("consensus_core") != CONSENSUS_SELECTOR_ID:
    raise ValueError("alternative selector V2 manifest consensus selector does not match exported constant")
if MANIFEST.get("selector_ids", {}).get("reentry_expansion") != EXPANSION_SELECTOR_ID:
    raise ValueError("alternative selector V2 manifest expansion selector does not match exported constant")


@dataclass(frozen=True)
class PredicateVote:
    state: Literal["true", "false", "pending"]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class FamilyVote:
    state: Literal["agree", "disagree", "pending"]
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class LaneEvaluation:
    consensus_core: PredicateVote
    reentry_expansion: PredicateVote
    lane: Literal["consensus_core", "reentry_expansion"] | None
    selection_status: Literal["selected", "not_selected", "pending"]
    family_count: int
    maximum_family_count: int
    decisive_families: tuple[str, ...]


@dataclass(frozen=True)
class PrimitivePresence:
    values: dict[str, Any]
    missing: tuple[str, ...]
    malformed: tuple[str, ...]


@dataclass(frozen=True)
class AlternativePickEvaluationV2:
    eligible: bool
    eligibility_reason_codes: tuple[str, ...]
    selector_fingerprint: str
    family_states: dict[str, FamilyVote]
    no_drag: TriBool
    lane: Literal["consensus_core", "reentry_expansion"] | None
    selection_status: Literal["selected", "not_selected", "pending"]
    family_count: int
    maximum_family_count: int
    decisive_families: tuple[str, ...]
    reason_codes: tuple[str, ...]
    normalized_inputs: dict[str, Any]
    primitive_presence: PrimitivePresence


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def selector_fingerprint() -> str:
    return sha256_hex(json.dumps(MANIFEST, sort_keys=True, separators=(",", ":"), ensure_ascii=False))


if selector_fingerprint() != FROZEN_SELECTOR_FINGERPRINT:
    raise ValueError("alternative selector V2 manifest fingerprint does not match frozen contract")


def tri_and(*values: TriBool) -> TriBool:
    return False if any(value is False for value in values) else None if any(value is None for value in values) else True


def tri_or(*values: TriBool) -> TriBool:
    return True if any(value is True for value in values) else None if any(value is None for value in values) else False


def tri_not(value: TriBool) -> TriBool:
    return None if value is None else not value


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _enum(value: Any) -> str:
    return _text(value).lower()


def _as_utc(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(f"{text[:-1]}+00:00" if text.endswith("Z") else text)
    except ValueError:
        return None
    return parsed.astimezone(ZoneInfo("UTC")) if parsed.tzinfo else parsed.replace(tzinfo=ZoneInfo("UTC"))


def _display_verdict(pick: dict[str, Any]) -> str:
    for field in MANIFEST["field_precedence"]["display_verdict"]:
        value = _text(pick.get(field))
        if value:
            return value
    return ""


def _finite_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _first_present(row: dict[str, Any], fields: list[str]) -> Any:
    for field in fields:
        if field in row:
            return row[field]
    return None


def validate_runtime_primitives_v2(*, pitcher: dict[str, Any], pick: dict[str, Any], exact_evidence: Any) -> PrimitivePresence:
    """Record raw presence without treating false, zero, or empty lists as absent."""
    values: dict[str, Any] = {}
    missing: list[str] = []
    malformed: list[str] = []

    def scalar(name: str, value: Any, *, kind: str = "text", allow_empty: bool = False) -> None:
        values[name] = value
        if value is None:
            missing.append(name)
        elif kind == "text" and (not isinstance(value, str) or (not allow_empty and not value.strip())):
            malformed.append(name)
        elif kind == "number" and _finite_number(value) is None:
            malformed.append(name)
        elif kind == "bool" and not isinstance(value, bool):
            malformed.append(name)

    scalar("side", pick.get("side"))
    scalar("edge", pick.get("edge"), kind="number")
    scalar("k_line", pitcher.get("k_line"), kind="number")
    scalar("game_time", pitcher.get("game_time"))
    scalar("quality_gate_level", pick.get("quality_gate_level"), allow_empty=True)
    scalar("model_win_prob", pick.get("win_prob") if pick.get("win_prob") is not None else pick.get("model_win_prob"), kind="number")
    for name in ("best_over_odds", "best_under_odds", "avg_ip", "recent_start_count", "season_k9", "recent_k9", "career_k9"):
        scalar(name, pitcher.get(name), kind="number")

    verdict = _first_present(pick, MANIFEST["field_precedence"]["display_verdict"])
    source_verdict = _first_present(pick, MANIFEST["field_precedence"]["source_fire_verdict"])
    adjusted = _first_present(pick, MANIFEST["field_precedence"]["adjusted_ev"])
    scalar("display_verdict", verdict)
    scalar("source_fire_verdict", source_verdict)
    scalar("adjusted_ev", adjusted, kind="number")

    relationship = pick.get("model_market_relationship")
    values["model_market_relationship"] = relationship
    if relationship is not None:
        if _enum(relationship) not in {"model_agrees_with_favorite", "model_fades_favorite", "model_neutral"}:
            malformed.append("model_market_relationship")
    elif _finite_number(pitcher.get("best_over_odds")) is None or _finite_number(pitcher.get("best_under_odds")) is None or not _enum(pick.get("model_side") or pick.get("side")):
        missing.append("model_market_relationship")
    else:
        values["model_market_relationship"] = "derived"

    skepticism = pick.get("large_edge_skepticism_flag")
    values["large_edge_skepticism_flag"] = skepticism
    if skepticism is not None and not isinstance(skepticism, bool):
        malformed.append("large_edge_skepticism_flag")
    elif skepticism is None:
        values["large_edge_skepticism_flag"] = "derived"

    labels = pick.get("market_anchor_selector")
    values["anchor_metadata"] = labels
    if labels is None:
        missing.append("anchor_metadata")
    elif isinstance(labels, str):
        try:
            labels = json.loads(labels)
        except json.JSONDecodeError:
            malformed.append("anchor_metadata")
    if labels is not None and not isinstance(labels, dict):
        malformed.append("anchor_metadata")
    elif isinstance(labels, dict) and not isinstance(labels.get("labels"), (list, tuple, set)):
        malformed.append("anchor_metadata")

    values["exact_evidence"] = exact_evidence
    if exact_evidence is None:
        missing.append("exact_evidence")
    elif not isinstance(exact_evidence, dict):
        malformed.append("exact_evidence")
    else:
        for name in ("provider", "candidate_identity", "candidate_became_current_at", "first_observed_at", "last_observed_at", "freshness_status", "observation_ids", "observations", "toward_pick_count", "away_from_pick_count", "book_count", "reversal_book_count", "volatile_book_count", "best_is_off_market"):
            value = exact_evidence.get(name)
            values[name] = value
            if value is None:
                missing.append(name)
        for name in ("toward_pick_count", "away_from_pick_count", "book_count", "reversal_book_count", "volatile_book_count"):
            if name in values and values[name] is not None and _finite_number(values[name]) is None:
                malformed.append(name)
        if "best_is_off_market" in values and values["best_is_off_market"] is not None and not isinstance(values["best_is_off_market"], bool):
            malformed.append("best_is_off_market")
        if "observations" in values and values["observations"] is not None and not isinstance(values["observations"], list):
            malformed.append("observations")
        if "observation_ids" in values and values["observation_ids"] is not None and not isinstance(values["observation_ids"], list):
            malformed.append("observation_ids")
    return PrimitivePresence(values, tuple(dict.fromkeys(missing)), tuple(dict.fromkeys(malformed)))


def parse_anchor_primitives_v2(pick: dict[str, Any]) -> tuple[FamilyVote, FamilyVote]:
    raw = pick.get("market_anchor_selector")
    if raw is None:
        pending = FamilyVote("pending", ("anchor_metadata_absent",))
        return pending, pending
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = None
    if not isinstance(raw, dict) or not isinstance(raw.get("labels"), (list, tuple, set)):
        pending = FamilyVote("pending", ("anchor_metadata_malformed",))
        return pending, pending
    labels = {_enum(value) for value in raw["labels"] if _text(value)}
    strict = FamilyVote("agree" if "market_anchor_strict" in labels else "disagree", ("market_anchor_strict" if "market_anchor_strict" in labels else "market_anchor_strict_absent",))
    core = FamilyVote("agree" if "market_anchor_core" in labels else "disagree", ("market_anchor_core" if "market_anchor_core" in labels else "market_anchor_core_absent",))
    return strict, core


def _family_to_tri(vote: FamilyVote) -> TriBool:
    return True if vote.state == "agree" else False if vote.state == "disagree" else None


def _tri_to_family(value: TriBool, *, true_reason: str, false_reason: str, pending_reason: str) -> FamilyVote:
    return FamilyVote("agree", (true_reason,)) if value is True else FamilyVote("disagree", (false_reason,)) if value is False else FamilyVote("pending", (pending_reason,))


def _v2_family(vote: v1.FamilyVote) -> FamilyVote:
    return FamilyVote(vote.state, vote.reason_codes)


def compose_anchor_v2(base: FamilyVote, strict: FamilyVote, core: FamilyVote) -> FamilyVote:
    return _tri_to_family(tri_or(_family_to_tri(strict), tri_and(_family_to_tri(base), _family_to_tri(core))), true_reason="market_anchor_v2_confirmed", false_reason="market_anchor_not_matched", pending_reason="anchor_dependency_pending")


def compose_preclose_v2(base: FamilyVote, raw_preclose: FamilyVote) -> FamilyVote:
    value = tri_and(_family_to_tri(base), _family_to_tri(raw_preclose))
    if value is None:
        return FamilyVote("pending", raw_preclose.reason_codes if raw_preclose.state == "pending" else base.reason_codes)
    return _tri_to_family(value, true_reason="preclose_v2_confirmed", false_reason="preclose_not_supported", pending_reason="preclose_dependency_pending")


def drag_core_v2(features: dict[str, Any]) -> PredicateVote:
    edge = _finite_number(features.get("edge"))
    high_edge: TriBool = None if edge is None else edge >= float(MANIFEST["thresholds"]["edge_high_skepticism_min"])
    relationship = _enum(features.get("model_market_relationship"))
    fade: TriBool = True if relationship == "model_fades_favorite" else False if relationship in {"model_agrees_with_favorite", "model_neutral"} else None
    verdict, side = _text(features.get("source_fire_verdict") or features.get("official_verdict")), _enum(features.get("side"))
    fire_under_fade = tri_and(None if not verdict else verdict.upper().startswith("FIRE"), None if side not in {"over", "under"} else side == "under", fade)
    value = tri_or(high_edge, fade, fire_under_fade)
    return PredicateVote("true" if value is True else "false" if value is False else "pending", ("drag_core_true" if value is True else "drag_core_false" if value is False else "drag_core_pending",))


def no_drag_v2(base: FamilyVote, strict_anchor: FamilyVote, drag_core: PredicateVote) -> PredicateVote:
    support = tri_or(_family_to_tri(base), _family_to_tri(strict_anchor))
    drag_value: TriBool = True if drag_core.state == "true" else False if drag_core.state == "false" else None
    value = tri_and(support, tri_not(drag_value))
    return PredicateVote("true" if value is True else "false" if value is False else "pending", ("no_drag_confirmed" if value is True else "no_drag_rejected" if value is False else "no_drag_pending",))


def evaluate_lanes_v2(families: dict[str, FamilyVote], no_drag: PredicateVote) -> LaneEvaluation:
    agree_count = sum(vote.state == "agree" for vote in families.values())
    maximum_count = agree_count + sum(vote.state == "pending" for vote in families.values())
    count_gate: TriBool = True if agree_count >= 2 else False if maximum_count < 2 else None
    no_drag_value: TriBool = True if no_drag.state == "true" else False if no_drag.state == "false" else None
    consensus_value = tri_and(no_drag_value, count_gate)
    reentry_value = _family_to_tri(families["reentry"])
    expansion_value = tri_and(reentry_value, tri_not(no_drag_value))
    consensus = PredicateVote("true" if consensus_value is True else "false" if consensus_value is False else "pending", ("consensus_core_selected" if consensus_value is True else "consensus_core_not_selected" if consensus_value is False else "consensus_core_pending",))
    expansion = PredicateVote("true" if expansion_value is True else "false" if expansion_value is False else "pending", ("reentry_expansion_selected" if expansion_value is True else "reentry_expansion_not_selected" if expansion_value is False else "reentry_expansion_pending",))
    lane = "consensus_core" if consensus_value is True else "reentry_expansion" if expansion_value is True else None
    status: Literal["selected", "not_selected", "pending"] = "selected" if lane else "not_selected" if consensus_value is False and expansion_value is False else "pending"
    decisive = tuple(name for name in FAMILY_ORDER if families[name].state == "agree")
    return LaneEvaluation(consensus, expansion, lane, status, agree_count, maximum_count, decisive)


def _has(presence: PrimitivePresence, names: set[str]) -> bool:
    blocked = set(presence.missing) | set(presence.malformed)
    return not names.intersection(blocked)


def _features_if_complete(presence: PrimitivePresence, required: set[str], *, pitcher: dict[str, Any], pick: dict[str, Any], exact_evidence: dict[str, Any], observed_at: Any) -> dict[str, Any] | None:
    if not _has(presence, required):
        return None
    canonical_pick = dict(pick)
    for field in MANIFEST["field_precedence"]["adjusted_ev"]:
        canonical_pick.pop(field, None)
    canonical_pick["adj_ev"] = presence.values["adjusted_ev"]
    features = v1.derive_runtime_features(pitcher=pitcher, pick=canonical_pick, market_evidence=exact_evidence, observed_at=observed_at)
    features["adjusted_ev"] = presence.values["adjusted_ev"]
    features["adjusted_ev_error"] = None
    return features


def preclose_proxy_score_v2(row: dict[str, Any], *, canonical_adjusted_ev: Any) -> dict[str, Any]:
    """Adapt the approved V1 scorer without reviving its truthy EV fallback."""
    adjusted_ev = _finite_number(canonical_adjusted_ev)
    if adjusted_ev is None:
        raise ValueError("canonical V2 adjusted EV must be finite")
    scorer_row = dict(row)
    for field in MANIFEST["field_precedence"]["adjusted_ev"]:
        scorer_row.pop(field, None)
    scored = v1.preclose_proxy_score_from_row(scorer_row)
    low_cut = float(MANIFEST["thresholds"]["adjusted_ev_low_max_exclusive"])
    moderate_cut = float(MANIFEST["thresholds"]["adjusted_ev_moderate_max_exclusive"])
    if adjusted_ev < low_cut:
        points, reason, target = int(MANIFEST["preclose_score_weights"]["ev_low"]), "low_ev_market_validation", "positive_reasons"
    elif adjusted_ev < moderate_cut:
        points, reason, target = int(MANIFEST["preclose_score_weights"]["ev_moderate"]), "moderate_ev_market_validation", "positive_reasons"
    else:
        points, reason, target = int(MANIFEST["preclose_score_weights"]["ev_high"]), "high_ev_clv_risk", "risk_reasons"
    scored["score"] += points
    scored[target].append(reason)
    scored["label"] = "strong_preclose_clv_proxy" if scored["score"] >= int(MANIFEST["thresholds"]["preclose_strong_score_min"]) else "medium_preclose_clv_proxy" if scored["score"] >= int(MANIFEST["thresholds"]["preclose_medium_score_min"]) else "weak_preclose_clv_proxy"
    return scored


def _raw_preclose_v2(features: dict[str, Any] | None, exact_evidence: Any, *, slate_date: str) -> FamilyVote:
    if features is None or not isinstance(exact_evidence, dict):
        return FamilyVote("pending", ("preclose_runtime_inputs_missing",))
    evidence = exact_evidence
    if _enum(evidence.get("provider")) not in set(MANIFEST["provider_allow_list"]):
        return FamilyVote("pending", ("preclose_provider_unsupported",))
    identity = evidence.get("candidate_identity")
    if not isinstance(identity, dict):
        return FamilyVote("pending", ("preclose_candidate_identity_missing",))
    expected = {"slate_date": slate_date, "game_time": features["game_time"], "pitcher": features["pitcher"], "side": features["side"], "k_line": features["k_line"], "provider": _enum(evidence.get("provider"))}
    received = {"slate_date": _text(identity.get("slate_date")), "game_time": _text(identity.get("game_time")), "pitcher": normalize(identity.get("pitcher") or ""), "side": _enum(identity.get("side")), "k_line": _finite_number(identity.get("k_line")), "provider": _enum(identity.get("provider"))}
    if not all(expected.values()) or received != expected:
        return FamilyVote("pending", ("preclose_candidate_identity_mismatch",))
    observations = evidence.get("observations")
    ids = evidence.get("observation_ids")
    since, checkpoint = _as_utc(evidence.get("candidate_became_current_at")), _as_utc(features.get("observed_at"))
    if since is None or checkpoint is None or not isinstance(observations, list) or not isinstance(ids, list):
        return FamilyVote("pending", ("preclose_candidate_window_missing",))
    parsed: list[tuple[str, Any]] = []
    for observation in observations:
        at = _as_utc(observation.get("observed_at")) if isinstance(observation, dict) else None
        if not isinstance(observation, dict) or not _text(observation.get("id")) or at is None:
            return FamilyVote("pending", ("preclose_observations_malformed",))
        parsed.append((_text(observation["id"]), at))
    observed_ids = {identifier for identifier, _ in parsed}
    if len(observed_ids) < 2 or observed_ids != {_text(value) for value in ids if _text(value)} or len({at for _, at in parsed}) < 2:
        return FamilyVote("pending", ("preclose_observations_immature",))
    if any(at < since or at > checkpoint for _, at in parsed):
        return FamilyVote("pending", ("preclose_observation_outside_candidate_window",))
    first, last = _as_utc(evidence.get("first_observed_at")), _as_utc(evidence.get("last_observed_at"))
    if first is None or last is None:
        return FamilyVote("pending", ("preclose_observation_times_missing",))
    if first != min(at for _, at in parsed) or last != max(at for _, at in parsed):
        return FamilyVote("pending", ("preclose_observation_bounds_invalid",))
    if _enum(evidence.get("freshness_status")) != "fresh":
        return FamilyVote("pending", ("preclose_evidence_stale",))
    if not isinstance(evidence.get("best_is_off_market"), bool):
        return FamilyVote("pending", ("preclose_best_off_market_missing",))
    if any(_finite_number(evidence.get(field)) is None for field in ("toward_pick_count", "away_from_pick_count", "book_count", "reversal_book_count", "volatile_book_count")):
        return FamilyVote("pending", ("preclose_evidence_malformed",))
    scored = preclose_proxy_score_v2({**evidence, **features}, canonical_adjusted_ev=features["adjusted_ev"])
    return FamilyVote("agree" if scored["label"] == "strong_preclose_clv_proxy" else "disagree", (scored["label"],))


def _eligible_reasons_v2(*, pitcher: dict[str, Any], pick: dict[str, Any], slate_date: str, is_tracked: bool, source_artifact_path: str, source_payload_sha256: str, source_artifact_byte_sha256: str, observed_at: str) -> tuple[str, ...]:
    reasons: list[str] = []
    observed, start = _as_utc(observed_at), _as_utc(pitcher.get("game_time"))
    if observed is None or start is None or observed >= start:
        reasons.append("game_started")
    elif slate_date != observed.astimezone(PHOENIX).date().isoformat():
        reasons.append("wrong_phoenix_slate_date")
    if is_tracked is not True:
        reasons.append("untracked_pick")
    if _enum(_display_verdict(pick)) == "pass":
        reasons.append("pass_verdict")
    if source_artifact_path not in MANIFEST["artifact_provenance"]["allowed_current_paths"]:
        reasons.append("artifact_path_not_current")
    pattern = MANIFEST["artifact_provenance"]["sha256_pattern"]
    if not isinstance(source_payload_sha256, str) or re.fullmatch(pattern, source_payload_sha256) is None:
        reasons.append("artifact_payload_sha256_invalid")
    if not isinstance(source_artifact_byte_sha256, str) or re.fullmatch(pattern, source_artifact_byte_sha256) is None:
        reasons.append("artifact_byte_sha256_invalid")
    identity = (pitcher.get("pitcher"), pitcher.get("team"), pitcher.get("opp_team"), pitcher.get("game_time"), pick.get("side"))
    if not all(_text(value) for value in identity) or _finite_number(pitcher.get("k_line")) is None or _enum(pick.get("side")) not in {"over", "under"}:
        reasons.append("candidate_identity_incomplete")
    official_line = pick.get("official_k_line")
    if official_line is not None and _finite_number(official_line) != _finite_number(pitcher.get("k_line")):
        reasons.append("line_mismatch")
    for field, value in (("source_artifact_path", source_artifact_path), ("source_payload_sha256", source_payload_sha256), ("source_artifact_byte_sha256", source_artifact_byte_sha256)):
        if pick.get(field) is not None and pick.get(field) != value:
            reasons.append("artifact_hash_mismatch")
    return tuple(dict.fromkeys(reasons))


def evaluate_alternative_pick_v2(*, pitcher: dict[str, Any], pick: dict[str, Any], exact_evidence: Any, slate_date: str, is_tracked: bool, source_artifact_path: str, source_payload_sha256: str, source_artifact_byte_sha256: str, observed_at: str) -> AlternativePickEvaluationV2:
    presence = validate_runtime_primitives_v2(pitcher=pitcher, pick=pick, exact_evidence=exact_evidence)
    evidence = exact_evidence if isinstance(exact_evidence, dict) else {}
    common = {"side", "edge", "k_line", "game_time", "quality_gate_level", "model_win_prob", "best_over_odds", "best_under_odds", "avg_ip", "recent_start_count", "season_k9", "recent_k9", "career_k9", "display_verdict", "source_fire_verdict", "adjusted_ev", "model_market_relationship", "large_edge_skepticism_flag"}
    features = _features_if_complete(presence, common, pitcher=pitcher, pick=pick, exact_evidence=evidence, observed_at=observed_at)
    if features is not None and (
        "anchor_metadata" in presence.missing or "anchor_metadata" in presence.malformed
    ):
        features = {
            **features,
            "anchor_labels": None,
            "anchor_metadata_malformed": "anchor_metadata" in presence.malformed,
        }
    base = _v2_family(v1.strong_base_strict_plus_selective(features)) if features is not None else FamilyVote("pending", ("base_runtime_primitives_missing",))
    strict, core = parse_anchor_primitives_v2(pick)
    anchor = compose_anchor_v2(base, strict, core)
    raw_preclose = _raw_preclose_v2(features, exact_evidence, slate_date=slate_date)
    preclose = compose_preclose_v2(base, raw_preclose)
    reentry = _v2_family(v1.moderate_edge_quality_reentry(features)) if features is not None else FamilyVote("pending", ("reentry_runtime_primitives_missing",))
    drag_features = features if features is not None else {"edge": pick.get("edge"), "model_market_relationship": pick.get("model_market_relationship"), "source_fire_verdict": _first_present(pick, MANIFEST["field_precedence"]["source_fire_verdict"]), "side": pick.get("side")}
    no_drag = no_drag_v2(base, strict, drag_core_v2(drag_features))
    families = {"base": base, "anchor": anchor, "preclose": preclose, "reentry": reentry}
    lanes = evaluate_lanes_v2(families, no_drag)
    eligibility = _eligible_reasons_v2(pitcher=pitcher, pick=pick, slate_date=slate_date, is_tracked=is_tracked, source_artifact_path=source_artifact_path, source_payload_sha256=source_payload_sha256, source_artifact_byte_sha256=source_artifact_byte_sha256, observed_at=observed_at)
    if eligibility:
        lanes = LaneEvaluation(lanes.consensus_core, lanes.reentry_expansion, None, "not_selected", lanes.family_count, lanes.maximum_family_count, ())
    reasons = tuple(dict.fromkeys((*eligibility, *(reason for vote in families.values() for reason in vote.reason_codes), *no_drag.reason_codes, *lanes.consensus_core.reason_codes, *lanes.reentry_expansion.reason_codes)))
    return AlternativePickEvaluationV2(not eligibility, eligibility, selector_fingerprint(), families, True if no_drag.state == "true" else False if no_drag.state == "false" else None, lanes.lane, lanes.selection_status, lanes.family_count, lanes.maximum_family_count, lanes.decisive_families, reasons, features or {}, presence)
