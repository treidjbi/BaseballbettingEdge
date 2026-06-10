# Gate F Pre-Close CLV Proxy Lab

Generated at: `2026-06-10T19:37:03.320929+00:00`

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, or dashboard source-of-truth.

## Executive Read

- Total source rows: `1718`
- Clean tracked win/loss rows analyzed: `886`
- Positive CLV target rows: `155`
- Strong pre-close proxy rows: `299`, positive CLV capture `97` (`+32.4%`), PnL `+7.18`.
- Ready-for-plan proxy buckets: `none`
- Watch-more proxy buckets: `strong_preclose_clv_proxy`

## Boundary

- CLV is the validation target, not a live selector.
- The proxy score uses pre-close fields only; changing CLV outcome fields does not change proxy membership.
- Current Gate C rows have limited rich live-market coverage, so this lab should improve as market-agreement and book-count fields fill in.

## Proxy Scoreboard

| Proxy bucket | Readiness | Rows | W-L | PnL | ROI | Positive CLV | Source FIRE | Retained FIRE | Capped to LEAN | Recent PnL | Slice risks |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `strong_preclose_clv_proxy` | `watch_more` | 299 | 166-133 | +7.18 | +2.4% | 97 (+32.4%) | 121 | 41 | 80 | -6.30 | 13 |
| `medium_preclose_clv_proxy` | `not_ready` | 130 | 67-63 | -5.36 | -4.1% | 15 (+11.5%) | 91 | 20 | 71 | -8.86 | 13 |
| `weak_preclose_clv_proxy` | `not_ready` | 457 | 213-244 | -43.08 | -9.4% | 43 (+9.4%) | 444 | 76 | 368 | -12.01 | 22 |

## Runtime Field Availability

| Field | Non-null rows | Coverage |
| --- | ---: | ---: |
| `toward_pick_count` | 192 | 21.7% |
| `away_from_pick_count` | 192 | 21.7% |
| `better_now_count` | 192 | 21.7% |
| `worse_now_count` | 192 | 21.7% |
| `book_count` | 192 | 21.7% |
| `broad_confirmation` | 886 | 100.0% |
| `best_is_off_market` | 0 | 0.0% |
| `reversal_book_count` | 192 | 21.7% |
| `volatile_book_count` | 192 | 21.7% |
| `provider` | 192 | 21.7% |
| `market_agreement_label` | 192 | 21.7% |

## Strong Proxy Slice Risks

- `line_bucket=2.5-3.5`: 56 rows, -10.77, -19.2%.
- `price_sign=plus`: 62 rows, -9.30, -15.0%.
- `model_market_relationship=model_fades_favorite`: 114 rows, -5.88, -5.2%.
- `no_vig_label=no_vig_thin_edge`: 50 rows, -5.47, -10.9%.
- `bet_timing_window=pre_5`: 18 rows, -5.23, -29.1%.
- `quality_gate_level=capped`: 103 rows, -4.66, -4.5%.
- `quality_gate_level=unknown`: 10 rows, -4.47, -44.7%.
- `side_price_movement=unchanged`: 156 rows, -3.20, -2.1%.

## Recommendation

- Do not promote a FIRE re-entry rule from CLV alone.
- Use `strong_preclose_clv_proxy` as the first live-safe candidate only if it holds profit, positive CLV capture, and slice stability after more graded rows and richer market fields.
- Keep `PROFIT_RESCUE_REFEREE_MODE=enforce` until a proxy bucket reaches `ready_for_plan` and Tyler approves a separate canary.
