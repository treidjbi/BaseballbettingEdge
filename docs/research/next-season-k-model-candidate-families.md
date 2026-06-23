# Next Season K Model Candidate Families

Research-only. This document does not change live behavior.

## Projection Candidates

1. `current_model`: existing K/9 + SwStr + lineup + umpire + park + bias model.
2. `market_shrink_15`, `market_shrink_25`, `market_shrink_35`: shrink current lambda toward posted K line.
3. `market_anchor_selector`: market-implied K plus baseball adjustment.
4. `path_b_lineup_splits`: use live PA-backed split rates where available with Path A fallback.
5. `workload_temper`: shrink projection when pregame workload/leash label is fragile.
6. `seasonality_prior`: shrunk month/regime prior validated against MLB-wide starter K environment.

## Selection Candidates

1. `keep_fire`: retained FIRE after confidence/profit-rescue caps.
2. `clv_supported_proxy`: runtime-safe proxy for rows that later beat close.
3. `market_supported_lean`: LEAN rows with broad or durable market support.
4. `high_edge_skeptic`: high raw edge rows contradicted by market/no-vig/workload.
5. `fire_under_brake`: FIRE unders with runtime-safe warning stack.
6. `no_bet_default`: explicit pass when no positive selector fires.

## Timing Candidates

1. `bet_now`: price/line is available and market support is fresh.
2. `wait_for_lineup`: projected-lineup or missing split context suppresses early betting.
3. `shop_only`: model likes side but best executable book differs from official ref.
4. `ignore_noise`: one-book or reversed movement with no broad support.

## Required Proof For Any Candidate

- Walk-forward positive result.
- Survives over/under.
- Survives K-line buckets.
- Survives plus/minus price.
- Survives FIRE/LEAN/raw-verdict slices.
- Survives quality gate and data maturity slices.
- Survives Path B coverage and fallback slices.
- Survives market-agreement and CLV-target slices.
- Does not depend on hindsight-only fields.
- Has one rollback flag in a future canary plan.
