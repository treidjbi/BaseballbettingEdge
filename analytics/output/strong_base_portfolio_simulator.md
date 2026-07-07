# Strong Base Portfolio Simulator

Generated at: `2026-07-07T21:28:48.761504+00:00`

read-only: No live behavior changes. This simulator does not change model math, thresholds, staking, provider order, notifications, locks, retention, calibration, dashboard artifacts, or source-of-truth behavior.

## Executive Read

- Current staked FIRE baseline: `595 (298-297), -45.96u / 721.0u risked, -6.4%`.
- Strict runtime core: `83 (55-28), +15.26u / 83.0u risked, +18.4%`. This is the cleanest no-hindsight retained-FIRE policy shape.
- Strict plus selective LEAN expansion: `215 (133-82), +28.02u / 215.0u risked, +13.0%`. Treat as a watch policy unless current-provider and recent slices survive.
- Positive-edge PASS expansion check: `9 (1-8), -6.95u / 9.0u risked, -77.2%`. Broad extra PASS volume remains closed if this is weak.
- Price-confirmed hindsight ceiling: `235 (133-102), +21.61u / 235.0u risked, +9.2%`. This is the process target, not a live selector.

## Policy Comparison

| Policy | Mode | Result | Current provider | Recent | Hindsight | Readiness |
| --- | --- | ---: | ---: | ---: | --- | --- |
| `current_staked_fire` | `verdict_units` | 595 (298-297), -45.96u / 721.0u risked, -6.4% | 26 (14-12), -1.80u / 26.0u risked, -6.9% | 30 (17-13), -0.75u / 30.0u risked, -2.5% | False | `baseline` |
| `current_tracked_flat` | `flat_1u` | 1417 (697-720), -105.53u / 1417.0u risked, -7.4% | 223 (113-110), -11.05u / 223.0u risked, -5.0% | 241 (122-119), -13.34u / 241.0u risked, -5.5% | False | `baseline` |
| `drag_suppressed_tracked_flat` | `flat_1u` | 363 (212-151), +12.68u / 363.0u risked, +3.5% | 47 (30-17), +3.61u / 47.0u risked, +7.7% | 51 (33-18), +4.64u / 51.0u risked, +9.1% | False | `watch_more` |
| `strict_runtime_core_flat` | `flat_1u` | 83 (55-28), +15.26u / 83.0u risked, +18.4% | 9 (7-2), +3.09u / 9.0u risked, +34.3% | 17 (11-6), +1.90u / 17.0u risked, +11.2% | False | `watch_more` |
| `strict_plus_selective_lean_flat` | `flat_1u` | 215 (133-82), +28.02u / 215.0u risked, +13.0% | 34 (22-12), +7.39u / 34.0u risked, +21.7% | 40 (26-14), +8.42u / 40.0u risked, +21.0% | False | `watch_more` |
| `positive_edge_pass_expansion_flat` | `flat_1u` | 9 (1-8), -6.95u / 9.0u risked, -77.2% | 0 (0-0), +0.00u / 0.0u risked, +0.0% | 9 (1-8), -6.95u / 9.0u risked, -77.2% | False | `watch_more` |
| `price_confirmed_hindsight_ceiling` | `flat_1u` | 235 (133-102), +21.61u / 235.0u risked, +9.2% | 20 (15-5), +8.92u / 20.0u risked, +44.6% | 33 (19-14), +2.95u / 33.0u risked, +8.9% | True | `hindsight_ceiling` |

## Policy Slice Risks

| Policy | Negative mandatory slices |
| --- | --- |
| `drag_suppressed_tracked_flat` | quality=capped (156 (83-73), -7.97u / 156.0u risked, -5.1%); path_b=path_b_real_or_mixed (144 (80-64), -5.63u / 144.0u risked, -3.9%); price=plus (44 (18-26), -3.28u / 44.0u risked, -7.4%); provider_era=post_boltodds_retirement (42 (23-19), -2.67u / 42.0u risked, -6.3%) |
| `strict_runtime_core_flat` | clv=worse_close_price (13 (7-6), -0.90u / 13.0u risked, -6.9%) |
| `strict_plus_selective_lean_flat` | clv=worse_close_price (32 (16-16), -3.73u / 32.0u risked, -11.7%); price=plus (56 (25-31), -2.98u / 56.0u risked, -5.3%) |
| `positive_edge_pass_expansion_flat` | none above the 10-row threshold |
| `price_confirmed_hindsight_ceiling` | market_agreement=market_against_model (13 (5-8), -5.44u / 13.0u risked, -41.9%); provider_era=post_boltodds_retirement (23 (10-13), -5.16u / 23.0u risked, -22.4%); price=plus (74 (33-41), -2.62u / 74.0u risked, -3.5%); market_agreement=market_no_signal (15 (7-8), -1.60u / 15.0u risked, -10.7%) |

## Next Decision

- Draft a live promotion plan only for a runtime-safe policy marked `promotion_plan_candidate`.
- If every runtime-safe policy is `watch_more` or `not_ready`, keep current live caps and continue collecting mainline-best-price evidence.
- Never promote the `price_confirmed_hindsight_ceiling` directly; convert it into pre-close or best-main-line price rules first.
