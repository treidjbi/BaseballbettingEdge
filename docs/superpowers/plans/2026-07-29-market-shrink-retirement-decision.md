# Market-Shrink Retirement Decision Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decide whether market-shrink should remain as low-cost diagnostic metadata or be retired from active shadow collection after a large negative graded sample.

**Architecture:** Extend the existing canary audit with decision-value and marginal-cost accounting. The review separates prediction diagnostics from betting performance, verifies whether the metadata changed any research conclusion, and produces a retain/retire recommendation. Disabling the Render flag is a separate Tyler-approved action.

**Tech Stack:** Python 3.11, existing market-shrink audit, Gate F challenger report, Gate C JSONL, Render/Supabase read-only evidence, pytest.

## Global Constraints

- Current evidence is `605` graded metadata rows, `300-305`, `-42.56u`, `-7.0%`, with zero applied rows.
- More rows are not the primary gate. A promotion path is closed unless a new candidate definition is proposed in a separate research plan.
- Preserve historical outputs and metadata provenance even if future collection is retired.
- Do not change `MARKET_SHRINK_PROJECTION_MODE`, projection math, lambda, thresholds, staking, provider behavior, notifications, locks, artifacts, UI, retention, or environment variables in this plan.
- Decision outcomes are exactly `retain_diagnostic_shadow`, `retire_after_approval`, or `replace_with_new_research_plan`.

---

### Task 1: Add decision-value accounting

**Files:**

- Modify: `analytics/diagnostics/market_shrink_projection_canary_audit.py`
- Modify: `tests/test_market_shrink_projection_canary_audit.py`

- [ ] Write failing tests for applied count, would-change count, selected-lambda drift, verdict-change agreement, projection-error lift, and missing metadata.
- [ ] Add current-provider and recent-14 scoreboards plus paired current-lambda projection error.
- [ ] Report whether shrink metadata changed any Gate F, no-drag, Strong Base, or market-anchor research classification.
- [ ] Emit a deterministic `decision_value` block without mutating runtime state.
- [ ] Run `python -m pytest tests/test_market_shrink_projection_canary_audit.py -v`.
- [ ] Commit `feat: add market shrink decision value audit`.

### Task 2: Measure marginal cost and dependencies

**Files:**

- Create: `docs/research/market-shrink-retirement-review.md`
- Modify: `docs/provider-cost-ledger.md` only if verified marginal provider or compute cost exists
- Modify: `docs/operational-risk-register.md` only if retirement changes a tracked risk

- [ ] Verify whether the shadow calculation causes provider calls, database rows, artifact bloat, or material cron duration; distinguish zero marginal provider cost from nonzero operational noise.
- [ ] Identify reports/tests that depend on the metadata and the preservation path for historical analysis.
- [ ] Treat zero betting lift but useful projection-error attribution as a possible reason to retain a cheaper diagnostic subset.
- [ ] Recommend one of the three allowed outcomes with exact evidence.
- [ ] Do not edit a Render environment variable.
- [ ] Commit `docs: decide market shrink shadow posture`.

### Task 3: Prepare, but do not execute, retirement

**Files:**

- Modify only after a `retire_after_approval` result: `docs/current-state.md`
- Create only after a `retire_after_approval` result: `docs/research/market-shrink-retirement-runbook.md`

- [ ] Document the exact services carrying `MARKET_SHRINK_PROJECTION_MODE`, expected off-state metadata, rollback value, and verification commands.
- [ ] Require a separate Tyler approval before changing the flag or deploying Render services.
- [ ] Run focused tests, `python -m pytest tests -q`, and `git diff --check`.
- [ ] Commit `docs: prepare market shrink retirement runbook` only if retirement is selected.

