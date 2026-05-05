"""Summarize provider/source usage from dashboard artifacts.

This diagnostic reads committed dashboard JSON only. Supabase shadow sidecar
tables hold provider-run and snapshot history separately.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "dashboard" / "data" / "processed"


def load_artifact(date_str: str, data_dir: Path = DATA_DIR) -> dict:
    """Load one processed dashboard artifact by slate date."""
    path = data_dir / f"{date_str}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _count_field(rows: list[dict], field: str) -> dict[str, int]:
    counts = Counter(str(row.get(field) or "unknown") for row in rows)
    return dict(sorted(counts.items()))


def summarize_artifact(artifact: dict) -> dict:
    """Return stable source, book, opening, and warning counts."""
    pitchers = artifact.get("pitchers") or []
    tracked_picks = artifact.get("tracked_picks") or []
    warnings = artifact.get("data_warnings") or []
    if not isinstance(warnings, list):
        warnings = [str(warnings)]

    return {
        "date": artifact.get("date"),
        "generated_at": artifact.get("generated_at"),
        "pitchers": len(pitchers),
        "tracked_picks": len(tracked_picks),
        "source_counts": _count_field(pitchers, "odds_source"),
        "book_counts": _count_field(pitchers, "ref_book"),
        "opening_counts": _count_field(pitchers, "opening_odds_source"),
        "data_warnings": warnings,
    }


def _append_count_section(lines: list[str], title: str, counts: dict[str, int]) -> None:
    lines.append("")
    lines.append(f"## {title}")
    if counts:
        for key, count in counts.items():
            lines.append(f"- `{key}`: {count}")
    else:
        lines.append("- none")


def render_summary(summary: dict) -> str:
    """Render a markdown source-health summary for controller capture."""
    lines = [
        "# Source Fallback Health",
        "",
        (
            "Supabase sidecar already stores provider-run and snapshot history "
            "in `market_provider_runs`, `market_snapshots`, and "
            "`provider_coverage_audits`; this diagnostic is local artifact "
            "health only."
        ),
        "",
        f"- Date: {summary['date']}",
        f"- Generated at: {summary['generated_at']}",
        f"- Pitcher records: {summary['pitchers']}",
        f"- Tracked picks: {summary['tracked_picks']}",
    ]

    _append_count_section(lines, "Odds Sources", summary["source_counts"])
    _append_count_section(lines, "Reference Books", summary["book_counts"])
    _append_count_section(lines, "Opening Sources", summary["opening_counts"])

    lines.append("")
    lines.append("## Data Warnings")
    if summary["data_warnings"]:
        for warning in summary["data_warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Summarize provider fallback health from a processed dashboard artifact."
    )
    parser.add_argument("date", help="Slate date in YYYY-MM-DD format")
    args = parser.parse_args(argv)

    print(render_summary(summarize_artifact(load_artifact(args.date))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
