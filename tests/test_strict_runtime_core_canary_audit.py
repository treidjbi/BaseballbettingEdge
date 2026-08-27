import importlib
import json

import pytest


def _audit_module():
    try:
        return importlib.import_module(
            "analytics.diagnostics.strict_runtime_core_canary_audit"
        )
    except ModuleNotFoundError:
        pytest.fail("strict runtime core audit module is not implemented")


def candidate_row(**overrides):
    row = {
        "is_tracked_pick": True,
        "slate_date": "2026-07-30",
        "normalized_pitcher": "test pitcher",
        "side": "over",
        "result": "win",
        "pick_history_pnl": 0.90,
        "display_verdict": "FIRE 1u",
        "edge": 0.05,
        "locked_adj_ev": 0.10,
        "model_market_relationship": "model_agrees_with_favorite",
        "line_bucket": "5.5",
        "price_sign": "minus",
        "price_bucket": "-100 to -129",
        "quality_gate_level": "clean",
        "bet_timing_window": "pre_30",
        "leash_risk_bucket": "normal",
        "batter_handedness_mode": "path_b",
        "provider_era": "therundown_propline",
        "provider": "therundown+propline",
        "market_agreement_label": "agree",
        "preclose_clv_proxy_label": "strong",
        "final_clv_bucket": "beat_close_price",
    }
    row.update(overrides)
    return row


def test_rule_spec_and_fingerprint_are_frozen_literals():
    audit = _audit_module()

    assert audit.RULE_SPEC == {
        "selector_id": "strict_runtime_core_flat",
        "version": 1,
        "prospective_start": "2026-07-30",
        "verdict": "FIRE*",
        "keep_labels": [
            "keep_fire_market_agreed_moderate_ev",
            "keep_fire_over_moderate_ev_normal_leash",
        ],
        "drag_labels": [
            "cap_fire_under_market_fade",
            "cap_high_raw_edge",
            "cap_market_fade",
        ],
        "post_start_policy": "exclude",
        "outcome_fields_used": [],
        "formula": (
            "FIRE AND (keep_fire_market_agreed_moderate_ev OR "
            "keep_fire_over_moderate_ev_normal_leash) AND NOT "
            "(cap_high_raw_edge OR cap_market_fade OR "
            "cap_fire_under_market_fade)"
        ),
    }
    assert audit.RULE_FINGERPRINT == (
        "6d07a98031a8b26915ad34fc031def76d26519850dc476db723d37f25a8d9905"
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {},
        {
            "side": "under",
            "leash_risk_bucket": "short",
            "model_market_relationship": "model_agrees_with_favorite",
        },
    ],
)
def test_eligible_fire_rows_use_one_of_the_two_runtime_safe_keep_labels(overrides):
    audit = _audit_module()

    evaluation = audit.evaluate_row(candidate_row(**overrides))

    assert evaluation.qualifies is True
    assert set(evaluation.keep_labels) & {
        "keep_fire_market_agreed_moderate_ev",
        "keep_fire_over_moderate_ev_normal_leash",
    }
    assert evaluation.drag_labels == ()
    assert evaluation.missing_inputs == ()
    assert evaluation.post_start_leakage is False


@pytest.mark.parametrize(
    ("overrides", "drag_label"),
    [
        ({"edge": 0.06}, "cap_high_raw_edge"),
        (
            {"model_market_relationship": "model_fades_favorite"},
            "cap_market_fade",
        ),
        (
            {"side": "under", "model_market_relationship": "model_fades_favorite"},
            "cap_fire_under_market_fade",
        ),
    ],
)
def test_every_frozen_drag_label_excludes_the_row(overrides, drag_label):
    audit = _audit_module()

    evaluation = audit.evaluate_row(candidate_row(**overrides))

    assert evaluation.qualifies is False
    assert drag_label in evaluation.drag_labels


@pytest.mark.parametrize(
    "overrides",
    [
        {"display_verdict": "LEAN"},
        {"display_verdict": "PASS"},
        {"side": "under", "model_market_relationship": "model_other"},
    ],
)
def test_non_fire_or_no_keep_label_rows_cannot_qualify(overrides):
    audit = _audit_module()
    assert audit.evaluate_row(candidate_row(**overrides)).qualifies is False


def test_selector_is_invariant_to_result_pnl_clv_and_postgame_workload():
    audit = _audit_module()
    base = audit.evaluate_row(candidate_row())
    changed = audit.evaluate_row(
        candidate_row(
            result="loss",
            pick_history_pnl=-9.0,
            final_clv_bucket="worse_close_line",
            actual_workload="short",
            actual_pitch_count=20,
        )
    )

    assert (base.qualifies, base.keep_labels, base.drag_labels) == (
        changed.qualifies,
        changed.keep_labels,
        changed.drag_labels,
    )


def test_missing_prospective_critical_input_fails_closed():
    audit = _audit_module()
    row = candidate_row()
    row.pop("provider")

    evaluation = audit.evaluate_row(row)

    assert evaluation.qualifies is False
    assert (
        "provider|live_display_provider|odds_source|"
        "official_line_source_provider|official_odds_source"
    ) in evaluation.missing_inputs


def test_gate_c_official_line_source_satisfies_provider_attribution():
    audit = _audit_module()
    row = candidate_row(
        provider=None,
        official_line_source_provider="therundown",
        official_odds_source="therundown+propline",
    )

    evaluation = audit.evaluate_row(row)

    assert evaluation.qualifies is True
    assert evaluation.missing_inputs == ()
    assert audit._slice_bucket(row, "provider_attribution") == "therundown"


def test_post_start_keep_over_row_is_detected_and_excluded():
    audit = _audit_module()

    evaluation = audit.evaluate_row(candidate_row(bet_timing_window="post_start"))

    assert evaluation.qualifies is False
    assert evaluation.post_start_leakage is True


def _lock_to_single_historical_row(monkeypatch, audit):
    historical = candidate_row(
        slate_date="2026-07-28",
        normalized_pitcher="historical pitcher",
    )
    score = audit.score([historical])
    monkeypatch.setattr(audit, "LOCKED_HISTORICAL", score)
    monkeypatch.setattr(audit, "LOCKED_CURRENT_PROVIDER", score)
    return historical


def test_build_audit_blocks_duplicate_keys_before_other_gates(monkeypatch):
    audit = _audit_module()
    historical = _lock_to_single_historical_row(monkeypatch, audit)

    summary = audit.build_audit([historical, dict(historical)])

    assert summary["status"] == "blocked_duplicate_keys"
    assert summary["integrity"]["duplicate_keys"] == [
        "2026-07-28|historical pitcher|over"
    ]


def test_build_audit_blocks_locked_baseline_drift():
    audit = _audit_module()

    summary = audit.build_audit([
        candidate_row(
            slate_date="2026-07-28",
            normalized_pitcher="historical pitcher",
        )
    ])

    assert summary["status"] == "blocked_baseline_drift"
    assert summary["reconciliation"]["matches"] is False


def test_build_audit_blocks_prospective_input_gaps(monkeypatch):
    audit = _audit_module()
    historical = _lock_to_single_historical_row(monkeypatch, audit)
    prospective = candidate_row(normalized_pitcher="missing provider")
    prospective.pop("provider")

    summary = audit.build_audit([historical, prospective])

    assert summary["status"] == "blocked_input_gap"
    assert summary["integrity"]["input_gap_rows"] == 1


def test_build_audit_blocks_post_start_leakage(monkeypatch):
    audit = _audit_module()
    historical = _lock_to_single_historical_row(monkeypatch, audit)

    summary = audit.build_audit([
        historical,
        candidate_row(
            normalized_pitcher="late evidence",
            bet_timing_window="post_start",
        ),
    ])

    assert summary["status"] == "blocked_post_start_leakage"
    assert summary["integrity"]["post_start_leakage_rows"] == 1


def test_scoreboards_and_diversity_counters_separate_profile_volume(monkeypatch):
    audit = _audit_module()
    historical = _lock_to_single_historical_row(monkeypatch, audit)
    rows = [
        historical,
        candidate_row(
            slate_date="2026-07-30",
            normalized_pitcher="over minus one",
        ),
        candidate_row(
            slate_date="2026-07-31",
            normalized_pitcher="under plus",
            side="under",
            leash_risk_bucket="short",
            display_verdict="FIRE 2u",
            price_sign="plus",
            price_bucket="plus",
            pick_history_pnl=1.2,
        ),
        candidate_row(
            slate_date="2026-08-01",
            normalized_pitcher="over minus loss",
            result="loss",
            pick_history_pnl=-1.0,
        ),
    ]

    summary = audit.build_audit(rows)

    assert summary["windows"]["prospective"] == {
        "rows": 3,
        "wins": 2,
        "losses": 1,
        "pnl": 1.1,
        "roi": 0.3667,
    }
    assert summary["windows"]["current_provider"]["rows"] == 4
    assert summary["windows"]["latest_14_slates"]["rows"] == 4
    assert summary["diversity"] == {
        "under_rows": 1,
        "plus_price_rows": 1,
        "fire_1u_rows": 3,
        "fire_2u_rows": 1,
        "provider_attributed_rows": 4,
        "market_agreement_attributed_rows": 4,
    }
    assert summary["leave_one_slate_out"]["cases"]
    assert set(summary["slices"]["current_provider"]) == set(audit.SLICE_DIMENSIONS)


def test_same_profile_rows_do_not_satisfy_under_or_plus_price_gates(monkeypatch):
    audit = _audit_module()
    historical = _lock_to_single_historical_row(monkeypatch, audit)
    monkeypatch.setattr(audit, "CURRENT_PROVIDER_REVIEW_FLOOR", 3)
    monkeypatch.setattr(audit, "DIVERSITY_FLOOR", 1)
    rows = [
        historical,
        candidate_row(normalized_pitcher="copy one"),
        candidate_row(normalized_pitcher="copy two"),
    ]

    summary = audit.build_audit(rows)

    assert summary["counter"]["rows"] == 3
    assert summary["diversity"]["under_rows"] == 0
    assert summary["diversity"]["plus_price_rows"] == 0
    assert summary["gates"]["current_provider_floor"] is True
    assert summary["gates"]["under_diversity"] is False
    assert summary["gates"]["plus_price_diversity"] is False
    assert "under_rows<1" in summary["diversity_blockers"]
    assert "plus_price_rows<1" in summary["diversity_blockers"]
    assert summary["status"] == "collecting"


def test_ready_for_review_requires_floor_diversity_attribution_and_positive_loo(
    monkeypatch,
):
    audit = _audit_module()
    historical = _lock_to_single_historical_row(monkeypatch, audit)
    monkeypatch.setattr(audit, "CURRENT_PROVIDER_REVIEW_FLOOR", 2)
    monkeypatch.setattr(audit, "DIVERSITY_FLOOR", 1)
    monkeypatch.setattr(audit, "MANDATORY_SLICE_FLOOR", 10)
    prospective = candidate_row(
        slate_date="2026-07-30",
        normalized_pitcher="diverse winner",
        side="under",
        leash_risk_bucket="short",
        display_verdict="FIRE 2u",
        price_sign="plus",
        price_bucket="plus",
        pick_history_pnl=1.2,
    )

    summary = audit.build_audit([historical, prospective])

    assert summary["status"] == "ready_for_review"
    assert all(summary["gates"].values())
    assert summary["diversity_blockers"] == []
    assert summary["leave_one_slate_out"]["minimum"]["pnl"] > 0


def test_final_clv_is_a_report_only_slice_not_a_selector_input(monkeypatch):
    audit = _audit_module()
    historical = _lock_to_single_historical_row(monkeypatch, audit)
    prospective = candidate_row(
        normalized_pitcher="clv report only",
        final_clv_bucket="worse_close_line",
    )

    evaluation = audit.evaluate_row(prospective)
    summary = audit.build_audit([historical, prospective])

    assert evaluation.qualifies is True
    assert summary["slices"]["prospective"]["final_clv"]["worse_close_line"][
        "rows"
    ] == 1


def test_main_writes_markdown_and_json_outputs(tmp_path):
    audit = _audit_module()
    input_path = tmp_path / "gate_c.jsonl"
    output_md = tmp_path / "strict.md"
    output_json = tmp_path / "strict.json"
    input_path.write_text(json.dumps(candidate_row()) + "\n", encoding="utf-8")

    assert audit.main([
        "--input",
        str(input_path),
        "--output-md",
        str(output_md),
        "--output-json",
        str(output_json),
    ]) == 0
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["selector"]["fingerprint"] == audit.RULE_FINGERPRINT
    assert "Diversity Gates" in output_md.read_text(encoding="utf-8")


def test_history_recovered_rows_are_historical_context_not_prospective_credit(
    monkeypatch,
):
    audit = _audit_module()
    historical = candidate_row(
        slate_date="2026-07-28",
        normalized_pitcher="recovered history",
        archive_outcome_reconciliation_source="picks_history_exact",
    )
    locked = audit.score([historical])
    monkeypatch.setattr(audit, "LOCKED_HISTORICAL", locked)
    monkeypatch.setattr(audit, "LOCKED_CURRENT_PROVIDER", locked)
    prospective = candidate_row(
        normalized_pitcher="recovered prospective",
        archive_outcome_reconciliation_source="picks_history_pitcher_game",
    )

    summary = audit.build_audit([historical, prospective])

    assert summary["reconciliation"]["matches"] is True
    assert summary["windows"]["historical_rebuild"]["rows"] == 1
    assert summary["windows"]["prospective"]["rows"] == 0
    assert summary["integrity"]["history_recovered_rows_context_only"] == 2
    assert summary["integrity"]["history_recovered_prospective_rows_excluded"] == 1


def test_legacy_post_start_rows_reconcile_history_but_are_never_prospective(
    monkeypatch,
):
    audit = _audit_module()
    historical = candidate_row(
        slate_date="2026-07-28",
        normalized_pitcher="legacy late history",
        bet_timing_window="post_start",
    )
    locked = audit.score([historical])
    monkeypatch.setattr(audit, "LOCKED_HISTORICAL", locked)
    monkeypatch.setattr(audit, "LOCKED_CURRENT_PROVIDER", locked)

    summary = audit.build_audit([historical])

    assert summary["reconciliation"]["matches"] is True
    assert summary["windows"]["historical_rebuild"]["rows"] == 1
    assert summary["integrity"]["historical_post_start_context_rows"] == 1
