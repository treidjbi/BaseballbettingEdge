# Gate F Projection Challenger Shadow Report

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, calibration, locks, or dashboard artifacts.

## Decision Summary

| Candidate | Status | Reason | Rows | MAE Delta | RMSE Delta | Side Accuracy Delta | Positive Rolling Windows | Bad Slices | FIRE 2u Degradation |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `market_shrink_15` | `promotion_plan_candidate` | Gate F shadow standards passed | 745 | -0.044 | -0.060 | +0.000 | 25 | 0 | no |
| `market_shrink_25` | `promotion_plan_candidate` | Gate F shadow standards passed | 745 | -0.070 | -0.094 | +0.000 | 25 | 0 | no |
| `market_shrink_35` | `promotion_plan_candidate` | Gate F shadow standards passed | 745 | -0.094 | -0.125 | +0.000 | 25 | 0 | no |
| `high_line_temper` | `blocked_mae_lift_too_small` | holdout MAE lift < 0.025 | 745 | -0.003 | -0.005 | -0.001 | 18 | 1 | no |
| `leash_cap` | `blocked_mae_lift_too_small` | holdout MAE lift < 0.025 | 745 | +0.016 | +0.026 | -0.009 | 1 | 5 | no |
| `handedness_bucket_adjust` | `blocked_hindsight_only` | candidate uses hindsight-only inputs | 745 | +0.000 | +0.000 | +0.000 | 26 | 0 | no |

## Read Rule

- `promotion_plan_candidate` means draft a later production plan; it does not approve live lambda.
- `blocked_hindsight_only` candidates can stay in research but cannot drive pre-lock behavior.
- Slice failures and FIRE 2u degradation block production-plan discussion even when aggregate MAE improves.
