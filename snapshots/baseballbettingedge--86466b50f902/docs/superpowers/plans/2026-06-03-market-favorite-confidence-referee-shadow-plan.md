# Market Favorite Confidence Referee Shadow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shadow-only market-favorite confidence-referee lab that tests whether market-favorite agreement should become a warning or confidence label for bet selection.

**Architecture:** Reuse the committed Gate C durable dataset and existing holdout/confidence-referee diagnostics. Add one focused diagnostic report that compares current model picks, model-with-market-favorite agreement, model-fading-market-favorite rows, and market-favorite-only side baselines across holdout and core slices. The output can recommend a later production promotion plan, but cannot change live picks, thresholds, staking, projections, notifications, provider order, or dashboard artifacts.

**Tech Stack:** Python 3.11, pytest, `data/research/gate_c/pitcher_k_outcome_dataset.jsonl`, existing `analytics/diagnostics/` patterns, Markdown report under `analytics/output/`.

---

## Operating Decision

This is a child plan of
`docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`.

## Execution Status

Implemented on branch `codex/gate-c-f-shadow-labs` on 2026-06-03.

- Diagnostic: `analytics/diagnostics/market_favorite_confidence_referee_shadow_lab.py`
- Tests: `tests/test_market_favorite_confidence_referee_shadow_lab.py`
- Report: `analytics/output/market_favorite_confidence_referee_shadow_lab.md`

Current read from the durable Gate C artifact:

- validation tracked rows: `220`, below the `250` promotion-plan threshold
- `market_favorite_referee_candidate`: `107` rows, `67-40`, `+10.26` flat
  units, `+9.6%` ROI
- status: `not_ready`, because validation sample size is still short

Keep running this after grading. It is close enough to keep watching, but it
does not yet deserve a live production implementation plan.

The 2026-06-03 durable Gate C artifact restored the full current-regime sample:

- official-close side rows: `1470`
- tracked pick rows: `757`
- duplicate dataset keys: `0`
- picks-history reconciliation: `757/757`

The current evidence says market-favorite behavior deserves a focused
shadow plan:

- Gate C holdout validation: `market_favorite_only` side accuracy was `123-84`
  / `59.4%`, versus current model `112-99` / `53.1%`.
- Gate C holdout tracked-pick alignment: `market_favorite_only` aligned `105`
  validation tracked rows and went `68-37`, `+13.17` flat units, `+12.5%` ROI.
- Confidence-referee model/market slices show sharp side differences: overs
  agreeing with market favorite were positive, while under market-favorite
  agreement was weak.

This is not proof to replace the model. It is enough to test a runtime-safe
referee label that can warn when the model fights the market or when market
agreement should require different confidence.

## Non-Goals

- Do not change `pipeline/run_pipeline.py`.
- Do not change `data/params.json`, `formula_change_date`, thresholds, verdicts,
  staking, calibration, locks, or dashboard artifacts.
- Do not change provider order or official source-of-truth rules.
- Do not use result, PnL, actual Ks, close price, CLV, or post-start movement as
  label inputs.
- Do not promote `market_favorite_only` as a replacement betting model.
- Do not add Supabase tables unless a later storage/cost plan approves them.

## Runtime-Safe Candidate Labels

Allowed pre-lock inputs:

- `side`
- `k_line` / `line_bucket`
- `american_odds` / `price_sign`
- `market_favorite_side`
- `favorite_gap_no_vig`
- `model_side`
- `model_market_relationship`
- `projected_ks`
- `edge`, `ev`, `adj_ev`
- `verdict` / locked verdict
- `quality_gate_level`
- `bet_timing_window`
- `opportunity_bucket`
- `leash_risk_bucket`
- `pitcher_archetype_bucket`

Candidate labels to test:

- `current_model_tracked`: current tracked pick side.
- `model_agrees_market_favorite`: tracked row where model side equals
  `market_favorite_side`.
- `model_fades_market_favorite`: tracked row where model side opposes
  `market_favorite_side`.
- `over_agrees_market_favorite`: tracked over with market-favorite agreement.
- `under_agrees_market_favorite`: tracked under with market-favorite agreement.
- `market_favorite_referee_candidate`: current tracked row with market-favorite
  agreement, clean or capped quality, and non-unknown timing.
- `market_fade_warning_candidate`: current tracked row fading the market
  favorite plus at least one caution flag: capped/unknown quality, late timing,
  high K-line under, high leash risk, or no CLV edge after validation.

`no_clv_edge` is validation-only. It may appear in explanations but cannot be a
runtime label input.

## Promotion Discussion Standard

This plan can only recommend drafting a later production promotion plan if the
shadow evidence passes all checks:

- at least `800` clean official-close side rows
- at least `250` validation tracked rows across at least `10` validation slates
- at least `100` validation rows for the proposed market-favorite label
- candidate uses only runtime-safe input fields
- validation side accuracy beats the comparable current-model tracked bucket by
  at least `3.0` percentage points
- validation flat ROI is positive and at least `5.0` flat units better than the
  comparable current-model tracked bucket
- result survives over/under, plus/minus, K-line, quality-gate, timing,
  opportunity/leash, and pitcher-archetype slices
- no hidden degradation appears in FIRE 2u rows or clean quality-gate rows
- a future implementation can be disabled by one config flag

Passing these checks still does not change live behavior. It only justifies a
separate Tyler-approved production implementation plan.

## File Map

- Create: `analytics/diagnostics/market_favorite_confidence_referee_shadow_lab.py`
  - Load the durable Gate C dataset.
  - Build runtime-safe market-favorite labels.
  - Split rows into train/validation by slate date.
  - Summarize candidate side accuracy, W/L, flat PnL, ROI, and core slices.
  - Write `analytics/output/market_favorite_confidence_referee_shadow_lab.md`.
- Create: `tests/test_market_favorite_confidence_referee_shadow_lab.py`
  - Test runtime-safe labels, leakage guardrails, summaries, holdout splits, and
    report content.
- Modify: `docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`
  - Add this plan as the active child plan for market-favorite confidence
    referee work.
- Modify: `docs/current-state.md`
  - Add the plan to the model lane and next decision.

## Task 1: Add Runtime-Safe Label Tests

**Files:**
- Create: `tests/test_market_favorite_confidence_referee_shadow_lab.py`
- Create: `analytics/diagnostics/market_favorite_confidence_referee_shadow_lab.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_market_favorite_confidence_referee_shadow_lab.py`:

```python
from analytics.diagnostics import market_favorite_confidence_referee_shadow_lab as lab


def _row(**overrides):
    row = {
        "dataset_key": "2026-06-01:jane-doe:over:5.5",
        "slate_date": "2026-06-01",
        "context_snapshot": "official_close",
        "is_tracked_pick": True,
        "side": "over",
        "k_line": 5.5,
        "line_bucket": "5.5",
        "price_sign": "minus",
        "market_favorite_side": "over",
        "favorite_gap_no_vig": 0.04,
        "model_side": "over",
        "model_market_relationship": "model_agrees_with_favorite",
        "verdict": "FIRE 1u",
        "quality_gate_level": "clean",
        "bet_timing_window": "pre_30",
        "opportunity_bucket": "normal",
        "leash_risk_bucket": "normal",
        "pitcher_archetype_bucket": "standard_starter",
        "result": "win",
        "actual_ks": 7,
        "pick_history_pnl": 0.91,
        "beat_close_price": True,
    }
    row.update(overrides)
    return row


def test_label_inputs_are_runtime_safe():
    assert "result" not in lab.RUNTIME_SAFE_FIELDS
    assert "actual_ks" not in lab.RUNTIME_SAFE_FIELDS
    assert "pick_history_pnl" not in lab.RUNTIME_SAFE_FIELDS
    assert "beat_close_price" not in lab.RUNTIME_SAFE_FIELDS
    assert "market_favorite_side" in lab.RUNTIME_SAFE_FIELDS
    assert "model_market_relationship" in lab.RUNTIME_SAFE_FIELDS


def test_candidate_flags_identify_market_favorite_agreement():
    flags = lab.candidate_flags(_row())

    assert flags["current_model_tracked"] is True
    assert flags["model_agrees_market_favorite"] is True
    assert flags["model_fades_market_favorite"] is False
    assert flags["over_agrees_market_favorite"] is True
    assert flags["under_agrees_market_favorite"] is False
    assert flags["market_favorite_referee_candidate"] is True


def test_candidate_flags_identify_fade_warning():
    flags = lab.candidate_flags(
        _row(
            side="under",
            model_side="under",
            market_favorite_side="over",
            model_market_relationship="model_fades_favorite",
            quality_gate_level="capped",
            bet_timing_window="pre_15",
        )
    )

    assert flags["model_fades_market_favorite"] is True
    assert flags["market_fade_warning_candidate"] is True
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_market_favorite_confidence_referee_shadow_lab.py -q
```

Expected: fail because the diagnostic module does not exist.

- [ ] **Step 3: Commit the failing test if using strict TDD**

```powershell
git add tests/test_market_favorite_confidence_referee_shadow_lab.py
git commit -m "test: add market favorite referee labels"
```

## Task 2: Implement Candidate Labels

**Files:**
- Modify: `analytics/diagnostics/market_favorite_confidence_referee_shadow_lab.py`
- Test: `tests/test_market_favorite_confidence_referee_shadow_lab.py`

- [ ] **Step 1: Add the minimal module**

Create `analytics/diagnostics/market_favorite_confidence_referee_shadow_lab.py`:

```python
"""Shadow lab for market-favorite confidence-referee candidates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
OUTPUT_PATH = ROOT / "analytics" / "output" / "market_favorite_confidence_referee_shadow_lab.md"
CLEAN_WINDOW_START = "2026-04-28"
WIN_LOSS_RESULTS = {"win", "loss"}

RUNTIME_SAFE_FIELDS = {
    "side",
    "k_line",
    "line_bucket",
    "american_odds",
    "price_sign",
    "market_favorite_side",
    "favorite_gap_no_vig",
    "model_side",
    "model_market_relationship",
    "projected_ks",
    "edge",
    "ev",
    "adj_ev",
    "verdict",
    "locked_verdict",
    "quality_gate_level",
    "bet_timing_window",
    "opportunity_bucket",
    "leash_risk_bucket",
    "pitcher_archetype_bucket",
}


def _text(value: Any) -> str:
    return str(value or "").strip().lower()


def load_jsonl(path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _tracked(row: dict[str, Any]) -> bool:
    return (
        str(row.get("slate_date") or "") >= CLEAN_WINDOW_START
        and row.get("context_snapshot") == "official_close"
        and row.get("is_tracked_pick") is True
        and row.get("result") in WIN_LOSS_RESULTS
        and _text(row.get("side")) in {"over", "under"}
    )


def _caution_count(row: dict[str, Any]) -> int:
    caution = 0
    if row.get("quality_gate_level") in {"capped", "unknown", None}:
        caution += 1
    if row.get("bet_timing_window") in {"pre_15", "pre_5", "post_start", "unknown"}:
        caution += 1
    if _text(row.get("side")) == "under" and row.get("line_bucket") in {"5.5", "6.5", "7.5+"}:
        caution += 1
    if row.get("leash_risk_bucket") in {"medium", "high"}:
        caution += 1
    return caution


def candidate_flags(row: dict[str, Any]) -> dict[str, bool]:
    side = _text(row.get("side"))
    favorite = _text(row.get("market_favorite_side"))
    model_side = _text(row.get("model_side")) or side
    agrees = side in {"over", "under"} and favorite in {"over", "under"} and model_side == favorite
    fades = side in {"over", "under"} and favorite in {"over", "under"} and model_side != favorite

    return {
        "current_model_tracked": _tracked(row),
        "model_agrees_market_favorite": _tracked(row) and agrees,
        "model_fades_market_favorite": _tracked(row) and fades,
        "over_agrees_market_favorite": _tracked(row) and side == "over" and agrees,
        "under_agrees_market_favorite": _tracked(row) and side == "under" and agrees,
        "market_favorite_referee_candidate": _tracked(row)
        and agrees
        and row.get("quality_gate_level") in {"clean", "capped"}
        and row.get("bet_timing_window") not in {"post_start", "unknown"},
        "market_fade_warning_candidate": _tracked(row) and fades and _caution_count(row) >= 1,
    }
```

- [ ] **Step 2: Run tests**

Run:

```powershell
python -m pytest tests/test_market_favorite_confidence_referee_shadow_lab.py -q
```

Expected: pass.

- [ ] **Step 3: Commit**

```powershell
git add analytics/diagnostics/market_favorite_confidence_referee_shadow_lab.py tests/test_market_favorite_confidence_referee_shadow_lab.py
git commit -m "feat: add market favorite referee labels"
```

## Task 3: Add Holdout And Slice Summaries

**Files:**
- Modify: `analytics/diagnostics/market_favorite_confidence_referee_shadow_lab.py`
- Modify: `tests/test_market_favorite_confidence_referee_shadow_lab.py`

- [ ] **Step 1: Add summary tests**

Append to `tests/test_market_favorite_confidence_referee_shadow_lab.py`:

```python
def test_summarize_candidate_counts_wins_pnl_and_roi():
    rows = [
        _row(dataset_key="a", result="win", pick_history_pnl=0.91),
        _row(dataset_key="b", result="loss", pick_history_pnl=-1.0, model_side="under", market_favorite_side="over"),
    ]

    summary = lab.summarize_candidate("model_agrees_market_favorite", rows)

    assert summary["rows"] == 1
    assert summary["wins"] == 1
    assert summary["losses"] == 0
    assert summary["flat_pnl"] == 0.91
    assert summary["flat_roi"] == 0.91


def test_split_holdout_keeps_late_dates_for_validation():
    rows = [_row(dataset_key=str(day), slate_date=f"2026-05-{day:02d}") for day in range(1, 11)]

    split = lab.split_holdout_rows(rows, train_fraction=0.7, min_validate_dates=3)

    assert split["train_dates"][-1] == "2026-05-07"
    assert split["validate_dates"] == ["2026-05-08", "2026-05-09", "2026-05-10"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_market_favorite_confidence_referee_shadow_lab.py -q
```

Expected: fail because summary helpers do not exist.

- [ ] **Step 3: Add summary helpers**

Append to the diagnostic module:

```python
def _pnl(row: dict[str, Any]) -> float:
    for key in ("pick_history_pnl", "theoretical_pnl", "pnl"):
        value = row.get(key)
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def tracked_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if _tracked(row)]


def summarize_candidate(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected = [row for row in tracked_rows(rows) if candidate_flags(row).get(name, False)]
    wins = sum(1 for row in selected if row.get("result") == "win")
    losses = sum(1 for row in selected if row.get("result") == "loss")
    pnl = round(sum(_pnl(row) for row in selected), 2)
    return {
        "name": name,
        "rows": len(selected),
        "wins": wins,
        "losses": losses,
        "flat_pnl": pnl,
        "flat_roi": round(pnl / len(selected), 3) if selected else None,
    }


def split_holdout_rows(
    rows: list[dict[str, Any]],
    *,
    train_fraction: float = 0.7,
    min_validate_dates: int = 5,
) -> dict[str, Any]:
    dates = sorted({str(row.get("slate_date") or "") for row in rows if row.get("slate_date")})
    if len(dates) <= 1:
        return {"train_dates": dates, "validate_dates": [], "train_rows": list(rows), "validate_rows": []}

    cut_index = int(len(dates) * train_fraction)
    cut_index = max(1, min(cut_index, len(dates) - 1))
    if len(dates) > min_validate_dates:
        cut_index = min(cut_index, len(dates) - min_validate_dates)

    train_dates = dates[:cut_index]
    validate_dates = dates[cut_index:]
    train_set = set(train_dates)
    validate_set = set(validate_dates)
    return {
        "train_dates": train_dates,
        "validate_dates": validate_dates,
        "train_rows": [row for row in rows if str(row.get("slate_date") or "") in train_set],
        "validate_rows": [row for row in rows if str(row.get("slate_date") or "") in validate_set],
    }
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_market_favorite_confidence_referee_shadow_lab.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add analytics/diagnostics/market_favorite_confidence_referee_shadow_lab.py tests/test_market_favorite_confidence_referee_shadow_lab.py
git commit -m "feat: summarize market favorite referee candidates"
```

## Task 4: Generate The Report

**Files:**
- Modify: `analytics/diagnostics/market_favorite_confidence_referee_shadow_lab.py`
- Modify: `tests/test_market_favorite_confidence_referee_shadow_lab.py`
- Write: `analytics/output/market_favorite_confidence_referee_shadow_lab.md`

- [ ] **Step 1: Add report test**

Append to `tests/test_market_favorite_confidence_referee_shadow_lab.py`:

```python
def test_build_report_includes_shadow_scope_and_decision_gate():
    report = lab.build_report([_row()])

    assert "Shadow-only" in report
    assert "Validation Candidate Scoreboard" in report
    assert "model_agrees_market_favorite" in report
    assert "Promotion Discussion Gate" in report
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m pytest tests/test_market_favorite_confidence_referee_shadow_lab.py::test_build_report_includes_shadow_scope_and_decision_gate -q
```

Expected: fail because `build_report` does not exist.

- [ ] **Step 3: Implement report generation**

Append to the diagnostic module:

```python
CANDIDATES = [
    "current_model_tracked",
    "model_agrees_market_favorite",
    "model_fades_market_favorite",
    "over_agrees_market_favorite",
    "under_agrees_market_favorite",
    "market_favorite_referee_candidate",
    "market_fade_warning_candidate",
]


def _fmt_roi(value: float | None) -> str:
    return "--" if value is None else f"{value:+.1%}"


def _summary_row(summary: dict[str, Any]) -> str:
    return (
        f"| `{summary['name']}` | {summary['rows']} | "
        f"{summary['wins']}-{summary['losses']} | "
        f"{summary['flat_pnl']:+.2f} | {_fmt_roi(summary['flat_roi'])} |"
    )


def build_report(rows: list[dict[str, Any]]) -> str:
    tracked = tracked_rows(rows)
    split = split_holdout_rows(tracked)
    validation = split["validate_rows"] or tracked

    lines = [
        "# Market Favorite Confidence Referee Shadow Lab",
        "",
        "Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, calibration, or dashboard artifacts.",
        "",
        "## Scope",
        "",
        f"- Clean window start: `{CLEAN_WINDOW_START}`",
        f"- Tracked rows: `{len(tracked)}`",
        f"- Training slates: `{len(split['train_dates'])}`",
        f"- Validation slates: `{len(split['validate_dates'])}`",
        "",
        "## Validation Candidate Scoreboard",
        "",
        "| Candidate | Rows | W-L | Flat PnL | Flat ROI |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    lines.extend(_summary_row(summarize_candidate(candidate, validation)) for candidate in CANDIDATES)
    lines.extend(
        [
            "",
            "## Promotion Discussion Gate",
            "",
            "- This report can only recommend drafting a later production plan.",
            "- A candidate must survive over/under, plus/minus, K-line, quality, timing, opportunity/leash, and pitcher-archetype slices.",
            "- Market-favorite evidence is a referee/selection warning candidate, not a replacement for the model.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    report = build_report(load_jsonl())
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(report + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run tests and generate report**

Run:

```powershell
python -m pytest tests/test_market_favorite_confidence_referee_shadow_lab.py -q
python analytics/diagnostics/market_favorite_confidence_referee_shadow_lab.py
```

Expected: tests pass and the report writes to
`analytics/output/market_favorite_confidence_referee_shadow_lab.md`.

- [ ] **Step 5: Commit**

```powershell
git add analytics/diagnostics/market_favorite_confidence_referee_shadow_lab.py tests/test_market_favorite_confidence_referee_shadow_lab.py analytics/output/market_favorite_confidence_referee_shadow_lab.md
git commit -m "feat: add market favorite referee shadow lab"
```

## Task 5: Add Core Slice Tables

**Files:**
- Modify: `analytics/diagnostics/market_favorite_confidence_referee_shadow_lab.py`
- Modify: `tests/test_market_favorite_confidence_referee_shadow_lab.py`

- [ ] **Step 1: Add slice tests**

Append to the test file:

```python
def test_summarize_slices_marks_small_samples():
    rows = [_row(dataset_key="a")]

    slices = lab.summarize_slices("market_favorite_referee_candidate", rows, "side", min_rows=50)

    assert slices[0]["bucket"] == "over"
    assert slices[0]["rows"] == 1
    assert slices[0]["sample_status"] == "small_sample"
```

- [ ] **Step 2: Implement slice summaries**

Add:

```python
def summarize_slices(
    candidate_name: str,
    rows: list[dict[str, Any]],
    field: str,
    *,
    min_rows: int = 50,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in tracked_rows(rows):
        if not candidate_flags(row).get(candidate_name, False):
            continue
        grouped.setdefault(str(row.get(field) or "unknown"), []).append(row)

    summaries = []
    for bucket, bucket_rows in sorted(grouped.items()):
        wins = sum(1 for row in bucket_rows if row.get("result") == "win")
        losses = sum(1 for row in bucket_rows if row.get("result") == "loss")
        pnl = round(sum(_pnl(row) for row in bucket_rows), 2)
        summaries.append(
            {
                "bucket": bucket,
                "rows": len(bucket_rows),
                "wins": wins,
                "losses": losses,
                "flat_pnl": pnl,
                "flat_roi": round(pnl / len(bucket_rows), 3) if bucket_rows else None,
                "sample_status": "enough_sample" if len(bucket_rows) >= min_rows else "small_sample",
            }
        )
    return summaries
```

- [ ] **Step 3: Update report with slices**

In `build_report`, before `Promotion Discussion Gate`, add slice tables for:

```python
for field in (
    "side",
    "price_sign",
    "line_bucket",
    "quality_gate_level",
    "bet_timing_window",
    "opportunity_bucket",
    "leash_risk_bucket",
    "pitcher_archetype_bucket",
):
    lines.extend(
        [
            "",
            f"### market_favorite_referee_candidate By {field}",
            "",
            "| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |",
            "| --- | ---: | ---: | ---: | ---: | --- |",
        ]
    )
    for item in summarize_slices("market_favorite_referee_candidate", validation, field):
        lines.append(
            f"| `{item['bucket']}` | {item['rows']} | {item['wins']}-{item['losses']} | "
            f"{item['flat_pnl']:+.2f} | {_fmt_roi(item['flat_roi'])} | `{item['sample_status']}` |"
        )
```

- [ ] **Step 4: Run tests and regenerate**

Run:

```powershell
python -m pytest tests/test_market_favorite_confidence_referee_shadow_lab.py -q
python analytics/diagnostics/market_favorite_confidence_referee_shadow_lab.py
```

Expected: tests pass and report includes core slice tables.

- [ ] **Step 5: Commit**

```powershell
git add analytics/diagnostics/market_favorite_confidence_referee_shadow_lab.py tests/test_market_favorite_confidence_referee_shadow_lab.py analytics/output/market_favorite_confidence_referee_shadow_lab.md
git commit -m "feat: add market favorite referee slices"
```

## Task 6: Wire The Plan Into Operations Docs

**Files:**
- Modify: `docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`
- Modify: `docs/current-state.md`
- Modify: automation memory when the daily brief should carry the update forward

- [ ] **Step 1: Update the controlling Gate C plan**

Add this sentence under `Gate C / Confidence-Referee Scope`:

```markdown
Market-favorite confidence-referee testing is controlled by `docs/superpowers/plans/2026-06-03-market-favorite-confidence-referee-shadow-plan.md`; it remains shadow-only and can only recommend a later Tyler-approved production promotion plan.
```

- [ ] **Step 2: Update `docs/current-state.md`**

Add the plan to the model lane source list and make the next decision:

```markdown
Execute the market-favorite confidence-referee plan first, then review whether the candidate survives validation slices strongly enough to draft a production implementation plan.
```

- [ ] **Step 3: Verify docs**

Run:

```powershell
rg -n "market-favorite-confidence-referee|market favorite" docs/current-state.md docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md docs/superpowers/plans/2026-06-03-market-favorite-confidence-referee-shadow-plan.md
git diff --check
```

Expected: references are present and diff check has no errors other than Windows line-ending warnings.

- [ ] **Step 4: Commit**

```powershell
git add docs/current-state.md docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md docs/superpowers/plans/2026-06-03-market-favorite-confidence-referee-shadow-plan.md
git commit -m "docs: add market favorite referee shadow plan"
```

## Rollback

This plan creates shadow diagnostics, tests, reports, and documentation only.
Rollback is deleting the diagnostic, tests, generated report, and doc pointers.
No production behavior changes.

## Decision Boundary

The highest possible outcome from this plan is a recommendation to draft a
separate production implementation plan with an explicit flag, rollback command,
one-slate canary, and Tyler approval. Do not implement live betting behavior
from this plan.
