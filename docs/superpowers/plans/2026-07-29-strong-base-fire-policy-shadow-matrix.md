# Strong Base FIRE Policy Shadow Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze and compare the strongest runtime-safe FIRE retention and downside-cap policies, then identify whether any one policy adds decision value beyond the active cap stack.

**Architecture:** Add one research-only policy matrix that evaluates fixed Strong Base candidate definitions on identical Gate C rows. It reports standalone and incremental results for the two downside caps, two retained-FIRE specialists, strict runtime core, and the Strong Base/market-anchor strict union. It does not create a live selector.

**Tech Stack:** Python 3.11, `strong_base_decision_lab.py`, `strong_base_portfolio_simulator.py`, `shadow_signal_synthesis_lab.py`, Gate C JSONL, pytest.

## Global Constraints

- Freeze these candidates before prospective collection:
  - `cap_high_raw_edge` (`925`, `-121.20u` historical);
  - `cap_market_fade` (`872`, `-94.37u` historical);
  - `keep_fire_over_moderate_ev_normal_leash` (`198`, `+21.25u`);
  - `keep_fire_market_agreed_moderate_ev` (`170`, `+20.05u`);
  - `strict_runtime_core_flat` (`96`, `+17.72u`); and
  - `keep_fire_if_strong_base_or_market_anchor_strict` (`112`, `+20.52u`).
- Historical results identify candidates; only post-freeze results may advance a new review counter.
- Downside policies must show incremental avoided loss after the existing quality/confidence/profit-rescue chain. Retention policies must never promote a PASS or LEAN.
- A candidate needs `75` prospective graded rows, positive current-provider and latest-14-slate PnL, positive leave-one-slate-out minimum, and all mandatory slices before a promotion-plan discussion.
- If two policies overlap more than `80%` of rows, keep the simpler one unless the more complex policy provides a material paired unit improvement.
- No live verdict, threshold, stake, provider, notification, lock, artifact, UI, retention, or environment change is in scope.

---

### Task 1: Create immutable policy specifications

**Files:**

- Create: `analytics/diagnostics/strong_base_fire_policy_matrix.py`
- Create: `tests/test_strong_base_fire_policy_matrix.py`

**Interfaces:**

- Define `PolicySpec(id, family, selector, fingerprint_fields)` where `family` is `downside_cap` or `retained_fire`.
- Export `policy_specs()`, `evaluate_policy(row, spec)`, `build_matrix(rows)`, `render_report(summary)`, and `main(argv=None)`.
- Write `analytics/output/strong_base_fire_policy_matrix.md` and `.json`.

- [ ] Write failing truth-table tests for every candidate boundary and exclusion.
- [ ] Generate a stable fingerprint per policy and reject duplicate ids.
- [ ] Prove selectors do not read result, PnL, actual workload, final CLV, or post-start evidence.
- [ ] Run `python -m pytest tests/test_strong_base_fire_policy_matrix.py -v`.
- [ ] Commit `test: freeze strong base fire policy matrix`.

### Task 2: Add overlap and incremental-value accounting

**Files:**

- Modify: `analytics/diagnostics/strong_base_fire_policy_matrix.py`
- Modify: `tests/test_strong_base_fire_policy_matrix.py`

- [ ] Add pairwise overlap, Jaccard similarity, unique-row count, and paired unit-delta tables.
- [ ] For downside caps, separate already-capped rows from incremental would-cap rows.
- [ ] For retained FIRE, compare retained rows with current displayed FIRE and never add stake.
- [ ] Add current-provider, prospective, recent-14, leave-one-slate-out, side, price, K-line, FIRE level, quality, timing, model/market, Path B, workload, CLV/proxy, provider, and agreement slices.
- [ ] Block readiness on missing critical attribution or a negative mandatory slice with at least 10 rows.
- [ ] Commit `feat: measure incremental strong base policy value`.

### Task 3: Schedule research output and issue a shortlist

**Files:**

- Modify: `scripts/run_post_grading_shadow_reports.py`
- Modify: `tests/test_post_grading_shadow_reports.py`
- Create: `docs/research/strong-base-fire-policy-shortlist.md`
- Modify: `docs/current-state.md`

- [ ] Invoke the matrix after Strong Base and synthesis reports.
- [ ] Add `--skip-strong-base-fire-policy-matrix` and a bounded log excerpt.
- [ ] Freeze at most one downside candidate and one retained-FIRE candidate for prospective review; keep all others as controls or retire them.
- [ ] Require Tyler approval before drafting any behavior-changing canary.
- [ ] Run focused tests, `python -m pytest tests -q`, and `git diff --check`.
- [ ] Commit `docs: shortlist strong base fire policies`.

