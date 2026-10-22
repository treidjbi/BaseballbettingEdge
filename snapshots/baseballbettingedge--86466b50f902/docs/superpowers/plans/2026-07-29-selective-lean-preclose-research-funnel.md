# Selective LEAN and Pre-Close Research Funnel Implementation Plan

> **2026-08-14 status:** Tyler approved one frozen research-only counter after
> the independent 2026-08-13 design review found that
> `expand_lean_low_line_capped_model_fade` had repaired its earlier
> current/recent weakness. Task 2 is now controlled by
> `2026-08-14-selective-lean-prospective-audit.md`. The original threshold
> funnel remains unimplemented; no additional LEAN rule or pre-close modifier
> was searched or promoted.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the current selective-LEAN ideas to at most one fixed, live-safe research candidate by testing whether pre-close confirmation repairs their weak current and recent performance.

**Architecture:** Build a research funnel over the existing Strong Base LEAN labels and pre-close proxy labels. Use a train/freeze/holdout sequence: historical rows may nominate one rule, but only later graded rows evaluate it. No LEAN is promoted or shown as an official pick.

**Tech Stack:** Python 3.11, Gate C JSONL, Strong Base labels, `gate_f_preclose_clv_proxy_lab.py`, market-agreement export, pytest.

## Global Constraints

- Start with exactly these research candidates:
  - `expand_lean_45_low_ev_normal_leash` (`127`, `+11.14u`; recent `-3.82u`);
  - `expand_lean_low_line_capped_model_fade` (`83`, `+1.96u`; current `-6.46u`);
  - `expand_lean_low_k_standard_no_vig` (`66`, `+1.93u`; current `-3.52u`); and
  - `strict_runtime_core_plus_selective_lean_and_preclose_strong` as a comparison only (`186`, `+31.40u`).
- The original July 29 current/recent weakness was superseded by the verified
  August 13 review. Only `expand_lean_low_line_capped_model_fade` is nominated;
  formal prospective evidence still starts at zero.
- Final CLV cannot be a selector input. Only exact pre-close evidence available before the official lock may be used.
- The funnel may nominate at most one fixed rule. If none clears holdout requirements, report `no_candidate`.
- A future review requires at least `75` post-freeze graded rows, positive current-provider and latest-14-slate PnL, at least `20` UNDER and `10` plus-price rows, and complete mandatory slices.
- No official-pick, history, accepted-bet, notification, lock, dashboard, provider, threshold, model, or staking writes.

---

### Task 1: Build the candidate funnel

**Files:**

- Create: `analytics/diagnostics/selective_lean_preclose_funnel.py`
- Create: `tests/test_selective_lean_preclose_funnel.py`

**Interfaces:**

- Export `candidate_specs()`, `preclose_bucket(row)`, `score_candidate(rows, spec)`, `choose_nominee(summary)`, `render_report(summary)`, and `main(argv=None)`.
- Write `analytics/output/selective_lean_preclose_funnel.md` and `.json`.

- [ ] Write failing tests for the three Strong Base labels, exact pre-close availability, missing/pending evidence, and post-start exclusion.
- [ ] Score base candidate, base-plus-preclose-strong, and base-plus-market-agreement variants without searching arbitrary thresholds.
- [ ] Add minimum-row and one-slate-concentration controls.
- [ ] Make `choose_nominee` return no candidate when recent/current-provider gates fail.
- [ ] Run `python -m pytest tests/test_selective_lean_preclose_funnel.py -v`.
- [ ] Commit `feat: add selective lean research funnel`.

### Task 2: Freeze one nominee or close the branch

**Files:**

- Create if nominated: `analytics/diagnostics/selective_lean_prospective_audit.py`
- Create if nominated: `tests/test_selective_lean_prospective_audit.py`
- Modify: `scripts/run_post_grading_shadow_reports.py`
- Modify: `tests/test_post_grading_shadow_reports.py`

- [x] Use only the last fully graded pre-freeze slate for selection; all later rows are holdout.
- [x] Freeze the exact rule and SHA-256 fingerprint, or record `no_candidate` and stop.
- [x] Count only rows with mature pre-lock evidence and no critical attribution gap.
- [x] Keep output post-grading-only and add a skip flag to the research runner.
- [ ] Commit `test: freeze selective lean holdout candidate` only if a nominee exists.

### Task 3: Review without promotion

**Files:**

- Create: `docs/research/selective-lean-preclose-review.md`
- Modify: `docs/current-state.md`

- [x] Report historical nomination data separately from prospective holdout data.
- [x] Include side, price, K-line, quality, timing, model/market, Path B, workload, CLV/proxy, provider, agreement, and rolling windows.
- [x] Issue `continue_research`, `ready_for_separate_shadow_design`, or `retire`.
- [x] Stop before any official-pick or staking design.
- [x] Run all focused tests, the full Python suite, and `git diff --check`.
- [ ] Commit `docs: review selective lean preclose research`.

