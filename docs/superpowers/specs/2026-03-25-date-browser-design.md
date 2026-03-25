# Date Browser Design

## Overview

Add a date browser to BaseballBettingEdge so users can view historical K-prop lines and track how lines moved day to day. The pipeline archives each day's data as a dated JSON file; the dashboard loads an index of available dates and lets the user select any past date to view.

---

## Goals

- Browse any past date's K-prop lines from the dashboard
- See how lines and juice moved across days for the same pitcher
- No backend required — fully static, pipeline-driven

---

## Architecture

### Pipeline

Two additions to `run_pipeline.py`:

1. **Dated archive file** — after writing `dashboard/data/processed/today.json`, also write `dashboard/data/processed/YYYY-MM-DD.json` (e.g. `2026-03-27.json`). Identical content, just a permanent dated copy.

2. **Index file** — after writing the dated file, update `dashboard/data/processed/index.json` by prepending the new date to the `dates` array (most recent first). Creates the file if it doesn't exist.

`index.json` schema:
```json
{
  "dates": ["2026-03-27", "2026-03-26", "2026-03-25"]
}
```

Both files are committed to the repo by GitHub Actions alongside `today.json`. Netlify serves them statically from `dashboard/data/processed/` (Netlify publish directory is `dashboard/` per `netlify.toml`).

**GitHub Actions workflow update required:** The `git add` line in `.github/workflows/pipeline.yml` must be updated from `git add data/processed/today.json` to `git add dashboard/data/processed/` so the dated file and `index.json` are staged and committed alongside `today.json`.

**Index.json size cap:** The pipeline caps `index.json` at the most recent 60 dates (≈ 30 calendar days at 2 pipeline runs/day). Older entries are dropped on write. This prevents unbounded growth over a full season (~360 pipeline runs).

### Dashboard

**Boot sequence (updated):**
1. Fetch `data/processed/index.json` to get available dates
2. Default to most recent date in the list
3. Fetch `data/processed/{selected-date}.json` and render

**Date selector UI:**
- Dropdown in the top bar, right of the title, left of the freshness badge
- Options are all dates from `index.json`, formatted as `Mon Mar 27` etc.
- Most recent date is selected by default and labelled `Today` if it matches current calendar date
- Selecting a different date re-fetches that day's file and re-renders all tabs
- Freshness banner logic applies to the selected date's `generated_at`, not the current time (a past date's data is intentionally "old" — no stale warning for past dates)

**Freshness badge for past dates:** Shows `{Month Day} · {time}` (e.g. `Mar 25 · 9:00 AM`) using `toLocaleDateString('en-US', {month:'short', day:'numeric'})`. No stale warning — past dates are intentionally old.

**Date dropdown formatting:** Uses `toLocaleDateString('en-US', {weekday:'short', month:'short', day:'numeric'})` e.g. `Thu Mar 27`. Most recent entry is labelled `Today` if it matches the current calendar date.

**Error states:**
- `index.json` not found → fall back to fetching `today.json` directly (graceful degradation, existing behavior)
- `index.json` found but selected date file not found → show "No data available for this date"
- Both `index.json` and `today.json` missing (fresh repo, pre-first-pipeline-run) → show existing "no data" empty state

---

## File Changes

| File | Change |
|---|---|
| `pipeline/run_pipeline.py` | Write dated file + update index.json after writing today.json |
| `dashboard/data/processed/index.json` | New — maintained by pipeline, committed by Actions |
| `dashboard/index.html` | Updated boot sequence + date selector UI |

No new Python dependencies. No changes to `today.json` schema or any other pipeline module.

---

## Out of Scope

- Comparing two dates side by side
- Charting line movement over time (Option B territory)
- Filtering/searching within a date's results (separate feature)
