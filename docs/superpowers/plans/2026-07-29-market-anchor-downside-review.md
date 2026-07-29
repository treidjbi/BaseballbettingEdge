# Market-Anchor Downside Review Implementation Plan

Status: **Implemented in research-only mode; decision `keep_shadow`; `enforce_downside` remains closed.**

## July 29 implementation result

The production-shaped hybrid rebuild through July 28 contains `3,434` side
rows, `1,793` tracked rows, zero duplicate dataset keys, and `1,750/1,750`
graded-pick reconciliation. The exact selector audit window starts on the June
16 shadow deployment and contains `743/743` tracked rows with stored selector
metadata.

The exact pre-start downside would-change cohort is `48` rows, all OVER and all
FIRE 1u: `27-21`, current displayed PnL `-0.763u`, hypothetical avoided-loss
delta `+0.763u`. Current-provider delta is `+4.632u` on `41` rows and the latest
14-slate delta is `+1.714u` on `24` rows. One post-start row was explicitly
excluded. Provider attribution is missing on all `48` rows and agreement is
missing on `45`; the local compact enrichment available for the reconstruction
ended July 13.

Decision: `keep_shadow`. The cohort is two rows short of the `50` floor, has
zero UNDER evidence, and fails the attribution gate. No Render variable or
live behavior changed.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Determine whether market-anchor strict can safely reduce existing FIRE exposure in a future canary, using a paired would-change cohort rather than promoting its favorable aggregate result.

**Architecture:** Extend the current market-anchor audit with an immutable downside counterfactual layer. The layer compares the displayed verdict to `enforce_downside` output, scores only rows whose verdict would change, and measures incremental value after quality, confidence-referee, and profit-rescue decisions. Runtime mode remains `shadow` throughout this plan.

**Tech Stack:** Python 3.11, existing `pipeline/market_anchor_selector.py`, Gate C JSONL, current canary audit, pytest, post-grading research runner.

## Global Constraints

- `MARKET_ANCHOR_SELECTOR_MODE=shadow` remains unchanged.
- Do not alter selector inputs, lambda, thresholds, staking, formula dates, providers, notifications, locks, artifacts, UI, or retention.
- Aggregate strict results (`155`, `93-62`, `+3.03u`) and strict displayed FIRE results (`28`, `20-8`, `+6.14u`) satisfy only the separate-review trigger.
- Promotion evidence must come from the exact downside would-change cohort and a paired control.
- Require at least `50` graded would-change rows, at least `10` on each side, and non-negative current-provider and latest-14-slate reads before a separate production-canary draft is allowed.
- Missing provider/agreement/CLV attribution is a blocker, not a neutral bucket.

---

### Task 1: Freeze the downside counterfactual contract

**Files:**

- Create: `analytics/diagnostics/market_anchor_downside_counterfactual_audit.py`
- Create: `tests/test_market_anchor_downside_counterfactual_audit.py`

**Interfaces:**

- Export `candidate_action(row)`, `paired_rows(rows)`, `build_summary(rows)`, `render_report(summary)`, and `main(argv=None)`.
- Read existing `market_anchor_selector` metadata; do not recompute with postgame fields.
- Write `analytics/output/market_anchor_downside_counterfactual_audit.md` and `.json`.

- [x] Write failing tests for unchanged rows, FIRE-to-LEAN, FIRE-to-PASS, already-capped rows, missing metadata, and post-start leakage.
- [x] Preserve raw/display/final verdict provenance and the earlier cap reason chain.
- [x] Emit counts for metadata coverage, would-change, applied, cap depth, and duplicate keys.
- [x] Run `python -m pytest tests/test_market_anchor_downside_counterfactual_audit.py -v`.
- [x] Commit `test: freeze market anchor downside cohort`.

### Task 2: Measure incremental value and mandatory slices

**Files:**

- Modify: `analytics/diagnostics/market_anchor_downside_counterfactual_audit.py`
- Modify: `tests/test_market_anchor_downside_counterfactual_audit.py`

- [x] Compare current displayed verdict results with the hypothetical downside verdict on the same rows.
- [x] Separate rows already changed by quality, confidence referee, or profit rescue from genuinely incremental market-anchor rows.
- [x] Add side, K-line, price, FIRE level, quality, timing, model/market, Path B, workload, CLV/proxy, provider, agreement, rolling-window, and leave-one-slate-out tables.
- [x] Report avoided losses, foregone wins, net unit delta, and maximum one-slate contribution.
- [x] Fail closed when the paired cohort cannot be reconstructed exactly.
- [x] Commit `feat: add paired market anchor downside audit`.

### Task 3: Integrate and decide

**Files:**

- Modify: `scripts/run_post_grading_shadow_reports.py`
- Modify: `tests/test_post_grading_shadow_reports.py`
- Create: `docs/research/market-anchor-downside-review-packet.md`
- Modify: `docs/current-state.md`

- [x] Run the counterfactual after the existing selector audit.
- [x] Add a skip flag and a concise log excerpt.
- [x] Rebuild through the latest fully graded slate and issue `keep_shadow`, `draft_separate_canary`, or `retire_downside_path`.
- [x] If `draft_separate_canary` wins, stop before editing Render variables; a new Tyler-approved activation plan is required.
- [x] Run focused tests, `python -m pytest tests -q`, and `git diff --check`.
- [x] Commit `docs: issue market anchor downside review`.

