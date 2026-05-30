# Gate E/F Under Skepticism And FIRE Conversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shadow-only Gate E/F candidate lab that tests whether under skepticism, FIRE conversion filters, market-shrink, and high-line tempering improve betting selection without changing live model behavior.

**Architecture:** Add one local diagnostic that consumes the existing compact pitcher K outcome dataset and writes a Gate E/F candidate report. Candidate labels must use only runtime-safe fields for grouping; outcomes, PnL, CLV, and results are validation-only. The report should decide whether a later promotion plan is worth drafting, not promote a model, staking, threshold, provider, or dashboard change.

**Tech Stack:** Python 3.11, existing JSONL compact dataset, pytest, Markdown report under `analytics/output/`.

---

## Operating Decision

This is a child plan of
`docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`.

The current Gate C read through 2026-05-28 says:

- current lambda is not broadly broken
- post-2026-04-28 betting drag is concentrated in selection and side conversion
- overs are positive while unders are materially negative
- FIRE selection is negative overall, with FIRE unders the clearest weak slice
- `market_shrink_25` is a projection-tempering candidate
- `high_line_temper` is a skepticism/referee candidate
- batter-handedness Path B remains hindsight-only until runtime-safe capture is proven

This plan turns those reads into a repeatable shadow lab.

## Non-Goals

- Do not change `pipeline/run_pipeline.py` live projection math.
- Do not change `data/params.json`, thresholds, verdicts, staking, calibration, or `formula_change_date`.
- Do not change provider order or enable `OFFICIAL_MARKET_SOURCE=boltodds_propline`.
- Do not change dashboard artifacts or notification behavior.
- Do not promote over-only or under-ban logic directly from this plan.
- Do not use `result`, PnL, CLV, actual Ks, or close price as label inputs.
- Do not use reconstructed batter handedness for live projection math.

## Current Evidence Baseline

Use the latest generated reports before executing this plan:

- `analytics/output/pitcher_k_outcome_dataset_summary.md`
- `analytics/output/confidence_referee_shadow_report.md`
- `analytics/output/gate_c_holdout_shadow_lab.md`
- `analytics/output/k_projection_shadow_lab.md`
- `analytics/output/batter_handedness_shadow_audit.md`
- `analytics/output/bet_conversion_shadow_audit.md`
- `analytics/output/pre_post_428_model_review.md`

Baseline through 2026-05-28:

- Compact dataset: 1,262 rows, 648 tracked picks, 0 duplicate keys, 0 missing results, 0 missing book odds.
- Post-2026-04-28 tracked picks: 338-310, -11.61u flat, -1.8% flat ROI.
- Post-2026-04-28 overs: 160-128, +15.19u.
- Post-2026-04-28 unders: 178-182, -26.80u.
- FIRE flat selection: negative.
- FIRE overs: positive.
- FIRE unders: materially negative.
- Whole-market post-bump MAE is better than immediate pre-bump, so this is not a broad projection-collapse plan.

## Candidate Families

All candidates are shadow labels only.

### Family 1: Under Skepticism

Goal: identify under rows that should require a better price, cleaner data, or a later review before they become promotion candidates.

Runtime-safe under-skeptic reasons:

- side is `under`
- K line bucket is `5.5`, `6.5`, or `7.5+`
- price sign is `minus`
- model agrees with market favorite on an under
- timing window is `pre_15`, `pre_5`, `post_start`, or `unknown`
- quality gate is `capped` or `unknown`
- pitcher archetype is `high_k_standard` or `high_k_deep_starter`
- opportunity bucket is `deep_starter` for an under

Candidate labels:

- `under_skeptic_2plus`: under row with at least two under-skeptic reasons
- `under_skeptic_3plus`: under row with at least three under-skeptic reasons
- `fire_without_under_skeptic_2plus`: current FIRE rows excluding `under_skeptic_2plus`
- `fire_without_under_skeptic_3plus`: current FIRE rows excluding `under_skeptic_3plus`

### Family 2: FIRE Conversion

Goal: test whether current FIRE ranking is selecting too many large-edge or high-adj-EV traps.

Runtime-safe candidate labels:

- `current_fire_flat`: current live FIRE 1u or FIRE 2u
- `current_fire_over`: current FIRE and side over
- `current_fire_under`: current FIRE and side under
- `fire_mid_edge`: current FIRE with `0.02 <= edge < 0.06`
- `fire_not_high_adj_ev`: current FIRE with `adj_ev < 0.17`
- `fire_model_margin_under_1_5`: current FIRE with picked-side model margin below 1.5 Ks
- `fire_clean_quality`: current FIRE with quality gate `clean`
- `fire_combined_skeptic`: current FIRE excluding `under_skeptic_2plus`, `adj_ev >= 0.17`, and `edge >= 0.06`

### Family 3: Projection Tempering

Goal: keep testing projection changes without treating them as selection rules.

Candidate projections:

- `current_model`
- `market_shrink_25`
- `high_line_temper`
- `leash_cap`

Promotion-readiness checks:

- MAE
- RMSE
- side accuracy
- tracked-pick alignment
- validation-window PnL if candidate still points to the tracked side

### Family 4: Batter Handedness Runtime Safety

Goal: separate hindsight research from future live-safe lineup data.

Path B remains blocked from live use until both are true:

- pre-lock lineup handedness capture reaches at least 95% of official/compact rows for 10 straight graded slates
- a holdout comparison shows Path B improves or preserves current-model MAE and side accuracy without weakening FIRE conversion

## Promotion Discussion Thresholds

This plan can only recommend drafting a later production promotion plan if all conditions pass:

- at least 30 clean post-2026-04-28 slates
- at least 500 clean graded side rows
- at least 150 validation current-FIRE rows
- candidate uses only runtime-safe input fields
- candidate beats `current_fire_flat` by at least 2.0 ROI percentage points or 5.0 flat units in validation
- candidate reduces current FIRE 1u losses by at least 15%
- candidate retains at least 75% of current FIRE 2u wins
- candidate does not depend on one tiny slice with fewer than 50 validation rows
- candidate survives side, price-sign, K-line bucket, timing-window, quality-gate, and model-versus-market slices

Passing these thresholds does not change production behavior. It only allows a separate Tyler-approved promotion plan.

## File Map

- Create `analytics/diagnostics/gate_ef_candidate_shadow_lab.py`
  - Load compact dataset.
  - Build runtime-safe candidate labels.
  - Summarize candidate performance and retention.
  - Write `analytics/output/gate_ef_candidate_shadow_lab.md`.
- Create `tests/test_gate_ef_candidate_shadow_lab.py`
  - Unit test runtime-safe labels, candidate summaries, retention metrics, and report content.
- Modify `docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`
  - Add a short pointer to this child Gate E/F plan.
- Modify `docs/current-state.md`
  - Update the model lane next decision.

## Task 1: Add Runtime-Safe Candidate Label Tests

**Files:**
- Create: `tests/test_gate_ef_candidate_shadow_lab.py`
- Create: `analytics/diagnostics/gate_ef_candidate_shadow_lab.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_gate_ef_candidate_shadow_lab.py`:

```python
from analytics.diagnostics import gate_ef_candidate_shadow_lab as lab


def test_under_skeptic_reasons_use_runtime_safe_fields_only():
    row = {
        "side": "under",
        "line_bucket": "5.5",
        "price_sign": "minus",
        "model_market_relationship": "model_agrees_with_favorite",
        "bet_timing_window": "pre_15",
        "quality_gate_level": "capped",
        "pitcher_archetype_bucket": "high_k_standard",
        "opportunity_bucket": "deep_starter",
        "result": "loss",
        "actual_ks": 8,
        "pick_history_pnl": -1,
    }

    reasons = lab.under_skeptic_reasons(row)

    assert reasons == [
        "under_high_line",
        "under_minus_price",
        "under_market_favorite_agreement",
        "under_late_or_unknown_timing",
        "under_capped_or_unknown_quality",
        "under_high_k_archetype",
        "under_deep_starter_opportunity",
    ]
    assert "result" not in lab.RUNTIME_SAFE_FIELDS
    assert "actual_ks" not in lab.RUNTIME_SAFE_FIELDS
    assert "pick_history_pnl" not in lab.RUNTIME_SAFE_FIELDS


def test_candidate_flags_mark_multi_reason_under_skeptic_rows():
    row = {
        "side": "under",
        "line_bucket": "6.5",
        "price_sign": "minus",
        "model_market_relationship": "model_fades_favorite",
        "bet_timing_window": "pre_30",
        "quality_gate_level": "clean",
        "pitcher_archetype_bucket": "standard_starter",
        "opportunity_bucket": "normal",
        "verdict": "FIRE 1u",
        "edge": 0.055,
        "adj_ev": 0.12,
        "projected_ks": 5.9,
        "k_line": 6.5,
    }

    flags = lab.candidate_flags(row)

    assert flags["current_fire_flat"] is True
    assert flags["current_fire_under"] is True
    assert flags["under_skeptic_2plus"] is True
    assert flags["under_skeptic_3plus"] is False
    assert flags["fire_without_under_skeptic_2plus"] is False
    assert flags["fire_mid_edge"] is True
    assert flags["fire_not_high_adj_ev"] is True
    assert flags["fire_model_margin_under_1_5"] is True
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_gate_ef_candidate_shadow_lab.py -q
```

Expected: fail because `analytics.diagnostics.gate_ef_candidate_shadow_lab` does not exist.

- [ ] **Step 3: Add the minimal diagnostic module shell**

Create `analytics/diagnostics/gate_ef_candidate_shadow_lab.py`:

```python
"""Gate E/F shadow lab for under skepticism and FIRE conversion candidates.

This diagnostic is shadow-only. It must not change live lambda, verdicts,
thresholds, staking, provider order, notifications, calibration, or dashboard
artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "analytics" / "output" / "pitcher_k_outcome_dataset.jsonl"
OUTPUT_PATH = ROOT / "analytics" / "output" / "gate_ef_candidate_shadow_lab.md"
CLEAN_WINDOW_START = "2026-04-28"
WIN_LOSS_RESULTS = {"win", "loss"}
FIRE_VERDICTS = {"FIRE 1u", "FIRE 2u"}

RUNTIME_SAFE_FIELDS = {
    "side",
    "line_bucket",
    "price_sign",
    "model_market_relationship",
    "bet_timing_window",
    "quality_gate_level",
    "pitcher_archetype_bucket",
    "opportunity_bucket",
    "verdict",
    "locked_verdict",
    "actionable_verdict",
    "edge",
    "adj_ev",
    "locked_adj_ev",
    "projected_ks",
    "applied_lambda",
    "raw_lambda",
    "lambda",
    "k_line",
    "locked_k_line",
}


def to_float(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def current_verdict(row: dict[str, Any]) -> str:
    return str(
        row.get("locked_verdict")
        or row.get("actionable_verdict")
        or row.get("verdict")
        or ""
    )


def is_current_fire(row: dict[str, Any]) -> bool:
    return current_verdict(row) in FIRE_VERDICTS


def current_adj_ev(row: dict[str, Any]) -> float | None:
    locked = to_float(row.get("locked_adj_ev"))
    if locked is not None:
        return locked
    return to_float(row.get("adj_ev"))


def current_projection(row: dict[str, Any]) -> float | None:
    for key in ("projected_ks", "applied_lambda", "raw_lambda", "lambda"):
        value = to_float(row.get(key))
        if value is not None:
            return value
    return None


def current_line(row: dict[str, Any]) -> float | None:
    locked = to_float(row.get("locked_k_line"))
    if locked is not None:
        return locked
    return to_float(row.get("k_line"))


def picked_side_model_margin(row: dict[str, Any]) -> float | None:
    projection = current_projection(row)
    line = current_line(row)
    side = str(row.get("side") or "").lower()
    if projection is None or line is None:
        return None
    if side == "over":
        return round(projection - line, 3)
    if side == "under":
        return round(line - projection, 3)
    return None


def under_skeptic_reasons(row: dict[str, Any]) -> list[str]:
    if str(row.get("side") or "").lower() != "under":
        return []

    reasons: list[str] = []
    if row.get("line_bucket") in {"5.5", "6.5", "7.5+"}:
        reasons.append("under_high_line")
    if row.get("price_sign") == "minus":
        reasons.append("under_minus_price")
    if row.get("model_market_relationship") == "model_agrees_with_favorite":
        reasons.append("under_market_favorite_agreement")
    if row.get("bet_timing_window") in {"pre_15", "pre_5", "post_start", "unknown"}:
        reasons.append("under_late_or_unknown_timing")
    if row.get("quality_gate_level") in {"capped", "unknown", None}:
        reasons.append("under_capped_or_unknown_quality")
    if row.get("pitcher_archetype_bucket") in {"high_k_standard", "high_k_deep_starter"}:
        reasons.append("under_high_k_archetype")
    if row.get("opportunity_bucket") == "deep_starter":
        reasons.append("under_deep_starter_opportunity")
    return reasons


def candidate_flags(row: dict[str, Any]) -> dict[str, bool]:
    side = str(row.get("side") or "").lower()
    fire = is_current_fire(row)
    edge = to_float(row.get("edge"))
    adj_ev = current_adj_ev(row)
    model_margin = picked_side_model_margin(row)
    under_reason_count = len(under_skeptic_reasons(row))

    return {
        "current_fire_flat": fire,
        "current_fire_over": fire and side == "over",
        "current_fire_under": fire and side == "under",
        "under_skeptic_2plus": side == "under" and under_reason_count >= 2,
        "under_skeptic_3plus": side == "under" and under_reason_count >= 3,
        "fire_without_under_skeptic_2plus": fire and not (side == "under" and under_reason_count >= 2),
        "fire_without_under_skeptic_3plus": fire and not (side == "under" and under_reason_count >= 3),
        "fire_mid_edge": fire and edge is not None and 0.02 <= edge < 0.06,
        "fire_not_high_adj_ev": fire and (adj_ev is None or adj_ev < 0.17),
        "fire_model_margin_under_1_5": fire and model_margin is not None and 0.0 <= model_margin < 1.5,
        "fire_clean_quality": fire and row.get("quality_gate_level") == "clean",
        "fire_combined_skeptic": fire
        and not (side == "under" and under_reason_count >= 2)
        and not (adj_ev is not None and adj_ev >= 0.17)
        and not (edge is not None and edge >= 0.06),
    }
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```powershell
python -m pytest tests/test_gate_ef_candidate_shadow_lab.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add analytics/diagnostics/gate_ef_candidate_shadow_lab.py tests/test_gate_ef_candidate_shadow_lab.py
git commit -m "test: add gate ef candidate labels"
```

## Task 2: Add Candidate Summary Metrics

**Files:**
- Modify: `tests/test_gate_ef_candidate_shadow_lab.py`
- Modify: `analytics/diagnostics/gate_ef_candidate_shadow_lab.py`

- [ ] **Step 1: Add failing summary tests**

Append to `tests/test_gate_ef_candidate_shadow_lab.py`:

```python
def test_summarize_candidate_reports_retention_and_avoided_losses():
    rows = [
        {
            "side": "under",
            "line_bucket": "6.5",
            "price_sign": "minus",
            "model_market_relationship": "model_agrees_with_favorite",
            "bet_timing_window": "pre_15",
            "quality_gate_level": "capped",
            "pitcher_archetype_bucket": "high_k_standard",
            "opportunity_bucket": "normal",
            "verdict": "FIRE 1u",
            "edge": 0.08,
            "adj_ev": 0.2,
            "projected_ks": 5.7,
            "k_line": 6.5,
            "result": "loss",
            "pick_history_pnl": -1.0,
        },
        {
            "side": "over",
            "line_bucket": "4.5",
            "price_sign": "minus",
            "model_market_relationship": "model_agrees_with_favorite",
            "bet_timing_window": "pre_30",
            "quality_gate_level": "clean",
            "pitcher_archetype_bucket": "standard_starter",
            "opportunity_bucket": "normal",
            "verdict": "FIRE 2u",
            "edge": 0.05,
            "adj_ev": 0.11,
            "projected_ks": 5.2,
            "k_line": 4.5,
            "result": "win",
            "pick_history_pnl": 1.8,
        },
    ]

    summary = lab.summarize_candidate("fire_without_under_skeptic_2plus", rows)

    assert summary["selected"] == 1
    assert summary["wins"] == 1
    assert summary["losses"] == 0
    assert summary["flat_pnl"] == 1.8
    assert summary["current_fire_rows"] == 2
    assert summary["current_fire_1u_losses_avoided"] == 1
    assert summary["current_fire_2u_wins_retained"] == 1
```

- [ ] **Step 2: Run the test to verify failure**

Run:

```powershell
python -m pytest tests/test_gate_ef_candidate_shadow_lab.py::test_summarize_candidate_reports_retention_and_avoided_losses -q
```

Expected: fail because `summarize_candidate` does not exist.

- [ ] **Step 3: Implement summary helpers**

Append to `analytics/diagnostics/gate_ef_candidate_shadow_lab.py`:

```python
def _row_pnl(row: dict[str, Any]) -> float:
    for key in ("pick_history_pnl", "theoretical_pnl", "pnl"):
        value = to_float(row.get(key))
        if value is not None:
            return value
    return 0.0


def clean_tracked_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if str(row.get("slate_date") or "") >= CLEAN_WINDOW_START
        and row.get("result") in WIN_LOSS_RESULTS
        and row.get("is_tracked_pick") is True
    ]


def summarize_candidate(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    clean_rows = clean_tracked_rows(rows)
    current_fire_rows = [row for row in clean_rows if candidate_flags(row)["current_fire_flat"]]
    selected = [row for row in clean_rows if candidate_flags(row).get(name, False)]

    wins = sum(1 for row in selected if row.get("result") == "win")
    losses = sum(1 for row in selected if row.get("result") == "loss")
    flat_pnl = round(sum(_row_pnl(row) for row in selected), 2)
    flat_roi = round(flat_pnl / len(selected), 4) if selected else None

    selected_ids = {row.get("dataset_key") for row in selected}
    avoided = [
        row
        for row in current_fire_rows
        if row.get("dataset_key") not in selected_ids
    ]

    return {
        "name": name,
        "selected": len(selected),
        "wins": wins,
        "losses": losses,
        "flat_pnl": flat_pnl,
        "flat_roi": flat_roi,
        "current_fire_rows": len(current_fire_rows),
        "current_fire_1u_losses_avoided": sum(
            1
            for row in avoided
            if current_verdict(row) == "FIRE 1u" and row.get("result") == "loss"
        ),
        "current_fire_2u_wins_retained": sum(
            1
            for row in selected
            if current_verdict(row) == "FIRE 2u" and row.get("result") == "win"
        ),
    }
```

- [ ] **Step 4: Run the tests**

Run:

```powershell
python -m pytest tests/test_gate_ef_candidate_shadow_lab.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add analytics/diagnostics/gate_ef_candidate_shadow_lab.py tests/test_gate_ef_candidate_shadow_lab.py
git commit -m "feat: summarize gate ef shadow candidates"
```

## Task 3: Add Report Generation

**Files:**
- Modify: `tests/test_gate_ef_candidate_shadow_lab.py`
- Modify: `analytics/diagnostics/gate_ef_candidate_shadow_lab.py`

- [ ] **Step 1: Add failing report test**

Append to `tests/test_gate_ef_candidate_shadow_lab.py`:

```python
def test_build_report_includes_shadow_warning_and_candidate_rows():
    rows = [
        {
            "dataset_key": "row-1",
            "slate_date": "2026-05-01",
            "is_tracked_pick": True,
            "side": "over",
            "line_bucket": "4.5",
            "price_sign": "minus",
            "model_market_relationship": "model_agrees_with_favorite",
            "bet_timing_window": "pre_30",
            "quality_gate_level": "clean",
            "pitcher_archetype_bucket": "standard_starter",
            "opportunity_bucket": "normal",
            "verdict": "FIRE 1u",
            "edge": 0.05,
            "adj_ev": 0.1,
            "projected_ks": 5.2,
            "k_line": 4.5,
            "result": "win",
            "pick_history_pnl": 0.91,
        }
    ]

    report = lab.build_report(rows)

    assert "Shadow-only" in report
    assert "current_fire_flat" in report
    assert "fire_without_under_skeptic_2plus" in report
    assert "Promotion Discussion Check" in report
```

- [ ] **Step 2: Run the test to verify failure**

Run:

```powershell
python -m pytest tests/test_gate_ef_candidate_shadow_lab.py::test_build_report_includes_shadow_warning_and_candidate_rows -q
```

Expected: fail because `build_report` does not exist.

- [ ] **Step 3: Implement report generation**

Append to `analytics/diagnostics/gate_ef_candidate_shadow_lab.py`:

```python
CANDIDATE_NAMES = [
    "current_fire_flat",
    "current_fire_over",
    "current_fire_under",
    "fire_without_under_skeptic_2plus",
    "fire_without_under_skeptic_3plus",
    "fire_mid_edge",
    "fire_not_high_adj_ev",
    "fire_model_margin_under_1_5",
    "fire_clean_quality",
    "fire_combined_skeptic",
]


def load_jsonl(path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _format_roi(value: float | None) -> str:
    return "--" if value is None else f"{value:+.1%}"


def _candidate_row(summary: dict[str, Any]) -> str:
    return (
        f"| `{summary['name']}` | {summary['selected']} | "
        f"{summary['wins']}-{summary['losses']} | "
        f"{summary['flat_pnl']:+.2f} | {_format_roi(summary['flat_roi'])} | "
        f"{summary['current_fire_1u_losses_avoided']} | "
        f"{summary['current_fire_2u_wins_retained']} |"
    )


def build_report(rows: list[dict[str, Any]]) -> str:
    clean_rows = clean_tracked_rows(rows)
    summaries = [summarize_candidate(name, rows) for name in CANDIDATE_NAMES]

    lines = [
        "# Gate E/F Candidate Shadow Lab",
        "",
        "Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, calibration, or dashboard artifacts.",
        "",
        "## Scope",
        "",
        f"- Clean window start: `{CLEAN_WINDOW_START}`",
        f"- Clean tracked rows: `{len(clean_rows)}`",
        "",
        "## Candidate Scoreboard",
        "",
        "| Candidate | Selected | W-L | Flat PnL | Flat ROI | FIRE 1u Losses Avoided | FIRE 2u Wins Retained |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    lines.extend(_candidate_row(summary) for summary in summaries)

    lines.extend(
        [
            "",
            "## Promotion Discussion Check",
            "",
            "- This report can only recommend a later promotion plan.",
            "- A candidate must improve validation ROI or flat units, reduce FIRE 1u losses, retain FIRE 2u wins, and survive side/price/line/timing/quality slices.",
            "- Any production change still requires a separate Tyler-approved implementation and rollback plan.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    report = build_report(load_jsonl())
    OUTPUT_PATH.write_text(report + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_gate_ef_candidate_shadow_lab.py -q
```

Expected: pass.

- [ ] **Step 5: Generate the report**

Run:

```powershell
python analytics/diagnostics/gate_ef_candidate_shadow_lab.py
```

Expected: writes `analytics/output/gate_ef_candidate_shadow_lab.md` and prints the report.

- [ ] **Step 6: Commit**

```powershell
git add analytics/diagnostics/gate_ef_candidate_shadow_lab.py tests/test_gate_ef_candidate_shadow_lab.py analytics/output/gate_ef_candidate_shadow_lab.md
git commit -m "feat: add gate ef candidate shadow lab"
```

## Task 4: Add Validation Slices Before Promotion Discussion

**Files:**
- Modify: `analytics/diagnostics/gate_ef_candidate_shadow_lab.py`
- Modify: `tests/test_gate_ef_candidate_shadow_lab.py`

- [ ] **Step 1: Add slice tests**

Append to `tests/test_gate_ef_candidate_shadow_lab.py`:

```python
def test_slice_summary_marks_small_samples():
    rows = [
        {
            "dataset_key": "row-1",
            "slate_date": "2026-05-01",
            "is_tracked_pick": True,
            "side": "under",
            "price_sign": "minus",
            "line_bucket": "5.5",
            "bet_timing_window": "pre_15",
            "quality_gate_level": "capped",
            "model_market_relationship": "model_agrees_with_favorite",
            "pitcher_archetype_bucket": "high_k_standard",
            "opportunity_bucket": "normal",
            "verdict": "FIRE 1u",
            "edge": 0.08,
            "adj_ev": 0.2,
            "projected_ks": 5.0,
            "k_line": 5.5,
            "result": "loss",
            "pick_history_pnl": -1.0,
        }
    ]

    slices = lab.summarize_slices("current_fire_flat", rows, "side", min_rows=50)

    assert slices[0]["bucket"] == "under"
    assert slices[0]["rows"] == 1
    assert slices[0]["sample_status"] == "small_sample"
```

- [ ] **Step 2: Run the test to verify failure**

Run:

```powershell
python -m pytest tests/test_gate_ef_candidate_shadow_lab.py::test_slice_summary_marks_small_samples -q
```

Expected: fail because `summarize_slices` does not exist.

- [ ] **Step 3: Implement slice summaries**

Add to `analytics/diagnostics/gate_ef_candidate_shadow_lab.py`:

```python
def summarize_slices(
    candidate_name: str,
    rows: list[dict[str, Any]],
    field: str,
    *,
    min_rows: int = 50,
) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in clean_tracked_rows(rows):
        if not candidate_flags(row).get(candidate_name, False):
            continue
        bucket = str(row.get(field) or "unknown")
        buckets.setdefault(bucket, []).append(row)

    summaries: list[dict[str, Any]] = []
    for bucket, bucket_rows in sorted(buckets.items()):
        wins = sum(1 for row in bucket_rows if row.get("result") == "win")
        losses = sum(1 for row in bucket_rows if row.get("result") == "loss")
        pnl = round(sum(_row_pnl(row) for row in bucket_rows), 2)
        roi = round(pnl / len(bucket_rows), 4) if bucket_rows else None
        summaries.append(
            {
                "bucket": bucket,
                "rows": len(bucket_rows),
                "wins": wins,
                "losses": losses,
                "flat_pnl": pnl,
                "flat_roi": roi,
                "sample_status": "enough_sample" if len(bucket_rows) >= min_rows else "small_sample",
            }
        )
    return summaries
```

- [ ] **Step 4: Update the report with core slices**

In `build_report`, after the candidate scoreboard, add section blocks for:

```python
    for field in (
        "side",
        "price_sign",
        "line_bucket",
        "bet_timing_window",
        "quality_gate_level",
        "model_market_relationship",
    ):
        lines.extend(
            [
                "",
                f"### fire_combined_skeptic By {field}",
                "",
                "| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |",
                "| --- | ---: | ---: | ---: | ---: | --- |",
            ]
        )
        for summary in summarize_slices("fire_combined_skeptic", rows, field):
            lines.append(
                f"| `{summary['bucket']}` | {summary['rows']} | "
                f"{summary['wins']}-{summary['losses']} | "
                f"{summary['flat_pnl']:+.2f} | {_format_roi(summary['flat_roi'])} | "
                f"`{summary['sample_status']}` |"
            )
```

- [ ] **Step 5: Run tests and regenerate**

Run:

```powershell
python -m pytest tests/test_gate_ef_candidate_shadow_lab.py -q
python analytics/diagnostics/gate_ef_candidate_shadow_lab.py
```

Expected: tests pass and report includes slice sections.

- [ ] **Step 6: Commit**

```powershell
git add analytics/diagnostics/gate_ef_candidate_shadow_lab.py tests/test_gate_ef_candidate_shadow_lab.py analytics/output/gate_ef_candidate_shadow_lab.md
git commit -m "feat: add gate ef validation slices"
```

## Task 5: Add Gate E/F Daily Brief Hook

**Files:**
- Modify: `docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`
- Modify: `docs/current-state.md`
- Modify: automation memory only when the daily brief should carry this forward

- [ ] **Step 1: Update the controlling Gate C plan**

Add this sentence under the Gate C / Confidence-Referee Scope section in
`docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`:

```markdown
Gate E/F under-skepticism and FIRE-conversion candidate testing is controlled by `docs/superpowers/plans/2026-05-29-gate-ef-under-fire-conversion-shadow-plan.md`; it remains shadow-only and cannot change live picks without a separate Tyler-approved promotion plan.
```

- [ ] **Step 2: Update the model lane in `docs/current-state.md`**

In the Four-Lane Operating Board model row, add the new plan to the Current Source list and update the Next Decision to:

```markdown
Keep Gate C shadow-only. Execute the Gate E/F candidate lab next, focused on under skepticism, FIRE conversion, market-shrink, high-line tempering, and runtime-safe handedness proof. Do not promote lambda, thresholds, staking, verdicts, or Path B handedness without a separate promotion plan.
```

- [ ] **Step 3: Update the BBE Operations Brief automation memory**

Append a short note to
`C:\Users\TylerReid\.codex\automations\yesterdays-pipeline-health-bbe\memory.md`:

```markdown
## 2026-05-29 Gate E/F Shadow Plan
- New child plan: `docs/superpowers/plans/2026-05-29-gate-ef-under-fire-conversion-shadow-plan.md`.
- Daily brief should keep Gate C/D/E/F shadow-only and report whether the planned Gate E/F lab exists, whether it was regenerated after grading, and whether any candidate survives under/over, price, K-line, timing, quality, and market-relationship slices.
- Default recommendation remains no live formula, threshold, staking, verdict, provider, notification, dashboard, or Path B handedness promotion without a separate Tyler-approved plan.
```

- [ ] **Step 4: Verify docs**

Run:

```powershell
rg -n "gate-ef-under-fire|Gate E/F" docs/current-state.md docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md docs/superpowers/plans/2026-05-29-gate-ef-under-fire-conversion-shadow-plan.md
git diff --check
```

Expected: references are present and diff check reports no errors other than Windows line-ending warnings.

- [ ] **Step 5: Commit**

```powershell
git add docs/current-state.md docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md docs/superpowers/plans/2026-05-29-gate-ef-under-fire-conversion-shadow-plan.md
git commit -m "docs: add gate ef under fire conversion plan"
```

## Execution Order

Execute Tasks 1 through 4 first. Task 5 can be done in the same branch after the report exists, or as a docs-only commit if Tyler wants the plan tracked before implementation begins.

## Rollback

This plan creates shadow diagnostics and docs only. Rollback is deleting the new diagnostic, tests, generated report, and doc references. No production flags or live model behavior are changed.

## Decision Boundary

If the candidate lab shows a strong candidate, the correct next step is a new promotion plan with:

- exact production code paths
- feature flag or config switch
- rollback command
- before/after validation
- one-slate canary
- explicit Tyler approval

Do not directly implement live betting behavior from this plan.
