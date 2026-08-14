# Selective LEAN Prospective Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the approved, research-only prospective counter for
`expand_lean_low_line_capped_model_fade` without changing any live behavior.

**Architecture:** Add one frozen Gate C diagnostic with deterministic
eligibility, reconciliation, slices, and review gates. Run it only inside the
existing post-grading research runner and write ignored local outputs.

**Tech Stack:** Python 3.11, Gate C JSONL, pytest, existing post-grading runner.

**Design:**
`docs/superpowers/specs/2026-08-14-selective-lean-prospective-audit-design.md`

## Constraints

- Prospective credit starts 2026-08-15; August 13-14 are a non-credit freeze
  gap.
- Pin the approved fingerprint
  `4e00a180e35fe75dc8889d47065a25c4351cb37ac55664eb42f01b77c07fd13a`.
- Fail closed on missing consumed-lock proof, provider attribution, market
  agreement, post-start timing, recovered history, or duplicate keys.
- Reuse Gate C and existing derived labels. Add no table, API call, production
  writer, or new dependency.
- Passing the research floor opens only a separate review.

### Task 1: Freeze the contract with failing tests

**Files:**

- Create: `tests/test_selective_lean_prospective_audit.py`

- [x] Pin the selector definition and fingerprint.
- [x] Cover exact match/non-match behavior and verdict precedence.
- [x] Cover consumed-lock proof and attribution fail-closed behavior.
- [x] Cover freeze-gap and no-back-credit behavior.
- [x] Cover duplicate blocking, slice output, and review gates.
- [x] Run the focused test and confirm it fails before implementation.

### Task 2: Implement the audit

**Files:**

- Create: `analytics/diagnostics/selective_lean_prospective_audit.py`

- [x] Implement load, selection, critical-input checks, scoring, slices, gates,
  reconciliation, Markdown rendering, JSON writing, and CLI.
- [x] Keep all output bounded and research-only.
- [x] Run the focused test to green.

### Task 3: Integrate the post-grading runner

**Files:**

- Modify: `scripts/run_post_grading_shadow_reports.py`
- Modify: `tests/test_post_grading_shadow_reports.py`

- [x] Write a failing runner test for invocation and independent skip behavior.
- [x] Add Markdown/JSON CLI paths, the skip flag, invocation, and a bounded
  summary excerpt.
- [x] Run both focused test files to green.

### Task 4: Record the research posture

**Files:**

- Modify: `docs/superpowers/plans/2026-07-29-selective-lean-preclose-research-funnel.md`
- Create: `docs/research/selective-lean-preclose-review.md`
- Modify: `docs/research/2026-07-29-research-candidate-plan-map.md`
- Modify: `docs/current-state.md`

- [x] Separate locked historical nomination from zero formal prospective rows.
- [x] Record consumed-lock linkage as the first fail-closed evidence blocker.
- [x] Keep every production and promotion gate closed.

### Task 5: Verify and hand off locally

- [x] Run focused audit and runner tests.
- [x] Run the complete Python test suite.
- [x] Run local diagnostic smoke tests against stale checked-in and fresh review
  Gate C inputs.
- [x] Run `git diff --check` and inspect `git status`.
- [x] Do not commit, push, deploy, or activate without separate Tyler approval.

## 2026-08-14 deployment record

Tyler separately approved merge and deployment. Exact commit `5f3b010c`
passed all `2,015` tests on both the feature branch and merged `main`, was
pushed to GitHub, and is live only as an intentional research release on
`bbe-gate-c-post-grading-review` deploy `dep-d9vkm6ou01pc738c91c0`.
Verification job `job-d9vkmqflk1mc738bb57g` succeeded at
`2026-08-14T17:12:03Z`.

The GitHub push also triggered the pre-existing auto-deploy setting on
`bbe-live-layer`; deploy `dep-d9vklmjl550s73fvr180` reached live on the same
commit. The commit changed no live-layer file or configuration, and the first
post-deploy scheduled run succeeded at `2026-08-14T17:11:21Z`. No pipeline
cron was redeployed, BoltOdds remained suspended, and every live behavior gate
remains closed.
