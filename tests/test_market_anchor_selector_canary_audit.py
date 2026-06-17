from analytics.diagnostics import market_anchor_selector_canary_audit as audit


def _row(**overrides):
    row = {
        "slate_date": "2026-06-16",
        "pitcher": "Example Starter",
        "side": "over",
        "result": "win",
        "pick_history_pnl": 0.91,
        "is_tracked_pick": True,
        "display_verdict": "FIRE 1u",
        "raw_verdict": "FIRE 1u",
        "quality_gate_level": "clean",
        "line_bucket": "5.5",
        "price_sign": "minus",
        "model_market_relationship": "model_agrees_with_favorite",
        "market_anchor_selector": {
            "mode": "shadow",
            "labels": [
                "market_anchor_side_agrees",
                "market_anchor_core",
                "market_anchor_strict",
            ],
            "would_verdict": "FIRE 1u",
            "applied": False,
        },
    }
    row.update(overrides)
    return row


def test_summarize_counts_strict_and_non_strict_fire_rows():
    rows = [
        _row(result="win", pick_history_pnl=0.91),
        _row(
            pitcher="Loss Starter",
            result="loss",
            pick_history_pnl=-1.0,
            market_anchor_selector={
                "mode": "shadow",
                "labels": ["market_anchor_side_agrees"],
                "would_verdict": "LEAN",
                "applied": False,
            },
        ),
    ]

    summary = audit.summarize(rows)

    assert summary["tracked_rows"] == 2
    assert summary["strict_fire"]["rows"] == 1
    assert summary["non_strict_fire"]["rows"] == 1
    assert summary["strict_fire"]["pnl"] == 0.91
    assert summary["non_strict_fire"]["pnl"] == -1.0


def test_render_report_states_shadow_only_boundary():
    report = audit.render_report(audit.summarize([_row()]))

    assert "# Market Anchor Selector Canary Audit" in report
    assert "Shadow-only" in report
    assert "does not change live" in report
    assert "Promotion Gate" in report


def test_render_report_warns_when_input_ends_before_selector_deploy():
    report = audit.render_report(
        audit.summarize(
            [
                _row(
                    slate_date="2026-06-12",
                    market_anchor_selector=None,
                )
            ]
        )
    )

    assert "Input Coverage" in report
    assert "Input ends before selector shadow deployment" in report
