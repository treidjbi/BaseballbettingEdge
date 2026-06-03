# Gate C Holdout Shadow Lab

This report is shadow-only. It does not change live lambda, verdicts, thresholds, staking, provider order, notifications, calibration, or dashboard artifacts.

- Generated at: `2026-06-03T18:39:16Z`
- Clean window start: `2026-04-28`
- Official-close market rows: `735`
- Tracked pick side rows: `757`
- Training slates: `25` (2026-04-28 to 2026-05-22)
- Validation slates: `11` (2026-05-23 to 2026-06-02)

## Training Fit

Handedness adjustments are learned only from training rows. The reconstructed lineup fields remain hindsight-only until future runtime capture proves them prelock-safe.

| Bucket | Train Rows | Raw Residual Delta | Applied Delta |
| --- | ---: | ---: | ---: |
| `opposite_hand_heavy` | 140 | -0.153 | -0.112 |
| `same_hand_heavy` | 382 | 0.026 | 0.023 |

## Training Scoreboard

Error is `actual Ks - projected Ks`; negative means the projection was too high. Side-only baselines intentionally have no MAE/RMSE.

| Candidate | Rows | Mean Error | MAE | RMSE | Side W-L | Side Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `current_model` | 522 | -0.022 | 1.807 | 2.283 | 289-233 | 55.4% |
| `market_shrink_25` | 522 | 0.037 | 1.760 | 2.224 | 289-233 | 55.4% |
| `high_line_temper` | 522 | -0.010 | 1.805 | 2.279 | 293-229 | 56.1% |
| `handedness_bucket_adjust` | 522 | -0.008 | 1.806 | 2.282 | 288-234 | 55.2% |
| `market_favorite_only` | 522 | -- | -- | -- | 274-229 | 54.5% |
| `over_only` | 522 | -- | -- | -- | 283-239 | 54.2% |
| `under_only` | 522 | -- | -- | -- | 239-283 | 45.8% |

## Validation Holdout

| Candidate | Rows | Mean Error | MAE | RMSE | Side W-L | Side Accuracy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `current_model` | 213 | -0.221 | 1.822 | 2.249 | 112-99 | 53.1% |
| `market_shrink_25` | 213 | -0.174 | 1.805 | 2.227 | 112-99 | 53.1% |
| `high_line_temper` | 213 | -0.213 | 1.819 | 2.251 | 111-99 | 52.9% |
| `handedness_bucket_adjust` | 213 | -0.217 | 1.823 | 2.251 | 112-99 | 53.1% |
| `market_favorite_only` | 213 | -- | -- | -- | 123-84 | 59.4% |
| `over_only` | 213 | -- | -- | -- | 100-113 | 46.9% |
| `under_only` | 213 | -- | -- | -- | 113-100 | 53.1% |

## Validation Tracked-Pick Alignment

This checks whether a candidate would still point to the side Tyler actually tracked inside the validation window. It is not a replacement betting rule.

| Candidate | Tracked Rows | Aligned Rows | W-L | Flat PnL | Flat ROI |
| --- | ---: | ---: | ---: | ---: | ---: |
| `current_model` | 220 | 183 | 101-82 | +2.46 | 1.3% |
| `market_shrink_25` | 220 | 183 | 101-82 | +2.46 | 1.3% |
| `high_line_temper` | 220 | 181 | 100-81 | +2.48 | 1.4% |
| `handedness_bucket_adjust` | 220 | 183 | 101-82 | +2.46 | 1.3% |
| `market_favorite_only` | 220 | 105 | 68-37 | +13.17 | 12.5% |
| `over_only` | 220 | 105 | 54-51 | -3.58 | -3.4% |
| `under_only` | 220 | 115 | 65-50 | +8.01 | 7.0% |

## Rolling Validation Windows

Rolling windows reduce dependence on one train/validation split. They are still shadow-only.

| Window | Candidate | Training Dates | Validation Dates | Rows | MAE | RMSE | Side W-L | Side Accuracy |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | `current_model` | `2026-04-28 to 2026-05-17` | `2026-05-18 to 2026-05-22` | 103 | 1.848 | 2.397 | 66-37 | 64.1% |
| 1 | `market_shrink_25` | `2026-04-28 to 2026-05-17` | `2026-05-18 to 2026-05-22` | 103 | 1.835 | 2.366 | 66-37 | 64.1% |
| 1 | `high_line_temper` | `2026-04-28 to 2026-05-17` | `2026-05-18 to 2026-05-22` | 103 | 1.850 | 2.390 | 67-36 | 65.0% |
| 2 | `current_model` | `2026-05-03 to 2026-05-22` | `2026-05-23 to 2026-05-27` | 104 | 1.757 | 2.248 | 58-46 | 55.8% |
| 2 | `market_shrink_25` | `2026-05-03 to 2026-05-22` | `2026-05-23 to 2026-05-27` | 104 | 1.762 | 2.238 | 58-46 | 55.8% |
| 2 | `high_line_temper` | `2026-05-03 to 2026-05-22` | `2026-05-23 to 2026-05-27` | 104 | 1.757 | 2.254 | 57-47 | 54.8% |
| 3 | `current_model` | `2026-05-08 to 2026-05-27` | `2026-05-28 to 2026-06-01` | 87 | 1.873 | 2.258 | 44-41 | 51.8% |
| 3 | `market_shrink_25` | `2026-05-08 to 2026-05-27` | `2026-05-28 to 2026-06-01` | 87 | 1.827 | 2.220 | 44-41 | 51.8% |
| 3 | `high_line_temper` | `2026-05-08 to 2026-05-27` | `2026-05-28 to 2026-06-01` | 87 | 1.866 | 2.256 | 44-40 | 52.4% |

## Read Rule

- Do not discard lambda from this report alone; side baselines have no projection-error metric and can be regime-chasing.
- `market_shrink_25` beat current lambda on validation MAE (1.805 vs 1.822), so it is a Gate F candidate, not a live change.
- `market_favorite_only` had the best validation side accuracy (59.4% vs current 53.1%); treat that as a referee/selection warning.
- Any live model change still needs Gate E/F proof across side, price, K-line, quality, and provider slices.
