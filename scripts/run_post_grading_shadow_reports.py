"""Run shadow-only post-grading model review reports.

This is intended for a Render cron after the official grading cron finishes.
It rebuilds research artifacts and prints the decision-facing excerpt to logs.
It does not change production picks, grading, calibration, provider order,
notifications, locks, retention, dashboard artifacts, or source-of-truth rules.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import build_pitcher_k_outcome_dataset as builder  # noqa: E402
from scripts import export_market_agreement_inputs  # noqa: E402
from analytics.diagnostics import bet_selection_edge_synthesis  # noqa: E402
from analytics.diagnostics import confidence_referee_canary_audit  # noqa: E402
from analytics.diagnostics import clv_process_target_validation  # noqa: E402
from analytics.diagnostics import gate_f_projection_challenger_shadow_report  # noqa: E402
from analytics.diagnostics import gate_f_preclose_clv_proxy_lab  # noqa: E402
from analytics.diagnostics import market_agreement_tracker  # noqa: E402
from analytics.diagnostics import market_anchor_downside_counterfactual_audit  # noqa: E402
from analytics.diagnostics import market_anchor_selector_canary_audit  # noqa: E402
from analytics.diagnostics import market_shrink_projection_canary_audit  # noqa: E402
from analytics.diagnostics import no_drag_composite_canary_audit  # noqa: E402
from analytics.diagnostics import profit_rescue_audit  # noqa: E402
from analytics.diagnostics import shadow_signal_synthesis_lab  # noqa: E402
from analytics.diagnostics import shadow_notification_candidate_audit  # noqa: E402
from analytics.diagnostics import strong_base_decision_lab  # noqa: E402
from analytics.diagnostics import strong_base_fire_policy_matrix  # noqa: E402
from analytics.diagnostics import strong_base_portfolio_simulator  # noqa: E402
from analytics.diagnostics import strict_runtime_core_canary_audit  # noqa: E402


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-source", choices=("hybrid", "local", "production"), default="hybrid")
    parser.add_argument("--artifact-api-url")
    parser.add_argument("--output-dir", type=Path, default=builder.DEFAULT_OUTPUT_DIR)
    parser.add_argument("--start-date", default=builder.dataset.CLEAN_WINDOW_START)
    parser.add_argument("--end-date")
    parser.add_argument(
        "--market-anchored-output",
        type=Path,
        default=builder.DEFAULT_MARKET_ANCHORED_REBUILD_OUTPUT,
    )
    parser.add_argument(
        "--skip-workload-no-vig-audit",
        action="store_true",
        help="Only skip this if the workload/no-vig report is being run separately.",
    )
    parser.add_argument(
        "--market-anchor-selector-audit-output",
        type=Path,
        default=ROOT / "analytics" / "output" / "market_anchor_selector_canary_audit.md",
    )
    parser.add_argument(
        "--skip-market-anchor-selector-audit",
        action="store_true",
        help="Skip only when selector metadata has not been deployed yet.",
    )
    parser.add_argument(
        "--market-anchor-downside-output-md",
        type=Path,
        default=market_anchor_downside_counterfactual_audit.DEFAULT_OUTPUT_MD,
    )
    parser.add_argument(
        "--market-anchor-downside-output-json",
        type=Path,
        default=market_anchor_downside_counterfactual_audit.DEFAULT_OUTPUT_JSON,
    )
    parser.add_argument(
        "--skip-market-anchor-downside-counterfactual-audit",
        action="store_true",
        help="Skip only when the stored market-anchor selector cohort is intentionally unavailable.",
    )
    parser.add_argument(
        "--confidence-referee-canary-output",
        type=Path,
        default=confidence_referee_canary_audit.OUTPUT_PATH,
    )
    parser.add_argument("--profit-rescue-output", type=Path, default=profit_rescue_audit.DEFAULT_OUTPUT)
    parser.add_argument("--bet-selection-edge-output", type=Path, default=bet_selection_edge_synthesis.DEFAULT_OUTPUT)
    parser.add_argument("--strong-base-output", type=Path, default=strong_base_decision_lab.DEFAULT_OUTPUT)
    parser.add_argument(
        "--portfolio-simulator-output",
        type=Path,
        default=strong_base_portfolio_simulator.DEFAULT_OUTPUT,
    )
    parser.add_argument(
        "--market-agreement-output-md",
        type=Path,
        default=market_agreement_tracker.OUTPUT_MD_PATH,
    )
    parser.add_argument(
        "--market-agreement-output-jsonl",
        type=Path,
        default=market_agreement_tracker.OUTPUT_JSONL_PATH,
    )
    parser.add_argument(
        "--preclose-clv-proxy-output",
        type=Path,
        default=gate_f_preclose_clv_proxy_lab.DEFAULT_OUTPUT,
    )
    parser.add_argument(
        "--clv-process-target-output-dir",
        type=Path,
        default=clv_process_target_validation.DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument(
        "--clv-process-target-market-input",
        type=Path,
        default=export_market_agreement_inputs.DEFAULT_OUTPUT_DIR / "market_pick_evidence.json",
        help="Bounded compact market evidence used only for the offline CLV target.",
    )
    parser.add_argument(
        "--skip-clv-process-target-validation",
        action="store_true",
        help="Skip only when the bounded CLV process-target review runs separately.",
    )
    parser.add_argument(
        "--shadow-signal-synthesis-output",
        type=Path,
        default=shadow_signal_synthesis_lab.DEFAULT_OUTPUT,
    )
    parser.add_argument(
        "--strong-base-fire-policy-matrix-output-md",
        type=Path,
        default=strong_base_fire_policy_matrix.DEFAULT_OUTPUT_MD,
    )
    parser.add_argument(
        "--strong-base-fire-policy-matrix-output-json",
        type=Path,
        default=strong_base_fire_policy_matrix.DEFAULT_OUTPUT_JSON,
    )
    parser.add_argument(
        "--skip-strong-base-fire-policy-matrix",
        action="store_true",
        help="Skip the frozen research-only FIRE policy matrix.",
    )
    parser.add_argument(
        "--no-drag-canary-output-md",
        type=Path,
        default=no_drag_composite_canary_audit.DEFAULT_OUTPUT_MD,
    )
    parser.add_argument(
        "--no-drag-canary-output-json",
        type=Path,
        default=no_drag_composite_canary_audit.DEFAULT_OUTPUT_JSON,
    )
    parser.add_argument(
        "--strict-runtime-core-output-md",
        type=Path,
        default=strict_runtime_core_canary_audit.DEFAULT_OUTPUT_MD,
    )
    parser.add_argument(
        "--strict-runtime-core-output-json",
        type=Path,
        default=strict_runtime_core_canary_audit.DEFAULT_OUTPUT_JSON,
    )
    parser.add_argument(
        "--skip-strict-runtime-core-audit",
        action="store_true",
        help="Skip the frozen research-only strict-runtime-core audit.",
    )
    parser.add_argument("--market-pick-evidence", type=Path)
    parser.add_argument("--live-market-display", type=Path)
    parser.add_argument("--market-snapshots", type=Path)
    parser.add_argument("--current-artifact", type=Path)
    parser.add_argument(
        "--refresh-market-agreement-inputs",
        action="store_true",
        help=(
            "Read bounded compact Supabase evidence and production artifacts "
            "before the single Gate C build."
        ),
    )
    parser.add_argument(
        "--market-agreement-input-dir",
        type=Path,
        default=export_market_agreement_inputs.DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument(
        "--gate-f-projection-output",
        type=Path,
        default=gate_f_projection_challenger_shadow_report.OUTPUT_PATH,
    )
    parser.add_argument(
        "--market-shrink-projection-output",
        type=Path,
        default=market_shrink_projection_canary_audit.DEFAULT_OUTPUT,
    )
    parser.add_argument("--shadow-notification-candidates", type=Path)
    parser.add_argument(
        "--shadow-notification-candidate-output",
        type=Path,
        default=ROOT / "analytics" / "output" / "shadow_notification_candidate_audit.md",
    )
    args = parser.parse_args(argv)
    if args.refresh_market_agreement_inputs and args.market_snapshots is not None:
        parser.error(
            "--market-snapshots is forbidden with --refresh-market-agreement-inputs"
        )
    return args


def _extract_sections(markdown: str, section_titles: set[str]) -> str:
    lines = markdown.splitlines()
    selected: list[str] = []
    capture = False
    for line in lines:
        if line.startswith("## "):
            capture = line[3:].strip() in section_titles
        if capture:
            selected.append(line)
    return "\n".join(selected).strip()


def _print_review_excerpt(report_path: Path, *, label: str, section_titles: set[str]) -> None:
    if not report_path.exists():
        print(f"{label} report was not found at {report_path}")
        return

    excerpt = _extract_sections(
        report_path.read_text(encoding="utf-8"),
        section_titles,
    )
    if excerpt:
        print(f"\n{label} excerpt:\n")
        print(excerpt)


def _write_gate_f_projection_report(*, dataset_path: Path, output_path: Path) -> None:
    rows = gate_f_projection_challenger_shadow_report.load_jsonl(dataset_path)
    report = gate_f_projection_challenger_shadow_report.build_report(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report if report.endswith("\n") else f"{report}\n", encoding="utf-8")
    print(f"Wrote {output_path} ({len(rows)} source rows)")


def _write_shadow_notification_candidate_report(*, candidates_path: Path | None, output_path: Path) -> None:
    if candidates_path is None:
        return
    rows = shadow_notification_candidate_audit.load_rows(candidates_path)
    report = shadow_notification_candidate_audit.build_report(rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report if report.endswith("\n") else f"{report}\n", encoding="utf-8")
    print(f"Wrote {output_path} ({len(rows)} source rows)")


def _clv_process_decision(summary: dict[str, object]) -> str:
    readiness = summary.get("readiness")
    if not isinstance(readiness, dict):
        return "proxy_failed"
    status = readiness.get("status")
    if status in {"keep_as_process_kpi", "ready_for_proxy_design"}:
        return str(status)
    return "proxy_failed"


def _format_percent(value: object) -> str:
    try:
        return f"{float(value):+.1%}"
    except (TypeError, ValueError):
        return "--"


def _print_clv_process_summary(output_dir: Path) -> None:
    """Print the bounded CLV process summary, never rows or pick actions."""
    path = output_dir / "clv_process_target_validation.json"
    if not path.exists():
        print("CLV process target: coverage --; strong lift --; current-provider drift --; readiness proxy_failed.")
        return
    try:
        summary = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("CLV process target: coverage --; strong lift --; current-provider drift --; readiness proxy_failed.")
        return
    if not isinstance(summary, dict):
        print("CLV process target: coverage --; strong lift --; current-provider drift --; readiness proxy_failed.")
        return
    rows = summary.get("rows")
    total_rows = len(rows) if isinstance(rows, list) else 0
    eligible_rows = summary.get("eligible_target_rows", 0)
    proxy_buckets = summary.get("proxy_buckets")
    strong_bucket = proxy_buckets.get("strong_preclose_clv_proxy", {}) if isinstance(proxy_buckets, dict) else {}
    strong_lift = strong_bucket.get("lift_vs_base_rate") if isinstance(strong_bucket, dict) else None
    drift_buckets = summary.get("provider_era_drift")
    current_drift = None
    if isinstance(drift_buckets, dict):
        current_bucket = drift_buckets.get("current_therundown_propline", {})
        if isinstance(current_bucket, dict):
            current_drift = current_bucket.get("lift_vs_base_rate")
    readiness = summary.get("readiness")
    if not isinstance(readiness, dict):
        readiness = {}
    decision = _clv_process_decision(summary)
    attributed = readiness.get("fully_attributed_current_provider_targets", 0)
    minimum_targets = readiness.get("minimum_current_provider_targets", 100)
    positive_windows = readiness.get("positive_proxy_lift_windows", 0)
    minimum_windows = readiness.get("minimum_positive_windows", 2)
    print(
        "CLV process target: "
        f"coverage {eligible_rows}/{total_rows}; strong lift {_format_percent(strong_lift)}; "
        f"current-provider drift {_format_percent(current_drift)}; readiness {decision} "
        f"({attributed}/{minimum_targets}, {positive_windows}/{minimum_windows} windows)."
    )


def _market_agreement_args(
    args: argparse.Namespace,
    dataset_path: Path,
    *,
    history_path: Path | None = None,
    market_pick_evidence_path: Path | None = None,
    live_market_display_path: Path | None = None,
    current_artifact_path: Path | None = None,
) -> list[str]:
    tracker_args = [
        "--gate-c-dataset",
        str(dataset_path),
        "--output-md",
        str(args.market_agreement_output_md),
        "--output-jsonl",
        str(args.market_agreement_output_jsonl),
    ]
    optional_paths = (
        ("--history", history_path),
        (
            "--market-pick-evidence",
            market_pick_evidence_path
            if market_pick_evidence_path is not None
            else args.market_pick_evidence,
        ),
        (
            "--live-market-display",
            live_market_display_path
            if live_market_display_path is not None
            else args.live_market_display,
        ),
        ("--market-snapshots", args.market_snapshots),
        (
            "--current-artifact",
            current_artifact_path
            if current_artifact_path is not None
            else args.current_artifact,
        ),
    )
    for flag, path in optional_paths:
        if path is not None:
            tracker_args.extend([flag, str(path)])
    return tracker_args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    dataset_path = args.output_dir / "pitcher_k_outcome_dataset.jsonl"
    refreshed_history_path: Path | None = None
    refreshed_evidence_path: Path | None = None
    refreshed_display_path: Path | None = None
    refreshed_current_artifact_path: Path | None = None

    if args.refresh_market_agreement_inputs:
        export_args = [
            "--output-dir",
            str(args.market_agreement_input_dir),
            "--start-date",
            args.start_date,
        ]
        if args.end_date:
            export_args.extend(["--end-date", args.end_date])
        if args.artifact_api_url:
            export_args.extend(["--artifact-api-url", args.artifact_api_url])
        export_market_agreement_inputs.main(export_args)
        refreshed_history_path = args.market_agreement_input_dir / "picks_history.json"
        refreshed_evidence_path = (
            args.market_agreement_input_dir / "market_pick_evidence.json"
        )
        refreshed_display_path = (
            args.market_agreement_input_dir / "live_market_display_state.json"
        )
        refreshed_current_artifact_path = args.market_agreement_input_dir / "today.json"
        market_agreement_tracker.main(
            _market_agreement_args(
                args,
                dataset_path,
                history_path=refreshed_history_path,
                market_pick_evidence_path=refreshed_evidence_path,
                live_market_display_path=refreshed_display_path,
                current_artifact_path=refreshed_current_artifact_path,
            )
        )

    builder_args = [
        "--artifact-source",
        args.artifact_source,
        "--output-dir",
        str(args.output_dir),
    ]
    if args.artifact_api_url:
        builder_args.extend(["--artifact-api-url", args.artifact_api_url])
    if args.start_date != builder.dataset.CLEAN_WINDOW_START:
        builder_args.extend(["--start-date", args.start_date])
    if args.end_date:
        builder_args.extend(["--end-date", args.end_date])
    if not args.skip_workload_no_vig_audit:
        builder_args.append("--run-workload-no-vig-audit")
    if args.refresh_market_agreement_inputs:
        builder_args.extend(
            [
                "--market-agreement-tracker",
                str(args.market_agreement_output_jsonl),
                "--live-market-display",
                str(refreshed_display_path),
            ]
        )
    builder_args.extend([
        "--run-market-anchored-rebuild",
        "--market-anchored-rebuild-output",
        str(args.market_anchored_output),
    ])

    builder.main(builder_args)
    if args.refresh_market_agreement_inputs:
        market_agreement_tracker.main(
            _market_agreement_args(
                args,
                dataset_path,
                history_path=refreshed_history_path,
                market_pick_evidence_path=refreshed_evidence_path,
                live_market_display_path=refreshed_display_path,
                current_artifact_path=refreshed_current_artifact_path,
            )
        )
    if not args.skip_market_anchor_selector_audit:
        market_anchor_selector_canary_audit.main([
            "--input",
            str(dataset_path),
            "--output",
            str(args.market_anchor_selector_audit_output),
        ])
    if not args.skip_market_anchor_downside_counterfactual_audit:
        market_anchor_downside_counterfactual_audit.main([
            "--input",
            str(dataset_path),
            "--output-md",
            str(args.market_anchor_downside_output_md),
            "--output-json",
            str(args.market_anchor_downside_output_json),
        ])
    confidence_referee_canary_audit.main([
        "--input",
        str(dataset_path),
        "--output",
        str(args.confidence_referee_canary_output),
    ])
    profit_rescue_audit.main([
        "--input",
        str(dataset_path),
        "--output",
        str(args.profit_rescue_output),
    ])
    bet_selection_edge_synthesis.main([
        "--input",
        str(dataset_path),
        "--output",
        str(args.bet_selection_edge_output),
    ])
    strong_base_decision_lab.main([
        "--input",
        str(dataset_path),
        "--output",
        str(args.strong_base_output),
    ])
    strong_base_portfolio_simulator.main([
        "--input",
        str(dataset_path),
        "--output",
        str(args.portfolio_simulator_output),
    ])
    if not args.refresh_market_agreement_inputs:
        market_agreement_tracker.main(_market_agreement_args(args, dataset_path))
    gate_f_preclose_clv_proxy_lab.main([
        "--input",
        str(dataset_path),
        "--output",
        str(args.preclose_clv_proxy_output),
    ])
    if not args.skip_clv_process_target_validation:
        clv_market_input = (
            refreshed_evidence_path
            if refreshed_evidence_path is not None
            else args.market_pick_evidence or args.clv_process_target_market_input
        )
        clv_process_target_validation.main([
            "--gate-c-input",
            str(dataset_path),
            "--market-input",
            str(clv_market_input),
            "--output-dir",
            str(args.clv_process_target_output_dir),
        ])
        _print_clv_process_summary(args.clv_process_target_output_dir)
    shadow_signal_synthesis_lab.main([
        "--input",
        str(dataset_path),
        "--market-agreement",
        str(args.market_agreement_output_jsonl),
        "--output",
        str(args.shadow_signal_synthesis_output),
    ])
    if not args.skip_strong_base_fire_policy_matrix:
        strong_base_fire_policy_matrix.main([
            "--input",
            str(dataset_path),
            "--output-md",
            str(args.strong_base_fire_policy_matrix_output_md),
            "--output-json",
            str(args.strong_base_fire_policy_matrix_output_json),
        ])
    no_drag_composite_canary_audit.main([
        "--input",
        str(dataset_path),
        "--output-md",
        str(args.no_drag_canary_output_md),
        "--output-json",
        str(args.no_drag_canary_output_json),
    ])
    if not args.skip_strict_runtime_core_audit:
        strict_runtime_core_canary_audit.main([
            "--input",
            str(dataset_path),
            "--output-md",
            str(args.strict_runtime_core_output_md),
            "--output-json",
            str(args.strict_runtime_core_output_json),
        ])
    _write_gate_f_projection_report(
        dataset_path=dataset_path,
        output_path=args.gate_f_projection_output,
    )
    market_shrink_projection_canary_audit.main([
        "--input",
        str(dataset_path),
        "--output",
        str(args.market_shrink_projection_output),
    ])
    _write_shadow_notification_candidate_report(
        candidates_path=args.shadow_notification_candidates,
        output_path=args.shadow_notification_candidate_output,
    )
    print("Post-grading shadow reports complete.")
    _print_review_excerpt(
        args.market_anchored_output,
        label="Market-anchored review",
        section_titles={"Executive Read", "Read Rule"},
    )
    if not args.skip_market_anchor_selector_audit:
        _print_review_excerpt(
            args.market_anchor_selector_audit_output,
            label="Market-anchor selector audit",
            section_titles={"Executive Read", "Input Coverage"},
        )
    if not args.skip_market_anchor_downside_counterfactual_audit:
        _print_review_excerpt(
            args.market_anchor_downside_output_md,
            label="Market-anchor downside audit",
            section_titles={"Executive Read", "Review Gates"},
        )
    _print_review_excerpt(
        args.market_shrink_projection_output,
        label="Market-shrink projection canary audit",
        section_titles={"Executive Read", "Rollback Recommendation"},
    )
    _print_review_excerpt(
        args.strong_base_output,
        label="Strong Base decision lab",
        section_titles={"Executive Read", "Candidate Policy Draft"},
    )
    _print_review_excerpt(
        args.portfolio_simulator_output,
        label="Strong Base portfolio simulator",
        section_titles={"Executive Read", "Policy Comparison"},
    )
    _print_review_excerpt(
        args.shadow_signal_synthesis_output,
        label="Shadow signal synthesis lab",
        section_titles={
            "Executive Read",
            "Unit Accumulation Candidate",
            "Market Agreement Input",
            "Composite Policy Shapes",
        },
    )
    if not args.skip_strong_base_fire_policy_matrix:
        _print_review_excerpt(
            args.strong_base_fire_policy_matrix_output_md,
            label="Strong Base FIRE policy matrix",
            section_titles={"Executive Read", "Policy Matrix"},
        )
    _print_review_excerpt(
        args.no_drag_canary_output_md,
        label="No-drag prospective canary",
        section_titles={"Executive Read", "Counter", "Baseline Reconciliation"},
    )
    if not args.skip_strict_runtime_core_audit:
        _print_review_excerpt(
            args.strict_runtime_core_output_md,
            label="Strict runtime core prospective audit",
            section_titles={"Executive Read", "Diversity Gates"},
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
