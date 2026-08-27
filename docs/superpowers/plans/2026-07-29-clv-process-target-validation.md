# CLV Process Target Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Use final CLV as an offline process target to validate live-safe pre-close and agreement proxies without allowing hindsight information into a selector.

**Architecture:** Create a matched research table that labels whether a tracked pick beat the closing price/line, then evaluates pre-lock proxy buckets against that target and graded outcome. The output measures discrimination, calibration, coverage, and drift; it never emits a verdict or pick action.

**Tech Stack:** Python 3.11, Gate C JSONL, market-price outcome audit, live-market outcome audit, pre-close CLV proxy lab, market-agreement tracker, pytest.

## Global Constraints

- Treat `evidence_clv_supported` (`277`, `155-122`, `+19.01u`, `+6.9%`) as a process benchmark, not a live candidate.
- The recent `30`-row result of `-4.64u` prevents a performance claim based on CLV support alone.
- Final CLV, closing line, final price, graded result, actual Ks, and actual workload are prohibited selector inputs.
- Provider/book, same-line versus alternate-line, timestamp, and freshness provenance must be explicit.
- Missing close evidence is `unknown`, never a loss, neutral, or inferred close.
- No model, verdict, threshold, staking, provider, notification, lock, artifact, UI, retention, or environment changes.

---

### Task 1: Build a canonical CLV target row

**Files:**

- Create: `analytics/diagnostics/clv_process_target_validation.py`
- Create: `tests/test_clv_process_target_validation.py`

**Interfaces:**

- Export `build_target_row(gate_c_row, market_rows)`, `classify_final_clv(row)`, `classify_proxy(row)`, `build_summary(rows)`, `render_report(summary)`, and `main(argv=None)`.
- Write `analytics/output/clv_process_target_validation.md` and `.json`.

- [ ] Write failing tests for same-line price CLV, line CLV, alternate-line rejection, stale evidence, missing close, and provider mismatch.
- [ ] Preserve exact observation ids/timestamps and the official lock reference.
- [ ] Deduplicate on normalized `(date, pitcher, side)` while retaining display names.
- [ ] Run `python -m pytest tests/test_clv_process_target_validation.py -v`.
- [ ] Commit `test: define canonical clv process target`.

### Task 2: Validate live-safe proxies

**Files:**

- Modify: `analytics/diagnostics/clv_process_target_validation.py`
- Modify: `tests/test_clv_process_target_validation.py`

- [ ] Compare strong/medium/weak pre-close proxy and market-agreement buckets against beat/neutral/worse close.
- [ ] Report coverage, precision, lift versus base rate, Brier-style calibration, and provider-era drift.
- [ ] Cross-tab process target with PnL without treating either as proof of the other.
- [ ] Add side, price, K-line, timing, quality, Path B, workload, provider, agreement, and rolling-window slices.
- [ ] Require at least `100` fully attributed current-provider targets and positive proxy lift in two consecutive 14-slate windows before `ready_for_proxy_design`.
- [ ] Commit `feat: validate preclose signals against clv target`.

### Task 3: Integrate and decide

**Files:**

- Modify: `scripts/run_post_grading_shadow_reports.py`
- Modify: `tests/test_post_grading_shadow_reports.py`
- Create: `docs/research/clv-process-target-review.md`
- Modify: `docs/current-state.md`

- [ ] Run after market-agreement and pre-close reports with bounded Supabase-derived inputs only.
- [ ] Add a skip flag and print coverage, lift, drift, and readiness only.
- [ ] Issue `keep_as_process_kpi`, `ready_for_proxy_design`, or `proxy_failed`.
- [ ] If proxy design is supported, create a separate Tyler-approved plan; do not reuse final CLV in runtime.
- [ ] Run focused tests, `python -m pytest tests -q`, and `git diff --check`.
- [ ] Commit `docs: review clv process target validity`.

## Final Review Correction (2026-07-30)

`market_pick_evidence` is a per-pick movement rollup, not an official-close
source. Its bounded export remains the agreement/pre-close input only and must
never be passed to the final-CLV validator. The runner requires a separate,
explicit, bounded read-only close-provenance packet before it may invoke that
validator. `--refresh-market-agreement-inputs` does not create this packet.

The close packet may be JSON or JSONL. Every non-empty row must explicitly
identify an `official_close` observation with slate date, normalized pitcher,
side, provider, bookmaker, observation id, timezone-aware close timestamp,
numeric close line and price, and freshness. Event identity is optional but
must match when both sides provide it. A valid explicit empty packet is allowed
and produces `unknown` close outcomes; a missing, unreadable, malformed, or
wrong-schema packet is a bounded `proxy_failed` runner outcome. It must not
prevent the later shadow reports from running.

Gate C PnL remains descriptive top-level context for the final report and must
not enter proxy inputs. The target requires a timezone-aware official lock
timestamp and a strictly later timezone-aware close timestamp. Invalid or
non-increasing timestamps remain `unknown` with a specific eligibility reason.
The shared provider-era classifier label is authoritative.

- [x] Add real-shape movement-rollup rejection and separate close-packet tests.
- [x] Validate JSON/JSONL packet structure before runner invocation; fail closed
  without aborting subsequent reports.
- [x] Preserve descriptive PnL, use the shared provider-era label, and cover
  timezone/order eligibility.
- [x] Update the review/current-state handoff: close producer missing,
  movement export insufficient, `keep_as_process_kpi`, and runner
  `proxy_failed` until a valid packet exists.

## Approved Offline Producer (2026-08-27)

Tyler approved a bounded research-only producer. The implementation is
`analytics/diagnostics/clv_official_close_packet.py`; it reads explicit
JSON/JSONL exports of `operational_pick_locks` and `market_snapshots`, with an
optional Gate C input used only to resolve `official_line_source_provider` or
an exact single-provider `official_odds_source`. It has no database client,
scheduled-runner wiring, publisher, or live-table write path.

The producer fails closed unless it can establish one exact provider/event
from a same-pitcher, side, book, line, price, and game-time snapshot observed
within 20 minutes before lock. It then requires the latest same-provider,
same-book, same-event snapshot to be strictly after lock, strictly before first
pitch, and no more than 20 minutes old at game time. BoltOdds is excluded from
the default provider allow-list. Missing, ambiguous, stale, or post-start rows
are written to a separate exclusions packet; a manifest records bounds,
counts, fingerprints, freshness settings, and zero database writes.

A bounded live shape check across August 25-26 found `42` lock rows: `10` had
one unique provider/event match and `32` were ambiguous because TheRundown and
PropLine shared the same pre-lock signature. That result is why the Gate C
official-provider resolver is optional but necessary for useful coverage; the
producer never guesses. No current close packet has been exported and
validated yet, so the recurring runner remains `proxy_failed` unless an
explicit valid packet is supplied. No CLV readiness count or performance
claim follows from this implementation.

- [x] Add test-first exact lock-provenance, timestamp-order, freshness,
  ambiguity, retired-provider, CLI-output, and validator-contract coverage.
- [x] Keep the producer offline and dry-run only; do not wire it into the
  recurring post-grading runner without a separate approval.
- [ ] Export one bounded current-provider window, inspect every exclusion, and
  validate the packet before measuring the existing readiness gates.

