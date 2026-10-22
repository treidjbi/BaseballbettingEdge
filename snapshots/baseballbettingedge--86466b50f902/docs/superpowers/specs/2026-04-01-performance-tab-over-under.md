# Performance Tab: Over/Under Split & Early-Data Display

**Date:** 2026-04-01
**Status:** Approved

## Overview

Update the Performance tab to show results split by verdict tier *and* side (over/under), always displaying all 6 rows from day one regardless of sample size. Remove the n≥10 gate that currently hides data during the early season.

## Goals

- Give the user a daily eyeball view of how each verdict/side combo is performing
- Keep the table structure stable (no rows appear or disappear as picks accumulate)
- Show `—` for any cell where there are 0 closed picks in that bucket

## Data Structure

`dashboard/data/performance.json` changes `by_verdict` (keyed dict) to `rows` (fixed-order array):

```json
{
  "generated_at": "2026-04-01T20:00:00Z",
  "total_picks": 9,
  "last_calibrated": null,
  "calibration_sample": null,
  "rows": [
    { "verdict": "FIRE 2u", "side": "over",  "picks": 2, "wins": 1, "losses": 1, "pushes": 0, "win_pct": 0.50, "roi": -4.55, "avg_ev": 0.082 },
    { "verdict": "FIRE 2u", "side": "under", "picks": 0, "wins": 0, "losses": 0, "pushes": 0, "win_pct": null, "roi": null,  "avg_ev": null  },
    { "verdict": "FIRE 1u", "side": "over",  "picks": 3, "wins": 2, "losses": 1, "pushes": 0, "win_pct": 0.67, "roi": 29.09, "avg_ev": 0.041 },
    { "verdict": "FIRE 1u", "side": "under", "picks": 1, "wins": 0, "losses": 1, "pushes": 0, "win_pct": 0.00, "roi": -100.0,"avg_ev": 0.012 },
    { "verdict": "LEAN",    "side": "over",  "picks": 2, "wins": 1, "losses": 1, "pushes": 0, "win_pct": 0.50, "roi": -4.55, "avg_ev": 0.018 },
    { "verdict": "LEAN",    "side": "under", "picks": 1, "wins": 1, "losses": 0, "pushes": 0, "win_pct": 1.00, "roi": 90.91, "avg_ev": 0.011 }
  ],
  "lambda_accuracy": { "avg_predicted": null, "avg_actual": null, "bias": null },
  "params": null
}
```

*ROI formula: `round((total_pnl / picks) * 100, 2)` where `total_pnl` is the sum of stored `pnl` column values (actual pnl per pick varies by odds — do not hardcode a fixed per-win constant). The example uses 0.909u per win at -110 for illustration only: `(2×0.909 - 1×1.0) / 3 × 100 = 29.09`.*

Row order is fixed: FIRE 2u over → FIRE 2u under → FIRE 1u over → FIRE 1u under → LEAN over → LEAN under.

**Field definitions (with explicit changes from current code):**
- `picks` — count of closed picks (result IN `win`, `loss`, `push`) in this bucket. Void/cancelled excluded.
- `wins` / `losses` / `pushes` — counts by result type.
- `win_pct` — **formula changes**: was `round(wins / picks, 3)`. Now `round(wins / (wins + losses), 3)`, excluding pushes from denominator. **Null** when `picks == 0` OR `wins + losses == 0` (push-only). Previously returned `0.0` for empty buckets; now `null`.
- `roi` — **formula changes**: was `round(total_pnl, 2)` (raw total PnL in units). Now `round((total_pnl / picks) * 100, 2)` (average PnL per pick as a percentage). **Null** when `picks == 0`. For push-only buckets: `_calc_pnl` returns `0.0` for push results, so `total_pnl = 0.0` and `roi = 0.0` (non-null).
- `avg_ev` — mean `adj_ev`, `round(..., 4)` (rounding unchanged). **Null** when `picks == 0`. `adj_ev` is `NOT NULL` in the picks schema (set at seed time), so push-only buckets always yield a non-null `avg_ev`. Previously returned `0.0` for empty buckets; now `null`.

`total_picks` — unchanged: `len(closed)` where `closed` is the list returned by `_load_closed_picks()`, which filters to `result IN ('win','loss','push')`. Each bucket also aggregates only win/loss/push rows, so `total_picks` always equals the sum of all bucket `picks` values. (Void/cancelled rows are excluded by the same SQL filter, not just by seeding rules.)

## Components

### `pipeline/calibrate.py`

- `_load_closed_picks()` (no arguments — opens its own connection): add `side` to the SELECT clause (currently missing). The column is named `side` in the picks table (confirmed in `init_db()` schema). Filter remains `result IN ('win','loss','push')` — void and cancelled rows are excluded.
- `build_performance(closed, current_params=None)`:
  - Replace grouping by `verdict` with grouping by `(verdict, side)`
  - Emit 6 rows in the fixed order above using an ordered list of `(verdict, side)` pairs as the scaffold
  - `win_pct`: `null` when `picks == 0` OR `wins + losses == 0`; otherwise `round(wins / (wins + losses), 3)`
  - `roi`: `null` when `picks == 0`; otherwise `round((total_pnl / picks) * 100, 2)`
  - `avg_ev`: `null` when `picks == 0`; otherwise `round(sum_ev / picks, 4)`
  - Output key changes from `by_verdict` (dict) to `rows` (list)
  - `total_picks`, `last_calibrated`, `calibration_sample`, `lambda_accuracy`, `params` fields unchanged

### `dashboard/index.html`

- `loadPerformance()`: existing fetch-failure handling is acceptable — keep "Performance data not yet available." message as-is. No change needed.
- `renderPerformance(data)`:
  - Replace the current guard `if (!data || data.total_picks < 10)` with `if (!data || !Array.isArray(data.rows))`. This handles both fetch failure and stale JSON (pre-migration files that still have `by_verdict` instead of `rows`). Both cases show the existing "Performance data not yet available." message.
  - Add a **Side** column header after **Verdict**
  - Iterate over `data.rows` (array) instead of `Object.entries(data.by_verdict)`
  - Render `—` for any `null` numeric field (`win_pct`, `roi`, `avg_ev`)
  - Each row renders `row.verdict` in the Verdict cell and `row.side` title-cased ("Over" / "Under") in the Side cell

### `tests/test_calibrate.py`

- `_insert_closed_pick` helper: add a `side` parameter with default `"over"` (must match the current hardcoded value to preserve existing test assertions — do not change the default) so new tests can also insert under picks
- Update all existing `build_performance` assertions: replace `result["by_verdict"]` dict lookups with `result["rows"]` array lookups (find a row by matching `verdict` + `side` fields)
- `test_build_performance_is_pure` in `TestPhase2Calibration` currently asserts `result["by_verdict"] == {}` — update to assert `len(result["rows"]) == 6` and all rows have `picks == 0`
- Add tests:
  - All 6 rows always present in the fixed order: FIRE 2u/over, FIRE 2u/under, FIRE 1u/over, FIRE 1u/under, LEAN/over, LEAN/under
  - Zero-pick rows have `null` for `win_pct`, `roi`, `avg_ev`
  - Over and under picks for the same verdict aggregate independently (an over win does not affect the under row)
  - Push-only bucket: `win_pct` is `null`, `roi` is `0.0`, `avg_ev` is non-null

## What Does Not Change

- Calibration logic (`_calibrate_phase1`, `_calibrate_phase2`) — untouched
- The `lambda_accuracy` and `params` sections of performance.json — untouched
- The calibration status note in the dashboard — untouched
- `fetch_results.py` and `results.db` schema — untouched
- `loadPerformance()` fetch-failure message — untouched

## Out of Scope

- Line shopping / per-book odds display (separate feature)
- Any changes to the model or pipeline scheduling
