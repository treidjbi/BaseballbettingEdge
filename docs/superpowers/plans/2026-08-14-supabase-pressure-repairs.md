# Supabase Pressure Repairs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the two confirmed avoidable Supabase pressure paths without changing provider, model, lock, notification, artifact-source, or retention behavior.

**Architecture:** Add one online partial B-tree index matching the live PropLine webhook inbox predicate. For lock-scope artifact publication, compare the locally computed canonical payload hashes with the current Supabase hashes and upsert only changed artifacts while preserving all three existing lock artifacts and the publication-run audit row.

**Tech Stack:** PostgreSQL/Supabase migration SQL, Python 3.11, pytest, existing `SupabaseMarketWriter` REST boundary.

## Global Constraints

- Do not apply the migration, run `supabase db push`, deploy, push Git, or change production configuration in this implementation session.
- Preserve TheRundown as official book-of-record and PropLine as fallback/live-movement sidecar.
- Preserve lock calculation/consumption, notification behavior, artifact keys, artifact payloads, and current source-of-truth rules.
- Do not delete, replay, or mark the 8,979 stale webhook rows.
- Keep the change minimal: no new dependencies and no compact-market reader refactor in this branch.
- Use TDD for Python behavior: write each regression test, verify the expected failure, implement the smallest passing change, then rerun the focused tests.

---

### Task 1: Online webhook inbox index migration

**Files:**
- Modify: `supabase/migrations/20260814175128_optimize_propline_webhook_inbox.sql`
- Create: `tests/test_propline_webhook_inbox_index_migration.py`

**Interfaces:**
- Consumes: live query predicate `processed = false AND received_at >= cutoff ORDER BY received_at ASC LIMIT 100`.
- Produces: partial B-tree index `idx_propline_webhook_deliveries_unprocessed_received_at` on `public.propline_webhook_deliveries (received_at ASC) WHERE processed IS FALSE`.

- [x] **Step 1: Write the failing migration-contract test**

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260814175128_optimize_propline_webhook_inbox.sql"


def test_webhook_inbox_index_matches_live_partial_ordered_query():
    sql = " ".join(MIGRATION.read_text(encoding="utf-8").lower().split())
    assert (
        "create index concurrently if not exists "
        "idx_propline_webhook_deliveries_unprocessed_received_at "
        "on public.propline_webhook_deliveries (received_at asc) "
        "where processed is false"
    ) in sql
```

- [x] **Step 2: Run the test and verify it fails because the CLI-created migration is empty**

Run: `python -m pytest tests/test_propline_webhook_inbox_index_migration.py -q`

Expected: one assertion failure because the partial index statement is absent.

- [x] **Step 3: Add the minimal online partial-index migration**

```sql
-- Apply only through a separately approved online migration step.
-- CONCURRENTLY avoids blocking the live webhook receiver while PostgreSQL builds the index.
create index concurrently if not exists idx_propline_webhook_deliveries_unprocessed_received_at
on public.propline_webhook_deliveries (received_at asc)
where processed is false;
```

- [x] **Step 4: Rerun the focused migration-contract test**

Run: `python -m pytest tests/test_propline_webhook_inbox_index_migration.py -q`

Expected: `1 passed`.

### Task 2: Content-aware lock artifact publication

**Files:**
- Modify: `scripts/publish_pipeline_artifacts_to_supabase.py`
- Modify: `tests/test_publish_pipeline_artifacts.py`

**Interfaces:**
- Consumes: candidate artifact rows from `collect_artifact_rows()` and current rows selected from `published_pipeline_artifacts` using `artifact_key` plus `payload_sha256`.
- Produces: `run()` result fields `artifact_count`, `candidate_artifact_count`, and `unchanged_artifact_count`; lock scope upserts only rows whose canonical hash differs or whose artifact key is absent.

- [x] **Step 1: Extend the test writer with the real select boundary**

```python
class FakeWriter:
    def __init__(self, selected_rows=None):
        self.selected_rows = list(selected_rows or [])
        self.selects = []
        self.upserts = []
        self.inserts = []

    def select_rows(self, table, params):
        self.selects.append((table, params))
        return list(self.selected_rows)
```

- [x] **Step 2: Write a failing regression test for a fully unchanged lock cycle**

Create all three lock-scope files, derive their candidate rows with `collect_artifact_rows`, feed only their `artifact_key`/`payload_sha256` values through `FakeWriter`, execute `run(..., scope="lock")`, and assert:

```python
assert result == {
    "artifact_count": 0,
    "candidate_artifact_count": 3,
    "unchanged_artifact_count": 3,
    "execute": True,
}
assert writer.upserts == []
assert writer.inserts[0][1][0]["artifact_count"] == 0
```

- [x] **Step 3: Write a second failing regression test for a partially changed lock cycle**

Provide current hashes for `today` and the dated slate but a deliberately stale hash for `picks_history`, then assert the sole upsert row has `artifact_key == "picks_history"`, `artifact_count == 1`, and `unchanged_artifact_count == 2`.

- [x] **Step 4: Run both new lock-scope tests and verify the expected failures**

Run: `python -m pytest tests/test_publish_pipeline_artifacts.py -k "lock_scope_skips_unchanged or lock_scope_upserts_only_changed" -q`

Expected: two failures because the existing implementation always upserts all three artifacts and does not return changed/unchanged counts.

- [x] **Step 5: Implement minimal hash filtering for lock scope**

Add a focused helper:

```python
def _changed_artifact_rows(*, writer, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    if not rows:
        return [], 0
    artifact_keys = [str(row["artifact_key"]) for row in rows]
    current_rows = writer.select_rows(
        "published_pipeline_artifacts",
        {
            "artifact_key": f"in.({','.join(artifact_keys)})",
            "select": "artifact_key,payload_sha256",
            "limit": str(len(artifact_keys)),
        },
    )
    current_hashes = {
        str(row.get("artifact_key")): str(row.get("payload_sha256"))
        for row in current_rows
        if row.get("artifact_key") and row.get("payload_sha256")
    }
    changed = [
        row for row in rows
        if current_hashes.get(str(row["artifact_key"])) != str(row["payload_sha256"])
    ]
    return changed, len(rows) - len(changed)
```

Use it only when `execute=True` and `scope == "lock"`. Do not call `upsert_rows` for an empty changed set. Continue writing one small `pipeline_artifact_publication_runs` audit row with the actual published count and unchanged count in metadata.

- [x] **Step 6: Rerun both lock-scope regression tests and verify they pass**

Run: `python -m pytest tests/test_publish_pipeline_artifacts.py -k "lock_scope_skips_unchanged or lock_scope_upserts_only_changed" -q`

Expected: `2 passed`.

- [x] **Step 7: Protect non-lock publication behavior**

Add a test asserting `scope="pipeline"` performs no hash-select and still publishes every collected artifact. This prevents the optimization from changing preview, grading, or full/refresh behavior.

- [x] **Step 8: Run the full publisher test module**

Run: `python -m pytest tests/test_publish_pipeline_artifacts.py -q`

Expected: all publisher tests pass.

### Task 3: Verification and handoff

**Files:**
- Review: `supabase/migrations/20260814175128_optimize_propline_webhook_inbox.sql`
- Review: `scripts/publish_pipeline_artifacts_to_supabase.py`
- Review: `tests/test_propline_webhook_inbox_index_migration.py`
- Review: `tests/test_publish_pipeline_artifacts.py`
- Update: automation memory only after verification.

**Interfaces:**
- Consumes: completed Task 1 and Task 2 changes.
- Produces: a clean, local, uncommitted feature branch ready for review; no remote or production mutation.

- [x] **Step 1: Run focused tests together**

Run: `python -m pytest tests/test_propline_webhook_inbox_index_migration.py tests/test_publish_pipeline_artifacts.py -q`

- [x] **Step 2: Run the complete Python suite**

Run: `python -m pytest tests/ -q`

- [x] **Step 3: Run read-only Supabase validation**

Run: `npx supabase db advisors --linked --type performance --level warn --fail-on none --output-format json`

Run: `npx supabase migration list --linked`

Do not run `supabase db push`, `supabase migration up`, or any SQL DDL against the linked project.

- [x] **Step 4: Review exact diff and repository state**

Run: `git diff --check`

Run: `git diff --stat`

Run: `git status --short --branch`

Confirm only the plan, migration, publisher, and two test files changed.

- [x] **Step 5: Record the automation handoff and report the explicit next gate**

Record test counts, branch, exact changed files, and that migration application, commit, push, deploy, and production verification still require separate approval.
