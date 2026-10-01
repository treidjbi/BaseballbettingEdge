# Profit Rescue Audit

Generated at: `2026-10-01T14:59:54.020934+00:00`
Anchor date: `2026-09-27`

downgrade-only: this report evaluates the `PROFIT_RESCUE_REFEREE_MODE=shadow|enforce` canary policy and does not change lambda, calibration, global EV thresholds, staking, provider order, notifications, locks, retention, or dashboard source-of-truth.

## Executive Read

- Total source rows: `5488`
- Clean tracked win/loss rows analyzed: `2893`
- Proposed policy: cap remaining FIRE 2u to FIRE 1u, cap remaining FIRE unders to LEAN, and cap remaining model-fades-market-favorite FIRE rows to LEAN.
- Read this as a risk-off production canary candidate, not proof that any LEAN should become FIRE.

## FIRE Exposure Windows

| Window | Rows | Current FIRE | Current FIRE PnL | Proposed FIRE | Proposed FIRE PnL | Downgraded to LEAN | FIRE PnL Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `clean_regime` | 2893 | 797 | -43.49 | 358 | +5.19 | 439 | +48.68 |
| `last_7_days` | 123 | 18 | -3.65 | 17 | -4.27 | 1 | -0.62 |
| `last_14_days` | 250 | 33 | +0.79 | 32 | +0.17 | 1 | -0.62 |
| `last_21_days` | 372 | 54 | +4.21 | 53 | +3.59 | 1 | -0.62 |
| `last_30_days` | 531 | 77 | +0.24 | 76 | -0.38 | 1 | -0.62 |

## Action Buckets

| Action | Rows | W-L | PnL | ROI |
| --- | ---: | ---: | ---: | ---: |
| `downgrade_fire_to_lean` | 439 | 201-238 | -48.66 | -11.1% |
| `downgrade_fire_two_to_fire_one` | 18 | 8-10 | -3.73 | -20.7% |
| `keep_fire` | 340 | 199-141 | +8.92 | +2.6% |
| `keep_non_fire` | 2096 | 1034-1062 | -144.23 | -6.9% |
