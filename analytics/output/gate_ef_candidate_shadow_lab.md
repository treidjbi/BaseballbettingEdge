# Gate E/F Candidate Shadow Lab

**Shadow-only warning:** This report is analysis-only. It must not change live model behavior, production thresholds, staking, provider order, dashboard artifacts consumed by the app, notifications, or source-of-truth behavior.

## Scope

- Clean evaluation window starts at `2026-04-28`.
- Clean tracked rows included: `757`.
- Candidate labels use runtime-safe fields for shadow diagnostics only.

## Candidate Scoreboard

| Candidate | Selected | W-L | Flat PnL | ROI | FIRE 1u losses avoided | FIRE 2u wins retained |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| current_fire_flat | 418 | 204-214 | -31.70 | -7.6% | 0 | 49 |
| current_fire_over | 187 | 97-90 | -3.81 | -2.0% | 90 | 14 |
| current_fire_under | 231 | 107-124 | -27.89 | -12.1% | 69 | 35 |
| fire_without_under_skeptic_2plus | 246 | 125-121 | -4.58 | -1.9% | 71 | 24 |
| fire_without_under_skeptic_3plus | 305 | 158-147 | +2.17 | +0.7% | 54 | 41 |
| fire_mid_edge | 106 | 54-52 | +1.06 | +1.0% | 107 | 0 |
| fire_not_high_adj_ev | 230 | 121-109 | -1.84 | -0.8% | 50 | 0 |
| fire_model_margin_under_1_5 | 385 | 186-199 | -29.68 | -7.7% | 7 | 44 |
| fire_clean_quality | 222 | 115-107 | -4.06 | -1.8% | 103 | 47 |
| fire_combined_skeptic | 73 | 41-32 | +9.39 | +12.9% | 127 | 0 |

## fire_combined_skeptic Slice Checks

### side

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| over | 54 | 31-23 | +6.92 | +12.8% | enough_sample |
| under | 19 | 10-9 | +2.47 | +13.0% | small_sample |

### price_sign

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| minus | 28 | 18-10 | +4.97 | +17.8% | small_sample |
| plus | 45 | 23-22 | +4.42 | +9.8% | small_sample |

### line_bucket

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| 2.5-3.5 | 17 | 8-9 | -0.55 | -3.2% | small_sample |
| 4.5 | 28 | 13-15 | -2.31 | -8.2% | small_sample |
| 5.5 | 21 | 15-6 | +9.58 | +45.6% | small_sample |
| 6.5 | 5 | 4-1 | +2.69 | +53.8% | small_sample |
| 7.5+ | 2 | 1-1 | -0.02 | -1.0% | small_sample |

### bet_timing_window

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| post_start | 2 | 2-0 | +1.83 | +91.5% | small_sample |
| pre_120 | 1 | 1-0 | +0.91 | +91.0% | small_sample |
| pre_15 | 11 | 6-5 | +1.00 | +9.1% | small_sample |
| pre_30 | 52 | 28-24 | +4.48 | +8.6% | enough_sample |
| pre_5 | 5 | 2-3 | -1.15 | -23.0% | small_sample |
| unknown | 2 | 2-0 | +2.32 | +116.0% | small_sample |

### quality_gate_level

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| capped | 26 | 15-11 | +4.18 | +16.1% | small_sample |
| clean | 46 | 25-21 | +4.13 | +9.0% | small_sample |
| unknown | 1 | 1-0 | +1.08 | +108.0% | small_sample |

### model_market_relationship

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| model_agrees_with_favorite | 20 | 12-8 | +1.39 | +7.0% | small_sample |
| model_fades_favorite | 52 | 28-24 | +7.09 | +13.6% | enough_sample |
| unknown | 1 | 1-0 | +0.91 | +91.0% | small_sample |

## Promotion Discussion Check

- Promising but not promotion-ready: fire_combined_skeptic selected 73 rows and retained 0 FIRE 2u wins; this is below the plan's validation/current-FIRE sample and retention standards.
- These rows are not production approval.
- A later Tyler-approved production plan is required before any candidate can affect live picks, thresholds, staking, notifications, provider behavior, or dashboard source-of-truth artifacts.
- Promotion discussion should compare this shadow evidence against the current live lambda baseline and the broader Gate E/F evidence package.
