# Pre-Phase-C Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Clean up the remaining SwStr confirmation, calibration, and analytics-tracking issues identified after Phase B so Phase C starts from a trustworthy model and measurement baseline.

**Architecture:** This is a narrow pre-Phase-C stabilization pass. It does **not** add new model signals. First, confirm the newly landed SwStr transport is actually populating fresh stored picks. Next, harden row-level completeness tracking so calibration only learns from complete inputs. Then repair the phase-2 calibration math and the Phase B analytics/reporting logic. The output of this plan is a clean go/no-go checkpoint for Phase C plus an explicit decision on whether SwStr-live behavior needs a new calibration era boundary.

**Tech Stack:** Python 3.11, pytest, pandas, matplotlib, requests, scipy, existing pipeline/analytics scripts.

---

## Scope Note

This plan intentionally stops short of Phase C feature work. No opener, park, rest, or K-variance additions belong here. The goal is to make sure:

1. SwStr is truly live on fresh stored rows
2. calibration is not learning from mixed-quality inputs
3. `analytics/performance.py` is trustworthy enough to guide Phase C priorities

The canonical running tracker remains:
- [2026-04-16-model-audit-and-gaps.md](C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/docs/superpowers/plans/2026-04-16-model-audit-and-gaps.md)

This plan is the executable cleanup companion to that addendum, not a replacement.

---

## File Map

**Likely files to modify**

- Modify: `pipeline/run_pipeline.py`
  SwStr health metadata + row-level `data_complete` logic.
- Modify: `pipeline/fetch_statcast.py`
  If the fresh-store confirmation exposes a remaining producer-side edge case, fix it here.
- Modify: `pipeline/calibrate.py`
  Repair ump residual math and, if approved, introduce a post-SwStr-live calibration boundary.
- Modify: `analytics/performance.py`
  Stake-weighted ROI/PnL, `adj_ev`-based buckets, and window-aware reporting.
- Modify: `docs/superpowers/plans/2026-04-16-model-audit-and-gaps.md`
  Record completion/progress checkpoints only; do not move detailed implementation steps into that file.

**Likely files to create**

- Create: `analytics/diagnostics/pre_c_swstr_confirmation.py`
  Focused forward-proof diagnostic for freshly stored rows.
- Create: `tests/test_calibrate.py` additions
  Regression coverage for ump residual math and any calibration-boundary helper.
- Create: `tests/test_run_pipeline.py` additions
  Regression coverage for row-level `data_complete`.
- Create: `tests/test_performance_analytics.py` only if needed
  Prefer targeted function-level coverage if the repo already has an analytics test pattern; otherwise keep verification command-based.

---

## Task 1: Confirm SwStr Is Landing On Fresh Stored Picks

**Files:**
- Create: `analytics/diagnostics/pre_c_swstr_confirmation.py`
- Read/verify: `data/picks_history.json`
- Read/verify: `dashboard/data/processed/today.json`

This task is a gate. Do **not** change analytics/performance based on assumptions about SwStr until this is checked on fresh stored rows after the mainline repair.

- [ ] **Step 1: Add a focused forward-proof diagnostic**

Create `analytics/diagnostics/pre_c_swstr_confirmation.py`:

```python
"""Confirm SwStr is live on fresh stored rows after the mainline transport repair."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HIST = ROOT / "data" / "picks_history.json"
TODAY = ROOT / "dashboard" / "data" / "processed" / "today.json"

if not HIST.exists():
    print(f"ERROR: {HIST} not found")
    raise SystemExit(1)

rows = json.loads(HIST.read_text(encoding="utf-8"))
recent = [r for r in rows if (r.get("date") or "") >= "2026-04-27"]

print("=== Fresh stored rows ===")
print("rows:", len(recent))
print("career_swstr_pct non-null:", sum(1 for r in recent if r.get("career_swstr_pct") is not None))
print("swstr_delta_k9 nonzero:", sum(1 for r in recent if abs((r.get("swstr_delta_k9") or 0.0)) > 1e-9))
print("data_complete true:", sum(1 for r in recent if r.get("data_complete") == 1))
print("top (date, complete, career_none, delta_zero) combos:")
combo = Counter(
    (
        r.get("date"),
        r.get("data_complete"),
        r.get("career_swstr_pct") is None,
        abs((r.get("swstr_delta_k9") or 0.0)) <= 1e-9,
    )
    for r in recent
)
for item, count in combo.most_common(10):
    print(count, item)

if TODAY.exists():
    today = json.loads(TODAY.read_text(encoding="utf-8"))
    pitchers = today.get("pitchers", [])
    print("\\n=== today.json live snapshot ===")
    print("pitchers:", len(pitchers))
    print("career_swstr_pct non-null:", sum(1 for p in pitchers if p.get("career_swstr_pct") is not None))
    print("swstr_delta_k9 nonzero:", sum(1 for p in pitchers if abs((p.get("swstr_delta_k9") or 0.0)) > 1e-9))
```

- [ ] **Step 2: Run the diagnostic on the first fresh post-repair slate**

Run:

```powershell
C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\.venv\Scripts\python.exe analytics\diagnostics\pre_c_swstr_confirmation.py
```

Expected:
- fresh rows exist for the first post-repair run
- at least some rows have non-null `career_swstr_pct`
- at least some rows have nonzero `swstr_delta_k9`

If all fresh rows still show `career_swstr_pct=None` or `swstr_delta_k9=0`, stop and re-open `pipeline/fetch_statcast.py` before continuing.

- [ ] **Step 3: Commit the diagnostic**

```bash
git add analytics/diagnostics/pre_c_swstr_confirmation.py
git commit -m "chore(pre-c): add SwStr forward-proof diagnostic"
```

---

## Task 2: Make `data_complete` Pitcher-Specific Instead Of Slate-Specific

**Files:**
- Modify: `pipeline/run_pipeline.py`
- Test: `tests/test_run_pipeline.py`

Current problem: a single healthy pitcher can make the whole slate look complete. This must become row-level before calibration can trust it.

- [ ] **Step 1: Write the failing tests**

Add focused tests in `tests/test_run_pipeline.py` around a new helper, for example `_row_data_complete(...)`:

```python
def test_row_data_complete_false_when_pitcher_has_neutral_swstr_baseline():
    from run_pipeline import _row_data_complete
    assert _row_data_complete(
        swstr_data={"swstr_pct": 0.141, "career_swstr_pct": None},
        ump_k_adj=0.42,
        swstr_meta={"current_usable": True, "career_usable": True},
        ump_meta={"pitcher_has_assignment": True, "pitcher_has_rate": True},
    ) is False


def test_row_data_complete_false_when_pitcher_lacks_ump_assignment():
    from run_pipeline import _row_data_complete
    assert _row_data_complete(
        swstr_data={"swstr_pct": 0.141, "career_swstr_pct": 0.122},
        ump_k_adj=0.0,
        swstr_meta={"current_usable": True, "career_usable": True},
        ump_meta={"pitcher_has_assignment": False, "pitcher_has_rate": False},
    ) is False


def test_row_data_complete_true_when_both_signals_are_live():
    from run_pipeline import _row_data_complete
    assert _row_data_complete(
        swstr_data={"swstr_pct": 0.141, "career_swstr_pct": 0.122},
        ump_k_adj=0.42,
        swstr_meta={"current_usable": True, "career_usable": True},
        ump_meta={"pitcher_has_assignment": True, "pitcher_has_rate": True},
    ) is True
```

- [ ] **Step 2: Run the tests to verify red**

Run:

```powershell
C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\.venv\Scripts\python.exe -m pytest tests\test_run_pipeline.py -k data_complete -v
```

Expected: FAIL because `_row_data_complete` does not exist yet and/or row-level completeness is not implemented.

- [ ] **Step 3: Add a small row-level completeness helper**

In `pipeline/run_pipeline.py`, add a focused helper that decides completeness per pitcher using:
- the specific pitcher's `swstr_data`
- SwStr transport metadata
- pitcher-level ump assignment/rate metadata

Implementation target:
- `False` if `career_swstr_pct is None` when the SwStr transport was otherwise expected to be usable
- `False` if the specific pitcher lacks ump assignment/rate coverage
- `True` only when the row’s upstream inputs are genuinely live

- [ ] **Step 4: Wire `record["data_complete"]` through the row helper**

Replace the current slate-level assignment:

```python
record["data_complete"] = swstr_ok and ump_ok
```

with a per-row call that uses the row’s actual signal state.

- [ ] **Step 5: Run the targeted tests**

Run:

```powershell
C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\.venv\Scripts\python.exe -m pytest tests\test_run_pipeline.py -k data_complete -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pipeline/run_pipeline.py tests/test_run_pipeline.py
git commit -m "fix(pre-c): make data_complete pitcher-specific"
```

---

## Task 3: Repair Phase-2 Ump Calibration Residual Math

**Files:**
- Modify: `pipeline/calibrate.py`
- Test: `tests/test_calibrate.py`

Current problem: ump calibration correlates against a residual that already includes the ump effect, which structurally biases `ump_scale` toward shrinkage.

- [ ] **Step 1: Write the failing test**

Add a focused regression test in `tests/test_calibrate.py` for a helper such as `_ump_neutral_residual(...)`:

```python
def test_ump_neutral_residual_adds_current_ump_contribution_back():
    from calibrate import _ump_neutral_residual
    residual = _ump_neutral_residual(
        actual_ks=8.0,
        raw_lambda=7.0,
        ump_k_adj=0.9,
        avg_ip=6.0,
        ump_scale=1.0,
    )
    assert round(residual, 3) == round((8.0 - 7.0) + (0.9 * (6.0 / 9.0) * 1.0), 3)
```

- [ ] **Step 2: Run targeted tests to verify red**

Run:

```powershell
C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\.venv\Scripts\python.exe -m pytest tests\test_calibrate.py -k ump -v
```

Expected: FAIL because the helper does not exist and/or current logic uses the confounded residual.

- [ ] **Step 3: Implement the helper and use it in `_calibrate_phase2`**

Refactor the ump section so it mirrors the SwStr pattern:
- compute the modeled ump contribution from `ump_k_adj`, `avg_ip`, and current `ump_scale`
- add that contribution back out before correlating

Do **not** change the outer calibration thresholds in this task. Only fix the residual math.

- [ ] **Step 4: Run targeted calibration tests**

Run:

```powershell
C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\.venv\Scripts\python.exe -m pytest tests\test_calibrate.py -k ump -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pipeline/calibrate.py tests/test_calibrate.py
git commit -m "fix(pre-c): use ump-neutral residual in phase-2 calibration"
```

---

## Task 4: Decide And Implement The Post-SwStr-Live Calibration Boundary

**Files:**
- Modify: `pipeline/calibrate.py`
- Modify: `data/params.json` only if explicitly chosen by the user during execution
- Update tracker: `docs/superpowers/plans/2026-04-16-model-audit-and-gaps.md`

This task has a decision gate. The user already approved the idea in principle, but the exact implementation should still be treated as an explicit choice during execution because it touches live calibration behavior.

- [ ] **Step 1: Quantify the mixed dead/live window**

Add a small one-off diagnostic or reuse Task 1’s script to answer:
- how many rows since `2026-04-08` have `career_swstr_pct=None`
- how many of those still have `data_complete=1`
- what date the first clearly live SwStr rows appear

- [ ] **Step 2: Present the execution decision**

During implementation, stop and present exactly these two options:

1. add a new calibration cutoff/boundary at the first confirmed SwStr-live date
2. keep the current cutoff and rely only on improved `data_complete` filtering

Recommendation: option 1 if the mixed window is still large enough to materially distort `swstr_k9_scale` and `lambda_bias`.

- [ ] **Step 3: If option 1 is chosen, implement the boundary minimally**

Prefer a small, explicit mechanism:
- either a new `formula_change_date` / equivalent calibration-floor update in `params.json`
- or a calibration-time filter keyed to the first confirmed SwStr-live date

Do **not** rewrite stored historical picks/results.

- [ ] **Step 4: Document the decision in the tracker**

Append the chosen calibration-boundary decision and rationale to:
- [2026-04-16-model-audit-and-gaps.md](C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/docs/superpowers/plans/2026-04-16-model-audit-and-gaps.md)

- [ ] **Step 5: Commit**

```bash
git add pipeline/calibrate.py data/params.json docs/superpowers/plans/2026-04-16-model-audit-and-gaps.md
git commit -m "chore(pre-c): set post-swstr-live calibration boundary"
```

If option 2 is chosen, adjust the commit message and only commit the tracker note / any filter changes actually made.

---

## Task 5: Repair `analytics/performance.py` So Phase B Readouts Are Trustworthy

**Files:**
- Modify: `analytics/performance.py`
- Verify by command output

Current problems already confirmed:
- PnL/ROI is not stake-weighted
- several EV views bucket `ev` instead of `adj_ev`
- movement slices conflate `first_seen`/ungated rows with true no-move rows
- full-history slices mix dead-window and live-window regimes too casually

- [ ] **Step 1: Fix stake-weighted PnL/ROI**

Update `_row()` and the rolling PnL plot so `pnl` is multiplied by `units_risked` before aggregation.

Verification target:
- current script’s false staked ROI `+1.04%` should move to the true stake-weighted value previously confirmed during review (`-1.66%` on the reviewed sample)

- [ ] **Step 2: Move EV-bucketed views to `adj_ev`**

At minimum:
- `by_ev_bucket`
- `dead_zone_profile`
- `plot_ev_vs_actual`

should bucket on `adj_ev`, because that is the signal that actually drove verdicts/staking.

- [ ] **Step 3: Split movement reporting into truthful categories**

Do not label every `movement_conf == 1.0` row as “no move.”
At minimum, distinguish:
- true preview/no-fade rows
- `first_seen`
- legacy/unknown opening-source rows

- [ ] **Step 4: Add an explicit post-fix/live-window reporting mode**

Provide one of:
- a default warning banner when running full-history
- or a helper/date fence for known dead windows

The goal is to make it hard to accidentally compare dead-window rows to live-window rows without noticing.

- [ ] **Step 5: Run the analytics command and capture the new baseline**

Run:

```powershell
C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\.venv\Scripts\python.exe analytics\performance.py --since 2026-04-08
```

Expected:
- stake-weighted ROI/PnL values
- EV tables aligned to `adj_ev`
- movement table labels that match real source semantics

- [ ] **Step 6: Commit**

```bash
git add analytics/performance.py
git commit -m "fix(pre-c): make phase-b analytics stake-weighted and regime-aware"
```

---

## Task 6: Pre-Phase-C Go/No-Go Checkpoint

**Files:**
- Update tracker: `docs/superpowers/plans/2026-04-16-model-audit-and-gaps.md`

- [ ] **Step 1: Summarize the post-cleanup state**

Capture:
- whether fresh stored rows prove SwStr is live
- whether row-level `data_complete` is fixed
- whether ump calibration math is repaired
- whether a new calibration boundary was adopted
- whether `analytics/performance.py` is now trustworthy enough to guide Phase C prioritization

- [ ] **Step 2: Update the tracker**

Append a short checkpoint note to:
- [2026-04-16-model-audit-and-gaps.md](C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/docs/superpowers/plans/2026-04-16-model-audit-and-gaps.md)

Mark this cleanup plan complete there and state whether Phase C is now unblocked.

- [ ] **Step 3: Final verification**

Run:

```powershell
C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\.venv\Scripts\python.exe -m pytest tests\test_fetch_statcast.py -q
C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\.venv\Scripts\python.exe -m pytest tests\test_build_features.py -q
C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\.venv\Scripts\python.exe -m pytest tests\test_run_pipeline.py -q
C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\.venv\Scripts\python.exe -m pytest tests\test_calibrate.py -q
C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\.venv\Scripts\python.exe analytics\diagnostics\pre_c_swstr_confirmation.py
C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\.venv\Scripts\python.exe analytics\performance.py --since 2026-04-08
```

Expected:
- green targeted tests
- SwStr live on fresh rows
- cleaned analytics output

- [ ] **Step 4: Commit tracker updates**

```bash
git add docs/superpowers/plans/2026-04-16-model-audit-and-gaps.md docs/superpowers/plans/2026-04-27-pre-phase-c-cleanup.md
git commit -m "docs(pre-c): record cleanup checkpoint before phase c"
```

---

## Recommended Execution Order

1. Task 1 — SwStr confirmation
2. Task 2 — row-level `data_complete`
3. Task 3 — ump residual math
4. Task 4 — calibration-boundary decision
5. Task 5 — analytics/performance cleanup
6. Task 6 — go/no-go checkpoint

If Task 1 fails, stop and re-open the producer before any of the later work.
