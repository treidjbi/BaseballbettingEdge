# PropLine Supabase Market Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an observation-only Supabase market-data layer that can track provider coverage, normalized odds snapshots, and future PropLine webhooks without changing the live BaseballBettingEdge production pipeline.

**Architecture:** Keep the current GitHub Actions plus JSON artifact pipeline as the production source of truth. Add a separate sidecar infrastructure lane that stores raw provider observations, normalized pitcher strikeout market snapshots, coverage audits, and webhook deliveries in Supabase. The sidecar can be fed by manual/shadow polling first and by PropLine webhooks later if the weekend trial proves coverage and the paid webhook tier makes business sense.

**Tech Stack:** Python 3.11, pytest, requests, Supabase Postgres, Supabase Edge Functions, Deno TypeScript, PropLine REST API, GitHub Actions manual dispatch.

---

## Why This Exists

The immediate trigger is provider coverage risk:

- TheRundown is not reliably populating FanDuel or DraftKings.
- The Odds API has limited useful coverage for this app.
- PropLine may be useful if the 2026-05-01 weekend trial proves it covers the target books and pitcher strikeout props well enough.

The long-term reason is bigger than PropLine. BaseballBettingEdge needs better infrastructure for market history, CLV, steam, provider comparisons, and model diagnostics. Today those signals are squeezed through daily JSON artifacts. Supabase should become the durable market-data ledger, but only after it observes silently.

## Non-Negotiable Guardrails

- Do not change `pipeline/fetch_odds.py` production provider order in this branch.
- Do not change `.github/workflows/pipeline.yml` in this branch.
- Do not change `dashboard/data/processed/today.json` or the v2 dashboard data contract.
- Do not make the dashboard, model, pick seeding, notifications, grading, or calibration read from Supabase.
- Do not add scheduled Supabase writes during the 2026-05-01 weekend trial.
- Do not subscribe to PropLine webhooks until the Monday 2026-05-04 provider review confirms PropLine coverage and the user approves the paid tier.
- Treat Supabase as observation-only until a later migration plan explicitly promotes it.
- Do not commit local Supabase secrets. `supabase/.env` must stay ignored.

## Current Repo Starting Point

Already present:

- `pipeline/fetch_odds.py` has PropLine constants, `propline_get()`, `_parse_propline_event_props()`, and fallback merge behavior.
- `scripts/probe_propline_books.py` safely probes PropLine coverage from GitHub Actions without printing API keys.
- `.github/workflows/pipeline.yml` has manual `workflow_dispatch` mode `propline_probe`.
- `tests/test_fetch_odds.py` covers PropLine parser behavior and fallback merge behavior.
- `pipeline/build_features.py` preserves `odds_source` and `propline_event_id` into pitcher records.

This plan should build around those pieces rather than replacing them.

## External Docs Checked

- PropLine LLM reference: `https://prop-line.com/llms-full.txt`
- PropLine API docs: `https://prop-line.com/docs`
- Supabase Edge Functions docs: `https://supabase.com/docs/guides/functions`
- Supabase Edge Function limits: `https://supabase.com/docs/guides/functions/limits`

Relevant PropLine facts:

- Base URL is `https://api.prop-line.com/v1`.
- Auth supports `X-API-Key`.
- MLB sport key is `baseball_mlb`.
- Pitcher strikeout market key is `pitcher_strikeouts`.
- The per-event odds response uses `bookmakers[] -> markets[] -> outcomes[]`.
- Webhook deliveries are a Streaming-tier feature and include `X-PropLine-Event`, `X-PropLine-Timestamp`, `X-PropLine-Signature`, and `X-PropLine-Delivery`.
- Signature shape is HMAC-SHA256 over `timestamp + "." + raw_body`.

## Target Branch

Use:

```bash
git checkout -b codex/propline-supabase-infra
```

Do this from a clean `main` checkout.

## Proposed File Structure

Create:

- `docs/superpowers/plans/2026-05-01-propline-supabase-market-infrastructure.md`
  - This plan.
- `supabase/config.toml`
  - Local Supabase function config, including public webhook endpoint JWT behavior.
- `supabase/migrations/<generated>_market_infrastructure.sql`
  - Tables, indexes, RLS, and comments for the sidecar ledger.
- `supabase/functions/propline-webhook/index.ts`
  - Dormant PropLine webhook receiver. Verifies HMAC, dedupes delivery IDs, stores raw payloads.
- `supabase/functions/propline-webhook/README.md`
  - Deployment and secret setup notes.
- `.gitignore`
  - Add local Supabase secret files if they are not already ignored.
- `market_infra/__init__.py`
  - Python package marker for sidecar utilities.
- `market_infra/prop_snapshot.py`
  - Pure normalization helpers for provider payloads into market snapshot rows.
- `market_infra/supabase_writer.py`
  - Small REST writer for Supabase inserts and upserts, used only by manual/shadow scripts.
- `scripts/shadow_propline_to_supabase.py`
  - Manual local script that pulls PropLine odds for one date and writes observation-only rows.
- `tests/test_market_infra_prop_snapshot.py`
  - Unit tests for normalization, target-book filtering, and dedupe keys.
- `tests/test_market_infra_supabase_writer.py`
  - Unit tests for safe request construction and no secret logging.

Do not modify:

- `pipeline/run_pipeline.py`
- `pipeline/fetch_odds.py`
- `.github/workflows/pipeline.yml`
- `dashboard/`
- `data/picks_history.json`
- `dashboard/data/processed/`

---

### Task 1: Create the isolated branch and confirm no production changes

**Files:**
- Read: `AGENTS.md`
- Read: `docs/current-state.md`
- Read: `docs/superpowers/plans/2026-04-28-one-week-evaluation-cadence.md`
- Create: no files

- [ ] **Step 1: Confirm checkout state**

Run:

```bash
git status --short --branch
```

Expected:

```text
## main...origin/main
```

No tracked file changes should be present before branching.

- [ ] **Step 2: Create the branch**

Run:

```bash
git checkout -b codex/propline-supabase-infra
```

Expected:

```text
Switched to a new branch 'codex/propline-supabase-infra'
```

- [ ] **Step 3: Reconfirm production files are untouched**

Run:

```bash
git diff -- .github/workflows/pipeline.yml pipeline/fetch_odds.py pipeline/run_pipeline.py dashboard
```

Expected: no output.

Commit after Task 1 only if the plan file was added in this branch:

```bash
git add docs/superpowers/plans/2026-05-01-propline-supabase-market-infrastructure.md
git commit -m "docs: plan propline supabase market infrastructure"
```

---

### Task 2: Add the Supabase schema for observation-only market history

**Files:**
- Create: `supabase/migrations/<generated>_market_infrastructure.sql`

- [ ] **Step 1: Discover the Supabase CLI before creating migration files**

Run:

```bash
supabase --help
supabase migration --help
supabase migration new --help
```

Expected: CLI help output showing the current migration command shape.

- [ ] **Step 2: Create the migration with the CLI**

Run:

```bash
supabase migration new market_infrastructure
```

Expected: a new file under `supabase/migrations/` ending in `_market_infrastructure.sql`.

- [ ] **Step 3: Write the schema**

Open the generated migration file and replace its contents with:

```sql
create table if not exists public.market_provider_runs (
  id uuid primary key default gen_random_uuid(),
  provider text not null check (provider in ('therundown', 'the_odds', 'propline')),
  mode text not null check (mode in ('manual_probe', 'shadow_poll', 'webhook', 'test')),
  slate_date date,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  status text not null default 'started' check (status in ('started', 'completed', 'failed')),
  request_count integer not null default 0 check (request_count >= 0),
  target_event_count integer not null default 0 check (target_event_count >= 0),
  parsed_pitcher_prop_count integer not null default 0 check (parsed_pitcher_prop_count >= 0),
  books_seen text[] not null default '{}',
  error_message text,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.market_events (
  id uuid primary key default gen_random_uuid(),
  provider text not null check (provider in ('therundown', 'the_odds', 'propline')),
  provider_event_id text not null,
  sport_key text not null default 'baseball_mlb',
  slate_date date,
  commence_time timestamptz,
  home_team text,
  away_team text,
  raw_event jsonb not null default '{}'::jsonb,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  unique (provider, provider_event_id)
);

create table if not exists public.market_snapshots (
  id uuid primary key default gen_random_uuid(),
  run_id uuid references public.market_provider_runs(id) on delete set null,
  provider text not null check (provider in ('therundown', 'the_odds', 'propline')),
  provider_event_id text not null,
  sport_key text not null default 'baseball_mlb',
  market_key text not null,
  bookmaker_key text not null,
  bookmaker_title text,
  player_name text not null,
  normalized_player_name text not null,
  side text not null check (side in ('over', 'under')),
  line numeric not null,
  american_odds integer not null,
  observed_at timestamptz not null default now(),
  book_updated_at timestamptz,
  source_payload jsonb not null default '{}'::jsonb,
  dedupe_key text not null unique,
  created_at timestamptz not null default now()
);

create table if not exists public.provider_coverage_audits (
  id uuid primary key default gen_random_uuid(),
  run_id uuid references public.market_provider_runs(id) on delete cascade,
  slate_date date not null,
  provider text not null check (provider in ('therundown', 'the_odds', 'propline')),
  target_books text[] not null default '{}',
  books_seen text[] not null default '{}',
  target_event_count integer not null default 0 check (target_event_count >= 0),
  parsed_pitcher_prop_count integer not null default 0 check (parsed_pitcher_prop_count >= 0),
  complete_pitcher_line_groups integer not null default 0 check (complete_pitcher_line_groups >= 0),
  same_line_overlap_count integer check (same_line_overlap_count >= 0),
  line_conflict_count integer check (line_conflict_count >= 0),
  missing_target_books text[] not null default '{}',
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);

create table if not exists public.propline_webhook_deliveries (
  id uuid primary key default gen_random_uuid(),
  prop_line_delivery_id text not null unique,
  prop_line_event text not null,
  prop_line_timestamp timestamptz not null,
  signature_valid boolean not null,
  processed boolean not null default false,
  processing_error text,
  payload jsonb not null,
  received_at timestamptz not null default now()
);

create index if not exists idx_market_snapshots_player_market
  on public.market_snapshots (normalized_player_name, market_key, observed_at desc);

create index if not exists idx_market_snapshots_event_market
  on public.market_snapshots (provider, provider_event_id, market_key, observed_at desc);

create index if not exists idx_market_snapshots_book
  on public.market_snapshots (bookmaker_key, observed_at desc);

create index if not exists idx_provider_coverage_audits_slate
  on public.provider_coverage_audits (slate_date desc, provider);

alter table public.market_provider_runs enable row level security;
alter table public.market_events enable row level security;
alter table public.market_snapshots enable row level security;
alter table public.provider_coverage_audits enable row level security;
alter table public.propline_webhook_deliveries enable row level security;

comment on table public.market_provider_runs is
  'Observation-only market provider runs. Not read by the production pipeline.';

comment on table public.market_snapshots is
  'Normalized player prop odds snapshots for market history, CLV, steam, and provider comparison.';

comment on table public.propline_webhook_deliveries is
  'Raw PropLine webhook inbox with delivery-id dedupe and HMAC validation status.';
```

- [ ] **Step 4: Verify migration syntax locally**

Run:

```bash
supabase db reset
```

Expected: local database resets and the migration applies without SQL errors.

If Docker or local Supabase is unavailable, do not guess. Stop and record the blocker in the branch notes.

- [ ] **Step 5: Ensure local Supabase secrets are ignored**

If `.gitignore` does not already include `supabase/.env`, add:

```gitignore
supabase/.env
```

Run:

```bash
git diff -- .gitignore
```

Expected: the only `.gitignore` change is the local Supabase env-file ignore.

- [ ] **Step 6: Commit the schema**

Run:

```bash
git add supabase/migrations .gitignore
git commit -m "feat: add market infrastructure schema"
```

---

### Task 3: Add pure PropLine snapshot normalization helpers

**Files:**
- Create: `market_infra/__init__.py`
- Create: `market_infra/prop_snapshot.py`
- Create: `tests/test_market_infra_prop_snapshot.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_market_infra_prop_snapshot.py`:

```python
from market_infra.prop_snapshot import snapshots_from_propline_event


def test_snapshots_from_propline_event_keeps_target_books_only():
    event = {
        "id": "pl-event-1",
        "sport_key": "baseball_mlb",
        "commence_time": "2026-05-01T23:05:00Z",
        "home_team": "Boston Red Sox",
        "away_team": "New York Yankees",
        "bookmakers": [
            {
                "key": "draftkings",
                "title": "DraftKings",
                "markets": [{
                    "key": "pitcher_strikeouts",
                    "outcomes": [
                        {"name": "Over", "description": "Gerrit Cole", "price": -120, "point": 7.5},
                        {"name": "Under", "description": "Gerrit Cole", "price": 100, "point": 7.5},
                    ],
                }],
            },
            {
                "key": "bovada",
                "title": "Bovada",
                "markets": [{
                    "key": "pitcher_strikeouts",
                    "outcomes": [
                        {"name": "Over", "description": "Gerrit Cole", "price": -118, "point": 7.5},
                    ],
                }],
            },
        ],
    }

    rows = snapshots_from_propline_event(event, observed_at="2026-05-01T18:00:00Z")

    assert len(rows) == 2
    assert {row["bookmaker_key"] for row in rows} == {"draftkings"}
    assert {row["side"] for row in rows} == {"over", "under"}
    assert rows[0]["provider"] == "propline"
    assert rows[0]["provider_event_id"] == "pl-event-1"
    assert rows[0]["market_key"] == "pitcher_strikeouts"
    assert rows[0]["normalized_player_name"] == "gerrit cole"
    assert rows[0]["dedupe_key"]


def test_snapshots_from_propline_event_dedupe_changes_with_price():
    base = {
        "id": "pl-event-1",
        "bookmakers": [{
            "key": "fanduel",
            "title": "FanDuel",
            "markets": [{
                "key": "pitcher_strikeouts",
                "outcomes": [
                    {"name": "Over", "description": "Gerrit Cole", "price": -120, "point": 7.5},
                ],
            }],
        }],
    }
    changed = {
        **base,
        "bookmakers": [{
            "key": "fanduel",
            "title": "FanDuel",
            "markets": [{
                "key": "pitcher_strikeouts",
                "outcomes": [
                    {"name": "Over", "description": "Gerrit Cole", "price": -130, "point": 7.5},
                ],
            }],
        }],
    }

    first = snapshots_from_propline_event(base, observed_at="2026-05-01T18:00:00Z")[0]
    second = snapshots_from_propline_event(changed, observed_at="2026-05-01T18:00:00Z")[0]

    assert first["dedupe_key"] != second["dedupe_key"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_market_infra_prop_snapshot.py -v
```

Expected: FAIL because `market_infra.prop_snapshot` does not exist.

- [ ] **Step 3: Implement the normalizer**

Create `market_infra/__init__.py` as an empty file.

Create `market_infra/prop_snapshot.py`:

```python
from __future__ import annotations

import hashlib
import json
from typing import Any

from pipeline.name_utils import normalize

PROPLINE_TARGET_BOOKS = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "betrivers": "BetRivers",
    "kalshi": "Kalshi",
}

PROPLINE_SPORT_KEY = "baseball_mlb"
PROPLINE_MARKET_KEY = "pitcher_strikeouts"


def _american_odds(value: Any) -> int | None:
    try:
        text = str(value).strip().replace("+", "")
        if not text or text.lower() in {"none", "null", "n/a", "-"}:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _side(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"over", "under"}:
        return text
    return None


def _dedupe_key(parts: dict[str, Any]) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def snapshots_from_propline_event(event: dict[str, Any], observed_at: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    provider_event_id = str(event.get("id") or "")
    if not provider_event_id:
        return rows

    for bookmaker in event.get("bookmakers") or []:
        bookmaker_key = str(bookmaker.get("key") or "").strip().lower()
        if bookmaker_key not in PROPLINE_TARGET_BOOKS:
            continue
        bookmaker_title = str(bookmaker.get("title") or PROPLINE_TARGET_BOOKS[bookmaker_key])

        for market in bookmaker.get("markets") or []:
            if market.get("key") != PROPLINE_MARKET_KEY:
                continue
            for outcome in market.get("outcomes") or []:
                side = _side(outcome.get("name"))
                player_name = str(outcome.get("description") or outcome.get("player") or "").strip()
                price = _american_odds(outcome.get("price"))
                point = outcome.get("point")
                if side is None or not player_name or price is None or point is None:
                    continue
                try:
                    line = float(point)
                except (TypeError, ValueError):
                    continue

                dedupe_parts = {
                    "provider": "propline",
                    "provider_event_id": provider_event_id,
                    "market_key": PROPLINE_MARKET_KEY,
                    "bookmaker_key": bookmaker_key,
                    "player": normalize(player_name),
                    "side": side,
                    "line": line,
                    "price": price,
                    "observed_at": observed_at,
                }

                rows.append({
                    "provider": "propline",
                    "provider_event_id": provider_event_id,
                    "sport_key": event.get("sport_key") or PROPLINE_SPORT_KEY,
                    "market_key": PROPLINE_MARKET_KEY,
                    "bookmaker_key": bookmaker_key,
                    "bookmaker_title": bookmaker_title,
                    "player_name": player_name,
                    "normalized_player_name": normalize(player_name),
                    "side": side,
                    "line": line,
                    "american_odds": price,
                    "observed_at": observed_at,
                    "book_updated_at": outcome.get("book_updated_at"),
                    "source_payload": outcome,
                    "dedupe_key": _dedupe_key(dedupe_parts),
                })

    return rows
```

- [ ] **Step 4: Verify tests pass**

Run:

```bash
python -m pytest tests/test_market_infra_prop_snapshot.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit the normalizer**

Run:

```bash
git add market_infra tests/test_market_infra_prop_snapshot.py
git commit -m "feat: normalize propline market snapshots"
```

---

### Task 4: Add a Supabase writer used only by manual/shadow scripts

**Files:**
- Create: `market_infra/supabase_writer.py`
- Create: `tests/test_market_infra_supabase_writer.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_market_infra_supabase_writer.py`:

```python
from unittest.mock import Mock, patch

from market_infra.supabase_writer import SupabaseMarketWriter


def test_writer_uses_service_role_header_without_logging_secret():
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = [{"id": "run-1"}]

    with patch("market_infra.supabase_writer.requests.post", return_value=response) as post:
        result = writer.insert_rows("market_provider_runs", [{"provider": "propline", "mode": "manual_probe"}])

    assert result == [{"id": "run-1"}]
    kwargs = post.call_args.kwargs
    assert kwargs["headers"]["apikey"] == "secret-key"
    assert kwargs["headers"]["Authorization"] == "Bearer secret-key"
    assert "secret-key" not in repr(kwargs["json"])


def test_upsert_rows_sets_conflict_target():
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = []

    with patch("market_infra.supabase_writer.requests.post", return_value=response) as post:
        writer.upsert_rows("market_snapshots", [{"dedupe_key": "abc"}], on_conflict="dedupe_key")

    assert post.call_args.kwargs["params"] == {"on_conflict": "dedupe_key"}
    assert post.call_args.kwargs["headers"]["Prefer"] == "resolution=merge-duplicates,return=representation"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_market_infra_supabase_writer.py -v
```

Expected: FAIL because `market_infra.supabase_writer` does not exist.

- [ ] **Step 3: Implement the writer**

Create `market_infra/supabase_writer.py`:

```python
from __future__ import annotations

import requests


class SupabaseMarketWriter:
    def __init__(self, supabase_url: str, service_role_key: str) -> None:
        self.supabase_url = supabase_url.rstrip("/")
        self.service_role_key = service_role_key

    def _headers(self, prefer: str) -> dict[str, str]:
        return {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
            "Content-Type": "application/json",
            "Prefer": prefer,
        }

    def insert_rows(self, table: str, rows: list[dict]) -> list[dict]:
        if not rows:
            return []
        response = requests.post(
            f"{self.supabase_url}/rest/v1/{table}",
            headers=self._headers("return=representation"),
            json=rows,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()

    def upsert_rows(self, table: str, rows: list[dict], on_conflict: str) -> list[dict]:
        if not rows:
            return []
        response = requests.post(
            f"{self.supabase_url}/rest/v1/{table}",
            headers=self._headers("resolution=merge-duplicates,return=representation"),
            params={"on_conflict": on_conflict},
            json=rows,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 4: Verify tests pass**

Run:

```bash
python -m pytest tests/test_market_infra_supabase_writer.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit the writer**

Run:

```bash
git add market_infra/supabase_writer.py tests/test_market_infra_supabase_writer.py
git commit -m "feat: add supabase market writer"
```

---

### Task 5: Add a manual PropLine shadow ingest script

**Files:**
- Create: `scripts/shadow_propline_to_supabase.py`

- [ ] **Step 1: Create the script**

Create `scripts/shadow_propline_to_supabase.py`:

```python
"""Write PropLine pitcher strikeout observations to Supabase sidecar tables.

This script is observation-only. It must not update today.json, picks_history,
dashboard artifacts, or production pipeline outputs.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))

from fetch_odds import PROPLINE_MARKET_KEY, PROPLINE_SPORT_KEY, _the_odds_event_date_phoenix, propline_get  # noqa: E402
from market_infra.prop_snapshot import snapshots_from_propline_event  # noqa: E402
from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: python scripts/shadow_propline_to_supabase.py YYYY-MM-DD", file=sys.stderr)
        return 2

    slate_date = sys.argv[1]
    observed_at = datetime.now(timezone.utc).isoformat()
    writer = SupabaseMarketWriter(_env("SUPABASE_URL"), _env("SUPABASE_SERVICE_ROLE_KEY"))

    run_rows = writer.insert_rows("market_provider_runs", [{
        "provider": "propline",
        "mode": "shadow_poll",
        "slate_date": slate_date,
        "status": "started",
        "metadata": {"script": "scripts/shadow_propline_to_supabase.py"},
    }])
    run_id = run_rows[0]["id"]

    request_count = 1
    books_seen: set[str] = set()
    event_rows: list[dict] = []
    snapshots: list[dict] = []
    target_events = []

    try:
        events = propline_get(f"/sports/{PROPLINE_SPORT_KEY}/events")
        if not isinstance(events, list):
            events = []
        target_events = [event for event in events if _the_odds_event_date_phoenix(event) == slate_date]

        for event in target_events:
            event_id = event.get("id")
            if not event_id:
                continue
            event_rows.append({
                "provider": "propline",
                "provider_event_id": str(event_id),
                "sport_key": event.get("sport_key") or PROPLINE_SPORT_KEY,
                "slate_date": slate_date,
                "commence_time": event.get("commence_time"),
                "home_team": event.get("home_team"),
                "away_team": event.get("away_team"),
                "raw_event": event,
                "last_seen_at": observed_at,
            })
            request_count += 1
            odds = propline_get(
                f"/sports/{PROPLINE_SPORT_KEY}/events/{event_id}/odds",
                params={"markets": PROPLINE_MARKET_KEY},
            )
            if not isinstance(odds, dict):
                continue
            for bookmaker in odds.get("bookmakers", []):
                if bookmaker.get("key"):
                    books_seen.add(str(bookmaker["key"]))
            for row in snapshots_from_propline_event(odds, observed_at=observed_at):
                row["run_id"] = run_id
                snapshots.append(row)

        writer.upsert_rows("market_events", event_rows, on_conflict="provider,provider_event_id")
        writer.upsert_rows("market_snapshots", snapshots, on_conflict="dedupe_key")
        writer.insert_rows("provider_coverage_audits", [{
            "run_id": run_id,
            "slate_date": slate_date,
            "provider": "propline",
            "target_books": ["draftkings", "fanduel", "betrivers", "kalshi"],
            "books_seen": sorted(books_seen),
            "target_event_count": len(target_events),
            "parsed_pitcher_prop_count": len({(s["normalized_player_name"], s["line"]) for s in snapshots}),
            "complete_pitcher_line_groups": len({(s["normalized_player_name"], s["line"], s["bookmaker_key"]) for s in snapshots}),
            "metadata": {"snapshot_rows": len(snapshots), "observed_at": observed_at},
        }])
        writer.upsert_rows("market_provider_runs", [{
            "id": run_id,
            "provider": "propline",
            "mode": "shadow_poll",
            "slate_date": slate_date,
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "request_count": request_count,
            "target_event_count": len(target_events),
            "parsed_pitcher_prop_count": len({(s["normalized_player_name"], s["line"]) for s in snapshots}),
            "books_seen": sorted(books_seen),
        }], on_conflict="id")
    except Exception as exc:
        writer.upsert_rows("market_provider_runs", [{
            "id": run_id,
            "provider": "propline",
            "mode": "shadow_poll",
            "slate_date": slate_date,
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "request_count": request_count,
            "target_event_count": len(target_events),
            "parsed_pitcher_prop_count": len({(s["normalized_player_name"], s["line"]) for s in snapshots}),
            "books_seen": sorted(books_seen),
            "error_message": str(exc)[:1000],
        }], on_conflict="id")
        raise

    print(
        f"PropLine shadow ingest date={slate_date} "
        f"events={len(target_events)} snapshots={len(snapshots)} books={','.join(sorted(books_seen)) or 'none'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run syntax check**

Run:

```bash
python -m py_compile scripts/shadow_propline_to_supabase.py
```

Expected: no output.

- [ ] **Step 3: Confirm this script is not connected to production**

Run:

```bash
git diff -- .github/workflows/pipeline.yml pipeline/fetch_odds.py pipeline/run_pipeline.py dashboard
```

Expected: no output.

- [ ] **Step 4: Commit the manual ingest script**

Run:

```bash
git add scripts/shadow_propline_to_supabase.py
git commit -m "feat: add manual propline shadow ingest"
```

---

### Task 6: Add a dormant PropLine webhook receiver

**Files:**
- Modify: `.gitignore`
- Create: `supabase/config.toml`
- Create: `supabase/functions/propline-webhook/index.ts`
- Create: `supabase/functions/propline-webhook/README.md`

- [ ] **Step 1: Initialize Supabase config without inventing a remote project id**

If `supabase/config.toml` does not exist, run:

```bash
supabase init
```

Then add this block to `supabase/config.toml`:

```toml
[functions.propline-webhook]
verify_jwt = false
```

Reason: PropLine will not send a Supabase user JWT. The function must verify PropLine's HMAC signature instead.

Do not hard-code a fake `project_id`. Link a real remote project later with the Supabase CLI only after the user confirms which Supabase project to use.

If `.gitignore` does not already include `supabase/.env`, add:

```gitignore
supabase/.env
```

- [ ] **Step 2: Create the webhook receiver**

Create `supabase/functions/propline-webhook/index.ts`:

```typescript
import { createClient } from "npm:@supabase/supabase-js@2";

const encoder = new TextEncoder();

function hex(buffer: ArrayBuffer): string {
  return [...new Uint8Array(buffer)]
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

async function hmacSha256(secret: string, timestamp: string, body: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    encoder.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    encoder.encode(`${timestamp}.${body}`),
  );
  return hex(signature);
}

function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i += 1) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}

Deno.serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 });
  }

  const secret = Deno.env.get("PROPLINE_WEBHOOK_SECRET");
  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!secret || !supabaseUrl || !serviceRoleKey) {
    return new Response("Webhook receiver not configured", { status: 500 });
  }

  const propLineEvent = req.headers.get("X-PropLine-Event") ?? "";
  const timestamp = req.headers.get("X-PropLine-Timestamp") ?? "";
  const signature = req.headers.get("X-PropLine-Signature") ?? "";
  const deliveryId = req.headers.get("X-PropLine-Delivery") ?? "";
  const body = await req.text();

  if (!propLineEvent || !timestamp || !signature || !deliveryId) {
    return new Response("Missing PropLine headers", { status: 400 });
  }

  const timestampSeconds = Number(timestamp);
  if (!Number.isFinite(timestampSeconds) || timestampSeconds <= 0) {
    return new Response("Invalid PropLine timestamp", { status: 400 });
  }
  const propLineTimestamp = new Date(timestampSeconds * 1000).toISOString();

  const expected = await hmacSha256(secret, timestamp, body);
  const signatureValid = timingSafeEqual(expected, signature);
  let payload: Record<string, unknown>;
  try {
    payload = JSON.parse(body);
  } catch {
    payload = { raw_body_parse_error: true };
  }

  const supabase = createClient(supabaseUrl, serviceRoleKey, {
    auth: { persistSession: false },
  });

  const { error } = await supabase
    .from("propline_webhook_deliveries")
    .upsert({
      prop_line_delivery_id: deliveryId,
      prop_line_event: propLineEvent,
      prop_line_timestamp: propLineTimestamp,
      signature_valid: signatureValid,
      payload,
      processed: false,
      processing_error: signatureValid ? null : "invalid_signature",
    }, { onConflict: "prop_line_delivery_id" });

  if (error) {
    return new Response("Failed to store delivery", { status: 500 });
  }

  if (!signatureValid) {
    return new Response("Invalid signature", { status: 401 });
  }

  return Response.json({ ok: true, deliveryId });
});
```

- [ ] **Step 3: Add receiver README**

Create `supabase/functions/propline-webhook/README.md`:

```markdown
# PropLine Webhook Receiver

Observation-only receiver for future PropLine line-movement and resolution webhooks.

This function is dormant until the user approves a PropLine Streaming or Streaming Lite tier.

Required secrets:

- `PROPLINE_WEBHOOK_SECRET`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

Security model:

- Supabase JWT verification is disabled because PropLine does not send Supabase JWTs.
- The receiver verifies `X-PropLine-Signature` with HMAC-SHA256.
- `X-PropLine-Delivery` is used as the dedupe key.
- The function stores raw payloads only. It does not alter production picks, dashboard JSON, notifications, or grading.
```

- [ ] **Step 4: Verify function syntax**

Run:

```bash
supabase functions serve propline-webhook --env-file supabase/.env
```

Expected: function starts locally.

In another terminal, send a deliberately unsigned request:

```bash
curl -i -X POST http://127.0.0.1:54321/functions/v1/propline-webhook -d '{}'
```

Expected: `400 Missing PropLine headers`.

- [ ] **Step 5: Commit the dormant receiver**

Run:

```bash
git add supabase/config.toml supabase/functions/propline-webhook
git commit -m "feat: add dormant propline webhook receiver"
```

---

### Task 7: Add a Monday decision checklist for migration readiness

**Files:**
- Modify: `docs/superpowers/plans/2026-05-01-propline-supabase-market-infrastructure.md`

- [ ] **Step 1: Use this Monday decision checklist**

At the Monday 2026-05-04 review, do not migrate just because the code exists. Require evidence:

```markdown
## Monday 2026-05-04 Migration Decision

- PropLine returned DraftKings pitcher K props: yes/no
- PropLine returned FanDuel pitcher K props: yes/no
- PropLine returned BetRivers pitcher K props: yes/no
- PropLine returned useful Kalshi markets: yes/no
- PropLine pitcher coverage vs MLB probables: X/Y
- PropLine same-line overlap with TheRundown: X
- PropLine line conflicts with TheRundown: X
- The Odds fallback still useful enough to keep: yes/no
- TheRundown FD/DK coverage issue repeated: yes/no
- Free/Hobby request limits sufficient for polling: yes/no
- Streaming Lite webhook value justified by line-movement/resolution use case: yes/no
- Recommendation: keep shadow only / use PropLine fallback / migrate polling / enable webhooks / defer
```

- [ ] **Step 2: Explicitly record no-go conditions**

Add:

```markdown
No-go conditions:

- PropLine misses either DraftKings or FanDuel pitcher strikeout coverage on most games.
- PropLine pitcher names do not match MLB probable starters cleanly enough.
- PropLine returns too many line conflicts without a clear source-of-truth rule.
- PropLine cannot stay inside the selected request tier.
- Supabase ingestion has not been verified with real inserted rows and RLS enabled.
- The branch changes any production pipeline path before approval.
```

- [ ] **Step 3: Commit the checklist update**

Run:

```bash
git add docs/superpowers/plans/2026-05-01-propline-supabase-market-infrastructure.md
git commit -m "docs: add propline migration decision checklist"
```

---

## Verification Before Merge

Run:

```bash
python -m pytest tests/test_market_infra_prop_snapshot.py tests/test_market_infra_supabase_writer.py -v
python -m py_compile scripts/shadow_propline_to_supabase.py
git diff -- .github/workflows/pipeline.yml pipeline/fetch_odds.py pipeline/run_pipeline.py dashboard
```

Expected:

- Tests pass.
- Script compiles.
- Production diff command has no output.

If Supabase local runtime is available, also run:

```bash
supabase db reset
supabase functions serve propline-webhook --env-file supabase/.env
```

Expected:

- Migration applies.
- Function starts.
- Missing-header test request returns 400.

## Business Decision After This Plan

This branch only earns the right to continue if it proves Supabase can store market observations safely.

It does not decide whether to switch away from TheRundown. That decision waits for the Monday provider review.

Possible Monday outcomes:

- **PropLine fails coverage:** Keep Supabase infrastructure as a general market-history foundation, but do not migrate providers.
- **PropLine works for FD/DK only:** Use it as a fallback or shadow provider first.
- **PropLine works for FD/DK/BetRivers/Kalshi and request economics work:** Plan a production polling migration.
- **PropLine works and webhook tier is worth it:** Plan webhook activation as a separate branch, with notifications integration only after raw webhook delivery storage is proven.
