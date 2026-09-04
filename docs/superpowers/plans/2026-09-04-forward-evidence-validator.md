# Offline forward-evidence validator implementation

Date: September 4, 2026. Tyler approved implementing the offline validator and
acceptance cases following the [defined contract](../specs/2026-09-04-forward-pregame-evidence-contract.md).
Branch: `codex/research-decision-time-adapter`.

## Scope

Add one standalone module/CLI, an explicit offline serialization profile,
synthetic fixture generation and focused tests. Validate receipt bytes and
availability, exact candidate/lock/proof identity, replayed exact market
evidence, known Path B/workload, manifest drift, capture inventories and
separate lifecycle attachments. Do not import a runtime writer or runner.
Do not modify production modules, the existing adapter, any historical
evidence, canonical dataset, audit threshold or scoring formula.

All outputs retain zero formal credit and no promotion status. A synthetic
activation declaration exercises input eligibility only; it is not a real
activation, an authenticated storage receipt or authorization to collect.
An offline file proves internal consistency, not that a capture service
actually persisted it at the declared time.

## Sequence and acceptance

1. Observe failing tests before implementation.
2. Reuse pure exact V2 evidence/proof/selector helpers; verify market replay
   rather than trusting supplied counts, labels or pending-to-neutral defaults.
3. Build positive weak/neutral/fallback cases and adversarial time, source,
   missingness, duplicate/retry, provenance, activation and drift cases.
4. Validate the preserved 352-record legacy adapter packet as ineligible for
   this new envelope; do not add missing fields or back-credit those rows.
5. Produce a reproducible offline acceptance packet and executed notebook,
   verify the old evidence remains unchanged, and run relevant regression tests.
6. Update this plan, board and operating brief; commit and push the feature
   branch. No merge, deployment, capture sink or activation is included.

The next decision after acceptance is a bounded capture/integration proposal
with its exact sink, read bounds, measured resource use, error isolation,
rollback and unset-until-approved activation manifest. This implementation
does not choose or activate that sink.

## Completed offline acceptance

Implementation and [serialization profile](../../research/forward-pregame-evidence-profile-v1.md)
are complete. The [review](../../research/2026-09-04-forward-evidence-validator-review.md)
links 76 new passing tests, 357 passing combined tests, the executed notebook
and a 20-scenario synthetic packet. Eight cases pass input-candidate checks;
twelve remain diagnostic/excluded. All formal credit is zero. The prior 352-row
adapter packet and all 327 old frozen rows remain legacy-schema evidence;
their files and original adapter reproduction are unchanged.

The accepted profile preserves known rule matches across unrelated input gaps,
replays exact market/proof logic, requires bound window receipts and affirmative
original seed provenance, and checks close attribution plus the existing CLV
bucket. No production helper, score, audit gate, collector or runner changed.

An existing proof-format limitation was exposed: complete inputs can score -1
(`weak_preclose_clv_proxy`), while V2 proof validation requires a nonnegative
score and emits a diagnostic pending record. That case remains excluded here;
affected live-row counts are unknown. Next is a scoped proof-format repair
review before capture integration, preserving signed scoring math while keeping
counts and all other proof constraints strict. Any capture proposal must also
address bounded-read completeness, immutable receipt provenance, the actual
source mappings and resource use. No real sink or activation is approved or set.
