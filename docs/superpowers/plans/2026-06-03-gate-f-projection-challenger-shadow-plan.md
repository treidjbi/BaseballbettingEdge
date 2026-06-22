# Gate F Projection Challenger Shadow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a stricter Gate F shadow validation package for projection challengers such as `market_shrink_25` and `high_line_temper` before any live lambda promotion is discussed.

**Architecture:** Extend the existing K-projection and Gate C holdout labs into a repeatable Gate F projection package. The package uses the durable Gate C dataset, rolling validation windows, and side/price/line/provider slices to decide whether a projection challenger deserves a later production implementation plan. It does not change live projection math.

**Tech Stack:** Python 3.11, pytest, `analytics/diagnostics/k_projection_shadow_lab.py`, `analytics/diagnostics/gate_c_holdout_shadow_lab.py`, `data/research/gate_c/pitcher_k_outcome_dataset.jsonl`, Markdown report under `analytics/output/`.

---

## Operating Decision

This is a child plan of
`docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`.

## Execution Status

Implemented on branch `codex/gate-c-f-shadow-labs` on 2026-06-03.

- Extended diagnostic: `analytics/diagnostics/k_projection_shadow_lab.py`
- Extended diagnostic: `analytics/diagnostics/gate_c_holdout_shadow_lab.py`
- Decision report: `analytics/diagnostics/gate_f_projection_challenger_shadow_report.py`
- Tests:
  - `tests/test_k_projection_shadow_lab.py`
  - `tests/test_gate_c_holdout_shadow_lab.py`
  - `tests/test_gate_f_projection_challenger_shadow_report.py`
- Reports:
  - `analytics/output/k_projection_shadow_lab.md`
  - `analytics/output/gate_c_holdout_shadow_lab.md`
  - `analytics/output/gate_f_projection_challenger_shadow_report.md`

Original 2026-06-03 Gate F decision report blocked all projection challengers
from production-plan status:

- `market_shrink_15`, `market_shrink_25`, and `market_shrink_35`: blocked
  because holdout MAE lift is below the `0.025` threshold, despite
  `market_shrink_25` and `market_shrink_35` improving MAE directionally.
- `high_line_temper` and `leash_cap`: blocked because aggregate lift is too
  small and rolling/slice evidence is not strong enough.
- `handedness_bucket_adjust`: blocked as hindsight-only until runtime-safe
  lineup-handedness capture is proven.

Keep this as a shadow validation package. No challenger deserves a live lambda
promotion plan yet.

2026-06-22 update after weekend data repair:

- Refreshed production Gate F report covered slates through 2026-06-21.
- `market_shrink_15`: `promotion_plan_candidate`, `219` rows, MAE delta
  `-0.030`, RMSE delta `-0.042`, side accuracy delta `+0.000`, `2`
  positive rolling windows, `0` bad slices, no FIRE 2u degradation.
- `market_shrink_25`: `promotion_plan_candidate`, `219` rows, MAE delta
  `-0.048`, RMSE delta `-0.066`, side accuracy delta `+0.000`, `2`
  positive rolling windows, `0` bad slices, no FIRE 2u degradation.
- `market_shrink_35`: `promotion_plan_candidate`, `219` rows, MAE delta
  `-0.063`, RMSE delta `-0.089`, side accuracy delta `+0.000`, `2`
  positive rolling windows, `0` bad slices, no FIRE 2u degradation.
- `high_line_temper` and `leash_cap` remain blocked for insufficient MAE lift;
  `handedness_bucket_adjust` remains blocked as hindsight-only.
- The resulting production-canary draft is
  `docs/superpowers/plans/2026-06-22-market-shrink-projection-production-canary.md`.
  It does not approve a live lambda change; `shadow` or `enforce` still needs
  Tyler's explicit approval.

Current 2026-06-03 evidence:

- K projection lab official-close rows: `735`.
- `current_model`: MAE `1.811`, RMSE `2.273`, side accuracy `54.7%`.
- `market_shrink_25`: MAE `1.773`, RMSE `2.225`, side accuracy `54.7%`.
- `high_line_temper`: MAE `1.809`, RMSE `2.271`, side accuracy `55.2%`.
- Tracked-pick alignment: `high_line_temper` aligned `314` rows at `+13.08`
  flat units / `4.2%` ROI versus current model `320` rows at `+9.32` /
  `2.9%`.
- Gate C validation holdout: `market_shrink_25` improved validation MAE
  (`1.805` vs current `1.822`), while side accuracy stayed tied.

This is enough to run a Gate F projection-challenger package. It is not enough
to change live lambda.

## Non-Goals

- Do not change `pipeline/build_features.py`, `pipeline/run_pipeline.py`, or
  any live projection formula.
- Do not change `data/params.json`, `formula_change_date`, verdict thresholds,
  staking, calibration, provider order, notifications, locks, or dashboard
  artifacts.
- Do not promote `market_shrink_25`, `high_line_temper`, `leash_cap`, or
  handedness adjustments directly from this plan.
- Do not use actual Ks, PnL, result, CLV, or close price as pregame inputs.
- Do not use reconstructed lineup handedness as runtime-safe until pre-lock
  capture is proven.

## Candidate Definitions

The first Gate F package should compare:

- `current_model`: current live projected Ks.
- `market_shrink_25`: move current projection 25% toward the market K line.
- `market_shrink_15`: move current projection 15% toward the market K line.
- `market_shrink_35`: move current projection 35% toward the market K line.
- `high_line_temper`: subtract 0.55 Ks only when line is `7.5+` and current
  projection is above the line.
- `leash_cap`: subtract 0.55 Ks for high leash risk or short-leash pitcher
  archetype, 0.25 Ks for medium leash risk.
- `handedness_bucket_adjust`: train-only adjustment from matchup buckets; this
  remains hindsight-only until runtime lineup-handedness capture is proven.

## Gate F Promotion Discussion Standard

This plan can only recommend a later production projection plan if a challenger:

- uses only runtime-safe inputs, except explicitly labeled hindsight-only
  handedness experiments
- covers at least `800` clean official-close side rows or Tyler accepts a
  smaller personal-use canary
- improves holdout MAE by at least `0.025` versus current model
- improves or preserves holdout RMSE within `0.010`
- improves or preserves side accuracy within `0.5` percentage points
- survives over/under, plus/minus, K-line, quality-gate, model/market, timing,
  opportunity/leash, and pitcher-archetype slices
- does not degrade FIRE 2u tracked alignment or clean quality-gate tracked
  alignment
- is positive or neutral in at least two rolling validation windows
- has an explainable failure mode and one feature/config flag rollback path

Passing these standards still only opens a separate Tyler-approved production
implementation plan.

## File Map

- Modify: `analytics/diagnostics/k_projection_shadow_lab.py`
  - Add `market_shrink_15` and `market_shrink_35`.
  - Add source path default or documented CLI command for the durable Gate C
    artifact.
  - Add side/price/line/quality/timing/provider slices for challengers.
- Modify: `analytics/diagnostics/gate_c_holdout_shadow_lab.py`
  - Add rolling validation windows and Gate F pass/fail summary.
  - Keep `handedness_bucket_adjust` clearly labeled as hindsight-only.
- Create or modify: `analytics/output/gate_f_projection_challenger_shadow_report.md`
  - One report that summarizes projection accuracy, holdout, rolling windows,
    tracked alignment, and promotion readiness.
- Modify: `tests/test_k_projection_shadow_lab.py`
  - Test new shrink challengers and slice summaries.
- Modify: `tests/test_gate_c_holdout_shadow_lab.py`
  - Test rolling windows and pass/fail rules.
- Modify: `docs/current-state.md`
  - Add this plan to the model lane.
- Modify: `docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`
  - Add this plan as the active Gate F projection child plan.

## Task 1: Add Shrink Challenger Tests

**Files:**
- Modify: `tests/test_k_projection_shadow_lab.py`
- Modify: `analytics/diagnostics/k_projection_shadow_lab.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_k_projection_shadow_lab.py`:

```python
def test_market_shrink_family_moves_projection_toward_line():
    row = {
        "projected_ks": 7.0,
        "k_line": 5.0,
    }

    assert lab.challenger_projection(row, "market_shrink_15") == 6.7
    assert lab.challenger_projection(row, "market_shrink_25") == 6.5
    assert lab.challenger_projection(row, "market_shrink_35") == 6.3


def test_market_shrink_family_handles_missing_line_without_change():
    row = {
        "projected_ks": 7.0,
        "k_line": None,
    }

    assert lab.challenger_projection(row, "market_shrink_15") == 7.0
    assert lab.challenger_projection(row, "market_shrink_35") == 7.0
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_k_projection_shadow_lab.py -q
```

Expected: fail because `market_shrink_15` and `market_shrink_35` are unknown.

- [ ] **Step 3: Update challenger list and projection function**

In `analytics/diagnostics/k_projection_shadow_lab.py`, update `CHALLENGERS`:

```python
CHALLENGERS = [
    "current_model",
    "market_shrink_15",
    "market_shrink_25",
    "market_shrink_35",
    "high_line_temper",
    "leash_cap",
    "recent_rate_blend",
    "career_rate_blend",
]
```

Add this helper near `challenger_projection`:

```python
def _market_shrink_projection(current: float, line: float | None, weight: float) -> float:
    if line is None:
        return round(current, 3)
    return round(current + ((line - current) * weight), 3)
```

Replace the existing `market_shrink_25` branch with:

```python
    if challenger == "market_shrink_15":
        return _market_shrink_projection(current, line, 0.15)

    if challenger == "market_shrink_25":
        return _market_shrink_projection(current, line, 0.25)

    if challenger == "market_shrink_35":
        return _market_shrink_projection(current, line, 0.35)
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_k_projection_shadow_lab.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add analytics/diagnostics/k_projection_shadow_lab.py tests/test_k_projection_shadow_lab.py
git commit -m "feat: add market shrink projection challengers"
```

## Task 2: Add Challenger Slice Summaries

**Files:**
- Modify: `analytics/diagnostics/k_projection_shadow_lab.py`
- Modify: `tests/test_k_projection_shadow_lab.py`

- [ ] **Step 1: Add slice tests**

Append:

```python
def test_summarize_challenger_slices_marks_sample_status():
    rows = [
        {
            "slate_date": "2026-06-01",
            "context_snapshot": "official_close",
            "result": "win",
            "actual_ks": 6,
            "projected_ks": 5.8,
            "k_line": 5.5,
            "line_bucket": "5.5",
            "side": "over",
            "winning_side": "over",
            "price_sign": "minus",
        }
    ]

    slices = lab.summarize_challenger_slices("current_model", rows, "line_bucket", min_rows=10)

    assert slices[0]["bucket"] == "5.5"
    assert slices[0]["rows"] == 1
    assert slices[0]["sample_status"] == "small_sample"
```

- [ ] **Step 2: Implement slice helper**

Add:

```python
def summarize_challenger_slices(
    challenger: str,
    rows: list[dict[str, Any]],
    field: str,
    *,
    min_rows: int = 25,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get(field) or "unknown")].append(row)

    output = []
    for bucket, bucket_rows in sorted(grouped.items()):
        summary = summarize_projection(challenger, bucket_rows)
        summary["bucket"] = bucket
        summary["sample_status"] = "enough_sample" if summary["rows"] >= min_rows else "small_sample"
        output.append(summary)
    return output
```

- [ ] **Step 3: Add report sections**

In `build_report`, add a `## Challenger Slice Checks` section for
`market_shrink_25` and `high_line_temper` across:

```python
("side", "price_sign", "line_bucket", "quality_gate_level", "model_market_relationship", "bet_timing_window", "opportunity_bucket", "leash_risk_bucket", "pitcher_archetype_bucket")
```

Each table should include bucket, rows, MAE, RMSE, side W-L, side accuracy, and
sample status.

- [ ] **Step 4: Run tests and regenerate**

Run:

```powershell
python -m pytest tests/test_k_projection_shadow_lab.py -q
python analytics/diagnostics/k_projection_shadow_lab.py --dataset data/research/gate_c/pitcher_k_outcome_dataset.jsonl --output analytics/output/k_projection_shadow_lab.md
```

Expected: tests pass and the report includes slice checks.

- [ ] **Step 5: Commit**

```powershell
git add analytics/diagnostics/k_projection_shadow_lab.py tests/test_k_projection_shadow_lab.py analytics/output/k_projection_shadow_lab.md
git commit -m "feat: add projection challenger slices"
```

## Task 3: Add Rolling Validation Windows

**Files:**
- Modify: `analytics/diagnostics/gate_c_holdout_shadow_lab.py`
- Modify: `tests/test_gate_c_holdout_shadow_lab.py`

- [ ] **Step 1: Add rolling-window tests**

Append:

```python
def test_rolling_validation_windows_keep_chronological_train_then_validate():
    rows = [
        {"slate_date": f"2026-05-{day:02d}", "context_snapshot": "official_close"}
        for day in range(1, 13)
    ]

    windows = lab.rolling_validation_windows(rows, train_dates=6, validate_dates=3, step_dates=3)

    assert windows[0]["train_dates"] == [
        "2026-05-01",
        "2026-05-02",
        "2026-05-03",
        "2026-05-04",
        "2026-05-05",
        "2026-05-06",
    ]
    assert windows[0]["validate_dates"] == ["2026-05-07", "2026-05-08", "2026-05-09"]
    assert windows[1]["validate_dates"] == ["2026-05-10", "2026-05-11", "2026-05-12"]
```

- [ ] **Step 2: Implement rolling windows**

Add:

```python
def rolling_validation_windows(
    rows: list[dict[str, Any]],
    *,
    train_dates: int = 20,
    validate_dates: int = 5,
    step_dates: int = 5,
) -> list[dict[str, Any]]:
    dates = sorted({str(row.get("slate_date") or "") for row in rows if row.get("slate_date")})
    windows = []
    start = 0
    while start + train_dates + validate_dates <= len(dates):
        train = dates[start : start + train_dates]
        validate = dates[start + train_dates : start + train_dates + validate_dates]
        train_set = set(train)
        validate_set = set(validate)
        windows.append(
            {
                "train_dates": train,
                "validate_dates": validate,
                "train_rows": [row for row in rows if str(row.get("slate_date") or "") in train_set],
                "validate_rows": [row for row in rows if str(row.get("slate_date") or "") in validate_set],
            }
        )
        start += step_dates
    return windows
```

- [ ] **Step 3: Add rolling summary to the report**

In `build_report`, compute rolling windows from `markets`, summarize
`current_model`, `market_shrink_25`, and `high_line_temper` in each validation
window, and add a `## Rolling Validation Windows` table.

- [ ] **Step 4: Run tests and regenerate**

Run:

```powershell
python -m pytest tests/test_gate_c_holdout_shadow_lab.py -q
python analytics/diagnostics/gate_c_holdout_shadow_lab.py --dataset data/research/gate_c/pitcher_k_outcome_dataset.jsonl --output analytics/output/gate_c_holdout_shadow_lab.md
```

Expected: tests pass and report includes rolling-window checks.

- [ ] **Step 5: Commit**

```powershell
git add analytics/diagnostics/gate_c_holdout_shadow_lab.py tests/test_gate_c_holdout_shadow_lab.py analytics/output/gate_c_holdout_shadow_lab.md
git commit -m "feat: add gate f rolling validation windows"
```

## Task 4: Build A Gate F Decision Report

**Files:**
- Create: `analytics/diagnostics/gate_f_projection_challenger_shadow_report.py`
- Create: `tests/test_gate_f_projection_challenger_shadow_report.py`
- Write: `analytics/output/gate_f_projection_challenger_shadow_report.md`

- [ ] **Step 1: Add report tests**

Create `tests/test_gate_f_projection_challenger_shadow_report.py`:

```python
from analytics.diagnostics import gate_f_projection_challenger_shadow_report as report


def test_gate_f_decision_requires_mae_and_slice_survival():
    candidate = {
        "name": "market_shrink_25",
        "holdout_mae_delta": -0.03,
        "holdout_rmse_delta": -0.02,
        "side_accuracy_delta": 0.0,
        "bad_slice_count": 0,
        "fire_2u_degradation": False,
        "positive_rolling_windows": 2,
        "runtime_safe": True,
    }

    decision = report.gate_f_decision(candidate)

    assert decision["status"] == "promotion_plan_candidate"


def test_gate_f_decision_blocks_hindsight_only_candidate():
    candidate = {
        "name": "handedness_bucket_adjust",
        "holdout_mae_delta": -0.04,
        "holdout_rmse_delta": -0.02,
        "side_accuracy_delta": 0.01,
        "bad_slice_count": 0,
        "fire_2u_degradation": False,
        "positive_rolling_windows": 2,
        "runtime_safe": False,
    }

    decision = report.gate_f_decision(candidate)

    assert decision["status"] == "blocked_hindsight_only"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_gate_f_projection_challenger_shadow_report.py -q
```

Expected: fail because the module does not exist.

- [ ] **Step 3: Implement decision helper**

Create `analytics/diagnostics/gate_f_projection_challenger_shadow_report.py`:

```python
"""Gate F projection challenger decision report.

Shadow-only. This module summarizes whether a projection challenger deserves a
later production implementation plan. It must not change live lambda.
"""

from __future__ import annotations

from typing import Any


def gate_f_decision(candidate: dict[str, Any]) -> dict[str, Any]:
    if not candidate.get("runtime_safe", False):
        return {"name": candidate["name"], "status": "blocked_hindsight_only"}
    if candidate.get("holdout_mae_delta", 0.0) > -0.025:
        return {"name": candidate["name"], "status": "blocked_mae_lift_too_small"}
    if candidate.get("holdout_rmse_delta", 0.0) > 0.010:
        return {"name": candidate["name"], "status": "blocked_rmse_degradation"}
    if candidate.get("side_accuracy_delta", 0.0) < -0.005:
        return {"name": candidate["name"], "status": "blocked_side_accuracy_degradation"}
    if candidate.get("bad_slice_count", 0) > 0:
        return {"name": candidate["name"], "status": "blocked_slice_failure"}
    if candidate.get("fire_2u_degradation", False):
        return {"name": candidate["name"], "status": "blocked_fire_2u_degradation"}
    if candidate.get("positive_rolling_windows", 0) < 2:
        return {"name": candidate["name"], "status": "blocked_not_rolling_stable"}
    return {"name": candidate["name"], "status": "promotion_plan_candidate"}
```

- [ ] **Step 4: Add report assembly**

Use the summaries from `k_projection_shadow_lab.py` and
`gate_c_holdout_shadow_lab.py` to write:

```markdown
# Gate F Projection Challenger Shadow Report

Shadow-only: this report does not change live lambda, verdicts, thresholds,
staking, provider order, notifications, calibration, or dashboard artifacts.

## Decision Summary

| Candidate | Status | Reason |
| --- | --- | --- |
```

The first implementation can call shared functions directly rather than parsing
Markdown output.

- [ ] **Step 5: Run tests and generate**

Run:

```powershell
python -m pytest tests/test_gate_f_projection_challenger_shadow_report.py tests/test_k_projection_shadow_lab.py tests/test_gate_c_holdout_shadow_lab.py -q
python analytics/diagnostics/gate_f_projection_challenger_shadow_report.py
```

Expected: tests pass and report writes
`analytics/output/gate_f_projection_challenger_shadow_report.md`.

- [ ] **Step 6: Commit**

```powershell
git add analytics/diagnostics/gate_f_projection_challenger_shadow_report.py tests/test_gate_f_projection_challenger_shadow_report.py analytics/output/gate_f_projection_challenger_shadow_report.md
git commit -m "feat: add gate f projection decision report"
```

## Task 5: Wire The Plan Into Operations Docs

**Files:**
- Modify: `docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`
- Modify: `docs/current-state.md`
- Modify: automation memory when the daily brief should carry the update forward

- [ ] **Step 1: Update the controlling Gate C/F plan**

Add this sentence under `Gate C / Confidence-Referee Scope`:

```markdown
Gate F projection-challenger validation is controlled by `docs/superpowers/plans/2026-06-03-gate-f-projection-challenger-shadow-plan.md`; it tests `market_shrink_25`, `high_line_temper`, and related challengers as shadow-only candidates and cannot change live lambda without a later Tyler-approved production plan.
```

- [ ] **Step 2: Update `docs/current-state.md`**

Add this plan to the model lane and note:

```markdown
Gate F projection-challenger work is now a separate shadow validation package; `market_shrink_25` and `high_line_temper` deserve study, but neither can change live lambda until the Gate F package passes and Tyler approves a production plan.
```

- [ ] **Step 3: Verify docs**

Run:

```powershell
rg -n "gate-f-projection|Gate F projection" docs/current-state.md docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md docs/superpowers/plans/2026-06-03-gate-f-projection-challenger-shadow-plan.md
git diff --check
```

Expected: references are present and diff check has no errors other than Windows line-ending warnings.

- [ ] **Step 4: Commit**

```powershell
git add docs/current-state.md docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md docs/superpowers/plans/2026-06-03-gate-f-projection-challenger-shadow-plan.md
git commit -m "docs: add gate f projection challenger plan"
```

## Rollback

This plan creates or extends shadow diagnostics and reports only. Rollback is
deleting the new report module, tests, generated Markdown, and doc pointers.
No production behavior changes.

## Decision Boundary

The highest possible outcome from this plan is a recommendation to draft a
separate production implementation plan with:

- exact production code paths
- one feature flag or config switch
- rollback command
- one-slate canary
- before/after diagnostics
- explicit Tyler approval

Do not implement live projection behavior from this plan.
