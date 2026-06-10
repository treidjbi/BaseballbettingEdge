# Workload And No-Vig EV Audit

Generated at: `2026-06-10T19:37:02.733111+00:00`

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, or dashboard source-of-truth.

## Executive Read

- Total source rows: `1718`
- Clean tracked win/loss rows analyzed: `886`
- Useful next decision: compare workload/no-vig warnings against confidence-referee caps, Path B coverage, CLV, and Gate F projection challenger output before drafting any live behavior change.

## Gate Read

- Gate E remains the research-readiness gate for each candidate family.
- Gate F remains the promotion-candidate gate; no bucket from this report can promote without holdout, slices, and a rollback plan.

## No-Vig Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_vig_confirmed_edge` | 700 | 352-348 | -38.85 | -5.5% | 61 | 9 |
| `no_vig_market_disagrees` | 91 | 43-48 | -7.72 | -8.5% | 42 | 7 |
| `no_vig_no_edge` | 52 | 26-26 | -0.46 | -0.9% | 21 | 1 |
| `no_vig_referee_agrees` | 4 | 3-1 | +2.24 | +56.0% | 0 | 0 |
| `no_vig_referee_disagrees` | 17 | 9-8 | +1.92 | +11.3% | 4 | 0 |
| `no_vig_thin_edge` | 22 | 13-9 | +1.64 | +7.5% | 10 | 0 |

## Workload Risk Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `workload_fragile` | 225 | 121-104 | +1.60 | +0.7% | 39 | 4 |
| `workload_stable` | 387 | 196-191 | -18.65 | -4.8% | 58 | 2 |
| `workload_watch` | 274 | 129-145 | -24.18 | -8.8% | 41 | 11 |

## Workload Sensitivity Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `workload_sensitivity_half_k` | 413 | 194-219 | -26.02 | -6.3% | 76 | 9 |
| `workload_sensitivity_one_k` | 300 | 163-137 | -2.79 | -0.9% | 43 | 7 |
| `workload_stable_margin` | 173 | 89-84 | -12.43 | -7.2% | 19 | 1 |

## Path B Coverage Buckets

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `path_a_or_unknown` | 826 | 419-407 | -33.68 | -4.1% | 123 | 16 |
| `path_b_5_8_real_splits` | 39 | 16-23 | -7.41 | -19.0% | 11 | 1 |
| `path_b_9_real_splits` | 21 | 11-10 | -0.14 | -0.7% | 4 | 0 |

## Referee Interaction Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `referee_cap_contradicted_by_no_vig` | 14 | 8-6 | +2.95 | +21.1% | 2 | 0 |
| `referee_cap_supported_by_no_vig_or_workload` | 7 | 4-3 | +1.20 | +17.2% | 2 | 0 |
| `referee_neutral` | 524 | 255-269 | -43.72 | -8.3% | 49 | 6 |
| `uncapped_row_with_shadow_warning` | 341 | 179-162 | -1.67 | -0.5% | 85 | 11 |

## Path B By No-Vig Label

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `path_a_or_unknown | no_vig_confirmed_edge` | 672 | 340-332 | -33.01 | -4.9% | 58 | 8 |
| `path_a_or_unknown | no_vig_market_disagrees` | 80 | 38-42 | -5.95 | -7.4% | 34 | 7 |
| `path_a_or_unknown | no_vig_no_edge` | 50 | 26-24 | +1.54 | +3.1% | 21 | 1 |
| `path_a_or_unknown | no_vig_referee_disagrees` | 2 | 2-0 | +2.10 | +105.1% | 0 | 0 |
| `path_a_or_unknown | no_vig_thin_edge` | 22 | 13-9 | +1.64 | +7.5% | 10 | 0 |
| `path_b_5_8_real_splits | no_vig_confirmed_edge` | 17 | 6-11 | -5.59 | -32.9% | 2 | 1 |
| `path_b_5_8_real_splits | no_vig_market_disagrees` | 9 | 4-5 | -1.54 | -17.1% | 7 | 0 |
| `path_b_5_8_real_splits | no_vig_no_edge` | 2 | 0-2 | -2.00 | -100.0% | 0 | 0 |
| `path_b_5_8_real_splits | no_vig_referee_agrees` | 3 | 3-0 | +3.24 | +108.0% | 0 | 0 |
| `path_b_5_8_real_splits | no_vig_referee_disagrees` | 8 | 3-5 | -1.52 | -19.0% | 2 | 0 |
| `path_b_9_real_splits | no_vig_confirmed_edge` | 11 | 6-5 | -0.25 | -2.2% | 1 | 0 |
| `path_b_9_real_splits | no_vig_market_disagrees` | 2 | 1-1 | -0.23 | -11.6% | 1 | 0 |
| `path_b_9_real_splits | no_vig_referee_agrees` | 1 | 0-1 | -1.00 | -100.0% | 0 | 0 |
| `path_b_9_real_splits | no_vig_referee_disagrees` | 7 | 4-3 | +1.33 | +19.1% | 2 | 0 |

## Path B By Referee Interaction

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `path_a_or_unknown | referee_cap_contradicted_by_no_vig` | 1 | 1-0 | +1.14 | +114.0% | 0 | 0 |
| `path_a_or_unknown | referee_cap_supported_by_no_vig_or_workload` | 1 | 1-0 | +0.96 | +96.2% | 0 | 0 |
| `path_a_or_unknown | referee_neutral` | 503 | 246-257 | -39.49 | -7.8% | 48 | 6 |
| `path_a_or_unknown | uncapped_row_with_shadow_warning` | 321 | 171-150 | +3.71 | +1.2% | 75 | 10 |
| `path_b_5_8_real_splits | referee_cap_contradicted_by_no_vig` | 6 | 3-3 | +0.48 | +8.0% | 0 | 0 |
| `path_b_5_8_real_splits | referee_cap_supported_by_no_vig_or_workload` | 5 | 3-2 | +1.24 | +24.8% | 2 | 0 |
| `path_b_5_8_real_splits | referee_neutral` | 12 | 5-7 | -2.50 | -20.8% | 0 | 0 |
| `path_b_5_8_real_splits | uncapped_row_with_shadow_warning` | 16 | 5-11 | -6.63 | -41.4% | 9 | 1 |
| `path_b_9_real_splits | referee_cap_contradicted_by_no_vig` | 7 | 4-3 | +1.33 | +19.1% | 2 | 0 |
| `path_b_9_real_splits | referee_cap_supported_by_no_vig_or_workload` | 1 | 0-1 | -1.00 | -100.0% | 0 | 0 |
| `path_b_9_real_splits | referee_neutral` | 9 | 4-5 | -1.73 | -19.2% | 1 | 0 |
| `path_b_9_real_splits | uncapped_row_with_shadow_warning` | 4 | 3-1 | +1.25 | +31.3% | 1 | 0 |
