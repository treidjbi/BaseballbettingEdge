# Market Shrink Projection Production Canary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a feature-flagged market-shrink projection canary that can test `market_shrink_25` in production artifacts without changing thresholds, staking, provider order, notifications, locks, retention, or dashboard source-of-truth.

**Architecture:** Keep the challenger in a small pure runtime module and call it inside `pipeline/build_features.py` after the current model lambda and existing line-gap cap are computed, but before side probabilities and EV are calculated. Default behavior is `off`; `shadow` writes metadata and a would-have lambda while preserving current live lambda; `enforce` may replace the side-probability lambda with the selected market-shrink lambda. Every row preserves the current model lambda for audit and rollback comparison.

**Tech Stack:** Python 3.11, pytest, existing single-file Python pipeline, Render cron env flags, Supabase/Netlify artifact verification, Gate C/Gate F diagnostics.

## Global Constraints

- This plan does not approve a live lambda change by itself; Tyler must separately approve `MARKET_SHRINK_PROJECTION_MODE=shadow` or `enforce`.
- The first production candidate is `market_shrink_25`; `market_shrink_15` and `market_shrink_35` may be computed as shadow comparison metadata only.
- Do not change `formula_change_date`, global verdict thresholds, staking, calibration rules, provider order, notification behavior, lock behavior, retention, or dashboard source-of-truth.
- Do not use actual Ks, result, PnL, CLV, close price, post-start movement, or reconstructed opportunity as runtime inputs.
- TheRundown remains the official artifact source. PropLine remains fallback/live-movement sidecar. BoltOdds remains retired.
- Rollback must be one Render env var change back to `MARKET_SHRINK_PROJECTION_MODE=off`, followed by normal Render cron redeploy.

---

## Evidence Trigger

The 2026-06-22 refreshed Gate F report says the market-shrink family hit the production-plan gate:

| Candidate | Status | Rows | MAE Delta | RMSE Delta | Side Accuracy Delta | Rolling Windows | Bad Slices | FIRE 2u Degradation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `market_shrink_15` | `promotion_plan_candidate` | 219 | -0.030 | -0.042 | +0.000 | 2 | 0 | no |
| `market_shrink_25` | `promotion_plan_candidate` | 219 | -0.048 | -0.066 | +0.000 | 2 | 0 | no |
| `market_shrink_35` | `promotion_plan_candidate` | 219 | -0.063 | -0.089 | +0.000 | 2 | 0 | no |

Blocked candidates remain blocked:

- `high_line_temper`: `blocked_mae_lift_too_small`
- `leash_cap`: `blocked_mae_lift_too_small`
- `handedness_bucket_adjust`: `blocked_hindsight_only`

Decision: draft a production-canary implementation plan only for the runtime-safe market-shrink family. Start with the balanced `market_shrink_25` candidate even though `market_shrink_35` has the largest aggregate MAE lift; this keeps the first live canary from over-collapsing the model into the market line.

## File Map

- Create: `pipeline/projection_challenger.py`
  - Pure env parsing and market-shrink projection helper.
- Create: `tests/test_projection_challenger.py`
  - Unit tests for mode parsing, candidate parsing, shrink math, invalid config fail-closed behavior, and shadow/enforce selected-lambda behavior.
- Modify: `pipeline/build_features.py`
  - Apply the challenger after current lambda and line-gap cap, before win-probability and EV calculation.
  - Preserve `model_lambda` and add top-level plus side-level `projection_challenger` metadata.
- Modify: `tests/test_build_features.py`
  - Verify default `off` is behavior-identical.
  - Verify `shadow` exposes would-have lambda without changing `lambda`, EV, or verdict.
  - Verify `enforce` changes `lambda` toward the K line and recalculates side EV from the shrunk lambda.
- Modify: `pipeline/fetch_results.py`
  - Persist projection metadata through SQLite and `picks_history.json`.
- Modify: `pipeline/run_pipeline.py`
  - Preserve projection metadata in tracked picks and archive reconciliation.
- Modify: `tests/test_fetch_results.py`
  - Verify projection metadata survives seed, update, export, and stale-PASS repair paths.
- Modify: `tests/test_run_pipeline.py`
  - Verify tracked-pick rows expose projection metadata and current-model lambda when present.
- Modify: `scripts/run_post_grading_shadow_reports.py`
  - No production behavior change; only verify existing Gate F report still runs after metadata is present.
- Modify: `docs/current-state.md`
  - Add this plan to the model lane and state that the only open production-plan candidate is market shrink.
- Modify: `docs/superpowers/plans/2026-06-03-gate-f-projection-challenger-shadow-plan.md`
  - Record the 2026-06-22 Gate F decision update.

## Runtime Contract

New environment variables:

```text
MARKET_SHRINK_PROJECTION_MODE=off|shadow|enforce
MARKET_SHRINK_PROJECTION_CANDIDATE=market_shrink_15|market_shrink_25|market_shrink_35
```

Defaults:

```text
MARKET_SHRINK_PROJECTION_MODE=off
MARKET_SHRINK_PROJECTION_CANDIDATE=market_shrink_25
```

Metadata shape:

```json
{
  "mode": "shadow",
  "candidate": "market_shrink_25",
  "applied": false,
  "current_lambda": 6.4,
  "would_lambda": 6.175,
  "selected_lambda": 6.4,
  "k_line": 5.5,
  "weight": 0.25,
  "delta": -0.225,
  "reason": "shadow_only"
}
```

Mode behavior:

- `off`: no behavior change; optional metadata may be absent.
- `shadow`: compute metadata, keep current live `lambda`, EV, and verdict unchanged.
- `enforce`: replace the probability lambda with `selected_lambda = would_lambda`, then recompute over/under probabilities, edge, EV, adjusted EV, quality gate, confidence referee, and profit rescue from that selected lambda.

The live artifact must preserve:

- `raw_lambda`: pre-bias raw model lambda, existing meaning.
- `model_lambda`: current live model lambda after bias and line-gap cap, before market shrink.
- `lambda`: selected lambda used for win probabilities. In `off` and `shadow`, this equals `model_lambda`; in `enforce`, this equals `selected_lambda`.
- `projection_challenger`: metadata object at pitcher row and side row level.

## Task 1: Add Pure Projection Challenger Module

**Files:**
- Create: `pipeline/projection_challenger.py`
- Create: `tests/test_projection_challenger.py`

**Interfaces:**
- Produces: `projection_challenger_mode(value: str | None = None) -> str`
- Produces: `projection_challenger_candidate(value: str | None = None) -> str`
- Produces: `market_shrink_projection(current_lambda: float, k_line: float, candidate: str) -> tuple[float, float]`
- Produces: `apply_projection_challenger(current_lambda: float, k_line: float, mode: str | None = None, candidate: str | None = None) -> dict`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_projection_challenger.py`:

```python
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))

from projection_challenger import (
    apply_projection_challenger,
    market_shrink_projection,
    projection_challenger_candidate,
    projection_challenger_mode,
)


def test_projection_challenger_mode_defaults_off(monkeypatch):
    monkeypatch.delenv("MARKET_SHRINK_PROJECTION_MODE", raising=False)

    assert projection_challenger_mode() == "off"


def test_projection_challenger_mode_accepts_shadow_and_enforce(monkeypatch):
    monkeypatch.setenv("MARKET_SHRINK_PROJECTION_MODE", "shadow")
    assert projection_challenger_mode() == "shadow"

    monkeypatch.setenv("MARKET_SHRINK_PROJECTION_MODE", "enforce")
    assert projection_challenger_mode() == "enforce"


def test_projection_challenger_mode_invalid_fails_closed(monkeypatch):
    monkeypatch.setenv("MARKET_SHRINK_PROJECTION_MODE", "yes")

    assert projection_challenger_mode() == "off"


def test_projection_challenger_candidate_defaults_market_shrink_25(monkeypatch):
    monkeypatch.delenv("MARKET_SHRINK_PROJECTION_CANDIDATE", raising=False)

    assert projection_challenger_candidate() == "market_shrink_25"


def test_market_shrink_projection_moves_toward_line():
    projected, weight = market_shrink_projection(7.0, 5.0, "market_shrink_25")

    assert projected == 6.5
    assert weight == 0.25


def test_apply_projection_challenger_shadow_preserves_selected_lambda():
    result = apply_projection_challenger(7.0, 5.0, mode="shadow", candidate="market_shrink_25")

    assert result["applied"] is False
    assert result["current_lambda"] == 7.0
    assert result["would_lambda"] == 6.5
    assert result["selected_lambda"] == 7.0
    assert result["reason"] == "shadow_only"


def test_apply_projection_challenger_enforce_selects_shrunk_lambda():
    result = apply_projection_challenger(7.0, 5.0, mode="enforce", candidate="market_shrink_25")

    assert result["applied"] is True
    assert result["selected_lambda"] == 6.5
    assert result["reason"] == "enforced"


def test_apply_projection_challenger_invalid_candidate_fails_closed():
    result = apply_projection_challenger(7.0, 5.0, mode="enforce", candidate="bad")

    assert result["applied"] is False
    assert result["selected_lambda"] == 7.0
    assert result["reason"] == "invalid_candidate"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_projection_challenger.py -q
```

Expected: fail because `projection_challenger` does not exist.

- [ ] **Step 3: Add the pure module**

Create `pipeline/projection_challenger.py`:

```python
"""Feature-flagged market-shrink projection challenger.

Runtime-safe: uses only current model lambda and the posted K line.
"""

from __future__ import annotations

import os
from typing import Any


VALID_MODES = {"off", "shadow", "enforce"}
MARKET_SHRINK_WEIGHTS = {
    "market_shrink_15": 0.15,
    "market_shrink_25": 0.25,
    "market_shrink_35": 0.35,
}
DEFAULT_CANDIDATE = "market_shrink_25"


def projection_challenger_mode(value: str | None = None) -> str:
    raw = (value if value is not None else os.getenv("MARKET_SHRINK_PROJECTION_MODE", "off")).strip().lower()
    return raw if raw in VALID_MODES else "off"


def projection_challenger_candidate(value: str | None = None) -> str:
    raw = (
        value
        if value is not None
        else os.getenv("MARKET_SHRINK_PROJECTION_CANDIDATE", DEFAULT_CANDIDATE)
    ).strip().lower()
    return raw if raw in MARKET_SHRINK_WEIGHTS else DEFAULT_CANDIDATE


def market_shrink_projection(current_lambda: float, k_line: float, candidate: str) -> tuple[float, float]:
    weight = MARKET_SHRINK_WEIGHTS[candidate]
    projected = current_lambda + ((k_line - current_lambda) * weight)
    return round(projected, 3), weight


def apply_projection_challenger(
    current_lambda: float,
    k_line: float,
    *,
    mode: str | None = None,
    candidate: str | None = None,
) -> dict[str, Any]:
    resolved_mode = projection_challenger_mode(mode)
    requested_candidate = (
        candidate
        if candidate is not None
        else os.getenv("MARKET_SHRINK_PROJECTION_CANDIDATE", DEFAULT_CANDIDATE)
    ).strip().lower()
    if requested_candidate not in MARKET_SHRINK_WEIGHTS:
        return {
            "mode": resolved_mode,
            "candidate": requested_candidate,
            "applied": False,
            "current_lambda": round(current_lambda, 3),
            "would_lambda": round(current_lambda, 3),
            "selected_lambda": round(current_lambda, 3),
            "k_line": k_line,
            "weight": None,
            "delta": 0.0,
            "reason": "invalid_candidate",
        }

    would_lambda, weight = market_shrink_projection(current_lambda, k_line, requested_candidate)
    selected_lambda = would_lambda if resolved_mode == "enforce" else round(current_lambda, 3)
    return {
        "mode": resolved_mode,
        "candidate": requested_candidate,
        "applied": resolved_mode == "enforce",
        "current_lambda": round(current_lambda, 3),
        "would_lambda": would_lambda,
        "selected_lambda": selected_lambda,
        "k_line": k_line,
        "weight": weight,
        "delta": round(would_lambda - current_lambda, 3),
        "reason": "enforced" if resolved_mode == "enforce" else "shadow_only" if resolved_mode == "shadow" else "off",
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```powershell
python -m pytest tests/test_projection_challenger.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add pipeline/projection_challenger.py tests/test_projection_challenger.py
git commit -m "feat: add market shrink projection challenger"
```

## Task 2: Wire Shadow Metadata Into Pitcher Records

**Files:**
- Modify: `pipeline/build_features.py`
- Modify: `tests/test_build_features.py`

**Interfaces:**
- Consumes: `apply_projection_challenger(...)` from Task 1.
- Produces: pitcher-level `model_lambda` and `projection_challenger` fields.
- Produces: side-level `projection_challenger` fields in `ev_over` and `ev_under`.

- [ ] **Step 1: Add failing tests**

Append to `tests/test_build_features.py`:

```python
def test_market_shrink_shadow_preserves_lambda_and_adds_metadata(monkeypatch):
    from build_features import build_pitcher_record

    monkeypatch.setenv("MARKET_SHRINK_PROJECTION_MODE", "shadow")
    monkeypatch.setenv("MARKET_SHRINK_PROJECTION_CANDIDATE", "market_shrink_25")

    rec = build_pitcher_record(SAMPLE_ODDS, SAMPLE_STATS, 0.0)

    assert rec["lambda"] == rec["model_lambda"]
    assert rec["projection_challenger"]["mode"] == "shadow"
    assert rec["projection_challenger"]["candidate"] == "market_shrink_25"
    assert rec["projection_challenger"]["applied"] is False
    assert rec["projection_challenger"]["would_lambda"] != rec["lambda"]
    assert rec["ev_over"]["projection_challenger"]["mode"] == "shadow"
    assert rec["ev_under"]["projection_challenger"]["mode"] == "shadow"


def test_market_shrink_enforce_replaces_selected_lambda(monkeypatch):
    from build_features import build_pitcher_record

    monkeypatch.setenv("MARKET_SHRINK_PROJECTION_MODE", "enforce")
    monkeypatch.setenv("MARKET_SHRINK_PROJECTION_CANDIDATE", "market_shrink_25")

    rec = build_pitcher_record(SAMPLE_ODDS, SAMPLE_STATS, 0.0)

    assert rec["projection_challenger"]["applied"] is True
    assert rec["lambda"] == round(rec["projection_challenger"]["selected_lambda"], 2)
    assert rec["lambda"] != rec["model_lambda"]
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_build_features.py::test_market_shrink_shadow_preserves_lambda_and_adds_metadata tests/test_build_features.py::test_market_shrink_enforce_replaces_selected_lambda -q
```

Expected: fail because metadata and `model_lambda` are not present.

- [ ] **Step 3: Import the challenger**

At the top of `pipeline/build_features.py`, add:

```python
from projection_challenger import apply_projection_challenger, projection_challenger_mode
```

- [ ] **Step 4: Refactor the current lambda cap into a named baseline**

Inside `build_pitcher_record`, replace the current line-gap cap block with:

```python
    MAX_LAMBDA_LINE_GAP = 2.5
    model_lam = min(applied_lam, k_line + MAX_LAMBDA_LINE_GAP)
    model_lam = max(model_lam, k_line - MAX_LAMBDA_LINE_GAP)

    projection_challenger = None
    selected_lam = model_lam
    if projection_challenger_mode() != "off":
        projection_challenger = apply_projection_challenger(model_lam, k_line)
        selected_lam = projection_challenger["selected_lambda"]

    applied_lam = selected_lam
```

- [ ] **Step 5: Add metadata to the returned pitcher row**

In the returned dict, add:

```python
        "model_lambda":        round(model_lam, 2),
        "projection_challenger": projection_challenger,
```

In both `ev_over` and `ev_under`, add:

```python
            "projection_challenger": projection_challenger,
```

- [ ] **Step 6: Run tests**

Run:

```powershell
python -m pytest tests/test_build_features.py::test_market_shrink_shadow_preserves_lambda_and_adds_metadata tests/test_build_features.py::test_market_shrink_enforce_replaces_selected_lambda -q
python -m pytest tests/test_build_features.py -q
```

Expected: tests pass.

- [ ] **Step 7: Commit**

```powershell
git add pipeline/build_features.py tests/test_build_features.py
git commit -m "feat: add market shrink projection metadata"
```

## Task 3: Persist Projection Metadata Through History And Tracked Picks

**Files:**
- Modify: `pipeline/fetch_results.py`
- Modify: `pipeline/run_pipeline.py`
- Modify: `tests/test_fetch_results.py`
- Modify: `tests/test_run_pipeline.py`

**Interfaces:**
- Consumes: side-level `projection_challenger` metadata from Task 2.
- Produces: `projection_challenger` object in `picks_history.json`, dated slate `tracked_picks`, and pitcher-card tracked-pick rows.

- [ ] **Step 1: Add failing persistence tests**

Add a seed/export test in `tests/test_fetch_results.py`:

```python
def test_seed_picks_persists_projection_challenger_metadata(tmp_db, tmp_path):
    _, fr = tmp_db

    today = tmp_path / "today.json"
    today.write_text(
        json.dumps(
            {
                "date": "2026-06-22",
                "pitchers": [
                    {
                        "pitcher": "Example Starter",
                        "team": "NYY",
                        "opp_team": "BOS",
                        "game_time": "2026-06-22T23:05:00Z",
                        "k_line": 5.5,
                        "lambda": 5.9,
                        "raw_lambda": 6.1,
                        "model_lambda": 6.1,
                        "best_over_odds": -120,
                        "best_under_odds": 100,
                        "projection_challenger": {"mode": "shadow", "candidate": "market_shrink_25"},
                        "ev_over": {
                            "verdict": "LEAN",
                            "edge": 0.04,
                            "ev": 0.08,
                            "adj_ev": 0.08,
                            "movement_conf": 1.0,
                            "projection_challenger": {"mode": "shadow", "candidate": "market_shrink_25"},
                        },
                        "ev_under": {"verdict": "PASS", "ev": -0.05, "adj_ev": -0.05, "movement_conf": 1.0},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert fr.seed_picks(today) == 1
    history_path = tmp_path / "picks_history.json"
    assert fr.export_db_to_history(history_path) == 1
    rows = json.loads(history_path.read_text(encoding="utf-8"))

    assert rows[0]["projection_challenger"]["mode"] == "shadow"
    assert rows[0]["projection_challenger"]["candidate"] == "market_shrink_25"
```

Add a tracked-pick test in `tests/test_run_pipeline.py`:

```python
def test_tracked_pick_row_exposes_projection_challenger_metadata():
    import run_pipeline

    row = run_pipeline._tracked_pick_row(
        {
            "date": "2026-06-22",
            "pitcher": "Example Starter",
            "team": "NYY",
            "opp_team": "BOS",
            "side": "over",
            "verdict": "LEAN",
            "k_line": 5.5,
            "odds": -120,
            "adj_ev": 0.08,
            "projection_challenger": {
                "mode": "shadow",
                "candidate": "market_shrink_25",
                "current_lambda": 6.1,
                "would_lambda": 5.95,
            },
        }
    )

    assert row["projection_challenger"]["mode"] == "shadow"
    assert row["projection_challenger"]["candidate"] == "market_shrink_25"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_fetch_results.py::test_seed_picks_persists_projection_challenger_metadata tests/test_run_pipeline.py::test_tracked_pick_row_exposes_projection_challenger_metadata -q
```

Expected: fail because the metadata column/row copy does not exist.

- [ ] **Step 3: Extend SQLite schema and seed/update paths**

In `pipeline/fetch_results.py`, add `projection_challenger_json TEXT` to the `picks` table and the migration list:

```python
("projection_challenger_json", "TEXT"),
```

When seeding side rows, set:

```python
projection_challenger_json = _json_or_none(ev_data.get("projection_challenger"))
```

Add the column to INSERT, UPDATE, and stale-PASS update statements beside `confidence_referee_json` and `market_anchor_selector_json`.

- [ ] **Step 4: Export/import metadata**

Add `projection_challenger_json` to the selected/exported columns and decode it:

```python
pick["projection_challenger"] = _json_load_or_none(pick.pop("projection_challenger_json", None))
```

When loading existing `picks_history.json` into SQLite, serialize:

```python
_json_or_none(p.get("projection_challenger"))
```

- [ ] **Step 5: Copy metadata into tracked rows**

In `pipeline/run_pipeline.py`, update `_tracked_pick_row` and `_reconciled_unlocked_tracked_pick`:

```python
    if pick.get("projection_challenger") is not None:
        row["projection_challenger"] = pick.get("projection_challenger")
```

and:

```python
    if side_data.get("projection_challenger") is not None:
        row["projection_challenger"] = side_data.get("projection_challenger")
```

- [ ] **Step 6: Run tests**

Run:

```powershell
python -m pytest tests/test_fetch_results.py::test_seed_picks_persists_projection_challenger_metadata tests/test_run_pipeline.py::test_tracked_pick_row_exposes_projection_challenger_metadata -q
python -m pytest tests/test_fetch_results.py tests/test_run_pipeline.py -q
```

Expected: tests pass.

- [ ] **Step 7: Commit**

```powershell
git add pipeline/fetch_results.py pipeline/run_pipeline.py tests/test_fetch_results.py tests/test_run_pipeline.py
git commit -m "feat: persist projection challenger metadata"
```

## Task 4: Add Artifact And Canary Audits

**Files:**
- Create: `analytics/diagnostics/market_shrink_projection_canary_audit.py`
- Create: `tests/test_market_shrink_projection_canary_audit.py`
- Modify: `scripts/run_post_grading_shadow_reports.py`
- Write: `analytics/output/market_shrink_projection_canary_audit.md`

**Interfaces:**
- Consumes: Gate C dataset rows plus `projection_challenger` metadata from `picks_history`.
- Produces: Markdown report with mode counts, candidate counts, changed lambda counts, tracked outcomes, FIRE/LEAN split, side split, K-line split, model-market relationship, quality gate, workload/no-vig labels, and rollback recommendation.

- [ ] **Step 1: Add audit tests**

Create `tests/test_market_shrink_projection_canary_audit.py`:

```python
from analytics.diagnostics import market_shrink_projection_canary_audit as audit


def test_summarize_counts_shadow_and_enforce_rows():
    rows = [
        {
            "slate_date": "2026-06-22",
            "result": "win",
            "is_tracked_pick": True,
            "projection_challenger": {
                "mode": "shadow",
                "candidate": "market_shrink_25",
                "applied": False,
                "current_lambda": 6.0,
                "would_lambda": 5.875,
            },
        },
        {
            "slate_date": "2026-06-22",
            "result": "loss",
            "is_tracked_pick": True,
            "projection_challenger": {
                "mode": "enforce",
                "candidate": "market_shrink_25",
                "applied": True,
                "current_lambda": 6.0,
                "would_lambda": 5.875,
            },
        },
    ]

    summary = audit.summarize(rows)

    assert summary["rows_with_metadata"] == 2
    assert summary["mode_counts"] == {"shadow": 1, "enforce": 1}
    assert summary["applied_rows"] == 1
```

- [ ] **Step 2: Implement the audit**

Create `analytics/diagnostics/market_shrink_projection_canary_audit.py`:

```python
"""Audit market-shrink projection canary metadata.

Read-only. This report does not change lambda or production artifacts.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "market_shrink_projection_canary_audit.md"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    with_meta = [row for row in rows if isinstance(row.get("projection_challenger"), dict)]
    mode_counts = Counter(row["projection_challenger"].get("mode") for row in with_meta)
    candidate_counts = Counter(row["projection_challenger"].get("candidate") for row in with_meta)
    applied_rows = sum(1 for row in with_meta if row["projection_challenger"].get("applied") is True)
    return {
        "total_rows": len(rows),
        "rows_with_metadata": len(with_meta),
        "mode_counts": dict(mode_counts),
        "candidate_counts": dict(candidate_counts),
        "applied_rows": applied_rows,
    }


def build_report(rows: list[dict[str, Any]]) -> str:
    summary = summarize(rows)
    lines = [
        "# Market Shrink Projection Canary Audit",
        "",
        "Read-only: this report does not change lambda, thresholds, staking, provider order, notifications, locks, retention, or dashboard source-of-truth.",
        "",
        "## Executive Read",
        "",
        f"- Total source rows: `{summary['total_rows']}`",
        f"- Rows with projection metadata: `{summary['rows_with_metadata']}`",
        f"- Applied rows: `{summary['applied_rows']}`",
        "",
        "## Mode Counts",
        "",
    ]
    for mode, count in sorted(summary["mode_counts"].items()):
        lines.append(f"- `{mode}`: `{count}`")
    lines.extend(["", "## Candidate Counts", ""])
    for candidate, count in sorted(summary["candidate_counts"].items()):
        lines.append(f"- `{candidate}`: `{count}`")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    rows = load_jsonl(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_report(rows), encoding="utf-8")
    print(f"Wrote {args.output} ({len(rows)} source rows)")
    return 0
```

- [ ] **Step 3: Wire post-grading runner**

Add optional output args to `scripts/run_post_grading_shadow_reports.py`:

```python
from analytics.diagnostics import market_shrink_projection_canary_audit
```

and after the Gate F report:

```python
    market_shrink_projection_canary_audit.main([
        "--input",
        str(dataset_path),
        "--output",
        str(args.market_shrink_projection_output),
    ])
```

- [ ] **Step 4: Run tests and generate report**

Run:

```powershell
python -m pytest tests/test_market_shrink_projection_canary_audit.py -q
python analytics/diagnostics/market_shrink_projection_canary_audit.py --input data/research/gate_c/pitcher_k_outcome_dataset.jsonl --output analytics/output/market_shrink_projection_canary_audit.md
```

Expected: tests pass and report writes.

- [ ] **Step 5: Commit**

```powershell
git add analytics/diagnostics/market_shrink_projection_canary_audit.py tests/test_market_shrink_projection_canary_audit.py scripts/run_post_grading_shadow_reports.py analytics/output/market_shrink_projection_canary_audit.md
git commit -m "feat: add market shrink projection canary audit"
```

## Task 5: Shadow Deployment And Verification

**Files:**
- Modify: Render env only after Tyler approval.
- Read: Netlify/Supabase artifacts.

**Interfaces:**
- Consumes: code from Tasks 1-4.
- Produces: one clean shadow slate with metadata and no live behavior changes.

- [ ] **Step 1: Deploy code with mode still off**

Run after merge to `main`:

```powershell
python scripts/deploy_render_pipeline_crons.py --execute
```

Expected: seven Render pipeline cron services deploy the commit.

- [ ] **Step 2: Tyler approval checkpoint**

Do not set the env var until Tyler explicitly approves:

```text
MARKET_SHRINK_PROJECTION_MODE=shadow
MARKET_SHRINK_PROJECTION_CANDIDATE=market_shrink_25
```

- [ ] **Step 3: Set shadow env on seven pipeline cron services**

Use Render UI or Render API to set the two env vars on:

```text
bbe-pipeline-preview
bbe-pipeline-grading
bbe-pipeline-full
bbe-pipeline-refresh-day
bbe-pipeline-refresh-evening
bbe-pipeline-refresh-final
bbe-pipeline-lock
```

- [ ] **Step 4: Redeploy and verify service commit**

Run:

```powershell
python scripts/deploy_render_pipeline_crons.py --execute
```

Expected: all seven cron services are live on the intended commit.

- [ ] **Step 5: Verify artifact metadata**

After the next full/refresh artifact, query Netlify:

```powershell
@'
const res = await fetch('https://baseballbettingedge.netlify.app/.netlify/functions/get-artifact?type=today');
const today = await res.json();
const rows = today.pitchers || [];
const meta = rows.filter(row => row.projection_challenger);
console.log(JSON.stringify({
  date: today.date,
  generated_at: today.generated_at,
  pitchers: rows.length,
  metadata_rows: meta.length,
  modes: meta.reduce((acc,row)=>{const mode=row.projection_challenger.mode; acc[mode]=(acc[mode]||0)+1; return acc;}, {}),
  applied_rows: meta.filter(row=>row.projection_challenger.applied).length
}, null, 2));
'@ | node -
```

Expected in `shadow`: `metadata_rows` equals pitcher count, mode count has `shadow`, and `applied_rows` is `0`.

- [ ] **Step 6: Verify no live behavior changed**

For a sample of rows, assert:

```text
lambda == model_lambda
projection_challenger.selected_lambda == model_lambda
projection_challenger.would_lambda may differ
```

If any `shadow` row changes `lambda`, stop and set `MARKET_SHRINK_PROJECTION_MODE=off`.

- [ ] **Step 7: Commit docs/handoff update**

After the first clean shadow smoke, update this plan's implementation status and `docs/current-state.md`.

## Task 6: Enforce Canary Decision And One-Slate Review

**Files:**
- Modify: Render env only after Tyler approval.
- Read: artifacts and post-grading reports.

**Interfaces:**
- Consumes: one clean shadow slate.
- Produces: one clean enforce slate for review.

- [ ] **Step 1: Tyler approval checkpoint**

Only Tyler can approve:

```text
MARKET_SHRINK_PROJECTION_MODE=enforce
MARKET_SHRINK_PROJECTION_CANDIDATE=market_shrink_25
```

- [ ] **Step 2: Set enforce env and redeploy**

Set the env vars on all seven pipeline cron services and run:

```powershell
python scripts/deploy_render_pipeline_crons.py --execute
```

- [ ] **Step 3: Verify current artifacts**

Expected for same-day artifacts after enforce:

```text
projection_challenger.mode == "enforce"
projection_challenger.applied == true
lambda == projection_challenger.selected_lambda
model_lambda == projection_challenger.current_lambda
```

- [ ] **Step 4: Review first graded enforce slate**

After grading, run:

```powershell
python scripts/run_post_grading_shadow_reports.py --artifact-source production
```

Review:

- tracked record and PnL by FIRE/LEAN
- FIRE 1u and FIRE 2u exposure changes
- over/under split
- plus/minus split
- K-line bucket
- quality-gate level
- confidence-referee/profit-rescue interactions
- Path B real-split/fallback buckets
- workload/no-vig buckets
- CLV and market-agreement buckets
- rolling window compared with prior shadow report

- [ ] **Step 5: Stop/continue rule**

Stop and revert to `off` if any of these occur:

- artifact schema breaks dashboard or tracked picks
- today's `lambda` lacks `model_lambda` rollback metadata
- FIRE exposure increases unexpectedly
- one-slate enforce produces large degradation concentrated in a clear runtime slice
- confidence-referee/profit-rescue metadata disappears
- source/provenance changes away from TheRundown or TheRundown+PropLine fallback

Continue observing if:

- artifacts are fresh
- metadata coverage is complete
- no source/provider behavior changed
- one-slate outcome is bad but slice diagnostics do not identify a production bug

## Task 7: Final Promotion Or Rollback Review

**Files:**
- Modify: this plan and `docs/current-state.md`.
- Do not modify production behavior without Tyler's decision.

- [ ] **Step 1: Gather final evidence**

Minimum review pack:

```powershell
python scripts/run_post_grading_shadow_reports.py --artifact-source production
```

Plus Netlify/Supabase artifact checks for:

- `today`
- latest dated slate
- `picks_history`
- `performance`
- `params`

- [ ] **Step 2: Write decision summary**

Add a dated section to this plan:

```markdown
## YYYY-MM-DD Canary Review

- Mode:
- Candidate:
- Clean enforce slates:
- Tracked rows:
- FIRE rows:
- PnL/ROI:
- Lambda movement distribution:
- Passed slices:
- Failed slices:
- Recommendation:
```

- [ ] **Step 3: Tyler decision**

Allowed decisions:

- `rollback_to_off`
- `keep_shadow`
- `continue_enforce_canary`
- `draft_permanent_market_shrink_plan`

Not allowed from this plan:

- permanent lambda formula change without a new plan
- threshold/staking change
- provider/source change
- notification change
- lock/retention/dashboard source-of-truth change

## Rollback

Immediate rollback:

```text
MARKET_SHRINK_PROJECTION_MODE=off
```

Then redeploy:

```powershell
python scripts/deploy_render_pipeline_crons.py --execute
```

Rollback verification:

```powershell
@'
const res = await fetch('https://baseballbettingedge.netlify.app/.netlify/functions/get-artifact?type=today');
const today = await res.json();
const rows = today.pitchers || [];
console.log({
  date: today.date,
  generated_at: today.generated_at,
  projectionRows: rows.filter(row => row.projection_challenger?.mode === 'enforce').length
});
'@ | node -
```

Expected after a fresh off-mode run: `projectionRows` is `0` or no rows are in enforce mode.

## Self-Review

Spec coverage:

- Gate F hit is limited to `market_shrink_15/25/35`.
- First canary uses `market_shrink_25`.
- Shadow and enforce are separate Tyler approvals.
- Runtime inputs are only current lambda and K line.
- Rollback is one env var.
- No provider, threshold, staking, notification, lock, retention, or dashboard-source change is included.

Placeholder scan:

- No TBD/TODO placeholders.
- Each task has files, concrete commands, and expected outputs.

Type consistency:

- `projection_challenger` is the metadata object name across pitcher rows, side rows, picks history, and tracked picks.
- `model_lambda` means current pre-challenger lambda.
- `lambda` remains the selected lambda used for probabilities.
