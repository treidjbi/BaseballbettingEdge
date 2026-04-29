"""Quality-gate audit for raw versus actionable betting verdicts."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT / "data" / "picks_history.json"
DEFAULT_SINCE = "2026-04-28"
VERDICT_ORDER = ["PASS", "LEAN", "FIRE 1u", "FIRE 2u"]
GATE_LEVEL_ORDER = ["clean", "capped", "blocked"]


def load_history(path: Path) -> list[dict]:
    """Load pick history rows from a JSON file."""
    return json.loads(path.read_text(encoding="utf-8"))


def filter_rows(
    rows: list[dict],
    since: str | None = DEFAULT_SINCE,
    all_history: bool = False,
) -> list[dict]:
    """Filter rows to the clean evaluation window unless all-history is requested."""
    if all_history or since is None:
        return list(rows)

    since_date = date.fromisoformat(since)
    filtered: list[dict] = []
    for row in rows:
        raw_date = row.get("date")
        if raw_date in (None, ""):
            continue
        try:
            if date.fromisoformat(str(raw_date)) >= since_date:
                filtered.append(row)
        except ValueError:
            continue
    return filtered


def _raw_verdict(row: dict) -> str:
    return str(row.get("raw_verdict") or row.get("verdict") or "missing")


def _actionable_verdict(row: dict) -> str:
    return str(row.get("actionable_verdict") or row.get("verdict") or "missing")


def _quality_level(row: dict) -> str:
    return str(row.get("quality_gate_level") or "clean")


def _input_flags(row: dict) -> list[str]:
    flags = row.get("input_quality_flags") or []
    if isinstance(flags, str):
        return [flags]
    if isinstance(flags, list):
        return [str(flag) for flag in flags if flag not in (None, "")]
    return []


def _ordered_keys(counter: Counter, preferred_order: list[str] | None = None) -> list[str]:
    keys: list[str] = []
    for key in preferred_order or []:
        if key in counter:
            keys.append(key)
    keys.extend(sorted(key for key in counter if key not in keys))
    return keys


def _is_protected_fire_2u(row: dict) -> bool:
    return _raw_verdict(row) == "FIRE 2u" and _actionable_verdict(row) != "FIRE 2u"


def _graded_outcomes_by_level(rows: list[dict]) -> dict[str, dict]:
    grouped: dict[str, dict] = defaultdict(
        lambda: {"graded": 0, "wins": 0, "losses": 0, "pnl_total": 0.0}
    )
    for row in rows:
        result = row.get("result")
        if result in (None, ""):
            continue

        level = _quality_level(row)
        bucket = grouped[level]
        bucket["graded"] += 1
        if result == "win":
            bucket["wins"] += 1
        elif result == "loss":
            bucket["losses"] += 1
        bucket["pnl_total"] += float(row.get("pnl") or 0.0)

    for bucket in grouped.values():
        if bucket["graded"]:
            bucket["avg_pnl"] = bucket["pnl_total"] / bucket["graded"]
        else:
            bucket["avg_pnl"] = 0.0
    return dict(grouped)


def _line_value(row: dict) -> str:
    value = row.get("line")
    if value is None:
        value = row.get("k_line")
    return "--" if value is None else str(value)


def _example_line(row: dict) -> str:
    pitcher = str(row.get("pitcher") or "Unknown pitcher")
    context = " ".join(
        part
        for part in [
            str(row.get("date") or ""),
            f"{row.get('team', '')}@{row.get('opp_team', '')}".strip("@"),
            str(row.get("side") or "").upper(),
            f"K {_line_value(row)}",
        ]
        if part
    )
    reason = row.get("verdict_cap_reason") or ", ".join(_input_flags(row)) or "quality gate"
    raw_adj_ev = row.get("raw_adj_ev")
    ev_text = "" if raw_adj_ev is None else f", raw_adj_ev={float(raw_adj_ev):+.1%}"
    return (
        f"- `{pitcher}` ({context}): raw=`{_raw_verdict(row)}`, actionable=`{_actionable_verdict(row)}`, "
        f"level=`{_quality_level(row)}`, reason={reason}{ev_text}"
    )


def _append_counter(lines: list[str], counter: Counter, order: list[str] | None = None) -> None:
    if not counter:
        lines.append("- None.")
        return
    for key in _ordered_keys(counter, order):
        lines.append(f"- `{key}`: {counter[key]}")


def build_report(
    rows: list[dict],
    since: str | None = DEFAULT_SINCE,
    all_history: bool = False,
) -> str:
    """Build a markdown report for input-quality gate behavior."""
    scoped_rows = filter_rows(rows, since=since, all_history=all_history)
    raw_counts = Counter(_raw_verdict(row) for row in scoped_rows)
    actionable_counts = Counter(_actionable_verdict(row) for row in scoped_rows)
    level_counts = Counter(_quality_level(row) for row in scoped_rows)
    flag_counts = Counter(flag for row in scoped_rows for flag in _input_flags(row))
    protected_rows = [row for row in scoped_rows if _is_protected_fire_2u(row)]
    graded_by_level = _graded_outcomes_by_level(scoped_rows)

    scope_label = "all history" if all_history else f"{since}+"
    lines = [
        "# E5 Quality Gate Audit",
        "",
        "This audit compares raw model verdicts against actionable betting verdicts after input-quality gates.",
        "",
        "## Scope",
        "",
        f"- Rows in scope: {len(scoped_rows)}",
        f"- History window: {scope_label}",
        "",
        "## Raw Verdict Counts",
        "",
    ]
    _append_counter(lines, raw_counts, VERDICT_ORDER)

    lines.extend(["", "## Actionable Verdict Counts", ""])
    _append_counter(lines, actionable_counts, VERDICT_ORDER)

    lines.extend(["", "## Quality Gate Levels", ""])
    _append_counter(lines, level_counts, GATE_LEVEL_ORDER)

    lines.extend(["", "## Input Quality Flags", ""])
    if flag_counts:
        _append_counter(lines, flag_counts)
    else:
        lines.append("- No input quality flags found.")

    lines.extend(
        [
            "",
            "## Raw FIRE 2u Protection",
            "",
            f"- Protected raw `FIRE 2u` rows: {len(protected_rows)}",
            "",
            "## Graded Outcomes By Quality Level",
            "",
        ]
    )
    if graded_by_level:
        for level in _ordered_keys(Counter({key: value["graded"] for key, value in graded_by_level.items()}), GATE_LEVEL_ORDER):
            row = graded_by_level[level]
            lines.append(
                f"- `{level}`: graded={row['graded']}, wins={row['wins']}, losses={row['losses']}, avg_pnl={row['avg_pnl']:+.2f}"
            )
    else:
        lines.append("- No graded rows in scope.")

    lines.extend(["", "## Examples Of Capped Or Blocked Picks", ""])
    if protected_rows:
        for row in protected_rows[:10]:
            lines.append(_example_line(row))
    else:
        lines.append("- No capped or blocked raw `FIRE 2u` examples in scope.")

    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit input-quality gates in pick history.")
    parser.add_argument("--history", type=Path, default=HISTORY_PATH, help="Path to picks_history.json")
    parser.add_argument("--since", default=DEFAULT_SINCE, help="ISO date lower bound for primary read")
    parser.add_argument(
        "--all-history",
        action="store_true",
        help="Include all rows instead of the default clean evaluation window",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    print(
        build_report(
            load_history(args.history),
            since=args.since,
            all_history=args.all_history,
        )
    )


if __name__ == "__main__":
    main()
