# July 27 Operations Action Items Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove normalized pitcher-name duplicates from the approved artifact path, schedule a bounded shadow-candidate review, schedule a dry-run-only retention decision, and restore verified Render CLI access.

**Architecture:** Keep the repair inside the ephemeral SQLite history hydration/seeding boundary, where exact display-name uniqueness currently allows accented aliases to coexist. Preserve display names while comparing identities with the existing `pipeline.name_utils.normalize` function. Keep model and retention decisions in separate read-only packets, then deploy only the approved pipeline repair through the existing seven-cron helper and verify the public Supabase/Netlify artifacts.

**Tech Stack:** Python 3.11, SQLite, pytest, Markdown operating packets, Supabase CLI read-only SQL, Render CLI v2.17.

## Global Constraints

- Do not change model math, parameters, formula dates, thresholds, staking, provider order, source-of-truth rules, notification behavior, lock behavior, dashboard behavior, secrets, environment variables, or retention rows.
- TheRundown-derived Render artifacts served through Supabase/Netlify remain production truth; PropLine remains fallback/live-movement sidecar; BoltOdds remains retired.
- History deduplication identity is exactly normalized `date + pitcher + side`, matching the existing SQLite uniqueness grain except for accent/case normalization.
- When duplicate history rows conflict, preserve a graded row over an ungraded row, then a locked row over an unlocked row, then the later serialized row so the freshest display spelling survives.
- No retention deletion is authorized. Retention work is query, packet, and scheduled decision only.
- Shadow review work may recommend another review; it cannot enable market-shrink, market-anchor, no-drag, or any live selector.
- Deployment requires a committed and pushed repair, authenticated Render CLI access, green tests, successful cron deploys, and direct artifact verification.

---

### Task 1: Repair normalized pitcher identity at history hydration and seeding

**Files:**
- Modify: `pipeline/fetch_results.py`
- Modify: `tests/test_fetch_results.py`

**Interfaces:**
- Produces: `_pick_identity(row) -> tuple[str, str, str] | None`, `_deduplicate_history_rows(rows) -> list[dict]`, and `_stored_pitcher_alias(conn, date, pitcher, side) -> str | None`.
- `load_history_into_db()` consumes `_deduplicate_history_rows` before inserts.
- `seed_picks()` consumes `_stored_pitcher_alias` and updates an unlocked normalized match rather than inserting an alias duplicate.

- [ ] **Step 1: Add the failing history-hydration regression test**

Add a test with two `2026-07-27` Under rows named `Martin Perez` and `Martin Pérez`. Make the unaccented row unlocked and the accented row locked. Assert that `load_history_into_db()` writes exactly one row and preserves the locked accented row.

- [ ] **Step 2: Run the hydration test and verify RED**

Run:

```powershell
python -m pytest tests/test_fetch_results.py::TestLoadHistoryIntoDb::test_deduplicates_normalized_pitcher_aliases_and_preserves_locked_row -q
```

Expected: FAIL because both exact display names are currently inserted.

- [ ] **Step 3: Add the failing future-seed regression test**

Load an open `Martin Perez` history row, then seed a current `Martin Pérez` card for the same date and side. Assert one database row, current accented display spelling, and an inserted count of zero.

- [ ] **Step 4: Run the seed test and verify RED**

Run:

```powershell
python -m pytest tests/test_fetch_results.py::TestSeedPicks::test_reuses_normalized_pitcher_alias_instead_of_inserting_duplicate -q
```

Expected: FAIL because the exact-name unique index currently permits a second row.

- [ ] **Step 5: Implement normalized history deduplication**

Use the existing `_normalize` import and this identity/rank shape:

```python
def _pick_identity(row: dict) -> tuple[str, str, str] | None:
    date = str(row.get("date") or "").strip()
    pitcher = _normalize(str(row.get("pitcher") or ""))
    side = str(row.get("side") or "").strip().lower()
    if not date or not pitcher or side not in {"over", "under"}:
        return None
    return date, pitcher, side


def _history_row_rank(row: dict, index: int) -> tuple[int, int, int]:
    return int(bool(row.get("result"))), int(bool(row.get("locked_at"))), index
```

Keep rows without a valid identity unchanged. For duplicate identities, retain the highest rank and preserve deterministic first-identity ordering.

- [ ] **Step 6: Implement normalized alias reuse in `seed_picks()`**

Query same-date/same-side pitchers, compare each with `_normalize`, and reuse the stored display name for `INSERT OR IGNORE` and `WHERE` clauses. When the row is unlocked, update `pitcher` to the current card spelling in the same statement that refreshes its current values.

- [ ] **Step 7: Run focused tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_fetch_results.py -q
python -m pytest tests/test_run_pipeline.py -q
```

- [ ] **Step 8: Commit the repair**

```powershell
git add pipeline/fetch_results.py tests/test_fetch_results.py docs/superpowers/plans/2026-07-27-operations-action-items.md
git commit -m "fix: dedupe normalized pitcher history identities"
```

---

### Task 2: Schedule the separate shadow-candidate review

**Files:**
- Create: `docs/research/2026-07-27-shadow-candidate-review-schedule.md`
- Modify: `docs/current-state.md`

**Interfaces:**
- Consumes: the July 27 market-anchor, market-shrink, moderate-edge-clean, CLV-supported, and no-drag evidence.
- Produces: an exact review date, required inputs, blocking slices, and a no-promotion decision boundary.

- [ ] **Step 1: Refresh the read-only evidence packet**

Use production artifacts and existing diagnostic outputs in a temp directory. Record current sample, date range, PnL/ROI, provider-era, side, K-line, quality, CLV, workload, Path B, and market-agreement coverage. Treat the production-index rebuild as partial when it does not cover April 28 onward.

- [ ] **Step 2: Write the scheduled review packet**

Set the review date to `2026-08-10`, after another 14-slate observation window. Require:

- market-anchor strict and strict-FIRE side/K-line/CLV/provider/market-agreement slices;
- market-shrink decision-changing counterfactuals rather than metadata-cohort PnL;
- moderate-edge-clean and CLV-supported de-duplicated current-provider samples;
- no-drag baseline reconciliation before any row advances the 52/75 counter.

The only allowed decisions are `keep_soaking`, `draft_new_shadow_candidate`, or `close_candidate`. Live promotion is out of scope.

- [ ] **Step 3: Update the Four-Lane Operating Board**

Add the scheduled review and current blockers to the Model and Tracking lanes without changing any live stage or gate.

- [ ] **Step 4: Validate the packet**

Run:

```powershell
rg -n "2026-08-10|keep_soaking|draft_new_shadow_candidate|close_candidate|52/75|no promotion" docs/research/2026-07-27-shadow-candidate-review-schedule.md docs/current-state.md
```

- [ ] **Step 5: Commit the shadow-review schedule**

```powershell
git add docs/research/2026-07-27-shadow-candidate-review-schedule.md docs/current-state.md
git commit -m "docs: schedule shadow candidate review"
```

---

### Task 3: Schedule the dry-run-only retention decision

**Files:**
- Create: `docs/research/2026-07-27-supabase-retention-decision.md`
- Modify: `docs/current-state.md`

**Interfaces:**
- Consumes: `scripts/supabase_storage_guardrail.sql`, `scripts/supabase_row_volume_guardrail.sql`, and `scripts/supabase_retention_readiness.sql` read-only results.
- Produces: an exact `2026-08-03` yes/no review with required compact coverage and rollback criteria.

- [ ] **Step 1: Run the three read-only guardrails**

Run each query once through `npx supabase db query --linked --file ... -o json`. Do not run `scripts/retire_market_snapshots.py --execute` and do not set `ALLOW_MARKET_SNAPSHOT_DELETE`.

- [ ] **Step 2: Write the retention decision packet**

Record database/table size, 14-day and 30-day candidate rows, compact coverage, coverage gaps, provider/date samples, and projected headroom. Schedule the decision for `2026-08-03` with only `continue_observing`, `approve_bounded_retirement`, or `fix_compaction_first` as allowed outcomes.

- [ ] **Step 3: Update the Tracking lane**

Add the scheduled decision and keep deletion closed unless a later Tyler approval explicitly selects `approve_bounded_retirement` after exact coverage verification.

- [ ] **Step 4: Validate the packet**

Run:

```powershell
rg -n "2026-08-03|continue_observing|approve_bounded_retirement|fix_compaction_first|deletion remains closed" docs/research/2026-07-27-supabase-retention-decision.md docs/current-state.md
```

- [ ] **Step 5: Commit the retention schedule**

```powershell
git add docs/research/2026-07-27-supabase-retention-decision.md docs/current-state.md
git commit -m "docs: schedule Supabase retention decision"
```

---

### Task 4: Restore Render authentication, publish the repair, and prove live behavior

**Files:**
- No code files beyond Tasks 1-3.
- Update: `docs/current-state.md` only if live deployment evidence materially changes the Pipeline lane.

**Interfaces:**
- Consumes: pushed `main`, Render CLI saved login, `scripts/deploy_render_pipeline_crons.py`, and public `get-artifact` endpoints.
- Produces: authenticated service inventory, seven successful pipeline cron deploys, and a fresh artifact with one normalized Pérez pick.

- [ ] **Step 1: Restore CLI authentication**

Run `render login --confirm`, complete the dashboard OAuth flow, then verify:

```powershell
render whoami -o json
render workspace current -o json
render services --output json
```

Do not print or copy tokens.

- [ ] **Step 2: Run full verification before integration**

```powershell
python -m pytest tests/ -q
git status --short
```

- [ ] **Step 3: Push the feature branch and integrate it into `main`**

Push the branch, fast-forward `main` only after the full suite is green, and push `main`. Verify `main` and `origin/main` match.

- [ ] **Step 4: Redeploy the approved pipeline cron group**

Run the existing validated helper from clean `main`:

```powershell
python scripts/deploy_render_pipeline_crons.py --execute
```

Verify each affected service reaches a successful deploy on the pushed commit. Do not change environment variables or schedules.

- [ ] **Step 5: Verify artifact repair**

Wait for the next approved Render refresh, then verify public `today` and `picks_history` artifacts have:

- one normalized `Martin Perez` identity for `2026-07-27 + under`;
- the canonical current display spelling `Martin Pérez`;
- unchanged line `3.5`, side `under`, verdict metadata, provider/source posture, model lambda, thresholds, locks, and notification classes.

Also verify Alt V2 still has one normalized candidate and no proof errors.

- [ ] **Step 6: Record deployment proof and final clean state**

Update the plan and `docs/current-state.md` with exact commit/deploy/artifact timestamps only after direct proof. Commit and push documentation, then verify both the main clone and worktree have no unexpected state.

---

## Self-Review

- Spec coverage: all four approved action items have an independent task and verification gate.
- Placeholder scan: no TBD/TODO/implement-later language is present.
- Type consistency: normalized identity is `tuple[str, str, str]`; allowed review outcomes are pinned in Tasks 2 and 3.
- Safety: model, provider, notification, lock, dashboard, staking, threshold, source-of-truth, and deletion behavior remain unchanged.
