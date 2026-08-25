# Active Provider Compaction Finalizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` when explicitly delegated, or `superpowers:executing-plans` when working directly through these checkpoints.

**Goal:** Prevent live compact-market publication from silently accepting a truncated 20,000-row prefix, add an exact read-only provider/date preview path for the 105 known incomplete active-provider partitions, and preserve the proven PropLine May 17 prior-day carryover class.

**Architecture:** Keep the frequent live compactor bounded and fail closed when its page ceiling is reached. Use the existing partition repair utility as the slower exact keyset-paged finalizer/preview foundation, while keeping active-provider execution disallowed. Build the 105-partition manifest from the completed August 25 audit checkpoints so no broad Supabase rerun is needed. Extend the bounded-retention proof only for the exact PropLine carryover dimensions already verified.

**Tech Stack:** Python 3.11, pytest, the existing Supabase REST writer, and linked Supabase CLI for one SELECT-only validation.

**Spec:** `docs/superpowers/plans/2026-08-18-bounded-retention-audit.md`

## Global constraints

- No deployment, merge to `main`, database write, deletion, vacuum, retention activation, provider/model/notification/lock/UI change, or source-of-truth change.
- Keep active-provider repair execution fail closed. Only the existing retired BoltOdds execution allowlist may remain.
- Use the completed August 25 checkpoint set for the 105-partition aggregate preview; do not rerun the 360-query audit.
- Supabase validation is limited to one narrow PropLine May 17 SELECT-only query. Do not retry rapidly on a pooler or authentication failure.
- Never print credentials or tokens.

### Task 1: Import the reviewed exact-partition foundation

**Files:**
- Modify: `scripts/repair_compact_market_snapshot_partition.py`
- Modify: `tests/test_repair_compact_market_snapshot_partition.py`

1. Bring only the reviewed keyset paging, source-state binding, cross-Phoenix carryover preservation, and multi-date retired-BoltOdds allowlist from commit `e2a9d5f3` onto this branch.
2. Do not import that commit's documentation changes and do not add PropLine or TheRundown to the execution allowlist.
3. Run:

```powershell
python -m pytest tests/test_repair_compact_market_snapshot_partition.py -q
```

Expected: all imported foundation tests pass.

### Task 2: Make live compaction fail closed at the row ceiling

**Files:**
- Modify: `tests/test_compact_market_snapshots_script.py`
- Modify: `scripts/compact_market_snapshots.py`

1. Add a test that returns a full page for every allowed page and asserts `_fetch_snapshot_pages` raises a page-ceiling error.
2. Add a `run()`-level test proving the same condition performs no compact upsert and no provider-usage write.
3. Run the focused tests and confirm they fail for the expected silent-prefix reason.
4. Implement the minimal guard: if all allowed pages are full, raise before returning rows.
5. Run:

```powershell
python -m pytest tests/test_compact_market_snapshots_script.py tests/test_market_snapshot_compaction.py -q
```

Expected: all tests pass and existing deterministic duplicate behavior is unchanged.

### Task 3: Let exact previews exceed 20,000 rows without opening execution

**Files:**
- Modify: `tests/test_repair_compact_market_snapshot_partition.py`
- Modify: `scripts/repair_compact_market_snapshot_partition.py`

1. Add a test proving keyset preview paging continues beyond 20 full 1,000-row pages.
2. Add a test proving the enlarged exact-preview ceiling still fails closed if every allowed page is full.
3. Add a test proving a PropLine or TheRundown execution attempt remains blocked before any write.
4. Increase only the preview page ceiling to 75 pages, above the observed 55,232-row maximum, while preserving keyset paging and all execution gates.
5. Run:

```powershell
python -m pytest tests/test_repair_compact_market_snapshot_partition.py -q
```

Expected: exact previews can cover the known active partitions; active-provider execution remains blocked.

### Task 4: Build the 105-partition aggregate preview manifest

**Files:**
- Create: `scripts/build_active_provider_compaction_preview_manifest.py`
- Create: `tests/test_build_active_provider_compaction_preview_manifest.py`

1. Add fixtures for complete PropLine/TheRundown date coverage, mixed exact/incomplete partitions, inconsistent query hashes, missing dates, and overwrite refusal.
2. Confirm the tests fail because the manifest builder does not yet exist.
3. Implement a local-only checkpoint reader that:
   - reads no Supabase data and makes no network requests;
   - validates one audit date and query-contract hash;
   - requires every requested provider/date exactly once;
   - emits only aggregate partition counts and timestamps;
   - lists repair partitions where missing plus mismatched groups is nonzero;
   - records `database_write_performed=false`, `deletion_approved=false`, and `retention_execution_closed=true`;
   - refuses to overwrite an existing output.
4. Run:

```powershell
python -m pytest tests/test_build_active_provider_compaction_preview_manifest.py -q
python scripts/build_active_provider_compaction_preview_manifest.py --checkpoint-dir "C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge\analytics\output\retention\canonical-2026-08-25-e309" --output "analytics\output\retention\active-provider-compaction-preview-2026-08-25.json"
```

Expected: 105 repair partitions, 34,861 aggregate upserts, 63 PropLine dates, and 42 TheRundown dates, with no database writes.

### Task 5: Preserve the exact PropLine May 17 carryover class

**Files:**
- Modify: `tests/test_retention_bounded_sql.py`
- Modify: `scripts/retention_bounded_sql.py`

1. Add SQL contract tests for a `propline_may17_prior_day_carryover` class requiring:
   - compact provider and slate date `propline` / `2026-05-17`;
   - linked source run slate date `2026-05-16`;
   - Phoenix observation date `2026-05-16`;
   - exact provider/book/player/side/line dimensions;
   - exact preservation in the canonical PropLine May 16 compact partition.
2. Confirm the focused tests fail because the class is absent.
3. Add only that bounded candidate and dimension branch to the existing proof query.
4. Run:

```powershell
python -m pytest tests/test_retention_bounded_sql.py -q
```

Expected: existing BoltOdds classes remain unchanged and the PropLine class is explicit and fail closed.

### Task 6: Run bounded verification

**Files:**
- Generated, ignored: `analytics/output/retention/active-provider-compaction-preview-2026-08-25.json`

1. Inspect the manifest totals against the completed August 25 audit evidence.
2. Generate the revised single-partition PropLine May 17 SELECT-only SQL.
3. From the linked main clone, run exactly one query:

```powershell
npx supabase db query --linked --file <generated-propline-may17-sql> -o json
```

Expected: 24 rows classified as the bounded carryover, zero unpreserved unexpected groups, and no write statement.
4. Remove the temporary SQL/result files after recording aggregate evidence.
5. On any CLI pooler/auth failure, stop without retrying and report reduced confidence.

### Task 7: Document, verify, and publish the feature branch

**Files:**
- Modify: `docs/superpowers/plans/2026-08-18-bounded-retention-audit.md`
- Modify: `docs/current-state.md`
- Modify: this plan

1. Record the implementation and preview results, explicitly stating that no deployment or database mutation occurred and deletion remains closed.
2. Run focused tests, then:

```powershell
python -m pytest tests -q
git diff --check
git status --short
```

3. Restore any generated tracked analytics report changed only by the test suite.
4. Review the diff for accidental provider/runtime/allowlist changes.
5. Commit the scoped changes and push `codex/retention-active-provider-finalizer`.
6. Do not merge or deploy. A later production rollout or database repair requires a separate decision.

## Execution record

- Implemented test-first on isolated branch
  `codex/retention-active-provider-finalizer`; no production deployment or
  database mutation occurred.
- The live compactor now fails closed before compact/provider-usage
  publication when every bounded page is full. The exact partition previewer
  uses deterministic keyset paging through a 75-page ceiling, while PropLine
  and TheRundown execution remain blocked.
- The local checkpoint manifest reconciled the completed August 25 audit to
  `105` active-provider repair partitions and `34,861` aggregate upserts:
  PropLine `63/15,387`, TheRundown `42/19,474`.
- The first narrow linked SELECT-only read completed without a retained
  terminal stream. After confirming it had ended, one repeat proved all `24`
  PropLine May 17 extras are exact May 16 carryover; preserved `24`,
  unpreserved `0`, and `retention_preservation_complete: true` under query contract
  `611dd4eb568a556d96658e74049d6579d2f6ac0f9cacdff57720b3176f97929e`.
  Both invocations were read-only.
- Focused verification passed `96` tests, all four changed/added scripts passed
  `py_compile`, and the complete repository suite passed `2,526` tests. The
  generated Gate F report was restored to its committed evidence.
- Deletion, vacuum/reclamation, active-provider repair execution, deployment,
  merge, and every provider/model/notification/lock/UI/source-of-truth change
  remain closed and require separate approval.

## 2026-08-25 Deployment record

- Tyler separately approved deployment of the fail-closed compaction safeguard
  only. Commit `643c8c10` was fast-forwarded to `main`; the merged tree passed
  all `2,526` tests and was pushed without changing the active-provider
  execution allowlist.
- The `main` push auto-deployed only `bbe-live-layer` as Render deploy
  `dep-da6u6j8ae00c7399fr6g`. It reached `live` at
  `2026-08-25T18:48:26Z` on the exact approved commit.
- The first post-deploy scheduled cycle used remote artifacts, completed at
  `2026-08-25T18:51:06Z`, and produced no error-level Render logs. It reported
  `compact:0` because compaction was not yet due.
- The most recent compact update was `2026-08-25T18:41:16Z`; with the existing
  1,800-second interval, the first normal due cron is
  `2026-08-25T19:20:00Z`. Observation of that cycle remains a separate pending
  verification item; the guard has not yet been claimed as naturally
  exercised.
- No active-provider repair, deletion, vacuum/reclamation, retention
  activation, provider/model/notification/lock/UI/source-of-truth change,
  Render setting, or environment-variable change was executed. The `34,861`
  aggregate repair-upsert gate remains closed pending a separate exact design
  and approval.

## 2026-08-25 First Due-Cycle Observation And Local Isolation Follow-Up

- The first compaction-due live-layer cycle started at
  `2026-08-25T19:20:12Z` and finished successfully at
  `2026-08-25T19:21:26Z`. The new safeguard naturally reached the 20,000-row
  ceiling, logged `snapshot query reached its fail-closed page ceiling`, and
  performed no partial compact publication.
- A linked SELECT after the cycle found the August 25 compact state unchanged
  at `876` rows, `20,000` represented snapshots, and latest update
  `2026-08-25T18:41:16.124362Z`. The rest of the live build continued from the
  remote artifact and completed normally.
- The contained compaction exception still collapsed the combined market-state
  result to top-level `build_failed`. Both the legacy and active V2 Alt
  recorders therefore returned `prerequisite_failed`, even though neither
  recorder consumes the compact table.
- Tyler approved a bounded local fix on branch
  `codex/compaction-alt-failure-isolation`: contain only the compact sub-result,
  keep its warning explicit, and exclude only that sub-result from the legacy
  and V2 Alt prerequisite checks. Top-level, current-line, official-line,
  lock, timing, and ready-to-bet failures remain blocking.
- The frequent compactor remains bounded at 20,000 rows. Raising it to the
  75,000-row exact-preview ceiling is intentionally outside this fix because
  it would repeat a large Supabase read every 30 minutes. Complete active-
  provider compaction needs a separate low-frequency finalizer design.
- Focused local verification passed `173` tests, and the complete repository
  suite passed `2,531` tests. The branch is not merged or deployed, and it
  performed no database mutation. Active-provider repair,
  deletion, vacuum/reclamation, retention activation, and every provider/
  model/notification/lock/UI/source-of-truth gate remain closed.
