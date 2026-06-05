# K Projection Shadow Lab

This report is shadow-only. It does not change live lambda, verdicts, thresholds, staking, provider order, notifications, or calibration.

## Scope

- Clean window start: `2026-04-28`
- Official-close market rows: `749`
- Challenger projections: `current_model, market_shrink_15, market_shrink_25, market_shrink_35, high_line_temper, leash_cap, recent_rate_blend, career_rate_blend`

## Projection Accuracy

Error is `actual Ks - projected Ks`; negative means the projection was too high.

| Challenger | Rows | Mean Error | MAE | RMSE | Side W-L | Side Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `current_model` | 749 | -0.084 | 1.804 | 2.265 | 410-336 | 55.0% |
| `market_shrink_15` | 749 | -0.052 | 1.781 | 2.234 | 410-336 | 55.0% |
| `market_shrink_25` | 749 | -0.031 | 1.767 | 2.217 | 410-336 | 55.0% |
| `market_shrink_35` | 749 | -0.009 | 1.756 | 2.203 | 410-336 | 55.0% |
| `high_line_temper` | 749 | -0.073 | 1.801 | 2.262 | 414-331 | 55.6% |
| `leash_cap` | 749 | -0.032 | 1.809 | 2.276 | 409-338 | 54.8% |
| `recent_rate_blend` | 749 | -0.066 | 1.819 | 2.285 | 394-355 | 52.6% |
| `career_rate_blend` | 749 | -0.087 | 1.817 | 2.281 | 397-352 | 53.0% |

## Tracked Pick Alignment

This checks whether a challenger would still point to the side Tyler actually tracked. It is not a replacement betting rule.

| Challenger | Tracked Rows | Aligned Rows | W-L | Flat PnL | Flat ROI |
| --- | ---: | ---: | ---: | ---: | ---: |
| `current_model` | 347 | 325 | 178-147 | +8.30 | 2.6% |
| `market_shrink_15` | 347 | 325 | 178-147 | +8.30 | 2.6% |
| `market_shrink_25` | 347 | 325 | 178-147 | +8.30 | 2.6% |
| `market_shrink_35` | 347 | 325 | 178-147 | +8.30 | 2.6% |
| `high_line_temper` | 347 | 318 | 177-141 | +13.06 | 4.1% |
| `leash_cap` | 347 | 322 | 177-145 | +9.10 | 2.8% |
| `recent_rate_blend` | 347 | 315 | 169-146 | +0.12 | 0.0% |
| `career_rate_blend` | 347 | 321 | 175-146 | +6.62 | 2.1% |

## Challenger Slice Checks

### market_shrink_25 By side

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `over` | 749 | 1.767 | 2.217 | 410-336 | 55.0% | `enough_sample` |

### market_shrink_25 By price_sign

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `minus` | 457 | 1.721 | 2.199 | 263-191 | 57.9% | `enough_sample` |
| `plus` | 292 | 1.840 | 2.244 | 147-145 | 50.3% | `enough_sample` |

### market_shrink_25 By line_bucket

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `2.5-3.5` | 159 | 1.628 | 2.014 | 87-70 | 55.4% | `enough_sample` |
| `4.5` | 295 | 1.695 | 2.164 | 161-134 | 54.6% | `enough_sample` |
| `5.5` | 204 | 1.843 | 2.279 | 112-91 | 55.2% | `enough_sample` |
| `6.5` | 67 | 2.007 | 2.460 | 39-28 | 58.2% | `enough_sample` |
| `7.5+` | 24 | 2.253 | 2.818 | 11-13 | 45.8% | `small_sample` |

### market_shrink_25 By quality_gate_level

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `blocked` | 1 | 2.125 | 2.125 | 1-0 | 100.0% | `small_sample` |
| `capped` | 360 | 1.813 | 2.231 | 188-170 | 52.5% | `enough_sample` |
| `clean` | 361 | 1.727 | 2.219 | 207-153 | 57.5% | `enough_sample` |
| `unknown` | 27 | 1.677 | 1.996 | 14-13 | 51.9% | `enough_sample` |

### market_shrink_25 By model_market_relationship

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `model_agrees_with_favorite` | 361 | 1.764 | 2.226 | 205-155 | 56.9% | `enough_sample` |
| `model_fades_favorite` | 362 | 1.765 | 2.192 | 192-168 | 53.3% | `enough_sample` |
| `unknown` | 26 | 1.842 | 2.435 | 13-13 | 50.0% | `enough_sample` |

### market_shrink_25 By bet_timing_window

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `post_start` | 24 | 1.810 | 2.217 | 14-10 | 58.3% | `small_sample` |
| `pre_120` | 1 | 2.915 | 2.915 | 1-0 | 100.0% | `small_sample` |
| `pre_15` | 73 | 1.734 | 2.145 | 39-34 | 53.4% | `enough_sample` |
| `pre_30` | 216 | 1.793 | 2.232 | 120-96 | 55.6% | `enough_sample` |
| `pre_5` | 25 | 1.679 | 1.997 | 10-15 | 40.0% | `enough_sample` |
| `unknown` | 410 | 1.759 | 2.233 | 226-181 | 55.5% | `enough_sample` |

### market_shrink_25 By opportunity_bucket

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `deep_starter` | 80 | 1.832 | 2.379 | 41-39 | 51.2% | `enough_sample` |
| `normal` | 610 | 1.755 | 2.178 | 334-273 | 55.0% | `enough_sample` |
| `short_leash` | 59 | 1.809 | 2.379 | 35-24 | 59.3% | `enough_sample` |

### market_shrink_25 By leash_risk_bucket

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `high` | 59 | 1.809 | 2.379 | 35-24 | 59.3% | `enough_sample` |
| `medium` | 28 | 1.669 | 1.966 | 11-16 | 40.7% | `enough_sample` |
| `normal` | 662 | 1.768 | 2.212 | 364-296 | 55.2% | `enough_sample` |

### market_shrink_25 By pitcher_archetype_bucket

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `deep_starter` | 52 | 1.866 | 2.343 | 25-27 | 48.1% | `enough_sample` |
| `high_k_deep_starter` | 28 | 1.768 | 2.445 | 16-12 | 57.1% | `enough_sample` |
| `high_k_standard` | 183 | 1.910 | 2.357 | 98-85 | 53.6% | `enough_sample` |
| `low_k_standard` | 44 | 1.699 | 2.029 | 26-17 | 60.5% | `enough_sample` |
| `short_leash` | 59 | 1.809 | 2.379 | 35-24 | 59.3% | `enough_sample` |
| `standard_starter` | 383 | 1.687 | 2.105 | 210-171 | 55.1% | `enough_sample` |

### high_line_temper By side

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `over` | 749 | 1.801 | 2.262 | 414-331 | 55.6% | `enough_sample` |

### high_line_temper By price_sign

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `minus` | 457 | 1.756 | 2.242 | 265-188 | 58.5% | `enough_sample` |
| `plus` | 292 | 1.872 | 2.293 | 149-143 | 51.0% | `enough_sample` |

### high_line_temper By line_bucket

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `2.5-3.5` | 159 | 1.683 | 2.082 | 87-70 | 55.4% | `enough_sample` |
| `4.5` | 295 | 1.732 | 2.205 | 161-134 | 54.6% | `enough_sample` |
| `5.5` | 204 | 1.874 | 2.319 | 112-91 | 55.2% | `enough_sample` |
| `6.5` | 67 | 2.031 | 2.515 | 39-28 | 58.2% | `enough_sample` |
| `7.5+` | 24 | 2.182 | 2.800 | 15-8 | 65.2% | `small_sample` |

### high_line_temper By quality_gate_level

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `blocked` | 1 | 3.000 | 3.000 | 1-0 | 100.0% | `small_sample` |
| `capped` | 360 | 1.843 | 2.271 | 190-167 | 53.2% | `enough_sample` |
| `clean` | 361 | 1.760 | 2.261 | 209-151 | 58.1% | `enough_sample` |
| `unknown` | 27 | 1.753 | 2.116 | 14-13 | 51.9% | `enough_sample` |

### high_line_temper By model_market_relationship

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `model_agrees_with_favorite` | 361 | 1.811 | 2.282 | 206-154 | 57.2% | `enough_sample` |
| `model_fades_favorite` | 362 | 1.782 | 2.223 | 195-164 | 54.3% | `enough_sample` |
| `unknown` | 26 | 1.928 | 2.509 | 13-13 | 50.0% | `enough_sample` |

### high_line_temper By bet_timing_window

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `post_start` | 24 | 1.917 | 2.347 | 14-10 | 58.3% | `small_sample` |
| `pre_120` | 1 | 2.720 | 2.720 | 1-0 | 100.0% | `small_sample` |
| `pre_15` | 73 | 1.803 | 2.262 | 39-34 | 53.4% | `enough_sample` |
| `pre_30` | 216 | 1.834 | 2.266 | 121-94 | 56.3% | `enough_sample` |
| `pre_5` | 25 | 1.722 | 2.132 | 13-12 | 52.0% | `enough_sample` |
| `unknown` | 410 | 1.780 | 2.261 | 226-181 | 55.5% | `enough_sample` |

### high_line_temper By opportunity_bucket

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `deep_starter` | 80 | 1.835 | 2.410 | 45-34 | 57.0% | `enough_sample` |
| `normal` | 610 | 1.796 | 2.229 | 334-273 | 55.0% | `enough_sample` |
| `short_leash` | 59 | 1.810 | 2.392 | 35-24 | 59.3% | `enough_sample` |

### high_line_temper By leash_risk_bucket

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `high` | 59 | 1.810 | 2.392 | 35-24 | 59.3% | `enough_sample` |
| `medium` | 28 | 1.725 | 2.019 | 12-15 | 44.4% | `enough_sample` |
| `normal` | 662 | 1.804 | 2.260 | 367-292 | 55.7% | `enough_sample` |

### high_line_temper By pitcher_archetype_bucket

| Bucket | Rows | MAE | RMSE | Side W-L | Side Accuracy | Sample |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `deep_starter` | 52 | 1.963 | 2.423 | 25-27 | 48.1% | `enough_sample` |
| `high_k_deep_starter` | 28 | 1.597 | 2.385 | 20-7 | 74.1% | `enough_sample` |
| `high_k_standard` | 183 | 2.003 | 2.451 | 98-85 | 53.6% | `enough_sample` |
| `low_k_standard` | 44 | 1.720 | 2.048 | 26-17 | 60.5% | `enough_sample` |
| `short_leash` | 59 | 1.810 | 2.392 | 35-24 | 59.3% | `enough_sample` |
| `standard_starter` | 383 | 1.706 | 2.136 | 210-171 | 55.1% | `enough_sample` |

## Current Model By K-Line Bucket

| K-Line Bucket | Rows | Mean Error | MAE | Side W-L | Side Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| `2.5-3.5` | 159 | -0.328 | 1.683 | 87-70 | 55.4% |
| `4.5` | 295 | -0.042 | 1.732 | 161-134 | 54.6% |
| `5.5` | 204 | -0.001 | 1.874 | 112-91 | 55.2% |
| `6.5` | 67 | 0.076 | 2.031 | 39-28 | 58.2% |
| `7.5+` | 24 | -0.150 | 2.268 | 11-13 | 45.8% |

## Current Model By Pitcher Archetype

| Archetype | Rows | Mean Error | MAE | Side W-L | Side Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: |
| `deep_starter` | 52 | -0.250 | 1.963 | 25-27 | 48.1% |
| `high_k_deep_starter` | 28 | -0.173 | 1.715 | 16-12 | 57.1% |
| `high_k_standard` | 183 | -0.419 | 1.997 | 98-85 | 53.6% |
| `low_k_standard` | 44 | 0.195 | 1.720 | 26-17 | 60.5% |
| `short_leash` | 59 | 0.442 | 1.810 | 35-24 | 59.3% |
| `standard_starter` | 383 | -0.009 | 1.706 | 210-171 | 55.1% |

## Read Rule

- Treat this as a challenger-projection scoreboard, not a production recommendation.
- Prefer challengers that improve MAE/RMSE and side accuracy without depending on post-start data.
- Do not promote a projection adjustment unless it survives later slates and side, price, line, and provider slices.
- If a simple challenger keeps improving, the next step is a Gate C/F promotion plan with a rollback switch.
