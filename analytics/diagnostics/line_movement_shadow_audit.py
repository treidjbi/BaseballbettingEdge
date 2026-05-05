"""Shadow audit for line movement and movement_conf performance."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT / "data" / "picks_history.json"

WEBHOOK_DECISION_RULE = (
    "Do not build webhooks until movement audit shows that better intraday history "
    "would change a real decision. If preview coverage is sparse or movement_conf "
    "rarely activates, webhooks may improve evidence collection but should not alter live EV yet."
)


def load_history(path: Path = HISTORY_PATH) -> list[dict]:
    """Read pick history rows from JSON."""
    return json.loads(path.read_text(encoding="utf-8"))


def movement_bucket(row: dict) -> str:
    """Bucket a pick by preview-opening availability and movement confidence."""
    source = row.get("opening_odds_source") or "unknown"
    if source != "preview":
        return "not_preview"

    conf = row.get("movement_conf")
    if conf is None:
        return "preview_unknown"

    conf_value = float(conf)
    if conf_value < 0.50:
        return "preview_heavy_fade"
    if conf_value < 0.75:
        return "preview_some_fade"
    if conf_value < 1.00:
        return "preview_minor_fade"
    return "preview_no_fade"


def summarize_rows(rows: list[dict]) -> dict[str, dict]:
    """Summarize graded win/loss rows by movement bucket."""
    buckets: dict[str, dict] = defaultdict(
        lambda: {"graded": 0, "wins": 0, "losses": 0, "pnl": 0.0}
    )

    for row in rows:
        result = row.get("result")
        if result not in {"win", "loss"}:
            continue

        bucket = buckets[movement_bucket(row)]
        bucket["graded"] += 1
        if result == "win":
            bucket["wins"] += 1
        else:
            bucket["losses"] += 1
        bucket["pnl"] += float(row.get("pnl") or 0.0)

    return {
        bucket: {**values, "pnl": round(values["pnl"], 2)}
        for bucket, values in sorted(buckets.items())
    }


def render_markdown(summary: dict[str, dict]) -> str:
    """Render the movement audit as markdown."""
    lines = [
        "# Line Movement Shadow Audit",
        "",
        (
            "Note: this is diagnostic only; do not change verdicts, EV, calibration, "
            "or webhook adoption from this alone."
        ),
        "",
        "Webhook decision rule: " + WEBHOOK_DECISION_RULE,
        "",
        "## Movement Buckets",
        "",
    ]

    if not summary:
        lines.append("- No graded win/loss rows found.")
    else:
        for bucket, row in summary.items():
            lines.append(
                f"- `{bucket}`: graded={row['graded']}, wins={row['wins']}, "
                f"losses={row['losses']}, pnl={row['pnl']:+.2f}u"
            )

    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit line movement buckets in pick history.")
    parser.add_argument("--history", type=Path, default=HISTORY_PATH, help="Path to picks_history.json")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    print(render_markdown(summarize_rows(load_history(args.history))))


if __name__ == "__main__":
    main()
