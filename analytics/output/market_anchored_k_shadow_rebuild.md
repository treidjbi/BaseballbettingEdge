# Market Anchored K Shadow Rebuild

Generated at: `2026-06-17T17:54:15.301538+00:00`

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, dashboard artifacts, or source-of-truth behavior.

## Executive Read

- Total source rows: `2020`
- Clean official-close side rows analyzed: `2020`
- Clean tracked rows analyzed: `1050`
- Official-close market count: `1010`
- Current FIRE tracked selector: `557` rows, `275-282`, `-37.67`, `-6.8%` ROI.
- Market-anchor core tracked selector: `528` rows, `288-240`, `-14.55`, `-2.8%` ROI.
- Market-anchor strict tracked selector: `164` rows, `97-67`, `+3.16`, `+1.9%` ROI.

## Rebuild Shape

- Start from no-vig market probability and K line to infer a market-implied Poisson projection.
- Add only a shrink-adjusted share of the current baseball projection back into that market prior.
- Reduce the baseball share when quality, workload, high-line, or market-fade context says the raw model should be trusted less.
- Score selection with runtime-safe labels first; use results, CLV, and actual opportunity only for validation and explanation.

## Projection Scoreboard

| Projection | Rows | Mean Error | MAE | RMSE | Side W-L | Side Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `current_model` | 1010 | -0.153 | 1.829 | 2.289 | 539-465 | +53.7% |
| `market_implied` | 1010 | -0.077 | 1.719 | 2.152 | 578-432 | +57.2% |
| `market_anchor` | 1010 | -0.095 | 1.730 | 2.164 | 572-438 | +56.6% |

## Tracked-Market Projection Scoreboard

| Projection | Rows | Mean Error | MAE | RMSE | Side W-L | Side Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `current_model` | 1010 | -0.153 | 1.829 | 2.289 | 539-465 | +53.7% |
| `market_implied` | 1010 | -0.077 | 1.719 | 2.152 | 578-432 | +57.2% |
| `market_anchor` | 1010 | -0.095 | 1.730 | 2.164 | 572-438 | +56.6% |

## Tracked-Pick Selector Scoreboard

| Selector | Rows | W-L | PnL | ROI |
| --- | ---: | ---: | ---: | ---: |
| `current_action_fire` | 557 | 275-282 | -37.67 | -6.8% |
| `market_price_only_favorite` | 492 | 278-214 | -10.29 | -2.1% |
| `market_anchor_side_agrees` | 597 | 332-265 | -6.29 | -1.1% |
| `market_anchor_core` | 528 | 288-240 | -14.55 | -2.8% |
| `market_anchor_strict` | 164 | 97-67 | +3.16 | +1.9% |

## Theoretical Official-Close Selector Scoreboard

| Selector | Rows | W-L | PnL | ROI |
| --- | ---: | ---: | ---: | ---: |
| `current_action_fire` | 557 | 275-282 | -37.67 | -6.8% |
| `market_price_only_favorite` | 975 | 555-420 | -21.84 | -2.2% |
| `market_anchor_side_agrees` | 1010 | 572-438 | -9.30 | -0.9% |
| `market_anchor_core` | 546 | 298-248 | -14.58 | -2.7% |
| `market_anchor_strict` | 169 | 99-70 | +1.77 | +1.1% |

## Market-Anchor Core Slice Risks

- `market_anchor_core` `side=under`: 229 rows, -17.58, -7.7% ROI.
- `market_anchor_core` `line_bucket=5.5`: 146 rows, -15.94, -10.9% ROI.
- `market_anchor_core` `model_market_relationship=model_agrees_with_favorite`: 391 rows, -13.43, -3.4% ROI.
- `market_anchor_core` `price_sign=minus`: 469 rows, -10.64, -2.3% ROI.
- `market_anchor_core` `quality_gate_level=capped`: 235 rows, -10.02, -4.3% ROI.
- `market_anchor_core` `quality_gate_level=unknown`: 14 rows, -5.19, -37.1% ROI.
- `market_anchor_core` `price_sign=plus`: 59 rows, -3.91, -6.6% ROI.
- `market_anchor_core` `model_market_relationship=unknown`: 22 rows, -3.13, -14.2% ROI.

## Market-Anchor Strict Slice Risks

- `market_anchor_strict` `quality_gate_level=unknown`: 9 rows, -3.91, -43.4% ROI.
- `market_anchor_strict` `side=under`: 96 rows, -1.85, -1.9% ROI.
- `market_anchor_strict` `line_bucket=2.5-3.5`: 19 rows, -1.55, -8.2% ROI.
- `market_anchor_strict` `line_bucket=6.5`: 18 rows, -0.55, -3.0% ROI.

## Read Rule

- This is a shadow rebuild diagnostic, not a production model proposal.
- Prefer the market-anchored shape only if it beats current FIRE selection and does not simply select a tiny, one-slate, one-side bucket.
- The theoretical official-close table can suggest direction, but tracked-pick performance is the cleaner first decision read.
- A live v2 selector would still need a separate plan, a feature flag, rollback path, and side/K-line/price/provider/CLV/workload/Path B/rolling-window survival.
