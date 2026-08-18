# Season Retention Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, read-only Phase 1 audit that proves raw-to-compact market coverage by provider/date, reports retention blockers, and preserves a BoltOdds retirement closure record without granting deletion authority.

**Architecture:** Add a single server-side PostgreSQL aggregation that emits one validation envelope, then pass that envelope to a pure-standard-library Python reporter. The reporter combines exact coverage with explicit season-evidence and pin manifests, fails closed on missing proof, and renders local JSON/Markdown reports; it never connects with service-role credentials or emits executable cleanup SQL.

**Tech Stack:** PostgreSQL SQL through the linked Supabase CLI, Python 3.11 standard library, pytest

**Spec:** `docs/superpowers/specs/2026-08-18-season-retention-foundation-design.md`

## Global Constraints

- Phase 1 is local and read-only; no database write, DDL, backfill, deletion, archive, vacuum, migration, function, trigger, or retention policy is allowed.
- Do not modify or call `scripts/retire_market_snapshots.py --execute`; do not set `ALLOW_MARKET_SNAPSHOT_DELETE`.
- Leave `scripts/supabase_retention_readiness.sql` unchanged as the existing sampled historical guardrail; the new query is an independent exact-evidence path.
- Do not change production code, schedules, providers, provider order, models, formula dates, thresholds, staking, notifications, locks, dashboard artifacts, source-of-truth rules, environment variables, or secrets.
- TheRundown remains official book-of-record, PropLine remains fallback/live-movement sidecar, and BoltOdds remains retired.
- Add no third-party dependency. Use `argparse`, `datetime`, `json`, `pathlib`, `re`, `sys`, and standard typing only.
- Generated reports default to ignored `analytics/output/retention/`; never commit a live Supabase extract or raw provider payload.
- Keep `retention_execution_closed=true`, `deletion_approved=false`, and `production_authority="none"` in every generated decision artifact.
- An age threshold is never sufficient proof. Exact compact coverage, decision-linked outcome evidence, and completed pin reconciliation are independent gates.
- Work only on `codex/season-retention-foundation`; local commits are allowed, but merge, push, deployment, production backfill, and deletion remain separate approvals.

## File Structure

- Create `scripts/supabase_retention_exact_coverage.sql`: one read-only query that computes exact group metrics and provider-runtime boundaries and returns one JSON envelope.
- Create `scripts/build_season_retention_readiness.py`: validates the envelope and local manifests, evaluates partitions, renders readiness and BoltOdds closure reports, and exposes the two CLI subcommands.
- Create `tests/test_build_season_retention_readiness.py`: contains all SQL-contract, validation, decision, rendering, redaction, CLI-exit, and BoltOdds closure tests using in-memory fixture builders.
- Do not modify the approved design spec, production modules, migrations, existing retention scripts, or operating-board docs during Phase 1 implementation.

## Shared Data Contracts

The SQL output must be a one-element JSON array from the Supabase CLI. The single row has a `retention_exact_coverage` field containing this envelope:

```json
{
  "audit_version": 1,
  "audit_generated_at": "2026-08-18T18:00:00+00:00",
  "complete": true,
  "retention_execution_closed": true,
  "deletion_approved": false,
  "query_scope": {
    "start_date": "2026-04-28",
    "end_date": "2026-08-18",
    "providers": ["boltodds", "propline", "the_odds", "therundown"]
  },
  "source_anomalies": [
    {
      "provider": "boltodds",
      "rows_missing_run_id": 0,
      "rows_missing_run_row": 0,
      "rows_missing_group_key": 0,
      "provider_run_mismatch_rows": 0
    }
  ],
  "coverage": [
    {
      "slate_date": "2026-06-01",
      "provider": "boltodds",
      "raw_snapshot_rows": 100,
      "raw_logical_bytes": 50000,
      "raw_group_count": 4,
      "compact_group_count": 4,
      "exact_group_count": 4,
      "mismatched_group_count": 0,
      "missing_compact_group_count": 0,
      "unexpected_compact_group_count": 0,
      "duplicate_compact_group_count": 0,
      "first_seen_mismatch_count": 0,
      "last_seen_mismatch_count": 0,
      "first_odds_mismatch_count": 0,
      "last_odds_mismatch_count": 0,
      "min_odds_mismatch_count": 0,
      "max_odds_mismatch_count": 0,
      "odds_move_count_mismatch_count": 0,
      "snapshot_count_mismatch_count": 0,
      "first_raw_seen_at": "2026-06-01T16:00:00+00:00",
      "last_raw_seen_at": "2026-06-01T22:00:00+00:00",
      "coverage_exact": true
    }
  ],
  "provider_runtime": [
    {
      "provider": "boltodds",
      "first_run_at": "2026-05-07T16:00:00+00:00",
      "last_run_at": "2026-06-17T17:20:59+00:00",
      "run_count": 20,
      "completed_run_count": 19,
      "failed_run_count": 1,
      "request_count": 40,
      "books_seen": ["betmgm", "betrivers", "caesars", "fanduel", "kalshi"],
      "first_snapshot_at": "2026-05-07T16:05:00+00:00",
      "last_snapshot_at": "2026-06-16T13:37:44+00:00",
      "snapshot_count": 611972,
      "snapshot_logical_bytes": 461536160,
      "last_heartbeat_at": "2026-06-17T17:20:59+00:00",
      "last_message_at": "2026-06-17T17:20:30+00:00",
      "heartbeat_count": 51900
    }
  ]
}
```

The optional normalized season-evidence manifest has one explicit record per audited slate date:

```json
{
  "schema_version": 1,
  "generated_at": "2026-08-18T18:00:00+00:00",
  "dates": [
    {
      "slate_date": "2026-06-01",
      "decision_linked": true,
      "evidence_counts": {
        "official_tracked_picks": 2,
        "accepted_bets": 1,
        "sent_notifications": 1,
        "consumed_locks": 2,
        "frozen_alt_v2_rows": 0,
        "operator_incidents": 0,
        "model_review_pins": 0
      },
      "required_evidence": {
        "results": true,
        "bet_timing": true,
        "checkpoint_market": true,
        "close_clv": true,
        "provider_metadata": true
      }
    }
  ]
}
```

The optional pin manifest has one explicit record per provider/date partition. An empty `pins` array is valid only when `reconciled` is explicitly true:

```json
{
  "schema_version": 1,
  "generated_at": "2026-08-18T18:00:00+00:00",
  "partitions": [
    {
      "slate_date": "2026-06-01",
      "provider": "boltodds",
      "reconciled": true,
      "pins": [
        {
          "reason": "accepted_bet",
          "status": "preserved",
          "preserved_artifact": "data/picks_history.json"
        }
      ]
    }
  ]
}
```

---

### Task 1: Exact Supabase Coverage Query

**Files:**
- Create: `scripts/supabase_retention_exact_coverage.sql`
- Create: `tests/test_build_season_retention_readiness.py`

**Interfaces:**
- Consumes: `public.market_snapshots`, `public.market_provider_runs`, `public.compact_market_line_movements`, and `public.market_feed_heartbeats` through SELECT-only SQL.
- Produces: one row named `retention_exact_coverage` containing the version-1 envelope in Shared Data Contracts.

- [ ] **Step 1: Write the failing SQL-contract tests**

Create `tests/test_build_season_retention_readiness.py` with these tests and constants:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "scripts" / "supabase_retention_exact_coverage.sql"
REPORTER_PATH = ROOT / "scripts" / "build_season_retention_readiness.py"


def test_exact_coverage_sql_exists_and_is_read_only():
    assert SQL_PATH.exists()
    sql = SQL_PATH.read_text(encoding="utf-8").lower()
    forbidden = (
        " insert ", " update ", " delete ", " truncate ", " drop ",
        " alter ", " create ", " grant ", " revoke ", " vacuum ",
    )
    assert not any(token in f" {sql} " for token in forbidden)
    assert "retention_execution_closed" in sql
    assert "deletion_approved" in sql


def test_exact_coverage_sql_uses_the_canonical_group_and_ordering_contract():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()
    for field in (
        "slate_date", "provider", "book_key", "normalized_player_name",
        "market_key", "side", "line",
    ):
        assert field in sql
    assert "order by observed_at asc, id asc" in sql
    assert "order by observed_at desc, id desc" in sql
    assert "lag(american_odds)" in sql
    assert "pg_column_size" in sql


def test_exact_coverage_sql_emits_all_blocking_metrics_and_runtime_boundaries():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()
    expected = (
        "raw_snapshot_rows", "raw_logical_bytes", "raw_group_count",
        "compact_group_count", "exact_group_count", "mismatched_group_count",
        "missing_compact_group_count", "unexpected_compact_group_count",
        "duplicate_compact_group_count", "first_seen_mismatch_count",
        "last_seen_mismatch_count", "first_odds_mismatch_count",
        "last_odds_mismatch_count", "min_odds_mismatch_count",
        "max_odds_mismatch_count", "odds_move_count_mismatch_count",
        "snapshot_count_mismatch_count", "coverage_exact",
        "rows_missing_run_id", "rows_missing_run_row",
        "rows_missing_group_key", "provider_run_mismatch_rows",
        "first_run_at", "last_run_at", "failed_run_count", "books_seen",
        "first_snapshot_at", "last_snapshot_at", "last_heartbeat_at",
        "last_message_at", "heartbeat_count",
    )
    for field in expected:
        assert field in sql


def test_exact_coverage_sql_documents_one_linked_cli_read():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()
    assert (
        "npx supabase db query --linked --file "
        "scripts\\supabase_retention_exact_coverage.sql -o json"
    ) in sql
```

- [ ] **Step 2: Run the SQL-contract tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_build_season_retention_readiness.py -v
```

Expected: FAIL because `scripts/supabase_retention_exact_coverage.sql` does not exist.

- [ ] **Step 3: Implement the exact SELECT-only SQL envelope**

Create `scripts/supabase_retention_exact_coverage.sql` with the following complete query:

```sql
-- Exact, read-only Supabase retention evidence for BBE market snapshots.
--
-- PowerShell:
--   npx supabase db query --linked --file scripts\supabase_retention_exact_coverage.sql -o json

with
settings as materialized (
  select
    date '2026-04-28' as start_date,
    (now() at time zone 'America/Phoenix')::date as end_date,
    array['boltodds', 'propline', 'the_odds', 'therundown']::text[] as providers
),
target_runs as materialized (
  select id, lower(trim(provider)) as provider, slate_date, started_at,
         completed_at, status, request_count, books_seen
  from public.market_provider_runs, settings
  where slate_date between settings.start_date and settings.end_date
    and lower(trim(provider)) = any(settings.providers)
),
raw_input as materialized (
  select
    ms.*,
    mpr.id as run_row_id,
    mpr.slate_date,
    lower(trim(mpr.provider)) as run_provider,
    pg_column_size(ms)::bigint as logical_bytes
  from public.market_snapshots ms
  left join public.market_provider_runs mpr on mpr.id = ms.run_id
  cross join settings
  where coalesce(
          mpr.slate_date,
          (ms.observed_at at time zone 'America/Phoenix')::date
        ) between settings.start_date and settings.end_date
    and lower(trim(ms.provider)) = any(settings.providers)
),
valid_raw as materialized (
  select
    slate_date,
    lower(trim(provider)) as provider,
    lower(trim(bookmaker_key)) as book_key,
    trim(normalized_player_name) as normalized_player_name,
    coalesce(nullif(trim(player_name), ''), trim(normalized_player_name)) as player_name,
    coalesce(nullif(trim(market_key), ''), 'pitcher_strikeouts') as market_key,
    lower(trim(side)) as side,
    line::numeric as line,
    observed_at,
    american_odds::integer as american_odds,
    id,
    logical_bytes
  from raw_input
  where run_row_id is not null
    and slate_date is not null
    and provider = run_provider
    and nullif(trim(bookmaker_key), '') is not null
    and nullif(trim(normalized_player_name), '') is not null
    and lower(trim(side)) in ('over', 'under')
    and line is not null
),
windowed_raw as materialized (
  select
    valid_raw.*,
    first_value(american_odds) over (
      partition by slate_date, provider, book_key, normalized_player_name, market_key, side, line
      order by observed_at asc, id asc
      rows between unbounded preceding and unbounded following
    ) as first_odds,
    first_value(american_odds) over (
      partition by slate_date, provider, book_key, normalized_player_name, market_key, side, line
      order by observed_at desc, id desc
      rows between unbounded preceding and unbounded following
    ) as last_odds,
    lag(american_odds) over (
      partition by slate_date, provider, book_key, normalized_player_name, market_key, side, line
      order by observed_at asc, id asc
    ) as previous_odds
  from valid_raw
),
raw_groups as materialized (
  select
    slate_date, provider, book_key, normalized_player_name, market_key, side, line,
    min(observed_at) as first_seen_at,
    max(observed_at) as last_seen_at,
    min(first_odds) as first_odds,
    min(last_odds) as last_odds,
    min(american_odds) as min_odds,
    max(american_odds) as max_odds,
    count(*) filter (
      where previous_odds is not null
        and american_odds is distinct from previous_odds
    )::integer as odds_move_count,
    count(*)::integer as snapshot_count,
    sum(logical_bytes)::bigint as raw_logical_bytes
  from windowed_raw
  group by slate_date, provider, book_key, normalized_player_name, market_key, side, line
),
compact_groups as materialized (
  select
    slate_date, lower(trim(provider)) as provider, lower(trim(book_key)) as book_key,
    trim(normalized_player_name) as normalized_player_name,
    coalesce(nullif(trim(market_key), ''), 'pitcher_strikeouts') as market_key,
    lower(trim(side)) as side, line::numeric as line,
    min(first_seen_at) as first_seen_at,
    max(last_seen_at) as last_seen_at,
    min(first_odds) as first_odds,
    min(last_odds) as last_odds,
    min(min_odds) as min_odds,
    max(max_odds) as max_odds,
    max(odds_move_count) as odds_move_count,
    max(snapshot_count) as snapshot_count,
    greatest(count(*) - 1, 0)::integer as compact_duplicate_count
  from public.compact_market_line_movements, settings
  where slate_date between settings.start_date and settings.end_date
    and lower(trim(provider)) = any(settings.providers)
  group by slate_date, lower(trim(provider)), lower(trim(book_key)),
           trim(normalized_player_name),
           coalesce(nullif(trim(market_key), ''), 'pitcher_strikeouts'),
           lower(trim(side)), line::numeric
),
joined_groups as materialized (
  select
    coalesce(r.slate_date, c.slate_date) as slate_date,
    coalesce(r.provider, c.provider) as provider,
    coalesce(r.book_key, c.book_key) as book_key,
    coalesce(r.normalized_player_name, c.normalized_player_name) as normalized_player_name,
    coalesce(r.market_key, c.market_key) as market_key,
    coalesce(r.side, c.side) as side,
    coalesce(r.line, c.line) as line,
    r.slate_date is not null as raw_present,
    c.slate_date is not null as compact_present,
    r.first_seen_at as raw_first_seen_at,
    c.first_seen_at as compact_first_seen_at,
    r.last_seen_at as raw_last_seen_at,
    c.last_seen_at as compact_last_seen_at,
    r.first_odds as raw_first_odds,
    c.first_odds as compact_first_odds,
    r.last_odds as raw_last_odds,
    c.last_odds as compact_last_odds,
    r.min_odds as raw_min_odds,
    c.min_odds as compact_min_odds,
    r.max_odds as raw_max_odds,
    c.max_odds as compact_max_odds,
    r.odds_move_count as raw_odds_move_count,
    c.odds_move_count as compact_odds_move_count,
    r.snapshot_count as raw_snapshot_count,
    c.snapshot_count as compact_snapshot_count,
    coalesce(r.raw_logical_bytes, 0)::bigint as raw_logical_bytes,
    coalesce(c.compact_duplicate_count, 0)::integer as compact_duplicate_count
  from raw_groups r
  full outer join compact_groups c
    on c.slate_date = r.slate_date
   and c.provider = r.provider
   and c.book_key = r.book_key
   and c.normalized_player_name = r.normalized_player_name
   and c.market_key = r.market_key
   and c.side = r.side
   and c.line = r.line
),
coverage_by_partition as materialized (
  select
    slate_date,
    provider,
    coalesce(sum(raw_snapshot_count) filter (where raw_present), 0)::bigint
      as raw_snapshot_rows,
    coalesce(sum(raw_logical_bytes) filter (where raw_present), 0)::bigint
      as raw_logical_bytes,
    count(*) filter (where raw_present)::bigint as raw_group_count,
    count(*) filter (where compact_present)::bigint as compact_group_count,
    count(*) filter (
      where raw_present and compact_present
        and raw_first_seen_at is not distinct from compact_first_seen_at
        and raw_last_seen_at is not distinct from compact_last_seen_at
        and raw_first_odds is not distinct from compact_first_odds
        and raw_last_odds is not distinct from compact_last_odds
        and raw_min_odds is not distinct from compact_min_odds
        and raw_max_odds is not distinct from compact_max_odds
        and raw_odds_move_count is not distinct from compact_odds_move_count
        and raw_snapshot_count is not distinct from compact_snapshot_count
    )::bigint as exact_group_count,
    count(*) filter (
      where raw_present and compact_present
        and (
          raw_first_seen_at is distinct from compact_first_seen_at
          or raw_last_seen_at is distinct from compact_last_seen_at
          or raw_first_odds is distinct from compact_first_odds
          or raw_last_odds is distinct from compact_last_odds
          or raw_min_odds is distinct from compact_min_odds
          or raw_max_odds is distinct from compact_max_odds
          or raw_odds_move_count is distinct from compact_odds_move_count
          or raw_snapshot_count is distinct from compact_snapshot_count
        )
    )::bigint as mismatched_group_count,
    count(*) filter (where raw_present and not compact_present)::bigint
      as missing_compact_group_count,
    count(*) filter (where compact_present and not raw_present)::bigint
      as unexpected_compact_group_count,
    coalesce(sum(compact_duplicate_count), 0)::bigint as duplicate_compact_group_count,
    count(*) filter (
      where raw_present and compact_present
        and raw_first_seen_at is distinct from compact_first_seen_at
    )::bigint as first_seen_mismatch_count,
    count(*) filter (
      where raw_present and compact_present
        and raw_last_seen_at is distinct from compact_last_seen_at
    )::bigint as last_seen_mismatch_count,
    count(*) filter (
      where raw_present and compact_present
        and raw_first_odds is distinct from compact_first_odds
    )::bigint as first_odds_mismatch_count,
    count(*) filter (
      where raw_present and compact_present
        and raw_last_odds is distinct from compact_last_odds
    )::bigint as last_odds_mismatch_count,
    count(*) filter (
      where raw_present and compact_present
        and raw_min_odds is distinct from compact_min_odds
    )::bigint as min_odds_mismatch_count,
    count(*) filter (
      where raw_present and compact_present
        and raw_max_odds is distinct from compact_max_odds
    )::bigint as max_odds_mismatch_count,
    count(*) filter (
      where raw_present and compact_present
        and raw_odds_move_count is distinct from compact_odds_move_count
    )::bigint as odds_move_count_mismatch_count,
    count(*) filter (
      where raw_present and compact_present
        and raw_snapshot_count is distinct from compact_snapshot_count
    )::bigint as snapshot_count_mismatch_count,
    min(raw_first_seen_at) filter (where raw_present) as first_raw_seen_at,
    max(raw_last_seen_at) filter (where raw_present) as last_raw_seen_at
  from joined_groups
  group by slate_date, provider
),
coverage_with_exactness as materialized (
  select
    coverage_by_partition.*,
    (
      missing_compact_group_count = 0
      and unexpected_compact_group_count = 0
      and duplicate_compact_group_count = 0
      and mismatched_group_count = 0
    ) as coverage_exact
  from coverage_by_partition
),
anomaly_counts as materialized (
  select
    lower(trim(provider)) as provider,
    count(*) filter (where run_id is null)::bigint as rows_missing_run_id,
    count(*) filter (where run_id is not null and run_row_id is null)::bigint
      as rows_missing_run_row,
    count(*) filter (
      where nullif(trim(bookmaker_key), '') is null
        or nullif(trim(normalized_player_name), '') is null
        or lower(trim(side)) not in ('over', 'under')
        or line is null
    )::bigint as rows_missing_group_key,
    count(*) filter (
      where run_row_id is not null
        and lower(trim(provider)) is distinct from run_provider
    )::bigint as provider_run_mismatch_rows
  from raw_input
  group by lower(trim(provider))
),
source_anomalies as materialized (
  select
    target.provider,
    coalesce(anomaly_counts.rows_missing_run_id, 0)::bigint as rows_missing_run_id,
    coalesce(anomaly_counts.rows_missing_run_row, 0)::bigint as rows_missing_run_row,
    coalesce(anomaly_counts.rows_missing_group_key, 0)::bigint as rows_missing_group_key,
    coalesce(anomaly_counts.provider_run_mismatch_rows, 0)::bigint
      as provider_run_mismatch_rows
  from unnest((select providers from settings)) as target(provider)
  left join anomaly_counts on anomaly_counts.provider = target.provider
),
run_summary as materialized (
  select
    provider,
    min(started_at) as first_run_at,
    max(coalesce(completed_at, started_at)) as last_run_at,
    count(*)::bigint as run_count,
    count(*) filter (where status = 'completed')::bigint as completed_run_count,
    count(*) filter (where status = 'failed')::bigint as failed_run_count,
    coalesce(sum(request_count), 0)::bigint as request_count
  from target_runs
  group by provider
),
book_summary as materialized (
  select
    provider,
    array_agg(distinct book_key order by book_key) as books_seen
  from valid_raw
  group by provider
),
snapshot_summary as materialized (
  select
    lower(trim(provider)) as provider,
    min(observed_at) as first_snapshot_at,
    max(observed_at) as last_snapshot_at,
    count(*)::bigint as snapshot_count,
    coalesce(sum(logical_bytes), 0)::bigint as snapshot_logical_bytes
  from raw_input
  group by lower(trim(provider))
),
heartbeat_summary as materialized (
  select
    lower(trim(h.provider)) as provider,
    max(h.observed_at) as last_heartbeat_at,
    max(h.last_message_at) as last_message_at,
    count(*)::bigint as heartbeat_count
  from public.market_feed_heartbeats h
  cross join settings
  where h.slate_date between settings.start_date and settings.end_date
    and lower(trim(h.provider)) = any(settings.providers)
  group by lower(trim(h.provider))
),
provider_runtime as materialized (
  select
    target.provider,
    run_summary.first_run_at,
    run_summary.last_run_at,
    coalesce(run_summary.run_count, 0)::bigint as run_count,
    coalesce(run_summary.completed_run_count, 0)::bigint as completed_run_count,
    coalesce(run_summary.failed_run_count, 0)::bigint as failed_run_count,
    coalesce(run_summary.request_count, 0)::bigint as request_count,
    coalesce(book_summary.books_seen, '{}'::text[]) as books_seen,
    snapshot_summary.first_snapshot_at,
    snapshot_summary.last_snapshot_at,
    coalesce(snapshot_summary.snapshot_count, 0)::bigint as snapshot_count,
    coalesce(snapshot_summary.snapshot_logical_bytes, 0)::bigint
      as snapshot_logical_bytes,
    heartbeat_summary.last_heartbeat_at,
    heartbeat_summary.last_message_at,
    coalesce(heartbeat_summary.heartbeat_count, 0)::bigint as heartbeat_count
  from unnest((select providers from settings)) as target(provider)
  left join run_summary on run_summary.provider = target.provider
  left join book_summary on book_summary.provider = target.provider
  left join snapshot_summary on snapshot_summary.provider = target.provider
  left join heartbeat_summary on heartbeat_summary.provider = target.provider
)
select jsonb_build_object(
  'audit_version', 1,
  'audit_generated_at', now(),
  'complete', true,
  'retention_execution_closed', true,
  'deletion_approved', false,
  'query_scope', jsonb_build_object(
    'start_date', (select start_date from settings),
    'end_date', (select end_date from settings),
    'providers', (select providers from settings)
  ),
  'source_anomalies', coalesce(
    (select jsonb_agg(to_jsonb(source_anomalies) order by provider) from source_anomalies),
    '[]'::jsonb
  ),
  'coverage', coalesce(
    (select jsonb_agg(to_jsonb(coverage_with_exactness) order by slate_date, provider)
     from coverage_with_exactness),
    '[]'::jsonb
  ),
  'provider_runtime', coalesce(
    (select jsonb_agg(to_jsonb(provider_runtime) order by provider) from provider_runtime),
    '[]'::jsonb
  )
) as retention_exact_coverage;
```

Do not add `source_snapshot_ids`, `metadata`, `source_payload`, or `error_message` to the output. Exact count and price/timestamp metrics are sufficient for Phase 1 and materially reduce query memory.

- [ ] **Step 4: Run the SQL-contract tests and verify they pass**

Run:

```powershell
python -m pytest tests/test_build_season_retention_readiness.py -v
git diff --check
```

Expected: all Task 1 tests PASS; `git diff --check` prints nothing.

- [ ] **Step 5: Commit the exact query**

```powershell
git add scripts/supabase_retention_exact_coverage.sql tests/test_build_season_retention_readiness.py
git commit -m "feat: add exact retention coverage query"
```

### Task 2: Envelope Validation and Retention Decisions

**Files:**
- Create: `scripts/build_season_retention_readiness.py`
- Modify: `tests/test_build_season_retention_readiness.py`

**Interfaces:**
- Consumes: `load_query_envelope(path_or_dash: str, stdin: TextIO) -> dict[str, Any]`, the version-1 envelope, the Gate C manifest, optional normalized season evidence, and optional pin manifest.
- Produces: `build_readiness_report` with keyword-only `envelope`, `gate_c`, `season_evidence`, `pins`, `as_of`, and `raw_retention_days` arguments, returning one fail-closed decision per provider/date partition plus summary counts.

- [ ] **Step 1: Write fixture builders and failing validation/decision tests**

Append fixture builders and tests to `tests/test_build_season_retention_readiness.py`:

```python
def _coverage(**overrides):
    row = {
        "slate_date": "2026-06-01", "provider": "boltodds",
        "raw_snapshot_rows": 100, "raw_logical_bytes": 50000,
        "raw_group_count": 4, "compact_group_count": 4, "exact_group_count": 4,
        "mismatched_group_count": 0,
        "missing_compact_group_count": 0, "unexpected_compact_group_count": 0,
        "duplicate_compact_group_count": 0,
        "first_seen_mismatch_count": 0, "last_seen_mismatch_count": 0,
        "first_odds_mismatch_count": 0, "last_odds_mismatch_count": 0,
        "min_odds_mismatch_count": 0, "max_odds_mismatch_count": 0,
        "odds_move_count_mismatch_count": 0, "snapshot_count_mismatch_count": 0,
        "first_raw_seen_at": "2026-06-01T16:00:00+00:00",
        "last_raw_seen_at": "2026-06-01T22:00:00+00:00",
        "coverage_exact": True,
    }
    row.update(overrides)
    return row


def _runtime(**overrides):
    row = {
        "provider": "boltodds", "first_run_at": "2026-05-07T16:00:00+00:00",
        "last_run_at": "2026-06-17T17:20:59+00:00", "run_count": 20,
        "completed_run_count": 19, "failed_run_count": 1, "request_count": 40,
        "books_seen": ["fanduel", "betmgm"],
        "first_snapshot_at": "2026-05-07T16:05:00+00:00",
        "last_snapshot_at": "2026-06-16T13:37:44+00:00",
        "snapshot_count": 611972, "snapshot_logical_bytes": 461536160,
        "last_heartbeat_at": "2026-06-17T17:20:59+00:00",
        "last_message_at": "2026-06-17T17:20:30+00:00", "heartbeat_count": 51900,
    }
    row.update(overrides)
    return row


def _envelope(*, coverage=None, anomalies=None, runtime=None):
    return {
        "audit_version": 1,
        "audit_generated_at": "2026-08-18T18:00:00+00:00",
        "complete": True,
        "retention_execution_closed": True,
        "deletion_approved": False,
        "query_scope": {
            "start_date": "2026-04-28", "end_date": "2026-08-18",
            "providers": ["boltodds"],
        },
        "source_anomalies": anomalies if anomalies is not None else [{
            "provider": "boltodds", "rows_missing_run_id": 0,
            "rows_missing_run_row": 0, "rows_missing_group_key": 0,
            "provider_run_mismatch_rows": 0,
        }],
        "coverage": coverage if coverage is not None else [_coverage()],
        "provider_runtime": runtime if runtime is not None else [_runtime()],
    }


def _season_evidence(*, complete=True):
    return {
        "schema_version": 1, "generated_at": "2026-08-18T18:00:00+00:00",
        "dates": [{
            "slate_date": "2026-06-01", "decision_linked": True,
            "evidence_counts": {
                "official_tracked_picks": 2, "accepted_bets": 1,
                "sent_notifications": 1, "consumed_locks": 2,
                "frozen_alt_v2_rows": 0, "operator_incidents": 0,
                "model_review_pins": 0,
            },
            "required_evidence": {
                "results": complete, "bet_timing": complete,
                "checkpoint_market": complete, "close_clv": complete,
                "provider_metadata": complete,
            },
        }],
    }


def _pins(*, reconciled=True, status="preserved"):
    return {
        "schema_version": 1, "generated_at": "2026-08-18T18:00:00+00:00",
        "partitions": [{
            "slate_date": "2026-06-01", "provider": "boltodds",
            "reconciled": reconciled,
            "pins": [{
                "reason": "accepted_bet", "status": status,
                "preserved_artifact": "data/picks_history.json",
            }],
        }],
    }


def _gate_c_manifest():
    return {
        "artifact": "gate_c_pitcher_k_outcome_dataset",
        "generated_at": "2026-08-18T17:00:00+00:00",
        "loaded_slate_dates": ["2026-06-01"],
        "jsonl_sha256": "a" * 64,
        "summary_sha256": "b" * 64,
        "reconciliation": {"graded_pick_rows": 2, "matched_pick_rows": 2,
                           "unmatched_pick_rows": 0},
        "summary_counts": {"rows_missing_result": 0, "tracked_pick_rows": 2,
                           "context_snapshot_counts": {"official_close": 2}},
    }


def test_load_query_envelope_accepts_supabase_array_wrapper(tmp_path):
    path = tmp_path / "query.json"
    path.write_text(json.dumps([{"retention_exact_coverage": _envelope()}]), encoding="utf-8")
    assert retention.load_query_envelope(str(path))["audit_version"] == 1


@pytest.mark.parametrize("mutation", [
    lambda value: value.update(complete=False),
    lambda value: value.update(retention_execution_closed=False),
    lambda value: value.update(deletion_approved=True),
    lambda value: value["coverage"][0].update(provider="unknown_provider"),
])
def test_validate_envelope_rejects_untrustworthy_input(mutation):
    envelope = _envelope()
    mutation(envelope)
    with pytest.raises(ValueError):
        retention.validate_envelope(envelope)


def test_stale_query_scope_is_rejected_for_requested_as_of_date():
    envelope = _envelope()
    envelope["query_scope"]["end_date"] = "2026-08-17"
    with pytest.raises(ValueError, match="query scope is stale"):
        retention.build_readiness_report(
            envelope=envelope, gate_c=_gate_c_manifest(),
            season_evidence=_season_evidence(), pins=_pins(),
            as_of="2026-08-18", raw_retention_days=30,
        )


def test_exact_old_partition_with_complete_evidence_is_ready_for_review():
    report = retention.build_readiness_report(
        envelope=_envelope(), gate_c=_gate_c_manifest(),
        season_evidence=_season_evidence(), pins=_pins(),
        as_of="2026-08-18", raw_retention_days=30,
    )
    assert report["partitions"][0]["decision"] == "ready_for_retention_review"
    assert report["retention_execution_closed"] is True
    assert report["deletion_approved"] is False


@pytest.mark.parametrize("field", [
    "missing_compact_group_count", "unexpected_compact_group_count",
    "duplicate_compact_group_count", "first_seen_mismatch_count",
    "last_seen_mismatch_count", "first_odds_mismatch_count",
    "last_odds_mismatch_count", "min_odds_mismatch_count",
    "max_odds_mismatch_count", "odds_move_count_mismatch_count",
    "snapshot_count_mismatch_count",
])
def test_every_compaction_mismatch_blocks(field):
    metric_mismatch = field not in {
        "missing_compact_group_count", "unexpected_compact_group_count",
        "duplicate_compact_group_count",
    }
    row = _coverage(**{
        field: 1,
        "mismatched_group_count": 1 if metric_mismatch else 0,
        "coverage_exact": False,
    })
    report = retention.build_readiness_report(
        envelope=_envelope(coverage=[row]), gate_c=_gate_c_manifest(),
        season_evidence=_season_evidence(), pins=_pins(),
        as_of="2026-08-18", raw_retention_days=30,
    )
    assert report["partitions"][0]["decision"] == "blocked_compaction"
    assert field in report["partitions"][0]["reason_codes"]


def test_recent_partition_is_not_in_policy_window():
    report = retention.build_readiness_report(
        envelope=_envelope(coverage=[_coverage(slate_date="2026-08-10")]),
        gate_c=_gate_c_manifest(), season_evidence=None, pins=None,
        as_of="2026-08-18", raw_retention_days=30,
    )
    assert report["partitions"][0]["decision"] == "not_in_policy_window"


def test_missing_or_incomplete_outcome_evidence_blocks():
    report = retention.build_readiness_report(
        envelope=_envelope(), gate_c=_gate_c_manifest(),
        season_evidence=_season_evidence(complete=False), pins=_pins(),
        as_of="2026-08-18", raw_retention_days=30,
    )
    assert report["partitions"][0]["decision"] == "blocked_outcome_evidence"


def test_missing_or_unpreserved_pin_evidence_blocks():
    report = retention.build_readiness_report(
        envelope=_envelope(), gate_c=_gate_c_manifest(),
        season_evidence=_season_evidence(), pins=_pins(status="pending"),
        as_of="2026-08-18", raw_retention_days=30,
    )
    assert report["partitions"][0]["decision"] == "blocked_pinned_evidence"
```

Add `from scripts import build_season_retention_readiness as retention` after the reporter file exists.

- [ ] **Step 2: Run the new tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_build_season_retention_readiness.py -v
```

Expected: FAIL because the reporter functions do not exist.

- [ ] **Step 3: Implement validation and fail-closed evaluation**

Create `scripts/build_season_retention_readiness.py` with these imports, constants, and loaders, then implement the validation and report rules below them:

```python
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, TextIO


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GATE_C_MANIFEST = ROOT / "data/research/gate_c/pitcher_k_outcome_dataset_manifest.json"
DEFAULT_OUTPUT_DIR = ROOT / "analytics/output/retention"
ALLOWED_PROVIDERS = {"boltodds", "propline", "the_odds", "therundown"}
MISMATCH_FIELDS = (
    "missing_compact_group_count", "unexpected_compact_group_count",
    "duplicate_compact_group_count", "first_seen_mismatch_count",
    "last_seen_mismatch_count", "first_odds_mismatch_count",
    "last_odds_mismatch_count", "min_odds_mismatch_count",
    "max_odds_mismatch_count", "odds_move_count_mismatch_count",
    "snapshot_count_mismatch_count",
)
REQUIRED_DECISION_EVIDENCE = (
    "results", "bet_timing", "checkpoint_market", "close_clv", "provider_metadata",
)
BOLTODDS_SUSPENDED_AT = datetime.fromisoformat("2026-06-17T17:22:29+00:00")


def load_query_envelope(
    path_or_dash: str, *, stdin: TextIO | None = None,
) -> dict[str, Any]:
    raw = (stdin or sys.stdin).read() if path_or_dash == "-" else Path(path_or_dash).read_text(encoding="utf-8")
    wrapper = json.loads(raw)
    if not isinstance(wrapper, list) or len(wrapper) != 1 or not isinstance(wrapper[0], dict):
        raise ValueError("Supabase query output must contain exactly one row")
    value = wrapper[0].get("retention_exact_coverage")
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("retention_exact_coverage must be a JSON object")
    return value


def load_json_object(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value
```

Implement the bodies with these exact rules:

1. `load_query_envelope()` reads `sys.stdin` when `path_or_dash == "-"`; otherwise it uses `Path.read_text(encoding="utf-8")`. Require a top-level list of length one, a mapping row, and a `retention_exact_coverage` value. Accept that field as either a mapping or a JSON string.
2. `validate_envelope()` requires `audit_version == 1`, `complete is True`, `retention_execution_closed is True`, `deletion_approved is False`, non-empty `query_scope.providers`, list-valued `coverage`, `source_anomalies`, and `provider_runtime`, and only the four allowed providers. Require unique anomaly/runtime entries for every provider listed in query scope, reject provider/date duplicates in coverage, and require every Shared Data Contracts field with the correct scalar/list type; booleans must be actual booleans, not truthy strings.
3. Parse all dates with `date.fromisoformat()` and timestamps with `datetime.fromisoformat(value.replace("Z", "+00:00"))`. Require timezone-aware timestamps, reject reversed query dates and `raw_retention_days <= 0`, and require `query_scope.end_date == as_of`; otherwise raise `ValueError("query scope is stale for requested as-of date")`.
4. Index season evidence by `slate_date` and pins by `(slate_date, provider)`. Duplicate keys are a validation error.
5. For each coverage row, calculate `age_days = (date.fromisoformat(as_of) - slate_date).days` and collect all blocker reason codes; do not stop at the first blocker.
6. If `age_days < raw_retention_days`, set `decision="not_in_policy_window"`. Keep blocker details under `deferred_reason_codes`, but do not describe the partition as ready.
7. Otherwise use decision precedence: any coverage/source anomaly -> `blocked_compaction`; missing Gate C or required season evidence -> `blocked_outcome_evidence`; missing/unreconciled/unpreserved pin evidence -> `blocked_pinned_evidence`; no blockers -> `ready_for_retention_review`.
8. A decision-linked date with `official_tracked_picks > 0` must appear in `gate_c.loaded_slate_dates`, have zero Gate C unmatched/result-missing counts, and have all five `required_evidence` values true. A date explicitly marked `decision_linked=false` may omit those five booleans, but still needs a season-evidence date record.
9. Missing season or pin manifests never mean an empty satisfied set. A pin is preserved only when `status == "preserved"` and `preserved_artifact` is a non-empty repository-relative path; `reconciled=true` with an unpreserved pin remains blocked.
10. Return a report with `report_type`, `generated_at`, `as_of`, `raw_retention_days`, the Gate C hashes/date coverage, `retention_execution_closed=true`, `deletion_approved=false`, `production_authority="none"`, `summary.decision_counts`, sorted `partitions`, and `provider_summaries`. Each provider summary aggregates only partitions inside the policy window and includes raw rows/bytes/groups, exact groups, missing groups, mismatched groups, and decision counts.

- [ ] **Step 4: Run the decision tests and verify they pass**

Run:

```powershell
python -m pytest tests/test_build_season_retention_readiness.py -v
git diff --check
```

Expected: all Task 1–2 tests PASS; no whitespace errors.

- [ ] **Step 5: Commit the validator and decision engine**

```powershell
git add scripts/build_season_retention_readiness.py tests/test_build_season_retention_readiness.py
git commit -m "feat: evaluate retention readiness evidence"
```

### Task 3: Safe Report Rendering and Readiness CLI

**Files:**
- Modify: `scripts/build_season_retention_readiness.py`
- Modify: `tests/test_build_season_retention_readiness.py`

**Interfaces:**
- Consumes: a validated readiness report from Task 2.
- Produces: `season_retention_readiness.json`, `season_retention_readiness.md`, and CLI exit codes `0`, `2`, or `3`.

- [ ] **Step 1: Write failing rendering, redaction, and CLI tests**

Append:

```python
def test_rendered_readiness_reports_are_closed_and_contain_no_secret_fields(tmp_path):
    envelope = _envelope()
    envelope["authorization"] = "Bearer secret"
    envelope["provider_runtime"][0]["api_key"] = "secret-value"
    report = retention.build_readiness_report(
        envelope=envelope, gate_c=_gate_c_manifest(),
        season_evidence=_season_evidence(), pins=_pins(),
        as_of="2026-08-18", raw_retention_days=30,
    )
    paths = retention.write_report_pair(
        report=report, output_dir=tmp_path, stem="season_retention_readiness"
    )
    combined = paths["json"].read_text(encoding="utf-8") + paths["markdown"].read_text(encoding="utf-8")
    lowered = combined.lower()
    assert "deletion status: closed" in lowered
    assert "retention_execution_closed" in combined
    for forbidden in ("bearer secret", "secret-value", "api_key", "authorization",
                      "delete from", "truncate table", "vacuum full"):
        assert forbidden not in lowered


def test_readiness_main_returns_two_for_blocked_report_and_writes_outputs(tmp_path):
    query = tmp_path / "query.json"
    gate_c = tmp_path / "gate-c.json"
    query.write_text(json.dumps([{"retention_exact_coverage": _envelope(
        coverage=[_coverage(missing_compact_group_count=1, coverage_exact=False)]
    )}]), encoding="utf-8")
    gate_c.write_text(json.dumps(_gate_c_manifest()), encoding="utf-8")
    exit_code = retention.main([
        "readiness", "--query-json", str(query), "--gate-c-manifest", str(gate_c),
        "--as-of", "2026-08-18", "--output-dir", str(tmp_path),
    ])
    assert exit_code == 2
    assert (tmp_path / "season_retention_readiness.json").exists()
    assert (tmp_path / "season_retention_readiness.md").exists()


def test_readiness_main_returns_zero_only_for_nonblocked_decisions(tmp_path):
    query = tmp_path / "query.json"
    gate_c = tmp_path / "gate-c.json"
    season = tmp_path / "season.json"
    pins = tmp_path / "pins.json"
    query.write_text(json.dumps([{"retention_exact_coverage": _envelope()}]), encoding="utf-8")
    gate_c.write_text(json.dumps(_gate_c_manifest()), encoding="utf-8")
    season.write_text(json.dumps(_season_evidence()), encoding="utf-8")
    pins.write_text(json.dumps(_pins()), encoding="utf-8")
    exit_code = retention.main([
        "readiness", "--query-json", str(query), "--gate-c-manifest", str(gate_c),
        "--season-evidence", str(season), "--pins", str(pins),
        "--as-of", "2026-08-18", "--output-dir", str(tmp_path),
    ])
    assert exit_code == 0


def test_main_returns_three_and_writes_no_report_for_invalid_input(tmp_path):
    query = tmp_path / "query.json"
    query.write_text("[]", encoding="utf-8")
    assert retention.main([
        "readiness", "--query-json", str(query),
        "--gate-c-manifest", str(tmp_path / "missing.json"),
        "--as-of", "2026-08-18", "--output-dir", str(tmp_path),
    ]) == 3
    assert not (tmp_path / "season_retention_readiness.json").exists()
```

- [ ] **Step 2: Run the rendering/CLI tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_build_season_retention_readiness.py -v
```

Expected: FAIL because rendering and CLI functions do not exist.

- [ ] **Step 3: Implement recursive redaction, Markdown rendering, file output, and readiness CLI**

Add these interfaces:

```python
SECRET_KEY = re.compile(
    r"(?:authorization|password|secret|token|api[_-]?key|service[_-]?role)", re.IGNORECASE
)


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: redact_sensitive(child)
            for key, child in value.items()
            if not SECRET_KEY.search(str(key))
        }
    if isinstance(value, list):
        return [redact_sensitive(child) for child in value]
    return value


def render_readiness_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]["decision_counts"]
    lines = [
        "# Season Retention Readiness",
        "",
        "**Deletion status: CLOSED**",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- As of: `{report['as_of']}`",
        f"- Raw retention candidate window: `{report['raw_retention_days']} days`",
        f"- Decision counts: `{json.dumps(summary, sort_keys=True)}`",
        "",
        "| Slate | Provider | Raw rows | Raw MB | Exact / Raw groups | Missing | Mismatched | Decision | Reasons |",
        "|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in report["partitions"]:
        lines.append(
            "| {slate_date} | {provider} | {raw_snapshot_rows} | {raw_mb:.2f} | "
            "{exact_group_count} / {raw_group_count} | {missing_compact_group_count} | "
            "{mismatched_group_count} | {decision} | {reasons} |".format(
                **row,
                raw_mb=row["raw_logical_bytes"] / 1024 / 1024,
                reasons=", ".join(row.get("reason_codes", ())) or "none",
            )
        )
    lines.extend([
        "",
        "`ready_for_retention_review` is evidence status only and does not authorize deletion.",
    ])
    return "\n".join(lines)


def write_report_pair(
    *, report: dict[str, Any], output_dir: Path, stem: str,
    renderer: Callable[[dict[str, Any]], str] = render_readiness_markdown,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    clean = redact_sensitive(report)
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(
        json.dumps(clean, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(renderer(clean).rstrip() + "\n", encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}
```

Implementation rules:

- `render_readiness_markdown()` starts with `# Season Retention Readiness` and `**Deletion status: CLOSED**`, then shows audit time, source date range, Gate C date range/hashes, summary decision counts, and a compact provider/date table with raw rows, logical MB, exact/missing/mismatch counts, decision, and reason codes.
- `render_readiness_markdown(report)` receives the already redacted report. `write_report_pair()` creates only the requested output directory, redacts before either renderer runs, serializes JSON with `indent=2`, `sort_keys=True`, and a trailing newline, and writes UTF-8. The BoltOdds branch passes `renderer=render_boltodds_markdown`; readiness uses the default.
- `parse_args()` creates subcommands `readiness` and `boltodds-closure`. Both accept `--query-json`, `--gate-c-manifest`, optional `--season-evidence`, optional `--pins`, required `--as-of`, and `--output-dir`. `readiness` additionally accepts `--raw-retention-days` with default `30`.
- `main()` catches `OSError`, `json.JSONDecodeError`, `TypeError`, and `ValueError`, prints `retention_audit_error: {exc}` to stderr, and returns `3` without writing reports.
- For `readiness`, return `2` if any partition decision starts with `blocked_`; otherwise return `0`. `not_in_policy_window` is non-executable and may return `0` because the report still keeps deletion closed.
- Print only output paths and summary counts. Never print the query envelope, raw payloads, manifest contents, or secrets.

- [ ] **Step 4: Run the targeted tests and verify they pass**

```powershell
python -m pytest tests/test_build_season_retention_readiness.py -v
git diff --check
```

Expected: all Task 1–3 tests PASS.

- [ ] **Step 5: Commit the readiness CLI**

```powershell
git add scripts/build_season_retention_readiness.py tests/test_build_season_retention_readiness.py
git commit -m "feat: render closed retention readiness reports"
```

### Task 4: BoltOdds Retirement Closure Package

**Files:**
- Modify: `scripts/build_season_retention_readiness.py`
- Modify: `tests/test_build_season_retention_readiness.py`

**Interfaces:**
- Consumes: the validated envelope, optional season/pin evidence, Gate C manifest, and the fixed documented suspension boundary `2026-06-17T17:22:29Z`.
- Produces: `build_boltodds_closure` with keyword-only `envelope`, `gate_c`, `season_evidence`, `pins`, and `as_of` arguments; `boltodds_retirement_closure.json`; `boltodds_retirement_closure.md`; and exit code `0`, `2`, or `3`.

- [ ] **Step 1: Write failing BoltOdds closure tests**

Append:

```python
def test_boltodds_closure_preserves_trial_facts_without_runtime_authority():
    closure = retention.build_boltodds_closure(
        envelope=_envelope(), gate_c=_gate_c_manifest(),
        season_evidence=_season_evidence(), pins=_pins(), as_of="2026-08-18",
    )
    assert closure["provider"] == "boltodds"
    assert closure["documented_suspension_at"] == "2026-06-17T17:22:29+00:00"
    assert closure["runtime"]["last_snapshot_at"] == "2026-06-16T13:37:44+00:00"
    assert closure["runtime"]["books_seen"] == ["betmgm", "fanduel"]
    assert closure["production_authority"] == "none"
    assert closure["runtime_reactivation_approved"] is False
    assert closure["retention_execution_closed"] is True
    assert closure["deletion_approved"] is False


def test_boltodds_closure_blocks_on_compaction_gaps_and_missing_preservation_inputs():
    envelope = _envelope(coverage=[_coverage(
        missing_compact_group_count=1, coverage_exact=False
    )])
    closure = retention.build_boltodds_closure(
        envelope=envelope, gate_c=_gate_c_manifest(),
        season_evidence=None, pins=None, as_of="2026-08-18",
    )
    assert closure["status"] == "incomplete_evidence"
    assert "compaction_not_exact" in closure["unresolved_evidence_gaps"]
    assert "season_evidence_manifest_missing" in closure["unresolved_evidence_gaps"]
    assert "pin_manifest_missing" in closure["unresolved_evidence_gaps"]
    assert closure["recommendation"] == "complete_evidence_before_retention_review"


@pytest.mark.parametrize("runtime_field", ["last_snapshot_at", "last_heartbeat_at"])
def test_boltodds_closure_flags_any_post_suspension_runtime(runtime_field):
    runtime = _runtime(**{runtime_field: "2026-06-17T17:22:30+00:00"})
    closure = retention.build_boltodds_closure(
        envelope=_envelope(runtime=[runtime]), gate_c=_gate_c_manifest(),
        season_evidence=_season_evidence(), pins=_pins(), as_of="2026-08-18",
    )
    assert closure["status"] == "operational_exception"
    assert "post_suspension_runtime_evidence" in closure["unresolved_evidence_gaps"]


def test_boltodds_closure_cli_writes_sanitized_json_and_markdown(tmp_path):
    query = tmp_path / "query.json"
    gate_c = tmp_path / "gate-c.json"
    query.write_text(json.dumps([{"retention_exact_coverage": _envelope()}]), encoding="utf-8")
    gate_c.write_text(json.dumps(_gate_c_manifest()), encoding="utf-8")
    exit_code = retention.main([
        "boltodds-closure", "--query-json", str(query),
        "--gate-c-manifest", str(gate_c), "--as-of", "2026-08-18",
        "--output-dir", str(tmp_path),
    ])
    assert exit_code == 2
    json_path = tmp_path / "boltodds_retirement_closure.json"
    md_path = tmp_path / "boltodds_retirement_closure.md"
    assert json_path.exists() and md_path.exists()
    combined = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")
    assert "Deletion status: CLOSED" in combined
    assert "does not authorize BoltOdds runtime reactivation" in combined
```

- [ ] **Step 2: Run the BoltOdds tests and verify they fail**

```powershell
python -m pytest tests/test_build_season_retention_readiness.py -v
```

Expected: FAIL because the closure builder and closure renderer do not exist.

- [ ] **Step 3: Implement the closure builder and CLI branch**

Build the closure with these rules and use this exact status/recommendation selection after collecting `unresolved_evidence_gaps` and `post_suspension_runtime`:

```python
if post_suspension_runtime:
    status = "operational_exception"
    recommendation = "investigate_accidental_reactivation"
elif unresolved_evidence_gaps:
    status = "incomplete_evidence"
    recommendation = "complete_evidence_before_retention_review"
else:
    status = "ready_for_retirement_review"
    recommendation = "schedule_separate_retention_review"


def render_boltodds_markdown(report: dict[str, Any]) -> str:
    runtime = report["runtime"]
    totals = report["coverage_totals"]
    lines = [
        "# BoltOdds Retirement Closure",
        "",
        "**Deletion status: CLOSED**",
        "",
        "This package does not authorize BoltOdds runtime reactivation.",
        "",
        f"- Status: `{report['status']}`",
        f"- Documented suspension: `{report['documented_suspension_at']}`",
        f"- Last heartbeat: `{runtime.get('last_heartbeat_at')}`",
        f"- Last snapshot: `{runtime.get('last_snapshot_at')}`",
        f"- Books observed: `{', '.join(runtime.get('books_seen', [])) or 'none'}`",
        f"- Raw rows / logical bytes: `{totals['raw_snapshot_rows']} / {totals['raw_logical_bytes']}`",
        f"- Exact / raw groups: `{totals['exact_group_count']} / {totals['raw_group_count']}`",
        f"- Missing / mismatched groups: `{totals['missing_compact_group_count']} / {totals['mismatched_group_count']}`",
        f"- Unresolved gaps: `{', '.join(report['unresolved_evidence_gaps']) or 'none'}`",
        f"- Recommendation: `{report['recommendation']}`",
        "",
        "BoltOdds remains historical research evidence only and has no production authority.",
    ]
    return "\n".join(lines)
```

- Select exactly one `provider_runtime` row for `boltodds`; zero or duplicates are validation errors.
- Aggregate all BoltOdds coverage rows into total raw rows/bytes/groups, exact groups, missing groups, unexpected groups, duplicate groups, and each mismatch total. Preserve a sorted `partitions` array.
- Record `documented_suspension_at=BOLTODDS_SUSPENDED_AT.isoformat()` and compare both last snapshot and last heartbeat to that boundary.
- Use `status="operational_exception"` for any post-suspension runtime evidence; otherwise use `incomplete_evidence` when exact coverage, season evidence, Gate C, or pins are incomplete; otherwise use `ready_for_retirement_review`.
- A ready closure is still non-executable. Always set `retention_execution_closed=true`, `deletion_approved=false`, `production_authority="none"`, and `runtime_reactivation_approved=false`.
- Set `recommendation="complete_evidence_before_retention_review"` for incomplete evidence, `recommendation="investigate_accidental_reactivation"` for an operational exception, and `recommendation="schedule_separate_retention_review"` only when the package is complete.
- Include `historical_lessons` stating that BoltOdds evidence is research-only and cannot drive provider order, official artifacts, picks, models, notifications, locks, UI, or retention execution.
- Include no provider metadata blobs, source payloads, error messages, credentials, or individual market rows.
- `render_boltodds_markdown()` starts with `# BoltOdds Retirement Closure`, `**Deletion status: CLOSED**`, and the exact sentence `This package does not authorize BoltOdds runtime reactivation.`
- The CLI writes the `boltodds_retirement_closure` report pair and returns `2` unless `status == "ready_for_retirement_review"`; invalid input returns `3`.

- [ ] **Step 4: Run all Phase 1 tests and verify they pass**

```powershell
python -m pytest tests/test_build_season_retention_readiness.py -v
git diff --check
```

Expected: all Phase 1 tests PASS; no diff errors.

- [ ] **Step 5: Commit the BoltOdds closure package**

```powershell
git add scripts/build_season_retention_readiness.py tests/test_build_season_retention_readiness.py
git commit -m "feat: generate BoltOdds retirement closure evidence"
```

### Task 5: Read-Only Live Verification and Full Regression

**Files:**
- Verify only: `scripts/supabase_retention_exact_coverage.sql`
- Verify only: `scripts/build_season_retention_readiness.py`
- Verify only: `tests/test_build_season_retention_readiness.py`
- Generate ignored local output: `analytics/output/retention/*`

**Interfaces:**
- Consumes: one linked Supabase SELECT result reused in memory for both report modes.
- Produces: verified local readiness and BoltOdds closure reports; no database or production mutation.

- [ ] **Step 1: Prove the exact SQL is non-mutating and the old execution path is untouched**

Run:

```powershell
rg -n "\b(insert|update|delete|truncate|drop|alter|create|grant|revoke|vacuum)\b" scripts/supabase_retention_exact_coverage.sql
git diff 9c0d3cdc -- scripts/retire_market_snapshots.py scripts/supabase_retention_readiness.sql
```

Expected: the first command finds only explanatory comments, not SQL statements; the second command prints nothing.

- [ ] **Step 2: Run the exact linked query once and reuse its stdout for both reports**

From the repository root in PowerShell:

```powershell
$retentionAuditJson = npx supabase db query --linked --file scripts\supabase_retention_exact_coverage.sql -o json
$retentionAuditJson | python scripts/build_season_retention_readiness.py readiness --query-json - --gate-c-manifest data/research/gate_c/pitcher_k_outcome_dataset_manifest.json --as-of 2026-08-18 --raw-retention-days 30 --output-dir analytics/output/retention
$readinessExit = $LASTEXITCODE
$retentionAuditJson | python scripts/build_season_retention_readiness.py boltodds-closure --query-json - --gate-c-manifest data/research/gate_c/pitcher_k_outcome_dataset_manifest.json --as-of 2026-08-18 --output-dir analytics/output/retention
$closureExit = $LASTEXITCODE
Write-Output "readiness_exit=$readinessExit closure_exit=$closureExit"
```

Expected: the database is queried once. Both reports are generated. Exit `2` is expected while exact compaction gaps and explicit season/pin inputs remain unresolved; exit `3` is a failure.

If the pooler returns `ECIRCUITBREAKER`, authentication retries, or a timeout, do not immediately rerun. Record the exact error, wait for a later operator window, and keep the report status blocked.

- [ ] **Step 3: Verify the live report reproduces the known 2026-08-18 blockers**

Run:

```powershell
Get-Content -Raw analytics/output/retention/season_retention_readiness.json
Get-Content -Raw analytics/output/retention/boltodds_retirement_closure.json
```

Verify these provider-level sums in the generated evidence:

- BoltOdds: 26,188 raw groups, 23,900 exact groups, 345 missing groups, 1,943 mismatched groups.
- PropLine older than 30 days: 16,842 raw groups, 5,321 exact groups, 304 missing groups, 11,217 mismatched groups.
- TheRundown older than 30 days: 16,909 raw groups, 1,654 exact groups, 7,425 missing groups, 7,830 mismatched groups.
- BoltOdds last heartbeat is at or before `2026-06-17T17:22:29Z`, last snapshot is at or before the same boundary, and no operational-exception status appears.
- Both reports state deletion is closed and contain no executable deletion statement.

If the exact query yields different totals, treat the fresh query as authoritative, explain the date-range or data-growth difference, and do not edit results to match the older audit.

- [ ] **Step 4: Run targeted and full regression tests**

```powershell
python -m pytest tests/test_build_season_retention_readiness.py tests/test_supabase_retention_readiness_sql.py tests/test_retire_market_snapshots.py tests/test_backfill_compact_market_movements_via_cli.py -v
python -m pytest tests/ -q
```

Expected: both commands PASS. Any unrelated pre-existing full-suite failure must be documented with the exact test and reproduced against commit `9c0d3cdc` before it is classified as pre-existing.

- [ ] **Step 5: Verify repository scope and commit only if a verification fix was required**

```powershell
git status --short
git diff --check
git log --oneline 9c0d3cdc..HEAD
```

Expected: only the three planned source/test files and this implementation plan are tracked changes across the branch; `analytics/output/retention/` does not appear because it is ignored. If verification required a source/test correction, commit only that correction:

```powershell
git add scripts/supabase_retention_exact_coverage.sql scripts/build_season_retention_readiness.py tests/test_build_season_retention_readiness.py
git commit -m "fix: close retention audit verification gaps"
```

Do not merge, push, deploy, backfill, delete, vacuum, or change retention settings. Hand off the local evidence and branch for review, with Phase 2 and Phase 3 still closed.
