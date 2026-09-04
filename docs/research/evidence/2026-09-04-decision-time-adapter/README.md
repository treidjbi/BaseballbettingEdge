# Offline adapter evidence

`frozen-source.json.gz` preserves the complete 327-row SELECT-only capture and
its query/capture time. The prior lineage folder supplies unchanged 660-row
Gate C input and 330 operational locks. `run/packet.json.gz` is the CLI output,
compressed losslessly after generation; its original JSON SHA-256 is recorded
in `verification.json`. `reproduce.py` verifies source hashes and rebuilds the
packet in memory without writing. `checks.ipynb` contains executed checks.

From the repository root, with project dependencies installed:

```bash
python docs/research/evidence/2026-09-04-decision-time-adapter/reproduce.py
python -m analytics.diagnostics.decision_time_research_adapter \
  --gate-c docs/research/evidence/2026-09-04-research-lineage/bounded-gate-c.jsonl.gz \
  --locks docs/research/evidence/2026-09-04-research-lineage/compact-and-lock-source.json.gz \
  --frozen docs/research/evidence/2026-09-04-decision-time-adapter/frozen-source.json.gz \
  --start-date 2026-08-15 --end-date 2026-09-03 \
  --output-dir /tmp/bbe-decision-time-new-review
```

Choose a new output directory each time; existing directories are refused.
Inside this repo, only new directories under `analytics/output` or
`docs/research/evidence` are allowed. JSON, JSONL and gzip are supported. CLI
inputs must be arrays or `rows` envelopes; the lock input also supports the
captured `locks` envelope. Non-finite JSON constants and malformed identities
fail the read. No network or automatic source fetch occurs.

`tests/fixtures/decision_time_research_adapter.json` is Brad Lord's captured
August 15 frozen/lock/archive triple. The separate fixture
`decision_time_adapter_synthetic_fresh.json` was generated from existing V2
proof-builder test helpers and is explicitly synthetic. It verifies mature
Preclose behavior only and is never included in the research evidence.

The 43 adapter tests and 142 relevant existing tests passed under project
Python 3.11 with temporary test dependencies outside the repo. Notebook
execution used the bundled Python runtime and a temporary local kernel;
no project dependency or environment configuration was changed.
