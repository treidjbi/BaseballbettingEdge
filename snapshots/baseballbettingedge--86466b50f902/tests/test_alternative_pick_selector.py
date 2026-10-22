import copy
import json

import pytest

from market_infra import alternative_pick_selector as selector


def _inputs(**overrides):
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
            "adj_ev": 0.09, "quality_gate_level": "clean",
            "model_win_prob": 0.56,
            "market_anchor_selector": {"labels": ["market_anchor_core"]},
        },
        "is_tracked": True,
        "market_evidence": {
            "provider": "therundown_propline", "toward_pick_count": 3,
            "away_from_pick_count": 0, "book_count": 3,
            "broad_confirmation": True, "best_is_off_market": False,
            "reversal_book_count": 0, "volatile_book_count": 0,
            "freshness_status": "fresh", "observation_ids": ["snap-a", "snap-b"],
            "first_observed_at": "2026-07-21T20:00:00Z",
            "last_observed_at": "2026-07-21T20:10:00Z",
            "candidate_became_current_at": "2026-07-21T19:55:00Z",
            "candidate_identity": {
                "slate_date": "2026-07-21", "game_time": "2026-07-21T23:10:00Z",
                "pitcher": "Test Pitcher", "side": "over", "k_line": 5.5,
                "provider": "therundown_propline",
            },
            "observations": [
                {"id": "snap-a", "observed_at": "2026-07-21T20:00:00Z"},
                {"id": "snap-b", "observed_at": "2026-07-21T20:10:00Z"},
            ],
        },
        "slate_date": "2026-07-21",
        "source_artifact_path": "dashboard/data/processed/today.json",
        "source_payload_sha256": "a" * 64,
        "source_artifact_byte_sha256": "b" * 64,
        "observed_at": "2026-07-21T20:10:00Z",
    }
    values.update(overrides)
    return values


def _evaluate(**overrides):
    return selector.evaluate_alternative_pick(**_inputs(**overrides))


def test_manifest_fingerprint_uses_canonical_json_with_explicit_nulls_and_string_thresholds():
    manifest = json.loads(selector.MANIFEST_PATH.read_text(encoding="utf-8"))
    canonical = json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assert selector.selector_fingerprint() == selector.sha256_hex(canonical)
    assert manifest["null_behavior"]["missing_required"] == "pending"
    assert isinstance(manifest["thresholds"]["edge_high_skepticism_min"], str)
    assert selector.FROZEN_SELECTOR_FINGERPRINT == "f8f7ccf652b8eda4860d07798bc4673920b0b9d727552bc7e2e6547d478b4579"
    assert selector.selector_fingerprint() == selector.FROZEN_SELECTOR_FINGERPRINT


def test_verdict_and_adjusted_ev_precedence_preserves_legacy_truthy_or_contract():
    assert selector.display_verdict({"display_verdict": "LEAN", "verdict": "FIRE 1u"}) == "LEAN"
    assert selector.source_fire_verdict({"raw_verdict": "PASS", "quality_actionable_verdict": "FIRE 2u"}) == "FIRE 2u"
    assert selector.adjusted_ev({"locked_adj_ev": 0.0, "adj_ev": 0.09, "ev": 0.10}) == 0.09
    assert selector.adjusted_ev({"locked_adj_ev": 0.11, "adj_ev": 0.09}) == 0.11
    assert selector.adjusted_ev({"locked_adj_ev": float("nan"), "adj_ev": 0.09}) is None


def test_runtime_features_are_derived_without_postgame_inputs():
    features = selector.derive_runtime_features(**{key: _inputs()[key] for key in ("pitcher", "pick", "market_evidence", "observed_at")})
    assert features["line_bucket"] == "5.5"
    assert features["price_sign"] == "minus"
    assert features["bet_timing_window"] == "early"
    assert features["model_market_relationship"] == "model_agrees_with_favorite"
    assert features["opportunity_bucket"] == "normal"
    assert features["pitcher_archetype_bucket"] == "standard_starter"
    assert features["large_edge_skepticism_flag"] is False
    assert features["model_no_vig_gap"] == pytest.approx(0.04916576381365123)
    assert features["official_book"] == "FanDuel"
    assert selector.derive_model_no_vig_gap(model_win_prob=None, over_odds=-115, under_odds=-105, side="over") is None


def test_runtime_no_vig_uses_canonical_win_prob_from_actual_ev_side_payload_shape():
    market = {
        "ev_over": {"edge": 0.035, "adj_ev": 0.09, "verdict": "FIRE 1u", "win_prob": 0.56},
        "ev_under": {"edge": 0.02, "adj_ev": 0.01, "verdict": "LEAN", "win_prob": 0.44},
    }
    pick = {**_inputs()["pick"], **market["ev_over"], "side": "over", "model_win_prob": None, "model_no_vig_gap": 0.99}
    features = selector.derive_runtime_features(pitcher=_inputs()["pitcher"], pick=pick, market_evidence=_inputs()["market_evidence"], observed_at=_inputs()["observed_at"])
    assert features["model_no_vig_gap"] == pytest.approx(0.04916576381365123)


def test_public_runtime_helpers_match_the_frozen_dataset_contract():
    assert selector.runtime_opportunity_bucket(6.3, 5) == "deep_starter"
    assert selector.runtime_leash_risk_bucket(is_opener=False, starter_mismatch=False, avg_ip=5.8, last_pitch_count=None, days_since_last_start=5) == "normal"
    assert selector.runtime_model_market_relationship("over", "under") == "model_fades_favorite"
    assert selector.runtime_pitcher_archetype_bucket(is_opener=False, starter_mismatch=False, opportunity_bucket="normal", season_k9=9.4, recent_k9=9.7, career_k9=9.1) == "standard_starter"


def test_eligible_universe_rejects_wrong_slate_untracked_pass_started_mismatch_and_unsupported_provider():
    cases = (
        ({"slate_date": "2026-07-20"}, "wrong_phoenix_slate_date"),
        ({"is_tracked": False}, "untracked_pick"),
        ({"is_tracked": "false"}, "untracked_pick"),
        ({"pick": {**_inputs()["pick"], "display_verdict": "PASS"}}, "pass_verdict"),
        ({"observed_at": "2026-07-21T23:10:00Z"}, "game_started"),
        ({"market_evidence": {**_inputs()["market_evidence"], "provider": "boltodds"}}, "unsupported_provider"),
        ({"pick": {**_inputs()["pick"], "official_k_line": 6.5}}, "line_mismatch"),
        ({"pick": {**_inputs()["pick"], "source_payload_sha256": "c" * 64}}, "artifact_hash_mismatch"),
    )
    for overrides, reason in cases:
        evaluation = _evaluate(**overrides)
        assert not evaluation.eligible
        assert reason in evaluation.eligibility_reason_codes


def test_eligible_universe_fails_closed_without_exact_today_artifact_provenance():
    cases = (
        ({"source_artifact_path": "dashboard/data/processed/2026-07-21.json"}, "artifact_path_not_current"),
        ({"source_payload_sha256": "not-a-sha"}, "artifact_payload_sha256_invalid"),
        ({"source_artifact_byte_sha256": ""}, "artifact_byte_sha256_invalid"),
        ({"pitcher": {key: value for key, value in _inputs()["pitcher"].items() if key != "team"}}, "candidate_identity_incomplete"),
    )
    for overrides, reason in cases:
        evaluation = _evaluate(**overrides)
        assert not evaluation.eligible
        assert reason in evaluation.eligibility_reason_codes


def test_absent_anchor_is_disagreement_but_malformed_anchor_is_pending():
    absent = _evaluate(pick={key: value for key, value in _inputs()["pick"].items() if key != "market_anchor_selector"})
    malformed = _evaluate(pick={**_inputs()["pick"], "market_anchor_selector": {"wrong": []}})
    assert absent.family_states["anchor"].state == "disagree"
    assert malformed.family_states["anchor"].state == "pending"


def test_four_families_return_distinct_votes_and_one_vote_per_family():
    evidence = {**_inputs()["market_evidence"], "candidate_became_current_at": "2026-07-21T22:15:00Z", "first_observed_at": "2026-07-21T22:20:00Z", "last_observed_at": "2026-07-21T22:40:00Z", "observations": [{"id": "snap-a", "observed_at": "2026-07-21T22:20:00Z"}, {"id": "snap-b", "observed_at": "2026-07-21T22:40:00Z"}]}
    evaluation = _evaluate(observed_at="2026-07-21T22:40:00Z", market_evidence=evidence, pick={**_inputs()["pick"], "market_anchor_selector": {"labels": ["market_anchor_core", "market_anchor_strict"]}})
    assert evaluation.family_states["base"].state == "agree"
    assert evaluation.family_states["anchor"].state == "agree"
    assert evaluation.family_states["preclose"].state == "agree"
    assert evaluation.family_states["reentry"].state == "agree"
    assert evaluation.family_count == 4


def test_incomplete_preclose_evidence_is_pending_and_cannot_qualify():
    evidence = {**_inputs()["market_evidence"], "observation_ids": ["snap-a"], "reversal_book_count": None}
    evaluation = _evaluate(market_evidence=evidence)
    assert evaluation.family_states["preclose"].state == "pending"
    assert evaluation.selection_status == "pending"
    assert evaluation.lane is None


def test_preclose_fails_pending_for_unbound_stale_or_reset_observations():
    cases = (
        ({"candidate_identity": None}, "preclose_candidate_identity_missing"),
        ({"freshness_status": "stale"}, "preclose_evidence_stale"),
        ({"candidate_became_current_at": "2026-07-21T20:05:00Z"}, "preclose_observation_before_current_candidate"),
        ({"observations": [{"id": "snap-a", "observed_at": "2026-07-21T20:00:00Z"}]}, "preclose_observations_immature"),
    )
    for overrides, reason in cases:
        evaluation = _evaluate(market_evidence={**_inputs()["market_evidence"], **overrides})
        assert evaluation.family_states["preclose"].state == "pending"
        assert reason in evaluation.reason_codes


def test_immature_preclose_evidence_stays_pending_even_when_base_disagrees():
    evaluation = _evaluate(
        pick={**_inputs()["pick"], "display_verdict": "LEAN"},
        market_evidence={**_inputs()["market_evidence"], "observation_ids": ["snap-a"]},
    )
    assert evaluation.family_states["base"].state == "disagree"
    assert evaluation.family_states["preclose"].state == "pending"


def test_preclose_requires_bounded_observation_times_and_exact_candidate_identity():
    missing_times = _evaluate(market_evidence={**_inputs()["market_evidence"], "last_observed_at": None})
    mismatch = _evaluate(market_evidence={**_inputs()["market_evidence"], "candidate_identity": {**_inputs()["market_evidence"]["candidate_identity"], "side": "under"}})
    assert missing_times.family_states["preclose"].state == "pending"
    assert "preclose_observation_times_missing" in missing_times.reason_codes
    assert mismatch.family_states["preclose"].state == "pending"
    assert "preclose_candidate_identity_mismatch" in mismatch.reason_codes


def test_unproved_no_drag_blocks_reentry_expansion():
    pick = {**_inputs()["pick"], "edge": None, "market_anchor_selector": None}
    evaluation = _evaluate(pick=pick)
    assert evaluation.family_states["reentry"].state == "pending"
    assert evaluation.no_drag is None
    assert evaluation.selection_status == "pending"


def test_missing_model_probability_or_reentry_source_inputs_are_pending_not_disagreement():
    missing_probability = _evaluate(pick={**_inputs()["pick"], "model_win_prob": None, "model_no_vig_gap": 0.99})
    missing_source = _evaluate(pick={**_inputs()["pick"], "display_verdict": "", "raw_verdict": "", "quality_actionable_verdict": ""})
    non_finite_ev = _evaluate(pick={**_inputs()["pick"], "locked_adj_ev": float("nan")})
    assert missing_probability.family_states["reentry"].state == "pending"
    assert missing_probability.normalized_inputs["model_no_vig_gap"] is None
    assert missing_source.family_states["reentry"].state == "pending"
    assert non_finite_ev.family_states["base"].state == "pending"
    assert non_finite_ev.family_states["reentry"].state == "pending"


def test_lanes_are_disjoint_for_consensus_and_reentry_expansion():
    evidence = {**_inputs()["market_evidence"], "candidate_became_current_at": "2026-07-21T22:15:00Z", "first_observed_at": "2026-07-21T22:20:00Z", "last_observed_at": "2026-07-21T22:40:00Z", "observations": [{"id": "snap-a", "observed_at": "2026-07-21T22:20:00Z"}, {"id": "snap-b", "observed_at": "2026-07-21T22:40:00Z"}]}
    consensus = _evaluate(observed_at="2026-07-21T22:40:00Z", market_evidence=evidence)
    expansion = _evaluate(
        observed_at="2026-07-21T22:40:00Z", market_evidence=evidence,
        pick={**_inputs()["pick"], "display_verdict": "LEAN", "raw_verdict": "FIRE 1u", "edge": 0.035, "market_anchor_selector": None},
    )
    assert consensus.lane == "consensus_core"
    assert expansion.lane == "reentry_expansion"
    assert not (consensus.lane == "consensus_core" and consensus.lane == "reentry_expansion")


def test_postgame_fields_have_no_effect_on_prospective_output():
    original = _evaluate()
    altered_pick = copy.deepcopy(_inputs()["pick"])
    altered_pick.update({"result": "loss", "pnl": -99, "final_clv": -10, "closing_price": 500})
    altered = _evaluate(pick=altered_pick)
    assert altered == original


def test_shared_predicates_match_golden_runtime_rows_without_a_research_ledger_constant():
    features = selector.derive_runtime_features(**{key: _inputs()[key] for key in ("pitcher", "pick", "market_evidence", "observed_at")})
    assert selector.strong_base_strict_plus_selective(features).state == "agree"
    assert selector.preclose_strong(features, _inputs()["market_evidence"]).state == "agree"
    assert selector.moderate_edge_quality_reentry(features).state == "agree"
    assert selector.prospective_ledger_seed() == {"rows": 0, "pnl": 0.0}


def test_preclose_requires_explicit_boolean_off_market_evidence_and_penalizes_true():
    inputs = _inputs()
    features = selector.derive_runtime_features(**{
        key: inputs[key] for key in ("pitcher", "pick", "market_evidence", "observed_at")
    })
    explicit_false = {**inputs["market_evidence"], "best_is_off_market": False}
    explicit_true = {**inputs["market_evidence"], "best_is_off_market": True}
    missing = {key: value for key, value in inputs["market_evidence"].items() if key != "best_is_off_market"}

    false_score = selector.preclose_proxy_score_from_row({**explicit_false, **features})
    true_score = selector.preclose_proxy_score_from_row({**explicit_true, **features})
    assert selector.preclose_strong(features, explicit_false).state == "agree"
    assert true_score["score"] < false_score["score"]
    assert "off_market_best_book" in true_score["risk_reasons"]
    for unavailable in (missing, {**missing, "best_is_off_market": "false"}, {**missing, "best_is_off_market": 0}):
        vote = selector.preclose_strong(features, unavailable)
        assert vote.state == "pending"
        assert "preclose_best_off_market_missing" in vote.reason_codes
