# Paired signed-score implementation acceptance

September 4, 2026. **The approved format repair is implemented on
`codex/research-decision-time-adapter` at `b08284fd`.** It has not been merged
or deployed. No capture, migration, activation or production setting changed.

Python and JavaScript now accept legitimate signed Preclose scores while
retaining nonnegative counts, maturity, identity, scalar and semantic checks.
The code change matches the [reviewed patch](evidence/2026-09-04-signed-score-proof-review/run/proposed.patch).
Scoring formulas, weights, label thresholds, selector fingerprints, model math,
staking and the frozen research contract are unchanged.

## Validation

| Check | Result |
| --- | --- |
| Test-first Python regressions | Negative proof and builder cases failed before repair; other reviewed cases passed |
| Test-first endpoint regression | After adding the required provisional artifact/checkpoint fields to the fixture, only the negative witness failed; zero and positive passed |
| [Python regressions](evidence/2026-09-04-signed-score-implementation/python-tests.txt) | 539 passed; 27 PostgreSQL behavior tests skipped because local server binaries are unavailable |
| [Node endpoint regressions](evidence/2026-09-04-signed-score-implementation/node-tests.txt) | 124 passed, including all 47 reviewed cases and three nonfinite exclusions through the actual handler with mocked reads |
| Builder and serializer | -1/weak, 0/weak and +7/strong survive complete proof construction and provisional row serialization; all three fixtures remain `not_selected` |
| New forward acceptance | 20 synthetic scenarios; nine input candidates, eleven diagnostic/excluded; zero formal credit |
| Captured history | 327/327 proofs still valid and Preclose-pending; original adapter still reproduces 309 linked records and 19 linked rule matches |

The Python suite includes proof, selector, serializer, recorder/live-layer,
schema-text, adapter, forward validator, Gate C, selective-LEAN and lock-repair
regressions. The skipped tests do not establish deployed database compatibility;
no SQL migration changed. Deployed reader revisions and live affected-row counts
remain unverified. These are software acceptance results, not new uptime or
predictive evidence.

## New manifest; old records preserved

The [new inactive manifest](evidence/2026-09-04-signed-score-implementation/run/inactive-reference-manifest.json)
changes exactly one forward dependency hash: the Python proof reader. The
[acceptance record](evidence/2026-09-04-signed-score-implementation/run/acceptance.json)
also pins both Python/JavaScript reader hashes and the full implementation commit.
All activation fields remain null. The contract hash, baselines, selector
fingerprint and every other forward dependency hash remain unchanged.

The prior 20-scenario packet is retained byte-for-byte. Revalidating it against
this new implementation correctly reports dependency drift on every case and
zero input eligibility; it is not silently reissued. The old review reproduced
at its original source revision before applying the fix. Its historical conclusion
remains eight accepted synthetic inputs at that revision. New acceptance has
nine because complete negative scores are now representable. Every other scenario's
frozen proof is identical to its previous counterpart.

The reproducer compares all tracked files in the prior signed-score review,
forward-validator, adapter and lineage evidence folders against commit `2129a9a7`.
No old packet, manifest, notebook, freeze or outcome is rewritten. Old schemas
and missing acquisition evidence still earn zero prospective credit. Alt V2
promotion paths remain retired; Kumar's unconsumed lock remains excluded.

## Next decision

The [bounded capture proposal](../superpowers/plans/2026-09-04-bounded-forward-capture-proposal.md)
is prepared. Start with an offline feasibility prototype using supplied source
receipts and a local output directory. The next evidence needed is whether the
unchanged frozen proof can be reproduced entirely from inputs actually available
by its lock, plus an affirmative original-seed witness and measured resource use.

Current source review identifies a concrete timing gap: the live layer records
`observed_at` before provider polling and snapshot reads. Later reads cannot inherit
that earlier timestamp as an acquisition receipt. An after-the-fact capture hook
alone would not satisfy the contract. No sink, schedule or live collector should
be enabled merely because this format repair passes.

[Reproducer and commands](evidence/2026-09-04-signed-score-implementation/README.md)
· [Companion operating brief](../operating-brief.md)
