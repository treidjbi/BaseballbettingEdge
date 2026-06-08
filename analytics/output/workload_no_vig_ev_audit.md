# Workload And No-Vig EV Audit

Generated at: `2026-06-08T17:58:30.866237+00:00`

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, or dashboard source-of-truth.

## Executive Read

- Total source rows: `1498`
- Clean tracked win/loss rows analyzed: `771`
- Useful next decision: compare workload/no-vig warnings against confidence-referee caps, Path B coverage, CLV, and Gate F projection challenger output before drafting any live behavior change.

## Gate Read

- Gate E remains the research-readiness gate for each candidate family.
- Gate F remains the promotion-candidate gate; no bucket from this report can promote without holdout, slices, and a rollback plan.

## No-Vig Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_vig_confirmed_edge` | 630 | 328-302 | -12.90 | -2.1% | 57 | 8 |
| `no_vig_market_disagrees` | 73 | 35-38 | -4.61 | -6.3% | 30 | 7 |
| `no_vig_no_edge` | 47 | 23-24 | -1.49 | -3.2% | 19 | 1 |
| `no_vig_thin_edge` | 21 | 13-8 | +2.64 | +12.6% | 9 | 0 |

## Workload Risk Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `workload_fragile` | 200 | 111-89 | +8.79 | +4.4% | 31 | 3 |
| `workload_stable` | 326 | 169-157 | -10.58 | -3.2% | 47 | 2 |
| `workload_watch` | 245 | 119-126 | -14.58 | -5.9% | 37 | 11 |

## Workload Sensitivity Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `workload_sensitivity_half_k` | 350 | 169-181 | -13.16 | -3.8% | 59 | 8 |
| `workload_sensitivity_one_k` | 268 | 148-120 | +1.63 | +0.6% | 37 | 7 |
| `workload_stable_margin` | 153 | 82-71 | -4.83 | -3.2% | 19 | 1 |

## Path B Coverage Buckets

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `path_a_or_unknown` | 771 | 399-372 | -16.37 | -2.1% | 115 | 16 |

## Referee Interaction Labels

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `referee_neutral` | 469 | 238-231 | -20.64 | -4.4% | 46 | 6 |
| `uncapped_row_with_shadow_warning` | 302 | 161-141 | +4.28 | +1.4% | 69 | 10 |

## Path B By No-Vig Label

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `path_a_or_unknown | no_vig_confirmed_edge` | 630 | 328-302 | -12.90 | -2.1% | 57 | 8 |
| `path_a_or_unknown | no_vig_market_disagrees` | 73 | 35-38 | -4.61 | -6.3% | 30 | 7 |
| `path_a_or_unknown | no_vig_no_edge` | 47 | 23-24 | -1.49 | -3.2% | 19 | 1 |
| `path_a_or_unknown | no_vig_thin_edge` | 21 | 13-8 | +2.64 | +12.6% | 9 | 0 |

## Path B By Referee Interaction

| Bucket | Rows | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `path_a_or_unknown | referee_neutral` | 469 | 238-231 | -20.64 | -4.4% | 46 | 6 |
| `path_a_or_unknown | uncapped_row_with_shadow_warning` | 302 | 161-141 | +4.28 | +1.4% | 69 | 10 |
