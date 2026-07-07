# Mainline Best Price Notification Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace noisy book-by-book line movement pushes with one same-main-line best-price alert per pick when the best actionable book/odds materially changes between 10-minute live-layer intervals.

**Architecture:** Add a pure Python policy builder that compares previous and current `live_market_display_state` rows before the current rows are upserted. It derives the best same-line price from `book_rows` at the pick `k_line`, emits shadow summaries by default, and only sends `notification_events` when `LIVE_MAINLINE_PRICE_NOTIFICATION_MODE=send`. Existing raw `line_movement_events` remain audit evidence; send mode excludes the old raw movement notification rows from user-facing delivery.

**Tech Stack:** Python 3.11, pytest, Supabase Postgres migrations, Render `bbe-live-layer`, existing Netlify `send-live-notifications`, existing `live_market_display_state` and `notification_events`.

Date: 2026-07-07
Owner: Tyler + Codex
Status: Implemented in code, verified locally, default `off`, and not promoted
to `shadow` or `send`. Safe-subset verification completed on 2026-07-07 in the
`codex/mainline-best-price-notifications` worktree without applying migrations,
changing Render env vars, deploying, or pushing.

## 2026-07-07 Safe-Subset Verification Checkpoint

Local verification completed for the code-ready/off-by-default posture:

- `python -m pytest tests/test_mainline_price_notifications.py tests/test_market_infra_live_events.py tests/test_live_layer_worker.py tests/test_live_layer_schema.py -q`
  returned `84 passed in 0.63s`.
- `node --test tests/test_send_live_notifications_function.mjs` returned
  `20` passing tests and preserved the generic sender path for
  `mainline_best_price_changed`.
- `git diff --check` returned clean.
- `npx supabase db push --linked --dry-run` did not run in this worktree
  because the local Supabase CLI is not linked to a project:
  `Cannot find project ref. Have you run supabase link?`

What was intentionally not executed in this checkpoint:

- No `npx supabase db push --linked` apply.
- No Render env var changes, including
  `LIVE_MAINLINE_PRICE_NOTIFICATION_MODE` or
  `LIVE_MAINLINE_PRICE_MIN_CENTS`.
- No Render deploy.
- No verification queries against live `shadow_pipeline_runs` or
  `notification_events`.
- No push to GitHub.

Current rollout posture:

- Code path exists for `off|shadow|send`.
- Default posture stays `off`.
- First rollout, if separately approved, must be `shadow`.
- `send` remains closed until a later Tyler approval after shadow evidence.

## Global Constraints

- Do not change model math, provider order, official artifact source, thresholds, staking, lock behavior, retention deletion, dashboard source-of-truth, or Render env vars unless Tyler explicitly approves that separate step.
- TheRundown/approved TheRundown+PropLine artifact path remains production truth; PropLine live-market evidence is sidecar evidence only.
- BoltOdds remains retired and must not be used for current notification promotion.
- Default mode must be `off`; first rollout should use `shadow`; `send` requires a separate Tyler approval after shadow evidence.
- Mainline policy means same line as the pick `k_line`, not off-market alternate lines.
- One alert per pick/provider/side/state transition; no alert on first observation, stale evidence, locked picks, post-start picks, or unchanged best same-line price.
- Raw market movement rows can remain audit evidence, but in `send` mode raw line/price movement notification rows must not be inserted into `notification_events`.

---

## File Structure

- Create `market_infra/mainline_price_notifications.py`
  - Pure policy functions for deriving best same-line price, comparing previous/current display rows, and creating notification rows plus shadow summary.
- Create `tests/test_mainline_price_notifications.py`
  - Unit coverage for first-observation suppression, same-line price changes, off-line suppression, stale/locked/post-start suppression, and dedupe payload shape.
- Modify `scripts/build_live_events_to_supabase.py`
  - Fetch previous `live_market_display_state` rows before current upsert.
  - Build mainline policy rows after current display rows are computed.
  - Include shadow summary in `shadow_pipeline_runs.metadata`.
  - Include mainline notification rows only in `send` mode.
  - In `send` mode, keep raw `line_movement_events` upserts but exclude raw movement rows from `notification_events`.
- Modify `tests/test_live_layer_worker.py`
  - Worker integration tests for `off`, `shadow`, and `send` modes.
- Add `supabase/migrations/20260707190000_mainline_price_notification_event_type.sql`
  - Allow `mainline_best_price_changed` in `notification_events.event_type`.
- Modify `tests/test_live_layer_schema.py`
  - Assert the migration exists and includes the new event type constraint.
- Modify `tests/test_send_live_notifications_function.mjs`
  - Confirm Netlify sender handles the new event type using title/body/payload without special casing.
- Update docs after implementation
  - `docs/current-state.md`
  - `docs/superpowers/plans/2026-06-04-live-notification-digest-coordinator.md`
  - This plan, with final status, deploy id, and verification evidence.

---

### Task 1: Add Pure Mainline Best-Price Policy Builder

**Files:**
- Create: `market_infra/mainline_price_notifications.py`
- Create: `tests/test_mainline_price_notifications.py`

**Interfaces:**
- Consumes: `previous_rows: list[dict[str, Any]]`, `current_rows: list[dict[str, Any]]`, `observed_at: datetime | str`, `min_price_move_cents: int`.
- Produces: `build_mainline_best_price_notification_rows(...) -> MainlineBestPriceResult`.
- Later tasks rely on `MainlineBestPriceResult.notification_rows`, `MainlineBestPriceResult.shadow_rows`, and `MainlineBestPriceResult.summary`.

- [ ] **Step 1: Write failing unit tests**

Create `tests/test_mainline_price_notifications.py`:

```python
from datetime import datetime, timezone

from market_infra.mainline_price_notifications import (
    build_mainline_best_price_notification_rows,
)


NOW = datetime(2026, 7, 7, 18, 40, tzinfo=timezone.utc)


def _display_row(**overrides):
    row = {
        "slate_date": "2026-07-07",
        "pitcher": "Jacob Misiorowski",
        "normalized_pitcher": "jacob misiorowski",
        "side": "over",
        "provider": "propline",
        "current_verdict": "FIRE 1u",
        "k_line": 7.5,
        "game_time": "2026-07-07T23:40:00Z",
        "game_state": "pregame",
        "is_locked": False,
        "freshness_status": "fresh",
        "book_rows": [
            {"book": "fanduel", "line": 7.5, "odds": -120},
            {"book": "draftkings", "line": 7.5, "odds": -125},
            {"book": "kalshi", "line": 8.5, "odds": 900},
        ],
        "observed_at": "2026-07-07T18:40:00+00:00",
    }
    row.update(overrides)
    return row


def test_first_observation_is_shadow_only_no_notification():
    result = build_mainline_best_price_notification_rows(
        slate_date="2026-07-07",
        previous_rows=[],
        current_rows=[_display_row()],
        observed_at=NOW,
        min_price_move_cents=10,
        mode="shadow",
    )

    assert result.notification_rows == []
    assert result.summary["mode"] == "shadow"
    assert result.summary["first_seen_count"] == 1
    assert result.shadow_rows[0]["candidate_action"] == "first_seen_shadow"


def test_same_line_best_price_change_emits_one_send_row():
    result = build_mainline_best_price_notification_rows(
        slate_date="2026-07-07",
        previous_rows=[_display_row(book_rows=[
            {"book": "fanduel", "line": 7.5, "odds": -120},
            {"book": "draftkings", "line": 7.5, "odds": -125},
            {"book": "kalshi", "line": 8.5, "odds": 900},
        ])],
        current_rows=[_display_row(book_rows=[
            {"book": "fanduel", "line": 7.5, "odds": -105},
            {"book": "draftkings", "line": 7.5, "odds": -125},
            {"book": "kalshi", "line": 8.5, "odds": 900},
        ])],
        observed_at=NOW,
        min_price_move_cents=10,
        mode="send",
    )

    assert len(result.notification_rows) == 1
    row = result.notification_rows[0]
    assert row["event_type"] == "mainline_best_price_changed"
    assert row["title"] == "Best Price Better Now"
    assert row["body"] == (
        "Jacob Misiorowski OVER 7.5 best price -120->-105 at fanduel; "
        "same main line, price better"
    )
    assert row["payload"]["previous_best_odds"] == -120
    assert row["payload"]["current_best_odds"] == -105
    assert row["payload"]["price_delta"] == 15
    assert row["payload"]["current_best_book"] == "fanduel"


def test_off_line_alt_book_does_not_drive_best_price():
    result = build_mainline_best_price_notification_rows(
        slate_date="2026-07-07",
        previous_rows=[_display_row(book_rows=[
            {"book": "fanduel", "line": 7.5, "odds": -120},
            {"book": "kalshi", "line": 8.5, "odds": 900},
        ])],
        current_rows=[_display_row(book_rows=[
            {"book": "fanduel", "line": 7.5, "odds": -120},
            {"book": "kalshi", "line": 8.5, "odds": 1200},
        ])],
        observed_at=NOW,
        min_price_move_cents=10,
        mode="send",
    )

    assert result.notification_rows == []
    assert result.summary["off_line_ignored_count"] == 1


def test_stale_locked_and_post_start_rows_are_suppressed():
    stale = _display_row(freshness_status="stale")
    locked = _display_row(is_locked=True)
    post_start = _display_row(game_time="2026-07-07T18:30:00Z")

    result = build_mainline_best_price_notification_rows(
        slate_date="2026-07-07",
        previous_rows=[_display_row()],
        current_rows=[stale, locked, post_start],
        observed_at=NOW,
        min_price_move_cents=10,
        mode="send",
    )

    assert result.notification_rows == []
    assert result.summary["suppressed_stale_count"] == 1
    assert result.summary["suppressed_locked_count"] == 1
    assert result.summary["suppressed_post_start_count"] == 1
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_mainline_price_notifications.py -q
```

Expected: fail with `ModuleNotFoundError: No module named 'market_infra.mainline_price_notifications'`.

- [ ] **Step 3: Add the pure implementation**

Create `market_infra/mainline_price_notifications.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


TRACKED_SEND_MODES = {"shadow", "send"}


@dataclass(frozen=True)
class MainlineBestPriceResult:
    notification_rows: list[dict[str, Any]]
    shadow_rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _numeric(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _matches_line(value: float, target: float) -> bool:
    return abs(value - target) < 0.001


def _format_odds(value: int) -> str:
    return f"{value:+d}"


def _row_key(row: dict[str, Any]) -> tuple[str, str, str] | None:
    normalized = str(row.get("normalized_pitcher") or "").strip()
    side = str(row.get("side") or "").strip().lower()
    provider = str(row.get("provider") or "").strip().lower()
    if normalized and side in {"over", "under"} and provider:
        return normalized, side, provider
    return None


def _is_post_start(row: dict[str, Any], observed_at: datetime) -> bool:
    game_time = _parse_datetime(row.get("game_time"))
    return bool(game_time and observed_at >= game_time)


def _best_same_line_price(row: dict[str, Any]) -> dict[str, Any] | None:
    pick_line = _numeric(row.get("k_line"))
    book_rows = row.get("book_rows")
    if pick_line is None or not isinstance(book_rows, list):
        return None

    same_line: list[dict[str, Any]] = []
    for book_row in book_rows:
        if not isinstance(book_row, dict):
            continue
        line = _numeric(book_row.get("line"))
        odds = _integer(book_row.get("odds"))
        book = str(book_row.get("book") or "").strip().lower()
        if line is None or odds is None or not book:
            continue
        if _matches_line(line, pick_line):
            same_line.append({"book": book, "line": line, "odds": odds})

    if not same_line:
        return None
    return sorted(same_line, key=lambda item: (-int(item["odds"]), item["book"]))[0]


def _body(
    *,
    pitcher: str,
    side: str,
    line: float,
    previous_odds: int,
    current_odds: int,
    current_book: str,
    better: bool,
) -> str:
    label = "better" if better else "worse"
    return (
        f"{pitcher} {side.upper()} {line:g} best price "
        f"{_format_odds(previous_odds)}->{_format_odds(current_odds)} at {current_book}; "
        f"same main line, price {label}"
    )


def build_mainline_best_price_notification_rows(
    *,
    slate_date: str,
    previous_rows: list[dict[str, Any]],
    current_rows: list[dict[str, Any]],
    observed_at: datetime | str,
    min_price_move_cents: int,
    mode: str,
) -> MainlineBestPriceResult:
    observed = _parse_datetime(observed_at) or datetime.now(timezone.utc)
    normalized_mode = str(mode or "off").strip().lower()
    summary: dict[str, Any] = {
        "mode": normalized_mode,
        "input_count": len(current_rows),
        "candidate_count": 0,
        "notification_count": 0,
        "first_seen_count": 0,
        "unchanged_count": 0,
        "below_threshold_count": 0,
        "off_line_ignored_count": 0,
        "suppressed_stale_count": 0,
        "suppressed_locked_count": 0,
        "suppressed_post_start_count": 0,
    }
    if normalized_mode not in TRACKED_SEND_MODES:
        return MainlineBestPriceResult([], [], summary)

    previous_by_key = {
        key: row
        for row in previous_rows
        if (key := _row_key(row)) is not None
    }
    notification_rows: list[dict[str, Any]] = []
    shadow_rows: list[dict[str, Any]] = []

    for current in current_rows:
        key = _row_key(current)
        if key is None:
            continue
        normalized, side, provider = key
        if not str(current.get("current_verdict") or "").startswith("FIRE"):
            continue
        if str(current.get("freshness_status") or "fresh") != "fresh":
            summary["suppressed_stale_count"] += 1
            continue
        if current.get("is_locked") or str(current.get("game_state") or "").lower() in {"locked", "in_progress", "final", "completed", "postponed"}:
            summary["suppressed_locked_count"] += 1
            continue
        if _is_post_start(current, observed):
            summary["suppressed_post_start_count"] += 1
            continue

        current_best = _best_same_line_price(current)
        if current_best is None:
            summary["off_line_ignored_count"] += 1
            continue
        previous = previous_by_key.get(key)
        previous_best = _best_same_line_price(previous) if previous else None
        if previous_best is None:
            summary["first_seen_count"] += 1
            shadow_rows.append({
                "candidate_action": "first_seen_shadow",
                "slate_date": slate_date,
                "normalized_pitcher": normalized,
                "side": side,
                "provider": provider,
                "current_best": current_best,
            })
            continue

        price_delta = int(current_best["odds"]) - int(previous_best["odds"])
        if price_delta == 0:
            summary["unchanged_count"] += 1
            continue
        if abs(price_delta) < max(1, int(min_price_move_cents)):
            summary["below_threshold_count"] += 1
            continue

        summary["candidate_count"] += 1
        better = price_delta > 0
        pitcher = str(current.get("pitcher") or normalized).strip()
        line = float(current_best["line"])
        shadow_row = {
            "candidate_action": "would_send" if normalized_mode == "send" else "would_send_shadow",
            "slate_date": slate_date,
            "pitcher": pitcher,
            "normalized_pitcher": normalized,
            "side": side,
            "provider": provider,
            "previous_best": previous_best,
            "current_best": current_best,
            "price_delta": price_delta,
            "observed_at": observed.isoformat(),
        }
        shadow_rows.append(shadow_row)
        if normalized_mode != "send":
            continue

        dedupe_key = (
            f"{slate_date}:mainline_best_price:{provider}:{normalized}:{side}:"
            f"{line:g}:{previous_best['odds']}:{current_best['book']}:{current_best['odds']}"
        )
        notification_rows.append({
            "slate_date": slate_date,
            "event_type": "mainline_best_price_changed",
            "severity": "watch" if better else "action",
            "title": "Best Price Better Now" if better else "Best Price Worse Now",
            "body": _body(
                pitcher=pitcher,
                side=side,
                line=line,
                previous_odds=int(previous_best["odds"]),
                current_odds=int(current_best["odds"]),
                current_book=str(current_best["book"]),
                better=better,
            ),
            "url": "/",
            "dedupe_key": dedupe_key,
            "payload": {
                "pitcher": pitcher,
                "normalized_pitcher": normalized,
                "side": side,
                "provider": provider,
                "k_line": line,
                "previous_best_book": previous_best["book"],
                "previous_best_odds": previous_best["odds"],
                "current_best_book": current_best["book"],
                "current_best_odds": current_best["odds"],
                "price_delta": price_delta,
                "game_time": current.get("game_time"),
                "game_state": current.get("game_state"),
                "is_locked": current.get("is_locked"),
            },
            "occurred_at": observed.isoformat(),
        })

    summary["notification_count"] = len(notification_rows)
    return MainlineBestPriceResult(notification_rows, shadow_rows, summary)
```

- [ ] **Step 4: Run unit tests to verify pass**

Run:

```bash
python -m pytest tests/test_mainline_price_notifications.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit**

Run:

```bash
git add market_infra/mainline_price_notifications.py tests/test_mainline_price_notifications.py
git commit -m "feat: add mainline best price notification policy"
```

Expected: commit succeeds with only the two new files.

---

### Task 2: Wire Shadow Mode Into Live Layer

**Files:**
- Modify: `scripts/build_live_events_to_supabase.py`
- Modify: `tests/test_live_layer_worker.py`

**Interfaces:**
- Consumes: `build_mainline_best_price_notification_rows(...)` from Task 1.
- Produces: `result["mainline_best_price_notifications"]`, `result["mainline_best_price_shadow_rows"]`, and `shadow_pipeline_runs.metadata.mainline_best_price_notifications`.

- [ ] **Step 1: Write failing worker shadow-mode test**

Append to `tests/test_live_layer_worker.py`:

```python
def test_mainline_best_price_shadow_mode_records_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_MAINLINE_PRICE_NOTIFICATION_MODE", "shadow")
    monkeypatch.setenv("LIVE_MAINLINE_PRICE_MIN_CENTS", "10")
    pitcher = _fire_pitcher(pitcher="Jacob Misiorowski")
    pitcher["k_line"] = 7.5
    today = _write_artifact(tmp_path, [pitcher])
    previous_state = _previous_fire_state("Jacob Misiorowski", game_time="2026-05-06T22:10:00Z")
    previous_state["normalized_pitcher"] = "jacob misiorowski"
    previous_state["k_line"] = 7.5

    previous_display = {
        "slate_date": "2026-05-06",
        "pitcher": "Jacob Misiorowski",
        "normalized_pitcher": "jacob misiorowski",
        "side": "over",
        "provider": "propline",
        "current_verdict": "FIRE 1u",
        "k_line": 7.5,
        "game_time": "2026-05-06T22:10:00Z",
        "game_state": "scheduled",
        "is_locked": False,
        "freshness_status": "fresh",
        "book_rows": [{"book": "fanduel", "line": 7.5, "odds": -120}],
    }
    writer = _writer_with_selects({
        "live_pick_state": [previous_state],
        "market_snapshots": [
            {
                "id": "snapshot-1",
                "provider": "propline",
                "provider_event_id": "game-1",
                "normalized_player_name": "jacob misiorowski",
                "player_name": "Jacob Misiorowski",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 7.5,
                "american_odds": -105,
                "observed_at": "2026-05-06T18:00:00+00:00",
            },
        ],
        "live_market_display_state": [previous_display],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["mainline_best_price_notifications"] == 0
    assert result["mainline_best_price"]["mode"] == "shadow"
    assert result["mainline_best_price"]["candidate_count"] == 1
    assert result["shadow_pipeline_timing"]["pipeline_run_row"]["metadata"]["mainline_best_price"]["candidate_count"] == 1
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
python -m pytest tests/test_live_layer_worker.py::test_mainline_best_price_shadow_mode_records_summary -q
```

Expected: fail because `mainline_best_price` is not in the result.

- [ ] **Step 3: Implement shadow wiring**

In `scripts/build_live_events_to_supabase.py`, add the import near the other `market_infra` imports:

```python
from market_infra.mainline_price_notifications import (  # noqa: E402
    build_mainline_best_price_notification_rows,
)
```

Add helpers near `_notification_coordinator_mode()`:

```python
def _mainline_best_price_notification_mode() -> str:
    value = os.getenv("LIVE_MAINLINE_PRICE_NOTIFICATION_MODE", "off").strip().lower()
    return value if value in {"off", "shadow", "send"} else "off"


def _mainline_best_price_min_cents() -> int:
    return max(1, _env_int("LIVE_MAINLINE_PRICE_MIN_CENTS", default=10))
```

Before building `market_pick_evidence_rows`, fetch previous display rows:

```python
    previous_live_market_display_rows = writer.select_rows(
        "live_market_display_state",
        {"slate_date": f"eq.{slate_date}"},
    )
```

After `live_market_display_rows = build_live_market_display_rows(...)`, add:

```python
    mainline_best_price_result = build_mainline_best_price_notification_rows(
        slate_date=slate_date,
        previous_rows=previous_live_market_display_rows,
        current_rows=live_market_display_rows,
        observed_at=observed_at,
        min_price_move_cents=_mainline_best_price_min_cents(),
        mode=_mainline_best_price_notification_mode(),
    )
```

Add the summary to `_write_shadow_pipeline_timing(... metadata_extra={...})`:

```python
            "mainline_best_price": mainline_best_price_result.summary,
```

Add the result fields in the returned dict:

```python
        "mainline_best_price": mainline_best_price_result.summary,
        "mainline_best_price_shadow_rows": mainline_best_price_result.shadow_rows,
        "mainline_best_price_notifications": len(mainline_best_price_result.notification_rows),
```

- [ ] **Step 4: Run worker shadow test**

Run:

```bash
python -m pytest tests/test_live_layer_worker.py::test_mainline_best_price_shadow_mode_records_summary -q
```

Expected: pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add scripts/build_live_events_to_supabase.py tests/test_live_layer_worker.py
git commit -m "feat: shadow mainline best price notification policy"
```

Expected: commit succeeds.

---

### Task 3: Add Send Mode And Suppress Old Raw Movement Sends

**Files:**
- Modify: `scripts/build_live_events_to_supabase.py`
- Modify: `tests/test_live_layer_worker.py`
- Create: `supabase/migrations/20260707190000_mainline_price_notification_event_type.sql`
- Modify: `tests/test_live_layer_schema.py`

**Interfaces:**
- Consumes: `mainline_best_price_result.notification_rows`.
- Produces: `notification_events.event_type='mainline_best_price_changed'`.

- [ ] **Step 1: Write failing send-mode worker test**

Append to `tests/test_live_layer_worker.py`:

```python
def test_mainline_best_price_send_mode_replaces_raw_movement_notifications(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_MAINLINE_PRICE_NOTIFICATION_MODE", "send")
    monkeypatch.setenv("LIVE_MAINLINE_PRICE_MIN_CENTS", "10")
    pitcher = _fire_pitcher(pitcher="Jacob Misiorowski")
    pitcher["k_line"] = 7.5
    today = _write_artifact(tmp_path, [pitcher])
    previous_state = _previous_fire_state("Jacob Misiorowski", game_time="2026-05-06T22:10:00Z")
    previous_state["normalized_pitcher"] = "jacob misiorowski"
    previous_state["k_line"] = 7.5

    previous_display = {
        "slate_date": "2026-05-06",
        "pitcher": "Jacob Misiorowski",
        "normalized_pitcher": "jacob misiorowski",
        "side": "over",
        "provider": "propline",
        "current_verdict": "FIRE 1u",
        "k_line": 7.5,
        "game_time": "2026-05-06T22:10:00Z",
        "game_state": "scheduled",
        "is_locked": False,
        "freshness_status": "fresh",
        "book_rows": [{"book": "fanduel", "line": 7.5, "odds": -120}],
    }
    writer = _writer_with_selects({
        "live_pick_state": [previous_state],
        "market_snapshots": [
            {
                "id": "snapshot-old",
                "provider": "propline",
                "provider_event_id": "game-1",
                "normalized_player_name": "jacob misiorowski",
                "player_name": "Jacob Misiorowski",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 7.5,
                "american_odds": -120,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "snapshot-new",
                "provider": "propline",
                "provider_event_id": "game-1",
                "normalized_player_name": "jacob misiorowski",
                "player_name": "Jacob Misiorowski",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 7.5,
                "american_odds": -105,
                "observed_at": "2026-05-06T18:00:00+00:00",
            },
        ],
        "live_market_display_state": [previous_display],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["line_movement_events"] == 1
    assert result["mainline_best_price_notifications"] == 1
    assert [row["event_type"] for row in result["notification_rows"]] == [
        "mainline_best_price_changed"
    ]
```

- [ ] **Step 2: Add schema migration test**

In `tests/test_live_layer_schema.py`, add:

```python
MAINLINE_PRICE_NOTIFICATION_MIGRATION = (
    MIGRATIONS_DIR / "20260707190000_mainline_price_notification_event_type.sql"
)


def test_mainline_price_notification_migration_allows_event_type():
    sql = MAINLINE_PRICE_NOTIFICATION_MIGRATION.read_text(encoding="utf-8")

    assert "drop constraint if exists notification_events_event_type_check" in sql
    assert "add constraint notification_events_event_type_check" in sql
    assert "mainline_best_price_changed" in sql
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_live_layer_worker.py::test_mainline_best_price_send_mode_replaces_raw_movement_notifications tests/test_live_layer_schema.py::test_mainline_price_notification_migration_allows_event_type -q
```

Expected: fail because send mode is not wired and the migration file does not exist.

- [ ] **Step 4: Implement send-mode routing**

In `scripts/build_live_events_to_supabase.py`, replace the `notification_rows = [...]` block with:

```python
    movement_rows_for_notifications = movement_notification_rows
    webhook_rows_for_notifications = propline_webhook_notification_rows
    if mainline_best_price_result.summary.get("mode") == "send":
        movement_rows_for_notifications = []
        webhook_rows_for_notifications = []

    notification_rows = [
        *pick_notification_rows,
        *missing_notification_rows,
        *movement_rows_for_notifications,
        *webhook_rows_for_notifications,
        *mainline_best_price_result.notification_rows,
        *reminder_notification_rows,
    ]
```

This preserves `line_movement_rows = build_line_movement_rows(movement_notification_rows)` and the `line_movement_events` upsert for audit.

- [ ] **Step 5: Create migration**

Create `supabase/migrations/20260707190000_mainline_price_notification_event_type.sql`:

```sql
alter table public.notification_events
  drop constraint if exists notification_events_event_type_check;
alter table public.notification_events
  add constraint notification_events_event_type_check
  check (
    event_type in (
      'new_fire_pick',
      'pick_upgraded',
      'pick_downgraded',
      'line_moved_with_us',
      'line_moved_against_us',
      'game_reminder_due',
      'webhook_received',
      'source_degraded',
      'start_window_digest',
      'new_fire_pick_digest',
      'pick_upgraded_digest',
      'pick_downgraded_digest',
      'mainline_best_price_changed'
    )
  );
comment on constraint notification_events_event_type_check
  on public.notification_events is
  'Allows default individual notification events, promoted digest event types, and mainline best-price movement alerts.';
```

- [ ] **Step 6: Run send-mode and schema tests**

Run:

```bash
python -m pytest tests/test_live_layer_worker.py::test_mainline_best_price_send_mode_replaces_raw_movement_notifications tests/test_live_layer_schema.py::test_mainline_price_notification_migration_allows_event_type -q
```

Expected: `2 passed`.

- [ ] **Step 7: Commit**

Run:

```bash
git add scripts/build_live_events_to_supabase.py tests/test_live_layer_worker.py tests/test_live_layer_schema.py supabase/migrations/20260707190000_mainline_price_notification_event_type.sql
git commit -m "feat: send mainline best price notifications"
```

Expected: commit succeeds.

---

### Task 4: Verify Netlify Sender Compatibility

**Files:**
- Modify: `tests/test_send_live_notifications_function.mjs`

**Interfaces:**
- Consumes: `notification_events` row with `event_type='mainline_best_price_changed'`.
- Produces: proof that sender uses existing title/body/payload path and suppresses post-start rows by payload `game_time`.

- [ ] **Step 1: Add sender test**

Append to `tests/test_send_live_notifications_function.mjs`:

```javascript
test('sends mainline best price notification rows through generic sender path', async () => {
  const event = eventRow({
    id: 'mainline-price-1',
    event_type: 'mainline_best_price_changed',
    title: 'Best Price Better Now',
    body: 'Jacob Misiorowski OVER 7.5 best price -120->-105 at fanduel; same main line, price better',
    dedupe_key: '2026-07-07:mainline_best_price:propline:jacob misiorowski:over:7.5:-120:fanduel:-105',
    payload: {
      pitcher: 'Jacob Misiorowski',
      normalized_pitcher: 'jacob misiorowski',
      side: 'over',
      provider: 'propline',
      k_line: 7.5,
      previous_best_book: 'fanduel',
      previous_best_odds: -120,
      current_best_book: 'fanduel',
      current_best_odds: -105,
      price_delta: 15,
      game_time: '2026-07-07T23:40:00Z',
    },
  });

  const { calls } = await runSender({
    events: [event],
    subscriptions: [subscriptionRow()],
    now: '2026-07-07T18:40:00.000Z',
  });

  assert.equal(calls.push.length, 1);
  assert.equal(calls.push[0].payload.title, 'Best Price Better Now');
  assert.equal(calls.push[0].payload.tag, event.dedupe_key);
});
```

- [ ] **Step 2: Run sender test**

Run:

```bash
node --test tests/test_send_live_notifications_function.mjs
```

Expected: pass with the existing sender implementation. If it fails because helper names differ, update only the test fixture names to match existing helper functions; do not add event-type-specific sender code unless the failure proves it is necessary.

- [ ] **Step 3: Commit if the test required changes**

Run:

```bash
git add tests/test_send_live_notifications_function.mjs
git commit -m "test: cover mainline best price notification sends"
```

Expected: commit succeeds if the test was added.

---

### Task 5: Deployment And Shadow Soak

**Files:**
- Modify: `docs/current-state.md`
- Modify: `docs/superpowers/plans/2026-06-04-live-notification-digest-coordinator.md`
- Modify: `docs/superpowers/plans/2026-07-07-mainline-best-price-notification-policy.md`

**Interfaces:**
- Consumes: all prior task commits.
- Produces: Render live-layer deployed in `shadow` first, with documented verification evidence.

- [ ] **Step 1: Run full verification**

Run:

```bash
python -m pytest tests/test_mainline_price_notifications.py tests/test_market_infra_live_events.py tests/test_live_layer_worker.py tests/test_live_layer_schema.py -q
node --test tests/test_send_live_notifications_function.mjs
git diff --check
```

Expected:

```text
pytest exits 0
node --test exits 0
git diff --check exits 0, allowing existing CRLF warnings only
```

- [ ] **Step 2: Apply Supabase migration dry-run**

Run:

```bash
npx supabase db push --linked --dry-run
```

Expected: dry run includes only `20260707190000_mainline_price_notification_event_type.sql` for this feature.

- [ ] **Step 3: Apply Supabase migration after Tyler approves**

Run only after approval:

```bash
npx supabase db push --linked
```

Expected: migration applies successfully. Do not print database secrets.

- [ ] **Step 4: Set shadow env only after Tyler approves**

Set on Render `bbe-live-layer` only:

```text
LIVE_MAINLINE_PRICE_NOTIFICATION_MODE=shadow
LIVE_MAINLINE_PRICE_MIN_CENTS=10
```

Do not change provider flags, notification coordinator mode, lock flags, model flags, or source-of-truth flags.

- [ ] **Step 5: Deploy `bbe-live-layer`**

Run:

```bash
git push origin main
render deploys create crn-d7tpb19o3t8c739p3qig --wait --confirm
```

Expected: deploy status `live` on the latest commit.

- [ ] **Step 6: Verify first post-deploy shadow run**

Run:

```bash
npx supabase db query --linked -o json "select observed_at, slate_date, metadata->'mainline_best_price' as mainline_best_price from public.shadow_pipeline_runs order by observed_at desc limit 3;"
```

Expected: latest run after deploy has `mainline_best_price.mode = "shadow"` and reports candidate counts without sending `mainline_best_price_changed` rows.

- [ ] **Step 7: Verify no send-mode rows during shadow**

Run:

```bash
npx supabase db query --linked -o json "select count(*) as rows from public.notification_events where event_type = 'mainline_best_price_changed' and created_at >= now() - interval '2 hours';"
```

Expected: `rows = 0` while mode is `shadow`.

- [ ] **Step 8: Update docs and commit**

Update docs with:

```markdown
Status: Implemented in shadow only; not promoted to send.
Evidence: first Render bbe-live-layer run observed at a concrete ISO timestamp copied from `shadow_pipeline_runs.observed_at`; mainline_best_price summary present; notification_events rows for mainline_best_price_changed = 0 in shadow.
Closed gates: send mode, raw movement replacement, new notification class promotion.
```

Run:

```bash
git add docs/current-state.md docs/superpowers/plans/2026-06-04-live-notification-digest-coordinator.md docs/superpowers/plans/2026-07-07-mainline-best-price-notification-policy.md
git commit -m "docs: record mainline best price notification shadow posture"
git push origin main
```

Expected: docs commit pushed.

---

## Self-Review

**Spec coverage:** The plan implements Tyler's requested 10-minute best-price-at-main-line check by deriving best same-line book/odds from current and previous `live_market_display_state` rows. It keeps raw movement audit rows, suppresses noisy alternate-line notification sends in send mode, and stages the policy behind `off|shadow|send`.

**Placeholder scan:** No task uses forbidden placeholder language or unspecified validation. Each code task has concrete test code, implementation code, commands, and expected outcomes.

**Type consistency:** `build_mainline_best_price_notification_rows(...)` returns `MainlineBestPriceResult` with `notification_rows`, `shadow_rows`, and `summary` in every task. The worker tasks use the same result fields and the event type is consistently `mainline_best_price_changed`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-07-mainline-best-price-notification-policy.md`. Two execution options:

**1. Subagent-Driven (recommended)** - Dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
