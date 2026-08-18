# Task 2 Report: Safe Adaptive Runner and Atomic Checkpoints

Run completed: `2026-08-18T15:33:12-07:00`

## Implementation summary

- Added the local bounded-retention runner with immutable scope, chunk, and
  checkpoint contracts.
- Fixed the candidate scope to the Phoenix clean regime beginning
  `2026-04-28`, an inclusive `as_of_date - 30 days` cutoff, and the ordered
  provider allowlist `boltodds`, `propline`, `the_odds`, `therundown`.
- Added deterministic provider-serial planning with the reviewed `1 -> 3 -> 7`
  cadence, 30-second slow threshold/cooldown, default-one and hard-five caps,
  and no retries.
- Added a SELECT-only linked CLI wrapper using a temporary SQL file, argv list,
  `shell=False`, captured text output, and the fixed 120-second local timeout.
- Added exact aggregate validation, stable sanitized failure codes, atomic JSON
  writes, contract/rendered SQL hashes, result hashes, scope fingerprints, and
  fail-closed resume validation.
- Added explicit linked-read acknowledgement gates for `run` and
  `runtime-boundary`. The `assemble` route is local-only and remains
  fail-closed for the later assembly task; it cannot issue a linked query or
  emit a false complete envelope.
- No live Supabase/provider call, write, deletion, backfill, vacuum, migration,
  provider change, dependency, push, deploy, or production behavior change was
  performed.

## Files

- `scripts/bounded_retention_audit.py`
- `tests/test_bounded_retention_audit.py`
- `.superpowers/sdd/2026-08-18-bounded-retention-audit/task-2-report.md`

Task 1's reviewed `scripts/retention_bounded_sql.py` and tests were used without
modification.

## RED evidence

1. Initial planner test collection failed exactly because
   `scripts.bounded_retention_audit` did not exist (`1` collection error).
2. Subprocess, parser, payload, atomic-write, and stable-failure tests then
   failed on the missing production interfaces (`19` failures, `11` passing).
3. Resume/checkpoint tests failed against the temporary empty loader (`7`
   failures, `32` passing).
4. CLI tests failed on the missing parser/runtime/assembly routes (`11`
   failures, `39` passing).
5. The non-directory output preflight test failed because a query could begin
   before rejecting the invalid local destination (`1` failure); the final
   implementation now rejects it before query construction/execution.

## GREEN evidence

- Task 2 focused tests: `55 passed`.
- Task 1 + Task 2 focused tests: `75 passed`.
- Full repository suite on the final implementation: `2226 passed in 126.80s`.
- `python -m py_compile scripts/retention_bounded_sql.py scripts/bounded_retention_audit.py` passed.
- `git diff --check` passed.

The full suite rewrote only
`analytics/output/gate_f_preclose_clv_proxy_lab.md`. Its committed textual
content was restored with `apply_patch`; the file has no remaining content
diff.

## Self-review

- The only subprocess command is the reviewed `npx supabase db query --linked
  --file ... -o json` argv form; SQL is validated as one SELECT-only statement
  before the temporary file is created.
- No provider, SQL, timeout, execute, delete, backfill, or vacuum input is
  exposed by the CLI.
- Every live-capable command requires `--run-linked-read`; multi-chunk work also
  requires `--allow-multi-chunk` and remains capped at five serial chunks.
- Failed units write no checkpoint and make no retry. Existing exact validated
  checkpoints remain resumable; malformed, stale, tampered, foreign, mixed,
  and overlapping evidence fails closed before another query.
- Payload validation independently recomputes partition matrices, count
  equations, mismatch bounds, runtime equality, and `coverage_exact`.
- Atomic writes serialize, flush, close, and fsync the temporary file before
  replacement. Interrupted `.tmp` files are not resume evidence.
- Task 1 SQL behavior, including its two reviewed runtime-boundary rulings, was
  preserved unchanged.

## Concerns / next gate

- No live validation has occurred and this implementation does not authorize
  one. Each one-date canary, runtime-boundary read, or capped multi-chunk run
  still needs separate Tyler approval.
- Final version 2 envelope assembly is intentionally not implemented here; the
  local `assemble` route fails closed until the later approved task supplies
  and tests that contract.
- The checkpoint `cli_version` binds the fixed linked-query CLI contract. The
  runner deliberately does not make an extra `npx --version` subprocess call,
  preserving the one-query/no-extra-call failure contract.
