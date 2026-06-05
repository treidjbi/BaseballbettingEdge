# Market Favorite Confidence Referee Production Canary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a feature-flagged confidence-referee canary that can cap price-driven FIRE picks when the model is fading the market favorite, without changing projection math, staking rules, provider order, or dashboard source-of-truth behavior.

**Architecture:** Keep the referee as a pure runtime module that reads only fields already available before lock: side odds, K line, lambda, model edge, quality-gate output, and current market favorite from the two-sided price. Apply it after the existing quality gate so it can only preserve or lower the actionable verdict. Use `MARKET_FAVORITE_REFEREE_MODE=off|shadow|enforce`, defaulting to `off`, so production rollback is one environment-variable change.

**Tech Stack:** Python 3.11, pytest, existing `pipeline/build_features.py`, `pipeline/quality_gates.py`, `pipeline/fetch_results.py`, `pipeline/run_pipeline.py`, committed Gate C diagnostics, Render cron deployment helper.

---

## Operating Decision

This is the separate production implementation plan required by
`docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md` and
`docs/superpowers/plans/2026-06-03-market-favorite-confidence-referee-shadow-plan.md`.

Tyler approved drafting this plan on 2026-06-05 and explicitly waived the
remaining validation-row shortfall. The refreshed shadow report had `234 / 250`
validation tracked rows, so the waiver is `16` rows. The proposed referee label
itself had enough rows for the candidate-label sample check.

Current evidence from `analytics/output/market_favorite_confidence_referee_shadow_lab.md`:

- Clean window: `2026-04-28+`.
- Tracked rows: `771`.
- Validation tracked rows: `234`.
- `current_model_tracked`: `234` rows, `126-108`, `+3.39` flat units, `+1.4%` ROI.
- `model_agrees_market_favorite`: `115` rows, `72-43`, `+10.80`, `+9.4%`.
- `model_fades_market_favorite`: `113` rows, `51-62`, `-7.07`, `-6.3%`.
- `market_favorite_referee_candidate`: `114` rows, `72-42`, `+11.80`, `+10.4%`.
- `market_fade_warning_candidate`: `80` rows, `36-44`, `-5.33`, `-6.7%`.

Working hypothesis: the live model sometimes creates apparent value because a
plus-price/underdog side raises EV even when the projection edge is thin or the
model is fighting the market. The canary should make that kind of row harder to
become FIRE. It should not replace the model with the market favorite.

## Implementation Status

2026-06-05 phase-one implementation is code-ready behind the default-off
`MARKET_FAVORITE_REFEREE_MODE` flag. The implemented slice includes the pure
runtime referee module, post-quality-gate integration, SQLite/history/tracked
pick metadata persistence, and a compact canary audit. Local verification
passed the full Python suite and the Netlify function Node tests with the flag
unset, so production behavior remains unchanged until a separate deployment and
environment-mode decision.

Next live sequence: merge/deploy code with `MARKET_FAVORITE_REFEREE_MODE=off`,
then run at least one full slate in `shadow`, then review the canary audit
before any `enforce` decision. This status does not approve lambda, threshold,
staking, provider, notification, lock, retention, or dashboard-source changes.

## Non-Goals

- Do not change `calc_lambda`, `lambda_bias`, `formula_change_date`, SwStr
  scaling, calibration, `data/params.json`, or any projection challenger.
- Do not change global verdict thresholds in `calc_verdict`.
- Do not change staking rules or unit sizing.
- Do not change provider order, `OFFICIAL_MARKET_SOURCE`, BoltOdds/PropLine
  strict mode, notifications, locks, retention, or dashboard source-of-truth.
- Do not promote `market_favorite_only` as a betting model.
- Do not use results, PnL, CLV, actual Ks, or post-start movement as runtime
  label inputs.
- Do not raise a verdict above the current model + quality-gate output.

## Production Behavior

Add one environment variable:

```text
MARKET_FAVORITE_REFEREE_MODE=off|shadow|enforce
```

Modes:

- `off`: default. No production behavior or artifact shape changes except code
  availability.
- `shadow`: compute referee metadata and a would-have-capped verdict, but keep
  `verdict` and `actionable_verdict` unchanged.
- `enforce`: compute referee metadata and cap `verdict` / `actionable_verdict`
  only when the runtime-safe referee says to lower confidence.

Runtime-safe fields:

- `side`, derived from `ev_over` or `ev_under`.
- `best_over_odds`, `best_under_odds`, `k_line`, `lambda`.
- side-level `edge`, `ev`, `adj_ev`, and quality-gated verdict.
- record-level `quality_gate_level`, `input_quality_flags`, and `data_maturity`.
- pre-lock market favorite derived from current two-sided prices.

No hindsight fields are allowed.

Referee rules for the first canary:

1. Derive market favorite from two-sided current odds.
   - If over and under are tied, missing, or invalid, label `market_favorite_side="tie"` or `unknown` and do not cap.
2. Model agrees with market favorite.
   - Add metadata.
   - Do not raise or lower the verdict.
3. Model fades market favorite.
   - If the side is FIRE 2u, cap max verdict to FIRE 1u.
   - If the fade is price-driven, cap max verdict to LEAN.
4. Price-driven fade means at least one of:
   - selected side is plus money and model probability edge is below `0.04`;
   - selected side projection margin is below `0.75` Ks;
   - selected side is an under with line bucket `5.5`, `6.5`, or `7.5+`;
   - existing quality gate is `capped` or `blocked`.

This is intentionally conservative. It only reduces aggressiveness on rows that
historically looked like weak conversion buckets.

## File Map

- Create: `pipeline/confidence_referee.py`
  - Pure runtime-safe market favorite and verdict-cap logic.
- Create: `tests/test_confidence_referee.py`
  - Unit tests for favorite derivation, agreement, fades, price-driven caps,
    shadow/enforce behavior, and no-raise invariant.
- Modify: `pipeline/quality_gates.py`
  - Apply referee after existing quality gate.
  - Keep `raw_verdict` as the pre-quality raw model verdict.
  - Keep quality-gated verdict metadata.
  - In `shadow`, expose would-have-capped verdict without changing live verdict.
  - In `enforce`, lower final `verdict` / `actionable_verdict` when needed.
- Modify: `tests/test_quality_gates.py`
  - Verify default `off` mode is behavior-identical.
  - Verify `shadow` mode does not change final verdict.
  - Verify `enforce` mode caps model-fade FIRE rows.
- Modify: `pipeline/fetch_results.py`
  - Persist referee metadata to `picks_history.json` for audit.
- Modify: `pipeline/run_pipeline.py`
  - Include referee metadata in tracked-pick rows.
- Modify: `tests/test_run_pipeline.py`
  - Verify tracked-pick rows expose referee metadata when present.
- Modify: `docs/current-state.md`
  - Add this plan as the model lane production canary plan.
- Modify: `docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`
  - Record Tyler's 16-row waiver and this production-canary path.
- Modify: BBE Operations Brief automation memory
  - Daily brief should report referee mode, capped counts, and whether the
    canary changed FIRE/LEAN counts.

## Task 1: Add Pure Referee Tests

**Files:**
- Create: `tests/test_confidence_referee.py`
- Create: `pipeline/confidence_referee.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_confidence_referee.py`:

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))

from confidence_referee import (
    apply_referee_to_side,
    market_favorite_side,
    referee_mode,
)


def _record(**overrides):
    record = {
        "pitcher": "Example Starter",
        "k_line": 5.5,
        "lambda": 5.95,
        "best_over_odds": -125,
        "best_under_odds": 105,
        "quality_gate_level": "clean",
        "input_quality_flags": [],
    }
    record.update(overrides)
    return record


def _side(**overrides):
    side = {
        "raw_verdict": "FIRE 2u",
        "actionable_verdict": "FIRE 2u",
        "verdict": "FIRE 2u",
        "edge": 0.055,
        "ev": 0.18,
        "adj_ev": 0.18,
    }
    side.update(overrides)
    return side


def test_referee_mode_defaults_off(monkeypatch):
    monkeypatch.delenv("MARKET_FAVORITE_REFEREE_MODE", raising=False)
    assert referee_mode() == "off"


def test_market_favorite_side_uses_current_two_sided_price():
    assert market_favorite_side(-125, 105) == "over"
    assert market_favorite_side(115, -130) == "under"
    assert market_favorite_side(-110, -110) == "tie"
    assert market_favorite_side(None, -110) == "unknown"


def test_off_mode_leaves_side_unchanged():
    updated = apply_referee_to_side(_record(), "over", _side(), mode="off")

    assert updated["verdict"] == "FIRE 2u"
    assert "confidence_referee" not in updated


def test_shadow_mode_adds_metadata_but_does_not_change_verdict():
    updated = apply_referee_to_side(
        _record(lambda=5.1, best_over_odds=-130, best_under_odds=120),
        "under",
        _side(edge=0.025, adj_ev=0.11),
        mode="shadow",
    )

    assert updated["verdict"] == "FIRE 2u"
    assert updated["actionable_verdict"] == "FIRE 2u"
    assert updated["confidence_referee"]["mode"] == "shadow"
    assert updated["confidence_referee"]["relationship"] == "model_fades_favorite"
    assert updated["confidence_referee"]["would_cap_to"] == "LEAN"


def test_enforce_mode_caps_price_driven_market_fade_to_lean():
    updated = apply_referee_to_side(
        _record(lambda=5.1, best_over_odds=-130, best_under_odds=120),
        "under",
        _side(edge=0.025, adj_ev=0.11),
        mode="enforce",
    )

    assert updated["raw_verdict"] == "FIRE 2u"
    assert updated["verdict"] == "LEAN"
    assert updated["actionable_verdict"] == "LEAN"
    assert updated["confidence_referee"]["applied"] is True
    assert "price_driven_market_fade" in updated["confidence_referee"]["reasons"]


def test_enforce_mode_caps_non_price_driven_fade_fire_two_to_fire_one():
    updated = apply_referee_to_side(
        _record(lambda=7.0, best_over_odds=115, best_under_odds=-130),
        "over",
        _side(edge=0.08, adj_ev=0.22),
        mode="enforce",
    )

    assert updated["verdict"] == "FIRE 1u"
    assert updated["confidence_referee"]["would_cap_to"] == "FIRE 1u"


def test_referee_never_raises_verdict_on_market_agreement():
    updated = apply_referee_to_side(
        _record(lambda=6.4, best_over_odds=-130, best_under_odds=120),
        "over",
        _side(raw_verdict="LEAN", actionable_verdict="LEAN", verdict="LEAN", adj_ev=0.04),
        mode="enforce",
    )

    assert updated["verdict"] == "LEAN"
    assert updated["confidence_referee"]["relationship"] == "model_agrees_with_favorite"
    assert updated["confidence_referee"]["applied"] is False
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_confidence_referee.py -q
```

Expected: fail because `pipeline/confidence_referee.py` does not exist.

- [ ] **Step 3: Commit failing tests if using strict TDD**

```powershell
git add tests/test_confidence_referee.py
git commit -m "test: add confidence referee canary tests"
```

## Task 2: Implement Pure Referee Module

**Files:**
- Create: `pipeline/confidence_referee.py`
- Test: `tests/test_confidence_referee.py`

- [ ] **Step 1: Add the pure module**

Create `pipeline/confidence_referee.py`:

```python
"""Runtime-safe market favorite confidence referee.

This module is pure and feature-flagged. It must not change lambda, global
thresholds, staking, provider order, notifications, locks, or dashboard
source-of-truth behavior.
"""

from __future__ import annotations

import copy
import os
from typing import Any


VALID_MODES = {"off", "shadow", "enforce"}
VERDICT_ORDER = {
    "PASS": 0,
    "LEAN": 1,
    "FIRE 1u": 2,
    "FIRE 2u": 3,
}
ORDER_VERDICT = {value: key for key, value in VERDICT_ORDER.items()}


def referee_mode() -> str:
    value = os.getenv("MARKET_FAVORITE_REFEREE_MODE", "off").strip().lower()
    return value if value in VALID_MODES else "off"


def american_to_implied(odds: Any) -> float | None:
    if isinstance(odds, bool):
        return None
    try:
        value = int(odds)
    except (TypeError, ValueError):
        return None
    if value == 0:
        return None
    if value > 0:
        return 100.0 / (value + 100.0)
    return abs(value) / (abs(value) + 100.0)


def market_favorite_side(over_odds: Any, under_odds: Any) -> str:
    over_prob = american_to_implied(over_odds)
    under_prob = american_to_implied(under_odds)
    if over_prob is None or under_prob is None:
        return "unknown"
    if abs(over_prob - under_prob) < 0.0001:
        return "tie"
    return "over" if over_prob > under_prob else "under"


def cap_verdict(verdict: str, max_verdict: str) -> str:
    current_order = VERDICT_ORDER.get(verdict, VERDICT_ORDER["PASS"])
    max_order = VERDICT_ORDER.get(max_verdict, VERDICT_ORDER["PASS"])
    return ORDER_VERDICT[min(current_order, max_order)]


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def _projection_margin(record: dict[str, Any], side: str) -> float | None:
    lam = _to_float(record.get("lambda"))
    k_line = _to_float(record.get("k_line"))
    if lam is None or k_line is None:
        return None
    if side == "over":
        return round(lam - k_line, 3)
    if side == "under":
        return round(k_line - lam, 3)
    return None


def _price_sign(odds: Any) -> str:
    value = _to_float(odds)
    if value is None:
        return "unknown"
    if value > 0:
        return "plus"
    if value < 0:
        return "minus"
    return "unknown"


def _line_bucket(k_line: Any) -> str:
    value = _to_float(k_line)
    if value is None:
        return "unknown"
    if value <= 3.5:
        return "2.5-3.5"
    if value >= 7.5:
        return "7.5+"
    return f"{value:.1f}"


def _is_price_driven_fade(
    record: dict[str, Any],
    side: str,
    side_data: dict[str, Any],
    selected_odds: Any,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    edge = _to_float(side_data.get("edge"))
    margin = _projection_margin(record, side)

    if _price_sign(selected_odds) == "plus" and (edge is None or edge < 0.04):
        reasons.append("plus_price_thin_probability_edge")
    if margin is None or margin < 0.75:
        reasons.append("thin_projection_margin")
    if side == "under" and _line_bucket(record.get("k_line")) in {"5.5", "6.5", "7.5+"}:
        reasons.append("under_high_line_bucket")
    if record.get("quality_gate_level") in {"capped", "blocked"}:
        reasons.append("quality_gate_caution")

    return bool(reasons), reasons


def apply_referee_to_side(
    record: dict[str, Any],
    side: str,
    side_data: dict[str, Any],
    *,
    mode: str | None = None,
) -> dict[str, Any]:
    active_mode = mode or referee_mode()
    if active_mode not in VALID_MODES:
        active_mode = "off"
    if active_mode == "off":
        return copy.deepcopy(side_data)

    updated = copy.deepcopy(side_data)
    side = side.lower()
    selected_odds = record.get(f"best_{side}_odds")
    favorite = market_favorite_side(record.get("best_over_odds"), record.get("best_under_odds"))
    relationship = (
        "model_agrees_with_favorite"
        if side == favorite
        else "model_fades_favorite"
        if favorite in {"over", "under"}
        else "unknown"
    )

    current_verdict = updated.get("actionable_verdict") or updated.get("verdict") or "PASS"
    would_cap_to = current_verdict
    applied = False
    reasons: list[str] = []

    if relationship == "model_fades_favorite":
        price_driven, price_reasons = _is_price_driven_fade(record, side, updated, selected_odds)
        if price_driven:
            would_cap_to = cap_verdict(current_verdict, "LEAN")
            reasons.append("price_driven_market_fade")
            reasons.extend(price_reasons)
        elif current_verdict == "FIRE 2u":
            would_cap_to = "FIRE 1u"
            reasons.append("market_fade_caps_fire_two")

    if VERDICT_ORDER.get(would_cap_to, 0) < VERDICT_ORDER.get(current_verdict, 0):
        applied = True

    updated["confidence_referee"] = {
        "mode": active_mode,
        "relationship": relationship,
        "market_favorite_side": favorite,
        "selected_side": side,
        "selected_odds": selected_odds,
        "price_sign": _price_sign(selected_odds),
        "projection_margin_ks": _projection_margin(record, side),
        "probability_edge": updated.get("edge"),
        "would_cap_to": would_cap_to,
        "applied": applied and active_mode == "enforce",
        "reasons": reasons,
    }

    if active_mode == "enforce" and applied:
        updated["actionable_verdict"] = would_cap_to
        updated["verdict"] = would_cap_to

    return updated
```

- [ ] **Step 2: Run focused tests**

Run:

```powershell
python -m pytest tests/test_confidence_referee.py -q
```

Expected: pass.

- [ ] **Step 3: Commit**

```powershell
git add pipeline/confidence_referee.py tests/test_confidence_referee.py
git commit -m "feat: add market favorite confidence referee"
```

## Task 3: Integrate After Existing Quality Gates

**Files:**
- Modify: `pipeline/quality_gates.py`
- Modify: `tests/test_quality_gates.py`

- [ ] **Step 1: Write integration tests**

Append to `tests/test_quality_gates.py`:

```python
def test_confidence_referee_default_off_is_behavior_identical(monkeypatch):
    monkeypatch.delenv("MARKET_FAVORITE_REFEREE_MODE", raising=False)
    record = clean_fire_record()
    record["lambda"] = 5.1
    record["best_over_odds"] = -130
    record["best_under_odds"] = 120
    record["ev_under"] = {"verdict": "FIRE 2u", "adj_ev": 0.18, "ev": 0.19, "edge": 0.025}

    gated = apply_quality_to_record(record)

    assert gated["ev_under"]["verdict"] == "FIRE 2u"
    assert "confidence_referee" not in gated["ev_under"]


def test_confidence_referee_shadow_does_not_change_verdict(monkeypatch):
    monkeypatch.setenv("MARKET_FAVORITE_REFEREE_MODE", "shadow")
    record = clean_fire_record()
    record["lambda"] = 5.1
    record["best_over_odds"] = -130
    record["best_under_odds"] = 120
    record["ev_under"] = {"verdict": "FIRE 2u", "adj_ev": 0.18, "ev": 0.19, "edge": 0.025}

    gated = apply_quality_to_record(record)

    assert gated["ev_under"]["verdict"] == "FIRE 2u"
    assert gated["ev_under"]["confidence_referee"]["mode"] == "shadow"
    assert gated["ev_under"]["confidence_referee"]["would_cap_to"] == "LEAN"


def test_confidence_referee_enforce_caps_after_quality_gate(monkeypatch):
    monkeypatch.setenv("MARKET_FAVORITE_REFEREE_MODE", "enforce")
    record = clean_fire_record()
    record["lambda"] = 5.1
    record["best_over_odds"] = -130
    record["best_under_odds"] = 120
    record["ev_under"] = {"verdict": "FIRE 2u", "adj_ev": 0.18, "ev": 0.19, "edge": 0.025}

    gated = apply_quality_to_record(record)

    assert gated["ev_under"]["raw_verdict"] == "FIRE 2u"
    assert gated["ev_under"]["verdict"] == "LEAN"
    assert gated["ev_under"]["actionable_verdict"] == "LEAN"
    assert gated["ev_under"]["confidence_referee"]["applied"] is True
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_quality_gates.py -q
```

Expected: the two referee tests fail because `quality_gates.py` has not yet
called the referee.

- [ ] **Step 3: Wire referee into `quality_gates.py`**

Modify imports:

```python
from confidence_referee import apply_referee_to_side
```

Change `_apply_quality_to_side` to accept the record and side key:

```python
def _apply_quality_to_side(record: dict, side_key: str, side: dict, quality: dict) -> dict:
    updated = copy.deepcopy(side)
    raw_verdict = updated.get("raw_verdict", updated.get("verdict", "PASS"))
    raw_adj_ev = updated.get("raw_adj_ev", updated.get("adj_ev", 0.0))
    actionable_verdict = cap_verdict(raw_verdict, quality["max_actionable_verdict"])

    updated["raw_verdict"] = raw_verdict
    updated["raw_adj_ev"] = raw_adj_ev
    updated["quality_actionable_verdict"] = actionable_verdict
    updated["actionable_verdict"] = actionable_verdict
    updated["verdict"] = actionable_verdict
    updated["quality_gate_level"] = quality["quality_gate_level"]
    updated["quality_gate_reasons"] = list(quality["quality_gate_reasons"])
    if quality["quality_gate_level"] == "blocked":
        updated["adj_ev"] = 0.0

    side_name = "over" if side_key == "ev_over" else "under"
    return apply_referee_to_side(record, side_name, updated)
```

Change `apply_quality_to_record` loop:

```python
for side_key in ("ev_over", "ev_under"):
    side = updated.get(side_key)
    if isinstance(side, dict):
        updated[side_key] = _apply_quality_to_side(updated, side_key, side, quality)
```

- [ ] **Step 4: Run focused tests**

Run:

```powershell
python -m pytest tests/test_confidence_referee.py tests/test_quality_gates.py -q
```

Expected: pass.

- [ ] **Step 5: Commit**

```powershell
git add pipeline/quality_gates.py tests/test_quality_gates.py
git commit -m "feat: apply confidence referee after quality gates"
```

## Task 4: Persist Referee Metadata For Audit

**Files:**
- Modify: `pipeline/fetch_results.py`
- Modify: `pipeline/run_pipeline.py`
- Modify: `tests/test_run_pipeline.py`

- [ ] **Step 1: Add persistence tests**

Append to `tests/test_run_pipeline.py`:

```python
def test_tracked_pick_row_exposes_confidence_referee_metadata():
    import run_pipeline

    row = run_pipeline._tracked_pick_row(
        {
            "date": "2026-06-05",
            "pitcher": "Example Starter",
            "team": "ARI",
            "opp_team": "LAD",
            "side": "under",
            "verdict": "LEAN",
            "raw_verdict": "FIRE 2u",
            "actionable_verdict": "LEAN",
            "confidence_referee": {
                "mode": "enforce",
                "relationship": "model_fades_favorite",
                "would_cap_to": "LEAN",
                "applied": True,
            },
        }
    )

    assert row["confidence_referee"]["mode"] == "enforce"
    assert row["confidence_referee"]["applied"] is True
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_run_pipeline.py::test_tracked_pick_row_exposes_confidence_referee_metadata -q
```

Expected: fail because `_tracked_pick_row` does not expose the metadata.

- [ ] **Step 3: Add SQLite/history column**

In `pipeline/fetch_results.py`, add this column to the `CREATE TABLE` statement:

```sql
confidence_referee_json TEXT
```

Add it to the migration column list:

```python
("confidence_referee_json", "TEXT"),
```

Inside `seed_picks`, capture side-level metadata:

```python
confidence_referee_json = _json_or_none(ev_data.get("confidence_referee"))
```

Add `confidence_referee_json` to the insert and unlocked-update statements.

Add `"confidence_referee_json"` to the export column list and decode it after
building pick dictionaries:

```python
pick["confidence_referee"] = _json_load_or_none(pick.pop("confidence_referee_json", None))
```

- [ ] **Step 4: Expose tracked-pick metadata**

In `pipeline/run_pipeline.py`, add this key to `_tracked_pick_row`:

```python
"confidence_referee": pick.get("confidence_referee"),
```

- [ ] **Step 5: Run focused tests**

Run:

```powershell
python -m pytest tests/test_run_pipeline.py::test_tracked_pick_row_exposes_confidence_referee_metadata -q
```

Expected: pass.

- [ ] **Step 6: Commit**

```powershell
git add pipeline/fetch_results.py pipeline/run_pipeline.py tests/test_run_pipeline.py
git commit -m "feat: persist confidence referee audit metadata"
```

## Task 5: Add Canary Report

**Files:**
- Create: `analytics/diagnostics/confidence_referee_canary_audit.py`
- Create: `tests/test_confidence_referee_canary_audit.py`
- Write: `analytics/output/confidence_referee_canary_audit.md`

- [ ] **Step 1: Write report tests**

Create `tests/test_confidence_referee_canary_audit.py`:

```python
from analytics.diagnostics import confidence_referee_canary_audit as audit


def test_summarize_counts_referee_modes_and_caps():
    rows = [
        {
            "verdict": "LEAN",
            "raw_verdict": "FIRE 2u",
            "confidence_referee": {"mode": "enforce", "applied": True},
        },
        {
            "verdict": "FIRE 1u",
            "raw_verdict": "FIRE 1u",
            "confidence_referee": {"mode": "enforce", "applied": False},
        },
    ]

    summary = audit.summarize(rows)

    assert summary["rows"] == 2
    assert summary["applied_caps"] == 1
    assert summary["mode_counts"] == {"enforce": 2}
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_confidence_referee_canary_audit.py -q
```

Expected: fail because the module does not exist.

- [ ] **Step 3: Implement minimal audit**

Create `analytics/diagnostics/confidence_referee_canary_audit.py`:

```python
"""Audit confidence-referee production canary effects."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT / "data" / "picks_history.json"
OUTPUT_PATH = ROOT / "analytics" / "output" / "confidence_referee_canary_audit.md"


def load_history(path: Path = HISTORY_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    mode_counts: Counter[str] = Counter()
    applied_caps = 0
    for row in rows:
        meta = row.get("confidence_referee") or {}
        if not isinstance(meta, dict):
            continue
        mode_counts[str(meta.get("mode") or "unknown")] += 1
        if meta.get("applied") is True:
            applied_caps += 1
    return {
        "rows": len(rows),
        "applied_caps": applied_caps,
        "mode_counts": dict(sorted(mode_counts.items())),
    }


def build_report(rows: list[dict[str, Any]]) -> str:
    summary = summarize(rows)
    return "\n".join(
        [
            "# Confidence Referee Canary Audit",
            "",
            "This report audits the feature-flagged market-favorite confidence referee.",
            "",
            f"- Rows: `{summary['rows']}`",
            f"- Applied caps: `{summary['applied_caps']}`",
            f"- Mode counts: `{summary['mode_counts']}`",
            "",
        ]
    )


def main() -> None:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(build_report(load_history()), encoding="utf-8")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run report and tests**

Run:

```powershell
python -m pytest tests/test_confidence_referee_canary_audit.py -q
python analytics/diagnostics/confidence_referee_canary_audit.py
```

Expected: tests pass and `analytics/output/confidence_referee_canary_audit.md`
is written.

- [ ] **Step 5: Commit**

```powershell
git add analytics/diagnostics/confidence_referee_canary_audit.py tests/test_confidence_referee_canary_audit.py
git add -f analytics/output/confidence_referee_canary_audit.md
git commit -m "feat: add confidence referee canary audit"
```

## Task 6: Production Verification And Canary Rollout

**Files:**
- Modify: `docs/current-state.md`
- Modify: BBE Operations Brief automation memory

- [ ] **Step 1: Verify default-off behavior locally**

Run:

```powershell
Remove-Item Env:\MARKET_FAVORITE_REFEREE_MODE -ErrorAction SilentlyContinue
python -m pytest tests/test_confidence_referee.py tests/test_quality_gates.py tests/test_run_pipeline.py -q
python -m pytest tests/ -q
```

Expected: all tests pass. Default-off runs must keep verdict behavior identical.

- [ ] **Step 2: Run one local shadow smoke test**

Run:

```powershell
$env:MARKET_FAVORITE_REFEREE_MODE='shadow'
python pipeline/run_pipeline.py 2026-06-05 --run-type full
Remove-Item Env:\MARKET_FAVORITE_REFEREE_MODE -ErrorAction SilentlyContinue
```

Expected:

- `today.json` contains `confidence_referee` metadata on non-PASS side rows.
- FIRE/LEAN/PASS counts are unchanged versus default-off for the same inputs.
- No lock, grading, provider, notification, or dashboard serving behavior changes.

- [ ] **Step 3: Run one local enforce smoke test**

Run:

```powershell
$env:MARKET_FAVORITE_REFEREE_MODE='enforce'
python pipeline/run_pipeline.py 2026-06-05 --run-type full
Remove-Item Env:\MARKET_FAVORITE_REFEREE_MODE -ErrorAction SilentlyContinue
```

Expected:

- Only model-fade rows are capped.
- No verdict is raised.
- `raw_verdict` preserves the original model verdict.
- `confidence_referee.applied=true` appears only on capped rows.

- [ ] **Step 4: Inspect local artifacts before committing**

If local smoke tests changed generated production artifacts, do not commit them
unless Tyler explicitly approves an artifact refresh as part of the
implementation. Inspect the changed paths before staging:

```powershell
git status --short
git diff -- dashboard/data/processed/today.json dashboard/data/processed/steam.json data/picks_history.json
```

Expected: generated local smoke artifacts are understood and are not
accidentally staged or committed.

- [ ] **Step 5: Commit implementation docs**

```powershell
git add docs/current-state.md
git commit -m "docs: record confidence referee canary rollout"
```

- [ ] **Step 6: Push and deploy code with mode off**

```powershell
git push origin main
python scripts/deploy_render_pipeline_crons.py
```

Expected: dry run finds all seven production pipeline cron services and creates
no deploys.

After Tyler approves deploy:

```powershell
python scripts/deploy_render_pipeline_crons.py --execute
```

Expected: Render preview, grading, full, refresh, and lock cron services deploy
the code with `MARKET_FAVORITE_REFEREE_MODE=off`.

- [ ] **Step 7: Enable shadow mode first**

Set Render pipeline cron env:

```text
MARKET_FAVORITE_REFEREE_MODE=shadow
```

Redeploy with:

```powershell
python scripts/deploy_render_pipeline_crons.py --execute
```

Expected:

- Next preview/full/refresh publishes fresh artifacts.
- Referee metadata appears.
- FIRE/LEAN/PASS counts do not change.
- `confidence_referee_canary_audit.md` shows zero applied live caps.

- [ ] **Step 8: Enable enforce canary after shadow verification**

Set Render pipeline cron env:

```text
MARKET_FAVORITE_REFEREE_MODE=enforce
```

Redeploy with:

```powershell
python scripts/deploy_render_pipeline_crons.py --execute
```

Expected:

- Only price-driven market-fade rows are capped.
- FIRE counts may fall; LEAN counts may rise.
- No projection lambda, threshold constants, staking, provider source, lock
  consumer, notification sender, or dashboard data-source flags change.

## Rollback

Immediate rollback:

```text
MARKET_FAVORITE_REFEREE_MODE=off
```

Then redeploy Render pipeline crons:

```powershell
python scripts/deploy_render_pipeline_crons.py --execute
```

Code rollback, only if needed:

```powershell
git revert <implementation_commit_sha>
git push origin main
python scripts/deploy_render_pipeline_crons.py --execute
```

Rollback success criteria:

- New artifacts stop applying confidence-referee caps.
- Existing locked picks remain locked at their captured verdicts.
- `raw_verdict` and `confidence_referee` metadata preserve audit history.

## Briefing Requirements

Every BBE Operations Brief after implementation should report:

- current `MARKET_FAVORITE_REFEREE_MODE`;
- count of rows with `confidence_referee.applied=true`;
- count of FIRE 2u -> FIRE 1u caps;
- count of FIRE -> LEAN caps;
- whether any capped row later won/lost after grading;
- whether the canary improved or hurt FIRE ROI versus the preserved raw verdict;
- confirmation that lambda, thresholds, staking, provider order, notifications,
  locks, retention, and dashboard source-of-truth remained unchanged.
