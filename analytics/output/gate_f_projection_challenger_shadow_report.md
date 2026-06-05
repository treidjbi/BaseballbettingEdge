# Gate F Projection Challenger Shadow Report

Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, calibration, locks, or dashboard artifacts.

## Decision Summary

| Candidate | Status | Reason | Rows | MAE Delta | RMSE Delta | Side Accuracy Delta | Positive Rolling Windows | Bad Slices | FIRE 2u Degradation |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `market_shrink_15` | `blocked_mae_lift_too_small` | holdout MAE lift < 0.025 | 227 | -0.010 | -0.015 | +0.000 | 2 | 0 | no |
| `market_shrink_25` | `blocked_mae_lift_too_small` | holdout MAE lift < 0.025 | 227 | -0.015 | -0.021 | +0.000 | 2 | 0 | no |
| `market_shrink_35` | `blocked_mae_lift_too_small` | holdout MAE lift < 0.025 | 227 | -0.017 | -0.024 | +0.000 | 2 | 0 | no |
| `high_line_temper` | `blocked_mae_lift_too_small` | holdout MAE lift < 0.025 | 227 | -0.005 | +0.000 | +0.003 | 1 | 1 | no |
| `leash_cap` | `blocked_mae_lift_too_small` | holdout MAE lift < 0.025 | 227 | +0.006 | +0.004 | -0.007 | 0 | 2 | no |
| `handedness_bucket_adjust` | `blocked_hindsight_only` | candidate uses hindsight-only inputs | 227 | +0.001 | +0.001 | +0.000 | 1 | 0 | no |

## Read Rule

- `promotion_plan_candidate` means draft a later production plan; it does not approve live lambda.
- `blocked_hindsight_only` candidates can stay in research but cannot drive pre-lock behavior.
- Slice failures and FIRE 2u degradation block production-plan discussion even when aggregate MAE improves.
