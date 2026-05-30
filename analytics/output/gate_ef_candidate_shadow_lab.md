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

## fire_combined_skeptic Slice Checks

### side

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| over | 47 | 29-18 | +9.40 | +20.0% | small_sample |
| under | 17 | 9-8 | +2.33 | +13.7% | small_sample |

### price_sign

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| minus | 25 | 18-7 | +7.97 | +31.9% | small_sample |
| plus | 39 | 20-19 | +3.76 | +9.6% | small_sample |

### line_bucket

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| 2.5-3.5 | 16 | 8-8 | +0.45 | +2.8% | small_sample |
| 4.5 | 22 | 11-11 | -0.65 | -2.9% | small_sample |
| 5.5 | 19 | 14-5 | +9.26 | +48.7% | small_sample |
| 6.5 | 5 | 4-1 | +2.69 | +53.8% | small_sample |
| 7.5+ | 2 | 1-1 | -0.02 | -1.0% | small_sample |

### bet_timing_window

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| post_start | 2 | 2-0 | +1.83 | +91.5% | small_sample |
| pre_120 | 1 | 1-0 | +0.91 | +91.0% | small_sample |
| pre_15 | 11 | 6-5 | +1.00 | +9.1% | small_sample |
| pre_30 | 43 | 25-18 | +6.82 | +15.9% | small_sample |
| pre_5 | 5 | 2-3 | -1.15 | -23.0% | small_sample |
| unknown | 2 | 2-0 | +2.32 | +116.0% | small_sample |

### quality_gate_level

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| capped | 21 | 13-8 | +4.72 | +22.5% | small_sample |
| clean | 42 | 24-18 | +5.93 | +14.1% | small_sample |
| unknown | 1 | 1-0 | +1.08 | +108.0% | small_sample |

### model_market_relationship

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| model_agrees_with_favorite | 18 | 12-6 | +3.39 | +18.8% | small_sample |
| model_fades_favorite | 45 | 25-20 | +7.43 | +16.5% | small_sample |
| unknown | 1 | 1-0 | +0.91 | +91.0% | small_sample |

## Promotion Discussion Check

- Promising but not promotion-ready: fire_combined_skeptic selected 64 rows and retained 0 FIRE 2u wins; this is below the plan's validation/current-FIRE sample and retention standards.
- These rows are not production approval.
- A later Tyler-approved production plan is required before any candidate can affect live picks, thresholds, staking, notifications, provider behavior, or dashboard source-of-truth artifacts.
- Promotion discussion should compare this shadow evidence against the current live lambda baseline and the broader Gate E/F evidence package.
