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
from analytics.diagnostics import market_anchor_selector_canary_audit  # noqa: E402


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


def _print_review_excerpt(report_path: Path) -> None:
    if not report_path.exists():
        print(f"Market-anchored report was not found at {report_path}")
        return

    excerpt = _extract_sections(
        report_path.read_text(encoding="utf-8"),
        {"Executive Read", "Read Rule"},
    )
    if excerpt:
        print("\nMarket-anchored review excerpt:\n")
        print(excerpt)


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
    if not args.skip_market_anchor_selector_audit:
        market_anchor_selector_canary_audit.main([
            "--input",
            str(args.output_dir / "pitcher_k_outcome_dataset.jsonl"),
            "--output",
            str(args.market_anchor_selector_audit_output),
        ])
    print("Post-grading shadow reports complete.")
    _print_review_excerpt(args.market_anchored_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
