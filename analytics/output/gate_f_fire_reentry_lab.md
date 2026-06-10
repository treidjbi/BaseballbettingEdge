# Gate F FIRE Re-Entry Selection Lab

Generated at: `2026-06-10T17:24:37.063492+00:00`

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, or dashboard source-of-truth.

## Executive Read

- Total source rows: `1662`
- Clean tracked win/loss rows analyzed: `854`
- Historical FIRE-like rows analyzed: `638`
- Profit-rescue shadow retention: `134` retained FIRE rows and `504` capped-to-LEAN rows (`21.0%` retained).
- This lab exists to prevent a permanent zero-FIRE product by finding evidence-backed re-entry candidates.
- Ready-for-plan candidates: `none`
- Watch-more candidates: `moderate_edge_quality_reentry, retained_fire_control`
- Process anchors, not runtime selectors: `clv_supported_reentry`

## Gate Read

- Gate F is now measuring FIRE re-entry volume and decision value, not just FIRE avoidance.
- A ready candidate still needs a Tyler-approved production plan and feature flag before it can affect live picks.
- Hindsight-only result, PnL, CLV, and actual workload fields are used for scoring/process support only, never as the sole live selector.

## Candidate Scoreboard

| Candidate | Kind | Readiness | Rows | W-L | PnL | ROI | Retained FIRE | Capped to LEAN | CLV support | Recent PnL | Slice risks |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `moderate_edge_quality_reentry` | `runtime_selector` | `watch_more` | 68 | 38-30 | +4.77 | +7.0% | 18 | 50 | 7 (+10.3%) | -1.00 | 4 |
| `retained_fire_control` | `runtime_selector` | `watch_more` | 134 | 77-57 | +2.71 | +2.0% | 134 | 0 | 18 (+13.4%) | -2.51 | 9 |
| `clv_supported_reentry` | `process_anchor` | `process_anchor` | 83 | 48-35 | +15.88 | +19.1% | 18 | 65 | 83 (+100.0%) | +1.22 | 2 |
| `avoid_fire_under_reentry` | `avoidance_rule` | `avoidance_rule` | 348 | 164-184 | -32.77 | -9.4% | 0 | 348 | 42 (+12.1%) | -1.48 | 27 |
| `market_aligned_reentry` | `runtime_selector` | `not_ready` | 250 | 137-113 | -13.77 | -5.5% | 103 | 147 | 24 (+9.6%) | +5.56 | 22 |

## Top Slice Risks

- `clv_supported_reentry`: no_vig_label=no_vig_thin_edge (11 rows, -0.49); line_bucket=5.5 (22 rows, -0.45).
- `market_aligned_reentry`: clv_label=clv_neutral_or_unknown (201 rows, -19.03); leash_risk_bucket=normal (210 rows, -16.43); side=under (147 rows, -15.04); price_sign=minus (250 rows, -13.77); model_market_relationship=model_agrees_with_favorite (250 rows, -13.77).
- `moderate_edge_quality_reentry`: line_bucket=4.5 (27 rows, -4.10); line_bucket=2.5-3.5 (11 rows, -2.62); side=under (33 rows, -0.95); price_sign=plus (28 rows, -0.01).
- `retained_fire_control`: display_verdict=LEAN (16 rows, -5.64); bet_timing_window=pre_5 (11 rows, -5.13); display_verdict=FIRE 2u (17 rows, -4.39); line_bucket=2.5-3.5 (35 rows, -3.94); model_market_relationship=unknown (12 rows, -2.55).
- `avoid_fire_under_reentry`: clv_label=clv_neutral_or_unknown (260 rows, -35.08); side=under (348 rows, -32.77); path_b_coverage_bucket=unknown (348 rows, -32.77); provider=unknown (348 rows, -32.77); market_agreement_label=unknown (348 rows, -32.77).

## Recommendation

- If no candidate is `ready_for_plan`, keep `PROFIT_RESCUE_REFEREE_MODE=enforce` and collect the next graded slates.
- If a candidate is `ready_for_plan`, draft a separate re-entry canary that restores FIRE only for that candidate family while preserving a one-env-var rollback.
- Do not change projection math from this report; projection challengers stay in the separate Gate F lambda lane.
