# Gate C Holdout Shadow Lab

This report is shadow-only. It does not change live lambda, verdicts, thresholds, staking, provider order, notifications, calibration, or dashboard artifacts.

- Generated at: `2026-06-05T15:24:39Z`
- Clean window start: `2026-04-28`
- Official-close market rows: `749`
- Tracked pick side rows: `771`
- Training slates: `25` (2026-04-28 to 2026-05-22)
- Validation slates: `12` (2026-05-23 to 2026-06-04)

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
| `current_model` | 227 | -0.229 | 1.798 | 2.223 | 121-103 | 54.0% |
| `market_shrink_25` | 227 | -0.186 | 1.783 | 2.202 | 121-103 | 54.0% |
| `high_line_temper` | 227 | -0.219 | 1.793 | 2.223 | 121-102 | 54.3% |
| `handedness_bucket_adjust` | 227 | -0.226 | 1.799 | 2.224 | 121-103 | 54.0% |
| `market_favorite_only` | 227 | -- | -- | -- | 134-87 | 60.6% |
| `over_only` | 227 | -- | -- | -- | 106-121 | 46.7% |
| `under_only` | 227 | -- | -- | -- | 121-106 | 53.3% |

## Validation Tracked-Pick Alignment

This checks whether a candidate would still point to the side Tyler actually tracked inside the validation window. It is not a replacement betting rule.

| Candidate | Tracked Rows | Aligned Rows | W-L | Flat PnL | Flat ROI |
| --- | ---: | ---: | ---: | ---: | ---: |
| `current_model` | 234 | 194 | 108-86 | +4.42 | 2.3% |
| `market_shrink_25` | 234 | 194 | 108-86 | +4.42 | 2.3% |
| `high_line_temper` | 234 | 191 | 107-84 | +5.44 | 2.8% |
| `handedness_bucket_adjust` | 234 | 194 | 108-86 | +4.42 | 2.3% |
| `market_favorite_only` | 234 | 111 | 73-38 | +15.71 | 14.2% |
| `over_only` | 234 | 110 | 56-54 | -4.61 | -4.2% |
| `under_only` | 234 | 124 | 70-54 | +7.99 | 6.4% |

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
- `market_shrink_25` beat current lambda on validation MAE (1.783 vs 1.798), so it is a Gate F candidate, not a live change.
- `market_favorite_only` had the best validation side accuracy (60.6% vs current 54.0%); treat that as a referee/selection warning.
- Any live model change still needs Gate E/F proof across side, price, K-line, quality, and provider slices.
