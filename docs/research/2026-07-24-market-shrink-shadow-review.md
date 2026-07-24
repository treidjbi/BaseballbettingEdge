# Market-Shrink Projection Review

Evidence through July 23, 2026

## Executive Summary

- **Decision: keep `market_shrink_25` in `shadow`; do not enable `enforce`.** The market-shrink family improves projection error, but the evidence does not yet show a profitable behavior-changing selection rule.
- **Gate F accuracy evidence is strong enough for continued candidate review.** On the `430`-row validation holdout, all three shrink weights improve MAE and RMSE, pass `11` rolling windows, show zero bad slices, and do not degrade FIRE 2u alignment.
- **Accuracy lift has not translated into betting lift.** The `499` graded tracked rows carrying shadow metadata are `250-249`, `-28.84u`; because the challenger was applied on zero rows, this is not an enforced-candidate result.
- **The missing analysis is the decision delta.** A separate counterfactual must isolate rows whose EV, verdict, or unit would actually change under enforcement before a live lambda change can be considered.

## Projection error improves without changing directional accuracy

The fresh Gate C rebuild contains `3,232` graded side rows from April 28 through
July 23. The projection lab has `1,616` official-close rows; the stricter Gate F
validation holdout contains `430` rows.

| Projection | Official-close MAE | Official-close RMSE | Side accuracy | Holdout MAE delta | Holdout RMSE delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| Current model | 1.866 | 2.342 | 52.5% | — | — |
| `market_shrink_15` | 1.839 | 2.307 | 52.5% | -0.030 | -0.036 |
| `market_shrink_25` | 1.822 | 2.287 | 52.5% | -0.049 | -0.056 |
| `market_shrink_35` | 1.808 | 2.271 | 52.5% | -0.066 | -0.074 |

The shrink family pulls lambda toward the posted K line, reducing the size of
projection misses. It does not improve directional accuracy in this sample.
All three candidates retain `11` positive validation windows, zero bad slices,
and no FIRE 2u degradation, so `promotion_plan_candidate` remains a fair Gate F
research label. That label opens a separate review; it is not approval to
change live lambda.

## Current shadow outcomes do not measure an enforced strategy

The runtime canary has `956` rows with `market_shrink_25` shadow metadata,
`956` changed would-have lambdas, and zero applied rows. Its `499` graded
tracked rows finished `250-249`, `-28.84u`, `-5.8%` ROI.

| Current tracked cohort with metadata | Rows | Record | Flat PnL | ROI |
| --- | ---: | ---: | ---: | ---: |
| FIRE 1u | 57 | 34-23 | +1.31u | +2.3% |
| LEAN | 421 | 205-216 | -32.19u | -7.6% |
| Clean quality | 251 | 135-116 | +3.59u | +1.4% |
| Capped quality | 248 | 115-133 | -32.42u | -13.1% |
| OVER | 180 | 93-87 | -5.23u | -2.9% |
| UNDER | 319 | 157-162 | -23.59u | -7.4% |

These outcomes describe the existing tracked portfolio while shrink metadata
was present. They cannot be credited to the challenger because shadow mode
preserved the current lambda, EV, and verdict. They do show why lower
projection error alone is not a sufficient promotion argument: price,
selection, and verdict conversion still determine betting value.

The projection lab reaches the same caution from another angle. The current
model and all three shrink candidates align with the same `656` tracked rows,
which finished `335-321`, `-28.61u`. Simple shrink usually leaves the
projection on the same side of the line, so it can improve MAE without changing
the bet.

## Recommended next review

1. Keep `MARKET_SHRINK_PROJECTION_MODE=shadow` and candidate
   `market_shrink_25`; do not enable `enforce`.
2. Build a read-only counterfactual that recalculates probability, EV, quality
   gates, referee decisions, and final verdict under the would-have lambda.
3. Score only the rows whose verdict or exposure would actually change, with
   current behavior as the paired control.
4. Require that decision-changing cohort to survive over/under, plus/minus,
   K-line, FIRE 1u/FIRE 2u, quality, timing, model/market, Path B, workload,
   CLV, provider, and rolling-window slices.
5. Set the prospective sample floor and rollback criteria in a separate
   Tyler-approved review plan rather than inferring them from the current
   metadata cohort.

## Further questions

- Which shrink weight creates enough genuine decision changes to evaluate
  without simply reproducing the current picks?
- Does the MAE improvement persist in later, provider-attributed windows?
- Does the counterfactual improve calibration and expected-value ranking, not
  just absolute K error?
- Are the losses concentrated in rows that an enforced shrink would remove, or
  in rows it would leave unchanged?

## Caveats and assumptions

- The Gate F holdout has `430` rows, below the plan's default `800`-row
  discussion standard unless Tyler accepts a smaller personal-use review.
- `promotion_plan_candidate` means a separate plan may be drafted; it does not
  mean promotion-ready or profitable.
- PnL is flat-unit research PnL from current tracked selections, not the
  counterfactual PnL of enforcement.
- The fresh rebuild and reports were generated read-only from the approved
  hybrid artifact path. They did not change production artifacts, lambda,
  parameters, providers, notifications, locks, dashboard behavior, or history.
- Controlling gates remain in
  `docs/superpowers/plans/2026-06-03-gate-f-projection-challenger-shadow-plan.md`
  and
  `docs/superpowers/plans/2026-06-22-market-shrink-projection-production-canary.md`.

