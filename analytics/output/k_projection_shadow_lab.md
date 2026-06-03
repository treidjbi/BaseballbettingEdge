# K Projection Shadow Lab

This report is shadow-only. It does not change live lambda, verdicts, thresholds, staking, provider order, notifications, or calibration.

## Scope

- Clean window start: `2026-04-28`
- Official-close market rows: `735`
- Challenger projections: `current_model, market_shrink_15, market_shrink_25, market_shrink_35, high_line_temper, leash_cap, recent_rate_blend, career_rate_blend`

## Projection Accuracy

Error is `actual Ks - projected Ks`; negative means the projection was too high.

| Challenger | Rows | Mean Error | MAE | RMSE | Side W-L | Side Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `current_model` | 735 | -0.079 | 1.811 | 2.273 | 401-332 | 54.7% |
| `market_shrink_15` | 735 | -0.046 | 1.787 | 2.242 | 401-332 | 54.7% |
| `market_shrink_25` | 735 | -0.025 | 1.773 | 2.225 | 401-332 | 54.7% |
| `market_shrink_35` | 735 | -0.003 | 1.762 | 2.210 | 401-332 | 54.7% |
| `high_line_temper` | 735 | -0.069 | 1.809 | 2.271 | 404-328 | 55.2% |
| `leash_cap` | 735 | -0.028 | 1.817 | 2.285 | 401-333 | 54.6% |
| `recent_rate_blend` | 735 | -0.062 | 1.825 | 2.292 | 385-350 | 52.4% |
| `career_rate_blend` | 735 | -0.083 | 1.823 | 2.289 | 388-347 | 52.8% |

## Tracked Pick Alignment

This checks whether a challenger would still point to the side Tyler actually tracked. It is not a replacement betting rule.

| Challenger | Tracked Rows | Aligned Rows | W-L | Flat PnL | Flat ROI |
| --- | ---: | ---: | ---: | ---: | ---: |
| `current_model` | 342 | 320 | 176-144 | +9.32 | 2.9% |
| `market_shrink_15` | 342 | 320 | 176-144 | +9.32 | 2.9% |
| `market_shrink_25` | 342 | 320 | 176-144 | +9.32 | 2.9% |
| `market_shrink_35` | 342 | 320 | 176-144 | +9.32 | 2.9% |
| `high_line_temper` | 342 | 314 | 175-139 | +13.08 | 4.2% |
| `leash_cap` | 342 | 317 | 175-142 | +10.12 | 3.2% |
| `recent_rate_blend` | 342 | 310 | 167-143 | +1.14 | 0.4% |
| `career_rate_blend` | 342 | 316 | 173-143 | +7.64 | 2.4% |

## Challenger Slice Checks

### market_shrink_25 By side

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `over` | 735 | 1.773 | 2.225 | 401-332 | 54.7% | `enough_sample` |

### market_shrink_25 By price_sign

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `minus` | 451 | 1.729 | 2.209 | 259-190 | 57.7% | `enough_sample` |
| `plus` | 284 | 1.843 | 2.248 | 142-142 | 50.0% | `enough_sample` |

### market_shrink_25 By line_bucket

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `2.5-3.5` | 154 | 1.652 | 2.039 | 83-70 | 54.2% | `enough_sample` |
| `4.5` | 291 | 1.700 | 2.170 | 158-133 | 54.3% | `enough_sample` |
| `5.5` | 201 | 1.829 | 2.267 | 111-89 | 55.5% | `enough_sample` |
| `6.5` | 66 | 2.027 | 2.477 | 38-28 | 57.6% | `enough_sample` |
| `7.5+` | 23 | 2.283 | 2.861 | 11-12 | 47.8% | `small_sample` |

### market_shrink_25 By quality_gate_level

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `blocked` | 1 | 2.125 | 2.125 | 1-0 | 100.0% | `small_sample` |
| `capped` | 346 | 1.827 | 2.248 | 179-166 | 51.9% | `enough_sample` |
| `clean` | 361 | 1.727 | 2.219 | 207-153 | 57.5% | `enough_sample` |
| `unknown` | 27 | 1.677 | 1.996 | 14-13 | 51.9% | `enough_sample` |

### market_shrink_25 By model_market_relationship

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `model_agrees_with_favorite` | 354 | 1.773 | 2.233 | 199-154 | 56.4% | `enough_sample` |
| `model_fades_favorite` | 355 | 1.768 | 2.200 | 189-165 | 53.4% | `enough_sample` |
| `unknown` | 26 | 1.842 | 2.435 | 13-13 | 50.0% | `enough_sample` |

### market_shrink_25 By bet_timing_window

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `post_start` | 24 | 1.810 | 2.217 | 14-10 | 58.3% | `small_sample` |
| `pre_120` | 1 | 2.915 | 2.915 | 1-0 | 100.0% | `small_sample` |
| `pre_15` | 73 | 1.734 | 2.145 | 39-34 | 53.4% | `enough_sample` |
| `pre_30` | 211 | 1.793 | 2.239 | 118-93 | 55.9% | `enough_sample` |
| `pre_5` | 25 | 1.679 | 1.997 | 10-15 | 40.0% | `enough_sample` |
| `unknown` | 401 | 1.770 | 2.243 | 219-180 | 54.9% | `enough_sample` |

### market_shrink_25 By opportunity_bucket

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `deep_starter` | 77 | 1.850 | 2.407 | 40-37 | 51.9% | `enough_sample` |
| `normal` | 602 | 1.761 | 2.186 | 329-271 | 54.8% | `enough_sample` |
| `short_leash` | 56 | 1.800 | 2.375 | 32-24 | 57.1% | `enough_sample` |

### market_shrink_25 By leash_risk_bucket

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `high` | 56 | 1.800 | 2.375 | 32-24 | 57.1% | `enough_sample` |
| `medium` | 28 | 1.669 | 1.966 | 11-16 | 40.7% | `enough_sample` |
| `normal` | 651 | 1.775 | 2.222 | 358-292 | 55.1% | `enough_sample` |

### market_shrink_25 By pitcher_archetype_bucket

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `deep_starter` | 50 | 1.890 | 2.370 | 24-26 | 48.0% | `enough_sample` |
| `high_k_deep_starter` | 27 | 1.776 | 2.472 | 16-11 | 59.3% | `enough_sample` |
| `high_k_standard` | 182 | 1.908 | 2.358 | 98-84 | 53.8% | `enough_sample` |
| `low_k_standard` | 42 | 1.728 | 2.062 | 24-17 | 58.5% | `enough_sample` |
| `short_leash` | 56 | 1.800 | 2.375 | 32-24 | 57.1% | `enough_sample` |
| `standard_starter` | 378 | 1.694 | 2.111 | 207-170 | 54.9% | `enough_sample` |

### high_line_temper By side

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `over` | 735 | 1.809 | 2.271 | 404-328 | 55.2% | `enough_sample` |

### high_line_temper By price_sign

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `minus` | 451 | 1.764 | 2.252 | 261-187 | 58.3% | `enough_sample` |
| `plus` | 284 | 1.881 | 2.301 | 143-141 | 50.4% | `enough_sample` |

### high_line_temper By line_bucket

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `2.5-3.5` | 154 | 1.710 | 2.110 | 83-70 | 54.2% | `enough_sample` |
| `4.5` | 291 | 1.738 | 2.212 | 158-133 | 54.3% | `enough_sample` |
| `5.5` | 201 | 1.859 | 2.307 | 111-89 | 55.5% | `enough_sample` |
| `6.5` | 66 | 2.057 | 2.533 | 38-28 | 57.6% | `enough_sample` |
| `7.5+` | 23 | 2.233 | 2.852 | 14-8 | 63.6% | `small_sample` |

### high_line_temper By quality_gate_level

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `blocked` | 1 | 3.000 | 3.000 | 1-0 | 100.0% | `small_sample` |
| `capped` | 346 | 1.861 | 2.290 | 180-164 | 52.3% | `enough_sample` |
| `clean` | 361 | 1.760 | 2.261 | 209-151 | 58.1% | `enough_sample` |
| `unknown` | 27 | 1.753 | 2.116 | 14-13 | 51.9% | `enough_sample` |

### high_line_temper By model_market_relationship

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `model_agrees_with_favorite` | 354 | 1.822 | 2.290 | 200-153 | 56.7% | `enough_sample` |
| `model_fades_favorite` | 355 | 1.788 | 2.233 | 191-162 | 54.1% | `enough_sample` |
| `unknown` | 26 | 1.928 | 2.509 | 13-13 | 50.0% | `enough_sample` |

### high_line_temper By bet_timing_window

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `post_start` | 24 | 1.917 | 2.347 | 14-10 | 58.3% | `small_sample` |
| `pre_120` | 1 | 2.720 | 2.720 | 1-0 | 100.0% | `small_sample` |
| `pre_15` | 73 | 1.803 | 2.262 | 39-34 | 53.4% | `enough_sample` |
| `pre_30` | 211 | 1.836 | 2.274 | 118-92 | 56.2% | `enough_sample` |
| `pre_5` | 25 | 1.722 | 2.132 | 13-12 | 52.0% | `enough_sample` |
| `unknown` | 401 | 1.793 | 2.273 | 219-180 | 54.9% | `enough_sample` |

### high_line_temper By opportunity_bucket

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `deep_starter` | 77 | 1.853 | 2.438 | 43-33 | 56.6% | `enough_sample` |
| `normal` | 602 | 1.804 | 2.237 | 329-271 | 54.8% | `enough_sample` |
| `short_leash` | 56 | 1.811 | 2.395 | 32-24 | 57.1% | `enough_sample` |

### high_line_temper By leash_risk_bucket

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `high` | 56 | 1.811 | 2.395 | 32-24 | 57.1% | `enough_sample` |
| `medium` | 28 | 1.725 | 2.019 | 12-15 | 44.4% | `enough_sample` |
| `normal` | 651 | 1.813 | 2.270 | 360-289 | 55.5% | `enough_sample` |

### high_line_temper By pitcher_archetype_bucket

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `deep_starter` | 50 | 1.980 | 2.447 | 24-26 | 48.0% | `enough_sample` |
| `high_k_deep_starter` | 27 | 1.618 | 2.420 | 19-7 | 73.1% | `enough_sample` |
| `high_k_standard` | 182 | 2.001 | 2.450 | 98-84 | 53.8% | `enough_sample` |
| `low_k_standard` | 42 | 1.755 | 2.085 | 24-17 | 58.5% | `enough_sample` |
| `short_leash` | 56 | 1.811 | 2.395 | 32-24 | 57.1% | `enough_sample` |
| `standard_starter` | 378 | 1.714 | 2.143 | 207-170 | 54.9% | `enough_sample` |

## Current Model By K-Line Bucket

| K-Line Bucket | Rows | Mean Error | MAE | Side W-L | Side Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| `2.5-3.5` | 154 | -0.347 | 1.710 | 83-70 | 54.2% |
| `4.5` | 291 | -0.041 | 1.738 | 158-133 | 54.3% |
| `5.5` | 201 | 0.019 | 1.859 | 111-89 | 55.5% |
| `6.5` | 66 | 0.082 | 2.057 | 38-28 | 57.6% |
| `7.5+` | 23 | -0.088 | 2.298 | 11-12 | 47.8% |

## Current Model By Pitcher Archetype

| Archetype | Rows | Mean Error | MAE | Side W-L | Side Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| `deep_starter` | 50 | -0.199 | 1.980 | 24-26 | 48.0% |
| `high_k_deep_starter` | 27 | -0.121 | 1.720 | 16-11 | 59.3% |
| `high_k_standard` | 182 | -0.407 | 1.994 | 98-84 | 53.8% |
| `low_k_standard` | 42 | 0.194 | 1.755 | 24-17 | 58.5% |
| `short_leash` | 56 | 0.522 | 1.811 | 32-24 | 57.1% |
| `standard_starter` | 378 | -0.022 | 1.714 | 207-170 | 54.9% |

## Read Rule

- Treat this as a challenger-projection scoreboard, not a production recommendation.
- Prefer challengers that improve MAE/RMSE and side accuracy without depending on post-start data.
- Do not promote a projection adjustment unless it survives later slates and side, price, line, and provider slices.
- If a simple challenger keeps improving, the next step is a Gate C/F promotion plan with a rollback switch.
