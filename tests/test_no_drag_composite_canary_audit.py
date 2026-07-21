import json
import math
import subprocess
import sys

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


def scored_rows(date, prefix, wins, losses, pnl):
    win_pnl = (pnl + losses) / wins
    return [
        graded_row(date, f"{prefix} win {index}", pnl=win_pnl)
        for index in range(wins)
    ] + [
        graded_row(
            date,
            f"{prefix} loss {index}",
            result="loss",
            pnl=-1.0,
        )
        for index in range(losses)
    ]


def locked_historical_rows():
    prior_provider = scored_rows(
        "2026-06-23",
        "prior provider",
        wins=88,
        losses=46,
        pnl=20.03,
    )
    current_provider = scored_rows(
        "2026-07-20",
        "current provider",
        wins=36,
        losses=16,
        pnl=9.17,
    )
    rows = prior_provider + current_provider
    assert audit.score(rows) == audit.LOCKED_HISTORICAL
    current_score = audit.score(current_provider)
    assert {
        key: current_score[key]
        for key in ("rows", "wins", "losses", "pnl")
    } == {
        key: audit.LOCKED_CURRENT_PROVIDER[key]
        for key in ("rows", "wins", "losses", "pnl")
    }
    return rows


def test_initial_counter_is_locked_52_plus_zero():
    historical = locked_historical_rows()
    summary = audit.build_audit(historical, generated_at="2026-07-21T16:00:00Z")
    assert summary["status"] == "collecting"
    assert summary["counter"] == {
        "locked_current_provider_rows": 52,
        "prospective_qualified_rows": 0,
        "rows": 52,
        "floor": 75,
        "remaining": 23,
    }


def test_prospective_rows_advance_counter_without_mutating_locked_history():
    historical = locked_historical_rows()
    prospective = [
        graded_row("2026-07-21", "future one"),
        graded_row("2026-07-22", "future two", result="loss", pnl=-1.0),
    ]
    summary = audit.build_audit(historical + prospective)
    assert summary["locked_baselines"]["current_provider"]["rows"] == 52
    assert summary["windows"]["prospective"]["rows"] == 2
    assert summary["counter"]["rows"] == 54
    assert summary["counter"]["remaining"] == 21


def test_reaching_floor_only_becomes_ready_for_review():
    historical = locked_historical_rows()
    prospective = [
        graded_row("2026-07-21", f"future {index}")
        for index in range(23)
    ]
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


def test_current_provider_historical_slice_reconciles_before_collecting():
    summary = audit.build_audit(locked_historical_rows())

    current_provider = summary["reconciliation"]["current_provider"]
    assert summary["status"] == "collecting"
    assert summary["reconciliation"]["matches"] is True
    assert current_provider["matches"] is True
    assert current_provider["observed"] == {
        "rows": 52,
        "wins": 36,
        "losses": 16,
        "pnl": 9.17,
        "roi": 0.1763,
    }
    assert current_provider["window"] == {
        "start": "2026-06-24",
        "end": "2026-07-20",
    }
    assert summary["counter"]["rows"] == 52


def test_current_provider_membership_drift_blocks_even_when_full_score_matches():
    historical = [dict(row) for row in locked_historical_rows()]
    shifted = next(
        row for row in historical if row["slate_date"] == "2026-07-20"
    )
    shifted["slate_date"] = "2026-06-23"

    summary = audit.build_audit(historical)

    assert summary["reconciliation"]["historical"]["matches"] is True
    assert summary["reconciliation"]["current_provider"]["matches"] is False
    assert summary["reconciliation"]["matches"] is False
    assert summary["status"] == "blocked_baseline_drift"
    assert summary["counter"]["prospective_qualified_rows"] == 0
    assert summary["counter"]["rows"] == 52


def test_duplicate_key_blocks_counter_advancement():
    historical = locked_historical_rows()
    duplicate = graded_row("2026-07-21", "same pitcher")
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
def test_prospective_critical_input_gap_blocks_run(missing_update):
    historical = locked_historical_rows()
    row = graded_row("2026-07-21", "future gap")
    row.update(missing_update)
    summary = audit.build_audit(historical + [row])
    assert summary["status"] == "blocked_input_gap"
    assert summary["integrity"]["input_gap_rows"] == 1
    assert summary["counter"]["rows"] == 52


def test_absent_market_anchor_metadata_is_false_not_input_gap():
    historical = locked_historical_rows()
    row = graded_row("2026-07-21", "future complete", market_anchor_selector=None)
    summary = audit.build_audit(historical + [row])
    assert summary["status"] == "collecting"
    assert summary["integrity"]["input_gap_rows"] == 0


@pytest.mark.parametrize(
    "invalid_date",
    [None, "", "   ", "not-an-iso-date", "2026-02-30"],
    ids=["none", "blank", "whitespace", "malformed", "impossible"],
)
def test_invalid_slate_dates_fail_closed_without_entering_scored_windows(
    invalid_date,
):
    invalid = graded_row(
        invalid_date,
        "future invalid date",
        display_verdict="PASS",
        market_anchor_selector={"labels": ["market_anchor_strict"]},
    )

    summary = audit.build_audit(locked_historical_rows() + [invalid])

    assert summary["status"] == "blocked_input_gap"
    assert summary["integrity"]["input_gap_rows"] == 1
    assert any(
        "slate_date" in missing
        for missing in summary["integrity"]["input_gaps"].values()
    )
    assert summary["counter"]["prospective_qualified_rows"] == 0
    assert summary["counter"]["rows"] == 52
    assert summary["windows"]["historical_rebuild"]["rows"] == 186
    assert summary["windows"]["prospective"]["rows"] == 0
    assert summary["windows"]["current_provider"]["rows"] == 52
    assert summary["windows"]["recent_14_slates"]["rows"] == 186


def test_whitespace_padded_date_uses_canonical_provider_era_reporting():
    prospective = graded_row(
        " 2026-07-21 ",
        "future padded date",
    )

    summary = audit.build_audit(locked_historical_rows() + [prospective])

    assert summary["status"] == "collecting"
    assert summary["integrity"]["input_gap_rows"] == 0
    assert summary["windows"]["prospective"]["rows"] == 1
    assert summary["windows"]["current_provider"]["rows"] == 53
    assert summary["windows"]["recent_14_slates"]["rows"] == 187
    assert summary["windows"]["recent_14_slates"]["slate_dates"][-1] == "2026-07-21"

    provider_era = summary["slices"]["prospective"]["provider_era"]
    assert provider_era["official_therundown_propline"]["rows"] == 1
    assert "pre_current_provider" not in provider_era

    report = audit.render_markdown(summary)
    prospective_report = report.split("### prospective", 1)[1].split("### combined", 1)[0]
    provider_era_report = prospective_report.split("#### provider_era", 1)[1].split(
        "#### provider_attribution",
        1,
    )[0]
    assert "`official_therundown_propline`: 1 rows" in provider_era_report
    assert "`pre_current_provider`" not in provider_era_report


def test_mandatory_slices_include_scores_and_missing_coverage():
    historical = locked_historical_rows()
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


def test_all_mandatory_slice_dimensions_are_pinned_for_every_window():
    expected_dimensions = (
        "verdict_family",
        "side",
        "k_line",
        "price_sign",
        "price_bucket",
        "quality",
        "path_b",
        "model_market",
        "workload_leash",
        "market_anchor",
        "market_agreement",
        "preclose_clv_proxy",
        "final_clv",
        "provider_era",
        "provider_attribution",
        "recent_14_slates",
    )
    summary = audit.build_audit(locked_historical_rows())

    assert audit.SLICE_DIMENSIONS == expected_dimensions
    assert tuple(summary["slices"]) == (
        "historical_rebuild",
        "prospective",
        "combined",
    )
    for window in summary["slices"].values():
        assert tuple(window) == expected_dimensions


def test_json_contract_has_exact_top_level_and_reconciliation_keys():
    summary = audit.build_audit(locked_historical_rows())

    assert set(summary) == {
        "generated_at",
        "selector",
        "status",
        "integrity",
        "locked_baselines",
        "reconciliation",
        "windows",
        "counter",
        "callouts",
        "slices",
        "live_boundary",
    }
    assert set(summary["reconciliation"]) == {
        "matches",
        "pnl_tolerance",
        "historical",
        "current_provider",
    }
    assert set(summary["reconciliation"]["historical"]) == {
        "matches",
        "checks",
        "observed",
        "locked",
    }
    assert set(summary["reconciliation"]["current_provider"]) == {
        "matches",
        "checks",
        "observed",
        "locked",
        "window",
    }


def _expected_markdown_bucket(bucket, bucket_score):
    return (
        f"- `{bucket}`: {bucket_score['rows']} rows, "
        f"{bucket_score['wins']}-{bucket_score['losses']}, "
        f"{bucket_score['pnl']:+.2f}u, {bucket_score['roi']:+.1%} ROI"
    )


def test_markdown_section_and_slice_statistics_are_complete_and_ordered():
    summary = audit.build_audit(
        locked_historical_rows()
        + [graded_row(" 2026-07-21 ", "future padded mandatory slices")]
    )
    report = audit.render_markdown(summary)
    section_titles = (
        "Executive Read",
        "Counter",
        "Baseline Reconciliation",
        "Prospective Evidence",
        "Current Provider and Recent",
        "Breakout or Deterioration",
        "Mandatory Slice Risks",
        "Slice Audit",
        "Live Boundary",
    )
    section_positions = [report.index(f"## {title}") for title in section_titles]
    assert section_positions == sorted(section_positions)

    window_names = ("historical_rebuild", "prospective", "combined")
    window_positions = [report.index(f"### {window}") for window in window_names]
    assert window_positions == sorted(window_positions)
    for index, window in enumerate(window_names):
        start = window_positions[index]
        end = window_positions[index + 1] if index + 1 < len(window_names) else report.index("## Live Boundary")
        window_report = report[start:end]
        dimension_positions = [
            window_report.index(f"#### {dimension}")
            for dimension in audit.SLICE_DIMENSIONS
        ]
        assert dimension_positions == sorted(dimension_positions)
        for dimension_index, dimension in enumerate(audit.SLICE_DIMENSIONS):
            dimension_start = dimension_positions[dimension_index]
            dimension_end = (
                dimension_positions[dimension_index + 1]
                if dimension_index + 1 < len(dimension_positions)
                else len(window_report)
            )
            dimension_report = window_report[dimension_start:dimension_end]
            missing = summary["integrity"]["slice_missing_coverage"][window][dimension]
            assert f"- Missing coverage: {missing} rows" in dimension_report
            for bucket, bucket_score in summary["slices"][window][dimension].items():
                assert _expected_markdown_bucket(bucket, bucket_score) in dimension_report


def test_markdown_leads_with_decision_fields_and_live_boundary():
    historical = locked_historical_rows()
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


def test_write_outputs_emits_matching_markdown_and_json(tmp_path):
    historical = locked_historical_rows()
    summary = audit.build_audit(historical, generated_at="2026-07-21T16:00:00Z")
    md_path = tmp_path / "audit.md"
    json_path = tmp_path / "audit.json"
    audit.write_outputs(summary, md_path, json_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["selector"]["id"] == audit.SELECTOR_ID
    assert payload["selector"]["fingerprint"] == audit.RULE_FINGERPRINT
    assert payload["status"] == "collecting"
    assert payload["reconciliation"]["current_provider"]["matches"] is True
    assert md_path.read_text(encoding="utf-8").endswith("\n")
    assert json_path.read_text(encoding="utf-8").endswith("\n")


def test_main_writes_both_outputs(tmp_path):
    historical = locked_historical_rows()
    input_path = tmp_path / "gate_c.jsonl"
    input_path.write_text(
        "\n".join(json.dumps(row) for row in historical) + "\n",
        encoding="utf-8",
    )
    md_path = tmp_path / "result.md"
    json_path = tmp_path / "result.json"
    assert audit.main([
        "--input", str(input_path),
        "--output-md", str(md_path),
        "--output-json", str(json_path),
    ]) == 0
    assert md_path.exists()
    assert json_path.exists()


def test_cli_subprocess_from_repo_root_fails_closed_on_invalid_date(tmp_path):
    rows = locked_historical_rows() + [
        graded_row(
            "not-an-iso-date",
            "subprocess invalid date",
            display_verdict="PASS",
            market_anchor_selector={"labels": ["market_anchor_strict"]},
        )
    ]
    input_path = tmp_path / "gate_c.jsonl"
    input_path.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    md_path = tmp_path / "subprocess-result.md"
    json_path = tmp_path / "subprocess-result.json"

    completed = subprocess.run(
        [
            sys.executable,
            "analytics/diagnostics/no_drag_composite_canary_audit.py",
            "--input",
            str(input_path),
            "--output-md",
            str(md_path),
            "--output-json",
            str(json_path),
        ],
        cwd=audit.ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "status=blocked_input_gap counter=52/75" in completed.stdout
    assert md_path.exists()
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["status"] == "blocked_input_gap"
    assert payload["counter"]["rows"] == 52


@pytest.mark.parametrize(
    ("overrides", "dimension", "bucket"),
    [
        (
            {"leash_risk_bucket": "  ", "opportunity_bucket": "normal"},
            "workload_leash",
            "normal",
        ),
        (
            {"provider": "\t", "live_display_provider": "propline"},
            "provider_attribution",
            "propline",
        ),
    ],
)
def test_slice_fallbacks_use_trimmed_first_non_empty(
    overrides,
    dimension,
    bucket,
):
    historical = locked_historical_rows()
    prospective = graded_row(
        "2026-07-21",
        "future fallback",
        display_verdict="PASS",
        market_anchor_selector={"labels": ["market_anchor_strict"]},
        **overrides,
    )
    summary = audit.build_audit(historical + [prospective])
    assert summary["slices"]["prospective"][dimension][bucket]["rows"] == 1


@pytest.mark.parametrize(
    "field",
    ["edge", "locked_adj_ev", "model_no_vig_gap", "pick_history_pnl"],
)
@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf")],
    ids=["nan", "positive_infinity", "negative_infinity"],
)
def test_non_finite_prospective_critical_numeric_blocks_and_stays_json_safe(
    field,
    value,
):
    historical = locked_historical_rows()
    prospective = graded_row(
        "2026-07-21",
        "future non finite",
        display_verdict="PASS",
        market_anchor_selector={"labels": ["market_anchor_strict"]},
    )
    prospective[field] = value
    summary = audit.build_audit(historical + [prospective])
    assert summary["status"] == "blocked_input_gap"
    assert summary["integrity"]["input_gap_rows"] == 1
    assert summary["counter"]["prospective_qualified_rows"] == 0
    assert summary["counter"]["rows"] == 52
    assert math.isfinite(summary["windows"]["prospective"]["pnl"])
    json.dumps(summary, allow_nan=False)


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        "NaN",
        "Infinity",
        "-Infinity",
    ],
    ids=[
        "numeric_nan",
        "numeric_positive_infinity",
        "numeric_negative_infinity",
        "string_nan",
        "string_positive_infinity",
        "string_negative_infinity",
    ],
)
@pytest.mark.parametrize(
    ("overrides", "winning_field"),
    [
        ({"locked_adj_ev": None, "adj_ev": 0.10, "ev": 0.03}, "locked_adj_ev"),
        ({"locked_adj_ev": 0.0, "adj_ev": None, "ev": 0.10}, "adj_ev"),
        ({"locked_adj_ev": 0.0, "adj_ev": 0.0, "ev": None}, "ev"),
    ],
    ids=["locked_before_later_finite", "adj_before_later_finite", "ev_terminal"],
)
def test_non_finite_adjusted_ev_precedence_winner_blocks_later_finite(
    value,
    overrides,
    winning_field,
):
    overrides = dict(overrides)
    overrides[winning_field] = value
    prospective = graded_row(
        "2026-07-21",
        f"future {winning_field} non finite",
        display_verdict="PASS",
        market_anchor_selector={"labels": ["market_anchor_strict"]},
        **overrides,
    )

    summary = audit.build_audit(locked_historical_rows() + [prospective])

    assert audit.adjusted_ev(prospective) is None
    assert summary["status"] == "blocked_input_gap"
    assert summary["integrity"]["input_gap_rows"] == 1
    assert any(
        f"{winning_field}:non_finite" in missing
        for missing in summary["integrity"]["input_gaps"].values()
    )
    assert summary["counter"]["prospective_qualified_rows"] == 0
    assert summary["counter"]["rows"] == 52
    json.dumps(summary, allow_nan=False)


def test_later_non_finite_adjusted_ev_is_ignored_after_finite_truthy_winner():
    prospective = graded_row(
        "2026-07-21",
        "future finite winner",
        locked_adj_ev=0.10,
        adj_ev=float("nan"),
        ev=float("inf"),
    )

    summary = audit.build_audit(locked_historical_rows() + [prospective])

    assert audit.adjusted_ev(prospective) == 0.10
    assert summary["status"] == "collecting"
    assert summary["integrity"]["input_gap_rows"] == 0
    assert summary["counter"]["rows"] == 53
    json.dumps(summary, allow_nan=False)
