# No-Drag and Strict Runtime Prospective Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce the August 10 independent decision packet for the frozen no-drag v1 canary and a newly frozen strict-runtime-core comparison without changing live behavior.

**Architecture:** Keep the existing no-drag audit immutable, add one post-grading strict-core audit with its own fingerprint and prospective counter, and combine only their review outputs in a dated operator packet. Both audits read the canonical Gate C row and write ignored Markdown/JSON research outputs.

**Tech Stack:** Python 3.11, Gate C JSONL, existing Strong Base labels, standard-library JSON/hashlib, pytest, Render research cron.

## Global Constraints

- Preserve no-drag selector id `combined_runtime_broad_no_hindsight_no_drag_v1` and its existing fingerprint.
- Start strict-core prospective evidence on the first graded slate after implementation; do not backdate prospective credit.
- Define strict core from runtime-safe Strong Base labels only; do not import result, PnL, final CLV, actual workload, or post-start data into the selector.
- No-drag has completed its `75`-row count floor. It remains blocked by diversity and slice survival, not by total count.
- Strict core's review floor is `50` graded current-provider rows, including at least `10` UNDER and `10` plus-price rows. If the product never presents those contexts, report a narrow OVER/minus specialist rather than weakening the gate.
- Require side, price, K-line, verdict family, quality, timing, model/market, Path B, workload, CLV/proxy, provider, agreement, rolling-window, and leave-one-slate-out reads.
- The strongest automated status is `ready_for_review`; no code path may change verdicts, units, thresholds, model math, providers, notifications, locks, artifacts, UI, retention, or environment variables.

---

### Task 1: Freeze the strict-runtime selector

**Files:**

- Create: `analytics/diagnostics/strict_runtime_core_canary_audit.py`
- Create: `tests/test_strict_runtime_core_canary_audit.py`

**Interfaces:**

- Export `RULE_SPEC`, `RULE_FINGERPRINT`, `evaluate_row(row)`, `build_audit(rows)`, `render_report(summary)`, and `main(argv=None)`.
- Reuse `strong_base_decision_lab.candidate_labels(row)` only for the immutable input labels; encode the strict allow/exclude rule locally.
- Write `analytics/output/strict_runtime_core_canary_audit.md` and `.json`.

- [ ] Write failing truth-table tests covering eligible FIRE rows, every drag exclusion, missing critical inputs, current-provider classification, and result-free selector behavior.
- [ ] Implement the frozen rule and stable JSON fingerprint.
- [ ] Add duplicate-key, baseline-drift, input-gap, and post-start leakage blockers.
- [ ] Run `python -m pytest tests/test_strict_runtime_core_canary_audit.py -v`.
- [ ] Commit `test: freeze strict runtime core prospective audit`.

### Task 2: Add prospective accounting and diversity gates

**Files:**

- Modify: `analytics/diagnostics/strict_runtime_core_canary_audit.py`
- Modify: `tests/test_strict_runtime_core_canary_audit.py`

- [ ] Add full, current-provider, prospective, latest-14-slate, and leave-one-slate-out scoreboards.
- [ ] Add explicit counters for UNDER, plus price, FIRE 1u/FIRE 2u, provider attribution, and market agreement.
- [ ] Make same-profile OVER/minus rows increase the descriptive sample but not satisfy the diversity gate.
- [ ] Prove final CLV is report-only and never used by `evaluate_row`.
- [ ] Run the focused test file and direct CLI against a temporary canonical Gate C build.
- [ ] Commit `feat: add strict core diversity review gates`.

### Task 3: Extend the post-grading research runner

**Files:**

- Modify: `scripts/run_post_grading_shadow_reports.py`
- Modify: `tests/test_post_grading_shadow_reports.py`

- [ ] Invoke the strict audit after Gate C, Strong Base, and market-agreement inputs are fresh.
- [ ] Add `--skip-strict-runtime-core-audit` for isolated diagnostics.
- [ ] Print only status, fingerprint, current-provider counter, diversity blockers, and recent PnL.
- [ ] Prove the runner cannot publish pipeline artifacts or write live tables.
- [ ] Run `python -m pytest tests/test_post_grading_shadow_reports.py tests/test_strict_runtime_core_canary_audit.py -v`.
- [ ] Commit `feat: schedule strict core research audit`.

### Task 4: Issue the August 10 decision packet

**Files:**

- Create: `docs/research/2026-08-10-no-drag-strict-runtime-decision.md`
- Modify: `docs/current-state.md`

- [ ] Rebuild canonical Gate C and both audits through the latest fully graded slate.
- [ ] Reconcile no-drag locked baselines/fingerprint and exclude all history-recovered rows from prospective credit.
- [ ] Present no-drag and strict core as independent decisions with all mandatory slices.
- [ ] Assign exactly one outcome to each: `keep_soaking`, `narrow_specialist_review`, `draft_separate_shadow_plan`, or `retire`.
- [ ] If either survives, stop and request Tyler's separate approval before any runtime or environment work.
- [ ] Commit `docs: issue no-drag and strict core decision packet`.

### Task 5: Final verification

- [ ] Run `python -m pytest tests/test_no_drag_composite_canary_audit.py tests/test_strict_runtime_core_canary_audit.py tests/test_post_grading_shadow_reports.py -v`.
- [ ] Run `python -m pytest tests -q`.
- [ ] Search the new code for `lambda`, `staking`, `notification_events`, `operational_pick_locks`, and publisher writes; document why any match is read-only.
- [ ] Confirm `git diff --check` and a clean intentional worktree.

