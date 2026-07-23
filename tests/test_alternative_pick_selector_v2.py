import copy
import itertools
import json

from market_infra import alternative_pick_selector as v1
from market_infra import alternative_pick_selector_v2 as selector


V2_BUNDLE_ID = "pregame_alternative_pick_methodology_v2"
V2_CONSENSUS_ID = "no_drag_distinct_family_consensus_core_v2"
V2_EXPANSION_ID = "moderate_edge_quality_reentry_expansion_v2"
V2_FINGERPRINT = "23bacff0fa923685ae52c5a9cfbadfb9f5902fb64d91759cfe9b4b1169a221c4"


def _vote(state: str) -> selector.FamilyVote:
    return selector.FamilyVote(state, (f"{state}_fixture",))


def _complete_inputs(**overrides):
    values = {
        "pitcher": {
            "pitcher": "Test Pitcher", "team": "ARI", "opp_team": "LAD",
            "game_time": "2026-07-21T23:10:00Z", "k_line": 5.5,
            "best_over_odds": -115, "best_under_odds": -105,
            "best_over_book": "FanDuel", "best_under_book": "DraftKings", "avg_ip": 5.8,
            "recent_start_count": 5, "season_k9": 9.4, "recent_k9": 9.7,
            "career_k9": 9.1,
        },
        "pick": {
            "side": "over", "display_verdict": "FIRE 1u", "edge": 0.035,
            "adj_ev": 0.09, "quality_gate_level": "clean", "model_win_prob": 0.56,
            "market_anchor_selector": {"labels": ["market_anchor_core"]},
        },
        "exact_evidence": {
            "provider": "therundown_propline", "toward_pick_count": 3,
            "away_from_pick_count": 0, "book_count": 3, "best_is_off_market": False,
            "reversal_book_count": 0, "volatile_book_count": 0, "freshness_status": "fresh",
            "observation_ids": ["snap-a", "snap-b"],
            "first_observed_at": "2026-07-21T22:20:00Z",
            "last_observed_at": "2026-07-21T22:40:00Z",
            "candidate_became_current_at": "2026-07-21T22:15:00Z",
            "candidate_identity": {
                "slate_date": "2026-07-21", "game_time": "2026-07-21T23:10:00Z",
                "pitcher": "Test Pitcher", "side": "over", "k_line": 5.5,
                "provider": "therundown_propline",
            },
            "observations": [
                {"id": "snap-a", "observed_at": "2026-07-21T22:20:00Z"},
                {"id": "snap-b", "observed_at": "2026-07-21T22:40:00Z"},
            ],
        },
        "slate_date": "2026-07-21", "is_tracked": True,
        "source_artifact_path": "dashboard/data/processed/today.json",
        "source_payload_sha256": "a" * 64,
        "source_artifact_byte_sha256": "b" * 64,
        "observed_at": "2026-07-21T22:40:00Z",
    }
    values.update(overrides)
    return values


def _evaluate(**overrides):
    return selector.evaluate_alternative_pick_v2(**_complete_inputs(**overrides))


def test_v2_manifest_has_new_bundle_and_selector_ids():
    assert selector.BUNDLE_ID == V2_BUNDLE_ID
    assert selector.CONSENSUS_SELECTOR_ID == V2_CONSENSUS_ID
    assert selector.EXPANSION_SELECTOR_ID == V2_EXPANSION_ID
    assert selector.MANIFEST["bundle_id"] == V2_BUNDLE_ID


def test_v2_manifest_fingerprint_is_frozen():
    manifest = json.loads(selector.MANIFEST_PATH.read_text(encoding="utf-8"))
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert selector.selector_fingerprint() == selector.sha256_hex(canonical)
    assert selector.FROZEN_SELECTOR_FINGERPRINT == V2_FINGERPRINT
    assert selector.selector_fingerprint() == V2_FINGERPRINT


def test_v2_manifest_preserves_v1_thresholds_weights_and_precedence():
    v1_manifest = json.loads(v1.MANIFEST_PATH.read_text(encoding="utf-8"))
    for field in ("serialization", "field_precedence", "enum_normalization", "artifact_provenance", "provider_allow_list", "thresholds", "preclose_score_weights", "timing_and_freeze"):
        assert selector.MANIFEST[field] == v1_manifest[field]
    assert selector.MANIFEST["null_behavior"]["absent_anchor_metadata"] == "pending"
    assert selector.MANIFEST["family_predicates"]["preclose"] == "base_support AND strong_preclose_clv_proxy AND exact_candidate_bound_evidence"


def test_v1_manifest_ids_and_fingerprint_are_unchanged():
    assert v1.BUNDLE_ID == "pregame_alternative_pick_methodology_v1"
    assert v1.CONSENSUS_SELECTOR_ID == "no_drag_distinct_family_consensus_core_v1"
    assert v1.EXPANSION_SELECTOR_ID == "moderate_edge_quality_reentry_expansion_v1"
    assert v1.selector_fingerprint() == v1.FROZEN_SELECTOR_FINGERPRINT == "f8f7ccf652b8eda4860d07798bc4673920b0b9d727552bc7e2e6547d478b4579"


def test_tri_and_or_not_cover_all_three_valued_combinations():
    expected_and = {(True, True): True, (True, False): False, (True, None): None, (False, True): False, (False, False): False, (False, None): False, (None, True): None, (None, False): False, (None, None): None}
    expected_or = {(True, True): True, (True, False): True, (True, None): True, (False, True): True, (False, False): False, (False, None): None, (None, True): True, (None, False): None, (None, None): None}
    for values in itertools.product((True, False, None), repeat=2):
        assert selector.tri_and(*values) is expected_and[values]
        assert selector.tri_or(*values) is expected_or[values]
    assert [selector.tri_not(value) for value in (True, False, None)] == [False, True, None]


def test_absent_or_malformed_anchor_metadata_is_pending():
    absent_strict, absent_core = selector.parse_anchor_primitives_v2({})
    assert absent_strict.state == absent_core.state == "pending"
    strict, core = selector.parse_anchor_primitives_v2({"market_anchor_selector": {"labels": "not-a-list"}})
    assert strict.state == core.state == "pending"


def test_evaluation_preserves_absent_and_malformed_anchor_for_proof_recomputation():
    for raw_anchor, malformed in ((None, False), ({"labels": "not-a-list"}, True)):
        inputs = _complete_inputs()
        if raw_anchor is None:
            inputs["pick"].pop("market_anchor_selector")
        else:
            inputs["pick"]["market_anchor_selector"] = raw_anchor

        evaluation = selector.evaluate_alternative_pick_v2(**inputs)

        assert evaluation.normalized_inputs["anchor_labels"] is None
        assert evaluation.normalized_inputs["anchor_metadata_malformed"] is malformed
        assert evaluation.family_states["anchor"].state == "pending"
        assert evaluation.family_states["base"].state == "agree"
        assert evaluation.family_states["preclose"].state == "agree"
        assert evaluation.lane == "consensus_core"
        assert evaluation.selection_status == "selected"


def test_anchor_uses_strict_or_base_and_core_short_circuits():
    assert selector.compose_anchor_v2(_vote("pending"), _vote("agree"), _vote("pending")).state == "agree"
    assert selector.compose_anchor_v2(_vote("agree"), _vote("disagree"), _vote("agree")).state == "agree"
    assert selector.compose_anchor_v2(_vote("disagree"), _vote("disagree"), _vote("pending")).state == "disagree"


def test_preclose_uses_base_and_raw_preclose_short_circuits():
    assert selector.compose_preclose_v2(_vote("disagree"), _vote("pending")).state == "disagree"
    assert selector.compose_preclose_v2(_vote("pending"), _vote("disagree")).state == "disagree"
    assert selector.compose_preclose_v2(_vote("agree"), _vote("agree")).state == "agree"


def test_drag_core_is_true_on_any_confirmed_drag_and_false_only_when_all_are_false():
    assert selector.drag_core_v2({"edge": 0.07, "model_market_relationship": "unknown", "source_fire_verdict": "", "side": ""}).state == "true"
    assert selector.drag_core_v2({"edge": 0.03, "model_market_relationship": "model_agrees_with_favorite", "source_fire_verdict": "LEAN", "side": "over"}).state == "false"
    assert selector.drag_core_v2({"edge": None, "model_market_relationship": "unknown", "source_fire_verdict": "", "side": ""}).state == "pending"


def test_no_drag_uses_support_and_not_drag_with_three_valued_short_circuits():
    assert selector.no_drag_v2(_vote("disagree"), _vote("disagree"), selector.PredicateVote("pending", ())).state == "false"
    assert selector.no_drag_v2(_vote("pending"), _vote("pending"), selector.PredicateVote("true", ())).state == "false"
    assert selector.no_drag_v2(_vote("agree"), _vote("pending"), selector.PredicateVote("false", ())).state == "true"


def test_consensus_selects_with_two_agreements_and_nonessential_pending():
    families = {"base": _vote("agree"), "anchor": _vote("agree"), "preclose": _vote("pending"), "reentry": _vote("pending")}
    lanes = selector.evaluate_lanes_v2(families, selector.PredicateVote("true", ()))
    assert (lanes.lane, lanes.selection_status, lanes.family_count, lanes.maximum_family_count) == ("consensus_core", "selected", 2, 4)


def test_consensus_is_false_when_maximum_possible_count_is_below_two():
    families = {name: _vote("disagree") for name in selector.FAMILY_ORDER}
    families["base"] = _vote("agree")
    lanes = selector.evaluate_lanes_v2(families, selector.PredicateVote("pending", ()))
    assert lanes.consensus_core.state == "false"
    assert lanes.selection_status == "not_selected"


def test_reentry_selects_with_preclose_pending_when_no_drag_is_false():
    families = {"base": _vote("disagree"), "anchor": _vote("pending"), "preclose": _vote("pending"), "reentry": _vote("agree")}
    lanes = selector.evaluate_lanes_v2(families, selector.PredicateVote("false", ()))
    assert (lanes.lane, lanes.selection_status) == ("reentry_expansion", "selected")


def test_pending_never_increments_family_count():
    families = {"base": _vote("agree"), "anchor": _vote("pending"), "preclose": _vote("pending"), "reentry": _vote("disagree")}
    lanes = selector.evaluate_lanes_v2(families, selector.PredicateVote("pending", ()))
    assert (lanes.family_count, lanes.maximum_family_count) == (1, 3)


def test_lanes_are_disjoint_for_every_family_truth_table_combination():
    for states in itertools.product(("agree", "disagree", "pending"), repeat=4):
        families = dict(zip(selector.FAMILY_ORDER, map(_vote, states)))
        for no_drag in ("true", "false", "pending"):
            lanes = selector.evaluate_lanes_v2(families, selector.PredicateVote(no_drag, ()))
            assert not (lanes.consensus_core.state == "true" and lanes.reentry_expansion.state == "true")
            assert lanes.lane in {None, "consensus_core", "reentry_expansion"}


def test_base_and_reentry_match_v1_for_complete_inputs():
    inputs = _complete_inputs()
    v1_evaluation = v1.evaluate_alternative_pick(
        pitcher=inputs["pitcher"], pick=inputs["pick"], market_evidence=inputs["exact_evidence"],
        slate_date=inputs["slate_date"], is_tracked=inputs["is_tracked"],
        source_artifact_path=inputs["source_artifact_path"], source_payload_sha256=inputs["source_payload_sha256"],
        source_artifact_byte_sha256=inputs["source_artifact_byte_sha256"], observed_at=inputs["observed_at"],
    )
    v2_evaluation = selector.evaluate_alternative_pick_v2(**inputs)
    assert v2_evaluation.family_states["base"].state == v1_evaluation.family_states["base"].state
    assert v2_evaluation.family_states["reentry"].state == v1_evaluation.family_states["reentry"].state


def test_forbidden_result_and_clv_fields_do_not_change_v2_output():
    original = _evaluate()
    altered = _complete_inputs()
    altered["pick"] = copy.deepcopy(altered["pick"])
    altered["pick"].update({"result": "loss", "pnl": -99, "final_clv": -10, "closing_price": 500})
    assert selector.evaluate_alternative_pick_v2(**altered) == original


def test_missing_v2_runtime_primitive_is_pending_not_false_or_zero():
    inputs = _complete_inputs()
    del inputs["pick"]["edge"]
    presence = selector.validate_runtime_primitives_v2(pitcher=inputs["pitcher"], pick=inputs["pick"], exact_evidence=inputs["exact_evidence"])
    evaluation = selector.evaluate_alternative_pick_v2(**inputs)
    assert "edge" in presence.missing
    assert evaluation.family_states["base"].state == "pending"


def test_explicit_false_and_zero_remain_distinct_from_missing():
    inputs = _complete_inputs()
    inputs["pick"]["edge"] = 0.0
    inputs["exact_evidence"]["best_is_off_market"] = False
    presence = selector.validate_runtime_primitives_v2(pitcher=inputs["pitcher"], pick=inputs["pick"], exact_evidence=inputs["exact_evidence"])
    assert "edge" not in presence.missing
    assert "best_is_off_market" not in presence.missing
    assert presence.values["edge"] == 0.0
    assert presence.values["best_is_off_market"] is False


def test_selector_never_uses_v1_default_coercion_for_v2_decision():
    inputs = _complete_inputs()
    inputs["pick"]["locked_adj_ev"] = 0.0
    del inputs["pick"]["adj_ev"]
    evaluation = selector.evaluate_alternative_pick_v2(**inputs)
    assert evaluation.normalized_inputs["adjusted_ev"] == 0.0
    assert evaluation.family_states["base"].state == "disagree"


def test_ineligible_untracked_or_pass_rows_never_select_a_lane():
    for overrides, reason in (({"is_tracked": False}, "untracked_pick"), ({"pick": {**_complete_inputs()["pick"], "display_verdict": "PASS"}}, "pass_verdict")):
        evaluation = _evaluate(**overrides)
        assert not evaluation.eligible
        assert reason in evaluation.eligibility_reason_codes
        assert evaluation.lane is None
        assert evaluation.selection_status == "not_selected"


def test_v2_adjusted_ev_zero_does_not_fall_through_to_a_later_value():
    inputs = _complete_inputs()
    inputs["pick"] = {**inputs["pick"], "locked_adj_ev": 0.0, "adj_ev": 0.09}
    evaluation = selector.evaluate_alternative_pick_v2(**inputs)
    assert evaluation.primitive_presence.values["adjusted_ev"] == 0.0
    assert evaluation.normalized_inputs["adjusted_ev"] == 0.0
    assert evaluation.family_states["base"].state == "disagree"


def test_preclose_requires_bounded_times_and_approved_provider():
    invalid_bounds = _complete_inputs()
    invalid_bounds["exact_evidence"] = {**invalid_bounds["exact_evidence"], "first_observed_at": "2026-07-21T22:19:00Z"}
    invalid_provider = _complete_inputs()
    invalid_provider["exact_evidence"] = {**invalid_provider["exact_evidence"], "provider": "boltodds", "candidate_identity": {**invalid_provider["exact_evidence"]["candidate_identity"], "provider": "boltodds"}}
    for inputs, reason in ((invalid_bounds, "preclose_observation_bounds_invalid"), (invalid_provider, "preclose_provider_unsupported")):
        evaluation = selector.evaluate_alternative_pick_v2(**inputs)
        assert evaluation.family_states["preclose"].state == "pending"
        assert reason in evaluation.reason_codes


def test_invalid_explicit_relationship_or_skepticism_is_pending_not_coerced():
    for pick in ({**_complete_inputs()["pick"], "model_market_relationship": "maybe"}, {**_complete_inputs()["pick"], "large_edge_skepticism_flag": "false"}):
        evaluation = _evaluate(pick=pick)
        assert evaluation.family_states["base"].state == "pending"
        assert evaluation.family_states["reentry"].state == "pending"


def test_v2_eligibility_requires_candidate_line_hash_and_provider_consistency():
    cases = (
        ({"pick": {**_complete_inputs()["pick"], "official_k_line": 6.5}}, "line_mismatch"),
        ({"pick": {**_complete_inputs()["pick"], "source_payload_sha256": "c" * 64}}, "artifact_hash_mismatch"),
    )
    for overrides, reason in cases:
        evaluation = _evaluate(**overrides)
        assert not evaluation.eligible
        assert reason in evaluation.eligibility_reason_codes
        assert evaluation.lane is None

    unsupported = _evaluate(exact_evidence={**_complete_inputs()["exact_evidence"], "provider": "boltodds", "candidate_identity": {**_complete_inputs()["exact_evidence"]["candidate_identity"], "provider": "boltodds"}})
    assert unsupported.eligible
    assert unsupported.family_states["preclose"].state == "pending"
    assert "preclose_provider_unsupported" in unsupported.reason_codes


def test_missing_exact_evidence_selects_consensus_with_preclose_pending():
    evaluation = _evaluate(exact_evidence=None)
    assert evaluation.eligible
    assert evaluation.family_states["preclose"].state == "pending"
    assert evaluation.lane == "consensus_core"
    assert evaluation.selection_status == "selected"


def test_zero_adjusted_ev_reaches_real_lean_4_5_base_decision():
    inputs = _complete_inputs()
    inputs["pitcher"] = {**inputs["pitcher"], "k_line": 4.5}
    inputs["pick"] = {**inputs["pick"], "display_verdict": "LEAN", "locked_adj_ev": 0.0}
    evaluation = selector.evaluate_alternative_pick_v2(**inputs)
    assert evaluation.normalized_inputs["adjusted_ev"] == 0.0
    assert evaluation.family_states["base"].state == "agree"


def test_preclose_score_uses_canonical_zero_and_nonzero_adjusted_ev_boundaries():
    row = {
        "edge": 0.03, "model_no_vig_gap": 0.02, "price_sign": "minus",
        "quality_gate_level": "clean", "bet_timing_window": "pre_30",
        "book_count": 3, "best_is_off_market": False,
        "reversal_book_count": 0, "volatile_book_count": 0,
        "toward_pick_count": 2, "away_from_pick_count": 0, "side": "over",
        "model_market_relationship": "model_agrees_with_favorite",
        "adj_ev": 0.17,
    }
    zero = selector.preclose_proxy_score_v2(row, canonical_adjusted_ev=0.0)
    moderate = selector.preclose_proxy_score_v2(row, canonical_adjusted_ev=0.06)
    assert zero["score"] == moderate["score"] + 1
    assert "low_ev_market_validation" in zero["positive_reasons"]
    assert "moderate_ev_market_validation" in moderate["positive_reasons"]
