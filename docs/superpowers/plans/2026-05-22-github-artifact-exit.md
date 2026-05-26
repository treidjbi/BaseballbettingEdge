# GitHub Artifact Exit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move BaseballBettingEdge's user-facing artifact publishing and time-sensitive orchestration off GitHub Actions while keeping GitHub as code repository, manual rollback, and audit backup.

**Architecture:** Supabase becomes the durable artifact store for dashboard JSON payloads, Netlify functions serve those artifacts to the static app, and Render runs the scheduled pipeline modes after parity is proven. GitHub Actions remains enabled as manual rollback until Supabase-served artifacts and Render schedules complete clean canaries.

**Tech Stack:** Python 3.11, pytest, Supabase Postgres/REST, Render cron/background services, Netlify functions, vanilla dashboard JavaScript, existing GitHub Actions pipeline as rollback.

---

Date: 2026-05-22
Owner: Tyler + Codex
Status: Future implementation plan

## Operating Decision

This plan starts after the Supabase lock ledger is stable:

1. Finish the current non-strict lock canary.
2. Enable `SUPABASE_LOCK_CONSUMER_STRICT=true` only after a clean slate.
3. Prove one strict lock canary.
4. Then begin this artifact-exit plan.

This is not a provider cutover and not a model change. TheRundown remains the
production odds source until the provider cutover plan passes its own gates.

## Non-Goals

- Do not change model math, EV thresholds, staking, calibration, or
  `formula_change_date`.
- Do not enable `OFFICIAL_MARKET_SOURCE=boltodds_propline`.
- Do not enable `ENABLE_BOLTODDS_PIPELINE_SOURCE`.
- Do not make the dashboard read raw `market_snapshots`.
- Do not delete GitHub artifact publishing until Supabase artifact parity,
  dashboard API canary, and Render schedule canary are all clean.
- Do not remove `data/picks_history.json` from the repo until a separate
  history-retention/backup decision says the Supabase copy is the durable
  source.

## Current Gap

The 2026-05-19 Supabase operational foundation plan moves lock timing away from
GitHub's schedule by letting Render write lock rows and dispatch lock-only
workflow runs. That solves the clock problem, but GitHub still publishes the
user-facing JSON artifacts by committing files.

This plan covers the missing next phase: making Supabase/Netlify the artifact
data plane and moving scheduled pipeline execution to Render.

## Target End State

GitHub should do these jobs:

- store code
- receive small, intentional commits
- provide manual rollback workflows
- keep archived JSON as optional backup while useful

GitHub should stop doing these jobs:

- act as the active slate clock
- decide whether lock windows publish on time
- be required for the dashboard to receive fresh `today.json`
- be required for live notification state to know the latest locked artifact

Supabase should do these jobs:

- store current and dated published artifact payloads
- store artifact publication lineage, hashes, and source run metadata
- expose artifact freshness and parity evidence to operations

Render should do these jobs:

- run preview, grading, full, refresh, and lock schedules after canary
- publish pipeline outputs into Supabase artifact tables
- keep GitHub manual rollback available during the transition

Netlify should do these jobs:

- serve dashboard artifacts from Supabase through server-side functions
- hide Supabase service credentials from the browser
- keep static GitHub/raw JSON as fallback during canary

## Source-Of-Truth Stages

| Stage | Dashboard reads | Pipeline runs | Lock source | Rollback |
| --- | --- | --- | --- | --- |
| 0 current | GitHub committed JSON | GitHub Actions | GitHub plus Supabase canary | Manual GitHub runs |
| 1 shadow mirror | GitHub committed JSON | GitHub Actions | Strict Supabase consumer | Supabase mirror ignored by app |
| 2 dashboard canary | Netlify artifact API, static JSON fallback | GitHub Actions | Strict Supabase consumer | Switch app config back to static |
| 3 Render scheduler canary | Netlify artifact API | Render primary, GitHub manual fallback | Supabase/Render | Manual GitHub workflow |
| 4 steady state | Netlify artifact API | Render | Supabase/Render | GitHub manual only |

Promotion rule: do not advance more than one stage in a single slate.

## Post-Cutover Cadence Model

Render primary scheduler does not mean every pipeline responsibility runs every
10 minutes. The target architecture has separate loops:

| Loop | Cadence target | Writes | Must not do |
| --- | --- | --- | --- |
| Live market/control loop (`bbe-live-layer`) | Every 10 minutes by default | Supabase live market state, operational locks, notification candidates/events, compact evidence | Publish dashboard artifacts, grade results, calibrate, change model outputs |
| Provider feed loop | BoltOdds WebSocket continuously; PropLine polling/webhooks through the live layer | Raw/derived provider evidence, `current_market_lines`, `official_market_lines` | Drive production picks before provider cutover gates pass |
| Artifact pipeline loop | Preview, grading, full, refresh, and lock modes on Render after Task 11; start from existing production cadence | Supabase-published artifacts and optional GitHub backup artifacts | Treat every mode as eligible for 10-minute execution |
| Notification/product loop | Netlify sender cadence plus event freshness TTL | Push delivery status and audit rows | Send stale, duplicate, or unapproved provider-movement alerts |

Steady-state artifact refresh can be tightened later, but only as a separate
cadence decision after:

- Render full/refresh/lock runtime is consistently below the action window;
- Supabase artifact publication and parity remain clean at the higher cadence;
- provider-mode dry runs read `official_market_lines` instead of raw snapshots;
- cost/row-volume guardrails remain acceptable;
- the higher cadence changes a real betting or notification decision.

Do not run grading/calibration or other end-of-slate paths every 10 minutes.
Lock-only runs should stay event/window driven, and live market movement should
flow through the live market/control loop rather than forcing a full artifact
publish on every provider tick.

## File Map

- Create `supabase/migrations/20260522_published_pipeline_artifacts.sql`
  - Supabase artifact table and publication-run table.
- Create `market_infra/published_artifacts.py`
  - Pure helpers for artifact keys, canonical hashes, row building, and parity
    comparison.
- Create `scripts/publish_pipeline_artifacts_to_supabase.py`
  - Dry-run-first publisher for existing local JSON artifacts.
- Create `scripts/compare_supabase_artifacts.py`
  - Read-only parity checker between Supabase payloads and local/GitHub raw
    artifacts.
- Create `netlify/functions/get-artifact.mjs`
  - Server-side artifact read endpoint for the dashboard.
- Modify `dashboard/v2-data.js`
  - Add an artifact-source adapter that can read from Netlify first and fall
    back to static JSON.
- Modify `dashboard/index.html`
  - Add the same source adapter for the legacy dashboard until it is fully
    retired.
- Modify `scripts/build_live_events_to_supabase.py`
  - Later phase only: optionally publish lock-updated artifacts to Supabase
    after strict canary.
- Modify `.github/workflows/pipeline.yml`
  - Shadow phase: publish artifacts to Supabase after successful runs.
  - Steady-state phase: disable scheduled triggers after Render is promoted.
- Create `render/pipeline-runner.md`
  - Render service setup notes and schedules.
- Modify `docs/current-state.md`
  - Track this as the post-lock artifact-exit plan.
- Modify `docs/operational-risk-register.md`
  - Add artifact API, Render pipeline runner, and stale Supabase artifact
    failure modes.

## Task 1: Add Published Artifact Schema

**Files:**
- Create: `supabase/migrations/20260522_published_pipeline_artifacts.sql`
- Create: `tests/test_published_artifacts_schema.py`

- [x] **Step 1: Write schema contract tests**

Create `tests/test_published_artifacts_schema.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260522_published_pipeline_artifacts.sql"


def test_published_pipeline_artifacts_schema_has_required_contract():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "create table if not exists public.published_pipeline_artifacts" in sql
    assert "artifact_key text not null unique" in sql
    assert "artifact_type text not null" in sql
    assert "payload jsonb not null" in sql
    assert "payload_sha256 text not null" in sql
    assert "generated_at timestamptz" in sql
    assert "published_at timestamptz not null default now()" in sql
    assert "source text not null" in sql
    assert "source_run_id text" in sql
    assert "source_commit_sha text" in sql
    assert "metadata jsonb not null default '{}'::jsonb" in sql


def test_published_pipeline_artifact_runs_schema_has_required_contract():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "create table if not exists public.pipeline_artifact_publication_runs" in sql
    assert "run_id text not null unique" in sql
    assert "source text not null" in sql
    assert "run_type text not null" in sql
    assert "slate_date date" in sql
    assert "status text not null" in sql
    assert "artifact_count integer not null default 0" in sql


def test_published_artifact_tables_are_rls_guarded():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "alter table public.published_pipeline_artifacts enable row level security" in sql
    assert "alter table public.pipeline_artifact_publication_runs enable row level security" in sql
    assert "grant select on public.published_pipeline_artifacts to bbe_ops_readonly" in sql
    assert "grant select on public.pipeline_artifact_publication_runs to bbe_ops_readonly" in sql
```

- [x] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_published_artifacts_schema.py -q
```

Expected: fail because the migration file does not exist.

- [x] **Step 3: Add migration**

Create `supabase/migrations/20260522_published_pipeline_artifacts.sql`:

```sql
create table if not exists public.published_pipeline_artifacts (
  id uuid primary key default gen_random_uuid(),
  artifact_key text not null unique,
  artifact_type text not null check (
    artifact_type in (
      'today',
      'dated_slate',
      'index',
      'steam',
      'performance',
      'params',
      'preview_lines',
      'picks_history'
    )
  ),
  slate_date date,
  payload jsonb not null,
  payload_sha256 text not null,
  generated_at timestamptz,
  source text not null check (
    source in ('github_actions', 'render_pipeline', 'render_live_layer', 'manual_backfill')
  ),
  source_run_id text,
  source_commit_sha text,
  published_at timestamptz not null default now(),
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_published_pipeline_artifacts_type_date
  on public.published_pipeline_artifacts (artifact_type, slate_date desc);

create index if not exists idx_published_pipeline_artifacts_published_at
  on public.published_pipeline_artifacts (published_at desc);

create table if not exists public.pipeline_artifact_publication_runs (
  id uuid primary key default gen_random_uuid(),
  run_id text not null unique,
  source text not null check (
    source in ('github_actions', 'render_pipeline', 'render_live_layer', 'manual_backfill')
  ),
  run_type text not null check (
    run_type in ('preview', 'grading', 'full', 'refresh', 'lock', 'manual_backfill')
  ),
  slate_date date,
  status text not null check (status in ('started', 'completed', 'failed')),
  artifact_count integer not null default 0,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  metadata jsonb not null default '{}'::jsonb
);

alter table public.published_pipeline_artifacts enable row level security;
alter table public.pipeline_artifact_publication_runs enable row level security;

comment on table public.published_pipeline_artifacts is
  'Canonical published dashboard JSON payloads during the GitHub artifact-exit migration.';

comment on table public.pipeline_artifact_publication_runs is
  'Publication run ledger for GitHub/Render artifact publishers.';

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'bbe_ops_readonly') then
    execute 'grant select on public.published_pipeline_artifacts to bbe_ops_readonly';
    execute 'grant select on public.pipeline_artifact_publication_runs to bbe_ops_readonly';

    execute 'drop policy if exists bbe_ops_readonly_select_published_pipeline_artifacts on public.published_pipeline_artifacts';
    execute 'create policy bbe_ops_readonly_select_published_pipeline_artifacts on public.published_pipeline_artifacts for select to bbe_ops_readonly using (true)';

    execute 'drop policy if exists bbe_ops_readonly_select_pipeline_artifact_publication_runs on public.pipeline_artifact_publication_runs';
    execute 'create policy bbe_ops_readonly_select_pipeline_artifact_publication_runs on public.pipeline_artifact_publication_runs for select to bbe_ops_readonly using (true)';
  end if;
end $$;
```

- [x] **Step 4: Verify schema tests pass**

Run:

```powershell
python -m pytest tests/test_published_artifacts_schema.py -q
```

Expected: pass.

- [x] **Step 5: Commit**

```powershell
git add supabase/migrations/20260522_published_pipeline_artifacts.sql tests/test_published_artifacts_schema.py
git commit -m "feat: add published artifact schema"
```

## Task 2: Add Artifact Row Builder

**Files:**
- Create: `market_infra/published_artifacts.py`
- Create: `tests/test_published_artifacts.py`

- [x] **Step 1: Write pure helper tests**

Create `tests/test_published_artifacts.py`:

```python
from pathlib import Path

from market_infra.published_artifacts import (
    artifact_key,
    artifact_type_from_path,
    build_artifact_row,
    canonical_payload_sha256,
)


def test_artifact_type_from_path_maps_known_outputs():
    assert artifact_type_from_path(Path("dashboard/data/processed/today.json")) == "today"
    assert artifact_type_from_path(Path("dashboard/data/processed/2026-05-22.json")) == "dated_slate"
    assert artifact_type_from_path(Path("dashboard/data/processed/index.json")) == "index"
    assert artifact_type_from_path(Path("dashboard/data/processed/steam.json")) == "steam"
    assert artifact_type_from_path(Path("dashboard/data/performance.json")) == "performance"
    assert artifact_type_from_path(Path("data/params.json")) == "params"
    assert artifact_type_from_path(Path("data/preview_lines.json")) == "preview_lines"
    assert artifact_type_from_path(Path("data/picks_history.json")) == "picks_history"


def test_artifact_key_is_stable():
    assert artifact_key("today", None) == "today"
    assert artifact_key("dated_slate", "2026-05-22") == "dated_slate:2026-05-22"


def test_canonical_payload_sha256_ignores_json_key_order():
    left = {"b": 2, "a": 1}
    right = {"a": 1, "b": 2}
    assert canonical_payload_sha256(left) == canonical_payload_sha256(right)


def test_build_artifact_row_extracts_date_and_generated_at(tmp_path):
    path = tmp_path / "dashboard" / "data" / "processed" / "2026-05-22.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"date":"2026-05-22","generated_at":"2026-05-22T15:41:07Z","pitchers":[]}',
        encoding="utf-8",
    )

    row = build_artifact_row(
        root=tmp_path,
        path=path,
        source="github_actions",
        source_run_id="26297280674",
        source_commit_sha="9cd8a02b",
    )

    assert row["artifact_key"] == "dated_slate:2026-05-22"
    assert row["artifact_type"] == "dated_slate"
    assert row["slate_date"] == "2026-05-22"
    assert row["generated_at"] == "2026-05-22T15:41:07Z"
    assert row["source"] == "github_actions"
    assert row["source_run_id"] == "26297280674"
    assert row["source_commit_sha"] == "9cd8a02b"
    assert row["metadata"]["artifact_path"].endswith("dashboard/data/processed/2026-05-22.json")
```

- [x] **Step 2: Run tests to verify failure**

```powershell
python -m pytest tests/test_published_artifacts.py -q
```

Expected: fail because `market_infra.published_artifacts` does not exist.

- [x] **Step 3: Implement pure helpers**

Create `market_infra/published_artifacts.py` with:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ARTIFACT_PATHS = [
    Path("dashboard/data/processed/today.json"),
    Path("dashboard/data/processed/index.json"),
    Path("dashboard/data/processed/steam.json"),
    Path("dashboard/data/performance.json"),
    Path("data/params.json"),
    Path("data/preview_lines.json"),
    Path("data/picks_history.json"),
]


def artifact_type_from_path(path: Path) -> str:
    text = path.as_posix()
    name = path.name
    if text.endswith("dashboard/data/processed/today.json"):
        return "today"
    if text.endswith("dashboard/data/processed/index.json"):
        return "index"
    if text.endswith("dashboard/data/processed/steam.json"):
        return "steam"
    if text.endswith("dashboard/data/performance.json"):
        return "performance"
    if text.endswith("data/params.json"):
        return "params"
    if text.endswith("data/preview_lines.json"):
        return "preview_lines"
    if text.endswith("data/picks_history.json"):
        return "picks_history"
    if text.startswith("dashboard/data/processed/") and name.endswith(".json"):
        return "dated_slate"
    raise ValueError(f"Unsupported artifact path: {path}")


def artifact_key(artifact_type: str, slate_date: str | None) -> str:
    if artifact_type == "dated_slate":
        if not slate_date:
            raise ValueError("dated_slate artifacts require slate_date")
        return f"dated_slate:{slate_date}"
    return artifact_type


def canonical_payload_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _slate_date_from_path_or_payload(path: Path, payload: dict[str, Any]) -> str | None:
    if artifact_type_from_path(path) == "dated_slate":
        return path.stem
    value = payload.get("date")
    return str(value) if value else None


def _generated_at(payload: dict[str, Any]) -> str | None:
    value = payload.get("generated_at") or payload.get("fetched_at") or payload.get("updated_at")
    return str(value) if value else None


def build_artifact_row(
    *,
    root: Path,
    path: Path,
    source: str,
    source_run_id: str | None = None,
    source_commit_sha: str | None = None,
) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    artifact_type = artifact_type_from_path(path.relative_to(root) if path.is_absolute() else path)
    slate_date = _slate_date_from_path_or_payload(path.relative_to(root) if path.is_absolute() else path, payload)
    relative_path = path.relative_to(root).as_posix() if path.is_absolute() else path.as_posix()
    return {
        "artifact_key": artifact_key(artifact_type, slate_date),
        "artifact_type": artifact_type,
        "slate_date": slate_date,
        "payload": payload,
        "payload_sha256": canonical_payload_sha256(payload),
        "generated_at": _generated_at(payload),
        "source": source,
        "source_run_id": source_run_id,
        "source_commit_sha": source_commit_sha,
        "metadata": {"artifact_path": relative_path},
    }
```

- [x] **Step 4: Verify tests pass**

```powershell
python -m pytest tests/test_published_artifacts.py -q
```

Expected: pass.

- [x] **Step 5: Commit**

```powershell
git add market_infra/published_artifacts.py tests/test_published_artifacts.py
git commit -m "feat: build published artifact rows"
```

## Task 3: Add Dry-Run-First Supabase Artifact Publisher

**Files:**
- Create: `scripts/publish_pipeline_artifacts_to_supabase.py`
- Create: `tests/test_publish_pipeline_artifacts.py`

- [x] **Step 1: Write publisher tests**

Create `tests/test_publish_pipeline_artifacts.py`:

```python
from pathlib import Path

from scripts.publish_pipeline_artifacts_to_supabase import collect_artifact_rows, run


class FakeWriter:
    def __init__(self):
        self.upserts = []
        self.inserts = []

    def upsert_rows(self, table, rows, on_conflict):
        self.upserts.append((table, rows, on_conflict))
        return len(rows)

    def insert_rows(self, table, rows):
        self.inserts.append((table, rows))
        return len(rows)


def test_collect_artifact_rows_includes_today_and_dated_archive(tmp_path):
    processed = tmp_path / "dashboard" / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "today.json").write_text('{"date":"2026-05-22","pitchers":[]}', encoding="utf-8")
    (processed / "2026-05-22.json").write_text('{"date":"2026-05-22","pitchers":[]}', encoding="utf-8")

    rows = collect_artifact_rows(
        root=tmp_path,
        slate_date="2026-05-22",
        source="github_actions",
        source_run_id="run-1",
        source_commit_sha="sha",
    )

    assert [row["artifact_key"] for row in rows] == ["today", "dated_slate:2026-05-22"]


def test_run_dry_run_does_not_write(tmp_path):
    processed = tmp_path / "dashboard" / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "today.json").write_text('{"date":"2026-05-22","pitchers":[]}', encoding="utf-8")
    writer = FakeWriter()

    result = run(
        root=tmp_path,
        writer=writer,
        slate_date="2026-05-22",
        source="github_actions",
        source_run_id="run-1",
        source_commit_sha="sha",
        execute=False,
    )

    assert result["artifact_count"] == 1
    assert writer.upserts == []


def test_run_execute_upserts_artifacts_and_run_row(tmp_path):
    processed = tmp_path / "dashboard" / "data" / "processed"
    processed.mkdir(parents=True)
    (processed / "today.json").write_text('{"date":"2026-05-22","pitchers":[]}', encoding="utf-8")
    writer = FakeWriter()

    result = run(
        root=tmp_path,
        writer=writer,
        slate_date="2026-05-22",
        source="github_actions",
        source_run_id="run-1",
        source_commit_sha="sha",
        execute=True,
    )

    assert result["artifact_count"] == 1
    assert writer.upserts[0][0] == "published_pipeline_artifacts"
    assert writer.upserts[0][2] == "artifact_key"
    assert writer.inserts[0][0] == "pipeline_artifact_publication_runs"
```

- [x] **Step 2: Run tests to verify failure**

```powershell
python -m pytest tests/test_publish_pipeline_artifacts.py -q
```

Expected: fail because the script does not exist.

- [x] **Step 3: Implement publisher**

Create `scripts/publish_pipeline_artifacts_to_supabase.py` with:

```python
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_infra.published_artifacts import ARTIFACT_PATHS, build_artifact_row
from market_infra.supabase_writer import SupabaseMarketWriter


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def collect_artifact_rows(
    *,
    root: Path,
    slate_date: str,
    source: str,
    source_run_id: str | None,
    source_commit_sha: str | None,
) -> list[dict[str, Any]]:
    paths = list(ARTIFACT_PATHS)
    paths.append(Path("dashboard/data/processed") / f"{slate_date}.json")
    rows = []
    for relative in paths:
        path = root / relative
        if not path.exists():
            continue
        rows.append(
            build_artifact_row(
                root=root,
                path=path,
                source=source,
                source_run_id=source_run_id,
                source_commit_sha=source_commit_sha,
            )
        )
    return rows


def run(
    *,
    root: Path,
    writer,
    slate_date: str,
    source: str,
    source_run_id: str | None,
    source_commit_sha: str | None,
    execute: bool,
) -> dict[str, Any]:
    rows = collect_artifact_rows(
        root=root,
        slate_date=slate_date,
        source=source,
        source_run_id=source_run_id,
        source_commit_sha=source_commit_sha,
    )
    run_row = {
        "run_id": source_run_id or f"{source}:{slate_date}:{datetime.now(timezone.utc).isoformat()}",
        "source": source,
        "run_type": os.environ.get("PIPELINE_RUN_TYPE", "full"),
        "slate_date": slate_date,
        "status": "completed",
        "artifact_count": len(rows),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "metadata": {"source_commit_sha": source_commit_sha},
    }
    if execute:
        writer.upsert_rows("published_pipeline_artifacts", rows, on_conflict="artifact_key")
        writer.insert_rows("pipeline_artifact_publication_runs", [run_row])
    return {"artifact_count": len(rows), "execute": execute}


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument("--source", default="github_actions")
    parser.add_argument("--source-run-id")
    parser.add_argument("--source-commit-sha")
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    writer = SupabaseMarketWriter(_env("SUPABASE_URL"), _env("SUPABASE_SERVICE_ROLE_KEY"))
    result = run(
        root=ROOT,
        writer=writer,
        slate_date=args.date,
        source=args.source,
        source_run_id=args.source_run_id,
        source_commit_sha=args.source_commit_sha,
        execute=args.execute,
    )
    mode = "execute" if args.execute else "dry_run"
    print(f"artifact_publish mode={mode} date={args.date} artifacts={result['artifact_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 4: Verify tests pass**

```powershell
python -m pytest tests/test_publish_pipeline_artifacts.py -q
```

Expected: pass.

- [x] **Step 5: Commit**

```powershell
git add scripts/publish_pipeline_artifacts_to_supabase.py tests/test_publish_pipeline_artifacts.py
git commit -m "feat: publish pipeline artifacts to supabase"
```

## Task 4: Shadow Publish Artifacts From GitHub Actions

**Files:**
- Modify: `.github/workflows/pipeline.yml`
- Modify: `tests/test_pipeline_workflow_contract.py`

- [x] **Step 1: Add workflow contract test**

Add a test asserting the workflow publishes artifacts after successful pipeline
runs when `ENABLE_SUPABASE_ARTIFACT_PUBLISH=true`:

```python
def test_pipeline_workflow_can_shadow_publish_artifacts_to_supabase():
    workflow = Path(".github/workflows/pipeline.yml").read_text(encoding="utf-8")

    assert "ENABLE_SUPABASE_ARTIFACT_PUBLISH" in workflow
    assert "publish_pipeline_artifacts_to_supabase.py" in workflow
    assert "--source github_actions" in workflow
    assert "--execute" in workflow
```

- [x] **Step 2: Run test to verify failure**

```powershell
python -m pytest tests/test_pipeline_workflow_contract.py::test_pipeline_workflow_can_shadow_publish_artifacts_to_supabase -q
```

Expected: fail because the workflow has no artifact publisher step.

- [x] **Step 3: Add gated workflow step**

Add this step after the current pipeline output commit step:

```yaml
      - name: Publish artifacts to Supabase
        if: ${{ vars.ENABLE_SUPABASE_ARTIFACT_PUBLISH == 'true' }}
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          PIPELINE_RUN_TYPE: ${{ github.event.inputs.mode || 'full' }}
        run: |
          python scripts/publish_pipeline_artifacts_to_supabase.py \
            --date "$TODAY" \
            --source github_actions \
            --source-run-id "${{ github.run_id }}" \
            --source-commit-sha "${{ github.sha }}" \
            --execute
```

- [x] **Step 4: Verify workflow tests**

```powershell
python -m pytest tests/test_pipeline_workflow_contract.py -q
```

Expected: pass.

- [x] **Step 5: Commit**

```powershell
git add .github/workflows/pipeline.yml tests/test_pipeline_workflow_contract.py
git commit -m "feat: shadow publish artifacts from pipeline"
```

## Task 5: Add Supabase Artifact API On Netlify

**Files:**
- Create: `netlify/functions/get-artifact.mjs`
- Create: `tests/test_get_artifact_function.mjs`

- [x] **Step 1: Write function tests**

Create `tests/test_get_artifact_function.mjs`:

```javascript
import assert from 'node:assert/strict';
import test from 'node:test';

import { handler } from '../netlify/functions/get-artifact.mjs';

test('get-artifact rejects unknown artifact types', async () => {
  const response = await handler({ queryStringParameters: { type: 'raw_snapshots' } });

  assert.equal(response.statusCode, 400);
});

test('get-artifact returns latest artifact payload', async () => {
  const oldFetch = global.fetch;
  global.fetch = async (url) => {
    assert.match(String(url), /published_pipeline_artifacts/);
    return {
      ok: true,
      json: async () => [{
        artifact_key: 'today',
        payload_sha256: 'sha',
        published_at: '2026-05-22T15:41:07Z',
        payload: { date: '2026-05-22', pitchers: [] },
      }],
    };
  };
  process.env.SUPABASE_URL = 'https://example.supabase.co';
  process.env.SUPABASE_SERVICE_ROLE_KEY = 'service-role';

  try {
    const response = await handler({ queryStringParameters: { type: 'today' } });
    assert.equal(response.statusCode, 200);
    assert.equal(JSON.parse(response.body).date, '2026-05-22');
    assert.equal(response.headers.ETag, '"sha"');
  } finally {
    global.fetch = oldFetch;
    delete process.env.SUPABASE_URL;
    delete process.env.SUPABASE_SERVICE_ROLE_KEY;
  }
});
```

- [x] **Step 2: Run tests to verify failure**

```powershell
node --test tests/test_get_artifact_function.mjs
```

Expected: fail because the function does not exist.

- [x] **Step 3: Implement function**

Create `netlify/functions/get-artifact.mjs`:

```javascript
const ALLOWED_TYPES = new Set([
  'today',
  'dated_slate',
  'index',
  'steam',
  'performance',
  'params',
  'preview_lines',
  'picks_history',
]);

function jsonResponse(statusCode, body, headers = {}) {
  return {
    statusCode,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      ...headers,
    },
    body: JSON.stringify(body),
  };
}

function artifactKey(type, date) {
  if (type === 'dated_slate') {
    if (!date) throw new Error('date is required for dated_slate');
    return `dated_slate:${date}`;
  }
  return type;
}

export async function handler(event) {
  const params = event.queryStringParameters || {};
  const type = params.type || 'today';
  const date = params.date || '';

  if (!ALLOWED_TYPES.has(type)) {
    return jsonResponse(400, { error: 'unsupported artifact type' });
  }

  let key;
  try {
    key = artifactKey(type, date);
  } catch (error) {
    return jsonResponse(400, { error: error.message });
  }

  const supabaseUrl = process.env.SUPABASE_URL;
  const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;
  if (!supabaseUrl || !serviceRoleKey) {
    return jsonResponse(500, { error: 'artifact api is not configured' });
  }

  const url = new URL(`${supabaseUrl}/rest/v1/published_pipeline_artifacts`);
  url.searchParams.set('artifact_key', `eq.${key}`);
  url.searchParams.set('select', 'artifact_key,payload,payload_sha256,published_at');
  url.searchParams.set('limit', '1');

  const response = await fetch(url, {
    headers: {
      apikey: serviceRoleKey,
      authorization: `Bearer ${serviceRoleKey}`,
    },
  });

  if (!response.ok) {
    return jsonResponse(502, { error: 'failed to read artifact' });
  }

  const rows = await response.json();
  if (!rows.length) {
    return jsonResponse(404, { error: 'artifact not found' });
  }

  const row = rows[0];
  return jsonResponse(200, row.payload, {
    'cache-control': 'public, max-age=30, stale-while-revalidate=120',
    etag: `"${row.payload_sha256}"`,
    'x-artifact-key': row.artifact_key,
    'x-artifact-published-at': row.published_at,
  });
}
```

- [x] **Step 4: Verify function tests**

```powershell
node --test tests/test_get_artifact_function.mjs
```

Expected: pass.

- [x] **Step 5: Commit**

```powershell
git add netlify/functions/get-artifact.mjs tests/test_get_artifact_function.mjs
git commit -m "feat: serve published artifacts from netlify"
```

## Task 6: Add Dashboard Artifact Source Adapter

**Files:**
- Modify: `dashboard/v2-data.js`
- Modify: `dashboard/v2-data.test.mjs`
- Modify: `dashboard/index.html`

- [x] **Step 1: Add v2 adapter tests**

Add tests that prove the dashboard can read from Netlify artifact API and fall
back to static files:

```javascript
test('loads today from artifact api when enabled', async () => {
  const oldFetch = global.fetch;
  global.fetch = async (url) => {
    const clean = String(url).split('?')[0];
    if (clean.endsWith('/.netlify/functions/get-artifact')) {
      return jsonResponse(todayJson);
    }
    throw new Error(`unexpected url ${url}`);
  };

  try {
    const data = await loadV2Data({ artifactSource: 'supabase' });
    assert.equal(data.slate.date, todayJson.date);
  } finally {
    global.fetch = oldFetch;
  }
});

test('falls back to static today when artifact api fails', async () => {
  const oldFetch = global.fetch;
  global.fetch = async (url) => {
    const clean = String(url).split('?')[0];
    if (clean.endsWith('/.netlify/functions/get-artifact')) {
      return { ok: false, status: 502, text: async () => 'bad gateway' };
    }
    if (clean.endsWith('/today.json')) return jsonResponse(todayJson);
    if (clean.endsWith('/performance.json')) return jsonResponse(perfJson);
    if (clean.endsWith('/steam.json')) return jsonResponse(steamJson);
    if (clean.endsWith('/index.json')) return jsonResponse({ dates: dateIndex });
    throw new Error(`unexpected url ${url}`);
  };

  try {
    const data = await loadV2Data({ artifactSource: 'supabase' });
    assert.equal(data.slate.date, todayJson.date);
  } finally {
    global.fetch = oldFetch;
  }
});
```

- [x] **Step 2: Run tests to verify failure**

```powershell
node --test dashboard/v2-data.test.mjs
```

Expected: fail because `loadV2Data` does not accept `artifactSource`.

- [x] **Step 3: Add artifact fetch helper**

In `dashboard/v2-data.js`, add a small helper that keeps static files as
fallback:

```javascript
function artifactApiUrl(type, date) {
  const url = new URL('/.netlify/functions/get-artifact', window.location.origin);
  url.searchParams.set('type', type);
  if (date) url.searchParams.set('date', date);
  return url.pathname + url.search;
}

async function fetchArtifactJson({ type, date, staticUrl, artifactSource = 'static' }) {
  if (artifactSource === 'supabase') {
    try {
      return await fetchJSON(artifactApiUrl(type, date));
    } catch (error) {
      console.warn(`artifact api failed for ${type}; falling back to static`, error);
    }
  }
  return fetchJSON(staticUrl);
}
```

Use it for `today`, dated slate files, `index`, `steam`, and `performance`.

- [x] **Step 4: Add legacy dashboard adapter**

In `dashboard/index.html`, add the same behavior around the existing fetch
locations. Keep the default source `static` until the canary is explicitly
enabled:

```javascript
const ARTIFACT_SOURCE = localStorage.getItem('bbe_artifact_source') || 'static';

function artifactApiUrl(type, date) {
  const params = new URLSearchParams({ type });
  if (date) params.set('date', date);
  return `/.netlify/functions/get-artifact?${params.toString()}`;
}

async function fetchArtifactJson(type, staticUrl, date) {
  if (ARTIFACT_SOURCE === 'supabase') {
    try {
      const res = await fetch(`${artifactApiUrl(type, date)}&t=${Date.now()}`);
      if (!res.ok) throw new Error(`artifact api ${res.status}`);
      return await res.json();
    } catch (error) {
      console.warn(`artifact api failed for ${type}; falling back to static`, error);
    }
  }
  const res = await fetch(`${staticUrl}?t=${Date.now()}`);
  if (!res.ok) throw new Error(`static artifact ${res.status}`);
  return await res.json();
}
```

- [x] **Step 5: Verify dashboard tests**

```powershell
node --test dashboard/v2-data.test.mjs
```

Expected: pass.

- [x] **Step 6: Commit**

```powershell
git add dashboard/v2-data.js dashboard/v2-data.test.mjs dashboard/index.html
git commit -m "feat: add supabase artifact dashboard source"
```

## Task 7: Add Artifact Parity Checker

**Files:**
- Create: `scripts/compare_supabase_artifacts.py`
- Create: `tests/test_compare_supabase_artifacts.py`

- [x] **Step 1: Write parity tests**

Create `tests/test_compare_supabase_artifacts.py`:

```python
from scripts.compare_supabase_artifacts import compare_hashes


def test_compare_hashes_reports_match():
    assert compare_hashes(local_sha="abc", remote_sha="abc") == {
        "matches": True,
        "local_sha": "abc",
        "remote_sha": "abc",
    }


def test_compare_hashes_reports_mismatch():
    assert compare_hashes(local_sha="abc", remote_sha="def") == {
        "matches": False,
        "local_sha": "abc",
        "remote_sha": "def",
    }
```

- [x] **Step 2: Run tests to verify failure**

```powershell
python -m pytest tests/test_compare_supabase_artifacts.py -q
```

Expected: fail because the script does not exist.

- [x] **Step 3: Implement checker**

Create `scripts/compare_supabase_artifacts.py` with a read-only CLI that:

- builds local artifact rows using `market_infra.published_artifacts`;
- fetches matching Supabase `published_pipeline_artifacts` rows by
  `artifact_key`;
- prints `match`, `missing`, or `mismatch` per artifact;
- exits `1` only when `--strict` is passed and any artifact is missing or
  mismatched.

Include this pure helper:

```python
def compare_hashes(*, local_sha: str, remote_sha: str | None) -> dict[str, object]:
    return {
        "matches": bool(remote_sha) and local_sha == remote_sha,
        "local_sha": local_sha,
        "remote_sha": remote_sha,
    }
```

- [x] **Step 4: Verify tests pass**

```powershell
python -m pytest tests/test_compare_supabase_artifacts.py -q
```

Expected: pass.

- [x] **Step 5: Commit**

```powershell
git add scripts/compare_supabase_artifacts.py tests/test_compare_supabase_artifacts.py
git commit -m "feat: compare supabase artifact parity"
```

## Task 8: Add Render Pipeline Runner Design

**Files:**
- Create: `render/pipeline-runner.md`
- Modify: `docs/operational-risk-register.md`

- [x] **Step 1: Create Render runner handoff**

Create `render/pipeline-runner.md`:

```markdown
# BBE Render Pipeline Runner

This service replaces GitHub scheduled pipeline execution after artifact parity
and dashboard API canaries pass.

## Proposed Services

| Service | Command | Schedule |
| --- | --- | --- |
| `bbe-pipeline-preview` | `python scripts/run_render_pipeline_mode.py --mode preview --shadow-prefix --execute` | 12:17 AM Phoenix |
| `bbe-pipeline-grading` | `python scripts/run_render_pipeline_mode.py --mode grading --shadow-prefix --execute` | 3:17 AM Phoenix |
| `bbe-pipeline-full-refresh` | `python scripts/run_render_pipeline_mode.py --mode pipeline --shadow-prefix --execute` | 6:17 AM, then 8:07 AM-6:07 PM Phoenix |
| `bbe-pipeline-lock` | `python scripts/run_render_pipeline_mode.py --mode lock --shadow-prefix --execute` | Triggered by live layer, not cron |

## Required Environment

- `RUNDOWN_API_KEY`
- `ODDS_API_KEY`
- `PROPLINE_API_KEY`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `ENABLE_SUPABASE_LOCK_CONSUMER=true`
- `SUPABASE_LOCK_CONSUMER_STRICT=true`
- `OFFICIAL_MARKET_SOURCE` unset or `therundown`
- `ENABLE_BOLTODDS_PIPELINE_SOURCE=false`

## Promotion Gate

Run Render in shadow for one slate while GitHub remains official. During
rehearsal, publish Render outputs under `render_shadow:<publish-date>:` keys so
they cannot overwrite the live Netlify artifact API mirror. Promote only when
Render-generated Supabase artifact hashes match GitHub committed artifacts for
`today`, dated archive, `steam`, `performance`, `params`, `preview_lines`, and
`picks_history` where those files are expected for the run type.

## Rollback

Disable Render schedules and set dashboard artifact source back to static.
Manual GitHub `workflow_dispatch` remains available.
```

- [x] **Step 2: Add risk register failure modes**

In `docs/operational-risk-register.md`, add rows for:

- Supabase artifact API stale
- Render pipeline runner fails
- Render/GitHub artifact parity mismatch
- Dashboard artifact API fallback hides stale Supabase data

Each row should name the first check and rollback action.

- [x] **Step 3: Commit**

```powershell
git add render/pipeline-runner.md docs/operational-risk-register.md
git commit -m "docs: plan render pipeline runner risk controls"
```

## Task 9: Shadow Render Pipeline Run

**Files:**
- Modify: `docs/current-state.md`
- No code change if Render service is configured through the dashboard/CLI.

- [x] **Step 1: Run one manual Render pipeline command**

Use a non-lock active slate command first:

```powershell
python pipeline/run_pipeline.py 2026-05-22
python scripts/publish_pipeline_artifacts_to_supabase.py --date 2026-05-22 --source render_pipeline --source-run-id manual-render-shadow-2026-05-22 --execute
python scripts/compare_supabase_artifacts.py --date 2026-05-22 --strict
```

Expected:

- pipeline completes;
- Supabase artifacts publish;
- parity checker passes against local committed artifacts;
- no dashboard source switch yet.

Result, 2026-05-24:

- A controlled one-off preview command succeeded on
  `bbe-pipeline-shadow-runner-hosted` (`crn-d89jpvdckfvc738nfla0`), job
  `job-d89jqolckfvc738ngg6g`.
- The job explicitly set `ENABLE_SUPABASE_LOCK_CONSUMER=false`,
  `SUPABASE_LOCK_CONSUMER_STRICT=false`,
  `OFFICIAL_MARKET_SOURCE=therundown`, and
  `ENABLE_BOLTODDS_PIPELINE_SOURCE=false`.
- Publication run `render-preview-shadow-20260524T180310Z` wrote 8
  `render_pipeline` artifacts at `2026-05-24T18:04:57Z`, with source commit
  `d8686401` and timestamp ordering valid.
- Because GitHub kept refreshing the official artifact stream during the
  Render test, the Render mirror rows did not match the latest GitHub commit
  `f124a44b`. The current mirror was restored with
  `manual-github-artifact-restore-after-render-canary-20260524T181000Z`, and
  a REST-backed strict parity check passed with 8/8 matches.
- No dashboard source switch, active Render schedule, provider source, model,
  threshold, staking, notification, or retention behavior changed.

- [x] **Step 2: Configure Render shadow schedule**

Create Render cron services from `render/pipeline-runner.md`, but keep GitHub
scheduled workflows official for one slate. Use the `--shadow-prefix` runner so
Render rows are written to prefixed artifact keys such as
`render_shadow:2026-05-26:today` instead of the live `today` key.

Result, 2026-05-26:

- Added `scripts/run_render_pipeline_mode.py` so Render uses the same
  preview/grading/full/lock publish contract as GitHub while writing rehearsal
  artifacts under `render_shadow:<publish-date>:` keys.
- One-off Render job `job-d8as33j7uimc73ck10og` succeeded for
  `2026-05-26` full mode and wrote 8 prefixed rows through publication run
  `manual-render-pipeline-2026-05-26-20260526T155239Z`.
- Normal live artifact keys still matched GitHub/static 8/8 after the one-off
  run, proving the prefix prevented mirror overwrite.
- Shadow-prefixed runs now force `ENABLE_SUPABASE_LOCK_CONSUMER=false`,
  `SUPABASE_LOCK_CONSUMER_STRICT=false`, `OFFICIAL_MARKET_SOURCE=therundown`,
  and `ENABLE_BOLTODDS_PIPELINE_SOURCE=false` while they run. This prevents the
  rehearsal from consuming official Supabase lock rows or quietly testing a
  provider-source change.
- Created morning-only Render shadow cron services, all on `main` at
  `4c6d0edc`, auto-deploy off:
  - `bbe-pipeline-preview-shadow` (`crn-d8as4l1akrks738ngep0`), schedule
    `17 7 * * *`.
  - `bbe-pipeline-grading-shadow` (`crn-d8as4pdckfvc73dgpme0`), schedule
    `17 10 * * *`.
  - `bbe-pipeline-full-shadow` (`crn-d8as4r8g4nts73b5f510`), schedule
    `17 13 * * *`.
- Follow-up commit `228d67fd` hardened the shadow wrapper so `--shadow-prefix`
  runs force the Supabase lock consumer off and keep the provider source on
  TheRundown. Existing shadow services were redeployed on that guarded commit.
- Added refresh-window Render shadow cron services, also on `main` with
  auto-deploy off:
  - `bbe-pipeline-refresh-shadow-day` (`crn-d8asbonavr4c73drnrhg`), schedule
    `7,37 15-23 * * *`.
  - `bbe-pipeline-refresh-shadow-evening` (`crn-d8asbrel51nc73ahmh60`),
    schedule `7,37 0 * * *`.
  - `bbe-pipeline-refresh-shadow-final` (`crn-d8asbv0jo6nc7381gma0`),
    schedule `7 1 * * *`.
- Guarded one-off Render job `job-d8ascuj7uimc73ckb640` succeeded for
  `2026-05-26` full mode, wrote 8 prefixed rows through publication run
  `manual-render-pipeline-2026-05-26-20260526T161330Z`, and left the normal
  live artifact keys on GitHub/static-compatible rows with strict parity 8/8.
- GitHub scheduled workflows remain official; dashboard reads remain static by
  default; this does not enable provider, model, threshold, staking,
  notification, retention, or dashboard-source changes.

- [ ] **Step 3: Compare GitHub and Render outputs**

For each expected run type, record:

- run start time;
- run completion time;
- artifact hash;
- publication row;
- dashboard API result;
- any mismatch.

Use:

```powershell
python scripts/compare_supabase_artifacts.py --date YYYY-MM-DD --remote-key-prefix "render_shadow:YYYY-MM-DD:" --strict
```

- [ ] **Step 4: Update current state**

If the shadow slate is clean, update `docs/current-state.md` to say Render
pipeline runner is in shadow artifact parity canary.

- [ ] **Step 5: Commit docs**

```powershell
git add docs/current-state.md
git commit -m "docs: record render artifact parity canary"
```

## Task 10: Dashboard API Canary

**Files:**
- Modify: `docs/current-state.md`
- No code change if Task 6 added the adapter.

- [x] **Step 1: Enable canary for Tyler only**

In the browser console on the deployed dashboard, set:

```javascript
localStorage.setItem('bbe_artifact_source', 'supabase')
```

Reload the dashboard.

- [x] **Step 2: Verify dashboard state**

Check:

- slate date matches GitHub/static artifact;
- pitcher count matches;
- tracked pick count matches;
- locked picks match;
- performance tab loads;
- date browser loads prior dated archive;
- no console errors from `get-artifact`.

- [x] **Step 3: Keep static fallback active**

Do not remove static fallback during this canary. If Supabase API fails, the app
should continue loading static JSON and log a warning.

- [x] **Step 4: Update current state**

If clean, update `docs/current-state.md` to say dashboard artifact API is in
Tyler-only canary.

- [x] **Step 5: Commit docs**

```powershell
git add docs/current-state.md
git commit -m "docs: record dashboard artifact api canary"
```

Result, 2026-05-24:

- Netlify `get-artifact` was initially unconfigured. The production site now
  has `SUPABASE_URL` plus the hosted Supabase service-role secret available to
  the function after deploy `6a13455bb5613060d352d0ba`.
- The Tyler-only browser canary used
  `localStorage.bbe_artifact_source=supabase`; dashboard defaults remain static.
- API parity passed for the current 2026-05-24 artifact set, and direct API
  checks for `today`, current dated slate, `performance`, and `index` matched
  static JSON. After the 18:43 UTC GitHub artifact commit, strict parity passed
  8/8 for 2026-05-24.
- The first prior-date click exposed missing historical dated archive rows
  (`dated_slate:2026-05-23` returned 404 and fell back to static). Backfilled
  2026-05-21, 2026-05-22, and 2026-05-23 dated-slate rows as
  `manual_backfill`; API responses now match static JSON and
  `scripts/compare_supabase_artifacts.py --date 2026-05-23 --strict` passes
  8/8.
- Playwright canary after backfill loaded the current slate and
  `?date=2026-05-23` through Netlify `get-artifact` with 200s for
  `dated_slate`, `performance`, `params`, `index`, and `steam`. No
  `get-artifact` console errors remained; the only observed browser noise was
  the existing favicon 404 and React DevTools info.
- No Render scheduler promotion, provider switch, model change, threshold
  change, staking change, retention deletion, or global dashboard-source switch
  was made.

## Task 11: Promote Render As Primary Scheduler

**Files:**
- Modify: `.github/workflows/pipeline.yml`
- Modify: `docs/current-state.md`
- Modify: `AGENTS.md`

- [ ] **Step 1: Confirm promotion gates**

Do not promote unless all are true:

- strict Supabase lock consumer completed one clean slate;
- GitHub and Render artifact hashes matched for one full slate;
- dashboard API canary loaded cleanly;
- manual GitHub workflow rollback was tested during the same week;
- Tyler explicitly approved Render as primary scheduler.

- [ ] **Step 2: Disable GitHub scheduled triggers**

In `.github/workflows/pipeline.yml`, remove or comment scheduled `cron` entries
and leave `workflow_dispatch`.

Keep manual dispatch inputs for:

- `mode=pipeline`
- `mode=grading`
- `mode=preview`
- `mode=lock`
- `mode=propline_probe`

- [ ] **Step 3: Update docs**

Update:

- `docs/current-state.md`: Render is primary scheduler; GitHub manual fallback.
- `AGENTS.md`: pipeline schedule section points to Render, not GitHub Actions.
- `docs/operational-risk-register.md`: GitHub scheduled-run delay is no longer
  the primary lock risk; Render schedule/run health is.

- [ ] **Step 4: Run checks**

```powershell
python -m pytest tests/test_pipeline_workflow_contract.py -q
git diff --check
```

Expected: pass.

- [ ] **Step 5: Commit and push**

```powershell
git add .github/workflows/pipeline.yml docs/current-state.md AGENTS.md docs/operational-risk-register.md
git commit -m "chore: make render primary pipeline scheduler"
git push
```

## Task 12: Reduce GitHub Artifact Publishing To Backup

**Files:**
- Modify: `docs/current-state.md`
- Modify: `docs/operational-risk-register.md`
- Modify: `docs/provider-cost-ledger.md`

- [ ] **Step 1: Keep manual GitHub rollback**

Leave manual `workflow_dispatch` in place. Do not delete the workflow.

- [ ] **Step 2: Define backup cadence**

Pick one backup posture:

1. GitHub manual only, no scheduled commits.
2. Nightly GitHub artifact backup commit after games complete.
3. Weekly GitHub artifact backup commit.

Recommended first posture: manual only for one week, then decide if a nightly
backup is worth the repo churn.

- [ ] **Step 3: Update docs**

Document:

- Supabase artifact API is production dashboard source.
- Render is production pipeline runner.
- GitHub Actions is manual fallback and optional backup.
- TheRundown remains provider source unless provider cutover separately
  promotes BoltOdds/PropLine.

- [ ] **Step 4: Commit**

```powershell
git add docs/current-state.md docs/operational-risk-register.md docs/provider-cost-ledger.md
git commit -m "docs: mark github artifacts as backup path"
git push
```

## Acceptance Gates

This plan is complete only when:

- Supabase `published_pipeline_artifacts` has current `today`, dated archive,
  `index`, `steam`, `performance`, `params`, `preview_lines`, and
  `picks_history` rows when those artifacts are expected.
- Netlify `get-artifact` serves the same payload hashes as the static files
  during canary.
- Dashboard v2 and legacy dashboard can load from Supabase artifact API.
- Render runs preview, grading, full/refresh, and lock paths on schedule.
- GitHub scheduled workflows are disabled only after Render proves parity.
- Manual GitHub fallback still works.
- No production provider, model, threshold, staking, notification, retention,
  or dashboard behavior changed outside this artifact-source migration.

## Rollback

Rollback must stay boring:

1. Set dashboard artifact source back to `static`.
2. Disable Render pipeline schedules.
3. Manually run GitHub `pipeline.yml` for the current Phoenix slate.
4. Verify GitHub raw `today.json`, dated archive, `steam.json`, and
   `picks_history.json`.
5. Keep Supabase artifact rows for audit; do not delete them during rollback.

## Current Recommendation

As of 2026-05-24, the strict/single-writer lock canary is treated as clean
enough to start artifact-exit Stage 1. Tasks 1-8 are implemented on `main`, the
hosted artifact mirror tables exist, and
`ENABLE_SUPABASE_ARTIFACT_PUBLISH=true` is enabled for shadow artifact
publication. Dashboard reads still default to static JSON, GitHub remains the
official artifact writer, and no Render schedule has been promoted.

Manual `main` run `26367454166` proved the Stage 1 path: it published 8
Supabase artifact rows for 2026-05-24, refreshed `published_at`, recorded
artifact commit `599f275f`, and
`scripts/compare_supabase_artifacts.py --date 2026-05-24 --strict` passed with
8/8 matches. First scheduled `main` run `26367602689` then published 8 shadow
artifacts, and follow-up manual run `26367707782` refreshed all 8 rows at
`2026-05-24T17:18:04Z`, recorded artifact commit `c37896ea`, and passed strict
parity with 8/8 matches.

Task 9 Step 1 has now been exercised as a one-off Render preview canary.
The successful hosted runner is `bbe-pipeline-shadow-runner-hosted`
(`crn-d89jpvdckfvc738nfla0`), with annual idle schedule and auto-deploy off.
Render job `job-d89jqolckfvc738ngg6g` completed and wrote 8 artifacts through
publication run `render-preview-shadow-20260524T180310Z`. Because GitHub
continued refreshing official artifacts during the canary, the Render rows were
not treated as the current source; restore run
`manual-github-artifact-restore-after-render-canary-20260524T181000Z` restored
the mirror to GitHub commit `f124a44b`, and
strict parity passed 8/8 again. Continue Stage 1 observation. The next safe
move is either a Tyler-only dashboard artifact API canary or one more matched
Render/GitHub shadow run; do not promote Render schedules or dashboard reads
without the next explicit approval.

Task 10 is now exercised as a Tyler-only dashboard artifact API canary. Netlify
`get-artifact` is configured, current 2026-05-24 artifacts and the tested prior
dated archives match static JSON, and the session-only dashboard source
`localStorage.bbe_artifact_source=supabase` loaded without `get-artifact`
errors after the dated-archive backfill.

The current recommendation is to let the rest of the 2026-05-24 slate run as a
soak, not to promote Task 11 today. Keep GitHub scheduled runs official,
dashboard static JSON as default, and static fallback active while observing
strict locks, 8-row artifact publication, strict parity after each artifact
commit, and current/prior-date dashboard API behavior. Task 11 remains a
separate Render primary scheduler go/no-go after full-slate evidence is
reviewed.

Post-slate update, 2026-05-25: the lock/artifact soak found one real contract
gap before Task 11. The final 2026-05-24 artifact had 25 top-level
`tracked_picks` but only 24 lockable pitcher-card picks because Matthew
Liberatore stayed in `picks_history` after the St. Louis probable changed to
Brycen Mautz. This should not be locked as an active bet, but it also should not
remain in the active tracked-pick count. The artifact enrichment layer now keeps
only matched, locked, or graded rows in active `tracked_picks`; unmatched
still-unlocked rows move to `inactive_tracked_picks` with
`inactive_reason=starter_replaced` when the same matchup has a replacement
pitcher, or `inactive_reason=missing_pitcher_card` otherwise. Require one more
clean slate where active tracked picks, Supabase lock rows, and shadow timing
counts align before treating strict locks as Task 11-ready.

Same-day artifact follow-up, 2026-05-25: the stale current-slate artifact
incident was caused by GitHub delayed grading committing/publishing stale
current-slate artifacts while Render/live-layer still depended on GitHub raw
`today.json` as the source artifact. It was not a Render lock failure. Commit
`213de1fb` patches the contract: grading runs skip `today.json` enrichment,
stage only dated archives plus grading-safe performance/history/params files,
and publish Supabase artifacts with `--scope grading` for the prior slate date.
The 2026-05-24 `dated_slate` Supabase mismatch was repaired with
`source=manual_backfill`, and strict parity for 2026-05-24 now passes 8/8.

Current Task 11 posture: use 2026-05-25 as an observation day after the hotfix.
The next useful move is a controlled Render primary-scheduler rehearsal/go-no-go
with manual GitHub rollback verified, not another lock-layer proof and not an
immediate provider/dashboard/model/staking/retention promotion.

Render cleanup, 2026-05-25: the two inert misconfigured runner clones
`bbe-pipeline-shadow-runner` (`crn-d89jdge7r5hc73dj8300`) and
`bbe-pipeline-shadow-runner-v2` (`crn-d89jjq3bc2fs73fa0qr0`) were deleted after
confirming their service names/IDs through the Render API. The known-good hosted
runner canary `bbe-pipeline-shadow-runner-hosted`
(`crn-d89jpvdckfvc738nfla0`) remains for the next scheduler rehearsal.

Scheduler follow-up, 2026-05-26: another stale current-slate artifact by the
morning brief strengthened the case for advancing Task 9 Step 2 / Task 11
rehearsal. Do not disable GitHub scheduled triggers yet because Render has not
matched a full slate. The next move is a Render scheduler rehearsal that uses
`scripts/run_render_pipeline_mode.py --shadow-prefix --execute`, so Render
publishes to `render_shadow:<publish-date>:` artifact keys and cannot overwrite
the live Netlify artifact API mirror. Compare those candidate rows with:

```powershell
python scripts/compare_supabase_artifacts.py --date YYYY-MM-DD --remote-key-prefix "render_shadow:YYYY-MM-DD:" --strict
```

Only after one clean full-slate Render/GitHub hash match should Task 11 proceed
to disabling GitHub scheduled triggers.

Scheduler-only follow-up later on 2026-05-26: the shadow schedule now covers
preview, grading, full, and refresh windows. This is still Task 9 rehearsal
evidence, not Task 11 promotion. The next checks are whether today's
refresh-shadow jobs and tomorrow's preview/grading/full shadow jobs write the
expected `render_shadow:<date>:` rows without consuming lock rows, dispatching
wrong-date artifacts, or touching provider/model/dashboard production behavior.
