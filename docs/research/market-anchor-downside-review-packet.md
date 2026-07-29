# Market-Anchor Downside Review Packet

Date: 2026-07-29

Status: **Keep shadow. No downside canary draft.**

This packet is research-only. It does not authorize `enforce_downside`, a
verdict, model, threshold, stake, provider, notification, lock, artifact, UI,
retention, environment-variable, or source-of-truth change.

## Decision

Keep `MARKET_ANCHOR_SELECTOR_MODE=shadow`. The paired downside signal is
slightly positive, but the exact cohort is still too small, one-sided, and
poorly attributed to justify a separate production-canary draft.

The production-shaped hybrid rebuild through July 28 contains `3,434` side
rows, `1,793` tracked rows, zero duplicate dataset keys, and `1,750/1,750`
graded-pick reconciliation. Within the selector's June 16–July 28 audit
window, all `743/743` tracked rows carry stored selector metadata.

## Exact downside cohort

One post-start candidate was excluded before scoring. The remaining exact
pre-start cohort contains `48` rows:

| Read | Rows | Record | Current displayed PnL | Downside delta |
| --- | ---: | ---: | ---: | ---: |
| Full paired cohort | 48 | 27-21 | -0.763u | +0.763u |
| Current-provider window | 41 | 21-20 | -4.632u | +4.632u |
| Latest 14 slates | 24 | 13-11 | -1.714u | +1.714u |

The full result represents `21.000u` of avoided losses offset by `20.237u` of
foregone wins. The maximum positive one-slate contribution is `2.000u`.
That is useful evidence that the downside hypothesis is plausible, not a large
enough margin to ignore concentration and attribution.

## Gates still closed

- Cohort count is `48/50`.
- Side balance is `48` OVER and `0` UNDER; the required `10` per side is not met.
- All rows are FIRE 1u and minus-price.
- Provider attribution is missing on `48/48`; market agreement is missing on
  `45/48`. The local compact enrichment used for this reconstruction ended
  July 13, so the next scheduled runner must refresh those fields before the
  attribution read is trusted.
- Normal-workload rows are `27-19` but `-1.237u`, and the clean-quality slice
  is `5-1` yet would have foregone `3.268u`.
- The `5.5` and `6.5` K-line slices would have foregone `1.054u` and `2.356u`.

## Recommendation

Do not wait for merely two more same-profile picks and then promote. Continue
collecting until the cohort has meaningful UNDER representation and refreshed
provider/agreement attribution. Re-run the exact paired audit after the next
complete 14-slate window. A future `draft_separate_canary` result still
requires Tyler approval and a new activation plan.

