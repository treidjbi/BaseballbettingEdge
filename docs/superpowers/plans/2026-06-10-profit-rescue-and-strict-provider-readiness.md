# Profit Rescue And Strict Provider Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a production-safe path to reduce unprofitable FIRE exposure while separately auditing whether BoltOdds + PropLine are ready for strict provider mode.

**Architecture:** Keep provider strictness and model profitability separate. Add a pure, feature-flagged verdict-conversion module that can only lower FIRE exposure and preserve raw verdict metadata; add read-only diagnostics for strict-provider readiness and profit-rescue impact. No lambda, calibration, global EV thresholds, staking, provider order, lock behavior, notification behavior, retention, or dashboard source-of-truth changes are approved by this plan.

**Tech Stack:** Python 3.11, pytest, Supabase linked CLI SQL, existing Gate C JSONL diagnostics.

---

## Guardrails

- `PROFIT_RESCUE_REFEREE_MODE=off|shadow|enforce` must default to `off`.
- Shadow mode may add metadata but must not change `verdict` or `actionable_verdict`.
- Enforce mode may only cap verdicts downward.
- Runtime rules must use only pregame/runtime-safe fields already present in pitcher records and side payloads.
- No LEAN promotion, FIRE promotion, lambda change, threshold change, staking change, provider change, notification change, lock change, retention deletion, or dashboard source-of-truth change is part of this work.
- Strict-provider readiness is read-only. Do not set `OFFICIAL_MARKET_STRICT=true` from this plan.

## Tasks

### Task 1: Profit-Rescue Referee

**Files:**
- Create: `pipeline/profit_rescue_referee.py`
- Modify: `pipeline/quality_gates.py`
- Test: `tests/test_profit_rescue_referee.py`

- [x] Write failing tests for off, shadow, and enforce modes.
- [x] Implement a pure verdict capper that:
  - caps remaining `FIRE 2u` to `FIRE 1u`;
  - caps remaining FIRE unders to `LEAN`;
  - caps remaining FIRE model-fades-market-favorite rows to `LEAN`;
  - records metadata under `profit_rescue_referee`;
  - never raises a verdict.
- [x] Wire it after quality gates and confidence referee.
- [x] Run focused tests.

### Task 2: Profit-Rescue Audit

**Files:**
- Create: `analytics/diagnostics/profit_rescue_audit.py`
- Create: `tests/test_profit_rescue_audit.py`
- Output: `analytics/output/profit_rescue_audit.md`

- [x] Write failing tests for proposed downgrade buckets and recent-window summaries.
- [x] Read the Gate C JSONL and summarize clean tracked win/loss rows by 7/14/21/30-day windows plus clean regime.
- [x] Compare current verdict results against the proposed rescue cap policy.
- [x] Render a concise markdown report with keep/downgrade/paper-only guidance.

### Task 3: Strict Provider Readiness

**Files:**
- Create: `scripts/supabase_strict_provider_readiness.sql`
- Create: `tests/test_supabase_strict_provider_readiness_sql.py`
- Output: `analytics/output/strict_provider_readiness.md`

- [x] Write a static SQL contract test that checks required tables and output labels.
- [x] Query artifact freshness, official/current market line coverage, provider audits, provider runs, request usage, lock rows, and webhook status.
- [x] Keep the report read-only and state go/no-go separately from any env-var change.

### Task 4: Docs And Handoff

**Files:**
- Modify: `docs/current-state.md`
- Modify: this plan

- [x] Update the model lane with the new downgrade-only rescue canary status.
- [x] Update the pipeline lane only with the strict-readiness audit status.
- [x] Do not mark strict provider mode or model rescue enforce mode promoted unless Tyler explicitly approves those env-var flips after reviewing evidence.

## 2026-06-10 Implementation Result

- `PROFIT_RESCUE_REFEREE_MODE` is implemented with default `off`; `shadow` adds metadata only; `enforce` caps remaining `FIRE 2u` to `FIRE 1u`, remaining FIRE unders to `LEAN`, and remaining model-fades-market-favorite FIRE rows to `LEAN`.
- `analytics/output/profit_rescue_audit.md` shows strong downside-control evidence on `854` clean tracked win/loss rows: current clean-regime FIRE exposure was `536` rows / `-34.07u`; proposed retained FIRE exposure was `118` rows / `+8.35u`; last 7 days improved from `64` FIRE rows / `-15.93u` to `11` retained FIRE rows / `-1.84u`.
- `scripts/supabase_strict_provider_readiness.sql` returned `readiness_status=watch`, with no blocking reasons but watch reasons for zero-row BoltOdds coverage audits, line conflicts, and provider-run failures.
- No environment variables were changed. Enforce mode and strict provider mode both remain separate Tyler approval decisions.
