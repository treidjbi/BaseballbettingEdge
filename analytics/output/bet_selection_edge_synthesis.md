# Bet Selection And Edge Synthesis

Generated at: `2026-06-10T04:22:06.062349+00:00`

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, or dashboard source-of-truth.

## Executive Read

- Total source rows: `1662`
- Clean tracked win/loss rows analyzed: `854`
- Useful next decision: use this as Gate E research evidence for which bet-selection contexts deserve deeper Gate F challenger testing.
- Bill James-style component thinking is reflected here as a diagnostic frame: do not judge edge from ERA/surface outcomes; compare strikeout skill, workload, market price, no-vig gap, CLV, and postgame opportunity separately.

## Gate Read

- Gate E remains the research-readiness gate for candidate labels and bet-selection slices.
- Gate F remains the promotion-candidate gate; no slice in this report can change live selection without holdout, rolling-window, side, K-line, FIRE/LEAN, CLV, workload, Path B, and market-agreement review.

## Verdict

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `FIRE 1u` | 412 | 412 | 0 | 206-206 | -23.89 | -5.8% | 47 | 5 |
| `LEAN` | 318 | 0 | 318 | 167-151 | -2.19 | -0.7% | 73 | 11 |
| `FIRE 2u` | 124 | 124 | 0 | 59-65 | -10.17 | -8.2% | 11 | 0 |

## Side

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `under` | 473 | 305 | 168 | 235-238 | -28.90 | -6.1% | 72 | 10 |
| `over` | 381 | 231 | 150 | 197-184 | -7.35 | -1.9% | 59 | 6 |

## Edge Buckets

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `edge_6_plus` | 425 | 359 | 66 | 209-216 | -32.75 | -7.7% | 30 | 4 |
| `edge_lt_2` | 222 | 56 | 166 | 119-103 | +4.29 | +1.9% | 86 | 8 |
| `edge_2_to_4` | 111 | 40 | 71 | 60-51 | +2.90 | +2.6% | 6 | 3 |
| `edge_4_to_6` | 96 | 81 | 15 | 44-52 | -10.69 | -11.1% | 9 | 1 |

## EV Buckets

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `adj_ev_6_to_17` | 368 | 314 | 54 | 185-183 | -17.55 | -4.8% | 43 | 9 |
| `adj_ev_17_plus` | 268 | 221 | 47 | 128-140 | -19.79 | -7.4% | 29 | 1 |
| `adj_ev_lt_6` | 218 | 1 | 217 | 119-99 | +1.09 | +0.5% | 59 | 6 |

## Edge By EV

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `edge_6_plus | adj_ev_17_plus` | 254 | 213 | 41 | 121-133 | -20.25 | -8.0% | 22 | 1 |
| `edge_6_plus | adj_ev_6_to_17` | 166 | 146 | 20 | 85-81 | -13.34 | -8.0% | 7 | 3 |
| `edge_lt_2 | adj_ev_lt_6` | 146 | 1 | 145 | 79-67 | +1.61 | +1.1% | 56 | 4 |
| `edge_4_to_6 | adj_ev_6_to_17` | 91 | 80 | 11 | 42-49 | -9.58 | -10.5% | 7 | 1 |
| `edge_lt_2 | adj_ev_6_to_17` | 65 | 48 | 17 | 34-31 | +1.11 | +1.7% | 25 | 4 |
| `edge_2_to_4 | adj_ev_lt_6` | 64 | 0 | 64 | 35-29 | -2.27 | -3.5% | 2 | 2 |
| `edge_2_to_4 | adj_ev_6_to_17` | 46 | 40 | 6 | 24-22 | +4.26 | +9.3% | 4 | 1 |
| `edge_lt_2 | adj_ev_17_plus` | 11 | 7 | 4 | 6-5 | +1.56 | +14.2% | 5 | 0 |
| `edge_6_plus | adj_ev_lt_6` | 5 | 0 | 5 | 3-2 | +0.84 | +16.9% | 1 | 0 |
| `edge_4_to_6 | adj_ev_lt_6` | 3 | 0 | 3 | 2-1 | +0.90 | +29.8% | 0 | 0 |
| `edge_4_to_6 | adj_ev_17_plus` | 2 | 1 | 1 | 0-2 | -2.00 | -100.0% | 2 | 0 |
| `edge_2_to_4 | adj_ev_17_plus` | 1 | 0 | 1 | 1-0 | +0.91 | +90.9% | 0 | 0 |

## Candidate Labels

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `baseline_watch` | 344 | 168 | 176 | 180-164 | -11.94 | -3.5% | 0 | 0 |
| `high_edge_skeptic` | 326 | 262 | 64 | 160-166 | -20.18 | -6.2% | 24 | 4 |
| `clv_supported` | 101 | 24 | 77 | 56-45 | +7.44 | +7.4% | 92 | 9 |
| `fire_under_watch` | 58 | 58 | 0 | 22-36 | -10.69 | -18.4% | 13 | 3 |
| `moderate_edge_clean_context` | 25 | 24 | 1 | 14-11 | -0.89 | -3.5% | 2 | 0 |

## Model Market Relationship

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `model_fades_favorite` | 425 | 260 | 165 | 192-233 | -31.79 | -7.5% | 66 | 15 |
| `model_agrees_with_favorite` | 399 | 253 | 146 | 224-175 | -4.95 | -1.2% | 63 | 1 |
| `unknown` | 30 | 23 | 7 | 16-14 | +0.49 | +1.6% | 2 | 0 |

## No-Vig Labels

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `no_vig_confirmed_edge` | 695 | 484 | 211 | 351-344 | -34.31 | -4.9% | 62 | 8 |
| `no_vig_no_edge` | 63 | 19 | 44 | 34-29 | +1.15 | +1.8% | 29 | 1 |
| `no_vig_thin_edge` | 57 | 19 | 38 | 28-29 | +0.46 | +0.8% | 21 | 4 |
| `no_vig_price_only_edge` | 39 | 14 | 25 | 19-20 | -3.56 | -9.1% | 19 | 3 |

## CLV Labels

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `clv_neutral_or_unknown` | 599 | 409 | 190 | 292-307 | -50.00 | -8.3% | 0 | 0 |
| `beat_close_price` | 131 | 58 | 73 | 75-56 | +13.82 | +10.5% | 131 | 0 |
| `worse_than_close_price` | 108 | 64 | 44 | 56-52 | -4.26 | -3.9% | 0 | 0 |
| `beat_close_line` | 16 | 5 | 11 | 9-7 | +4.19 | +26.2% | 0 | 16 |

## Opportunity By Actual Outing

| Bucket | Rows | FIRE | LEAN | W-L | PnL | ROI | Beat close price | Beat close line |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `normal | normal_outing` | 420 | 248 | 172 | 209-211 | -19.54 | -4.7% | 68 | 11 |
| `normal | short_outing` | 141 | 79 | 62 | 81-60 | +13.08 | +9.3% | 20 | 3 |
| `normal | deep_outing` | 135 | 86 | 49 | 63-72 | -19.58 | -14.5% | 19 | 0 |
| `deep_starter | normal_outing` | 55 | 39 | 16 | 31-24 | +3.61 | +6.6% | 13 | 1 |
| `short_leash | normal_outing` | 32 | 27 | 5 | 17-15 | -0.37 | -1.1% | 4 | 1 |
| `short_leash | deep_outing` | 30 | 25 | 5 | 14-16 | -3.69 | -12.3% | 2 | 0 |
| `deep_starter | short_outing` | 28 | 23 | 5 | 9-19 | -11.17 | -39.9% | 1 | 0 |
| `deep_starter | deep_outing` | 9 | 5 | 4 | 5-4 | +0.54 | +6.0% | 3 | 0 |
| `short_leash | short_outing` | 4 | 4 | 0 | 3-1 | +0.88 | +21.9% | 1 | 0 |
