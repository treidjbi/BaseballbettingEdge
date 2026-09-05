# Signed-score proof repair review

Date: September 4, 2026. Branch: `codex/research-decision-time-adapter`.
Status: **Review complete; paired patch proposed and tested in memory only.**

## Decision and scope

Following the [completed offline validator](2026-09-04-forward-evidence-validator.md),
review the existing negative-score rejection before choosing capture integration.
The justified next implementation is a paired Python/JavaScript proof-format
repair on an isolated branch, with regression tests and a new dependency manifest.
The [exact proposed patch](../../research/evidence/2026-09-04-signed-score-proof-review/run/proposed.patch)
is an evidence artifact, **not applied code**. This review does not authorize
deployment, a live writer, new capture, historical repair or prospective credit.

The user requires unchanged production behavior. Both affected files serve
runtime consumers, so this review tests source strings in memory and leaves
the actual files unchanged. No model math, score weights, label thresholds,
selector fingerprint, staking, providers, notifications, retention or settings
change. Alt V2 promotion paths remain retired. The existing forward contract
and all dated evidence remain intact.

## Required repair behavior

- In Python `_preclose_state_valid` and JavaScript `precloseContractValid`,
  separate `score` from the nonnegative count fields. Require a finite integral
  score under each existing numeric helper; do not clamp or take its absolute
  value. Preserve semantic recomputation and exact score/label/reason checks.
- Keep all six observation/book/direction/reversal/volatility counts nonnegative,
  maturity and identity rules strict, and pending aggregates null. Preserve
  existing scalar coercion semantics; a new scalar-type policy is outside scope.
- Change both readers together. A Python-only release produces proofs the current
  dashboard validator rejects. Existing representable proofs must remain identical.
- Never regenerate old pending freezes. The recorded population is not a repair
  backlog or evidence that 327 rows suffered this particular bug.

## Completed evidence

The [review](../../research/2026-09-04-signed-score-proof-review.md) and
[reproducer](../../research/evidence/2026-09-04-signed-score-proof-review/reproduce.py)
verify 47 shared cases against both full proof validators: valid scores -1, 0
and +7, plus 44 malformed/tampered cases. Both reject three additional nonfinite
score cases. The three valid cases remain `not_selected` in Alt V2; their synthetic
forward envelopes each pass input checks but receive zero formal credit.

All 327 captured proofs validate identically before/after and retain pending
Preclose. The original 20-case offline acceptance and historical adapter reproduce
unchanged. The live affected-row count and deployed schema/reader versions have
not been measured. Repository SQL review found no score-sign constraint; this
is not a live database compatibility test.

## Next decision and revisit trigger

Next decide whether to implement this exact paired format repair on the feature
branch. Acceptance must include the Python proof/selection/recording and Node
endpoint suites, these signed-score/adversarial cases, unchanged legacy behavior,
unchanged scorer/selector fingerprints and a separately issued dependency manifest.
Preserve previous manifest/packet bytes rather than regenerating old acceptance
under new source hashes.

After implementation acceptance, prepare the bounded capture proposal: actual
sink and source mappings, immutable acquisition receipts, original ungraded seed
witness, complete paginated reads, measured request/storage use, failure isolation
and rollback. This review does not establish those properties. Keep capture
inactive and real activation fields null until that separate review. A future
runtime rollout needs both deployed readers verified at the approved revision;
rollback disables new capture and restores the paired readers without deleting
or rewriting already preserved evidence.

Retain this one-time compatibility packet. Pause repeated negative-score probes
unless the proposed implementation, source hashes or proof contract changes.
Other operating lanes retain their own triggers in the companion brief.
