# Decision-time adapter implementation review — September 4, 2026

**Implemented as a standalone offline research tool.** The captured 20-slate
corpus produces 309 linked records and 19 linked selective-LEAN rule matches.
**Formal prospective credit remains zero.** These are linkage results, not
new evidence that the selector wins. Production and the scheduled research
runner are unchanged.

The [approved contract](../superpowers/plans/2026-09-04-decision-time-research-adapter.md)
controls this implementation. The [preceding lineage decision](2026-09-04-research-lineage-decision.md)
and [operational/selection assessments](2026-09-04-operating-and-research-assessment.md)
remain historical records. This review closes the adapter implementation step;
it does not refresh operational health or reopen any retired promotion path.

## Captured evidence and results

Inputs cover August 15–September 3 inclusive. The fresh SELECT-only V2 capture
at **22:48:48Z September 4** contains all 327 immutable frozen-pregame rows,
including pending and unselected states. Gate C and operational locks reuse
the preceding bounded lineage capture. This is a captured-corpus validation,
not an assertion of current hosted-run completeness.

| Measure | Observed result | Meaning |
| --- | --- | --- |
| Gate C input | 660 rows; 351 tracked sides | Untracked sides do not become candidate linkage rows |
| Operational locks | 330 | Includes Kumar Rocker's one unconsumed lock |
| Frozen V2 rows | 327; all pass the existing complete proof validator | Valid diagnostic-pending proofs can still lack usable selector inputs |
| Union of identities | 352 | Each date/pitcher/side retained, including missing-source cases |
| Validated decision inputs | 325 | Two minimal pending proofs cannot supply selector features |
| Fully linked records | 309; 43 excluded | Exact proof, consumed lock, archive quote/book/time and closed history required |
| Frozen selective-LEAN matches | 23 | Rule matches only; not formal eligibility |
| Linked frozen matches | 19; 13 dates; 18 pitchers | Descriptive diversity, not credited sample/diversity gates |
| Final-archive matches | 23; overlap with frozen set 21 | Equal counts conceal four different identities |
| Formal prospective credit | **0** | No baselines, timing, attribution or promotion rules waived |

The earlier 314-row strict lock preview becomes 309 after requiring frozen
decision inputs: Andrew Alvarez, Jacob deGrom and Peter Lambert on August 20
lack frozen rows; Randy Vasquez on August 21 and Justin Hagenman on September 2
have incomplete frozen inputs. The latter two are archive-only selector
matches. Erick Fedde on August 29 and Mason Adams on August 30 are frozen-only
matches. No archive feature fills those gaps or resolves those disagreements.

Four of the 23 frozen matches fail book linkage: Daniel Lynch IV and Tomoyuki
Sugano on August 23, Erick Fedde on August 29, and Anthony Molina on August 31.
Across all 352 identities, exclusion reasons are 25 missing frozen rows,
22 missing locks, 15 archive/lock book conflicts, eight unavailable closed
history P&L values, two incomplete frozen selector inputs, one missing Gate C
row and one unconsumed lock. Reasons overlap; they do not sum to 43.
Kumar remains excluded. No history repair was attempted.

## What the adapter establishes

The [module](../../analytics/diagnostics/decision_time_research_adapter.py)
validates the complete existing V2 proof against its persisted row, then
requires pregame insertion/freeze, freeze/lock timing, the lock's recorded
artifact byte hash, and exact quote identity. Duplicate identities or reused
source IDs are quarantined. Selector features come only from frozen normalized
inputs. Outcomes cannot change selection.

The output keeps `decision_time`, `lock_proof`, `archive_context`,
`outcome_context` and `pregame_evidence` separate. Decision-time provider
comes from the validated official binding; archived explicit official fields
are read separately. Movement-provider fields never fill official attribution.
Its nested `records` envelope is intentionally incompatible with a flat Gate C
replacement. The existing audit's provider reader is unchanged.

All 327 captured Preclose proofs remain **pending**. No frozen market-agreement
or Path B contract exists in those inputs. Later archive agreement, proxy,
Path B or workload values cannot manufacture pregame evidence. A synthetic
fresh-proof test demonstrates the supported valid branch; it is test data and
is absent from the research packet. The adapter gives no formal credit even
when a synthetic complete Preclose proof passes.

Hash equality here links recorded identifiers. It does not claim that the
served artifact's bytes reproduce every issuer/SQL JSONB hash. That separate
serialization limitation remains as documented in the lineage review. Visible
history-recovery flags cause exclusion; missing flags do not certify complete
recovery provenance.

## Predictive value, costs and next decision

No P&L is recalculated, and no new stake, fee, spread or slippage assumption is
introduced. Recorded history and theoretical P&L remain separately labeled
outcome context. Neither is measured net execution profit or profit after
allocated provider/infrastructure costs. The 19 matches must not be presented
as a new winning prospective cohort. The original 103-row nomination baseline,
frozen selective-LEAN hypothesis and sample/diversity rules remain unchanged.

**Next decision:** review a forward-only pregame evidence contract before
considering runner integration. It must specify exact decision-time agreement,
mature Preclose availability and observation bounds, frozen Path B attribution,
recovery provenance, supported official-provider fields, and a start boundary
that grants no retroactive credit. Reuse existing evidence where it genuinely
meets that contract; do not add another overlapping collector by default.

**Revisit trigger:** a reviewed contract plus captured pregame examples passing
all required inputs and negative tests, followed by a separately scoped
integration decision. More rows with the same structural gaps do not trigger
another promotion scoreboard. Retain the offline adapter and frozen controls;
keep the recommendation to pause repetitive ineligible promotion readouts.
No scheduling change has been made.

## Verification and reproduction

Test-first validation observed the initial missing-module failure, then
passing linkage tests. Additional failing adversarial tests exposed and fixed
cross-artifact hash binding, future-generated artifacts, and reused source IDs.
Final relevant regression result: **185 passed**, including **43 adapter
tests** plus existing proof, Gate C dataset, selective-LEAN and exact history
repair suites. The [executed notebook](evidence/2026-09-04-decision-time-adapter/checks.ipynb)
rebuilds the packet in memory, validates source-file hashes, verifies exact
saved-output equality, and checks the cohort differences and zero credit.

- [Machine-readable verification](evidence/2026-09-04-decision-time-adapter/verification.json)
- [Complete nested packet, lossless gzip](evidence/2026-09-04-decision-time-adapter/run/packet.json.gz)
- [Frozen source capture and exact SELECT](evidence/2026-09-04-decision-time-adapter/frozen-source.json.gz)
- [Evidence inventory and CLI reproduction](evidence/2026-09-04-decision-time-adapter/README.md)

Implementation is isolated on `codex/research-decision-time-adapter`. No model
math, staking, thresholds, provider behavior, notifications, retention,
production settings, canonical datasets, historical records or existing
runtime modules were changed. No merge or deployment is part of this release.
