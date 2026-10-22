# Supabase Migration History Alignment Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align local Supabase migration files with the live 2026-05-18 migration history so future provider-infrastructure deploys are reproducible.

**Architecture:** Preserve the live database behavior and repair the repo/history mismatch by using timestamped migration filenames that match Supabase's recorded versions. Keep the provider runtime hardening migration idempotent because the indexes already exist live.

**Tech Stack:** Supabase Postgres migrations, pytest schema checks, PowerShell/Git.

---

## Scope

This is a migration-history repair only. It must not change provider order, production odds source, model math, thresholds, staking, dashboard artifacts, retention, or notification behavior.

## Files

- Rename: `supabase/migrations/20260518_*.sql` to timestamped `20260518HHMMSS_*.sql` files matching live migration history.
- Add: `supabase/migrations/20260518174819_market_state_write_guards_fail_closed_legacy_selected.sql`
- Modify: `tests/test_live_layer_schema.py`
- Modify: `tests/test_boltodds_schema.py`
- Modify: `docs/superpowers/plans/2026-05-13-boltodds-propline-official-provider-cutover.md`

## Tasks

- [x] **Step 1: Confirm live migration history**

Run a read-only Supabase query against `supabase_migrations.schema_migrations` for versions starting with `20260518`.

Expected live versions:

```text
20260518174018_market_state_write_guards
20260518174322_market_state_write_guards_tighten_churn
20260518174819_market_state_write_guards_fail_closed_legacy_selected
20260518175106_market_state_write_guard_search_path
20260518175711_market_state_write_guard_ignore_legacy_updates
20260518180629_market_state_write_guard_block_legacy_selected_marker
20260518181008_market_state_write_guard_current_throttle_10_min
20260518181547_market_state_write_guard_block_legacy_decisions
```

- [x] **Step 2: Record provider runtime hardening in live history**

Apply the idempotent provider runtime hardening migration so Supabase records:

```text
20260518213238_provider_runtime_hardening
```

The SQL uses `create index if not exists`, so existing live indexes remain unchanged.

- [x] **Step 3: Align local migration filenames**

Rename the local date-only files to the timestamped versions above, and add the missing fail-closed migration file for the live `20260518174819` step.

- [x] **Step 4: Add regression coverage**

Add tests that require all migration filenames to use a 14-digit timestamp prefix and require the local 2026-05-18 migration set to include the live versions.

- [x] **Step 5: Verify**

Run:

```powershell
python -m pytest tests/test_live_layer_schema.py tests/test_boltodds_schema.py -q
python -m pytest tests -q
git status --short
```
