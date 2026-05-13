# BoltOdds Production Line-Movement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Promote BoltOdds from shadow evidence into the production live line-movement layer that powers timing, confidence, and eventually notifications, while keeping TheRundown as the official book-of-record pipeline.

**Architecture:** Keep GitHub Actions + TheRundown responsible for official picks, archives, grading, calibration, and `today.json`. Run one always-on BoltOdds WebSocket worker as the low-latency market telemetry source, writing Supabase live-market state, movement events, and shadow/then-live notification candidates. Promotion happens in gates: fix freshness, stabilize worker, prove movement quality, expose decision support, then enable tightly scoped alerts.

**Tech Stack:** Python 3.11, `websockets`, Render background worker, Supabase REST/Postgres tables, Netlify notification functions, existing `market_infra` helpers, pytest.

---

## Diagnosis From 2026-05-13

The May 13 stale-day symptom was real:

- Latest BoltOdds heartbeats were fresh around `2026-05-13 10:06 AM` Phoenix.
- The worker still wrote `slate_date=2026-05-12`.
- `market_snapshots` had zero BoltOdds rows after Phoenix midnight on May 13.
- GitHub raw `today.json` was later verified as `date=2026-05-13`, `generated_at=2026-05-13T15:50:57Z`, with 30 pitchers.

Root cause:

- `scripts/boltodds_ws_worker.py` resolves `slate_date`, production artifact, and `production_pitcher_names` once at process startup.
- The worker restarted at about `2026-05-13 07:03 AM` Phoenix, before GitHub's delayed full run updated `today.json` at about `08:50 AM` Phoenix.
- Because the worker is persistent, it kept the May 12 slate and May 12 pitcher filter after the May 13 artifact became available.
- Incoming May 13 BoltOdds messages could heartbeat, but the stale `allowed_player_names` filter suppressed snapshots for May 13 pitchers.

This is a production-readiness blocker. A persistent worker must rotate slates when the production artifact advances.

## Production Boundary

BoltOdds production means:

- production live movement telemetry
- production live market display state
- production confidence/referee evidence
- production notification input after gates pass

BoltOdds production does **not** initially mean:

- replacing TheRundown as book-of-record odds source
- changing `pipeline/run_pipeline.py`
- changing `today.json` or dated archive semantics
- changing grading, calibration, thresholds, staking, or projection math
- writing official pick lines from BoltOdds

## Provider Decision

Tyler's current direction is reasonable: for active line movement, BoltOdds is the cheapest useful stack candidate if Starter continues to cover enough MLB pitcher strikeout books. Public BoltOdds docs/pricing checked on 2026-05-13 show Starter at `$99/mo`, one league and one market per connection, all sportsbooks, one concurrent connection, and WebSocket support. That matches this app's narrow need: MLB pitcher strikeouts.

Do not jump to Growth or Pro unless a specific blocker appears. Starter is enough if the app only needs one league and one market.

## Gates

| Gate | Opens When | Allows | Blocks |
| --- | --- | --- | --- |
| Gate 0: Freshness Fix | Worker rotates when `today.json` advances and stops filtering today's messages through yesterday's pitchers | Continue shadow collection | Production alerts |
| Gate 1: Worker Stability | 3 active slates with current-slate heartbeats, snapshots, and coverage audits; no stale slate after artifact rollover | Production line-movement display backend | Notification sends |
| Gate 2: Coverage Sufficiency | At least 3 useful target books cover the full slate, including FanDuel plus two of BetMGM/BetRivers/Caesars/Kalshi; DraftKings remains optional unless Tyler requires it | Dashboard decision support | Provider migration |
| Gate 3: Decision Value | Movement/referee buckets improve timing, CLV, skip decisions, or confidence versus polling-only evidence | Shadow-to-live alert candidates | Automatic betting logic |
| Gate 4: Notification Quality | Would-have-sent alerts are deduped, timely, low-noise, and actionable across at least 5 slates | Limited production notifications | Broad alert classes |
| Gate 5: Cost/Retention | Raw snapshots are bounded or summarized; Supabase/Render costs stay acceptable | Keep BoltOdds after trial/month | Pro upgrade or unbounded storage |

## File Plan

Modify:

- `scripts/boltodds_ws_worker.py`
  - Add periodic production artifact refresh.
  - Rotate `slate_date`, production payload, production path, and pitcher allow-list when the artifact date advances.
  - Write explicit heartbeat metadata for artifact date, artifact generated time, artifact source, and rotation events.
  - Never rotate backwards.
  - Keep a stale-artifact warning when Phoenix date is ahead of artifact date during expected GitHub delay windows.
- `tests/test_boltodds_ws_worker.py`
  - Add failing tests for stale-day rollover and no backwards rotation.
- `analytics/diagnostics/boltodds_migration_risk_audit.py`
  - Add stale-slate and artifact-date checks to the post-trial risk read.
- `tests/test_boltodds_migration_risk_audit.py`
  - Pin the stale-slate health classification.
- `docs/boltodds-starter-trial.md`
  - Add the production-readiness gates and the May 13 root-cause note.
- `docs/current-state.md`
  - Reference this plan after Gate 0 lands.

Do not modify:

- `pipeline/run_pipeline.py`
- `pipeline/fetch_odds.py`
- `pipeline/build_features.py`
- `data/params.json`
- `data/picks_history.json`
- `dashboard/data/processed/today.json`

## Task 1: Fix Persistent Worker Slate Rollover

**Files:**
- Modify: `scripts/boltodds_ws_worker.py`
- Modify: `tests/test_boltodds_ws_worker.py`

- [ ] **Step 1: Add a failing unit test for artifact rollover**

Add this test to `tests/test_boltodds_ws_worker.py`:

```python
def test_refresh_production_context_rotates_to_new_artifact_date(monkeypatch):
    payloads = [
        ({"date": "2026-05-12", "pitchers": [{"pitcher": "Old Starter"}]}, "today.json"),
        ({"date": "2026-05-13", "pitchers": [{"pitcher": "New Starter"}]}, "today.json"),
    ]

    def fake_loader(*args, **kwargs):
        return payloads.pop(0)

    monkeypatch.setattr(boltodds_ws_worker, "_load_production_artifact", fake_loader)
    context = boltodds_ws_worker.load_production_context(
        slate_date_override=None,
        artifact_url="https://example.test/today.json",
    )

    refreshed = boltodds_ws_worker.refresh_production_context_if_advanced(
        context,
        slate_date_override=None,
        artifact_url="https://example.test/today.json",
    )

    assert refreshed.slate_date == "2026-05-13"
    assert refreshed.production_pitcher_names == {"new starter"}
    assert refreshed.rotated is True
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
python -m pytest tests/test_boltodds_ws_worker.py::test_refresh_production_context_rotates_to_new_artifact_date -q
```

Expected:

```text
AttributeError: module 'scripts.boltodds_ws_worker' has no attribute 'load_production_context'
```

- [ ] **Step 3: Add a small context object and loader**

In `scripts/boltodds_ws_worker.py`, add:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class ProductionContext:
    slate_date: str
    production_payload: dict | None
    production_path: str | None
    production_pitcher_names: set[str]
    rotated: bool = False
```

Then add:

```python
def load_production_context(
    *,
    slate_date_override: str | None,
    artifact_url: str | None,
) -> ProductionContext:
    production_payload, production_path = _load_production_artifact(
        slate_date_override,
        artifact_url=artifact_url or None,
    )
    slate_date = slate_date_override or str(
        (production_payload or {}).get("date") or ""
    ).strip()
    if not slate_date:
        raise EnvironmentError("SLATE_DATE is required when today.json has no date")
    return ProductionContext(
        slate_date=slate_date,
        production_payload=production_payload,
        production_path=production_path,
        production_pitcher_names=_production_pitcher_names(production_payload),
    )
```

- [ ] **Step 4: Add refresh logic that only rotates forward**

Add:

```python
def refresh_production_context_if_advanced(
    current: ProductionContext,
    *,
    slate_date_override: str | None,
    artifact_url: str | None,
) -> ProductionContext:
    if slate_date_override:
        return current
    refreshed = load_production_context(
        slate_date_override=None,
        artifact_url=artifact_url,
    )
    if refreshed.slate_date <= current.slate_date:
        return current
    return ProductionContext(
        slate_date=refreshed.slate_date,
        production_payload=refreshed.production_payload,
        production_path=refreshed.production_path,
        production_pitcher_names=refreshed.production_pitcher_names,
        rotated=True,
    )
```

- [ ] **Step 5: Use `ProductionContext` in `run_worker()`**

Replace the one-time `production_payload`, `production_path`, `slate_date`, and `production_pitcher_names` variables with a `context` variable:

```python
context = load_production_context(
    slate_date_override=slate_date_override,
    artifact_url=artifact_url or None,
)
```

Use `context.slate_date`, `context.production_payload`, `context.production_path`, and `context.production_pitcher_names` everywhere rows are built.

- [ ] **Step 6: Refresh context inside the WebSocket loop**

Add an env-controlled interval:

```python
artifact_refresh_seconds = _optional_float_env(
    "BOLTODDS_ARTIFACT_REFRESH_SECONDS",
    300.0,
)
last_artifact_refresh_monotonic = monotonic()
```

Inside the message loop, before parsing rows:

```python
if (
    artifact_refresh_seconds > 0
    and (now_monotonic - last_artifact_refresh_monotonic) >= artifact_refresh_seconds
):
    refreshed_context = refresh_production_context_if_advanced(
        context,
        slate_date_override=slate_date_override,
        artifact_url=artifact_url or None,
    )
    last_artifact_refresh_monotonic = now_monotonic
    if refreshed_context.rotated:
        context = refreshed_context
        write_heartbeat(
            writer,
            run_id=run_id,
            slate_date=context.slate_date,
            event="slate_rotated",
            books_seen=books_seen,
            last_message_at=last_message_at,
            metadata={
                "production_artifact_path": context.production_path,
                "pitcher_count": len(context.production_pitcher_names),
            },
        )
```

Make `context` nonlocal in `flush()` so batches after rotation use the current slate and production payload.

- [ ] **Step 7: Run the focused worker tests**

Run:

```bash
python -m pytest tests/test_boltodds_ws_worker.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Deploy once and verify live rows**

After merging/pushing the BoltOdds worker branch and manually deploying Render:

```sql
select slate_date, observed_at, metadata
from market_feed_heartbeats
where provider='boltodds'
order by observed_at desc
limit 10;
```

Expected:

- latest `slate_date` matches current `today.json.date`
- a `slate_rotated` heartbeat appears when the artifact advances
- `market_snapshots` writes current-slate rows after artifact rotation

## Task 2: Add Stale-Slate Risk Detection

**Files:**
- Modify: `analytics/diagnostics/boltodds_migration_risk_audit.py`
- Modify: `tests/test_boltodds_migration_risk_audit.py`

- [ ] **Step 1: Add a failing stale-slate test**

Add a test that passes:

```python
summary = build_migration_risk_summary(
    current_slate_date="2026-05-13",
    provider_run_rows=[{"slate_date": "2026-05-12", "status": "started"}],
    heartbeat_rows=[{"slate_date": "2026-05-12"}],
    coverage_audit_rows=[],
    snapshot_rows=[],
)
```

Assert:

```python
assert summary["freshness"]["stale_slate_detected"] is True
assert "latest heartbeat slate date is behind current slate" in summary["risk_flags"]
```

- [ ] **Step 2: Implement stale-slate fields**

Add these summary fields:

- `current_slate_date`
- `latest_provider_run_slate_date`
- `latest_heartbeat_slate_date`
- `latest_coverage_audit_slate_date`
- `stale_slate_detected`

Flag stale if any latest live layer date is older than current production `today.json.date`.

- [ ] **Step 3: Run diagnostic tests**

Run:

```bash
python -m pytest tests/test_boltodds_migration_risk_audit.py -q
```

Expected: all tests pass.

## Task 3: Promote Live Display State, Not Official Odds

**Files:**
- Modify: `scripts/boltodds_ws_worker.py`
- Modify: `scripts/build_live_events_to_supabase.py`
- Modify: `market_infra/live_market_display.py`
- Modify: `tests/test_market_infra_live_market_display.py`

- [ ] **Step 1: Confirm current display-state inputs**

Run:

```bash
python -m pytest tests/test_market_infra_live_market_display.py -q
```

Expected: tests pass before changes.

- [ ] **Step 2: Add BoltOdds-first display source preference**

In `market_infra/live_market_display.py`, keep TheRundown pick state as the model source, but prefer BoltOdds snapshots for:

- current consensus
- best actionable book
- off-market book
- book freshness
- broad confirmation
- reversal/volatility flags

PropLine remains fallback display evidence when BoltOdds is stale or absent.

- [ ] **Step 3: Add stale-provider suppression**

If the latest BoltOdds snapshot for a pitcher/side is older than a configured freshness window, mark it as stale and fall back to PropLine or display `market_status=stale`.

- [ ] **Step 4: Verify display tests**

Run:

```bash
python -m pytest tests/test_market_infra_live_market_display.py tests/test_live_layer_worker.py -q
```

Expected: all tests pass.

## Task 4: Shadow Notification Promotion

**Files:**
- Modify: `market_infra/shadow_notification_candidates.py`
- Modify: `tests/test_market_infra_shadow_notification_candidates.py`
- Modify: `analytics/diagnostics/live_market_outcome_audit.py`
- Modify: `tests/test_live_market_outcome_audit.py`

- [ ] **Step 1: Keep alerts shadow-only while broadening candidate classes**

Add candidate classes:

- `late_bet_confirmed`
- `wait_better_number_available`
- `skip_market_faded_model`
- `skip_stale_or_volatile`
- `fire_moved_against_pick`
- `fire_moved_with_pick`

- [ ] **Step 2: Require strict suppression reasons**

Every candidate row must include:

- `provider_fresh`
- `broad_confirmation`
- `single_book_noise`
- `reversal_or_volatility`
- `minutes_to_game`
- `data_complete_enough`
- `suppression_reason`

- [ ] **Step 3: Run shadow candidate tests**

Run:

```bash
python -m pytest tests/test_market_infra_shadow_notification_candidates.py tests/test_live_market_outcome_audit.py -q
```

Expected: all tests pass.

## Task 5: Enable Limited Production Notifications

**Files:**
- Modify: `market_infra/live_events.py`
- Modify: `netlify/functions/send-live-notifications.mjs`
- Modify: `tests/test_market_infra_live_events.py`

Only start this task after Gate 4 passes.

- [ ] **Step 1: Add production allowlist env**

Use an environment variable such as:

```text
LIVE_BOLTODDS_ALERT_CLASSES=late_bet_confirmed,skip_market_faded_model
```

If the env var is empty, BoltOdds candidates stay shadow-only.

- [ ] **Step 2: Promote only allowlisted candidate rows**

Convert selected shadow candidates into `notification_events` only when:

- class is allowlisted
- provider is fresh
- event is pregame
- dedupe key has not been sent
- suppression reason is empty
- current production pick still exists in `today.json`

- [ ] **Step 3: Verify no accidental broad send**

Run:

```bash
python -m pytest tests/test_market_infra_live_events.py -q
```

Expected: tests prove no notification rows are created when the allowlist is empty.

## Task 6: Retention And Cost Controls

**Files:**
- Create: `scripts/compact_boltodds_market_snapshots.py`
- Create: `tests/test_compact_boltodds_market_snapshots.py`
- Modify: `docs/provider-cost-ledger.md`
- Modify: `docs/operational-risk-register.md`

- [ ] **Step 1: Add compact daily summary script**

Summarize raw `market_snapshots` into compact rows by:

- slate date
- provider
- pitcher
- side
- book
- pregame checkpoint
- opening/latest/best/worst line and odds
- movement direction

- [ ] **Step 2: Add dry-run output**

The script must default to dry-run mode and print counts before writing anything.

- [ ] **Step 3: Add retention recommendation**

After compact summaries are proven, keep raw BoltOdds `market_snapshots` for 14-30 days and keep compact summaries for the season.

## Production Rollout Recommendation

Use this sequence:

1. Fix Gate 0 immediately on the BoltOdds trial branch.
2. Manually deploy once.
3. Watch 2-3 active slates for current-slate heartbeats, snapshots, coverage, and stale-feed behavior.
4. Promote BoltOdds to production display evidence, not official odds.
5. Let shadow notification candidates run for at least 5 slates.
6. Enable one or two alert classes with an env allowlist.
7. Revisit whether PropLine can be reduced after BoltOdds proves active movement value.

The long-term target stack should be:

- TheRundown: official scheduled book-of-record artifacts.
- BoltOdds Starter: active line movement, best-book/current-market state, timing and notification evidence.
- PropLine: keep only if it provides fallback coverage or a cheaper useful role after BoltOdds is stable.
- The Odds API: emergency FD/DK fallback only.

Do not buy BoltOdds Growth/Pro unless one market/one league stops being enough.
