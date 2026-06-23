"""Render the season-end decision packet for next-season model canaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LAB_JSON = ROOT / "analytics" / "output" / "next_season_candidate_model_lab.json"
DEFAULT_LAB_MARKDOWN = ROOT / "analytics" / "output" / "next_season_candidate_model_lab.md"
DEFAULT_LAB = DEFAULT_LAB_JSON
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "next_season_model_decision_packet.md"
DEFAULT_CONTEXT_SOURCES = {
    "Seasonal audit": ROOT / "analytics" / "output" / "seasonal_k_environment_audit.md",
    "Bet-selection synthesis": ROOT / "analytics" / "output" / "bet_selection_edge_synthesis.md",
    "Gate F report": ROOT / "analytics" / "output" / "gate_f_projection_challenger_shadow_report.md",
    "Market agreement tracker": ROOT / "analytics" / "output" / "market_agreement_tracker.md",
}
SOURCE_READY_STATUSES = {"available", "loaded"}


def decision_label(*, rows: int, pnl: float, bad_slices: int, sources_available: bool = True) -> str:
    if rows < 150:
        return "watch_more"
    if pnl <= 0:
        return "blocked_negative_pnl"
    if bad_slices > 0:
        return "blocked_bad_slice"
    if not sources_available:
        return "blocked_unavailable_sources"
    return "canary_plan_candidate"


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def source_status(label: str, path: Path, *, rows: int | None = None, status: str | None = None) -> dict[str, Any]:
    resolved_status = status or ("available" if path.exists() else "missing")
    return {
        "label": label,
        "status": resolved_status,
        "path": display_path(path),
        "rows": rows,
    }


def default_lab_path() -> Path:
    if DEFAULT_LAB_JSON.exists():
        return DEFAULT_LAB_JSON
    return DEFAULT_LAB_MARKDOWN


def clean_cell(value: str) -> str:
    return value.strip().strip("`").strip()


def header_key(value: str) -> str:
    key = clean_cell(value).lower().replace(" ", "_").replace("-", "_").replace("/", "_")
    return "".join(char for char in key if char.isalnum() or char == "_").strip("_")


def parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return default


def parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def parse_markdown_table(path: Path) -> list[dict[str, Any]]:
    headers: list[str] = []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue

        cells = [clean_cell(cell) for cell in stripped.strip("|").split("|")]
        if not headers:
            candidate_headers = [header_key(cell) for cell in cells]
            if "candidate" in candidate_headers:
                headers = candidate_headers
            continue

        if all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        if len(cells) != len(headers):
            continue

        row = dict(zip(headers, cells))
        if row.get("candidate"):
            rows.append(row)
    return rows


def load_json_rows(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for key in ("candidates", "results", "rows"):
            value = data.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def normalize_candidate_row(row: dict[str, Any]) -> dict[str, Any]:
    rows = parse_int(row.get("rows"))
    pnl = parse_float(row.get("pnl"))
    decision_rows = parse_int(row.get("test_rows"), default=rows)
    decision_pnl = parse_float(row.get("test_pnl"), default=pnl)
    bad_slices = parse_int(row.get("bad_slices") or row.get("bad_slice_count"))
    return {
        "candidate": clean_cell(str(row.get("candidate", ""))),
        "decision": decision_label(rows=decision_rows, pnl=decision_pnl, bad_slices=bad_slices),
        "rows": rows,
        "pnl": pnl,
        "decision_rows": decision_rows,
        "decision_pnl": decision_pnl,
        "bad_slices": bad_slices,
    }


def load_candidate_rows(path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not path.exists():
        return [], source_status("Candidate lab", path, rows=0, status="missing")

    try:
        if path.suffix.lower() == ".json":
            raw_rows = load_json_rows(path)
        else:
            raw_rows = parse_markdown_table(path)
    except (OSError, json.JSONDecodeError) as exc:
        status = source_status("Candidate lab", path, rows=0, status="unavailable")
        status["note"] = str(exc)
        return [], status

    candidates = [normalize_candidate_row(row) for row in raw_rows if row.get("candidate")]
    status = "loaded" if candidates else "loaded_empty"
    return candidates, source_status("Candidate lab", path, rows=len(candidates), status=status)


def context_source_statuses() -> list[dict[str, Any]]:
    return [source_status(label, path) for label, path in DEFAULT_CONTEXT_SOURCES.items()]


def sources_available(source_statuses: list[dict[str, Any]]) -> bool:
    return all(status.get("status") in SOURCE_READY_STATUSES for status in source_statuses)


def gate_candidate_decisions(
    candidates: list[dict[str, Any]], source_statuses: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if sources_available(source_statuses):
        return [dict(candidate) for candidate in candidates]
    gated: list[dict[str, Any]] = []
    for candidate in candidates:
        row = dict(candidate)
        if row.get("decision") == "canary_plan_candidate":
            row["decision"] = "blocked_unavailable_sources"
        gated.append(row)
    return gated


def render(candidates: list[dict[str, Any]], source_statuses: list[dict[str, Any]] | None = None) -> str:
    lines = [
        "# Next Season Model Decision Packet",
        "",
        "Research-only. This packet does not change live behavior.",
        "",
        "## Source Status",
        "",
    ]
    if source_statuses:
        for status in source_statuses:
            detail = f" (`{status['path']}`"
            if status.get("rows") is not None:
                detail += f", rows={status['rows']}"
            detail += ")"
            lines.append(f"- {status['label']}: {status['status']}{detail}")
            if status.get("note"):
                lines.append(f"  - Note: {status['note']}")
    else:
        lines.append("- Source status not provided.")
    lines.extend(
        [
            "",
            "## Candidate Decisions",
            "",
            "| Candidate | Decision | Rows | PnL |",
            "| --- | --- | ---: | ---: |",
        ]
    )
    for row in candidates:
        lines.append(f"| `{row['candidate']}` | `{row['decision']}` | {row['rows']} | {row['pnl']} |")
    if not candidates:
        lines.extend(["", "No candidate rows loaded."])
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
    parser.add_argument("--lab", type=Path, default=None, help="Candidate lab JSON or markdown report.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    lab_path = args.lab or default_lab_path()
    candidates, lab_status = load_candidate_rows(lab_path)
    source_statuses = [lab_status, *context_source_statuses()]
    candidates = gate_candidate_decisions(candidates, source_statuses)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(candidates, source_statuses), encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
