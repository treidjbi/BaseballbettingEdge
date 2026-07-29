# Market-Anchor Downside Review Implementation Plan

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

- [ ] Write failing tests for unchanged rows, FIRE-to-LEAN, FIRE-to-PASS, already-capped rows, missing metadata, and post-start leakage.
- [ ] Preserve raw/display/final verdict provenance and the earlier cap reason chain.
- [ ] Emit counts for metadata coverage, would-change, applied, cap depth, and duplicate keys.
- [ ] Run `python -m pytest tests/test_market_anchor_downside_counterfactual_audit.py -v`.
- [ ] Commit `test: freeze market anchor downside cohort`.

### Task 2: Measure incremental value and mandatory slices

**Files:**

- Modify: `analytics/diagnostics/market_anchor_downside_counterfactual_audit.py`
- Modify: `tests/test_market_anchor_downside_counterfactual_audit.py`

- [ ] Compare current displayed verdict results with the hypothetical downside verdict on the same rows.
- [ ] Separate rows already changed by quality, confidence referee, or profit rescue from genuinely incremental market-anchor rows.
- [ ] Add side, K-line, price, FIRE level, quality, timing, model/market, Path B, workload, CLV/proxy, provider, agreement, rolling-window, and leave-one-slate-out tables.
- [ ] Report avoided losses, foregone wins, net unit delta, and maximum one-slate contribution.
- [ ] Fail closed when the paired cohort cannot be reconstructed exactly.
- [ ] Commit `feat: add paired market anchor downside audit`.

### Task 3: Integrate and decide

**Files:**

- Modify: `scripts/run_post_grading_shadow_reports.py`
- Modify: `tests/test_post_grading_shadow_reports.py`
- Create: `docs/research/market-anchor-downside-review-packet.md`
- Modify: `docs/current-state.md`

- [ ] Run the counterfactual after the existing selector audit.
- [ ] Add a skip flag and a concise log excerpt.
- [ ] Rebuild through the latest fully graded slate and issue `keep_shadow`, `draft_separate_canary`, or `retire_downside_path`.
- [ ] If `draft_separate_canary` wins, stop before editing Render variables; a new Tyler-approved activation plan is required.
- [ ] Run focused tests, `python -m pytest tests -q`, and `git diff --check`.
- [ ] Commit `docs: issue market anchor downside review`.

