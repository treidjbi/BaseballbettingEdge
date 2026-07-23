"""Frozen official-close Alt Picks parity research.

This module is deliberately a hindsight-capable research comparator.  It reads
the Gate C research corpus, never creates prospective records, and is not a
runtime, proof, endpoint, UI, or state dependency.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import sys
from datetime import date
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.diagnostics import gate_f_fire_reentry_lab as fire_reentry
from analytics.diagnostics import gate_f_preclose_clv_proxy_lab as preclose_proxy
from analytics.diagnostics import strong_base_decision_lab as strong_base


DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
FIXTURE_DIRECTORY = ROOT / "tests" / "fixtures" / "alternative_pick_selection_v2"
DEFAULT_PARITY_INPUT = FIXTURE_DIRECTORY / "legacy_official_close_parity.json.gz"
FIXTURE_MANIFEST = FIXTURE_DIRECTORY / "manifest.json"
CLEAN_START_DATE = date(2026, 4, 28)
FROZEN_END_DATE = date(2026, 7, 20)
WIN_LOSS_RESULTS = {"win", "loss"}
DRAG_LABELS = {
    "cap_high_raw_edge",
    "cap_market_fade",
    "cap_fire_under_market_fade",
}
FROZEN_ANCHORS = {
    "consensus_core": {"rows": 152, "wins": 106, "losses": 46, "pnl": 32.603},
    "reentry_expansion": {"rows": 80, "wins": 42, "losses": 38, "pnl": 5.982},
    "combined": {"rows": 232, "wins": 148, "losses": 84, "pnl": 38.585},
}
LEGACY_PARITY_FIELD_ORDER = (
    "slate_date",
    "context_snapshot",
    "is_tracked_pick",
    "result",
    "dataset_key",
    "pick_history_pnl",
    "raw_verdict",
    "quality_actionable_verdict",
    "display_verdict",
    "quality_gate_level",
    "side",
    "edge",
    "locked_adj_ev",
    "adj_ev",
    "ev",
    "model_no_vig_gap",
    "model_market_relationship",
    "leash_risk_bucket",
    "opportunity_bucket",
    "line_bucket",
    "pitcher_archetype_bucket",
    "market_anchor_selector",
    "market_anchor_selector_labels",
    "side_price_movement",
    "toward_pick_count",
    "away_from_pick_count",
    "price_sign",
    "bet_timing_window",
    "book_count",
    "books_seen",
    "broad_confirmation",
    "best_is_off_market",
    "reversal_book_count",
    "volatile_book_count",
    "beat_close_price",
    "beat_close_line",
    "price_clv_cents",
    "line_clv_delta",
    "large_edge_skepticism_flag",
)
LEGACY_PARITY_FIELDS = frozenset(LEGACY_PARITY_FIELD_ORDER)


def _date(value: Any) -> date | None:
    try:
        return date.fromisoformat(str(value or "").strip()[:10])
    except ValueError:
        return None


def _labels(value: Any) -> set[str]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = value
    if isinstance(value, dict):
        value = value.get("labels", [])
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(item).strip() for item in value if str(item or "").strip()}


def _anchor_labels(row: dict[str, Any]) -> set[str]:
    return _labels(row.get("market_anchor_selector")) | _labels(
        row.get("market_anchor_selector_labels")
    )


def _base_and_drag(row: dict[str, Any]) -> tuple[bool, bool]:
    labels = strong_base.candidate_labels(row)
    drag = bool(labels & DRAG_LABELS)
    keep_fire = bool(labels & {
        "keep_fire_market_agreed_moderate_ev",
        "keep_fire_over_moderate_ev_normal_leash",
    })
    selective_lean = bool(labels & {
        "expand_lean_45_low_ev_normal_leash",
        "expand_lean_low_k_standard_no_vig",
        "expand_lean_low_line_capped_model_fade",
    })
    # This is the frozen legacy Boolean: Base is one family, not one vote per
    # underlying strong-base label.
    base = (keep_fire and not drag) or (
        selective_lean
        and not bool(labels & {"cap_high_raw_edge", "cap_fire_under_market_fade"})
    )
    return base, drag


def historical_family_flags(row: dict[str, Any]) -> dict[str, bool]:
    """Return the documented legacy Boolean families for one official-close row."""
    base, drag_core = _base_and_drag(row)
    anchor_labels = _anchor_labels(row)
    market_anchor_strict = "market_anchor_strict" in anchor_labels
    market_anchor_core = "market_anchor_core" in anchor_labels
    anchor = market_anchor_strict or (base and market_anchor_core)
    preclose = base and (
        preclose_proxy.preclose_clv_proxy_label(row) == "strong_preclose_clv_proxy"
    )
    reentry_labels = fire_reentry.candidate_labels(row)
    source_fire = fire_reentry.source_fire_verdict(row).upper().startswith("FIRE")
    reentry = source_fire and "moderate_edge_quality_reentry" in reentry_labels
    support = base or market_anchor_strict
    no_drag = support and not drag_core
    explicit_family_count = sum((base, anchor, preclose, reentry))
    consensus_core = no_drag and explicit_family_count >= 2
    reentry_expansion = reentry and not no_drag
    return {
        "base": base,
        "market_anchor_strict": market_anchor_strict,
        "market_anchor_core": market_anchor_core,
        "anchor": anchor,
        "preclose": preclose,
        "source_fire": source_fire,
        "reentry": reentry,
        "support": support,
        "drag_core": drag_core,
        "no_drag": no_drag,
        "consensus_core": consensus_core,
        "reentry_expansion": reentry_expansion,
        "explicit_family_count": explicit_family_count,
    }


def _pnl(row: dict[str, Any]) -> float:
    for field in ("pick_history_pnl", "pnl", "theoretical_pnl"):
        value = row.get(field)
        if isinstance(value, bool):
            continue
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(parsed):
            return parsed
    return 0.0


def _score(rows: list[dict[str, Any]]) -> dict[str, int | float]:
    wins = sum(row.get("result") == "win" for row in rows)
    losses = sum(row.get("result") == "loss" for row in rows)
    # Freeze the published July 21 research convention. The originating lab
    # rounded each row to three decimals before adding the flat-unit outcomes;
    # rounding only the final raw sum drifts by a few thousandths.
    pnl = round(sum(round(_pnl(row), 3) for row in rows), 3)
    return {
        "rows": wins + losses,
        "wins": wins,
        "losses": losses,
        "pnl": pnl,
    }


def summarize_legacy_official_close(
    rows: list[dict[str, Any]], *, end_date: date = FROZEN_END_DATE,
) -> dict[str, Any]:
    """Score disjoint official-close research lanes through a fixed cutoff.

    The frozen anchors are a documented reference, while ``observed`` makes
    input-corpus drift visible instead of converting it into prospective state.
    """
    eligible = [
        row for row in rows
        if (slate_date := _date(row.get("slate_date"))) is not None
        and CLEAN_START_DATE <= slate_date <= end_date
        and row.get("context_snapshot") == "official_close"
        and row.get("result") in WIN_LOSS_RESULTS
        and bool(row.get("is_tracked_pick"))
    ]
    lane_rows = {"consensus_core": [], "reentry_expansion": []}
    for row in eligible:
        flags = historical_family_flags(row)
        if flags["consensus_core"]:
            lane_rows["consensus_core"].append(row)
        elif flags["reentry_expansion"]:
            lane_rows["reentry_expansion"].append(row)

    observed = {
        "consensus_core": _score(lane_rows["consensus_core"]),
        "reentry_expansion": _score(lane_rows["reentry_expansion"]),
        "combined": _score(lane_rows["consensus_core"] + lane_rows["reentry_expansion"]),
    }
    return {
        "research_only": True,
        "end_date": end_date.isoformat(),
        "frozen_anchors": FROZEN_ANCHORS,
        "observed": observed,
        "matches_frozen_anchors": observed == FROZEN_ANCHORS,
        "prospective_ledger": {"rows": 0, "pnl": 0.0},
        "lane_rows": {
            lane: [row.get("dataset_key") for row in selected]
            for lane, selected in lane_rows.items()
        },
    }


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        parsed
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and isinstance(parsed := json.loads(line), dict)
    ]


def load_legacy_parity_fixture(path: Path = DEFAULT_PARITY_INPUT) -> list[dict[str, Any]]:
    """Expand the compact, test-only legacy parity fixture into source rows.

    Each packed row starts with a hexadecimal presence mask followed by values
    for only the fields that existed in the recovered corpus. This preserves
    missing-versus-null semantics while keeping the 1,621-row research fixture
    small enough to review and source-control.
    """
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        payload = json.load(handle)
    if payload.get("schema_version") != "legacy_official_close_parity_v1":
        raise ValueError("unsupported legacy parity fixture schema")
    fields = payload.get("fields")
    if fields != list(LEGACY_PARITY_FIELD_ORDER):
        raise ValueError("legacy parity fixture fields changed")
    packed_rows = payload.get("rows")
    if not isinstance(packed_rows, list):
        raise ValueError("legacy parity fixture rows are malformed")

    rows: list[dict[str, Any]] = []
    for packed in packed_rows:
        if not isinstance(packed, list) or not packed or not isinstance(packed[0], str):
            raise ValueError("legacy parity fixture row is malformed")
        try:
            mask = int(packed[0], 16)
        except ValueError as exc:
            raise ValueError("legacy parity fixture mask is malformed") from exc
        present_fields = [field for index, field in enumerate(fields) if mask & (1 << index)]
        if len(packed) != len(present_fields) + 1:
            raise ValueError("legacy parity fixture row width does not match mask")
        rows.append(dict(zip(present_fields, packed[1:])))
    return rows


def load_fixture_manifest(path: Path = FIXTURE_MANIFEST) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("fixture manifest must be an object")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare frozen Alt Picks official-close research anchors.")
    parser.add_argument("--input", type=Path, default=DEFAULT_PARITY_INPUT)
    parser.add_argument("--end-date", type=date.fromisoformat, default=FROZEN_END_DATE)
    args = parser.parse_args(argv)
    rows = load_legacy_parity_fixture(args.input) if args.input.suffix == ".gz" else load_jsonl(args.input)
    summary = summarize_legacy_official_close(rows, end_date=args.end_date)
    for lane in ("consensus_core", "reentry_expansion", "combined"):
        score = summary["frozen_anchors"][lane]
        print(f"Frozen {lane}: {score['wins']}-{score['losses']}, {score['pnl']:+.3f}u")
    print(f"Observed corpus matches frozen anchors: {summary['matches_frozen_anchors']}")
    return 0 if summary["matches_frozen_anchors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
