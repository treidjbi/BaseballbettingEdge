# Profit Rescue Audit

Generated at: `2026-06-10T16:01:20.488547+00:00`
Anchor date: `2026-06-08`

downgrade-only: this report evaluates the `PROFIT_RESCUE_REFEREE_MODE=shadow|enforce` canary policy and does not change lambda, calibration, global EV thresholds, staking, provider order, notifications, locks, retention, or dashboard source-of-truth.

## Executive Read

- Total source rows: `1662`
- Clean tracked win/loss rows analyzed: `854`
- Proposed policy: cap remaining FIRE 2u to FIRE 1u, cap remaining FIRE unders to LEAN, and cap remaining model-fades-market-favorite FIRE rows to LEAN.
- Read this as a risk-off production canary candidate, not proof that any LEAN should become FIRE.

## FIRE Exposure Windows

| Window | Rows | Current FIRE | Current FIRE PnL | Proposed FIRE | Proposed FIRE PnL | Downgraded to LEAN | FIRE PnL Delta |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `clean_regime` | 854 | 536 | -34.07 | 118 | +8.35 | 418 | +42.42 |
| `last_7_days` | 122 | 64 | -15.93 | 11 | -1.84 | 53 | +14.09 |
| `last_14_days` | 251 | 131 | -16.73 | 27 | -0.68 | 104 | +16.05 |
| `last_21_days` | 398 | 235 | -20.00 | 52 | -1.34 | 183 | +18.66 |
| `last_30_days` | 585 | 359 | -24.78 | 81 | +2.68 | 278 | +27.46 |

## Action Buckets

| Action | Rows | W-L | PnL | ROI |
| --- | ---: | ---: | ---: | ---: |
| `downgrade_fire_to_lean` | 418 | 194-224 | -42.42 | -10.2% |
| `downgrade_fire_two_to_fire_one` | 17 | 7-10 | -4.39 | -25.8% |
| `keep_fire` | 101 | 64-37 | +12.75 | +12.6% |
| `keep_non_fire` | 318 | 167-151 | -2.19 | -0.7% |
