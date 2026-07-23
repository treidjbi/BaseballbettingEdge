import subprocess
import sys
from pathlib import Path

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


def test_summarize_builds_windows_mandatory_slices_and_leave_one_slate_out(
    monkeypatch,
):
    monkeypatch.setattr(audit, "REVIEW_CLEAN_SELECTOR_FLOOR", 3)
    monkeypatch.setattr(audit, "REVIEW_STRICT_FLOOR", 3)
    monkeypatch.setattr(
        audit.preclose_proxy,
        "preclose_clv_proxy_label",
        lambda row: row.get("test_preclose_proxy", "missing"),
    )
    rows = [
        _row(
            slate_date="2026-06-24",
            pitcher="Win One",
            k_line=4.5,
            line_bucket="4.5",
            price_sign="plus",
            pick_history_pnl=1.0,
            bet_timing_window="pre_30",
            beat_close_price=True,
            leash_risk_bucket="normal",
            lineup_real_split_count=9,
            provider="propline",
            market_agreement_label="market_with_model",
            test_preclose_proxy="strong",
        ),
        _row(
            slate_date="2026-06-25",
            pitcher="Under Loss",
            side="under",
            result="loss",
            k_line=6.5,
            line_bucket="6.5",
            price_sign="minus",
            pick_history_pnl=-1.0,
            display_verdict="LEAN",
            quality_gate_level="capped",
            bet_timing_window="pre_15",
            price_clv_cents=-12,
            leash_risk_bucket="high",
            batter_handedness_mode="path_b",
            lineup_real_split_count=0,
            provider=None,
            market_agreement_label=None,
            test_preclose_proxy="weak",
        ),
        _row(
            slate_date="2026-07-10",
            pitcher="Win Two",
            k_line=5.5,
            line_bucket="5.5",
            pick_history_pnl=1.0,
            bet_timing_window="pre_30",
            beat_close_line=True,
            opportunity_bucket="normal",
            lineup_split_source="mixed",
            provider="therundown+propline",
            market_agreement_label="market_mixed",
            test_preclose_proxy="medium",
        ),
        _row(
            slate_date="2026-07-11",
            pitcher="Win Three",
            k_line=5.5,
            line_bucket="5.5",
            pick_history_pnl=1.0,
            bet_timing_window="unknown",
            opportunity_bucket="medium",
            batter_handedness_mode="path_b",
            lineup_real_split_count=0,
            provider="therundown+propline",
            market_agreement_label="market_with_model",
            test_preclose_proxy="strong",
        ),
        _row(
            slate_date="2026-07-11",
            pitcher="Non Strict",
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

    assert summary["clean_selector_rows"] == 4
    assert summary["strict_windows"]["current_provider"]["rows"] == 4
    assert summary["strict_fire_windows"]["recent_14_slates"]["rows"] == 3
    assert summary["strict_slices"]["side"]["under"]["pnl"] == -1.0
    assert summary["strict_slices"]["k_line"]["6.5"]["rows"] == 1
    assert summary["strict_slices"]["market_agreement"]["missing"]["rows"] == 1
    assert summary["strict_slices"]["provider"]["missing"]["rows"] == 1
    assert summary["strict_fire_slices"]["side"]["over"]["rows"] == 3
    assert summary["leave_one_slate_out"]["strict_all"]["minimum"]["pnl"] == 1.0
    assert summary["leave_one_slate_out"]["strict_all"]["minimum"][
        "excluded_slate_date"
    ] in {"2026-06-24", "2026-07-10", "2026-07-11"}
    assert summary["strict_fire_all_over"] is True
    assert summary["review_status"] == "separate_shadow_review_ready"


def test_render_report_keeps_over_only_idea_in_a_new_separate_shadow_review(
    monkeypatch,
):
    monkeypatch.setattr(audit, "REVIEW_CLEAN_SELECTOR_FLOOR", 1)
    monkeypatch.setattr(audit, "REVIEW_STRICT_FLOOR", 1)
    rows = [
        _row(slate_date="2026-07-10", pitcher="Win One", pick_history_pnl=1.0),
        _row(slate_date="2026-07-11", pitcher="Win Two", pick_history_pnl=1.0),
    ]

    report = audit.render_report(audit.summarize(rows))

    assert "Review Floors And Windows" in report
    assert "raw review floors" in report
    assert "all `OVER`" in report
    assert "Mandatory Strict Slices" in report
    assert "Leave-One-Slate-Out" in report
    assert "Blocking Evidence" in report
    assert "new selector id, fingerprint, baseline, plan, and prospective canary" in report
    assert "`enforce_downside` remains closed" in report


def test_market_anchor_audit_supports_direct_script_execution():
    repo_root = Path(__file__).resolve().parents[1]

    result = subprocess.run(
        [
            sys.executable,
            "analytics/diagnostics/market_anchor_selector_canary_audit.py",
            "--help",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--input" in result.stdout
