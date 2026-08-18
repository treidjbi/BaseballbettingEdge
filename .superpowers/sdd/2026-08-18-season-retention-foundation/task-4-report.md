# Task 4 — BoltOdds Retirement Closure Package

Run time: 2026-08-18T11:38:51-07:00

## Scope

- Added `build_boltodds_closure`, deterministic BoltOdds runtime/book evidence,
  coverage aggregation, closure Markdown rendering, and the `boltodds-closure`
  CLI mode.
- Reused the Task 1–3 envelope validators, evidence indexers, and redacted
  report-pair writer; no alternate parser was introduced.
- The builder validates the envelope at entry and blocks closure on every
  BoltOdds provider-level source anomaly, even when dated coverage is exact.
- Added focused regression tests for normal closed authority, missing evidence,
  post-suspension activity, provider anomalies, validation at entry, and CLI
  report generation.

## TDD evidence

- RED: `python -m pytest tests/test_build_season_retention_readiness.py -v`
  returned 7 expected failures (`build_boltodds_closure` absent and closure CLI
  unavailable), with 46 existing tests passing.
- GREEN: `python -m pytest tests/test_build_season_retention_readiness.py -v`
  returned `53 passed in 0.15s`.
- Scope check: `git diff --check` completed with exit code 0.

## Constraints preserved

- No Supabase, live, production, deployment, backfill, or deletion calls made.
- `analytics/output/gate_f_preclose_clv_proxy_lab.md` was preserved and excluded
  from staging and the Task 4 commit.

## Concern

The intentionally preserved CLV proxy lab remains modified outside Task 4 and
must be reconciled separately before branch handoff.
