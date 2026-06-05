# Market Favorite Confidence Referee Shadow Lab

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, calibration, locks, or dashboard artifacts.

## Scope

- Clean window start: `2026-04-28`
- Tracked rows: `771`
- Training slates: `25`
- Validation slates: `12`

## Validation Candidate Scoreboard

| Candidate | Rows | W-L | Flat PnL | Flat ROI |
| --- | ---: | ---: | ---: | ---: |
| `current_model_tracked` | 234 | 126-108 | +3.39 | +1.4% |
| `model_agrees_market_favorite` | 115 | 72-43 | +10.80 | +9.4% |
| `model_fades_market_favorite` | 113 | 51-62 | -7.07 | -6.3% |
| `over_agrees_market_favorite` | 48 | 29-19 | +2.99 | +6.2% |
| `under_agrees_market_favorite` | 67 | 43-24 | +7.81 | +11.7% |
| `market_favorite_referee_candidate` | 114 | 72-42 | +11.80 | +10.4% |
| `market_fade_warning_candidate` | 80 | 36-44 | -5.33 | -6.7% |

### market_favorite_referee_candidate By side

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| `over` | 48 | 29-19 | +2.99 | +6.2% | `small_sample` |
| `under` | 66 | 43-23 | +8.81 | +13.3% | `enough_sample` |

### market_favorite_referee_candidate By price_sign

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| `minus` | 107 | 68-39 | +10.02 | +9.4% | `enough_sample` |
| `plus` | 7 | 4-3 | +1.78 | +25.4% | `small_sample` |

### market_favorite_referee_candidate By line_bucket

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| `2.5-3.5` | 21 | 11-10 | -1.17 | -5.6% | `small_sample` |
| `4.5` | 44 | 29-15 | +5.36 | +12.2% | `small_sample` |
| `5.5` | 33 | 21-12 | +4.74 | +14.4% | `small_sample` |
| `6.5` | 14 | 9-5 | +1.53 | +10.9% | `small_sample` |
| `7.5+` | 2 | 2-0 | +1.35 | +67.5% | `small_sample` |

### market_favorite_referee_candidate By quality_gate_level

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| `capped` | 70 | 44-26 | +6.60 | +9.4% | `enough_sample` |
| `clean` | 44 | 28-16 | +5.20 | +11.8% | `small_sample` |

### market_favorite_referee_candidate By bet_timing_window

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| `pre_15` | 1 | 1-0 | +0.60 | +60.0% | `small_sample` |
| `pre_30` | 113 | 71-42 | +11.20 | +9.9% | `enough_sample` |

### market_favorite_referee_candidate By opportunity_bucket

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| `deep_starter` | 13 | 9-4 | +2.59 | +19.9% | `small_sample` |
| `normal` | 89 | 53-36 | +4.11 | +4.6% | `enough_sample` |
| `short_leash` | 12 | 10-2 | +5.10 | +42.5% | `small_sample` |

### market_favorite_referee_candidate By leash_risk_bucket

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| `high` | 12 | 10-2 | +5.10 | +42.5% | `small_sample` |
| `medium` | 3 | 2-1 | +0.25 | +8.3% | `small_sample` |
| `normal` | 99 | 60-39 | +6.45 | +6.5% | `enough_sample` |

### market_favorite_referee_candidate By pitcher_archetype_bucket

| Bucket | Rows | W-L | Flat PnL | Flat ROI | Sample |
| --- | ---: | ---: | ---: | ---: | --- |
| `deep_starter` | 10 | 6-4 | +0.40 | +4.0% | `small_sample` |
| `high_k_deep_starter` | 3 | 3-0 | +2.19 | +73.0% | `small_sample` |
| `high_k_standard` | 24 | 13-11 | -1.77 | -7.4% | `small_sample` |
| `low_k_standard` | 7 | 4-3 | -0.20 | -2.9% | `small_sample` |
| `short_leash` | 12 | 10-2 | +5.10 | +42.5% | `small_sample` |
| `standard_starter` | 58 | 36-22 | +6.08 | +10.5% | `enough_sample` |

## Promotion Discussion Gate

- Status: `not_ready`
- Blockers: `validation tracked rows 234 < 250`
- This report can only recommend drafting a later production plan.
- A candidate must survive over/under, plus/minus, K-line, quality, timing, opportunity/leash, and pitcher-archetype slices.
- Market-favorite evidence is a referee/selection warning candidate, not a replacement for the model.
