# Next Season K Model Rebuild Master Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the rest of the 2026 MLB season into a clean evidence-collection and season-end rebuild program so the 2027 pitcher strikeout model can use proven market, baseball, timing, and seasonality signals without overfitting or leaking hindsight.

**Architecture:** Keep 2026 production behavior low-volume and gate-protected while building a season-end research layer around the durable Gate C outcome dataset, live-market trackers, accepted-bet evidence, and postgame explanation fields. The rebuild should produce transparent candidate selectors and projection variants first, then one or more separately approved next-season canary plans.

**Tech Stack:** Python 3.11, stdlib JSON/CSV/pathlib/argparse, existing NumPy/SciPy dependencies, existing Gate C artifacts in `data/research/gate_c/`, existing analytics diagnostics, pytest, Render/Supabase/Netlify artifacts as read-only evidence sources.

## Global Constraints

- This is a master research and planning document, not approval to change live model behavior.
- Do not change live lambda, verdict thresholds, staking, provider order, notification behavior, lock behavior, retention, calibration, dashboard source-of-truth, Render env vars, GitHub variables, secrets, or `formula_change_date` from this plan.
- Keep the 2026 rest-of-season betting posture low-volume and personal-use: only limited discretionary play when final displayed FIRE rows survive the active gates.
- Preserve TheRundown as official artifact truth. PropLine remains fallback/live-movement sidecar. BoltOdds remains retired/historical.
- Do not use result, PnL, CLV, closing price, actual Ks, actual IP, actual pitch count, batters faced, post-start movement, or reconstructed lineup/opportunity as runtime inputs.
- Seasonality must be modeled as a shrunk, tested prior or feature family, never as a hard-coded calendar bump.
- Every candidate must separate available-before-lock features from hindsight-only explanation fields.
- Every next-season behavior change requires a separate Tyler-approved canary plan with rollback.
- Avoid new dependencies unless a child plan proves the ROI. Prefer transparent NumPy/SciPy scorecards and walk-forward tests before heavier ML.
- Preserve the personal-use boundary; do not recommend public sharing, selling access, broader distribution, or monetization without a separate compliance/data-rights review.

---

## Why This Plan Exists

The current gates are correctly reducing action because the old selection layer was forcing too many weak bets through. The season-to-date result is not best explained as "the projection model is useless." The better read is:

- broad projection quality has not collapsed;
- high raw edge, high adjusted EV, FIRE unders, and raw FIRE 2u have been weak in the clean regime;
- narrow process pockets such as CLV-supported rows, beat-close-price rows, retained FIRE rows, and some market-supported LEAN buckets look more useful;
- early-season side behavior differed from later-season behavior, so seasonality must be preserved instead of averaged away;
- by season end, the project should have enough pitcher-market outcomes to rebuild around what actually predicted bettable edges.

This plan turns that into a structured offseason rebuild path.

## Things Tyler Was Not Forgetting, But The Plan Must Explicitly Preserve

- **Seasonality:** early-season unders, later overs/mixed behavior, changing starter workloads, weather, league K environment, and books sharpening after April must be separate features or regimes.
- **Market maturity:** lines may be weaker early when pitcher roles, velocity, pitch mix, and team leash are uncertain; later market agreement may matter more than raw model gap.
- **Timing and CLV:** actual bet time, lock time, closing price, line movement, and accepted-bet rows must be separated. A model pick is not always a Tyler bet.
- **Runtime availability:** lineup handedness, confirmed lineups, umpire, park, rest, pitch count history, market state, and book availability must each carry an availability flag.
- **Hindsight explanations:** actual opportunity, actual Ks, close price, CLV, and post-start movement can explain misses but cannot define live selectors.
- **Pitcher role drift:** openers, bulk relievers, call-ups, innings caps, returns from IL, late-season shutdowns, and playoff-race workload changes need explicit labels.
- **Book/provider effects:** one-book outliers, line conflicts, missing target books, and best-executable price must be evaluated separately from official model truth.
- **No-bet as a product state:** the next model should be allowed to pass most slates if only a narrow positive selector survives.
- **Walk-forward proof:** train/test splits must respect time. Do not randomly shuffle one season and call it proof.
- **Next-season transfer risk:** 2026 findings become priors for 2027, not permanent constants.

## File Map

This master plan should not be executed as one giant task. It defines child workstreams. The expected files are:

- Create: `docs/research/next-season-k-model-feature-catalog.md`
  - Canonical feature inventory, source hierarchy, runtime availability, leakage class, and seasonality notes.
- Create: `analytics/diagnostics/season_end_model_rebuild_dataset.py`
  - Read-only builder that joins Gate C rows, market-agreement rows, live-display snapshots, accepted-bet rows when exported, and seasonality labels into a season-end JSONL.
- Create: `tests/test_season_end_model_rebuild_dataset.py`
  - Contract tests for no-leakage flags, field coverage, and deterministic output.
- Modify: `analytics/diagnostics/seasonal_k_environment_audit.py`
  - Expand from app-pick monthly actual Ks into richer seasonality/regime labels, while preserving selection-bias warnings.
- Modify: `tests/test_seasonal_k_environment_audit.py`
  - Add seasonality/regime tests.
- Create: `analytics/diagnostics/next_season_candidate_model_lab.py`
  - Walk-forward lab for transparent projection and selection candidates.
- Create: `tests/test_next_season_candidate_model_lab.py`
  - Tests for time splits, candidate metrics, and leakage rejection.
- Create: `analytics/diagnostics/next_season_model_decision_packet.py`
  - Report generator that summarizes which candidate families are ready for next-season canary planning.
- Create: `tests/test_next_season_model_decision_packet.py`
  - Tests for decision labels and required slices.
- Write: `analytics/output/season_end_model_rebuild_dataset_summary.md`
- Write: `analytics/output/next_season_candidate_model_lab.md`
- Write: `analytics/output/next_season_model_decision_packet.md`

## Status Summary

- Tasks 1-6: completed scaffold as of 2026-06-23.
- Task 7: deferred until the 2026 regular season is fully graded and season-end artifacts are frozen.
- Final review note: decision-packet canary candidates now require explicit slice metadata (`bad_slices` or `bad_slice_count`) and explicit parseable test metrics (`test_rows` and `test_pnl`). Missing slice metadata blocks as `blocked_missing_slices`; missing test metrics that would otherwise promote block as `blocked_missing_test_metrics`.

## Task 1: Create The Next-Season Feature Catalog

**Files:**
- Create: `docs/research/next-season-k-model-feature-catalog.md`

**Interfaces:**
- Consumes: existing docs and reports only.
- Produces: a canonical feature catalog used by Tasks 2-6.

- [x] **Step 1: Write the feature catalog**

Create `docs/research/next-season-k-model-feature-catalog.md` with this structure:

```markdown
# Next Season K Model Feature Catalog

This document is research-only. It does not change live lambda, thresholds, staking, providers, notifications, locks, retention, calibration, or dashboard source-of-truth.

## Feature Classes

| Class | Examples | Runtime-safe? | Hindsight-only? | Current source |
| --- | --- | --- | --- | --- |
| Identity | slate_date, pitcher, team, opponent, home_away, game_time | yes | no | Gate C dataset |
| Market price | side, K line, book, odds, no-vig side probability, market favorite side | yes when captured before lock | closing price is hindsight | TheRundown artifacts, PropLine sidecar, Gate C |
| Model state | lambda, model_lambda, edge, EV, adjusted EV, raw verdict, displayed verdict | yes | no | today/dated artifacts, Gate C |
| Quality and availability | lineup_used, quality_gate_level, data warnings, split source, umpire availability | yes | no | pipeline artifacts |
| Live movement | pregame movement with/against model, book count, better/worse now, broad confirmation | yes if timestamped pre-start | post-start movement is hindsight | market_pick_evidence, live_market_display_state |
| Timing and CLV | locked_at, accepted_bet_time, beat_close_price, beat_close_line | lock/accepted time is runtime context | close result and CLV are hindsight labels | picks_history, accepted_bets, Gate C |
| Baseball skill | season K/9, recent K/9, career K/9, SwStr, handedness, lineup K rate | yes when fetched pre-lock | actual result is hindsight | pipeline stats, FanGraphs cache, Path B |
| Workload and leash | rest, last pitch count, opener flag, pregame workload bucket | yes if known pre-lock | actual IP/pitches/batters faced are hindsight | pipeline stats, actual_opportunity_backfill |
| Context | park, umpire, weather/roof, run environment, game total | yes if known pre-lock | postgame environment adjustments are hindsight | pipeline + future source review |
| Seasonality | month, week, early/mid/late season, league K environment, starter ramp period | yes as shrunk prior if validated | using same-row result to assign effect is hindsight | seasonal audit + MLB-wide validation |
```

## Required Availability Labels

Every season-end row must carry:

- `available_pre_lock`: true when all fields in the candidate were knowable before lock.
- `runtime_feature_group`: one of `market`, `model`, `baseball`, `workload`, `quality`, `seasonality`, `timing`.
- `hindsight_explanation_only`: true for result, PnL, actual Ks, CLV, close price, actual opportunity, or post-start movement.
- `source_confidence`: one of `official_artifact`, `sidecar_pregame`, `manual_accepted_bet`, `reconstructed_postgame`, `missing`.

## Seasonality Rules

- Preserve early season, April/May/June/July/August/September, and final-month buckets separately.
- Compare app-picked rows to MLB-wide starter K/start before using month effects.
- Treat early-season under strength as a candidate regime, not as a permanent under bias.
- Treat later-season over/mixed behavior as separate from April.
- Include starter ramp-up, innings caps, call-ups, IL return, and team shutdown risk as possible seasonality explanations.
```

- [x] **Step 2: Review against current docs**

Run:

```powershell
rg "hindsight|runtime-safe|seasonality|CLV|accepted-bet|Path B|workload|market agreement" docs/research docs/superpowers/plans
```

Expected: output includes the Gate C dataset plan, active gates synthesis, market tracker map, workload/no-vig plan, and Path B plan. Update the catalog only if one of those docs names a feature class not listed above.

- [x] **Step 3: Commit**

```powershell
git add docs/research/next-season-k-model-feature-catalog.md
git commit -m "docs: add next season model feature catalog"
```

## Task 2: Build A Season-End Rebuild Dataset

**Files:**
- Create: `analytics/diagnostics/season_end_model_rebuild_dataset.py`
- Create: `tests/test_season_end_model_rebuild_dataset.py`
- Write: `analytics/output/season_end_model_rebuild_dataset_summary.md`

**Interfaces:**
- Consumes: `data/research/gate_c/pitcher_k_outcome_dataset.jsonl`.
- Optionally consumes: exported market agreement JSONL, exported live display state JSON, exported accepted bets JSON.
- Produces: deterministic row list with no-leakage labels and seasonality buckets.

- [x] **Step 1: Write failing tests**

Create `tests/test_season_end_model_rebuild_dataset.py`:

```python
from analytics.diagnostics import season_end_model_rebuild_dataset as rebuild


def test_build_row_marks_hindsight_fields_as_not_runtime_safe():
    source = {
        "slate_date": "2026-06-23",
        "pitcher": "Example Starter",
        "side": "over",
        "k_line": 5.5,
        "actual_ks": 7,
        "pnl": 0.91,
        "beat_close_price": True,
        "model_market_relationship": "model_agrees_with_favorite",
        "quality_gate_level": "clean",
    }

    row = rebuild.build_row(source)

    assert row["available_pre_lock"] is True
    assert row["hindsight_labels"]["actual_ks"] == 7
    assert row["hindsight_labels"]["beat_close_price"] is True
    assert "actual_ks" not in row["runtime_features"]
    assert "beat_close_price" not in row["runtime_features"]


def test_season_bucket_preserves_early_mid_late_context():
    assert rebuild.season_bucket("2026-03-28") == "early_season"
    assert rebuild.season_bucket("2026-05-15") == "spring_midseason"
    assert rebuild.season_bucket("2026-07-15") == "summer_midseason"
    assert rebuild.season_bucket("2026-09-10") == "late_season"


def test_summarize_reports_runtime_and_hindsight_coverage():
    rows = [
        {
            "available_pre_lock": True,
            "runtime_features": {"quality_gate_level": "clean"},
            "hindsight_labels": {"beat_close_price": True},
            "season_bucket": "early_season",
        }
    ]

    summary = rebuild.summarize(rows)

    assert summary["rows"] == 1
    assert summary["available_pre_lock_rows"] == 1
    assert summary["season_buckets"] == {"early_season": 1}
    assert summary["hindsight_label_counts"]["beat_close_price"] == 1
```

- [x] **Step 2: Run tests to verify failure**

```powershell
python -m pytest tests/test_season_end_model_rebuild_dataset.py -q
```

Expected: fail because `season_end_model_rebuild_dataset` does not exist.

- [x] **Step 3: Implement minimal dataset builder**

Create `analytics/diagnostics/season_end_model_rebuild_dataset.py`:

```python
"""Build a no-leakage season-end research dataset for next-season model work."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "season_end_model_rebuild_dataset.jsonl"
DEFAULT_SUMMARY = ROOT / "analytics" / "output" / "season_end_model_rebuild_dataset_summary.md"

HINDSIGHT_FIELDS = {
    "actual_ks",
    "result",
    "pnl",
    "closing_odds",
    "closing_line",
    "beat_close_price",
    "beat_close_line",
    "price_clv_cents",
    "line_clv_delta",
    "actual_ip",
    "actual_pitch_count",
    "batters_faced",
}

RUNTIME_FIELDS = {
    "slate_date",
    "pitcher",
    "normalized_pitcher",
    "team",
    "opp_team",
    "side",
    "k_line",
    "american_odds",
    "bookmaker_key",
    "model_win_prob",
    "projected_ks",
    "edge",
    "ev",
    "adj_ev",
    "verdict",
    "raw_verdict",
    "quality_gate_level",
    "model_market_relationship",
    "no_vig_side_probability",
    "opportunity_bucket",
    "leash_risk_bucket",
    "pitcher_throws",
    "lineup_used",
    "lineup_right_batters",
    "lineup_left_batters",
    "lineup_switch_batters",
    "handedness_matchup_bucket",
}


def season_bucket(date_str: str) -> str:
    month = int(str(date_str)[5:7])
    day = int(str(date_str)[8:10])
    if month <= 4:
        return "early_season"
    if month == 5 or (month == 6 and day <= 15):
        return "spring_midseason"
    if month in {6, 7, 8}:
        return "summer_midseason"
    return "late_season"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_row(source: dict[str, Any]) -> dict[str, Any]:
    slate_date = source.get("slate_date") or source.get("date")
    runtime_features = {key: source.get(key) for key in RUNTIME_FIELDS if key in source}
    hindsight_labels = {key: source.get(key) for key in HINDSIGHT_FIELDS if key in source}
    return {
        "dataset_key": source.get("dataset_key") or "|".join(
            str(part or "")
            for part in [slate_date, source.get("normalized_pitcher") or source.get("pitcher"), source.get("side"), source.get("k_line")]
        ),
        "slate_date": slate_date,
        "season_bucket": season_bucket(slate_date),
        "available_pre_lock": True,
        "runtime_features": runtime_features,
        "hindsight_labels": hindsight_labels,
        "source_confidence": "official_artifact",
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    season_counts = Counter(row.get("season_bucket") for row in rows)
    hindsight_counts: Counter[str] = Counter()
    for row in rows:
        for key, value in row.get("hindsight_labels", {}).items():
            if value is not None:
                hindsight_counts[key] += 1
    return {
        "rows": len(rows),
        "available_pre_lock_rows": sum(1 for row in rows if row.get("available_pre_lock") is True),
        "season_buckets": dict(sorted(season_counts.items())),
        "hindsight_label_counts": dict(sorted(hindsight_counts.items())),
    }


def render_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# Season-End Model Rebuild Dataset Summary",
        "",
        "Research-only. This output does not change live lambda, thresholds, staking, providers, notifications, locks, retention, calibration, or dashboard source-of-truth.",
        "",
        f"- Rows: `{summary['rows']}`",
        f"- Available pre-lock rows: `{summary['available_pre_lock_rows']}`",
        "",
        "## Season Buckets",
    ]
    for bucket, count in summary["season_buckets"].items():
        lines.append(f"- `{bucket}`: `{count}`")
    lines.extend(["", "## Hindsight Label Coverage"])
    for label, count in summary["hindsight_label_counts"].items():
        lines.append(f"- `{label}`: `{count}`")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args(argv)

    rows = [build_row(row) for row in load_jsonl(args.input)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else ""), encoding="utf-8")
    args.summary.write_text(render_summary(summarize(rows)), encoding="utf-8")
    print(f"Wrote {args.output} ({len(rows)} rows)")
    print(f"Wrote {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 4: Run tests and builder**

```powershell
python -m pytest tests/test_season_end_model_rebuild_dataset.py -q
python analytics/diagnostics/season_end_model_rebuild_dataset.py --input data/research/gate_c/pitcher_k_outcome_dataset.jsonl
```

Expected: tests pass and `analytics/output/season_end_model_rebuild_dataset_summary.md` writes row counts.

- [x] **Step 5: Commit**

```powershell
git add analytics/diagnostics/season_end_model_rebuild_dataset.py tests/test_season_end_model_rebuild_dataset.py analytics/output/season_end_model_rebuild_dataset_summary.md
git commit -m "feat: add season-end model rebuild dataset"
```

## Task 3: Upgrade Seasonality From A Warning To A Tested Feature Family

**Files:**
- Modify: `analytics/diagnostics/seasonal_k_environment_audit.py`
- Modify: `tests/test_seasonal_k_environment_audit.py`
- Write: `analytics/output/seasonal_k_environment_audit.md`

**Interfaces:**
- Consumes: `picks_history.json` and, later, optional MLB-wide starter K/start data.
- Produces: seasonality buckets that can be used in Task 5 as candidate features.

- [x] **Step 1: Add failing tests for regime labels**

Append to `tests/test_seasonal_k_environment_audit.py`:

```python
def test_regime_bucket_keeps_early_and_late_season_separate():
    assert audit.regime_bucket("2026-04-05") == "early_season"
    assert audit.regime_bucket("2026-06-10") == "spring_midseason"
    assert audit.regime_bucket("2026-07-20") == "summer_midseason"
    assert audit.regime_bucket("2026-09-05") == "late_season"


def test_summarize_side_by_regime_preserves_over_under_direction():
    rows = [
        {"date": "2026-04-05", "side": "under", "result": "win", "pnl": 0.91, "actual_ks": 4},
        {"date": "2026-04-06", "side": "under", "result": "loss", "pnl": -1.0, "actual_ks": 7},
        {"date": "2026-07-05", "side": "over", "result": "win", "pnl": 1.1, "actual_ks": 8},
    ]

    summary = audit.summarize_side_by_regime(rows)

    assert summary["early_season | under"]["rows"] == 2
    assert summary["early_season | under"]["pnl"] == -0.09
    assert summary["summer_midseason | over"]["rows"] == 1
    assert summary["summer_midseason | over"]["pnl"] == 1.1
```

- [x] **Step 2: Run tests to verify failure**

```powershell
python -m pytest tests/test_seasonal_k_environment_audit.py -q
```

Expected: fail because `regime_bucket` and `summarize_side_by_regime` do not exist.

- [x] **Step 3: Add regime helpers**

Add to `analytics/diagnostics/seasonal_k_environment_audit.py`:

```python
def regime_bucket(date_str: str) -> str:
    month = int(str(date_str)[5:7])
    day = int(str(date_str)[8:10])
    if month <= 4:
        return "early_season"
    if month == 5 or (month == 6 and day <= 15):
        return "spring_midseason"
    if month in {6, 7, 8}:
        return "summer_midseason"
    return "late_season"


def summarize_side_by_regime(rows: list[dict]) -> dict:
    buckets: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("result") not in {"win", "loss"}:
            continue
        side = row.get("side") or "unknown"
        buckets[f"{regime_bucket(row.get('date'))} | {side}"].append(row)

    summary = {}
    for bucket, group in sorted(buckets.items()):
        pnl = round(sum(float(row.get("pnl") or 0.0) for row in group), 2)
        summary[bucket] = {
            "rows": len(group),
            "wins": sum(1 for row in group if row.get("result") == "win"),
            "losses": sum(1 for row in group if row.get("result") == "loss"),
            "pnl": pnl,
        }
    return summary
```

- [x] **Step 4: Render side-by-regime output**

Update `render()` in `analytics/diagnostics/seasonal_k_environment_audit.py` to accept an optional second argument and append:

```python
def render(summary: dict, side_regime_summary: dict | None = None) -> str:
    ...
    lines.extend(["", "## Side By Regime"])
    if side_regime_summary:
        for bucket, row in side_regime_summary.items():
            lines.append(
                f"- `{bucket}`: rows={row['rows']}, {row['wins']}-{row['losses']}, pnl={row['pnl']}"
            )
    else:
        lines.append("- No side/regime summary available.")
```

Update `main()` to call:

```python
rows = load_history(args.history)
print(render(summarize_by_month(rows), summarize_side_by_regime(rows)))
```

- [x] **Step 5: Run tests and write output**

```powershell
python -m pytest tests/test_seasonal_k_environment_audit.py -q
python analytics/diagnostics/seasonal_k_environment_audit.py > analytics/output/seasonal_k_environment_audit.md
```

Expected: tests pass and the report contains `## Side By Regime`.

- [x] **Step 6: Commit**

```powershell
git add analytics/diagnostics/seasonal_k_environment_audit.py tests/test_seasonal_k_environment_audit.py analytics/output/seasonal_k_environment_audit.md
git commit -m "feat: expand seasonal K environment audit"
```

## Task 4: Define Candidate Families For The Offseason Lab

**Files:**
- Create: `docs/research/next-season-k-model-candidate-families.md`

**Interfaces:**
- Consumes: feature catalog and current Gate C/Gate F reports.
- Produces: fixed candidate families for Task 5. No production behavior.

- [x] **Step 1: Write candidate family doc**

Create `docs/research/next-season-k-model-candidate-families.md`:

```markdown
# Next Season K Model Candidate Families

Research-only. This document does not change live behavior.

## Projection Candidates

1. `current_model`: existing K/9 + SwStr + lineup + umpire + park + bias model.
2. `market_shrink_15`, `market_shrink_25`, `market_shrink_35`: shrink current lambda toward posted K line.
3. `market_anchor_selector`: market-implied K plus baseball adjustment.
4. `path_b_lineup_splits`: use live PA-backed split rates where available with Path A fallback.
5. `workload_temper`: shrink projection when pregame workload/leash label is fragile.
6. `seasonality_prior`: shrunk month/regime prior validated against MLB-wide starter K environment.

## Selection Candidates

1. `keep_fire`: retained FIRE after confidence/profit-rescue caps.
2. `clv_supported_proxy`: runtime-safe proxy for rows that later beat close.
3. `market_supported_lean`: LEAN rows with broad or durable market support.
4. `high_edge_skeptic`: high raw edge rows contradicted by market/no-vig/workload.
5. `fire_under_brake`: FIRE unders with runtime-safe warning stack.
6. `no_bet_default`: explicit pass when no positive selector fires.

## Timing Candidates

1. `bet_now`: price/line is available and market support is fresh.
2. `wait_for_lineup`: projected-lineup or missing split context suppresses early betting.
3. `shop_only`: model likes side but best executable book differs from official ref.
4. `ignore_noise`: one-book or reversed movement with no broad support.

## Required Proof For Any Candidate

- Walk-forward positive result.
- Survives over/under.
- Survives K-line buckets.
- Survives plus/minus price.
- Survives FIRE/LEAN/raw-verdict slices.
- Survives quality gate and data maturity slices.
- Survives Path B coverage and fallback slices.
- Survives market-agreement and CLV-target slices.
- Does not depend on hindsight-only fields.
- Has one rollback flag in a future canary plan.
```

- [x] **Step 2: Commit**

```powershell
git add docs/research/next-season-k-model-candidate-families.md
git commit -m "docs: define next season model candidate families"
```

## Task 5: Build The Walk-Forward Candidate Model Lab

**Files:**
- Create: `analytics/diagnostics/next_season_candidate_model_lab.py`
- Create: `tests/test_next_season_candidate_model_lab.py`
- Write: `analytics/output/next_season_candidate_model_lab.md`

**Interfaces:**
- Consumes: rows from `analytics/diagnostics/season_end_model_rebuild_dataset.py`.
- Produces: candidate metrics and readiness labels.

- [x] **Step 1: Write failing tests**

Create `tests/test_next_season_candidate_model_lab.py`:

```python
from analytics.diagnostics import next_season_candidate_model_lab as lab


def test_walk_forward_split_respects_time_order():
    rows = [
        {"slate_date": "2026-04-01"},
        {"slate_date": "2026-05-01"},
        {"slate_date": "2026-06-01"},
        {"slate_date": "2026-07-01"},
    ]

    train, test = lab.walk_forward_split(rows, test_start="2026-06-01")

    assert [row["slate_date"] for row in train] == ["2026-04-01", "2026-05-01"]
    assert [row["slate_date"] for row in test] == ["2026-06-01", "2026-07-01"]


def test_score_candidate_rejects_hindsight_runtime_fields():
    rows = [
        {"runtime_features": {"edge": 0.05}, "hindsight_labels": {"result": "win", "pnl": 0.91}},
    ]

    candidate = lab.Candidate(
        name="bad_candidate",
        runtime_fields=("edge", "beat_close_price"),
        selector=lambda row: True,
    )

    result = lab.score_candidate(candidate, rows)

    assert result["status"] == "blocked_hindsight_runtime_field"
    assert result["rows"] == 0


def test_score_candidate_counts_wins_losses_and_pnl():
    rows = [
        {"runtime_features": {"edge": 0.05}, "hindsight_labels": {"result": "win", "pnl": 0.91}},
        {"runtime_features": {"edge": 0.06}, "hindsight_labels": {"result": "loss", "pnl": -1.0}},
    ]

    candidate = lab.Candidate(
        name="edge_positive",
        runtime_fields=("edge",),
        selector=lambda row: row["runtime_features"].get("edge", 0) > 0,
    )

    result = lab.score_candidate(candidate, rows)

    assert result["status"] == "watch"
    assert result["rows"] == 2
    assert result["wins"] == 1
    assert result["losses"] == 1
    assert result["pnl"] == -0.09
```

- [x] **Step 2: Run tests to verify failure**

```powershell
python -m pytest tests/test_next_season_candidate_model_lab.py -q
```

Expected: fail because `next_season_candidate_model_lab` does not exist.

- [x] **Step 3: Implement minimal candidate lab**

Create `analytics/diagnostics/next_season_candidate_model_lab.py`:

```python
"""Walk-forward candidate lab for next-season pitcher K model work."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "analytics" / "output" / "season_end_model_rebuild_dataset.jsonl"
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "next_season_candidate_model_lab.md"
HINDSIGHT_FIELD_NAMES = {
    "actual_ks",
    "result",
    "pnl",
    "beat_close_price",
    "beat_close_line",
    "price_clv_cents",
    "line_clv_delta",
    "actual_ip",
    "actual_pitch_count",
    "batters_faced",
}


@dataclass(frozen=True)
class Candidate:
    name: str
    runtime_fields: tuple[str, ...]
    selector: Callable[[dict[str, Any]], bool]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def walk_forward_split(rows: list[dict[str, Any]], *, test_start: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(rows, key=lambda row: row.get("slate_date") or "")
    train = [row for row in ordered if (row.get("slate_date") or "") < test_start]
    test = [row for row in ordered if (row.get("slate_date") or "") >= test_start]
    return train, test


def score_candidate(candidate: Candidate, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if any(field in HINDSIGHT_FIELD_NAMES for field in candidate.runtime_fields):
        return {"candidate": candidate.name, "status": "blocked_hindsight_runtime_field", "rows": 0}

    selected = [row for row in rows if candidate.selector(row)]
    graded = [row for row in selected if row.get("hindsight_labels", {}).get("result") in {"win", "loss"}]
    wins = sum(1 for row in graded if row["hindsight_labels"]["result"] == "win")
    losses = sum(1 for row in graded if row["hindsight_labels"]["result"] == "loss")
    pnl = round(sum(float(row.get("hindsight_labels", {}).get("pnl") or 0.0) for row in graded), 2)
    status = "review_ready" if len(graded) >= 150 and pnl > 0 else "watch"
    return {
        "candidate": candidate.name,
        "status": status,
        "rows": len(graded),
        "wins": wins,
        "losses": losses,
        "pnl": pnl,
    }


def default_candidates() -> list[Candidate]:
    return [
        Candidate(
            name="model_agrees_with_favorite",
            runtime_fields=("model_market_relationship",),
            selector=lambda row: row["runtime_features"].get("model_market_relationship") == "model_agrees_with_favorite",
        ),
        Candidate(
            name="clean_quality_only",
            runtime_fields=("quality_gate_level",),
            selector=lambda row: row["runtime_features"].get("quality_gate_level") == "clean",
        ),
    ]


def render(results: list[dict[str, Any]]) -> str:
    lines = [
        "# Next Season Candidate Model Lab",
        "",
        "Research-only. This report does not change live lambda, thresholds, staking, providers, notifications, locks, retention, calibration, or dashboard source-of-truth.",
        "",
        "| Candidate | Status | Rows | W-L | PnL |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for row in results:
        lines.append(
            f"| `{row['candidate']}` | `{row['status']}` | {row.get('rows', 0)} | {row.get('wins', 0)}-{row.get('losses', 0)} | {row.get('pnl', 0)} |"
        )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    rows = load_jsonl(args.input)
    results = [score_candidate(candidate, rows) for candidate in default_candidates()]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(results), encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 4: Run tests and report**

```powershell
python -m pytest tests/test_next_season_candidate_model_lab.py -q
python analytics/diagnostics/season_end_model_rebuild_dataset.py --input data/research/gate_c/pitcher_k_outcome_dataset.jsonl
python analytics/diagnostics/next_season_candidate_model_lab.py
```

Expected: tests pass and `analytics/output/next_season_candidate_model_lab.md` writes candidate rows.

- [x] **Step 5: Commit**

```powershell
git add analytics/diagnostics/next_season_candidate_model_lab.py tests/test_next_season_candidate_model_lab.py analytics/output/next_season_candidate_model_lab.md
git commit -m "feat: add next season candidate model lab"
```

## Task 6: Build The Season-End Decision Packet

**Files:**
- Create: `analytics/diagnostics/next_season_model_decision_packet.py`
- Create: `tests/test_next_season_model_decision_packet.py`
- Write: `analytics/output/next_season_model_decision_packet.md`

**Interfaces:**
- Consumes: candidate lab results, seasonal audit, bet-selection synthesis, Gate F report, market agreement tracker.
- Produces: the offseason yes/no decision packet for next-season canary plans.

- [x] **Step 1: Write failing tests**

Create `tests/test_next_season_model_decision_packet.py`:

```python
from analytics.diagnostics import next_season_model_decision_packet as packet


def test_decision_label_requires_sample_and_positive_pnl():
    assert packet.decision_label(rows=149, pnl=20.0, bad_slices=0) == "watch_more"
    assert packet.decision_label(rows=150, pnl=-1.0, bad_slices=0) == "blocked_negative_pnl"
    assert packet.decision_label(rows=150, pnl=10.0, bad_slices=1) == "blocked_bad_slice"
    assert packet.decision_label(rows=150, pnl=10.0, bad_slices=0) == "canary_plan_candidate"


def test_render_names_required_final_decisions():
    rendered = packet.render(
        [
            {
                "candidate": "market_supported_lean",
                "decision": "canary_plan_candidate",
                "rows": 160,
                "pnl": 8.5,
            }
        ]
    )

    assert "market_supported_lean" in rendered
    assert "Allowed offseason decisions" in rendered
    assert "draft_next_season_canary_plan" in rendered
```

- [x] **Step 2: Run tests to verify failure**

```powershell
python -m pytest tests/test_next_season_model_decision_packet.py -q
```

Expected: fail because `next_season_model_decision_packet` does not exist.

- [x] **Step 3: Implement decision packet**

Create `analytics/diagnostics/next_season_model_decision_packet.py`:

```python
"""Render the season-end decision packet for next-season model canaries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LAB = ROOT / "analytics" / "output" / "next_season_candidate_model_lab.json"
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "next_season_model_decision_packet.md"


def decision_label(*, rows: int, pnl: float, bad_slices: int) -> str:
    if rows < 150:
        return "watch_more"
    if pnl <= 0:
        return "blocked_negative_pnl"
    if bad_slices > 0:
        return "blocked_bad_slice"
    return "canary_plan_candidate"


def render(candidates: list[dict[str, Any]]) -> str:
    lines = [
        "# Next Season Model Decision Packet",
        "",
        "Research-only. This packet does not change live behavior.",
        "",
        "| Candidate | Decision | Rows | PnL |",
        "| --- | --- | ---: | ---: |",
    ]
    for row in candidates:
        lines.append(f"| `{row['candidate']}` | `{row['decision']}` | {row['rows']} | {row['pnl']} |")
    lines.extend(
        [
            "",
            "## Allowed offseason decisions",
            "",
            "- `watch_more`",
            "- `drop_candidate`",
            "- `draft_next_season_canary_plan`",
            "- `keep_research_only`",
            "",
            "## Still not allowed from this packet",
            "",
            "- Live lambda change",
            "- Threshold or staking change",
            "- Provider/source switch",
            "- Notification behavior change",
            "- Lock or retention behavior change",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    candidates: list[dict[str, Any]] = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render(candidates), encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [x] **Step 4: Run tests and packet**

```powershell
python -m pytest tests/test_next_season_model_decision_packet.py -q
python analytics/diagnostics/next_season_model_decision_packet.py
```

Expected: tests pass and `analytics/output/next_season_model_decision_packet.md` writes.

- [x] **Step 5: Commit**

```powershell
git add analytics/diagnostics/next_season_model_decision_packet.py tests/test_next_season_model_decision_packet.py analytics/output/next_season_model_decision_packet.md
git commit -m "feat: add next season model decision packet"
```

## Task 7: Run The Season-End Review And Draft Child Canary Plans

**Files:**
- Modify: this plan with a season-end review section.
- Create later, only after Tyler approval: one child plan per candidate, for example `docs/superpowers/plans/2026-10-01-next-season-market-supported-lean-canary.md`.

**Interfaces:**
- Consumes: outputs from Tasks 1-6.
- Produces: a Tyler decision list, not live behavior.

**Status:** Deferred until the 2026 regular season is fully graded and the season-end artifacts are frozen. Do not draft child canary plans from the scaffold-only packet.

- [ ] **Step 1: Freeze season-end artifacts**

Run after the 2026 regular season and grading are complete:

```powershell
python scripts/build_pitcher_k_outcome_dataset.py --artifact-source hybrid --output-dir data/research/gate_c --run-workload-no-vig-audit
python analytics/diagnostics/season_end_model_rebuild_dataset.py --input data/research/gate_c/pitcher_k_outcome_dataset.jsonl
python analytics/diagnostics/seasonal_k_environment_audit.py > analytics/output/seasonal_k_environment_audit.md
python analytics/diagnostics/next_season_candidate_model_lab.py
python analytics/diagnostics/next_season_model_decision_packet.py
```

Expected: every command exits `0`; no production artifact is published; outputs are written only under `analytics/output/` and `data/research/gate_c/`.

- [ ] **Step 2: Review required slices**

For every candidate in the decision packet, manually verify these slices exist in the packet or source reports:

```text
over/under
FIRE 1u/FIRE 2u/LEAN/raw verdict
plus/minus price
low/mid/high K line
quality gate and data maturity
timing window
model-market relationship
no-vig label
CLV target
workload/leash label
Path B coverage and fallback
provider/source attribution
market-agreement label
seasonality regime
rolling window
```

Expected: candidates missing any required slice stay `watch_more`.

- [ ] **Step 3: Add season-end review section**

Append to this plan:

```markdown
## Season-End Review

- Season rows:
- Graded pitcher-market rows:
- Tracked pick rows:
- Accepted-bet matched rows:
- Best projection candidate:
- Best selection candidate:
- Best timing candidate:
- Strongest negative brake:
- Seasonality finding:
- Candidates to drop:
- Candidates to draft as child canary plans:
- Tyler decision:
```

- [ ] **Step 4: Draft only approved child plans**

For each Tyler-approved candidate, create a separate child plan. Each child plan must have:

- one behavior change only;
- one feature flag or rollback switch;
- one first-slate canary scope;
- exact pass/fail metrics;
- no staking/provider/notification/dashboard source changes unless the child plan is specifically about that lane.

- [ ] **Step 5: Commit**

```powershell
git add docs/superpowers/plans/2026-06-23-next-season-k-model-rebuild-master-plan.md analytics/output/seasonal_k_environment_audit.md analytics/output/season_end_model_rebuild_dataset_summary.md analytics/output/next_season_candidate_model_lab.md analytics/output/next_season_model_decision_packet.md
git commit -m "docs: record next season model rebuild review"
```

## Rest-Of-Season Operating Rule

Until the season-end packet exists:

- play limited discretionary action only when displayed FIRE rows survive the active caps;
- treat no-bet days as healthy, not as product failure;
- preserve every row needed for season-end reconstruction;
- do not loosen gates to increase volume;
- do not promote market-shrink, market-anchor, Path B, or LEAN re-entry from one slate;
- use daily briefs to watch evidence quality, not to chase action.

## Self-Review

Spec coverage:

- Results and gates are included through Gate C, Gate F, confidence referee, profit rescue, market agreement, Path B, workload/no-vig, and market-shrink.
- Inputs are separated into runtime-safe and hindsight-only.
- Seasonality is explicit and includes early season under strength, later over/mixed behavior, starter workload, and market maturity.
- Full-season pitcher-market result collection is centered in the season-end dataset and decision packet.
- Next-season behavior changes require separate child canary plans.

Placeholder scan:

- No placeholder markers are present.
- Every task has exact files, commands, and expected outputs.

Type consistency:

- `runtime_features`, `hindsight_labels`, `season_bucket`, and `available_pre_lock` are used consistently across dataset and lab tasks.
- `canary_plan_candidate`, `watch_more`, `blocked_negative_pnl`, `blocked_bad_slice`, `blocked_missing_slices`, and `blocked_missing_test_metrics` are the decision labels used by the decision packet.
