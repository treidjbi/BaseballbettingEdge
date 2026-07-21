import copy
import json

from market_infra import alternative_pick_selector as selector


def _inputs(**overrides):
    values = {
        "pitcher": {
            "pitcher": "Test Pitcher", "team": "ARI", "opp_team": "LAD",
            "game_time": "2026-07-21T23:10:00Z", "k_line": 5.5,
            "best_over_odds": -115, "best_under_odds": -105, "avg_ip": 5.8,
            "recent_start_count": 5, "season_k9": 9.4, "recent_k9": 9.7,
            "career_k9": 9.1,
        },
        "pick": {
            "side": "over", "display_verdict": "FIRE 1u", "edge": 0.035,
            "adj_ev": 0.09, "quality_gate_level": "clean",
            "model_no_vig_gap": 0.05,
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


def test_verdict_and_adjusted_ev_precedence_preserves_legacy_truthy_or_contract():
    assert selector.display_verdict({"display_verdict": "LEAN", "verdict": "FIRE 1u"}) == "LEAN"
    assert selector.source_fire_verdict({"raw_verdict": "PASS", "quality_actionable_verdict": "FIRE 2u"}) == "FIRE 2u"
    assert selector.adjusted_ev({"locked_adj_ev": 0.0, "adj_ev": 0.09, "ev": 0.10}) == 0.09
    assert selector.adjusted_ev({"locked_adj_ev": 0.11, "adj_ev": 0.09}) == 0.11


def test_runtime_features_are_derived_without_postgame_inputs():
    features = selector.derive_runtime_features(**{key: _inputs()[key] for key in ("pitcher", "pick", "market_evidence", "observed_at")})
    assert features["line_bucket"] == "5.5"
    assert features["price_sign"] == "minus"
    assert features["bet_timing_window"] == "early"
    assert features["model_market_relationship"] == "model_agrees_with_favorite"
    assert features["opportunity_bucket"] == "normal"
    assert features["pitcher_archetype_bucket"] == "standard_starter"
    assert features["large_edge_skepticism_flag"] is False


def test_public_runtime_helpers_match_the_frozen_dataset_contract():
    assert selector.runtime_opportunity_bucket(6.3, 5) == "deep_starter"
    assert selector.runtime_leash_risk_bucket(is_opener=False, starter_mismatch=False, avg_ip=5.8, last_pitch_count=None, days_since_last_start=5) == "normal"
    assert selector.runtime_model_market_relationship("over", "under") == "model_fades_favorite"
    assert selector.runtime_pitcher_archetype_bucket(is_opener=False, starter_mismatch=False, opportunity_bucket="normal", season_k9=9.4, recent_k9=9.7, career_k9=9.1) == "standard_starter"


def test_eligible_universe_rejects_wrong_slate_untracked_pass_started_mismatch_and_unsupported_provider():
    cases = (
        ({"slate_date": "2026-07-20"}, "wrong_phoenix_slate_date"),
        ({"is_tracked": False}, "untracked_pick"),
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


def test_absent_anchor_is_disagreement_but_malformed_anchor_is_pending():
    absent = _evaluate(pick={key: value for key, value in _inputs()["pick"].items() if key != "market_anchor_selector"})
    malformed = _evaluate(pick={**_inputs()["pick"], "market_anchor_selector": {"wrong": []}})
    assert absent.family_states["anchor"].state == "disagree"
    assert malformed.family_states["anchor"].state == "pending"


def test_four_families_return_distinct_votes_and_one_vote_per_family():
    evidence = {**_inputs()["market_evidence"], "first_observed_at": "2026-07-21T22:20:00Z", "last_observed_at": "2026-07-21T22:40:00Z"}
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


def test_immature_preclose_evidence_stays_pending_even_when_base_disagrees():
    evaluation = _evaluate(
        pick={**_inputs()["pick"], "display_verdict": "LEAN"},
        market_evidence={**_inputs()["market_evidence"], "observation_ids": ["snap-a"]},
    )
    assert evaluation.family_states["base"].state == "disagree"
    assert evaluation.family_states["preclose"].state == "pending"


def test_preclose_requires_bounded_observation_times_and_exact_candidate_identity():
    missing_times = _evaluate(market_evidence={**_inputs()["market_evidence"], "last_observed_at": None})
    mismatch = _evaluate(market_evidence={**_inputs()["market_evidence"], "candidate_side": "under"})
    assert missing_times.family_states["preclose"].state == "pending"
    assert "preclose_observation_times_missing" in missing_times.reason_codes
    assert not mismatch.eligible
    assert "market_identity_mismatch" in mismatch.eligibility_reason_codes


def test_unproved_no_drag_blocks_reentry_expansion():
    pick = {**_inputs()["pick"], "edge": None, "market_anchor_selector": None}
    evaluation = _evaluate(pick=pick)
    assert evaluation.family_states["reentry"].state == "pending"
    assert evaluation.no_drag is None
    assert evaluation.selection_status == "pending"


def test_lanes_are_disjoint_for_consensus_and_reentry_expansion():
    evidence = {**_inputs()["market_evidence"], "first_observed_at": "2026-07-21T22:20:00Z", "last_observed_at": "2026-07-21T22:40:00Z"}
    consensus = _evaluate(observed_at="2026-07-21T22:40:00Z", market_evidence=evidence)
    expansion = _evaluate(
        observed_at="2026-07-21T22:40:00Z", market_evidence=evidence,
        pick={**_inputs()["pick"], "display_verdict": "LEAN", "raw_verdict": "FIRE 1u", "edge": 0.035, "market_anchor_selector": None},
    )
    assert consensus.lane == "consensus_core"
    assert expansion.lane in {None, "reentry_expansion"}
    assert not (consensus.lane == "consensus_core" and consensus.lane == "reentry_expansion")


def test_postgame_fields_have_no_effect_on_prospective_output():
    original = _evaluate()
    altered_pick = copy.deepcopy(_inputs()["pick"])
    altered_pick.update({"result": "loss", "pnl": -99, "final_clv": -10, "closing_price": 500})
    altered = _evaluate(pick=altered_pick)
    assert altered == original


def test_research_parity_anchors_are_not_a_prospective_ledger():
    anchors = selector.research_parity_anchors()
    assert anchors == {"base": 32.603, "preclose": 5.982, "combined": 38.585}
    assert selector.prospective_ledger_seed() == {"rows": 0, "pnl": 0.0}
