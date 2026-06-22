"""Audit market-shrink projection canary metadata.

Read-only. This report does not change lambda or production artifacts.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.diagnostics import workload_no_vig_ev_audit  # noqa: E402

DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "market_shrink_projection_canary_audit.md"
WIN_LOSS_RESULTS = {"win", "loss"}


def _is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _projection_challenger(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("projection_challenger")
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _changed_lambda(meta: dict[str, Any]) -> bool:
    current = _to_float(meta.get("current_lambda"))
    would = _to_float(meta.get("would_lambda"))
    if current is None or would is None:
        return False
    return abs(would - current) > 1e-9


def _row_pnl(row: dict[str, Any]) -> float:
    for key in ("pick_history_pnl", "theoretical_pnl", "pnl"):
        value = _to_float(row.get(key))
        if value is not None:
            return value
    return 0.0


def _verdict(row: dict[str, Any]) -> str:
    return str(
        row.get("display_verdict")
        or row.get("locked_verdict")
        or row.get("actionable_verdict")
        or row.get("verdict")
        or "unknown"
    ).strip() or "unknown"


def _score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    score = {"rows": 0, "wins": 0, "losses": 0, "pnl": 0.0, "roi": 0.0}
    for row in rows:
        score["rows"] += 1
        if row.get("result") == "win":
            score["wins"] += 1
        elif row.get("result") == "loss":
            score["losses"] += 1
        score["pnl"] = round(float(score["pnl"]) + _row_pnl(row), 2)
    if score["rows"]:
        score["roi"] = round(float(score["pnl"]) / int(score["rows"]), 4)
    return score


def _bucket_score(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if field == "verdict":
            key = _verdict(row)
        else:
            key = str(row.get(field) or "unknown").strip() or "unknown"
        buckets[key].append(row)
    return {key: _score(bucket_rows) for key, bucket_rows in sorted(buckets.items())}


def _bucket_score_by_label(
    rows: list[dict[str, Any]],
    labeler,
) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = str(labeler(row) or "unknown").strip() or "unknown"
        buckets[key].append(row)
    return {key: _score(bucket_rows) for key, bucket_rows in sorted(buckets.items())}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(parsed)
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    with_meta = [row for row in rows if _projection_challenger(row)]
    tracked_graded = [
        row
        for row in with_meta
        if _is_true(row.get("is_tracked_pick")) and row.get("result") in WIN_LOSS_RESULTS
    ]
    metas = [_projection_challenger(row) for row in with_meta]
    mode_counts = Counter(meta.get("mode") for meta in metas)
    candidate_counts = Counter(meta.get("candidate") for meta in metas)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_rows": len(rows),
        "rows_with_metadata": len(with_meta),
        "tracked_graded": _score(tracked_graded),
        "mode_counts": dict(mode_counts),
        "candidate_counts": dict(candidate_counts),
        "applied_rows": sum(1 for meta in metas if meta.get("applied") is True),
        "changed_lambda_rows": sum(1 for meta in metas if _changed_lambda(meta)),
        "by_verdict": _bucket_score(tracked_graded, "verdict"),
        "by_side": _bucket_score(tracked_graded, "side"),
        "by_line_bucket": _bucket_score(tracked_graded, "line_bucket"),
        "by_model_market_relationship": _bucket_score(tracked_graded, "model_market_relationship"),
        "by_quality_gate_level": _bucket_score(tracked_graded, "quality_gate_level"),
        "by_workload_risk_label": _bucket_score_by_label(
            tracked_graded,
            workload_no_vig_ev_audit.workload_risk_label,
        ),
        "by_workload_sensitivity_label": _bucket_score_by_label(
            tracked_graded,
            workload_no_vig_ev_audit.workload_sensitivity_label,
        ),
        "by_no_vig_label": _bucket_score_by_label(
            tracked_graded,
            workload_no_vig_ev_audit.no_vig_edge_label,
        ),
    }


def _format_pnl(value: Any) -> str:
    return f"{(_to_float(value) or 0.0):+.2f}"


def _format_roi(value: Any) -> str:
    number = _to_float(value)
    if number is None:
        return "--"
    return f"{number:+.1%}"


def _score_line(label: str, score: dict[str, Any]) -> str:
    return (
        f"- {label}: `{score['rows']}` rows, `{score['wins']}-{score['losses']}`, "
        f"`{_format_pnl(score['pnl'])}`, `{_format_roi(score['roi'])}` ROI."
    )


def _append_score_section(lines: list[str], title: str, buckets: dict[str, dict[str, Any]]) -> None:
    lines.extend(["", f"## {title}", ""])
    if not buckets:
        lines.append("- No tracked graded metadata rows.")
        return
    for label, score in buckets.items():
        lines.append(_score_line(label, score))


def _rollback_recommendation(summary: dict[str, Any]) -> str:
    if summary["rows_with_metadata"] == 0:
        return (
            "No projection metadata found yet; keep `MARKET_SHRINK_PROJECTION_MODE=off` "
            "until Tyler separately approves shadow activation."
        )
    if summary["applied_rows"] == 0:
        return "Shadow metadata only; keep observing and do not enforce from this report alone."
    return "Enforce rows present; review slices before deciding whether to continue or roll back to `off`."


def build_report(rows: list[dict[str, Any]]) -> str:
    summary = summarize(rows)
    lines = [
        "# Market Shrink Projection Canary Audit",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        "Read-only: this report does not change lambda, thresholds, staking, provider order, notifications, locks, retention, or dashboard source-of-truth.",
        "",
        "## Executive Read",
        "",
        f"- Total source rows: `{summary['total_rows']}`",
        f"- Rows with projection metadata: `{summary['rows_with_metadata']}`",
        f"- Changed would-have lambda rows: `{summary['changed_lambda_rows']}`",
        f"- Applied rows: `{summary['applied_rows']}`",
        _score_line("Tracked graded rows with metadata", summary["tracked_graded"]),
        "",
        "## Mode Counts",
        "",
    ]
    if summary["mode_counts"]:
        for mode, count in sorted(summary["mode_counts"].items()):
            lines.append(f"- `{mode}`: `{count}`")
    else:
        lines.append("- No projection metadata found yet.")

    lines.extend(["", "## Candidate Counts", ""])
    if summary["candidate_counts"]:
        for candidate, count in sorted(summary["candidate_counts"].items()):
            lines.append(f"- `{candidate}`: `{count}`")
    else:
        lines.append("- No projection metadata found yet.")

    _append_score_section(lines, "Verdict Split", summary["by_verdict"])
    _append_score_section(lines, "Side Split", summary["by_side"])
    _append_score_section(lines, "K-Line Split", summary["by_line_bucket"])
    _append_score_section(lines, "Model-Market Split", summary["by_model_market_relationship"])
    _append_score_section(lines, "Quality Gate Split", summary["by_quality_gate_level"])
    _append_score_section(lines, "Workload Risk Split", summary["by_workload_risk_label"])
    _append_score_section(lines, "Workload Sensitivity Split", summary["by_workload_sensitivity_label"])
    _append_score_section(lines, "No-Vig Split", summary["by_no_vig_label"])

    lines.extend(
        [
            "",
            "## Rollback Recommendation",
            "",
            f"- {_rollback_recommendation(summary)}",
            "- Do not change thresholds, staking, providers, notifications, locks, retention, or dashboard source-of-truth from this report.",
            "",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    rows = load_jsonl(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_report(rows), encoding="utf-8")
    print(f"Wrote {args.output} ({len(rows)} source rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
