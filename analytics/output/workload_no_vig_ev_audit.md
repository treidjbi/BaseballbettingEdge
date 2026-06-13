# Workload And No-Vig EV Audit

Generated at: `2026-06-13T17:38:36.000985+00:00`

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, or dashboard source-of-truth.

## Executive Read

- Total source rows: `1840`
- Clean tracked win/loss rows analyzed: `956`
- Useful next decision: compare workload/no-vig warnings against confidence-referee caps, Path B coverage, CLV, and Gate F projection challenger output before drafting any live behavior change.

## Gate Read

- Gate E remains the research-readiness gate for each candidate family.
- Gate F remains the promotion-candidate gate; no bucket from this report can promote without holdout, slices, and a rollback plan.

## No-Vig Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_vig_confirmed_edge` | 732 | 367-365 | -44.13 | -6.0% | 67 | 9 |
| `no_vig_market_disagrees` | 100 | 46-54 | -11.30 | -11.3% | 46 | 7 |
| `no_vig_no_edge` | 57 | 29-28 | -0.23 | -0.4% | 21 | 2 |
| `no_vig_referee_agrees` | 5 | 3-2 | +1.24 | +24.8% | 0 | 0 |
| `no_vig_referee_disagrees` | 39 | 19-20 | +1.39 | +3.6% | 8 | 0 |
| `no_vig_thin_edge` | 23 | 13-10 | +0.64 | +2.8% | 11 | 0 |

## Workload Risk Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `workload_fragile` | 239 | 128-111 | +0.67 | +0.3% | 42 | 4 |
| `workload_stable` | 427 | 211-216 | -29.56 | -6.9% | 67 | 2 |
| `workload_watch` | 290 | 138-152 | -23.50 | -8.1% | 44 | 12 |

## Workload Sensitivity Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `workload_sensitivity_half_k` | 443 | 206-237 | -32.39 | -7.3% | 84 | 9 |
| `workload_sensitivity_one_k` | 322 | 175-147 | -2.88 | -0.9% | 47 | 8 |
| `workload_stable_margin` | 191 | 96-95 | -17.12 | -9.0% | 22 | 1 |

## Path B Coverage Buckets

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `path_a_or_unknown` | 826 | 419-407 | -33.68 | -4.1% | 123 | 16 |
| `path_b_5_8_real_splits` | 86 | 38-48 | -12.69 | -14.8% | 23 | 1 |
| `path_b_9_real_splits` | 44 | 20-24 | -6.01 | -13.7% | 7 | 1 |

## Referee Interaction Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `referee_cap_contradicted_by_no_vig` | 32 | 16-16 | +2.16 | +6.8% | 6 | 0 |
| `referee_cap_supported_by_no_vig_or_workload` | 12 | 6-6 | +0.47 | +3.9% | 2 | 0 |
| `referee_neutral` | 548 | 266-282 | -48.01 | -8.8% | 54 | 6 |
| `uncapped_row_with_shadow_warning` | 364 | 189-175 | -7.01 | -1.9% | 91 | 12 |

## Path B By No-Vig Label

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `path_a_or_unknown | no_vig_confirmed_edge` | 672 | 340-332 | -33.01 | -4.9% | 58 | 8 |
| `path_a_or_unknown | no_vig_market_disagrees` | 80 | 38-42 | -5.95 | -7.4% | 34 | 7 |
| `path_a_or_unknown | no_vig_no_edge` | 50 | 26-24 | +1.54 | +3.1% | 21 | 1 |
| `path_a_or_unknown | no_vig_referee_disagrees` | 2 | 2-0 | +2.10 | +105.1% | 0 | 0 |
| `path_a_or_unknown | no_vig_thin_edge` | 22 | 13-9 | +1.64 | +7.5% | 10 | 0 |
| `path_b_5_8_real_splits | no_vig_confirmed_edge` | 39 | 17-22 | -8.00 | -20.5% | 7 | 1 |
| `path_b_5_8_real_splits | no_vig_market_disagrees` | 17 | 7-10 | -4.11 | -24.2% | 11 | 0 |
| `path_b_5_8_real_splits | no_vig_no_edge` | 5 | 1-4 | -3.09 | -61.8% | 0 | 0 |
| `path_b_5_8_real_splits | no_vig_referee_agrees` | 3 | 3-0 | +3.24 | +108.0% | 0 | 0 |
| `path_b_5_8_real_splits | no_vig_referee_disagrees` | 21 | 10-11 | +0.27 | +1.3% | 4 | 0 |
| `path_b_5_8_real_splits | no_vig_thin_edge` | 1 | 0-1 | -1.00 | -100.0% | 1 | 0 |
| `path_b_9_real_splits | no_vig_confirmed_edge` | 21 | 10-11 | -3.12 | -14.9% | 2 | 0 |
| `path_b_9_real_splits | no_vig_market_disagrees` | 3 | 1-2 | -1.23 | -41.0% | 1 | 0 |
| `path_b_9_real_splits | no_vig_no_edge` | 2 | 2-0 | +1.32 | +66.2% | 0 | 1 |
| `path_b_9_real_splits | no_vig_referee_agrees` | 2 | 0-2 | -2.00 | -100.0% | 0 | 0 |
| `path_b_9_real_splits | no_vig_referee_disagrees` | 16 | 7-9 | -0.99 | -6.2% | 4 | 0 |

## Path B By Referee Interaction

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `path_a_or_unknown | referee_cap_contradicted_by_no_vig` | 1 | 1-0 | +1.14 | +114.0% | 0 | 0 |
| `path_a_or_unknown | referee_cap_supported_by_no_vig_or_workload` | 1 | 1-0 | +0.96 | +96.2% | 0 | 0 |
| `path_a_or_unknown | referee_neutral` | 503 | 246-257 | -39.49 | -7.8% | 48 | 6 |
| `path_a_or_unknown | uncapped_row_with_shadow_warning` | 321 | 171-150 | +3.71 | +1.2% | 75 | 10 |
| `path_b_5_8_real_splits | referee_cap_contradicted_by_no_vig` | 17 | 9-8 | +2.33 | +13.7% | 2 | 0 |
| `path_b_5_8_real_splits | referee_cap_supported_by_no_vig_or_workload` | 7 | 4-3 | +1.18 | +16.9% | 2 | 0 |
| `path_b_5_8_real_splits | referee_neutral` | 29 | 13-16 | -5.28 | -18.2% | 5 | 0 |
| `path_b_5_8_real_splits | uncapped_row_with_shadow_warning` | 33 | 12-21 | -10.93 | -33.1% | 14 | 1 |
| `path_b_9_real_splits | referee_cap_contradicted_by_no_vig` | 14 | 6-8 | -1.31 | -9.3% | 4 | 0 |
| `path_b_9_real_splits | referee_cap_supported_by_no_vig_or_workload` | 4 | 1-3 | -1.68 | -42.0% | 0 | 0 |
| `path_b_9_real_splits | referee_neutral` | 16 | 7-9 | -3.24 | -20.2% | 1 | 0 |
| `path_b_9_real_splits | uncapped_row_with_shadow_warning` | 10 | 6-4 | +0.21 | +2.1% | 2 | 1 |
