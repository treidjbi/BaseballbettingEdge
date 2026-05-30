# Gate E/F Candidate Shadow Lab

**Shadow-only warning:** This report is analysis-only. It must not change live model behavior, production thresholds, staking, provider order, dashboard artifacts consumed by the app, notifications, or source-of-truth behavior.

## Scope

- Clean evaluation window starts at `2026-04-28`.
- Clean tracked rows included: `648`.
- Candidate labels use runtime-safe fields for shadow diagnostics only.

## Candidate Scoreboard

| Candidate | Selected | W-L | Flat PnL | ROI | FIRE 1u losses avoided | FIRE 2u wins retained |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| current_fire_flat | 370 | 180-190 | -28.52 | -7.7% | 0 | 46 |
| current_fire_over | 168 | 88-80 | -2.33 | -1.4% | 79 | 13 |
| current_fire_under | 202 | 92-110 | -26.19 | -13.0% | 62 | 33 |
| fire_without_under_skeptic_2plus | 216 | 112-104 | -0.34 | -0.2% | 64 | 22 |
| fire_without_under_skeptic_3plus | 271 | 142-129 | +4.78 | +1.8% | 48 | 38 |
| fire_mid_edge | 90 | 48-42 | +5.38 | +6.0% | 99 | 0 |
| fire_not_high_adj_ev | 198 | 105-93 | -0.08 | -0.0% | 48 | 0 |
| fire_model_margin_under_1_5 | 341 | 165-176 | -25.57 | -7.5% | 7 | 42 |
| fire_clean_quality | 200 | 104-96 | -2.96 | -1.5% | 90 | 44 |
| fire_combined_skeptic | 64 | 38-26 | +11.73 | +18.3% | 115 | 0 |

## Promotion Discussion Check

- These rows are not production approval.
- A later Tyler-approved production plan is required before any candidate can affect live picks, thresholds, staking, notifications, provider behavior, or dashboard source-of-truth artifacts.
- Promotion discussion should compare this shadow evidence against the current live lambda baseline and the broader Gate E/F evidence package.
