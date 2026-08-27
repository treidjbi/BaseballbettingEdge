# Manual Active-Provider Compaction Intervals Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` when explicitly delegated, or
> `superpowers:executing-plans` when working directly. Steps use checkbox
> (`- [ ]`) syntax for tracking.

**Goal:** Convert the behavior-disabled daily finalizer into a safe manual,
one-date-at-a-time compaction tool without creating a Render service or opening
retention deletion.

**Architecture:** Preserve the current D-1 default and fixed provider engine,
then add a validated explicit slate-date input at the orchestration boundary.
Keep historical execution behind a new exact manual gate so the existing D-1
gate cannot authorize an arbitrary date. Document an operator-run interval
cadence while leaving all deletion work separately closed.

**Tech Stack:** Python 3.11, `argparse`, `datetime`, `zoneinfo`, pytest, and the
existing `SupabaseMarketWriter`.

**Spec:**
`docs/superpowers/specs/2026-08-27-manual-active-provider-compaction-intervals-design.md`

## Global Constraints

- Add no Render service, schedule, worker, environment setting, dependency,
  table, migration, or secret.
- Perform no live Supabase preview, database write, deletion, vacuum, retention
  activation, provider-usage write, deploy, merge, or push during Tasks 1-2.
- Keep the fixed providers exactly `("propline", "therundown")`.
- Accept one explicit slate date only; do not add a provider or range argument.
- Keep `compact_market_line_movements` as the only possible execute-mode write
  target and retain all current fingerprint, deadline, attempts, post-write
  proof, redaction, and fail-closed behavior.
- Preserve the existing D-1 write gate for implicit D-1 only. Explicit-date
  execution requires the new exact manual gate.
- Raw snapshot and webhook deletion remain separately closed.

---

### Task 1: Add A Validated Manual Slate-Date Boundary

**Files:**
- Modify: `scripts/run_daily_active_provider_compaction_finalizer.py`
- Modify: `tests/test_daily_active_provider_compaction_finalizer.py`

**Interfaces:**
- Consumes: existing `_target_slate_date()` and `run_finalizer()` behavior.
- Produces: `_resolve_target_slate_date(*, now_utc, explicit_slate_date)`
  returning `(target_slate_date, target_date_source)` and a new optional
  `slate_date` keyword on `run_finalizer()`.

- [x] **Step 1: Write failing target-boundary tests**

Add tests proving:

```python
target, source = finalizer._resolve_target_slate_date(
    now_utc=datetime(2026, 8, 27, 12, tzinfo=timezone.utc),
    explicit_slate_date="2026-08-19",
)
assert (target, source) == ("2026-08-19", "explicit")
```

Also assert malformed, non-canonical, pre-`2026-04-28`, Phoenix same-day, and
future dates raise `ValueError`. Assert the existing omitted-date case returns
Phoenix D-1 with source `phoenix_d_minus_one`.

- [x] **Step 2: Run the target tests and verify RED**

Run:

```powershell
python -m pytest tests/test_daily_active_provider_compaction_finalizer.py -k "explicit_slate or target_date_source" -v
```

Expected: fail because `_resolve_target_slate_date` and the explicit date
contract do not exist.

- [x] **Step 3: Implement the minimal resolver and orchestration input**

Add:

```python
CLEAN_REGIME_START = date(2026, 4, 28)

def _resolve_target_slate_date(
    *,
    now_utc: datetime,
    explicit_slate_date: str | None,
) -> tuple[str, str]:
    d_minus_one = date.fromisoformat(_target_slate_date(now_utc))
    if explicit_slate_date is None:
        return d_minus_one.isoformat(), "phoenix_d_minus_one"
    parsed = date.fromisoformat(explicit_slate_date)
    if parsed.isoformat() != explicit_slate_date:
        raise ValueError("slate_date must use canonical YYYY-MM-DD format")
    if parsed < CLEAN_REGIME_START or parsed > d_minus_one:
        raise ValueError("slate_date is outside the allowed historical window")
    return parsed.isoformat(), "explicit"
```

Add `slate_date: str | None = None` to `run_finalizer()`, call the resolver
before starting provider reads, and include `target_date_source` in every
report branch and the safe top-level allowlist.

- [x] **Step 4: Run focused tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_daily_active_provider_compaction_finalizer.py -k "explicit_slate or target_date_source or phoenix_target or preview_targets" -v
```

Expected: all selected tests pass.

- [x] **Step 5: Commit the independently testable target boundary**

```powershell
git add scripts/run_daily_active_provider_compaction_finalizer.py tests/test_daily_active_provider_compaction_finalizer.py
git commit -m "feat: add manual compaction slate date"
```

---

### Task 2: Add A Separate Manual CLI Write Gate

**Files:**
- Modify: `scripts/run_daily_active_provider_compaction_finalizer.py`
- Modify: `tests/test_daily_active_provider_compaction_finalizer.py`

**Interfaces:**
- Consumes: Task 1's `slate_date` input.
- Produces: `--slate-date`,
  `MANUAL_WRITE_GATE_ENV="ALLOW_MANUAL_ACTIVE_PROVIDER_COMPACTION_WRITE"`, and
  `MANUAL_WRITE_GATE_VALUE="EXACT_DATE_ACTIVE_PROVIDERS_COMPACT_ONLY"`.

- [x] **Step 1: Write failing CLI and gate-isolation tests**

Add tests proving:

```python
args = finalizer._parse_args(["--slate-date", "2026-08-19"])
assert args.slate_date == "2026-08-19"
```

Use a fake writer/finalizer to prove the explicit date is forwarded in preview
mode. For execute mode, prove the daily gate alone rejects `--slate-date`, the
manual gate alone rejects implicit D-1, and only the exact matching gate for
the selected target source loads credentials and calls `run_finalizer`.
Continue rejecting `--provider`, `--date`, and range inputs without echoing
sensitive values.

- [x] **Step 2: Run the CLI tests and verify RED**

Run:

```powershell
python -m pytest tests/test_daily_active_provider_compaction_finalizer.py -k "manual_gate or explicit_date_cli or arbitrary_date" -v
```

Expected: fail because `--slate-date` and the manual gate do not exist.

- [x] **Step 3: Implement the minimal CLI and gate selection**

Add `--slate-date` to `_parse_args()`. In `main()`, select the manual gate only
when `args.slate_date is not None`; otherwise select the existing D-1 gate.
Require `--execute` plus the exact selected gate before loading credentials.
Pass `slate_date=args.slate_date` to `run_finalizer()`.

- [x] **Step 4: Run the complete finalizer safety suite**

Run:

```powershell
python -m pytest tests/test_daily_active_provider_compaction_finalizer.py tests/test_repair_compact_market_snapshot_partition.py tests/test_compact_market_snapshots_script.py tests/test_market_snapshot_compaction.py tests/test_market_infra_supabase_writer.py -q
```

Expected: all tests pass with no network access.

- [x] **Step 5: Commit the independently testable CLI gate**

```powershell
git add scripts/run_daily_active_provider_compaction_finalizer.py tests/test_daily_active_provider_compaction_finalizer.py
git commit -m "feat: gate manual historical compaction"
```

---

### Task 3: Record The Manual-Only Operating Posture

**Files:**
- Modify: `docs/superpowers/plans/2026-08-26-daily-active-provider-compaction-finalizer.md`
- Modify: `docs/current-state.md`
- Modify: `docs/operational-risk-register.md`
- Modify: this plan

**Interfaces:**
- Consumes: Tasks 1-2 verified behavior and exact test counts.
- Produces: a durable manual runbook and an unchanged deletion gate.

- [x] **Step 1: Update the controlling docs**

Record that Tyler declined a new Render service in favor of manual intervals.
Document preview commands for a single explicit date and state that execute
requires a separately supplied exact manual gate. Do not include secret values
or a deletion command. Set the tracking-lane next decision to review a bounded
manual preview/repair tranche; keep raw and webhook deletion closed.

- [x] **Step 2: Run complete verification**

Run:

```powershell
python -m pytest tests -q
python -m py_compile scripts/run_daily_active_provider_compaction_finalizer.py
git diff --check
git status --short
```

Expected: all tests pass, compilation succeeds, whitespace checks pass, and
only the planned script, tests, spec, plan, and handoff docs are changed.

- [x] **Step 3: Prove the production boundary stayed closed**

Run:

```powershell
git diff origin/main..HEAD -- render.yaml dashboard netlify pipeline market_infra/supabase_writer.py
git diff origin/main..HEAD -- scripts/repair_compact_market_snapshot_partition.py
python -c "from scripts.run_daily_active_provider_compaction_finalizer import ACTIVE_PROVIDERS; assert ACTIVE_PROVIDERS == ('propline', 'therundown')"
```

Expected: both diffs are empty and the fixed provider assertion passes.

- [x] **Step 4: Commit the documentation and verification record**

```powershell
git add docs/current-state.md docs/operational-risk-register.md docs/superpowers/specs/2026-08-27-manual-active-provider-compaction-intervals-design.md docs/superpowers/plans/2026-08-26-daily-active-provider-compaction-finalizer.md docs/superpowers/plans/2026-08-27-manual-active-provider-compaction-intervals.md
git commit -m "docs: adopt manual compaction intervals"
```

Do not merge, push, deploy, run a live preview, set either write gate, write to
Supabase, or delete data as part of this plan. Those actions remain later
operator checkpoints.

## Execution Record (2026-08-27)

- Implemented test-first on isolated branch
  `codex/manual-retention-intervals`, rebased onto `origin/main` commit
  `e63a6252` without conflict.
- Target-boundary RED proof: `7` expected failures because the resolver and
  explicit slate-date input did not exist. GREEN proof: `9` selected tests
  passed.
- CLI/gate RED proof: `6` expected failures because `--slate-date` and the
  manual write gate did not exist. GREEN proof: `10` selected tests passed.
- The complete finalizer/reader/writer safety suite passed `134` tests after
  the rebase. The complete repository suite passed `2,602` tests.
- Implementation commits after the rebase are `6d02ead6` (validated manual
  date), `72541d18` (separate manual gate), and `9a58f9c6` (manual operating
  posture and plan).
- Fixed providers remain exactly `("propline", "therundown")`; there is no
  provider or date-range argument. The historical repair allowlist, frequent
  live compactor, writer, Render, dashboard, Netlify, pipeline, and database
  schemas are unchanged.
- `database_write_performed=false`; `live_preview_performed=false`;
  `render_service_created=false`; `deletion_performed=false`;
  `retention_execution_closed=true`. Neither write gate was set.
- The full suite regenerated only the known tracked
  `analytics/output/gate_f_preclose_clv_proxy_lab.md` fixture artifact. Its
  exact committed hash was restored before final status review.

## First Manual Production Checkpoint (2026-08-27)

- The explicit `2026-05-14` preview failed closed because PropLine had source
  evidence but TheRundown had no provider runs, raw snapshots, or rebuilt
  compacts. It attempted no write and performed no deletion.
- The explicit `2026-06-12` preview passed twice with identical provider source
  and preview fingerprints. It identified `208` PropLine and `369` TheRundown
  compact rows to repair (`577` total), with no evidence blockers.
- After Tyler separately approved that exact compact-only tranche, the manual
  write gate authorized one `2026-06-12` execution. It wrote `208` PropLine and
  `369` TheRundown compact rows; both providers reported
  `execution_status=confirmed` and `post_write_exact=true`.
- A fresh post-write preview returned zero missing compacts, zero mismatched
  compacts, zero unexpected compacts, and `rows_to_upsert_count=0` for both
  providers. PropLine is exact at `218` rebuilt/existing rows and TheRundown is
  exact at `456` rebuilt/existing rows for the target date.
- `deletion_performed=false` throughout. Raw retention deletion, vacuum,
  receiver changes, provider changes, and automated cadence remain closed.
  Every additional historical date still requires its own successful preview
  and separately approved compact-only execution.
- The next read-only checkpoint for `2026-06-13` passed with no evidence
  blockers and no write attempt. It identified `185` PropLine and `591`
  TheRundown compact rows to repair (`776` total). That exact tranche remains
  preview-only pending separate Tyler approval.
