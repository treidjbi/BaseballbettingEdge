# Live Layer Event System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a scalable live layer that detects meaningful pick and line-movement changes every 5-10 minutes, stores them in Supabase, and sends deduped, timely notifications without changing the official grading pipeline.

**Architecture:** GitHub Actions remains the book-of-record runner for preview, full, grading, calibration, and archive commits. Supabase becomes the append-only live event/state layer for market snapshots, live pick state, notification dedupe, reminders, and webhook processing. A small Python-friendly worker runs more frequently than the main pipeline, writes live events to Supabase, and lets Netlify handle push delivery and dashboard API reads.

**Tech Stack:** Python 3.11, pytest, Supabase Postgres + REST, existing `market_infra` helpers, Netlify Functions, Netlify Blobs for existing subscriptions only, optional Render Cron for the live worker after the GitHub shadow proof.

**Status Note 2026-05-07:** The live layer is active on Render as
`bbe-live-layer`, using fresh GitHub raw `today.json`, PropLine polling when
configured, Supabase live tables, and Netlify `send-live-notifications`. It is
still separate from dashboard artifacts, grading, picks history, calibration,
and production provider order.

---

## Product Intent

The current dashboard is useful, but it still feels batch-oriented. The live layer should make the app feel like a betting assistant that notices important changes while preserving the slower, safer model pipeline.

Target user-facing events:

- New FIRE pick appears.
- LEAN upgrades to FIRE.
- FIRE 1u upgrades to FIRE 2u.
- FIRE pick downgrades or disappears before lock.
- Line moves with the model side.
- Line moves against the model side.
- Odds improve enough to make a pick newly actionable.
- Game reminder fires at a useful cadence instead of batching 20 reminders at once.
- PropLine webhook arrives and is processed into the same event system.

Non-goals for v1:

- Do not change `today.json` output semantics.
- Do not change verdict thresholds.
- Do not change grading or calibration.
- Do not make PropLine the primary provider.
- Do not use TheRundown for high-frequency live polling.
- Do not expose service-role Supabase credentials to the dashboard.
- Do not replace the existing static dashboard data path until the live layer proves stable.

Provider cost guardrail:

- TheRundown Starter should remain the official book-of-record source for scheduled preview, full, refresh, grading-adjacent artifacts, and archives.
- The live worker must not poll TheRundown every 5-10 minutes for market movement. That usage pattern can exceed the current TheRundown Starter data-point allowance on normal MLB slates.
- PropLine Streaming Lite is the preferred live movement source because its plan is designed around frequent requests, line-movement webhooks, and resolution delivery.
- The live layer should read TheRundown-derived picks from `today.json`, then compare those picks against PropLine snapshots/webhook events for live movement and notification decisions.
- Any future TheRundown live polling beyond the existing pipeline cadence requires a separate cost/usage review and explicit approval.

---

## Long-Term Product Direction

The live layer should support three future product modes without rewrites:

1. **Operator Mode**
   - What should Tyler look at right now?
   - Examples: new FIRE, upgraded FIRE, line moved against us, game starting soon.

2. **Audit Mode**
   - Why did this pick change?
   - Examples: odds moved, lineup confirmed, umpire became known, market source changed.

3. **Learning Mode**
   - Did live signals help over time?
   - Examples: CLV by provider, movement-with-us performance, notification-to-result review, stale-line miss analysis.

This is why Supabase is the right state layer: event history and dedupe matter more than raw file storage. The main pipeline should stay boring and official; the live layer can be fast, additive, and disposable if needed.

---

## Current Foundation

Already present:

- `supabase/migrations/20260501193409_market_infrastructure.sql`
  - `market_provider_runs`
  - `market_events`
  - `market_snapshots`
  - `provider_coverage_audits`
  - `propline_webhook_deliveries`
  - `artifact_snapshots`
- `scripts/shadow_propline_to_supabase.py`
  - Polls PropLine and writes normalized market snapshots.
- `scripts/shadow_artifacts_to_supabase.py`
  - Captures immutable JSON artifacts.
- `.github/workflows/shadow-market-infra.yml`
  - Runs observation-only PropLine shadow polling every 10 minutes.
- `netlify/functions/propline-webhook.mjs`
  - Receives signed PropLine webhook deliveries and stores raw inbox rows.
- `netlify/functions/send-notifications.mjs`
  - Sends push notifications from static `today.json` changes and stores notification state in Netlify Blobs.

Main gaps:

- No durable `live_pick_state`.
- No normalized `line_movement_events`.
- No durable `notification_events`.
- No `game_reminder_state`.
- Webhook deliveries are stored but not processed.
- Dashboard has no read-safe live feed.
- Notification dedupe is split between Netlify Blobs and future Supabase state.

---

## File Structure

Create:

- `supabase/migrations/20260506_live_layer_events.sql`
  - Adds live event/state tables and read-safe views.
- `market_infra/live_events.py`
  - Pure Python detection logic for pick changes, movement events, reminders, and notification rows.
- `scripts/build_live_events_to_supabase.py`
  - Worker entrypoint that reads latest artifacts + Supabase snapshots and writes live state/events.
- `scripts/process_propline_webhooks.py`
  - Processes valid webhook inbox rows into normalized market snapshots or movement events.
- `netlify/functions/live-events.mjs`
  - Read-only dashboard API for recent live events.
- `netlify/functions/send-live-notifications.mjs`
  - Sends unsent Supabase notification events to push subscribers.
- `tests/test_market_infra_live_events.py`
  - Unit tests for event detection.
- `tests/test_live_layer_worker.py`
  - Tests worker row construction and writer calls without network.
- `tests/test_process_propline_webhooks.py`
  - Tests webhook processing behavior.
- `tests/test_netlify_live_events.mjs`
  - Tests public API filtering and secret handling if the repo keeps Node tests.

Modify:

- `.github/workflows/shadow-market-infra.yml`
  - Add an optional `build_live_events` dispatch flag and a scheduled proof run.
- `netlify/functions/package.json`
  - Add a Node test script only if Netlify function tests are introduced.
- `netlify/functions/send-notifications.mjs`
  - Later phase only: either leave as book-of-record fallback or reduce duplicate logic after Supabase live notifications prove stable.
- `docs/current-state.md`
  - Add live-layer operating mode after implementation is accepted.

Do not modify:

- `pipeline/run_pipeline.py`
- `pipeline/build_features.py`
- `data/picks_history.json`
- `dashboard/data/processed/today.json` schema

---

## Data Model

### `live_pick_state`

One current row per slate/pitcher/side.

```sql
create table if not exists public.live_pick_state (
  id uuid primary key default gen_random_uuid(),
  slate_date date not null,
  pitcher text not null,
  normalized_pitcher text not null,
  side text not null check (side in ('over', 'under')),
  current_verdict text not null,
  previous_verdict text,
  k_line numeric not null,
  current_odds integer,
  current_book text,
  game_time timestamptz,
  game_state text,
  is_fire boolean not null default false,
  is_locked boolean not null default false,
  source_artifact_path text not null,
  source_artifact_sha256 text,
  last_model_seen_at timestamptz not null default now(),
  last_event_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (slate_date, normalized_pitcher, side)
);
```

### `line_movement_events`

Append-only movement facts.

```sql
create table if not exists public.line_movement_events (
  id uuid primary key default gen_random_uuid(),
  slate_date date not null,
  normalized_pitcher text not null,
  pitcher text not null,
  side text not null check (side in ('over', 'under')),
  bookmaker_key text not null,
  previous_line numeric,
  current_line numeric not null,
  previous_odds integer,
  current_odds integer not null,
  movement_direction text not null check (
    movement_direction in ('with_model', 'against_model', 'neutral')
  ),
  movement_kind text not null check (
    movement_kind in ('line', 'odds', 'line_and_odds')
  ),
  observed_at timestamptz not null,
  dedupe_key text not null unique,
  source_snapshot_id uuid,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
```

### `notification_events`

Durable, deduped notification queue.

```sql
create table if not exists public.notification_events (
  id uuid primary key default gen_random_uuid(),
  slate_date date,
  event_type text not null check (
    event_type in (
      'new_fire_pick',
      'pick_upgraded',
      'pick_downgraded',
      'line_moved_with_us',
      'line_moved_against_us',
      'game_reminder_due',
      'webhook_received',
      'source_degraded'
    )
  ),
  severity text not null default 'info' check (severity in ('info', 'watch', 'action')),
  title text not null,
  body text not null,
  url text not null default '/',
  dedupe_key text not null unique,
  payload jsonb not null default '{}'::jsonb,
  occurred_at timestamptz not null default now(),
  sent_at timestamptz,
  send_attempts integer not null default 0 check (send_attempts >= 0),
  last_send_error text,
  created_at timestamptz not null default now()
);
```

### `game_reminder_state`

One row per pick/reminder window.

```sql
create table if not exists public.game_reminder_state (
  id uuid primary key default gen_random_uuid(),
  slate_date date not null,
  normalized_pitcher text not null,
  side text not null check (side in ('over', 'under')),
  reminder_window text not null check (
    reminder_window in ('75_min', '45_min', '25_min', '10_min')
  ),
  game_time timestamptz not null,
  due_at timestamptz not null,
  fired_at timestamptz,
  dedupe_key text not null unique,
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now()
);
```

### Read-safe view

```sql
create or replace view public.live_activity_feed as
select
  id,
  slate_date,
  event_type,
  severity,
  title,
  body,
  url,
  occurred_at,
  payload
from public.notification_events
where occurred_at >= now() - interval '36 hours'
order by occurred_at desc;
```

Security rule:

- Keep tables service-role only at first.
- Expose dashboard reads through `netlify/functions/live-events.mjs`.
- Add direct Supabase read policies only after the dashboard API shape stabilizes.

---

## Event Rules

### Pick upgrade rules

Verdict rank:

```python
VERDICT_RANK = {
    "PASS": 0,
    "LEAN": 1,
    "FIRE 1u": 2,
    "FIRE 2u": 3,
}
```

Emit:

- `new_fire_pick` when no previous state exists and current verdict is FIRE.
- `pick_upgraded` when current rank is greater than previous rank and current verdict is FIRE.
- `pick_downgraded` when previous verdict was FIRE and current verdict is lower.

Do not emit:

- PASS to LEAN.
- LEAN to PASS.
- Any change after the pick is locked.

### Movement rules

For a model side:

- Over likes lower line and better over odds.
- Under likes higher line and better under odds.
- Line movement is more important than odds-only movement.

Emit:

- `line_moved_with_us` when the current line/odds improves relative to the previous market snapshot for the same pitcher/book/side.
- `line_moved_against_us` when the current line/odds worsens relative to the previous snapshot.

Do not emit:

- Movement smaller than 10 American odds points when line is unchanged.
- Movement for PASS picks.
- Repeated movement with the same `dedupe_key`.

### Reminder rules

Use smaller windows than the current broad 5-75 minute reminder logic.

Recommended v1:

- FIRE 2u: 45 minutes and 10 minutes.
- FIRE 1u: 25 minutes.
- LEAN: no push reminder by default; visible in dashboard feed only.

This avoids the current "20 at a time" behavior while preserving useful urgency.

---

## Runtime Recommendation

### Phase 1 runtime

Use GitHub Actions shadow workflow for proof because secrets already exist and it is low-friction.

Cadence:

- Every 10 minutes during the MLB betting window.
- Observation-only.
- PropLine-only market polling for live movement.
- No TheRundown high-frequency polling.
- Writes Supabase events.
- Does not call Netlify live notification sender automatically until event quality is reviewed.

### Phase 2 runtime

Move the live worker to Render Cron if Phase 1 proves useful.

Why Render first:

- Python-native.
- Reuses existing parsing and artifact code.
- Easier than rewriting the live worker in TypeScript.
- Cheap enough for a pet project.
- More predictable than GitHub schedule queues for frequent refreshes.

Cloudflare Worker remains a good later option if the worker becomes mostly HTTP fetch + normalization in TypeScript.

Supabase Edge Functions should stay optional. They are useful for webhook processing, but not ideal for Python-heavy market/model logic.

---

## Hard Pause Checkpoints

Pause after Task 2:

- Confirm event rows look right before enabling push delivery.
- Review whether event volume is useful or noisy.

Pause after Task 4:

- Confirm notification copy, dedupe, and pacing before live pushes.
- Decide whether LEAN reminders should exist at all.

Pause after Task 6:

- Decide whether to move worker runtime from GitHub Actions to Render Cron.

Pause before any production provider change:

- Keep the June 1 PropLine review checkpoint intact.
- Do not promote PropLine based only on live-layer convenience.
- Do not increase TheRundown polling cadence without a cost/usage review.

---

### Task 1: Add Supabase live-layer schema

**Files:**
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/supabase/migrations/20260506_live_layer_events.sql`
- Test: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/tests/test_live_layer_schema.py`

- [ ] **Step 1: Write schema assertions**

Create `tests/test_live_layer_schema.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "supabase" / "migrations" / "20260506_live_layer_events.sql"


def test_live_layer_migration_defines_required_tables():
    sql = MIGRATION.read_text(encoding="utf-8")

    for table in [
        "live_pick_state",
        "line_movement_events",
        "notification_events",
        "game_reminder_state",
    ]:
        assert f"create table if not exists public.{table}" in sql
        assert f"alter table public.{table} enable row level security" in sql


def test_live_layer_migration_uses_unique_dedupe_keys():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "dedupe_key text not null unique" in sql
    assert "unique (slate_date, normalized_pitcher, side)" in sql
    assert "create or replace view public.live_activity_feed" in sql
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_live_layer_schema.py -v
```

Expected: FAIL because the migration file does not exist.

- [ ] **Step 3: Create the migration**

Create `supabase/migrations/20260506_live_layer_events.sql` with the four table definitions and read-safe view from the Data Model section above. Add indexes:

```sql
create index if not exists idx_live_pick_state_slate
  on public.live_pick_state (slate_date desc, is_fire, updated_at desc);

create index if not exists idx_line_movement_events_slate
  on public.line_movement_events (slate_date desc, normalized_pitcher, observed_at desc);

create index if not exists idx_notification_events_unsent
  on public.notification_events (sent_at, occurred_at desc)
  where sent_at is null;

create index if not exists idx_game_reminder_state_due
  on public.game_reminder_state (due_at, fired_at)
  where fired_at is null;
```

Add RLS:

```sql
alter table public.live_pick_state enable row level security;
alter table public.line_movement_events enable row level security;
alter table public.notification_events enable row level security;
alter table public.game_reminder_state enable row level security;
```

Add comments that state these tables are live-layer sidecar state and not the official grading record.

- [ ] **Step 4: Run schema test**

Run:

```bash
python -m pytest tests/test_live_layer_schema.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add supabase/migrations/20260506_live_layer_events.sql tests/test_live_layer_schema.py
git commit -m "feat: add live layer schema"
```

---

### Task 2: Implement pure live event detection

**Files:**
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/market_infra/live_events.py`
- Test: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/tests/test_market_infra_live_events.py`

- [ ] **Step 1: Write tests for pick changes**

Create `tests/test_market_infra_live_events.py`:

```python
from datetime import datetime, timezone

from market_infra.live_events import build_pick_change_events


NOW = datetime(2026, 5, 6, 18, 0, tzinfo=timezone.utc)


def _pick(pitcher="Tarik Skubal", side="over", verdict="FIRE 1u", line=6.5):
    return {
        "pitcher": pitcher,
        "team": "DET",
        "opp_team": "BOS",
        "k_line": line,
        "game_time": "2026-05-06T22:10:00Z",
        "game_state": "scheduled",
        f"ev_{side}": {
            "verdict": verdict,
            "adj_ev": 0.09,
            "edge": 0.05,
        },
        f"best_{side}_odds": -110,
        f"best_{side}_book": "FanDuel",
    }


def test_new_fire_pick_emits_notification_event():
    events, state_rows = build_pick_change_events(
        slate_date="2026-05-06",
        pitchers=[_pick()],
        previous_state={},
        observed_at=NOW,
        source_artifact_path="dashboard/data/processed/today.json",
        source_artifact_sha256="abc",
    )

    assert state_rows[0]["current_verdict"] == "FIRE 1u"
    assert events == [{
        "slate_date": "2026-05-06",
        "event_type": "new_fire_pick",
        "severity": "action",
        "title": "New FIRE Pick",
        "body": "Tarik Skubal FIRE 1u OVER 6.5 Ks at FanDuel",
        "url": "/",
        "dedupe_key": "2026-05-06:new_fire_pick:tarik skubal:over:FIRE 1u:6.5",
        "payload": {
            "pitcher": "Tarik Skubal",
            "side": "over",
            "verdict": "FIRE 1u",
            "k_line": 6.5,
            "book": "FanDuel",
            "odds": -110,
        },
        "occurred_at": NOW.isoformat(),
    }]


def test_lean_to_fire_emits_upgrade_event():
    previous = {
        ("2026-05-06", "tarik skubal", "over"): {
            "current_verdict": "LEAN",
        }
    }

    events, _ = build_pick_change_events(
        slate_date="2026-05-06",
        pitchers=[_pick(verdict="FIRE 2u")],
        previous_state=previous,
        observed_at=NOW,
        source_artifact_path="dashboard/data/processed/today.json",
        source_artifact_sha256="abc",
    )

    assert events[0]["event_type"] == "pick_upgraded"
    assert events[0]["title"] == "Pick Upgraded"
    assert events[0]["payload"]["previous_verdict"] == "LEAN"
    assert events[0]["payload"]["verdict"] == "FIRE 2u"


def test_locked_pick_does_not_emit_upgrade_event():
    pick = _pick(verdict="FIRE 2u")
    pick["game_state"] = "in_progress"
    previous = {
        ("2026-05-06", "tarik skubal", "over"): {
            "current_verdict": "LEAN",
        }
    }

    events, _ = build_pick_change_events(
        slate_date="2026-05-06",
        pitchers=[pick],
        previous_state=previous,
        observed_at=NOW,
        source_artifact_path="dashboard/data/processed/today.json",
        source_artifact_sha256="abc",
    )

    assert events == []
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_market_infra_live_events.py -v
```

Expected: FAIL with `ModuleNotFoundError` for `market_infra.live_events`.

- [ ] **Step 3: Implement minimal pick event logic**

Create `market_infra/live_events.py`:

```python
from __future__ import annotations

from datetime import datetime

from name_utils import normalize


VERDICT_RANK = {
    "PASS": 0,
    "LEAN": 1,
    "FIRE 1u": 2,
    "FIRE 2u": 3,
}


def _is_locked(pitcher: dict) -> bool:
    return pitcher.get("game_state") in {"in_progress", "final"} or bool(pitcher.get("locked_at"))


def _side_row(pitcher: dict, side: str) -> dict | None:
    ev = pitcher.get(f"ev_{side}") or {}
    verdict = ev.get("verdict") or "PASS"
    if verdict == "PASS":
        return None
    book = pitcher.get(f"best_{side}_book") or pitcher.get("ref_book")
    odds = pitcher.get(f"best_{side}_odds")
    return {
        "side": side,
        "verdict": verdict,
        "book": book,
        "odds": odds,
        "adj_ev": ev.get("adj_ev"),
        "edge": ev.get("edge"),
    }


def build_pick_change_events(
    *,
    slate_date: str,
    pitchers: list[dict],
    previous_state: dict[tuple[str, str, str], dict],
    observed_at: datetime,
    source_artifact_path: str,
    source_artifact_sha256: str | None,
) -> tuple[list[dict], list[dict]]:
    events: list[dict] = []
    state_rows: list[dict] = []
    occurred_at = observed_at.isoformat()

    for pitcher in pitchers:
        normalized_pitcher = normalize(pitcher.get("pitcher") or "")
        if not normalized_pitcher:
            continue
        locked = _is_locked(pitcher)
        for side in ("over", "under"):
            side_row = _side_row(pitcher, side)
            if not side_row:
                continue
            verdict = side_row["verdict"]
            key = (slate_date, normalized_pitcher, side)
            previous = previous_state.get(key)
            previous_verdict = previous.get("current_verdict") if previous else None
            current_rank = VERDICT_RANK.get(verdict, 0)
            previous_rank = VERDICT_RANK.get(previous_verdict or "PASS", 0)
            is_fire = current_rank >= VERDICT_RANK["FIRE 1u"]
            k_line = pitcher.get("k_line")

            state_rows.append({
                "slate_date": slate_date,
                "pitcher": pitcher.get("pitcher"),
                "normalized_pitcher": normalized_pitcher,
                "side": side,
                "current_verdict": verdict,
                "previous_verdict": previous_verdict,
                "k_line": k_line,
                "current_odds": side_row["odds"],
                "current_book": side_row["book"],
                "game_time": pitcher.get("game_time"),
                "game_state": pitcher.get("game_state"),
                "is_fire": is_fire,
                "is_locked": locked,
                "source_artifact_path": source_artifact_path,
                "source_artifact_sha256": source_artifact_sha256,
                "last_model_seen_at": occurred_at,
                "metadata": {
                    "adj_ev": side_row["adj_ev"],
                    "edge": side_row["edge"],
                    "team": pitcher.get("team"),
                    "opp_team": pitcher.get("opp_team"),
                },
            })

            if locked or not is_fire:
                continue
            if previous is None:
                event_type = "new_fire_pick"
                title = "New FIRE Pick"
            elif current_rank > previous_rank:
                event_type = "pick_upgraded"
                title = "Pick Upgraded"
            else:
                continue

            events.append({
                "slate_date": slate_date,
                "event_type": event_type,
                "severity": "action",
                "title": title,
                "body": (
                    f"{pitcher.get('pitcher')} {verdict} "
                    f"{side.upper()} {k_line} Ks at {side_row['book']}"
                ),
                "url": "/",
                "dedupe_key": f"{slate_date}:{event_type}:{normalized_pitcher}:{side}:{verdict}:{k_line}",
                "payload": {
                    "pitcher": pitcher.get("pitcher"),
                    "side": side,
                    "previous_verdict": previous_verdict,
                    "verdict": verdict,
                    "k_line": k_line,
                    "book": side_row["book"],
                    "odds": side_row["odds"],
                },
                "occurred_at": occurred_at,
            })

    return events, state_rows
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_market_infra_live_events.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add market_infra/live_events.py tests/test_market_infra_live_events.py
git commit -m "feat: detect live pick events"
```

---

### Task 3: Add movement and reminder detection

**Files:**
- Modify: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/market_infra/live_events.py`
- Modify: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/tests/test_market_infra_live_events.py`

- [ ] **Step 1: Add movement tests**

Append to `tests/test_market_infra_live_events.py`:

```python
from market_infra.live_events import build_line_movement_events, build_reminder_events


def test_over_line_drop_is_with_model_movement():
    events = build_line_movement_events(
        slate_date="2026-05-06",
        live_picks=[{
            "pitcher": "Tarik Skubal",
            "normalized_pitcher": "tarik skubal",
            "side": "over",
            "current_verdict": "FIRE 1u",
        }],
        previous_snapshots=[{
            "normalized_player_name": "tarik skubal",
            "bookmaker_key": "fanduel",
            "line": 6.5,
            "american_odds": -110,
            "observed_at": "2026-05-06T17:50:00+00:00",
        }],
        current_snapshots=[{
            "id": "snapshot-1",
            "normalized_player_name": "tarik skubal",
            "player_name": "Tarik Skubal",
            "bookmaker_key": "fanduel",
            "line": 5.5,
            "american_odds": -112,
            "observed_at": "2026-05-06T18:00:00+00:00",
        }],
    )

    assert events[0]["event_type"] == "line_moved_with_us"
    assert events[0]["payload"]["movement_direction"] == "with_model"
    assert events[0]["dedupe_key"] == "2026-05-06:line:fanduel:tarik skubal:over:6.5:-110:5.5:-112"


def test_under_line_drop_is_against_model_movement():
    events = build_line_movement_events(
        slate_date="2026-05-06",
        live_picks=[{
            "pitcher": "Tarik Skubal",
            "normalized_pitcher": "tarik skubal",
            "side": "under",
            "current_verdict": "FIRE 1u",
        }],
        previous_snapshots=[{
            "normalized_player_name": "tarik skubal",
            "bookmaker_key": "fanduel",
            "line": 6.5,
            "american_odds": -110,
            "observed_at": "2026-05-06T17:50:00+00:00",
        }],
        current_snapshots=[{
            "id": "snapshot-1",
            "normalized_player_name": "tarik skubal",
            "player_name": "Tarik Skubal",
            "bookmaker_key": "fanduel",
            "line": 5.5,
            "american_odds": -112,
            "observed_at": "2026-05-06T18:00:00+00:00",
        }],
    )

    assert events[0]["event_type"] == "line_moved_against_us"
    assert events[0]["payload"]["movement_direction"] == "against_model"


def test_fire_1u_gets_25_minute_reminder_only():
    events, rows = build_reminder_events(
        slate_date="2026-05-06",
        live_picks=[{
            "pitcher": "Tarik Skubal",
            "normalized_pitcher": "tarik skubal",
            "side": "over",
            "current_verdict": "FIRE 1u",
            "k_line": 6.5,
            "game_time": "2026-05-06T18:25:00+00:00",
            "is_locked": False,
        }],
        existing_reminders=set(),
        observed_at=NOW,
    )

    assert rows[0]["reminder_window"] == "25_min"
    assert events[0]["event_type"] == "game_reminder_due"
    assert events[0]["dedupe_key"] == "2026-05-06:reminder:25_min:tarik skubal:over"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_market_infra_live_events.py -v
```

Expected: FAIL because movement and reminder functions are not defined.

- [ ] **Step 3: Implement movement and reminder functions**

Add functions to `market_infra/live_events.py`:

```python
def build_line_movement_events(
    *,
    slate_date: str,
    live_picks: list[dict],
    previous_snapshots: list[dict],
    current_snapshots: list[dict],
) -> list[dict]:
    actionable = {
        (row["normalized_pitcher"], row["side"]): row
        for row in live_picks
        if VERDICT_RANK.get(row.get("current_verdict", "PASS"), 0) >= VERDICT_RANK["FIRE 1u"]
    }
    previous_by_book_player = {
        (row["bookmaker_key"], row["normalized_player_name"]): row
        for row in previous_snapshots
    }
    events: list[dict] = []

    for snapshot in current_snapshots:
        normalized = snapshot.get("normalized_player_name")
        book = snapshot.get("bookmaker_key")
        previous = previous_by_book_player.get((book, normalized))
        if not previous:
            continue
        for side in ("over", "under"):
            pick = actionable.get((normalized, side))
            if not pick:
                continue
            previous_line = float(previous["line"])
            current_line = float(snapshot["line"])
            previous_odds = int(previous["american_odds"])
            current_odds = int(snapshot["american_odds"])
            if previous_line == current_line and abs(current_odds - previous_odds) < 10:
                continue

            line_delta = current_line - previous_line
            odds_delta = current_odds - previous_odds
            if side == "over":
                with_model = line_delta < 0 or (line_delta == 0 and odds_delta > 0)
            else:
                with_model = line_delta > 0 or (line_delta == 0 and odds_delta > 0)

            direction = "with_model" if with_model else "against_model"
            event_type = "line_moved_with_us" if with_model else "line_moved_against_us"
            movement_kind = "line_and_odds" if previous_line != current_line and previous_odds != current_odds else (
                "line" if previous_line != current_line else "odds"
            )
            dedupe_key = (
                f"{slate_date}:line:{book}:{normalized}:{side}:"
                f"{previous_line:g}:{previous_odds}:{current_line:g}:{current_odds}"
            )
            events.append({
                "slate_date": slate_date,
                "event_type": event_type,
                "severity": "watch" if with_model else "action",
                "title": "Line Moved With Us" if with_model else "Line Moved Against Us",
                "body": (
                    f"{pick['pitcher']} {side.upper()} moved "
                    f"{previous_line:g} to {current_line:g} at {book}"
                ),
                "url": "/",
                "dedupe_key": dedupe_key,
                "payload": {
                    "pitcher": pick["pitcher"],
                    "side": side,
                    "bookmaker_key": book,
                    "previous_line": previous_line,
                    "current_line": current_line,
                    "previous_odds": previous_odds,
                    "current_odds": current_odds,
                    "movement_direction": direction,
                    "movement_kind": movement_kind,
                    "source_snapshot_id": snapshot.get("id"),
                },
                "occurred_at": snapshot["observed_at"],
            })

    return events


def build_reminder_events(
    *,
    slate_date: str,
    live_picks: list[dict],
    existing_reminders: set[str],
    observed_at: datetime,
) -> tuple[list[dict], list[dict]]:
    events: list[dict] = []
    rows: list[dict] = []
    windows = {
        "FIRE 2u": [("45_min", 45), ("10_min", 10)],
        "FIRE 1u": [("25_min", 25)],
    }

    for pick in live_picks:
        if pick.get("is_locked") or not pick.get("game_time"):
            continue
        verdict = pick.get("current_verdict")
        for window_name, minutes in windows.get(verdict, []):
            game_time = datetime.fromisoformat(str(pick["game_time"]).replace("Z", "+00:00"))
            minutes_to_game = (game_time - observed_at).total_seconds() / 60
            if minutes_to_game < 0 or minutes_to_game > minutes:
                continue
            if minutes_to_game < max(0, minutes - 10):
                continue
            dedupe_key = f"{slate_date}:reminder:{window_name}:{pick['normalized_pitcher']}:{pick['side']}"
            if dedupe_key in existing_reminders:
                continue
            rows.append({
                "slate_date": slate_date,
                "normalized_pitcher": pick["normalized_pitcher"],
                "side": pick["side"],
                "reminder_window": window_name,
                "game_time": game_time.isoformat(),
                "due_at": observed_at.isoformat(),
                "fired_at": observed_at.isoformat(),
                "dedupe_key": dedupe_key,
                "metadata": {"verdict": verdict, "pitcher": pick["pitcher"]},
            })
            events.append({
                "slate_date": slate_date,
                "event_type": "game_reminder_due",
                "severity": "action",
                "title": "Pick Starts Soon",
                "body": f"{pick['pitcher']} {verdict} {pick['side'].upper()} {pick['k_line']} Ks",
                "url": "/",
                "dedupe_key": dedupe_key,
                "payload": {
                    "pitcher": pick["pitcher"],
                    "side": pick["side"],
                    "verdict": verdict,
                    "k_line": pick["k_line"],
                    "game_time": game_time.isoformat(),
                    "reminder_window": window_name,
                },
                "occurred_at": observed_at.isoformat(),
            })

    return events, rows
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_market_infra_live_events.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add market_infra/live_events.py tests/test_market_infra_live_events.py
git commit -m "feat: detect line movement and reminders"
```

---

### Task 4: Add Supabase live event worker

**Files:**
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/scripts/build_live_events_to_supabase.py`
- Test: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/tests/test_live_layer_worker.py`
- Modify: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/market_infra/supabase_writer.py`

- [ ] **Step 1: Add writer read helper tests**

Append to `tests/test_market_infra_supabase_writer.py`:

```python
def test_select_rows_passes_query_params():
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = [{"current_verdict": "FIRE 1u"}]

    with patch("market_infra.supabase_writer.requests.get", return_value=response) as get:
        result = writer.select_rows("live_pick_state", {"slate_date": "eq.2026-05-06"})

    assert result == [{"current_verdict": "FIRE 1u"}]
    assert get.call_args.kwargs["params"] == {"slate_date": "eq.2026-05-06"}
    assert get.call_args.kwargs["headers"]["Authorization"] == "Bearer secret-key"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_market_infra_supabase_writer.py -v
```

Expected: FAIL because `select_rows` does not exist.

- [ ] **Step 3: Implement `select_rows`**

Add to `market_infra/supabase_writer.py`:

```python
    def select_rows(self, table: str, params: dict[str, str]) -> list[dict]:
        response = requests.get(
            f"{self.supabase_url}/rest/v1/{table}",
            headers=self._headers("return=representation"),
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 4: Add worker tests**

Create `tests/test_live_layer_worker.py`:

```python
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import build_live_events_to_supabase


def test_worker_writes_state_and_notification_events(tmp_path):
    today = tmp_path / "today.json"
    today.write_text(
        """
        {
          "date": "2026-05-06",
          "pitchers": [
            {
              "pitcher": "Tarik Skubal",
              "team": "DET",
              "opp_team": "BOS",
              "k_line": 6.5,
              "game_time": "2026-05-06T22:10:00Z",
              "game_state": "scheduled",
              "best_over_odds": -110,
              "best_over_book": "FanDuel",
              "ev_over": {"verdict": "FIRE 1u", "adj_ev": 0.09, "edge": 0.05}
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    writer = Mock()
    writer.select_rows.side_effect = [
        [],
        [],
        [],
        [],
    ]

    with patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["notification_events"] == 1
    writer.upsert_rows.assert_any_call(
        "live_pick_state",
        result["state_rows"],
        on_conflict="slate_date,normalized_pitcher,side",
    )
    writer.upsert_rows.assert_any_call(
        "notification_events",
        result["notification_rows"],
        on_conflict="dedupe_key",
    )
```

- [ ] **Step 5: Run worker test to verify it fails**

Run:

```bash
python -m pytest tests/test_live_layer_worker.py -v
```

Expected: FAIL because `scripts/build_live_events_to_supabase.py` does not exist.

- [ ] **Step 6: Implement worker entrypoint**

Create `scripts/build_live_events_to_supabase.py`:

```python
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))

from market_infra.live_events import build_pick_change_events  # noqa: E402
from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _previous_state(rows: list[dict]) -> dict[tuple[str, str, str], dict]:
    return {
        (row["slate_date"], row["normalized_pitcher"], row["side"]): row
        for row in rows
    }


def run(
    *,
    slate_date: str,
    artifact_path: Path,
    supabase_url: str,
    service_role_key: str,
) -> dict:
    payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    writer = SupabaseMarketWriter(supabase_url, service_role_key)
    previous_rows = writer.select_rows("live_pick_state", {"slate_date": f"eq.{slate_date}"})

    notification_rows, state_rows = build_pick_change_events(
        slate_date=slate_date,
        pitchers=payload.get("pitchers") or [],
        previous_state=_previous_state(previous_rows),
        observed_at=datetime.now(timezone.utc),
        source_artifact_path=str(artifact_path.relative_to(ROOT)).replace("\\", "/"),
        source_artifact_sha256=_sha256(artifact_path),
    )

    writer.upsert_rows("live_pick_state", state_rows, on_conflict="slate_date,normalized_pitcher,side")
    writer.upsert_rows("notification_events", notification_rows, on_conflict="dedupe_key")
    return {
        "state_rows": state_rows,
        "notification_rows": notification_rows,
        "live_pick_state": len(state_rows),
        "notification_events": len(notification_rows),
    }


def main() -> int:
    slate_date = sys.argv[1] if len(sys.argv) > 1 else ""
    artifact = ROOT / "dashboard" / "data" / "processed" / "today.json"
    if not slate_date:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        slate_date = payload["date"]
    result = run(
        slate_date=slate_date,
        artifact_path=artifact,
        supabase_url=_env("SUPABASE_URL"),
        service_role_key=_env("SUPABASE_SERVICE_ROLE_KEY"),
    )
    print(
        "Live event build "
        f"date={slate_date} state_rows={result['live_pick_state']} "
        f"notification_events={result['notification_events']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Run focused tests**

Run:

```bash
python -m pytest tests/test_market_infra_supabase_writer.py tests/test_live_layer_worker.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add market_infra/supabase_writer.py scripts/build_live_events_to_supabase.py tests/test_market_infra_supabase_writer.py tests/test_live_layer_worker.py
git commit -m "feat: write live events to supabase"
```

---

### Task 5: Add dashboard live feed API

**Files:**
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/netlify/functions/live-events.mjs`
- Test: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/netlify/functions/live-events.test.mjs`

- [ ] **Step 1: Add function test**

Create `netlify/functions/live-events.test.mjs`:

```javascript
import assert from 'node:assert/strict';
import { test } from 'node:test';
import liveEvents, { buildSupabaseUrl } from './live-events.mjs';

test('buildSupabaseUrl limits rows and orders newest first', () => {
  const url = buildSupabaseUrl('https://example.supabase.co', 25);
  assert.equal(
    url,
    'https://example.supabase.co/rest/v1/live_activity_feed?select=*&order=occurred_at.desc&limit=25',
  );
});

test('liveEvents returns rows from Supabase anon read endpoint', async () => {
  const originalFetch = global.fetch;
  const originalEnv = process.env;
  process.env = {
    ...originalEnv,
    SUPABASE_URL: 'https://example.supabase.co',
    SUPABASE_ANON_KEY: 'anon-key',
  };
  global.fetch = async (_url, options) => {
    assert.equal(options.headers.apikey, 'anon-key');
    return new Response(JSON.stringify([{ title: 'New FIRE Pick' }]), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    });
  };

  const response = await liveEvents(new Request('https://site.test/.netlify/functions/live-events'));
  const body = await response.json();

  assert.equal(response.status, 200);
  assert.equal(body.events.length, 1);

  global.fetch = originalFetch;
  process.env = originalEnv;
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
node --test netlify/functions/live-events.test.mjs
```

Expected: FAIL because `live-events.mjs` does not exist.

- [ ] **Step 3: Implement live feed function**

Create `netlify/functions/live-events.mjs`:

```javascript
const jsonHeaders = {
  'Content-Type': 'application/json',
  'Cache-Control': 'no-store',
};

function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: jsonHeaders });
}

function envValue(name) {
  return globalThis.Netlify?.env?.get?.(name) || process.env[name] || '';
}

export function buildSupabaseUrl(baseUrl, limit) {
  const safeLimit = Math.max(1, Math.min(Number(limit) || 25, 50));
  return `${baseUrl.replace(/\/$/, '')}/rest/v1/live_activity_feed?select=*&order=occurred_at.desc&limit=${safeLimit}`;
}

export default async function liveEvents(req) {
  if (req.method !== 'GET') {
    return json(405, { error: 'Method not allowed' });
  }

  const supabaseUrl = envValue('SUPABASE_URL');
  const anonKey = envValue('SUPABASE_ANON_KEY');
  if (!supabaseUrl || !anonKey) {
    return json(500, { error: 'Live feed not configured' });
  }

  const requestUrl = new URL(req.url);
  const limit = requestUrl.searchParams.get('limit') || 25;
  const response = await fetch(buildSupabaseUrl(supabaseUrl, limit), {
    headers: {
      apikey: anonKey,
      Authorization: `Bearer ${anonKey}`,
    },
  });

  if (!response.ok) {
    return json(502, { error: 'Live feed unavailable' });
  }

  return json(200, { events: await response.json() });
}
```

- [ ] **Step 4: Run function test**

Run:

```bash
node --test netlify/functions/live-events.test.mjs
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add netlify/functions/live-events.mjs netlify/functions/live-events.test.mjs
git commit -m "feat: add live activity feed api"
```

Pause here before dashboard UI work. Confirm whether live event volume is useful and whether public feed rows should hide any payload fields.

---

### Task 6: Add live notification sender

**Files:**
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/netlify/functions/send-live-notifications.mjs`
- Test: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/netlify/functions/send-live-notifications.test.mjs`

- [ ] **Step 1: Add test for unsent-event fetch URL**

Create `netlify/functions/send-live-notifications.test.mjs`:

```javascript
import assert from 'node:assert/strict';
import { test } from 'node:test';
import { buildUnsentEventsUrl } from './send-live-notifications.mjs';

test('buildUnsentEventsUrl fetches unsent action/watch events oldest first', () => {
  const url = buildUnsentEventsUrl('https://example.supabase.co');
  assert.equal(
    url,
    'https://example.supabase.co/rest/v1/notification_events?select=*&sent_at=is.null&order=occurred_at.asc&limit=20',
  );
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
node --test netlify/functions/send-live-notifications.test.mjs
```

Expected: FAIL because `send-live-notifications.mjs` does not exist.

- [ ] **Step 3: Implement minimal sender**

Create `netlify/functions/send-live-notifications.mjs` with:

```javascript
import webPush from 'web-push';
import { getStore } from '@netlify/blobs';
import { timingSafeEqual } from 'node:crypto';

const jsonHeaders = { 'Content-Type': 'application/json' };

function json(status, body) {
  return new Response(JSON.stringify(body), { status, headers: jsonHeaders });
}

function safeSecretEqual(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string') return false;
  const ba = Buffer.from(a);
  const bb = Buffer.from(b);
  if (ba.length !== bb.length) return false;
  return timingSafeEqual(ba, bb);
}

function envValue(name) {
  return globalThis.Netlify?.env?.get?.(name) || process.env[name] || '';
}

export function buildUnsentEventsUrl(baseUrl) {
  return `${baseUrl.replace(/\/$/, '')}/rest/v1/notification_events?select=*&sent_at=is.null&order=occurred_at.asc&limit=20`;
}

async function markEventSent({ supabaseUrl, serviceRoleKey, id, sentAt, attempts, error }) {
  const response = await fetch(`${supabaseUrl.replace(/\/$/, '')}/rest/v1/notification_events?id=eq.${id}`, {
    method: 'PATCH',
    headers: {
      apikey: serviceRoleKey,
      Authorization: `Bearer ${serviceRoleKey}`,
      'Content-Type': 'application/json',
      Prefer: 'return=minimal',
    },
    body: JSON.stringify({
      sent_at: error ? null : sentAt,
      send_attempts: attempts,
      last_send_error: error,
    }),
  });
  if (!response.ok) {
    throw new Error(`mark_sent_failed:${response.status}`);
  }
}

export default async function sendLiveNotifications(req) {
  if (req.method !== 'POST') return json(405, { error: 'Method not allowed' });

  const notifySecret = envValue('NOTIFY_SECRET');
  if (!notifySecret || !safeSecretEqual(req.headers.get('x-notify-secret') || '', notifySecret)) {
    return json(401, { error: 'Unauthorized' });
  }

  const supabaseUrl = envValue('SUPABASE_URL');
  const serviceRoleKey = envValue('SUPABASE_SERVICE_ROLE_KEY');
  const vapidPublic = envValue('VAPID_PUBLIC_KEY');
  const vapidPrivate = envValue('VAPID_PRIVATE_KEY');
  const vapidSubject = envValue('VAPID_SUBJECT');
  if (!supabaseUrl || !serviceRoleKey || !vapidPublic || !vapidPrivate || !vapidSubject) {
    return json(500, { error: 'Live notifications not configured' });
  }

  webPush.setVapidDetails(vapidSubject, vapidPublic, vapidPrivate);

  const eventsResponse = await fetch(buildUnsentEventsUrl(supabaseUrl), {
    headers: {
      apikey: serviceRoleKey,
      Authorization: `Bearer ${serviceRoleKey}`,
    },
  });
  if (!eventsResponse.ok) return json(502, { error: 'Could not fetch notification events' });
  const events = await eventsResponse.json();

  const subStore = getStore({ name: 'push-subscriptions', consistency: 'strong' });
  const { blobs } = await subStore.list();
  const subscriptions = [];
  for (const blob of blobs || []) {
    const sub = await subStore.get(blob.key, { type: 'json' }).catch(() => null);
    if (sub) subscriptions.push({ key: blob.key, sub });
  }

  let sent = 0;
  for (const event of events) {
    const notification = {
      title: event.title,
      body: event.body,
      tag: event.dedupe_key,
      url: event.url || '/',
    };
    let eventSent = 0;
    let error = null;
    for (const { sub } of subscriptions) {
      try {
        await webPush.sendNotification(sub, JSON.stringify(notification));
        eventSent += 1;
      } catch (err) {
        error = err.message || 'send_failed';
      }
    }
    sent += eventSent;
    await markEventSent({
      supabaseUrl,
      serviceRoleKey,
      id: event.id,
      sentAt: new Date().toISOString(),
      attempts: Number(event.send_attempts || 0) + 1,
      error,
    });
  }

  return json(200, { events: events.length, sent });
}
```

- [ ] **Step 4: Run function test**

Run:

```bash
node --test netlify/functions/send-live-notifications.test.mjs
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add netlify/functions/send-live-notifications.mjs netlify/functions/send-live-notifications.test.mjs
git commit -m "feat: send live notification events"
```

Pause here before wiring this into an automatic schedule. Run manually first with one test event.

---

### Task 7: Process PropLine webhook inbox rows

**Files:**
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/scripts/process_propline_webhooks.py`
- Test: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/tests/test_process_propline_webhooks.py`

- [ ] **Step 1: Add webhook processor tests**

Create `tests/test_process_propline_webhooks.py`:

```python
from unittest.mock import Mock, patch

from scripts import process_propline_webhooks


def test_processor_skips_invalid_signature_rows():
    writer = Mock()
    writer.select_rows.return_value = [{
        "id": "delivery-1",
        "signature_valid": False,
        "payload": {"event": "line_movement"},
    }]

    with patch.object(process_propline_webhooks, "SupabaseMarketWriter", return_value=writer):
        result = process_propline_webhooks.run(
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["processed"] == 0
    writer.upsert_rows.assert_called_once()
    row = writer.upsert_rows.call_args.args[1][0]
    assert row["processed"] is True
    assert row["processing_error"] == "invalid_signature"


def test_processor_marks_unknown_payload_shape():
    writer = Mock()
    writer.select_rows.return_value = [{
        "id": "delivery-1",
        "signature_valid": True,
        "payload": {"unexpected": True},
    }]

    with patch.object(process_propline_webhooks, "SupabaseMarketWriter", return_value=writer):
        result = process_propline_webhooks.run(
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["processed"] == 0
    row = writer.upsert_rows.call_args.args[1][0]
    assert row["processing_error"] == "unsupported_payload_shape"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_process_propline_webhooks.py -v
```

Expected: FAIL because processor script does not exist.

- [ ] **Step 3: Implement inbox processor skeleton**

Create `scripts/process_propline_webhooks.py`:

```python
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def run(*, supabase_url: str, service_role_key: str) -> dict:
    writer = SupabaseMarketWriter(supabase_url, service_role_key)
    rows = writer.select_rows(
        "propline_webhook_deliveries",
        {
            "processed": "eq.false",
            "order": "received_at.asc",
            "limit": "25",
        },
    )

    updates = []
    processed = 0
    for row in rows:
        if not row.get("signature_valid"):
            updates.append({
                "id": row["id"],
                "processed": True,
                "processing_error": "invalid_signature",
            })
            continue

        payload = row.get("payload") or {}
        if not isinstance(payload, dict) or not payload.get("bookmakers"):
            updates.append({
                "id": row["id"],
                "processed": True,
                "processing_error": "unsupported_payload_shape",
            })
            continue

        updates.append({
            "id": row["id"],
            "processed": True,
            "processing_error": None,
        })
        processed += 1

    writer.upsert_rows("propline_webhook_deliveries", updates, on_conflict="id")
    return {"deliveries": len(rows), "processed": processed}


def main() -> int:
    result = run(
        supabase_url=_env("SUPABASE_URL"),
        service_role_key=_env("SUPABASE_SERVICE_ROLE_KEY"),
    )
    print(f"PropLine webhook processing deliveries={result['deliveries']} processed={result['processed']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_process_propline_webhooks.py -v
```

Expected: PASS.

- [ ] **Step 5: Extend processor after receiving more real webhook payload samples**

Use the existing valid row in `propline_webhook_deliveries` as the first sample. Add a fixture with its payload shape and convert it into:

- `market_snapshots` rows when the payload includes full odds outcomes.
- `line_movement_events` rows when the payload only describes movement.
- `notification_events` rows only after dedupe behavior has been reviewed.

This step intentionally waits for observed payload evidence before guessing at every PropLine webhook shape.

- [ ] **Step 6: Commit**

```bash
git add scripts/process_propline_webhooks.py tests/test_process_propline_webhooks.py
git commit -m "feat: process propline webhook inbox"
```

---

### Task 8: Wire the proof workflow

**Files:**
- Modify: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/.github/workflows/shadow-market-infra.yml`
- Test: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/tests/test_shadow_market_workflow.py`

- [ ] **Step 1: Add workflow test**

Append to `tests/test_shadow_market_workflow.py`:

```python
def test_shadow_workflow_can_build_live_events():
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "build_live_events" in text
    assert "python scripts/build_live_events_to_supabase.py" in text
    assert "python scripts/process_propline_webhooks.py" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_shadow_market_workflow.py -v
```

Expected: FAIL because workflow does not call the live scripts yet.

- [ ] **Step 3: Add workflow flags and steps**

Modify `.github/workflows/shadow-market-infra.yml`:

```yaml
      build_live_events:
        description: "Build live pick/movement/reminder events into Supabase"
        required: false
        type: boolean
        default: false
      process_webhooks:
        description: "Process pending PropLine webhook deliveries"
        required: false
        type: boolean
        default: true
```

Add capture resolution for scheduled runs:

```bash
BUILD_LIVE_EVENTS="${{ github.event.inputs.build_live_events }}"
PROCESS_WEBHOOKS="${{ github.event.inputs.process_webhooks }}"

if [ "${{ github.event_name }}" = "schedule" ]; then
  BUILD_LIVE_EVENTS="true"
  PROCESS_WEBHOOKS="true"
fi

if [ -z "$BUILD_LIVE_EVENTS" ]; then
  BUILD_LIVE_EVENTS="false"
fi
if [ -z "$PROCESS_WEBHOOKS" ]; then
  PROCESS_WEBHOOKS="true"
fi

echo "build_live_events=$BUILD_LIVE_EVENTS" >> "$GITHUB_OUTPUT"
echo "process_webhooks=$PROCESS_WEBHOOKS" >> "$GITHUB_OUTPUT"
```

Add steps after artifact/propline capture:

```yaml
      - name: Process PropLine webhook inbox
        if: ${{ steps.capture.outputs.process_webhooks == 'true' }}
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: python scripts/process_propline_webhooks.py

      - name: Build live events to Supabase
        if: ${{ steps.capture.outputs.build_live_events == 'true' }}
        env:
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
        run: python scripts/build_live_events_to_supabase.py "${{ steps.slate.outputs.date }}"
```

- [ ] **Step 4: Run workflow test**

Run:

```bash
python -m pytest tests/test_shadow_market_workflow.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/shadow-market-infra.yml tests/test_shadow_market_workflow.py
git commit -m "ci: build live events from shadow workflow"
```

Pause here. Manually dispatch once with `build_live_events=true`, then inspect Supabase row counts before enabling notification delivery.

---

### Task 9: Dashboard integration after proof

**Files:**
- Modify: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2-app.jsx`
- Modify: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2-data.js`
- Test: existing dashboard browser checks

- [ ] **Step 1: Add live-feed fetcher behind a soft failure path**

Add a fetch to `/.netlify/functions/live-events?limit=25`.

Expected behavior:

- If the function returns events, show a compact activity feed.
- If the function fails, hide the feed and keep the dashboard usable.
- Do not block `today.json` rendering.

- [ ] **Step 2: Add a compact feed, not a marketing panel**

Design guidance:

- Dense list.
- Timestamp.
- Event icon or severity chip.
- Pitcher, side, line, and book when available.
- No oversized cards.
- No explanatory wall of text.

- [ ] **Step 3: Browser verify**

Run the local dashboard and check:

- Desktop feed does not crowd pitcher cards.
- Mobile feed does not push core picks too far down.
- Empty/error state does not show scary developer text.

Expected: the dashboard still works if Supabase or Netlify live feed is unavailable.

Pause before shipping dashboard UI. Decide whether live activity belongs at the top, under a "Live" tab, or as a compact notification drawer.

---

### Task 10: Move worker runtime after proof

**Files:**
- Create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/docs/ops/live-layer-runtime.md`
- Optional create: `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/render.yaml`

- [ ] **Step 1: Run GitHub proof for at least two slates**

Success criteria:

- No duplicate notification events beyond `dedupe_key` expectations.
- Event volume is readable.
- No service-role key exposure.
- Live worker failures do not affect main pipeline.
- Movement events match obvious market movement in `market_snapshots`.
- TheRundown request/data-point usage does not increase because of the live layer.

- [ ] **Step 2: Choose runtime**

Recommended decision:

- Choose Render Cron if the worker remains Python-heavy.
- Choose Cloudflare Worker only if the worker is rewritten as TypeScript and does not need pipeline modules.
- Keep GitHub Actions if 10-minute latency is acceptable and schedule jitter is not causing product issues.

- [ ] **Step 3: Write runtime doc**

Create `docs/ops/live-layer-runtime.md`:

```markdown
# Live Layer Runtime

## Current runtime

The live layer runs from [GitHub Actions | Render Cron | Cloudflare Worker].

## Responsibilities

- Poll PropLine market snapshots.
- Process pending webhook deliveries.
- Build live pick, movement, reminder, and notification events.
- Never modify official pipeline artifacts.

## Required secrets

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `PROPLINE_API_KEY`
- `NOTIFY_SECRET` if this runtime calls Netlify notification dispatch

## Health checks

- `market_provider_runs` has a completed row inside the last 15 minutes during the active betting window.
- `notification_events` duplicate count by `dedupe_key` is zero.
- `propline_webhook_deliveries` unprocessed valid rows do not accumulate for more than 30 minutes.

## Rollback

Disable the live worker schedule. The official dashboard and grading pipeline continue from static artifacts.
```

- [ ] **Step 4: Commit**

```bash
git add docs/ops/live-layer-runtime.md
git commit -m "docs: document live layer runtime"
```

---

## What Tyler Needs To Decide

Before implementation:

1. **Notification aggressiveness**
   - Recommended: FIRE only for pushes; LEAN stays dashboard-only.
   - Alternative: LEAN game reminders can be enabled later if the feed feels too quiet.

2. **Reminder windows**
   - Recommended: FIRE 2u at 45 and 10 minutes; FIRE 1u at 25 minutes.
   - Alternative: one reminder per pick at 20-30 minutes.

3. **Runtime after proof**
   - Recommended: prove with GitHub shadow workflow, then move to Render Cron if the 10-minute layer is valuable.
   - Alternative: stay on GitHub if schedule jitter is acceptable.

4. **Dashboard placement**
   - Recommended: compact "Live" feed near top on desktop and below key pick summary on mobile.
   - Alternative: notification drawer / tab if the feed gets noisy.

5. **Public visibility**
   - Recommended: use Netlify API first, not direct Supabase browser reads.
   - Alternative: add Supabase anon read policies after the view is proven safe.

---

## Success Criteria

The live layer is successful if:

- New FIRE and upgrade notifications are sent within 5-10 minutes.
- Game reminders arrive in smaller, useful groups.
- Line movement with/against us is visible and deduped.
- PropLine webhook deliveries are processed or clearly marked as unsupported.
- Main pipeline artifacts remain unchanged.
- Grading remains unchanged.
- The dashboard still works if the live layer fails.
- Event history can answer: which live alerts were useful, noisy, or misleading?

---

## Rollback Plan

Rollback is simple:

1. Disable the live worker schedule.
2. Disable `send-live-notifications`.
3. Leave Supabase tables in place for audit.
4. Keep existing `send-notifications.mjs` static-artifact path as the fallback.
5. Do not touch main pipeline artifacts.

This makes the live layer a reversible product enhancement, not a risky infrastructure migration.

---

## Self-Review

Spec coverage:

- More frequent refreshes: covered by worker runtime and GitHub proof schedule.
- New FIRE pick: covered by `new_fire_pick`.
- Pick upgraded: covered by `pick_upgraded`.
- Game reminders: covered by `game_reminder_state` and narrower reminder windows.
- Line moved with/against us: covered by `line_movement_events`.
- PropLine webhooks: covered by inbox processing.
- Long-term scalability: covered by append-only events, separate state tables, API read layer, and runtime migration checkpoint.

Placeholder scan:

- The plan avoids open-ended implementation placeholders. The only intentional evidence-gated step is webhook shape expansion, because guessing unsupported provider payloads would create brittle code.

Type consistency:

- Event names, table names, and helper names are consistent across schema, Python, workflow, and Netlify tasks.

Execution choice:

- Subagent-driven execution is recommended because Tasks 1-4 can be implemented independently from Tasks 5-7, with review checkpoints before push delivery and dashboard UI.
