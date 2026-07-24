# Market-Anchor Shadow Review

Evidence through July 23, 2026

## Executive Summary

- **Decision: keep the selector in `shadow`; do not enable `enforce_downside`.** The existing selector has cleared the raw floor for a separate review, but it has not cleared the mandatory side, K-line, CLV, workload, provider, and market-agreement gates.
- **The strict shape is materially better than the non-strict comparison.** All strict rows are `82-50`, `+7.26u`, while strict displayed FIRE is `20-7`, `+7.14u`; non-strict displayed FIRE is `23-19`, `-1.87u`.
- **The strongest result is concentrated.** Every strict displayed FIRE row is an `OVER`, and most strict rows lack provider and market-agreement attribution. This is promising research evidence, not a safe general downside-cap rule.
- **A narrower OVER-only idea would be a new candidate.** It would require a new selector id, fingerprint, baseline, plan, and prospective canary rather than a reinterpretation of the current selector.

## The signal is real enough to review, but not broad enough to enforce

The fresh hybrid Gate C rebuild contains `3,232` graded side rows and `1,686`
tracked rows from April 28 through July 23. It reconciles `1,651/1,652` clean
graded picks with zero duplicate keys; the sole unmatched row remains the
approved fail-closed Robert Gasser cross-line exception from June 3.

| Market-anchor cohort | Rows | Record | Flat PnL | ROI |
| --- | ---: | ---: | ---: | ---: |
| Strict, all | 132 | 82-50 | +7.26u | +5.5% |
| Strict, current-provider window | 92 | 59-33 | +8.96u | +9.7% |
| Strict, recent 14 slates | 48 | 31-17 | +5.39u | +11.2% |
| Strict displayed FIRE | 27 | 20-7 | +7.14u | +26.5% |
| Non-strict displayed FIRE | 42 | 23-19 | -1.87u | -4.5% |
| Strict after removing worst single slate | 128 | 78-50 | +4.32u | +3.4% |

The aggregate advantage survives removal of the best contributing slate and
is stronger in the current-provider and recent windows. That is enough to keep
the selector on the active review list. It is not enough to infer that every
current FIRE failing the strict label should be capped.

## Concentration and missing attribution remain the blockers

The required slices do not yet tell one consistent story:

| Blocking slice | Rows | Record | Flat PnL | ROI |
| --- | ---: | ---: | ---: | ---: |
| Strict `6.5` K line | 22 | 12-10 | -1.25u | -5.7% |
| Neutral or unknown final CLV | 106 | 61-45 | -3.24u | -3.1% |
| Medium pre-close CLV proxy | 18 | 9-9 | -2.78u | -15.5% |
| Weak pre-close CLV proxy | 45 | 24-21 | -3.84u | -8.5% |
| High workload | 13 | 7-6 | -1.36u | -10.4% |
| Medium workload | 4 | 2-2 | -0.48u | -11.9% |
| Post-BoltOdds-retirement provider era | 31 | 18-13 | -1.14u | -3.7% |

The strict `UNDER` cohort is `57-39`, but only `+0.69u` across `96` rows.
All `27` strict displayed FIRE rows are `OVER`, so the headline FIRE result has
no side balance. Provider and market-agreement labels are each missing on
`123/132` strict rows. Those gaps prevent a reliable answer about whether the
advantage comes from the selector itself, a specific market context, or a
concentrated slice.

## Recommended next review

1. Continue the current selector unchanged in `shadow`.
2. Re-run this packet after at least one more 14-slate window and require the
   mandatory slices to remain positive or explainably neutral.
3. Improve provider and market-agreement attribution before treating the
   current-provider result as causal evidence.
4. If the desired hypothesis is specifically an OVER-only selector, write a
   separate research plan with a new identity and prospective baseline.
5. Keep `MARKET_ANCHOR_SELECTOR_MODE=enforce_downside` closed until Tyler
   separately approves a behavior-changing plan after those checks.

## Further questions

- Does the current-provider advantage persist once most strict rows carry
  provider and market-agreement labels?
- Is strong pre-close confirmation the actual useful filter, rather than the
  broad strict label?
- Can an independently frozen candidate reproduce the OVER result
  prospectively without selecting the winning historical slice?

## Caveats and assumptions

- This is a shadow, observational review; it does not estimate the causal
  effect of enabling `enforce_downside`.
- PnL is flat-unit research PnL from the tracked prices, not a staking
  recommendation.
- The fresh rebuild was generated read-only from the approved hybrid artifact
  path. It did not change production artifacts, model behavior, providers,
  notifications, locks, dashboard behavior, or history.
- Controlling gates remain in
  `docs/superpowers/plans/2026-06-16-market-anchored-v2-selector-shadow-canary.md`.
