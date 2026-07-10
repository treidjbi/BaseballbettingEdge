# Strict Runtime Core Plus Selective LEAN Canary Packet

Date: 2026-07-10

Status: read-only canary-review candidate packet. This does not approve live
changes to model math, thresholds, staking, provider order, notifications,
locks, retention, dashboard source of truth, or `formula_change_date`.

## Executive Decision

Escalate `strict_runtime_core_plus_selective_lean` from generic watchlist item
to canary-review candidate.

This is the aggressive unit-accumulation candidate. It gives up the smallest
sample purity of the higher-conviction watch policy in exchange for more
baseball-season volume and the largest historical unit total among the
runtime-safe policy shapes now under review.

Primary lens: total units over a long season.

Guardrail lens: ROI, current-provider survival, recent-window survival, and
known negative slices.

The 2026-07-10 post-grading refresh matters because the candidate gained units
on a losing tracked slate. The normal 2026-07-09 tracked card lost `-2.639u`,
while the selector added three qualifying rows, went `2-1`, and gained
`+0.75u`. That is not production proof, but it is strong enough to stop treating
this as passive research.

## Historical Record

Clean Gate C window: 2026-04-28 through 2026-07-09.

| Policy | Picks | Record | Units | ROI | FIRE | LEAN |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Current tracked baseline | 1,478 | 730-748 | -106.34u | -7.2% | n/a | n/a |
| Current FIRE-only baseline | 605 | 304-301 | -35.48u | -5.9% | 605 | 0 |
| `strict_runtime_core_plus_selective_lean` | 225 | 140-85 | +30.18u | +13.4% | 85 | 140 |
| Broad no-hindsight no-drag composite | 171 | 114-57 | +27.27u | +16.0% | 85 | 86 |
| Higher-conviction watch composite | 133 | 85-48 | +20.10u | +15.1% | 29 | 104 |

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

- It keeps meaningful volume: 225 historical picks, not a tiny precision slice.
- It flips the post-formula baseline from -106.34u to +30.18u in the same clean
  review window.
- It has enough LEAN expansion to matter: 140 of the 225 candidate rows are
  selective LEAN rows.
- It still beats the current FIRE-only baseline by a wide margin: +30.18u
  versus -35.48u.
- It keeps the narrower policies as guardrails, not as the starting point.

## Current Survival Checks

The first current-provider and recent reads are positive:

| Slice | Picks | Record | Units | ROI |
| --- | ---: | ---: | ---: | ---: |
| Current-provider slice | 44 | 29-15 | +9.55u | +21.7% |
| Recent slice | 44 | 29-15 | +9.55u | +21.7% |

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

## Frozen Selector Contract

The canary review should freeze the policy exactly as named in
`analytics/diagnostics/shadow_signal_synthesis_lab.py`:

- Selector id: `strict_runtime_core_plus_selective_lean`.
- Runtime-safe inputs only: Strong Base strict retained FIRE labels plus
  Strong Base selective LEAN labels.
- No final CLV, actual result, postgame opportunity, or closing-line hindsight
  can define whether a live row qualifies.
- Market agreement, pre-close proxy, CLV/proxy, workload, Path B, and quality
  labels are review slices and guardrails, not hidden selector inputs.

If the selector definition changes, the canary review must restart with a new
id and a fresh record. Do not quietly mutate the candidate under the same name.

## Canary Review Shape

Run this as a report-only canary candidate:

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
4. The daily brief calls out the selector when it gains units on losing tracked
   slates or loses units while the tracked slate wins.
5. No dashboard verdict, stake, pick, provider, notification, or lock behavior
   changes until Tyler separately approves a live canary.

## Disabled Live-Canary Shape

If Tyler approves the next step, the first live implementation should be
disabled or metadata-only by default:

- Proposed flag: `STRICT_RUNTIME_CORE_SELECTIVE_LEAN_MODE=off|shadow`.
- `off`: no runtime metadata and no behavior change.
- `shadow`: stamp whether each tracked side would qualify for
  `strict_runtime_core_plus_selective_lean`, plus the retained-FIRE versus
  selective-LEAN family and the known risk-slice flags.
- Explicitly not allowed in the first implementation: auto-promoting LEAN to
  FIRE, changing displayed verdicts, changing staking, changing lambda, changing
  thresholds, changing provider order, changing notifications, changing locks,
  or changing dashboard source of truth.

An `enforce` mode should not exist until a later promotion plan defines the
exact live action and Tyler approves it.

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

## Go / No-Go Metrics

Use these as the next packet's decision checks:

| Check | Go signal | No-go signal |
| --- | --- | --- |
| Full candidate | Positive units and no sharp drawdown from the 225-row base | Full candidate turns flat/negative or profit concentrates in one fragile slice |
| Current-provider | Positive through at least 75 graded candidate rows, unless Tyler accepts earlier risk | Current-provider slice falls below breakeven before reaching 75 rows |
| Recent window | Positive over the latest 14 slates and not carried by one outlier slate | Recent window loses despite full-history strength |
| FIRE vs LEAN | Retained FIRE and selective LEAN are both non-negative, or selective LEAN clearly pays for the expansion | LEAN expansion alone becomes the drag |
| Side and K-line | No single side or K-line bucket explains most of the profit | One side/K-line slice is materially negative and large enough to matter |
| Price | Plus and minus price buckets are either both acceptable or the weak bucket is explicitly excluded | `+100 to +119` stays materially negative without exclusion |
| CLV/proxy | Worse-close and weak-preclose rows are bounded or excluded | Worse-close / weak-preclose rows keep leaking units |
| Path B / quality | Candidate survives Path B and quality-gate capped/clean splits | Candidate only works in low-quality or pre-lineup rows |
| Market agreement | Agreement-with-model remains supportive and agreement-against does not drive losses | Agreement-against rows dominate the losing slice |

## Next Work

The next implementation step is a separate disabled-shadow plan, not a live
flip: add metadata-only runtime tagging for this frozen selector after Tyler
approves the exact `off|shadow` flag shape. Until then, continue the daily
post-grading refresh and treat this packet as the canary-review source of
truth.
