# Workload And No-Vig EV Audit

Generated at: `2026-06-10T03:35:19.828555+00:00`

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, or dashboard source-of-truth.

## Executive Read

- Total source rows: `1662`
- Clean tracked win/loss rows analyzed: `854`
- Useful next decision: compare workload/no-vig warnings against confidence-referee caps, Path B coverage, CLV, and Gate F projection challenger output before drafting any live behavior change.

## Gate Read

- Gate E remains the research-readiness gate for each candidate family.
- Gate F remains the promotion-candidate gate; no bucket from this report can promote without holdout, slices, and a rollback plan.

## No-Vig Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_vig_confirmed_edge` | 685 | 345-340 | -36.93 | -5.4% | 60 | 8 |
| `no_vig_market_disagrees` | 83 | 40-43 | -5.20 | -6.3% | 37 | 7 |
| `no_vig_no_edge` | 50 | 26-24 | +1.54 | +3.1% | 21 | 1 |
| `no_vig_referee_agrees` | 3 | 2-1 | +1.08 | +36.0% | 0 | 0 |
| `no_vig_referee_disagrees` | 11 | 6-5 | +1.62 | +14.8% | 3 | 0 |
| `no_vig_thin_edge` | 22 | 13-9 | +1.64 | +7.5% | 10 | 0 |

## Workload Risk Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `workload_fragile` | 218 | 119-99 | +4.86 | +2.2% | 36 | 3 |
| `workload_stable` | 370 | 187-183 | -19.27 | -5.2% | 55 | 2 |
| `workload_watch` | 266 | 126-140 | -21.83 | -8.2% | 40 | 11 |

## Workload Sensitivity Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `workload_sensitivity_half_k` | 395 | 186-209 | -23.92 | -6.1% | 71 | 8 |
| `workload_sensitivity_one_k` | 292 | 160-132 | -0.47 | -0.2% | 41 | 7 |
| `workload_stable_margin` | 167 | 86-81 | -11.86 | -7.1% | 19 | 1 |

## Path B Coverage Buckets

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `path_a_or_unknown` | 826 | 419-407 | -33.68 | -4.1% | 123 | 16 |
| `path_b_5_8_real_splits` | 16 | 6-10 | -4.02 | -25.1% | 4 | 0 |
| `path_b_9_real_splits` | 12 | 7-5 | +1.45 | +12.1% | 4 | 0 |

## Referee Interaction Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `referee_cap_contradicted_by_no_vig` | 9 | 5-4 | +1.66 | +18.5% | 2 | 0 |
| `referee_cap_supported_by_no_vig_or_workload` | 5 | 3-2 | +1.04 | +20.8% | 1 | 0 |
| `referee_neutral` | 514 | 250-264 | -43.06 | -8.4% | 49 | 6 |
| `uncapped_row_with_shadow_warning` | 326 | 174-152 | +4.11 | +1.3% | 79 | 10 |

## Path B By No-Vig Label

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `path_a_or_unknown | no_vig_confirmed_edge` | 672 | 340-332 | -33.01 | -4.9% | 58 | 8 |
| `path_a_or_unknown | no_vig_market_disagrees` | 80 | 38-42 | -5.95 | -7.4% | 34 | 7 |
| `path_a_or_unknown | no_vig_no_edge` | 50 | 26-24 | +1.54 | +3.1% | 21 | 1 |
| `path_a_or_unknown | no_vig_referee_disagrees` | 2 | 2-0 | +2.10 | +105.1% | 0 | 0 |
| `path_a_or_unknown | no_vig_thin_edge` | 22 | 13-9 | +1.64 | +7.5% | 10 | 0 |
| `path_b_5_8_real_splits | no_vig_confirmed_edge` | 8 | 2-6 | -4.22 | -52.7% | 1 | 0 |
| `path_b_5_8_real_splits | no_vig_market_disagrees` | 2 | 1-1 | -0.02 | -1.0% | 2 | 0 |
| `path_b_5_8_real_splits | no_vig_referee_agrees` | 2 | 2-0 | +2.08 | +104.0% | 0 | 0 |
| `path_b_5_8_real_splits | no_vig_referee_disagrees` | 4 | 1-3 | -1.86 | -46.5% | 1 | 0 |
| `path_b_9_real_splits | no_vig_confirmed_edge` | 5 | 3-2 | +0.30 | +6.0% | 1 | 0 |
| `path_b_9_real_splits | no_vig_market_disagrees` | 1 | 1-0 | +0.77 | +76.9% | 1 | 0 |
| `path_b_9_real_splits | no_vig_referee_agrees` | 1 | 0-1 | -1.00 | -100.0% | 0 | 0 |
| `path_b_9_real_splits | no_vig_referee_disagrees` | 5 | 3-2 | +1.38 | +27.6% | 2 | 0 |

## Path B By Referee Interaction

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `path_a_or_unknown | referee_cap_contradicted_by_no_vig` | 1 | 1-0 | +1.14 | +114.0% | 0 | 0 |
| `path_a_or_unknown | referee_cap_supported_by_no_vig_or_workload` | 1 | 1-0 | +0.96 | +96.2% | 0 | 0 |
| `path_a_or_unknown | referee_neutral` | 503 | 246-257 | -39.49 | -7.8% | 48 | 6 |
| `path_a_or_unknown | uncapped_row_with_shadow_warning` | 321 | 171-150 | +3.71 | +1.2% | 75 | 10 |
| `path_b_5_8_real_splits | referee_cap_contradicted_by_no_vig` | 3 | 1-2 | -0.86 | -28.7% | 0 | 0 |
| `path_b_5_8_real_splits | referee_cap_supported_by_no_vig_or_workload` | 3 | 2-1 | +1.08 | +36.0% | 1 | 0 |
| `path_b_5_8_real_splits | referee_neutral` | 7 | 2-5 | -3.22 | -46.0% | 0 | 0 |
| `path_b_5_8_real_splits | uncapped_row_with_shadow_warning` | 3 | 1-2 | -1.02 | -34.0% | 3 | 0 |
| `path_b_9_real_splits | referee_cap_contradicted_by_no_vig` | 5 | 3-2 | +1.38 | +27.6% | 2 | 0 |
| `path_b_9_real_splits | referee_cap_supported_by_no_vig_or_workload` | 1 | 0-1 | -1.00 | -100.0% | 0 | 0 |
| `path_b_9_real_splits | referee_neutral` | 4 | 2-2 | -0.35 | -8.7% | 1 | 0 |
| `path_b_9_real_splits | uncapped_row_with_shadow_warning` | 2 | 2-0 | +1.42 | +70.9% | 1 | 0 |
