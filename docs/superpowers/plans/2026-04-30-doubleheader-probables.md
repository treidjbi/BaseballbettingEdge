# Doubleheader Probables Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop valid doubleheader game-one starters from being dropped as `starter_mismatch` when the same team also has a later probable starter on the same slate.

**Architecture:** Keep the existing pitcher-card output and odds flow intact. Change MLB probable tracking from a single team-name value to a helper-compatible collection of probable names when a team appears more than once, then teach run-time mismatch and dropped-prop diagnostics to match against any probable for that team.

**Tech Stack:** Python 3.11, pytest, MLB Stats API schedule payloads, existing `fetch_stats` and `run_pipeline` helpers.

---

## File Plan

Modify:

- `pipeline/fetch_stats.py`: preserve all probable starters per team when multiple games exist on one slate.
- `pipeline/run_pipeline.py`: normalize probable values whether they are a string, `None`, or a list of names.
- `tests/test_fetch_stats.py`: add a doubleheader schedule regression test.
- `tests/test_run_pipeline.py`: add mismatch and dropped-prop tests for multi-probable teams.

Do not modify:

- Dashboard files.
- Model thresholds, calibration, `formula_change_date`, or staking rules.
- TheRundown book priority/filtering.

---

## Task 1: Add Regression Coverage

**Files:**

- Modify: `tests/test_fetch_stats.py`
- Modify: `tests/test_run_pipeline.py`

- [x] **Step 1: Add a failing fetch_stats doubleheader test**

Add a mocked schedule with Houston/Baltimore appearing twice on the same date:

```python
def test_fetch_stats_preserves_multiple_probables_for_doubleheader_teams():
    # Expected: Houston and Baltimore each expose both game-one and game-two probables.
    stats, probables = fetch_stats(
        "2026-04-30",
        ["Peter Lambert", "Lance McCullers Jr.", "Chris Bassitt", "Brandon Young"],
    )
    assert set(probables["Houston Astros"]) == {"Peter Lambert", "Lance McCullers Jr."}
    assert set(probables["Baltimore Orioles"]) == {"Chris Bassitt", "Brandon Young"}
```

- [x] **Step 2: Add failing run_pipeline helper tests**

Add tests showing:

```python
run_pipeline._restamp_starter_mismatch(
    [{"pitcher": "Peter Lambert", "team": "Houston Astros", "starter_mismatch": False}],
    {"Houston Astros": ["Peter Lambert", "Lance McCullers Jr."]},
)
# Expected: not a mismatch.
```

and dropped-prop classification treats every probable in the list as a real probable.

- [x] **Step 3: Run the focused tests and confirm RED**

Run:

```bash
python -m pytest tests/test_fetch_stats.py::test_fetch_stats_preserves_multiple_probables_for_doubleheader_teams tests/test_run_pipeline.py::test_restamp_starter_mismatch_accepts_any_doubleheader_probable tests/test_run_pipeline.py::test_classify_dropped_props_flattens_doubleheader_probables -q
```

Expected before implementation: at least one test fails because `probables_by_team` overwrites earlier same-team probables or helpers cannot flatten list values.

---

## Task 2: Implement Doubleheader-Safe Probable Matching

**Files:**

- Modify: `pipeline/fetch_stats.py`
- Modify: `pipeline/run_pipeline.py`

- [x] **Step 1: Preserve all scheduled probables per team**

In `fetch_stats`, replace single-value overwrite with append semantics:

```python
if team_name:
    probable_name = (pitcher or {}).get("fullName")
    if team_name not in probables_by_team:
        probables_by_team[team_name] = []
    if probable_name and probable_name not in probables_by_team[team_name]:
        probables_by_team[team_name].append(probable_name)
```

Use an empty list when MLB has not posted a probable for that scheduled team.

- [x] **Step 2: Add a small probable flattener in run_pipeline**

Add a helper that returns normalized probable names from strings, lists, tuples, sets, or `None`.

- [x] **Step 3: Use that helper in `_classify_dropped_props` and `_restamp_starter_mismatch`**

Expected behavior:

- no probable data: keep the existing conservative behavior.
- one probable: same behavior as before.
- multiple probables for one team: mark mismatch only when the record pitcher matches none of them.

- [x] **Step 4: Run focused tests and confirm GREEN**

Run:

```bash
python -m pytest tests/test_fetch_stats.py tests/test_run_pipeline.py -q
```

Expected: focused test files pass.

---

## Task 3: Verify With Live Apr 30 Shape

**Files:**

- Read-only command against local code and live MLB API.

- [x] **Step 1: Run a small fetch_stats probe for the Apr 30 HOU/BAL doubleheader**

Run:

```bash
python - <<'PY'
import sys
sys.path.insert(0, "pipeline")
from fetch_stats import fetch_stats
stats, probables = fetch_stats("2026-04-30", ["Peter Lambert", "Chris Bassitt", "Lance McCullers Jr.", "Brandon Young"])
print(probables.get("Houston Astros"))
print(probables.get("Baltimore Orioles"))
print(sorted(stats))
PY
```

Expected: Houston and Baltimore each list both probable starters, and all available named starters resolve in `stats`.

- [x] **Step 2: Run the project test subset that protects this surface**

Run:

```bash
python -m pytest tests/test_fetch_stats.py tests/test_run_pipeline.py -q
```

Expected: no regressions in stats fetching, dropped-prop classification, or starter-mismatch handling.

---

## Self-Review

- Spec coverage: this fixes the concrete Apr 30 doubleheader overwrite without changing UI or betting thresholds.
- Placeholder scan: no deferred implementation placeholders.
- Type consistency: callers must use the new probable flattener before comparing values, so string/list/empty-list values are handled in one place.
