"""Bounded, independently auditable decision proofs for Alt Picks V2."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from market_infra.alternative_pick_preclose_v2 import ExactPrecloseResult
from market_infra import alternative_pick_selector_v2 as selector_v2
from market_infra.published_artifacts import canonical_payload_sha256


MAX_PROOF_DB_BYTES = 32_768
MAX_PROOF_APPLICATION_BYTES = 30_720
MAX_DECISIVE_TOKENS = 32

V2_SCHEMA_VERSION = "v2"
APPROVED_ARTIFACT_PATH = "dashboard/data/processed/today.json"
SUPPORTED_PROVIDERS = frozenset({"therundown", "propline"})
FAMILY_ORDER = ("base", "anchor", "preclose", "reentry")
NORMALIZED_INPUT_FIELDS = (
    "side", "official_verdict", "source_fire_verdict", "pitcher", "game_time",
    "k_line", "line_bucket", "odds", "official_book", "price_sign",
    "bet_timing_window", "model_market_relationship", "model_no_vig_gap", "edge",
    "adjusted_ev", "adjusted_ev_error", "quality_gate_level", "opportunity_bucket",
    "leash_risk_bucket", "pitcher_archetype_bucket", "large_edge_skepticism_flag",
    "anchor_labels", "anchor_metadata_malformed", "observed_at",
)


@dataclass(frozen=True)
class EvaluationProofBuild:
    proof: dict[str, Any]
    selection_safe: bool
    reason_codes: tuple[str, ...]


def _value(source: Any, key: str, default: Any = None) -> Any:
    return source.get(key, default) if isinstance(source, Mapping) else getattr(source, key, default)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _enum(value: Any) -> str:
    return _text(value).lower()


def _hash(value: Any) -> str | None:
    text = _enum(value)
    return text if len(text) == 64 and all(char in "0123456789abcdef" for char in text) else None


def _number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _integer(value: Any) -> int | None:
    parsed = _number(value)
    return int(parsed) if parsed is not None and parsed.is_integer() else None


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def _json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, allow_nan=False))


def _encoded_size(proof: Mapping[str, Any]) -> int:
    return len(json.dumps(
        proof, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False,
    ).encode("utf-8"))


def _state(value: Any) -> str:
    state = _enum(_value(value, "state", "pending"))
    return state if state in {"agree", "disagree", "pending"} else "pending"


def _family_objects(evaluation: Any) -> dict[str, selector_v2.FamilyVote]:
    raw = _value(evaluation, "family_states", {})
    if not isinstance(raw, Mapping):
        raise ValueError("family states must be an object")
    families: dict[str, selector_v2.FamilyVote] = {}
    for name in FAMILY_ORDER:
        value = raw.get(name)
        state = _state(value)
        reasons = _value(value, "reason_codes", ())
        if not isinstance(reasons, (list, tuple)):
            raise ValueError("family reasons must be bounded arrays")
        families[name] = selector_v2.FamilyVote(
            state, tuple(_text(reason) for reason in reasons if _text(reason)),
        )
    return families


def _tri_state(value: Any) -> str:
    return "true" if value is True else "false" if value is False else "pending"


def _family_tri(vote: selector_v2.FamilyVote) -> bool | None:
    return True if vote.state == "agree" else False if vote.state == "disagree" else None


def _bounded_string_list(value: Any, *, maximum: int = 32) -> list[str]:
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValueError("proof input list is not bounded")
    result = [_text(item) for item in value]
    if any(not item for item in result) or len(set(result)) != len(result):
        raise ValueError("proof input list is malformed")
    return result


def _provider_token(provider: str, identifier: str) -> str:
    return identifier if identifier.startswith(f"{provider}:") else f"{provider}:{identifier}"


def _decisive_tokens(
    *, full_tokens: Sequence[str], bindings: Mapping[str, Any], reversal_count: int,
) -> list[str]:
    if not full_tokens:
        return []
    wanted = {full_tokens[0], full_tokens[-1]}
    for provider, binding in bindings.items():
        if not isinstance(binding, Mapping):
            continue
        for identifier in binding.get("seed_snapshot_ids", ()):
            wanted.add(_provider_token(provider, _text(identifier)))
        provider_tokens = [token for token in full_tokens if token.startswith(f"{provider}:")]
        if provider_tokens:
            wanted.update((provider_tokens[0], provider_tokens[-1]))
    if reversal_count > 0 and len(full_tokens) > 2:
        wanted.add(full_tokens[len(full_tokens) // 2])
    decisive = [token for token in full_tokens if token in wanted]
    if len(decisive) > MAX_DECISIVE_TOKENS:
        raise ValueError("decisive token set exceeds bound")
    return decisive


def _candidate_proof(
    candidate: Mapping[str, Any], *, official_provider: str, official_binding_key: str | None,
) -> dict[str, Any]:
    return {
        "candidate_identity": _text(candidate.get("candidate_identity")),
        "slate_date": _text(candidate.get("slate_date")),
        "normalized_pitcher": _text(candidate.get("normalized_pitcher")),
        "side": _enum(candidate.get("side")),
        "model_k_line": _number(candidate.get("model_k_line")),
        "game_time": _iso(candidate.get("game_time")),
        "line_source_provider": official_provider,
        "official_binding_key": official_binding_key,
    }


def _artifact_proof(artifact: Mapping[str, Any]) -> dict[str, Any]:
    payload = artifact.get("payload")
    return {
        "source_artifact_path": _text(artifact.get("path")),
        "source_artifact_generated_at": _iso(artifact.get("generated_at")),
        "source_artifact_sha256": canonical_payload_sha256(payload) if payload is not None else None,
        "source_artifact_byte_sha256": _hash(artifact.get("byte_sha256")),
    }


def _diagnostic_build(
    *, candidate: Mapping[str, Any], artifact: Mapping[str, Any], reason: str,
) -> EvaluationProofBuild:
    official_provider = _enum(candidate.get("line_source_provider"))
    if official_provider not in SUPPORTED_PROVIDERS:
        official_provider = "therundown"
    proof = {
        "schema_version": V2_SCHEMA_VERSION,
        "bundle_id": selector_v2.BUNDLE_ID,
        "selector_fingerprint": selector_v2.FROZEN_SELECTOR_FINGERPRINT,
        "candidate": _candidate_proof(
            candidate, official_provider=official_provider, official_binding_key=None,
        ),
        "artifact": _artifact_proof(artifact),
        "bindings": {},
        "freshness": {},
        "normalized_inputs": {},
        "preclose": {
            "qualifying_observation_count": 0,
            "decisive_observation_tokens": [],
            "full_ordered_token_sha256": hashlib.sha256(b"").hexdigest(),
            "first_observed_at": None,
            "last_observed_at": None,
            "freshness_status": "pending",
            "book_count": None,
            "books_seen": [],
            "toward_pick_count": None,
            "away_from_pick_count": None,
            "side_price_movement": None,
            "broad_confirmation": None,
            "reversal_book_count": None,
            "volatile_book_count": None,
            "best_is_off_market": None,
            "score": None,
            "label": None,
            "positive_reasons": [],
            "risk_reasons": [],
            "reason_codes": [reason],
        },
        "decision": {
            "support": "pending",
            "drag_core": "pending",
            "no_drag": "pending",
            "family_states": {
                name: {"state": "pending", "reason_codes": [reason]}
                for name in FAMILY_ORDER
            },
            "consensus_core": "pending",
            "reentry_expansion": "pending",
            "selected_lane": None,
            "selection_status": "pending",
            "decisive_families": [],
            "preclose_required_for_selected_lane": False,
            "reason_codes": [reason],
        },
    }
    return EvaluationProofBuild(proof, False, (reason,))


def _build_full_proof(
    *, candidate: Mapping[str, Any], evaluation: Any,
    exact_preclose: ExactPrecloseResult, artifact: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(candidate, Mapping) or not isinstance(artifact, Mapping):
        raise ValueError("candidate and artifact must be objects")
    if not isinstance(exact_preclose, ExactPrecloseResult):
        raise ValueError("exact Preclose result is required")
    if _value(evaluation, "selector_fingerprint") != selector_v2.FROZEN_SELECTOR_FINGERPRINT:
        raise ValueError("selector fingerprint mismatch")

    artifact_part = _artifact_proof(artifact)
    if (
        artifact_part["source_artifact_path"] != APPROVED_ARTIFACT_PATH
        or artifact_part["source_artifact_sha256"] != _hash(artifact.get("payload_sha256"))
        or artifact_part["source_artifact_byte_sha256"] is None
    ):
        raise ValueError("artifact provenance mismatch")

    fragment = exact_preclose.proof_fragment
    exact = fragment.get("exact_preclose") if isinstance(fragment, Mapping) else None
    if (
        not isinstance(exact, Mapping)
        or fragment.get("schema_version") != "alternative_pick_preclose_v2"
        or not isinstance(exact.get("bindings_by_provider"), Mapping)
    ):
        raise ValueError("exact Preclose proof fragment is malformed")
    official_provider = _enum(exact.get("official_provider"))
    declared_provider = _enum(candidate.get("line_source_provider"))
    if official_provider not in SUPPORTED_PROVIDERS or (
        declared_provider and declared_provider != official_provider
    ):
        raise ValueError("official provider mismatch")
    official_binding_key = _hash(exact.get("official_binding_key"))
    if official_binding_key is None:
        raise ValueError("official binding key is invalid")

    market = exact_preclose.market_evidence
    window = exact_preclose.evidence_window
    if not isinstance(market, Mapping) or not isinstance(window, Mapping):
        raise ValueError("exact Preclose evidence is malformed")
    participating = set(_bounded_string_list(market.get("participating_providers", [])))
    provider_windows = exact.get("provider_window_started_at")
    provider_freshness = exact.get("provider_freshness")
    if not isinstance(provider_windows, Mapping) or not isinstance(provider_freshness, Mapping):
        raise ValueError("provider proof details are malformed")

    raw_bindings = exact["bindings_by_provider"]
    if len(raw_bindings) > len(SUPPORTED_PROVIDERS):
        raise ValueError("provider binding set is not bounded")
    bindings: dict[str, Any] = {}
    for provider in sorted(raw_bindings):
        binding = raw_bindings[provider]
        if provider not in SUPPORTED_PROVIDERS or not isinstance(binding, Mapping):
            raise ValueError("provider binding is malformed")
        event_id = _text(binding.get("provider_event_id"))
        binding_key = _hash(binding.get("binding_key"))
        current_ids = _bounded_string_list(binding.get("current_line_ids", []))
        seed_ids = _bounded_string_list(binding.get("seed_snapshot_ids", []))
        if not event_id or binding_key is None:
            raise ValueError("provider binding identity is invalid")
        bindings[provider] = {
            "role": "official" if provider == official_provider else "sidecar",
            "provider_event_id": event_id,
            "current_line_ids": current_ids,
            "seed_observation_tokens": [_provider_token(provider, item) for item in seed_ids],
            "binding_key": binding_key,
            "window_started_at": _iso(provider_windows.get(provider)),
            "mature": provider in participating,
        }
        if bindings[provider]["window_started_at"] is None:
            raise ValueError("provider window start is invalid")
    if official_provider not in bindings or bindings[official_provider]["binding_key"] != official_binding_key:
        raise ValueError("official binding is inconsistent")

    freshness: dict[str, Any] = {}
    for provider in sorted(provider_freshness):
        value = provider_freshness[provider]
        if provider not in bindings or not isinstance(value, Mapping):
            raise ValueError("provider freshness is malformed")
        status = _enum(value.get("freshness_status"))
        latest = _iso(value.get("latest_snapshot_at"))
        if status not in {"fresh", "stale", "pending"} or latest is None:
            raise ValueError("provider freshness is invalid")
        freshness[provider] = {
            "freshness_status": status,
            "latest_snapshot_at": latest,
        }

    normalized_raw = _value(evaluation, "normalized_inputs", {})
    if not isinstance(normalized_raw, Mapping):
        raise ValueError("normalized inputs must be an object")
    normalized_inputs = {
        field: _json_copy(normalized_raw[field])
        for field in NORMALIZED_INPUT_FIELDS if field in normalized_raw
    }
    families = _family_objects(evaluation)
    labels = normalized_inputs.get("anchor_labels")
    strict_anchor = (
        True if isinstance(labels, list) and "market_anchor_strict" in labels
        else False if isinstance(labels, list) else None
    )
    support = selector_v2.tri_or(_family_tri(families["base"]), strict_anchor)
    drag_vote = selector_v2.drag_core_v2(normalized_inputs)
    no_drag_vote = selector_v2.no_drag_v2(
        families["base"],
        selector_v2.FamilyVote(
            "agree" if strict_anchor is True else "disagree" if strict_anchor is False else "pending",
            (),
        ),
        drag_vote,
    )
    lanes = selector_v2.evaluate_lanes_v2(families, no_drag_vote)
    expected_no_drag = True if no_drag_vote.state == "true" else False if no_drag_vote.state == "false" else None
    if any((
        _value(evaluation, "no_drag") is not expected_no_drag,
        _value(evaluation, "lane") != lanes.lane,
        _value(evaluation, "selection_status") != lanes.selection_status,
        _integer(_value(evaluation, "family_count")) != lanes.family_count,
    )):
        raise ValueError("evaluation decision does not match recomputed logic")

    observations = market.get("observations")
    full_tokens = market.get("observation_ids")
    if not isinstance(observations, list) or not isinstance(full_tokens, list):
        raise ValueError("qualifying observation list is malformed")
    ordered_tokens = [_text(token) for token in full_tokens]
    observed_tokens = [
        _text(row.get("id")) for row in observations if isinstance(row, Mapping)
    ]
    if (
        any(not token or ":" not in token for token in ordered_tokens)
        or len(set(ordered_tokens)) != len(ordered_tokens)
        or observed_tokens != ordered_tokens
        or _integer(window.get("observation_count")) != len(ordered_tokens)
        or list(window.get("observation_ids", [])) != full_tokens
    ):
        raise ValueError("qualifying observations are inconsistent")
    first_at = _iso(market.get("first_observed_at"))
    last_at = _iso(market.get("last_observed_at"))
    observation_times = [_iso(row.get("observed_at")) for row in observations]
    if ordered_tokens and (
        any(value is None for value in observation_times)
        or first_at != min(observation_times)
        or last_at != max(observation_times)
    ):
        raise ValueError("qualifying observation bounds are inconsistent")

    reversal_count = _integer(market.get("reversal_book_count"))
    if reversal_count is None and _enum(market.get("freshness_status")) == "pending":
        reversal_count = 0
    if reversal_count is None or reversal_count < 0:
        raise ValueError("reversal count is invalid")
    decisive = _decisive_tokens(
        full_tokens=ordered_tokens, bindings=raw_bindings, reversal_count=reversal_count,
    )
    scored: dict[str, Any] | None = None
    if market.get("freshness_status") == "fresh":
        scored = selector_v2.preclose_proxy_score_v2(
            {**dict(market), **normalized_inputs},
            canonical_adjusted_ev=normalized_inputs.get("adjusted_ev"),
        )

    decisive_families = list(lanes.decisive_families)
    preclose_required = bool(
        lanes.lane == "consensus_core"
        and families["preclose"].state == "agree"
        and sum(
            families[name].state == "agree" for name in FAMILY_ORDER if name != "preclose"
        ) < 2
    )
    family_states = {
        name: {"state": vote.state, "reason_codes": list(vote.reason_codes)}
        for name, vote in families.items()
    }
    return {
        "schema_version": V2_SCHEMA_VERSION,
        "bundle_id": selector_v2.BUNDLE_ID,
        "selector_fingerprint": selector_v2.FROZEN_SELECTOR_FINGERPRINT,
        "candidate": _candidate_proof(
            candidate, official_provider=official_provider,
            official_binding_key=official_binding_key,
        ),
        "artifact": artifact_part,
        "bindings": bindings,
        "freshness": freshness,
        "normalized_inputs": normalized_inputs,
        "preclose": {
            "qualifying_observation_count": len(ordered_tokens),
            "decisive_observation_tokens": decisive,
            "full_ordered_token_sha256": hashlib.sha256(
                "|".join(ordered_tokens).encode("utf-8")
            ).hexdigest(),
            "first_observed_at": first_at,
            "last_observed_at": last_at,
            "freshness_status": _enum(market.get("freshness_status")) or "pending",
            "book_count": market.get("book_count"),
            "books_seen": _json_copy(market.get("books_seen", [])),
            "toward_pick_count": market.get("toward_pick_count"),
            "away_from_pick_count": market.get("away_from_pick_count"),
            "side_price_movement": market.get("side_price_movement"),
            "broad_confirmation": market.get("broad_confirmation"),
            "reversal_book_count": market.get("reversal_book_count"),
            "volatile_book_count": market.get("volatile_book_count"),
            "best_is_off_market": market.get("best_is_off_market"),
            "score": scored.get("score") if scored else None,
            "label": scored.get("label") if scored else None,
            "positive_reasons": list(scored.get("positive_reasons", [])) if scored else [],
            "risk_reasons": list(scored.get("risk_reasons", [])) if scored else [],
            "reason_codes": list(market.get("aggregation_reason_codes", [])),
        },
        "decision": {
            "support": _tri_state(support),
            "drag_core": drag_vote.state,
            "no_drag": no_drag_vote.state,
            "family_states": family_states,
            "consensus_core": lanes.consensus_core.state,
            "reentry_expansion": lanes.reentry_expansion.state,
            "selected_lane": lanes.lane,
            "selection_status": lanes.selection_status,
            "decisive_families": decisive_families,
            "preclose_required_for_selected_lane": preclose_required,
            "reason_codes": list(_value(evaluation, "reason_codes", ()) or ()),
        },
    }


def build_evaluation_proof_v2(
    *, candidate: Mapping[str, Any], evaluation: Any,
    exact_preclose: ExactPrecloseResult, artifact: Mapping[str, Any],
) -> EvaluationProofBuild:
    """Build a selected proof whole or return a small valid pending diagnostic."""
    safe_candidate = candidate if isinstance(candidate, Mapping) else {}
    safe_artifact = artifact if isinstance(artifact, Mapping) else {}
    try:
        proof = _build_full_proof(
            candidate=safe_candidate, evaluation=evaluation,
            exact_preclose=exact_preclose, artifact=safe_artifact,
        )
        size = _encoded_size(proof)
        if size > MAX_PROOF_APPLICATION_BYTES:
            return _diagnostic_build(
                candidate=safe_candidate, artifact=safe_artifact,
                reason="evaluation_proof_oversized",
            )
        valid, reasons = validate_evaluation_proof_v2(proof=proof)
        if not valid:
            reason = "evaluation_proof_oversized" if "evaluation_proof_oversized" in reasons else "evaluation_proof_invalid"
            return _diagnostic_build(candidate=safe_candidate, artifact=safe_artifact, reason=reason)
        return EvaluationProofBuild(proof, True, ())
    except (TypeError, ValueError, OverflowError):
        return _diagnostic_build(
            candidate=safe_candidate, artifact=safe_artifact,
            reason="evaluation_proof_invalid",
        )


def validate_evaluation_proof_v2(
    *, proof: Mapping[str, Any], row: Mapping[str, Any] | None = None,
) -> tuple[bool, tuple[str, ...]]:
    """Validate proof shape plus optional persisted-row identity bindings."""
    if row and row.get("bundle_id") == "pregame_alternative_pick_methodology_v1":
        return (True, ()) if isinstance(proof, Mapping) and not proof else (
            False, ("v1_evaluation_proof_must_be_empty",)
        )
    reasons: list[str] = []
    if not isinstance(proof, Mapping):
        return False, ("evaluation_proof_not_object",)
    try:
        size = _encoded_size(proof)
    except (TypeError, ValueError, OverflowError):
        return False, ("evaluation_proof_not_json",)
    if size > MAX_PROOF_DB_BYTES:
        reasons.append("evaluation_proof_db_oversized")
    if size > MAX_PROOF_APPLICATION_BYTES:
        reasons.append("evaluation_proof_oversized")
    required_top = {
        "schema_version", "bundle_id", "selector_fingerprint", "candidate", "artifact",
        "bindings", "freshness", "normalized_inputs", "preclose", "decision",
    }
    if set(proof) != required_top:
        reasons.append("evaluation_proof_shape_invalid")
    if proof.get("schema_version") != V2_SCHEMA_VERSION:
        reasons.append("evaluation_proof_schema_invalid")
    if proof.get("bundle_id") != selector_v2.BUNDLE_ID:
        reasons.append("evaluation_proof_bundle_mismatch")
    if proof.get("selector_fingerprint") != selector_v2.FROZEN_SELECTOR_FINGERPRINT:
        reasons.append("evaluation_proof_fingerprint_mismatch")

    candidate = proof.get("candidate")
    artifact = proof.get("artifact")
    preclose = proof.get("preclose")
    decision = proof.get("decision")
    for name, value in (
        ("candidate", candidate), ("artifact", artifact),
        ("bindings", proof.get("bindings")), ("freshness", proof.get("freshness")),
        ("normalized_inputs", proof.get("normalized_inputs")),
        ("preclose", preclose), ("decision", decision),
    ):
        if not isinstance(value, Mapping):
            reasons.append(f"evaluation_proof_{name}_invalid")
    if not isinstance(candidate, Mapping) or not isinstance(artifact, Mapping) or not isinstance(preclose, Mapping) or not isinstance(decision, Mapping):
        return False, tuple(dict.fromkeys(reasons))

    diagnostic_reasons = decision.get("reason_codes")
    is_diagnostic = bool(
        decision.get("selection_status") == "pending"
        and decision.get("selected_lane") is None
        and isinstance(diagnostic_reasons, list)
        and len(diagnostic_reasons) == 1
        and diagnostic_reasons[0] in {"evaluation_proof_invalid", "evaluation_proof_oversized"}
    )

    if any((
        not _text(candidate.get("candidate_identity")),
        not _text(candidate.get("slate_date")),
        not _text(candidate.get("normalized_pitcher")),
        _enum(candidate.get("side")) not in {"over", "under"},
        _number(candidate.get("model_k_line")) is None,
        _iso(candidate.get("game_time")) is None,
        _enum(candidate.get("line_source_provider")) not in SUPPORTED_PROVIDERS,
    )):
        reasons.append("evaluation_proof_candidate_identity_invalid")
    if any((
        artifact.get("source_artifact_path") != APPROVED_ARTIFACT_PATH,
        _hash(artifact.get("source_artifact_sha256")) is None,
        _hash(artifact.get("source_artifact_byte_sha256")) is None,
    )):
        reasons.append("evaluation_proof_artifact_invalid")

    bindings = proof.get("bindings")
    if isinstance(bindings, Mapping):
        official_provider = _enum(candidate.get("line_source_provider"))
        official_binding = bindings.get(official_provider)
        if not is_diagnostic and (
            not isinstance(official_binding, Mapping)
            or official_binding.get("role") != "official"
            or _hash(official_binding.get("binding_key")) != _hash(candidate.get("official_binding_key"))
        ):
            reasons.append("evaluation_proof_official_binding_mismatch")
        if len(bindings) > len(SUPPORTED_PROVIDERS):
            reasons.append("evaluation_proof_bindings_unbounded")
        for provider, binding in bindings.items():
            if provider not in SUPPORTED_PROVIDERS or not isinstance(binding, Mapping):
                reasons.append("evaluation_proof_binding_invalid")
                continue
            seed_tokens = binding.get("seed_observation_tokens")
            current_ids = binding.get("current_line_ids")
            if any((
                binding.get("role") not in {"official", "sidecar"},
                not _text(binding.get("provider_event_id")),
                _hash(binding.get("binding_key")) is None,
                _iso(binding.get("window_started_at")) is None,
                not isinstance(binding.get("mature"), bool),
                not isinstance(seed_tokens, list),
                isinstance(seed_tokens, list) and (
                    len(seed_tokens) > MAX_DECISIVE_TOKENS
                    or any(not _text(token).startswith(f"{provider}:") for token in seed_tokens)
                ),
                not isinstance(current_ids, list),
                isinstance(current_ids, list) and len(current_ids) > MAX_DECISIVE_TOKENS,
            )):
                reasons.append("evaluation_proof_binding_invalid")

    count = _integer(preclose.get("qualifying_observation_count"))
    tokens = preclose.get("decisive_observation_tokens")
    if count is None or count < 0:
        reasons.append("evaluation_proof_count_invalid")
    if (
        not isinstance(tokens, list) or len(tokens) > MAX_DECISIVE_TOKENS
        or len({_text(token) for token in tokens}) != len(tokens)
        or any(not _text(token) or ":" not in _text(token) for token in tokens)
    ):
        reasons.append("evaluation_proof_tokens_invalid")
    if _hash(preclose.get("full_ordered_token_sha256")) is None:
        reasons.append("evaluation_proof_token_digest_invalid")
    if count and (_iso(preclose.get("first_observed_at")) is None or _iso(preclose.get("last_observed_at")) is None):
        reasons.append("evaluation_proof_observation_bounds_invalid")

    family_states = decision.get("family_states")
    if not isinstance(family_states, Mapping) or set(family_states) != set(FAMILY_ORDER):
        reasons.append("evaluation_proof_family_states_invalid")
    elif any(_enum(_value(family_states[name], "state")) not in {"agree", "disagree", "pending"} for name in FAMILY_ORDER):
        reasons.append("evaluation_proof_family_states_invalid")
    for field in ("support", "drag_core", "no_drag", "consensus_core", "reentry_expansion"):
        if decision.get(field) not in {"true", "false", "pending"}:
            reasons.append("evaluation_proof_logic_invalid")
            break
    lane = decision.get("selected_lane")
    status = decision.get("selection_status")
    if lane not in {None, "consensus_core", "reentry_expansion"} or status not in {"selected", "not_selected", "pending"}:
        reasons.append("evaluation_proof_decision_invalid")
    elif (status == "selected") != (lane is not None):
        reasons.append("evaluation_proof_decision_invalid")
    if not isinstance(decision.get("decisive_families"), list):
        reasons.append("evaluation_proof_decisive_families_invalid")
    if not isinstance(decision.get("preclose_required_for_selected_lane"), bool):
        reasons.append("evaluation_proof_preclose_dependency_invalid")

    if row is not None:
        if row.get("bundle_id") != selector_v2.BUNDLE_ID:
            reasons.append("evaluation_proof_row_bundle_mismatch")
        if row.get("selector_fingerprint") != proof.get("selector_fingerprint"):
            reasons.append("evaluation_proof_row_fingerprint_mismatch")
        row_candidate_checks = (
            ("candidate_identity", "candidate_identity", _text),
            ("slate_date", "slate_date", _text),
            ("normalized_pitcher", "normalized_pitcher", _text),
            ("side", "side", _enum),
            ("model_k_line", "model_k_line", _number),
            ("game_time", "game_time", _iso),
        )
        if any(normalizer(row.get(row_key)) != normalizer(candidate.get(proof_key)) for row_key, proof_key, normalizer in row_candidate_checks):
            reasons.append("evaluation_proof_row_candidate_mismatch")
        artifact_checks = (
            ("source_artifact_path", "source_artifact_path", _text),
            ("source_artifact_sha256", "source_artifact_sha256", _hash),
            ("source_artifact_byte_sha256", "source_artifact_byte_sha256", _hash),
        )
        if any(normalizer(row.get(row_key)) != normalizer(artifact.get(proof_key)) for row_key, proof_key, normalizer in artifact_checks):
            reasons.append("evaluation_proof_row_artifact_mismatch")
        if row.get("selection_status") != status or row.get("lane") != lane:
            reasons.append("evaluation_proof_row_decision_mismatch")
    result = tuple(dict.fromkeys(reasons))
    return not result, result
