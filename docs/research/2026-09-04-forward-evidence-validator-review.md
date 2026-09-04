# Offline forward-evidence validator review

September 4, 2026. **Implemented and verified offline. Capture remains inactive;
formal prospective credit is zero.**

The [validator](../../analytics/diagnostics/forward_pregame_evidence_validator.py)
implements the [approved contract](../superpowers/specs/2026-09-04-forward-pregame-evidence-contract.md)
using a separate [serialization profile](forward-pregame-evidence-profile-v1.md).
It reads local packets, replays exact market evidence and existing V2 selector/
proof logic, validates pregame source availability, and checks later history
and close attachments separately. It imports no runtime recorder, writer or
post-grading runner. It does not change the existing adapter or scoring math.

## Acceptance evidence

| Check | Result | Interpretation |
| --- | --- | --- |
| New validator tests | 76 passed | Positive, boundary, missingness, conflict, retry, recovery, manifest and file-safety cases |
| Relevant combined regression suites | 357 passed | Includes existing adapter, V2 proof/market/selector, Gate C, selective LEAN and history repair tests |
| Saved synthetic scenarios | 20 | Eight pass input-candidate checks; twelve are correctly diagnostic/excluded |
| Old adapter packet | All 352 rows rejected as the prior schema | Includes its 19 previously linked matches; no field filling or back-credit |
| Old full V2 capture | All 327 rows rejected as the prior schema | Historical freezes remain unchanged |
| Original adapter reproduction | Exact output and source-file hashes still match | Still 309 linked records, 19 linked matches and zero credit |
| Real activation / formal credit | Inactive / **0** | Synthetic activation declarations are tests only |

Eight passing scenarios include against, mixed and observed-neutral market
states, both sides, real/mixed/fallback/no-lineup Path B contexts, and an
identical retry. These demonstrate evidence handling; they are fabricated
test cases and provide no predictive or profitable-selection evidence.

Failures keep reason codes and the capture inventory. A known frozen selector
match remains visible when market evidence is unavailable. Conflicting retries
and reused source IDs quarantine the identity; missing captures stay in the
denominator. Pushes and voids remain visible outside the win/loss count.

The initial tests failed before the module existed. Added adversarial tests
then exposed missing window-identity binding, absent/contradictory seed proof,
misattributed or relabeled closes, and a frozen row allegedly inserted after
the containing envelope had completed. Those validator gaps were fixed and
the final suites passed. The
[executed notebook](evidence/2026-09-04-forward-evidence-validator/checks.ipynb)
regenerates the synthetic inputs, verifies saved outputs, checks old-source
hashes and reproduces the existing proof limitation below.

## Existing V2 proof limitation remains unresolved

A complete-input synthetic case produces **score -1, label
`weak_preclose_clv_proxy`** through the existing V2 scorer. However,
`_preclose_state_valid` in the
[existing proof module](../../market_infra/alternative_pick_evaluation_proof_v2.py)
requires every integer in a group containing `score` to be nonnegative. The
proof builder consequently emits an `evaluation_proof_invalid` diagnostic
pending record. Its selector inputs are no longer complete.

The new validator excludes that case as `frozen_preclose_pending` and preserves
the original reason. It does not clamp the score, invent normalized inputs,
modify V2 validation, or select only positive evidence. Nonnegative weak
labels and known adverse/neutral evidence can pass the new validator; this
does **not** establish support for all mathematically valid weak scores.

This is an observed inconsistency between the existing scorer and proof
format, independent of whether a candidate wins. The probe does not show how
many live rows it affected; that attribution was not measured. The preserved
327 historical proofs cannot be repaired or credited from this synthetic test.

**Next decision:** review a narrowly scoped, research-only proof-format repair
proposal before capture integration. It should allow valid signed scores
without weakening nonnegative counts or other proof checks, preserve scoring
weights/thresholds and historical records, and prove negative/zero/positive
score round-trips plus malformed-count exclusions. This review authorizes no
such runtime change. A capture proposal must also address the already-known
page-cap/immaturity reasons with measured bounded reads, not relaxed guards.

## Operating and evidence boundaries

The stored inactive reference manifest has no activation time, first slate,
capture sink or release commit. The validator can check a synthetic activation
declaration, but every output permanently sets formal credit to zero and
performs no baseline portfolio audit or promotion decision.

Receipt hashes prove the enclosed bytes and their declared chronology are
internally consistent. They do not authenticate an external service's actual
persistence time, count receipt, source path or review approval. Before any
live capture, the integration packet must demonstrate trusted acquisition and
immutable persistence, its exact source-to-witness mappings and inventory,
sink/read bounds, measured resource use, failure isolation and rollback. No
physical hosted sink has been chosen by this work.

Recorded P&L is separate outcome context; the validator does not recompute
returns or allocate fees, slippage or operating costs. It checks final-CLV
attribution and the existing bucket calculation using the supplied exact quote.
None of the synthetic returns is a real trade or an eligible prospective row.
Operational reliability was not refreshed during this offline implementation.

Retain the validator, original adapter and frozen controls. Continue the
recommendation to pause repetitive promotion readouts while input gaps remain.
Revisit on proof-format acceptance and a bounded capture proposal; count growth
alone is insufficient. Model, UI and infrastructure lanes retain their own
decisions. All original research gates and historical records remain intact.

- [Implementation plan and completion record](../superpowers/plans/2026-09-04-forward-evidence-validator.md)
- [Acceptance results and source hashes](evidence/2026-09-04-forward-evidence-validator/run/acceptance.json)
- [Synthetic input packets](evidence/2026-09-04-forward-evidence-validator/run/synthetic-inputs.json.gz)
- [Inactive local reference manifest](evidence/2026-09-04-forward-evidence-validator/run/inactive-reference-manifest.json)
- [Commands and evidence inventory](evidence/2026-09-04-forward-evidence-validator/README.md)
- [Final test output](evidence/2026-09-04-forward-evidence-validator/test-results.txt)

Work is isolated on `codex/research-decision-time-adapter`. No merge,
deployment, capture, schema migration, scheduled integration, production
module/settings change, notification, retention action or history write was
performed.
