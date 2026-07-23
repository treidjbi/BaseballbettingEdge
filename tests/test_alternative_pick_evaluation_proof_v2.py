from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timedelta

import pytest

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
        "official_verdict": "FIRE 1u",
    })
    return candidate


def _evaluation(**overrides):
    evaluation = {
        "selector_fingerprint": V2_FINGERPRINT,
        "family_states": {
            "base": {"state": "agree", "reason_codes": ["strong_base_strict_runtime_core"]},
            "anchor": {"state": "agree", "reason_codes": ["market_anchor_v2_confirmed"]},
            "preclose": {"state": "agree", "reason_codes": ["preclose_v2_confirmed"]},
            "reentry": {"state": "disagree", "reason_codes": ["reentry_predicate_false"]},
        },
        "no_drag": True,
        "lane": "consensus_core",
        "selection_status": "selected",
        "family_count": 3,
        "maximum_family_count": 3,
        "decisive_families": ("base", "anchor", "preclose"),
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
            "is_opener": False,
            "starter_mismatch": False,
            "last_pitch_count": 95,
            "days_since_last_start": 5,
            "workload_input_status": "complete",
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
        "observation_ids": list(tokens),
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
        "observation_ids": list(tokens),
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
        "movement_observation_ids": list(tokens),
        "ladder_observation_ids": list(tokens),
        "direction_change_pivot_tokens": [],
        "latest_ladder_observation_tokens": [tokens[-1]],
        "ladder_observation_token_sha256": hashlib.sha256(
            "|".join(tokens).encode("utf-8")
        ).hexdigest(),
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


def _pending_exact_preclose(reason="official_provider_immature"):
    reasons = [reason] if isinstance(reason, str) else list(reason)
    exact = _exact_preclose()
    market = copy.deepcopy(exact.market_evidence)
    market.update({
        "participating_providers": [],
        "observation_ids": [],
        "observations": [],
        "first_observed_at": None,
        "last_observed_at": None,
        "freshness_status": "pending",
        "book_count": None,
        "toward_pick_count": None,
        "away_from_pick_count": None,
        "side_price_movement": None,
        "broad_confirmation": None,
        "reversal_book_count": None,
        "volatile_book_count": None,
        "best_is_off_market": None,
        "aggregation_reason_codes": reasons,
    })
    window = copy.deepcopy(exact.evidence_window)
    window.update({
        "ready": False,
        "observation_ids": [],
        "observation_count": 0,
        "first_observed_at": None,
        "last_observed_at": None,
        "freshness_status": "pending",
        "reason_codes": tuple(reasons),
        "bound_observations": [],
    })
    fragment = copy.deepcopy(exact.proof_fragment)
    fragment_exact = fragment["exact_preclose"]
    fragment_exact.update({
        "movement_observation_ids": [],
        "ladder_observation_ids": [],
        "direction_change_pivot_tokens": [],
        "latest_ladder_observation_tokens": [],
        "ladder_observation_token_sha256": hashlib.sha256(b"").hexdigest(),
        "provider_freshness": {},
        "ladder": None,
        "reason_codes": reasons,
    })
    return ExactPrecloseResult(market, window, fragment)


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
    assert proof["decision"]["family_count"] == 3
    assert proof["decision"]["maximum_family_count"] == 3
    assert proof["decision"]["selected_lane"] == "consensus_core"
    assert proof["decision"]["preclose_required_for_selected_lane"] is False
    assert proof_v2.validate_evaluation_proof_v2(proof=proof) == (True, ())


@pytest.mark.parametrize(
    ("anchor_labels", "malformed"),
    ((None, False), (None, True)),
)
def test_v2_pending_anchor_is_preserved_and_does_not_veto_base_plus_preclose(
    anchor_labels, malformed,
):
    evaluation = _evaluation()
    evaluation["normalized_inputs"]["anchor_labels"] = anchor_labels
    evaluation["normalized_inputs"]["anchor_metadata_malformed"] = malformed
    evaluation["family_states"]["anchor"] = {
        "state": "pending", "reason_codes": ["anchor_dependency_pending"],
    }
    evaluation["family_count"] = 2
    evaluation["maximum_family_count"] = 3
    evaluation["decisive_families"] = ("base", "preclose")

    built = _build(evaluation=evaluation)

    assert built.selection_safe is True
    assert built.proof["normalized_inputs"]["anchor_labels"] is None
    assert built.proof["normalized_inputs"]["anchor_metadata_malformed"] is malformed
    assert built.proof["decision"]["family_states"]["anchor"]["state"] == "pending"
    assert built.proof["decision"]["selected_lane"] == "consensus_core"
    assert built.proof["decision"]["selection_status"] == "selected"


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


def test_v2_decisive_tokens_include_real_pivots_latest_ladder_and_reject_retired_prefixes():
    exact = _exact_preclose()
    exact.proof_fragment["exact_preclose"]["direction_change_pivot_tokens"] = [
        exact.market_evidence["observation_ids"][2]
    ]
    exact.proof_fragment["exact_preclose"]["ladder_observation_ids"].append("propline:ladder-latest")
    exact.proof_fragment["exact_preclose"]["latest_ladder_observation_tokens"] = ["propline:ladder-latest"]
    exact.proof_fragment["exact_preclose"]["ladder_observation_token_sha256"] = hashlib.sha256(
        "|".join(exact.proof_fragment["exact_preclose"]["ladder_observation_ids"]).encode("utf-8")
    ).hexdigest()
    built = _build(exact_preclose=exact)

    assert built.selection_safe is True
    assert exact.market_evidence["observation_ids"][2] in built.proof["preclose"]["decisive_observation_tokens"]
    assert "propline:ladder-latest" in built.proof["preclose"]["decisive_observation_tokens"]
    assert built.proof["preclose"]["ladder_observation_token_sha256"] == exact.proof_fragment["exact_preclose"]["ladder_observation_token_sha256"]

    retired = copy.deepcopy(exact)
    retired.proof_fragment["exact_preclose"]["direction_change_pivot_tokens"] = ["boltodds:retired"]
    rejected = _build(exact_preclose=retired)
    assert rejected.selection_safe is False
    assert rejected.reason_codes == ("evaluation_proof_invalid",)


def test_v2_proof_is_under_the_application_working_ceiling():
    built = _build(exact_preclose=_exact_preclose(token_count=500))
    encoded = json.dumps(
        built.proof, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    ).encode("utf-8")

    assert built.selection_safe is True
    assert len(encoded) <= proof_v2.MAX_PROOF_APPLICATION_BYTES
    assert proof_v2.MAX_PROOF_APPLICATION_BYTES < proof_v2.MAX_PROOF_DB_BYTES


def test_v2_oversized_or_malformed_proof_forces_a_valid_pending_diagnostic():
    oversized_exact = _exact_preclose()
    for provider, binding in oversized_exact.proof_fragment["exact_preclose"]["bindings_by_provider"].items():
        binding["current_line_ids"] = [
            f"{index:02d}" + provider[0] * (proof_v2.MAX_TOKEN_BYTES - 2)
            for index in range(32)
        ]
        binding["seed_snapshot_ids"] = [
            f"{index:02d}" + provider[-1] * (proof_v2.MAX_TOKEN_BYTES - 2)
            for index in range(32)
        ]
    oversized = _build(exact_preclose=oversized_exact)
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


@pytest.mark.parametrize(
    ("candidate_change", "proof_change"),
    (
        ({"line_source_provider": None}, None),
        ({"line_source_provider": "boltodds"}, None),
        ({"line_source_provider": "propline"}, None),
        (None, {"source_artifact_path": "dashboard/data/processed/other.json"}),
        (None, {"source_artifact_byte_sha256": "f" * 64}),
    ),
)
def test_v2_builder_requires_exact_official_provider_and_artifact_binding(candidate_change, proof_change):
    candidate = _candidate()
    if candidate_change:
        candidate.update(candidate_change)
    exact = _exact_preclose()
    if proof_change:
        exact.proof_fragment["exact_preclose"].update(proof_change)

    built = _build(candidate=candidate, exact_preclose=exact)

    assert built.selection_safe is False
    assert built.reason_codes == ("evaluation_proof_invalid",)


@pytest.mark.parametrize(
    "mutate",
    (
        lambda exact: exact.market_evidence.update(participating_providers=["propline"]),
        lambda exact: exact.proof_fragment["exact_preclose"]["provider_freshness"]["therundown"].update(freshness_status="stale"),
        lambda exact: exact.market_evidence.update(participating_providers=["therundown"]),
    ),
)
def test_v2_builder_requires_exact_official_maturity_and_matching_freshness_keys(mutate):
    exact = _exact_preclose()
    mutate(exact)

    built = _build(exact_preclose=exact)

    assert built.selection_safe is False
    assert built.reason_codes == ("evaluation_proof_invalid",)


def test_v2_pending_preclose_retains_the_exact_unresolved_reason():
    exact = _pending_exact_preclose()
    exact.proof_fragment["exact_preclose"]["reason_codes"] = ["different_reason"]
    evaluation = _evaluation()
    evaluation["family_states"]["preclose"] = {
        "state": "pending", "reason_codes": ["official_provider_immature"],
    }
    evaluation["family_count"] = 2
    evaluation["maximum_family_count"] = 3
    evaluation["decisive_families"] = ("base", "anchor")

    built = _build(evaluation=evaluation, exact_preclose=exact)

    assert built.selection_safe is False
    assert built.reason_codes == ("evaluation_proof_invalid",)


@pytest.mark.parametrize(
    "mutate",
    (
        lambda proof: proof["bindings"]["propline"].update(role="official"),
        lambda proof: proof["bindings"]["therundown"].update(role="sidecar"),
        lambda proof: proof["freshness"].pop("propline"),
    ),
)
def test_v2_validator_enforces_exact_roles_and_freshness_membership(mutate):
    proof = copy.deepcopy(_build().proof)
    mutate(proof)

    valid, reasons = proof_v2.validate_evaluation_proof_v2(proof=proof)

    assert valid is False
    assert any("binding" in reason or "freshness" in reason for reason in reasons)


def test_v2_pending_preclose_keeps_unresolved_aggregates_null():
    exact = _pending_exact_preclose()
    evaluation = _evaluation()
    evaluation["family_states"]["preclose"] = {
        "state": "pending", "reason_codes": ["official_provider_immature"],
    }
    evaluation["family_count"] = 2
    evaluation["maximum_family_count"] = 3
    evaluation["decisive_families"] = ("base", "anchor")
    built = _build(evaluation=evaluation, exact_preclose=exact)

    assert built.selection_safe is True
    for field in (
        "book_count", "toward_pick_count", "away_from_pick_count",
        "side_price_movement", "broad_confirmation", "reversal_book_count",
        "volatile_book_count", "best_is_off_market", "score", "label",
    ):
        assert built.proof["preclose"][field] is None
    assert built.proof["preclose"]["reason_codes"] == ["official_provider_immature"]

    changed = copy.deepcopy(built.proof)
    changed["preclose"]["book_count"] = 0
    changed["preclose"]["best_is_off_market"] = False
    assert proof_v2.validate_evaluation_proof_v2(proof=changed)[0] is False


def test_v2_real_selector_pending_dependencies_build_selection_safe_proof():
    reasons = ("official_provider_immature", "exact_ladder_missing")
    exact = _pending_exact_preclose(reasons)
    exact.market_evidence["candidate_identity"] = {
        "slate_date": "2026-07-22",
        "game_time": GAME_TIME,
        "pitcher": "tarik skubal",
        "side": "over",
        "k_line": 6.5,
        "provider": "therundown",
    }
    evaluation = proof_v2.selector_v2.evaluate_alternative_pick_v2(
        pitcher={
            "pitcher": "Tarik Skubal",
            "team": "DET",
            "opp_team": "PIT",
            "game_time": GAME_TIME,
            "k_line": 6.5,
            "best_over_odds": -120,
            "best_under_odds": -105,
            "best_over_book": "fanduel",
            "best_under_book": "draftkings",
            "avg_ip": 5.8,
            "recent_start_count": 5,
            "season_k9": 9.4,
            "recent_k9": 9.7,
            "career_k9": 9.1,
            "is_opener": False,
            "starter_mismatch": False,
            "last_pitch_count": 95,
            "days_since_last_start": 5,
        },
        pick={
            "side": "over",
            "display_verdict": "FIRE 1u",
            "edge": 0.035,
            "adj_ev": 0.09,
            "quality_gate_level": "clean",
            "model_win_prob": 0.56,
            "market_anchor_selector": {"labels": ["market_anchor_strict"]},
        },
        exact_evidence=exact.market_evidence,
        slate_date="2026-07-22",
        is_tracked=True,
        source_artifact_path="dashboard/data/processed/today.json",
        source_payload_sha256=_artifact()["payload_sha256"],
        source_artifact_byte_sha256="b" * 64,
        observed_at=OBSERVED_AT,
    )

    built = _build(evaluation=evaluation, exact_preclose=exact)

    assert evaluation.family_states["preclose"].reason_codes == reasons
    assert built.selection_safe is True
    assert built.proof["decision"]["selected_lane"] == evaluation.lane
    assert built.proof["decision"]["selection_status"] == evaluation.selection_status
    assert built.proof["decision"]["family_states"] == {
        name: {
            "state": vote.state,
            "reason_codes": list(vote.reason_codes),
        }
        for name, vote in evaluation.family_states.items()
    }


@pytest.mark.parametrize(
    "mutate",
    (
        lambda proof: proof["preclose"].update(book_count=-1),
        lambda proof: proof["preclose"].update(best_is_off_market=None),
        lambda proof: proof["preclose"].update(reversal_book_count=1, volatile_book_count=0),
        lambda proof: proof["preclose"].update(first_observed_at="2026-07-22T20:20:00+00:00"),
    ),
)
def test_v2_fresh_preclose_requires_complete_consistent_shape(mutate):
    proof = copy.deepcopy(_build().proof)
    mutate(proof)

    valid, reasons = proof_v2.validate_evaluation_proof_v2(proof=proof)

    assert valid is False
    assert "evaluation_proof_preclose_state_invalid" in reasons


@pytest.mark.parametrize(
    ("candidate_change", "input_change"),
    (
        ({}, {"side": "under"}),
        ({}, {"pitcher": "other pitcher"}),
        ({}, {"game_time": "2026-07-22T23:30:00+00:00"}),
        ({}, {"k_line": 7.5}),
        ({}, {"odds": -115}),
        ({}, {"official_book": "draftkings"}),
        ({}, {"official_verdict": "LEAN"}),
    ),
)
def test_v2_builder_binds_normalized_candidate_and_display_inputs(candidate_change, input_change):
    candidate = _candidate(**candidate_change)
    evaluation = _evaluation()
    evaluation["normalized_inputs"].update(input_change)

    built = _build(candidate=candidate, evaluation=evaluation)

    assert built.selection_safe is False
    assert built.reason_codes == ("evaluation_proof_invalid",)
    assert proof_v2.validate_evaluation_proof_v2(proof=built.proof) == (True, ())


@pytest.mark.parametrize(
    "mutate",
    (
        lambda proof: proof["normalized_inputs"].update(adjusted_ev=0.9),
        lambda proof: proof["preclose"].update(score=proof["preclose"]["score"] + 1),
        lambda proof: proof["preclose"].update(label="weak_preclose_clv_proxy"),
        lambda proof: proof["decision"]["family_states"]["base"].update(state="disagree"),
        lambda proof: proof["decision"].update(support="false"),
        lambda proof: proof["decision"].update(drag_core="true"),
        lambda proof: proof["decision"].update(no_drag="false"),
        lambda proof: proof["decision"].update(consensus_core="false"),
        lambda proof: proof["decision"].update(reentry_expansion="true"),
        lambda proof: proof["decision"].update(family_count=2),
        lambda proof: proof["decision"].update(maximum_family_count=4),
        lambda proof: proof["decision"].update(decisive_families=["base"]),
        lambda proof: proof["decision"].update(preclose_required_for_selected_lane=True),
    ),
)
def test_v2_validator_recomputes_family_preclose_and_lane_semantics(mutate):
    proof = copy.deepcopy(_build().proof)
    mutate(proof)

    valid, reasons = proof_v2.validate_evaluation_proof_v2(proof=proof)

    assert valid is False
    assert "evaluation_proof_semantics_mismatch" in reasons


@pytest.mark.parametrize(
    ("field", "malformed_value"),
    (
        *((field, 123) for field in sorted(proof_v2.NORMALIZED_TEXT_INPUT_FIELDS)),
        *((field, "0.035") for field in sorted(proof_v2.NORMALIZED_NUMBER_INPUT_FIELDS)),
        *((field, "-120") for field in sorted(proof_v2.NORMALIZED_INTEGER_INPUT_FIELDS)),
        *((field, 1) for field in sorted(proof_v2.NORMALIZED_BOOLEAN_INPUT_FIELDS)),
    ),
)
def test_v2_validator_fails_closed_for_malformed_normalized_scalar_types(
    field, malformed_value,
):
    proof = copy.deepcopy(_build().proof)
    proof["normalized_inputs"][field] = malformed_value

    valid, reasons = proof_v2.validate_evaluation_proof_v2(proof=proof)

    assert valid is False
    assert "evaluation_proof_semantics_mismatch" in reasons


def test_v2_proof_requires_workload_inputs_with_exact_scalar_contracts():
    workload_fields = {
        "is_opener", "starter_mismatch", "last_pitch_count",
        "days_since_last_start", "workload_input_status",
    }
    assert workload_fields.issubset(proof_v2.NORMALIZED_INPUT_FIELDS)

    for field in workload_fields:
        proof = copy.deepcopy(_build().proof)
        proof["normalized_inputs"].pop(field)
        valid, reasons = proof_v2.validate_evaluation_proof_v2(proof=proof)
        assert valid is False
        assert "evaluation_proof_semantics_mismatch" in reasons

    malformed_values = {
        "is_opener": 0,
        "starter_mismatch": "false",
        "last_pitch_count": True,
        "days_since_last_start": -1,
        "workload_input_status": "unknown",
    }
    for field, malformed in malformed_values.items():
        proof = copy.deepcopy(_build().proof)
        proof["normalized_inputs"][field] = malformed
        valid, reasons = proof_v2.validate_evaluation_proof_v2(proof=proof)
        assert valid is False
        assert "evaluation_proof_semantics_mismatch" in reasons


def test_v2_zero_rest_flows_from_selector_through_selection_safe_proof():
    exact = _pending_exact_preclose(("official_provider_immature", "exact_ladder_missing"))
    exact.market_evidence["candidate_identity"] = {
        "slate_date": "2026-07-22",
        "game_time": GAME_TIME,
        "pitcher": "tarik skubal",
        "side": "over",
        "k_line": 6.5,
        "provider": "therundown",
    }
    evaluation = proof_v2.selector_v2.evaluate_alternative_pick_v2(
        pitcher={
            "pitcher": "Tarik Skubal",
            "team": "DET",
            "opp_team": "PIT",
            "game_time": GAME_TIME,
            "k_line": 6.5,
            "best_over_odds": -120,
            "best_under_odds": -105,
            "best_over_book": "fanduel",
            "best_under_book": "draftkings",
            "avg_ip": 5.8,
            "recent_start_count": 5,
            "season_k9": 9.4,
            "recent_k9": 9.7,
            "career_k9": 9.1,
            "is_opener": False,
            "starter_mismatch": False,
            "last_pitch_count": 95,
            "days_since_last_start": 0,
        },
        pick={
            "side": "over",
            "display_verdict": "FIRE 1u",
            "edge": 0.035,
            "adj_ev": 0.09,
            "quality_gate_level": "clean",
            "model_win_prob": 0.56,
            "market_anchor_selector": {"labels": ["market_anchor_strict"]},
        },
        exact_evidence=exact.market_evidence,
        slate_date="2026-07-22",
        is_tracked=True,
        source_artifact_path="dashboard/data/processed/today.json",
        source_payload_sha256=_artifact()["payload_sha256"],
        source_artifact_byte_sha256="b" * 64,
        observed_at=OBSERVED_AT,
    )

    built = _build(evaluation=evaluation, exact_preclose=exact)

    assert evaluation.normalized_inputs["days_since_last_start"] == 0
    assert evaluation.normalized_inputs["leash_risk_bucket"] == "medium"
    assert built.selection_safe is True
    assert proof_v2.validate_evaluation_proof_v2(proof=built.proof) == (True, ())


@pytest.mark.parametrize(
    ("status", "reason"),
    (
        ("missing", "workload_inputs_missing"),
        ("malformed", "workload_inputs_malformed"),
    ),
)
def test_v2_proof_recomputes_incomplete_workload_as_pending(status, reason):
    proof = copy.deepcopy(_build().proof)
    proof["normalized_inputs"]["is_opener"] = None
    proof["normalized_inputs"]["workload_input_status"] = status

    expected, _ = proof_v2._recompute_semantics(
        proof["normalized_inputs"], proof["preclose"],
    )

    assert expected["family_states"]["base"] == {
        "state": "pending", "reason_codes": [reason],
    }
    assert expected["family_states"]["reentry"] == {
        "state": "pending", "reason_codes": [reason],
    }


def _consistent_noncomplete_workload_proof(
    *, field: str, status: str, include_null: bool,
):
    proof = copy.deepcopy(_build().proof)
    proof["normalized_inputs"][field] = -1
    proof["normalized_inputs"]["workload_input_status"] = status
    if include_null:
        proof["normalized_inputs"]["is_opener"] = None
    expected, _ = proof_v2._recompute_semantics(
        proof["normalized_inputs"], proof["preclose"],
    )
    proof["decision"].update(expected)
    proof["decision"]["reason_codes"] = [f"workload_inputs_{status}"]
    return proof


@pytest.mark.parametrize("field", ("last_pitch_count", "days_since_last_start"))
def test_v2_proof_rejects_negative_workload_integer_labeled_missing(field):
    proof = _consistent_noncomplete_workload_proof(
        field=field, status="missing", include_null=True,
    )

    valid, reasons = proof_v2.validate_evaluation_proof_v2(proof=proof)

    assert valid is False
    assert "evaluation_proof_semantics_mismatch" in reasons


@pytest.mark.parametrize("field", ("last_pitch_count", "days_since_last_start"))
def test_v2_proof_accepts_negative_workload_integer_labeled_malformed(field):
    proof = _consistent_noncomplete_workload_proof(
        field=field, status="malformed", include_null=False,
    )

    assert proof_v2.validate_evaluation_proof_v2(proof=proof) == (True, ())


def test_v2_proof_rejects_changed_raw_workload_without_matching_decision():
    proof = copy.deepcopy(_build().proof)
    proof["normalized_inputs"]["last_pitch_count"] = None

    valid, reasons = proof_v2.validate_evaluation_proof_v2(proof=proof)

    assert valid is False
    assert "evaluation_proof_semantics_mismatch" in reasons


@pytest.mark.parametrize(
    ("updates", "case"),
    (
        ({"is_opener": True}, "opener_requires_high_leash_and_opener_archetype"),
        ({"last_pitch_count": 105}, "high_pitch_count_requires_medium_leash"),
        ({"opportunity_bucket": "short_leash"}, "short_opportunity_requires_matching_buckets"),
        ({"pitcher_archetype_bucket": "opener_or_mismatch"}, "orphan_opener_archetype"),
        ({"pitcher_archetype_bucket": "short_leash"}, "orphan_short_leash_archetype"),
    ),
)
def test_v2_proof_rejects_semantically_unbound_workload_buckets(updates, case):
    proof = copy.deepcopy(_build().proof)
    proof["normalized_inputs"].update(updates)

    valid, reasons = proof_v2.validate_evaluation_proof_v2(proof=proof)

    assert valid is False, case
    assert "evaluation_proof_semantics_mismatch" in reasons


@pytest.mark.parametrize(
    "updates",
    (
        {
            "is_opener": True,
            "leash_risk_bucket": "high",
            "pitcher_archetype_bucket": "opener_or_mismatch",
        },
        {
            "starter_mismatch": True,
            "leash_risk_bucket": "high",
            "pitcher_archetype_bucket": "opener_or_mismatch",
        },
        {
            "last_pitch_count": 105,
            "leash_risk_bucket": "medium",
        },
        {
            "days_since_last_start": 3,
            "leash_risk_bucket": "medium",
        },
        {
            "opportunity_bucket": "short_leash",
            "leash_risk_bucket": "high",
            "pitcher_archetype_bucket": "short_leash",
        },
    ),
)
def test_v2_proof_accepts_workload_values_with_matching_derived_buckets(updates):
    proof = copy.deepcopy(_build().proof)
    proof["normalized_inputs"].update(updates)

    assert proof_v2.validate_evaluation_proof_v2(proof=proof) == (True, ())


def test_v2_worst_case_valid_proof_fits_postgres_jsonb_text_ceiling():
    evaluation = _evaluation()
    reason = "r" * proof_v2.MAX_REASON_BYTES
    evaluation["reason_codes"] = tuple([reason] * proof_v2.MAX_REASON_COUNT)
    evaluation["normalized_inputs"]["anchor_labels"] = [
        "market_anchor_strict",
        *[
            f"{index:02d}" + "a" * (proof_v2.MAX_LABEL_BYTES - 2)
            for index in range(proof_v2.MAX_LABEL_COUNT - 1)
        ],
    ]
    built = _build(evaluation=evaluation, exact_preclose=_exact_preclose(token_count=500))

    assert built.selection_safe is True
    assert proof_v2.postgres_jsonb_text_size(built.proof) <= proof_v2.MAX_PROOF_DB_BYTES
    assert proof_v2.validate_evaluation_proof_v2(proof=built.proof) == (True, ())


def test_postgres_jsonb_size_estimator_expands_large_finite_numbers():
    compact = len(json.dumps({"value": 1e308}).encode("utf-8"))

    estimated = proof_v2.postgres_jsonb_text_size({"value": 1e308})

    assert compact < 32
    assert estimated > 300


def test_v2_diagnostic_sanitizes_oversized_identity_fields_and_revalidates():
    candidate = _candidate()
    candidate.update({
        "candidate_identity": "x" * 100_000,
        "normalized_pitcher": "y" * 100_000,
        "line_source_provider": "boltodds",
    })
    artifact = _artifact()
    artifact.update({"path": "z" * 100_000, "byte_sha256": "invalid"})

    built = _build(candidate=candidate, artifact=artifact)

    assert built.selection_safe is False
    assert built.reason_codes == ("evaluation_proof_invalid",)
    assert proof_v2.postgres_jsonb_text_size(built.proof) <= proof_v2.MAX_PROOF_DB_BYTES
    assert proof_v2.validate_evaluation_proof_v2(proof=built.proof) == (True, ())
