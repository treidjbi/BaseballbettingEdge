# Frozen No-Drag Composite Prospective Canary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only, post-grading-only audit that freezes `combined_runtime_broad_no_hindsight_no_drag_v1`, reconciles its locked July 20 baseline, and prospectively counts evidence toward a separate 75-row review floor without changing live behavior.

**Architecture:** A dedicated diagnostic owns the frozen rule specification, SHA-256 fingerprint, direct selector implementation, fail-closed evidence accounting, mandatory slices, and Markdown/JSON outputs. The existing post-grading runner invokes it only after Gate C and Shadow Signal Synthesis are rebuilt. A new research packet and the Four-Lane Operating Board identify this v1 canary as the lead research candidate while preserving the prior strict-plus-selective policy as the comparison/control.

**Tech Stack:** Python 3.11, standard-library `argparse`/`dataclasses`/`hashlib`/`json`, pytest, existing Gate C JSONL dataset, existing post-grading runner.

## Global Constraints

- Selector id is exactly `combined_runtime_broad_no_hindsight_no_drag_v1`.
- Prospective evidence begins exactly on `2026-07-21`; the historical rebuild ends on `2026-07-20` and the clean window begins on `2026-04-28`.
- Locked clean-window baseline is exactly `186` rows, `124-62`, `+29.20u`, `+15.7%`.
- Locked current-provider baseline is exactly `52` rows, `36-16`, `+9.17u`, `+17.6%`.
- Locked recent reference is exactly `35` rows, `24-11`, `+5.68u`, `+16.2%`.
- Review floor is exactly `75`; the untouched starting countdown is `52 + 0 = 52`, with `23` remaining.
- The diagnostic must encode the v1 selector directly and must not call `shadow_signal_synthesis_lab._composite_policies()` or its mutable no-drag entry.
- Preserve Python truthy-`or` adjusted-EV precedence: `locked_adj_ev`, then `adj_ev`, then `ev`; numeric zero falls through.
- Historical reconciliation tolerance is `0.005u`; drift, duplicate keys, or prospective critical-input gaps block counter advancement.
- Allowed statuses are exactly `blocked_duplicate_keys`, `blocked_baseline_drift`, `blocked_input_gap`, `collecting`, and `ready_for_review`.
- `ready_for_review` is the strongest state. The implementation must never auto-promote or imply approval.
- Outputs are exactly `analytics/output/no_drag_composite_canary_audit.md` and `analytics/output/no_drag_composite_canary_audit.json`.
- The feature is post-grading research only. Do not change live artifacts, model math, verdicts, thresholds, staking, providers, notifications, locks, UI, retention, calibration, source-of-truth behavior, environment variables, or `formula_change_date`.
- The committed Gate C file in this clone currently ends before the July 20 freeze. Direct CLI execution against that stale file must succeed but report `blocked_baseline_drift`; the existing post-grading builder is what refreshes the corpus before the scheduled audit runs.

---

## File Structure

- Create `analytics/diagnostics/no_drag_composite_canary_audit.py`: frozen rule, fingerprint, row evaluation, integrity gates, evidence windows, slice audit, output renderers, and CLI.
- Create `tests/test_no_drag_composite_canary_audit.py`: selector truth table, fingerprint, accounting, blocking, slices, renderer, output, and direct-CLI coverage.
- Modify `scripts/run_post_grading_shadow_reports.py`: invoke the new audit after synthesis and print only its executive/counter/reconciliation excerpt.
- Modify `tests/test_post_grading_shadow_reports.py`: prove invocation order, output paths, and excerpt scoping.
- Create `docs/research/no-drag-composite-prospective-canary-packet.md`: operator-facing research packet for the frozen v1 candidate.
- Modify `docs/current-state.md`: make the no-drag v1 canary the lead research candidate and retain strict-plus-selective as the comparison/control.
- Generate ignored runtime files at `analytics/output/no_drag_composite_canary_audit.md` and `analytics/output/no_drag_composite_canary_audit.json`; verify them locally, but do not force-add ignored analytics output to Git.

---

### Task 1: Freeze the Selector Contract and Fingerprint

**Files:**

- Create: `analytics/diagnostics/no_drag_composite_canary_audit.py`
- Create: `tests/test_no_drag_composite_canary_audit.py`

**Interfaces:**

- Produces: `RULE_SPEC: dict[str, Any]`, `RULE_FINGERPRINT: str`, `Evaluation`, `verdict(row)`, `adjusted_ev(row)`, `ev_bucket(row)`, `market_anchor_labels(row)`, and `evaluate_row(row)`.
- `Evaluation` fields are `qualifies: bool`, `families: tuple[str, ...]`, `drag_labels: tuple[str, ...]`, and `missing_inputs: tuple[str, ...]`.
- Task 2 consumes `evaluate_row`, `RULE_FINGERPRINT`, and the exact constants defined here.

- [ ] **Step 1: Write the failing selector and fingerprint tests**

Create a focused fixture and assertions that cover every frozen branch, every exclusion, verdict precedence, numeric boundaries, JSON-string/object market-anchor labels, and the exact fingerprint:

```python
import json

import pytest

from analytics.diagnostics import no_drag_composite_canary_audit as audit


def candidate_row(**overrides):
    row = {
        "is_tracked_pick": True,
        "slate_date": "2026-07-21",
        "normalized_pitcher": "test pitcher",
        "side": "over",
        "result": "win",
        "pick_history_pnl": 1.0,
        "display_verdict": "FIRE 1u",
        "edge": 0.04,
        "locked_adj_ev": 0.10,
        "model_market_relationship": "model_agrees_with_favorite",
        "line_bucket": "4.5",
        "price_sign": "minus",
        "price_bucket": "-100 to -129",
        "bet_timing_window": "pre_30",
        "leash_risk_bucket": "normal",
        "pitcher_archetype_bucket": "standard_starter",
        "model_no_vig_gap": 0.01,
        "quality_gate_level": "clean",
        "batter_handedness_mode": "path_b",
        "lineup_real_split_count": 3,
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    ("overrides", "family"),
    [
        ({}, "strong_base_strict_runtime_core"),
        (
            {
                "display_verdict": "FIRE 1u",
                "model_market_relationship": "model_other",
                "bet_timing_window": "unknown",
            },
            "strong_base_strict_runtime_core",
        ),
        (
            {
                "display_verdict": "LEAN",
                "locked_adj_ev": 0.03,
                "model_market_relationship": "model_other",
            },
            "strong_base_selective_lean",
        ),
        (
            {
                "display_verdict": "LEAN",
                "line_bucket": "5.5",
                "pitcher_archetype_bucket": "low_k_standard",
                "model_no_vig_gap": 0.02,
                "model_market_relationship": "model_other",
            },
            "strong_base_selective_lean",
        ),
        (
            {
                "display_verdict": "PASS",
                "model_market_relationship": "model_other",
                "market_anchor_selector": {"labels": ["market_anchor_strict"]},
            },
            "market_anchor_strict",
        ),
    ],
)
def test_frozen_selector_positive_truth_table(overrides, family):
    evaluation = audit.evaluate_row(candidate_row(**overrides))
    assert evaluation.qualifies is True
    assert family in evaluation.families
    assert evaluation.drag_labels == ()
    assert evaluation.missing_inputs == ()


@pytest.mark.parametrize(
    ("overrides", "drag_label"),
    [
        ({"edge": 0.06}, "cap_high_raw_edge"),
        ({"model_market_relationship": "model_fades_favorite"}, "cap_market_fade"),
        (
            {"side": "under", "model_market_relationship": "model_fades_favorite"},
            "cap_fire_under_market_fade",
        ),
    ],
)
def test_frozen_drag_rules_exclude_rows(overrides, drag_label):
    evaluation = audit.evaluate_row(candidate_row(**overrides))
    assert evaluation.qualifies is False
    assert drag_label in evaluation.drag_labels


def test_selective_low_line_model_fade_is_removed_by_outer_drag():
    evaluation = audit.evaluate_row(candidate_row(
        display_verdict="LEAN",
        line_bucket="2.5-3.5",
        locked_adj_ev=0.03,
        model_market_relationship="model_fades_favorite",
        quality_gate_level="capped",
    ))
    assert "strong_base_selective_lean" in evaluation.families
    assert "cap_market_fade" in evaluation.drag_labels
    assert evaluation.qualifies is False


def test_verdict_precedence_uses_first_non_empty_value():
    row = candidate_row(
        display_verdict="LEAN",
        locked_verdict="FIRE 2u",
        actionable_verdict="PASS",
        locked_adj_ev=0.03,
        model_market_relationship="model_other",
    )
    assert audit.verdict(row) == "LEAN"
    assert audit.evaluate_row(row).families == ("strong_base_selective_lean",)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (-0.001, "ev_negative"),
        (0.0, "ev_unknown"),
        (0.059999, "ev_0_to_6"),
        (0.06, "ev_6_to_17"),
        (0.169999, "ev_6_to_17"),
        (0.17, "ev_17_plus"),
    ],
)
def test_adjusted_ev_boundaries(value, expected):
    assert audit.ev_bucket({"locked_adj_ev": value}) == expected


def test_adjusted_ev_preserves_truthy_or_zero_fallthrough():
    row = {"locked_adj_ev": 0.0, "adj_ev": 0.10, "ev": 0.03}
    assert audit.adjusted_ev(row) == 0.10


# A lone zero resolves to ev_unknown under the frozen Python truthy-or chain;
# zero falls through only when a later adjusted-EV source is truthy.


def test_market_anchor_labels_accept_object_fallback_and_json_object():
    assert audit.market_anchor_labels({
        "market_anchor_selector": {"labels": ["market_anchor_strict"]},
    }) == {"market_anchor_strict"}
    assert audit.market_anchor_labels({
        "market_anchor_selector_labels": ["market_anchor_strict"],
    }) == {"market_anchor_strict"}
    assert audit.market_anchor_labels({
        "market_anchor_selector": json.dumps({"labels": ["market_anchor_strict"]}),
    }) == {"market_anchor_strict"}


def test_rule_fingerprint_is_pinned():
    assert audit.RULE_FINGERPRINT == "22b03ecea02aa83e9174c24f5f05878823cb67766fe1c75102d34bfe5c3b4aa4"
```

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
python -m pytest tests/test_no_drag_composite_canary_audit.py -q
```

Expected: collection fails because `analytics.diagnostics.no_drag_composite_canary_audit` does not exist.

- [ ] **Step 3: Implement the frozen constants, canonical rule spec, and selector**

Start the module with the repository-root import guard, these exact constants, and this canonical rule object; JSON serialization must use `sort_keys=True` and `separators=(",", ":")`:

```python
"""Audit the frozen no-drag composite as post-grading research only.

This diagnostic cannot change live picks, model math, verdicts, staking,
providers, notifications, locks, UI, retention, artifacts, or source of truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from analytics.diagnostics import gate_f_preclose_clv_proxy_lab as preclose_proxy
from analytics.diagnostics import strong_base_decision_lab as strong_base
from pipeline.name_utils import normalize

DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
DEFAULT_OUTPUT_MD = ROOT / "analytics" / "output" / "no_drag_composite_canary_audit.md"
DEFAULT_OUTPUT_JSON = ROOT / "analytics" / "output" / "no_drag_composite_canary_audit.json"
SELECTOR_ID = "combined_runtime_broad_no_hindsight_no_drag_v1"
SELECTOR_VERSION = 1
CLEAN_WINDOW_START = "2026-04-28"
HISTORICAL_END = "2026-07-20"
PROSPECTIVE_START = "2026-07-21"
CURRENT_PROVIDER_START = "2026-06-24"
REVIEW_FLOOR = 75
LOCKED_HISTORICAL = {"rows": 186, "wins": 124, "losses": 62, "pnl": 29.20, "roi": 0.157}
LOCKED_CURRENT_PROVIDER = {"rows": 52, "wins": 36, "losses": 16, "pnl": 9.17, "roi": 0.176}
LOCKED_RECENT_REFERENCE = {"rows": 35, "wins": 24, "losses": 11, "pnl": 5.68, "roi": 0.162}
BASELINE_PNL_TOLERANCE = 0.005
WIN_LOSS_RESULTS = {"win", "loss"}
VERDICT_FIELDS = (
    "display_verdict",
    "locked_verdict",
    "actionable_verdict",
    "current_verdict",
    "verdict",
)

RULE_SPEC = {
    "selector_id": SELECTOR_ID,
    "version": SELECTOR_VERSION,
    "prospective_start": PROSPECTIVE_START,
    "verdict_precedence": list(VERDICT_FIELDS),
    "adjusted_ev": {
        "precedence": ["locked_adj_ev", "adj_ev", "ev"],
        "join": "python_truthy_or",
        "buckets": [
            {"label": "ev_negative", "min": None, "max_exclusive": 0.0},
            {"label": "ev_0_to_6", "min": 0.0, "max_exclusive": 0.06},
            {"label": "ev_6_to_17", "min": 0.06, "max_exclusive": 0.17},
            {"label": "ev_17_plus", "min": 0.17, "max_exclusive": None},
        ],
    },
    "keep_fire": {
        "keep_fire_market_agreed_moderate_ev": {
            "verdict": "FIRE*",
            "model_market_relationship": "model_agrees_with_favorite",
            "adjusted_ev_bucket": "ev_6_to_17",
            "bet_timing_window": "pre_30",
        },
        "keep_fire_over_moderate_ev_normal_leash": {
            "verdict": "FIRE*",
            "side": "over",
            "adjusted_ev_bucket": "ev_6_to_17",
            "leash_or_opportunity_bucket": "normal",
        },
    },
    "expand_lean": {
        "expand_lean_45_low_ev_normal_leash": {
            "verdict": "LEAN",
            "line_bucket": "4.5",
            "adjusted_ev_bucket": "ev_0_to_6",
            "leash_or_opportunity_bucket": "normal",
        },
        "expand_lean_low_k_standard_no_vig": {
            "verdict": "LEAN",
            "pitcher_archetype_bucket": "low_k_standard",
            "model_no_vig_gap_min": 0.02,
        },
        "expand_lean_low_line_capped_model_fade": {
            "verdict": "LEAN",
            "line_bucket": "2.5-3.5",
            "model_market_relationship": "model_fades_favorite",
            "quality_gate_level": "capped",
        },
    },
    "market_anchor": {
        "label": "market_anchor_strict",
        "sources": ["market_anchor_selector.labels", "market_anchor_selector_labels"],
    },
    "drag": {
        "cap_high_raw_edge": {"edge_min": 0.06},
        "cap_market_fade": {"model_market_relationship": "model_fades_favorite"},
        "cap_fire_under_market_fade": {
            "verdict": "FIRE*",
            "side": "under",
            "model_market_relationship": "model_fades_favorite",
        },
    },
    "formula": "(strict_runtime_core OR selective_lean OR market_anchor_strict) AND NOT drag_core",
}
RULE_FINGERPRINT = hashlib.sha256(
    json.dumps(RULE_SPEC, sort_keys=True, separators=(",", ":")).encode("utf-8")
).hexdigest()


@dataclass(frozen=True)
class Evaluation:
    qualifies: bool
    families: tuple[str, ...]
    drag_labels: tuple[str, ...]
    missing_inputs: tuple[str, ...]


def to_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def verdict(row: dict[str, Any]) -> str:
    return str(next((row.get(field) for field in VERDICT_FIELDS if row.get(field)), "")).strip()


def adjusted_ev(row: dict[str, Any]) -> float | None:
    return to_float(row.get("locked_adj_ev")) or to_float(row.get("adj_ev")) or to_float(row.get("ev"))


def ev_bucket(row: dict[str, Any]) -> str:
    value = adjusted_ev(row)
    if value is None:
        return "ev_unknown"
    if value < 0:
        return "ev_negative"
    if value < 0.06:
        return "ev_0_to_6"
    if value < 0.17:
        return "ev_6_to_17"
    return "ev_17_plus"


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def market_anchor_labels(row: dict[str, Any]) -> set[str]:
    nested = _json_object(row.get("market_anchor_selector")).get("labels") or []
    flat = row.get("market_anchor_selector_labels") or []

    def values(value: Any) -> list[Any]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, (list, tuple, set)):
            return list(value)
        return []

    return {
        str(label).strip()
        for label in values(nested) + values(flat)
        if str(label or "").strip()
    }


def evaluate_row(row: dict[str, Any]) -> Evaluation:
    selected_verdict = verdict(row)
    is_fire = selected_verdict.startswith("FIRE")
    is_lean = selected_verdict == "LEAN"
    side = str(row.get("side") or "").strip().lower()
    relationship = str(row.get("model_market_relationship") or "").strip()
    line_bucket = str(row.get("line_bucket") or "").strip()
    leash = str(row.get("leash_risk_bucket") or row.get("opportunity_bucket") or "").strip().lower()
    quality = str(row.get("quality_gate_level") or "").strip().lower()
    timing = str(row.get("bet_timing_window") or "").strip()
    archetype = str(row.get("pitcher_archetype_bucket") or "").strip()
    no_vig_gap = to_float(row.get("model_no_vig_gap"))
    families: list[str] = []
    drag_labels: list[str] = []

    edge = to_float(row.get("edge"))
    if edge is not None and edge >= 0.06:
        drag_labels.append("cap_high_raw_edge")
    if relationship == "model_fades_favorite":
        drag_labels.append("cap_market_fade")
    if is_fire and side == "under" and relationship == "model_fades_favorite":
        drag_labels.append("cap_fire_under_market_fade")

    keep_fire = is_fire and (
        (
            relationship == "model_agrees_with_favorite"
            and ev_bucket(row) == "ev_6_to_17"
            and timing == "pre_30"
        )
        or (
            side == "over"
            and ev_bucket(row) == "ev_6_to_17"
            and leash == "normal"
        )
    )
    if keep_fire and not drag_labels:
        families.append("strong_base_strict_runtime_core")

    selective_lean = is_lean and (
        (
            line_bucket == "4.5"
            and ev_bucket(row) == "ev_0_to_6"
            and leash == "normal"
        )
        or (
            archetype == "low_k_standard"
            and no_vig_gap is not None
            and no_vig_gap >= 0.02
        )
        or (
            line_bucket == "2.5-3.5"
            and relationship == "model_fades_favorite"
            and quality == "capped"
        )
    )
    if selective_lean and not {
        "cap_high_raw_edge",
        "cap_fire_under_market_fade",
    }.intersection(drag_labels):
        families.append("strong_base_selective_lean")

    if "market_anchor_strict" in market_anchor_labels(row):
        families.append("market_anchor_strict")

    return Evaluation(
        qualifies=bool(families) and not drag_labels,
        families=tuple(families),
        drag_labels=tuple(drag_labels),
        missing_inputs=(),
    )
```

Keep family and drag tuples deterministic in rule-spec order. The low-line model-fade LEAN family remains visible in `families` even though the outer market-fade drag makes `qualifies=False`.

Prospective critical-field validation is added in Task 2; Task 1 returns an empty `missing_inputs` tuple for complete rows.

- [ ] **Step 4: Run focused tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_no_drag_composite_canary_audit.py -q
```

Expected: all Task 1 selector and fingerprint tests pass.

- [ ] **Step 5: Commit Task 1**

```powershell
git add analytics/diagnostics/no_drag_composite_canary_audit.py tests/test_no_drag_composite_canary_audit.py
git commit -m "feat: freeze no-drag canary selector"
```

---

### Task 2: Add Fail-Closed Evidence Accounting, Slices, Outputs, and CLI

**Files:**

- Modify: `analytics/diagnostics/no_drag_composite_canary_audit.py`
- Modify: `tests/test_no_drag_composite_canary_audit.py`

**Interfaces:**

- Consumes: Task 1 `evaluate_row`, `RULE_FINGERPRINT`, selector constants, and locked baselines.
- Produces: `load_jsonl(path)`, `score(rows)`, `build_audit(rows, generated_at=None)`, `render_markdown(summary)`, `write_outputs(summary, md_path, json_path)`, and `main(argv=None) -> int`.
- The JSON result is the automation contract. Top-level keys are `generated_at`, `selector`, `status`, `integrity`, `locked_baselines`, `reconciliation`, `windows`, `counter`, `callouts`, `slices`, and `live_boundary`.

- [ ] **Step 1: Write failing accounting and integrity tests**

Append tests that build an exact locked-history fixture without needing 186 literal rows by monkeypatching the locked constants only inside unit tests. The production constants remain untouched:

```python
def graded_row(date, pitcher, result="win", pnl=1.0, **overrides):
    return candidate_row(
        slate_date=date,
        normalized_pitcher=pitcher,
        result=result,
        pick_history_pnl=pnl,
        **overrides,
    )


def lock_history_to(monkeypatch, rows):
    score = audit.score(rows)
    monkeypatch.setattr(audit, "LOCKED_HISTORICAL", {
        "rows": score["rows"],
        "wins": score["wins"],
        "losses": score["losses"],
        "pnl": score["pnl"],
        "roi": score["roi"],
    })


def test_initial_counter_is_locked_52_plus_zero(monkeypatch):
    historical = [graded_row("2026-07-20", "history one")]
    lock_history_to(monkeypatch, historical)
    summary = audit.build_audit(historical, generated_at="2026-07-21T16:00:00Z")
    assert summary["status"] == "collecting"
    assert summary["counter"] == {
        "locked_current_provider_rows": 52,
        "prospective_qualified_rows": 0,
        "rows": 52,
        "floor": 75,
        "remaining": 23,
    }


def test_prospective_rows_advance_counter_without_mutating_locked_history(monkeypatch):
    historical = [graded_row("2026-07-20", "history one")]
    prospective = [
        graded_row("2026-07-21", "future one"),
        graded_row("2026-07-22", "future two", result="loss", pnl=-1.0),
    ]
    lock_history_to(monkeypatch, historical)
    summary = audit.build_audit(historical + prospective)
    assert summary["locked_baselines"]["current_provider"]["rows"] == 52
    assert summary["windows"]["prospective"]["rows"] == 2
    assert summary["counter"]["rows"] == 54
    assert summary["counter"]["remaining"] == 21


def test_reaching_floor_only_becomes_ready_for_review(monkeypatch):
    historical = [graded_row("2026-07-20", "history one")]
    prospective = [
        graded_row("2026-07-21", f"future {index}")
        for index in range(23)
    ]
    lock_history_to(monkeypatch, historical)
    summary = audit.build_audit(historical + prospective)
    assert summary["status"] == "ready_for_review"
    assert summary["counter"]["rows"] == 75
    assert summary["counter"]["remaining"] == 0
    assert "promot" not in summary["status"]


def test_baseline_drift_blocks_counter_advancement():
    summary = audit.build_audit([graded_row("2026-07-20", "wrong baseline")])
    assert summary["status"] == "blocked_baseline_drift"
    assert summary["counter"]["rows"] == 52
    assert summary["counter"]["prospective_qualified_rows"] == 0
    assert summary["reconciliation"]["matches"] is False


def test_duplicate_key_blocks_counter_advancement(monkeypatch):
    historical = [graded_row("2026-07-20", "history one")]
    duplicate = graded_row("2026-07-21", "same pitcher")
    lock_history_to(monkeypatch, historical)
    summary = audit.build_audit(historical + [duplicate, dict(duplicate)])
    assert summary["status"] == "blocked_duplicate_keys"
    assert summary["integrity"]["duplicate_keys"] == [
        "2026-07-21|same pitcher|over"
    ]
    assert summary["counter"]["rows"] == 52


@pytest.mark.parametrize(
    "missing_update",
    [
        {"display_verdict": None, "locked_verdict": None, "actionable_verdict": None, "current_verdict": None, "verdict": None},
        {"edge": None},
        {"locked_adj_ev": None, "adj_ev": None, "ev": None},
        {"model_market_relationship": None},
        {"line_bucket": None},
        {"price_sign": None},
        {"price_bucket": None},
        {"bet_timing_window": None},
        {"leash_risk_bucket": None, "opportunity_bucket": None},
        {"pitcher_archetype_bucket": None},
        {"model_no_vig_gap": None},
        {"quality_gate_level": None},
        {"batter_handedness_mode": None},
        {"pick_history_pnl": None, "pnl": None, "theoretical_pnl": None},
    ],
)
def test_prospective_critical_input_gap_blocks_run(monkeypatch, missing_update):
    historical = [graded_row("2026-07-20", "history one")]
    lock_history_to(monkeypatch, historical)
    row = graded_row("2026-07-21", "future gap")
    row.update(missing_update)
    summary = audit.build_audit(historical + [row])
    assert summary["status"] == "blocked_input_gap"
    assert summary["integrity"]["input_gap_rows"] == 1
    assert summary["counter"]["rows"] == 52


def test_absent_market_anchor_metadata_is_false_not_input_gap(monkeypatch):
    historical = [graded_row("2026-07-20", "history one")]
    lock_history_to(monkeypatch, historical)
    row = graded_row("2026-07-21", "future complete", market_anchor_selector=None)
    summary = audit.build_audit(historical + [row])
    assert summary["status"] == "collecting"
    assert summary["integrity"]["input_gap_rows"] == 0
```

Critical input groups are exact and fail closed only for prospective tracked win/loss rows:

```python
CRITICAL_INPUT_GROUPS = (
    ("slate_date",),
    ("normalized_pitcher", "pitcher", "player_name"),
    ("side",),
    ("result",),
    ("pick_history_pnl", "pnl", "theoretical_pnl"),
    VERDICT_FIELDS,
    ("edge",),
    ("locked_adj_ev", "adj_ev", "ev"),
    ("model_market_relationship",),
    ("line_bucket",),
    ("price_sign",),
    ("price_bucket",),
    ("bet_timing_window",),
    ("leash_risk_bucket", "opportunity_bucket"),
    ("pitcher_archetype_bucket",),
    ("model_no_vig_gap",),
    ("quality_gate_level",),
    ("batter_handedness_mode",),
)

NUMERIC_CRITICAL_GROUPS = {
    ("pick_history_pnl", "pnl", "theoretical_pnl"),
    ("edge",),
    ("locked_adj_ev", "adj_ev", "ev"),
    ("model_no_vig_gap",),
}


def _value_present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


def missing_critical_inputs(row: dict[str, Any]) -> tuple[str, ...]:
    if str(row.get("slate_date") or row.get("date") or "")[:10] < PROSPECTIVE_START:
        return ()
    missing: list[str] = []
    for group in CRITICAL_INPUT_GROUPS:
        if group in NUMERIC_CRITICAL_GROUPS:
            present = any(to_float(row.get(field)) is not None for field in group)
        else:
            present = any(_value_present(row.get(field)) for field in group)
        if not present:
            missing.append("|".join(group))
    raw_selector = row.get("market_anchor_selector")
    selector = _json_object(raw_selector)
    if raw_selector is not None and selector and "labels" not in selector and not _value_present(row.get("market_anchor_selector_labels")):
        missing.append("market_anchor_selector.labels|market_anchor_selector_labels")
    return tuple(missing)
```

Numeric zero is present for critical-input validation even though adjusted-EV selection preserves truthy-`or` fallthrough. `market_anchor_selector` and `market_anchor_selector_labels` are deliberately absent from this list.

In Task 2, change the final `Evaluation` construction in `evaluate_row` to `missing_inputs=missing_critical_inputs(row)`. A row may still expose its observed family/drag evaluation for debugging, but any nonempty prospective `missing_inputs` blocks counter advancement for the entire run.

- [ ] **Step 2: Run accounting tests and verify RED**

Run:

```powershell
python -m pytest tests/test_no_drag_composite_canary_audit.py -q
```

Expected: failures identify missing `score`/`build_audit` behavior and integrity fields.

- [ ] **Step 3: Implement evidence windows, scorekeeping, and status precedence**

Implement these exact mechanics:

```python
def pick_key(row: dict[str, Any]) -> str:
    date = str(row.get("slate_date") or row.get("date") or "")[:10]
    pitcher_source = row.get("normalized_pitcher") or row.get("pitcher") or row.get("player_name") or ""
    pitcher = normalize(pitcher_source).strip()
    side = str(row.get("side") or "").strip().lower()
    return "|".join((date, pitcher, side))


def row_pnl(row: dict[str, Any]) -> float | None:
    for field in ("pick_history_pnl", "pnl", "theoretical_pnl"):
        value = to_float(row.get(field))
        if value is not None:
            return value
    return None


def score(rows: list[dict[str, Any]]) -> dict[str, Any]:
    wins = sum(row.get("result") == "win" for row in rows)
    losses = sum(row.get("result") == "loss" for row in rows)
    pnl = round(sum(row_pnl(row) or 0.0 for row in rows), 3)
    count = wins + losses
    return {
        "rows": count,
        "wins": wins,
        "losses": losses,
        "pnl": pnl,
        "roi": round(pnl / count, 4) if count else 0.0,
    }
```

Filter the source to tracked rows with `result in WIN_LOSS_RESULTS`. Historical rows satisfy `2026-04-28 <= slate_date <= 2026-07-20`; prospective rows satisfy `slate_date >= 2026-07-21`. Current-provider rows satisfy `slate_date >= 2026-06-24`. Recent rows use the latest 14 distinct slate dates among selected candidate rows.

Historical reconciliation compares rows, wins, and losses exactly and PnL within `0.005u` of `+29.20u`. ROI is reported but is not a separate reconciliation gate because it is derived from reconciled rows and PnL.

Status precedence is exact:

```python
if duplicate_keys:
    status = "blocked_duplicate_keys"
elif not reconciliation_matches:
    status = "blocked_baseline_drift"
elif input_gap_rows:
    status = "blocked_input_gap"
elif LOCKED_CURRENT_PROVIDER["rows"] + prospective_score["rows"] >= REVIEW_FLOOR:
    status = "ready_for_review"
else:
    status = "collecting"
```

For any blocked status, publish the observed prospective score but set `counter.prospective_qualified_rows=0` and keep `counter.rows=52`. This makes the failed run auditable without advancing the review floor.

- [ ] **Step 4: Write failing mandatory-slice, Markdown, JSON, and CLI tests**

Append:

```python
def test_mandatory_slices_include_scores_and_missing_coverage(monkeypatch):
    historical = [graded_row("2026-07-20", "history one")]
    prospective = graded_row(
        "2026-07-21",
        "future one",
        display_verdict="LEAN",
        locked_adj_ev=0.03,
        model_market_relationship="model_other",
        market_agreement_label=None,
        provider=None,
        live_display_provider=None,
        price_clv_cents=5,
    )
    lock_history_to(monkeypatch, historical)
    summary = audit.build_audit(historical + [prospective])
    prospective_slices = summary["slices"]["prospective"]
    assert prospective_slices["verdict_family"]["LEAN"]["rows"] == 1
    assert prospective_slices["side"]["over"]["rows"] == 1
    assert prospective_slices["price_bucket"]["-100 to -129"]["rows"] == 1
    assert prospective_slices["path_b"]["path_b_real_or_mixed"]["rows"] == 1
    assert prospective_slices["market_agreement"]["missing"]["rows"] == 1
    assert prospective_slices["provider_attribution"]["missing"]["rows"] == 1
    assert summary["integrity"]["slice_missing_coverage"]["prospective"]["market_agreement"] == 1
    assert summary["integrity"]["slice_missing_coverage"]["prospective"]["provider_attribution"] == 1


def test_markdown_leads_with_decision_fields_and_live_boundary(monkeypatch):
    historical = [graded_row("2026-07-20", "history one")]
    lock_history_to(monkeypatch, historical)
    report = audit.render_markdown(audit.build_audit(historical))
    assert report.startswith("# No-Drag Composite Prospective Canary Audit")
    assert "## Executive Read" in report
    assert audit.SELECTOR_ID in report
    assert audit.RULE_FINGERPRINT in report
    assert "`collecting`" in report
    assert "52" in report and "23" in report
    assert "## Baseline Reconciliation" in report
    assert "## Mandatory Slice Risks" in report
    assert "## Live Boundary" in report
    assert "requires a separate Tyler-approved plan" in report


def test_write_outputs_emits_matching_markdown_and_json(tmp_path, monkeypatch):
    historical = [graded_row("2026-07-20", "history one")]
    lock_history_to(monkeypatch, historical)
    summary = audit.build_audit(historical, generated_at="2026-07-21T16:00:00Z")
    md_path = tmp_path / "audit.md"
    json_path = tmp_path / "audit.json"
    audit.write_outputs(summary, md_path, json_path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["selector"]["id"] == audit.SELECTOR_ID
    assert payload["selector"]["fingerprint"] == audit.RULE_FINGERPRINT
    assert payload["status"] == "collecting"
    assert md_path.read_text(encoding="utf-8").endswith("\n")
    assert json_path.read_text(encoding="utf-8").endswith("\n")


def test_main_runs_from_repo_root_and_writes_both_outputs(tmp_path, monkeypatch):
    input_path = tmp_path / "gate_c.jsonl"
    input_path.write_text(json.dumps(graded_row("2026-07-20", "history one")) + "\n", encoding="utf-8")
    lock_history_to(monkeypatch, [graded_row("2026-07-20", "history one")])
    md_path = tmp_path / "result.md"
    json_path = tmp_path / "result.json"
    assert audit.main([
        "--input", str(input_path),
        "--output-md", str(md_path),
        "--output-json", str(json_path),
    ]) == 0
    assert md_path.exists()
    assert json_path.exists()
```

- [ ] **Step 5: Run reporting tests and verify RED**

Run:

```powershell
python -m pytest tests/test_no_drag_composite_canary_audit.py -q
```

Expected: failures identify absent slice, rendering, output, or CLI behavior.

- [ ] **Step 6: Implement all mandatory slices and output contracts**

Define exact dimensions:

```python
SLICE_DIMENSIONS = (
    "verdict_family",
    "side",
    "k_line",
    "price_sign",
    "price_bucket",
    "quality",
    "path_b",
    "model_market",
    "workload_leash",
    "market_anchor",
    "market_agreement",
    "preclose_clv_proxy",
    "final_clv",
    "provider_era",
    "provider_attribution",
    "recent_14_slates",
)
```

Bucket functions are exact:

- `verdict_family`: `FIRE`, `LEAN`, or `other` from frozen verdict precedence.
- `side`: normalized `over`/`under`, otherwise `missing`.
- `k_line`: `line_bucket`, otherwise `missing`.
- `price_sign`: `price_sign`, otherwise `missing`.
- `price_bucket`: `price_bucket`, otherwise `missing`.
- `quality`: `quality_gate_level`, otherwise `missing`.
- `path_b`: use `strong_base_decision_lab.path_b_coverage_bucket`.
- `model_market`: `model_market_relationship`, otherwise `missing`.
- `workload_leash`: first non-empty `leash_risk_bucket`/`opportunity_bucket`, otherwise `missing`.
- `market_anchor`: `market_anchor_strict`, else `market_anchor_core`, else `none`.
- `market_agreement`: `market_agreement_label`, otherwise `missing`.
- `preclose_clv_proxy`: use `gate_f_preclose_clv_proxy_lab.preclose_clv_proxy_label`.
- `final_clv`: use `strong_base_decision_lab.clv_bucket`; this is outcome-audit evidence only.
- `provider_era`: use `strong_base_decision_lab.provider_era`.
- `provider_attribution`: first non-empty `provider`/`live_display_provider`, otherwise `missing`; never substitute sportsbook/bookmaker for provider source.
- `recent_14_slates`: `included` for rows in the current recent window and `outside` for other combined rows.

Build slice scoreboards separately for `historical_rebuild`, `prospective`, and `combined`. For every dimension, count rows in the literal `missing` bucket and publish those counts under `integrity.slice_missing_coverage`. Do not silently exclude missing rows.

Callout logic is descriptive and must not become a hidden promotion gate:

```python
if status.startswith("blocked_"):
    callout = "integrity_block"
elif prospective_score["rows"] == 0:
    callout = "no_prospective_rows"
elif prospective_score["rows"] < 10:
    callout = "small_sample"
elif prospective_score["pnl"] > 0 and prospective_score["roi"] >= 0.10:
    callout = "positive_breakout_watch"
elif prospective_score["pnl"] < 0:
    callout = "deterioration_watch"
else:
    callout = "neutral_soak"
```

Mandatory-slice risks contain every bucket with at least 10 rows and negative PnL plus every nonzero missing-coverage count. Sort negative buckets by PnL ascending, then rows descending. These are reporting callouts only and cannot alter eligibility, the counter, or status.

The Markdown section order is exact: `Executive Read`, `Counter`, `Baseline Reconciliation`, `Prospective Evidence`, `Current Provider and Recent`, `Breakout or Deterioration`, `Mandatory Slice Risks`, `Slice Audit`, `Live Boundary`. The live boundary states that the audit cannot change live behavior and that promotion requires a separate Tyler-approved plan.

CLI flags are exact:

```python
parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
parser.add_argument("--output-md", type=Path, default=DEFAULT_OUTPUT_MD)
parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
```

`main` returns zero after writing both files even when status is blocked, because a fail-closed audit is a successful diagnostic run, not a process crash.

- [ ] **Step 7: Run the complete focused test file and verify GREEN**

Run:

```powershell
python -m pytest tests/test_no_drag_composite_canary_audit.py -q
```

Expected: all selector, integrity, accounting, slice, renderer, output, and CLI tests pass.

- [ ] **Step 8: Exercise the real default CLI against the committed stale Gate C artifact**

Run:

```powershell
python analytics/diagnostics/no_drag_composite_canary_audit.py
```

Expected: exit code zero; both output files are created; JSON status is `blocked_baseline_drift`; the report explains that the committed corpus does not reconcile and the counter remains 52/75. This is the expected local stale-input proof, not the production post-grading result.

- [ ] **Step 9: Commit Task 2**

```powershell
git add analytics/diagnostics/no_drag_composite_canary_audit.py tests/test_no_drag_composite_canary_audit.py
git commit -m "feat: add no-drag prospective canary audit"
```

The two `analytics/output` files are intentionally ignored runtime artifacts. Leave them untracked and do not use `git add -f`.

---

### Task 3: Integrate the Read-Only Post-Grading Runner

**Files:**

- Modify: `scripts/run_post_grading_shadow_reports.py`
- Modify: `tests/test_post_grading_shadow_reports.py`

**Interfaces:**

- Consumes: `no_drag_composite_canary_audit.main(argv)` and the Gate C dataset produced by `builder.main`.
- Produces: runner flags `--no-drag-canary-output-md` and `--no-drag-canary-output-json` and a log excerpt limited to `Executive Read`, `Counter`, and `Baseline Reconciliation`.

- [ ] **Step 1: Write the failing runner integration test**

Update the existing main runner test with paths, a fake audit writer, the expected call immediately after `shadow_signal_synthesis`, and excerpt assertions:

```python
no_drag_output_md = tmp_path / "no_drag_composite_canary_audit.md"
no_drag_output_json = tmp_path / "no_drag_composite_canary_audit.json"


def fake_no_drag_main(argv):
    calls.append(("no_drag_canary", argv))
    no_drag_output_md.write_text(
        "# No-Drag Composite Prospective Canary Audit\n\n"
        "## Executive Read\n\n"
        "- Status: `collecting`.\n\n"
        "## Counter\n\n"
        "- Counter: `52/75`; `23` remaining.\n\n"
        "## Baseline Reconciliation\n\n"
        "- Rebuilt history matches the locked baseline.\n\n"
        "## Slice Audit\n\n"
        "- Not needed in the scheduler excerpt.\n",
        encoding="utf-8",
    )
    no_drag_output_json.write_text("{}\n", encoding="utf-8")


monkeypatch.setattr(runner.no_drag_composite_canary_audit, "main", fake_no_drag_main)
```

Add these runner arguments:

```python
"--no-drag-canary-output-md", str(no_drag_output_md),
"--no-drag-canary-output-json", str(no_drag_output_json),
```

Expected call:

```python
(
    "no_drag_canary",
    [
        "--input",
        str(output_dir / "pitcher_k_outcome_dataset.jsonl"),
        "--output-md",
        str(no_drag_output_md),
        "--output-json",
        str(no_drag_output_json),
    ],
),
```

Assert the captured log contains `No-drag prospective canary excerpt:`, `Status: `collecting``, `52/75`, and `Rebuilt history matches`, while `Slice Audit` and `Not needed in the scheduler excerpt` are absent.

- [ ] **Step 2: Run the runner test and verify RED**

Run:

```powershell
python -m pytest tests/test_post_grading_shadow_reports.py -q
```

Expected: failure because the runner has no no-drag import, arguments, invocation, or excerpt.

- [ ] **Step 3: Add the smallest runner integration**

Add the import:

```python
from analytics.diagnostics import no_drag_composite_canary_audit  # noqa: E402
```

Add parser defaults:

```python
parser.add_argument(
    "--no-drag-canary-output-md",
    type=Path,
    default=no_drag_composite_canary_audit.DEFAULT_OUTPUT_MD,
)
parser.add_argument(
    "--no-drag-canary-output-json",
    type=Path,
    default=no_drag_composite_canary_audit.DEFAULT_OUTPUT_JSON,
)
```

Immediately after `shadow_signal_synthesis_lab.main(...)`, call:

```python
no_drag_composite_canary_audit.main([
    "--input",
    str(dataset_path),
    "--output-md",
    str(args.no_drag_canary_output_md),
    "--output-json",
    str(args.no_drag_canary_output_json),
])
```

After the existing Shadow Signal Synthesis excerpt, print:

```python
_print_review_excerpt(
    args.no_drag_canary_output_md,
    label="No-drag prospective canary",
    section_titles={"Executive Read", "Counter", "Baseline Reconciliation"},
)
```

Do not add a new environment variable, service, schedule, artifact field, database write, or external request.

- [ ] **Step 4: Run focused runner and diagnostic tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_no_drag_composite_canary_audit.py tests/test_post_grading_shadow_reports.py -q
```

Expected: both test files pass.

- [ ] **Step 5: Commit Task 3**

```powershell
git add scripts/run_post_grading_shadow_reports.py tests/test_post_grading_shadow_reports.py
git commit -m "feat: run no-drag audit after grading"
```

---

### Task 4: Publish the Research Packet and Update the Operating Board

**Files:**

- Create: `docs/research/no-drag-composite-prospective-canary-packet.md`
- Modify: `docs/current-state.md`

**Interfaces:**

- Consumes: selector ID, fingerprint, locked baselines, output paths, status rules, and the stale-local-versus-fresh-post-grading distinction from Tasks 1-3.
- Produces: the operator-facing decision packet and updated model-lane handoff.

- [ ] **Step 1: Write the new research packet**

The packet must contain these sections and facts:

```markdown
# No-Drag Composite Prospective Canary Packet

Date: 2026-07-21

Status: frozen post-grading research canary. This is not live promotion approval.

## Executive Decision

Track `combined_runtime_broad_no_hindsight_no_drag_v1` as the lead research candidate beginning with the 2026-07-21 slate. Preserve `strict_runtime_core_plus_selective_lean` as the comparison/control.

## Locked Baseline

| Read | Rows | Record | Units | ROI |
| --- | ---: | ---: | ---: | ---: |
| Clean window through 2026-07-20 | 186 | 124-62 | +29.20u | +15.7% |
| Current-provider starting point | 52 | 36-16 | +9.17u | +17.6% |
| Recent 14-slate reference | 35 | 24-11 | +5.68u | +16.2% |

The review floor is 75 current-provider candidate rows, so the prospective canary begins with 23 additional rows required.

## Frozen Contract

Record selector fingerprint `22b03ecea02aa83e9174c24f5f05878823cb67766fe1c75102d34bfe5c3b4aa4` and state that any semantic change requires a new ID, fingerprint, baseline, and counter.

## Daily Read

Read the Markdown/JSON audit after Gate C and Shadow Signal Synthesis. Treat duplicate keys, baseline drift, and prospective critical-input gaps as blocking integrity states. A stale committed Gate C file is expected to block locally; the scheduled post-grading builder must refresh the corpus before the production audit.

## Review Floor

At 75 rows the strongest allowed status is `ready_for_review`. Promotion still requires a separate Tyler-approved plan and survival across FIRE/LEAN, side, K-line, price, quality, Path B, model/market, workload, market agreement, pre-close proxy, final CLV, provider, and rolling-window slices.

## Live Boundary

The canary cannot change model math, verdicts, thresholds, staking, providers, notifications, locks, UI, retention, artifacts, calibration, source-of-truth behavior, environment variables, or `formula_change_date`.
```

- [ ] **Step 2: Update the Four-Lane Operating Board model row**

Add `2026-07-21-no-drag-composite-prospective-canary.md` to the model lane's Current Source list. Replace the stale statement that strict-plus-selective is the preferred candidate with a concise overlay:

```markdown
As of 2026-07-21, Tyler approved the post-grading-only prospective canary for `combined_runtime_broad_no_hindsight_no_drag_v1`. Its locked clean-window baseline is `186` rows, `124-62`, `+29.20u`, `+15.7%`; its locked current-provider start is `52` rows, `36-16`, `+9.17u`, leaving `23` prospective rows to the `75`-row review floor. The diagnostic can only become `ready_for_review`; it cannot promote itself. `strict_runtime_core_plus_selective_lean` remains the comparison/control rather than the lead candidate.
```

Update the model lane's Next Decision to read the new Markdown/JSON audit after each graded slate, resolve any integrity block before trusting the counter, and keep every live gate closed until a separate review plan is approved.

- [ ] **Step 3: Verify documentation and guardrails**

Run:

```powershell
rg -n "combined_runtime_broad_no_hindsight_no_drag_v1|124-62|29.20u|52|23|ready_for_review|strict_runtime_core_plus_selective_lean" docs/research/no-drag-composite-prospective-canary-packet.md docs/current-state.md
rg -n "OFFICIAL_MARKET_SOURCE|LIVE_|formula_change_date|staking|notification|lock|retention" analytics/diagnostics/no_drag_composite_canary_audit.py scripts/run_post_grading_shadow_reports.py
git diff --check
```

Expected: the packet and board contain the frozen ID/baselines/countdown and keep the prior candidate as control; code references only explanatory live-boundary language and introduces no live flag or behavior; `git diff --check` is clean.

- [ ] **Step 4: Run the full relevant regression suite**

Run:

```powershell
python -m pytest tests/test_no_drag_composite_canary_audit.py tests/test_post_grading_shadow_reports.py tests/test_shadow_signal_synthesis_lab.py tests/test_strong_base_decision_lab.py tests/test_pitcher_k_outcome_dataset.py -q
```

Expected: all selected diagnostic, runner, synthesis, Strong Base, and Gate C tests pass.

- [ ] **Step 5: Commit Task 4**

```powershell
git add docs/research/no-drag-composite-prospective-canary-packet.md docs/current-state.md
git commit -m "docs: activate no-drag research canary"
```

---

## Final Verification

After all task reviews are clean:

1. Run the full Python suite from the isolated worktree:

   ```powershell
   python -m pytest tests/ -q
   ```

2. Run syntax and whitespace checks:

   ```powershell
   python -m py_compile analytics/diagnostics/no_drag_composite_canary_audit.py scripts/run_post_grading_shadow_reports.py
   git diff --check main...HEAD
   ```

3. Run the diagnostic from the repository root and inspect both outputs:

   ```powershell
   python analytics/diagnostics/no_drag_composite_canary_audit.py
   python -c "import json; p=json.load(open('analytics/output/no_drag_composite_canary_audit.json', encoding='utf-8')); print(p['status'], p['counter'])"
   ```

   With the currently committed stale Gate C corpus, the expected local result is `blocked_baseline_drift` and a counter held at 52. Do not misreport this as the fresh post-grading production result.

4. Confirm scope by inspecting changed files:

   ```powershell
   git status --short
   git diff --stat main...HEAD
   git diff --name-only main...HEAD
   ```

   Expected changed scope: one diagnostic, two focused test files, one existing runner, one new research packet, and `docs/current-state.md`. The two generated analytics outputs remain ignored runtime files and must not appear in the branch diff. No pipeline model, dashboard, provider, notification, lock, migration, environment, or retention file may appear.

5. Dispatch a whole-branch reviewer on the complete `main...HEAD` review package. Fix and re-review every Critical or Important finding before presenting integration options.

6. Do not deploy from the implementation branch. After Tyler chooses integration and the reviewed branch reaches `main`, the separate approved operational step is to redeploy only `bbe-gate-c-post-grading-review`, preserve its command/schedule/environment/read-only posture, run one verification job, and confirm the refreshed audit starts at 52 with 23 remaining without changing live artifacts or notifications.

## Operational Verification (2026-07-22)

- Redeployed only `bbe-gate-c-post-grading-review` from current `main` as
  `dep-d9ge7o3tqb8s73cqjq1g`; its existing schedule, command, environment, and
  read-only posture were preserved.
- Verification job `job-d9ge8j4m0tmc73eota20` succeeded and rebuilt Gate C at
  3,134 source rows / 1,635 tracked rows with zero duplicate keys.
- The frozen canary reconciled both the 186-row historical baseline and the
  52-row current-provider starting baseline. It credited two qualified
  prospective rows and reported `collecting` at `54/75`, with 21 rows
  remaining.
- This is counter progress only. It does not authorize a model, verdict,
  threshold, staking, provider, notification, lock, UI, artifact, or retention
  change; `ready_for_review` remains the strongest possible future status.

## Research Outcome-Recovery Boundary (2026-07-23)

Gate C exact-outcome recovery can add retrospective rows that were absent from
the frozen no-drag baseline. Those rows now carry
`archive_outcome_reconciliation_source=picks_history_exact`.

The no-drag audit excludes every such row from both the frozen historical
rebuild and prospective counter. This is an input-boundary guard only:

- selector id/version and rule fingerprint remain unchanged;
- locked baselines remain `186` historical and `52` current-provider rows;
- history-recovered rows receive no historical or prospective credit; and
- normal prospectively collected graded rows continue to advance the counter.

Live temporary verification excluded `24` history-recovered rows, reconciled
both locked baselines, preserved fingerprint
`22b03ecea02aa83e9174c24f5f05878823cb67766fe1c75102d34bfe5c3b4aa4`,
and reported `collecting` at `58/75` with `17` remaining. The six qualified
prospective rows are `4-2`, `+0.69u`, `+11.4%` ROI. This is counter progress
only; all live promotion gates remain closed.

The deployed compact-input research run at `2026-07-23T17:16:27Z` preserved
rule fingerprint
`22b03ecea02aa83e9174c24f5f05878823cb67766fe1c75102d34bfe5c3b4aa4`,
reconciled both locked baselines, excluded the same `24` history-recovered
rows, and remained `collecting` at `58/75` with `17` remaining. The deployment
did not backfill or advance the prospective counter.
