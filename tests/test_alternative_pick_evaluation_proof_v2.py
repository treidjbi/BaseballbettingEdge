from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timedelta

from market_infra import alternative_pick_evaluation_proof_v2 as proof_v2
from market_infra.alternative_pick_preclose_v2 import ExactPrecloseResult
from market_infra.alternative_pick_selection_state import candidate_record
from market_infra.published_artifacts import canonical_payload_sha256


V2_BUNDLE_ID = "pregame_alternative_pick_methodology_v2"
V2_FINGERPRINT = "23bacff0fa923685ae52c5a9cfbadfb9f5902fb64d91759cfe9b4b1169a221c4"
GAME_TIME = "2026-07-22T23:00:00+00:00"
OBSERVED_AT = "2026-07-22T20:10:00+00:00"


def _candidate(**overrides):
    values = {
        "slate_date": "2026-07-22",
        "pitcher": "Tarik Skubal",
        "side": "over",
        "model_k_line": 6.5,
        "team": "DET",
        "opp_team": "PIT",
        "game_time": GAME_TIME,
        "provider_posture": "therundown_propline",
    }
    values.update(overrides)
    candidate = candidate_record(**values)
    candidate.update({
        "line_source_provider": "therundown",
        "source_artifact_path": "dashboard/data/processed/today.json",
        "lock_source_artifact_path": "dashboard/data/processed/today.json",
        "official_odds": -120,
        "official_book": "fanduel",
    })
    return candidate


def _evaluation(**overrides):
    evaluation = {
        "selector_fingerprint": V2_FINGERPRINT,
        "family_states": {
            "base": {"state": "agree", "reason_codes": ["strong_base_strict_runtime_core"]},
            "anchor": {"state": "agree", "reason_codes": ["anchor_strict"]},
            "preclose": {"state": "pending", "reason_codes": ["preclose_evidence_stale"]},
            "reentry": {"state": "disagree", "reason_codes": ["reentry_predicate_false"]},
        },
        "no_drag": True,
        "lane": "consensus_core",
        "selection_status": "selected",
        "family_count": 2,
        "maximum_family_count": 3,
        "decisive_families": ("base", "anchor"),
        "reason_codes": ("consensus_core_selected",),
        "normalized_inputs": {
            "side": "over",
            "official_verdict": "FIRE 1u",
            "source_fire_verdict": "FIRE 1u",
            "pitcher": "tarik skubal",
            "game_time": GAME_TIME,
            "k_line": 6.5,
            "line_bucket": "6.5",
            "odds": -120,
            "official_book": "fanduel",
            "price_sign": "minus",
            "bet_timing_window": "pre_30",
            "model_market_relationship": "model_agrees_with_favorite",
            "model_no_vig_gap": 0.031,
            "edge": 0.035,
            "adjusted_ev": 0.09,
            "adjusted_ev_error": None,
            "quality_gate_level": "clean",
            "opportunity_bucket": "normal",
            "leash_risk_bucket": "normal",
            "pitcher_archetype_bucket": "standard",
            "large_edge_skepticism_flag": False,
            "anchor_labels": ["market_anchor_strict"],
            "anchor_metadata_malformed": False,
            "observed_at": OBSERVED_AT,
        },
    }
    evaluation.update(overrides)
    return evaluation


def _exact_preclose(*, token_count=6, proof_overrides=None, evidence_overrides=None):
    tokens = [f"therundown:snapshot-{index:03d}" for index in range(token_count)]
    first_observed_at = datetime.fromisoformat("2026-07-22T20:00:00+00:00")
    observations = [
        {"id": token, "observed_at": (first_observed_at + timedelta(seconds=index)).isoformat()}
        for index, token in enumerate(tokens)
    ]
    market_evidence = {
        "provider": "therundown",
        "participating_providers": ["therundown", "propline"],
        "candidate_became_current_at": "2026-07-22T19:55:00+00:00",
        "observation_ids": tokens,
        "observations": observations,
        "first_observed_at": observations[0]["observed_at"],
        "last_observed_at": observations[-1]["observed_at"],
        "freshness_status": "fresh",
        "book_count": 2,
        "books_seen": ["draftkings", "fanduel"],
        "toward_pick_count": 2,
        "away_from_pick_count": 0,
        "side_price_movement": "with_side",
        "broad_confirmation": False,
        "reversal_book_count": 0,
        "volatile_book_count": 0,
        "best_is_off_market": False,
        "aggregation_reason_codes": [],
    }
    market_evidence.update(evidence_overrides or {})
    evidence_window = {
        "ready": True,
        "first_current_at": "2026-07-22T19:55:00+00:00",
        "provider_window_started_at": {
            "therundown": "2026-07-22T19:55:00+00:00",
            "propline": "2026-07-22T19:56:00+00:00",
        },
        "observation_ids": tokens,
        "observation_count": token_count,
        "first_observed_at": observations[0]["observed_at"],
        "last_observed_at": observations[-1]["observed_at"],
        "freshness_status": "fresh",
        "reason_codes": (),
        "bound_observations": observations,
    }
    exact = {
        "official_provider": "therundown",
        "official_binding_key": "d" * 64,
        "sidecar_binding_keys": {"propline": "e" * 64},
        "bindings_by_provider": {
            "therundown": {
                "provider": "therundown",
                "provider_event_id": "tr-event",
                "current_line_ids": ["101"],
                "seed_snapshot_ids": ["snapshot-000"],
                "mapped_game_times": [GAME_TIME],
                "binding_key": "d" * 64,
            },
            "propline": {
                "provider": "propline",
                "provider_event_id": "pl-event",
                "current_line_ids": ["202"],
                "seed_snapshot_ids": ["snapshot-001"],
                "mapped_game_times": [GAME_TIME],
                "binding_key": "e" * 64,
            },
        },
        "provider_window_started_at": evidence_window["provider_window_started_at"],
        "movement_observation_ids": tokens,
        "ladder_observation_ids": tokens,
        "provider_freshness": {
            "therundown": {"latest_snapshot_at": observations[-1]["observed_at"], "freshness_status": "fresh"},
            "propline": {"latest_snapshot_at": observations[-1]["observed_at"], "freshness_status": "fresh"},
        },
        "ladder": {
            "best_is_off_market": False,
            "latest_snapshot_at": observations[-1]["observed_at"],
            "freshness_status": "fresh",
        },
        "source_artifact_path": "dashboard/data/processed/today.json",
        "source_artifact_byte_sha256": "b" * 64,
        "reason_codes": [],
    }
    exact.update(proof_overrides or {})
    return ExactPrecloseResult(
        market_evidence=market_evidence,
        evidence_window=evidence_window,
        proof_fragment={"schema_version": "alternative_pick_preclose_v2", "exact_preclose": exact},
    )


def _artifact():
    payload = {"date": "2026-07-22", "pitchers": [{"pitcher": "Tarik Skubal"}]}
    return {
        "path": "dashboard/data/processed/today.json",
        "payload": payload,
        "payload_sha256": canonical_payload_sha256(payload),
        "byte_sha256": "b" * 64,
        "generated_at": "2026-07-22T20:05:00+00:00",
    }


def _build(**overrides):
    values = {
        "candidate": _candidate(),
        "evaluation": _evaluation(),
        "exact_preclose": _exact_preclose(),
        "artifact": _artifact(),
    }
    values.update(overrides)
    return proof_v2.build_evaluation_proof_v2(**values)


def test_v2_proof_contains_recomputable_inputs_bindings_freshness_and_logic():
    built = _build()
    proof = built.proof

    assert built.selection_safe is True
    assert tuple(proof) == (
        "schema_version", "bundle_id", "selector_fingerprint", "candidate",
        "artifact", "bindings", "freshness", "normalized_inputs", "preclose", "decision",
    )
    assert proof["schema_version"] == "v2"
    assert proof["bundle_id"] == V2_BUNDLE_ID
    assert proof["candidate"] == {
        "candidate_identity": _candidate()["candidate_identity"],
        "slate_date": "2026-07-22",
        "normalized_pitcher": "tarik skubal",
        "side": "over",
        "model_k_line": 6.5,
        "game_time": GAME_TIME,
        "line_source_provider": "therundown",
        "official_binding_key": "d" * 64,
    }
    assert proof["bindings"]["therundown"]["role"] == "official"
    assert proof["bindings"]["propline"]["role"] == "sidecar"
    assert proof["freshness"]["therundown"]["freshness_status"] == "fresh"
    assert proof["normalized_inputs"] == _evaluation()["normalized_inputs"]
    assert proof["preclose"]["score"] == 11
    assert proof["preclose"]["label"] == "strong_preclose_clv_proxy"
    assert proof["decision"]["support"] == "true"
    assert proof["decision"]["drag_core"] == "false"
    assert proof["decision"]["no_drag"] == "true"
    assert proof["decision"]["consensus_core"] == "true"
    assert proof["decision"]["reentry_expansion"] == "false"
    assert proof["decision"]["selected_lane"] == "consensus_core"
    assert proof["decision"]["preclose_required_for_selected_lane"] is False
    assert proof_v2.validate_evaluation_proof_v2(proof=proof) == (True, ())


def test_v2_proof_uses_bounded_decisive_tokens_and_full_token_digest():
    exact = _exact_preclose(token_count=60)
    built = _build(exact_preclose=exact)
    preclose = built.proof["preclose"]
    full_tokens = exact.market_evidence["observation_ids"]

    assert preclose["qualifying_observation_count"] == 60
    assert len(preclose["decisive_observation_tokens"]) <= proof_v2.MAX_DECISIVE_TOKENS
    assert preclose["decisive_observation_tokens"][0] == full_tokens[0]
    assert preclose["decisive_observation_tokens"][-1] == full_tokens[-1]
    assert preclose["full_ordered_token_sha256"] == hashlib.sha256(
        "|".join(full_tokens).encode("utf-8")
    ).hexdigest()
    assert full_tokens[30] not in preclose["decisive_observation_tokens"]


def test_v2_proof_is_under_the_application_working_ceiling():
    built = _build(exact_preclose=_exact_preclose(token_count=500))
    encoded = json.dumps(
        built.proof, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")

    assert built.selection_safe is True
    assert len(encoded) <= proof_v2.MAX_PROOF_APPLICATION_BYTES
    assert proof_v2.MAX_PROOF_APPLICATION_BYTES < proof_v2.MAX_PROOF_DB_BYTES


def test_v2_oversized_or_malformed_proof_forces_a_valid_pending_diagnostic():
    oversized_evaluation = _evaluation()
    oversized_evaluation["normalized_inputs"] = {
        **oversized_evaluation["normalized_inputs"],
        "anchor_labels": ["x" * proof_v2.MAX_PROOF_APPLICATION_BYTES],
    }
    oversized = _build(evaluation=oversized_evaluation)
    malformed_exact = _exact_preclose(proof_overrides={"bindings_by_provider": ["not", "an", "object"]})
    malformed = _build(exact_preclose=malformed_exact)

    for built, reason in (
        (oversized, "evaluation_proof_oversized"),
        (malformed, "evaluation_proof_invalid"),
    ):
        assert built.selection_safe is False
        assert reason in built.reason_codes
        assert built.proof["decision"]["selection_status"] == "pending"
        assert built.proof["decision"]["selected_lane"] is None
        assert built.proof["decision"]["reason_codes"] == [reason]
        assert proof_v2.validate_evaluation_proof_v2(proof=built.proof) == (True, ())
        assert len(json.dumps(built.proof, separators=(",", ":")).encode("utf-8")) <= proof_v2.MAX_PROOF_APPLICATION_BYTES


def test_v2_proof_rejects_bundle_fingerprint_candidate_or_artifact_mismatch():
    built = _build()
    candidate = _candidate()
    artifact = _artifact()
    row = {
        **candidate,
        "bundle_id": V2_BUNDLE_ID,
        "selector_fingerprint": V2_FINGERPRINT,
        "source_artifact_path": artifact["path"],
        "source_artifact_sha256": artifact["payload_sha256"],
        "source_artifact_byte_sha256": artifact["byte_sha256"],
        "selection_status": "selected",
        "lane": "consensus_core",
    }
    mutations = (
        ("bundle", lambda proof: proof.update(bundle_id="wrong")),
        ("fingerprint", lambda proof: proof.update(selector_fingerprint="f" * 64)),
        ("candidate", lambda proof: proof["candidate"].update(candidate_identity="wrong")),
        ("binding", lambda proof: proof["candidate"].update(official_binding_key="f" * 64)),
        ("artifact", lambda proof: proof["artifact"].update(source_artifact_byte_sha256="f" * 64)),
        ("decision", lambda proof: proof["decision"]["family_states"]["base"].update(state="invalid")),
    )

    for label, mutate in mutations:
        changed = copy.deepcopy(built.proof)
        mutate(changed)
        valid, reasons = proof_v2.validate_evaluation_proof_v2(proof=changed, row=row)
        assert valid is False, label
        assert reasons, label
