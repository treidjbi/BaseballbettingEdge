# Post-Phase-C Live Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify that the newly landed Phase B/C signals are flowing on a real run, being stored in the live artifacts, and materially participating in lambda / verdict generation.

**Architecture:** This is an operational validation pass, not a feature build. We run the real pipeline path, inspect the stored JSON artifacts and diagnostics, then do a few targeted record-level checks that prove opener, park, rest, SwStr, and warning fields are not just present but affecting output semantics.

**Tech Stack:** Python 3.11, pytest, existing diagnostics in `analytics/diagnostics/`, GitHub Actions or local repo venv pipeline run, JSON inspection from `today.json` / `picks_history.json`.

---

### Task 1: Run the real pipeline path

**Files:**
- Read: `dashboard/data/processed/today.json`
- Read: `data/picks_history.json`
- Reference: `pipeline/run_pipeline.py`

- [ ] **Step 1: Trigger a real pipeline run**

Preferred production-path proof:

```text
Run the normal GitHub workflow that generates today's slate.
```

Local fallback if needed:

```powershell
cd C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge
.\.venv\Scripts\python.exe pipeline\run_pipeline.py 2026-04-27
```

- [ ] **Step 2: Confirm the run completed and wrote fresh artifacts**

Run:

```powershell
cd C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge
Get-Item dashboard\data\processed\today.json, data\picks_history.json | Select-Object Name, LastWriteTime, Length
```

Expected:
- `today.json` and `picks_history.json` have a fresh timestamp from the manual run
- file sizes are non-zero

---

### Task 2: Confirm raw field activation in live output

**Files:**
- Read: `dashboard/data/processed/today.json`
- Read: `analytics/diagnostics/pre_c_swstr_confirmation.py`

- [ ] **Step 1: Run the existing forward-proof diagnostic**

Run:

```powershell
cd C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge
.\.venv\Scripts\python.exe analytics\diagnostics\pre_c_swstr_confirmation.py
```

Expected:
- fresh rows exist for the current post-fix date window
- at least some rows show non-null `career_swstr_pct`
- at least some rows show nonzero `swstr_delta_k9`
- at least some rows show `data_complete == 1`

- [ ] **Step 2: Inspect current-slate field population directly**

Run:

```powershell
@'
import json
from pathlib import Path

path = Path(r"C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\dashboard\data\processed\today.json")
data = json.loads(path.read_text(encoding="utf-8"))
pitchers = data.get("pitchers", [])

def nz(v):
    return isinstance(v, (int, float)) and abs(v) > 1e-9

print("pitchers", len(pitchers))
print("career_swstr_pct non-null", sum(1 for p in pitchers if p.get("career_swstr_pct") is not None))
print("swstr_delta_k9 nonzero", sum(1 for p in pitchers if nz(p.get("swstr_delta_k9"))))
print("park_factor populated", sum(1 for p in pitchers if p.get("park_factor") is not None))
print("days_since_last_start populated", sum(1 for p in pitchers if p.get("days_since_last_start") is not None))
print("last_pitch_count populated", sum(1 for p in pitchers if p.get("last_pitch_count") is not None))
print("rest_k9_delta nonzero", sum(1 for p in pitchers if nz(p.get("rest_k9_delta"))))
print("is_opener flagged", sum(1 for p in pitchers if p.get("is_opener") is True))
print("data_warnings", data.get("data_warnings", []))
'@ | .\.venv\Scripts\python.exe -
```

Expected:
- `park_factor` populated for essentially the full slate
- `days_since_last_start` / `last_pitch_count` populated for most starters
- `swstr_delta_k9` nonzero on at least some pitchers
- `data_warnings` is either empty on a healthy run or readable and source-specific on a degraded one

---

### Task 3: Prove the new signals influence behavior, not just storage

**Files:**
- Read: `dashboard/data/processed/today.json`
- Reference: `pipeline/build_features.py`

- [ ] **Step 1: Spot-check opener suppression**

Run:

```powershell
@'
import json
from pathlib import Path

path = Path(r"C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\dashboard\data\processed\today.json")
data = json.loads(path.read_text(encoding="utf-8"))
pitchers = data.get("pitchers", [])
openers = [p for p in pitchers if p.get("is_opener")]
print("openers", len(openers))
for p in openers[:5]:
    print(p["pitcher"], p.get("opener_note"), p["ev_over"]["verdict"], p["ev_under"]["verdict"], p["ev_over"].get("adj_ev"), p["ev_under"].get("adj_ev"))
'@ | .\.venv\Scripts\python.exe -
```

Expected:
- any flagged opener has `PASS` / `PASS`
- opener rows show `adj_ev == 0.0` on both sides

- [ ] **Step 2: Spot-check park/rest/SwStr contribution breadcrumbs**

Run:

```powershell
@'
import json
from pathlib import Path

path = Path(r"C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\dashboard\data\processed\today.json")
data = json.loads(path.read_text(encoding="utf-8"))
pitchers = data.get("pitchers", [])

interesting = [
    p for p in pitchers
    if p.get("park_factor") not in (None, 1.0)
    or (isinstance(p.get("rest_k9_delta"), (int, float)) and abs(p.get("rest_k9_delta")) > 1e-9)
    or (isinstance(p.get("swstr_delta_k9"), (int, float)) and abs(p.get("swstr_delta_k9")) > 1e-9)
]

print("interesting pitchers", len(interesting))
for p in interesting[:10]:
    print({
        "pitcher": p["pitcher"],
        "lambda": p.get("lambda"),
        "raw_lambda": p.get("raw_lambda"),
        "park_factor": p.get("park_factor"),
        "days_since_last_start": p.get("days_since_last_start"),
        "last_pitch_count": p.get("last_pitch_count"),
        "rest_k9_delta": p.get("rest_k9_delta"),
        "swstr_delta_k9": p.get("swstr_delta_k9"),
        "ump_k_adj": p.get("ump_k_adj"),
    })
'@ | .\.venv\Scripts\python.exe -
```

Expected:
- at least some rows show non-neutral `park_factor`
- at least some rows show nonzero `swstr_delta_k9` and/or `rest_k9_delta`
- those rows carry the corresponding breadcrumbs in the output record

---

### Task 4: Re-run analytics with the live-window lens

**Files:**
- Read: `analytics/performance.py`

- [ ] **Step 1: Run analytics on the broad recent window**

Run:

```powershell
cd C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge
.\.venv\Scripts\python.exe analytics\performance.py --since 2026-04-08
```

Expected:
- script runs cleanly
- dead-window warning is still present until enough post-`2026-04-28` rows exist

- [ ] **Step 2: Once fresh post-fix rows exist, run the clean-window slice**

Run:

```powershell
cd C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge
.\.venv\Scripts\python.exe analytics\performance.py --since 2026-04-28
```

Expected:
- signal activation block starts showing the true post-fix rates for:
  - `swstr_delta_k9 != 0`
  - `park_factor populated`
  - `rest_k9_delta`
  - `is_opener`

---

### Task 5: Make the go/no-go call for the next planning phase

**Files:**
- Read: `docs/superpowers/plans/2026-04-16-model-audit-and-gaps.md`
- Read: `docs/superpowers/plans/2026-04-27-bucketed-lambda-calibration.md`

- [ ] **Step 1: Summarize the live-check result**

Record the result in plain language:
- which Phase C fields populated cleanly
- whether any `data_warnings` fired
- whether opener suppression behaved correctly
- whether park/rest/SwStr breadcrumbs show up on real rows
- whether any field appears present-but-dormant

- [ ] **Step 2: Use that result to choose the next plan**

Decision rule:
- if the live checks pass, proceed to the next planning track:
  1. current data structure / historics / storage / use
  2. projection-quality audit
- if one of the new fields is present but dormant or obviously miswired, stop and write a targeted follow-up fix plan before the broader audit work

