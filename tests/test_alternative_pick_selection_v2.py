from __future__ import annotations

import copy

import pytest

from market_infra import alternative_pick_evaluation_proof_v2 as proof_v2
from market_infra import alternative_pick_selection_state as v1_state
from market_infra import alternative_pick_selection_v2 as selection_v2
from market_infra.alternative_pick_preclose_v2 import ExactPrecloseResult
from market_infra.published_artifacts import canonical_payload_sha256


V2_BUNDLE_ID = "pregame_alternative_pick_methodology_v2"
V2_CONSENSUS_ID = "no_drag_distinct_family_consensus_core_v2"
V2_FINGERPRINT = "23bacff0fa923685ae52c5a9cfbadfb9f5902fb64d91759cfe9b4b1169a221c4"
GAME_TIME = "2026-07-22T23:00:00+00:00"
OBSERVED_AT = "2026-07-22T20:10:00+00:00"


def _candidate():
    candidate = v1_state.candidate_record(
        slate_date="2026-07-22", pitcher="Tarik Skubal", side="over",
        model_k_line=6.5, team="DET", opp_team="PIT", game_time=GAME_TIME,
        provider_posture="therundown_propline",
    )
    candidate.update({
        "line_source_provider": "therundown",
        "source_artifact_path": "dashboard/data/processed/today.json",
        "lock_source_artifact_path": "dashboard/data/processed/today.json",
        "official_odds": -120,
        "official_book": "fanduel",
        "official_verdict": "FIRE 1u",
    })
    return candidate


def _evaluation():
    return {
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
            "side": "over", "official_verdict": "FIRE 1u", "source_fire_verdict": "FIRE 1u",
            "pitcher": "tarik skubal", "game_time": GAME_TIME, "k_line": 6.5,
            "line_bucket": "6.5", "odds": -120, "official_book": "fanduel",
            "price_sign": "minus", "bet_timing_window": "pre_30",
            "model_market_relationship": "model_agrees_with_favorite",
            "model_no_vig_gap": 0.031, "edge": 0.035, "adjusted_ev": 0.09,
            "adjusted_ev_error": None, "quality_gate_level": "clean",
            "opportunity_bucket": "normal", "leash_risk_bucket": "normal",
            "pitcher_archetype_bucket": "standard", "large_edge_skepticism_flag": False,
            "is_opener": False, "starter_mismatch": False,
            "last_pitch_count": 95, "days_since_last_start": 5,
            "workload_input_status": "complete",
            "anchor_labels": ["market_anchor_strict"], "anchor_metadata_malformed": False,
            "observed_at": OBSERVED_AT,
        },
    }


def _exact_preclose():
    tokens = ["therundown:snap-1", "therundown:snap-2", "propline:snap-3"]
    times = [
        "2026-07-22T20:00:00+00:00",
        "2026-07-22T20:04:00+00:00",
        "2026-07-22T20:07:00+00:00",
    ]
    observations = [
        {"id": token, "observed_at": observed_at}
        for token, observed_at in zip(tokens, times)
    ]
    market = {
        "provider": "therundown", "participating_providers": ["therundown", "propline"],
        "candidate_became_current_at": "2026-07-22T19:55:00+00:00",
        "observation_ids": list(tokens), "observations": observations,
        "first_observed_at": times[0], "last_observed_at": times[-1],
        "freshness_status": "fresh", "book_count": 2,
        "books_seen": ["draftkings", "fanduel"], "toward_pick_count": 2,
        "away_from_pick_count": 0, "side_price_movement": "with_side",
        "broad_confirmation": False, "reversal_book_count": 0,
        "volatile_book_count": 0, "best_is_off_market": False,
        "aggregation_reason_codes": [],
    }
    window = {
        "ready": True, "first_current_at": "2026-07-22T19:55:00+00:00",
        "provider_window_started_at": {
            "therundown": "2026-07-22T19:55:00+00:00",
            "propline": "2026-07-22T19:56:00+00:00",
        },
        "observation_ids": list(tokens), "observation_count": 3,
        "first_observed_at": times[0], "last_observed_at": times[-1],
        "freshness_status": "fresh", "reason_codes": (),
        "bound_observations": observations,
    }
    exact = {
        "official_provider": "therundown", "official_binding_key": "d" * 64,
        "sidecar_binding_keys": {"propline": "e" * 64},
        "bindings_by_provider": {
            "therundown": {
                "provider": "therundown", "provider_event_id": "tr-event",
                "current_line_ids": ["101"], "seed_snapshot_ids": ["snap-1"],
                "mapped_game_times": [GAME_TIME], "binding_key": "d" * 64,
            },
            "propline": {
                "provider": "propline", "provider_event_id": "pl-event",
                "current_line_ids": ["202"], "seed_snapshot_ids": ["snap-3"],
                "mapped_game_times": [GAME_TIME], "binding_key": "e" * 64,
            },
        },
        "provider_window_started_at": window["provider_window_started_at"],
        "movement_observation_ids": list(tokens), "ladder_observation_ids": list(tokens),
        "direction_change_pivot_tokens": [],
        "latest_ladder_observation_tokens": [tokens[-1]],
        "ladder_observation_token_sha256": __import__("hashlib").sha256(
            "|".join(tokens).encode("utf-8")
        ).hexdigest(),
        "provider_freshness": {
            "therundown": {"latest_snapshot_at": times[1], "freshness_status": "fresh"},
            "propline": {"latest_snapshot_at": times[2], "freshness_status": "fresh"},
        },
        "ladder": {"best_is_off_market": False, "latest_snapshot_at": times[2], "freshness_status": "fresh"},
        "source_artifact_path": "dashboard/data/processed/today.json",
        "source_artifact_byte_sha256": "b" * 64, "reason_codes": [],
    }
    return ExactPrecloseResult(market, window, {"schema_version": "alternative_pick_preclose_v2", "exact_preclose": exact})


def _pending_exact_preclose():
    exact = _exact_preclose()
    market = {
        **exact.market_evidence,
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
        "aggregation_reason_codes": ["official_provider_immature"],
    }
    window = {
        **exact.evidence_window,
        "ready": False,
        "observation_ids": [],
        "observation_count": 0,
        "first_observed_at": None,
        "last_observed_at": None,
        "freshness_status": "pending",
        "reason_codes": ("official_provider_immature",),
        "bound_observations": [],
    }
    fragment = copy.deepcopy(exact.proof_fragment)
    fragment["exact_preclose"]["movement_observation_ids"] = []
    fragment["exact_preclose"]["ladder_observation_ids"] = []
    fragment["exact_preclose"]["direction_change_pivot_tokens"] = []
    fragment["exact_preclose"]["latest_ladder_observation_tokens"] = []
    fragment["exact_preclose"]["ladder_observation_token_sha256"] = __import__("hashlib").sha256(
        b""
    ).hexdigest()
    fragment["exact_preclose"]["provider_freshness"] = {}
    fragment["exact_preclose"]["ladder"] = None
    fragment["exact_preclose"]["reason_codes"] = ["official_provider_immature"]
    return ExactPrecloseResult(market, window, fragment)


def _artifact():
    payload = {"date": "2026-07-22", "pitchers": [{"pitcher": "Tarik Skubal"}]}
    return {
        "path": "dashboard/data/processed/today.json", "payload": payload,
        "payload_sha256": canonical_payload_sha256(payload), "byte_sha256": "b" * 64,
        "generated_at": "2026-07-22T20:05:00+00:00",
    }


def _proof_build(*, evaluation=None, exact=None):
    return proof_v2.build_evaluation_proof_v2(
        candidate=_candidate(), evaluation=evaluation or _evaluation(),
        exact_preclose=exact or _exact_preclose(), artifact=_artifact(),
    )


def _row(*, evaluation=None, exact=None, proof_build=None):
    evaluation = evaluation or _evaluation()
    exact = exact or _exact_preclose()
    return selection_v2.build_provisional_row_v2(
        candidate=_candidate(), evaluation=evaluation, exact_preclose=exact,
        proof_build=proof_build or _proof_build(evaluation=evaluation, exact=exact),
        artifact=_artifact(), observed_at=OBSERVED_AT,
    )


def _lock(candidate):
    return {
        "dedupe_key": "2026-07-22:tarik skubal:over", "slate_date": "2026-07-22",
        "normalized_pitcher": "tarik skubal", "side": "over", "locked_k_line": 6.5,
        "locked_odds": -120, "locked_book": "fanduel", "game_time": GAME_TIME,
        "status_at_capture": "due_now", "observed_at": OBSERVED_AT,
        "locked_at": OBSERVED_AT, "should_lock_at": OBSERVED_AT,
        "minutes_until_start": 30.0,
        "source_artifact_path": "dashboard/data/processed/today.json",
        "source_artifact_sha256": "b" * 64,
        "metadata": {"team": candidate["team"], "opp_team": candidate["opp_team"]},
    }


def test_v2_provisional_row_uses_only_v2_ids_and_valid_proof():
    row = _row()

    assert row is not None
    assert row["bundle_id"] == V2_BUNDLE_ID
    assert row["selector_id"] == V2_CONSENSUS_ID
    assert row["selector_fingerprint"] == V2_FINGERPRINT
    assert "_v1" not in row["bundle_id"] + row["selector_id"]
    assert proof_v2.validate_evaluation_proof_v2(proof=row["evaluation_proof"], row=row) == (True, ())
    assert row["evidence_observation_ids"] == row["evaluation_proof"]["preclose"]["decisive_observation_tokens"]
    assert row["evidence_observation_count"] == row["evaluation_proof"]["preclose"]["qualifying_observation_count"]
    assert row["evidence_first_observed_at"] == row["evaluation_proof"]["preclose"]["first_observed_at"]
    assert row["evidence_last_observed_at"] == row["evaluation_proof"]["preclose"]["last_observed_at"]


def test_v2_selected_row_can_retain_pending_nonessential_preclose():
    exact = _pending_exact_preclose()
    evaluation = _evaluation()
    evaluation["family_states"]["preclose"] = {"state": "pending", "reason_codes": ["official_provider_immature"]}
    evaluation["family_count"] = 2
    evaluation["maximum_family_count"] = 3
    evaluation["decisive_families"] = ("base", "anchor")
    row = _row(evaluation=evaluation, exact=exact, proof_build=_proof_build(evaluation=evaluation, exact=exact))

    assert row["selection_status"] == "selected"
    assert row["lane"] == "consensus_core"
    assert row["family_states"]["preclose"]["state"] == "pending"
    assert row["evaluation_proof"]["decision"]["preclose_required_for_selected_lane"] is False


def test_v2_frozen_row_preserves_evaluation_proof_exactly():
    provisional = _row()
    original = copy.deepcopy(provisional["evaluation_proof"])
    frozen = v1_state.build_frozen_row(
        provisional_row=provisional, lock_row=_lock(provisional), observed_at=OBSERVED_AT,
    )

    assert frozen is not None
    assert frozen["checkpoint"] == "frozen_pregame"
    assert frozen["evaluation_proof"] == original
    assert provisional["evaluation_proof"] == original


def test_v1_row_remains_valid_with_empty_evaluation_proof():
    valid, reasons = proof_v2.validate_evaluation_proof_v2(
        proof={}, row={"bundle_id": "pregame_alternative_pick_methodology_v1"},
    )

    assert valid is True
    assert reasons == ()


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("selector_id", None),
        ("bundle_id", "pregame_alternative_pick_methodology_v1"),
        ("selector_fingerprint", "f" * 64),
        ("candidate_identity", "f" * 64),
        ("slate_date", "2026-07-23"),
        ("normalized_pitcher", "other pitcher"),
        ("side", "under"),
        ("model_k_line", 7.5),
        ("game_time", "2026-07-22T23:30:00+00:00"),
        ("official_odds", -115),
        ("official_book", "draftkings"),
        ("official_verdict", "LEAN"),
        ("source_artifact_generated_at", "2026-07-22T20:06:00+00:00"),
        ("source_artifact_path", "dashboard/data/processed/other.json"),
        ("source_artifact_sha256", "f" * 64),
        ("source_artifact_byte_sha256", "e" * 64),
        ("family_states", {}),
        ("family_count", 0),
        ("evidence_observation_ids", []),
        ("evidence_observation_count", 0),
        ("evidence_first_observed_at", "2026-07-22T19:59:00+00:00"),
        ("evidence_last_observed_at", "2026-07-22T20:08:00+00:00"),
        ("evidence_freshness_status", "pending"),
        ("selection_status", "pending"),
        ("lane", None),
    ),
)
def test_v2_row_validation_binds_every_duplicated_persisted_field(field, value):
    row = _row()
    row[field] = value

    valid, reasons = proof_v2.validate_evaluation_proof_v2(
        proof=row["evaluation_proof"], row=row,
    )

    assert valid is False
    assert any(reason.startswith("evaluation_proof_row_") for reason in reasons)
