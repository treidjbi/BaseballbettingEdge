# Four-Action Operations Follow-Through Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Tyler's four approved July 28 follow-ups as read-only operational reviews: publisher-timeout diagnosis, no-drag/strict-runtime-core packet, retention readiness decision, and a natural-refresh lineup/PropLine maturity check.

**Architecture:** Keep each review independent and evidence-backed. Query existing Render, Supabase, and served-artifact surfaces without triggering pipeline repairs or changing runtime configuration. Record conclusions in research handoffs, then update the Four-Lane Operating Board only for material evidence changes.

**Tech Stack:** PowerShell, Git, Render read-only API tooling already present in the repo, linked Supabase CLI SQL, production `get-artifact`/comparison endpoints, Markdown handoffs.

---

Date: 2026-07-28
Owner: Tyler + Codex
Status: Complete; verified and pushed on the isolated review branch

## Guardrails

- Do not dispatch GitHub rollback workflows or trigger Render jobs.
- Do not change code, production environment variables, provider order, strictness, model behavior, notifications, locks, UI, retention, or artifact source-of-truth behavior.
- Do not execute retention deletion or compaction writes.
- Treat the no-drag and strict-runtime-core evidence as a review packet, not a promotion approval.
- Observe the next normal refresh rather than forcing a refresh.

### Task 1: Establish a reproducible evidence baseline

- [x] Confirm repo root, remote, branch, clean tree, and current `origin/main` ancestry.
- [x] Read the current model and retention checkpoints plus the latest automation handoff.
- [x] Run the existing test baseline before editing handoff documents.

### Task 2: Diagnose artifact-publisher statement timeouts

- [x] Capture both July 27 failure windows and the adjacent successful lock cycles.
- [x] Trace the lock publication call from Render wrapper through the Supabase artifact upsert.
- [x] Compare payload count/size, table/index health, and historical timeout frequency using read-only evidence.
- [x] Document scope, impact, root-cause confidence, and separately gated resilience options.

### Task 3: Prepare the no-drag / strict-runtime-core packet

- [x] Reconcile the frozen no-drag baseline, fingerprint, prospective counter, and current-provider segment.
- [x] Report strict-runtime-core results with required sample, date, side, price, K-line, timing, provider, and concentration caveats when available.
- [x] Keep the August 10 decision checkpoint and state whether the evidence is review-ready or promotion-ready.

### Task 4: Run the retention readiness decision

- [x] Execute storage, row-volume, and retention-readiness SQL through the linked CLI.
- [x] Validate 14-day and 30-day raw-row/byte estimates and compact-coverage gaps.
- [x] Record an explicit delete/no-delete decision and the next safe evidence step.

### Task 5: Observe lineup and PropLine fallback maturation

- [x] Wait for the next naturally scheduled artifact refresh.
- [x] Compare artifact generation time, lineup confirmation, quality caps, source attribution, and the PropLine fallback row with the prior read.
- [x] Report only actionable changes; do not trigger a repair or source switch.

### Task 6: Handoff and verification

- [x] Update controlling research checkpoints and `docs/current-state.md` only where the evidence materially changed.
- [x] Run document/link checks, `git diff --check`, and the relevant test verification.
- [x] Commit and push the isolated review branch; leave production unchanged.
