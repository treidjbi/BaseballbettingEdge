# Signed-score proof compatibility review

September 4, 2026. **Recommend a paired format repair before capture integration.**
The concrete patch is tested but unapplied. This is code compatibility evidence,
not operational uptime, model accuracy or profitable selection evidence.

The existing V2 scorer can legitimately return **-1 / weak Preclose**. Python's
proof builder puts `score` into the same nonnegative-value check as book counts,
then replaces that complete proof with a minimal `evaluation_proof_invalid`
pending record. The dashboard's JavaScript reader duplicates the same restriction.
Fixing only the writer would leave the reader rejecting its output.

## Consumer scope

| Consumer | Current finding | Proposed treatment |
| --- | --- | --- |
| [Python proof builder/validator](../../market_infra/alternative_pick_evaluation_proof_v2.py) | `_preclose_state_valid` rejects negative scores before semantic equality checks | Separate signed score from nonnegative counts; preserve every other check |
| [V2 scorer](../../market_infra/alternative_pick_selector_v2.py) | Existing signed arithmetic produces -1; label remains weak | Keep weights, thresholds, families and fingerprint unchanged |
| [JavaScript endpoint validator](../../netlify/functions/alternative-picks.mjs) | `precloseContractValid` repeats the restriction; `validateV2Proof` recomputes semantics | Apply matching format repair before any paired runtime rollout |
| [Recorder](../../market_infra/alternative_pick_recording_v2.py), [serializer](../../market_infra/alternative_pick_selection_v2.py), [adapter](../../analytics/diagnostics/decision_time_research_adapter.py), [forward validator](../../analytics/diagnostics/forward_pregame_evidence_validator.py) | Reuse Python proof helpers; changing the helper can change future evidence/diagnostic availability | Regression-test these paths before implementation acceptance |
| [Repository proof migration](../../supabase/migrations/20260722230000_alternative_pick_v2_evaluation_proof.sql) | JSONB shape/size/row-binding constraints; no score-sign constraint found in repository migrations | No schema change proposed; deployed constraints and versions unverified |

The [patch](evidence/2026-09-04-signed-score-proof-review/run/proposed.patch)
changes only two shape predicates. It keeps existing finite/integral numeric
helpers, without introducing a new strict JSON integer-type policy. Both full
validators still require the recorded score, label and reasons to equal the
recomputed result; arbitrary negative scores do not become valid.

## Counterfactual acceptance

All inputs below are synthetic. September 6 dates and activation declarations
are fixture data. The harness temporarily substitutes only the Python shape
helper, restores it in `finally`, and imports two JavaScript source strings in
memory. It never invokes the endpoint handler, database writers or network.

| Case | Current full Python / JS readers | Proposed full Python / JS readers | Meaning |
| --- | --- | --- | --- |
| Complete -1 / weak proof | Both reject; Python builder emits a valid pending diagnostic instead | Both accept the complete proof | Preserve known weak evidence and its normalized inputs |
| Complete 0 / weak proof | Both accept | Both accept; generated packet unchanged | Zero remains valid |
| Complete +7 / strong proof | Both accept | Both accept; generated packet unchanged | Positive behavior preserved |
| 44 malformed/tampered cases | Both reject | Both reject | Negative/missing/Boolean/fractional/nonnumeric counts; invalid/altered scores; altered labels, reasons, freshness and time ordering stay excluded |
| NaN and positive/negative infinity | Both reject | Both reject | Three additional nonfinite cases per reader |

The three complete cases all remain Alt V2 `not_selected` with no lane. Each
synthetic envelope passes forward input-candidate checks under the in-memory
proposal; all receive **zero formal prospective credit**. A weak score becomes
observable, not favorable. Preclose remains an attribution slice for selective
LEAN, not a newly required positive filter.

The experiment deliberately retains the current disk-source manifest while
changing a helper in memory. It is a counterfactual acceptance test, **not** a
valid new implementation manifest or trusted receipt. Actual implementation
must issue new dependency hashes and acceptance evidence, preserving old packets.

## Historical and prospective boundaries

The preserved August 15–September 3 source has 327 frozen rows. Python validation
is identical before/after for all 327; all still have pending Preclose. This
does not establish how many live observations lost complete proofs because of
negative scores. Do not infer a cause for pending rows or reconstruct their
missing inputs from later data.

The original 20-case acceptance still reproduces eight input candidates and zero
formal credit. Its 352-row adapter and 327-row frozen legacy inputs remain
excluded from the new schema. Original adapter reproduction and source hashes
pass unchanged. No activation, cost-adjusted outcome or new prospective sample
is created. Capture is inactive; Kumar remains excluded; Alt V2 stays retired.

## Decision and limits

Next implement the narrowly scoped paired repair on the feature branch with
writer/serializer and full endpoint regression suites, then prepare the capture
proposal. **Do not deploy or activate capture from this review alone.** The
original task preserves production behavior; shared helpers affect runtime
evidence and potentially displayed diagnostic state even with unchanged math.

Remaining capture questions are the exact sink/read bounds, reliable acquisition
and original-seed witnesses, completeness, measured resource use, error isolation
and rollback. Deployed reader versions and database constraints need verification
before rollout. No fresh uptime or live affected-row count was measured; the
companion brief retains its dated operational evidence.

Retain this packet as a one-time regression reference. Revisit on implementation,
source drift or a proof-contract change. Repeated synthetic score probes now add
no decision information. Detailed gates are in the
[controlling plan](../superpowers/plans/2026-09-04-signed-score-proof-repair-review.md).

Evidence: [results](evidence/2026-09-04-signed-score-proof-review/run/acceptance.json),
[47 cases](evidence/2026-09-04-signed-score-proof-review/run/synthetic-rows.json.gz),
[reproducer instructions](evidence/2026-09-04-signed-score-proof-review/README.md).
