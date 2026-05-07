# Bet Conversion Shadow Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shadow-only diagnostic that compares alternative bet-selection signals before any live threshold, staking, or projection changes.

**Architecture:** Add one standalone analytics diagnostic that reads `data/picks_history.json`, filters to clean `2026-04-28+` win/loss rows, and compares flat 1u performance for current FIRE selection, adjusted EV buckets, edge buckets, model-margin buckets, and side-specific slices. The diagnostic writes a markdown report under `analytics/output/` and is excluded from pipeline behavior.

**Tech Stack:** Python 3.11, pytest, committed JSON history, existing `analytics/diagnostics` patterns.

---

## File Plan

- Create `analytics/diagnostics/bet_conversion_shadow_audit.py`
  - Load pick history.
  - Filter clean win/loss rows.
  - Compute picked-side model margin.
  - Evaluate named shadow strategies with flat 1u accounting.
  - Render a markdown report with recommendation framing.
- Create `tests/test_bet_conversion_shadow_audit.py`
  - Pin clean-window filtering.
  - Pin model-margin math for over and under picks.
  - Pin flat 1u strategy accounting.
  - Pin report sections and strategy names.
- Write generated output to `analytics/output/bet_conversion_shadow_audit.md`
  - Local analysis artifact only.

## Guardrails

- Do not change `pipeline/`.
- Do not change `data/params.json`.
- Do not change verdict thresholds.
- Do not change staking.
- Do not change provider order.
- Do not write anything that the dashboard reads as a live contract.

## Task 1: Write Tests First

**Files:**
- Create: `tests/test_bet_conversion_shadow_audit.py`
- Future implementation: `analytics/diagnostics/bet_conversion_shadow_audit.py`

- [ ] **Step 1: Add tests for clean filtering and model margin**

```python
from analytics.diagnostics.bet_conversion_shadow_audit import (
    clean_win_loss_rows,
    picked_side_model_margin,
)


def test_clean_win_loss_rows_keeps_only_post_cutover_win_loss_rows():
    rows = [
        {"date": "2026-04-27", "result": "win", "pitcher": "Transition"},
        {"date": "2026-04-28", "result": "void", "pitcher": "Void"},
        {"date": "2026-04-28", "result": "win", "pitcher": "Clean Win"},
        {"date": "2026-05-07", "result": None, "pitcher": "Open"},
    ]

    filtered = clean_win_loss_rows(rows)

    assert [row["pitcher"] for row in filtered] == ["Clean Win"]


def test_picked_side_model_margin_supports_over_and_under():
    over = {"side": "over", "k_line": 4.5, "applied_lambda": 5.25}
    under = {"side": "under", "k_line": 5.5, "applied_lambda": 4.75}

    assert picked_side_model_margin(over) == 0.75
    assert picked_side_model_margin(under) == 0.75
```

- [ ] **Step 2: Add tests for flat 1u strategy summaries**

```python
from analytics.diagnostics.bet_conversion_shadow_audit import summarize_strategy


def test_summarize_strategy_uses_flat_one_unit_pnl():
    rows = [
        {"result": "win", "pnl": 0.91, "verdict": "FIRE 1u"},
        {"result": "loss", "pnl": -1.0, "verdict": "FIRE 2u"},
        {"result": "win", "pnl": 0.83, "verdict": "LEAN"},
    ]

    summary = summarize_strategy(
        "current_fire_flat",
        rows,
        lambda row: str(row.get("verdict", "")).startswith("FIRE"),
    )

    assert summary["selected"] == 2
    assert summary["wins"] == 1
    assert summary["losses"] == 1
    assert summary["flat_pnl"] == -0.09
    assert summary["flat_roi"] == -0.045
```

- [ ] **Step 3: Add tests for the report contract**

```python
from analytics.diagnostics.bet_conversion_shadow_audit import build_report


def test_build_report_includes_shadow_strategy_sections():
    rows = [
        {
            "date": "2026-04-28",
            "result": "win",
            "pnl": 0.91,
            "verdict": "FIRE 2u",
            "edge": 0.05,
            "adj_ev": 0.19,
            "side": "under",
            "k_line": 5.5,
            "applied_lambda": 4.8,
            "quality_gate_level": "clean",
        }
    ]

    report = build_report(rows)

    assert "# Bet Conversion Shadow Audit" in report
    assert "`current_fire_flat`" in report
    assert "`edge_4_to_6`" in report
    assert "`adj_ev_17_plus`" in report
    assert "`current_fire_under`" in report
```

- [ ] **Step 4: Run tests and confirm they fail because the module does not exist**

Run:

```bash
python -m pytest tests/test_bet_conversion_shadow_audit.py -q
```

Expected:

```text
ModuleNotFoundError: No module named 'analytics.diagnostics.bet_conversion_shadow_audit'
```

## Task 2: Implement The Diagnostic

**Files:**
- Create: `analytics/diagnostics/bet_conversion_shadow_audit.py`
- Test: `tests/test_bet_conversion_shadow_audit.py`

- [ ] **Step 1: Implement data loading and clean filtering**

```python
ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT / "data" / "picks_history.json"
CLEAN_WINDOW_START = "2026-04-28"
WIN_LOSS_RESULTS = {"win", "loss"}
```

Implement `load_history(path=HISTORY_PATH)` and `clean_win_loss_rows(rows)`.

- [ ] **Step 2: Implement numeric helpers and model margin**

Implement:

```python
def to_float(value: object) -> float | None:
    ...

def current_adj_ev(row: dict) -> float | None:
    ...

def current_projection(row: dict) -> float | None:
    ...

def picked_side_model_margin(row: dict) -> float | None:
    ...
```

Expected:

- Use `locked_adj_ev` before `adj_ev`.
- Use `applied_lambda`, then `raw_lambda`, then `lambda`, then `projected_ks`.
- For over picks, margin is `projection - k_line`.
- For under picks, margin is `k_line - projection`.

- [ ] **Step 3: Implement strategy accounting**

Implement `summarize_strategy(name, rows, predicate)` with flat 1u accounting:

```python
{
    "name": name,
    "selected": 2,
    "wins": 1,
    "losses": 1,
    "flat_units": 2.0,
    "flat_pnl": -0.09,
    "flat_roi": -0.045,
    "current_fire_1u_losses_selected": 0,
    "current_fire_2u_wins_selected": 1,
}
```

- [ ] **Step 4: Implement default shadow strategies**

Include:

```text
current_fire_flat
current_fire_over
current_fire_under
adj_ev_6_to_17
adj_ev_17_plus
edge_2_to_4
edge_4_to_6
edge_6_plus
model_margin_0_to_0_75
model_margin_0_75_to_1_5
model_margin_1_5_plus
clean_quality_fire
capped_quality_fire
```

- [ ] **Step 5: Render the markdown report**

Report must include:

- scope counts
- strategy comparison table
- side-specific warning
- recommended next read
- explicit line that this is shadow-only and not a live change

- [ ] **Step 6: Run focused tests**

Run:

```bash
python -m pytest tests/test_bet_conversion_shadow_audit.py -q
```

Expected: all tests pass.

## Task 3: Generate The Current Report

**Files:**
- Read: `data/picks_history.json`
- Write local-only: `analytics/output/bet_conversion_shadow_audit.md`

- [ ] **Step 1: Generate report**

Run:

```bash
python analytics/diagnostics/bet_conversion_shadow_audit.py > analytics/output/bet_conversion_shadow_audit.md
```

- [ ] **Step 2: Read the report**

Run:

```bash
Get-Content analytics/output/bet_conversion_shadow_audit.md
```

Expected:

- The report shows `206` clean win/loss rows.
- It compares current FIRE rows against edge, adjusted EV, model-margin, and quality-gate slices.
- It does not recommend a live change.

## Task 4: Verification

**Files:**
- Test: `tests/test_bet_conversion_shadow_audit.py`
- Existing diagnostic tests: `tests/test_e4_bet_selection_audit.py`

- [ ] **Step 1: Run focused tests**

```bash
python -m pytest tests/test_bet_conversion_shadow_audit.py tests/test_e4_bet_selection_audit.py -q
```

- [ ] **Step 2: Check git diff**

```bash
git diff --check
git status --short
```

Expected:

- No whitespace errors.
- Only the new plan, diagnostic, test, and generated analytics report are modified.
