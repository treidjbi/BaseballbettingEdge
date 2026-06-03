# Market Favorite Confidence Referee Shadow Lab

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, calibration, locks, or dashboard artifacts.

## Scope

- Clean window start: `2026-04-28`
- Tracked rows: `757`
- Training slates: `25`
- Validation slates: `11`

## Validation Candidate Scoreboard

| Candidate | Rows | W-L | Flat PnL | Flat ROI |
| --- | ---: | ---: | ---: | ---: |
| `current_model_tracked` | 220 | 119-101 | +4.43 | +2.0% |
| `model_agrees_market_favorite` | 108 | 67-41 | +9.26 | +8.6% |
| `model_fades_market_favorite` | 106 | 49-57 | -4.49 | -4.2% |
| `over_agrees_market_favorite` | 47 | 28-19 | +2.24 | +4.8% |
| `under_agrees_market_favorite` | 61 | 39-22 | +7.02 | +11.5% |
| `market_favorite_referee_candidate` | 107 | 67-40 | +10.26 | +9.6% |
| `market_fade_warning_candidate` | 73 | 34-39 | -2.75 | -3.8% |

### market_favorite_referee_candidate By side

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| `over` | 47 | 28-19 | +2.24 | +4.8% | `small_sample` |
| `under` | 60 | 39-21 | +8.02 | +13.4% | `enough_sample` |

### market_favorite_referee_candidate By price_sign

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| `minus` | 100 | 63-37 | +8.48 | +8.5% | `enough_sample` |
| `plus` | 7 | 4-3 | +1.78 | +25.4% | `small_sample` |

### market_favorite_referee_candidate By line_bucket

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| `2.5-3.5` | 19 | 10-9 | -0.93 | -4.9% | `small_sample` |
| `4.5` | 42 | 27-15 | +4.03 | +9.6% | `small_sample` |
| `5.5` | 31 | 20-11 | +4.99 | +16.1% | `small_sample` |
| `6.5` | 13 | 8-5 | +0.81 | +6.2% | `small_sample` |
| `7.5+` | 2 | 2-0 | +1.35 | +67.5% | `small_sample` |

### market_favorite_referee_candidate By quality_gate_level

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| `capped` | 63 | 39-24 | +5.05 | +8.0% | `enough_sample` |
| `clean` | 44 | 28-16 | +5.20 | +11.8% | `small_sample` |

### market_favorite_referee_candidate By bet_timing_window

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| `pre_15` | 1 | 1-0 | +0.60 | +60.0% | `small_sample` |
| `pre_30` | 106 | 66-40 | +9.65 | +9.1% | `enough_sample` |

### market_favorite_referee_candidate By opportunity_bucket

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| `deep_starter` | 12 | 8-4 | +1.83 | +15.2% | `small_sample` |
| `normal` | 85 | 51-34 | +4.75 | +5.6% | `enough_sample` |
| `short_leash` | 10 | 8-2 | +3.68 | +36.8% | `small_sample` |

### market_favorite_referee_candidate By leash_risk_bucket

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| `high` | 10 | 8-2 | +3.68 | +36.8% | `small_sample` |
| `medium` | 3 | 2-1 | +0.25 | +8.3% | `small_sample` |
| `normal` | 94 | 57-37 | +6.33 | +6.7% | `enough_sample` |

### market_favorite_referee_candidate By pitcher_archetype_bucket

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| `deep_starter` | 9 | 5-4 | -0.36 | -4.0% | `small_sample` |
| `high_k_deep_starter` | 3 | 3-0 | +2.19 | +73.0% | `small_sample` |
| `high_k_standard` | 24 | 13-11 | -1.77 | -7.4% | `small_sample` |
| `low_k_standard` | 6 | 4-2 | +0.80 | +13.3% | `small_sample` |
| `short_leash` | 10 | 8-2 | +3.68 | +36.8% | `small_sample` |
| `standard_starter` | 55 | 34-21 | +5.72 | +10.4% | `enough_sample` |

## Promotion Discussion Gate

- Status: `not_ready`
- Blockers: `validation tracked rows 220 < 250`
- This report can only recommend drafting a later production plan.
- A candidate must survive over/under, plus/minus, K-line, quality, timing, opportunity/leash, and pitcher-archetype slices.
- Market-favorite evidence is a referee/selection warning candidate, not a replacement for the model.
