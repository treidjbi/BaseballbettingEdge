# Gate F Pre-Close CLV Proxy Lab

Generated at: `2026-06-10T23:42:37.935238+00:00`

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, or dashboard source-of-truth.

## Executive Read

- Total source rows: `1718`
- Clean tracked win/loss rows analyzed: `886`
- Positive CLV target rows: `155`
- Strong pre-close proxy rows: `294`, positive CLV capture `92` (`+31.3%`), PnL `+3.54`.
- Ready-for-plan proxy buckets: `none`
- Watch-more proxy buckets: `strong_preclose_clv_proxy`

## Boundary

- CLV is the validation target, not a live selector.
- The proxy score uses pre-close fields only; changing CLV outcome fields does not change proxy membership.
- Current Gate C rows have limited rich live-market coverage, so this lab should improve as market-agreement and book-count fields fill in.

## Proxy Scoreboard

| Proxy bucket | Readiness | Rows | W-L | PnL | ROI | Positive CLV | Source FIRE | Retained FIRE | Capped to LEAN | Recent PnL | Slice risks |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `strong_preclose_clv_proxy` | `watch_more` | 294 | 162-132 | +3.54 | +1.2% | 92 (+31.3%) | 121 | 41 | 80 | -12.33 | 13 |
| `medium_preclose_clv_proxy` | `not_ready` | 135 | 70-65 | -3.73 | -2.8% | 20 (+14.8%) | 94 | 20 | 74 | -4.08 | 11 |
| `weak_preclose_clv_proxy` | `not_ready` | 457 | 214-243 | -41.06 | -9.0% | 43 (+9.4%) | 441 | 76 | 365 | -10.75 | 23 |

## Runtime Field Availability

| Field | Non-null rows | Coverage |
| --- | ---: | ---: |
| `toward_pick_count` | 192 | 21.7% |
| `away_from_pick_count` | 192 | 21.7% |
| `better_now_count` | 192 | 21.7% |
| `worse_now_count` | 192 | 21.7% |
| `book_count` | 278 | 31.4% |
| `broad_confirmation` | 886 | 100.0% |
| `best_is_off_market` | 220 | 24.8% |
| `reversal_book_count` | 192 | 21.7% |
| `volatile_book_count` | 192 | 21.7% |
| `provider` | 192 | 21.7% |
| `market_agreement_label` | 192 | 21.7% |

## Strong Proxy Slice Risks

- `price_sign=plus`: 57 rows, -10.70, -18.8%.
- `line_bucket=2.5-3.5`: 56 rows, -9.25, -16.5%.
- `quality_gate_level=capped`: 103 rows, -6.43, -6.2%.
- `no_vig_label=no_vig_thin_edge`: 47 rows, -6.35, -13.5%.
- `bet_timing_window=pre_5`: 18 rows, -5.23, -29.1%.
- `quality_gate_level=unknown`: 10 rows, -4.47, -44.7%.
- `side_price_movement=unchanged`: 153 rows, -4.36, -2.9%.
- `bet_timing_window=pre_30`: 214 rows, -4.17, -1.9%.

## Recommendation

- Do not promote a FIRE re-entry rule from CLV alone.
- Use `strong_preclose_clv_proxy` as the first live-safe candidate only if it holds profit, positive CLV capture, and slice stability after more graded rows and richer market fields.
- Keep `PROFIT_RESCUE_REFEREE_MODE=enforce` until a proxy bucket reaches `ready_for_plan` and Tyler approves a separate canary.
