"""Run shadow-only post-grading model review reports.

This is intended for a Render cron after the official grading cron finishes.
It rebuilds research artifacts and prints the decision-facing excerpt to logs.
It does not change production picks, grading, calibration, provider order,
notifications, locks, retention, dashboard artifacts, or source-of-truth rules.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import build_pitcher_k_outcome_dataset as builder  # noqa: E402
from analytics.diagnostics import bet_selection_edge_synthesis  # noqa: E402
from analytics.diagnostics import confidence_referee_canary_audit  # noqa: E402
from analytics.diagnostics import gate_f_projection_challenger_shadow_report  # noqa: E402
from analytics.diagnostics import market_agreement_tracker  # noqa: E402
from analytics.diagnostics import market_anchor_selector_canary_audit  # noqa: E402
from analytics.diagnostics import profit_rescue_audit  # noqa: E402
from analytics.diagnostics import shadow_notification_candidate_audit  # noqa: E402


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
        "--confidence-referee-canary-output",
        type=Path,
        default=confidence_referee_canary_audit.OUTPUT_PATH,
    )
    parser.add_argument("--profit-rescue-output", type=Path, default=profit_rescue_audit.DEFAULT_OUTPUT)
    parser.add_argument("--bet-selection-edge-output", type=Path, default=bet_selection_edge_synthesis.DEFAULT_OUTPUT)
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
    parser.add_argument("--market-pick-evidence", type=Path)
    parser.add_argument("--live-market-display", type=Path)
    parser.add_argument("--market-snapshots", type=Path)
    parser.add_argument("--current-artifact", type=Path)
    parser.add_argument(
        "--gate-f-projection-output",
        type=Path,
        default=gate_f_projection_challenger_shadow_report.OUTPUT_PATH,
    )
    parser.add_argument("--shadow-notification-candidates", type=Path)
    parser.add_argument(
        "--shadow-notification-candidate-output",
        type=Path,
        default=ROOT / "analytics" / "output" / "shadow_notification_candidate_audit.md",
    )
    return parser.parse_args(argv)


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


def _market_agreement_args(args: argparse.Namespace, dataset_path: Path) -> list[str]:
    tracker_args = [
        "--gate-c-dataset",
        str(dataset_path),
        "--output-md",
        str(args.market_agreement_output_md),
        "--output-jsonl",
        str(args.market_agreement_output_jsonl),
    ]
    optional_paths = (
        ("--market-pick-evidence", args.market_pick_evidence),
        ("--live-market-display", args.live_market_display),
        ("--market-snapshots", args.market_snapshots),
        ("--current-artifact", args.current_artifact),
    )
    for flag, path in optional_paths:
        if path is not None:
            tracker_args.extend([flag, str(path)])
    return tracker_args


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
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
    builder_args.extend([
        "--run-market-anchored-rebuild",
        "--market-anchored-rebuild-output",
        str(args.market_anchored_output),
    ])

    builder.main(builder_args)
    dataset_path = args.output_dir / "pitcher_k_outcome_dataset.jsonl"
    if not args.skip_market_anchor_selector_audit:
        market_anchor_selector_canary_audit.main([
            "--input",
            str(dataset_path),
            "--output",
            str(args.market_anchor_selector_audit_output),
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
    market_agreement_tracker.main(_market_agreement_args(args, dataset_path))
    _write_gate_f_projection_report(
        dataset_path=dataset_path,
        output_path=args.gate_f_projection_output,
    )
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
