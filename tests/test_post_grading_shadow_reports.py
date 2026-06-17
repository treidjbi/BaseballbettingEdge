from scripts import run_post_grading_shadow_reports as runner


def test_runner_rebuilds_shadow_reports_and_prints_review_excerpt(tmp_path, monkeypatch, capsys):
    calls = []
    output_dir = tmp_path / "gate_c"
    market_anchor_output = tmp_path / "market_anchored_k_shadow_rebuild.md"
    selector_audit_output = tmp_path / "market_anchor_selector_canary_audit.md"

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

    exit_code = runner.main([
        "--output-dir",
        str(output_dir),
        "--market-anchored-output",
        str(market_anchor_output),
        "--market-anchor-selector-audit-output",
        str(selector_audit_output),
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
    ]

    output = capsys.readouterr().out
    assert "Post-grading shadow reports complete." in output
    assert "## Executive Read" in output
    assert "Strict selector: +10.78u." in output
    assert "## Read Rule" in output
    assert "Shadow-only. No production model changes." in output
    assert "Market-anchor selector audit excerpt:" in output
    assert "Rows with selector metadata: `24`." in output
    assert "Input Coverage" in output
    assert "Implementation Notes" not in output
    assert "Promotion Gate" not in output
