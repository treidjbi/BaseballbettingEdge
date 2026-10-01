# Market Anchored K Shadow Rebuild

Generated at: `2026-10-01T14:57:59.733667+00:00`

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, dashboard artifacts, or source-of-truth behavior.

## Executive Read

- Total source rows: `5488`
- Clean official-close side rows analyzed: `5488`
- Clean tracked rows analyzed: `2893`
- Official-close market count: `2744`
- Current FIRE tracked selector: `797` rows, `408-389`, `-43.34`, `-5.4%` ROI.
- Market-anchor core tracked selector: `1628` rows, `877-751`, `-74.41`, `-4.6%` ROI.
- Market-anchor strict tracked selector: `468` rows, `276-192`, `+7.95`, `+1.7%` ROI.

## Rebuild Shape

- Start from no-vig market probability and K line to infer a market-implied Poisson projection.
- Add only a shrink-adjusted share of the current baseball projection back into that market prior.
- Reduce the baseball share when quality, workload, high-line, or market-fade context says the raw model should be trusted less.
- Score selection with runtime-safe labels first; use results, CLV, and actual opportunity only for validation and explanation.

## Projection Scoreboard

| Projection | Rows | Mean Error | MAE | RMSE | Side W-L | Side Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `current_model` | 2744 | -0.040 | 1.876 | 2.349 | 1428-1303 | +52.3% |
| `market_implied` | 2744 | -0.042 | 1.744 | 2.176 | 1543-1201 | +56.2% |
| `market_anchor` | 2744 | -0.042 | 1.755 | 2.189 | 1517-1227 | +55.3% |

## Tracked-Market Projection Scoreboard

| Projection | Rows | Mean Error | MAE | RMSE | Side W-L | Side Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `current_model` | 2744 | -0.040 | 1.876 | 2.349 | 1428-1303 | +52.3% |
| `market_implied` | 2744 | -0.042 | 1.744 | 2.176 | 1543-1201 | +56.2% |
| `market_anchor` | 2744 | -0.042 | 1.755 | 2.189 | 1517-1227 | +55.3% |

## Tracked-Pick Selector Scoreboard

| Selector | Rows | W-L | PnL | ROI |
| --- | ---: | ---: | ---: | ---: |
| `current_action_fire` | 797 | 408-389 | -43.34 | -5.4% |
| `market_price_only_favorite` | 1426 | 799-627 | -52.74 | -3.7% |
| `market_anchor_side_agrees` | 1767 | 957-810 | -75.17 | -4.2% |
| `market_anchor_core` | 1628 | 877-751 | -74.41 | -4.6% |
| `market_anchor_strict` | 468 | 276-192 | +7.95 | +1.7% |

## Theoretical Official-Close Selector Scoreboard

| Selector | Rows | W-L | PnL | ROI |
| --- | ---: | ---: | ---: | ---: |
| `current_action_fire` | 797 | 408-389 | -43.34 | -5.4% |
| `market_price_only_favorite` | 2657 | 1505-1152 | -76.00 | -2.9% |
| `market_anchor_side_agrees` | 2744 | 1517-1227 | -96.63 | -3.5% |
| `market_anchor_core` | 1649 | 890-759 | -72.47 | -4.4% |
| `market_anchor_strict` | 473 | 278-195 | +6.56 | +1.4% |

## Market-Anchor Core Slice Risks

- `market_anchor_core` `model_market_relationship=model_agrees_with_favorite`: 1228 rows, -56.15, -4.6% ROI.
- `market_anchor_core` `price_sign=minus`: 1447 rows, -55.08, -3.8% ROI.
- `market_anchor_core` `quality_gate_level=capped`: 780 rows, -52.24, -6.7% ROI.
- `market_anchor_core` `side=under`: 771 rows, -39.33, -5.1% ROI.
- `market_anchor_core` `line_bucket=4.5`: 573 rows, -38.68, -6.8% ROI.
- `market_anchor_core` `side=over`: 857 rows, -35.08, -4.1% ROI.
- `market_anchor_core` `line_bucket=5.5`: 418 rows, -24.66, -5.9% ROI.
- `market_anchor_core` `model_market_relationship=model_fades_favorite`: 343 rows, -21.75, -6.3% ROI.

## Market-Anchor Strict Slice Risks

- `market_anchor_strict` `quality_gate_level=unknown`: 9 rows, -3.91, -43.4% ROI.
- `market_anchor_strict` `line_bucket=4.5`: 157 rows, -2.06, -1.3% ROI.
- `market_anchor_strict` `line_bucket=6.5`: 62 rows, -1.11, -1.8% ROI.
- `market_anchor_strict` `side=under`: 284 rows, -0.57, -0.2% ROI.

## Read Rule

- This is a shadow rebuild diagnostic, not a production model proposal.
- Prefer the market-anchored shape only if it beats current FIRE selection and does not simply select a tiny, one-slate, one-side bucket.
- The theoretical official-close table can suggest direction, but tracked-pick performance is the cleaner first decision read.
- A live v2 selector would still need a separate plan, a feature flag, rollback path, and side/K-line/price/provider/CLV/workload/Path B/rolling-window survival.
