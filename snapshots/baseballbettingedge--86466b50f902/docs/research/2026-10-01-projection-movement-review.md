# Frozen 2026 projection, line and movement review

Date: 2026-10-01. Offline analysis only; no APIs, fresh grading, provider calls, or production changes. Reproduce from the repository root with `python3 analytics/reviews/2026-10-01/projection/review.py`. The script reads the frozen corpus and writes only its review directory. Full monthly, Monday-start weekly, pitcher-team, opposing-team, line, probability and movement tables are in that directory.

## Decision

The model was almost unbiased in aggregate but less accurate than the published betting line. Its chosen-side probabilities were substantially too optimistic. Improving average K projections is a credible research direction; it does not by itself solve betting profitability. The strongest first target for 2027 research is calibrated probabilities and prices on identical decision-time populations, followed by selection and stake conversion. Do not build team exclusion rules or promote movement/CLV filters from these retrospective slices.

## Evidence identity and limits

- Frozen Gate C corpus: `data/research/gate_c/pitcher_k_outcome_dataset.jsonl`.
- SHA-256: `4b44d70d1bcae23be35354ec9ea9b84886f62642c4900fd56c4e65817748a8cd`; checked against the manifest by the script.
- April 28–September 27: 5,488 side rows, exactly 2,744 distinct pitcher/date observations; every observation contains one OVER and one UNDER. Projection, actual Ks, line and game time agree between each pair. We count each pair once for projection accuracy.
- All rows are `official_close` context. This compares retained final-artifact projections and lines against already recorded actual Ks. It is **not** proof that every value was available at selection/lock time.
- These are selected covered pitcher markets, not all MLB starts. Team cuts describe that population.
- 2,893 research side rows are marked tracked. They include recovered/descriptive research rows and must not be substituted for the published 2,777 settled picks. Their probabilities/results use their corpus market line. Their linked history PnL can refer to the tracked line; movement-PnL tables are descriptive attached-history summaries, not independently regraded results.
- No number here is Tyler's actual betting-account result. That requires a complete accepted-bet ledger.

## Projection accuracy

Bias is forecast minus actual; lower MAE/RMSE is better. A betting line is a useful simple benchmark, not a literal expected-K forecast (market medians, discrete lines and juice matter).

| Forecast | Mean Ks | Bias | MAE | RMSE |
| --- | ---: | ---: | ---: | ---: |
| Recorded actual | 4.926 | — | — | — |
| Current model | 4.966 | +0.040 | 1.876 | 2.349 |
| Published betting line | 4.833 | -0.093 | 1.785 | 2.210 |
| 15% toward line | 4.946 | +0.020 | 1.844 | 2.306 |
| 25% toward line | 4.933 | +0.007 | 1.825 | 2.281 |
| 35% toward line | 4.920 | -0.006 | 1.808 | 2.260 |

These full-corpus shrink comparisons are descriptive hindsight calculations, not a fresh holdout or a simulated betting strategy. The model has lower MAE than the line in only 3 of 22 Monday-start weeks and none of the six calendar-month slices. Near-zero full-season bias conceals substantial individual forecast error.

| Month | Pitcher dates | Model bias | Model MAE | Line MAE |
| --- | ---: | ---: | ---: | ---: |
| April 28–30 | 63 | +0.007 | 1.942 | 1.722 |
| May | 636 | +0.095 | 1.807 | 1.772 |
| June | 598 | +0.049 | 1.891 | 1.799 |
| July | 470 | -0.161 | 1.934 | 1.840 |
| August | 538 | +0.033 | 1.796 | 1.706 |
| September through 27 | 439 | +0.179 | 1.983 | 1.830 |

The September 21 week had the largest model MAE (2.245, 116 pitcher dates), against 2.000 for the line. Team comparisons are available for all pitcher teams and opponents. Illustratively, the Texas pitcher-team sample has high model MAE (2.254, 88) but the line is slightly worse (2.261), so high error is not necessarily a model-specific defect. Against the White Sox, Royals and Mariners, model biases are +0.581, +0.510 and +0.526 Ks, respectively; those are exploratory workload/opponent-calibration leads, not validated betting exclusions.

Retained shadow challenger metadata yields 1,605 paired unique pitcher dates: current-lambda MAE 1.8896 versus would-lambda MAE 1.8339, a 0.0558-K improvement. That is consistent with the frozen report, but does not identify profitable would-bet decisions. The separate frozen Gate F holdout remains the source for its own candidate eligibility; these full-season calculations do not replace its protocol.

## Probability versus actual outcomes

Brier score is mean squared probability error; lower is better. The all-market comparison uses OVER once per pitcher date to avoid double counting mirrored sides.

| Population | n | Mean model probability | Actual win rate | Mean no-vig market probability | Model Brier | Market Brier |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| All market OVER rows | 2,744 | 47.61% | 49.93% | 49.40% | 0.2670 | 0.2445 |
| Tracked research OVER | 1,270 | 59.55% | 49.69% | 49.44% | 0.2654 | 0.2441 |
| Tracked research UNDER | 1,623 | 61.68% | 49.97% | 50.66% | 0.2668 | 0.2448 |

Independent checks rule out a side-sign or push-counting explanation: every retained line is a half-integer, zero actual outcomes equal their line, all 5,488 win/loss labels agree with actual Ks versus the side's line, and opposing model probabilities sum to one within rounding. Of 2,893 tracked research rows, 2,855 are exact-line matches and 38 match only pitcher/side at a changed line. Excluding those 38 leaves OVER forecast 59.58% versus 49.52% wins (1,252) and UNDER forecast 61.83% versus 49.91% wins (1,603). Thus changed-line matches do not explain the optimism. Exact-line matching still does not establish original probability availability or reconciliation to the narrower official published settled population.

The selected research populations have roughly 10–12 percentage points of probability optimism. This is a more direct warning than mean K bias: the system selected supposedly favorable tails that did not win at the forecast rate. At common negative odds, a roughly 50% hit rate loses money. However, isolate final-artifact probabilities from original locked probabilities before attributing all of this to the runtime model. Do not equate these research rows with actual accepted bets.

## Movement and CLV: suggestive, incompletely attributed

All 5,488 rows have retained opening/current odds and a simple side-price movement label. **None** has `line_movement` or `market_agreement_label`. Therefore this corpus cannot support a complete time-series movement, steam/reversal or market-agreement season audit. The label is defined by a raw American-odds difference of at least 10; it is not probability-point movement, and sign crossings distort its magnitude threshold.

| Tracked research price label | Rows | Recorded win rate | Attached history PnL |
| --- | ---: | ---: | ---: |
| With side | 717 | 54.95% | -0.05u (716 PnL rows) |
| Against side | 454 | 46.70% | -43.88u |
| Unchanged / below threshold | 1,722 | 48.55% | -142.06u (1,720 PnL rows) |

Moving with the side is associated with a better hit rate, but the attached PnL is approximately flat. Prices and when a bet could actually be taken remain central. Final movement is hindsight and cannot be used as a runtime predictor without pre-lock inputs.

Gate C's naive retained CLV labels show price-only (338 rows, +15.82u attached history), line-only (22, +4.72u), and no positive CLV edge (2,533, -206.53u on 2,530 PnL rows). **These are not validated execution CLV.** The builder compares linked locked odds with final artifact odds without enforcing same book, same provider, exact event and after-lock close provenance; 187 tracked rows have different bet-time and artifact book labels. “No CLV edge” also combines neutral and worse cases. Do not mix these counts with the separately defined CLV-supported research bucket.

The canonical CLV process review documents only 33 fully attributed targets from August 25–26, reconciled to 42 consumed locks with nine excluded gaps. That historical two-slate receipt is not season-wide coverage. Missing close provenance stays unknown. Do not promote the naive Gate C CLV labels into a 2027 filter.

## Next offline tests

1. Pair frozen original decision-time projection, exact line/odds and recorded actual Ks; quantify missing/late provenance before modeling. Original selection probabilities and final-artifact probabilities must have separate labels.
2. Compare current projection, line benchmark and predeclared shrink candidates on identical observations. Include paired time-block uncertainty, probability reliability, tails, expected-versus-realized return, and actual attainable prices.
3. Reconstruct explicit fixed-stake would-bet decisions with stated thresholds, price handling and exposure. Report changes in selection/turnover; do not award promotion solely for lower MAE.
4. Decompose errors by month/week, pitcher team and opposing team, workload and K line. Shrink small slices toward the full population and treat the explored 2026 season as discovery, not untouched confirmation.
5. For TheRundown-only 2027, specify economical timestamped decision/close captures from existing scheduled data. Historical PropLine data remains research evidence, but a predictor dependent on canceled PropLine cannot be a future runtime requirement. Any collection/restart needs the separately reviewed authorization.

All outputs are reproducible from the frozen source and retain dormancy. No model, odds source, staking, threshold or notification promotion follows from this review.

## Drilldown data contract

`analytics/reviews/2026-10-01/projection/pitcher_game_comparison.csv` and `.json` contain all 2,744 unique observations with date, pitcher, pitcher team, opponent, projected Ks, betting line, actual Ks, signed model/line errors, OVER probability, and both side odds. Source aliases are explicit: `date = slate_date`, `opponent = opp_team`, `line = k_line`; errors equal forecast/line minus actual. OVER probability and odds come from the OVER row; UNDER odds come from its exact paired UNDER row. Team/opponent agreement is asserted between paired rows. Team names are preserved as the corpus's 30 full MLB team names (including `Athletics`), with no inferred abbreviation mapping. These are final-artifact quoted odds, not accepted execution prices.
