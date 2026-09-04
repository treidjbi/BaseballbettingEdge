# September 4 research-lineage evidence

This packet diagnoses Gate C provenance, prospective lock linkage and the
Kumar Rocker exception. It changes no historical source or production state.
The reproduction writes only derived files within this directory.

| File | Evidence |
| --- | --- |
| [compact-and-lock-source.json.gz](compact-and-lock-source.json.gz) | Exact SELECT SQL/capture time, 20 artifact metadata rows, 330 locks, 896 compact market rows and 1,343 display rows; each compact query has a 2,001-row safety cap, neither reached |
| [served-artifacts.json.gz](served-artifacts.json.gz) | Twenty full dated API payloads plus one bounded history payload, each with URL, response hash and capture time; August 15–September 3 |
| [kumar-source.json](kumar-source.json) | Current exact unconsumed lock, named archive card and empty matching history read |
| [mlb-schedule.json](mlb-schedule.json) / [mlb-kumar-boxscore.json](mlb-kumar-boxscore.json) | Official game/player identity and actual result; not official BBE pick/history repair |
| [frozen-candidate-proof.json](frozen-candidate-proof.json) | 23 immutable Alt V2 records matching the selective-LEAN input predicate; not 23 selected Alt picks |
| [selector-disagreements.json](selector-disagreements.json) | Exact four identities where final-archive and available frozen-input candidate sets differ |
| [transport-sample.json](transport-sample.json) | Direct SQL August 30 payload text for semantic comparison with served JSON; stored issuer hash retained independently |
| [analysis.json](analysis.json) | Historical newline proof, bounded build/reconciliation, strict join exclusions and remaining selective-LEAN gaps |
| [bounded-gate-c.jsonl.gz](bounded-gate-c.jsonl.gz) | The 660-row offline derivative; not a replacement canonical artifact or hosted scheduled result |
| [reproduce.py](reproduce.py) / [lineage-checks.ipynb](lineage-checks.ipynb) | Full offline code and executed companion checks |

Gzip files are lossless, ordinary JSON or JSONL. Python example:

```python
import gzip, json
from pathlib import Path
payload = json.loads(gzip.decompress(Path('served-artifacts.json.gz').read_bytes()))
```

From the repo root, reproduce using Python 3.11+:

```bash
.venv/bin/python docs/research/evidence/2026-09-04-research-lineage/reproduce.py
```

The captured public reads were bounded by date and used at most three
simultaneous artifact requests. An initial expected-hash assertion failed;
the capture was then repeated with each mismatch retained rather than
silently certified. All 20 issuer-versus-reserialized-payload hash differences
remain reported. The two transport formats compare semantically equal on the
directly sampled August 30 artifact; this is not full issuer-byte validation.
No current provider odds polling or raw snapshot query was added.

The existing dataset, selective-LEAN and repair tests passed 47 tests using
temporary external test dependencies. No dependency or production environment
was changed. The notebook executes the same source-based checks and writes
only this packet's derived files. `verification.json` pins source and code
hashes. Future live refreshes should create a new dated packet.
