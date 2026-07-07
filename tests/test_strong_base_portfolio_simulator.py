import json
import subprocess
import sys
from pathlib import Path

from analytics.diagnostics import strong_base_portfolio_simulator as simulator


def _row(**overrides):
    row = {
        "slate_date": "2026-06-25",
        "is_tracked_pick": True,
        "result": "win",
        "side": "over",
        "display_verdict": "FIRE 1u",
        "locked_verdict": "FIRE 1u",
        "edge": 0.045,
        "adj_ev": 0.11,
        "model_no_vig_gap": 0.05,
        "model_market_relationship": "model_agrees_with_favorite",
        "quality_gate_level": "clean",
        "line_bucket": "4.5",
        "price_sign": "minus",
        "bet_timing_window": "pre_30",
        "leash_risk_bucket": "normal",
        "pitcher_archetype_bucket": "standard_starter",
        "batter_handedness_mode": "path_b",
        "lineup_real_split_count": 3,
        "market_agreement_label": "market_with_model",
        "pick_history_pnl": 0.91,
        "theoretical_pnl": 0.91,
        "beat_close_price": False,
        "beat_close_line": False,
        "price_clv_cents": 0,
    }
    row.update(overrides)
    return row


def test_current_fire_policy_is_stake_aware_and_excludes_lean_units():
    rows = [
        _row(display_verdict="FIRE 2u", locked_verdict="FIRE 2u", pick_history_pnl=0.8),
        _row(display_verdict="FIRE 1u", locked_verdict="FIRE 1u", result="loss", pick_history_pnl=-1.0),
        _row(display_verdict="LEAN", locked_verdict="LEAN", pick_history_pnl=0.91),
    ]

    summary = simulator.build_portfolio_summary(rows)
    current = summary["policies"]["current_staked_fire"]

    assert current["rows"] == 2
    assert current["units"] == 3.0
    assert current["pnl"] == 0.6
    assert current["roi"] == 0.2
    assert current["lean_rows"] == 0


def test_runtime_policy_excludes_drag_caps_but_keeps_candidate_lean_expansion():
    keep_fire = _row(pick_history_pnl=0.91)
    high_edge_fire = _row(edge=0.08, pick_history_pnl=0.91)
    market_fade_fire = _row(
        model_market_relationship="model_fades_favorite",
        side="under",
        result="loss",
        pick_history_pnl=-1.0,
    )
    lean_candidate = _row(
        display_verdict="LEAN",
        locked_verdict="LEAN",
        adj_ev=0.04,
        pick_history_pnl=0.91,
    )

    summary = simulator.build_portfolio_summary([
        keep_fire,
        high_edge_fire,
        market_fade_fire,
        lean_candidate,
    ])

    strict = summary["policies"]["strict_runtime_core_flat"]
    expansion = summary["policies"]["strict_plus_selective_lean_flat"]

    assert strict["rows"] == 1
    assert strict["pnl"] == 0.91
    assert expansion["rows"] == 2
    assert expansion["lean_rows"] == 1
    assert expansion["pnl"] == 1.82


def test_hindsight_clv_ceiling_is_separated_from_runtime_policies():
    rows = [
        _row(beat_close_price=True, pick_history_pnl=0.91),
        _row(beat_close_price=False, price_clv_cents=-10, result="loss", pick_history_pnl=-1.0),
    ]

    summary = simulator.build_portfolio_summary(rows)

    assert summary["policies"]["price_confirmed_hindsight_ceiling"]["rows"] == 1
    assert summary["policies"]["price_confirmed_hindsight_ceiling"]["uses_hindsight"] is True
    assert summary["policies"]["strict_runtime_core_flat"]["uses_hindsight"] is False


def test_render_report_states_simulator_is_read_only_and_names_next_decision():
    summary = simulator.build_portfolio_summary([
        _row(pick_history_pnl=0.91),
        _row(edge=0.08, result="loss", pick_history_pnl=-1.0),
    ])

    rendered = simulator.render_report(summary)

    assert "# Strong Base Portfolio Simulator" in rendered
    assert "read-only" in rendered
    assert "No live behavior changes" in rendered
    assert "Policy Comparison" in rendered
    assert "Next Decision" in rendered


def test_script_entrypoint_runs_from_repo_root(tmp_path):
    input_path = tmp_path / "rows.jsonl"
    output_path = tmp_path / "report.md"
    input_path.write_text(json.dumps(_row()) + "\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(Path("analytics") / "diagnostics" / "strong_base_portfolio_simulator.py"),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        check=False,
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "# Strong Base Portfolio Simulator" in output_path.read_text(encoding="utf-8")
