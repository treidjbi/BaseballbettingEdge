# Market Agreement Tracker

Shadow-only: this report does not change picks, locks, thresholds, staking, provider order, notifications, or calibration.

## Summary

- Evidence rows: `2482`
- FIRE rows: `1496`
- LEAN rows: `986`
- Confidence-referee applied caps: `56`
- Graded rows: `2171`

## Sample Gate

- Overall status: `review_ready`
- Movement-backed graded rows: `2171`
- Minimum overall graded rows: `75`
- Minimum bucket graded rows: `50`
- Buckets below the minimum are watch-only even when their PnL looks attractive.

## Agreement Buckets

| Tracker Bucket | Agreement | Strength | Magnitude | Rows | FIRE | LEAN | Ref Caps | Graded | W-L | PnL | ROI |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `fire_no_signal` | `market_no_signal` | `no_movement_signal` | `small_or_none` | 1049 | 1049 | 0 | 0 | 967 | 481-486 | -56.82 | -5.9% |
| `lean_no_signal` | `market_no_signal` | `no_movement_signal` | `small_or_none` | 543 | 0 | 543 | 0 | 452 | 255-197 | +21.50 | +4.8% |
| `fire_market_with_us` | `market_with_model` | `mixed_or_reversed` | `line_half_plus` | 60 | 60 | 0 | 0 | 56 | 29-27 | +0.78 | +1.4% |
| `lean_mixed` | `market_mixed` | `mixed_or_reversed` | `line_half_plus` | 56 | 0 | 56 | 0 | 47 | 28-19 | +4.50 | +9.6% |
| `fire_mixed` | `market_mixed` | `mixed_or_reversed` | `line_half_plus` | 50 | 50 | 0 | 0 | 42 | 18-24 | -6.81 | -16.2% |
| `lean_market_with_us` | `market_with_model` | `mixed_or_reversed` | `line_half_plus` | 51 | 0 | 51 | 0 | 41 | 30-11 | +16.74 | +40.8% |
| `fire_market_with_us` | `market_with_model` | `broad_with_model` | `small_or_none` | 46 | 46 | 0 | 0 | 40 | 25-15 | +9.46 | +23.6% |
| `fire_market_against_us` | `market_against_model` | `single_book_against_model` | `small_or_none` | 43 | 43 | 0 | 0 | 38 | 12-26 | -14.94 | -39.3% |
| `lean_market_against_us` | `market_against_model` | `single_book_against_model` | `small_or_none` | 45 | 0 | 45 | 0 | 37 | 24-13 | +6.71 | +18.1% |
| `lean_market_with_us` | `market_with_model` | `broad_with_model` | `small_or_none` | 39 | 0 | 39 | 0 | 34 | 19-15 | +2.42 | +7.1% |
| `referee_cap_no_signal` | `market_no_signal` | `no_movement_signal` | `small_or_none` | 30 | 3 | 27 | 30 | 30 | 18-12 | +8.19 | +27.3% |
| `fire_market_against_us` | `market_against_model` | `mixed_or_reversed` | `line_half_plus` | 35 | 35 | 0 | 0 | 29 | 9-20 | -12.42 | -42.8% |
| `lean_market_against_us` | `market_against_model` | `mixed_or_reversed` | `line_half_plus` | 31 | 0 | 31 | 0 | 26 | 12-14 | -5.55 | -21.3% |
| `lean_mixed` | `market_mixed` | `mixed_or_reversed` | `small_or_none` | 36 | 0 | 36 | 0 | 25 | 11-14 | -4.48 | -17.9% |
| `fire_no_signal` | `market_no_signal` | `mixed_or_reversed` | `small_or_none` | 22 | 22 | 0 | 0 | 21 | 12-9 | +1.13 | +5.4% |
| `fire_market_against_us` | `market_against_model` | `mixed_or_reversed` | `odds_20c_plus` | 20 | 20 | 0 | 0 | 19 | 11-8 | +2.13 | +11.2% |
| `fire_market_with_us` | `market_with_model` | `mixed_or_reversed` | `odds_20c_plus` | 20 | 20 | 0 | 0 | 17 | 8-9 | -1.68 | -9.9% |
| `fire_mixed` | `market_mixed` | `mixed_or_reversed` | `small_or_none` | 22 | 22 | 0 | 0 | 16 | 7-9 | -1.98 | -12.4% |
| `fire_market_against_us` | `market_against_model` | `mixed_or_reversed` | `small_or_none` | 18 | 18 | 0 | 0 | 16 | 11-5 | +3.83 | +23.9% |
| `fire_market_with_us` | `market_with_model` | `single_book_with_model` | `small_or_none` | 15 | 15 | 0 | 0 | 14 | 6-8 | -3.41 | -24.4% |
| `lean_market_with_us` | `market_with_model` | `single_book_with_model` | `small_or_none` | 16 | 0 | 16 | 0 | 13 | 7-6 | +0.93 | +7.1% |
| `fire_market_with_us` | `market_with_model` | `single_book_with_model` | `line_half_plus` | 13 | 13 | 0 | 0 | 11 | 6-5 | +0.65 | +5.9% |
| `fire_market_with_us` | `market_with_model` | `mixed_or_reversed` | `small_or_none` | 11 | 11 | 0 | 0 | 11 | 3-8 | -5.54 | -50.4% |
| `fire_market_with_us` | `market_with_model` | `mixed_or_reversed` | `odds_10_19c` | 12 | 12 | 0 | 0 | 10 | 8-2 | +5.09 | +50.9% |
| `fire_market_with_us` | `market_with_model` | `single_book_with_model` | `odds_20c_plus` | 12 | 12 | 0 | 0 | 10 | 5-5 | -1.02 | -10.2% |
| `lean_market_against_us` | `market_against_model` | `mixed_or_reversed` | `odds_20c_plus` | 10 | 0 | 10 | 0 | 8 | 4-4 | -0.22 | -2.8% |
| `lean_mixed` | `market_mixed` | `mixed_or_reversed` | `odds_20c_plus` | 10 | 0 | 10 | 0 | 8 | 3-5 | -2.32 | -29.0% |
| `lean_market_with_us` | `market_with_model` | `mixed_or_reversed` | `small_or_none` | 13 | 0 | 13 | 0 | 7 | 4-3 | +0.14 | +2.0% |
| `lean_market_against_us` | `market_against_model` | `mixed_or_reversed` | `small_or_none` | 10 | 0 | 10 | 0 | 7 | 4-3 | +0.70 | +10.0% |
| `fire_market_against_us` | `market_against_model` | `single_book_against_model` | `odds_10_19c` | 9 | 9 | 0 | 0 | 7 | 3-4 | -1.38 | -19.7% |

## LEAN Buckets

| Tracker Bucket | Strength | Magnitude | Rows | FIRE | LEAN | Ref Caps | Graded | W-L | PnL | ROI |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `lean_no_signal` | `no_movement_signal` | `small_or_none` | 543 | 0 | 543 | 0 | 452 | 255-197 | +21.50 | +4.8% |
| `lean_mixed` | `mixed_or_reversed` | `line_half_plus` | 56 | 0 | 56 | 0 | 47 | 28-19 | +4.50 | +9.6% |
| `lean_market_with_us` | `mixed_or_reversed` | `line_half_plus` | 51 | 0 | 51 | 0 | 41 | 30-11 | +16.74 | +40.8% |
| `lean_market_against_us` | `single_book_against_model` | `small_or_none` | 45 | 0 | 45 | 0 | 37 | 24-13 | +6.71 | +18.1% |
| `lean_market_with_us` | `broad_with_model` | `small_or_none` | 39 | 0 | 39 | 0 | 34 | 19-15 | +2.42 | +7.1% |
| `referee_cap_no_signal` | `no_movement_signal` | `small_or_none` | 27 | 0 | 27 | 27 | 27 | 15-12 | +5.01 | +18.6% |
| `lean_market_against_us` | `mixed_or_reversed` | `line_half_plus` | 31 | 0 | 31 | 0 | 26 | 12-14 | -5.55 | -21.3% |
| `lean_mixed` | `mixed_or_reversed` | `small_or_none` | 36 | 0 | 36 | 0 | 25 | 11-14 | -4.48 | -17.9% |
| `lean_market_with_us` | `single_book_with_model` | `small_or_none` | 16 | 0 | 16 | 0 | 13 | 7-6 | +0.93 | +7.1% |
| `lean_market_against_us` | `mixed_or_reversed` | `odds_20c_plus` | 10 | 0 | 10 | 0 | 8 | 4-4 | -0.22 | -2.8% |
| `lean_mixed` | `mixed_or_reversed` | `odds_20c_plus` | 10 | 0 | 10 | 0 | 8 | 3-5 | -2.32 | -29.0% |
| `lean_market_with_us` | `mixed_or_reversed` | `small_or_none` | 13 | 0 | 13 | 0 | 7 | 4-3 | +0.14 | +2.0% |
| `lean_market_against_us` | `mixed_or_reversed` | `small_or_none` | 10 | 0 | 10 | 0 | 7 | 4-3 | +0.70 | +10.0% |
| `lean_market_with_us` | `single_book_with_model` | `odds_20c_plus` | 8 | 0 | 8 | 0 | 6 | 4-2 | +1.50 | +25.0% |
| `lean_market_with_us` | `mixed_or_reversed` | `odds_10_19c` | 8 | 0 | 8 | 0 | 5 | 5-0 | +3.63 | +72.6% |
| `lean_mixed` | `mixed_or_reversed` | `odds_10_19c` | 8 | 0 | 8 | 0 | 5 | 2-3 | -1.35 | -27.0% |
| `lean_market_with_us` | `mixed_or_reversed` | `odds_20c_plus` | 5 | 0 | 5 | 0 | 5 | 1-4 | -3.20 | -64.0% |
| `lean_market_against_us` | `single_book_against_model` | `odds_10_19c` | 6 | 0 | 6 | 0 | 4 | 2-2 | -0.39 | -9.8% |
| `lean_market_with_us` | `single_book_with_model` | `line_half_plus` | 5 | 0 | 5 | 0 | 4 | 3-1 | +1.89 | +47.2% |
| `lean_market_against_us` | `broad_against_model` | `line_half_plus` | 4 | 0 | 4 | 0 | 4 | 3-1 | +2.96 | +74.0% |
| `lean_market_against_us` | `single_book_against_model` | `odds_20c_plus` | 4 | 0 | 4 | 0 | 4 | 2-2 | +0.18 | +4.5% |
| `lean_market_with_us` | `single_book_with_model` | `odds_10_19c` | 4 | 0 | 4 | 0 | 4 | 3-1 | +0.88 | +22.0% |
| `referee_cap_market_against_us` | `single_book_against_model` | `small_or_none` | 4 | 0 | 4 | 4 | 4 | 3-1 | +2.04 | +51.0% |
| `referee_cap_market_with_us` | `broad_with_model` | `small_or_none` | 4 | 0 | 4 | 4 | 4 | 1-3 | -2.02 | -50.5% |
| `lean_market_against_us` | `mixed_or_reversed` | `odds_10_19c` | 5 | 0 | 5 | 0 | 3 | 1-2 | -0.86 | -28.7% |
| `referee_cap_market_against_us` | `mixed_or_reversed` | `line_half_plus` | 3 | 0 | 3 | 3 | 3 | 1-2 | -0.64 | -21.3% |
| `referee_cap_market_against_us` | `mixed_or_reversed` | `odds_20c_plus` | 3 | 0 | 3 | 3 | 3 | 2-1 | +1.08 | +36.0% |
| `referee_cap_market_with_us` | `mixed_or_reversed` | `line_half_plus` | 3 | 0 | 3 | 3 | 3 | 1-2 | -1.04 | -34.7% |
| `lean_market_against_us` | `single_book_against_model` | `line_half_plus` | 3 | 0 | 3 | 0 | 2 | 2-0 | +2.05 | +102.5% |
| `lean_market_against_us` | `broad_against_model` | `odds_10_19c` | 2 | 0 | 2 | 0 | 2 | 0-2 | -2.00 | -100.0% |

## Referee Cap Buckets

| Tracker Bucket | Referee Relationship | Strength | Magnitude | Rows | FIRE | LEAN | Ref Caps | Graded | W-L | PnL | ROI |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `referee_cap_no_signal` | `model_fades_favorite` | `no_movement_signal` | `small_or_none` | 30 | 3 | 27 | 30 | 30 | 18-12 | +8.19 | +27.3% |
| `referee_cap_market_against_us` | `model_fades_favorite` | `mixed_or_reversed` | `odds_20c_plus` | 4 | 1 | 3 | 4 | 4 | 3-1 | +2.14 | +53.5% |
| `referee_cap_market_against_us` | `model_fades_favorite` | `single_book_against_model` | `small_or_none` | 4 | 0 | 4 | 4 | 4 | 3-1 | +2.04 | +51.0% |
| `referee_cap_market_with_us` | `model_fades_favorite` | `broad_with_model` | `small_or_none` | 4 | 0 | 4 | 4 | 4 | 1-3 | -2.02 | -50.5% |
| `referee_cap_market_against_us` | `model_fades_favorite` | `mixed_or_reversed` | `line_half_plus` | 3 | 0 | 3 | 3 | 3 | 1-2 | -0.64 | -21.3% |
| `referee_cap_market_with_us` | `model_fades_favorite` | `mixed_or_reversed` | `line_half_plus` | 3 | 0 | 3 | 3 | 3 | 1-2 | -1.04 | -34.7% |
| `referee_cap_mixed` | `model_fades_favorite` | `mixed_or_reversed` | `line_half_plus` | 2 | 0 | 2 | 2 | 2 | 2-0 | +1.94 | +97.0% |
| `referee_cap_market_against_us` | `model_fades_favorite` | `broad_against_model` | `odds_20c_plus` | 1 | 0 | 1 | 1 | 1 | 1-0 | +1.10 | +110.0% |
| `referee_cap_market_with_us` | `model_fades_favorite` | `mixed_or_reversed` | `odds_10_19c` | 1 | 0 | 1 | 1 | 1 | 0-1 | -1.00 | -100.0% |
| `referee_cap_market_with_us` | `model_fades_favorite` | `mixed_or_reversed` | `odds_20c_plus` | 1 | 0 | 1 | 1 | 1 | 0-1 | -1.00 | -100.0% |
| `referee_cap_market_with_us` | `model_fades_favorite` | `single_book_with_model` | `small_or_none` | 1 | 0 | 1 | 1 | 1 | 0-1 | -1.00 | -100.0% |
| `referee_cap_mixed` | `model_fades_favorite` | `mixed_or_reversed` | `small_or_none` | 1 | 0 | 1 | 1 | 1 | 1-0 | +0.96 | +96.0% |
| `referee_cap_no_signal` | `model_fades_favorite` | `mixed_or_reversed` | `small_or_none` | 1 | 0 | 1 | 1 | 1 | 1-0 | +1.14 | +114.0% |

## Read Rule

- `movement_agreement_label` asks whether live market movement moved with or against the model side.
- `movement_strength_label` separates broad multi-book support from single-book or reversed noise.
- `movement_magnitude_bucket` separates line moves from small price-only moves.
- Referee-cap buckets are review flags. They do not override the referee or promote LEANs automatically.
- Wait for enough graded slates before treating any bucket as a decision rule.
