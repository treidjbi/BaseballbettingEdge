"""Render the season-end decision packet for next-season model canaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LAB = ROOT / "analytics" / "output" / "next_season_candidate_model_lab.json"
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "next_season_model_decision_packet.md"


def decision_label(*, rows: int, pnl: float, bad_slices: int) -> str:
    if rows < 150:
        return "watch_more"
    if pnl <= 0:
        return "blocked_negative_pnl"
    if bad_slices > 0:
        return "blocked_bad_slice"
    return "canary_plan_candidate"


def render(candidates: list[dict[str, Any]]) -> str:
    lines = [
        "# Next Season Model Decision Packet",
        "",
        "Research-only. This packet does not change live behavior.",
        "",
        "| Candidate | Decision | Rows | PnL |",
        "| --- | --- | ---: | ---: |",
    ]
    for row in candidates:
        lines.append(f"| `{row['candidate']}` | `{row['decision']}` | {row['rows']} | {row['pnl']} |")
    lines.extend(
        [
            "",
            "## Allowed offseason decisions",
            "",
            "- `watch_more`",
            "- `drop_candidate`",
            "- `draft_next_season_canary_plan`",
            "- `keep_research_only`",
            "",
            "## Still not allowed from this packet",
            "",
            "- Live lambda change",
            "- Threshold or staking change",
            "- Provider/source switch",
            "- Notification behavior change",
            "- Lock or retention behavior change",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    candidates: list[dict[str, Any]] = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(candidates), encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
