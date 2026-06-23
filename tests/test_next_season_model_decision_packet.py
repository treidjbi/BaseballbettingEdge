from analytics.diagnostics import next_season_model_decision_packet as packet


def test_decision_label_requires_sample_and_positive_pnl():
    assert packet.decision_label(rows=149, pnl=20.0, bad_slices=0) == "watch_more"
    assert packet.decision_label(rows=150, pnl=-1.0, bad_slices=0) == "blocked_negative_pnl"
    assert packet.decision_label(rows=150, pnl=10.0, bad_slices=1) == "blocked_bad_slice"
    assert packet.decision_label(rows=150, pnl=10.0, bad_slices=0) == "canary_plan_candidate"


def test_render_names_required_final_decisions():
    rendered = packet.render(
        [
            {
                "candidate": "market_supported_lean",
                "decision": "canary_plan_candidate",
                "rows": 160,
                "pnl": 8.5,
            }
        ]
    )

    assert "market_supported_lean" in rendered
    assert "Allowed offseason decisions" in rendered
    assert "draft_next_season_canary_plan" in rendered


def test_main_generates_packet_from_markdown_candidate_lab(tmp_path):
    lab_path = tmp_path / "next_season_candidate_model_lab.md"
    output_path = tmp_path / "decision_packet.md"
    lab_path.write_text(
        "\n".join(
            [
                "# Next Season Candidate Model Lab",
                "",
                "| Candidate | Status | Rows | W-L | PnL | Bad Slices |",
                "| --- | --- | ---: | ---: | ---: | ---: |",
                "| `market_supported_lean` | `review_ready` | 160 | 90-70 | 8.5 | 0 |",
                "| `fire_under_brake` | `watch` | 151 | 70-81 | -3.25 | 0 |",
                "",
            ]
        ),
        encoding="utf-8",
    )

    exit_code = packet.main(["--lab", str(lab_path), "--output", str(output_path)])

    rendered = output_path.read_text(encoding="utf-8")
    assert exit_code == 0
    assert "| `market_supported_lean` | `canary_plan_candidate` | 160 | 8.5 |" in rendered
    assert "| `fire_under_brake` | `blocked_negative_pnl` | 151 | -3.25 |" in rendered
    assert "- Candidate lab: loaded" in rendered


def test_missing_slice_metadata_blocks_positive_candidate_from_canary_plan():
    row = packet.normalize_candidate_row(
        {
            "candidate": "market_supported_lean",
            "rows": 160,
            "pnl": 8.5,
            "test_rows": 160,
            "test_pnl": 8.5,
        }
    )

    assert row["decision"] == "blocked_missing_slices"


def test_main_surfaces_missing_candidate_lab(tmp_path):
    lab_path = tmp_path / "missing_lab.md"
    output_path = tmp_path / "decision_packet.md"

    exit_code = packet.main(["--lab", str(lab_path), "--output", str(output_path)])

    rendered = output_path.read_text(encoding="utf-8")
    assert exit_code == 0
    assert "- Candidate lab: missing" in rendered
    assert "No candidate rows loaded." in rendered


def test_source_status_blocks_positive_candidate_from_canary_plan():
    candidates = [
        {
            "candidate": "market_supported_lean",
            "decision": "canary_plan_candidate",
            "rows": 160,
            "pnl": 8.5,
            "bad_slices": 0,
        }
    ]
    source_statuses = [
        {"label": "Candidate lab", "status": "loaded", "path": "candidate.md", "rows": 1},
        {"label": "Seasonal audit", "status": "missing", "path": "seasonal.md", "rows": None},
    ]

    gated = packet.gate_candidate_decisions(candidates, source_statuses)

    assert gated[0]["decision"] == "blocked_unavailable_sources"
