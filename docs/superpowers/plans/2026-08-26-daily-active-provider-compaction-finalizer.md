# Daily Active-Provider Compaction Finalizer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a behavior-disabled, separately schedulable daily finalizer
that exactly previews yesterday's PropLine and TheRundown compact partitions
and contains a double-gated, compact-only execution path for later approval.

**Architecture:** Expose the existing keyset-paged partition preview as a
public read-only interface, then compose it from a new isolated daily
orchestrator. The orchestrator derives Phoenix D-1 internally, preflights both
providers, binds any later upsert to a fresh source-state fingerprint, and
emits only aggregate evidence. The frequent live compactor, historical repair
allowlist, and retention/deletion paths remain unchanged.

**Tech Stack:** Python 3.11, `pytest`, `requests`, `zoneinfo`, the existing
`SupabaseMarketWriter`, Supabase Data API/PostgREST, and Render cron at a later
deployment gate.

**Spec:**
`docs/superpowers/specs/2026-08-26-daily-active-provider-compaction-finalizer-design.md`

## Global Constraints

- Do not merge to `main`, deploy, create a Render service, change a Render
  command/environment variable, or connect the new finalizer to a schedule in
  this implementation phase.
- Do not perform a Supabase write, live preview, deletion, vacuum, retention
  activation, provider-usage write, schema change, or migration.
- Keep `scripts/compact_market_snapshots.py` and its 20,000-row live ceiling
  unchanged.
- Keep `EXECUTION_PARTITIONS` in
  `scripts/repair_compact_market_snapshot_partition.py` unchanged and limited
  to the reviewed retired-BoltOdds dates.
- The scheduled finalizer provider tuple is exactly `("propline",
  "therundown")`, in that order. BoltOdds and The Odds API are excluded.
- The scheduled finalizer derives D-1 from `America/Phoenix` internally and
  exposes no arbitrary date or provider argument.
- Preview is the default and performs zero database writes in every success or
  failure state.
- A future write requires both `--execute` and exact environment value
  `ALLOW_DAILY_ACTIVE_PROVIDER_COMPACTION_WRITE=D1_ACTIVE_PROVIDERS_COMPACT_ONLY`.
  Adding that value to Render remains separately approval-gated.
- Execute mode may upsert only `compact_market_line_movements`, with
  `attempts=1`, after both provider preflights complete and a fresh per-provider
  source-state fingerprint matches.
- Execute mode performs at most two full raw partition reads per provider:
  initial preflight and fresh pre-write validation. Post-write verification
  reads only `compact_market_line_movements` and compares canonical count/hash
  against the fresh rebuild, preserving the 300,000-row maximum.
- The finalizer never writes provider usage and never deletes any row.
- The wall-clock budget is exactly `480.0` seconds. The deadline is checked
  before every Supabase request and before every upsert.
- Logs and returned summaries may contain aggregate counts, aggregate
  timestamps, hashes, provider names, mode, target date, elapsed time, and
  status only. Never include source IDs, player names, books, raw rows,
  credentials, response bodies, or exception messages.
- Use existing dependencies only. Add no table, migration, package, audit
  table, dashboard code, notification code, lock code, provider adapter, or
  `render.yaml` entry.
- The official Supabase changelog was checked on 2026-08-26. Its current Data
  API exposure changes apply to newly exposed tables; this plan uses only
  existing server-side tables and adds none. Recheck the
  [official changelog](https://supabase.com/changelog?types=breaking-change)
  immediately before implementation and stop if a new Data API or key change
  affects the existing server-side REST contract.
- [Supabase's current key guidance](https://supabase.com/docs/guides/getting-started/api-keys)
  says the legacy `service_role` key remains valid until explicitly disabled
  but is targeted for deprecation by the end of 2026. This scoped
  implementation keeps the existing server-side key and writer contract. Key
  migration, rotation, shared-writer header changes, and any Render secret
  change require a separate plan and approval before the later service-
  creation gate.
- All Supabase reads and writes continue through the existing server-only
  service key. The key must never enter dashboard or browser code.

---

## File Responsibility Map

- `scripts/repair_compact_market_snapshot_partition.py`: own the exact
  provider/date read, deterministic rebuild, compact comparison, aggregate
  evidence report, and unchanged historical repair executor.
- `scripts/run_daily_active_provider_compaction_finalizer.py`: own Phoenix D-1
  targeting, fixed provider coordination, deadline enforcement, preview
  summary, finalizer-specific write gates, source revalidation, compact-only
  upsert, and CLI exit behavior.
- `tests/test_repair_compact_market_snapshot_partition.py`: protect the public
  exact-preview contract and the unchanged historical execution boundary.
- `tests/test_daily_active_provider_compaction_finalizer.py`: prove daily
  targeting, isolation, safety gates, idempotency, failure recovery, deadline,
  and redacted output without network access.
- `docs/superpowers/plans/2026-08-25-active-provider-compaction-finalizer.md`:
  retain the audit/fail-closed history and record the local finalizer result.
- `docs/current-state.md`: summarize the tracking-lane stage and next approval
  after local verification.

## Public Interfaces Locked By This Plan

```python
# scripts/repair_compact_market_snapshot_partition.py
def build_partition_preview(
    *,
    provider: str,
    slate_date: str,
    writer: SupabaseMarketWriter,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Return aggregate preview evidence and canonical rows that would upsert."""


def verify_compact_partition_exact(
    *,
    provider: str,
    slate_date: str,
    writer: SupabaseMarketWriter,
    expected_compact_count: int,
    expected_compacts_sha256: str,
) -> dict[str, Any]:
    """Return aggregate compact-only count/hash proof; never canonical rows."""


# scripts/run_daily_active_provider_compaction_finalizer.py
ACTIVE_PROVIDERS: tuple[str, ...] = ("propline", "therundown")
WRITE_GATE_ENV = "ALLOW_DAILY_ACTIVE_PROVIDER_COMPACTION_WRITE"
WRITE_GATE_VALUE = "D1_ACTIVE_PROVIDERS_COMPACT_ONLY"
DEFAULT_DEADLINE_SECONDS = 480.0


def run_finalizer(
    *,
    writer: SupabaseMarketWriter,
    execute: bool = False,
    allow_execute: bool = False,
    now_utc: datetime | None = None,
    monotonic_fn: Callable[[], float] = time.monotonic,
    deadline_seconds: float = DEFAULT_DEADLINE_SECONDS,
) -> dict[str, Any]:
    """Preview or, when separately double-gated, finalize Phoenix D-1."""
```

`build_partition_preview` returns canonical would-upsert rows only to trusted
server-side Python callers. The daily summary selects an explicit aggregate
allowlist and never serializes those rows.

---

### Task 1: Expose The Exact Partition Preview Contract

**Files:**
- Modify: `scripts/repair_compact_market_snapshot_partition.py:40-85`
- Modify: `scripts/repair_compact_market_snapshot_partition.py:472-618`
- Modify: `scripts/repair_compact_market_snapshot_partition.py:621-642`
- Modify: `scripts/repair_compact_market_snapshot_partition.py:681-718`
- Modify: `tests/test_repair_compact_market_snapshot_partition.py:147-197`
- Modify: `tests/test_repair_compact_market_snapshot_partition.py:866-906`

**Interfaces:**
- Consumes: existing `_build_preview`, `_validated_date`, `PROVIDERS`, and
  `SupabaseMarketWriter`.
- Produces: public `build_partition_preview(...)`, report field
  `evidence_blockers: list[str]`, source timestamp fields, and fingerprint
  version `5`.

- [x] **Step 1: Write failing public-contract tests**

Add these assertions to the existing preview fixture and add a direct public
entrypoint regression:

```python
def test_public_partition_preview_separates_evidence_from_execution_blockers():
    repair = _module()
    snapshots = [
        _snapshot(SNAP_1, "2026-06-16T18:00:00Z", -110, provider="propline"),
        _snapshot(SNAP_2, "2026-06-16T18:05:00Z", -125, provider="propline"),
    ]
    run_rows = [{
        "id": RUN_ID,
        "provider": "propline",
        "slate_date": "2026-06-16",
        "created_at": "2026-06-16T18:00:00Z",
    }]
    writer = FakeWriter(snapshots=snapshots, existing=[], run_rows=run_rows)

    report, rows_to_upsert = repair.build_partition_preview(
        provider="propline",
        slate_date="2026-06-16",
        writer=writer,
    )

    assert report["evidence_blockers"] == []
    assert report["blockers"] == ["execution_partition_not_allowlisted"]
    assert report["execution_eligible"] is False
    assert report["first_source_observed_at"] == "2026-06-16T18:00:00Z"
    assert report["last_source_observed_at"] == "2026-06-16T18:05:00Z"
    assert report["preview_fingerprint_version"] == 5
    assert len(rows_to_upsert) == 1
    assert writer.upserts == []


def test_empty_partition_is_an_evidence_failure_but_exact_partition_is_clean():
    repair = _module()

    empty_report, empty_rows = repair.build_partition_preview(
        provider="propline",
        slate_date="2026-06-16",
        writer=FakeWriter(run_rows=[], heartbeats=[], snapshots=[], existing=[]),
    )
    assert empty_report["evidence_blockers"] == [
        "no_provider_runs",
        "no_raw_snapshots",
        "no_rebuilt_compacts",
    ]
    assert empty_report["first_source_observed_at"] is None
    assert empty_report["last_source_observed_at"] is None
    assert empty_rows == []

    snapshots = [
        _snapshot(SNAP_1, "2026-06-16T18:00:00Z", -110, provider="propline"),
        _snapshot(SNAP_2, "2026-06-16T18:05:00Z", -125, provider="propline"),
    ]
    run_rows = [{
        "id": RUN_ID,
        "provider": "propline",
        "slate_date": "2026-06-16",
        "created_at": "2026-06-16T18:00:00Z",
    }]
    first_writer = FakeWriter(snapshots=snapshots, existing=[], run_rows=run_rows)
    _, rebuilt_rows = repair.build_partition_preview(
        provider="propline",
        slate_date="2026-06-16",
        writer=first_writer,
    )
    exact_writer = FakeWriter(
        snapshots=snapshots,
        existing=rebuilt_rows,
        run_rows=run_rows,
    )
    exact_report, exact_rows = repair.build_partition_preview(
        provider="propline",
        slate_date="2026-06-16",
        writer=exact_writer,
    )
    assert exact_report["evidence_blockers"] == []
    assert exact_report["rows_to_upsert_count"] == 0
    assert exact_rows == []
```

Update the existing fingerprint assertion from `4` to `5`. Add this direct
binding regression:

```python
def test_source_timestamp_bounds_are_bound_into_both_fingerprints():
    repair = _module()
    report, _ = repair.build_partition_preview(
        provider="boltodds",
        slate_date="2026-06-16",
        writer=FakeWriter(),
    )
    changed = dict(report)
    changed["first_source_observed_at"] = "2026-06-16T17:59:59Z"
    assert repair._source_state_sha256(changed) != report["source_state_sha256"]
    assert repair._preview_fingerprint(changed) != report["preview_sha256"]
```

- [x] **Step 2: Run the focused tests and confirm the public interface is absent**

Run:

```powershell
python -m pytest tests/test_repair_compact_market_snapshot_partition.py -q
```

Expected: the new tests fail because `build_partition_preview` and the new
aggregate fields do not exist.

- [x] **Step 3: Add the public preview and evidence-only blocker set**

Extend the source fingerprint fields and build the report with two blocker
levels:

```python
SOURCE_STATE_FIELDS = (
    "provider",
    "slate_date",
    "provider_run_count",
    "heartbeat_row_count",
    "in_window_heartbeat_count",
    "out_of_window_heartbeat_count",
    "raw_snapshot_count",
    "snapshot_in_window_count",
    "snapshot_out_of_window_count",
    "first_source_observed_at",
    "last_source_observed_at",
    "rebuilt_compact_count",
    "rebuilt_compacts_sha256",
)


def _source_observed_bounds(
    rows: list[dict[str, Any]],
) -> tuple[str | None, str | None]:
    if not rows:
        return None, None
    observed = sorted(
        _aware_datetime(row.get("observed_at"), label="snapshot observed_at")
        for row in rows
    )
    return (
        observed[0].isoformat().replace("+00:00", "Z"),
        observed[-1].isoformat().replace("+00:00", "Z"),
    )


def build_partition_preview(
    *,
    provider: str,
    slate_date: str,
    writer: SupabaseMarketWriter,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    normalized_provider = str(provider).strip().lower()
    if normalized_provider not in PROVIDERS:
        raise ValueError(f"provider must be one of: {', '.join(PROVIDERS)}")
    normalized_date = _validated_date(str(slate_date).strip())
    return _build_preview(
        provider=normalized_provider,
        slate_date=normalized_date,
        writer=writer,
    )
```

Inside `_build_preview`, derive the timestamps and construct blockers exactly
as follows:

```python
first_source_observed_at, last_source_observed_at = _source_observed_bounds(
    snapshot_rows
)
evidence_blockers: list[str] = []
if not run_rows:
    evidence_blockers.append("no_provider_runs")
if not snapshot_rows:
    evidence_blockers.append("no_raw_snapshots")
if not rebuilt_rows:
    evidence_blockers.append("no_rebuilt_compacts")
if comparison["unexpected_compact_count"]:
    evidence_blockers.append("unexpected_compact_rows")

blockers = list(evidence_blockers)
if not is_execution_partition(provider, slate_date):
    blockers.append("execution_partition_not_allowlisted")
if not comparison["rows_to_upsert"]:
    blockers.append("no_changes")
```

Add `evidence_blockers`, both timestamps, and fingerprint version `5` to the
report. Add the timestamps and `evidence_blockers` to `_preview_fingerprint`.
Change historical `run(...)` to call `build_partition_preview(...)`; do not
change any historical execute condition or allowlist.

The historical executor's post-write source hash must use the same versioned
source fields:

```python
post_first_source_observed_at, post_last_source_observed_at = (
    _source_observed_bounds(post_snapshot_rows)
)
post_source_state_sha256 = _source_state_sha256({
    "provider": normalized_provider,
    "slate_date": normalized_date,
    "provider_run_count": len(post_run_rows),
    **post_heartbeat_summary,
    "raw_snapshot_count": len(post_snapshot_rows),
    **post_snapshot_window_summary,
    "first_source_observed_at": post_first_source_observed_at,
    "last_source_observed_at": post_last_source_observed_at,
    "rebuilt_compact_count": len(post_rebuilt_rows),
    "rebuilt_compacts_sha256": post_rebuilt_sha256,
})
```

Include both post-write timestamp fields in the returned execution report so
existing exact-repair tests prove the new fingerprint remains internally
consistent.

- [x] **Step 4: Run exact-preview and compactor regressions**

Run:

```powershell
python -m pytest tests/test_repair_compact_market_snapshot_partition.py tests/test_compact_market_snapshots_script.py tests/test_market_snapshot_compaction.py -q
```

Expected: all tests pass; active-provider historical execution remains blocked
and the frequent compactor remains unchanged.

- [x] **Step 5: Commit the public read-only contract**

```powershell
git add scripts/repair_compact_market_snapshot_partition.py tests/test_repair_compact_market_snapshot_partition.py
git commit -m "refactor: expose exact compaction preview"
```

---

### Task 2: Build The Isolated Daily Preview Orchestrator

**Files:**
- Create: `scripts/run_daily_active_provider_compaction_finalizer.py`
- Create: `tests/test_daily_active_provider_compaction_finalizer.py`

**Interfaces:**
- Consumes: `build_partition_preview(...)` from Task 1 and an injected
  `SupabaseMarketWriter`.
- Produces: `_target_slate_date(...)`, `_DeadlineBoundWriter`, aggregate
  provider summaries, and preview-capable `run_finalizer(...)`.

- [x] **Step 1: Write failing date, provider-order, and zero-write tests**

Create the test module with a recording writer and deterministic preview
factory:

```python
from datetime import datetime, timezone
import importlib
import json

import pytest
import requests


def _module():
    return importlib.import_module(
        "scripts.run_daily_active_provider_compaction_finalizer"
    )


class RecordingWriter:
    def __init__(self):
        self.selects = []
        self.upserts = []
        self.on_upsert = None
        self.upsert_errors = []

    def select_rows(self, table, params, **kwargs):
        self.selects.append((table, dict(params), dict(kwargs)))
        return []

    def upsert_rows(self, table, rows, on_conflict, **kwargs):
        self.upserts.append((table, list(rows), on_conflict, dict(kwargs)))
        if self.on_upsert is not None:
            self.on_upsert(rows)
        if self.upsert_errors:
            error = self.upsert_errors.pop(0)
            if error is not None:
                raise error
        return []


def _report(provider, *, blockers=(), rows_to_upsert=1, source_hash=None):
    return {
        "provider": provider,
        "slate_date": "2026-08-25",
        "provider_run_count": 2,
        "heartbeat_row_count": 3,
        "in_window_heartbeat_count": 3,
        "out_of_window_heartbeat_count": 0,
        "raw_snapshot_count": 100,
        "snapshot_in_window_count": 100,
        "snapshot_out_of_window_count": 0,
        "first_source_observed_at": "2026-08-25T14:00:00Z",
        "last_source_observed_at": "2026-08-26T01:00:00Z",
        "rebuilt_compact_count": 10,
        "existing_compact_count": 9,
        "missing_compact_count": rows_to_upsert,
        "mismatched_compact_count": 0,
        "unexpected_compact_count": 0,
        "rows_to_upsert_count": rows_to_upsert,
        "evidence_blockers": list(blockers),
        "source_state_sha256": source_hash or f"source-{provider}",
        "preview_sha256": f"preview-{provider}",
    }


def test_preview_targets_phoenix_d_minus_one_in_fixed_provider_order(monkeypatch):
    finalizer = _module()
    calls = []
    writer = RecordingWriter()

    def fake_preview(*, provider, slate_date, writer):
        calls.append((provider, slate_date))
        return _report(provider), [{"provider": provider}]

    monkeypatch.setattr(finalizer, "build_partition_preview", fake_preview)
    result = finalizer.run_finalizer(
        writer=writer,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )

    assert calls == [
        ("propline", "2026-08-25"),
        ("therundown", "2026-08-25"),
    ]
    assert result["mode"] == "preview"
    assert result["status"] == "success"
    assert result["database_write_attempted"] is False
    assert result["database_write_performed"] is False
    assert result["deletion_performed"] is False
    assert writer.upserts == []
```

Add these concrete regressions in the same file:

```python
def test_phoenix_target_is_stable_across_utc_date_boundary():
    finalizer = _module()
    now_utc = datetime(2026, 8, 26, 2, 0, tzinfo=timezone.utc)
    assert finalizer._target_slate_date(now_utc) == "2026-08-24"


def test_preview_allows_would_upserts_but_blocks_unexpected_compacts(monkeypatch):
    finalizer = _module()

    def would_upsert(*, provider, slate_date, writer):
        return _report(provider, rows_to_upsert=4), [
            {"provider": provider, "row": index} for index in range(4)
        ]

    monkeypatch.setattr(finalizer, "build_partition_preview", would_upsert)
    clean = finalizer.run_finalizer(
        writer=RecordingWriter(),
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert clean["status"] == "success"
    assert [row["rows_to_upsert_count"] for row in clean["provider_results"]] == [4, 4]

    def unexpected(*, provider, slate_date, writer):
        report = _report(provider, blockers=("unexpected_compact_rows",))
        report["unexpected_compact_count"] = 1
        return report, []

    monkeypatch.setattr(finalizer, "build_partition_preview", unexpected)
    blocked = finalizer.run_finalizer(
        writer=RecordingWriter(),
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert blocked["status"] == "failed"
    assert blocked["preflight_complete"] is False


def test_first_provider_exception_is_sanitized_and_second_preflight_still_runs(
    monkeypatch,
):
    finalizer = _module()
    calls = []

    def preview(*, provider, slate_date, writer):
        calls.append(provider)
        if provider == "propline":
            raise ValueError("player-and-source-id-must-not-leak")
        return _report(provider), [{"provider": provider}]

    monkeypatch.setattr(finalizer, "build_partition_preview", preview)
    result = finalizer.run_finalizer(
        writer=RecordingWriter(),
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    encoded = json.dumps(result, sort_keys=True)
    assert calls == ["propline", "therundown"]
    assert result["status"] == "failed"
    assert result["provider_results"][0]["error_type"] == "ValueError"
    assert "player-and-source-id-must-not-leak" not in encoded


def test_preview_summary_contains_no_canonical_rows_or_source_ids(monkeypatch):
    finalizer = _module()

    def preview(*, provider, slate_date, writer):
        return _report(provider), [{
            "provider": provider,
            "player_name": "Sensitive Pitcher",
            "source_snapshot_ids": ["sensitive-source-id"],
        }]

    monkeypatch.setattr(finalizer, "build_partition_preview", preview)
    result = finalizer.run_finalizer(
        writer=RecordingWriter(),
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    encoded = json.dumps(result, sort_keys=True)
    assert "Sensitive Pitcher" not in encoded
    assert "sensitive-source-id" not in encoded
    assert "canonical_rows" not in encoded


def test_deadline_bound_writer_refuses_requests_at_or_after_cutoff():
    finalizer = _module()
    underlying = RecordingWriter()

    def expired():
        raise finalizer.FinalizerDeadlineExceeded("daily finalizer deadline exceeded")

    writer = finalizer._DeadlineBoundWriter(underlying, expired)
    with pytest.raises(finalizer.FinalizerDeadlineExceeded):
        writer.select_rows("market_snapshots", {"limit": "1"}, attempts=1)
    with pytest.raises(finalizer.FinalizerDeadlineExceeded):
        writer.upsert_rows(
            "compact_market_line_movements",
            [{"safe": "aggregate"}],
            "slate_date,provider",
            attempts=1,
        )
    assert underlying.selects == []
    assert underlying.upserts == []
```

- [x] **Step 2: Run the new test file and confirm the module is absent**

Run:

```powershell
python -m pytest tests/test_daily_active_provider_compaction_finalizer.py -q
```

Expected: collection or import fails because the finalizer module does not
exist.

- [x] **Step 3: Implement the preview core and deadline-bound writer**

Create the module with these constants and helpers:

```python
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_infra.supabase_writer import SupabaseMarketWriter
from scripts.repair_compact_market_snapshot_partition import (
    ON_CONFLICT,
    build_partition_preview,
)

PHOENIX = ZoneInfo("America/Phoenix")
ACTIVE_PROVIDERS = ("propline", "therundown")
WRITE_GATE_ENV = "ALLOW_DAILY_ACTIVE_PROVIDER_COMPACTION_WRITE"
WRITE_GATE_VALUE = "D1_ACTIVE_PROVIDERS_COMPACT_ONLY"
DEFAULT_DEADLINE_SECONDS = 480.0


class FinalizerDeadlineExceeded(RuntimeError):
    pass


class _DeadlineBoundWriter:
    def __init__(self, writer: SupabaseMarketWriter, check_deadline: Callable[[], None]):
        self._writer = writer
        self._check_deadline = check_deadline

    def select_rows(self, table: str, params: dict[str, str], **kwargs):
        self._check_deadline()
        return self._writer.select_rows(table, params, **kwargs)

    def upsert_rows(self, table: str, rows: list[dict], on_conflict: str, **kwargs):
        self._check_deadline()
        return self._writer.upsert_rows(table, rows, on_conflict, **kwargs)


def _target_slate_date(now_utc: datetime) -> str:
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")
    return (now_utc.astimezone(PHOENIX).date() - timedelta(days=1)).isoformat()
```

In `run_finalizer`, reject nonpositive `deadline_seconds`, resolve
`now_utc = now_utc or datetime.now(timezone.utc)`, create
`started = monotonic_fn()`, and create a `check_deadline` closure that raises
when `monotonic_fn() - started >= deadline_seconds`. Wrap
the injected writer before passing it to `build_partition_preview` so every
page request is guarded. Catch provider exceptions individually, record only
`error_type=type(error).__name__`, and continue to the second provider during
preflight.

Build provider summaries by selecting this fixed field tuple:

```python
PROVIDER_SUMMARY_FIELDS = (
    "provider",
    "slate_date",
    "provider_run_count",
    "heartbeat_row_count",
    "in_window_heartbeat_count",
    "out_of_window_heartbeat_count",
    "raw_snapshot_count",
    "snapshot_in_window_count",
    "snapshot_out_of_window_count",
    "first_source_observed_at",
    "last_source_observed_at",
    "rebuilt_compact_count",
    "existing_compact_count",
    "missing_compact_count",
    "mismatched_compact_count",
    "unexpected_compact_count",
    "rows_to_upsert_count",
    "evidence_blockers",
    "source_state_sha256",
    "preview_sha256",
)


def _aggregate_provider_summary(report: dict[str, Any]) -> dict[str, Any]:
    return {
        field: report[field]
        for field in PROVIDER_SUMMARY_FIELDS
        if field in report
    }


def _preflight_failure(
    *,
    provider: str,
    slate_date: str,
    error: Exception,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "slate_date": slate_date,
        "evidence_blockers": ["provider_preview_failed"],
        "error_type": type(error).__name__,
    }
```

For this task, fail closed if `execute=True` with static error
`execute mode is disabled until the compact-only executor is installed`.
Preview success means both providers returned complete evidence with empty
`evidence_blockers`; missing or mismatched stored rows remain successful
would-upsert evidence. Compute `preflight_complete` from both provider
summaries and always return the top-level safety fields:

```python
preflight_complete = (
    len(provider_summaries) == len(ACTIVE_PROVIDERS)
    and all(not item.get("evidence_blockers") for item in provider_summaries)
    and all("error_type" not in item for item in provider_summaries)
)
status = "success" if preflight_complete else "failed"

return {
    "report_type": "daily_active_provider_compaction_finalizer",
    "mode": "preview",
    "target_slate_date": target_slate_date,
    "status": status,
    "preflight_complete": preflight_complete,
    "provider_results": provider_summaries,
    "database_write_attempted": False,
    "database_write_performed": False,
    "provider_usage_rows_written": 0,
    "deletion_performed": False,
    "retention_execution_closed": True,
    "deadline_exceeded": any(
        item.get("error_type") == "FinalizerDeadlineExceeded"
        for item in provider_summaries
    ),
    "elapsed_seconds": round(monotonic_fn() - started, 3),
}
```

The preview branch of `run_finalizer` is implemented with this exact control
shape:

```python
if execute and not allow_execute:
    raise ValueError("daily active-provider compaction write gate is closed")
if execute:
    raise ValueError(
        "execute mode is disabled until the compact-only executor is installed"
    )
if deadline_seconds <= 0:
    raise ValueError("deadline_seconds must be positive")

resolved_now = now_utc or datetime.now(timezone.utc)
target_slate_date = _target_slate_date(resolved_now)
started = monotonic_fn()

def check_deadline() -> None:
    if monotonic_fn() - started >= deadline_seconds:
        raise FinalizerDeadlineExceeded("daily finalizer deadline exceeded")

bounded_writer = _DeadlineBoundWriter(writer, check_deadline)
provider_summaries: list[dict[str, Any]] = []
for provider in ACTIVE_PROVIDERS:
    try:
        check_deadline()
        report, _ = build_partition_preview(
            provider=provider,
            slate_date=target_slate_date,
            writer=bounded_writer,
        )
        provider_summaries.append(_aggregate_provider_summary(report))
    except (
        FinalizerDeadlineExceeded,
        requests.RequestException,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        provider_summaries.append(_preflight_failure(
            provider=provider,
            slate_date=target_slate_date,
            error=error,
        ))
```

- [x] **Step 4: Run preview and exact-reader tests**

Run:

```powershell
python -m pytest tests/test_daily_active_provider_compaction_finalizer.py tests/test_repair_compact_market_snapshot_partition.py -q
```

Expected: all tests pass, and the preview test records zero writes.

- [x] **Step 5: Commit the isolated preview core**

```powershell
git add scripts/run_daily_active_provider_compaction_finalizer.py tests/test_daily_active_provider_compaction_finalizer.py
git commit -m "feat: add daily compaction preview finalizer"
```

---

### Task 3: Add The Double-Gated Compact-Only Executor

**Files:**
- Modify: `scripts/run_daily_active_provider_compaction_finalizer.py`
- Modify: `tests/test_daily_active_provider_compaction_finalizer.py`

**Interfaces:**
- Consumes: the two complete preflight reports and internal canonical
  would-upsert rows from Task 2.
- Produces: `_execute_provider(...)` and the final execute-mode provider result
  states `no_op`, `confirmed`, `confirmed_by_post_state`, `failed`, and
  `not_attempted_after_prior_failure`.

- [x] **Step 1: Write failing execute-gate and preflight-order tests**

Add tests that use an ordered event list shared by the preview fake and writer:

```python
def test_execute_requires_allow_gate_before_any_provider_read(monkeypatch):
    finalizer = _module()
    writer = RecordingWriter()

    try:
        finalizer.run_finalizer(writer=writer, execute=True, allow_execute=False)
    except ValueError as error:
        assert str(error) == "daily active-provider compaction write gate is closed"
    else:
        raise AssertionError("closed execute gate did not fail")

    assert writer.selects == []
    assert writer.upserts == []


def test_execute_preflights_both_providers_before_first_upsert(monkeypatch):
    finalizer = _module()
    events = []
    writer = RecordingWriter()

    # The preview sequence returns one preflight and one pre-write raw read per
    # provider. Compact-only post-state verification uses its own fake.
    sequence = PreviewSequence.exact_write_cycle(events)
    monkeypatch.setattr(finalizer, "build_partition_preview", sequence)
    writer.on_upsert = lambda rows: events.append(("upsert", rows[0]["provider"]))

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )

    first_upsert = next(index for index, event in enumerate(events) if event[0] == "upsert")
    assert ("preflight", "propline") in events[:first_upsert]
    assert ("preflight", "therundown") in events[:first_upsert]
    assert result["status"] == "success"
```

Implement this explicit preview sequencer:

```python
class PreviewSequence:
    def __init__(self, responses, events=None):
        self.responses = {
            provider: list(items) for provider, items in responses.items()
        }
        self.events = events if events is not None else []

    def __call__(self, *, provider, slate_date, writer):
        phase, result = self.responses[provider].pop(0)
        self.events.append((phase, provider))
        if isinstance(result, Exception):
            raise result
        report, rows = result
        return dict(report), [dict(row) for row in rows]

    @classmethod
    def exact_write_cycle(cls, events=None):
        responses = {}
        for provider in ("propline", "therundown"):
            pending = _report(provider, rows_to_upsert=1)
            responses[provider] = [
                ("preflight", (pending, [{"provider": provider}])),
                ("fresh", (pending, [{"provider": provider}])),
            ]
        return cls(responses, events)
```

Add the remaining execute regressions with concrete response sequences:

```python
def test_any_preflight_failure_causes_zero_upserts(monkeypatch):
    finalizer = _module()
    writer = RecordingWriter()
    sequence = PreviewSequence({
        "propline": [("preflight", ValueError("sensitive"))],
        "therundown": [("preflight", (_report("therundown"), [{"provider": "therundown"}]))],
    })
    monkeypatch.setattr(finalizer, "build_partition_preview", sequence)

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert result["status"] == "failed"
    assert result["preflight_complete"] is False
    assert writer.upserts == []


def test_source_drift_before_first_write_causes_zero_upserts(monkeypatch):
    finalizer = _module()
    writer = RecordingWriter()
    sequence = PreviewSequence({
        "propline": [
            ("preflight", (_report("propline", source_hash="source-a"), [{"provider": "propline"}])),
            ("fresh", (_report("propline", source_hash="source-b"), [{"provider": "propline"}])),
        ],
        "therundown": [
            ("preflight", (_report("therundown"), [{"provider": "therundown"}])),
        ],
    })
    monkeypatch.setattr(finalizer, "build_partition_preview", sequence)

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert result["provider_results"][0]["failure_reason"] == "source_state_drift"
    assert result["provider_results"][1]["execution_status"] == "not_attempted_after_prior_failure"
    assert writer.upserts == []


def test_exact_partitions_are_idempotent_no_ops(monkeypatch):
    finalizer = _module()
    writer = RecordingWriter()
    responses = {}
    for provider in ("propline", "therundown"):
        exact = _report(provider, rows_to_upsert=0)
        responses[provider] = [
            ("preflight", (exact, [])),
            ("fresh", (exact, [])),
        ]
    monkeypatch.setattr(finalizer, "build_partition_preview", PreviewSequence(responses))

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert [row["execution_status"] for row in result["provider_results"]] == [
        "no_op",
        "no_op",
    ]
    assert result["database_write_attempted"] is False
    assert writer.upserts == []


def test_successful_upsert_uses_one_attempt_and_return_minimal(monkeypatch):
    finalizer = _module()
    writer = RecordingWriter()
    monkeypatch.setattr(
        finalizer,
        "build_partition_preview",
        PreviewSequence.exact_write_cycle(),
    )

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert result["status"] == "success"
    assert len(writer.upserts) == 2
    for table, rows, on_conflict, kwargs in writer.upserts:
        assert table == "compact_market_line_movements"
        assert len(rows) == 1
        assert on_conflict == finalizer.ON_CONFLICT
        assert kwargs["attempts"] == 1
        assert kwargs["return_representation"] is False


def test_ambiguous_upsert_is_success_only_when_post_state_is_exact(monkeypatch):
    finalizer = _module()
    writer = RecordingWriter()
    writer.upsert_errors = [requests.Timeout("sensitive-timeout"), None]
    monkeypatch.setattr(
        finalizer,
        "build_partition_preview",
        PreviewSequence.exact_write_cycle(),
    )

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert result["provider_results"][0]["execution_status"] == "confirmed_by_post_state"
    assert result["provider_results"][0]["database_write_performed"] is None
    assert "sensitive-timeout" not in json.dumps(result)


def test_ambiguous_inexact_upsert_fails_and_prevents_second_write(monkeypatch):
    finalizer = _module()
    writer = RecordingWriter()
    writer.upsert_errors = [requests.Timeout("ambiguous")]
    pending = _report("propline", rows_to_upsert=1)
    sequence = PreviewSequence({
        "propline": [
            ("preflight", (pending, [{"provider": "propline"}])),
            ("fresh", (pending, [{"provider": "propline"}])),
        ],
        "therundown": [
            ("preflight", (_report("therundown"), [{"provider": "therundown"}])),
        ],
    })
    monkeypatch.setattr(finalizer, "build_partition_preview", sequence)

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert result["status"] == "failed"
    assert result["provider_results"][0]["post_write_exact"] is False
    assert result["provider_results"][1]["execution_status"] == "not_attempted_after_prior_failure"
    assert len(writer.upserts) == 1


def test_second_provider_failure_reports_bounded_partial_state(monkeypatch):
    finalizer = _module()
    writer = RecordingWriter()
    writer.upsert_errors = [None, requests.Timeout("ambiguous")]
    propline_pending = _report("propline", rows_to_upsert=1)
    propline_exact = _report("propline", rows_to_upsert=0)
    rundown_pending = _report("therundown", rows_to_upsert=1)
    sequence = PreviewSequence({
        "propline": [
            ("preflight", (propline_pending, [{"provider": "propline"}])),
            ("fresh", (propline_pending, [{"provider": "propline"}])),
        ],
        "therundown": [
            ("preflight", (rundown_pending, [{"provider": "therundown"}])),
            ("fresh", (rundown_pending, [{"provider": "therundown"}])),
        ],
    })
    monkeypatch.setattr(finalizer, "build_partition_preview", sequence)

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert result["status"] == "failed"
    assert result["provider_results"][0]["execution_status"] == "confirmed"
    assert result["provider_results"][1]["execution_status"] == "failed"
    assert result["database_write_attempted"] is True


def test_retry_treats_completed_first_provider_as_no_op(monkeypatch):
    finalizer = _module()
    writer = RecordingWriter()
    propline_exact = _report("propline", rows_to_upsert=0)
    rundown_pending = _report("therundown", rows_to_upsert=1)
    rundown_exact = _report("therundown", rows_to_upsert=0)
    sequence = PreviewSequence({
        "propline": [
            ("preflight", (propline_exact, [])),
            ("fresh", (propline_exact, [])),
        ],
        "therundown": [
            ("preflight", (rundown_pending, [{"provider": "therundown"}])),
            ("fresh", (rundown_pending, [{"provider": "therundown"}])),
        ],
    })
    monkeypatch.setattr(finalizer, "build_partition_preview", sequence)

    result = finalizer.run_finalizer(
        writer=writer,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
    )
    assert result["provider_results"][0]["execution_status"] == "no_op"
    assert result["provider_results"][1]["execution_status"] == "confirmed"
    assert len(writer.upserts) == 1
    assert writer.upserts[0][1][0]["provider"] == "therundown"


def test_deadline_expiry_before_upsert_performs_zero_new_writes(monkeypatch):
    finalizer = _module()
    underlying = RecordingWriter()
    sequence = PreviewSequence({
        "propline": [
            ("preflight", (_report("propline"), [{"provider": "propline"}])),
            ("fresh", (_report("propline"), [{"provider": "propline"}])),
        ],
        "therundown": [
            ("preflight", (_report("therundown"), [{"provider": "therundown"}])),
        ],
    })
    monkeypatch.setattr(finalizer, "build_partition_preview", sequence)

    class TickingClock:
        def __init__(self):
            self.value = -1.0

        def __call__(self):
            self.value += 1.0
            return self.value

    result = finalizer.run_finalizer(
        writer=underlying,
        execute=True,
        allow_execute=True,
        now_utc=datetime(2026, 8, 26, 12, 5, tzinfo=timezone.utc),
        monotonic_fn=TickingClock(),
        deadline_seconds=3.5,
    )
    assert result["status"] == "failed"
    assert result["deadline_exceeded"] is True
    assert underlying.upserts == []
```

- [x] **Step 2: Run execute tests and confirm the fail-closed stub blocks them**

Run:

```powershell
python -m pytest tests/test_daily_active_provider_compaction_finalizer.py -q
```

Expected: the new execute-path tests fail because Task 2 deliberately left
execute mode closed.

- [x] **Step 3: Implement source-bound one-attempt execution**

Store both preflight reports and row lists before entering the write loop. If
either provider has an exception or non-empty `evidence_blockers`, return
failed with zero upserts.

Implement the provider executor with this contract:

```python
def _failed_execution(
    *,
    provider: str,
    slate_date: str,
    reason: str,
    report: dict[str, Any] | None = None,
    error_type: str | None = None,
    attempted: bool = False,
    performed: bool | None = False,
    write_row_count: int = 0,
) -> dict[str, Any]:
    result = (
        _aggregate_provider_summary(report)
        if report is not None
        else {"provider": provider, "slate_date": slate_date}
    )
    result.update({
        "execution_status": "failed",
        "failure_reason": reason,
        "database_write_attempted": attempted,
        "database_write_performed": performed,
        "write_row_count": write_row_count,
        "post_write_exact": False,
    })
    if error_type is not None:
        result["write_error_type"] = error_type
    return result


def _execution_result(
    *,
    report: dict[str, Any],
    status: str,
    attempted: bool,
    performed: bool | None,
    write_row_count: int,
    write_error_type: str | None,
    post_write_exact: bool,
) -> dict[str, Any]:
    result = _aggregate_provider_summary(report)
    result.update({
        "execution_status": status,
        "database_write_attempted": attempted,
        "database_write_performed": performed,
        "write_row_count": write_row_count,
        "post_write_exact": post_write_exact,
    })
    if write_error_type is not None:
        result["write_error_type"] = write_error_type
    return result


def _execute_provider(
    *,
    provider: str,
    slate_date: str,
    writer: _DeadlineBoundWriter,
    preflight_report: dict[str, Any],
) -> dict[str, Any]:
    fresh_report, fresh_rows = build_partition_preview(
        provider=provider,
        slate_date=slate_date,
        writer=writer,
    )
    if fresh_report["evidence_blockers"]:
        return _failed_execution(
            provider=provider,
            slate_date=slate_date,
            reason="fresh_preflight_blocked",
            report=fresh_report,
        )
    if fresh_report["source_state_sha256"] != preflight_report["source_state_sha256"]:
        return _failed_execution(
            provider=provider,
            slate_date=slate_date,
            reason="source_state_drift",
            report=fresh_report,
        )

    if not fresh_rows:
        return {
            **_aggregate_provider_summary(fresh_report),
            "execution_status": "no_op",
            "database_write_attempted": False,
            "database_write_performed": False,
            "write_row_count": 0,
            "post_write_exact": True,
        }

    write_outcome = "confirmed"
    write_performed: bool | None = True
    write_error_type: str | None = None
    try:
        writer.upsert_rows(
            "compact_market_line_movements",
            fresh_rows,
            on_conflict=ON_CONFLICT,
            attempts=1,
            return_representation=False,
        )
    except requests.RequestException as error:
        write_outcome = "ambiguous"
        write_performed = None
        write_error_type = type(error).__name__

    try:
        compact_proof = verify_compact_partition_exact(
            provider=provider,
            slate_date=slate_date,
            writer=writer,
            expected_compact_count=fresh_report["rebuilt_compact_count"],
            expected_compacts_sha256=fresh_report["rebuilt_compacts_sha256"],
        )
    except (
        FinalizerDeadlineExceeded,
        requests.RequestException,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        return _failed_execution(
            provider=provider,
            slate_date=slate_date,
            reason="post_write_check_failed",
            report=fresh_report,
            error_type=type(error).__name__,
            attempted=True,
            performed=write_performed,
            write_row_count=len(fresh_rows),
        )
    post_exact = compact_proof["compact_state_exact"]
    if write_outcome == "ambiguous" and post_exact:
        write_outcome = "confirmed_by_post_state"
    return _execution_result(
        report=fresh_report,
        status=write_outcome if post_exact else "failed",
        attempted=True,
        performed=write_performed,
        write_row_count=len(fresh_rows),
        write_error_type=write_error_type,
        post_write_exact=post_exact,
    )
```

`_failed_execution` and `_execution_result` must return only the allowed
aggregate fields. They accept a static reason code, never exception text.
After both preflights complete, replace Task 2's execute stub with this write
loop. In execute mode, initialize
`preflight_reports: dict[str, dict[str, Any]] = {}` before the initial provider
loop and assign `preflight_reports[provider] = report` immediately after every
successful `build_partition_preview` call. Do not store or serialize the
preflight canonical rows. Then use this write loop:

```python
if not preflight_complete:
    return {
        "report_type": "daily_active_provider_compaction_finalizer",
        "mode": "execute",
        "target_slate_date": target_slate_date,
        "status": "failed",
        "preflight_complete": False,
        "provider_results": provider_summaries,
        "database_write_attempted": False,
        "database_write_performed": False,
        "provider_usage_rows_written": 0,
        "deletion_performed": False,
        "retention_execution_closed": True,
        "deadline_exceeded": any(
            item.get("error_type") == "FinalizerDeadlineExceeded"
            for item in provider_summaries
        ),
        "elapsed_seconds": round(monotonic_fn() - started, 3),
    }

provider_results: list[dict[str, Any]] = []
for index, provider in enumerate(ACTIVE_PROVIDERS):
    try:
        check_deadline()
        result = _execute_provider(
            provider=provider,
            slate_date=target_slate_date,
            writer=bounded_writer,
            preflight_report=preflight_reports[provider],
        )
    except (
        FinalizerDeadlineExceeded,
        requests.RequestException,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        result = _failed_execution(
            provider=provider,
            slate_date=target_slate_date,
            reason="provider_execution_failed",
            error_type=type(error).__name__,
        )
    provider_results.append(result)
    if result["execution_status"] == "failed":
        for remaining in ACTIVE_PROVIDERS[index + 1:]:
            provider_results.append({
                "provider": remaining,
                "slate_date": target_slate_date,
                "execution_status": "not_attempted_after_prior_failure",
                "failure_reason": "prior_provider_failed",
                "database_write_attempted": False,
                "database_write_performed": False,
                "write_row_count": 0,
                "post_write_exact": False,
            })
        break

successful_states = {"no_op", "confirmed", "confirmed_by_post_state"}
status = (
    "success"
    if len(provider_results) == len(ACTIVE_PROVIDERS)
    and all(item["execution_status"] in successful_states for item in provider_results)
    else "failed"
)
```

Top-level status is therefore success only when both providers are `no_op`,
`confirmed`, or `confirmed_by_post_state`.

Set top-level execution fields from provider results. Compute
`top_level_write_performed` before building the result:

```python
attempted_results = [
    item for item in provider_results if item["database_write_attempted"]
]
if any(item["database_write_performed"] is None for item in attempted_results):
    top_level_write_performed: bool | None = None
else:
    top_level_write_performed = any(
        item["database_write_performed"] is True for item in attempted_results
    )
```

For a run containing an ambiguous inexact write, keep
`database_write_performed=None` at both provider and top level. Do not retry.
Return the complete execute result using the computed values:

```python
return {
    "report_type": "daily_active_provider_compaction_finalizer",
    "mode": "execute",
    "target_slate_date": target_slate_date,
    "status": status,
    "preflight_complete": True,
    "provider_results": provider_results,
    "database_write_attempted": any(
        item["database_write_attempted"] for item in provider_results
    ),
    "database_write_performed": top_level_write_performed,
    "provider_usage_rows_written": 0,
    "deletion_performed": False,
    "retention_execution_closed": True,
    "deadline_exceeded": any(
        item.get("error_type") == "FinalizerDeadlineExceeded"
        or item.get("write_error_type") == "FinalizerDeadlineExceeded"
        for item in provider_results
    ),
    "elapsed_seconds": round(monotonic_fn() - started, 3),
}
```

- [x] **Step 4: Run execute, exact-reader, and writer regressions**

Run:

```powershell
python -m pytest tests/test_daily_active_provider_compaction_finalizer.py tests/test_repair_compact_market_snapshot_partition.py tests/test_supabase_writer.py -q
```

Expected: all tests pass; every upsert assertion shows
`attempts=1`, `return_representation=False`, and table
`compact_market_line_movements`.

- [x] **Step 5: Commit the compact-only executor**

```powershell
git add scripts/run_daily_active_provider_compaction_finalizer.py tests/test_daily_active_provider_compaction_finalizer.py
git commit -m "feat: gate daily compact finalization"
```

---

### Task 4: Add The Redacted CLI Contract

**Files:**
- Modify: `scripts/run_daily_active_provider_compaction_finalizer.py`
- Modify: `tests/test_daily_active_provider_compaction_finalizer.py`

**Interfaces:**
- Consumes: `run_finalizer(...)` from Task 3 and server-side environment
  variables `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
- Produces: `main(argv: list[str] | None = None) -> int` with preview default,
  `--execute` as the only mode flag, one-line aggregate JSON, and stable exit
  codes `0`, `2`, and `3`.

- [x] **Step 1: Write failing CLI and redaction tests**

Add the following tests:

```python
def test_cli_accepts_no_arbitrary_date_or_provider(monkeypatch):
    finalizer = _module()
    with pytest.raises(SystemExit):
        finalizer._parse_args(["--date", "2026-08-25"])
    with pytest.raises(SystemExit):
        finalizer._parse_args(["--provider", "propline"])


def test_execute_cli_checks_exact_gate_before_loading_credentials(monkeypatch):
    finalizer = _module()
    monkeypatch.delenv(finalizer.WRITE_GATE_ENV, raising=False)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    assert finalizer.main(["--execute"]) == 3


def test_preview_cli_prints_one_aggregate_json_line(monkeypatch, capsys):
    finalizer = _module()
    monkeypatch.setattr(finalizer, "SupabaseMarketWriter", lambda *args: object())
    monkeypatch.setattr(
        finalizer,
        "run_finalizer",
        lambda **kwargs: {
            "report_type": "daily_active_provider_compaction_finalizer",
            "mode": "preview",
            "status": "success",
            "provider_results": [],
            "database_write_attempted": False,
            "database_write_performed": False,
            "provider_usage_rows_written": 0,
            "deletion_performed": False,
            "retention_execution_closed": True,
        },
    )
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret-value")

    assert finalizer.main([]) == 0
    captured = capsys.readouterr()
    assert len(captured.out.splitlines()) == 1
    assert json.loads(captured.out)["status"] == "success"
    assert "secret-value" not in captured.out + captured.err
```

Also add these concrete redaction and exit-code checks:

```python
def test_runtime_failure_returns_two_and_prints_no_exception_message(
    monkeypatch,
    capsys,
):
    finalizer = _module()
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret-value")
    monkeypatch.setattr(finalizer, "SupabaseMarketWriter", lambda *args: object())
    monkeypatch.setattr(
        finalizer,
        "run_finalizer",
        lambda **kwargs: {
            "report_type": "daily_active_provider_compaction_finalizer",
            "mode": "preview",
            "target_slate_date": "2026-08-25",
            "status": "failed",
            "preflight_complete": False,
            "provider_results": [{"provider": "propline", "error_type": "ValueError"}],
            "database_write_attempted": False,
            "database_write_performed": False,
            "provider_usage_rows_written": 0,
            "deletion_performed": False,
            "retention_execution_closed": True,
            "elapsed_seconds": 1.0,
        },
    )
    assert finalizer.main([]) == 2
    captured = capsys.readouterr()
    assert json.loads(captured.out)["status"] == "failed"
    assert "secret-value" not in captured.out + captured.err


def test_configuration_failure_returns_three_with_static_error_code(monkeypatch, capsys):
    finalizer = _module()
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    assert finalizer.main([]) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip() == "daily_compaction_finalizer_config_error:OSError"


@pytest.mark.parametrize(
    "value",
    ["", "true", "1", "d1_active_providers_compact_only", "D1_ACTIVE_PROVIDERS"],
)
def test_execute_gate_requires_the_exact_literal_value(monkeypatch, value):
    finalizer = _module()
    monkeypatch.setenv(finalizer.WRITE_GATE_ENV, value)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    assert finalizer.main(["--execute"]) == 3


def test_summary_serialization_rejects_unapproved_top_level_fields():
    finalizer = _module()
    report = {
        "report_type": "daily_active_provider_compaction_finalizer",
        "status": "success",
        "provider_results": [{
            "provider": "propline",
            "execution_status": "no_op",
            "canonical_rows": [{"source_snapshot_ids": ["nested-secret-id"]}],
        }],
        "canonical_rows": [{"source_snapshot_ids": ["secret-id"]}],
        "credentials": "secret-value",
    }
    safe = finalizer._safe_summary(report)
    assert safe == {
        "report_type": "daily_active_provider_compaction_finalizer",
        "status": "success",
        "provider_results": [{
            "provider": "propline",
            "execution_status": "no_op",
        }],
    }
    assert "secret-id" not in json.dumps(safe)
    assert "nested-secret-id" not in json.dumps(safe)
    assert "secret-value" not in json.dumps(safe)
```

- [x] **Step 2: Run CLI tests and confirm the CLI contract is incomplete**

Run:

```powershell
python -m pytest tests/test_daily_active_provider_compaction_finalizer.py -q
```

Expected: new CLI tests fail before `_parse_args`, `_safe_summary`, and final
exit behavior are implemented.

- [x] **Step 3: Implement preview-default parsing and safe output**

Use no date, provider, output, or retry option:

```python
def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


SAFE_TOP_LEVEL_FIELDS = (
    "report_type",
    "mode",
    "target_slate_date",
    "status",
    "preflight_complete",
    "database_write_attempted",
    "database_write_performed",
    "provider_usage_rows_written",
    "deletion_performed",
    "retention_execution_closed",
    "deadline_exceeded",
    "elapsed_seconds",
)

SAFE_PROVIDER_FIELDS = PROVIDER_SUMMARY_FIELDS + (
    "error_type",
    "execution_status",
    "failure_reason",
    "database_write_attempted",
    "database_write_performed",
    "write_row_count",
    "write_error_type",
    "post_write_exact",
)


def _safe_summary(report: dict[str, Any]) -> dict[str, Any]:
    safe = {key: report[key] for key in SAFE_TOP_LEVEL_FIELDS if key in report}
    safe["provider_results"] = [
        {key: item[key] for key in SAFE_PROVIDER_FIELDS if key in item}
        for item in report.get("provider_results", [])
    ]
    return safe
```

Gate execute before loading either credential:

```python
def main(argv: list[str] | None = None) -> int:
    try:
        args = _parse_args(argv if argv is not None else sys.argv[1:])
        allow_execute = os.environ.get(WRITE_GATE_ENV, "") == WRITE_GATE_VALUE
        if args.execute and not allow_execute:
            raise EnvironmentError("daily_active_provider_compaction_write_gate_closed")
        writer = SupabaseMarketWriter(
            _env("SUPABASE_URL"),
            _env("SUPABASE_SERVICE_ROLE_KEY"),
        )
        report = run_finalizer(
            writer=writer,
            execute=args.execute,
            allow_execute=allow_execute,
        )
        print(json.dumps(_safe_summary(report), sort_keys=True, separators=(",", ":")))
        return 0 if report["status"] == "success" else 2
    except requests.RequestException as error:
        print(f"daily_compaction_finalizer_request_error:{type(error).__name__}", file=sys.stderr)
        return 2
    except FinalizerDeadlineExceeded as error:
        print(f"daily_compaction_finalizer_runtime_error:{type(error).__name__}", file=sys.stderr)
        return 2
    except (EnvironmentError, OSError, TypeError, ValueError) as error:
        print(f"daily_compaction_finalizer_config_error:{type(error).__name__}", file=sys.stderr)
        return 3
```

Do not print `str(error)`. End the module with
`raise SystemExit(main())` under the normal `__main__` guard.

- [x] **Step 4: Run CLI security and complete focused tests**

Run:

```powershell
python -m pytest tests/test_daily_active_provider_compaction_finalizer.py tests/test_repair_compact_market_snapshot_partition.py tests/test_supabase_writer.py -q
python -m py_compile scripts/run_daily_active_provider_compaction_finalizer.py scripts/repair_compact_market_snapshot_partition.py
```

Expected: all tests and both compilations pass; captured output contains no
credentials, raw rows, source IDs, player names, books, or exception messages.

- [x] **Step 5: Commit the CLI and redaction boundary**

```powershell
git add scripts/run_daily_active_provider_compaction_finalizer.py tests/test_daily_active_provider_compaction_finalizer.py
git commit -m "feat: add redacted compaction finalizer cli"
```

---

### Task 5: Complete Local Verification And Handoff Documentation

**Files:**
- Modify: `docs/superpowers/plans/2026-08-25-active-provider-compaction-finalizer.md`
- Modify: `docs/current-state.md`
- Modify: `docs/superpowers/plans/2026-08-26-daily-active-provider-compaction-finalizer.md`

**Interfaces:**
- Consumes: the exact implementation commit and all focused test results.
- Produces: a reviewable pushed feature branch with no production activation
  and a precise next decision of merge review, followed by a separate
  preview-only Render creation decision.

- [x] **Step 1: Run the focused finalizer safety suite**

Run:

```powershell
python -m pytest tests/test_daily_active_provider_compaction_finalizer.py tests/test_repair_compact_market_snapshot_partition.py tests/test_compact_market_snapshots_script.py tests/test_market_snapshot_compaction.py tests/test_supabase_writer.py -q
```

Expected: all tests pass, including fixed provider order, preview zero-write,
double gating, source drift, ambiguous write, idempotent retry, deadline, and
redaction regressions.

- [x] **Step 2: Run the complete repository verification**

Run:

```powershell
python -m pytest tests -q
git diff --check
```

Expected: the complete test suite passes and Git reports no whitespace errors.
If tests change a tracked generated report, restore only that generated report
to its pre-test content and rerun `git status --short`.

- [x] **Step 3: Prove the production boundary stayed closed**

Run:

```powershell
git diff origin/main..HEAD --name-only
git diff origin/main..HEAD -- render.yaml dashboard netlify pipeline market_infra/supabase_writer.py
git diff origin/main..HEAD -- scripts/repair_compact_market_snapshot_partition.py | rg "EXECUTION_PARTITIONS|ALLOW_COMPACT_MARKET_PARTITION_REPAIR"
```

Expected:

- changed runtime files are limited to the two planned scripts and two test
  files;
- the second command prints no diff;
- any third-command matches are unchanged context only; and
- no active provider appears in `EXECUTION_PARTITIONS`.

Also run this static assertion:

```powershell
python -c "from scripts.run_daily_active_provider_compaction_finalizer import ACTIVE_PROVIDERS, DEFAULT_DEADLINE_SECONDS; assert ACTIVE_PROVIDERS == ('propline', 'therundown'); assert DEFAULT_DEADLINE_SECONDS == 480.0"
```

- [x] **Step 4: Record the local-only implementation evidence**

Append an execution record to the 2026-08-25 controlling plan using exact
commit IDs and test counts. Update the tracking/data lane in
`docs/current-state.md` to say:

```markdown
The separate daily active-provider compaction finalizer is implemented and
locally verified on an isolated branch. Preview remains the default; no Render
service exists, the write gate is unset, no live preview or database mutation
occurred, the historical 105-partition backlog remains closed, and deletion
remains NO-GO. The reviewed feature branch was pushed at
`6090f2547776411d4da94bba2f56add3b2238ba8` (`6090f254`). The next decision is
a separate merge review/decision; preview-only Render cron creation remains a
later separately reviewed decision.
```

In this plan's execution record, include:

- the exact implementation commit;
- focused and full-suite counts;
- `database_write_performed=false`;
- `live_preview_performed=false`;
- `render_service_created=false`;
- `historical_backlog_execution_closed=true`; and
- `retention_execution_closed=true`.

Do not update the automation memory because production posture has not
changed.

- [x] **Step 5: Run final review using the completion skills**

Use `superpowers:requesting-code-review` for an independent requirements and
quality review. Resolve only findings inside this approved scope. Then use
`superpowers:verification-before-completion` and rerun the commands it
requires against the final commit.

- [x] **Step 6: Commit and push the reviewed feature branch**

```powershell
git add docs/superpowers/plans/2026-08-25-active-provider-compaction-finalizer.md docs/current-state.md docs/superpowers/plans/2026-08-26-daily-active-provider-compaction-finalizer.md
git commit -m "docs: record daily finalizer verification"
git status --short --branch
git push
```

Expected: the feature branch is clean and tracks its remote. Do not merge,
deploy, create the Render cron, set the write gate, or run the finalizer live.

## Delivery Checkpoint

Completion of this plan produces reviewed, behavior-disabled code only. The
next approvals remain separate and sequential:

1. merge the reviewed code;
2. create `bbe-market-compaction-finalizer` directly in Render with proposed
   schedule `47 12 * * *` and preview command only;
3. observe three consecutive clean natural previews;
4. review current Render cost and read/runtime evidence;
5. separately decide whether to activate compact-only execute mode;
6. separately design bounded historical backlog repair; and
7. separately decide any retention deletion after backup, recovery, exact
   coverage, season-evidence, and dry-run gates pass.

No checkpoint inherits approval from the one before it.

## Task 5 Local Verification Record (Steps 1-4)

- Final reviewed implementation branch:
  `codex/daily-compaction-finalizer-implementation`, at implementation HEAD
  `304555b1bd796f435fbbc5754cdb3dc96af7073f` (`304555b1`). The bounded
  final-review hardening commit addressed the reviewed deadline, read-budget,
  and unexpected-exception boundaries.
- Focused suite: `117 passed`; complete repository suite: `2,573 passed`.
  The focused command used
  `tests/test_market_infra_supabase_writer.py`, the authorized replacement for
  the nonexistent `tests/test_supabase_writer.py` named above.
- `git diff --check` passed. The only test-generated tracked change was
  `analytics/output/gate_f_preclose_clv_proxy_lab.md`; its zero-row fixture
  output was verified and only that exact generated report was restored to
  HEAD before this documentation change.
- Boundary commands showed no diff under `render.yaml`, `dashboard`,
  `netlify`, `pipeline`, or `market_infra/supabase_writer.py`. The code/test
  portion of `origin/main..HEAD` is limited to
  `scripts/repair_compact_market_snapshot_partition.py`,
  `scripts/run_daily_active_provider_compaction_finalizer.py`,
  `tests/test_repair_compact_market_snapshot_partition.py`, and
  `tests/test_daily_active_provider_compaction_finalizer.py`; the separate
  design and this plan are documentation. No active provider appears in
  historical `EXECUTION_PARTITIONS`. Static assertions confirmed
  `ACTIVE_PROVIDERS == ('propline', 'therundown')` and
  `DEFAULT_DEADLINE_SECONDS == 480.0`.
- `database_write_performed=false`; `live_preview_performed=false`;
  `render_service_created=false`; `historical_backlog_execution_closed=true`;
  `retention_execution_closed=true`.
- Preview remains the default; no Render service exists and the write gate is
  unset. The historical `105`-partition backlog remains closed, deletion is
  NO-GO, and no automation memory was updated. The reviewed feature branch was
  pushed at `6090f2547776411d4da94bba2f56add3b2238ba8` (`6090f254`) and tracks
  its upstream. The next decision is a separate merge review/decision;
  preview-only Render cron creation remains a later separately reviewed step.

## Final Review Correction Record (2026-08-26)

- Review started from `36502102e5382bcb88addbe1aa9ed3aa26747243`.
- Bounded final-review hardening was committed as
  `304555b1bd796f435fbbc5754cdb3dc96af7073f` (`304555b1`). The final
  independent re-review addressed all findings and returned **Ready to merge:
  Yes**.
- Strict TDD reproduced the three Important findings before fixes:
  deadline boundary `2 failed, 31 passed`; compact-only/read-budget
  `9 failed, 72 passed`; unexpected exception boundaries
  `4 failed, 34 passed`.
- Finalizer and exact-reader modules passed `85` tests. The authorized
  five-file safety suite passed `117` tests, and the complete repository suite
  passed `2,573` tests.
- Execute now performs at most two full raw reads per provider. Post-write
  proof reads only `compact_market_line_movements` and compares canonical
  count/hash against the fresh rebuild.
- Deadline checks run after bounded operations and final elapsed time can
  force top-level failure while preserving known or ambiguous write state.
- Unexpected `Exception` subclasses are sanitized at preflight, fresh-read,
  upsert, and post-check boundaries. `BaseException`, `SystemExit`, and
  `KeyboardInterrupt` are not caught.
- The full suite regenerated only
  `analytics/output/gate_f_preclose_clv_proxy_lab.md`; its zero-row fixture
  diff was verified and that exact tracked artifact was restored to HEAD.
- Compile, whitespace, static provider/deadline/allowlist, and boundary diff
  checks passed. No network, Supabase, database, Render, deploy, push, merge,
  deletion, retention, provider-usage, notification, lock, UI, model, or
  source-of-truth action occurred.
- Step 6 push completed for
  `codex/daily-compaction-finalizer-implementation` at
  `6090f2547776411d4da94bba2f56add3b2238ba8` (`6090f254`), with upstream
  tracking set. The next decision is a separate merge review/decision; Render
  creation, live preview, execute activation, historical backlog work, and
  deletion remain separately gated.
