# Workload And No-Vig K Projection EV Synthesis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shadow-only evaluation package that tests whether BaseballBettingEdge should improve K projection and EV selection by adding workload/opportunity proxies, no-vig market comparison, and Path B/referee interaction slices before any live model change.

**Architecture:** Keep the current live lambda, confidence referee, Path B handedness canary, provider order, staking, thresholds, and dashboard source-of-truth unchanged. Reuse the durable Gate C pitcher outcome dataset as the row source, then add one focused diagnostic report that compares current model output against workload-adjusted and no-vig EV candidate labels. Treat full batter-by-batter simulation and pitch-mix/stuff models as later Gate E/F candidates only after the cheaper shadow evidence proves they are worth the added data/source complexity.

**Tech Stack:** Python 3.11, pytest, existing `data/research/gate_c/pitcher_k_outcome_dataset.jsonl`, `analytics/diagnostics/`, `analytics/output/`, Render/Netlify artifacts only for existing source data.

---

## Operating Decision

This is a child plan of `docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`.

The outside K-projection deep dive is directionally useful, but it should not trigger a model rewrite. The practical synthesis for this repo is:

- Current live projection is still a calibrated K/9-to-Poisson lambda model.
- The strongest near-term gap is workload/opportunity structure, not a broad projection collapse.
- The strongest EV gap is selection and price conversion, especially FIRE unders and high adjusted-EV buckets.
- Path B handedness and the confidence referee are already active feature-flagged canaries, so new research must measure their interaction with workload/no-vig signals instead of creating competing rules.
- Gate E and Gate F remain relevant. They should not be removed; they should be used as the promotion discipline for each candidate family.

## Gate Interpretation

Keep the existing Gate C -> Gate D -> Gate E -> Gate F ladder.

| Gate | Still Relevant? | Updated Role |
| --- | --- | --- |
| Gate C | Yes | Compact evidence, runtime-safe field labeling, no-leakage boundaries, and candidate report clarity. |
| Gate D | Yes | Daily collection proof across clean graded slates, including Path B/referee/workload/no-vig labels with zero duplicate keys. |
| Gate E | Yes | Research readiness: enough rows and stable slices to take a candidate seriously. Applies separately to workload, no-vig EV, referee v2, Path B, and projection challengers. |
| Gate F | Yes | Promotion-candidate proof: holdout lift, rolling windows, side/price/line/provider/quality slices, no FIRE 2u degradation, runtime-safe inputs, and rollback plan. |

Do not add a new Gate G. If a candidate cannot satisfy Gate E/F, it stays shadow-only even if it is conceptually appealing.

## What To Adopt From The Deep Dive

Adopt now, in shadow:

- Workload-first framing: separate K opportunity from K skill.
- No-vig market comparison: compare model probability to two-sided market probability, not only the selected side's offered odds.
- Sensitivity labels: identify rows where a small workload shift changes the verdict/side.
- Confirmed-lineup interaction: measure Path B rows separately from Path A/fallback rows.
- Distribution awareness: report when Poisson mean is fragile around 4.5, 5.5, 6.5, and 7.5 key lines.

Defer until cheaper evidence justifies it:

- Full batter-by-batter simulation.
- Pitch-level pitch-mix/arsenal whiff matching.
- Stuff+/PitchingBot-style external inputs.
- Bullpen/rest/game-script modeling from new data providers.
- Any live EV threshold, staking, or lambda change.

## Candidate Families

### Candidate Family 1: Workload/Opportunity Proxy

Shadow question: does the model lose because it overstated or understated opportunity?

Use only fields already present or cheaply derivable:

- `avg_ip`
- `recent_start_count`
- `last_pitch_count`
- `opportunity_bucket`
- `leash_risk_bucket`
- `pitcher_archetype_bucket`
- `quality_gate_level`
- `lineup_used`
- `batter_handedness_mode`
- `lineup_split_source`

First candidate labels:

- `workload_stable`: normal leash, normal opportunity, mature starter.
- `workload_fragile_under`: high/medium leash risk, short-leash, opener risk, low recent start count, or capped quality.
- `workload_fragile_over`: projected over depends on high opportunity, deep starter assumption, or high K line.
- `workload_sensitivity_half_k`: current side would change if projected Ks moved 0.5 toward the line.
- `workload_sensitivity_one_k`: current side would change if projected Ks moved 1.0 toward the line.

### Candidate Family 2: No-Vig EV Gate

Shadow question: are current FIRE/LEAN rows truly beating the market, or only looking good because of plus-price payout math?

Use existing research fields:

- `model_win_prob`
- `no_vig_side_probability`
- `model_no_vig_gap`
- `american_odds`
- `price_sign`
- `market_favorite_side`
- `model_market_relationship`
- `verdict`
- `quality_gate_level`

First candidate labels:

- `no_vig_confirmed_edge`: model no-vig gap >= 0.04.
- `no_vig_thin_edge`: model no-vig gap between 0.02 and 0.04.
- `no_vig_price_only_edge`: positive offered-odds EV but model no-vig gap < 0.02.
- `no_vig_market_disagrees`: model fades market favorite and no-vig gap < 0.04.
- `no_vig_referee_agrees`: confidence referee cap aligns with thin/no-vig market disagreement.
- `no_vig_referee_disagrees`: confidence referee cap suppresses a row that later had strong no-vig/CLV support.

### Candidate Family 3: Path B Handedness Interaction

Shadow question: does Path B improve projection or selection when it has real runtime split coverage?

Keep Path B feature-flagged and runtime-safe:

- `BATTER_HANDEDNESS_MODE=path_b` may use live-collected, PA-backed split samples.
- Historical boxscore handedness reconstruction remains research-only.
- Missing or untrusted batter splits must fall back per batter to Path A.

Report slices:

- `batter_handedness_mode`
- `lineup_split_source`
- `lineup_real_split_count`
- `lineup_path_a_fallback_count`
- Path B rows with 0, 1-4, 5-8, and 9 real splits
- confidence-referee capped rows by Path B coverage bucket
- no-vig edge rows by Path B coverage bucket

### Candidate Family 4: Referee V2 Questions

Shadow question: did the enforced confidence referee cap the right rows?

The current referee is already live as verdict-conversion only. This plan does not change it. The diagnostic should only label:

- capped row later confirmed by no-vig/CLV/workload risk
- capped row later contradicted by no-vig/CLV/workload support
- uncapped row with workload/no-vig warning
- market-favorite agreement row with weak workload support

If a referee v2 candidate emerges, it still needs Gate E/F and a separate production canary plan.

## Non-Goals

- Do not change `pipeline/build_features.py` live lambda.
- Do not change `pipeline/confidence_referee.py` behavior.
- Do not change `data/params.json`, `formula_change_date`, global thresholds, or staking.
- Do not change provider order, `OFFICIAL_MARKET_SOURCE`, `OFFICIAL_MARKET_STRICT`, locks, notifications, retention, or dashboard source-of-truth.
- Do not use actual Ks, PnL, CLV, close price, actual pitch count, or batters faced as pre-lock inputs.
- Do not use historical handedness backfill as live Path B input.
- Do not add new external paid data or higher polling cadence.

## File Map

- Modify: `analytics/diagnostics/pitcher_k_outcome_dataset.py`
  - Ensure no-vig fields and existing workload/path-b fields are exposed consistently in rows.
- Create: `analytics/diagnostics/workload_no_vig_ev_audit.py`
  - Build workload, no-vig, Path B, and referee interaction labels from the Gate C dataset.
- Create: `tests/test_workload_no_vig_ev_audit.py`
  - Unit tests for no-vig labels, workload sensitivity labels, Path B buckets, and referee interaction labels.
- Create: `analytics/output/workload_no_vig_ev_audit.md`
  - Shadow report with decision summary and candidate family scoreboards.
- Modify: `scripts/build_pitcher_k_outcome_dataset.py`
  - Optionally call the new audit after dataset rebuild only if a flag is passed.
- Modify: `docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`
  - Register this child plan and clarify Gate E/F relevance.
- Modify: `docs/current-state.md`
  - Add this child plan to the model lane and next decision.
- Modify: BBE Operations Brief automation memory
  - Carry the new daily read focus forward.

## Task 1: Add Workload/No-Vig Audit Helpers

**Files:**
- Create: `analytics/diagnostics/workload_no_vig_ev_audit.py`
- Create: `tests/test_workload_no_vig_ev_audit.py`

- [ ] **Step 1: Write failing tests for no-vig labels**

Add this test file:

```python
from analytics.diagnostics import workload_no_vig_ev_audit as audit


def test_no_vig_labels_confirmed_thin_and_price_only_edges():
    assert audit.no_vig_edge_label({"model_no_vig_gap": 0.05, "ev": 0.08}) == "no_vig_confirmed_edge"
    assert audit.no_vig_edge_label({"model_no_vig_gap": 0.025, "ev": 0.08}) == "no_vig_thin_edge"
    assert audit.no_vig_edge_label({"model_no_vig_gap": 0.005, "ev": 0.08}) == "no_vig_price_only_edge"
    assert audit.no_vig_edge_label({"model_no_vig_gap": -0.01, "ev": -0.02}) == "no_vig_no_edge"


def test_no_vig_missing_values_stay_unknown():
    assert audit.no_vig_edge_label({"model_no_vig_gap": None, "ev": 0.08}) == "unknown"
```

- [ ] **Step 2: Run the failing tests**

Run:

```powershell
python -m pytest tests/test_workload_no_vig_ev_audit.py -q
```

Expected: fail because `analytics.diagnostics.workload_no_vig_ev_audit` does not exist.

- [ ] **Step 3: Create the minimal helper module**

Create `analytics/diagnostics/workload_no_vig_ev_audit.py`:

```python
from __future__ import annotations

from typing import Any


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number


def no_vig_edge_label(row: dict[str, Any]) -> str:
    gap = _to_float(row.get("model_no_vig_gap"))
    ev = _to_float(row.get("ev") or row.get("adj_ev"))
    if gap is None:
        return "unknown"
    if gap >= 0.04:
        return "no_vig_confirmed_edge"
    if gap >= 0.02:
        return "no_vig_thin_edge"
    if ev is not None and ev > 0:
        return "no_vig_price_only_edge"
    return "no_vig_no_edge"
```

- [ ] **Step 4: Verify the helper tests pass**

Run:

```powershell
python -m pytest tests/test_workload_no_vig_ev_audit.py -q
```

Expected: all tests pass.

## Task 2: Add Workload Sensitivity Labels

**Files:**
- Modify: `analytics/diagnostics/workload_no_vig_ev_audit.py`
- Modify: `tests/test_workload_no_vig_ev_audit.py`

- [ ] **Step 1: Add failing tests for sensitivity labels**

Append:

```python
def test_workload_sensitivity_labels_use_projection_margin():
    assert audit.workload_sensitivity_label({"k_margin_to_line": 0.25}) == "workload_sensitivity_half_k"
    assert audit.workload_sensitivity_label({"k_margin_to_line": 0.75}) == "workload_sensitivity_one_k"
    assert audit.workload_sensitivity_label({"k_margin_to_line": 1.25}) == "workload_stable_margin"


def test_workload_risk_label_uses_existing_opportunity_fields():
    row = {"leash_risk_bucket": "high", "opportunity_bucket": "short_leash", "quality_gate_level": "capped"}
    assert audit.workload_risk_label(row) == "workload_fragile"

    row = {"leash_risk_bucket": "normal", "opportunity_bucket": "normal", "quality_gate_level": "clean"}
    assert audit.workload_risk_label(row) == "workload_stable"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_workload_no_vig_ev_audit.py -q
```

Expected: fail because the workload helper functions do not exist.

- [ ] **Step 3: Implement workload labels**

Append to `analytics/diagnostics/workload_no_vig_ev_audit.py`:

```python
def workload_sensitivity_label(row: dict[str, Any]) -> str:
    margin = _to_float(row.get("k_margin_to_line"))
    if margin is None:
        return "unknown"
    margin = abs(margin)
    if margin < 0.5:
        return "workload_sensitivity_half_k"
    if margin < 1.0:
        return "workload_sensitivity_one_k"
    return "workload_stable_margin"


def workload_risk_label(row: dict[str, Any]) -> str:
    leash = str(row.get("leash_risk_bucket") or "").lower()
    opportunity = str(row.get("opportunity_bucket") or "").lower()
    gate = str(row.get("quality_gate_level") or "").lower()
    archetype = str(row.get("pitcher_archetype_bucket") or "").lower()
    if leash in {"high", "medium"}:
        return "workload_fragile"
    if opportunity == "short_leash" or archetype == "short_leash":
        return "workload_fragile"
    if gate in {"capped", "blocked"}:
        return "workload_watch"
    return "workload_stable"
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_workload_no_vig_ev_audit.py -q
```

Expected: all tests pass.

## Task 3: Add Path B And Referee Interaction Labels

**Files:**
- Modify: `analytics/diagnostics/workload_no_vig_ev_audit.py`
- Modify: `tests/test_workload_no_vig_ev_audit.py`

- [ ] **Step 1: Add failing tests**

Append:

```python
def test_path_b_coverage_bucket_uses_real_split_count():
    assert audit.path_b_coverage_bucket({"batter_handedness_mode": "path_b", "lineup_real_split_count": 0}) == "path_b_zero_real_splits"
    assert audit.path_b_coverage_bucket({"batter_handedness_mode": "path_b", "lineup_real_split_count": 4}) == "path_b_partial_real_splits"
    assert audit.path_b_coverage_bucket({"batter_handedness_mode": "path_b", "lineup_real_split_count": 9}) == "path_b_full_real_splits"
    assert audit.path_b_coverage_bucket({"batter_handedness_mode": "path_a", "lineup_real_split_count": 9}) == "path_a_or_unknown"


def test_referee_interaction_label_compares_cap_to_no_vig_and_workload():
    capped = {"confidence_referee": {"applied": True}, "model_no_vig_gap": 0.01, "leash_risk_bucket": "high"}
    assert audit.referee_interaction_label(capped) == "referee_cap_supported_by_no_vig_or_workload"

    contradicted = {"confidence_referee": {"applied": True}, "model_no_vig_gap": 0.05, "leash_risk_bucket": "normal"}
    assert audit.referee_interaction_label(contradicted) == "referee_cap_contradicted_by_no_vig"

    uncapped = {"confidence_referee": {"applied": False}, "model_no_vig_gap": 0.01, "leash_risk_bucket": "high"}
    assert audit.referee_interaction_label(uncapped) == "uncapped_row_with_shadow_warning"
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```powershell
python -m pytest tests/test_workload_no_vig_ev_audit.py -q
```

Expected: fail because the helper functions do not exist.

- [ ] **Step 3: Implement interaction labels**

Append:

```python
def path_b_coverage_bucket(row: dict[str, Any]) -> str:
    if str(row.get("batter_handedness_mode") or "").lower() != "path_b":
        return "path_a_or_unknown"
    count = int(_to_float(row.get("lineup_real_split_count")) or 0)
    if count <= 0:
        return "path_b_zero_real_splits"
    if count < 9:
        return "path_b_partial_real_splits"
    return "path_b_full_real_splits"


def _referee_applied(row: dict[str, Any]) -> bool:
    referee = row.get("confidence_referee")
    return isinstance(referee, dict) and referee.get("applied") is True


def referee_interaction_label(row: dict[str, Any]) -> str:
    applied = _referee_applied(row)
    no_vig = no_vig_edge_label(row)
    workload = workload_risk_label(row)
    has_warning = no_vig in {"no_vig_price_only_edge", "no_vig_no_edge"} or workload == "workload_fragile"
    has_confirmed_edge = no_vig == "no_vig_confirmed_edge"
    if applied and has_confirmed_edge and workload != "workload_fragile":
        return "referee_cap_contradicted_by_no_vig"
    if applied and has_warning:
        return "referee_cap_supported_by_no_vig_or_workload"
    if not applied and has_warning:
        return "uncapped_row_with_shadow_warning"
    return "referee_neutral"
```

- [ ] **Step 4: Run tests**

Run:

```powershell
python -m pytest tests/test_workload_no_vig_ev_audit.py -q
```

Expected: all tests pass.

## Task 4: Build The Markdown Report

**Files:**
- Modify: `analytics/diagnostics/workload_no_vig_ev_audit.py`
- Modify: `tests/test_workload_no_vig_ev_audit.py`
- Create: `analytics/output/workload_no_vig_ev_audit.md`

- [ ] **Step 1: Add report-rendering tests**

Append:

```python
def test_build_summary_counts_candidate_labels():
    rows = [
        {"model_no_vig_gap": 0.05, "ev": 0.08, "k_margin_to_line": 0.4, "leash_risk_bucket": "normal", "opportunity_bucket": "normal", "quality_gate_level": "clean", "result": "win", "pnl": 1.0},
        {"model_no_vig_gap": 0.005, "ev": 0.08, "k_margin_to_line": 0.3, "leash_risk_bucket": "high", "opportunity_bucket": "short_leash", "quality_gate_level": "capped", "result": "loss", "pnl": -1.0},
    ]
    summary = audit.build_summary(rows)
    assert summary["total_rows"] == 2
    assert summary["no_vig_labels"]["no_vig_confirmed_edge"]["rows"] == 1
    assert summary["workload_risk_labels"]["workload_fragile"]["rows"] == 1


def test_render_report_keeps_shadow_warning_and_gate_e_f_language():
    summary = {
        "total_rows": 0,
        "no_vig_labels": {},
        "workload_risk_labels": {},
        "workload_sensitivity_labels": {},
        "path_b_coverage_buckets": {},
        "referee_interaction_labels": {},
    }
    report = audit.render_report(summary)
    assert "Shadow-only" in report
    assert "Gate E" in report
    assert "Gate F" in report
```

- [ ] **Step 2: Implement summary/render helpers**

Append:

```python
from collections import defaultdict


def _empty_bucket() -> dict[str, float | int]:
    return {"rows": 0, "wins": 0, "losses": 0, "pnl": 0.0}


def _add_result(bucket: dict[str, float | int], row: dict[str, Any]) -> None:
    bucket["rows"] += 1
    if row.get("result") == "win":
        bucket["wins"] += 1
    elif row.get("result") == "loss":
        bucket["losses"] += 1
    pnl = _to_float(row.get("pnl") or row.get("theoretical_pnl")) or 0.0
    bucket["pnl"] = round(float(bucket["pnl"]) + pnl, 3)


def _summarize_by(rows: list[dict[str, Any]], label_fn) -> dict[str, dict[str, float | int]]:
    buckets: dict[str, dict[str, float | int]] = defaultdict(_empty_bucket)
    for row in rows:
        _add_result(buckets[label_fn(row)], row)
    return dict(sorted(buckets.items()))


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total_rows": len(rows),
        "no_vig_labels": _summarize_by(rows, no_vig_edge_label),
        "workload_risk_labels": _summarize_by(rows, workload_risk_label),
        "workload_sensitivity_labels": _summarize_by(rows, workload_sensitivity_label),
        "path_b_coverage_buckets": _summarize_by(rows, path_b_coverage_bucket),
        "referee_interaction_labels": _summarize_by(rows, referee_interaction_label),
    }


def _render_bucket_table(lines: list[str], title: str, buckets: dict[str, dict[str, float | int]]) -> None:
    lines.append(f"## {title}")
    lines.append("")
    lines.append("| Bucket | Rows | W-L | PnL |")
    lines.append("| --- | ---: | ---: | ---: |")
    if not buckets:
        lines.append("| -- | 0 | 0-0 | +0.00 |")
        lines.append("")
        return
    for label, bucket in buckets.items():
        pnl = float(bucket["pnl"])
        lines.append(f"| `{label}` | {bucket['rows']} | {bucket['wins']}-{bucket['losses']} | {pnl:+.2f} |")
    lines.append("")


def render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Workload And No-Vig EV Audit",
        "",
        "Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, locks, retention, calibration, or dashboard source-of-truth.",
        "",
        f"- Total rows: `{summary.get('total_rows', 0)}`",
        "",
        "## Gate Read",
        "",
        "- Gate E remains the research-readiness gate for candidate families.",
        "- Gate F remains the promotion-candidate gate; no bucket from this report can promote without holdout, slices, and a rollback plan.",
        "",
    ]
    _render_bucket_table(lines, "No-Vig Labels", summary.get("no_vig_labels", {}))
    _render_bucket_table(lines, "Workload Risk Labels", summary.get("workload_risk_labels", {}))
    _render_bucket_table(lines, "Workload Sensitivity Labels", summary.get("workload_sensitivity_labels", {}))
    _render_bucket_table(lines, "Path B Coverage Buckets", summary.get("path_b_coverage_buckets", {}))
    _render_bucket_table(lines, "Referee Interaction Labels", summary.get("referee_interaction_labels", {}))
    return "\n".join(lines).rstrip() + "\n"
```

- [ ] **Step 3: Add CLI entrypoint**

Append:

```python
import argparse
import json
from pathlib import Path


DEFAULT_INPUT = Path("data/research/gate_c/pitcher_k_outcome_dataset.jsonl")
DEFAULT_OUTPUT = Path("analytics/output/workload_no_vig_ev_audit.md")


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)

    rows = load_rows(Path(args.input))
    report = render_report(build_summary(rows))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    print(f"Wrote {output} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests and generate report**

Run:

```powershell
python -m pytest tests/test_workload_no_vig_ev_audit.py -q
python analytics/diagnostics/workload_no_vig_ev_audit.py
```

Expected: tests pass and `analytics/output/workload_no_vig_ev_audit.md` is written.

## Task 5: Wire Optional Report Build Into Gate C Refresh

**Files:**
- Modify: `scripts/build_pitcher_k_outcome_dataset.py`
- Modify: `tests/test_build_pitcher_k_outcome_dataset.py`

- [ ] **Step 1: Add CLI flag test**

Add a test that invokes the script argument parser with:

```powershell
python scripts/build_pitcher_k_outcome_dataset.py --artifact-source hybrid --output-dir data/research/gate_c --run-workload-no-vig-audit
```

Expected behavior: the dataset still builds first, then the workload/no-vig audit runs against the freshly written dataset.

- [ ] **Step 2: Implement `--run-workload-no-vig-audit`**

Import the audit module only inside the flag path so normal Gate C builds stay unchanged:

```python
if args.run_workload_no_vig_audit:
    from analytics.diagnostics import workload_no_vig_ev_audit

    workload_no_vig_ev_audit.main([
        "--input",
        str(output_dir / "pitcher_k_outcome_dataset.jsonl"),
        "--output",
        "analytics/output/workload_no_vig_ev_audit.md",
    ])
```

- [ ] **Step 3: Verify normal and audit builds**

Run:

```powershell
python scripts/build_pitcher_k_outcome_dataset.py --artifact-source hybrid --output-dir data/research/gate_c
python scripts/build_pitcher_k_outcome_dataset.py --artifact-source hybrid --output-dir data/research/gate_c --run-workload-no-vig-audit
```

Expected: first command only rebuilds Gate C artifacts; second also writes the workload/no-vig report.

## Task 6: Documentation And Briefing Handoff

**Files:**
- Modify: `docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`
- Modify: `docs/current-state.md`
- Modify: BBE Operations Brief automation memory

- [ ] **Step 1: Update controlling Gate C plan**

Add this child plan under current implementation status and clarify:

```text
Gate E and Gate F remain the model-promotion discipline. They now apply to each candidate family: workload/opportunity, no-vig EV gates, referee v2, Path B handedness, and projection challengers.
```

- [ ] **Step 2: Update current-state model lane**

Add this plan to the read order and model lane next decision:

```text
2026-06-08-workload-no-vig-k-projection-ev-synthesis.md
```

The next decision should be:

```text
Run the workload/no-vig audit after the next clean graded slate and compare its labels against confidence-referee caps and Path B coverage before drafting any live behavior change.
```

- [ ] **Step 3: Update BBE Operations Brief memory**

Append a short note to:

```text
C:\Users\TylerReid\.codex\automations\yesterdays-pipeline-health-bbe\memory.md
```

The note should say the next brief should include:

- workload/no-vig report if present
- Path B coverage buckets
- confidence-referee capped rows against no-vig/workload labels
- Gate E/F status

- [ ] **Step 4: Verify docs and git status**

Run:

```powershell
git diff -- docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md docs/current-state.md docs/superpowers/plans/2026-06-08-workload-no-vig-k-projection-ev-synthesis.md
git status --short
```

Expected: only the intended plan/docs files are modified before commit. Automation memory is outside the repo.

## Promotion Standard

No candidate from this plan can change live behavior unless all are true:

- Candidate uses only runtime-safe inputs.
- Candidate has at least 500 clean graded side rows or Tyler explicitly approves a smaller personal-use canary.
- Candidate survives over/under, plus/minus, K-line, quality-gate, model/market, timing, Path B coverage, provider, and workload slices.
- Candidate improves holdout outcome or process quality without relying on hindsight fields.
- Candidate does not degrade FIRE 2u retained wins or clean quality-gate alignment.
- Candidate has a one-env-var or one-commit rollback plan.
- Tyler explicitly approves a separate production implementation plan.

## Expected First Read

The expected first useful output is not "change the model." It is one of:

- Keep current lambda and referee, collect more rows.
- Draft a no-vig EV-gate shadow canary.
- Draft a workload/opportunity skepticism shadow canary.
- Tighten Path B collection/reporting before model use.
- Defer full simulator/pitch-mix work because the cheaper evidence is not strong enough.
