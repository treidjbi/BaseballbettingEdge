from scripts import run_post_grading_shadow_reports as runner


def test_runner_rebuilds_shadow_reports_and_prints_review_excerpt(tmp_path, monkeypatch, capsys):
    calls = []
    output_dir = tmp_path / "gate_c"
    market_anchor_output = tmp_path / "market_anchored_k_shadow_rebuild.md"
    selector_audit_output = tmp_path / "market_anchor_selector_canary_audit.md"
    confidence_referee_output = tmp_path / "confidence_referee_canary_audit.md"
    profit_rescue_output = tmp_path / "profit_rescue_audit.md"
    bet_selection_output = tmp_path / "bet_selection_edge_synthesis.md"
    strong_base_output = tmp_path / "strong_base_decision_lab.md"
    portfolio_simulator_output = tmp_path / "strong_base_portfolio_simulator.md"
    market_agreement_output = tmp_path / "market_agreement_tracker.md"
    market_agreement_jsonl = tmp_path / "market_agreement_tracker.jsonl"
    shadow_signal_output = tmp_path / "shadow_signal_synthesis_lab.md"
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
    assert "Implementation Notes" not in output
    assert "Promotion Gate" not in output
    assert "Debug Detail" not in output
