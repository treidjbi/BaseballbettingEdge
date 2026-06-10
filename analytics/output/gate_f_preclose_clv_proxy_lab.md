# Gate F Pre-Close CLV Proxy Lab

Generated at: `2026-06-10T19:04:13.892450+00:00`

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, or dashboard source-of-truth.

## Executive Read

- Total source rows: `1662`
- Clean tracked win/loss rows analyzed: `854`
- Positive CLV target rows: `147`
- Strong pre-close proxy rows: `291`, positive CLV capture `93` (`+32.0%`), PnL `+9.05`.
- Ready-for-plan proxy buckets: `none`
- Watch-more proxy buckets: `strong_preclose_clv_proxy`

## Boundary

- CLV is the validation target, not a live selector.
- The proxy score uses pre-close fields only; changing CLV outcome fields does not change proxy membership.
- Current Gate C rows have limited rich live-market coverage, so this lab should improve as market-agreement and book-count fields fill in.

## Proxy Scoreboard

| Proxy bucket | Readiness | Rows | W-L | PnL | ROI | Positive CLV | Source FIRE | Retained FIRE | Capped to LEAN | Recent PnL | Slice risks |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `strong_preclose_clv_proxy` | `watch_more` | 291 | 164-127 | +9.05 | +3.1% | 93 (+32.0%) | 113 | 39 | 74 | -8.55 | 12 |
| `medium_preclose_clv_proxy` | `not_ready` | 126 | 63-63 | -8.30 | -6.6% | 17 (+13.5%) | 97 | 22 | 75 | -6.34 | 14 |
| `weak_preclose_clv_proxy` | `not_ready` | 437 | 205-232 | -37.02 | -8.5% | 37 (+8.5%) | 428 | 73 | 355 | -5.66 | 23 |

## Runtime Field Availability

| Field | Non-null rows | Coverage |
| --- | ---: | ---: |
| `toward_pick_count` | 0 | 0.0% |
| `away_from_pick_count` | 0 | 0.0% |
| `better_now_count` | 0 | 0.0% |
| `worse_now_count` | 0 | 0.0% |
| `book_count` | 0 | 0.0% |
| `broad_confirmation` | 854 | 100.0% |
| `best_is_off_market` | 0 | 0.0% |
| `reversal_book_count` | 0 | 0.0% |
| `volatile_book_count` | 0 | 0.0% |
| `provider` | 0 | 0.0% |
| `market_agreement_label` | 0 | 0.0% |

## Strong Proxy Slice Risks

- `model_market_relationship=model_fades_favorite`: 107 rows, -9.93, -9.3%.
- `price_sign=plus`: 62 rows, -9.46, -15.3%.
- `line_bucket=2.5-3.5`: 57 rows, -8.19, -14.4%.
- `quality_gate_level=capped`: 105 rows, -6.90, -6.6%.
- `bet_timing_window=pre_5`: 17 rows, -6.53, -38.4%.
- `quality_gate_level=unknown`: 10 rows, -4.47, -44.7%.
- `side_price_movement=unchanged`: 159 rows, -3.27, -2.1%.
- `no_vig_label=no_vig_thin_edge`: 52 rows, -3.17, -6.1%.

## Recommendation

- Do not promote a FIRE re-entry rule from CLV alone.
- Use `strong_preclose_clv_proxy` as the first live-safe candidate only if it holds profit, positive CLV capture, and slice stability after more graded rows and richer market fields.
- Keep `PROFIT_RESCUE_REFEREE_MODE=enforce` until a proxy bucket reaches `ready_for_plan` and Tyler approves a separate canary.
