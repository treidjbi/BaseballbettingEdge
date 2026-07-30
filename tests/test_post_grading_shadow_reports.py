import json
from types import SimpleNamespace

from scripts import run_post_grading_shadow_reports as runner


def test_runner_runs_clv_process_validation_after_agreement_and_preclose_reports(
    tmp_path, monkeypatch, capsys
):
    """The CLV target remains an offline decision report fed by bounded inputs."""
    calls = []
    output_dir = tmp_path / "gate_c"
    dataset_path = output_dir / "pitcher_k_outcome_dataset.jsonl"
    market_input = tmp_path / "market_pick_evidence.json"
    market_input.write_text("[]", encoding="utf-8")
    preclose_output = tmp_path / "gate_f_preclose_clv_proxy_lab.md"
    clv_output_dir = tmp_path / "clv"

    def fake_builder_main(argv):
        calls.append(("gate_c_build", argv))
        output_dir.mkdir(parents=True, exist_ok=True)
        dataset_path.write_text("", encoding="utf-8")

    def fake_simple_main(label):
        return lambda argv: calls.append((label, argv))

    def fake_preclose_main(argv):
        calls.append(("preclose", argv))
        preclose_output.write_text("# Pre-close\n", encoding="utf-8")

    def fake_clv_main(argv):
        calls.append(("clv", argv))
        clv_output_dir.mkdir(parents=True, exist_ok=True)
        (clv_output_dir / "clv_process_target_validation.json").write_text(
            json.dumps(
                {
                    "eligible_target_rows": 12,
                    "rows": [{"dataset_key": "one"}] * 20,
                    "proxy_buckets": {
                        "strong_preclose_clv_proxy": {"lift_vs_base_rate": 0.125}
                    },
                    "provider_era_drift": {
                        "current_therundown_propline": {"lift_vs_base_rate": 0.05}
                    },
                    "readiness": {
                        "status": "keep_as_process_kpi",
                        "fully_attributed_current_provider_targets": 12,
                        "minimum_current_provider_targets": 100,
                        "positive_proxy_lift_windows": 0,
                        "minimum_positive_windows": 2,
                    },
                }
            ),
            encoding="utf-8",
        )

    monkeypatch.setattr(runner.builder, "main", fake_builder_main)
    monkeypatch.setattr(runner.market_agreement_tracker, "main", fake_simple_main("agreement"))
    monkeypatch.setattr(
        runner,
        "gate_f_preclose_clv_proxy_lab",
        SimpleNamespace(main=fake_preclose_main, DEFAULT_OUTPUT=preclose_output),
    )
    monkeypatch.setattr(
        runner,
        "clv_process_target_validation",
        SimpleNamespace(main=fake_clv_main, DEFAULT_OUTPUT_DIR=clv_output_dir),
    )
    for module in (
        runner.market_anchor_selector_canary_audit,
        runner.market_anchor_downside_counterfactual_audit,
        runner.confidence_referee_canary_audit,
        runner.profit_rescue_audit,
        runner.bet_selection_edge_synthesis,
        runner.strong_base_decision_lab,
        runner.strong_base_portfolio_simulator,
        runner.shadow_signal_synthesis_lab,
        runner.strong_base_fire_policy_matrix,
        runner.no_drag_composite_canary_audit,
        runner.strict_runtime_core_canary_audit,
        runner.market_shrink_projection_canary_audit,
    ):
        monkeypatch.setattr(module, "main", fake_simple_main(module.__name__.split(".")[-1]))
    monkeypatch.setattr(runner, "_write_gate_f_projection_report", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_write_shadow_notification_candidate_report", lambda **kwargs: None)
    monkeypatch.setattr(runner, "_print_review_excerpt", lambda *args, **kwargs: None)

    assert runner.main(
        [
            "--output-dir",
            str(output_dir),
            "--market-pick-evidence",
            str(market_input),
            "--preclose-clv-proxy-output",
            str(preclose_output),
            "--clv-process-target-output-dir",
            str(clv_output_dir),
        ]
    ) == 0

    labels = [label for label, _ in calls]
    assert labels.index("agreement") < labels.index("preclose") < labels.index("clv")
    clv_args = next(argv for label, argv in calls if label == "clv")
    assert clv_args == [
        "--gate-c-input",
        str(dataset_path),
        "--market-input",
        str(market_input),
        "--output-dir",
        str(clv_output_dir),
    ]
    output = capsys.readouterr().out
    assert "CLV process target: coverage 12/20; strong lift +12.5%;" in output
    assert "current-provider drift +5.0%; readiness keep_as_process_kpi (12/100, 0/2 windows)." in output
    assert "dataset_key" not in output


def test_runner_skip_flag_omits_clv_process_validation():
    args = runner._parse_args(["--skip-clv-process-target-validation"])

    assert args.skip_clv_process_target_validation is True


def test_runner_rebuilds_shadow_reports_and_prints_review_excerpt(tmp_path, monkeypatch, capsys):
    calls = []
    output_dir = tmp_path / "gate_c"
    market_anchor_output = tmp_path / "market_anchored_k_shadow_rebuild.md"
    selector_audit_output = tmp_path / "market_anchor_selector_canary_audit.md"
    anchor_downside_output_md = tmp_path / "market_anchor_downside_counterfactual_audit.md"
    anchor_downside_output_json = tmp_path / "market_anchor_downside_counterfactual_audit.json"
    confidence_referee_output = tmp_path / "confidence_referee_canary_audit.md"
    profit_rescue_output = tmp_path / "profit_rescue_audit.md"
    bet_selection_output = tmp_path / "bet_selection_edge_synthesis.md"
    strong_base_output = tmp_path / "strong_base_decision_lab.md"
    portfolio_simulator_output = tmp_path / "strong_base_portfolio_simulator.md"
    market_agreement_output = tmp_path / "market_agreement_tracker.md"
    market_agreement_jsonl = tmp_path / "market_agreement_tracker.jsonl"
    shadow_signal_output = tmp_path / "shadow_signal_synthesis_lab.md"
    fire_policy_matrix_output_md = tmp_path / "strong_base_fire_policy_matrix.md"
    fire_policy_matrix_output_json = tmp_path / "strong_base_fire_policy_matrix.json"
    no_drag_output_md = tmp_path / "no_drag_composite_canary_audit.md"
    no_drag_output_json = tmp_path / "no_drag_composite_canary_audit.json"
    strict_output_md = tmp_path / "strict_runtime_core_canary_audit.md"
    strict_output_json = tmp_path / "strict_runtime_core_canary_audit.json"
    gate_f_output = tmp_path / "gate_f_projection_challenger_shadow_report.md"
    market_shrink_output = tmp_path / "market_shrink_projection_canary_audit.md"
    shadow_candidates = tmp_path / "shadow_notification_candidates.json"
    shadow_candidates.write_text("[]", encoding="utf-8")
    shadow_candidate_output = tmp_path / "shadow_notification_candidate_audit.md"

    def fake_builder_main(argv):
        calls.append(argv)
        market_anchor_output.write_text(
            "# Market-Anchored K Projection Shadow Rebuild\n\n"
            "## Executive Read\n\n"
            "- Strict selector: +10.78u.\n"
            "- Core selector: near breakeven.\n\n"
            "## Read Rule\n\n"
            "- Shadow-only. No production model changes.\n\n"
            "## Implementation Notes\n\n"
            "- Not needed in the log excerpt.\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(runner.builder, "main", fake_builder_main)

    def fake_selector_audit_main(argv):
        calls.append(("selector_audit", argv))
        selector_audit_output.write_text(
            "# Market Anchor Selector Canary Audit\n\n"
            "## Executive Read\n\n"
            "- Rows with selector metadata: `24`.\n\n"
            "## Input Coverage\n\n"
            "- Slate date range: `2026-04-28` to `2026-06-16`.\n\n"
            "## Promotion Gate\n\n"
            "- Not needed in the log excerpt.\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(runner.market_anchor_selector_canary_audit, "main", fake_selector_audit_main)

    def fake_anchor_downside_main(argv):
        calls.append(("anchor_downside", argv))
        anchor_downside_output_md.write_text(
            "# Market-Anchor Downside Counterfactual Audit\n\n"
            "## Executive Read\n\n"
            "- Decision: `keep_shadow`.\n\n"
            "## Review Gates\n\n"
            "- `would_change_floor_50`: `closed`\n\n"
            "## Debug Detail\n\n"
            "- Not needed in the log excerpt.\n",
            encoding="utf-8",
        )
        anchor_downside_output_json.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(
        runner.market_anchor_downside_counterfactual_audit,
        "main",
        fake_anchor_downside_main,
    )

    def fake_simple_report(label):
        def _fake(argv):
            calls.append((label, argv))
        return _fake

    monkeypatch.setattr(
        runner.confidence_referee_canary_audit,
        "main",
        fake_simple_report("confidence_referee_canary"),
    )
    monkeypatch.setattr(
        runner.profit_rescue_audit,
        "main",
        fake_simple_report("profit_rescue"),
    )
    monkeypatch.setattr(
        runner.bet_selection_edge_synthesis,
        "main",
        fake_simple_report("bet_selection_edge"),
    )
    monkeypatch.setattr(
        runner.strong_base_decision_lab,
        "main",
        fake_simple_report("strong_base"),
    )

    def fake_portfolio_simulator_main(argv):
        calls.append(("portfolio_simulator", argv))
        portfolio_simulator_output.write_text(
            "# Strong Base Portfolio Simulator\n\n"
            "## Executive Read\n\n"
            "- Strict runtime core: +4.25u.\n\n"
            "## Policy Comparison\n\n"
            "| Policy | Result |\n"
            "| --- | ---: |\n"
            "| `strict_runtime_core_flat` | +4.25u |\n\n"
            "## Debug Detail\n\n"
            "- Not needed in the log excerpt.\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        runner.strong_base_portfolio_simulator,
        "main",
        fake_portfolio_simulator_main,
    )
    monkeypatch.setattr(
        runner.market_agreement_tracker,
        "main",
        fake_simple_report("market_agreement"),
    )

    def fake_shadow_signal_synthesis_main(argv):
        calls.append(("shadow_signal_synthesis", argv))
        shadow_signal_output.write_text(
            "# Shadow Signal Synthesis Lab\n\n"
            "## Executive Read\n\n"
            "- Combined watch: +3.25u.\n\n"
            "## Unit Accumulation Candidate\n\n"
            "- Preferred aggressive candidate: `strict_runtime_core_plus_selective_lean`.\n\n"
            "## Market Agreement Input\n\n"
            "- Raw market-agreement rows: `12`.\n\n"
            "## Composite Policy Shapes\n\n"
            "| Signal | Result |\n"
            "| --- | ---: |\n"
            "| `combined_positive_runtime_watch` | +3.25u |\n\n"
            "## Debug Detail\n\n"
            "- Not needed in the log excerpt.\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        runner.shadow_signal_synthesis_lab,
        "main",
        fake_shadow_signal_synthesis_main,
    )

    def fake_fire_policy_matrix_main(argv):
        calls.append(("fire_policy_matrix", argv))
        fire_policy_matrix_output_md.write_text(
            "# Strong Base FIRE Policy Shadow Matrix\n\n"
            "## Executive Read\n\n"
            "- Prospective freeze date: `2026-07-30`.\n\n"
            "## Policy Matrix\n\n"
            "| Policy | Readiness |\n"
            "| --- | --- |\n"
            "| `strict_runtime_core_flat` | `collecting` |\n\n"
            "## Debug Detail\n\n"
            "- Not needed in the log excerpt.\n",
            encoding="utf-8",
        )
        fire_policy_matrix_output_json.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(
        runner.strong_base_fire_policy_matrix,
        "main",
        fake_fire_policy_matrix_main,
    )

    def fake_no_drag_main(argv):
        calls.append(("no_drag_canary", argv))
        no_drag_output_md.write_text(
            "# No-Drag Composite Prospective Canary Audit\n\n"
            "## Executive Read\n\n"
            "- Status: `collecting`.\n\n"
            "## Counter\n\n"
            "- Counter: `52/75`; `23` remaining.\n\n"
            "## Baseline Reconciliation\n\n"
            "- Rebuilt history matches the locked baseline.\n\n"
            "## Slice Audit\n\n"
            "- Not needed in the scheduler excerpt.\n",
            encoding="utf-8",
        )
        no_drag_output_json.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(runner.no_drag_composite_canary_audit, "main", fake_no_drag_main)

    def fake_strict_runtime_main(argv):
        calls.append(("strict_runtime_core", argv))
        strict_output_md.write_text(
            "# Strict Runtime Core Prospective Canary Audit\n\n"
            "## Executive Read\n\n"
            "- Status: `collecting`\n"
            "- Fingerprint: `frozen-strict-core`.\n"
            "- Current-provider counter: `20/50`.\n"
            "- Latest 14 selected slates: `17` rows, `14-3`, `+7.106u`.\n\n"
            "## Diversity Gates\n\n"
            "- UNDER rows: `0/10`.\n"
            "- Plus-price rows: `0/10`.\n"
            "- Remaining diversity blockers: `[under_rows<10, plus_price_rows<10]`.\n\n"
            "## Debug Detail\n\n"
            "- Not needed in the scheduler excerpt.\n",
            encoding="utf-8",
        )
        strict_output_json.write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(
        runner.strict_runtime_core_canary_audit,
        "main",
        fake_strict_runtime_main,
    )

    def fake_market_shrink_audit_main(argv):
        calls.append(("market_shrink_projection", argv))
        market_shrink_output.write_text(
            "# Market Shrink Projection Canary Audit\n\n"
            "## Executive Read\n\n"
            "- Rows with projection metadata: `0`.\n\n"
            "## Rollback Recommendation\n\n"
            "- Keep `MARKET_SHRINK_PROJECTION_MODE=off`.\n\n"
            "## Debug Detail\n\n"
            "- Not needed in the log excerpt.\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(
        runner.market_shrink_projection_canary_audit,
        "main",
        fake_market_shrink_audit_main,
    )
    monkeypatch.setattr(
        runner.shadow_notification_candidate_audit,
        "load_rows",
        lambda path: calls.append(("shadow_candidate_load", path)) or [],
    )
    monkeypatch.setattr(
        runner.shadow_notification_candidate_audit,
        "build_report",
        lambda rows: calls.append(("shadow_candidate_report", rows)) or "# Shadow Candidates\n",
    )

    monkeypatch.setattr(
        runner.gate_f_projection_challenger_shadow_report,
        "load_jsonl",
        lambda path: calls.append(("gate_f_load", path)) or [{"dataset_key": "row-1"}],
    )
    monkeypatch.setattr(
        runner.gate_f_projection_challenger_shadow_report,
        "build_report",
        lambda rows: calls.append(("gate_f_report", rows)) or "# Gate F\n",
    )

    exit_code = runner.main([
        "--output-dir",
        str(output_dir),
        "--market-anchored-output",
        str(market_anchor_output),
        "--market-anchor-selector-audit-output",
        str(selector_audit_output),
        "--market-anchor-downside-output-md",
        str(anchor_downside_output_md),
        "--market-anchor-downside-output-json",
        str(anchor_downside_output_json),
        "--confidence-referee-canary-output",
        str(confidence_referee_output),
        "--profit-rescue-output",
        str(profit_rescue_output),
        "--bet-selection-edge-output",
        str(bet_selection_output),
        "--strong-base-output",
        str(strong_base_output),
        "--portfolio-simulator-output",
        str(portfolio_simulator_output),
        "--market-agreement-output-md",
        str(market_agreement_output),
        "--market-agreement-output-jsonl",
        str(market_agreement_jsonl),
        "--shadow-signal-synthesis-output",
        str(shadow_signal_output),
        "--strong-base-fire-policy-matrix-output-md",
        str(fire_policy_matrix_output_md),
        "--strong-base-fire-policy-matrix-output-json",
        str(fire_policy_matrix_output_json),
        "--no-drag-canary-output-md",
        str(no_drag_output_md),
        "--no-drag-canary-output-json",
        str(no_drag_output_json),
        "--strict-runtime-core-output-md",
        str(strict_output_md),
        "--strict-runtime-core-output-json",
        str(strict_output_json),
        "--gate-f-projection-output",
        str(gate_f_output),
        "--market-shrink-projection-output",
        str(market_shrink_output),
        "--shadow-notification-candidates",
        str(shadow_candidates),
        "--shadow-notification-candidate-output",
        str(shadow_candidate_output),
    ])

    assert exit_code == 0
    assert calls == [
        [
            "--artifact-source",
            "hybrid",
            "--output-dir",
            str(output_dir),
            "--run-workload-no-vig-audit",
            "--run-market-anchored-rebuild",
            "--market-anchored-rebuild-output",
            str(market_anchor_output),
        ],
        (
            "selector_audit",
            [
                "--input",
                str(output_dir / "pitcher_k_outcome_dataset.jsonl"),
                "--output",
                str(selector_audit_output),
            ],
        ),
        (
            "anchor_downside",
            [
                "--input",
                str(output_dir / "pitcher_k_outcome_dataset.jsonl"),
                "--output-md",
                str(anchor_downside_output_md),
                "--output-json",
                str(anchor_downside_output_json),
            ],
        ),
        (
            "confidence_referee_canary",
            [
                "--input",
                str(output_dir / "pitcher_k_outcome_dataset.jsonl"),
                "--output",
                str(confidence_referee_output),
            ],
        ),
        (
            "profit_rescue",
            [
                "--input",
                str(output_dir / "pitcher_k_outcome_dataset.jsonl"),
                "--output",
                str(profit_rescue_output),
            ],
        ),
        (
            "bet_selection_edge",
            [
                "--input",
                str(output_dir / "pitcher_k_outcome_dataset.jsonl"),
                "--output",
                str(bet_selection_output),
            ],
        ),
        (
            "strong_base",
            [
                "--input",
                str(output_dir / "pitcher_k_outcome_dataset.jsonl"),
                "--output",
                str(strong_base_output),
            ],
        ),
        (
            "portfolio_simulator",
            [
                "--input",
                str(output_dir / "pitcher_k_outcome_dataset.jsonl"),
                "--output",
                str(portfolio_simulator_output),
            ],
        ),
        (
            "market_agreement",
            [
                "--gate-c-dataset",
                str(output_dir / "pitcher_k_outcome_dataset.jsonl"),
                "--output-md",
                str(market_agreement_output),
                "--output-jsonl",
                str(market_agreement_jsonl),
            ],
        ),
        (
            "shadow_signal_synthesis",
            [
                "--input",
                str(output_dir / "pitcher_k_outcome_dataset.jsonl"),
                "--market-agreement",
                str(market_agreement_jsonl),
                "--output",
                str(shadow_signal_output),
            ],
        ),
        (
            "fire_policy_matrix",
            [
                "--input",
                str(output_dir / "pitcher_k_outcome_dataset.jsonl"),
                "--output-md",
                str(fire_policy_matrix_output_md),
                "--output-json",
                str(fire_policy_matrix_output_json),
            ],
        ),
        (
            "no_drag_canary",
            [
                "--input",
                str(output_dir / "pitcher_k_outcome_dataset.jsonl"),
                "--output-md",
                str(no_drag_output_md),
                "--output-json",
                str(no_drag_output_json),
            ],
        ),
        (
            "strict_runtime_core",
            [
                "--input",
                str(output_dir / "pitcher_k_outcome_dataset.jsonl"),
                "--output-md",
                str(strict_output_md),
                "--output-json",
                str(strict_output_json),
            ],
        ),
        ("gate_f_load", output_dir / "pitcher_k_outcome_dataset.jsonl"),
        ("gate_f_report", [{"dataset_key": "row-1"}]),
        (
            "market_shrink_projection",
            [
                "--input",
                str(output_dir / "pitcher_k_outcome_dataset.jsonl"),
                "--output",
                str(market_shrink_output),
            ],
        ),
        ("shadow_candidate_load", shadow_candidates),
        ("shadow_candidate_report", []),
    ]
    assert gate_f_output.read_text(encoding="utf-8") == "# Gate F\n"
    assert shadow_candidate_output.read_text(encoding="utf-8") == "# Shadow Candidates\n"

    output = capsys.readouterr().out
    assert "Post-grading shadow reports complete." in output
    assert "## Executive Read" in output
    assert "Strict selector: +10.78u." in output
    assert "## Read Rule" in output
    assert "Shadow-only. No production model changes." in output
    assert "Market-anchor selector audit excerpt:" in output
    assert "Rows with selector metadata: `24`." in output
    assert "Input Coverage" in output
    assert "Market-anchor downside audit excerpt:" in output
    assert "Decision: `keep_shadow`" in output
    assert "would_change_floor_50" in output
    assert "Market-shrink projection canary audit excerpt:" in output
    assert "Rows with projection metadata: `0`." in output
    assert "Rollback Recommendation" in output
    assert "MARKET_SHRINK_PROJECTION_MODE=off" in output
    assert "Strong Base portfolio simulator excerpt:" in output
    assert "Strict runtime core: +4.25u." in output
    assert "Policy Comparison" in output
    assert "Shadow signal synthesis lab excerpt:" in output
    assert "Combined watch: +3.25u." in output
    assert "Unit Accumulation Candidate" in output
    assert "strict_runtime_core_plus_selective_lean" in output
    assert "Raw market-agreement rows: `12`." in output
    assert "combined_positive_runtime_watch" in output
    assert "Strong Base FIRE policy matrix excerpt:" in output
    assert "Prospective freeze date: `2026-07-30`" in output
    assert "strict_runtime_core_flat" in output
    assert "No-drag prospective canary excerpt:" in output
    assert "Status: `collecting`" in output
    assert "52/75" in output
    assert "Rebuilt history matches" in output
    assert "Strict runtime core prospective audit excerpt:" in output
    assert "Fingerprint: `frozen-strict-core`" in output
    assert "Current-provider counter: `20/50`" in output
    assert "UNDER rows: `0/10`" in output
    assert "Plus-price rows: `0/10`" in output
    assert "Slice Audit" not in output
    assert "Not needed in the scheduler excerpt" not in output
    assert "Implementation Notes" not in output
    assert "Promotion Gate" not in output
    assert "Debug Detail" not in output


def test_runner_refreshes_compact_inputs_before_one_gate_c_build(tmp_path, monkeypatch):
    calls = []
    output_dir = tmp_path / "gate_c"
    input_dir = tmp_path / "market_inputs"
    agreement_md = tmp_path / "market_agreement_tracker.md"
    agreement_jsonl = tmp_path / "market_agreement_tracker.jsonl"
    dataset_path = output_dir / "pitcher_k_outcome_dataset.jsonl"

    def fake_exporter_main(argv):
        calls.append(("export_inputs", argv))
        input_dir.mkdir(parents=True)
        for filename, payload in {
            "market_pick_evidence.json": [],
            "live_market_display_state.json": [],
            "picks_history.json": [],
            "today.json": {"slate_date": "2026-07-22", "pitchers": []},
            "manifest.json": {"artifact": "market_agreement_inputs"},
        }.items():
            (input_dir / filename).write_text(
                json.dumps(payload),
                encoding="utf-8",
            )
        return 0

    def fake_tracker_main(argv):
        phase = "market_agreement_final" if dataset_path.exists() else "market_agreement_prebuild"
        calls.append((phase, argv))
        agreement_jsonl.write_text("", encoding="utf-8")

    def fake_builder_main(argv):
        calls.append(("gate_c_build", argv))
        output_dir.mkdir(parents=True)
        dataset_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(runner.export_market_agreement_inputs, "main", fake_exporter_main)
    monkeypatch.setattr(runner.market_agreement_tracker, "main", fake_tracker_main)
    monkeypatch.setattr(runner.builder, "main", fake_builder_main)

    for module_name, module in (
        ("selector_audit", runner.market_anchor_selector_canary_audit),
        ("confidence_referee", runner.confidence_referee_canary_audit),
        ("profit_rescue", runner.profit_rescue_audit),
        ("bet_selection", runner.bet_selection_edge_synthesis),
        ("strong_base", runner.strong_base_decision_lab),
        ("portfolio", runner.strong_base_portfolio_simulator),
        ("anchor_downside", runner.market_anchor_downside_counterfactual_audit),
        ("shadow_signal", runner.shadow_signal_synthesis_lab),
        ("fire_policy_matrix", runner.strong_base_fire_policy_matrix),
        ("no_drag", runner.no_drag_composite_canary_audit),
        ("strict_runtime", runner.strict_runtime_core_canary_audit),
        ("market_shrink", runner.market_shrink_projection_canary_audit),
    ):
        monkeypatch.setattr(
            module,
            "main",
            lambda argv, label=module_name: calls.append((label, argv)),
        )
    monkeypatch.setattr(
        runner,
        "_write_gate_f_projection_report",
        lambda **kwargs: calls.append(("gate_f", kwargs)),
    )
    monkeypatch.setattr(runner, "_print_review_excerpt", lambda *args, **kwargs: None)

    exit_code = runner.main(
        [
            "--refresh-market-agreement-inputs",
            "--market-agreement-input-dir",
            str(input_dir),
            "--output-dir",
            str(output_dir),
            "--end-date",
            "2026-07-22",
            "--market-agreement-output-md",
            str(agreement_md),
            "--market-agreement-output-jsonl",
            str(agreement_jsonl),
            "--skip-strict-runtime-core-audit",
        ]
    )

    assert exit_code == 0
    assert [label for label, _ in calls[:4]] == [
        "export_inputs",
        "market_agreement_prebuild",
        "gate_c_build",
        "market_agreement_final",
    ]
    assert [label for label, _ in calls].count("gate_c_build") == 1

    export_args = calls[0][1]
    assert export_args == [
        "--output-dir",
        str(input_dir),
        "--start-date",
        runner.builder.dataset.CLEAN_WINDOW_START,
        "--end-date",
        "2026-07-22",
    ]

    prebuild_args = calls[1][1]
    assert "--history" in prebuild_args
    assert str(input_dir / "picks_history.json") in prebuild_args
    assert "--market-pick-evidence" in prebuild_args
    assert str(input_dir / "market_pick_evidence.json") in prebuild_args
    assert "--live-market-display" in prebuild_args
    assert str(input_dir / "live_market_display_state.json") in prebuild_args
    assert "--current-artifact" in prebuild_args
    assert str(input_dir / "today.json") in prebuild_args
    assert "--market-snapshots" not in prebuild_args

    builder_args = calls[2][1]
    assert builder_args.count("--market-agreement-tracker") == 1
    assert str(agreement_jsonl) in builder_args
    assert builder_args.count("--live-market-display") == 1
    assert str(input_dir / "live_market_display_state.json") in builder_args

    final_args = calls[3][1]
    assert final_args[final_args.index("--gate-c-dataset") + 1] == str(dataset_path)
    shadow_signal_args = next(args for label, args in calls if label == "shadow_signal")
    assert shadow_signal_args[shadow_signal_args.index("--market-agreement") + 1] == str(
        agreement_jsonl
    )
    no_drag_args = next(args for label, args in calls if label == "no_drag")
    assert no_drag_args[no_drag_args.index("--input") + 1] == str(dataset_path)
    assert not any(label == "strict_runtime" for label, _ in calls)
