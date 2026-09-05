# Unapplied signed-score proposal evidence

`run/proposed.patch` is an unapplied proposal artifact. `run/acceptance.json`
records both readers' results and original source hashes. Every row in
`run/synthetic-rows.json.gz` is synthetic, with zero formal credit.

From the repo root with project Python dependencies and Node installed:

```bash
python docs/research/evidence/2026-09-04-signed-score-proof-review/reproduce.py
```

Normal execution is read-only. It rebuilds cases in memory, checks exact saved
results/diff, rechecks 327 captured rows, and reproduces the preceding validator
and adapter packets. `--create` was used once and refuses an existing `run`
directory. No source file, old packet or production state is modified. The JS
helper imports source strings via data URLs and exposes full proof validators;
it never invokes the HTTP handler.

There are 47 shared JSON cases: three complete signed-score proofs and 44
malformed/tampered exclusions. Both readers additionally reject three nonfinite
scores. The historical comparison uses Python; it does not assert live endpoint
or database compatibility.

The helper runs in memory while forward fixtures retain the on-disk dependency
manifest. This is deliberately counterfactual, not evidence of a new deployed
implementation or activation. Implementation requires a separately generated
manifest and packet. Do not overwrite this or previous evidence on source drift.
