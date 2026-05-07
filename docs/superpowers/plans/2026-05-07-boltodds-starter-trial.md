# BoltOdds Starter Trial Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare a shadow-only BoltOdds WebSocket worker so Tyler can start the 7-day free trial, provide `BOLTODDS_API_KEY`, and immediately capture MLB pitcher strikeout market evidence without changing production picks.

**Architecture:** Keep GitHub Actions and TheRundown as the book-of-record pipeline during the trial. Add a separate Render worker that maintains one BoltOdds WebSocket connection, normalizes MLB pitcher strikeout updates, and writes `provider='boltodds'` evidence into the existing Supabase shadow market tables. Promotion to notifications, fallback odds, or production provider behavior requires explicit post-trial approval.

**Tech Stack:** Python 3.11, pytest, requests, websockets, Render background worker, Supabase Postgres REST, existing `market_infra` helpers, BoltOdds WebSocket and discovery endpoints.

---

## Why This Plan Exists

The current live-market problem is not model logic. It is infrastructure shape.

- TheRundown remains useful as the official scheduled source, but high-frequency polling is a cost/usage risk.
- PropLine polling works, but PropLine webhooks have not produced real deliveries yet.
- BoltOdds may solve the live movement problem, but it is a persistent WebSocket feed, not a GitHub Actions or Netlify Functions style task.

The trial should prove whether BoltOdds Starter can cover the exact app need:

- Sport: `MLB`
- Market: pitcher strikeouts
- Books: FanDuel, DraftKings, BetRivers, and ideally Kalshi
- Runtime: one persistent WebSocket connection
- Output: normalized shadow snapshots in Supabase

Do not buy Pro for this trial. Starter is the decision boundary. If Starter cannot cover MLB pitcher strikeouts cleanly, the recommendation is to pass or revisit after the season rather than jump straight to the $349/month plan.

## External Research Notes

BoltOdds public docs checked on 2026-05-07:

- Pricing page: Starter is $99/month, includes real-time sports betting data via WebSocket, all sportsbooks, one sports league per connection, one market per connection, advanced filters, and one concurrent connection. It also advertises a 7-day free trial.
- Pricing page: Pro is $349/month, includes all leagues, all markets, three concurrent connections, parlays endpoint, and priority support.
- Docs: Odds WebSocket endpoint is `wss://spro.agency/api` with an API key query parameter.
- Docs: Discovery endpoints are `GET https://spro.agency/api/get_info`, `GET https://spro.agency/api/get_games`, and `GET https://spro.agency/api/get_markets`; all require an API key query parameter.
- Docs: WebSocket messages include `socket_connected`, `initial_state`, `game_update`, `line_update`, `sport_clear`, `book_clear`, `ping`, `error`, and `subscription_updated`.
- Docs: Subscription filters must use exact values returned by discovery endpoints; wrong sport/book/market strings are ignored.
- Docs: WebSocket and GET endpoint rate limits are 12/min/IP, so the worker should use one persistent connection and low-frequency discovery calls.

Key implication: the trial must include an explicit discovery step before the worker subscribes, because we do not yet know the exact BoltOdds pitcher strikeout market string.

## Infrastructure Recommendation

Keep the app split into two systems during the trial:

1. **Book-of-record pipeline:** GitHub Actions + TheRundown + static JSON artifacts stay responsible for picks, grading, calibration, `today.json`, and dashboard truth.
2. **Live-market sidecar:** Render worker + BoltOdds WebSocket + Supabase shadow tables become the always-on live market evidence layer.

Do not move the core pipeline off GitHub Actions just because BoltOdds needs a persistent worker. The first infrastructure migration should be narrow: live line movement capture and, later, notifications. Grading, historical picks, model calibration, and static artifact publishing can stay scheduled until there is a separate reason to move them.

Recommended production path if the trial works:

- Phase 1: BoltOdds writes shadow `market_snapshots` only.
- Phase 2: BoltOdds writes shadow `line_movement_events` against current production picks, but sends no pushes.
- Phase 3: BoltOdds powers live movement notifications with strict dedupe and stale-feed checks.
- Phase 4: BoltOdds becomes a fallback odds provider only when TheRundown misses a target book or the live feed has a confirmed fresher line.
- Phase 5: Broader production migration only after at least one full paid month proves uptime, coverage, cost, and decision impact.

This avoids a large rewrite while still testing the thing BoltOdds might uniquely solve: timely line movement.

## WebSocket Capability Delta

BoltOdds WebSocket has different value than the current GitHub/PropLine setup:

- **Lower latency:** movement can be captured in seconds instead of at the next 10-minute PropLine poll or 30-minute production refresh.
- **Intra-window movement capture:** line or odds moves that appear and revert between scheduled runs can still be stored.
- **Better notification timing:** the app can alert when a FIRE pick moves against us, when a better book appears, or when a target book opens a missing line.
- **Source-health precision:** stale feed detection can be based on seconds since last message and seconds since last book update, not just whether a scheduled job eventually ran.
- **Movement quality metrics:** we can measure move sequence, book order, volatility, odds-path strength, and whether movement was broad market steam or one-book noise.
- **Reduced pressure on TheRundown polling:** TheRundown can remain the official scheduled source without becoming an expensive high-frequency telemetry feed.

The tradeoff is operational complexity. WebSocket infrastructure needs reconnect logic, a heartbeat, retention rules, queue/dedupe behavior, and monitoring. Without that, it can fail more quietly than GitHub Actions because a process can stay up while the market subscription is stale.

## Non-Negotiable Guardrails

- Do not change production provider order.
- Do not make `pipeline/run_pipeline.py` read from BoltOdds.
- Do not make `dashboard/data/processed/today.json` depend on BoltOdds.
- Do not send push notifications from BoltOdds during the first trial phase.
- Do not add BoltOdds to `pipeline/requirements.txt`; keep live-worker dependencies isolated.
- Do not store `BOLTODDS_API_KEY` in git.
- Do not use more than one BoltOdds WebSocket connection on Starter.
- Do not interpret missing BoltOdds data as a model problem.
- Do not buy Pro unless Starter trial evidence proves the ROI and Tyler explicitly approves.
- Do not move grading, calibration, historical pick storage, or static artifact generation off GitHub Actions during the Starter trial.
- Do not use BoltOdds for live notifications until shadow `line_movement_events` have proven dedupe, freshness, and current-pick matching.

## Problems Expected If We Migrate Too Quickly

These are the failure modes this plan must defend against:

| Change | Likely Problem | Mitigation |
| --- | --- | --- |
| Move from scheduled jobs to a persistent worker | The worker can disconnect, silently stop receiving subscription updates, or restart during the slate | Add reconnect/backoff, heartbeat rows, stale-feed alerts, and Render restart visibility before trial activation |
| Write every WebSocket tick as a raw snapshot | Supabase table growth can accelerate quickly and make diagnostics noisy or expensive | Add time-based batching, dedupe, retention, and daily rollups before any paid month |
| Promote BoltOdds directly to notifications | Duplicate pushes, stale pushes, and noise from one-book moves can erode trust fast | Start with shadow `line_movement_events`, require current-pick matching, and only notify on configured movement classes |
| Promote BoltOdds directly to odds provider | The model may mix provider semantics, book names, event IDs, and player names incorrectly | Keep TheRundown as book-of-record, reconcile names/events first, and promote only fallback cases after review |
| Depend on one WebSocket connection | Starter only allows one concurrent connection, so a bad subscription shape can block the whole slate | Use discovery probe first, subscribe to MLB pitcher strikeouts only, and stop if Starter cannot cover the target market |
| Move core pipeline off GitHub Actions | Grading, calibration, artifact publishing, and history writes become entangled with live-feed uptime | Keep core pipeline scheduled; move only live market capture/notifications first |
| Treat no WebSocket movement as no market movement | A stale subscription can look like a quiet slate | Compare against TheRundown artifacts, PropLine polling, and per-book last-seen timestamps before drawing conclusions |
| Store provider data without operational controls | A bad feed, bad mapping, or surprise volume spike can run all day | Add kill switch, provider mode env var, and trial stop checklist |

## Trial Readiness Criteria

Do not start the 7-day free trial until these are true:

- The implementation branch contains the shadow worker, discovery probe, Supabase migration, diagnostics, and operator runbook.
- The worker can run locally without a BoltOdds key far enough to validate env checks, dependency imports, and no production-file writes.
- Render is configured as a single background worker with `autoDeploy: false`.
- Supabase accepts `provider='boltodds'` and `mode='shadow_stream'` rows.
- The runbook includes the trial start timestamp, cancel-before-billing deadline, and stop procedure.
- The worker includes heartbeat/stale-feed state so an apparently running process is not mistaken for a healthy feed.
- Day 0 raw payload capture is limited and intentional so the real BoltOdds shape can become a fixture without flooding storage.

## Target Branch

Use a named branch:

```bash
git checkout main
git pull --ff-only
git checkout -b codex/boltodds-starter-trial
```

## Proposed File Structure

Create:

- `docs/superpowers/plans/2026-05-07-boltodds-starter-trial.md`
  - This plan.
- `requirements-live.txt`
  - Render/live-worker dependency file. Keeps `websockets` out of the GitHub pipeline dependency set.
- `supabase/migrations/20260507_boltodds_shadow_trial.sql`
  - Extends existing shadow table provider/mode check constraints for `boltodds` and creates `market_feed_heartbeats`.
- `market_infra/boltodds_snapshot.py`
  - Pure normalization helpers for BoltOdds `initial_state`, `game_update`, and `line_update` payloads.
- `market_infra/boltodds_client.py`
  - Small REST/WebSocket client helpers: discovery URLs, target market selection, subscribe message construction.
- `scripts/probe_boltodds_markets.py`
  - Trial activation probe. Confirms sport, target books, and pitcher strikeout market before starting worker.
- `scripts/boltodds_ws_worker.py`
  - Render worker entrypoint. Connects to BoltOdds WebSocket, subscribes, normalizes updates, writes Supabase rows, and maintains run health.
- `market_infra/live_feed_health.py`
  - Provider-agnostic heartbeat, stale-feed, and run-health helpers for always-on workers.
- `analytics/diagnostics/boltodds_trial_audit.py`
  - Post-slate comparison of BoltOdds vs production artifacts and existing provider audits.
- `analytics/diagnostics/boltodds_migration_risk_audit.py`
  - Post-trial migration-readiness summary covering uptime, stale periods, row volume, notification candidates, and provider conflicts.
- `docs/boltodds-starter-trial.md`
  - Operator handoff: env vars, Render setup, activation steps, trial monitoring, and stop rule.
- `render.yaml`
  - Optional Blueprint for a single private background worker. If another Render service already owns the repo, add the service manually instead of applying the Blueprint blindly.
- `tests/test_market_infra_boltodds_snapshot.py`
  - Unit tests for normalization.
- `tests/test_market_infra_boltodds_client.py`
  - Unit tests for market selection and subscribe message construction.
- `tests/test_boltodds_ws_worker.py`
  - Unit tests for worker write flow, run status, and no notification side effects.
- `tests/test_market_infra_live_feed_health.py`
  - Unit tests for heartbeat and stale-feed helpers.
- `tests/test_boltodds_trial_audit.py`
  - Unit tests for trial summary metrics.
- `tests/test_boltodds_migration_risk_audit.py`
  - Unit tests for post-trial migration risk summary.

Modify:

- `market_infra/provider_audit.py`
  - Keep target books shared; no provider-specific branching unless BoltOdds book names require title-to-key mapping.
- `tests/test_market_infra_provider_audit.py`
  - Add BoltOdds snapshots to confirm the existing audit logic remains provider-agnostic.
- `scripts/boltodds_ws_worker.py`
  - After Task 7, add reconnect/backoff, time-based flushing, heartbeat updates, limited raw payload capture, and explicit failed-run status.
- `docs/boltodds-starter-trial.md`
  - Add trial-start timestamp, cancel-before-billing checklist, stop-worker procedure, and production migration checklist.

Do not modify:

- `.github/workflows/pipeline.yml`
- `pipeline/run_pipeline.py`
- `pipeline/fetch_odds.py`
- `dashboard/data/processed/today.json`
- `data/picks_history.json`

---

### Task 1: Create the Plan Branch and Confirm Scope

**Files:**
- Read: `AGENTS.md`
- Read: `docs/current-state.md`
- Create: no files

- [ ] **Step 1: Confirm the current clone and branch**

Run:

```bash
git status --short --branch
```

Expected:

```text
## main...origin/main
```

- [ ] **Step 2: Pull the latest branch**

Run:

```bash
git pull --ff-only
```

Expected:

```text
Already up to date.
```

or a clean fast-forward.

- [ ] **Step 3: Create the implementation branch**

Run:

```bash
git checkout -b codex/boltodds-starter-trial
```

Expected:

```text
Switched to a new branch 'codex/boltodds-starter-trial'
```

- [ ] **Step 4: Confirm production files are untouched**

Run:

```bash
git diff -- .github/workflows/pipeline.yml pipeline/run_pipeline.py pipeline/fetch_odds.py dashboard/data/processed/today.json data/picks_history.json
```

Expected: no output.

- [ ] **Step 5: Commit this plan if it is not already committed**

Run:

```bash
git add docs/superpowers/plans/2026-05-07-boltodds-starter-trial.md
git commit -m "docs: plan boltodds starter trial"
```

Expected: one docs-only commit.

---

### Task 2: Add Isolated Live Worker Dependencies

**Files:**
- Create: `requirements-live.txt`
- Test: no test file

- [ ] **Step 1: Create the dependency file**

Write `requirements-live.txt`:

```text
-r pipeline/requirements.txt
websockets==12.0
```

- [ ] **Step 2: Verify the production pipeline dependency file did not change**

Run:

```bash
git diff -- pipeline/requirements.txt
```

Expected: no output.

- [ ] **Step 3: Verify install command**

Run:

```bash
python -m pip install -r requirements-live.txt --dry-run
```

Expected: output includes `websockets==12.0` or says requirements are already satisfied.

- [ ] **Step 4: Commit**

Run:

```bash
git add requirements-live.txt
git commit -m "chore: add live worker requirements"
```

---

### Task 3: Extend Supabase Shadow Constraints for BoltOdds

**Files:**
- Create: `supabase/migrations/20260507_boltodds_shadow_trial.sql`
- Test: `tests/test_boltodds_schema.py`

- [ ] **Step 1: Write the failing schema test**

Create `tests/test_boltodds_schema.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MIGRATION = ROOT / "supabase" / "migrations" / "20260507_boltodds_shadow_trial.sql"


def test_boltodds_migration_exists():
    assert MIGRATION.exists()


def test_boltodds_migration_extends_provider_checks():
    sql = MIGRATION.read_text(encoding="utf-8")

    for table in [
        "market_provider_runs",
        "market_events",
        "market_snapshots",
        "provider_coverage_audits",
    ]:
        assert f"alter table public.{table}" in sql

    assert "'boltodds'" in sql
    assert "'shadow_stream'" in sql
    assert "'discovery_probe'" in sql


def test_boltodds_migration_creates_feed_heartbeat_table():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "create table if not exists public.market_feed_heartbeats" in sql
    assert "last_message_at" in sql
    assert "books_seen" in sql
    assert "run_id" in sql
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_boltodds_schema.py -q
```

Expected: fails because the migration file does not exist.

- [ ] **Step 3: Add the migration**

Create `supabase/migrations/20260507_boltodds_shadow_trial.sql`:

```sql
alter table public.market_provider_runs
  drop constraint if exists market_provider_runs_provider_check;

alter table public.market_provider_runs
  add constraint market_provider_runs_provider_check
  check (provider in ('therundown', 'the_odds', 'propline', 'boltodds'));

alter table public.market_provider_runs
  drop constraint if exists market_provider_runs_mode_check;

alter table public.market_provider_runs
  add constraint market_provider_runs_mode_check
  check (mode in ('manual_probe', 'shadow_poll', 'webhook', 'test', 'discovery_probe', 'shadow_stream'));

alter table public.market_events
  drop constraint if exists market_events_provider_check;

alter table public.market_events
  add constraint market_events_provider_check
  check (provider in ('therundown', 'the_odds', 'propline', 'boltodds'));

alter table public.market_snapshots
  drop constraint if exists market_snapshots_provider_check;

alter table public.market_snapshots
  add constraint market_snapshots_provider_check
  check (provider in ('therundown', 'the_odds', 'propline', 'boltodds'));

alter table public.provider_coverage_audits
  drop constraint if exists provider_coverage_audits_provider_check;

alter table public.provider_coverage_audits
  add constraint provider_coverage_audits_provider_check
  check (provider in ('therundown', 'the_odds', 'propline', 'boltodds'));

comment on constraint market_provider_runs_provider_check on public.market_provider_runs is
  'Allows BoltOdds shadow trial rows without making BoltOdds a production provider.';

create table if not exists public.market_feed_heartbeats (
  id uuid primary key default gen_random_uuid(),
  created_at timestamptz not null default now(),
  provider text not null check (provider in ('propline', 'boltodds')),
  mode text not null check (mode in ('shadow_poll', 'webhook', 'shadow_stream')),
  slate_date date not null,
  run_id uuid references public.market_provider_runs(id) on delete set null,
  observed_at timestamptz not null,
  last_message_at timestamptz,
  books_seen text[] not null default '{}',
  metadata jsonb not null default '{}'::jsonb
);

create index if not exists idx_market_feed_heartbeats_provider_observed
  on public.market_feed_heartbeats(provider, observed_at desc);

comment on table public.market_feed_heartbeats is
  'Always-on feed heartbeat rows for shadow polling, webhooks, and WebSocket workers.';
```

- [ ] **Step 4: Run schema test**

Run:

```bash
python -m pytest tests/test_boltodds_schema.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

Run:

```bash
git add supabase/migrations/20260507_boltodds_shadow_trial.sql tests/test_boltodds_schema.py
git commit -m "db: allow boltodds shadow market rows"
```

---

### Task 4: Add Pure BoltOdds Snapshot Normalization

**Files:**
- Create: `market_infra/boltodds_snapshot.py`
- Create: `tests/test_market_infra_boltodds_snapshot.py`

- [ ] **Step 1: Write the failing normalization tests**

Create `tests/test_market_infra_boltodds_snapshot.py`:

```python
from market_infra.boltodds_snapshot import snapshots_from_boltodds_message


def _message(action="line_update"):
    return {
        "timestamp": "2026-05-07T20:15:30+00:00",
        "action": action,
        "data": {
            "sport": "MLB",
            "sportsbook": "fanduel",
            "game": "New York Yankees vs Boston Red Sox, 2026-05-07, 07",
            "home_team": "Boston Red Sox",
            "away_team": "New York Yankees",
            "info": {
                "id": 12345,
                "game": "New York Yankees vs Boston Red Sox, 2026-05-07, 07",
                "when": "2026-05-07, 07:10 PM",
                "link": "https://example.test/event/12345",
            },
            "outcomes": {
                "Gerrit Cole Over 6.5 Strikeouts": {
                    "odds": "-118",
                    "link": "https://example.test/betslip",
                    "outcome_name": "Pitcher Strikeouts",
                    "outcome_line": "6.5",
                    "outcome_over_under": "Over",
                    "outcome_target": "Gerrit Cole",
                },
                "Gerrit Cole Under 6.5 Strikeouts": {
                    "odds": "+102",
                    "link": "https://example.test/betslip",
                    "outcome_name": "Pitcher Strikeouts",
                    "outcome_line": "6.5",
                    "outcome_over_under": "Under",
                    "outcome_target": "Gerrit Cole",
                },
            },
        },
    }


def test_snapshots_from_boltodds_line_update_normalizes_pitcher_strikeouts():
    rows = snapshots_from_boltodds_message(
        _message(),
        observed_at="2026-05-07T20:15:31+00:00",
        allowed_markets={"pitcher strikeouts"},
        target_books={"fanduel": "FanDuel"},
    )

    assert len(rows) == 2
    assert rows[0]["provider"] == "boltodds"
    assert rows[0]["provider_event_id"] == "12345"
    assert rows[0]["sport_key"] == "MLB"
    assert rows[0]["market_key"] == "Pitcher Strikeouts"
    assert rows[0]["bookmaker_key"] == "fanduel"
    assert rows[0]["bookmaker_title"] == "FanDuel"
    assert rows[0]["player_name"] == "Gerrit Cole"
    assert rows[0]["normalized_player_name"] == "gerrit cole"
    assert rows[0]["side"] == "over"
    assert rows[0]["line"] == 6.5
    assert rows[0]["american_odds"] == -118
    assert rows[0]["observed_at"] == "2026-05-07T20:15:31+00:00"
    assert rows[0]["dedupe_key"]


def test_snapshots_from_boltodds_ignores_wrong_market_and_book():
    message = _message()
    message["data"]["sportsbook"] = "bovada"

    rows = snapshots_from_boltodds_message(
        message,
        observed_at="2026-05-07T20:15:31+00:00",
        allowed_markets={"pitcher strikeouts"},
        target_books={"fanduel": "FanDuel"},
    )

    assert rows == []


def test_snapshots_from_boltodds_handles_initial_state():
    rows = snapshots_from_boltodds_message(
        _message(action="initial_state"),
        observed_at="2026-05-07T20:15:31+00:00",
        allowed_markets={"pitcher strikeouts"},
        target_books={"fanduel": "FanDuel"},
    )

    assert len(rows) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_market_infra_boltodds_snapshot.py -q
```

Expected: fails because `market_infra.boltodds_snapshot` does not exist.

- [ ] **Step 3: Implement the normalizer**

Create `market_infra/boltodds_snapshot.py`:

```python
from __future__ import annotations

import hashlib
import json
from typing import Any

from pipeline.name_utils import normalize


BOLTODDS_DEFAULT_TARGET_BOOKS = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "betrivers": "BetRivers",
    "kalshi": "Kalshi",
}

BOLTODDS_SUPPORTED_ACTIONS = {"initial_state", "game_update", "line_update"}


def _american_odds(value: Any) -> int | None:
    try:
        text = str(value).strip().replace("+", "")
        if not text or text.lower() in {"none", "null", "n/a", "-"}:
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def _line(value: Any) -> float | None:
    try:
        return float(value)
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


def _market_allowed(value: Any, allowed_markets: set[str]) -> bool:
    return str(value or "").strip().lower() in allowed_markets


def snapshots_from_boltodds_message(
    message: dict[str, Any],
    *,
    observed_at: str,
    allowed_markets: set[str],
    target_books: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    if message.get("action") not in BOLTODDS_SUPPORTED_ACTIONS:
        return []

    data = message.get("data") or {}
    sportsbook = str(data.get("sportsbook") or "").strip().lower()
    target_books = target_books or BOLTODDS_DEFAULT_TARGET_BOOKS
    if sportsbook not in target_books:
        return []

    provider_event_id = str((data.get("info") or {}).get("id") or data.get("game") or "")
    if not provider_event_id:
        return []

    rows: list[dict[str, Any]] = []
    for outcome_label, outcome in (data.get("outcomes") or {}).items():
        market_name = str(outcome.get("outcome_name") or "").strip()
        if not _market_allowed(market_name, allowed_markets):
            continue

        player_name = str(outcome.get("outcome_target") or "").strip()
        side = _side(outcome.get("outcome_over_under"))
        line = _line(outcome.get("outcome_line"))
        price = _american_odds(outcome.get("odds"))
        if not player_name or side is None or line is None or price is None:
            continue

        normalized_player = normalize(player_name)
        dedupe_parts = {
            "provider": "boltodds",
            "provider_event_id": provider_event_id,
            "market_key": market_name,
            "bookmaker_key": sportsbook,
            "player": normalized_player,
            "side": side,
            "line": line,
            "price": price,
            "observed_at": observed_at,
        }
        rows.append({
            "provider": "boltodds",
            "provider_event_id": provider_event_id,
            "sport_key": str(data.get("sport") or "MLB"),
            "market_key": market_name,
            "bookmaker_key": sportsbook,
            "bookmaker_title": target_books[sportsbook],
            "player_name": player_name,
            "normalized_player_name": normalized_player,
            "side": side,
            "line": line,
            "american_odds": price,
            "observed_at": observed_at,
            "book_updated_at": message.get("timestamp"),
            "source_payload": {
                "action": message.get("action"),
                "game": data.get("game"),
                "home_team": data.get("home_team"),
                "away_team": data.get("away_team"),
                "outcome_label": outcome_label,
                "outcome": outcome,
            },
            "dedupe_key": _dedupe_key(dedupe_parts),
        })

    return rows
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_market_infra_boltodds_snapshot.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Commit**

Run:

```bash
git add market_infra/boltodds_snapshot.py tests/test_market_infra_boltodds_snapshot.py
git commit -m "feat: normalize boltodds pitcher strikeout snapshots"
```

---

### Task 5: Add BoltOdds Discovery and Subscription Helpers

**Files:**
- Create: `market_infra/boltodds_client.py`
- Create: `tests/test_market_infra_boltodds_client.py`

- [ ] **Step 1: Write failing client tests**

Create `tests/test_market_infra_boltodds_client.py`:

```python
from market_infra.boltodds_client import (
    build_subscribe_message,
    select_pitcher_strikeout_markets,
    target_books_from_env,
)


def test_select_pitcher_strikeout_markets_prefers_exact_aliases():
    markets = {
        "fanduel": {
            "MLB": ["Moneyline", "Pitcher Strikeouts", "Hits Allowed"],
        },
        "draftkings": {
            "MLB": ["Pitcher Strikeouts", "Total Bases"],
        },
    }

    selected = select_pitcher_strikeout_markets(markets, ["Pitcher Strikeouts", "Strikeouts"])

    assert selected == ["Pitcher Strikeouts"]


def test_select_pitcher_strikeout_markets_can_match_strikeout_contains():
    markets = {
        "fanduel": {
            "MLB": ["Pitcher Strikeouts O/U", "Moneyline"],
        },
    }

    selected = select_pitcher_strikeout_markets(markets, ["Pitcher Strikeouts", "Strikeouts"])

    assert selected == ["Pitcher Strikeouts O/U"]


def test_build_subscribe_message_uses_exact_filter_values():
    message = build_subscribe_message(
        sports=["MLB"],
        sportsbooks=["fanduel", "draftkings"],
        markets=["Pitcher Strikeouts"],
    )

    assert message == {
        "action": "subscribe",
        "filters": {
            "sports": ["MLB"],
            "sportsbooks": ["fanduel", "draftkings"],
            "markets": ["Pitcher Strikeouts"],
        },
    }


def test_target_books_from_env_defaults_to_trial_books(monkeypatch):
    monkeypatch.delenv("BOLTODDS_TARGET_BOOKS", raising=False)

    assert target_books_from_env() == {
        "draftkings": "DraftKings",
        "fanduel": "FanDuel",
        "betrivers": "BetRivers",
        "kalshi": "Kalshi",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_market_infra_boltodds_client.py -q
```

Expected: fails because `market_infra.boltodds_client` does not exist.

- [ ] **Step 3: Implement client helpers**

Create `market_infra/boltodds_client.py`:

```python
from __future__ import annotations

import os
from typing import Any

import requests


BOLTODDS_REST_BASE = "https://spro.agency/api"
BOLTODDS_WS_URL = "wss://spro.agency/api"
BOLTODDS_DEFAULT_BOOKS = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "betrivers": "BetRivers",
    "kalshi": "Kalshi",
}
BOLTODDS_DEFAULT_MARKET_ALIASES = ["Pitcher Strikeouts", "Strikeouts", "Pitcher Strikeouts O/U"]


def target_books_from_env() -> dict[str, str]:
    raw = os.environ.get("BOLTODDS_TARGET_BOOKS", "").strip()
    if not raw:
        return dict(BOLTODDS_DEFAULT_BOOKS)
    selected = {}
    for key in [part.strip().lower() for part in raw.split(",") if part.strip()]:
        selected[key] = BOLTODDS_DEFAULT_BOOKS.get(key, key.title())
    return selected


def market_aliases_from_env() -> list[str]:
    raw = os.environ.get("BOLTODDS_MARKET_ALIASES", "").strip()
    if not raw:
        return list(BOLTODDS_DEFAULT_MARKET_ALIASES)
    return [part.strip() for part in raw.split(",") if part.strip()]


def build_subscribe_message(
    *,
    sports: list[str],
    sportsbooks: list[str],
    markets: list[str],
) -> dict[str, Any]:
    return {
        "action": "subscribe",
        "filters": {
            "sports": sports,
            "sportsbooks": sportsbooks,
            "markets": markets,
        },
    }


def select_pitcher_strikeout_markets(markets_payload: dict[str, Any], aliases: list[str]) -> list[str]:
    alias_lowers = {alias.strip().lower() for alias in aliases}
    discovered = set()
    fallback = set()
    for sport_map in markets_payload.values():
        for market_name in sport_map.get("MLB", []) if isinstance(sport_map, dict) else []:
            normalized = str(market_name).strip()
            lowered = normalized.lower()
            if lowered in alias_lowers:
                discovered.add(normalized)
            elif "strikeout" in lowered and "pitcher" in lowered:
                fallback.add(normalized)
    return sorted(discovered or fallback)


def get_json(path: str, *, api_key: str, params: dict[str, str] | None = None) -> Any:
    params = dict(params or {})
    params["key"] = api_key
    response = requests.get(f"{BOLTODDS_REST_BASE}/{path.lstrip('/')}", params=params, timeout=20)
    response.raise_for_status()
    return response.json()
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_market_infra_boltodds_client.py -q
```

Expected:

```text
4 passed
```

- [ ] **Step 5: Commit**

Run:

```bash
git add market_infra/boltodds_client.py tests/test_market_infra_boltodds_client.py
git commit -m "feat: add boltodds discovery helpers"
```

---

### Task 6: Add the Activation Probe Script

**Files:**
- Create: `scripts/probe_boltodds_markets.py`
- Create: `tests/test_probe_boltodds_markets.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_probe_boltodds_markets.py`:

```python
from scripts.probe_boltodds_markets import build_probe_summary


def test_build_probe_summary_marks_starter_ready_when_market_and_books_exist():
    info = {"sports": ["MLB"], "sportsbooks": ["fanduel", "draftkings", "betrivers"]}
    markets = {
        "fanduel": {"MLB": ["Pitcher Strikeouts"]},
        "draftkings": {"MLB": ["Pitcher Strikeouts"]},
        "betrivers": {"MLB": ["Pitcher Strikeouts"]},
    }

    summary = build_probe_summary(
        info=info,
        markets=markets,
        target_books={"fanduel": "FanDuel", "draftkings": "DraftKings", "betrivers": "BetRivers"},
        aliases=["Pitcher Strikeouts"],
    )

    assert summary["starter_ready"] is True
    assert summary["selected_markets"] == ["Pitcher Strikeouts"]
    assert summary["missing_books"] == []


def test_build_probe_summary_blocks_when_pitcher_market_missing():
    info = {"sports": ["MLB"], "sportsbooks": ["fanduel"]}
    markets = {"fanduel": {"MLB": ["Moneyline"]}}

    summary = build_probe_summary(
        info=info,
        markets=markets,
        target_books={"fanduel": "FanDuel"},
        aliases=["Pitcher Strikeouts"],
    )

    assert summary["starter_ready"] is False
    assert summary["selected_markets"] == []
    assert summary["blocking_reasons"] == ["No MLB pitcher strikeout market matched configured aliases"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_probe_boltodds_markets.py -q
```

Expected: fails because `scripts.probe_boltodds_markets` does not exist.

- [ ] **Step 3: Implement probe script**

Create `scripts/probe_boltodds_markets.py`:

```python
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_infra.boltodds_client import (  # noqa: E402
    get_json,
    market_aliases_from_env,
    select_pitcher_strikeout_markets,
    target_books_from_env,
)


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def build_probe_summary(
    *,
    info: dict[str, Any],
    markets: dict[str, Any],
    target_books: dict[str, str],
    aliases: list[str],
) -> dict[str, Any]:
    sports = set(info.get("sports") or [])
    books = {str(book).lower() for book in info.get("sportsbooks") or []}
    missing_books = [book for book in target_books if book not in books]
    selected_markets = select_pitcher_strikeout_markets(markets, aliases)

    blocking_reasons = []
    if "MLB" not in sports:
        blocking_reasons.append("MLB is not listed in BoltOdds get_info sports")
    if not selected_markets:
        blocking_reasons.append("No MLB pitcher strikeout market matched configured aliases")
    if len(target_books) - len(missing_books) < 2:
        blocking_reasons.append("Fewer than two target books are available")

    return {
        "starter_ready": not blocking_reasons,
        "selected_markets": selected_markets,
        "missing_books": missing_books,
        "available_target_books": [book for book in target_books if book not in missing_books],
        "blocking_reasons": blocking_reasons,
    }


def main() -> int:
    api_key = _env("BOLTODDS_API_KEY")
    target_books = target_books_from_env()
    aliases = market_aliases_from_env()
    info = get_json("get_info", api_key=api_key)
    markets = get_json(
        "get_markets",
        api_key=api_key,
        params={
            "sports": "MLB",
            "sportsbooks": ",".join(target_books),
        },
    )
    summary = build_probe_summary(info=info, markets=markets, target_books=target_books, aliases=aliases)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["starter_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_probe_boltodds_markets.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Run compile check**

Run:

```bash
python -m py_compile scripts/probe_boltodds_markets.py
```

Expected: no output.

- [ ] **Step 6: Commit**

Run:

```bash
git add scripts/probe_boltodds_markets.py tests/test_probe_boltodds_markets.py
git commit -m "feat: add boltodds starter probe"
```

---

### Task 7: Add the BoltOdds WebSocket Shadow Worker

**Files:**
- Create: `scripts/boltodds_ws_worker.py`
- Create: `tests/test_boltodds_ws_worker.py`

- [ ] **Step 1: Write failing worker tests**

Create `tests/test_boltodds_ws_worker.py`:

```python
from unittest.mock import Mock

from scripts.boltodds_ws_worker import build_run_rows, write_snapshot_batch


def test_build_run_rows_uses_shadow_stream_mode():
    started = build_run_rows(
        slate_date="2026-05-07",
        status="started",
        request_count=0,
        books_seen=[],
        metadata={"worker": "boltodds_ws_worker"},
    )

    assert started["provider"] == "boltodds"
    assert started["mode"] == "shadow_stream"
    assert started["slate_date"] == "2026-05-07"
    assert started["status"] == "started"


def test_write_snapshot_batch_upserts_snapshots_and_audit():
    writer = Mock()
    writer.insert_rows.return_value = [{"id": "run-1"}]
    snapshots = [
        {
            "provider": "boltodds",
            "provider_event_id": "12345",
            "sport_key": "MLB",
            "market_key": "Pitcher Strikeouts",
            "bookmaker_key": "fanduel",
            "bookmaker_title": "FanDuel",
            "player_name": "Gerrit Cole",
            "normalized_player_name": "gerrit cole",
            "side": "over",
            "line": 6.5,
            "american_odds": -118,
            "observed_at": "2026-05-07T20:15:31+00:00",
            "source_payload": {},
            "dedupe_key": "snapshot-1",
        },
        {
            "provider": "boltodds",
            "provider_event_id": "12345",
            "sport_key": "MLB",
            "market_key": "Pitcher Strikeouts",
            "bookmaker_key": "fanduel",
            "bookmaker_title": "FanDuel",
            "player_name": "Gerrit Cole",
            "normalized_player_name": "gerrit cole",
            "side": "under",
            "line": 6.5,
            "american_odds": +102,
            "observed_at": "2026-05-07T20:15:31+00:00",
            "source_payload": {},
            "dedupe_key": "snapshot-2",
        },
    ]

    result = write_snapshot_batch(
        writer=writer,
        run_id="run-1",
        slate_date="2026-05-07",
        snapshots=snapshots,
        production_payload={"pitchers": []},
        books_seen={"fanduel"},
        target_event_count=1,
    )

    assert result["snapshot_count"] == 2
    writer.upsert_rows.assert_any_call("market_snapshots", snapshots, on_conflict="dedupe_key")
    assert writer.insert_rows.call_args.args[0] == "provider_coverage_audits"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
python -m pytest tests/test_boltodds_ws_worker.py -q
```

Expected: fails because `scripts.boltodds_ws_worker` does not exist.

- [ ] **Step 3: Implement the worker skeleton and pure write helpers**

Create `scripts/boltodds_ws_worker.py`:

```python
from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import websockets

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_infra.boltodds_client import (  # noqa: E402
    BOLTODDS_WS_URL,
    build_subscribe_message,
    market_aliases_from_env,
    select_pitcher_strikeout_markets,
    target_books_from_env,
)
from market_infra.boltodds_snapshot import snapshots_from_boltodds_message  # noqa: E402
from market_infra.provider_audit import build_provider_coverage_audit  # noqa: E402
from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402
from scripts.probe_boltodds_markets import build_probe_summary  # noqa: E402
from market_infra.boltodds_client import get_json  # noqa: E402


DEFAULT_ARTIFACT = ROOT / "dashboard" / "data" / "processed" / "today.json"


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _optional_env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_production_artifact(path: Path = DEFAULT_ARTIFACT) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_run_rows(
    *,
    slate_date: str,
    status: str,
    request_count: int,
    books_seen: list[str],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    row = {
        "provider": "boltodds",
        "mode": "shadow_stream",
        "slate_date": slate_date,
        "status": status,
        "request_count": request_count,
        "books_seen": books_seen,
        "metadata": metadata,
    }
    if status in {"completed", "failed"}:
        row["completed_at"] = _now_utc()
    return row


def write_snapshot_batch(
    *,
    writer: SupabaseMarketWriter,
    run_id: str,
    slate_date: str,
    snapshots: list[dict[str, Any]],
    production_payload: dict[str, Any],
    books_seen: set[str],
    target_event_count: int,
) -> dict[str, Any]:
    for row in snapshots:
        row["run_id"] = run_id
    writer.upsert_rows("market_snapshots", snapshots, on_conflict="dedupe_key")
    audit = build_provider_coverage_audit(snapshots, production_payload)
    writer.insert_rows("provider_coverage_audits", [{
        "run_id": run_id,
        "slate_date": slate_date,
        "provider": "boltodds",
        "target_books": audit["target_books"],
        "books_seen": sorted(books_seen),
        "target_event_count": target_event_count,
        "parsed_pitcher_prop_count": audit["parsed_pitcher_prop_count"],
        "complete_pitcher_line_groups": audit["complete_pitcher_line_groups"],
        "same_line_overlap_count": audit["same_line_overlap_count"],
        "line_conflict_count": audit["line_conflict_count"],
        "missing_target_books": audit["missing_target_books"],
        "metadata": {
            **audit["metadata"],
            "snapshot_rows": len(snapshots),
            "worker": "scripts/boltodds_ws_worker.py",
        },
    }])
    return {"snapshot_count": len(snapshots)}


async def run_worker() -> None:
    api_key = _env("BOLTODDS_API_KEY")
    slate_date = _optional_env("SLATE_DATE") or _load_production_artifact().get("date")
    if not slate_date:
        raise EnvironmentError("SLATE_DATE or today.json date is required")

    target_books = target_books_from_env()
    aliases = market_aliases_from_env()
    info = get_json("get_info", api_key=api_key)
    markets_payload = get_json(
        "get_markets",
        api_key=api_key,
        params={"sports": "MLB", "sportsbooks": ",".join(target_books)},
    )
    summary = build_probe_summary(info=info, markets=markets_payload, target_books=target_books, aliases=aliases)
    if not summary["starter_ready"]:
        raise RuntimeError(f"BoltOdds Starter probe failed: {summary['blocking_reasons']}")

    selected_markets = summary["selected_markets"]
    production_payload = _load_production_artifact()
    writer = SupabaseMarketWriter(_env("SUPABASE_URL"), _env("SUPABASE_SERVICE_ROLE_KEY"))
    run = writer.insert_rows("market_provider_runs", [build_run_rows(
        slate_date=slate_date,
        status="started",
        request_count=2,
        books_seen=[],
        metadata={"worker": "scripts/boltodds_ws_worker.py", "selected_markets": selected_markets},
    )])[0]
    run_id = run["id"]

    books_seen: set[str] = set()
    target_event_ids: set[str] = set()
    batch: list[dict[str, Any]] = []
    subscribe_message = build_subscribe_message(
        sports=["MLB"],
        sportsbooks=list(target_books),
        markets=selected_markets,
    )

    try:
        async with websockets.connect(f"{BOLTODDS_WS_URL}?key={api_key}", max_size=None) as websocket:
            await websocket.recv()
            await websocket.send(json.dumps(subscribe_message))
            while True:
                raw = await websocket.recv()
                message = json.loads(raw)
                if message.get("action") == "ping":
                    continue
                observed_at = _now_utc()
                rows = snapshots_from_boltodds_message(
                    message,
                    observed_at=observed_at,
                    allowed_markets={market.lower() for market in selected_markets},
                    target_books=target_books,
                )
                for row in rows:
                    books_seen.add(row["bookmaker_key"])
                    target_event_ids.add(row["provider_event_id"])
                batch.extend(rows)
                if len(batch) >= int(_optional_env("BOLTODDS_BATCH_SIZE", "100")):
                    write_snapshot_batch(
                        writer=writer,
                        run_id=run_id,
                        slate_date=slate_date,
                        snapshots=batch,
                        production_payload=production_payload,
                        books_seen=books_seen,
                        target_event_count=len(target_event_ids),
                    )
                    batch = []
    finally:
        if batch:
            write_snapshot_batch(
                writer=writer,
                run_id=run_id,
                slate_date=slate_date,
                snapshots=batch,
                production_payload=production_payload,
                books_seen=books_seen,
                target_event_count=len(target_event_ids),
            )
        writer.upsert_rows("market_provider_runs", [{
            "id": run_id,
            **build_run_rows(
                slate_date=slate_date,
                status="completed",
                request_count=2,
                books_seen=sorted(books_seen),
                metadata={"worker": "scripts/boltodds_ws_worker.py", "selected_markets": selected_markets},
            ),
        }], on_conflict="id")


def main() -> int:
    asyncio.run(run_worker())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_boltodds_ws_worker.py -q
```

Expected:

```text
2 passed
```

- [ ] **Step 5: Run compile check**

Run:

```bash
python -m py_compile scripts/boltodds_ws_worker.py
```

Expected: no output.

- [ ] **Step 6: Commit**

Run:

```bash
git add scripts/boltodds_ws_worker.py tests/test_boltodds_ws_worker.py
git commit -m "feat: add boltodds websocket shadow worker"
```

---

### Task 8: Add Trial Diagnostics

**Files:**
- Create: `analytics/diagnostics/boltodds_trial_audit.py`
- Create: `tests/test_boltodds_trial_audit.py`

- [ ] **Step 1: Write failing diagnostic tests**

Create `tests/test_boltodds_trial_audit.py`:

```python
from analytics.diagnostics.boltodds_trial_audit import summarize_provider_audits


def test_summarize_provider_audits_counts_best_active_rows():
    rows = [
        {
            "slate_date": "2026-05-07",
            "provider": "boltodds",
            "complete_pitcher_line_groups": 40,
            "same_line_overlap_count": 30,
            "line_conflict_count": 2,
            "missing_target_books": ["kalshi"],
            "metadata": {
                "target_book_group_counts": {"fanduel": 18, "draftkings": 18, "betrivers": 4, "kalshi": 0},
                "production_book_group_counts": {"fanduel": 20, "draftkings": 20, "betrivers": 6, "kalshi": 10},
                "fillable_missing_book_counts": {"fanduel": 0, "draftkings": 0, "betrivers": 3, "kalshi": 0},
                "non_target_books_seen": [],
            },
        },
    ]

    summary = summarize_provider_audits(rows)

    assert summary["slates"] == 1
    assert summary["total_complete_pitcher_line_groups"] == 40
    assert summary["total_same_line_overlap_count"] == 30
    assert summary["total_line_conflict_count"] == 2
    assert summary["missing_target_books_by_slate"] == {"2026-05-07": ["kalshi"]}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_boltodds_trial_audit.py -q
```

Expected: fails because `analytics.diagnostics.boltodds_trial_audit` does not exist.

- [ ] **Step 3: Implement diagnostic helper**

Create `analytics/diagnostics/boltodds_trial_audit.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def summarize_provider_audits(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "slates": len({row["slate_date"] for row in rows}),
        "total_complete_pitcher_line_groups": sum(int(row.get("complete_pitcher_line_groups") or 0) for row in rows),
        "total_same_line_overlap_count": sum(int(row.get("same_line_overlap_count") or 0) for row in rows),
        "total_line_conflict_count": sum(int(row.get("line_conflict_count") or 0) for row in rows),
        "missing_target_books_by_slate": {
            row["slate_date"]: row.get("missing_target_books") or []
            for row in rows
        },
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize BoltOdds trial provider coverage audits.")
    parser.add_argument("--input", required=True, help="JSON export of provider_coverage_audits rows")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    rows = json.loads(Path(args.input).read_text(encoding="utf-8"))
    print(json.dumps(summarize_provider_audits(rows), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_boltodds_trial_audit.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit**

Run:

```bash
git add analytics/diagnostics/boltodds_trial_audit.py tests/test_boltodds_trial_audit.py
git commit -m "feat: add boltodds trial audit helper"
```

---

### Task 8A: Add WebSocket Operational Hardening

**Files:**
- Create: `market_infra/live_feed_health.py`
- Create: `tests/test_market_infra_live_feed_health.py`
- Modify: `scripts/boltodds_ws_worker.py`
- Modify: `tests/test_boltodds_ws_worker.py`

- [ ] **Step 1: Write failing heartbeat and stale-feed tests**

Create `tests/test_market_infra_live_feed_health.py`:

```python
from market_infra.live_feed_health import build_heartbeat_row, classify_feed_health


def test_build_heartbeat_row_records_provider_and_last_message():
    row = build_heartbeat_row(
        provider="boltodds",
        mode="shadow_stream",
        slate_date="2026-05-07",
        run_id="run-123",
        observed_at="2026-05-07T20:15:00+00:00",
        last_message_at="2026-05-07T20:14:55+00:00",
        books_seen=["draftkings", "fanduel"],
        reconnect_count=2,
        message_count=150,
    )

    assert row["provider"] == "boltodds"
    assert row["mode"] == "shadow_stream"
    assert row["slate_date"] == "2026-05-07"
    assert row["run_id"] == "run-123"
    assert row["last_message_at"] == "2026-05-07T20:14:55+00:00"
    assert row["books_seen"] == ["draftkings", "fanduel"]
    assert row["metadata"]["reconnect_count"] == 2
    assert row["metadata"]["message_count"] == 150


def test_classify_feed_health_marks_stale_after_threshold_seconds():
    result = classify_feed_health(
        now_iso="2026-05-07T20:20:00+00:00",
        last_message_iso="2026-05-07T20:14:30+00:00",
        stale_after_seconds=300,
    )

    assert result["status"] == "stale"
    assert result["seconds_since_last_message"] == 330


def test_classify_feed_health_marks_live_inside_threshold_seconds():
    result = classify_feed_health(
        now_iso="2026-05-07T20:20:00+00:00",
        last_message_iso="2026-05-07T20:19:15+00:00",
        stale_after_seconds=300,
    )

    assert result["status"] == "live"
    assert result["seconds_since_last_message"] == 45
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_market_infra_live_feed_health.py -q
```

Expected: fails because `market_infra.live_feed_health` does not exist.

- [ ] **Step 3: Add heartbeat helpers**

Create `market_infra/live_feed_health.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def build_heartbeat_row(
    *,
    provider: str,
    mode: str,
    slate_date: str,
    run_id: str,
    observed_at: str,
    last_message_at: str | None,
    books_seen: list[str],
    reconnect_count: int,
    message_count: int,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "mode": mode,
        "slate_date": slate_date,
        "run_id": run_id,
        "observed_at": observed_at,
        "last_message_at": last_message_at,
        "books_seen": sorted(books_seen),
        "metadata": {
            "reconnect_count": reconnect_count,
            "message_count": message_count,
        },
    }


def classify_feed_health(
    *,
    now_iso: str,
    last_message_iso: str | None,
    stale_after_seconds: int,
) -> dict[str, Any]:
    if not last_message_iso:
        return {
            "status": "no_messages",
            "seconds_since_last_message": None,
        }

    elapsed = int((_parse_iso(now_iso) - _parse_iso(last_message_iso)).total_seconds())
    return {
        "status": "stale" if elapsed > stale_after_seconds else "live",
        "seconds_since_last_message": elapsed,
    }
```

- [ ] **Step 4: Run heartbeat tests**

Run:

```bash
python -m pytest tests/test_market_infra_live_feed_health.py -q
```

Expected:

```text
3 passed
```

- [ ] **Step 5: Add worker tests for failed status, time flush, and no notification side effects**

Append these tests to `tests/test_boltodds_ws_worker.py`:

```python
from scripts.boltodds_ws_worker import build_run_rows, should_flush_batch


def test_build_run_rows_can_mark_failed_with_error_message():
    row = build_run_rows(
        slate_date="2026-05-07",
        status="failed",
        request_count=2,
        books_seen=["fanduel"],
        metadata={"worker": "scripts/boltodds_ws_worker.py"},
        error_message="websocket disconnected",
    )

    assert row["status"] == "failed"
    assert row["error_message"] == "websocket disconnected"
    assert "completed_at" in row


def test_should_flush_batch_when_size_or_interval_threshold_hit():
    assert should_flush_batch(
        batch_size=100,
        max_batch_size=100,
        now_monotonic=50.0,
        last_flush_monotonic=49.0,
        max_flush_seconds=10.0,
    )
    assert should_flush_batch(
        batch_size=3,
        max_batch_size=100,
        now_monotonic=60.0,
        last_flush_monotonic=49.0,
        max_flush_seconds=10.0,
    )
    assert not should_flush_batch(
        batch_size=3,
        max_batch_size=100,
        now_monotonic=55.0,
        last_flush_monotonic=49.0,
        max_flush_seconds=10.0,
    )
```

- [ ] **Step 6: Run worker tests to verify they fail**

Run:

```bash
python -m pytest tests/test_boltodds_ws_worker.py -q
```

Expected: fails because `error_message` and `should_flush_batch` are not implemented yet.

- [ ] **Step 7: Harden the worker**

Modify `scripts/boltodds_ws_worker.py`:

- `build_run_rows(...)` accepts `error_message: str | None = None` and includes it when present.
- Add `should_flush_batch(batch_size, max_batch_size, now_monotonic, last_flush_monotonic, max_flush_seconds)`.
- Track `last_message_at`, `message_count`, and `reconnect_count`.
- Flush when batch size reaches `BOLTODDS_BATCH_SIZE` or when `BOLTODDS_FLUSH_SECONDS` has elapsed.
- Insert a `market_feed_heartbeats` row at least once per flush using `build_heartbeat_row(...)`.
- On exception, upsert `market_provider_runs.status='failed'` with `error_message`.
- On graceful shutdown, upsert `market_provider_runs.status='completed'`.
- Limit raw sample capture to `BOLTODDS_RAW_SAMPLE_LIMIT`, default `50`, stored in run metadata only.

Minimum helper implementation:

```python
def should_flush_batch(
    *,
    batch_size: int,
    max_batch_size: int,
    now_monotonic: float,
    last_flush_monotonic: float,
    max_flush_seconds: float,
) -> bool:
    if batch_size <= 0:
        return False
    return batch_size >= max_batch_size or (now_monotonic - last_flush_monotonic) >= max_flush_seconds
```

- [ ] **Step 8: Run focused operational tests**

Run:

```bash
python -m pytest tests/test_market_infra_live_feed_health.py tests/test_boltodds_ws_worker.py -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

Run:

```bash
git add market_infra/live_feed_health.py tests/test_market_infra_live_feed_health.py scripts/boltodds_ws_worker.py tests/test_boltodds_ws_worker.py
git commit -m "feat: harden boltodds websocket worker"
```

---

### Task 8B: Add Migration Risk Audit

**Files:**
- Create: `analytics/diagnostics/boltodds_migration_risk_audit.py`
- Create: `tests/test_boltodds_migration_risk_audit.py`

- [ ] **Step 1: Write failing migration-risk summary tests**

Create `tests/test_boltodds_migration_risk_audit.py`:

```python
from analytics.diagnostics.boltodds_migration_risk_audit import summarize_migration_risk


def test_summarize_migration_risk_flags_stale_periods_and_volume():
    summary = summarize_migration_risk(
        provider_audits=[
            {
                "slate_date": "2026-05-07",
                "complete_pitcher_line_groups": 40,
                "same_line_overlap_count": 30,
                "line_conflict_count": 4,
                "missing_target_books": ["kalshi"],
            }
        ],
        heartbeat_rows=[
            {
                "provider": "boltodds",
                "metadata": {
                    "feed_health": {"status": "stale", "seconds_since_last_message": 420},
                    "reconnect_count": 3,
                },
            }
        ],
        snapshot_rows=[
            {"bookmaker_key": "fanduel", "normalized_player_name": "gerrit cole"},
            {"bookmaker_key": "draftkings", "normalized_player_name": "gerrit cole"},
            {"bookmaker_key": "fanduel", "normalized_player_name": "logan webb"},
        ],
        shadow_notification_events=[
            {"movement_class": "price_against_pick"},
            {"movement_class": "duplicate_suppressed"},
        ],
        max_daily_snapshot_rows=2,
    )

    assert summary["audit_slates"] == 1
    assert summary["total_line_conflicts"] == 4
    assert summary["missing_target_books"] == ["kalshi"]
    assert summary["stale_heartbeat_count"] == 1
    assert summary["max_reconnect_count"] == 3
    assert summary["snapshot_rows"] == 3
    assert summary["row_volume_status"] == "too_high"
    assert summary["shadow_notification_candidates"] == 2
    assert "stale_feed" in summary["migration_blockers"]
    assert "row_volume" in summary["migration_blockers"]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
python -m pytest tests/test_boltodds_migration_risk_audit.py -q
```

Expected: fails because `analytics.diagnostics.boltodds_migration_risk_audit` does not exist.

- [ ] **Step 3: Implement migration-risk summary**

Create `analytics/diagnostics/boltodds_migration_risk_audit.py`:

```python
from __future__ import annotations

from typing import Any


def summarize_migration_risk(
    *,
    provider_audits: list[dict[str, Any]],
    heartbeat_rows: list[dict[str, Any]],
    snapshot_rows: list[dict[str, Any]],
    shadow_notification_events: list[dict[str, Any]],
    max_daily_snapshot_rows: int,
) -> dict[str, Any]:
    missing_books = sorted({
        book
        for row in provider_audits
        for book in (row.get("missing_target_books") or [])
    })
    stale_heartbeats = [
        row for row in heartbeat_rows
        if ((row.get("metadata") or {}).get("feed_health") or {}).get("status") == "stale"
    ]
    reconnect_counts = [
        int((row.get("metadata") or {}).get("reconnect_count") or 0)
        for row in heartbeat_rows
    ]
    blockers: list[str] = []
    if stale_heartbeats:
        blockers.append("stale_feed")
    if len(snapshot_rows) > max_daily_snapshot_rows:
        blockers.append("row_volume")
    if any(int(row.get("line_conflict_count") or 0) > 0 for row in provider_audits):
        blockers.append("line_conflicts")

    return {
        "audit_slates": len({row.get("slate_date") for row in provider_audits if row.get("slate_date")}),
        "total_complete_pitcher_line_groups": sum(int(row.get("complete_pitcher_line_groups") or 0) for row in provider_audits),
        "total_same_line_overlap": sum(int(row.get("same_line_overlap_count") or 0) for row in provider_audits),
        "total_line_conflicts": sum(int(row.get("line_conflict_count") or 0) for row in provider_audits),
        "missing_target_books": missing_books,
        "stale_heartbeat_count": len(stale_heartbeats),
        "max_reconnect_count": max(reconnect_counts or [0]),
        "snapshot_rows": len(snapshot_rows),
        "row_volume_status": "too_high" if len(snapshot_rows) > max_daily_snapshot_rows else "ok",
        "distinct_books": sorted({row.get("bookmaker_key") for row in snapshot_rows if row.get("bookmaker_key")}),
        "distinct_players": len({row.get("normalized_player_name") for row in snapshot_rows if row.get("normalized_player_name")}),
        "shadow_notification_candidates": len(shadow_notification_events),
        "migration_blockers": blockers,
    }
```

- [ ] **Step 4: Run migration-risk tests**

Run:

```bash
python -m pytest tests/test_boltodds_migration_risk_audit.py -q
```

Expected:

```text
1 passed
```

- [ ] **Step 5: Commit**

Run:

```bash
git add analytics/diagnostics/boltodds_migration_risk_audit.py tests/test_boltodds_migration_risk_audit.py
git commit -m "feat: add boltodds migration risk audit"
```

---

### Task 9: Add Render and Operator Handoff

**Files:**
- Create: `render.yaml`
- Create: `docs/boltodds-starter-trial.md`
- Test: no test file

- [ ] **Step 1: Add Render Blueprint**

Create `render.yaml`:

```yaml
services:
  - type: worker
    name: baseballbettingedge-boltodds-shadow
    runtime: python
    plan: starter
    buildCommand: "pip install -r requirements-live.txt"
    startCommand: "python scripts/boltodds_ws_worker.py"
    autoDeploy: false
    envVars:
      - key: BOLTODDS_API_KEY
        sync: false
      - key: SUPABASE_URL
        sync: false
      - key: SUPABASE_SERVICE_ROLE_KEY
        sync: false
      - key: BOLTODDS_TARGET_BOOKS
        value: "fanduel,draftkings,betrivers,kalshi"
      - key: BOLTODDS_MARKET_ALIASES
        value: "Pitcher Strikeouts,Pitcher Strikeouts O/U,Strikeouts"
      - key: BOLTODDS_BATCH_SIZE
        value: "100"
```

- [ ] **Step 2: Add operator handoff doc**

Create `docs/boltodds-starter-trial.md`:

```markdown
# BoltOdds Starter Trial Runbook

## Purpose

Run BoltOdds as a shadow-only live market feed for MLB pitcher strikeouts.

The worker writes only to Supabase shadow tables:

- `market_provider_runs`
- `market_events`
- `market_snapshots`
- `provider_coverage_audits`

It does not update picks, `today.json`, grading, calibration, or push notifications.

## Before Starting the 7-Day Trial

Confirm these are deployed:

- `requirements-live.txt`
- `supabase/migrations/20260507_boltodds_shadow_trial.sql`
- `market_infra/boltodds_snapshot.py`
- `market_infra/boltodds_client.py`
- `scripts/probe_boltodds_markets.py`
- `scripts/boltodds_ws_worker.py`
- `render.yaml`

## Trial Activation

1. Start the BoltOdds 7-day free trial on the Starter plan.
2. Provide the API key as `BOLTODDS_API_KEY`.
3. Run the discovery probe:

```bash
$env:BOLTODDS_API_KEY = Read-Host "Enter BoltOdds API key"
python scripts/probe_boltodds_markets.py
```

Expected success shape:

```json
{
  "starter_ready": true,
  "selected_markets": ["Pitcher Strikeouts"],
  "missing_books": []
}
```

If `starter_ready` is false, do not start Render. Capture the output and ask BoltOdds support whether Starter includes MLB pitcher strikeouts for the missing books/market.

## Trial Calendar and Billing Guardrail

Record the trial timestamps before starting Render. In PowerShell:

```powershell
$trialStartedUtc = (Get-Date).ToUniversalTime()
$trialStartedPhoenix = [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId($trialStartedUtc, 'US Mountain Standard Time')
$cancelBeforeUtc = $trialStartedUtc.AddDays(6)
$cancelBeforePhoenix = [System.TimeZoneInfo]::ConvertTimeBySystemTimeZoneId($cancelBeforeUtc, 'US Mountain Standard Time')

"TRIAL_STARTED_AT_PHOENIX=$($trialStartedPhoenix.ToString('o'))"
"TRIAL_STARTED_AT_UTC=$($trialStartedUtc.ToString('o'))"
"CANCEL_BEFORE_PHOENIX=$($cancelBeforePhoenix.ToString('o'))"
"CANCEL_BEFORE_UTC=$($cancelBeforeUtc.ToString('o'))"
```

Use a 6-day cancellation deadline rather than waiting for day 7. The trial is only worth continuing into a paid month if the Day 4-6 evidence already shows Starter-level coverage and stability.

## Render Environment Variables

Set:

```text
BOLTODDS_API_KEY=set in Render from the trial dashboard key
SUPABASE_URL=https://htoaytcsjrdyyzcwxjfg.supabase.co
SUPABASE_SERVICE_ROLE_KEY=set in Render from the existing Supabase service role secret
BOLTODDS_TARGET_BOOKS=fanduel,draftkings,betrivers,kalshi
BOLTODDS_MARKET_ALIASES=Pitcher Strikeouts,Pitcher Strikeouts O/U,Strikeouts
BOLTODDS_BATCH_SIZE=100
BOLTODDS_FLUSH_SECONDS=10
BOLTODDS_STALE_AFTER_SECONDS=300
BOLTODDS_RAW_SAMPLE_LIMIT=50
```

Set `autoDeploy=false`. The worker should only be restarted intentionally during the trial.

## Trial Monitoring

Check Supabase:

```sql
select provider, mode, slate_date, status, started_at, completed_at, request_count, books_seen, error_message
from market_provider_runs
where provider = 'boltodds'
order by created_at desc
limit 20;
```

```sql
select slate_date, books_seen, complete_pitcher_line_groups, same_line_overlap_count,
       line_conflict_count, missing_target_books, metadata
from provider_coverage_audits
where provider = 'boltodds'
order by created_at desc
limit 20;
```

Check freshness:

```sql
select provider, mode, slate_date, observed_at, last_message_at, books_seen, metadata
from market_feed_heartbeats
where provider = 'boltodds'
order by observed_at desc
limit 20;
```

The `market_feed_heartbeats` table is created by `supabase/migrations/20260507_boltodds_shadow_trial.sql`.


Check row volume:

```sql
select date_trunc('hour', observed_at::timestamptz) as hour_bucket,
       count(*) as snapshot_rows,
       count(distinct bookmaker_key) as books,
       count(distinct normalized_player_name) as players
from market_snapshots
where provider = 'boltodds'
  and observed_at >= now() - interval '24 hours'
group by 1
order by 1 desc;
```

## Seven-Day Success Criteria

Starter is worth keeping only if:

- One connection stays stable through normal slate windows.
- FanDuel and DraftKings coverage is consistently useful.
- BetRivers appears often enough to beat PropLine or fill TheRundown gaps.
- Pitcher K line conflicts are low and explainable.
- Movement arrives earlier than PropLine polling often enough to improve alerts.
- Render cost plus BoltOdds Starter cost is justified by better actionable timing.
- Heartbeat stays live during active slate windows with no unexplained stale periods over 5 minutes.
- Supabase row volume remains manageable with batching and dedupe.
- Raw payload fixtures confirm the normalizer matches real BoltOdds data, not just docs examples.
- Shadow notification candidates are meaningful and not mostly duplicate/noisy one-book moves.

## Stop Rule

Cancel before billing if:

- Starter cannot subscribe to MLB pitcher strikeouts.
- One connection cannot carry the slate.
- Target books are missing or stale.
- The feed requires Pro to do the single-market MLB pitcher K use case.
- Normalized rows cannot be reconciled to production pitcher names/lines.
- The worker has repeated reconnect loops or stale periods during active slate windows.
- Snapshot volume is high enough that retention/rollups need work before a paid month.
- Shadow notification candidates are too noisy to trust.

## Stop Worker Procedure

1. Stop the Render worker.
2. Confirm no new rows arrive:

```sql
select max(observed_at) as latest_boltodds_snapshot
from market_snapshots
where provider = 'boltodds';
```

3. Leave Supabase rows in place for review.
4. Do not delete raw evidence until the trial audit is complete.

## Post-Production Infrastructure Roadmap

If the trial passes, production should evolve in this order:

1. **Live health surface:** expose provider health, last message time, stale state, and books seen.
2. **Shadow movement events:** derive `line_movement_events` from BoltOdds snapshots against current production picks without sending pushes.
3. **Notification queue:** add a Supabase-backed queue with dedupe keys for pick, side, book, line, price, and movement class.
4. **Live notification worker:** let Render or Netlify send push notifications from queued events after stale-feed and duplicate checks.
5. **Provider arbitration:** define source priority and fallback rules for TheRundown, PropLine, BoltOdds, and The Odds API.
6. **Dashboard live overlay:** show live line movement and source freshness separately from static `today.json`.
7. **Retention and rollups:** keep recent raw snapshots, summarize daily movement, and archive only useful comparison metrics long-term.

Do not combine all seven into one release. Each step should produce a visible capability and a rollback point.

## Migration Risk Checklist

Before any fallback or production provider migration, answer these with evidence:

- Which target books does BoltOdds cover during active slate windows?
- How often does BoltOdds disagree with TheRundown on pitcher line value?
- Are disagreements stale-source issues, book-specific line differences, or parser/name-mapping issues?
- Does BoltOdds improve BetRivers coverage enough to matter?
- Does BoltOdds include Kalshi in a usable way, or does TheRundown remain necessary for Kalshi?
- How many notification candidates would have fired, and how many would Tyler actually care about?
- How often does the worker reconnect, and how long are stale periods?
- What is the daily Supabase row volume before and after dedupe/rollup?
- Can the app stop BoltOdds without breaking picks, dashboard, grading, or notifications?
- Is the paid month ROI justified by better timing, better coverage, or both?
```

- [ ] **Step 3: Commit**

Run:

```bash
git add render.yaml docs/boltodds-starter-trial.md
git commit -m "docs: add boltodds trial runbook and render worker"
```

---

### Task 10: Local Verification Before Trial Key

**Files:**
- Read: all created files

- [ ] **Step 1: Run focused tests**

Run:

```bash
python -m pytest tests/test_boltodds_schema.py tests/test_market_infra_boltodds_snapshot.py tests/test_market_infra_boltodds_client.py tests/test_probe_boltodds_markets.py tests/test_boltodds_ws_worker.py tests/test_market_infra_live_feed_health.py tests/test_boltodds_trial_audit.py tests/test_boltodds_migration_risk_audit.py -q
```

Expected:

```text
21 passed
```

- [ ] **Step 2: Run existing market/live layer tests**

Run:

```bash
python -m pytest tests/test_market_infra_provider_audit.py tests/test_market_infra_supabase_writer.py tests/test_live_layer_worker.py tests/test_shadow_propline_to_supabase.py -q
```

Expected: all tests pass.

- [ ] **Step 3: Confirm production files are still untouched**

Run:

```bash
git diff -- .github/workflows/pipeline.yml pipeline/run_pipeline.py pipeline/fetch_odds.py dashboard/data/processed/today.json data/picks_history.json
```

Expected: no output.

- [ ] **Step 4: Push the branch**

Run:

```bash
git push -u origin codex/boltodds-starter-trial
```

Expected: branch pushed.

---

### Task 11: Trial Activation After Tyler Provides the Key

**Files:**
- Read: `docs/boltodds-starter-trial.md`

- [ ] **Step 1: Set local key for discovery only**

Run in PowerShell:

```powershell
$env:BOLTODDS_API_KEY = Read-Host "Enter BoltOdds API key"
```

Expected: no output.

- [ ] **Step 2: Run discovery probe**

Run:

```bash
python scripts/probe_boltodds_markets.py
```

Expected if Starter works:

```json
{
  "starter_ready": true,
  "selected_markets": ["Pitcher Strikeouts"],
  "missing_books": []
}
```

Acceptable with caveat:

```json
{
  "starter_ready": true,
  "selected_markets": ["Pitcher Strikeouts"],
  "missing_books": ["kalshi"]
}
```

Blocking:

```json
{
  "starter_ready": false,
  "blocking_reasons": ["No MLB pitcher strikeout market matched configured aliases"]
}
```

- [ ] **Step 3: Apply Supabase migration**

Use the existing Supabase workflow for this repo. If using CLI:

```bash
supabase db push
```

Expected: migration applies without error.

- [ ] **Step 4: Deploy Render worker with env vars**

Set the Render service env vars exactly as listed in `docs/boltodds-starter-trial.md`.

Start command:

```bash
python scripts/boltodds_ws_worker.py
```

Expected Render logs:

```text
socket_connected
subscription_updated
```

or equivalent BoltOdds connection/subscription messages.

- [ ] **Step 5: Confirm Supabase rows**

Run:

```sql
select provider, mode, slate_date, status, books_seen, error_message, created_at
from market_provider_runs
where provider = 'boltodds'
order by created_at desc
limit 5;
```

Expected:

```text
provider=boltodds
mode=shadow_stream
status=started
error_message=null
```

- [ ] **Step 6: Confirm snapshots**

Run:

```sql
select provider, sport_key, market_key, bookmaker_key, player_name, side, line, american_odds, observed_at
from market_snapshots
where provider = 'boltodds'
order by observed_at desc
limit 20;
```

Expected: pitcher strikeout rows for target books.

---

## Trial Interpretation Rules

### Day 1

Goal: prove connection, market mapping, and row writes.

Do not judge ROI. Do not judge provider quality yet.

### Days 2-3

Goal: compare coverage to TheRundown and PropLine polling.

Look for:

- target books present
- same-line overlap
- line conflicts
- player name normalization misses
- stale periods

### Days 4-7

Goal: decide whether Starter earns a paid month.

Keep Starter only if:

- one connection is stable
- MLB pitcher strikeout market is available without Pro
- FanDuel/DraftKings are consistently useful
- BetRivers provides enough incremental value
- movement latency beats 10-minute polling enough to matter

## Promotion Gates After Trial

### Gate A: Shadow Notifications

Allow BoltOdds snapshots to create shadow `line_movement_events`, but do not send pushes.

Requirements:

- Match BoltOdds rows to current production picks by normalized pitcher, side, line, book, and slate date.
- Create deterministic dedupe keys so reconnects and repeated messages do not duplicate events.
- Classify movement as price-only, line-value, book-opened, book-removed, or stale-source correction.
- Compare candidate events against PropLine polling and production artifact movement.

### Gate B: Live Notifications

Send push notifications only for movement against current FIRE picks after dedupe is proven.

Requirements:

- Notify only when provider health is live.
- Notify only when the pick is still pre-lock and pre-game.
- Suppress duplicate movement for the same pick/book/side unless line or price crosses a new configured threshold.
- Keep a kill switch that disables BoltOdds pushes without stopping the production pipeline.

### Gate C: Fallback Provider

Use BoltOdds as fallback only when TheRundown misses a target book or PropLine is stale.

Requirements:

- Preserve `odds_source` attribution so BoltOdds rows can be audited separately.
- Prefer TheRundown for book-of-record lines unless a fallback condition is explicitly met.
- Run a post-slate conflict audit before trusting fallback rows in calibration or performance analysis.
- Never treat BoltOdds fallback coverage as proof that TheRundown is wrong without source freshness evidence.

### Gate D: Production Provider

Consider only after at least one full week of reliable Starter evidence and explicit Tyler approval.

Requirements:

- At least one paid-month review, not just the free trial.
- Stable coverage for FanDuel and DraftKings, with BetRivers incrementally useful.
- Known Kalshi answer: either supported well enough by BoltOdds or intentionally left on TheRundown.
- Documented cost, uptime, row volume, alert value, and rollback process.
- A clear migration plan for notification source, dashboard live overlay, provider arbitration, and retention.

## Post-Production Capabilities Still Missing

Even after the Starter trial implementation, the app will still not have these production capabilities:

- **Unified provider arbitration:** one place that decides TheRundown vs PropLine vs BoltOdds vs The Odds API by book, market, freshness, and fallback condition.
- **Live notification queue:** durable queue rows with dedupe, retry, notification status, and user-facing suppression rules.
- **Provider health dashboard:** visible last-message time, stale state, reconnect count, books seen, and snapshot volume.
- **Live dashboard overlay:** a frontend layer that shows live line movement separately from static `today.json`.
- **Retention policy:** raw WebSocket rows should roll into daily summaries instead of growing forever.
- **Migration audit:** a repeatable report showing coverage, conflicts, latency advantage, alert candidates, and row volume by slate.
- **Operational controls:** environment-level switches for provider mode, notification mode, watched books, stale thresholds, and emergency stop.
- **Rollback procedure:** a documented way to stop BoltOdds and return to TheRundown + PropLine polling without code changes.

## Recommended Post-Production Implementation Order

1. Add provider health visibility.
2. Add shadow movement events.
3. Add notification queue with no pushes.
4. Enable pushes for a narrow movement class, such as FIRE pick line moving against us.
5. Add dashboard live overlay for movement and source health.
6. Add fallback provider adapter for missing target books only.
7. Revisit broader provider migration after one paid month.

Do not skip directly from trial snapshots to production provider migration. The risk is not only bad data; it is bad timing, duplicate notifications, stale-source confidence, and user trust erosion.

## Self-Review

Spec coverage:

- 7-day free trial flow is covered by Tasks 9-11.
- Starter-only decision boundary is explicit in guardrails and trial interpretation.
- Render worker architecture is covered by Tasks 7 and 9.
- Supabase shadow storage is covered by Tasks 3, 7, and 8.
- Notifications are intentionally deferred to promotion gates, with shadow notification and live notification requirements now explicit.
- GitHub Actions remains production book-of-record during trial.
- Infrastructure recommendation, WebSocket capability delta, post-production roadmap, and migration failure modes are covered before implementation tasks.
- Operational hardening is covered by Task 8A before trial activation.

Placeholder scan:

- This plan avoids `TODO`, `TBD`, and open-ended implementation instructions.
- The only human-supplied secret is `BOLTODDS_API_KEY`, which must not be written into git.

Type consistency:

- Provider value is consistently `boltodds`.
- Worker mode is consistently `shadow_stream`.
- Discovery mode is consistently `discovery_probe`.
- Snapshot row fields match the existing `market_snapshots` table contract.
