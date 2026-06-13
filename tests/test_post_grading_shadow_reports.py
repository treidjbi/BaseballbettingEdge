from scripts import run_post_grading_shadow_reports as runner


def test_runner_rebuilds_shadow_reports_and_prints_review_excerpt(tmp_path, monkeypatch, capsys):
    calls = []
    output_dir = tmp_path / "gate_c"
    market_anchor_output = tmp_path / "market_anchored_k_shadow_rebuild.md"

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

    exit_code = runner.main([
        "--output-dir",
        str(output_dir),
        "--market-anchored-output",
        str(market_anchor_output),
    ])

    assert exit_code == 0
    assert calls == [[
        "--artifact-source",
        "hybrid",
        "--output-dir",
        str(output_dir),
        "--run-workload-no-vig-audit",
        "--run-market-anchored-rebuild",
        "--market-anchored-rebuild-output",
        str(market_anchor_output),
    ]]

    output = capsys.readouterr().out
    assert "Post-grading shadow reports complete." in output
    assert "## Executive Read" in output
    assert "Strict selector: +10.78u." in output
    assert "## Read Rule" in output
    assert "Shadow-only. No production model changes." in output
    assert "Implementation Notes" not in output
