# Next Season Candidate Model Lab

Research-only. This report does not change live lambda, thresholds, staking, providers, notifications, locks, retention, calibration, or dashboard source-of-truth.

Walk-forward split: train rows before `2026-06-01`; test rows on/after `2026-06-01`.
PnL preference: `pick_history_pnl`, then `theoretical_pnl`, then legacy `pnl`.

| Candidate | Status | Rows | W-L | PnL | Train Rows | Train PnL | Test Rows | Test PnL |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `model_agrees_with_favorite` | `watch` | 934 | 467-467 | -50.63 | 674 | -37.63 | 260 | -12.99 |
| `clean_quality_only` | `watch` | 1050 | 525-525 | -69.23 | 682 | -46.65 | 368 | -22.58 |
