# October 1 offline season review

Intentional preserved analysis artifacts, not operational pipeline outputs.
No provider requests, grading, calibration, production writes or restarts.

- `sources/published_history.json`: preserved 4,102-row already-published snapshot;
  exact provenance and original-freeze-hash difference in adjacent JSON.
- `results/analyze_results.py`: rerun from repository root with Python 3.
- `projection/review.py`: rerun from repository root with Python 3.
- `results/*.csv`, `results/results_summary.json`, `projection/*.csv` and JSON:
  reproducible reviewed tables. Published accounting and research populations
  are distinct. Published PnL uses flat 1u risk, not actual account stakes.
- `report/`: authored interactive report content and snapshot builder, retained
  for recovery. Shared Data App runtime lives outside this repository at
  `/Users/tyler/Documents/Codex/BBE-2026-Season-Review`.

Local interactive preview: http://127.0.0.1:4187/
Portable complete offline copy:
`/Users/tyler/Documents/Codex/BBE-2026-Season-Review/.data-app-offline/exports/season-review.html`.
To serve again: `python3 -m http.server 4187 --bind 127.0.0.1 --directory /Users/tyler/Documents/Codex/BBE-2026-Season-Review/dist`.

The snapshot builder updates the existing report project; it does not install
or recreate the shared runtime. To reconstruct after losing the local project,
prepare the installed Data plugin's report template, restore the authored
files under `src/content/report/`, restore report identity
`report:80aac7e4-cd91-404b-a917-d8406438f11f`, then build the snapshot and report.

Validation: both offline analysis scripts completed with their reconciliation
assertions. Independent agent reproduced totals and projection errors. Report
build passed; rendered overview, chart series, results table, team filter and
pitcher search verified in the local browser. Narrow-screen rendering was not
separately tested. No production code was changed.
