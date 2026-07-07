# Live Notification Digest Coordinator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace same-category notification piles with grouped digests while keeping individual market-movement alerts, strengthened by BoltOdds/PropLine confirmation evidence.

**Architecture:** Add a pure notification coordinator between the existing live-layer event builders and the `notification_events` insert. The coordinator groups start-window reminders and same-run pick-change events, leaves line/price movement individual, and records enough source-event context for audit and later UI deep links. All behavior starts behind a shadow/off flag and does not change model math, provider order, thresholds, staking, locks, grading, artifacts, or dashboard defaults.

**Tech Stack:** Python 3.11, pytest, Render `bbe-live-layer`, Supabase `notification_events`, existing Netlify `send-live-notifications`, existing live-market evidence tables.

---

Date: 2026-06-04
Owner: Tyler + Codex
Status: Implemented, merged to `main`, deployed to Render `bbe-live-layer`,
and promoted to grouped mode on 2026-06-07 after Tyler approval. Supabase digest
event types are allowed. Grouped production sends are enabled only for
start-window reminders and same-run pick-change classes; line/price movement
alerts remain individual.

2026-07-07 verification note: the separate
`2026-07-07-mainline-best-price-notification-policy.md` feature is implemented
in code and verified locally, but it is not part of this grouped-mode approval.
It remains default-`off` pending a linked Supabase dry run, Tyler-approved
shadow env flip, and post-deploy verification. This plan still controls grouped
digest classes only.

## 2026-06-07 Grouped Promotion Checkpoint

Tyler approved promoting the notification grouping change on 2026-06-07.
Render `bbe-live-layer` was updated to:

- `LIVE_NOTIFICATION_COORDINATOR_MODE=grouped`
- `LIVE_NOTIFICATION_GROUP_START_WINDOWS=true`
- `LIVE_NOTIFICATION_GROUP_PICK_CHANGES=true`

This promotion changes only the notification queue rows for approved grouped
classes. It does not change model math, thresholds, staking, provider order,
locks, grading, artifacts, retention, or dashboard source-of-truth behavior.
Rollback is one environment-variable change:
`LIVE_NOTIFICATION_COORDINATOR_MODE=off`, followed by a live-layer redeploy.

## 2026-06-04 Implementation Checkpoint

Commit `046cc525` adds the pure coordinator, live-layer wiring, shadow
movement-strength labels, audit label counts, and a Supabase migration that
allows digest event types. On 2026-06-04, Render `bbe-live-layer` was deployed
on that commit and configured with:

- `LIVE_NOTIFICATION_COORDINATOR_MODE=shadow`
- `LIVE_NOTIFICATION_GROUP_START_WINDOWS=true`
- `LIVE_NOTIFICATION_GROUP_PICK_CHANGES=true`

The 2026-06-04 18:31 UTC live-layer run wrote
`shadow_pipeline_runs.metadata.notification_coordinator` with `mode=shadow` and
both grouping flags true. That pass had `input_count=0` / `grouped_count=0`, so
it proved runtime wiring but did not yet prove a real digest opportunity.
Current user-facing notification sends remain individual until a separate
promotion step.

## 2026-06-04 Schema Prep Checkpoint

Tyler approved applying the digest-event schema prep while keeping grouped sends
disabled. The local migration
`supabase/migrations/20260604172500_notification_digest_event_types.sql` was
applied directly to the linked Supabase database because `supabase db push`
would have encountered unrelated older local/remote migration-history drift.
The migration history was repaired for version `20260604172500` only.

Functional verification used a transaction that inserted a
`start_window_digest` notification row and immediately rolled it back; the query
returned `digest_event_type_insert_rollback_ok=true`. No production notification
row was left behind. `LIVE_NOTIFICATION_COORDINATOR_MODE` remains `shadow`.

## Operating Decision

Tyler's product goal is to make notifications useful as a triage layer, not a
10-minute pile of individual pitcher pushes.

Current live-layer behavior:

- `build_pick_change_events` emits one notification per pitcher/side for
  `new_fire_pick`, `pick_upgraded`, and `pick_downgraded`.
- `build_reminder_events` emits one reminder per pitcher/side.
- `build_line_movement_events` emits individual provider/book movement events.
- Netlify `send-live-notifications` sends whatever fresh rows are queued in
  `notification_events`.

Target behavior:

- Group start reminders for games in the same 30-minute start window.
- Group same-category pick changes produced by the same 10-minute Render run.
- Keep line/price movement individual, but label it with stronger evidence from
  PropLine polling/webhooks, BoltOdds snapshots/heartbeats, broad confirmation,
  volatility, and single-book noise.
- Promote one class at a time after shadow review.

## Plan Consolidation

This plan is the near-term implementation child of
`2026-05-20-live-notification-coordinator.md`.

Do not physically merge provider, notification, UI, and model plans into one
document:

- Provider readiness stays controlled by
  `2026-05-13-boltodds-propline-official-provider-cutover.md`.
- Notification grouping and movement-alert quality are controlled here.
- The future dashboard market panel stays controlled by
  `2026-05-20-live-market-decision-ui.md`.
- Gate C/Gate F model research stays shadow-only and separate.

The shared contract across notification and UI plans is the decision-label
vocabulary: `bet_now`, `shop_price`, `wait`, `monitor`, `ignore_stale`, and
`system_issue`.

## Non-Goals

- Do not change model math, thresholds, staking, or calibration.
- Do not change provider order or strict provider mode.
- Do not enable new BoltOdds/PropLine production movement sends without the
  notification-specific gates below.
- Do not change lock timing or grading.
- Do not change dashboard artifacts or make the market UI default-on.
- Do not add another Supabase table unless the existing queue/metadata cannot
  support audit.

## Notification Classes

### Grouped Classes

Start-window digest:

- Inputs: current `game_reminder_due` rows.
- Group key: `slate_date`, 30-minute game-time bucket, reminder family.
- Send shape: one push per bucket.
- Example title: `6 tracked pitchers start by 4:00 PM Phoenix`.
- Example body: `3 FIRE, 2 LEAN, 1 watch. Open app for final prices.`

Pick-change digest:

- Inputs: `new_fire_pick`, `pick_upgraded`, `pick_downgraded`.
- Group key: `slate_date`, event type, live-layer observed run bucket.
- Keep upgrades and downgrades separate.
- Send shape: one push per event type per Render run when there are multiple
  rows; single-row events may keep the existing body.
- Example title: `3 picks upgraded`.
- Example body: `2 FIRE upgrades, 1 LEAN->FIRE. Open app to review.`

Lock-batch digest:

- Already conceptually covered by the older coordinator plan.
- Do not implement until start-window and pick-change digests are stable.

### Individual Classes

Line/price movement:

- Keep individual because the action is pitcher/book/side-specific.
- Strengthen the alert before broad production promotion by adding evidence
  labels:
  - `single_book`
  - `broad_confirmation`
  - `propline_polling_confirmed`
  - `propline_webhook_confirmed`
  - `boltodds_confirmed`
  - `provider_conflict`
  - `volatile_or_reversed`
  - `stale_or_heartbeat_missing`
- First production candidate should be narrow: active FIRE picks only, fresh
  state only, and either `broad_confirmation` or explicit provider confirmation.

System health:

- Keep individual and sparse.
- Do not mix technical failures with betting-action digest copy.

## Promotion Sequence

1. Add a pure coordinator in `shadow` mode and leave current sends unchanged.
2. Compare coordinator output against actual queued/sent pushes for at least one
   clean slate.
3. Enable grouped start-window digests first.
4. Enable grouped pick-change digests second.
5. Add movement-strength labels in shadow.
6. Promote one narrow movement-alert class only after the shadow rows show
   decision value and low noise.
7. Hand the same labels to the future UI market panel.

## File Map

- Create: `market_infra/notification_coordinator.py`
  - Pure grouping and pass-through helpers.
- Modify: `scripts/build_live_events_to_supabase.py`
  - Apply coordinator before `notification_events` insert when enabled.
  - Include coordinator shadow summary in run result and
    `shadow_pipeline_runs.metadata`.
- Modify: `market_infra/live_events.py`
  - Add source context to reminder and pick-change payloads only if needed by
    the pure coordinator.
- Modify: `market_infra/shadow_notification_candidates.py`
  - Add movement-strength labels for provider-backed movement candidates.
- Create or modify: `analytics/diagnostics/shadow_notification_candidate_audit.py`
  - Include digest opportunities and movement-strength counts.
- Tests:
  - `tests/test_notification_coordinator.py`
  - `tests/test_live_layer_worker.py`
  - `tests/test_market_infra_shadow_notification_candidates.py`
  - `tests/test_shadow_notification_candidate_audit.py`

## Environment Flags

Add one coordinator mode flag:

```text
LIVE_NOTIFICATION_COORDINATOR_MODE=off|shadow|grouped
```

Defaults:

- `off`: current behavior.
- `shadow`: compute grouped rows and summary, but insert the original current
  notification rows.
- `grouped`: insert grouped rows for approved grouped classes and pass through
  individual movement/system rows.

Optional future class flags:

```text
LIVE_NOTIFICATION_GROUP_START_WINDOWS=true|false
LIVE_NOTIFICATION_GROUP_PICK_CHANGES=true|false
LIVE_NOTIFICATION_MOVEMENT_STRENGTH_SHADOW=true|false
```

Class flags should default false until the corresponding shadow review passes.

## Task 1: Add Pure Coordinator Tests

**Files:**
- Create: `tests/test_notification_coordinator.py`
- Create: `market_infra/notification_coordinator.py`

- [ ] **Step 1: Write grouped reminder test**

Create `tests/test_notification_coordinator.py`:

```python
from datetime import datetime, timezone

from market_infra import notification_coordinator as coordinator


NOW = datetime(2026, 6, 4, 17, 0, tzinfo=timezone.utc).isoformat()


def _event(event_type, pitcher, *, game_time="2026-06-04T17:30:00+00:00", verdict="FIRE 1u"):
    normalized = pitcher.lower()
    return {
        "slate_date": "2026-06-04",
        "event_type": event_type,
        "severity": "action",
        "title": "Pick Starts Soon",
        "body": f"{pitcher} {verdict}",
        "url": "/",
        "dedupe_key": f"2026-06-04:{event_type}:{normalized}",
        "payload": {
            "pitcher": pitcher,
            "normalized_pitcher": normalized,
            "side": "over",
            "verdict": verdict,
            "k_line": 5.5,
            "game_time": game_time,
        },
        "occurred_at": NOW,
    }


def test_start_window_digest_groups_same_30_minute_bucket():
    rows = [
        _event("game_reminder_due", "Pitcher A", game_time="2026-06-04T17:30:00+00:00"),
        _event("game_reminder_due", "Pitcher B", game_time="2026-06-04T17:45:00+00:00"),
    ]

    result = coordinator.coordinate_notification_rows(
        rows,
        mode="grouped",
        observed_at=NOW,
        group_start_windows=True,
    )

    assert len(result.notification_rows) == 1
    digest = result.notification_rows[0]
    assert digest["event_type"] == "start_window_digest"
    assert digest["dedupe_key"] == "2026-06-04:digest:start_window:2026-06-04T17:30:00+00:00"
    assert digest["payload"]["source_event_count"] == 2
    assert digest["payload"]["source_dedupe_keys"] == [
        "2026-06-04:game_reminder_due:pitcher a",
        "2026-06-04:game_reminder_due:pitcher b",
    ]
```

- [ ] **Step 2: Run test to verify failure**

Run:

```powershell
python -m pytest tests/test_notification_coordinator.py::test_start_window_digest_groups_same_30_minute_bucket -q
```

Expected: fail because `market_infra.notification_coordinator` does not exist.

- [ ] **Step 3: Commit failing test if using strict TDD**

```powershell
git add tests/test_notification_coordinator.py
git commit -m "test: add notification digest coordinator contract"
```

## Task 2: Implement Minimal Coordinator

**Files:**
- Modify: `market_infra/notification_coordinator.py`
- Test: `tests/test_notification_coordinator.py`

- [ ] **Step 1: Add dataclass and pass-through mode**

Create `market_infra/notification_coordinator.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


GROUPABLE_PICK_CHANGE_TYPES = {"new_fire_pick", "pick_upgraded", "pick_downgraded"}


@dataclass(frozen=True)
class CoordinationResult:
    notification_rows: list[dict[str, Any]]
    shadow_rows: list[dict[str, Any]]
    suppressed_rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _parse_datetime(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _bucket_start(value: Any, minutes: int) -> str | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    minute = (parsed.minute // minutes) * minutes
    bucket = parsed.replace(minute=minute, second=0, microsecond=0)
    return bucket.isoformat()


def coordinate_notification_rows(
    rows: list[dict[str, Any]],
    *,
    mode: str,
    observed_at: str,
    group_start_windows: bool = False,
    group_pick_changes: bool = False,
) -> CoordinationResult:
    if mode not in {"off", "shadow", "grouped"}:
        mode = "off"
    if mode == "off":
        return CoordinationResult(rows, [], [], {
            "mode": "off",
            "input_count": len(rows),
            "output_count": len(rows),
            "grouped_count": 0,
        })
    output = list(rows)
    return CoordinationResult(output, [], [], {
        "mode": mode,
        "input_count": len(rows),
        "output_count": len(output),
        "grouped_count": 0,
    })
```

- [ ] **Step 2: Implement start-window digest grouping**

Add these helpers to `market_infra/notification_coordinator.py`:

```python
def _is_start_window_row(row: Mapping[str, Any]) -> bool:
    return row.get("event_type") == "game_reminder_due"


def _start_window_group_key(row: Mapping[str, Any]) -> tuple[str, str] | None:
    payload = row.get("payload") or {}
    slate_date = str(row.get("slate_date") or payload.get("slate_date") or "")
    bucket = floor_datetime_to_bucket(payload.get("game_time") or row.get("game_time"), minutes=30)
    if not slate_date or not bucket:
        return None
    return (slate_date, bucket)
```

Update `coordinate_notification_rows` so `game_reminder_due` rows with the same
`(slate_date, start_window_bucket)` are replaced by a single
`start_window_digest` only when all of these are true:

- `mode == "grouped"`;
- `group_start_windows is True`;
- the group has at least two source rows;
- each source row has a non-empty `dedupe_key`.

Groups that fail those checks must pass through unchanged.

The digest payload must include:

- `source_event_count`
- `source_dedupe_keys`
- `pitchers`
- `fire_count`
- `lean_count`
- `start_window_bucket`

- [ ] **Step 3: Run tests**

Run:

```powershell
python -m pytest tests/test_notification_coordinator.py -q
```

Expected: pass for the first grouped reminder test.

## Task 3: Add Pick-Change Digest Tests And Implementation

**Files:**
- Modify: `tests/test_notification_coordinator.py`
- Modify: `market_infra/notification_coordinator.py`

- [ ] **Step 1: Add tests**

Append these concrete tests to `tests/test_notification_coordinator.py`:

```python
def test_groups_same_run_pick_upgrades():
    rows = [
        make_pick_change("pick_upgraded", "Sandy Alcantara", observed_at="2026-06-04T17:10:00Z"),
        make_pick_change("pick_upgraded", "Spencer Strider", observed_at="2026-06-04T17:10:00Z"),
    ]

    result = coordinate_notification_rows(
        rows,
        mode="grouped",
        observed_at="2026-06-04T17:10:00Z",
        group_pick_changes=True,
    )

    assert [row["event_type"] for row in result.rows] == ["pick_upgraded_digest"]
    assert result.rows[0]["payload"]["source_event_count"] == 2
    assert result.rows[0]["payload"]["pitchers"] == ["Sandy Alcantara", "Spencer Strider"]


def test_keeps_upgrade_and_downgrade_separate():
    rows = [
        make_pick_change("pick_upgraded", "Sandy Alcantara", observed_at="2026-06-04T17:10:00Z"),
        make_pick_change("pick_downgraded", "Spencer Strider", observed_at="2026-06-04T17:10:00Z"),
    ]

    result = coordinate_notification_rows(
        rows,
        mode="grouped",
        observed_at="2026-06-04T17:10:00Z",
        group_pick_changes=True,
    )

    assert [row["event_type"] for row in result.rows] == ["pick_upgraded", "pick_downgraded"]


def test_single_pick_change_passes_through():
    rows = [make_pick_change("pick_upgraded", "Sandy Alcantara", observed_at="2026-06-04T17:10:00Z")]

    result = coordinate_notification_rows(
        rows,
        mode="grouped",
        observed_at="2026-06-04T17:10:00Z",
        group_pick_changes=True,
    )

    assert result.rows == rows


def test_movement_rows_stay_individual():
    rows = [
        make_movement("line_moved_with_us", "Sandy Alcantara"),
        make_movement("line_moved_against_us", "Spencer Strider"),
    ]

    result = coordinate_notification_rows(
        rows,
        mode="grouped",
        observed_at="2026-06-04T17:10:00Z",
        group_pick_changes=True,
    )

    assert result.rows == rows
```

- [ ] **Step 2: Implement grouping**

Group pick changes by:

```text
slate_date:event_type:observed_10_minute_bucket
```

Use event types:

- `new_fire_pick_digest`
- `pick_upgraded_digest`
- `pick_downgraded_digest`

- [ ] **Step 3: Run tests**

Run:

```powershell
python -m pytest tests/test_notification_coordinator.py -q
```

Expected: pass.

## Task 4: Wire Coordinator Into Live Layer In Shadow Mode

**Files:**
- Modify: `scripts/build_live_events_to_supabase.py`
- Modify: `tests/test_live_layer_worker.py`

- [ ] **Step 1: Add worker tests**

Add these worker-level test cases to `tests/test_live_layer_worker.py`:

```python
def test_notification_coordinator_default_is_noop(monkeypatch):
    monkeypatch.delenv("LIVE_NOTIFICATION_COORDINATOR_MODE", raising=False)
    result = run_live_layer_with_fake_notification_rows(two_same_window_reminders())

    assert inserted_notification_rows(result) == two_same_window_reminders()
    assert result["notification_coordinator"]["mode"] == "off"


def test_notification_coordinator_shadow_records_summary_only(monkeypatch):
    monkeypatch.setenv("LIVE_NOTIFICATION_COORDINATOR_MODE", "shadow")
    monkeypatch.setenv("LIVE_NOTIFICATION_GROUP_START_WINDOWS", "true")
    result = run_live_layer_with_fake_notification_rows(two_same_window_reminders())

    assert inserted_notification_rows(result) == two_same_window_reminders()
    assert result["notification_coordinator"]["input_count"] == 2
    assert result["notification_coordinator"]["grouped_count"] == 1


def test_notification_coordinator_grouped_inserts_digest(monkeypatch):
    monkeypatch.setenv("LIVE_NOTIFICATION_COORDINATOR_MODE", "grouped")
    monkeypatch.setenv("LIVE_NOTIFICATION_GROUP_START_WINDOWS", "true")
    result = run_live_layer_with_fake_notification_rows(two_same_window_reminders())

    assert [row["event_type"] for row in inserted_notification_rows(result)] == ["start_window_digest"]
```

- [ ] **Step 2: Implement env parsing and coordinator call**

Call the coordinator after `notification_rows` is assembled and before
`writer.insert_ignore_rows("notification_events", ...)`.

Include `notification_coordinator` summary in:

- the returned `result` object;
- `shadow_pipeline_runs.metadata.notification_coordinator`.

- [ ] **Step 3: Run focused tests**

Run:

```powershell
python -m pytest tests/test_notification_coordinator.py tests/test_live_layer_worker.py -q
```

Expected: pass.

## Task 5: Add Movement Strength Labels In Shadow

**Files:**
- Modify: `market_infra/shadow_notification_candidates.py`
- Modify: `tests/test_market_infra_shadow_notification_candidates.py`

- [x] **Step 1: Add tests**

Add tests for these labels:

- `single_book`
- `broad_confirmation`
- `stale_or_heartbeat_missing`
- `volatile_or_reversed`
- `propline_polling_confirmed`
- `boltodds_confirmed`

- [x] **Step 2: Implement labels in metadata**

Add `movement_strength_labels` to each shadow candidate metadata object.

- [x] **Step 3: Run tests**

Run:

```powershell
python -m pytest tests/test_market_infra_shadow_notification_candidates.py -q
```

Expected: pass.

## Task 6: Update Daily Review And Handoff Docs

**Files:**
- Modify: `analytics/diagnostics/shadow_notification_candidate_audit.py`
- Modify: `docs/current-state.md`
- Modify: `docs/superpowers/plans/2026-05-20-live-notification-coordinator.md`
- Modify: `docs/superpowers/plans/2026-05-20-live-market-decision-ui.md`

- [ ] **Step 1: Add digest opportunity summary**

The audit report should summarize:

- actual queued/sent notification count;
- grouped start-window opportunities;
- grouped pick-change opportunities;
- movement candidates by strength label;
- duplicate/stale/post-start suppressions.

- [ ] **Step 2: Run audit tests**

Run:

```powershell
python -m pytest tests/test_shadow_notification_candidate_audit.py -q
```

Expected: pass.

- [ ] **Step 3: Update docs and commit**

Run:

```powershell
git status --short
git add market_infra/notification_coordinator.py scripts/build_live_events_to_supabase.py market_infra/shadow_notification_candidates.py analytics/diagnostics/shadow_notification_candidate_audit.py tests/test_notification_coordinator.py tests/test_live_layer_worker.py tests/test_market_infra_shadow_notification_candidates.py tests/test_shadow_notification_candidate_audit.py docs/current-state.md docs/superpowers/plans/2026-05-20-live-notification-coordinator.md docs/superpowers/plans/2026-05-20-live-market-decision-ui.md
git commit -m "Add live notification digest coordinator"
```

## Verification Before Enabling Sends

Before `LIVE_NOTIFICATION_COORDINATOR_MODE=grouped` is used in Render:

- Run the focused tests above.
- Run the live-layer smoke in shadow mode.
- Confirm Netlify sender queue health:
  - pending
  - sent
  - failed
  - stale-suppressed
- Review one slate where shadow digests would have reduced notification count.
- Keep `LIVE_NOTIFICATIONS_ENABLED` and GitHub legacy sender posture unchanged
  unless Tyler explicitly approves the class promotion.

## Rollback

Set:

```text
LIVE_NOTIFICATION_COORDINATOR_MODE=off
```

This restores current per-pitcher notification rows without touching model,
provider, lock, grading, artifact, or dashboard behavior.
