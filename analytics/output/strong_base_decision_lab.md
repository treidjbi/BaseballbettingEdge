# Strong Base Decision Lab

Generated at: `2026-07-07T21:13:08.881061+00:00`

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, dashboard artifacts, or source-of-truth behavior.

## Executive Read

- Total source rows: `2722`; clean analyzed rows: `2722`.
- Tracked post-bump portfolio: `1417 (697-720), -105.53u, -7.4%`.
- Working answer: positive CLV is real process evidence, but broad pick volume is still losing; the lab should preserve price/timing-confirmed contexts and cut high-edge, market-faded, CLV-neutral mass.
- Nontracked PASS expansion check: `9 (1-8), -6.95u, -77.2%` positive-edge/EV PASS sides. Generic PASS expansion stays closed.
- Readiness rule: a runtime candidate is not plan-ready unless it has enough rows, positive PnL, current-provider support, positive recent form, and no meaningful negative mandatory slice.

## Positive CLV vs Mass Losses

| Bucket | Result |
| --- | ---: |
| All tracked | 1417 (697-720), -105.53u, -7.4% |
| `beat_close_price` | 215 (122-93), +18.19u, +8.5% |
| `beat_close_line` | 20 (11-9), +3.42u, +17.1% |
| `no_or_worse_price_clv` | 1182 (564-618), -127.14u, -10.8% |
| `edge_6_plus` | 708 (331-377), -86.44u, -12.2% |
| `model_fades_favorite` | 701 (302-399), -81.46u, -11.6% |

## Candidate Policy Draft

| Candidate | Lane | Runtime-safe | Result | Current provider | Recent | CLV support | Readiness |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `avoid_no_or_worse_price_clv_mass` | `cap_or_suppress` | False | 1182 (564-618), -127.14u, -10.8% | 203 (98-105), -19.97u, -9.8% | 219 (105-114), -23.63u, -10.8% | 0.0% | `cap_or_suppress_watch` |
| `cap_high_raw_edge` | `cap_or_suppress` | True | 708 (331-377), -86.44u, -12.2% | 123 (53-70), -23.93u, -19.5% | 135 (59-76), -25.25u, -18.7% | 9.3% | `cap_or_suppress_watch` |
| `cap_market_fade` | `cap_or_suppress` | True | 701 (302-399), -81.46u, -11.6% | 112 (50-62), -8.10u, -7.2% | 119 (51-68), -13.08u, -11.0% | 17.3% | `cap_or_suppress_watch` |
| `cap_fire_under_market_fade` | `cap_or_suppress` | True | 149 (60-89), -23.14u, -15.5% | 0 (0-0), +0.00u, +0.0% | 44 (14-30), -15.02u, -34.1% | 16.8% | `cap_or_suppress_watch` |
| `evidence_clv_supported` | `evidence_only` | False | 235 (133-102), +21.61u, +9.2% | 20 (15-5), +8.92u, +44.6% | 33 (19-14), +2.95u, +8.9% | 100.0% | `process_anchor` |
| `expand_lean_45_low_ev_normal_leash` | `expand_lean` | True | 100 (62-38), +13.42u, +13.4% | 18 (11-7), +3.78u, +21.0% | 26 (16-10), +4.52u, +17.4% | 21.0% | `watch_more` |
| `expand_lean_low_line_capped_model_fade` | `expand_lean` | True | 64 (36-28), +10.50u, +16.4% | 17 (9-8), +2.08u, +12.2% | 27 (13-14), +0.69u, +2.6% | 18.8% | `watch_more` |
| `expand_lean_low_k_standard_no_vig` | `expand_lean` | True | 49 (31-18), +10.10u, +20.6% | 13 (9-4), +3.66u, +28.1% | 26 (16-10), +3.71u, +14.3% | 14.3% | `watch_more` |
| `keep_fire_over_moderate_ev_normal_leash` | `keep_fire` | True | 170 (105-65), +23.50u, +13.8% | 18 (12-6), +2.52u, +14.0% | 23 (16-7), +4.25u, +18.5% | 11.8% | `watch_more` |
| `keep_fire_market_agreed_moderate_ev` | `keep_fire` | True | 141 (94-47), +21.81u, +15.5% | 18 (11-7), +0.63u, +3.5% | 24 (16-8), +3.07u, +12.8% | 17.0% | `watch_more` |

## Slice Risks

| Candidate | Negative mandatory slices |
| --- | --- |
| `keep_fire_market_agreed_moderate_ev` | clv=worse_close_price (24 (13-11), -1.92u, -8.0%); path_b=path_b_real_or_mixed (43 (25-18), -0.45u, -1.0%) |
| `keep_fire_over_moderate_ev_normal_leash` | market_agreement=market_no_signal (14 (7-7), -0.90u, -6.4%); path_b=path_b_real_or_mixed (43 (25-18), -0.27u, -0.6%) |
| `expand_lean_45_low_ev_normal_leash` | clv=worse_close_price (19 (9-10), -2.79u, -14.7%) |
| `expand_lean_low_k_standard_no_vig` | quality=clean (12 (5-7), -3.50u, -29.1%) |
| `expand_lean_low_line_capped_model_fade` | none above the 10-row threshold |
| `cap_high_raw_edge` | clv=neutral_or_unknown (555 (246-309), -94.08u, -17.0%); market_agreement=missing (664 (315-349), -73.50u, -11.1%); path_b=path_b_real_or_mixed (295 (128-167), -53.72u, -18.2%); side=under (425 (200-225), -51.69u, -12.2%) |
| `cap_market_fade` | model_market=model_fades_favorite (701 (302-399), -81.46u, -11.6%); price=plus (487 (191-296), -77.29u, -15.9%); clv=neutral_or_unknown (485 (200-285), -70.40u, -14.5%); market_agreement=missing (599 (256-343), -66.87u, -11.2%) |
| `cap_fire_under_market_fade` | clv=neutral_or_unknown (103 (38-65), -24.36u, -23.6%); side=under (149 (60-89), -23.14u, -15.5%); model_market=model_fades_favorite (149 (60-89), -23.14u, -15.5%); provider_era=pre_current_provider (149 (60-89), -23.14u, -15.5%) |
| `avoid_no_or_worse_price_clv_mass` | market_agreement=missing (1067 (507-560), -122.05u, -11.4%); clv=neutral_or_unknown (1001 (478-523), -106.00u, -10.6%); model_market=model_fades_favorite (580 (239-341), -86.90u, -15.0%); provider_era=pre_current_provider (858 (412-446), -84.06u, -9.8%) |
| `evidence_clv_supported` | market_agreement=market_against_model (13 (5-8), -5.44u, -41.9%); provider_era=post_boltodds_retirement (23 (10-13), -5.16u, -22.4%); price=plus (74 (33-41), -2.62u, -3.5%); market_agreement=market_no_signal (15 (7-8), -1.60u, -10.7%) |

## Next Gate

- Draft a separate promotion plan only for candidates marked `ready_for_plan`; everything else stays watch-only or process-anchor evidence.
- For `process_anchor` CLV rows, use mainline-best-price and pre-close proxy evidence before converting the signal into a live rule.
- Keep model math, thresholds, staking, provider order, notification classes, locks, retention, and dashboard source-of-truth unchanged until Tyler approves a separate implementation plan.
