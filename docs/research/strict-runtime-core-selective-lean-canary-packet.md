# Strict Runtime Core Plus Selective LEAN Canary Packet

Date: 2026-07-09

Status: read-only canary-review packet. This does not approve live changes to
model math, thresholds, staking, provider order, notifications, locks,
retention, dashboard source of truth, or `formula_change_date`.

## Executive Decision

Build the next review around `strict_runtime_core_plus_selective_lean`.

This is the aggressive unit-accumulation candidate. It gives up the smallest
sample purity of the higher-conviction watch policy in exchange for more
baseball-season volume and the largest historical unit total among the
runtime-safe policy shapes now under review.

Primary lens: total units over a long season.

Guardrail lens: ROI, current-provider survival, recent-window survival, and
known negative slices.

## Historical Record

Clean Gate C window: 2026-04-28 through 2026-07-08.

| Policy | Picks | Record | Units | ROI | FIRE | LEAN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Current tracked baseline | 1,460 | 722-738 | -102.70u | -7.0% | n/a | n/a |
| Current FIRE-only baseline | 601 | 302-299 | -34.80u | -5.8% | 601 | 0 |
| `strict_runtime_core_plus_selective_lean` | 222 | 138-84 | +29.43u | +13.3% | 85 | 137 |
| Broad no-hindsight no-drag composite | 170 | 113-57 | +26.63u | +15.7% | 85 | 84 |
| Higher-conviction watch composite | 131 | 84-47 | +20.46u | +15.6% | 29 | 102 |

The chosen candidate is not the highest ROI slice. It is the best fit for
Tyler's stated preference: more picks and more accumulated units if the
candidate survives the next review gates.

## Candidate Definition

The policy is the union of two runtime-safe families already defined in
`analytics/diagnostics/shadow_signal_synthesis_lab.py`:

1. Retained FIRE rows from the Strong Base strict runtime core.
2. Selective LEAN rows from Strong Base expand-LEAN lanes.

It does not rely on final CLV as an input. CLV and pre-close proxy evidence are
used to audit the policy, not to define it.

## Why This Is The Right Aggressive Base

- It keeps meaningful volume: 222 historical picks, not a tiny precision slice.
- It flips the post-formula baseline from -102.70u to +29.43u in the same clean
  review window.
- It has enough LEAN expansion to matter: 137 of the 222 candidate rows are
  selective LEAN rows.
- It still beats the current FIRE-only baseline by a wide margin: +29.43u
  versus -34.80u.
- It keeps the narrower policies as guardrails, not as the starting point.

## Current Survival Checks

The first current-provider and recent reads are positive:

| Slice | Picks | Record | Units | ROI |
| --- | ---: | ---: | ---: | ---: |
| Current-provider slice | 41 | 27-14 | +8.80u | +21.5% |
| Recent slice | 45 | 29-16 | +8.16u | +18.1% |

That is strong enough to build the review packet around this policy. It is not
yet live-promotion proof because the sample still needs slice stability.

## Known Risk Slices

The synthesis report flags these negative slices inside the candidate:

| Slice | Record | Units | Read |
| --- | ---: | ---: | --- |
| Weak pre-close proxy | 7-13 | -5.46u | Timing/market confirmation risk |
| Price bucket +100 to +119 | 14-18 | -3.19u | Plus-price band needs review |
| Worse-close-price | 17-16 | -2.93u | Execution/timing risk, not a direct live input |

The aggressive approach should not immediately exclude these from the shadow
candidate. It should track the full policy first, then report the candidate
with and without these flags so Tyler can choose whether volume or cleaner
execution matters more after more slates.

## Shadow Canary Shape

Run this as a report-only canary:

1. Every post-grading run refreshes Gate C and market-agreement outputs.
2. The synthesis report records `strict_runtime_core_plus_selective_lean` as
   the preferred aggressive unit candidate.
3. The daily review reads:
   - full candidate record
   - current-provider slice
   - recent slice
   - FIRE versus LEAN split
   - side and K-line split
   - price bucket split
   - market-agreement with/against/missing split
   - pre-close proxy split
   - Path B and quality-gate split
4. No dashboard verdict, stake, pick, provider, notification, or lock behavior
   changes until Tyler separately approves a live canary.

## Promotion Packet Floor

Draft a live-canary plan only if the candidate keeps accumulating units while
the obvious risk slices stay bounded:

- Full candidate remains positive on total units.
- Current-provider slice remains positive after at least 75 graded candidate
  rows, or Tyler explicitly accepts earlier risk.
- Recent 14-slate slice remains positive.
- LEAN expansion remains positive separately from retained FIRE.
- No single mandatory slice explains most of the profit.
- Known weak slices are either improved, explicitly excluded, or accepted as
  volume tradeoffs.
- Market-agreement-against rows are not silently driving losses.

## Next Work

The next implementation step is still read-only: extend daily review output so
`strict_runtime_core_plus_selective_lean` is the named candidate and the report
shows the unit-first watch items above. After that, run at least the next two
graded slates before deciding whether to draft a feature-flagged live canary.
