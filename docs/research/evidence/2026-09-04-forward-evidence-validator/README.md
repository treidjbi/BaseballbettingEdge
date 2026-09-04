# Offline validator evidence

Everything in `run/synthetic-inputs.json.gz` is synthetic. It includes explicit
synthetic activation declarations for acceptance testing; these activate
nothing. `run/inactive-reference-manifest.json` retains null real activation
fields. `run/acceptance.json` contains the 20-case results, exact old-source
hashes and the existing negative-score proof probe. The referenced original
352-row/327-row evidence remains in its original folder, unchanged.

From the repository root with project dependencies installed:

```bash
python docs/research/evidence/2026-09-04-forward-evidence-validator/reproduce.py
python -m analytics.diagnostics.forward_pregame_evidence_validator \
  --input /path/to/one-packet.json.gz --output-dir /tmp/bbe-forward-new-check
```

The first command regenerates synthetic inputs in memory and checks exact
saved-output/source equality without writing. `checks.ipynb` executes those
checks and displays case outcomes plus the historical exclusions. `--create`
is for initial construction only and refuses an existing `run` directory.
CLI output likewise requires a new directory and refuses canonical production
paths. Input may be JSON or gzip JSON; source paths inside receipts are never
fetched. The 64 MiB decompressed-input limit is local validation safety only.

`test-results.txt` preserves 357 passing relevant tests, including 76 new tests.
Test-first work observed the missing-module failure and later focused failures
before their fixes. Notebook execution used the bundled runtime and temporary
kernel/dependencies outside the repo. No dependency, production configuration,
history or runtime module was changed.

The serialized examples are explanatory witnesses. A trusted live capture
service, actual original-history mapping, immutable storage and approval
receipt remain unimplemented. This packet cannot establish real prospective
eligibility, net profit or rollout readiness.
