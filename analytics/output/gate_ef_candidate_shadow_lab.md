# Gate E/F Candidate Shadow Lab

**Shadow-only warning:** This report is analysis-only. It must not change live model behavior, production thresholds, staking, provider order, dashboard artifacts consumed by the app, notifications, or source-of-truth behavior.

## Scope

- Clean evaluation window starts at `2026-04-28`.
- Clean tracked rows included: `670`.
- Candidate labels use runtime-safe fields for shadow diagnostics only.

## Candidate Scoreboard

| Candidate | Selected | W-L | Flat PnL | ROI | FIRE 1u losses avoided | FIRE 2u wins retained |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| current_fire_flat | 379 | 184-195 | -30.57 | -8.1% | 0 | 47 |
| current_fire_over | 172 | 89-83 | -4.33 | -2.5% | 81 | 13 |
| current_fire_under | 207 | 95-112 | -26.24 | -12.7% | 64 | 34 |
| fire_without_under_skeptic_2plus | 220 | 113-107 | -2.34 | -1.1% | 66 | 22 |
| fire_without_under_skeptic_3plus | 277 | 144-133 | +2.44 | +0.9% | 49 | 39 |
| fire_mid_edge | 92 | 48-44 | +3.38 | +3.7% | 101 | 0 |
| fire_not_high_adj_ev | 203 | 106-97 | -3.39 | -1.7% | 48 | 0 |
| fire_model_margin_under_1_5 | 348 | 167-181 | -28.88 | -8.3% | 7 | 42 |
| fire_clean_quality | 204 | 106-98 | -3.61 | -1.8% | 93 | 45 |
| fire_combined_skeptic | 65 | 38-27 | +10.73 | +16.5% | 118 | 0 |

## fire_combined_skeptic Slice Checks

### side

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| over | 48 | 29-19 | +8.40 | +17.5% | small_sample |
| under | 17 | 9-8 | +2.33 | +13.7% | small_sample |

### price_sign

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| minus | 26 | 18-8 | +6.97 | +26.8% | small_sample |
| plus | 39 | 20-19 | +3.76 | +9.6% | small_sample |

### line_bucket

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| 2.5-3.5 | 16 | 8-8 | +0.45 | +2.8% | small_sample |
| 4.5 | 23 | 11-12 | -1.65 | -7.2% | small_sample |
| 5.5 | 19 | 14-5 | +9.26 | +48.7% | small_sample |
| 6.5 | 5 | 4-1 | +2.69 | +53.8% | small_sample |
| 7.5+ | 2 | 1-1 | -0.02 | -1.0% | small_sample |

### bet_timing_window

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| post_start | 2 | 2-0 | +1.83 | +91.5% | small_sample |
| pre_120 | 1 | 1-0 | +0.91 | +91.0% | small_sample |
| pre_15 | 11 | 6-5 | +1.00 | +9.1% | small_sample |
| pre_30 | 44 | 25-19 | +5.82 | +13.2% | small_sample |
| pre_5 | 5 | 2-3 | -1.15 | -23.0% | small_sample |
| unknown | 2 | 2-0 | +2.32 | +116.0% | small_sample |

### quality_gate_level

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| capped | 22 | 13-9 | +3.72 | +16.9% | small_sample |
| clean | 42 | 24-18 | +5.93 | +14.1% | small_sample |
| unknown | 1 | 1-0 | +1.08 | +108.0% | small_sample |

### model_market_relationship

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| model_agrees_with_favorite | 18 | 12-6 | +3.39 | +18.8% | small_sample |
| model_fades_favorite | 46 | 25-21 | +6.43 | +14.0% | small_sample |
| unknown | 1 | 1-0 | +0.91 | +91.0% | small_sample |

## Promotion Discussion Check

- Promising but not promotion-ready: fire_combined_skeptic selected 65 rows and retained 0 FIRE 2u wins; this is below the plan's validation/current-FIRE sample and retention standards.
- These rows are not production approval.
- A later Tyler-approved production plan is required before any candidate can affect live picks, thresholds, staking, notifications, provider behavior, or dashboard source-of-truth artifacts.
- Promotion discussion should compare this shadow evidence against the current live lambda baseline and the broader Gate E/F evidence package.
