# SwStr Signal Repair And Rebaseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore the dormant SwStr delta signal (`swstr_delta_k9`) so new picks stop defaulting to neutral SwStr inputs, then rebaseline Phase B analytics on fresh post-fix data.

**Architecture:** This is a plumbing-and-verification plan, not a model-redesign plan. First, prove the current failure mode with a focused diagnostic and red tests. Next, refactor `fetch_statcast.py` so career SwStr baselines are fetched season-by-season instead of relying on the current multi-year query path that is yielding `career_swstr_pct=None` for every stored post-4/8 row. Finally, document the forward-only fix window and rerun the analytics slices after one fresh graded slate so the B1/B2/B4 findings are read with the SwStr signal alive.

**Tech Stack:** Python 3.11, pybaseball, pandas, pytest, existing analytics/diagnostics scripts.

---

## Scope Note

Phase B surfaced two categories of issues:

1. **Plumbing issue:** `swstr_delta_k9` appears fully dead (`0/422` active since `2026-04-08`, `career_swstr_pct=None` on every stored row).
2. **Model-shape issues:** over-side residual asymmetry and high-lambda negative residuals.

These are **not** the same subsystem. Fix the SwStr plumbing first, let it soak, rerun Phase B, and only then decide whether the model-shape issues still need a dedicated bias/tail plan. Do **not** bundle per-side bias terms or tail haircuts into this plan.

## File Map

**Existing files this plan expects to modify**

- Modify: `pipeline/fetch_statcast.py`
  Current-season and career SwStr fetch logic. This is the likely root cause area because post-4/8 stored rows show `career_swstr_pct=None` universally.
- Modify: `tests/test_fetch_statcast.py`
  New focused regression tests for current-season lookup, career baseline aggregation, and graceful fallback behavior. This file does not exist yet and should be created.
- Create: `analytics/diagnostics/b5_swstr_activation.py`
  Focused one-off diagnostic that prints the SwStr field population/activation rates from `picks_history.json` and optionally probes the live `fetch_swstr()` return shape.
- Modify: `docs/data-caveats.md`
  Add a note describing the SwStr-neutral bug window and the forward-only fix policy (no historical regrade/backfill).
- Modify: `CLAUDE.md`
  Update the API/model notes so the repaired SwStr contract is documented where future debugging starts.

**Files intentionally out of scope**

- `pipeline/build_features.py`
  The math is already exercised by existing SwStr delta tests; the current failure signal points upstream at data-fetch/plumbing, not the delta formula itself.
- `pipeline/calibrate.py`
  Do not alter `lambda_bias`, `swstr_k9_scale`, or `formula_change_date` in this plan.
- `analytics/performance.py`
  Phase B already landed. Use it for verification only; do not mix more analytics work into this plan.

---

### Task 1: Capture The Failure Mode In A Dedicated Diagnostic

**Files:**
- Create: `analytics/diagnostics/b5_swstr_activation.py`

- [ ] **Step 1: Add a focused SwStr diagnostic script**

Create `analytics/diagnostics/b5_swstr_activation.py` with this content:

```python
"""Diagnose dormant SwStr signal in picks_history.json and live fetch_swstr().

Purpose:
  - Confirm whether stored picks are carrying neutral SwStr inputs
  - Distinguish "current SwStr missing" from "career baseline missing"
  - Probe the live fetch_swstr() contract on a small pitcher sample
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HIST = ROOT / "data" / "picks_history.json"

if not HIST.exists():
    print(f"ERROR: {HIST} not found")
    raise SystemExit(1)

rows = json.loads(HIST.read_text())
rows = [r for r in rows if (r.get("date") or "") >= "2026-04-08"]

print("=== Stored picks since 2026-04-08 ===")
print("rows:", len(rows))
print("swstr_delta_k9 nonzero:", sum(1 for r in rows if abs((r.get("swstr_delta_k9") or 0.0)) > 1e-9))
print("swstr_pct is None:", sum(1 for r in rows if r.get("swstr_pct") is None))
print("career_swstr_pct is None:", sum(1 for r in rows if r.get("career_swstr_pct") is None))
print(
    "current==career:",
    sum(
        1 for r in rows
        if r.get("swstr_pct") is not None
        and r.get("career_swstr_pct") is not None
        and r.get("swstr_pct") == r.get("career_swstr_pct")
    ),
)

combo_counts = Counter(
    (r.get("swstr_pct"), r.get("career_swstr_pct"), r.get("swstr_delta_k9"))
    for r in rows
)
print("top stored combos:")
for combo, count in combo_counts.most_common(10):
    print(f"  {count:>4}  {combo}")

sys.path.insert(0, str(ROOT / "pipeline"))
from fetch_statcast import fetch_swstr  # noqa: E402

sample_pitchers = sorted({r["pitcher"] for r in rows if r.get("pitcher")})[:10]
if not sample_pitchers:
    print("No pitchers found in picks_history sample; stopping.")
    raise SystemExit(0)

print("\\n=== Live fetch_swstr() sample ===")
print("pitchers:", sample_pitchers)
result = fetch_swstr(2026, sample_pitchers)
for name in sample_pitchers:
    print(name, "->", result.get(name))
```

- [ ] **Step 2: Run the diagnostic and capture the red baseline**

Run:

```powershell
C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\.venv\Scripts\python.exe analytics\diagnostics\b5_swstr_activation.py
```

Expected right now (red state):
- stored `swstr_delta_k9 nonzero: 0`
- stored `career_swstr_pct is None` equal to the full post-`2026-04-08` sample
- live `fetch_swstr()` likely returns `career_swstr_pct=None` for the sample pitchers too

- [ ] **Step 3: Commit the diagnostic script**

```bash
git add analytics/diagnostics/b5_swstr_activation.py
git commit -m "chore(swstr): add activation diagnostic for dormant swstr signal"
```

---

### Task 2: Add Red Tests For Current And Career SwStr Contracts

**Files:**
- Create: `tests/test_fetch_statcast.py`
- Modify: `pipeline/fetch_statcast.py`

- [ ] **Step 1: Write failing tests for the repaired fetch contract**

Create `tests/test_fetch_statcast.py` with this content:

```python
import os
import sys
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))

import fetch_statcast  # noqa: E402


def _fg_df(rows):
    return pd.DataFrame(rows)


def test_fetch_swstr_returns_current_and_3yr_career_average():
    current_df = _fg_df([
        {"Name": "Shota Imanaga", "SwStr%": 0.145},
        {"Name": "Chris Sale", "SwStr%": 0.160},
    ])
    prior_2023 = _fg_df([
        {"Name": "Shota Imanaga", "SwStr%": 0.120},
        {"Name": "Chris Sale", "SwStr%": 0.150},
    ])
    prior_2024 = _fg_df([
        {"Name": "Shota Imanaga", "SwStr%": 0.125},
        {"Name": "Chris Sale", "SwStr%": 0.155},
    ])
    prior_2025 = _fg_df([
        {"Name": "Shota Imanaga", "SwStr%": 0.130},
        {"Name": "Chris Sale", "SwStr%": 0.158},
    ])

    with patch(
        "fetch_statcast.pitching_stats",
        side_effect=[current_df, prior_2023, prior_2024, prior_2025],
    ):
        result = fetch_statcast.fetch_swstr(2026, ["Shota Imanaga", "Chris Sale"])

    assert result["Shota Imanaga"]["swstr_pct"] == 0.145
    assert round(result["Shota Imanaga"]["career_swstr_pct"], 3) == 0.125
    assert result["Chris Sale"]["swstr_pct"] == 0.160
    assert round(result["Chris Sale"]["career_swstr_pct"], 3) == 0.154


def test_fetch_swstr_handles_partial_career_window():
    current_df = _fg_df([{"Name": "Roki Sasaki", "SwStr%": 0.138}])
    empty_prior = pd.DataFrame(columns=["Name", "SwStr%"])
    prior_2025 = _fg_df([{"Name": "Roki Sasaki", "SwStr%": 0.118}])

    with patch(
        "fetch_statcast.pitching_stats",
        side_effect=[current_df, empty_prior, empty_prior, prior_2025],
    ):
        result = fetch_statcast.fetch_swstr(2026, ["Roki Sasaki"])

    assert result["Roki Sasaki"]["swstr_pct"] == 0.138
    assert result["Roki Sasaki"]["career_swstr_pct"] == 0.118


def test_fetch_swstr_returns_none_when_no_prior_seasons_exist():
    current_df = _fg_df([{"Name": "Jacob Misiorowski", "SwStr%": 0.141}])
    empty_prior = pd.DataFrame(columns=["Name", "SwStr%"])

    with patch(
        "fetch_statcast.pitching_stats",
        side_effect=[current_df, empty_prior, empty_prior, empty_prior],
    ):
        result = fetch_statcast.fetch_swstr(2026, ["Jacob Misiorowski"])

    assert result["Jacob Misiorowski"]["swstr_pct"] == 0.141
    assert result["Jacob Misiorowski"]["career_swstr_pct"] is None
```

- [ ] **Step 2: Run the new test file and verify it fails**

Run:

```powershell
C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\.venv\Scripts\python.exe -m pytest tests\test_fetch_statcast.py -q
```

Expected: FAIL because the current `fetch_swstr()` implementation does not call `pitching_stats()` season-by-season for the three prior years and therefore will not satisfy the mocked call sequence / averaging behavior.

- [ ] **Step 3: Add a contract test for accent-insensitive matching**

Append this test:

```python
def test_fetch_swstr_matches_normalized_pitcher_names():
    current_df = _fg_df([{"Name": "Shota Imanaga", "SwStr%": 0.140}])
    empty_prior = pd.DataFrame(columns=["Name", "SwStr%"])

    with patch(
        "fetch_statcast.pitching_stats",
        side_effect=[current_df, empty_prior, empty_prior, empty_prior],
    ):
        result = fetch_statcast.fetch_swstr(2026, ["Shōta Imanaga"])

    assert result["Shōta Imanaga"]["swstr_pct"] == 0.140
```

- [ ] **Step 4: Run the test file again**

Run:

```powershell
C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\.venv\Scripts\python.exe -m pytest tests\test_fetch_statcast.py -q
```

Expected: still FAIL, for the same implementation reason, but without syntax/import errors.

---

### Task 3: Refactor `fetch_statcast.py` To Build Career Baselines Season-By-Season

**Files:**
- Modify: `pipeline/fetch_statcast.py`
- Test: `tests/test_fetch_statcast.py`

- [ ] **Step 1: Add a helper that fetches one season safely**

In `pipeline/fetch_statcast.py`, add this helper below `_get_swstr_col`:

```python
def _fetch_swstr_lookup_for_window(start_season: int, end_season: int) -> dict:
    """Fetch one FanGraphs window and return {normalized_name: swstr_pct}.

    Returns {} on any failure so callers can decide whether to degrade
    partially (career only) or fully (current season missing).
    """
    try:
        df = pitching_stats(start_season, end_season, qual=0)
    except Exception as e:
        log.info(
            "fetch_swstr: pitching_stats(%s, %s) failed: %s",
            start_season, end_season, e,
        )
        return {}

    if df is None or df.empty:
        return {}

    swstr_col = _get_swstr_col(df)
    if not swstr_col:
        log.info(
            "fetch_swstr: SwStr%% column not found for %s-%s window",
            start_season, end_season,
        )
        return {}

    return _build_swstr_lookup(df, swstr_col)
```

- [ ] **Step 2: Add a helper that averages prior seasons instead of relying on one multi-year call**

Still in `pipeline/fetch_statcast.py`, add:

```python
def _fetch_career_swstr_lookup(season: int) -> dict:
    """Return 3-year pre-season SwStr% averages keyed by normalized pitcher name.

    Fetches each prior season individually and averages only the seasons
    that actually return data for a pitcher.
    """
    season_maps = []
    for yr in range(season - 3, season):
        season_maps.append(_fetch_swstr_lookup_for_window(yr, yr))

    sums = {}
    counts = {}
    for lookup in season_maps:
        for name, swstr in lookup.items():
            sums[name] = sums.get(name, 0.0) + swstr
            counts[name] = counts.get(name, 0) + 1

    return {name: sums[name] / counts[name] for name in sums if counts[name] > 0}
```

- [ ] **Step 3: Replace the existing current/career fetch body to use the helpers**

Replace the current `fetch_swstr()` internals with this structure:

```python
def fetch_swstr(season: int, pitcher_names: list) -> dict:
    fallback = {
        name: {"swstr_pct": LEAGUE_AVG_SWSTR, "career_swstr_pct": None}
        for name in pitcher_names
    }

    current_lookup = _fetch_swstr_lookup_for_window(season, season)
    if not current_lookup:
        log.warning(
            "fetch_swstr: current-season lookup empty for %s - using neutral for all",
            season,
        )
        return fallback

    career_lookup = _fetch_career_swstr_lookup(season)

    result = {}
    for name in pitcher_names:
        key = _norm(name)
        current = current_lookup.get(key, LEAGUE_AVG_SWSTR)
        career = career_lookup.get(key)
        result[name] = {
            "swstr_pct": current,
            "career_swstr_pct": career,
        }
    return result
```

- [ ] **Step 4: Preserve the existing informative logging**

Before returning from `fetch_swstr()`, keep a per-pitcher log line in this shape:

```python
log.info(
    "fetch_swstr: %s -> SwStr%% %.1f%% (career: %s)",
    name,
    current * 100,
    f"{career * 100:.1f}%" if career is not None else "n/a",
)
```

- [ ] **Step 5: Run the focused SwStr tests and make them pass**

Run:

```powershell
C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\.venv\Scripts\python.exe -m pytest tests\test_fetch_statcast.py -q
```

Expected: PASS.

- [ ] **Step 6: Run the existing build-features SwStr tests as a regression check**

Run:

```powershell
C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\.venv\Scripts\python.exe -m pytest tests\test_build_features.py -q
```

Expected: PASS, including `TestCalcSwstrDeltaK9`, `TestCalcLambdaSwstrDelta`, and the `build_pitcher_record` SwStr cases.

- [ ] **Step 7: Commit the SwStr plumbing repair**

```bash
git add pipeline/fetch_statcast.py tests/test_fetch_statcast.py
git commit -m "fix(swstr): rebuild career swstr baselines season-by-season"
```

---

### Task 4: Document The Forward-Only Fix Window

**Files:**
- Modify: `docs/data-caveats.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add a data caveat note for the dead-SwStr window**

Append a new note to `docs/data-caveats.md` in the same style as the existing bug-window entries:

```markdown
### 2026-04-08 -> <deploy-date> — SwStr delta neutral window

During this window, stored picks carried `career_swstr_pct = null`, which
forced `swstr_delta_k9 = 0.0` for every record even when current-season
SwStr% was available. This made the SwStr signal effectively dormant in
decision-time lambda.

Remediation is forward-only:
- do not rewrite `picks_history.json`
- do not regrade historical picks
- do not bump `formula_change_date`

Interpretation:
- dashboard/performance slices across this window understate the influence of
  swing-and-miss form
- post-fix Phase B rebaseline should be read from fresh graded slates only
```

- [ ] **Step 2: Add a CLAUDE.md breadcrumb under API/model notes**

Add a short bullet under the FanGraphs / PyBaseball SwStr section in `CLAUDE.md`:

```markdown
- Career SwStr% baseline is the mean of the three prior seasons fetched
  season-by-season. If `career_swstr_pct` suddenly goes null across the board,
  check `pipeline/fetch_statcast.py` before trusting any Phase B bias slices.
```

- [ ] **Step 3: Commit the docs note**

```bash
git add docs/data-caveats.md CLAUDE.md
git commit -m "docs(swstr): record dead-signal window and repaired fetch contract"
```

---

### Task 5: Rebaseline Phase B Once Fresh Post-Fix Data Exists

**Files:**
- Verify only: `analytics/performance.py`
- Verify only: `analytics/diagnostics/b5_swstr_activation.py`

- [ ] **Step 1: Run the SwStr diagnostic immediately after the code fix**

Run:

```powershell
C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\.venv\Scripts\python.exe analytics\diagnostics\b5_swstr_activation.py
```

Expected immediately after the code fix:
- the live `fetch_swstr()` sample should show at least some pitchers with non-`None` `career_swstr_pct`
- stored picks will still remain all-zero/null in the historical post-4/8 sample, because we are not backfilling

- [ ] **Step 2: Wait for one fresh graded slate under the repaired code**

Do **not** evaluate B1/B2/B4 off the old sample. Wait until at least one full slate has:
- been generated with repaired SwStr fetches
- graded through the normal results pipeline

- [ ] **Step 3: Rerun the analytics report on the refreshed sample**

Run:

```powershell
C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\.venv\Scripts\python.exe analytics\performance.py --since 2026-04-08
```

Expected:
- `swstr_delta_k9 != 0` no longer shows `0.00% FEATURE DEAD`
- feature-contribution means show a non-flat `swstr_delta_k9`
- only after that should the team re-interpret over-side bias / high-lambda tail findings

- [ ] **Step 4: Post the rebaseline findings and stop**

At the end of this plan, report:
- whether `swstr_delta_k9` is alive again
- the first post-fix activation rate
- whether the original B1/B2/B4 concerns still look directionally true

Do **not** auto-start model changes from that output. If the over/tail findings still hold after the SwStr repair, write a separate plan for side-bias / tail-miscalibration follow-up.

---

## Self-Review

**Spec coverage:** This plan covers the dead SwStr activation found in Phase B (`swstr_delta_k9 != 0` at `0.00%`) and the immediate need to rebaseline the analytics once the signal is restored. It intentionally does not include per-side bias terms, bucketed lambda bias, or tail haircuts; those belong in a separate model-change plan after rebaseline.

**Placeholder scan:** No `TODO`/`TBD` placeholders remain. Every task names exact files, commands, and target code.

**Type consistency:** The plan consistently uses the current `fetch_swstr()` return contract: `{pitcher_name: {"swstr_pct": float, "career_swstr_pct": float | None}}`, and keeps `swstr_delta_k9` as the downstream computed field in stored picks.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-27-swstr-signal-repair-and-rebaseline.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
