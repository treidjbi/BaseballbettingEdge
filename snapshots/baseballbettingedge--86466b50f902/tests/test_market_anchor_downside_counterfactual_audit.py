import json

from analytics.diagnostics import market_anchor_downside_counterfactual_audit as audit


def _row(**overrides):
    row = {
        "slate_date": "2026-07-28",
        "pitcher": "Test Pitcher",
        "side": "over",
        "result": "loss",
        "pick_history_pnl": -1.0,
        "raw_verdict": "FIRE 1u",
        "display_verdict": "FIRE 1u",
        "verdict": "FIRE 1u",
        "line_bucket": "5.5",
        "price_sign": "minus_110_to_129",
        "quality_gate_level": "clean",
        "bet_timing_window": "pre_30",
        "model_market_relationship": "model_agrees_with_favorite",
        "path_b_coverage_bucket": "covered",
        "workload_bucket": "normal",
        "clv_bucket": "beat_close_price",
        "provider_era": "therundown_propline",
        "market_agreement_label": "agree",
        "market_anchor_selector": {
            "mode": "shadow",
            "selected_side": "over",
            "current_verdict": "FIRE 1u",
            "would_verdict": "LEAN",
            "would_cap_to": "LEAN",
            "applied": False,
            "labels": ["market_anchor_loose"],
            "reasons": ["cap_fire_without_market_anchor_strict"],
        },
    }
    row.update(overrides)
    return row


def test_candidate_action_classifies_unchanged_fire():
    row = _row()
    row["market_anchor_selector"] = {
        **row["market_anchor_selector"],
        "would_verdict": "FIRE 1u",
        "would_cap_to": None,
        "labels": ["market_anchor_strict"],
        "reasons": [],
    }

    action = audit.candidate_action(row)

    assert action["classification"] == "unchanged"
    assert action["would_change"] is False
    assert action["exact"] is True


def test_candidate_action_preserves_fire_to_lean_provenance():
    action = audit.candidate_action(_row(cap_reasons=["quality_gate_clean"]))

    assert action["classification"] == "would_change"
    assert action["would_change"] is True
    assert action["cap_depth"] == 1
    assert action["raw_verdict"] == "FIRE 1u"
    assert action["display_verdict"] == "FIRE 1u"
    assert action["selector_current_verdict"] == "FIRE 1u"
    assert action["hypothetical_verdict"] == "LEAN"
    assert action["selector_reasons"] == ["cap_fire_without_market_anchor_strict"]
    assert action["earlier_cap_reasons"] == ["quality_gate_clean"]


def test_candidate_action_supports_fire_to_pass_cap_depth():
    row = _row(display_verdict="FIRE 2u", raw_verdict="FIRE 2u", verdict="FIRE 2u")
    row["market_anchor_selector"] = {
        **row["market_anchor_selector"],
        "current_verdict": "FIRE 2u",
        "would_verdict": "PASS",
        "would_cap_to": "PASS",
    }

    action = audit.candidate_action(row)

    assert action["classification"] == "would_change"
    assert action["cap_depth"] == 3


def test_candidate_action_excludes_already_capped_row():
    row = _row(display_verdict="LEAN", verdict="LEAN")
    row["market_anchor_selector"] = {
        **row["market_anchor_selector"],
        "current_verdict": "LEAN",
        "would_verdict": "LEAN",
        "would_cap_to": None,
        "reasons": [],
    }
    row["confidence_referee"] = {"applied": True, "reason": "cap_market_fade"}

    action = audit.candidate_action(row)

    assert action["classification"] == "already_capped"
    assert action["would_change"] is False
    assert "confidence_referee" in action["earlier_cap_layers"]


def test_missing_metadata_and_post_start_fail_closed():
    missing = _row(market_anchor_selector=None)
    post_start = _row(bet_timing_window="post_start")

    assert audit.candidate_action(missing)["classification"] == "missing_metadata"
    assert audit.candidate_action(missing)["exact"] is False
    assert audit.candidate_action(post_start)["classification"] == "post_start_excluded"
    assert audit.candidate_action(post_start)["exact"] is False


def test_explicit_post_start_exclusion_does_not_break_prestart_cohort_integrity():
    summary = audit.build_summary([_row(pitcher="Pregame"), _row(pitcher="Late", bet_timing_window="post_start")])

    assert summary["would_change_rows"] == 1
    assert summary["post_start_excluded_rows"] == 1
    assert summary["exact_reconstruction"] is True


def test_paired_summary_scores_avoided_losses_and_foregone_wins():
    loss = _row(pitcher="Loss", result="loss", pick_history_pnl=-1.0)
    win = _row(pitcher="Win", result="win", pick_history_pnl=0.8)

    paired = audit.paired_rows([loss, win])
    summary = audit.build_summary([loss, win])

    assert len(paired) == 2
    assert summary["cohort"]["rows"] == 2
    assert summary["cohort"]["avoided_losses"] == 1
    assert summary["cohort"]["avoided_loss_units"] == 1.0
    assert summary["cohort"]["foregone_wins"] == 1
    assert summary["cohort"]["foregone_win_units"] == 0.8
    assert summary["cohort"]["net_unit_delta"] == 0.2
    assert "side" in summary["slices"]
    assert "leave_one_slate_out" in summary


def test_gate_c_official_line_source_fills_provider_attribution():
    row = _row(
        provider_era=None,
        odds_source=None,
        market_source_mode=None,
        market_provider=None,
        official_line_source_provider="therundown",
        official_odds_source="therundown+propline",
    )

    summary = audit.build_summary([row])

    assert summary["slices"]["provider"]["therundown"]["rows"] == 1
    assert summary["missing_critical_attribution"]["provider"] == 0


def test_duplicate_candidate_key_blocks_exact_reconstruction():
    row = _row()
    summary = audit.build_summary([row, dict(row)])

    assert summary["duplicate_keys"] == 1
    assert summary["exact_reconstruction"] is False
    assert summary["decision"] == "keep_shadow"


def test_main_writes_markdown_and_json(tmp_path):
    input_path = tmp_path / "rows.jsonl"
    output_md = tmp_path / "audit.md"
    output_json = tmp_path / "audit.json"
    input_path.write_text(json.dumps(_row()) + "\n", encoding="utf-8")

    assert audit.main([
        "--input", str(input_path),
        "--output-md", str(output_md),
        "--output-json", str(output_json),
    ]) == 0
    assert "Market-Anchor Downside Counterfactual Audit" in output_md.read_text(encoding="utf-8")
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["cohort"]["rows"] == 1
