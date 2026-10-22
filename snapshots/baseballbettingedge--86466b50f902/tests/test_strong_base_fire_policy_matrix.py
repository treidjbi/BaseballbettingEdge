import json

from analytics.diagnostics import strong_base_fire_policy_matrix as matrix


def _row(**overrides):
    row = {
        "slate_date": "2026-07-30",
        "pitcher": "Test Pitcher",
        "side": "over",
        "result": "win",
        "pick_history_pnl": 0.9,
        "raw_verdict": "FIRE 1u",
        "display_verdict": "FIRE 1u",
        "verdict": "FIRE 1u",
        "edge": 0.05,
        "adj_ev_roi": 0.10,
        "line_bucket": "5.5",
        "price_sign": "minus_110_to_129",
        "quality_gate_level": "clean",
        "bet_timing_window": "pre_30",
        "model_market_relationship": "model_agrees_with_favorite",
        "leash_risk_bucket": "normal",
        "path_b_coverage_bucket": "covered",
        "workload_bucket": "normal",
        "clv_bucket": "beat_close_price",
        "provider_era": "therundown_propline",
        "market_agreement_label": "agree",
        "market_anchor_selector": {"labels": ["market_anchor_strict"]},
    }
    row.update(overrides)
    return row


def _spec(policy_id):
    return next(spec for spec in matrix.policy_specs() if spec.id == policy_id)


def test_policy_specs_are_unique_and_stably_fingerprinted():
    specs = matrix.policy_specs()

    assert [spec.id for spec in specs] == [
        "cap_high_raw_edge",
        "cap_market_fade",
        "keep_fire_over_moderate_ev_normal_leash",
        "keep_fire_market_agreed_moderate_ev",
        "strict_runtime_core_flat",
        "keep_fire_if_strong_base_or_market_anchor_strict",
    ]
    assert len({spec.id for spec in specs}) == len(specs)
    assert all(len(spec.fingerprint) == 64 for spec in specs)
    assert [spec.fingerprint for spec in specs] == [spec.fingerprint for spec in matrix.policy_specs()]


def test_downside_cap_boundaries_and_already_capped_split():
    high = _spec("cap_high_raw_edge")
    fade = _spec("cap_market_fade")

    assert matrix.evaluate_policy(_row(edge=0.06), high)["action"] == "incremental_would_cap"
    assert matrix.evaluate_policy(_row(edge=0.0599), high)["selected"] is False
    assert matrix.evaluate_policy(
        _row(model_market_relationship="model_fades_favorite"), fade
    )["action"] == "incremental_would_cap"
    assert matrix.evaluate_policy(
        _row(model_market_relationship="model_fades_favorite", display_verdict="LEAN"), fade
    )["action"] == "already_capped"


def test_retained_fire_truth_tables_never_promote_non_fire():
    over = _spec("keep_fire_over_moderate_ev_normal_leash")
    agreed = _spec("keep_fire_market_agreed_moderate_ev")

    assert matrix.evaluate_policy(_row(), over)["action"] == "retained_fire"
    assert matrix.evaluate_policy(_row(side="under"), over)["selected"] is False
    assert matrix.evaluate_policy(_row(leash_risk_bucket="short"), over)["selected"] is False
    assert matrix.evaluate_policy(_row(adj_ev_roi=0.06), agreed)["action"] == "retained_fire"
    assert matrix.evaluate_policy(_row(adj_ev_roi=0.18), agreed)["selected"] is False
    assert matrix.evaluate_policy(_row(bet_timing_window="pre_15"), agreed)["selected"] is False
    assert matrix.evaluate_policy(_row(display_verdict="LEAN"), over)["action"] == "excluded_non_fire"
    assert matrix.evaluate_policy(_row(display_verdict="PASS"), agreed)["action"] == "excluded_non_fire"


def test_strict_core_and_anchor_union_boundaries():
    strict = _spec("strict_runtime_core_flat")
    union = _spec("keep_fire_if_strong_base_or_market_anchor_strict")

    assert matrix.evaluate_policy(_row(), strict)["selected"] is True
    assert matrix.evaluate_policy(_row(edge=0.06), strict)["selected"] is False
    assert matrix.evaluate_policy(
        _row(model_market_relationship="model_fades_favorite"), strict
    )["selected"] is False
    anchor_only = _row(
        side="under",
        adj_ev_roi=0.02,
        leash_risk_bucket="short",
        market_anchor_selector={"labels": ["market_anchor_strict"]},
    )
    assert matrix.evaluate_policy(anchor_only, strict)["selected"] is False
    assert matrix.evaluate_policy(anchor_only, union)["action"] == "retained_fire"


def test_policy_decisions_are_invariant_to_postgame_fields():
    for spec in matrix.policy_specs():
        base = matrix.evaluate_policy(_row(), spec)
        changed = matrix.evaluate_policy(
            _row(result="loss", pick_history_pnl=-9.0, actual_workload="bad", final_clv=-99)
        , spec)
        assert (base["selected"], base["action"]) == (changed["selected"], changed["action"])


def test_policies_do_not_consume_post_start_evidence():
    spec = _spec("cap_high_raw_edge")
    result = matrix.evaluate_policy(_row(edge=0.08, bet_timing_window="post_start"), spec)
    assert result["selected"] is True
    assert result["action"] == "incremental_would_cap"

    agreed = _spec("keep_fire_market_agreed_moderate_ev")
    assert matrix.evaluate_policy(_row(bet_timing_window="post_start"), agreed)["selected"] is False


def test_matrix_includes_overlap_incremental_and_readiness_sections():
    rows = [
        _row(pitcher="A", edge=0.08, result="loss", pick_history_pnl=-1.0),
        _row(pitcher="B", result="win", pick_history_pnl=0.8),
    ]
    summary = matrix.build_matrix(rows)

    assert summary["prospective_start"] == "2026-07-30"
    assert len(summary["policies"]) == 6
    assert summary["overlap"]
    high = next(item for item in summary["policies"] if item["id"] == "cap_high_raw_edge")
    assert high["selector_match_rows"] == 1
    assert high["incremental_would_cap_rows"] == 1
    assert high["prospective"]["rows"] == 1
    assert "leave_one_slate_out" in high
    assert "side" in high["slices"]


def test_current_provider_and_recent_windows_are_distinct_from_prospective_counter():
    summary = matrix.build_matrix([_row(slate_date="2026-07-28", edge=0.08, result="loss", pick_history_pnl=-1.0)])
    high = next(item for item in summary["policies"] if item["id"] == "cap_high_raw_edge")

    assert high["prospective"]["rows"] == 0
    assert high["current_provider"]["rows"] == 1
    assert high["latest_14_slates"]["rows"] == 1


def test_main_writes_markdown_and_json(tmp_path):
    input_path = tmp_path / "rows.jsonl"
    output_md = tmp_path / "matrix.md"
    output_json = tmp_path / "matrix.json"
    input_path.write_text(json.dumps(_row()) + "\n", encoding="utf-8")

    assert matrix.main([
        "--input", str(input_path),
        "--output-md", str(output_md),
        "--output-json", str(output_json),
    ]) == 0
    assert "Strong Base FIRE Policy Shadow Matrix" in output_md.read_text(encoding="utf-8")
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    assert payload["prospective_start"] == "2026-07-30"
