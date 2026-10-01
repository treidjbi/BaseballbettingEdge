# Workload And No-Vig EV Audit

Generated at: `2026-10-01T14:57:59.700626+00:00`

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, or dashboard source-of-truth.

## Executive Read

- Total source rows: `5488`
- Clean tracked win/loss rows analyzed: `2893`
- Useful next decision: compare workload/no-vig warnings against confidence-referee caps, Path B coverage, CLV, and Gate F projection challenger output before drafting any live behavior change.

## Gate Read

- Gate E remains the research-readiness gate for each candidate family.
- Gate F remains the promotion-candidate gate; no bucket from this report can promote without holdout, slices, and a rollback plan.

## No-Vig Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_vig_confirmed_edge` | 1892 | 994-898 | -92.53 | -4.9% | 164 | 11 |
| `no_vig_market_disagrees` | 187 | 92-95 | -13.54 | -7.2% | 59 | 7 |
| `no_vig_no_edge` | 137 | 68-69 | +0.05 | +0.0% | 30 | 4 |
| `no_vig_referee_agrees` | 10 | 3-7 | -2.76 | -27.6% | 0 | 0 |
| `no_vig_referee_disagrees` | 633 | 263-370 | -82.67 | -13.1% | 68 | 0 |
| `no_vig_thin_edge` | 34 | 22-12 | +4.14 | +12.2% | 17 | 0 |

## Workload Risk Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `workload_fragile` | 831 | 417-414 | -50.06 | -6.0% | 97 | 7 |
| `workload_stable` | 1172 | 596-576 | -50.41 | -4.3% | 144 | 2 |
| `workload_watch` | 890 | 429-461 | -86.85 | -9.8% | 97 | 13 |

## Workload Sensitivity Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `workload_sensitivity_half_k` | 1203 | 562-641 | -89.42 | -7.4% | 157 | 9 |
| `workload_sensitivity_one_k` | 1004 | 523-481 | -46.97 | -4.7% | 113 | 10 |
| `workload_stable_margin` | 686 | 357-329 | -50.92 | -7.4% | 68 | 3 |

## Path B Coverage Buckets

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `path_a_or_unknown` | 850 | 431-419 | -35.40 | -4.2% | 129 | 16 |
| `path_b_1_4_real_splits` | 11 | 6-5 | +0.07 | +0.6% | 1 | 0 |
| `path_b_5_8_real_splits` | 1447 | 719-728 | -95.55 | -6.6% | 166 | 4 |
| `path_b_9_real_splits` | 414 | 200-214 | -38.67 | -9.3% | 42 | 2 |
| `path_b_zero_real_splits` | 171 | 86-85 | -17.76 | -10.4% | 0 | 0 |

## Referee Interaction Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `referee_cap_contradicted_by_no_vig` | 455 | 192-263 | -52.88 | -11.6% | 51 | 0 |
| `referee_cap_supported_by_no_vig_or_workload` | 188 | 74-114 | -32.55 | -17.3% | 17 | 0 |
| `referee_neutral` | 1338 | 698-640 | -74.42 | -5.6% | 119 | 6 |
| `uncapped_row_with_shadow_warning` | 912 | 478-434 | -27.46 | -3.0% | 151 | 16 |

## Path B By No-Vig Label

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `path_a_or_unknown | no_vig_confirmed_edge` | 690 | 349-341 | -34.06 | -4.9% | 61 | 8 |
| `path_a_or_unknown | no_vig_market_disagrees` | 83 | 39-44 | -7.24 | -8.7% | 36 | 7 |
| `path_a_or_unknown | no_vig_no_edge` | 51 | 26-25 | +0.54 | +1.1% | 21 | 1 |
| `path_a_or_unknown | no_vig_referee_disagrees` | 2 | 2-0 | +2.10 | +105.1% | 0 | 0 |
| `path_a_or_unknown | no_vig_thin_edge` | 24 | 15-9 | +3.27 | +13.6% | 11 | 0 |
| `path_b_1_4_real_splits | no_vig_confirmed_edge` | 7 | 6-1 | +4.07 | +58.1% | 1 | 0 |
| `path_b_1_4_real_splits | no_vig_market_disagrees` | 1 | 0-1 | -1.00 | -100.0% | 0 | 0 |
| `path_b_1_4_real_splits | no_vig_referee_disagrees` | 3 | 0-3 | -3.00 | -100.0% | 0 | 0 |
| `path_b_5_8_real_splits | no_vig_confirmed_edge` | 818 | 441-377 | -30.66 | -3.8% | 86 | 3 |
| `path_b_5_8_real_splits | no_vig_market_disagrees` | 85 | 46-39 | -1.61 | -1.9% | 19 | 0 |
| `path_b_5_8_real_splits | no_vig_no_edge` | 61 | 30-31 | -0.04 | -0.1% | 5 | 1 |
| `path_b_5_8_real_splits | no_vig_referee_agrees` | 5 | 3-2 | +2.24 | +44.8% | 0 | 0 |
| `path_b_5_8_real_splits | no_vig_referee_disagrees` | 470 | 193-277 | -67.35 | -14.3% | 51 | 0 |
| `path_b_5_8_real_splits | no_vig_thin_edge` | 8 | 6-2 | +1.87 | +23.4% | 5 | 0 |
| `path_b_9_real_splits | no_vig_confirmed_edge` | 242 | 125-117 | -22.79 | -9.4% | 16 | 0 |
| `path_b_9_real_splits | no_vig_market_disagrees` | 17 | 7-10 | -2.69 | -15.8% | 4 | 0 |
| `path_b_9_real_splits | no_vig_no_edge` | 24 | 11-13 | -0.44 | -1.8% | 4 | 2 |
| `path_b_9_real_splits | no_vig_referee_agrees` | 5 | 0-5 | -5.00 | -100.0% | 0 | 0 |
| `path_b_9_real_splits | no_vig_referee_disagrees` | 124 | 56-68 | -6.75 | -5.4% | 17 | 0 |
| `path_b_9_real_splits | no_vig_thin_edge` | 2 | 1-1 | -1.00 | -50.0% | 1 | 0 |
| `path_b_zero_real_splits | no_vig_confirmed_edge` | 135 | 73-62 | -9.08 | -6.7% | 0 | 0 |
| `path_b_zero_real_splits | no_vig_market_disagrees` | 1 | 0-1 | -1.00 | -100.0% | 0 | 0 |
| `path_b_zero_real_splits | no_vig_no_edge` | 1 | 1-0 | +0.00 | +0.0% | 0 | 0 |
| `path_b_zero_real_splits | no_vig_referee_disagrees` | 34 | 12-22 | -7.68 | -22.6% | 0 | 0 |

## Path B By Referee Interaction

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `path_a_or_unknown | referee_cap_contradicted_by_no_vig` | 1 | 1-0 | +1.14 | +114.0% | 0 | 0 |
| `path_a_or_unknown | referee_cap_supported_by_no_vig_or_workload` | 1 | 1-0 | +0.96 | +96.2% | 0 | 0 |
| `path_a_or_unknown | referee_neutral` | 520 | 255-265 | -40.26 | -7.7% | 52 | 6 |
| `path_a_or_unknown | uncapped_row_with_shadow_warning` | 328 | 174-154 | +2.77 | +0.8% | 77 | 10 |
| `path_b_1_4_real_splits | referee_cap_contradicted_by_no_vig` | 3 | 0-3 | -3.00 | -100.0% | 0 | 0 |
| `path_b_1_4_real_splits | referee_neutral` | 5 | 4-1 | +2.38 | +47.7% | 1 | 0 |
| `path_b_1_4_real_splits | uncapped_row_with_shadow_warning` | 3 | 2-1 | +0.68 | +22.7% | 0 | 0 |
| `path_b_5_8_real_splits | referee_cap_contradicted_by_no_vig` | 333 | 136-197 | -48.82 | -14.7% | 35 | 0 |
| `path_b_5_8_real_splits | referee_cap_supported_by_no_vig_or_workload` | 142 | 60-82 | -16.29 | -11.5% | 16 | 0 |
| `path_b_5_8_real_splits | referee_neutral` | 555 | 296-259 | -27.98 | -5.0% | 57 | 0 |
| `path_b_5_8_real_splits | uncapped_row_with_shadow_warning` | 417 | 227-190 | -2.46 | -0.6% | 58 | 4 |
| `path_b_9_real_splits | referee_cap_contradicted_by_no_vig` | 95 | 47-48 | +3.47 | +3.6% | 16 | 0 |
| `path_b_9_real_splits | referee_cap_supported_by_no_vig_or_workload` | 34 | 9-25 | -15.22 | -44.8% | 1 | 0 |
| `path_b_9_real_splits | referee_neutral` | 171 | 91-80 | -11.58 | -6.8% | 9 | 0 |
| `path_b_9_real_splits | uncapped_row_with_shadow_warning` | 114 | 53-61 | -15.35 | -13.5% | 16 | 2 |
| `path_b_zero_real_splits | referee_cap_contradicted_by_no_vig` | 23 | 8-15 | -5.68 | -24.7% | 0 | 0 |
| `path_b_zero_real_splits | referee_cap_supported_by_no_vig_or_workload` | 11 | 4-7 | -2.00 | -18.2% | 0 | 0 |
| `path_b_zero_real_splits | referee_neutral` | 87 | 52-35 | +3.02 | +3.5% | 0 | 0 |
| `path_b_zero_real_splits | uncapped_row_with_shadow_warning` | 50 | 22-28 | -13.10 | -26.2% | 0 | 0 |
