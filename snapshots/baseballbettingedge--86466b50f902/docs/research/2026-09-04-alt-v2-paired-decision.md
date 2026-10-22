# Alt V2 paired decision — September 4, 2026

Later September 4 [lineage follow-up](2026-09-04-research-lineage-decision.md):
Kumar Rocker's missing row has an unconsumed operational lock; MLB confirms
3 strikeouts, but the existing consumed-lock repair contract excludes it.
Historical Gate C hash provenance is resolved through CRLF reconstruction.
Neither finding changes the frozen Alt results or retirement decisions below.

**Retire Consensus Core and Re-entry Expansion from active promotion research;
retain their frozen records as comparison controls.** Neither has demonstrated
incremental selection value. This is a decision about research attention, not
a command to disable runtime collection, change the Alt tab, or alter betting
behavior. No production setting, model, staking, threshold, provider,
notification, retention, or history is changed.

Current source reads were captured September 4 at 21:58–22:01Z. The closed
evaluation window is July 24–September 3: 42 slate dates. September 4's open
slate is excluded. This completes the **75-frozen-pick formal paired review**
in the [original review cadence](../superpowers/specs/2026-07-21-pregame-alternative-pick-methodology-design.md#review-cadence),
under the [V2 dependency-aware contract](../superpowers/specs/2026-07-22-alt-picks-dependency-aware-v2-design.md).
It does not complete the separate Gate C provenance or consumed-lock research
linkage work recommended in the [operating assessment](2026-09-04-operating-and-research-assessment.md).

## Evidence classes and cost convention

- **Historical research:** the V2 design quotes the earlier hindsight-capable
  comparator: Consensus 106–46/+32.603u, Re-entry 42–38/+5.982u, combined
  +38.585u. These are not prospective V2 freezes and are not pooled below.
- **Prospective decisions:** 113 immutable `frozen_pregame` V2 selections,
  each made before first pitch and joined to its consumed operational lock.
  All 113 pass the existing evaluation-proof validator with the same frozen
  fingerprint. Current canonical history supplies the later outcomes.
- **Counterfactual exposure:** the tables score those prospectively selected
  rows at **1u risk per selection at its locked odds**. Mainline FIRE is scored
  at its recorded verdict size; all 91 FIREs here are 1u. The all-tracked
  comparator assumes 1u even on LEANs. These are paper portfolios, not evidence
  of accepted bets or actual executed returns. Post-outcome slices and CLV
  partitions are descriptive, not prospective selectors.

A win returns odds/100 at positive odds or 100/abs(odds) at negative odds; a
loss is -1u and a void 0u. ROI divides by nonvoid risk units. Recorded prices
capture the offered payout, including the effect of bookmaker pricing; vig
is not subtracted again. **Fees, slippage, missed execution and allocated
provider/hosting costs are unmeasured.** No fully costed net-profit claim is
available. Additional nonnegative execution/operating costs would worsen the
negative totals. The frozen prices are not a best-book shopping simulation.

## Paired portfolio comparison

| Same date window | Rows | W–L–void | P&L u | ROI on settled risk |
| --- | ---: | --- | ---: | ---: |
| Mainline displayed FIRE | 91 | 47–44–0 | -9.085 | -9.98% |
| All closed locked mainline rows, flat including LEAN | 726 | 365–358–3 | -43.490 | -6.02% |
| Common frozen-V2 universe, flat | 719 | 361–355–3 | -44.321 | -6.19% |
| **Alt V2 combined** | **113** | **49–63–1** | **-24.889** | **-22.22%** |
| Consensus Core | 77 | 38–38–1 | -11.090 | -14.59% |
| Re-entry Expansion | 36 | 11–25–0 | -13.799 | -38.33% |
| V2 not selected, graded | 589 | 304–284–1 | -18.443 | -3.14% |
| V2 pending, graded | 17 | 8–8–1 | -0.988 | -6.17% |

The 720 frozen V2 states contain 113 selected, 590 not selected and 17 pending.
One not-selected outcome is missing; seven additional graded operational locks
have no frozen V2 state. Neither group is silently classified as a successful
or failed Alt selection. Alt coverage is 113/720 frozen states (15.69%), or
113/727 operational locks (15.54%).

The exact overlap makes the exposure difference explicit:

| Portfolio component | Rows | W–L–void | P&L u |
| --- | ---: | --- | ---: |
| Alt selections already displayed FIRE | 26 | 14–12–0 | -1.979 |
| Alt's additional LEAN selections | 87 | 35–51–1 | -22.910 |
| Mainline FIRE omitted by Alt | 65 | 33–32–0 | -7.106 |

Replacing mainline FIRE with the combined Alt paper portfolio changes P&L by
**-15.804u**, while increasing nonvoid risk from 91u to 112u. That is an
observed portfolio contrast, not a causal estimate at equal risk. The overlap
has slightly less-negative ROI than all FIRE, but it does not establish a
profitable filter; most Alt exposure adds losing LEANs. Mainline itself is
negative, so this review does not validate the production selection policy.

## Separate lane decisions

### Consensus Core: retire active promotion path

**Frozen hypothesis:** no-drag support plus at least two distinct affirmative
families identifies stronger selections than the mainline opportunity set.
The exact formula is `no_drag AND family_count >= 2`, where
`no_drag = (base_support OR market_anchor_strict) AND NOT drag_core`.
The Base, Anchor, Preclose and Re-entry predicates and thresholds remain in
the [frozen manifest](../../market_infra/alternative_pick_selector_manifest_v2.json).
Distinct family names do not establish statistical independence: the votes
share model, market and quality inputs.

**Prospective eligibility:** the V2 bundle/fingerprint, exact candidate and
source-artifact binding, pregame freeze, immutable operational-lock line/odds,
and semantically sufficient family proof must agree. Required unknown inputs
stay pending. A nonessential pending Preclose family may not veto a decision
already proven by the other families. All 77 selected Consensus records pass;
76 have nonvoid outcomes.

**Sample and diversity:** the contract calls for the bundle's formal review
at 75 freezes or season end; it does not specify a separate numerical floor
for each lane or each slice. Consensus now has 77 rows, 35 selected slate dates
and 63 pitchers, with no pitcher contributing more than three rows. It covers
38 OVER and 39 UNDER, but **zero plus-price or model-fade selections**. All
77 are `pre_30`, with actual lock lead times about 24.25–29.86 minutes. These
are narrow-contract observations, not broad price/timing validation.

**Result and attribution:** -11.090u/-14.59%; OVER -7.117u and UNDER -3.972u.
Both clean quality (42/-6.488u) and capped quality (35/-4.602u) lose. Exact
source is TheRundown on 74 rows/-11.406u and PropLine on only 3/+0.317u; those
three rows cannot establish a provider advantage. Path B has 12 all-real
split rows/-0.384u, 64 mixed/fallback rows/-10.705u and one unmatched-context
void. All selected workload inputs are complete; the seven deep-starter
opportunity rows are positive, but that is a small hindsight partition.

Only 2 of 29 overlapping complete 14-slate windows are positive. Removing any
single slate leaves total P&L between -12.572u and -7.090u. The latest common
window, August 21–September 3, is 10–13/-6.116u. These checks show the loss is
not explained by one slate; they are not independent replications or a formal
test proving negative true expected value.

**Decision:** retire V2 Consensus as an active promotion candidate, keep its
unchanged frozen control, and stop routine searches for a winning price,
pitcher or line subset inside this sample. Missing diversity and incomplete
CLV attribution do not justify promoting a losing candidate or extending it
indefinitely just to accumulate more rows.

### Re-entry Expansion: retire active promotion path

**Frozen hypothesis:** source-FIRE moderate-edge, clean-quality selections
outside no-drag recover useful opportunities suppressed by other controls.
The exact formula is `reentry_support AND NOT no_drag`. The unchanged re-entry
predicate requires source FIRE, `0.02 <= edge < 0.06`, adjusted EV `<0.17`,
model/no-vig gap `>=0.04`, clean/none quality and no large-edge-skepticism flag,
with all required inputs present. This is disjoint from Consensus.

**Prospective eligibility:** the same V2 identity, immutable freeze, exact
lock and sufficient-proof contract applies; unresolved no-drag cannot be
treated as false. All 36 selected rows pass and have graded nonvoid outcomes.
Irrelevant missing Preclose evidence is not a disqualifier for this lane.

**Sample and diversity:** 36 rows on 25 dates and 29 pitchers, maximum three
rows per pitcher; 18 OVER/18 UNDER, 27 plus-price/9 minus-price, 34 model fades
and 2 agreements. All are clean quality, complete workload, TheRundown exact
source and `pre_30` timing. The lane has **not** independently reached 75 rows;
the governing trigger is the combined methodology review, not a lane-level
promotion entitlement. No new sample threshold is invented here.

**Result and attribution:** 11–25, -13.799u/-38.33%. OVER -7.995u and UNDER
-5.805u; plus prices -12.360u and minus prices -1.439u. Both all-real Path B
(8/-3.914u) and mixed/fallback (28/-9.885u) lose. Normal, deep-starter and
short-leash opportunity buckets all lose. The one displayed FIRE wins
+0.885u, while the 35 incremental LEANs lose -14.684u. This is especially weak
evidence for restoring capped exposure.

Zero of 29 complete 14-slate windows are positive. Removing any single slate
leaves -15.745u to -10.799u. The latest August 21–September 3 window is
3–11/-7.620u. These observations support stopping promotion effort despite
the smaller lane sample; they do not prove the lane could never improve by
chance in future observations.

**Decision:** retire V2 Re-entry as an active promotion candidate. Preserve its
frozen comparison record; do not loosen the predicate, promote its LEANs, or
start another post-hoc variant from its few winning subgroups.

## CLV, required slices and unresolved attribution

[Every required slice and all 29 rolling windows](evidence/2026-09-04-alt-v2-decision/required-slices.md)
are retained for both lanes, combined Alt, all mainline locks and mainline
FIRE. They include side, K line, price sign, official verdict, exact provider
and provider posture, Path B, workload/opportunity/leash, quality, timing,
model/market, book and CLV. Unknown values stay visible. Mainline posture may
come from a lock-consistent dated archive; selected Alt posture comes from the
frozen record. Broader posture is not the exact quote's source.

The bounded close export targets only these 113 selected rows and returns 458
snapshots; none reaches its 101-row per-target cap. It filters by exact
provider/event/name/side/book and pregame time, **not by locked line**. The
existing offline close producer requires an exact quote within 20 minutes
before lock, then a same-provider/event/book close after lock, before game,
and within 20 minutes of first pitch. Official provider attribution is taken
from the frozen proof, not the stale local Gate C file.

| Lane | Accepted close | Beat price | Neutral | Worse price | Unknown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Consensus | 58/77 | 17 | 36 | 5 | 19 |
| Re-entry | 32/36 | 1 | 26 | 5 | 4 |
| Combined | 90/113 | 18 | 62 | 10 | 23 |

No accepted close changes line. The 23 exclusions comprise 22 missing exact
pre-lock provenance snapshots and one missing pregame close; ten targets have
no snapshots at all. Retained raw coverage is incomplete and those absences
are not neutral CLV. Consensus beats price more often than it loses price in
the accepted subset, but its beat-price rows still lose 4.911u. That describes
timing, not demonstrated predictive value. This selected-only packet does
not update the separate 100-target CLV process gate or establish full-mainline
CLV coverage. It is not accepted-bet execution CLV.

The remaining limits are material to interpretation:

1. **One canonical-history omission:** August 19 Kumar Rocker UNDER 4.5 at
   -138, operational lock `dabe1657-2a2d-4bbd-a708-4fdc6bd3e9a3`, has no matching
   current history row. It is an unselected LEAN. The denominator is 726/727
   operational locks, not complete history. No result is inferred from an
   unfinished archive. A loss/win would move the all-tracked total to between
   -44.490u and -42.765u; it cannot affect Alt or mainline FIRE. Reconcile this
   exact exception separately; do not repeat a blanket history repair.
2. **Path B is contextual:** 725/726 graded locks have a dated-archive tracked
   pick matching the exact time, line, odds and verdict. Selected coverage is
   112/113; the unmatched row is the August 1 Reynaldo López void. The archived
   pitcher features were published later and are not proven frozen covariates.
   Do not interpret these slices as a causal estimate of Path B's effect.
3. **Proof integrity is bounded:** the existing validator checks the preserved
   proof's schema, identity and semantic sufficiency. The original full
   `today.json` bytes for every freeze were not independently reconstructed.
   Stored artifact hashes and SQL/source snapshots remain available for audit.
4. **Dependence and selection remain:** repeated pitchers, correlated family
   inputs and overlapping windows preclude counting every row/window as an
   independent experiment. We have not run a multiplicity-corrected test or
   estimated a causal provider, model-math or feature contribution. The
   retirement decision is about the lack of useful demonstrated value and
   further research cost, not proof that true expected value is below zero.

## What happens next

| Work | Treatment now | Next decision and evidence | Revisit trigger |
| --- | --- | --- | --- |
| Consensus V2 | Retire active promotion path; retain frozen control | Reopen only for an exact evidence correction that changes this result, or a separately justified new hypothesis with a new fingerprint and untouched future holdout | Documented reconciliation changes the conclusion, or Tyler opens a separately reviewed research proposal; a positive hindsight slice or generic count growth is insufficient |
| Re-entry V2 | Retire active promotion path; retain frozen control | Same requirement, with an explicit reason suppressed source-FIRE exposure should improve after costs | Same evidence-led trigger; do not wait for an invented 75-row lane quota |
| Routine Alt scoreboards and subgroup searches | Recommend pausing recurring promotion-oriented review | Keep integrity/freeze failure checks and the fixed decision packet; collection and display continue unchanged | Contract violation, season-end control summary under the existing cadence, or a separately approved reopening |
| Research data reliability | Next bounded work item | Read-only Gate C file/manifest/hosted lineage reconciliation; design exact consumed-lock joins and investigate the Kumar omission | Current manifest mismatch, structural zero eligibility or a reproducible history omission; any history write/repair is separately scoped |
| Other research candidates | Retain existing frozen gates | Strict core, high-edge FIRE cap, anchor downside and selective LEAN still require their own current attributed evidence | Their controlling sample/diversity/attribution gates; this Alt decision provides no cross-lane promotion |

The operating posture remains Watch as assessed earlier today. This research
packet adds one bounded history-completeness exception; it does not establish
a current grading outage. Daily operations should focus on fresh publication,
grading, consumed locks and sender failures. No additional polling, provider
spend, raw retention, scheduled jobs or production settings are changed.

## Reproduction and verification

[Evidence inventory and exact captured SQL](evidence/2026-09-04-alt-v2-decision/README.md)
· [Executed companion notebook](evidence/2026-09-04-alt-v2-decision/decision-checks.ipynb)
· [Offline reproduction script](evidence/2026-09-04-alt-v2-decision/reproduce.py)
· [Machine-readable analysis and checks](evidence/2026-09-04-alt-v2-decision/analysis.json)
· [Close packet and explicit exclusions](evidence/2026-09-04-alt-v2-decision/official-close-packet.json).

Checks passed: 113/113 semantic proofs, unique joins, selected pregame timing,
exact consumed-lock/hash/price/line/verdict agreement, 726 graded-history lock
reconciliations, outcome-to-actual-K arithmetic, and bounded close provenance.
The existing proof and close-producer suites passed **105 tests**. Offline
reproduction changes only this packet's derived files. Historical records,
prior assessments and their earlier count/window definitions are preserved.
