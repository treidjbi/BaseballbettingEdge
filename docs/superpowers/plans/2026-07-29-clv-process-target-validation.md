# CLV Process Target Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Use final CLV as an offline process target to validate live-safe pre-close and agreement proxies without allowing hindsight information into a selector.

**Architecture:** Create a matched research table that labels whether a tracked pick beat the closing price/line, then evaluates pre-lock proxy buckets against that target and graded outcome. The output measures discrimination, calibration, coverage, and drift; it never emits a verdict or pick action.

**Tech Stack:** Python 3.11, Gate C JSONL, market-price outcome audit, live-market outcome audit, pre-close CLV proxy lab, market-agreement tracker, pytest.

## Global Constraints

- Treat `evidence_clv_supported` (`276`, `155-121`, `+20.01u`, `+7.2%`) as a process benchmark, not a live candidate.
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

