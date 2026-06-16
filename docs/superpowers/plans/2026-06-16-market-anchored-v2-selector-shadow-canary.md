# Market-Anchored V2 Selector Shadow Canary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a feature-flagged, market-anchored v2 selector as shadow metadata first, then use post-grading evidence to decide whether a tightly bounded downside-only canary deserves Tyler approval.

**Architecture:** Create a pure runtime selector module that computes market-implied K projection, market-anchor projection, strict/core selector labels, and would-have action metadata from fields already present in `today.json`. Wire it after quality, confidence-referee, and profit-rescue caps so the first implementation cannot change live behavior in `off` or `shadow` mode. Persist the metadata into `picks_history` and Gate C so post-grading audits can compare current displayed verdicts against the v2 selector without changing lambda, thresholds, staking, provider order, notifications, locks, retention, dashboard source-of-truth, or calibration.

**Tech Stack:** Python 3.11, existing pipeline quality-gate chain, SQLite-backed `picks_history.json`, Gate C JSONL diagnostics, pytest, Render post-grading shadow report runner.

---

Date: 2026-06-16
Owner: Tyler + Codex
Status: Default-off metadata plumbing implemented on branch `codex/market-anchor-selector-shadow`; not deployed; production behavior closed

## Implementation Update: 2026-06-16

The default-off plumbing now exists on branch
`codex/market-anchor-selector-shadow`. The implementation adds:

- pure selector metadata in `pipeline/market_anchor_selector.py`
- quality-gate wiring after confidence-referee and profit-rescue caps
- SQLite / `picks_history.json` round-trip support
- tracked-pick and Gate C passthrough fields
- a post-grading selector canary audit and runner skip flag

The runtime default remains `MARKET_ANCHOR_SELECTOR_MODE=off`, which adds no
metadata and does not change verdicts. `shadow` is available in code for a
future Tyler-approved deployment. `enforce_downside` remains closed until the
post-grading audit gates pass and Tyler separately approves that environment
change.

## Evidence Read

Current report: `analytics/output/market_anchored_k_shadow_rebuild.md`, generated `2026-06-13T17:38:36Z`.

- Current FIRE tracked selector: `549` rows, `269-280`, `-39.93u`, `-7.3% ROI`.
- Market-anchor core tracked selector: `485` rows, `269-216`, `-5.48u`, `-1.1% ROI`.
- Market-anchor strict tracked selector: `149` rows, `90-59`, `+6.41u`, `+4.3% ROI`.
- Projection lift: current model MAE/RMSE/side accuracy was `1.832` / `2.286` / `53.9%`; market-anchor was `1.741` / `2.175` / `56.9%`.

Interpretation: strict market-anchor shape is promising enough for a shadow/canary plan, not enough for immediate model, threshold, staking, or live promotion.

## Guardrails

- This plan does not approve any environment-variable promotion.
- Default runtime mode must be `MARKET_ANCHOR_SELECTOR_MODE=off`.
- `shadow` mode may add metadata only.
- Any behavior-changing mode must be downside-only: it may lower current FIRE exposure but must never promote PASS or LEAN to FIRE.
- Do not change `lambda`, `raw_lambda`, `formula_change_date`, EV thresholds, staking, provider/source order, notification classes, lock behavior, retention, dashboard source-of-truth, calibration, or Render env vars from this plan.
- Do not use result, PnL, CLV, actual IP, actual pitch count, batters faced, or post-start live rows as runtime selector inputs.
- Treat market-anchor metadata as personal-use research evidence only.

## Runtime Selector Contract

Environment variable:

```text
MARKET_ANCHOR_SELECTOR_MODE=off|shadow|enforce_downside
```

Mode behavior:

| Mode | Metadata | Verdict Behavior |
| --- | --- | --- |
| `off` | no selector metadata | no change |
| `shadow` | add `market_anchor_selector` metadata to each side | no change |
| `enforce_downside` | add metadata and set `applied=true` when a FIRE would be capped | cap current FIRE rows that fail `market_anchor_strict` to `LEAN`; never raise a verdict |

`enforce_downside` must stay unconfigured until a later Tyler approval after this plan's audit gates pass.

Side metadata shape:

```json
{
  "mode": "shadow",
  "selected_side": "over",
  "market_favorite_side": "over",
  "relationship": "model_agrees_with_favorite",
  "no_vig_side_probability": 0.5412,
  "market_implied_projection": 5.2143,
  "market_anchor_projection": 5.4872,
  "anchor_side": "over",
  "anchor_edge": 0.0214,
  "labels": ["market_anchor_side_agrees", "market_anchor_core", "market_anchor_strict"],
  "current_verdict": "FIRE 1u",
  "would_verdict": "FIRE 1u",
  "would_cap_to": "FIRE 1u",
  "applied": false,
  "reasons": []
}
```

Strict label rules, using runtime-safe fields only:

- `market_anchor_side_agrees`: market-anchor projection points to the selected side.
- `market_anchor_core`: side agrees and anchored no-vig edge is between `0.005` and `0.12`.
- `market_anchor_strict`: core plus selected side is the market favorite, model agrees with favorite, quality gate is clean/none, line is at or below `6.5`, workload is not fragile, and timing/opening context is not late/noisy.

Workload runtime proxy:

- Stable when `days_since_last_start` is missing or `>= 4`, and `last_pitch_count` is missing or `<= 110`.
- Fragile when `days_since_last_start < 4` or `last_pitch_count > 110`.
- Do not use actual IP, actual pitch count, batters faced, or final result.

## File Structure

- Create `pipeline/market_anchor_selector.py`
  - Pure selector math and metadata application.
  - Imports `american_to_implied`, `market_favorite_side`, `cap_verdict`, and `VERDICT_ORDER` from `pipeline/confidence_referee.py`.
- Create `tests/test_market_anchor_selector.py`
  - Unit tests for mode parsing, no-vig conversion, projection inversion, strict labels, shadow mode, and downside-only enforce mode.
- Modify `pipeline/quality_gates.py`
  - Apply selector after `apply_profit_rescue_to_side`.
- Modify `tests/test_quality_gates.py`
  - Integration tests proving default/off behavior is identical and shadow metadata is attached after existing caps.
- Modify `pipeline/fetch_results.py`
  - Add `market_anchor_selector_json` SQLite column and round-trip it through seed/load/export.
- Modify `tests/test_fetch_results.py`
  - Persistence tests for seeded today rows, history load, and history export.
- Modify `pipeline/run_pipeline.py`
  - Add selector metadata to tracked pick rows and reconciliation rows.
- Modify `tests/test_run_pipeline.py`
  - Tracked-pick visibility tests.
- Modify `analytics/diagnostics/pitcher_k_outcome_dataset.py`
  - Carry `market_anchor_selector` into Gate C rows from side artifacts and `picks_history`.
- Modify `tests/test_pitcher_k_outcome_dataset.py`
  - Gate C metadata enrichment tests.
- Create `analytics/diagnostics/market_anchor_selector_canary_audit.py`
  - Post-grading audit for shadow metadata and would-have verdicts.
- Create `tests/test_market_anchor_selector_canary_audit.py`
  - Audit bucketing tests.
- Modify `scripts/run_post_grading_shadow_reports.py`
  - Add optional `--run-market-anchor-selector-audit`, default on after metadata exists.
- Modify `docs/current-state.md`
  - Add this plan to read order and model-lane next decision after implementation.

## Task 1: Pure Runtime Selector Module

**Files:**
- Create: `pipeline/market_anchor_selector.py`
- Create: `tests/test_market_anchor_selector.py`

- [ ] **Step 1: Write failing unit tests**

Add `tests/test_market_anchor_selector.py`:

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))

from market_anchor_selector import (
    apply_market_anchor_selector_to_side,
    market_anchor_mode,
    market_implied_projection,
    no_vig_side_probability,
)


def _record(**overrides):
    record = {
        "pitcher": "Example Starter",
        "k_line": 5.5,
        "lambda": 6.2,
        "best_over_odds": -130,
        "best_under_odds": 110,
        "quality_gate_level": "clean",
        "opening_odds_source": "preview",
        "days_since_last_start": 5,
        "last_pitch_count": 92,
    }
    record.update(overrides)
    return record


def _side(**overrides):
    side = {
        "verdict": "FIRE 1u",
        "actionable_verdict": "FIRE 1u",
        "raw_verdict": "FIRE 1u",
        "edge": 0.055,
        "ev": 0.09,
        "adj_ev": 0.08,
    }
    side.update(overrides)
    return side


def test_mode_defaults_off_and_invalid_returns_off(monkeypatch):
    monkeypatch.delenv("MARKET_ANCHOR_SELECTOR_MODE", raising=False)
    assert market_anchor_mode() == "off"
    monkeypatch.setenv("MARKET_ANCHOR_SELECTOR_MODE", "bad")
    assert market_anchor_mode() == "off"


def test_no_vig_side_probability_normalizes_two_prices():
    over_prob = no_vig_side_probability(-130, 110, "over")
    under_prob = no_vig_side_probability(-130, 110, "under")
    assert round(over_prob + under_prob, 6) == 1.0
    assert over_prob > under_prob


def test_market_projection_inverts_no_vig_probability():
    projection = market_implied_projection(k_line=4.5, over_probability=0.5)
    assert 4.0 < projection < 5.0
    assert market_implied_projection(k_line=4.5, over_probability=0.62) > projection


def test_shadow_adds_metadata_without_changing_verdict():
    updated = apply_market_anchor_selector_to_side(_record(), "over", _side(), mode="shadow")

    assert updated["verdict"] == "FIRE 1u"
    assert updated["actionable_verdict"] == "FIRE 1u"
    assert updated["market_anchor_selector"]["mode"] == "shadow"
    assert updated["market_anchor_selector"]["applied"] is False
    assert "market_anchor_selector" in updated


def test_strict_label_requires_clean_market_favorite_stable_context():
    updated = apply_market_anchor_selector_to_side(_record(), "over", _side(), mode="shadow")
    labels = updated["market_anchor_selector"]["labels"]

    assert "market_anchor_core" in labels
    assert "market_anchor_strict" in labels

    fragile = apply_market_anchor_selector_to_side(
        _record(days_since_last_start=3),
        "over",
        _side(),
        mode="shadow",
    )
    assert "market_anchor_strict" not in fragile["market_anchor_selector"]["labels"]


def test_enforce_downside_caps_fire_that_fails_strict_only():
    updated = apply_market_anchor_selector_to_side(
        _record(days_since_last_start=3),
        "over",
        _side(verdict="FIRE 2u", actionable_verdict="FIRE 2u", raw_verdict="FIRE 2u"),
        mode="enforce_downside",
    )

    assert updated["verdict"] == "LEAN"
    assert updated["actionable_verdict"] == "LEAN"
    assert updated["raw_verdict"] == "FIRE 2u"
    assert updated["market_anchor_selector"]["applied"] is True
    assert "cap_fire_without_market_anchor_strict" in updated["market_anchor_selector"]["reasons"]


def test_enforce_downside_never_raises_lean():
    updated = apply_market_anchor_selector_to_side(
        _record(),
        "over",
        _side(verdict="LEAN", actionable_verdict="LEAN", raw_verdict="LEAN"),
        mode="enforce_downside",
    )

    assert updated["verdict"] == "LEAN"
    assert updated["actionable_verdict"] == "LEAN"
    assert updated["market_anchor_selector"]["would_verdict"] == "LEAN"
    assert updated["market_anchor_selector"]["applied"] is False
```

- [ ] **Step 2: Run red test**

Run:

```powershell
python -m pytest tests/test_market_anchor_selector.py -q
```

Expected: fails with `ModuleNotFoundError: No module named 'market_anchor_selector'`.

- [ ] **Step 3: Add selector module**

Create `pipeline/market_anchor_selector.py`:

```python
"""Runtime-safe market-anchored selector metadata.

This module is pure and feature-flagged. In shadow mode it only annotates side
payloads. In enforce_downside mode it can only lower current FIRE exposure and
must not change lambda, thresholds, staking, provider order, notifications,
locks, retention, calibration, or dashboard source-of-truth behavior.
"""

from __future__ import annotations

import copy
import math
import os
from typing import Any

from confidence_referee import (
    VERDICT_ORDER,
    american_to_implied,
    cap_verdict,
    market_favorite_side,
)


VALID_MODES = {"off", "shadow", "enforce_downside"}


def market_anchor_mode() -> str:
    value = os.getenv("MARKET_ANCHOR_SELECTOR_MODE", "off").strip().lower()
    return value if value in VALID_MODES else "off"


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _clamp_probability(value: float) -> float:
    return max(0.0001, min(0.9999, value))


def poisson_cdf(k: int, lam: float) -> float:
    if k < 0:
        return 0.0
    lam = max(0.0, lam)
    term = math.exp(-lam)
    total = term
    for idx in range(1, k + 1):
        term *= lam / idx
        total += term
    return max(0.0, min(1.0, total))


def poisson_over_probability(k_line: float, lam: float) -> float:
    return _clamp_probability(1.0 - poisson_cdf(math.floor(k_line), lam))


def market_implied_projection(k_line: float, over_probability: float) -> float:
    target = _clamp_probability(over_probability)
    low = 0.0
    high = max(12.0, k_line + 8.0)
    while poisson_over_probability(k_line, high) < target and high < 40.0:
        high *= 1.5

    for _ in range(72):
        mid = (low + high) / 2.0
        if poisson_over_probability(k_line, mid) < target:
            low = mid
        else:
            high = mid
    return round((low + high) / 2.0, 4)


def no_vig_side_probability(over_odds: Any, under_odds: Any, side: str) -> float | None:
    over = american_to_implied(over_odds)
    under = american_to_implied(under_odds)
    if over is None or under is None or over + under <= 0:
        return None
    side_value = str(side or "").strip().lower()
    if side_value == "over":
        return round(over / (over + under), 4)
    if side_value == "under":
        return round(under / (over + under), 4)
    return None


def _current_verdict(side_data: dict[str, Any]) -> str:
    return str(side_data.get("actionable_verdict") or side_data.get("verdict") or "PASS").strip() or "PASS"


def _is_fire(verdict: Any) -> bool:
    return str(verdict or "").startswith("FIRE")


def _relationship(record: dict[str, Any], selected_side: str) -> tuple[str, str]:
    favorite_side = market_favorite_side(record.get("best_over_odds"), record.get("best_under_odds"))
    if selected_side == favorite_side:
        return "model_agrees_with_favorite", favorite_side
    if favorite_side in {"over", "under"}:
        return "model_fades_favorite", favorite_side
    return "unknown", favorite_side


def _stable_workload(record: dict[str, Any]) -> bool:
    days = _to_float(record.get("days_since_last_start"))
    pitches = _to_float(record.get("last_pitch_count"))
    if days is not None and days < 4:
        return False
    if pitches is not None and pitches > 110:
        return False
    return True


def _line(record: dict[str, Any]) -> float | None:
    return _to_float(record.get("k_line"))


def _selected_side_probability(k_line: float, projection: float, selected_side: str) -> float:
    over_probability = poisson_over_probability(k_line, projection)
    if selected_side == "over":
        return over_probability
    return _clamp_probability(1.0 - over_probability)


def _baseball_blend_weight(record: dict[str, Any], relationship: str) -> float:
    weight = 0.35
    quality = str(record.get("quality_gate_level") or "").strip().lower()
    line = _line(record)

    if quality and quality not in {"clean", "none"}:
        weight -= 0.10
    if relationship == "model_fades_favorite":
        weight -= 0.10
    if not _stable_workload(record):
        weight -= 0.10
    if line is not None and line >= 7.5:
        weight -= 0.05
    return max(0.15, min(0.45, weight))


def _projected_side(k_line: float, projection: float) -> str | None:
    if projection > k_line:
        return "over"
    if projection < k_line:
        return "under"
    return None


def _selector_metadata(record: dict[str, Any], selected_side: str, side_data: dict[str, Any], mode: str) -> dict[str, Any]:
    line = _line(record)
    current_projection = _to_float(record.get("lambda"))
    over_probability = no_vig_side_probability(
        record.get("best_over_odds"),
        record.get("best_under_odds"),
        "over",
    )
    side_probability = no_vig_side_probability(
        record.get("best_over_odds"),
        record.get("best_under_odds"),
        selected_side,
    )
    relationship, favorite_side = _relationship(record, selected_side)

    market_projection = None
    anchor_projection = current_projection
    anchor_side = None
    anchor_edge = None
    labels: list[str] = []

    if line is not None and over_probability is not None:
        market_projection = market_implied_projection(line, over_probability)
        if current_projection is not None:
            weight = _baseball_blend_weight(record, relationship)
            anchor_projection = round(market_projection + ((current_projection - market_projection) * weight), 4)
        else:
            anchor_projection = market_projection

    if line is not None and anchor_projection is not None:
        anchor_side = _projected_side(line, anchor_projection)
        selected_probability = _selected_side_probability(line, anchor_projection, selected_side)
        if side_probability is not None:
            anchor_edge = round(selected_probability - side_probability, 4)

    if anchor_side == selected_side:
        labels.append("market_anchor_side_agrees")
    if anchor_side == selected_side and anchor_edge is not None and 0.005 <= anchor_edge <= 0.12:
        labels.append("market_anchor_core")

    quality = str(record.get("quality_gate_level") or "").strip().lower()
    clean_quality = quality in {"", "clean", "none"}
    stable_line = line is None or line <= 6.5
    stable_timing = str(record.get("opening_odds_source") or "").strip().lower() in {"preview", "full_movement", ""}
    if (
        "market_anchor_core" in labels
        and relationship == "model_agrees_with_favorite"
        and selected_side == favorite_side
        and clean_quality
        and _stable_workload(record)
        and stable_line
        and stable_timing
    ):
        labels.append("market_anchor_strict")

    current_verdict = _current_verdict(side_data)
    would_verdict = current_verdict
    reasons: list[str] = []
    if _is_fire(current_verdict) and "market_anchor_strict" not in labels:
        would_verdict = cap_verdict(current_verdict, "LEAN")
        reasons.append("cap_fire_without_market_anchor_strict")

    applied = mode == "enforce_downside" and VERDICT_ORDER.get(would_verdict, 0) < VERDICT_ORDER.get(current_verdict, 0)

    return {
        "mode": mode,
        "selected_side": selected_side,
        "market_favorite_side": favorite_side,
        "relationship": relationship,
        "no_vig_side_probability": side_probability,
        "market_implied_projection": market_projection,
        "market_anchor_projection": anchor_projection,
        "anchor_side": anchor_side,
        "anchor_edge": anchor_edge,
        "labels": labels,
        "current_verdict": current_verdict,
        "would_verdict": would_verdict,
        "would_cap_to": would_verdict,
        "applied": applied,
        "reasons": reasons,
    }


def apply_market_anchor_selector_to_side(
    record: dict[str, Any],
    side: str,
    side_data: dict[str, Any],
    mode: str | None = None,
) -> dict[str, Any]:
    active_mode = mode or market_anchor_mode()
    if active_mode not in VALID_MODES:
        active_mode = "off"

    updated = copy.deepcopy(side_data)
    if active_mode == "off":
        return updated

    selected_side = str(side or "").strip().lower()
    if selected_side not in {"over", "under"}:
        return updated

    metadata = _selector_metadata(record, selected_side, updated, active_mode)
    updated["market_anchor_selector"] = metadata

    if metadata["applied"]:
        updated["verdict"] = metadata["would_verdict"]
        updated["actionable_verdict"] = metadata["would_verdict"]

    return updated
```

- [ ] **Step 4: Run green test**

Run:

```powershell
python -m pytest tests/test_market_anchor_selector.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add pipeline/market_anchor_selector.py tests/test_market_anchor_selector.py
git commit -m "feat: add market anchor selector module"
```

## Task 2: Wire Selector After Existing Caps

**Files:**
- Modify: `pipeline/quality_gates.py`
- Modify: `tests/test_quality_gates.py`

- [ ] **Step 1: Write failing integration tests**

Append to `tests/test_quality_gates.py`:

```python
def test_market_anchor_selector_default_off_is_behavior_identical(monkeypatch):
    monkeypatch.delenv("MARKET_ANCHOR_SELECTOR_MODE", raising=False)
    record = clean_fire_record()

    gated = apply_quality_to_record(record)

    assert gated["ev_over"]["verdict"] == "FIRE 2u"
    assert "market_anchor_selector" not in gated["ev_over"]


def test_market_anchor_selector_shadow_runs_after_profit_rescue(monkeypatch):
    monkeypatch.setenv("PROFIT_RESCUE_REFEREE_MODE", "enforce")
    monkeypatch.setenv("MARKET_ANCHOR_SELECTOR_MODE", "shadow")
    record = clean_fire_record()
    record["best_over_odds"] = -125
    record["best_under_odds"] = 105

    gated = apply_quality_to_record(record)

    assert gated["ev_over"]["profit_rescue_referee"]["applied"] is True
    assert gated["ev_over"]["verdict"] == "FIRE 1u"
    assert gated["ev_over"]["market_anchor_selector"]["mode"] == "shadow"
    assert gated["ev_over"]["market_anchor_selector"]["current_verdict"] == "FIRE 1u"
    assert gated["ev_over"]["market_anchor_selector"]["applied"] is False
```

- [ ] **Step 2: Run red test**

Run:

```powershell
python -m pytest tests/test_quality_gates.py -q
```

Expected: the second new test fails because `market_anchor_selector` is not wired.

- [ ] **Step 3: Wire module into quality gates**

Modify imports in `pipeline/quality_gates.py`:

```python
from market_anchor_selector import apply_market_anchor_selector_to_side
```

Modify `_apply_quality_to_side`:

```python
    side_name = "over" if side_key == "ev_over" else "under"
    updated = apply_referee_to_side(record, side_name, updated)
    updated = apply_profit_rescue_to_side(record, side_name, updated)
    return apply_market_anchor_selector_to_side(record, side_name, updated)
```

- [ ] **Step 4: Run green tests**

Run:

```powershell
python -m pytest tests/test_quality_gates.py tests/test_market_anchor_selector.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

Run:

```powershell
git add pipeline/quality_gates.py tests/test_quality_gates.py
git commit -m "feat: attach market anchor selector metadata"
```

## Task 3: Persist Selector Metadata Through History

**Files:**
- Modify: `pipeline/fetch_results.py`
- Modify: `tests/test_fetch_results.py`

- [ ] **Step 1: Write failing persistence tests**

Update `tests/test_fetch_results.py`:

```python
def test_market_anchor_selector_column_exists(tmp_db):
    import fetch_results as fr
    fr.init_db()
    with fr.get_db() as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(picks)")}
    assert "market_anchor_selector_json" in cols


def test_seed_picks_stores_market_anchor_selector_json(tmp_db, tmp_path):
    import fetch_results as fr
    today = {
        "date": "2026-06-16",
        "pitchers": [
            {
                "pitcher": "Example Starter",
                "team": "Arizona Diamondbacks",
                "opp_team": "Los Angeles Dodgers",
                "k_line": 5.5,
                "lambda": 6.2,
                "raw_lambda": 6.2,
                "game_time": "2026-06-16T23:40:00Z",
                "lineup_used": True,
                "data_complete": True,
                "ev_over": {
                    "verdict": "FIRE 1u",
                    "actionable_verdict": "FIRE 1u",
                    "raw_verdict": "FIRE 1u",
                    "edge": 0.04,
                    "ev": 0.08,
                    "adj_ev": 0.08,
                    "raw_adj_ev": 0.08,
                    "movement_conf": 1.0,
                    "market_anchor_selector": {
                        "mode": "shadow",
                        "labels": ["market_anchor_strict"],
                        "applied": False,
                    },
                },
                "ev_under": {
                    "verdict": "PASS",
                    "actionable_verdict": "PASS",
                    "edge": -0.02,
                    "ev": -0.03,
                    "adj_ev": -0.03,
                    "movement_conf": 1.0,
                },
                "best_over_odds": -115,
                "best_under_odds": -105,
            }
        ],
    }
    path = tmp_path / "today.json"
    path.write_text(json.dumps(today))

    fr.seed_picks(path)

    with fr.get_db() as conn:
        row = conn.execute("SELECT market_anchor_selector_json FROM picks").fetchone()
    assert json.loads(row[0])["labels"] == ["market_anchor_strict"]


def test_history_export_round_trips_market_anchor_selector(tmp_db, tmp_path):
    import fetch_results as fr
    fr.init_db()
    with fr.get_db() as conn:
        conn.execute(
            """
            INSERT INTO picks (
                date, pitcher, team, side, k_line, verdict, ev, adj_ev,
                raw_lambda, applied_lambda, odds, movement_conf,
                market_anchor_selector_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "2026-06-16",
                "Example Starter",
                "ARI",
                "over",
                5.5,
                "FIRE 1u",
                0.08,
                0.08,
                6.2,
                6.2,
                -115,
                1.0,
                json.dumps({"mode": "shadow", "applied": False}),
            ),
        )
    history_path = tmp_path / "picks_history.json"

    fr.export_db_to_history(history_path)
    exported = json.loads(history_path.read_text())

    assert exported[0]["market_anchor_selector"] == {"mode": "shadow", "applied": False}
```

- [ ] **Step 2: Run red tests**

Run:

```powershell
python -m pytest tests/test_fetch_results.py -q
```

Expected: failures mention missing `market_anchor_selector_json`.

- [ ] **Step 3: Add SQLite column and seed path**

Modify `init_db()` in `pipeline/fetch_results.py`:

```python
                confidence_referee_json TEXT,
                market_anchor_selector_json TEXT
```

Add migration entry:

```python
            ("market_anchor_selector_json", "TEXT"),
```

Inside `seed_picks()`, after `confidence_referee_json`:

```python
                market_anchor_selector_json = _json_or_none(ev_data.get("market_anchor_selector"))
```

Add `market_anchor_selector_json` to the INSERT column list and values list immediately after `confidence_referee_json`.

- [ ] **Step 4: Add load/export round trip**

In `load_history_into_db()`, add `market_anchor_selector_json` to the INSERT columns and `_json_or_none(p.get("market_anchor_selector"))` to values.

In `export_db_to_history()`, select `market_anchor_selector_json`, add it to `cols`, and decode it:

```python
        pick["market_anchor_selector"] = _json_load_or_none(
            pick.pop("market_anchor_selector_json", None)
        )
```

- [ ] **Step 5: Run green tests**

Run:

```powershell
python -m pytest tests/test_fetch_results.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

Run:

```powershell
git add pipeline/fetch_results.py tests/test_fetch_results.py
git commit -m "feat: persist market anchor selector metadata"
```

## Task 4: Surface Metadata In Dashboard Artifacts And Gate C

**Files:**
- Modify: `pipeline/run_pipeline.py`
- Modify: `tests/test_run_pipeline.py`
- Modify: `analytics/diagnostics/pitcher_k_outcome_dataset.py`
- Modify: `tests/test_pitcher_k_outcome_dataset.py`

- [ ] **Step 1: Write failing tracked-pick tests**

Add to `tests/test_run_pipeline.py` near existing confidence/profit metadata tests:

```python
def test_tracked_pick_row_exposes_market_anchor_selector_metadata():
    import run_pipeline
    pick = {
        "date": "2026-06-16",
        "pitcher": "Example Starter",
        "team": "ARI",
        "opp_team": "LAD",
        "side": "over",
        "verdict": "FIRE 1u",
        "k_line": 5.5,
        "odds": -115,
        "adj_ev": 0.08,
        "game_time": "2026-06-16T23:40:00Z",
        "market_anchor_selector": {"mode": "shadow", "labels": ["market_anchor_strict"]},
    }

    row = run_pipeline._tracked_pick_row(pick)

    assert row["market_anchor_selector"]["mode"] == "shadow"
    assert row["market_anchor_selector"]["labels"] == ["market_anchor_strict"]
```

- [ ] **Step 2: Write failing Gate C tests**

Add to `tests/test_pitcher_k_outcome_dataset.py`:

```python
def test_gate_c_rows_carry_market_anchor_selector_from_side_payload():
    from analytics.diagnostics import pitcher_k_outcome_dataset as dataset

    market = {
        "date": "2026-06-16",
        "pitcher": "Example Starter",
        "k_line": 5.5,
        "over_odds": -115,
        "under_odds": -105,
        "actual_ks": 6,
        "winning_side": "over",
        "lambda": 6.2,
        "ev_over": {
            "verdict": "FIRE 1u",
            "edge": 0.04,
            "ev": 0.08,
            "adj_ev": 0.08,
            "market_anchor_selector": {"mode": "shadow", "labels": ["market_anchor_strict"]},
        },
        "ev_under": {"verdict": "PASS", "edge": -0.02, "ev": -0.03, "adj_ev": -0.03},
    }

    rows = dataset.build_official_close_rows([market])
    over = next(row for row in rows if row["side"] == "over")

    assert over["market_anchor_selector"]["labels"] == ["market_anchor_strict"]
```

- [ ] **Step 3: Run red tests**

Run:

```powershell
python -m pytest tests/test_run_pipeline.py tests/test_pitcher_k_outcome_dataset.py -q
```

Expected: failures mention missing `market_anchor_selector`.

- [ ] **Step 4: Add tracked-pick passthrough**

In `pipeline/run_pipeline.py`, update `_tracked_pick_row()`:

```python
    if pick.get("market_anchor_selector") is not None:
        row["market_anchor_selector"] = pick.get("market_anchor_selector")
```

Update `_reconciled_unlocked_tracked_pick()` after profit-rescue passthrough:

```python
    if side_data.get("market_anchor_selector") is not None:
        row["market_anchor_selector"] = side_data.get("market_anchor_selector")
```

- [ ] **Step 5: Add Gate C fields**

In `analytics/diagnostics/pitcher_k_outcome_dataset.py`, add to each side row:

```python
                "market_anchor_selector": ev.get("market_anchor_selector") or market.get("market_anchor_selector"),
                "market_anchor_selector_mode": (
                    (ev.get("market_anchor_selector") or {}).get("mode")
                    if isinstance(ev.get("market_anchor_selector"), dict)
                    else None
                ),
                "market_anchor_selector_labels": (
                    (ev.get("market_anchor_selector") or {}).get("labels")
                    if isinstance(ev.get("market_anchor_selector"), dict)
                    else None
                ),
                "market_anchor_selector_applied": (
                    (ev.get("market_anchor_selector") or {}).get("applied")
                    if isinstance(ev.get("market_anchor_selector"), dict)
                    else None
                ),
```

In `enrich_rows_with_pick_history()`, set defaults:

```python
        next_row.setdefault("market_anchor_selector", None)
        next_row.setdefault("market_anchor_selector_mode", None)
        next_row.setdefault("market_anchor_selector_labels", None)
        next_row.setdefault("market_anchor_selector_applied", None)
```

When `pick is not None`, merge history metadata:

```python
                    "market_anchor_selector": pick.get("market_anchor_selector")
                    if pick.get("market_anchor_selector") is not None
                    else next_row.get("market_anchor_selector"),
```

After `next_row.update(...)`, normalize derived fields:

```python
            selector = next_row.get("market_anchor_selector")
            if isinstance(selector, dict):
                next_row["market_anchor_selector_mode"] = selector.get("mode")
                next_row["market_anchor_selector_labels"] = selector.get("labels")
                next_row["market_anchor_selector_applied"] = selector.get("applied")
```

- [ ] **Step 6: Run green tests**

Run:

```powershell
python -m pytest tests/test_run_pipeline.py tests/test_pitcher_k_outcome_dataset.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

Run:

```powershell
git add pipeline/run_pipeline.py analytics/diagnostics/pitcher_k_outcome_dataset.py tests/test_run_pipeline.py tests/test_pitcher_k_outcome_dataset.py
git commit -m "feat: expose market anchor selector in research rows"
```

## Task 5: Post-Grading Selector Audit

**Files:**
- Create: `analytics/diagnostics/market_anchor_selector_canary_audit.py`
- Create: `tests/test_market_anchor_selector_canary_audit.py`
- Modify: `scripts/run_post_grading_shadow_reports.py`

- [ ] **Step 1: Write failing audit tests**

Create `tests/test_market_anchor_selector_canary_audit.py`:

```python
from analytics.diagnostics import market_anchor_selector_canary_audit as audit


def _row(**overrides):
    row = {
        "slate_date": "2026-06-16",
        "pitcher": "Example Starter",
        "side": "over",
        "result": "win",
        "pick_history_pnl": 0.91,
        "is_tracked_pick": True,
        "display_verdict": "FIRE 1u",
        "raw_verdict": "FIRE 1u",
        "quality_gate_level": "clean",
        "line_bucket": "5.5",
        "price_sign": "minus",
        "model_market_relationship": "model_agrees_with_favorite",
        "market_anchor_selector": {
            "mode": "shadow",
            "labels": ["market_anchor_side_agrees", "market_anchor_core", "market_anchor_strict"],
            "would_verdict": "FIRE 1u",
            "applied": False,
        },
    }
    row.update(overrides)
    return row


def test_summarize_counts_strict_and_non_strict_fire_rows():
    rows = [
        _row(result="win", pick_history_pnl=0.91),
        _row(
            pitcher="Loss Starter",
            result="loss",
            pick_history_pnl=-1.0,
            market_anchor_selector={
                "mode": "shadow",
                "labels": ["market_anchor_side_agrees"],
                "would_verdict": "LEAN",
                "applied": False,
            },
        ),
    ]

    summary = audit.summarize(rows)

    assert summary["tracked_rows"] == 2
    assert summary["strict_fire"]["rows"] == 1
    assert summary["non_strict_fire"]["rows"] == 1
    assert summary["strict_fire"]["pnl"] == 0.91
    assert summary["non_strict_fire"]["pnl"] == -1.0


def test_render_report_states_shadow_only_boundary():
    report = audit.render_report(audit.summarize([_row()]))

    assert "# Market Anchor Selector Canary Audit" in report
    assert "Shadow-only" in report
    assert "does not change live" in report
    assert "Promotion Gate" in report
```

- [ ] **Step 2: Run red test**

Run:

```powershell
python -m pytest tests/test_market_anchor_selector_canary_audit.py -q
```

Expected: fails because the audit module does not exist.

- [ ] **Step 3: Implement audit module**

Create `analytics/diagnostics/market_anchor_selector_canary_audit.py`:

```python
"""Post-grading audit for market-anchor selector shadow metadata."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "market_anchor_selector_canary_audit.md"
WIN_LOSS_RESULTS = {"win", "loss"}


def _to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _selector(row: dict[str, Any]) -> dict[str, Any]:
    value = row.get("market_anchor_selector")
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _labels(row: dict[str, Any]) -> set[str]:
    raw = _selector(row).get("labels") or row.get("market_anchor_selector_labels") or []
    if isinstance(raw, str):
        raw = [raw]
    return {str(label) for label in raw if str(label or "").strip()}


def _is_fire(value: Any) -> bool:
    return str(value or "").startswith("FIRE")


def _row_pnl(row: dict[str, Any]) -> float:
    return _to_float(row.get("pick_history_pnl")) or _to_float(row.get("pnl")) or 0.0


def _score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    score = {"rows": 0, "wins": 0, "losses": 0, "pnl": 0.0, "roi": 0.0}
    for row in rows:
        if row.get("result") not in WIN_LOSS_RESULTS:
            continue
        score["rows"] += 1
        if row.get("result") == "win":
            score["wins"] += 1
        else:
            score["losses"] += 1
        score["pnl"] = round(score["pnl"] + _row_pnl(row), 3)
    if score["rows"]:
        score["roi"] = round(score["pnl"] / score["rows"], 4)
    return score


def _tracked(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if row.get("is_tracked_pick") is True and row.get("result") in WIN_LOSS_RESULTS
    ]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    tracked = _tracked(rows)
    with_selector = [row for row in tracked if _selector(row)]
    fire_rows = [row for row in with_selector if _is_fire(row.get("display_verdict") or row.get("verdict"))]
    strict_fire = [row for row in fire_rows if "market_anchor_strict" in _labels(row)]
    non_strict_fire = [row for row in fire_rows if "market_anchor_strict" not in _labels(row)]
    strict_all = [row for row in with_selector if "market_anchor_strict" in _labels(row)]

    slices: dict[str, dict[str, Any]] = {}
    for field in ("side", "line_bucket", "price_sign", "quality_gate_level", "model_market_relationship"):
        buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in strict_all:
            buckets[str(row.get(field) or "unknown")].append(row)
        for bucket, bucket_rows in buckets.items():
            if len(bucket_rows) >= 5:
                slices[f"{field}={bucket}"] = _score(bucket_rows)

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "tracked_rows": len(tracked),
        "selector_rows": len(with_selector),
        "fire_rows": _score(fire_rows),
        "strict_fire": _score(strict_fire),
        "non_strict_fire": _score(non_strict_fire),
        "strict_all": _score(strict_all),
        "strict_slices": slices,
    }


def _format_pnl(value: Any) -> str:
    return f"{(_to_float(value) or 0.0):+.2f}"


def _format_roi(value: Any) -> str:
    number = _to_float(value)
    return "--" if number is None else f"{number:+.1%}"


def _score_line(label: str, score: dict[str, Any]) -> str:
    return (
        f"- {label}: `{score['rows']}` rows, `{score['wins']}-{score['losses']}`, "
        f"`{_format_pnl(score['pnl'])}`, `{_format_roi(score['roi'])}` ROI."
    )


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Market Anchor Selector Canary Audit",
        "",
        f"Generated at: `{summary['generated_at']}`",
        "",
        "Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, dashboard artifacts, or source-of-truth behavior.",
        "",
        "## Executive Read",
        "",
        f"- Tracked graded rows: `{summary['tracked_rows']}`",
        f"- Rows with selector metadata: `{summary['selector_rows']}`",
        _score_line("Displayed FIRE with selector metadata", summary["fire_rows"]),
        _score_line("Market-anchor strict displayed FIRE", summary["strict_fire"]),
        _score_line("Non-strict displayed FIRE", summary["non_strict_fire"]),
        _score_line("All market-anchor strict tracked rows", summary["strict_all"]),
        "",
        "## Strict Slice Check",
        "",
    ]
    slices = summary.get("strict_slices") or {}
    if not slices:
        lines.append("- No strict slices met the minimum display threshold.")
    else:
        for label, score in sorted(slices.items()):
            lines.append(_score_line(label, score))
    lines.extend(
        [
            "",
            "## Promotion Gate",
            "",
            "- Do not enable `MARKET_ANCHOR_SELECTOR_MODE=enforce_downside` from this report alone.",
            "- A promotion review requires at least `150` clean tracked rows with selector metadata and at least `75` strict rows.",
            "- Strict rows must stay positive after excluding one slate and must survive side, K-line, price, quality, timing, CLV, workload, Path B, provider/source, and market-agreement slices.",
            "- Non-strict FIRE rows must remain clearly worse before any downside-only cap can be considered.",
            "",
        ]
    )
    return "\n".join(lines)


def load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    report = render_report(summarize(load_rows(args.input)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Add post-grading runner flag**

In `scripts/run_post_grading_shadow_reports.py`, add parser args:

```python
    parser.add_argument(
        "--market-anchor-selector-audit-output",
        type=Path,
        default=ROOT / "analytics" / "output" / "market_anchor_selector_canary_audit.md",
    )
    parser.add_argument(
        "--skip-market-anchor-selector-audit",
        action="store_true",
        help="Skip only when selector metadata has not been deployed yet.",
    )
```

Import and invoke:

```python
from analytics.diagnostics import market_anchor_selector_canary_audit  # noqa: E402
```

After `builder.main(builder_args)`:

```python
    if not args.skip_market_anchor_selector_audit:
        market_anchor_selector_canary_audit.main([
            "--input",
            str(args.output_dir / "pitcher_k_outcome_dataset.jsonl"),
            "--output",
            str(args.market_anchor_selector_audit_output),
        ])
```

- [ ] **Step 5: Run green tests and generate audit**

Run:

```powershell
python -m pytest tests/test_market_anchor_selector_canary_audit.py -q
python scripts/run_post_grading_shadow_reports.py --skip-market-anchor-selector-audit
```

Expected: unit test passes; existing post-grading command still works while metadata has not soaked.

After selector metadata is present in at least one graded slate, run:

```powershell
python scripts/run_post_grading_shadow_reports.py
```

Expected: writes `analytics/output/market_anchor_selector_canary_audit.md`.

- [ ] **Step 6: Commit**

Run:

```powershell
git add analytics/diagnostics/market_anchor_selector_canary_audit.py tests/test_market_anchor_selector_canary_audit.py scripts/run_post_grading_shadow_reports.py
git commit -m "feat: audit market anchor selector canary"
```

## Task 6: Documentation, Gates, And Deployment Plan

**Files:**
- Modify: `docs/current-state.md`
- Modify: `docs/superpowers/plans/2026-06-09-active-gates-and-soak-synthesis.md`
- Modify: this plan

- [ ] **Step 1: Update model-lane docs**

In `docs/current-state.md`, add this plan to the model read order and model lane:

```markdown
- `docs/superpowers/plans/2026-06-16-market-anchored-v2-selector-shadow-canary.md`
  for the feature-flagged market-anchor selector shadow/canary path.
```

Add to the model lane stage:

```markdown
The market-anchored v2 selector plan is draft/implementation-ready for shadow
metadata only. Its default mode is `off`; `shadow` may be deployed only after
tests pass and Tyler approves the implementation push. `enforce_downside`
remains closed pending post-grading audit evidence and separate Tyler approval.
```

- [ ] **Step 2: Add Gate 12E to active gates synthesis**

In `docs/superpowers/plans/2026-06-09-active-gates-and-soak-synthesis.md`, add:

```markdown
### Gate 12E: Market-Anchored V2 Selector

**State:** Draft plan; production behavior closed.

The selector may add runtime-safe `market_anchor_selector` metadata in shadow
mode. It must not change verdicts unless Tyler separately approves
`MARKET_ANCHOR_SELECTOR_MODE=enforce_downside` after audit gates pass.

Promotion-review floors:

- At least `150` clean tracked rows with selector metadata.
- At least `75` market-anchor strict tracked rows.
- Strict rows positive after excluding one slate.
- Strict rows survive over/under, K-line, plus/minus price, quality, timing,
  CLV, workload, Path B, provider/source, market-agreement, and rolling-window
  slices.
- Non-strict FIRE rows remain materially worse than strict FIRE rows.
- No artifact, lock, notification, provider-source, or dashboard-source
  regression during shadow soak.

Still closed:

- automatic LEAN promotion
- any lambda, threshold, staking, provider, notification, lock, retention, or
  dashboard source-of-truth change
- `MARKET_ANCHOR_SELECTOR_MODE=enforce_downside`
```

- [ ] **Step 3: Verification commands**

Run:

```powershell
python -m pytest tests/test_market_anchor_selector.py tests/test_quality_gates.py tests/test_fetch_results.py tests/test_run_pipeline.py tests/test_pitcher_k_outcome_dataset.py tests/test_market_anchor_selector_canary_audit.py -q
python scripts/run_post_grading_shadow_reports.py --skip-market-anchor-selector-audit
git status --short --branch
```

Expected:

- All focused tests pass.
- Post-grading command still rebuilds existing reports.
- Working tree contains only intended docs/code/test changes before commit.

- [ ] **Step 4: Commit docs**

Run:

```powershell
git add docs/current-state.md docs/superpowers/plans/2026-06-09-active-gates-and-soak-synthesis.md docs/superpowers/plans/2026-06-16-market-anchored-v2-selector-shadow-canary.md
git commit -m "docs: plan market anchor selector shadow canary"
```

## Shadow Deployment Gate

Shadow deployment can be considered after Tasks 1-6 pass and Tyler approves the implementation push.

First safe runtime deployment:

```text
MARKET_ANCHOR_SELECTOR_MODE=shadow
```

Apply only to the seven Render pipeline cron services as one validated group. Do not change provider flags, model params, thresholds, staking, notification flags, lock flags, retention flags, or dashboard source-of-truth flags in the same deployment.

Post-deploy verification:

- The next fresh `today.json` contains side-level `market_anchor_selector.mode=shadow` on actionable rows.
- Displayed verdict counts match the same run with mode off when comparing the same input slate.
- `picks_history.json` open rows include `market_anchor_selector`.
- No new FIRE appears because of selector metadata.
- No PASS or LEAN is promoted.
- Gate C refresh carries `market_anchor_selector_mode`, labels, and applied flag.
- `analytics/output/market_anchor_selector_canary_audit.md` is generated after at least one graded selector slate.

## Promotion Review Gate

Do not request or perform `MARKET_ANCHOR_SELECTOR_MODE=enforce_downside` until all of these are true:

- At least `150` clean tracked rows have selector metadata.
- At least `75` strict rows are graded.
- Strict rows have positive ROI and non-negative CLV support.
- Strict performance remains positive after removing the single best slate.
- Non-strict displayed FIRE rows are materially worse than strict displayed FIRE rows.
- Strict rows survive side, K-line, plus/minus price, quality, timing, provider/source, workload, Path B, market agreement, and rolling-window slices.
- The canary behavior is explicitly limited to capping current FIRE rows that fail strict to `LEAN`.
- Tyler separately approves the environment change.

## Rollback

Set:

```text
MARKET_ANCHOR_SELECTOR_MODE=off
```

Expected rollback behavior:

- No `market_anchor_selector` metadata on new artifacts.
- Existing historical metadata remains in `picks_history` and Gate C for audit.
- Verdicts continue through quality, confidence-referee, and profit-rescue exactly as before.
