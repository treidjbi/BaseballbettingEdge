# Next Season Candidate Model Lab

Research-only. This report does not change live lambda, thresholds, staking, providers, notifications, locks, retention, calibration, or dashboard source-of-truth.

Walk-forward split: train rows before `2026-06-01`; test rows on/after `2026-06-01`.
PnL preference: `pick_history_pnl`, then `theoretical_pnl`, then legacy `pnl`.

| Candidate | Status | Rows | W-L | PnL | Train Rows | Train PnL | Test Rows | Test PnL |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `model_agrees_with_favorite` | `watch` | 2704 | 1352-1352 | -156.69 | 674 | -37.63 | 2030 | -119.06 |
| `clean_quality_only` | `watch` | 2788 | 1394-1394 | -180.36 | 682 | -46.65 | 2106 | -133.71 |
