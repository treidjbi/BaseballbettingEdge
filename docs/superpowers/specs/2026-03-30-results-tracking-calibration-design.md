# Results Tracking & Auto-Calibration Design

**Date:** 2026-03-30
**Status:** Approved

---

## Overview

Add result tracking and automatic model calibration to BaseballBettingEdge. After each game day, the pipeline fetches actual pitcher strikeout totals from the MLB Stats API, records them in a SQLite database, and periodically recalibrates model parameters based on observed outcomes. The dashboard gains a Performance tab showing ROI and accuracy by verdict tier.

---

## Goals

- Track whether each pick (FIRE 2u / FIRE 1u / LEAN) won or lost
- Display cumulative performance stats by verdict tier on the dashboard
- Automatically tune model parameters as the season accumulates results
- Keep everything file-based and compatible with the existing GitHub Actions + Netlify architecture — no new infrastructure

---

## Architecture

### Pipeline Changes

The 9am and 1pm pipeline runs are **untouched**. Two new steps are appended to the **8pm run only**:

```
Existing 8pm pipeline run
    ├─ fetch_odds.py        (unchanged)
    ├─ fetch_stats.py       (unchanged)
    ├─ fetch_umpires.py     (unchanged)
    ├─ fetch_statcast.py    (unchanged)
    ├─ build_features.py    (updated: reads params.json)
    ├─ [NEW] fetch_results.py   ← seeds today's picks, closes yesterday's picks
    └─ [NEW] calibrate.py       ← recalibrates params.json, writes performance.json
```

### New Files

| File | Purpose |
|---|---|
| `pipeline/fetch_results.py` | Seeds picks into DB, fetches MLB box scores, closes out results |
| `pipeline/calibrate.py` | Analyzes results, writes `data/params.json` and `dashboard/data/performance.json` |
| `data/results.db` | SQLite database (committed to git as binary) |
| `data/params.json` | Calibrated model parameters (committed, human-readable) |
| `dashboard/data/performance.json` | Aggregated performance stats for the dashboard |

### Updated Files

| File | Change |
|---|---|
| `pipeline/build_features.py` | Reads `data/params.json`; falls back to hardcoded defaults if missing; `blend_k9()` accepts `weight_season_cap` and `weight_recent` as parameters |
| `pipeline/run_pipeline.py` | Calls `fetch_results` and `calibrate` on 8pm run; passes `run_type` flag |
| `.github/workflows/pipeline.yml` | 8pm job passes `--run-type evening`; `git add` includes `data/results.db`, `data/params.json`, `dashboard/data/performance.json` |
| `dashboard/index.html` | Adds Performance tab |

---

## Database Schema

Single table in `data/results.db`. The `results.db` file is added to `.gitattributes` as binary (`data/results.db binary`) to avoid merge conflicts.

```sql
CREATE TABLE IF NOT EXISTS picks (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  date            TEXT NOT NULL,        -- YYYY-MM-DD ET game date
  pitcher         TEXT NOT NULL,
  team            TEXT NOT NULL,
  side            TEXT NOT NULL,        -- 'over' or 'under'
  k_line          REAL NOT NULL,
  verdict         TEXT NOT NULL,        -- 'FIRE 2u', 'FIRE 1u', 'LEAN', 'PASS'
  ev              REAL NOT NULL,        -- raw EV from model
  adj_ev          REAL NOT NULL,        -- confidence-adjusted EV
  raw_lambda      REAL NOT NULL,        -- pre-bias model prediction (for calibration baseline)
  applied_lambda  REAL NOT NULL,        -- lambda after bias correction (what was used for verdict)
  odds            INTEGER NOT NULL,     -- best available odds at pick time (e.g. -110)
  movement_conf   REAL NOT NULL,        -- movement confidence multiplier
  result          TEXT,                 -- 'win', 'loss', 'push', 'void', 'cancelled', NULL
  actual_ks       INTEGER,              -- NULL until game completes; NULL forever for void/cancelled
  pnl             REAL,                 -- units won/lost (NULL until closed; 0 for void/cancelled)
  fetched_at      TEXT                  -- ISO 8601 UTC timestamp of result fetch
);

-- Unique on date + pitcher + side. Double-headers are out of scope (same pitcher
-- cannot start both games of a double-header; second prop would be a different starter).
CREATE UNIQUE INDEX IF NOT EXISTS idx_picks_date_pitcher_side
  ON picks (date, pitcher, side);
```

### What gets a row

Only the side with a **non-PASS** verdict is inserted per pitcher per day. If a pitcher has FIRE 1u OVER and PASS UNDER, only the OVER row is inserted. If both sides are non-PASS (rare), both rows are inserted. PASS rows are never inserted and never appear in performance stats or calibration.

### P&L Calculation

Standard per-unit calculation based on actual odds at the time of the pick:
- **Win:** `pnl = 100 / abs(odds)` if odds negative, `pnl = odds / 100` if positive
- **Loss:** `pnl = -1.0`
- **Push:** `pnl = 0.0`
- **Void (scratch):** `pnl = 0.0`
- **Cancelled (postponement):** `pnl = 0.0`

---

## fetch_results.py

**Trigger:** 8pm ET pipeline run only (controlled by `run_pipeline.py` via `--run-type evening`).

### Date Handling

`fetch_results.py` derives dates independently from the system wall clock using ET timezone — it does **not** rely on the `date_str` argument passed to the pipeline (which is in UTC and will be one day ahead on the overnight 8pm→1am UTC run):

```python
from datetime import datetime, timedelta
import pytz

ET = pytz.timezone("America/New_York")
now_et = datetime.now(ET)
today_et = now_et.strftime("%Y-%m-%d")
yesterday_et = (now_et - timedelta(days=1)).strftime("%Y-%m-%d")
```

### Step 1 — Seed today's picks

Before fetching results, insert today's non-PASS picks from `dashboard/data/processed/today.json` into the DB:

```python
# For each pitcher in today.json:
#   For side in ['over', 'under']:
#     If ev_over['verdict'] != 'PASS' (for side='over'), insert row
# Use INSERT OR IGNORE to handle re-runs
```

`raw_lambda` = lambda from `today.json` before any bias correction was applied (stored separately in `today.json` output — see build_features.py changes).
`applied_lambda` = lambda after bias correction (the value actually used for the verdict).

### Step 2 — Fetch results for yesterday's picks

Query picks where `date = yesterday_et` and `result IS NULL`.

For each unique team in those rows, call MLB Stats API:
```
GET https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={yesterday_et}&hydrate=boxscore
```

This returns all games for the date with box scores embedded, avoiding one API call per game.

From each game's box score, extract the starting pitcher's `stats.pitching.strikeOuts`.

Match pitchers by name (case-insensitive, strip accents) to open picks rows.

Compute `result` and `pnl` based on `k_line` and `side`, then:
```sql
UPDATE picks SET actual_ks=?, result=?, pnl=?, fetched_at=? WHERE id=?
```

### Step 3 — Close out orphans

After the results fetch, run:
```sql
UPDATE picks
SET result='cancelled', pnl=0.0, fetched_at=?
WHERE result IS NULL
  AND date < ?   -- more than 3 days old in ET
```
Where the threshold date is `yesterday_et - 2 days`. Pitchers who were scratched (name mismatch in box score) get `result='void'` via explicit detection: if the game finished but the pitcher name doesn't match any box score entry, mark as `void` rather than leaving NULL.

**Error handling:**
- Game not yet final → skip (result stays NULL, caught by next run or orphan cleanup)
- API failure → log error, continue with other teams; does not crash pipeline

---

## calibrate.py

**Trigger:** Runs after `fetch_results.py` on 8pm run. Always writes `dashboard/data/performance.json`. Only writes `data/params.json` when calibration thresholds are met.

### Two-Phase Calibration

**Phase 1 — n ≥ 30 closed non-PASS picks** (result IN ('win','loss','push')):
- Calibrate `lambda_bias`
- Calibrate EV thresholds

**Phase 2 — n ≥ 60 closed non-PASS picks**:
- Everything in Phase 1
- Calibrate `ump_scale`
- Calibrate `weight_season_cap` and `weight_recent`

If `n < 30`, `calibrate.py` writes `performance.json` but exits without writing `params.json`. `build_features.py` uses hardcoded defaults.

### Parameters Calibrated

| Parameter | Default | Phase | What it corrects |
|---|---|---|---|
| `lambda_bias` | 0.0 | 1 (n≥30) | Additive offset if model consistently over/under-predicts actual Ks |
| `ev_thresholds.fire2` | 0.06 | 1 (n≥30) | Adjusted based on observed win rate vs implied |
| `ev_thresholds.fire1` | 0.03 | 1 (n≥30) | Same |
| `ev_thresholds.lean` | 0.01 | 1 (n≥30) | Same |
| `ump_scale` | 1.0 | 2 (n≥60) | Scales ump K adjustment if it adds no signal |
| `weight_season_cap` | 0.70 | 2 (n≥60) | Max blend weight for season K/9 |
| `weight_recent` | 0.20 | 2 (n≥60) | Blend weight for recent K/9 |

### Calibration Logic

**Lambda bias** — uses `raw_lambda` (pre-bias column) as baseline so estimates don't drift across cycles:
```python
lambda_bias = mean(actual_ks) - mean(raw_lambda)
# Rolling 60-day window of closed picks (result IN ('win','loss','push'))
```

**Ump scale** — Pearson correlation between `ump_k_adj` and `(actual_ks - raw_lambda)`. If |correlation| < 0.05 and n ≥ 60, decay scale toward 0.5 by 0.05 per cycle. Bounded [0.0, 1.5].

**EV thresholds** — For each tier, compute `observed_win_rate`. Compare to `implied_win_rate` from average odds. If observed > implied by > 3% consistently (rolling 30-day), raise cutoff by 0.005. If observed < implied, lower by 0.005. Bounds: fire2 ∈ [0.04, 0.10], fire1 ∈ [0.02, 0.06], lean ∈ [0.005, 0.03].

**Blend weights** — Simple linear regression of `actual_ks ~ season_k9 + recent_k9 + career_k9` (values stored in picks or derived from today.json archive). Constrained: weights sum to 1.0, each ≥ 0.05, season_cap ≤ 0.85.

### Output — `data/params.json`

```json
{
  "updated_at": "2026-04-15T01:00:00Z",
  "sample_size": 87,
  "ev_thresholds": { "fire2": 0.06, "fire1": 0.03, "lean": 0.01 },
  "weight_season_cap": 0.70,
  "weight_recent": 0.20,
  "ump_scale": 1.0,
  "lambda_bias": 0.0
}
```

### Output — `dashboard/data/performance.json`

Written on every 8pm run (even before n≥30):

```json
{
  "generated_at": "2026-04-15T01:00:00Z",
  "total_picks": 115,
  "last_calibrated": "2026-04-15T01:00:00Z",
  "calibration_sample": 87,
  "by_verdict": {
    "FIRE 2u": { "picks": 12, "wins": 8, "losses": 4, "pushes": 0, "win_pct": 0.667, "roi": 1.82, "avg_ev": 0.082 },
    "FIRE 1u": { "picks": 31, "wins": 18, "losses": 13, "pushes": 0, "win_pct": 0.581, "roi": 0.61, "avg_ev": 0.041 },
    "LEAN":    { "picks": 44, "wins": 22, "losses": 22, "pushes": 0, "win_pct": 0.500, "roi": -0.28, "avg_ev": 0.018 }
  },
  "lambda_accuracy": {
    "avg_predicted": 6.82,
    "avg_actual": 6.71,
    "bias": -0.11
  },
  "params": { "...current params.json contents or null if not yet calibrated..." }
}
```

Note: PASS rows are **excluded** from `by_verdict` — PASS means no bet was placed, so ROI is not meaningful.

---

## build_features.py Changes

### params.json loading

At startup, attempt to load `data/params.json`. If present and valid, use its values; otherwise use module-level defaults:

```python
import json, os

DEFAULTS = {
    "ev_thresholds": {"fire2": 0.06, "fire1": 0.03, "lean": 0.01},
    "weight_season_cap": 0.70,
    "weight_recent": 0.20,
    "ump_scale": 1.0,
    "lambda_bias": 0.0,
}

def load_params():
    path = os.path.join(os.path.dirname(__file__), "../data/params.json")
    try:
        with open(path) as f:
            return {**DEFAULTS, **json.load(f)}
    except (FileNotFoundError, json.JSONDecodeError):
        return DEFAULTS
```

### blend_k9() signature update

`blend_k9()` is updated to accept `weight_season_cap` and `weight_recent` as parameters (with defaults matching current hardcoded values), so calibrated weights from `params.json` are actually applied:

```python
def blend_k9(season_k9, recent_k9, career_k9, ip,
             weight_season_cap=0.70, weight_recent=0.20):
    w_season = min(ip / 60, weight_season_cap)
    w_recent = weight_recent
    w_career = max(0.0, 1.0 - w_season - w_recent)
    return w_season * season_k9 + w_recent * recent_k9 + w_career * career_k9
```

### Lambda output

`build_features.py` now outputs both `raw_lambda` (pre-bias) and the final `lambda` (post-bias) in `today.json`, so `fetch_results.py` can store both in the DB:

```json
{
  "raw_lambda": 7.05,
  "lambda": 7.21
}
```

`ump_k_adj` is multiplied by `params["ump_scale"]` before being added to lambda.
`lambda_bias` is added after all other adjustments, before the Poisson CDF calculation.

---

## run_pipeline.py Changes

```python
def main(date_str=None, run_type="full"):
    # ... existing steps (all runs) ...
    fetch_odds(...)
    fetch_stats(...)
    fetch_umpires(...)
    fetch_statcast(...)
    build_features(...)

    # Evening-only steps
    if run_type == "evening":
        fetch_results()   # no date_str arg — derives ET dates internally
        calibrate()
```

CLI: `python run_pipeline.py --run-type evening`

---

## GitHub Actions Changes (pipeline.yml)

The 8pm cron job (`0 1 * * *`) is updated to:
1. Pass `--run-type evening` to the pipeline script
2. Stage the three new output files in the git commit step:

```yaml
- name: Commit and push data
  run: |
    git add dashboard/data/processed/
    git add dashboard/data/performance.json
    git add data/results.db
    git add data/params.json
    git diff --cached --quiet || git commit -m "chore: pipeline update $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    git push
```

---

## Dashboard: Performance Tab

New third tab in `dashboard/index.html`. Fetches `../data/performance.json` on load (same pattern as `today.json`).

**If `total_picks < 10`:** Show "Not enough data yet — check back after opening week."

**If `total_picks ≥ 10`:**
- Summary table: verdict tier → Picks / Win % / ROI (units) / Avg EV (PASS excluded)
- Lambda accuracy row: "Model predicted X.XX avg Ks, actual was X.XX (bias: ±X.XX)"
- Calibration status: "Last recalibrated YYYY-MM-DD (n=87 picks)" or "Not yet calibrated (n=12, need 30)"

---

## Testing

- `test_fetch_results.py`:
  - Correct result/pnl for win, loss, push, void, cancelled
  - INSERT OR IGNORE deduplication on re-runs
  - Only non-PASS verdicts seeded
  - Orphan cleanup (rows older than 3 days with NULL result → 'cancelled')
  - Scratch detection (game complete but pitcher not in box score → 'void')
  - ET date derivation (confirm yesterday_et is correct regardless of UTC date)
- `test_calibrate.py`:
  - Lambda bias uses `raw_lambda` column (not `applied_lambda`)
  - Phase 1 fires at n≥30, phase 2 at n≥60
  - Threshold adjustment bounds enforced
  - Early exit (no params.json written) when n < 30
  - performance.json always written
  - PASS rows excluded from all aggregations
- `test_build_features.py`:
  - params.json loading with file present, file missing, malformed file
  - `blend_k9()` respects `weight_season_cap` and `weight_recent` arguments
  - `raw_lambda` and `lambda` both present in output JSON
  - `ump_scale` applied to ump_k_adj
  - `lambda_bias` applied after other adjustments

---

## Deployment Notes

- `data/results.db` added to `.gitattributes` as binary: `data/results.db binary`
- No new GitHub secrets needed — MLB Stats API is unauthenticated
- Pipeline runtime impact: `fetch_results.py` adds ~3-5s (single hydrated schedule call), `calibrate.py` adds ~1s
- `dashboard/data/performance.json` served statically by Netlify alongside `today.json`
- Double-headers are out of scope: the same pitcher cannot start both games; second game's prop would use a different starter name, and the unique index prevents collision
