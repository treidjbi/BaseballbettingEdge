# Strong Base Decision System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shadow-only decision framework that finds the smallest durable set of BBE pick contexts worth keeping or expanding while identifying the contexts that should stay capped, suppressed, or evidence-only.

**Architecture:** Reuse the existing Gate C pitcher outcome dataset as the source row and add one focused diagnostic report that reconciles positive CLV against negative portfolio PnL. The report sorts candidate contexts into keep-FIRE, expand-LEAN, cap/suppress, and evidence-only lanes, then forces each candidate through mandatory slices before any promotion discussion. This plan does not change live model math, thresholds, staking, provider order, notifications, locks, retention, dashboard source-of-truth, or production artifacts.

**Tech Stack:** Python 3.11, existing Gate C JSONL artifact, pytest, Markdown report under `analytics/output/`, dated plan docs under `docs/superpowers/plans/`.

## Global Constraints

- Treat `2026-04-28+` as the clean post-bump evaluation regime.
- Use `data/research/gate_c/pitcher_k_outcome_dataset.jsonl` or a freshly generated temporary Gate C JSONL as the evidence source.
- Separate positive CLV/process evidence from runtime-safe decision rules; final CLV is post-close and cannot directly become a live selector.
- Require candidate survival across side, K-line, price, model-market favorite agreement, CLV/proxy CLV, quality gate, Path B coverage, provider era, market agreement, and rolling recent form.
- Do not make live model, threshold, staking, provider, notification, lock, retention, dashboard source-of-truth, or `formula_change_date` changes from this lab.
- Any live behavior change after this plan requires a separate Tyler-approved promotion plan.

---

## Evidence Problem

The current contradiction is real:

- Positive CLV exists and appears to be the cleanest process signal.
- The tracked post-bump portfolio is still losing heavily.
- High raw edge and high adjusted EV are not automatically better; recent evidence shows those buckets can be the trap.
- Generic PASS or LEAN expansion is not supported unless the new candidate also has a stronger base than "the model says edge."

The decision system should answer:

1. Which FIRE contexts should remain FIRE?
2. Which LEAN contexts might be worth betting when stronger-base evidence is present?
3. Which FIRE/LEAN contexts should stay capped, reduced, or ignored?
4. Which good-looking signals are only process anchors because they rely on final CLV or sparse provider-era evidence?

## File Structure

- Create `analytics/diagnostics/strong_base_decision_lab.py`
  - Loads Gate C JSONL rows.
  - Builds candidate labels and policy lanes.
  - Computes tracked portfolio, CLV, PASS expansion, candidate scoreboards, current-provider slices, recent-window slices, and mandatory negative slice risks.
  - Writes `analytics/output/strong_base_decision_lab.md`.
- Create `tests/test_strong_base_decision_lab.py`
  - Covers candidate labeling, provider-era labels, Path B coverage labels, CLV/process separation, PASS expansion counting, readiness gates, and report language.
- Create `analytics/output/strong_base_decision_lab.md`
  - First generated report artifact from the latest clean post-bump Gate C corpus.
- Create `analytics/diagnostics/strong_base_portfolio_simulator.py`
  - Reuses Strong Base candidate labels to compare current staked FIRE, current
    tracked flat picks, drag-suppressed tracked picks, strict retained FIRE,
    strict plus selective LEAN, positive-edge PASS expansion, and CLV-confirmed
    hindsight ceilings.
- Create `tests/test_strong_base_portfolio_simulator.py`
  - Covers stake-aware FIRE units, no-hindsight separation, strict runtime
    filtering, selective LEAN expansion, report language, and direct script
    execution from the repo root.
- Create `analytics/output/strong_base_portfolio_simulator.md`
  - First generated portfolio policy report from the latest clean post-bump
    Gate C corpus.
- Create `analytics/diagnostics/shadow_signal_synthesis_lab.py`
  - Combines Strong Base candidate lanes, market-anchor selector labels,
    pre-close proxy labels, and market-agreement tracker exports into one
    read-only policy-shape scoreboard.
- Create `tests/test_shadow_signal_synthesis_lab.py`
  - Covers market-agreement JSONL loading, per-pick agreement overlay,
    combined policy scoring, and shadow-only report language.
- Create `analytics/output/shadow_signal_synthesis_lab.md`
  - First generated synthesis report from the refreshed Gate C corpus and
    refreshed market-agreement tracker export.
- Modify `scripts/run_post_grading_shadow_reports.py`
  - Regenerates the Strong Base report, portfolio simulator, market-agreement
    tracker, and shadow signal synthesis report as part of the existing
    review-only post-grading model report runner.
- Modify `docs/current-state.md`
  - Add the Strong Base lab to the model-lane read order and next-decision language once the first report is generated.
- Modify `C:\Users\TylerReid\.codex\automations\yesterdays-pipeline-health-bbe\memory.md`
  - Carry the new report path and current gate posture into the next operations brief.

## Portfolio Simulator Addendum

After the first Strong Base lab proved that positive CLV and mass losses were
both real, Tyler asked for the path to a positive-unit producer. The answer
needs a portfolio simulator, not just candidate bucket tables.

The simulator is still read-only and uses the same Gate C corpus. It must keep
three ideas separate:

1. Current staked reality: FIRE 1u risks 1u, FIRE 2u risks 2u, LEAN risks 0u.
2. No-hindsight runtime policies: drag suppression, strict retained FIRE, and
   selective LEAN expansion.
3. Hindsight ceiling: rows that beat closing price or line, which can define
   the target but cannot directly become a live selector.

First refreshed 2,722-row report:

- Current staked FIRE: `595` rows, `298-297`, `-45.96u` on `721u` risked,
  `-6.4%` ROI.
- Current tracked flat: `1,417` rows, `697-720`, `-105.53u`, `-7.4%` ROI.
- Drag-suppressed tracked flat: `363` rows, `212-151`, `+12.68u`,
  `+3.5%` ROI.
- Strict runtime core flat: `83` rows, `55-28`, `+15.26u`, `+18.4%` ROI.
- Strict plus selective LEAN flat: `215` rows, `133-82`, `+28.02u`,
  `+13.0%` ROI.
- Positive-edge PASS expansion: `9` rows, `1-8`, `-6.95u`, `-77.2%` ROI.
- Price-confirmed hindsight ceiling: `235` rows, `133-102`, `+21.61u`,
  `+9.2%` ROI.

Gate posture: all runtime policies remain `watch_more`, not live promotion.
The positive historical policy shapes are useful, but current-provider,
recent-window, plus-price, worse-CLV, Path B, quality, and market-agreement
slices must survive before any promotion plan.

## Shadow Signal Synthesis Addendum

Tyler asked to mesh the positive shadow signals together instead of evaluating
market-anchor, Strong Base, pre-close proxy, and market agreement in isolation.
The resulting synthesis lab is still read-only and does not approve live model,
threshold, staking, provider, notification, lock, retention, dashboard
source-of-truth, or `formula_change_date` changes.

First refreshed report through the July 8 graded slate:

- Current tracked baseline: `1,460` rows, `722-738`, `-102.70u`, `-7.0%`.
- Market agreement export coverage: `1,935` raw tracker rows, `432` tracked
  covered picks; agreement-with-model was `53` rows, `33-20`, `+6.61u`,
  while agreement-against-model was `46` rows, `21-25`, `-7.29u`.
- Market-anchor strict remained the standout individual anchor: `91` rows,
  `57-34`, `+5.54u`; strict displayed FIRE was `20` rows, `14-6`, `+3.74u`.
- Strong Base strict plus selective LEAN was `222` rows, `138-84`, `+29.43u`.
- Broad no-hindsight combined policy without drag rows was `170` rows,
  `113-57`, `+26.63u`; the higher-conviction watch composite was `131`
  rows, `84-47`, `+20.46u`.

Gate posture: useful enough to keep building a separate canary-review packet,
but not promotion-ready. The next review must stress current-provider, recent,
side, K-line, price, worse-CLV/proxy, Path B, quality, workload, market
agreement, and provider slices before choosing any live policy shape.

Tyler then chose the aggressive unit-accumulation base:
`strict_runtime_core_plus_selective_lean`, not the smaller ROI-first watch
slice. The governing packet is
`docs/research/strict-runtime-core-selective-lean-canary-packet.md`.

Decision framing:

- Primary lens: total units and seasonal volume.
- Candidate baseline: `222` rows, `138-84`, `+29.43u`, `+13.3%`, with `85`
  retained FIRE rows and `137` selective LEAN rows.
- Guardrails: current-provider, recent-window, side, K-line, price,
  market-agreement, pre-close proxy, CLV/proxy, Path B, quality, workload, and
  provider slices.
- Boundary: this remains read-only until Tyler separately approves a
  feature-flagged live canary plan.

## Candidate Lanes

The first report should include these initial lanes:

| Lane | Candidate | Live meaning |
| --- | --- | --- |
| keep-FIRE | `keep_fire_market_agreed_moderate_ev` | Runtime-safe watch bucket for FIRE rows where the model agrees with the market favorite and adjusted EV is moderate. |
| keep-FIRE | `keep_fire_over_moderate_ev_normal_leash` | Runtime-safe watch bucket for FIRE overs with moderate EV and normal leash. |
| expand-LEAN | `expand_lean_45_low_ev_normal_leash` | Runtime-safe watch bucket for LEAN 4.5K rows with low adjusted EV and normal leash. |
| expand-LEAN | `expand_lean_low_k_standard_no_vig` | Runtime-safe watch bucket for low-K-standard LEAN rows with positive no-vig gap. |
| expand-LEAN | `expand_lean_low_line_capped_model_fade` | Odd positive historical bucket that needs provider-era and market-agreement survival before it can matter. |
| cap/suppress | `cap_high_raw_edge` | High raw edge is treated as suspicion until proven otherwise. |
| cap/suppress | `cap_market_fade` | Market-fade mass remains a drag bucket unless a narrow exception earns a plan. |
| cap/suppress | `cap_fire_under_market_fade` | FIRE unders that fade the market remain closed for re-entry. |
| cap/suppress | `avoid_no_or_worse_price_clv_mass` | Process-drag validation target; not a direct live rule because final CLV is post-close. |
| evidence-only | `evidence_clv_supported` | Positive process anchor; must be converted into pre-close/mainline-best-price proxy evidence before live use. |

### Task 1: Add The Strong Base Diagnostic

**Files:**
- Create: `analytics/diagnostics/strong_base_decision_lab.py`
- Create: `tests/test_strong_base_decision_lab.py`

**Interfaces:**
- Consumes: Gate C JSONL rows with fields including `slate_date`, `is_tracked_pick`, `result`, `side`, `display_verdict`, `edge`, `adj_ev`, `model_no_vig_gap`, `model_market_relationship`, `quality_gate_level`, `line_bucket`, `price_sign`, `bet_timing_window`, `leash_risk_bucket`, `pitcher_archetype_bucket`, `batter_handedness_mode`, `lineup_real_split_count`, `market_agreement_label`, `pick_history_pnl`, `beat_close_price`, and `beat_close_line`.
- Produces: `build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]`, `render_report(summary: dict[str, Any]) -> str`, and CLI output at `analytics/output/strong_base_decision_lab.md`.

- [ ] **Step 1: Write the failing tests**

Add tests that assert:

```python
from analytics.diagnostics import strong_base_decision_lab as lab


def test_candidate_rules_cover_keep_expand_cap_and_process_anchor_lanes():
    row = {
        "slate_date": "2026-06-25",
        "is_tracked_pick": True,
        "result": "win",
        "side": "over",
        "display_verdict": "FIRE 1u",
        "edge": 0.045,
        "adj_ev": 0.11,
        "model_no_vig_gap": 0.05,
        "model_market_relationship": "model_agrees_with_favorite",
        "quality_gate_level": "clean",
        "line_bucket": "4.5",
        "price_sign": "minus",
        "bet_timing_window": "pre_30",
        "leash_risk_bucket": "normal",
        "pick_history_pnl": 0.91,
        "beat_close_price": True,
    }

    assert "keep_fire_market_agreed_moderate_ev" in lab.candidate_labels(row)
    assert "keep_fire_over_moderate_ev_normal_leash" in lab.candidate_labels(row)
    assert "evidence_clv_supported" in lab.candidate_labels(row)
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `python -m pytest tests/test_strong_base_decision_lab.py -q`

Expected before implementation: import failure for `strong_base_decision_lab`.

- [ ] **Step 3: Implement the diagnostic**

Implement these exact public functions:

```python
def candidate_labels(row: dict[str, Any]) -> set[str]:
    if not _tracked_win_loss(row):
        return set()
    return {definition.name for definition in candidate_definitions() if definition.rule(row)}


def build_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    selected = analysis_rows(rows)
    tracked = [row for row in selected if _tracked_win_loss(row)]
    nontracked_pass = [row for row in selected if _nontracked_pass(row)]
    positive_pass = [row for row in nontracked_pass if _positive_edge_ev(row)]
    candidates = {
        definition.name: _candidate_summary(definition, tracked)
        for definition in candidate_definitions()
    }
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "total_rows": len(rows),
        "analysis_rows": len(selected),
        "tracked": _stats(tracked),
        "clv": {
            "beat_close_price": _stats([row for row in tracked if clv_bucket(row) == "beat_close_price"]),
            "beat_close_line": _stats([row for row in tracked if clv_bucket(row) == "beat_close_line"]),
            "no_or_worse_price_clv": _stats([row for row in tracked if clv_bucket(row) not in {"beat_close_price", "beat_close_line"}]),
        },
        "pass_expansion": {
            "all_nontracked_pass": _stats(nontracked_pass),
            "positive_edge_ev": _stats(positive_pass),
        },
        "candidates": candidates,
    }
```

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `python -m pytest tests/test_strong_base_decision_lab.py -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add analytics/diagnostics/strong_base_decision_lab.py tests/test_strong_base_decision_lab.py
git commit -m "feat: add strong base decision lab"
```

### Task 2: Generate The First Strong Base Report

**Files:**
- Read: `data/research/gate_c/pitcher_k_outcome_dataset.jsonl` or a temp rebuilt Gate C JSONL.
- Create: `analytics/output/strong_base_decision_lab.md`

**Interfaces:**
- Consumes: `analytics/diagnostics/strong_base_decision_lab.py --input <gate-c-jsonl> --output analytics/output/strong_base_decision_lab.md`
- Produces: first report with executive read, positive CLV vs mass losses, candidate policy draft, slice risks, and next gate.

- [ ] **Step 1: Build a fresh temp Gate C corpus**

Run:

```bash
python scripts/build_pitcher_k_outcome_dataset.py --artifact-source hybrid --output-dir "$env:TEMP\\bbe-strong-base-gate-c" --start-date 2026-04-28
```

Expected: output includes nonzero `rows`, nonzero `tracked`, zero duplicate keys, and clean graded-pick reconciliation except already documented unmatched rows.

- [ ] **Step 2: Generate the report**

Run:

```bash
python analytics/diagnostics/strong_base_decision_lab.py --input "$env:TEMP\\bbe-strong-base-gate-c\\pitcher_k_outcome_dataset.jsonl" --output analytics/output/strong_base_decision_lab.md
```

Expected: command prints `Wrote analytics\output\strong_base_decision_lab.md`.

- [ ] **Step 3: Inspect the report for gate posture**

Run:

```bash
Get-Content analytics/output/strong_base_decision_lab.md -TotalCount 120
```

Expected:
- The report states `Shadow-only`.
- The report includes `Positive CLV vs Mass Losses`.
- The report includes `Candidate Policy Draft`.
- Generic PASS expansion remains closed unless the positive-edge/EV PASS row count is material.
- Any `ready_for_plan` candidate still requires a separate Tyler-approved plan.

- [ ] **Step 4: Commit**

```bash
git add analytics/output/strong_base_decision_lab.md
git commit -m "docs: add strong base decision report"
```

### Task 3: Wire The Lab Into Handoff Surfaces

**Files:**
- Modify: `scripts/run_post_grading_shadow_reports.py`
- Modify: `docs/current-state.md`
- Modify: `C:\Users\TylerReid\.codex\automations\yesterdays-pipeline-health-bbe\memory.md`

**Interfaces:**
- Consumes: generated `analytics/output/strong_base_decision_lab.md`
- Produces: recurring review-only report generation, durable model-lane handoff language, and daily brief overlay.

- [ ] **Step 1: Add the report to the post-grading shadow runner**

In `scripts/run_post_grading_shadow_reports.py`, import the diagnostic and add an output argument:

```python
from analytics.diagnostics import strong_base_decision_lab  # noqa: E402

parser.add_argument("--strong-base-output", type=Path, default=strong_base_decision_lab.DEFAULT_OUTPUT)
```

After `bet_selection_edge_synthesis.main(...)`, call:

```python
strong_base_decision_lab.main([
    "--input",
    str(dataset_path),
    "--output",
    str(args.strong_base_output),
])
```

At the end of `main`, print the decision-facing excerpt:

```python
_print_review_excerpt(
    args.strong_base_output,
    label="Strong Base decision lab",
    section_titles={"Executive Read", "Candidate Policy Draft"},
)
```

- [ ] **Step 2: Update current-state read order**

In `docs/current-state.md`, add `analytics/diagnostics/strong_base_decision_lab.py` beside `bet_selection_edge_synthesis.py` as the read-only report for the Strong Base Expansion and Exposure Reduction Lab.

- [ ] **Step 3: Update model-lane next decision**

In the model lane, add one sentence:

```markdown
The Strong Base Decision Lab is the current read-only umbrella for reconciling positive CLV against mass portfolio losses; it can identify keep-FIRE, expand-LEAN, cap/suppress, and evidence-only candidates, but it does not approve live behavior changes.
```

- [ ] **Step 4: Update automation memory**

Append the run time, report path, candidate posture, and no-live-change guardrail to `C:\Users\TylerReid\.codex\automations\yesterdays-pipeline-health-bbe\memory.md`.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_post_grading_shadow_reports.py docs/current-state.md
git commit -m "docs: wire strong base lab into model lane"
```

### Task 4: Verification

**Files:**
- Read: all modified files

**Interfaces:**
- Consumes: working tree, pytest, generated report.
- Produces: evidence that the framework is read-only and usable.

- [ ] **Step 1: Run focused tests**

Run:

```bash
python -m pytest tests/test_strong_base_decision_lab.py tests/test_bet_selection_edge_synthesis.py -q
```

Expected: all tests pass.

- [ ] **Step 2: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no whitespace errors.

- [ ] **Step 3: Confirm no production behavior files changed unintentionally**

Run:

```bash
git diff --name-only HEAD
```

Expected modified files are limited to:
- `analytics/diagnostics/strong_base_decision_lab.py`
- `tests/test_strong_base_decision_lab.py`
- `scripts/run_post_grading_shadow_reports.py`
- `analytics/output/strong_base_decision_lab.md`
- `docs/superpowers/plans/2026-07-07-strong-base-decision-system.md`
- `docs/current-state.md`

- [ ] **Step 4: Push**

Run:

```bash
git status --short --branch
git push origin main
```

Expected: `main` pushes cleanly to `origin/main`.

## Self-Review

- Spec coverage: The plan maps every requested success criterion to a report surface: good-process vs bad-selection in CLV and drag tables, runtime-safe candidate contexts in the candidate policy draft, positive CLV concentration in the CLV section, keep/expand/cap/evidence-only lanes in candidate definitions, mandatory slices in slice risks, and no live changes in global constraints.
- Placeholder scan: No `TBD`, `TODO`, or unspecified implementation step is required for the first version.
- Type consistency: The public functions are `candidate_labels`, `build_summary`, and `render_report`; tests and CLI use those exact names.
