"""Bounded, independently auditable decision proofs for Alt Picks V2."""

from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Mapping, Sequence

from market_infra.alternative_pick_preclose_v2 import ExactPrecloseResult
from market_infra import alternative_pick_selector_v2 as selector_v2
from market_infra.published_artifacts import canonical_payload_sha256


MAX_PROOF_DB_BYTES = 32_768
MAX_PROOF_APPLICATION_BYTES = 30_720
MAX_DECISIVE_TOKENS = 32
MAX_SOURCE_TOKENS = 10_000
MAX_REASON_COUNT = 16
MAX_REASON_BYTES = 128
MAX_LABEL_COUNT = 16
MAX_LABEL_BYTES = 128
MAX_TEXT_BYTES = 256
MAX_TOKEN_BYTES = 384

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
    "is_opener", "starter_mismatch", "last_pitch_count", "days_since_last_start",
    "workload_input_status", "anchor_labels", "anchor_metadata_malformed", "observed_at",
)
NORMALIZED_TEXT_INPUT_FIELDS = frozenset({
    "side", "official_verdict", "source_fire_verdict", "pitcher", "game_time",
    "line_bucket", "official_book", "price_sign", "bet_timing_window",
    "model_market_relationship", "adjusted_ev_error", "quality_gate_level",
    "opportunity_bucket", "leash_risk_bucket", "pitcher_archetype_bucket",
    "workload_input_status", "observed_at",
})
NORMALIZED_NUMBER_INPUT_FIELDS = frozenset({
    "k_line", "model_no_vig_gap", "edge", "adjusted_ev",
})
NORMALIZED_INTEGER_INPUT_FIELDS = frozenset({"odds"})
NORMALIZED_BOOLEAN_INPUT_FIELDS = frozenset({
    "large_edge_skepticism_flag", "anchor_metadata_malformed",
})
NORMALIZED_NULLABLE_BOOLEAN_INPUT_FIELDS = frozenset({
    "is_opener", "starter_mismatch",
})
NORMALIZED_NULLABLE_INTEGER_INPUT_FIELDS = frozenset({
    "last_pitch_count", "days_since_last_start",
})
ROW_BINDING_INPUT_FIELDS = (
    "side", "pitcher", "game_time", "k_line", "odds", "official_book",
    "official_verdict",
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


def postgres_jsonb_text_size(proof: Mapping[str, Any]) -> int:
    """Conservative byte count for PostgreSQL ``jsonb::text`` serialization."""
    def render(value: Any) -> str:
        if value is None:
            return "null"
        if value is True:
            return "true"
        if value is False:
            return "false"
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("non-finite JSON number")
            return format(Decimal(str(value)), "f")
        if isinstance(value, str):
            return json.dumps(value, ensure_ascii=False)
        if isinstance(value, Mapping):
            return "{" + ", ".join(
                f"{json.dumps(str(key), ensure_ascii=False)}: {render(item)}"
                for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            ) + "}"
        if isinstance(value, (list, tuple)):
            return "[" + ", ".join(render(item) for item in value) + "]"
        raise TypeError("proof contains a non-JSON value")

    return len(render(proof).encode("utf-8"))


def _bounded_text(value: Any, *, maximum: int = MAX_TEXT_BYTES) -> str:
    text = _text(value)
    if not text or len(text.encode("utf-8")) > maximum:
        raise ValueError("proof string is missing or unbounded")
    return text


def _bounded_reasons(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or len(value) > MAX_REASON_COUNT:
        raise ValueError("proof reasons are not bounded")
    return tuple(_bounded_text(reason, maximum=MAX_REASON_BYTES) for reason in value)


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
        reasons = _bounded_reasons(_value(value, "reason_codes", ()))
        families[name] = selector_v2.FamilyVote(
            state, reasons,
        )
    return families


def _tri_state(value: Any) -> str:
    return "true" if value is True else "false" if value is False else "pending"


def _family_tri(vote: selector_v2.FamilyVote) -> bool | None:
    return True if vote.state == "agree" else False if vote.state == "disagree" else None


def _bounded_string_list(
    value: Any, *, maximum: int = 32, item_bytes: int = MAX_TEXT_BYTES,
) -> list[str]:
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValueError("proof input list is not bounded")
    result = [_bounded_text(item, maximum=item_bytes) for item in value]
    if len(set(result)) != len(result):
        raise ValueError("proof input list is malformed")
    return result


def _provider_token(provider: str, identifier: str) -> str:
    return identifier if identifier.startswith(f"{provider}:") else f"{provider}:{identifier}"


def _validated_token(token: Any, bindings: Mapping[str, Any]) -> str:
    value = _bounded_text(token, maximum=MAX_TOKEN_BYTES)
    provider, separator, identifier = value.partition(":")
    if not separator or not identifier or provider not in SUPPORTED_PROVIDERS or provider not in bindings:
        raise ValueError("proof token provider is unsupported or unbound")
    return value


def _decisive_tokens(
    *, full_tokens: Sequence[str], bindings: Mapping[str, Any],
    pivot_tokens: Sequence[str], latest_ladder_tokens: Sequence[str],
) -> list[str]:
    wanted = set(pivot_tokens) | set(latest_ladder_tokens)
    if full_tokens:
        wanted.update((full_tokens[0], full_tokens[-1]))
    for provider, binding in bindings.items():
        if not isinstance(binding, Mapping):
            continue
        for identifier in binding.get("seed_snapshot_ids", ()):
            wanted.add(_provider_token(provider, _text(identifier)))
        provider_tokens = [token for token in full_tokens if token.startswith(f"{provider}:")]
        if provider_tokens:
            wanted.update((provider_tokens[0], provider_tokens[-1]))
    ordered = list(dict.fromkeys((*full_tokens, *pivot_tokens, *latest_ladder_tokens)))
    decisive = [token for token in ordered if token in wanted]
    if len(decisive) > MAX_DECISIVE_TOKENS:
        raise ValueError("decisive token set exceeds bound")
    return decisive


def _candidate_proof(
    candidate: Mapping[str, Any], *, official_provider: str, official_binding_key: str | None,
) -> dict[str, Any]:
    return {
        "candidate_identity": _bounded_text(candidate.get("candidate_identity"), maximum=64),
        "slate_date": _bounded_text(candidate.get("slate_date"), maximum=10),
        "normalized_pitcher": _bounded_text(candidate.get("normalized_pitcher"), maximum=128),
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


def _safe_digest(value: Any) -> str:
    return hashlib.sha256(_text(value).encode("utf-8")).hexdigest()


def _diagnostic_candidate(candidate: Mapping[str, Any]) -> dict[str, Any]:
    provider = _enum(candidate.get("line_source_provider"))
    provider = provider if provider in SUPPORTED_PROVIDERS else "therundown"
    normalized = _text(candidate.get("normalized_pitcher"))
    if not normalized or len(normalized.encode("utf-8")) > 128:
        normalized = f"invalid-{_safe_digest(normalized)[:16]}"
    side = _enum(candidate.get("side"))
    line = _number(candidate.get("model_k_line"))
    return {
        "candidate_identity": _hash(candidate.get("candidate_identity")) or _safe_digest(candidate.get("candidate_identity")),
        "slate_date": _text(candidate.get("slate_date")) if len(_text(candidate.get("slate_date"))) <= 10 else "1970-01-01",
        "normalized_pitcher": normalized,
        "side": side if side in {"over", "under"} else "over",
        "model_k_line": line if line is not None else 0.0,
        "game_time": _iso(candidate.get("game_time")) or "1970-01-01T00:00:00+00:00",
        "line_source_provider": provider,
        "official_binding_key": None,
    }


def _diagnostic_artifact(artifact: Mapping[str, Any]) -> dict[str, Any]:
    payload_hash = None
    try:
        if artifact.get("payload") is not None:
            payload_hash = canonical_payload_sha256(artifact.get("payload"))
    except (TypeError, ValueError, OverflowError):
        payload_hash = None
    return {
        "source_artifact_path": APPROVED_ARTIFACT_PATH,
        "source_artifact_generated_at": _iso(artifact.get("generated_at")),
        "source_artifact_sha256": payload_hash or "0" * 64,
        "source_artifact_byte_sha256": _hash(artifact.get("byte_sha256")) or "0" * 64,
    }


def _diagnostic_build(
    *, candidate: Mapping[str, Any], artifact: Mapping[str, Any], reason: str,
) -> EvaluationProofBuild:
    diagnostic_candidate = _diagnostic_candidate(candidate)
    diagnostic_inputs = {
        "side": diagnostic_candidate["side"],
        "pitcher": diagnostic_candidate["normalized_pitcher"],
        "game_time": diagnostic_candidate["game_time"],
        "k_line": diagnostic_candidate["model_k_line"],
        "odds": _integer(candidate.get("official_odds")),
        "official_book": _enum(candidate.get("official_book")) or None,
        "official_verdict": _text(candidate.get("official_verdict")) or None,
    }
    proof = {
        "schema_version": V2_SCHEMA_VERSION,
        "bundle_id": selector_v2.BUNDLE_ID,
        "selector_fingerprint": selector_v2.FROZEN_SELECTOR_FINGERPRINT,
        "candidate": diagnostic_candidate,
        "artifact": _diagnostic_artifact(artifact),
        "bindings": {},
        "freshness": {},
        "normalized_inputs": diagnostic_inputs,
        "preclose": {
            "qualifying_observation_count": 0,
            "decisive_observation_tokens": [],
            "full_ordered_token_sha256": hashlib.sha256(b"").hexdigest(),
            "direction_change_pivot_tokens": [],
            "latest_ladder_observation_tokens": [],
            "ladder_observation_token_sha256": hashlib.sha256(b"").hexdigest(),
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
            "family_count": 0,
            "maximum_family_count": 4,
            "decisive_families": [],
            "preclose_required_for_selected_lane": False,
            "reason_codes": [reason],
        },
    }
    if (
        _encoded_size(proof) > MAX_PROOF_APPLICATION_BYTES
        or postgres_jsonb_text_size(proof) > MAX_PROOF_DB_BYTES
        or not validate_evaluation_proof_v2(proof=proof)[0]
    ):
        proof["candidate"] = {
            "candidate_identity": "0" * 64,
            "slate_date": "1970-01-01",
            "normalized_pitcher": "invalid",
            "side": "over",
            "model_k_line": 0.0,
            "game_time": "1970-01-01T00:00:00+00:00",
            "line_source_provider": "therundown",
            "official_binding_key": None,
        }
        proof["artifact"] = {
            "source_artifact_path": APPROVED_ARTIFACT_PATH,
            "source_artifact_generated_at": None,
            "source_artifact_sha256": "0" * 64,
            "source_artifact_byte_sha256": "0" * 64,
        }
        proof["normalized_inputs"] = {
            "side": "over", "pitcher": "invalid",
            "game_time": "1970-01-01T00:00:00+00:00", "k_line": 0.0,
            "odds": None, "official_book": None, "official_verdict": None,
        }
    return EvaluationProofBuild(proof, False, (reason,))


def _bounded_normalized_inputs(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) != set(NORMALIZED_INPUT_FIELDS):
        raise ValueError("normalized proof inputs do not match the exact contract")
    normalized = {
        field: _json_copy(raw[field]) for field in NORMALIZED_INPUT_FIELDS
    }
    for field, value in normalized.items():
        if field == "anchor_labels":
            if value is not None:
                bounded_labels = _bounded_string_list(
                    value, maximum=MAX_LABEL_COUNT, item_bytes=MAX_LABEL_BYTES,
                )
                if bounded_labels != value:
                    raise ValueError("normalized proof labels are not canonical")
                normalized[field] = bounded_labels
        elif field in NORMALIZED_TEXT_INPUT_FIELDS:
            if value is not None and not isinstance(value, str):
                raise ValueError("normalized proof text input has an invalid type")
            if value is not None:
                bounded_text = _bounded_text(value)
                if bounded_text != value:
                    raise ValueError("normalized proof text input is not canonical")
                normalized[field] = bounded_text
        elif field in NORMALIZED_NUMBER_INPUT_FIELDS:
            if value is not None and (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(value)
            ):
                raise ValueError("normalized proof numeric input has an invalid type")
        elif field in NORMALIZED_INTEGER_INPUT_FIELDS:
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int)
            ):
                raise ValueError("normalized proof integer input has an invalid type")
        elif field in NORMALIZED_BOOLEAN_INPUT_FIELDS:
            if not isinstance(value, bool):
                raise ValueError("normalized proof Boolean input has an invalid type")
        elif field in NORMALIZED_NULLABLE_BOOLEAN_INPUT_FIELDS:
            if value is not None and not isinstance(value, bool):
                raise ValueError("normalized proof nullable Boolean input has an invalid type")
        elif field in NORMALIZED_NULLABLE_INTEGER_INPUT_FIELDS:
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int)
            ):
                raise ValueError("normalized proof nullable integer input has an invalid type")
        else:
            raise ValueError("normalized proof input field has no type contract")
    workload_status = normalized["workload_input_status"]
    workload_values = (
        normalized["is_opener"], normalized["starter_mismatch"],
        normalized["last_pitch_count"], normalized["days_since_last_start"],
    )
    if workload_status not in {"complete", "missing", "malformed"}:
        raise ValueError("normalized proof workload status is invalid")
    if workload_status == "complete" and (
        not isinstance(workload_values[0], bool)
        or not isinstance(workload_values[1], bool)
        or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in workload_values[2:]
        )
    ):
        raise ValueError("complete workload proof inputs are invalid")
    if workload_status == "complete":
        opener_or_mismatch = bool(
            normalized["is_opener"] or normalized["starter_mismatch"]
        )
        short_leash = normalized["opportunity_bucket"] == "short_leash"
        expected_leash = (
            "high" if opener_or_mismatch or short_leash
            else "medium" if (
                normalized["last_pitch_count"] >= 105
                or normalized["days_since_last_start"] < 4
            )
            else "normal"
        )
        archetype = normalized["pitcher_archetype_bucket"]
        archetype_bound = (
            archetype == "opener_or_mismatch" if opener_or_mismatch
            else archetype == "short_leash" if short_leash
            else archetype not in {"opener_or_mismatch", "short_leash"}
        )
        if normalized["leash_risk_bucket"] != expected_leash or not archetype_bound:
            raise ValueError("complete workload proof buckets are inconsistent")
    has_null_workload_value = any(value is None for value in workload_values)
    has_negative_workload_integer = any(
        isinstance(value, int) and not isinstance(value, bool) and value < 0
        for value in workload_values[2:]
    )
    if workload_status == "missing" and (
        not has_null_workload_value or has_negative_workload_integer
    ):
        raise ValueError("missing workload proof inputs are inconsistent")
    if workload_status == "malformed" and not (
        has_null_workload_value or has_negative_workload_integer
    ):
        raise ValueError("malformed workload proof inputs lack a malformed value")
    return normalized


def _candidate_inputs_match(
    *, candidate: Mapping[str, Any], candidate_part: Mapping[str, Any],
    normalized: Mapping[str, Any],
) -> bool:
    return all((
        _enum(normalized.get("side")) == _enum(candidate_part.get("side")),
        _enum(normalized.get("pitcher")) == _enum(candidate_part.get("normalized_pitcher")),
        _iso(normalized.get("game_time")) == _iso(candidate_part.get("game_time")),
        _number(normalized.get("k_line")) == _number(candidate_part.get("model_k_line")),
        _integer(normalized.get("odds")) == _integer(candidate.get("official_odds")),
        _enum(normalized.get("official_book")) == _enum(candidate.get("official_book")),
        _text(normalized.get("official_verdict")) == _text(candidate.get("official_verdict")),
    ))


def _provider_contract_valid(
    *, candidate_provider: str, bindings: Mapping[str, Any],
    freshness: Mapping[str, Any], preclose_status: str,
) -> bool:
    official = [
        provider for provider, binding in bindings.items()
        if isinstance(binding, Mapping) and binding.get("role") == "official"
    ]
    if official != [candidate_provider]:
        return False
    if any(
        not isinstance(binding, Mapping)
        or binding.get("role") != ("official" if provider == candidate_provider else "sidecar")
        for provider, binding in bindings.items()
    ):
        return False
    mature = {
        provider for provider, binding in bindings.items()
        if isinstance(binding, Mapping) and binding.get("mature") is True
    }
    if set(freshness) != mature:
        return False
    if preclose_status == "fresh":
        official_binding = bindings.get(candidate_provider)
        official_freshness = freshness.get(candidate_provider)
        if (
            not isinstance(official_binding, Mapping)
            or official_binding.get("mature") is not True
            or not isinstance(official_freshness, Mapping)
            or official_freshness.get("freshness_status") != "fresh"
            or any(
                not isinstance(value, Mapping) or value.get("freshness_status") != "fresh"
                for value in freshness.values()
            )
        ):
            return False
    return True


def _preclose_state_valid(preclose: Mapping[str, Any]) -> bool:
    status = _enum(preclose.get("freshness_status"))
    count = _integer(preclose.get("qualifying_observation_count"))
    if status not in {"fresh", "pending"} or count is None or count < 0:
        return False
    aggregate_fields = (
        "book_count", "toward_pick_count", "away_from_pick_count",
        "side_price_movement", "broad_confirmation", "reversal_book_count",
        "volatile_book_count", "best_is_off_market", "score", "label",
    )
    if status == "pending":
        return all(preclose.get(field) is None for field in aggregate_fields) and bool(
            _bounded_reasons(preclose.get("reason_codes", []))
        ) and preclose.get("positive_reasons") == [] and preclose.get("risk_reasons") == []

    integers = {
        field: _integer(preclose.get(field))
        for field in (
            "book_count", "toward_pick_count", "away_from_pick_count",
            "reversal_book_count", "volatile_book_count",
        )
    }
    first = _iso(preclose.get("first_observed_at"))
    last = _iso(preclose.get("last_observed_at"))
    books_seen = preclose.get("books_seen")
    if (any(value is None or value < 0 for value in integers.values())
            or _integer(preclose.get("score")) is None):
        return False
    return all((
        count >= 2,
        isinstance(preclose.get("broad_confirmation"), bool),
        isinstance(preclose.get("best_is_off_market"), bool),
        preclose.get("side_price_movement") in {"with_side", "against_side", "neutral"},
        integers["reversal_book_count"] == integers["volatile_book_count"],
        integers["toward_pick_count"] + integers["away_from_pick_count"] <= integers["book_count"],
        isinstance(books_seen, list) and len(books_seen) == integers["book_count"],
        first is not None and last is not None and first <= last,
        bool(_text(preclose.get("label"))),
        preclose.get("reason_codes") == [],
    ))


def _family_payload(vote: selector_v2.FamilyVote) -> dict[str, Any]:
    return {"state": vote.state, "reason_codes": list(vote.reason_codes)}


def _recompute_semantics(
    normalized_inputs: Mapping[str, Any], preclose: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    workload_status = _enum(normalized_inputs.get("workload_input_status"))
    if workload_status == "complete":
        base_v1 = selector_v2.v1.strong_base_strict_plus_selective(dict(normalized_inputs))
        base = selector_v2.FamilyVote(base_v1.state, base_v1.reason_codes)
    else:
        base = selector_v2.FamilyVote(
            "pending", (f"workload_inputs_{workload_status}",),
        )
    labels = normalized_inputs.get("anchor_labels")
    anchor_malformed = normalized_inputs.get("anchor_metadata_malformed") is True
    if isinstance(labels, list) and not anchor_malformed:
        label_set = {_enum(label) for label in labels}
        strict = selector_v2.FamilyVote(
            "agree" if "market_anchor_strict" in label_set else "disagree",
            ("market_anchor_strict" if "market_anchor_strict" in label_set else "market_anchor_strict_absent",),
        )
        core = selector_v2.FamilyVote(
            "agree" if "market_anchor_core" in label_set else "disagree",
            ("market_anchor_core" if "market_anchor_core" in label_set else "market_anchor_core_absent",),
        )
    else:
        reason = "anchor_metadata_malformed" if anchor_malformed else "anchor_metadata_absent"
        strict = core = selector_v2.FamilyVote("pending", (reason,))
    anchor = selector_v2.compose_anchor_v2(base, strict, core)

    scored: dict[str, Any] | None = None
    if _enum(preclose.get("freshness_status")) == "fresh":
        scored = selector_v2.preclose_proxy_score_v2(
            {**dict(preclose), **dict(normalized_inputs)},
            canonical_adjusted_ev=normalized_inputs.get("adjusted_ev"),
        )
        raw_preclose = selector_v2.FamilyVote(
            "agree" if scored["label"] == "strong_preclose_clv_proxy" else "disagree",
            (scored["label"],),
        )
    else:
        reasons = _bounded_reasons(preclose.get("reason_codes", []))
        raw_preclose = selector_v2.FamilyVote(
            "pending", reasons or ("preclose_evidence_pending",),
        )
    preclose_vote = selector_v2.compose_preclose_v2(base, raw_preclose)
    if workload_status == "complete":
        reentry_v1 = selector_v2.v1.moderate_edge_quality_reentry(dict(normalized_inputs))
        reentry = selector_v2.FamilyVote(reentry_v1.state, reentry_v1.reason_codes)
    else:
        reentry = selector_v2.FamilyVote(
            "pending", (f"workload_inputs_{workload_status}",),
        )
    families = {
        "base": base, "anchor": anchor, "preclose": preclose_vote, "reentry": reentry,
    }
    support = selector_v2.tri_or(_family_tri(base), _family_tri(strict))
    drag = selector_v2.drag_core_v2(dict(normalized_inputs))
    no_drag = selector_v2.no_drag_v2(base, strict, drag)
    lanes = selector_v2.evaluate_lanes_v2(families, no_drag)
    preclose_required = bool(
        lanes.lane == "consensus_core"
        and preclose_vote.state == "agree"
        and sum(
            families[name].state == "agree" for name in FAMILY_ORDER if name != "preclose"
        ) < 2
    )
    return ({
        "support": _tri_state(support),
        "drag_core": drag.state,
        "no_drag": no_drag.state,
        "family_states": {name: _family_payload(vote) for name, vote in families.items()},
        "consensus_core": lanes.consensus_core.state,
        "reentry_expansion": lanes.reentry_expansion.state,
        "selected_lane": lanes.lane,
        "selection_status": lanes.selection_status,
        "family_count": lanes.family_count,
        "maximum_family_count": lanes.maximum_family_count,
        "decisive_families": list(lanes.decisive_families),
        "preclose_required_for_selected_lane": preclose_required,
    }, scored)


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
    if (
        official_provider not in SUPPORTED_PROVIDERS
        or declared_provider not in SUPPORTED_PROVIDERS
        or declared_provider != official_provider
    ):
        raise ValueError("official provider mismatch")
    if (
        _text(exact.get("source_artifact_path")) != artifact_part["source_artifact_path"]
        or _hash(exact.get("source_artifact_byte_sha256"))
        != artifact_part["source_artifact_byte_sha256"]
    ):
        raise ValueError("exact Preclose artifact binding mismatch")
    official_binding_key = _hash(exact.get("official_binding_key"))
    if official_binding_key is None:
        raise ValueError("official binding key is invalid")

    market = exact_preclose.market_evidence
    window = exact_preclose.evidence_window
    if not isinstance(market, Mapping) or not isinstance(window, Mapping):
        raise ValueError("exact Preclose evidence is malformed")
    participating = set(_bounded_string_list(
        market.get("participating_providers", []),
        maximum=len(SUPPORTED_PROVIDERS), item_bytes=32,
    ))
    if not participating.issubset(SUPPORTED_PROVIDERS):
        raise ValueError("participating provider is unsupported")
    provider_windows = exact.get("provider_window_started_at")
    provider_freshness = exact.get("provider_freshness")
    if not isinstance(provider_windows, Mapping) or not isinstance(provider_freshness, Mapping):
        raise ValueError("provider proof details are malformed")

    raw_bindings = exact["bindings_by_provider"]
    if len(raw_bindings) > len(SUPPORTED_PROVIDERS):
        raise ValueError("provider binding set is not bounded")
    mature_providers = set(provider_freshness)
    bindings: dict[str, Any] = {}
    for provider in sorted(raw_bindings):
        binding = raw_bindings[provider]
        if provider not in SUPPORTED_PROVIDERS or not isinstance(binding, Mapping):
            raise ValueError("provider binding is malformed")
        event_id = _bounded_text(binding.get("provider_event_id"))
        binding_key = _hash(binding.get("binding_key"))
        current_ids = _bounded_string_list(
            binding.get("current_line_ids", []), item_bytes=MAX_TOKEN_BYTES,
        )
        seed_ids = _bounded_string_list(
            binding.get("seed_snapshot_ids", []), item_bytes=MAX_TOKEN_BYTES,
        )
        if not event_id or binding_key is None:
            raise ValueError("provider binding identity is invalid")
        bindings[provider] = {
            "role": "official" if provider == official_provider else "sidecar",
            "provider_event_id": event_id,
            "current_line_ids": current_ids,
            "seed_observation_tokens": [_provider_token(provider, item) for item in seed_ids],
            "binding_key": binding_key,
            "window_started_at": _iso(provider_windows.get(provider)),
            "mature": provider in mature_providers,
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

    preclose_status = _enum(market.get("freshness_status"))
    if (
        not mature_providers.issubset(bindings)
        or not _provider_contract_valid(
            candidate_provider=official_provider, bindings=bindings,
            freshness=freshness, preclose_status=preclose_status,
        )
        or (preclose_status == "fresh" and participating != mature_providers)
    ):
        raise ValueError("provider roles or freshness are inconsistent")

    normalized_raw = _value(evaluation, "normalized_inputs", {})
    if not isinstance(normalized_raw, Mapping):
        raise ValueError("normalized inputs must be an object")
    normalized_inputs = _bounded_normalized_inputs(normalized_raw)
    candidate_part = _candidate_proof(
        candidate, official_provider=official_provider,
        official_binding_key=official_binding_key,
    )
    if not _candidate_inputs_match(
        candidate=candidate, candidate_part=candidate_part,
        normalized=normalized_inputs,
    ):
        raise ValueError("candidate and normalized inputs are inconsistent")
    supplied_families = _family_objects(evaluation)

    observations = market.get("observations")
    full_tokens = market.get("observation_ids")
    if (
        not isinstance(observations, list) or not isinstance(full_tokens, list)
        or len(observations) > MAX_SOURCE_TOKENS or len(full_tokens) > MAX_SOURCE_TOKENS
    ):
        raise ValueError("qualifying observation list is malformed")
    ordered_tokens = [_validated_token(token, raw_bindings) for token in full_tokens]
    observed_tokens = [
        _validated_token(row.get("id"), raw_bindings)
        for row in observations if isinstance(row, Mapping)
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

    ladder_tokens = [
        _validated_token(token, raw_bindings)
        for token in _bounded_string_list(
            exact.get("ladder_observation_ids", []),
            maximum=MAX_SOURCE_TOKENS, item_bytes=MAX_TOKEN_BYTES,
        )
    ]
    pivot_tokens = [
        _validated_token(token, raw_bindings)
        for token in _bounded_string_list(
            exact.get("direction_change_pivot_tokens", []),
            maximum=MAX_DECISIVE_TOKENS, item_bytes=MAX_TOKEN_BYTES,
        )
    ]
    latest_ladder_tokens = [
        _validated_token(token, raw_bindings)
        for token in _bounded_string_list(
            exact.get("latest_ladder_observation_tokens", []),
            maximum=MAX_DECISIVE_TOKENS, item_bytes=MAX_TOKEN_BYTES,
        )
    ]
    ladder_digest = _hash(exact.get("ladder_observation_token_sha256"))
    if (
        ladder_digest != hashlib.sha256("|".join(ladder_tokens).encode("utf-8")).hexdigest()
        or not set(pivot_tokens).issubset(ordered_tokens)
        or not set(latest_ladder_tokens).issubset(ladder_tokens)
    ):
        raise ValueError("decisive token provenance is inconsistent")
    decisive = _decisive_tokens(
        full_tokens=ordered_tokens, bindings=raw_bindings,
        pivot_tokens=pivot_tokens, latest_ladder_tokens=latest_ladder_tokens,
    )
    books_seen = _bounded_string_list(
        market.get("books_seen", []), maximum=32, item_bytes=64,
    )
    aggregation_reasons = list(_bounded_reasons(
        market.get("aggregation_reason_codes", []),
    ))
    window_reasons = list(_bounded_reasons(window.get("reason_codes", ())))
    fragment_reasons = list(_bounded_reasons(exact.get("reason_codes", [])))
    if preclose_status == "fresh":
        if aggregation_reasons or window_reasons or fragment_reasons:
            raise ValueError("fresh Preclose cannot retain unresolved reasons")
    elif (
        preclose_status != "pending"
        or not aggregation_reasons
        or aggregation_reasons != window_reasons
        or aggregation_reasons != fragment_reasons
    ):
        raise ValueError("pending Preclose reason is inconsistent")
    preclose_payload = {
        "qualifying_observation_count": len(ordered_tokens),
        "decisive_observation_tokens": decisive,
        "full_ordered_token_sha256": hashlib.sha256(
            "|".join(ordered_tokens).encode("utf-8")
        ).hexdigest(),
        "direction_change_pivot_tokens": pivot_tokens,
        "latest_ladder_observation_tokens": latest_ladder_tokens,
        "ladder_observation_token_sha256": ladder_digest,
        "first_observed_at": first_at,
        "last_observed_at": last_at,
        "freshness_status": _enum(market.get("freshness_status")) or "pending",
        "book_count": market.get("book_count"),
        "books_seen": books_seen,
        "toward_pick_count": market.get("toward_pick_count"),
        "away_from_pick_count": market.get("away_from_pick_count"),
        "side_price_movement": market.get("side_price_movement"),
        "broad_confirmation": market.get("broad_confirmation"),
        "reversal_book_count": market.get("reversal_book_count"),
        "volatile_book_count": market.get("volatile_book_count"),
        "best_is_off_market": market.get("best_is_off_market"),
        "score": None,
        "label": None,
        "positive_reasons": [],
        "risk_reasons": [],
        "reason_codes": aggregation_reasons,
    }
    semantic_decision, scored = _recompute_semantics(normalized_inputs, preclose_payload)
    if scored:
        preclose_payload.update({
            "score": scored["score"],
            "label": scored["label"],
            "positive_reasons": list(scored["positive_reasons"]),
            "risk_reasons": list(scored["risk_reasons"]),
        })
    if not _preclose_state_valid(preclose_payload):
        raise ValueError("Preclose state shape is invalid")
    supplied_family_payload = {
        name: _family_payload(vote) for name, vote in supplied_families.items()
    }
    supplied_decision = {
        "family_states": supplied_family_payload,
        "no_drag": _tri_state(_value(evaluation, "no_drag")),
        "selected_lane": _value(evaluation, "lane"),
        "selection_status": _value(evaluation, "selection_status"),
        "family_count": _integer(_value(evaluation, "family_count")),
        "maximum_family_count": _integer(_value(evaluation, "maximum_family_count")),
        "decisive_families": list(_value(evaluation, "decisive_families", ()) or ()),
    }
    for key, value in supplied_decision.items():
        if semantic_decision[key] != value:
            raise ValueError("evaluation decision does not match recomputed semantics")
    decision_reasons = list(_bounded_reasons(
        _value(evaluation, "reason_codes", ()) or (),
    ))
    return {
        "schema_version": V2_SCHEMA_VERSION,
        "bundle_id": selector_v2.BUNDLE_ID,
        "selector_fingerprint": selector_v2.FROZEN_SELECTOR_FINGERPRINT,
        "candidate": candidate_part,
        "artifact": artifact_part,
        "bindings": bindings,
        "freshness": freshness,
        "normalized_inputs": normalized_inputs,
        "preclose": preclose_payload,
        "decision": {
            **semantic_decision,
            "reason_codes": decision_reasons,
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
        if (
            _encoded_size(proof) > MAX_PROOF_APPLICATION_BYTES
            or postgres_jsonb_text_size(proof) > MAX_PROOF_DB_BYTES
        ):
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
    if (
        row and row.get("bundle_id") == "pregame_alternative_pick_methodology_v1"
        and isinstance(proof, Mapping) and not proof
    ):
        return True, ()
    reasons: list[str] = []
    if not isinstance(proof, Mapping):
        return False, ("evaluation_proof_not_object",)
    try:
        size = _encoded_size(proof)
    except (TypeError, ValueError, OverflowError):
        return False, ("evaluation_proof_not_json",)
    try:
        db_size = postgres_jsonb_text_size(proof)
    except (TypeError, ValueError, OverflowError):
        return False, ("evaluation_proof_not_json",)
    if db_size > MAX_PROOF_DB_BYTES:
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
        _hash(candidate.get("candidate_identity")) is None,
        not _text(candidate.get("slate_date")) or len(_text(candidate.get("slate_date"))) > 10,
        not _text(candidate.get("normalized_pitcher")) or len(_text(candidate.get("normalized_pitcher")).encode("utf-8")) > 128,
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
                    or any(
                        not _text(token).startswith(f"{provider}:")
                        or len(_text(token).encode("utf-8")) > MAX_TOKEN_BYTES
                        for token in seed_tokens
                    )
                ),
                not isinstance(current_ids, list),
                isinstance(current_ids, list) and (
                    len(current_ids) > MAX_DECISIVE_TOKENS
                    or any(len(_text(value).encode("utf-8")) > MAX_TOKEN_BYTES for value in current_ids)
                ),
            )):
                reasons.append("evaluation_proof_binding_invalid")

    freshness = proof.get("freshness")
    if isinstance(freshness, Mapping):
        for provider, value in freshness.items():
            if (
                provider not in bindings or not isinstance(value, Mapping)
                or value.get("freshness_status") not in {"fresh", "stale", "pending"}
                or _iso(value.get("latest_snapshot_at")) is None
            ):
                reasons.append("evaluation_proof_freshness_invalid")
    if (
        not is_diagnostic
        and isinstance(bindings, Mapping)
        and isinstance(freshness, Mapping)
        and not _provider_contract_valid(
            candidate_provider=_enum(candidate.get("line_source_provider")),
            bindings=bindings, freshness=freshness,
            preclose_status=_enum(preclose.get("freshness_status")),
        )
    ):
        reasons.append("evaluation_proof_binding_freshness_mismatch")

    count = _integer(preclose.get("qualifying_observation_count"))
    tokens = preclose.get("decisive_observation_tokens")
    if count is None or count < 0:
        reasons.append("evaluation_proof_count_invalid")
    token_values: list[str] = []
    try:
        if not isinstance(tokens, list) or len(tokens) > MAX_DECISIVE_TOKENS:
            raise ValueError
        token_values = [_validated_token(token, bindings) for token in tokens]
        if len(set(token_values)) != len(token_values):
            raise ValueError
    except (TypeError, ValueError):
        reasons.append("evaluation_proof_tokens_invalid")
    if _hash(preclose.get("full_ordered_token_sha256")) is None:
        reasons.append("evaluation_proof_token_digest_invalid")
    pivot_tokens = preclose.get("direction_change_pivot_tokens")
    latest_ladder_tokens = preclose.get("latest_ladder_observation_tokens")
    try:
        pivots = [_validated_token(token, bindings) for token in _bounded_string_list(
            pivot_tokens, maximum=MAX_DECISIVE_TOKENS, item_bytes=MAX_TOKEN_BYTES,
        )]
        latest = [_validated_token(token, bindings) for token in _bounded_string_list(
            latest_ladder_tokens, maximum=MAX_DECISIVE_TOKENS, item_bytes=MAX_TOKEN_BYTES,
        )]
        if not set((*pivots, *latest)).issubset(token_values):
            raise ValueError
    except (TypeError, ValueError):
        reasons.append("evaluation_proof_decisive_provenance_invalid")
    if _hash(preclose.get("ladder_observation_token_sha256")) is None:
        reasons.append("evaluation_proof_ladder_digest_invalid")
    if count and (_iso(preclose.get("first_observed_at")) is None or _iso(preclose.get("last_observed_at")) is None):
        reasons.append("evaluation_proof_observation_bounds_invalid")
    try:
        _bounded_string_list(preclose.get("books_seen", []), maximum=32, item_bytes=64)
        _bounded_reasons(preclose.get("positive_reasons", []))
        _bounded_reasons(preclose.get("risk_reasons", []))
        _bounded_reasons(preclose.get("reason_codes", []))
    except (TypeError, ValueError):
        reasons.append("evaluation_proof_preclose_bounds_invalid")
    try:
        if not _preclose_state_valid(preclose):
            reasons.append("evaluation_proof_preclose_state_invalid")
    except (TypeError, ValueError):
        reasons.append("evaluation_proof_preclose_state_invalid")

    family_states = decision.get("family_states")
    if not isinstance(family_states, Mapping) or set(family_states) != set(FAMILY_ORDER):
        reasons.append("evaluation_proof_family_states_invalid")
    else:
        for name in FAMILY_ORDER:
            if _enum(_value(family_states[name], "state")) not in {"agree", "disagree", "pending"}:
                reasons.append("evaluation_proof_family_states_invalid")
            try:
                _bounded_reasons(_value(family_states[name], "reason_codes", []))
            except (TypeError, ValueError):
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
    if (
        _integer(decision.get("family_count")) is None
        or _integer(decision.get("maximum_family_count")) is None
    ):
        reasons.append("evaluation_proof_family_count_invalid")
    if not isinstance(decision.get("preclose_required_for_selected_lane"), bool):
        reasons.append("evaluation_proof_preclose_dependency_invalid")
    try:
        _bounded_reasons(decision.get("reason_codes", []))
    except (TypeError, ValueError):
        reasons.append("evaluation_proof_decision_reasons_invalid")

    if is_diagnostic:
        diagnostic_inputs = proof.get("normalized_inputs")
        if (
            not isinstance(diagnostic_inputs, Mapping)
            or set(diagnostic_inputs) != set(ROW_BINDING_INPUT_FIELDS)
            or bindings != {} or freshness != {}
        ):
            reasons.append("evaluation_proof_diagnostic_invalid")
        elif any((
            _enum(diagnostic_inputs.get("side")) != _enum(candidate.get("side")),
            _enum(diagnostic_inputs.get("pitcher")) != _enum(candidate.get("normalized_pitcher")),
            _iso(diagnostic_inputs.get("game_time")) != _iso(candidate.get("game_time")),
            _number(diagnostic_inputs.get("k_line")) != _number(candidate.get("model_k_line")),
        )):
            reasons.append("evaluation_proof_candidate_input_mismatch")
    else:
        try:
            normalized = _bounded_normalized_inputs(proof.get("normalized_inputs", {}))
            if any((
                _enum(normalized.get("side")) != _enum(candidate.get("side")),
                _enum(normalized.get("pitcher")) != _enum(candidate.get("normalized_pitcher")),
                _iso(normalized.get("game_time")) != _iso(candidate.get("game_time")),
                _number(normalized.get("k_line")) != _number(candidate.get("model_k_line")),
            )):
                raise ValueError
            expected_decision, expected_score = _recompute_semantics(normalized, preclose)
            semantic_keys = (
                "support", "drag_core", "no_drag", "family_states",
                "consensus_core", "reentry_expansion", "selected_lane",
                "selection_status", "family_count", "maximum_family_count",
                "decisive_families", "preclose_required_for_selected_lane",
            )
            if any(decision.get(key) != expected_decision[key] for key in semantic_keys):
                raise ValueError
            expected_preclose = {
                "score": expected_score.get("score") if expected_score else None,
                "label": expected_score.get("label") if expected_score else None,
                "positive_reasons": list(expected_score.get("positive_reasons", [])) if expected_score else [],
                "risk_reasons": list(expected_score.get("risk_reasons", [])) if expected_score else [],
            }
            if any(preclose.get(key) != value for key, value in expected_preclose.items()):
                raise ValueError
        except (TypeError, ValueError, OverflowError):
            reasons.append("evaluation_proof_semantics_mismatch")

    if row is not None:
        if row.get("bundle_id") != selector_v2.BUNDLE_ID:
            reasons.append("evaluation_proof_row_bundle_mismatch")
        if row.get("selector_fingerprint") != proof.get("selector_fingerprint"):
            reasons.append("evaluation_proof_row_fingerprint_mismatch")
        expected_selector = {
            "consensus_core": selector_v2.CONSENSUS_SELECTOR_ID,
            "reentry_expansion": selector_v2.EXPANSION_SELECTOR_ID,
        }.get(lane)
        if row.get("selector_id") != expected_selector:
            reasons.append("evaluation_proof_row_selector_mismatch")
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
            ("source_artifact_generated_at", "source_artifact_generated_at", _iso),
            ("source_artifact_sha256", "source_artifact_sha256", _hash),
            ("source_artifact_byte_sha256", "source_artifact_byte_sha256", _hash),
        )
        if any(normalizer(row.get(row_key)) != normalizer(artifact.get(proof_key)) for row_key, proof_key, normalizer in artifact_checks):
            reasons.append("evaluation_proof_row_artifact_mismatch")
        normalized = proof.get("normalized_inputs")
        if not isinstance(normalized, Mapping) or any((
            _enum(row.get("side")) != _enum(normalized.get("side")),
            _enum(row.get("normalized_pitcher")) != _enum(normalized.get("pitcher")),
            _iso(row.get("game_time")) != _iso(normalized.get("game_time")),
            _number(row.get("model_k_line")) != _number(normalized.get("k_line")),
            _integer(row.get("official_odds")) != _integer(normalized.get("odds")),
            _enum(row.get("official_book")) != _enum(normalized.get("official_book")),
            _text(row.get("official_verdict")) != _text(normalized.get("official_verdict")),
        )):
            reasons.append("evaluation_proof_row_normalized_inputs_mismatch")
        if row.get("selection_status") != status or row.get("lane") != lane:
            reasons.append("evaluation_proof_row_decision_mismatch")
        if row.get("family_states") != family_states:
            reasons.append("evaluation_proof_row_family_states_mismatch")
        if _integer(row.get("family_count")) != _integer(decision.get("family_count")):
            reasons.append("evaluation_proof_row_family_count_mismatch")
        if row.get("evidence_observation_ids") != preclose.get("decisive_observation_tokens"):
            reasons.append("evaluation_proof_row_evidence_ids_mismatch")
        if _integer(row.get("evidence_observation_count")) != count:
            reasons.append("evaluation_proof_row_evidence_count_mismatch")
        if _iso(row.get("evidence_first_observed_at")) != _iso(preclose.get("first_observed_at")):
            reasons.append("evaluation_proof_row_evidence_first_mismatch")
        if _iso(row.get("evidence_last_observed_at")) != _iso(preclose.get("last_observed_at")):
            reasons.append("evaluation_proof_row_evidence_last_mismatch")
        if row.get("evidence_freshness_status") != preclose.get("freshness_status"):
            reasons.append("evaluation_proof_row_evidence_freshness_mismatch")
    result = tuple(dict.fromkeys(reasons))
    return not result, result
