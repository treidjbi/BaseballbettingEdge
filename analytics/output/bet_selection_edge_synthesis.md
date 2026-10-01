# Bet Selection And Edge Synthesis

Generated at: `2026-10-01T15:00:30.014755+00:00`

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, or dashboard source-of-truth.

## Executive Read

- Total source rows: `5488`
- Clean tracked win/loss rows analyzed: `2893`
- Useful next decision: use this as Gate E research evidence for which bet-selection contexts deserve deeper Gate F challenger testing.
- Bill James-style component thinking is reflected here as a diagnostic frame: do not judge edge from ERA/surface outcomes; compare strikeout skill, workload, market price, no-vig gap, CLV, and postgame opportunity separately.

## Gate Read

- Gate E remains the research-readiness gate for candidate labels and bet-selection slices.
- Gate F remains the promotion-candidate gate; no slice in this report can change live selection without holdout, rolling-window, side, K-line, FIRE/LEAN, CLV, workload, Path B, and market-agreement review.

## Verdict

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `LEAN` | 1980 | 0 | 1980 | 973-1007 | -142.70 | -7.2% | 258 | 14 |
| `FIRE 1u` | 665 | 665 | 0 | 346-319 | -31.05 | -4.7% | 69 | 7 |
| `FIRE 2u` | 132 | 132 | 0 | 62-70 | -12.28 | -9.3% | 11 | 1 |
| `PASS` | 116 | 0 | 0 | 61-55 | -1.28 | -1.1% | 0 | 0 |

## Side

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `under` | 1623 | 315 | 1257 | 811-812 | -118.11 | -7.3% | 186 | 14 |
| `over` | 1270 | 482 | 723 | 631-639 | -69.21 | -5.5% | 152 | 8 |

## Edge Buckets

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `edge_6_plus` | 1565 | 542 | 1023 | 744-821 | -166.56 | -10.6% | 134 | 7 |
| `edge_lt_2` | 562 | 63 | 383 | 286-276 | -20.73 | -3.7% | 148 | 11 |
| `edge_2_to_4` | 403 | 51 | 352 | 215-188 | -4.61 | -1.1% | 27 | 3 |
| `edge_4_to_6` | 363 | 141 | 222 | 197-166 | +4.58 | +1.3% | 29 | 1 |

## EV Buckets

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `adj_ev_6_to_17` | 1090 | 479 | 611 | 558-532 | -49.90 | -4.6% | 112 | 9 |
| `adj_ev_17_plus` | 1026 | 313 | 713 | 478-548 | -109.36 | -10.7% | 104 | 4 |
| `adj_ev_lt_6` | 777 | 5 | 656 | 406-371 | -28.05 | -3.6% | 122 | 9 |

## Edge By EV

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `edge_6_plus | adj_ev_17_plus` | 1011 | 305 | 706 | 471-540 | -108.83 | -10.8% | 97 | 4 |
| `edge_6_plus | adj_ev_6_to_17` | 531 | 236 | 295 | 263-268 | -53.31 | -10.0% | 34 | 3 |
| `edge_lt_2 | adj_ev_lt_6` | 475 | 4 | 355 | 243-232 | -18.61 | -3.9% | 110 | 7 |
| `edge_4_to_6 | adj_ev_6_to_17` | 345 | 140 | 205 | 189-156 | +7.01 | +2.0% | 27 | 1 |
| `edge_2_to_4 | adj_ev_lt_6` | 264 | 0 | 264 | 145-119 | -5.61 | -2.1% | 9 | 2 |
| `edge_2_to_4 | adj_ev_6_to_17` | 138 | 51 | 87 | 69-69 | +0.08 | +0.1% | 18 | 1 |
| `edge_lt_2 | adj_ev_6_to_17` | 76 | 52 | 24 | 37-39 | -3.68 | -4.9% | 33 | 4 |
| `edge_6_plus | adj_ev_lt_6` | 23 | 1 | 22 | 10-13 | -4.41 | -19.2% | 3 | 0 |
| `edge_4_to_6 | adj_ev_lt_6` | 15 | 0 | 15 | 8-7 | +0.57 | +3.8% | 0 | 0 |
| `edge_lt_2 | adj_ev_17_plus` | 11 | 7 | 4 | 6-5 | +1.56 | +14.2% | 5 | 0 |
| `edge_4_to_6 | adj_ev_17_plus` | 3 | 1 | 2 | 0-3 | -3.00 | -100.0% | 2 | 0 |
| `edge_2_to_4 | adj_ev_17_plus` | 1 | 0 | 1 | 1-0 | +0.91 | +90.9% | 0 | 0 |

## Candidate Labels

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline_watch` | 1273 | 277 | 880 | 661-612 | -51.94 | -4.1% | 0 | 0 |
| `high_edge_skeptic` | 1244 | 371 | 873 | 581-663 | -131.65 | -10.6% | 107 | 7 |
| `clv_supported` | 222 | 37 | 185 | 120-102 | +3.58 | +1.6% | 210 | 12 |
| `moderate_edge_clean_context` | 94 | 52 | 42 | 58-36 | +5.38 | +5.7% | 8 | 0 |
| `fire_under_watch` | 60 | 60 | 0 | 22-38 | -12.69 | -21.1% | 13 | 3 |

## Model Market Relationship

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `model_agrees_with_favorite` | 1431 | 481 | 887 | 789-642 | -58.27 | -4.1% | 176 | 3 |
| `model_fades_favorite` | 1371 | 275 | 1045 | 602-769 | -134.82 | -9.8% | 155 | 18 |
| `unknown` | 91 | 41 | 48 | 51-40 | +5.77 | +6.3% | 7 | 1 |

## No-Vig Labels

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_vig_confirmed_edge` | 2518 | 739 | 1776 | 1254-1264 | -174.61 | -6.9% | 225 | 11 |
| `no_vig_no_edge` | 211 | 22 | 83 | 105-106 | -12.92 | -6.1% | 49 | 4 |
| `no_vig_thin_edge` | 105 | 20 | 81 | 53-52 | +1.92 | +1.8% | 37 | 4 |
| `no_vig_price_only_edge` | 59 | 16 | 40 | 30-29 | -1.71 | -2.9% | 27 | 3 |

## CLV Labels

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `clv_neutral_or_unknown` | 2272 | 625 | 1531 | 1122-1150 | -170.22 | -7.5% | 0 | 0 |
| `beat_close_price` | 338 | 80 | 258 | 187-151 | +15.82 | +4.7% | 338 | 0 |
| `worse_than_close_price` | 261 | 84 | 177 | 121-140 | -37.64 | -14.4% | 0 | 0 |
| `beat_close_line` | 22 | 8 | 14 | 12-10 | +4.72 | +21.5% | 0 | 22 |

## Opportunity By Actual Outing

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `normal | actual_outing_unknown` | 2260 | 611 | 1560 | 1128-1132 | -143.62 | -6.3% | 273 | 20 |
| `deep_starter | actual_outing_unknown` | 331 | 128 | 185 | 166-165 | -16.57 | -5.0% | 39 | 1 |
| `short_leash | actual_outing_unknown` | 302 | 58 | 235 | 148-154 | -27.13 | -9.0% | 26 | 1 |
