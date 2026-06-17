# Workload And No-Vig EV Audit

Generated at: `2026-06-17T17:54:14.673727+00:00`

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, or dashboard source-of-truth.

## Executive Read

- Total source rows: `2020`
- Clean tracked win/loss rows analyzed: `1050`
- Useful next decision: compare workload/no-vig warnings against confidence-referee caps, Path B coverage, CLV, and Gate F projection challenger output before drafting any live behavior change.

## Gate Read

- Gate E remains the research-readiness gate for each candidate family.
- Gate F remains the promotion-candidate gate; no bucket from this report can promote without holdout, slices, and a rollback plan.

## No-Vig Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_vig_confirmed_edge` | 777 | 390-387 | -49.35 | -6.3% | 72 | 9 |
| `no_vig_market_disagrees` | 107 | 50-57 | -10.84 | -10.1% | 51 | 7 |
| `no_vig_no_edge` | 63 | 32-31 | -0.08 | -0.1% | 24 | 2 |
| `no_vig_referee_agrees` | 8 | 3-5 | -1.76 | -22.0% | 0 | 0 |
| `no_vig_referee_disagrees` | 69 | 29-40 | -7.00 | -10.2% | 14 | 0 |
| `no_vig_thin_edge` | 26 | 16-10 | +2.82 | +10.8% | 13 | 0 |

## Workload Risk Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `workload_fragile` | 262 | 137-125 | -5.99 | -2.3% | 45 | 4 |
| `workload_stable` | 471 | 231-240 | -36.28 | -7.7% | 78 | 2 |
| `workload_watch` | 317 | 152-165 | -23.94 | -7.5% | 51 | 12 |

## Workload Sensitivity Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `workload_sensitivity_half_k` | 493 | 231-262 | -34.81 | -7.1% | 94 | 9 |
| `workload_sensitivity_one_k` | 349 | 185-164 | -10.86 | -3.1% | 52 | 8 |
| `workload_stable_margin` | 208 | 104-104 | -20.53 | -9.9% | 28 | 1 |

## Path B Coverage Buckets

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `path_a_or_unknown` | 826 | 419-407 | -33.68 | -4.1% | 123 | 16 |
| `path_b_5_8_real_splits` | 146 | 64-82 | -23.48 | -16.1% | 39 | 1 |
| `path_b_9_real_splits` | 78 | 37-41 | -9.04 | -11.6% | 12 | 1 |

## Referee Interaction Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `referee_cap_contradicted_by_no_vig` | 51 | 24-27 | +0.49 | +1.0% | 12 | 0 |
| `referee_cap_supported_by_no_vig_or_workload` | 26 | 8-18 | -9.26 | -35.6% | 2 | 0 |
| `referee_neutral` | 585 | 285-300 | -52.10 | -8.9% | 58 | 6 |
| `uncapped_row_with_shadow_warning` | 388 | 203-185 | -5.34 | -1.4% | 102 | 12 |

## Path B By No-Vig Label

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `path_a_or_unknown | no_vig_confirmed_edge` | 672 | 340-332 | -33.01 | -4.9% | 58 | 8 |
| `path_a_or_unknown | no_vig_market_disagrees` | 80 | 38-42 | -5.95 | -7.4% | 34 | 7 |
| `path_a_or_unknown | no_vig_no_edge` | 50 | 26-24 | +1.54 | +3.1% | 21 | 1 |
| `path_a_or_unknown | no_vig_referee_disagrees` | 2 | 2-0 | +2.10 | +105.1% | 0 | 0 |
| `path_a_or_unknown | no_vig_thin_edge` | 22 | 13-9 | +1.64 | +7.5% | 10 | 0 |
| `path_b_5_8_real_splits | no_vig_confirmed_edge` | 65 | 29-36 | -13.00 | -20.0% | 11 | 1 |
| `path_b_5_8_real_splits | no_vig_market_disagrees` | 23 | 10-13 | -4.28 | -18.6% | 15 | 0 |
| `path_b_5_8_real_splits | no_vig_no_edge` | 9 | 4-5 | -0.94 | -10.4% | 2 | 0 |
| `path_b_5_8_real_splits | no_vig_referee_agrees` | 4 | 3-1 | +2.24 | +56.0% | 0 | 0 |
| `path_b_5_8_real_splits | no_vig_referee_disagrees` | 41 | 15-26 | -8.69 | -21.2% | 8 | 0 |
| `path_b_5_8_real_splits | no_vig_thin_edge` | 4 | 3-1 | +1.18 | +29.4% | 3 | 0 |
| `path_b_9_real_splits | no_vig_confirmed_edge` | 40 | 21-19 | -3.34 | -8.3% | 3 | 0 |
| `path_b_9_real_splits | no_vig_market_disagrees` | 4 | 2-2 | -0.61 | -15.3% | 2 | 0 |
| `path_b_9_real_splits | no_vig_no_edge` | 4 | 2-2 | -0.68 | -16.9% | 1 | 1 |
| `path_b_9_real_splits | no_vig_referee_agrees` | 4 | 0-4 | -4.00 | -100.0% | 0 | 0 |
| `path_b_9_real_splits | no_vig_referee_disagrees` | 26 | 12-14 | -0.42 | -1.6% | 6 | 0 |

## Path B By Referee Interaction

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `path_a_or_unknown | referee_cap_contradicted_by_no_vig` | 1 | 1-0 | +1.14 | +114.0% | 0 | 0 |
| `path_a_or_unknown | referee_cap_supported_by_no_vig_or_workload` | 1 | 1-0 | +0.96 | +96.2% | 0 | 0 |
| `path_a_or_unknown | referee_neutral` | 503 | 246-257 | -39.49 | -7.8% | 48 | 6 |
| `path_a_or_unknown | uncapped_row_with_shadow_warning` | 321 | 171-150 | +3.71 | +1.2% | 75 | 10 |
| `path_b_5_8_real_splits | referee_cap_contradicted_by_no_vig` | 32 | 13-19 | -3.81 | -11.9% | 6 | 0 |
| `path_b_5_8_real_splits | referee_cap_supported_by_no_vig_or_workload` | 13 | 5-8 | -2.64 | -20.3% | 2 | 0 |
| `path_b_5_8_real_splits | referee_neutral` | 49 | 23-26 | -7.86 | -16.0% | 9 | 0 |
| `path_b_5_8_real_splits | uncapped_row_with_shadow_warning` | 52 | 23-29 | -9.18 | -17.6% | 22 | 1 |
| `path_b_9_real_splits | referee_cap_contradicted_by_no_vig` | 18 | 10-8 | +3.16 | +17.6% | 6 | 0 |
| `path_b_9_real_splits | referee_cap_supported_by_no_vig_or_workload` | 12 | 2-10 | -7.58 | -63.2% | 0 | 0 |
| `path_b_9_real_splits | referee_neutral` | 33 | 16-17 | -4.75 | -14.4% | 1 | 0 |
| `path_b_9_real_splits | uncapped_row_with_shadow_warning` | 15 | 9-6 | +0.13 | +0.9% | 5 | 1 |
