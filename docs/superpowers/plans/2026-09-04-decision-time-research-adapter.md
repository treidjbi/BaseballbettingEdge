# Decision-time research adapter — September 4, 2026

Status: Tyler approved standalone research-only implementation following the
[lineage decision](../../research/2026-09-04-research-lineage-decision.md).
Branch: `codex/research-decision-time-adapter`.

Implementation complete and verified offline; see the
[implementation review](../../research/2026-09-04-decision-time-adapter-review.md).

## Scope and contract

Implement one offline adapter and CLI under `analytics/diagnostics/`. Reuse
captured Gate C rows, consumed operational locks and full immutable Alt V2
records. Do not modify the canonical builder, selective-LEAN audit, runner,
collector, provider queries, model, settings, histories or existing evidence.
No deployment or scheduled integration is included.

The output is a new nested evidence envelope, not a flat Gate C replacement.
Keep decision-time fields, operational proof, archived context and outcome
evidence separate. All outputs explicitly carry zero formal prospective
credit; this adapter cannot waive baselines, diversity gates, no-back-credit
rules or missing agreement/proxy/Path B evidence.

Required behavior:

1. Index identities by exact slate date, normalized pitcher and side, then
   require unique rows and exact game, locked line/odds/verdict/time/book.
   Duplicate candidates must not be silently resolved by newest/first row.
2. Validate the complete V2 proof with the existing validator and persisted
   row binding. Require a frozen-pregame checkpoint, original insertion and
   freeze before game, freeze equal to lock time, and the same lock artifact
   hash. A diagnostic pending proof cannot supply absent selector fields.
3. Take selector inputs only from validated frozen normalized inputs. Preserve
   disagreement with the final archive instead of choosing whichever wins.
   Do not use outcomes or archived features to fill missing frozen inputs.
4. Resolve decision-time official quote provider only from the validated
   proof's exact official binding. Read explicit archived official fields
   separately (line-source first, then single-provider official odds source);
   never use movement `provider` as an official-source fallback. A composite
   provider posture does not identify the exact quote source.
5. Preserve archive reference-book differences as conflicts in linkage.
   Preserve lock-source and archive-source paths independently. An unconsumed
   lock, absent outcome context, bad quote/timing or invalid proof stays
   excluded; none is repaired by this tool.
6. Expose a validated preclose label only when its exact proof is fresh and
   its observations precede/equal the lock. Pending or post-lock evidence
   remains unavailable. Do not manufacture market-agreement or frozen Path B
   labels from final archives; expose those unresolved contracts explicitly.
7. Quarantine identifiable recovered history. A passing join is not proof
   that all historical recovery provenance exists; no formal credit follows.
8. Read JSON/JSONL, optionally gzip, with explicit inclusive date bounds.
   Write only a new output directory; refuse an existing directory and repo
   production/canonical paths. No network, environment secrets or writer
   dependencies. Keep output deterministic and input values unchanged.

## Validation and handoff

- Write and observe failing focused tests before implementing the module.
- Exercise good linkage, complete proof binding, unknown/pending inputs,
  duplicate identities, identity/date/game/quote/hash conflicts, post-start
  freezes, post-lock observations, unconsumed locks, recovered history,
  outcome independence, provider separation and safe output paths.
- Run against the current 20-slate captured corpus. Preserve every exclusion
  and compare archive versus frozen selective-LEAN matches without granting
  credit. Do not replace the original 103-row nomination baseline.
- Run relevant existing proof, dataset, audit and repair suites. Update this
  plan with observed results, then the board and operating brief.
- Commit and push the feature branch. Runner integration and any forward-only
  collector contract remain separate work after offline review.

## Completed validation

Observed initial RED before implementation, then adversarial RED cases before
their fixes. Final scoped test run: 185 passed, including 43 new adapter tests.
Captured-input reconstruction matches the saved packet exactly: 352 identities,
309 linked, 325 validated frozen inputs, 23 frozen selective-LEAN matches,
19 linked matches and zero formal prospective credit. All 327 captured complete
V2 proofs validate, but two diagnostic-pending proofs lack selector inputs.
All captured Preclose states are pending. The executed notebook and source
hashes are linked from the implementation review.

The Gate C index uses only explicitly tracked sides; other identities enter
through locks/frozen records. Reused source IDs as well as duplicate tuple
identities fail closed. Hash binding requires both the frozen source-byte hash
and lock-artifact hash to equal the operational lock's recorded hash; artifact
generation must precede/equal freeze. These checks certify internal linkage,
not independent reconstruction of served/issuer bytes.

Next decision is a forward-only evidence contract for missing pregame agreement,
Preclose maturity, Path B and recovery provenance before any separately scoped
runner integration. No live or historical data change was made.

## Subsequent approved contract definition

Tyler approved defining the forward-only pregame evidence contract. The
[completed contract](../specs/2026-09-04-forward-pregame-evidence-contract.md)
now controls prospective availability, exact agreement/Preclose reuse, frozen
Path B, original-seed provenance and a separate immutable evidence envelope.
It preserves the selector, baselines and review gates. Capture is inactive and
activation fields remain unset; no old adapter row receives credit.

The next bounded step is an offline envelope validator and synthetic acceptance
packet, including the contract's negative cases. Capture/runner integration,
physical hosted sink and release remain separate decisions. This update is
documentation only; the adapter and its saved evidence are unchanged.

### Subsequent offline validator implementation

The approved [forward-evidence validator](2026-09-04-forward-evidence-validator.md)
is complete with synthetic acceptance and unchanged historical exclusions.
It grants no formal credit and changes no existing adapter/runtime behavior.
The linked review identifies the existing negative-score proof-format blocker
to resolve before a capture proposal; real capture and activation remain unset.
