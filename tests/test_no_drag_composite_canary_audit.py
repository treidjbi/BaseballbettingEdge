import json

import pytest

from analytics.diagnostics import no_drag_composite_canary_audit as audit


def candidate_row(**overrides):
    row = {
        "is_tracked_pick": True,
        "slate_date": "2026-07-21",
        "normalized_pitcher": "test pitcher",
        "side": "over",
        "result": "win",
        "pick_history_pnl": 1.0,
        "display_verdict": "FIRE 1u",
        "edge": 0.04,
        "locked_adj_ev": 0.10,
        "model_market_relationship": "model_agrees_with_favorite",
        "line_bucket": "4.5",
        "price_sign": "minus",
        "price_bucket": "-100 to -129",
        "bet_timing_window": "pre_30",
        "leash_risk_bucket": "normal",
        "pitcher_archetype_bucket": "standard_starter",
        "model_no_vig_gap": 0.01,
        "quality_gate_level": "clean",
        "batter_handedness_mode": "path_b",
        "lineup_real_split_count": 3,
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    ("overrides", "family"),
    [
        ({}, "strong_base_strict_runtime_core"),
        (
            {
                "display_verdict": "FIRE 1u",
                "model_market_relationship": "model_other",
                "bet_timing_window": "unknown",
            },
            "strong_base_strict_runtime_core",
        ),
        (
            {
                "display_verdict": "LEAN",
                "locked_adj_ev": 0.03,
                "model_market_relationship": "model_other",
            },
            "strong_base_selective_lean",
        ),
        (
            {
                "display_verdict": "LEAN",
                "line_bucket": "5.5",
                "pitcher_archetype_bucket": "low_k_standard",
                "model_no_vig_gap": 0.02,
                "model_market_relationship": "model_other",
            },
            "strong_base_selective_lean",
        ),
        (
            {
                "display_verdict": "PASS",
                "model_market_relationship": "model_other",
                "market_anchor_selector": {"labels": ["market_anchor_strict"]},
            },
            "market_anchor_strict",
        ),
    ],
)
def test_frozen_selector_positive_truth_table(overrides, family):
    evaluation = audit.evaluate_row(candidate_row(**overrides))
    assert evaluation.qualifies is True
    assert family in evaluation.families
    assert evaluation.drag_labels == ()
    assert evaluation.missing_inputs == ()


@pytest.mark.parametrize(
    ("overrides", "drag_label"),
    [
        ({"edge": 0.06}, "cap_high_raw_edge"),
        ({"model_market_relationship": "model_fades_favorite"}, "cap_market_fade"),
        (
            {"side": "under", "model_market_relationship": "model_fades_favorite"},
            "cap_fire_under_market_fade",
        ),
    ],
)
def test_frozen_drag_rules_exclude_rows(overrides, drag_label):
    evaluation = audit.evaluate_row(candidate_row(**overrides))
    assert evaluation.qualifies is False
    assert drag_label in evaluation.drag_labels


def test_selective_low_line_model_fade_is_removed_by_outer_drag():
    evaluation = audit.evaluate_row(candidate_row(
        display_verdict="LEAN",
        line_bucket="2.5-3.5",
        locked_adj_ev=0.03,
        model_market_relationship="model_fades_favorite",
        quality_gate_level="capped",
    ))
    assert "strong_base_selective_lean" in evaluation.families
    assert "cap_market_fade" in evaluation.drag_labels
    assert evaluation.qualifies is False


def test_verdict_precedence_uses_first_non_empty_value():
    row = candidate_row(
        display_verdict="LEAN",
        locked_verdict="FIRE 2u",
        actionable_verdict="PASS",
        locked_adj_ev=0.03,
        model_market_relationship="model_other",
    )
    assert audit.verdict(row) == "LEAN"
    assert audit.evaluate_row(row).families == ("strong_base_selective_lean",)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (-0.001, "ev_negative"),
        (0.0, "ev_unknown"),
        (0.059999, "ev_0_to_6"),
        (0.06, "ev_6_to_17"),
        (0.169999, "ev_6_to_17"),
        (0.17, "ev_17_plus"),
    ],
)
def test_adjusted_ev_boundaries(value, expected):
    assert audit.ev_bucket({"locked_adj_ev": value}) == expected


def test_adjusted_ev_preserves_truthy_or_zero_fallthrough():
    row = {"locked_adj_ev": 0.0, "adj_ev": 0.10, "ev": 0.03}
    assert audit.adjusted_ev(row) == 0.10


def test_market_anchor_labels_accept_object_fallback_and_json_object():
    assert audit.market_anchor_labels({
        "market_anchor_selector": {"labels": ["market_anchor_strict"]},
    }) == {"market_anchor_strict"}
    assert audit.market_anchor_labels({
        "market_anchor_selector_labels": ["market_anchor_strict"],
    }) == {"market_anchor_strict"}
    assert audit.market_anchor_labels({
        "market_anchor_selector": json.dumps({"labels": ["market_anchor_strict"]}),
    }) == {"market_anchor_strict"}


def test_rule_fingerprint_is_pinned():
    assert audit.RULE_FINGERPRINT == "22b03ecea02aa83e9174c24f5f05878823cb67766fe1c75102d34bfe5c3b4aa4"


def graded_row(date, pitcher, result="win", pnl=1.0, **overrides):
    return candidate_row(
        slate_date=date,
        normalized_pitcher=pitcher,
        result=result,
        pick_history_pnl=pnl,
        **overrides,
    )


def lock_history_to(monkeypatch, rows):
    score = audit.score(rows)
    monkeypatch.setattr(audit, "LOCKED_HISTORICAL", {
        "rows": score["rows"],
        "wins": score["wins"],
        "losses": score["losses"],
        "pnl": score["pnl"],
        "roi": score["roi"],
    })


def test_initial_counter_is_locked_52_plus_zero(monkeypatch):
    historical = [graded_row("2026-07-20", "history one")]
    lock_history_to(monkeypatch, historical)
    summary = audit.build_audit(historical, generated_at="2026-07-21T16:00:00Z")
    assert summary["status"] == "collecting"
    assert summary["counter"] == {
        "locked_current_provider_rows": 52,
        "prospective_qualified_rows": 0,
        "rows": 52,
        "floor": 75,
        "remaining": 23,
    }


def test_prospective_rows_advance_counter_without_mutating_locked_history(monkeypatch):
    historical = [graded_row("2026-07-20", "history one")]
    prospective = [
        graded_row("2026-07-21", "future one"),
        graded_row("2026-07-22", "future two", result="loss", pnl=-1.0),
    ]
    lock_history_to(monkeypatch, historical)
    summary = audit.build_audit(historical + prospective)
    assert summary["locked_baselines"]["current_provider"]["rows"] == 52
    assert summary["windows"]["prospective"]["rows"] == 2
    assert summary["counter"]["rows"] == 54
    assert summary["counter"]["remaining"] == 21


def test_reaching_floor_only_becomes_ready_for_review(monkeypatch):
    historical = [graded_row("2026-07-20", "history one")]
    prospective = [
        graded_row("2026-07-21", f"future {index}")
        for index in range(23)
    ]
    lock_history_to(monkeypatch, historical)
    summary = audit.build_audit(historical + prospective)
    assert summary["status"] == "ready_for_review"
    assert summary["counter"]["rows"] == 75
    assert summary["counter"]["remaining"] == 0
    assert "promot" not in summary["status"]


def test_baseline_drift_blocks_counter_advancement():
    summary = audit.build_audit([graded_row("2026-07-20", "wrong baseline")])
    assert summary["status"] == "blocked_baseline_drift"
    assert summary["counter"]["rows"] == 52
    assert summary["counter"]["prospective_qualified_rows"] == 0
    assert summary["reconciliation"]["matches"] is False


def test_duplicate_key_blocks_counter_advancement(monkeypatch):
    historical = [graded_row("2026-07-20", "history one")]
    duplicate = graded_row("2026-07-21", "same pitcher")
    lock_history_to(monkeypatch, historical)
    summary = audit.build_audit(historical + [duplicate, dict(duplicate)])
    assert summary["status"] == "blocked_duplicate_keys"
    assert summary["integrity"]["duplicate_keys"] == [
        "2026-07-21|same pitcher|over"
    ]
    assert summary["counter"]["rows"] == 52


@pytest.mark.parametrize(
    "missing_update",
    [
        {"display_verdict": None, "locked_verdict": None, "actionable_verdict": None, "current_verdict": None, "verdict": None},
        {"edge": None},
        {"locked_adj_ev": None, "adj_ev": None, "ev": None},
        {"model_market_relationship": None},
        {"line_bucket": None},
        {"price_sign": None},
        {"price_bucket": None},
        {"bet_timing_window": None},
        {"leash_risk_bucket": None, "opportunity_bucket": None},
        {"pitcher_archetype_bucket": None},
        {"model_no_vig_gap": None},
        {"quality_gate_level": None},
        {"batter_handedness_mode": None},
        {"pick_history_pnl": None, "pnl": None, "theoretical_pnl": None},
    ],
)
def test_prospective_critical_input_gap_blocks_run(monkeypatch, missing_update):
    historical = [graded_row("2026-07-20", "history one")]
    lock_history_to(monkeypatch, historical)
    row = graded_row("2026-07-21", "future gap")
    row.update(missing_update)
    summary = audit.build_audit(historical + [row])
    assert summary["status"] == "blocked_input_gap"
    assert summary["integrity"]["input_gap_rows"] == 1
    assert summary["counter"]["rows"] == 52


def test_absent_market_anchor_metadata_is_false_not_input_gap(monkeypatch):
    historical = [graded_row("2026-07-20", "history one")]
    lock_history_to(monkeypatch, historical)
    row = graded_row("2026-07-21", "future complete", market_anchor_selector=None)
    summary = audit.build_audit(historical + [row])
    assert summary["status"] == "collecting"
    assert summary["integrity"]["input_gap_rows"] == 0


def test_mandatory_slices_include_scores_and_missing_coverage(monkeypatch):
    historical = [graded_row("2026-07-20", "history one")]
    prospective = graded_row(
        "2026-07-21",
        "future one",
        display_verdict="LEAN",
        locked_adj_ev=0.03,
        model_market_relationship="model_other",
        market_agreement_label=None,
        provider=None,
        live_display_provider=None,
        price_clv_cents=5,
    )
    lock_history_to(monkeypatch, historical)
    summary = audit.build_audit(historical + [prospective])
    prospective_slices = summary["slices"]["prospective"]
    assert prospective_slices["verdict_family"]["LEAN"]["rows"] == 1
    assert prospective_slices["side"]["over"]["rows"] == 1
    assert prospective_slices["price_bucket"]["-100 to -129"]["rows"] == 1
    assert prospective_slices["path_b"]["path_b_real_or_mixed"]["rows"] == 1
    assert prospective_slices["market_agreement"]["missing"]["rows"] == 1
    assert prospective_slices["provider_attribution"]["missing"]["rows"] == 1
    assert summary["integrity"]["slice_missing_coverage"]["prospective"]["market_agreement"] == 1
    assert summary["integrity"]["slice_missing_coverage"]["prospective"]["provider_attribution"] == 1


def test_markdown_leads_with_decision_fields_and_live_boundary(monkeypatch):
    historical = [graded_row("2026-07-20", "history one")]
    lock_history_to(monkeypatch, historical)
    report = audit.render_markdown(audit.build_audit(historical))
    assert report.startswith("# No-Drag Composite Prospective Canary Audit")
    assert "## Executive Read" in report
    assert audit.SELECTOR_ID in report
    assert audit.RULE_FINGERPRINT in report
    assert "`collecting`" in report
    assert "52" in report and "23" in report
    assert "## Baseline Reconciliation" in report
    assert "## Mandatory Slice Risks" in report
    assert "## Live Boundary" in report
    assert "requires a separate Tyler-approved plan" in report


def test_write_outputs_emits_matching_markdown_and_json(tmp_path, monkeypatch):
    historical = [graded_row("2026-07-20", "history one")]
    lock_history_to(monkeypatch, historical)
    summary = audit.build_audit(historical, generated_at="2026-07-21T16:00:00Z")
    md_path = tmp_path / "audit.md"
    json_path = tmp_path / "audit.json"
    audit.write_outputs(summary, md_path, json_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["selector"]["id"] == audit.SELECTOR_ID
    assert payload["selector"]["fingerprint"] == audit.RULE_FINGERPRINT
    assert payload["status"] == "collecting"
    assert md_path.read_text(encoding="utf-8").endswith("\n")
    assert json_path.read_text(encoding="utf-8").endswith("\n")


def test_main_runs_from_repo_root_and_writes_both_outputs(tmp_path, monkeypatch):
    input_path = tmp_path / "gate_c.jsonl"
    input_path.write_text(json.dumps(graded_row("2026-07-20", "history one")) + "\n", encoding="utf-8")
    lock_history_to(monkeypatch, [graded_row("2026-07-20", "history one")])
    md_path = tmp_path / "result.md"
    json_path = tmp_path / "result.json"
    assert audit.main([
        "--input", str(input_path),
        "--output-md", str(md_path),
        "--output-json", str(json_path),
    ]) == 0
    assert md_path.exists()
    assert json_path.exists()
