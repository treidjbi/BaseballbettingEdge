# 2026-04-28 Pipeline Stability And Data Integrity Hotfix

## Goal

Stabilize the live pipeline after the grading-boundary bump so the app remains usable, today's slate stays trustworthy, and noisy upstream data cannot silently poison picks or calibration-facing artifacts.

## Hotfix Scope

1. Fix v2 results/grading empty-state crash.
2. Repair preview odds auth path and add a targeted health diagnostic.
3. Restore live batter aggregate K-rate fetch after FanGraphs legacy-path degradation.
4. Add connection-health observability to `today.json`.
5. Fence non-modelable odds props before downstream feature work.
6. Prevent adjacent UTC schedule blocks from corrupting the ET-target slate in `fetch_stats`.
7. Suppress pregame `starter_mismatch` cards before output/seeding as a final integrity fence.

## Implemented

- `dashboard/v2-app.jsx`
- `dashboard/v2-app.js`
- `pipeline/fetch_odds.py`
- `pipeline/fetch_batter_stats.py`
- `pipeline/fetch_stats.py`
- `pipeline/run_pipeline.py`
- `.github/workflows/pipeline.yml`
- `analytics/diagnostics/d_preview_health.py`
- `analytics/diagnostics/d_connection_health.py`
- `tests/test_dashboard_perf_payload.py`
- `tests/test_pipeline_workflow_contract.py`
- `tests/test_connection_health.py`
- `tests/test_fetch_odds.py`
- `tests/test_fetch_batter_stats.py`
- `tests/test_fetch_stats.py`
- `tests/test_run_pipeline.py`

## Validation

- `python -m pytest tests -q` -> passing
- Live local `pipeline/run_pipeline.py 2026-04-28` -> healthy output path

Current live-state read after the final local run:

- `today.json` ET-today pitchers: `25`
- `starter_mismatch=true`: `0`
- SwStr fields: populated and non-neutral on the live slate
- Rest/workload fields: populated on live pitcher rows
- Expected morning degradations still visible:
  - `fetch_umpires returned 0 entries for 14 scheduled games`
  - `fetch_lineups: confirmed 0/25 opposing lineups (25 still projected)`

## Remaining Risk

The upstream odds feed is still noisy at the raw ingestion layer (`props_seen` remains far above `stats_resolved`), but the new integrity fences prevent that junk from flowing through to final picks. If Actions/runtime pressure remains high after this hotfix, the next follow-up should target earlier raw-feed pruning rather than another grading/calibration boundary bump.
