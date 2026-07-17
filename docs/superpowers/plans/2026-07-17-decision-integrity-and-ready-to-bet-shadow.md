# Decision Integrity And Ready-To-Bet Shadow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep alternate K lines visible but non-actionable by default, and record shadow-only `ready_to_bet` transitions without changing current notification sends.

**Architecture:** The dashboard adapter establishes a same-model-line trust boundary before selecting compact market rows or prefilling Log Bet. A new pure Python decision-state module derives `watching|ready|logged|locked|started` from artifact, live-market, accepted-bet, and prior-state inputs; the Render live layer records state metadata and transition candidates only when an explicit shadow flag is enabled.

**Tech Stack:** Vanilla JavaScript, React 18 UMD, Node built-in test runner, Babel JSX compilation, Python 3.11, pytest, Supabase Postgres migrations, Render `bbe-live-layer`, Netlify static dashboard.

## Global Constraints

- Alternate lines remain visible in the detail book board and manual ticket selector.
- A different-line row must never become the automatic Log Bet default.
- `LIVE_READY_TO_BET_SHADOW=off|record`; code default is `off`.
- `record` must not insert `notification_events` or suppress existing notification rows.
- Ready qualification requires displayed FIRE, `quality_gate_level=clean`, pre-start, unlocked, no accepted bet, and a fresh same-line supported-book price.
- State precedence is `started > locked > logged > ready > watching`.
- Reuse `live_pick_state.metadata`, `shadow_pipeline_runs.metadata`, and `shadow_notification_candidates`; add no new table.
- Exclude BoltOdds from ready qualification.
- Do not change model math, thresholds, staking, calibration, provider order, polling cadence, source of truth, lock behavior, retention, or current notification classes.

---

## File Map

- Modify `dashboard/v2-data.js`: retain `model_line`, label alternate-line rows, and prefer fresh same-line rows.
- Modify `dashboard/v2-data.test.mjs`: behavioral coverage for normalization and preferred-row selection.
- Modify `dashboard/v2-app.jsx`: alternate-line copy/tone and same-line-only automatic ticket prefill.
- Regenerate `dashboard/v2-app.js`: committed Babel output.
- Modify `dashboard/v2.html`: cache-bust the updated adapter and app bundle.
- Modify `tests/test_dashboard_accepted_bet_log.py`: static contract coverage for UI copy, prefill gate, selector preservation, and cache keys.
- Create `market_infra/ready_to_bet_shadow.py`: pure decision-state and transition-candidate builder.
- Create `tests/test_ready_to_bet_shadow.py`: exhaustive state and qualification tests.
- Create `supabase/migrations/20260717181500_ready_to_bet_shadow_candidate.sql`: additive candidate/provider constraint update.
- Modify `tests/test_live_layer_schema.py`: migration contract test.
- Modify `scripts/build_live_events_to_supabase.py`: feature mode, fail-closed accepted-bet read, state annotation, safe shadow-candidate write, and run metadata.
- Modify `tests/test_live_layer_worker.py`: worker integration and unchanged-notification tests.
- Modify `analytics/diagnostics/shadow_notification_candidate_audit.py`: dedicated readiness summary.
- Modify `tests/test_shadow_notification_candidate_audit.py`: readiness report tests.
- Modify `docs/current-state.md`, `docs/superpowers/plans/2026-05-20-live-market-decision-ui.md`, and `docs/superpowers/plans/2026-06-04-live-notification-digest-coordinator.md`: implementation/deployment posture.

---

### Task 1: Enforce Same-Line Preference In The Dashboard Adapter

**Files:**
- Modify: `dashboard/v2-data.test.mjs`
- Modify: `dashboard/v2-data.js`

**Interfaces:**
- Consumes: sanitized `live_market_display_state` rows with `k_line`, `main_line`, `best_line`, freshness, provider, and observation time.
- Produces: normalized rows with `model_line`; `preferredMarketRow(candidate, current)` ranks fresh same-line rows before different-line rows.

- [ ] **Step 1: Write the failing adapter tests**

Change the existing off-market expectation and add the preferred-row regression in `dashboard/v2-data.test.mjs`:

```javascript
test("off-market live rows are labeled as alternate-line context", async () => {
  const todayJson = {
    date: "2026-04-28",
    pitchers: [{
      pitcher: "Off Market Pitcher",
      k_line: 7.5,
      best_over_odds: 944,
      ev_over: { verdict: "LEAN", adj_ev: 0.01 },
      ev_under: { verdict: "PASS", adj_ev: -0.01 },
    }],
  };
  const window = await runV2DataTest({
    todayJson,
    liveMarketDisplay: {
      rows: [{
        slate_date: "2026-04-28",
        normalized_pitcher: "off market pitcher",
        pitcher: "Off Market Pitcher",
        side: "over",
        provider: "propline",
        observed_at: "2026-04-28T22:55:00Z",
        freshness_status: "fresh",
        actionable_state: "off_market",
        k_line: 7.5,
        main_line: 2.5,
        best_book: "thescore",
        best_line: 2.5,
        best_odds: -450,
      }],
    },
  });

  const row = window.V2_DATA.pitchers[0].market_display.OVER;
  assert.equal(row.model_line, 7.5);
  assert.equal(row.action_label, "alt_line_context");
});

test("fresh same-model-line row outranks a newer alternate-line row", async () => {
  const todayJson = {
    date: "2026-04-28",
    pitchers: [{
      pitcher: "Trust Boundary Pitcher",
      k_line: 7.5,
      best_over_odds: 105,
      ev_over: { verdict: "FIRE 1u", adj_ev: 0.08 },
      ev_under: { verdict: "PASS", adj_ev: -0.04 },
    }],
  };
  const window = await runV2DataTest({
    todayJson,
    liveMarketDisplay: {
      rows: [
        {
          slate_date: "2026-04-28",
          normalized_pitcher: "trust boundary pitcher",
          side: "over",
          provider: "therundown_propline",
          observed_at: "2026-04-28T22:50:00Z",
          freshness_status: "fresh",
          actionable_state: "playable_now",
          k_line: 7.5,
          best_book: "fanduel",
          best_line: 7.5,
          best_odds: 105,
        },
        {
          slate_date: "2026-04-28",
          normalized_pitcher: "trust boundary pitcher",
          side: "over",
          provider: "propline",
          observed_at: "2026-04-28T22:55:00Z",
          freshness_status: "fresh",
          actionable_state: "off_market",
          k_line: 7.5,
          best_book: "thescore",
          best_line: 2.5,
          best_odds: -450,
        },
      ],
    },
  });

  const row = window.V2_DATA.pitchers[0].market_display.OVER;
  assert.equal(row.provider, "therundown_propline");
  assert.equal(row.best_line, 7.5);
});
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
node --test dashboard/v2-data.test.mjs
```

Expected: the first new test receives `shop_price`/missing `model_line`, and the second selects the newer 2.5K row.

- [ ] **Step 3: Implement normalized model-line and same-line rank**

Update `marketActionLabel`, `normalizeMarketDisplayRow`, and `marketRowScore` in `dashboard/v2-data.js`:

```javascript
function marketActionLabel(row) {
  const freshness = String(row.freshness_status || '').toLowerCase();
  const actionable = String(row.actionable_state || '').toLowerCase();
  const status = String(row.market_status || '').toLowerCase();
  const consensus = String(row.market_consensus || '').toLowerCase();
  if (freshness && !['fresh', 'held_fresh', 'heartbeat_held'].includes(freshness)) return 'stale';
  if (actionable.includes('off_market')) return 'alt_line_context';
  if (actionable.includes('shop')) return 'shop_price';
  if (actionable.includes('play') || actionable.includes('bet')) return 'playable';
  if (status.includes('playable') || status.includes('confirmed')) return 'playable';
  if (consensus.includes('away') || consensus.includes('against')) return 'market_disagrees';
  if (consensus.includes('toward') || consensus.includes('with')) return 'market_agrees';
  return 'monitor';
}
```

Add to the normalized object:

```javascript
model_line: numericOrNull(row.k_line ?? row.model_line ?? row.pick_line),
main_line: numericOrNull(row.main_line ?? row.k_line ?? row.line),
```

Add the helper and place its result after freshness but before observation time:

```javascript
function marketSameModelLineRank(row) {
  const bestLine = numericOrNull(row?.best_line);
  const modelLine = numericOrNull(row?.model_line);
  if (bestLine == null || modelLine == null) return 0;
  return Math.abs(bestLine - modelLine) < 0.001 ? 1 : 0;
}

function marketRowScore(row) {
  return [
    marketFreshnessRank(row),
    marketSameModelLineRank(row),
    marketObservedAtMs(row),
    marketActionRank(row),
    row?.broad_confirmation === true ? 1 : 0,
    numericOrNull(row?.book_count) || 0,
    marketProviderRank(row),
  ];
}
```

- [ ] **Step 4: Run the adapter tests and verify GREEN**

Run:

```powershell
node --test dashboard/v2-data.test.mjs
```

Expected: all adapter tests pass.

- [ ] **Step 5: Commit the adapter boundary**

```powershell
git add dashboard/v2-data.js dashboard/v2-data.test.mjs
git commit -m "fix: prefer same-line live market rows"
```

---

### Task 2: Guard Compact Copy And Automatic Bet-Ticket Prefill

**Files:**
- Modify: `tests/test_dashboard_accepted_bet_log.py`
- Modify: `dashboard/v2-app.jsx`
- Regenerate: `dashboard/v2-app.js`
- Modify: `dashboard/v2.html`

**Interfaces:**
- Consumes: normalized dashboard row plus selected model side.
- Produces: `alt_line_context` copy/tone and a live prefill only when `sameMarketLine(...)` is true; manual different-line selection remains available.

- [ ] **Step 1: Write failing dashboard contract tests**

Add to `tests/test_dashboard_accepted_bet_log.py`:

```python
def test_dashboard_treats_different_line_as_context_not_default():
    app = DASHBOARD_APP.read_text(encoding="utf-8")

    assert 'alt_line_context: "Alt-line context"' in app
    assert 'label === "alt_line_context"' in app
    assert "if (!sameMarketLine(row, side, p)) return false;" in app
    assert '["playable", "playable_price", "shop_price", "market_agrees"]' in app


def test_dashboard_keeps_manual_different_line_selection():
    app = DASHBOARD_APP.read_text(encoding="utf-8")

    assert 'badges.push(bookRow.sameLine ? "Same line" : "Different line")' in app
    assert "function selectBetTicketBookRow(bookRow)" in app
    assert 'priceSource: "live_best"' in app


def test_dashboard_cache_busts_same_line_trust_assets():
    html = DASHBOARD_HTML.read_text(encoding="utf-8")

    assert "v2-data.js?v=2026-07-17-same-line-trust" in html
    assert "v2-app.js?v=2026-07-17-same-line-trust" in html
```

Update the older cache-bust test to expect these same two asset keys.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
python -m pytest tests/test_dashboard_accepted_bet_log.py -q
```

Expected: failures for missing `Alt-line context`, missing same-line prefill guard, and old asset versions.

- [ ] **Step 3: Implement alternate-line copy, tone, and prefill guard**

Update the helpers in `dashboard/v2-app.jsx`:

```javascript
function marketEffectiveActionLabel(row, side, p = null) {
  if (!row) return null;
  const modelLine = marketModelLine(row, side, p);
  if (isFiniteNumber(row?.best_line) && isFiniteNumber(modelLine) && !sameMarketLine(row, side, p)) {
    return "alt_line_context";
  }
  const label = row.action_label || "monitor";
  const actionable = String(row.actionable_state || "").toLowerCase();
  if (label === "monitor" && actionable.includes("off_market")) return "alt_line_context";
  const cushion = marketPriceCushionForSide(row, side);
  if (label === "monitor" && isFreshMarketRow(row) && sameMarketLine(row, side, p) && isFiniteNumber(cushion) && cushion >= 0) {
    return "playable_price";
  }
  return label;
}

function isLiveMarketBetPrefill(row, side = null, p = null) {
  if (!row || row.freshness_status === "stale") return false;
  if (!isFiniteNumber(row.best_line) || !isFiniteNumber(row.best_odds) || !row.best_book) return false;
  if (!sameMarketLine(row, side, p)) return false;
  const label = marketEffectiveActionLabel(row, side, p);
  return ["playable", "playable_price", "shop_price", "market_agrees"].includes(label) ||
    row.actionable_state === "playable_now";
}
```

Update tone and copy:

```javascript
function marketActionTone(row, side = null, p = null) {
  if (!row) return "neutral";
  const label = marketEffectiveActionLabel(row, side, p);
  if (["stale", "monitor", "alt_line_context"].includes(label)) return "warn";
  if (label === "market_disagrees") return "neg";
  return "pos";
}
```

Add to `marketActionText`:

```javascript
alt_line_context: "Alt-line context",
```

Leave `selectBetTicketBookRow(bookRow)` unchanged so explicit manual alternate-line selection still fills the editable ticket.

- [ ] **Step 4: Update cache keys and rebuild the JSX bundle**

Set both asset query strings in `dashboard/v2.html` to `2026-07-17-same-line-trust`, then run:

```powershell
Push-Location dashboard
npx --yes -p @babel/core@7 -p @babel/cli@7 -p @babel/preset-react@7 babel v2-app.jsx --presets=@babel/preset-react -o v2-app.js
Pop-Location
node --check dashboard/v2-app.js
```

Expected: Babel exits zero and `node --check` prints no error.

- [ ] **Step 5: Verify the dashboard tests**

Run:

```powershell
python -m pytest tests/test_dashboard_accepted_bet_log.py -q
node --test dashboard/v2-data.test.mjs dashboard/v2-movement-helpers.test.mjs
```

Expected: all focused tests pass.

- [ ] **Step 6: Commit the UI guard**

```powershell
git add dashboard/v2-app.jsx dashboard/v2-app.js dashboard/v2.html tests/test_dashboard_accepted_bet_log.py
git commit -m "fix: keep alternate lines out of bet defaults"
```

---

### Task 3: Build The Pure Ready-To-Bet Shadow Engine

**Files:**
- Create: `tests/test_ready_to_bet_shadow.py`
- Create: `market_infra/ready_to_bet_shadow.py`

**Interfaces:**
- Produces: `ReadyToBetResult(state_rows, candidate_rows, summary)`.
- Main function:

```python
build_ready_to_bet_shadow(
    *,
    slate_date: str,
    pitchers: list[dict[str, Any]],
    state_rows: list[dict[str, Any]],
    previous_state_rows: list[dict[str, Any]],
    live_market_rows: list[dict[str, Any]],
    accepted_bets: list[dict[str, Any]],
    accepted_bets_available: bool,
    notification_rows: list[dict[str, Any]],
    observed_at: datetime | str,
    mode: str,
) -> ReadyToBetResult
```

- [ ] **Step 1: Write the failing state-engine tests**

Create `tests/test_ready_to_bet_shadow.py` with fixtures and these concrete assertions:

```python
from datetime import datetime, timezone

import pytest

from market_infra.ready_to_bet_shadow import build_ready_to_bet_shadow


NOW = datetime(2026, 7, 17, 18, 0, tzinfo=timezone.utc)


def _pitcher(**overrides):
    row = {
        "pitcher": "Tarik Skubal",
        "k_line": 6.5,
        "game_time": "2026-07-17T23:10:00Z",
        "game_state": "scheduled",
        "quality_gate_level": "clean",
        "ev_over": {"verdict": "FIRE 1u", "quality_gate_level": "clean"},
    }
    row.update(overrides)
    return row


def _state(**overrides):
    row = {
        "slate_date": "2026-07-17",
        "pitcher": "Tarik Skubal",
        "normalized_pitcher": "tarik skubal",
        "side": "over",
        "current_verdict": "FIRE 1u",
        "k_line": 6.5,
        "game_time": "2026-07-17T23:10:00Z",
        "game_state": "scheduled",
        "is_locked": False,
        "metadata": {},
    }
    row.update(overrides)
    return row


def _market(**overrides):
    row = {
        "slate_date": "2026-07-17",
        "pitcher": "Tarik Skubal",
        "normalized_pitcher": "tarik skubal",
        "side": "over",
        "provider": "therundown_propline",
        "k_line": 6.5,
        "best_book": "fanduel",
        "best_line": 6.5,
        "best_odds": 105,
        "freshness_status": "fresh",
        "market_consensus": "toward_pick",
        "bet_value_consensus": "better_now",
        "book_count": 3,
        "books_seen": ["fanduel", "draftkings", "betrivers"],
        "broad_confirmation": True,
        "dedupe_key": "market-row",
    }
    row.update(overrides)
    return row


def _build(**overrides):
    args = {
        "slate_date": "2026-07-17",
        "pitchers": [_pitcher()],
        "state_rows": [_state()],
        "previous_state_rows": [],
        "live_market_rows": [_market()],
        "accepted_bets": [],
        "accepted_bets_available": True,
        "notification_rows": [],
        "observed_at": NOW,
        "mode": "record",
    }
    args.update(overrides)
    return build_ready_to_bet_shadow(**args)


def test_clean_unlocked_fire_with_fresh_same_line_becomes_ready():
    result = _build()

    assert result.state_rows[0]["metadata"]["decision_state"] == "ready"
    assert result.summary["state_counts"] == {"ready": 1}
    assert len(result.candidate_rows) == 1
    assert result.candidate_rows[0]["candidate_type"] == "ready_to_bet"
    assert result.candidate_rows[0]["dedupe_key"] == "2026-07-17:ready_to_bet:tarik skubal:over"


@pytest.mark.parametrize(
    ("changes", "expected_state", "expected_reason"),
    [
        ({"state_rows": [_state(current_verdict="LEAN")]}, "watching", "not_fire"),
        ({"pitchers": [_pitcher(quality_gate_level="capped", ev_over={"verdict": "FIRE 1u", "quality_gate_level": "capped"})]}, "watching", "quality_not_clean"),
        ({"live_market_rows": [_market(freshness_status="stale")]}, "watching", "same_line_market_unavailable"),
        ({"live_market_rows": [_market(best_line=2.5)]}, "watching", "same_line_market_unavailable"),
        ({"accepted_bets": [{"slate_date": "2026-07-17", "normalized_pitcher": "tarik skubal", "side": "over"}]}, "logged", "accepted_bet_logged"),
        ({"state_rows": [_state(is_locked=True)]}, "locked", "pick_locked"),
        ({"state_rows": [_state(game_state="in_progress")]}, "started", "game_started"),
        ({"accepted_bets_available": False}, "watching", "accepted_bet_state_unavailable"),
    ],
)
def test_non_ready_states_fail_closed(changes, expected_state, expected_reason):
    result = _build(**changes)

    metadata = result.state_rows[0]["metadata"]
    assert metadata["decision_state"] == expected_state
    assert expected_reason in metadata["decision_reasons"]
    assert result.candidate_rows == []


def test_only_transition_into_ready_creates_candidate():
    previous = [_state(metadata={"decision_state": "ready"})]

    result = _build(previous_state_rows=previous)

    assert result.state_rows[0]["metadata"]["decision_state"] == "ready"
    assert result.candidate_rows == []


def test_boltodds_cannot_qualify():
    result = _build(live_market_rows=[_market(provider="boltodds")])

    assert result.state_rows[0]["metadata"]["decision_state"] == "watching"
    assert result.candidate_rows == []


def test_off_mode_is_noop():
    source = [_state()]

    result = _build(state_rows=source, mode="off")

    assert result.state_rows == source
    assert result.candidate_rows == []
    assert result.summary["mode"] == "off"
```

- [ ] **Step 2: Run the unit tests and verify RED**

Run:

```powershell
python -m pytest tests/test_ready_to_bet_shadow.py -q
```

Expected: collection fails because `market_infra.ready_to_bet_shadow` does not exist.

- [ ] **Step 3: Implement the pure state engine**

Create `market_infra/ready_to_bet_shadow.py` with:

```python
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pipeline.name_utils import normalize


ACTIVE_PROVIDERS = {"therundown_propline", "therundown", "propline"}
PROVIDER_RANK = {"therundown_propline": 3, "therundown": 2, "propline": 1}
FRESH_STATUSES = {"fresh", "held_fresh", "heartbeat_held"}
STARTED_STATES = {"in_progress", "final", "completed"}
LOCKED_STATES = {"locked", "postponed"}


@dataclass(frozen=True)
class ReadyToBetResult:
    state_rows: list[dict[str, Any]]
    candidate_rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _row_key(row: dict[str, Any]) -> tuple[str, str] | None:
    normalized_pitcher = str(row.get("normalized_pitcher") or normalize(str(row.get("pitcher") or ""))).strip()
    side = str(row.get("side") or "").strip().lower()
    if not normalized_pitcher or side not in {"over", "under"}:
        return None
    return normalized_pitcher, side


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("metadata")
    return value if isinstance(value, dict) else {}


def _quality_level(pitcher: dict[str, Any], side: str) -> str:
    side_data = pitcher.get(f"ev_{side}")
    if not isinstance(side_data, dict):
        side_data = {}
    return str(side_data.get("quality_gate_level") or pitcher.get("quality_gate_level") or "missing").strip().lower()


def _same_line_market(row: dict[str, Any], target_line: float) -> bool:
    provider = str(row.get("provider") or "").strip().lower()
    freshness = str(row.get("freshness_status") or "").strip().lower()
    best_line = _numeric(row.get("best_line"))
    return (
        provider in ACTIVE_PROVIDERS
        and freshness in FRESH_STATUSES
        and best_line is not None
        and abs(best_line - target_line) < 0.001
        and bool(str(row.get("best_book") or "").strip())
        and _numeric(row.get("best_odds")) is not None
    )


def _preferred_market(rows: list[dict[str, Any]], target_line: float) -> dict[str, Any] | None:
    candidates = [row for row in rows if _same_line_market(row, target_line)]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda row: (
            PROVIDER_RANK.get(str(row.get("provider") or "").lower(), 0),
            str(row.get("observed_at") or ""),
        ),
    )


def _minutes_and_window(game_time: Any, observed_at: datetime) -> tuple[int | None, str]:
    parsed = _parse_datetime(game_time)
    if parsed is None:
        return None, "unknown"
    minutes = int(round((parsed - observed_at).total_seconds() / 60.0))
    if minutes <= 0:
        return minutes, "post_start"
    if minutes <= 5:
        return minutes, "pre_5"
    if minutes <= 15:
        return minutes, "pre_15"
    if minutes <= 30:
        return minutes, "pre_30"
    if minutes <= 60:
        return minutes, "pre_60"
    if minutes <= 120:
        return minutes, "pre_120"
    return minutes, "early"


def _notification_types(notification_rows: list[dict[str, Any]], key: tuple[str, str]) -> list[str]:
    values = set()
    for row in notification_rows:
        payload = row.get("payload") if isinstance(row.get("payload"), dict) else {}
        row_key = _row_key({**row, **payload})
        if row_key == key:
            values.add(str(row.get("event_type") or ""))
    return sorted(value for value in values if value)


def build_ready_to_bet_shadow(
    *,
    slate_date: str,
    pitchers: list[dict[str, Any]],
    state_rows: list[dict[str, Any]],
    previous_state_rows: list[dict[str, Any]],
    live_market_rows: list[dict[str, Any]],
    accepted_bets: list[dict[str, Any]],
    accepted_bets_available: bool,
    notification_rows: list[dict[str, Any]],
    observed_at: datetime | str,
    mode: str,
) -> ReadyToBetResult:
    normalized_mode = str(mode or "off").strip().lower()
    if normalized_mode != "record":
        return ReadyToBetResult(state_rows, [], {"mode": "off", "state_counts": {}, "candidate_count": 0})

    observed = _parse_datetime(observed_at)
    if observed is None:
        raise ValueError("observed_at must be parseable")

    pitchers_by_name = {
        normalize(str(row.get("pitcher") or "")): row
        for row in pitchers
        if str(row.get("pitcher") or "").strip()
    }
    previous_by_key = {key: row for row in previous_state_rows if (key := _row_key(row))}
    market_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in live_market_rows:
        key = _row_key(row)
        if key:
            market_by_key.setdefault(key, []).append(row)
    accepted_keys = {
        key for row in accepted_bets if (key := _row_key(row))
    }

    state_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    output_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []

    for source in state_rows:
        row = dict(source)
        key = _row_key(row)
        if key is None:
            output_rows.append(row)
            continue
        normalized_pitcher, side = key
        pitcher = pitchers_by_name.get(normalized_pitcher, {})
        game_state = str(row.get("game_state") or pitcher.get("game_state") or "").strip().lower()
        target_line = _numeric(row.get("k_line"))
        market = None if target_line is None else _preferred_market(market_by_key.get(key, []), target_line)
        quality_level = _quality_level(pitcher, side)
        reasons: list[str] = []

        if game_state in STARTED_STATES:
            decision_state = "started"
            reasons.append("game_started")
        elif bool(row.get("is_locked")) or game_state in LOCKED_STATES:
            decision_state = "locked"
            reasons.append("pick_locked")
        elif accepted_bets_available and key in accepted_keys:
            decision_state = "logged"
            reasons.append("accepted_bet_logged")
        else:
            if not accepted_bets_available:
                reasons.append("accepted_bet_state_unavailable")
            if not str(row.get("current_verdict") or "").startswith("FIRE"):
                reasons.append("not_fire")
            if quality_level != "clean":
                reasons.append("quality_not_clean")
            if market is None:
                reasons.append("same_line_market_unavailable")
            decision_state = "ready" if not reasons else "watching"

        state_counts[decision_state] += 1
        reason_counts.update(reasons)
        metadata = dict(_metadata(row))
        metadata.update({
            "decision_state": decision_state,
            "decision_reasons": reasons,
            "decision_state_observed_at": observed.isoformat(),
            "ready_to_bet_shadow_mode": normalized_mode,
        })
        row["metadata"] = metadata
        output_rows.append(row)

        previous_state = str(_metadata(previous_by_key.get(key, {})).get("decision_state") or "")
        if decision_state != "ready" or previous_state == "ready" or market is None:
            continue

        minutes_to_game, time_window = _minutes_and_window(row.get("game_time") or pitcher.get("game_time"), observed)
        books_seen = sorted(str(book).strip().lower() for book in market.get("books_seen") or [] if str(book).strip())
        candidate_rows.append({
            "slate_date": slate_date,
            "pitcher": row.get("pitcher"),
            "normalized_pitcher": normalized_pitcher,
            "side": side,
            "provider": market.get("provider"),
            "current_verdict": row.get("current_verdict"),
            "k_line": target_line,
            "candidate_type": "ready_to_bet",
            "candidate_action": "would_send_shadow",
            "playable_state": "playable_now",
            "market_consensus": market.get("market_consensus") if market.get("market_consensus") in {"toward_pick", "away_from_pick", "mixed", "none"} else "none",
            "bet_value_consensus": market.get("bet_value_consensus") if market.get("bet_value_consensus") in {"better_now", "worse_now", "mixed", "none"} else "none",
            "time_window": time_window,
            "minutes_to_game": minutes_to_game,
            "book_count": int(market.get("book_count") or len(books_seen)),
            "books_seen": books_seen,
            "broad_confirmation": market.get("broad_confirmation") is True,
            "single_book": len(books_seen) == 1,
            "betrivers_only": books_seen == ["betrivers"],
            "reversal_book_count": 0,
            "volatile_book_count": 0,
            "suppression_reasons": [],
            "evidence_dedupe_key": market.get("dedupe_key"),
            "occurred_at": observed.isoformat(),
            "dedupe_key": f"{slate_date}:ready_to_bet:{normalized_pitcher}:{side}",
            "metadata": {
                "decision_state": "ready",
                "previous_decision_state": previous_state or None,
                "quality_gate_level": quality_level,
                "best_book": market.get("best_book"),
                "best_line": market.get("best_line"),
                "best_odds": market.get("best_odds"),
                "freshness_status": market.get("freshness_status"),
                "same_run_notification_types": _notification_types(notification_rows, key),
            },
        })

    return ReadyToBetResult(
        state_rows=output_rows,
        candidate_rows=candidate_rows,
        summary={
            "mode": normalized_mode,
            "state_counts": dict(sorted(state_counts.items())),
            "reason_counts": dict(sorted(reason_counts.items())),
            "candidate_count": len(candidate_rows),
            "accepted_bets_available": accepted_bets_available,
        },
    )
```

- [ ] **Step 4: Run the state-engine tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_ready_to_bet_shadow.py -q
```

Expected: all state-engine tests pass.

- [ ] **Step 5: Commit the pure engine**

```powershell
git add market_infra/ready_to_bet_shadow.py tests/test_ready_to_bet_shadow.py
git commit -m "feat: add ready to bet shadow state engine"
```

---

### Task 4: Extend The Existing Shadow Candidate Contract And Audit

**Files:**
- Create: `supabase/migrations/20260717181500_ready_to_bet_shadow_candidate.sql`
- Modify: `tests/test_live_layer_schema.py`
- Modify: `tests/test_shadow_notification_candidate_audit.py`
- Modify: `analytics/diagnostics/shadow_notification_candidate_audit.py`

**Interfaces:**
- Supabase accepts `candidate_type='ready_to_bet'` and `provider='therundown_propline'` only in the existing shadow table.
- The existing audit adds `summarize_ready_to_bet(rows)` and a dedicated readiness section.

- [ ] **Step 1: Write failing migration and audit tests**

Add to `tests/test_live_layer_schema.py`:

```python
READY_TO_BET_SHADOW_MIGRATION = (
    MIGRATIONS_DIR / "20260717181500_ready_to_bet_shadow_candidate.sql"
)


def test_ready_to_bet_shadow_migration_extends_existing_candidate_contract():
    sql = READY_TO_BET_SHADOW_MIGRATION.read_text(encoding="utf-8")

    assert "drop constraint if exists shadow_notification_candidates_provider_check" in sql
    assert "drop constraint if exists shadow_notification_candidates_candidate_type_check" in sql
    assert "'therundown_propline'" in sql
    assert "'ready_to_bet'" in sql
    assert "create table" not in sql.lower()
```

Add to `tests/test_shadow_notification_candidate_audit.py`:

```python
from analytics.diagnostics.shadow_notification_candidate_audit import summarize_ready_to_bet


def test_ready_to_bet_summary_counts_dates_windows_and_overlap():
    rows = [
        {
            "slate_date": "2026-07-17",
            "provider": "therundown_propline",
            "candidate_type": "ready_to_bet",
            "time_window": "pre_60",
            "metadata": {"same_run_notification_types": ["pick_upgraded"]},
        },
        {
            "slate_date": "2026-07-18",
            "provider": "therundown",
            "candidate_type": "ready_to_bet",
            "time_window": "pre_30",
            "metadata": {"same_run_notification_types": []},
        },
    ]

    assert summarize_ready_to_bet(rows) == {
        "rows": 2,
        "by_date": {"2026-07-17": 1, "2026-07-18": 1},
        "by_provider": {"therundown": 1, "therundown_propline": 1},
        "by_time_window": {"pre_30": 1, "pre_60": 1},
        "notification_overlap": {"pick_upgraded": 1},
    }
```

- [ ] **Step 2: Run tests and verify RED**

```powershell
python -m pytest tests/test_live_layer_schema.py::test_ready_to_bet_shadow_migration_extends_existing_candidate_contract tests/test_shadow_notification_candidate_audit.py::test_ready_to_bet_summary_counts_dates_windows_and_overlap -q
```

Expected: missing migration and missing `summarize_ready_to_bet` fail.

- [ ] **Step 3: Create the additive migration**

Create `supabase/migrations/20260717181500_ready_to_bet_shadow_candidate.sql`:

```sql
alter table public.shadow_notification_candidates
  drop constraint if exists shadow_notification_candidates_provider_check;

alter table public.shadow_notification_candidates
  add constraint shadow_notification_candidates_provider_check
  check (provider in ('propline', 'boltodds', 'therundown', 'therundown_propline'));

alter table public.shadow_notification_candidates
  drop constraint if exists shadow_notification_candidates_candidate_type_check;

alter table public.shadow_notification_candidates
  add constraint shadow_notification_candidates_candidate_type_check
  check (
    candidate_type in (
      'market_confirmed_playable',
      'market_confirmed_worse_number',
      'better_number_market_fade',
      'mixed_market',
      'no_clear_signal',
      'ready_to_bet'
    )
  );
```

- [ ] **Step 4: Add the readiness audit summary**

Add to `analytics/diagnostics/shadow_notification_candidate_audit.py`:

```python
def summarize_ready_to_bet(rows: list[dict[str, Any]]) -> dict[str, Any]:
    ready_rows = [row for row in rows if row.get("candidate_type") == "ready_to_bet"]
    by_date: Counter[str] = Counter()
    by_provider: Counter[str] = Counter()
    by_time_window: Counter[str] = Counter()
    notification_overlap: Counter[str] = Counter()
    for row in ready_rows:
        by_date[str(row.get("slate_date") or "unknown")] += 1
        by_provider[str(row.get("provider") or "unknown")] += 1
        by_time_window[str(row.get("time_window") or "unknown")] += 1
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        for event_type in metadata.get("same_run_notification_types") or []:
            notification_overlap[str(event_type)] += 1
    return {
        "rows": len(ready_rows),
        "by_date": dict(sorted(by_date.items())),
        "by_provider": dict(sorted(by_provider.items())),
        "by_time_window": dict(sorted(by_time_window.items())),
        "notification_overlap": dict(sorted(notification_overlap.items())),
    }
```

Append a `## Ready-To-Bet Shadow` section in `build_report` using those four maps and explicitly state that it is not a live notification class.

Insert before the existing `## Promotion Rule` section:

```python
ready = summarize_ready_to_bet(rows)
lines.extend([
    "",
    "## Ready-To-Bet Shadow",
    "",
    f"- Rows: {ready['rows']}",
    f"- By date: {json.dumps(ready['by_date'], sort_keys=True)}",
    f"- By provider: {json.dumps(ready['by_provider'], sort_keys=True)}",
    f"- By time window: {json.dumps(ready['by_time_window'], sort_keys=True)}",
    f"- Same-run notification overlap: {json.dumps(ready['notification_overlap'], sort_keys=True)}",
    "- This is shadow evidence only; `ready_to_bet` is not a live notification class.",
])
```

- [ ] **Step 5: Verify migration and audit tests**

```powershell
python -m pytest tests/test_live_layer_schema.py tests/test_shadow_notification_candidate_audit.py -q
```

Expected: all schema and audit tests pass.

- [ ] **Step 6: Commit schema and audit support**

```powershell
git add supabase/migrations/20260717181500_ready_to_bet_shadow_candidate.sql tests/test_live_layer_schema.py analytics/diagnostics/shadow_notification_candidate_audit.py tests/test_shadow_notification_candidate_audit.py
git commit -m "feat: add ready to bet shadow candidate contract"
```

---

### Task 5: Wire Shadow State Into The Live Layer Without Changing Sends

**Files:**
- Modify: `tests/test_live_layer_worker.py`
- Modify: `scripts/build_live_events_to_supabase.py`

**Interfaces:**
- Consumes: `build_ready_to_bet_shadow(...)` from Task 3.
- Produces: `result['ready_to_bet_shadow']`, `result['ready_to_bet_candidate_rows']`, state metadata, and `shadow_pipeline_runs.metadata.ready_to_bet_shadow`.
- Existing `result['notification_rows']` and `notification_events` inserts remain unchanged.

- [ ] **Step 1: Write failing worker tests**

Add focused tests to `tests/test_live_layer_worker.py`:

```python
def test_ready_to_bet_shadow_record_preserves_notification_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_READY_TO_BET_SHADOW", "record")
    pitcher = _fire_pitcher()
    pitcher["quality_gate_level"] = "clean"
    pitcher["ev_over"]["quality_gate_level"] = "clean"
    today = _write_artifact(tmp_path, [pitcher])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "accepted_bets": [],
        "market_snapshots": [{
            "id": "snapshot-1",
            "provider": "propline",
            "provider_event_id": "game-1",
            "normalized_player_name": "tarik skubal",
            "player_name": "Tarik Skubal",
            "bookmaker_key": "fanduel",
            "side": "over",
            "line": 6.5,
            "american_odds": 105,
            "observed_at": "2026-05-06T18:00:00+00:00",
        }],
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

    assert [row["event_type"] for row in result["notification_rows"]] == ["new_fire_pick"]
    assert result["ready_to_bet_shadow"]["candidate_count"] == 1
    assert result["state_rows"][0]["metadata"]["decision_state"] == "ready"
    writer.insert_ignore_rows.assert_any_call(
        "shadow_notification_candidates",
        result["ready_to_bet_candidate_rows"],
        on_conflict="dedupe_key",
    )
    assert result["shadow_pipeline_timing"]["pipeline_run_row"]["metadata"]["ready_to_bet_shadow"]["mode"] == "record"


def test_ready_to_bet_shadow_accepted_bet_read_failure_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_READY_TO_BET_SHADOW", "record")
    pitcher = _fire_pitcher()
    pitcher["quality_gate_level"] = "clean"
    pitcher["ev_over"]["quality_gate_level"] = "clean"
    today = _write_artifact(tmp_path, [pitcher])
    writer = Mock()

    def select_rows(table, params):
        if table == "accepted_bets":
            raise RuntimeError("accepted bets unavailable")
        if table == "market_snapshots":
            return []
        return []

    writer.select_rows.side_effect = select_rows

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

    assert result["ready_to_bet_shadow"]["accepted_bets_available"] is False
    assert result["ready_to_bet_candidate_rows"] == []
    assert [row["event_type"] for row in result["notification_rows"]] == ["new_fire_pick"]


def test_ready_to_bet_shadow_default_off_skips_accepted_bet_read(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVE_READY_TO_BET_SHADOW", raising=False)
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({"live_pick_state": [], "market_snapshots": [], "game_reminder_state": []})

    with patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["ready_to_bet_shadow"]["mode"] == "off"
    assert not any(call.args[0] == "accepted_bets" for call in writer.select_rows.call_args_list)
```

- [ ] **Step 2: Run worker tests and verify RED**

```powershell
python -m pytest tests/test_live_layer_worker.py -k "ready_to_bet_shadow" -q
```

Expected: failures because the worker has no mode, result fields, read, or candidate write.

- [ ] **Step 3: Add mode and safe write helpers**

Import the builder and add helpers in `scripts/build_live_events_to_supabase.py`:

```python
from market_infra.ready_to_bet_shadow import build_ready_to_bet_shadow  # noqa: E402


def _ready_to_bet_shadow_mode() -> str:
    value = str(os.getenv("LIVE_READY_TO_BET_SHADOW") or "off").strip().lower()
    return value if value in {"off", "record"} else "off"


def _write_ready_to_bet_candidates(
    *,
    writer: SupabaseMarketWriter,
    rows: list[dict[str, Any]],
    mode: str,
) -> dict[str, Any]:
    if mode != "record":
        return {"skipped": True, "reason": "disabled", "rows": 0}
    if not rows:
        return {"skipped": True, "reason": "no_candidates", "rows": 0}
    try:
        inserted = writer.insert_ignore_rows(
            "shadow_notification_candidates",
            rows,
            on_conflict="dedupe_key",
        )
        inserted_count = len(inserted) if isinstance(inserted, list) else len(rows)
        return {"skipped": False, "rows": len(rows), "inserted_rows": inserted_count}
    except Exception as error:
        print(f"Warning: ready-to-bet shadow candidate write failed ({error})", file=sys.stderr)
        return {"skipped": True, "reason": "write_failed", "rows": len(rows), "error": str(error)[:1000]}
```

- [ ] **Step 4: Add fail-closed accepted-bet read and pure builder call**

After `notification_rows` is assembled and before notification coordination:

```python
ready_to_bet_mode = _ready_to_bet_shadow_mode()
accepted_bets: list[dict[str, Any]] = []
accepted_bets_available = True
if ready_to_bet_mode == "record":
    try:
        accepted_bets = writer.select_rows(
            "accepted_bets",
            {
                "slate_date": f"eq.{slate_date}",
                "select": "slate_date,pitcher,normalized_pitcher,side,book,k_line,odds,accepted_at",
            },
        )
    except Exception as error:
        accepted_bets_available = False
        print(f"Warning: accepted-bet state read failed ({error}); ready shadow failing closed", file=sys.stderr)

ready_to_bet_result = build_ready_to_bet_shadow(
    slate_date=slate_date,
    pitchers=payload.get("pitchers") or [],
    state_rows=state_rows,
    previous_state_rows=previous_rows,
    live_market_rows=live_market_display_rows,
    accepted_bets=accepted_bets,
    accepted_bets_available=accepted_bets_available,
    notification_rows=notification_rows,
    observed_at=observed_at,
    mode=ready_to_bet_mode,
)
state_rows = ready_to_bet_result.state_rows
```

After the existing market-derived shadow candidate upsert:

```python
ready_to_bet_write = _write_ready_to_bet_candidates(
    writer=writer,
    rows=ready_to_bet_result.candidate_rows,
    mode=ready_to_bet_mode,
)
```

Add `ready_to_bet_shadow` and `ready_to_bet_shadow_write` to
`shadow_pipeline_runs.metadata`, and add these return keys:

```python
"ready_to_bet_shadow": ready_to_bet_result.summary,
"ready_to_bet_shadow_write": ready_to_bet_write,
"ready_to_bet_candidate_rows": ready_to_bet_result.candidate_rows,
```

Do not append ready rows to `notification_rows` or pass them to
`coordinate_notification_rows`.

- [ ] **Step 5: Run focused worker tests and verify GREEN**

```powershell
python -m pytest tests/test_ready_to_bet_shadow.py tests/test_live_layer_worker.py -k "ready_to_bet_shadow or notification_coordinator or mainline_best_price" -q
```

Expected: ready-shadow tests pass and notification coordinator/mainline-price tests remain green.

- [ ] **Step 6: Commit live-layer wiring**

```powershell
git add scripts/build_live_events_to_supabase.py tests/test_live_layer_worker.py
git commit -m "feat: record ready to bet shadow transitions"
```

---

### Task 6: Verify The Complete Change And Update Operating Docs

**Files:**
- Modify: `docs/current-state.md`
- Modify: `docs/superpowers/plans/2026-05-20-live-market-decision-ui.md`
- Modify: `docs/superpowers/plans/2026-06-04-live-notification-digest-coordinator.md`

**Interfaces:**
- Documents the UI trust boundary and the timing flag as shadow-only.
- Does not mark `record` deployed until live evidence exists.

- [ ] **Step 1: Run complete focused verification**

```powershell
node --check dashboard/v2-app.js
node --test dashboard/v2-data.test.mjs dashboard/v2-movement-helpers.test.mjs tests/test_live_market_display_function.mjs tests/test_send_live_notifications_function.mjs tests/test_accepted_bets_function.mjs
python -m pytest tests/test_dashboard_accepted_bet_log.py tests/test_ready_to_bet_shadow.py tests/test_live_layer_schema.py tests/test_shadow_notification_candidate_audit.py tests/test_market_infra_live_market_display.py tests/test_mainline_price_notifications.py tests/test_notification_coordinator.py tests/test_live_layer_worker.py -q
git diff --check
```

Expected: all Node/Python tests pass, JavaScript syntax is valid, and `git diff --check` is clean.

- [ ] **Step 2: Perform a requirement-by-requirement diff review**

Run:

```powershell
git diff --stat f1c85c97..HEAD
git diff f1c85c97..HEAD -- dashboard/v2-data.js dashboard/v2-app.jsx market_infra/ready_to_bet_shadow.py scripts/build_live_events_to_supabase.py supabase/migrations/20260717181500_ready_to_bet_shadow_candidate.sql
```

Confirm explicitly:

- different-line rows are still visible;
- automatic prefill requires same line;
- `notification_rows` receives no ready candidate;
- BoltOdds is absent from `ACTIVE_PROVIDERS`;
- feature default is `off`;
- no model/provider/lock/retention file changed.

- [ ] **Step 3: Update controlling docs with implementation-ready posture**

Add a dated note to the UI plan:

```markdown
**2026-07-17 same-line trust update:** Alternate-line book rows remain visible, but the compact card labels them `Alt-line context`, same-line live rows outrank different-line rows, and Log Bet automatically prefills only from the model K line. Manual alternate-line selection remains available.
```

Add a dated note to the notification plan:

```markdown
**2026-07-17 ready-to-bet shadow update:** `LIVE_READY_TO_BET_SHADOW=off|record` records decision state and first `ready_to_bet` transitions only. It does not create or suppress notification events. Live send/suppression remains closed pending at least five normal slates and separate Tyler approval.
```

Update the Four-Lane Operating Board next decisions:

- UI: verify same-line defaulting and alternate-line context on the next normal slate.
- Pipeline/notifications: collect five normal slates of ready-shadow overlap and false-candidate evidence before any send/suppression review.

- [ ] **Step 4: Commit and push implementation/docs**

```powershell
git add docs/current-state.md docs/superpowers/plans/2026-05-20-live-market-decision-ui.md docs/superpowers/plans/2026-06-04-live-notification-digest-coordinator.md
git commit -m "docs: record decision integrity shadow posture"
git status --short
git push origin HEAD
```

Expected: clean working tree and all implementation commits pushed.

---

### Task 7: Roll Out UI Trust And Shadow Recording In Safe Order

**Files/Systems:**
- Deploy: Netlify production site `47c15fdf-6278-4109-8877-545cc29eb418`
- Apply: linked Supabase migration
- Deploy: Render service `bbe-live-layer` (`crn-d7tpb19o3t8c739p3qig`)
- Set: `LIVE_READY_TO_BET_SHADOW=record` only after off-mode verification

**Interfaces:**
- UI change is live after Netlify deploy.
- Schema is additive.
- Render code deploys with feature default `off`, then shadow recording is explicitly enabled.

- [ ] **Step 1: Verify the pushed commit and clean checkout**

```powershell
git status --short
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

Expected: working tree clean and local/remote `main` hashes match.

- [ ] **Step 2: Deploy and smoke the dashboard trust fix**

Use the repo-linked Netlify site and deploy the `dashboard` plus existing functions without changing environment variables. Then verify production root and `/v2.html`:

```powershell
netlify deploy --prod --dir dashboard --functions netlify/functions --site 47c15fdf-6278-4109-8877-545cc29eb418
```

Expected smoke:

- asset URLs contain `2026-07-17-same-line-trust`;
- different-line rows say `Alt-line context`;
- Log Bet opens on artifact values when only a different live line exists;
- manual different-line selection still works;
- no mobile horizontal overflow at 390px.

- [ ] **Step 3: Dry-run and apply the additive Supabase migration**

```powershell
npx supabase db push --linked --dry-run
npx supabase db push --linked
```

Expected: only `20260717181500_ready_to_bet_shadow_candidate.sql` is pending/applied. Do not print database secrets.

Verify constraints:

```powershell
npx supabase db query --linked -o json "select conname, pg_get_constraintdef(oid) as definition from pg_constraint where conrelid = 'public.shadow_notification_candidates'::regclass and conname in ('shadow_notification_candidates_provider_check','shadow_notification_candidates_candidate_type_check') order by conname;"
```

Expected: provider includes `therundown_propline`; candidate type includes `ready_to_bet`.

- [ ] **Step 4: Deploy live-layer code with shadow mode off**

Confirm `LIVE_READY_TO_BET_SHADOW` is absent or `off` on only
`crn-d7tpb19o3t8c739p3qig`, then run:

```powershell
render deploys create crn-d7tpb19o3t8c739p3qig --wait --confirm
```

Expected: deploy status `live` on the pushed commit.

- [ ] **Step 5: Verify off-mode behavior before enabling recording**

After one scheduled live-layer tick, run:

```powershell
npx supabase db query --linked -o json "select observed_at, metadata->'ready_to_bet_shadow' as ready_to_bet_shadow, metadata->'notification_coordinator' as notification_coordinator from public.shadow_pipeline_runs order by observed_at desc limit 3;"
npx supabase db query --linked -o json "select event_type, count(*) from public.notification_events where created_at >= now() - interval '30 minutes' group by event_type order by event_type;"
```

Expected: ready mode is `off`; existing grouped/mainline notification posture is unchanged; no `ready_to_bet` notification event exists.

- [ ] **Step 6: Enable record mode and redeploy only the live layer**

Set on Render service `crn-d7tpb19o3t8c739p3qig` only:

```text
LIVE_READY_TO_BET_SHADOW=record
```

Do not change any other Render env var. Redeploy:

```powershell
render deploys create crn-d7tpb19o3t8c739p3qig --wait --confirm
```

- [ ] **Step 7: Verify the first record-mode tick**

```powershell
npx supabase db query --linked -o json "select observed_at, metadata->'ready_to_bet_shadow' as ready_to_bet_shadow, metadata->'ready_to_bet_shadow_write' as ready_to_bet_shadow_write from public.shadow_pipeline_runs order by observed_at desc limit 5;"
npx supabase db query --linked -o json "select slate_date, pitcher, side, provider, current_verdict, k_line, time_window, minutes_to_game, occurred_at, metadata from public.shadow_notification_candidates where candidate_type = 'ready_to_bet' order by occurred_at desc limit 25;"
npx supabase db query --linked -o json "select count(*) as invalid_live_events from public.notification_events where event_type = 'ready_to_bet';"
```

Expected:

- latest run reports `mode=record`;
- candidates, if any, are FIRE/clean/unlocked/pre-start/same-line and exclude BoltOdds;
- `invalid_live_events=0`;
- current notification queue/sender counts remain healthy.

- [ ] **Step 8: Record live evidence and rollback instructions**

Update `docs/current-state.md` and both controlling plans with the concrete deploy ID, commit, first record-mode `observed_at`, candidate count, and queue proof. Commit and push:

```powershell
git add docs/current-state.md docs/superpowers/plans/2026-05-20-live-market-decision-ui.md docs/superpowers/plans/2026-06-04-live-notification-digest-coordinator.md
git commit -m "docs: record ready to bet shadow deployment"
git push origin main
```

Rollback boundaries:

- timing rollback: set `LIVE_READY_TO_BET_SHADOW=off` and redeploy `bbe-live-layer`;
- UI rollback: redeploy the previous Netlify production commit or use `?marketSheet=0` as the immediate operator opt-out;
- do not roll back the additive Supabase constraint migration unless it is proven harmful;
- no model/provider/lock/sender rollback should be needed because those surfaces are unchanged.

---

## Self-Review

**Spec coverage:** Tasks 1-2 implement same-line row preference, alternate-line context copy, same-line-only automatic prefill, manual alternate-line preservation, bundle rebuild, and mobile smoke. Tasks 3-5 implement all five decision states, precedence, readiness gates, accepted-bet fail-closed behavior, BoltOdds exclusion, stable transition dedupe, existing-table persistence, run metadata, and unchanged notification rows. Tasks 4 and 7 provide the five-slate audit foundation and safe rollout sequence.

**Placeholder scan:** The plan contains no placeholder markers, unspecified validation steps, or undefined neighboring interfaces. Every code task contains explicit tests, expected RED reason, implementation snippets, GREEN command, and commit command.

**Type consistency:** `build_ready_to_bet_shadow(...)` returns `ReadyToBetResult` with `state_rows`, `candidate_rows`, and `summary`. Worker integration and tests use those exact names. The mode values are consistently `off|record`, state values are consistently `watching|ready|logged|locked|started`, and the candidate type is consistently `ready_to_bet`.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-17-decision-integrity-and-ready-to-bet-shadow.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, and keep each TDD cycle isolated.
2. **Inline Execution** - execute tasks in this session using `superpowers:executing-plans`, with checkpoints between the dashboard, shadow engine, worker wiring, and rollout.
