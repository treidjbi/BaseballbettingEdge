"""V2 provisional row shaping over the frozen V1 canonical row helpers."""

from __future__ import annotations

from typing import Any

from market_infra import alternative_pick_selection_state as v1_state
from market_infra.alternative_pick_evaluation_proof_v2 import (
    EvaluationProofBuild,
    _diagnostic_build,
    validate_evaluation_proof_v2,
)
from market_infra.alternative_pick_preclose_v2 import ExactPrecloseResult
from market_infra.alternative_pick_selector_v2 import (
    BUNDLE_ID,
    CONSENSUS_SELECTOR_ID,
    EXPANSION_SELECTOR_ID,
    FROZEN_SELECTOR_FINGERPRINT,
)


SELECTOR_IDS_BY_LANE = {
    "consensus_core": CONSENSUS_SELECTOR_ID,
    "reentry_expansion": EXPANSION_SELECTOR_ID,
}


def build_provisional_row_v2(
    *, candidate: dict[str, Any], evaluation: Any,
    exact_preclose: ExactPrecloseResult,
    proof_build: EvaluationProofBuild,
    artifact: dict[str, Any], observed_at: str,
) -> dict[str, Any] | None:
    """Build an isolated V2 row while preserving V1 identity and lock semantics."""
    if not isinstance(exact_preclose, ExactPrecloseResult):
        return None
    common = v1_state.build_provisional_row(
        candidate=candidate,
        evaluation=evaluation,
        evidence_window=exact_preclose.evidence_window,
        artifact=artifact,
        observed_at=observed_at,
    )
    if common is None:
        return None

    proof = proof_build.proof if isinstance(proof_build, EvaluationProofBuild) else {}
    proof_valid, _ = validate_evaluation_proof_v2(proof=proof)
    selected_safe = bool(
        isinstance(proof_build, EvaluationProofBuild)
        and proof_build.selection_safe
        and proof_valid
    )
    if not proof_valid:
        proof_build = _diagnostic_build(
            candidate=candidate, artifact=artifact, reason="evaluation_proof_invalid",
        )
        proof = proof_build.proof
    decision = proof["decision"]
    preclose = proof["preclose"]
    lane = decision["selected_lane"] if selected_safe else None
    selection_status = decision["selection_status"] if selected_safe else "pending"
    family_states = decision["family_states"]
    reason_codes = [
        *common.get("reason_codes", []),
        *decision.get("reason_codes", []),
        *proof_build.reason_codes,
    ]

    row = {
        **common,
        "bundle_id": BUNDLE_ID,
        "selector_id": SELECTOR_IDS_BY_LANE.get(lane),
        "selector_fingerprint": FROZEN_SELECTOR_FINGERPRINT,
        "lane": lane,
        "selection_status": selection_status,
        "family_states": family_states,
        "family_count": sum(
            value.get("state") == "agree"
            for value in family_states.values() if isinstance(value, dict)
        ),
        "reason_codes": list(dict.fromkeys(reason for reason in reason_codes if reason)),
        "evidence_observation_ids": list(preclose["decisive_observation_tokens"]),
        "evidence_observation_count": preclose["qualifying_observation_count"],
        "evidence_first_observed_at": preclose["first_observed_at"],
        "evidence_last_observed_at": preclose["last_observed_at"],
        "evidence_freshness_status": preclose["freshness_status"],
        "evaluation_proof": proof,
    }
    valid, _ = validate_evaluation_proof_v2(proof=proof, row=row)
    if valid:
        return row

    fallback = _diagnostic_build(
        candidate=candidate, artifact=artifact, reason="evaluation_proof_invalid",
    )
    proof = fallback.proof
    row.update({
        "selector_id": None,
        "lane": None,
        "selection_status": "pending",
        "family_states": proof["decision"]["family_states"],
        "family_count": 0,
        "reason_codes": list(dict.fromkeys((*row["reason_codes"], *fallback.reason_codes))),
        "evidence_observation_ids": [],
        "evidence_observation_count": 0,
        "evidence_first_observed_at": None,
        "evidence_last_observed_at": None,
        "evidence_freshness_status": "pending",
        "evaluation_proof": proof,
    })
    return row if validate_evaluation_proof_v2(proof=proof, row=row)[0] else None
