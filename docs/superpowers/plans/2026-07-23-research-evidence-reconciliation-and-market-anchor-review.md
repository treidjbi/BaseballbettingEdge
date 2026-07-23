# Research Evidence Reconciliation And Market-Anchor Review Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore complete, same-run Gate C and market-agreement evidence and
expand the market-anchor shadow review without changing any live BBE behavior.

**Architecture:** The Gate C archive loader will hydrate only missing outcomes
from one unique exact graded history match. A new read-only exporter will pull
the two existing compact Supabase rollups plus current production artifacts;
the post-grading runner will generate market-agreement labels before its single
Gate C build and render the final tracker afterward. The existing
market-anchor audit will add mandatory slices and leave-one-slate-out reads
without changing the selector.

**Tech Stack:** Python 3.11, pytest, Supabase PostgREST through the existing
`SupabaseMarketWriter`, Netlify/Supabase `get-artifact`, Render cron, Markdown
handoffs.

## Global Constraints

- Work only on `codex/research-evidence-repair` until reviewed and verified.
- Do not mutate production dated archives, `picks_history`, grading state,
  params, published dashboard artifacts, or Supabase rows.
- Do not query scheduled raw `market_snapshots`; export only
  `market_pick_evidence` and `live_market_display_state`.
- Keep `MARKET_ANCHOR_SELECTOR_MODE=shadow` and preserve its selector
  fingerprint and candidate logic.
- Preserve the frozen no-drag selector, fingerprint, 52-row locked base, and
  75-row review floor; do not backfill prospective rows.
- Do not change provider order, provider flags, model math, thresholds,
  staking, notification behavior, locks, UI, accepted bets, retention,
  artifact source, or source-of-truth behavior.
- Only `bbe-gate-c-post-grading-review` may be deployed.
- Never print or commit `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, Render
  tokens, or any other secret.
- Use test-driven development: each production behavior must have a test that
  is observed failing for the expected reason before implementation.

---

## File map

- Modify `analytics/diagnostics/pitcher_k_outcome_dataset.py`: exact archive
  outcome hydration and research provenance.
- Modify `scripts/build_pitcher_k_outcome_dataset.py`: aggregate hydration
  diagnostics into the Gate C summary and manifest.
- Modify `tests/test_pitcher_k_outcome_dataset.py`: archive hydration behavior.
- Modify `tests/test_build_pitcher_k_outcome_dataset.py`: manifest diagnostics.
- Create `scripts/export_market_agreement_inputs.py`: bounded read-only
  Supabase/artifact exporter.
- Create `tests/test_export_market_agreement_inputs.py`: exporter paging,
  validation, atomicity, and secret-safety tests.
- Modify `scripts/run_post_grading_shadow_reports.py`: optional export,
  pre-build tracker, explicit Gate C inputs, and final tracker pass.
- Modify `tests/test_post_grading_shadow_reports.py`: orchestration order and
  backward compatibility.
- Modify `analytics/diagnostics/market_anchor_selector_canary_audit.py`:
  mandatory slices, rolling/current-provider windows, and leave-one-slate-out.
- Modify `tests/test_market_anchor_selector_canary_audit.py`: expanded audit
  contract.
- Modify `docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`:
  Gate C recovery handoff.
- Modify `docs/superpowers/plans/2026-06-07-market-agreement-tracker.md`:
  scheduled compact export handoff.
- Modify `docs/superpowers/plans/2026-06-16-market-anchored-v2-selector-shadow-canary.md`:
  dedicated slice-review result.
- Modify `docs/current-state.md`: Four-Lane Operating Board stage and next
  decisions.

---

### Task 1: Exact Gate C Archive Outcome Recovery

**Files:**
- Modify: `tests/test_pitcher_k_outcome_dataset.py`
- Modify: `analytics/diagnostics/pitcher_k_outcome_dataset.py`
- Modify: `tests/test_build_pitcher_k_outcome_dataset.py`
- Modify: `scripts/build_pitcher_k_outcome_dataset.py`

**Interfaces:**
- Consumes: dated archive pitcher rows and the same local/production
  `picks_history` payload already used by Gate C.
- Produces:
  `build_archive_outcome_index(history_rows, start_date) -> dict`;
  optional `outcome_history_rows` and `outcome_reconciliation_stats` archive
  loader arguments; per-row `archive_outcome_reconciliation_source`; manifest
  `archive_outcome_reconciliation`.

- [ ] **Step 1: Write failing archive hydration tests**

Add focused tests that construct an archive row with full market context but
null `actual_ks`, then supply history explicitly:

```python
def test_load_archived_markets_recovers_missing_actual_from_one_exact_graded_history_row(tmp_path):
    archive = tmp_path / "2026-06-16.json"
    archive.write_text(json.dumps({
        "pitchers": [{
            "pitcher": "Adrian Houser",
            "k_line": 3.5,
            "actual_ks": None,
            "result": None,
            "best_over_odds": 114,
            "best_under_odds": -146,
            "ev_over": {"verdict": "PASS"},
            "ev_under": {"verdict": "LEAN"},
        }]
    }), encoding="utf-8")
    stats = {}

    markets = dataset.load_archived_markets_for_dataset(
        tmp_path,
        start_date="2026-06-16",
        end_date="2026-06-16",
        outcome_history_rows=[{
            "date": "2026-06-16",
            "pitcher": "Adrian Houser",
            "side": "under",
            "locked_k_line": 3.5,
            "result": "win",
            "actual_ks": 2,
        }],
        outcome_reconciliation_stats=stats,
    )

    assert len(markets) == 1
    assert markets[0]["actual_ks"] == 2
    assert markets[0]["winning_side"] == "under"
    assert markets[0]["archive_outcome_reconciliation_source"] == "picks_history_exact"
    assert stats == {"recovered_markets": 1, "ambiguous_markets": 0}
```

Add separate tests proving that an archive-provided actual is never
overwritten and that line mismatch, ungraded history, missing `actual_ks`, and
two exact candidates remain excluded while incrementing ambiguity only for the
two-candidate case.

- [ ] **Step 2: Run the new tests and verify RED**

Run:

```powershell
python -m pytest tests/test_pitcher_k_outcome_dataset.py -k "archive and (recover or outcome)" -q
```

Expected: FAIL because the new loader arguments/provenance do not exist and the
Adrian-shaped row is filtered.

- [ ] **Step 3: Implement the minimal exact-match index and hydration**

In `pitcher_k_outcome_dataset.py`, add:

```python
def build_archive_outcome_index(
    history_rows: list[dict[str, Any]],
    *,
    start_date: str = CLEAN_WINDOW_START,
) -> dict[tuple[str, str, float], list[dict[str, Any]]]:
    index: dict[tuple[str, str, float], list[dict[str, Any]]] = {}
    for pick in history_rows:
        slate_date = str(pick.get("date") or pick.get("slate_date") or "").strip()
        line = _to_float(
            pick.get("locked_k_line")
            if pick.get("locked_k_line") is not None
            else pick.get("k_line")
        )
        result = str(pick.get("result") or "").strip().lower()
        actual = _to_float(pick.get("actual_ks"))
        normalized = _normalized(pick.get("pitcher"))
        if (
            slate_date < start_date
            or not normalized
            or line is None
            or result not in {"win", "loss"}
            or actual is None
        ):
            continue
        index.setdefault((slate_date, normalized, line), []).append(pick)
    return index
```

Update `_markets_from_archive_payload()` to copy the record, consult only the
exact `(date, normalized pitcher, archive line)` key when `actual_ks` is null,
recover only when `len(candidates) == 1`, and leave all ambiguous/missing cases
to the existing filter. Do not infer from side or result alone.

Thread optional `outcome_history_rows` and
`outcome_reconciliation_stats` through local and remote archive loaders.
Initialize missing stat keys to zero and increment recovered/ambiguous market
counts exactly once per archive pitcher.

- [ ] **Step 4: Run Gate C unit tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_pitcher_k_outcome_dataset.py -q
```

Expected: all tests pass, including the new exact-match and fail-closed cases.

- [ ] **Step 5: Write failing builder diagnostics tests**

Update the builder tests so mocked `dataset.build_dataset()` writes:

```python
diagnostics["archive_outcome_reconciliation"] = {
    "recovered_markets": 1,
    "ambiguous_markets": 0,
}
```

Assert the generated manifest contains that exact object and the rendered
summary input receives both counters.

- [ ] **Step 6: Run builder diagnostics tests and verify RED**

Run:

```powershell
python -m pytest tests/test_build_pitcher_k_outcome_dataset.py -q
```

Expected: FAIL because the builder does not pass or persist diagnostics.

- [ ] **Step 7: Aggregate diagnostics through hybrid builds**

Add an optional `diagnostics` mapping to `dataset.build_dataset()`. Load the
history payload once for archive hydration and use it for history enrichment.

Change `_build_rows()` to return:

```python
tuple[list[dict[str, Any]], list[str], dict[str, int]]
```

Aggregate `recovered_markets` and `ambiguous_markets` across the local base and
production fill dates. Add the aggregate to both `summary_counts` and the
manifest as:

```python
"archive_outcome_reconciliation": {
    "recovered_markets": recovered,
    "ambiguous_markets": ambiguous,
}
```

- [ ] **Step 8: Run builder and dataset tests**

Run:

```powershell
python -m pytest tests/test_pitcher_k_outcome_dataset.py tests/test_build_pitcher_k_outcome_dataset.py -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit Task 1**

```powershell
git add analytics/diagnostics/pitcher_k_outcome_dataset.py scripts/build_pitcher_k_outcome_dataset.py tests/test_pitcher_k_outcome_dataset.py tests/test_build_pitcher_k_outcome_dataset.py
git commit -m "fix: reconcile exact Gate C archive outcomes"
```

---

### Task 2: Bounded Compact Market-Agreement Input Export

**Files:**
- Create: `scripts/export_market_agreement_inputs.py`
- Create: `tests/test_export_market_agreement_inputs.py`

**Interfaces:**
- Consumes:
  `SupabaseMarketWriter`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`,
  production artifact API URL, inclusive start/end dates.
- Produces:
  `export_inputs(writer, artifact_loader, output_dir, start_date, end_date,
  page_size=1000) -> dict[str, Any]` plus four JSON inputs and one manifest.

- [ ] **Step 1: Write failing pagination and source-boundary tests**

Create a fake writer with `count_rows()` and `select_rows()` call recording.
Use 1,005 evidence rows and 1,001 display rows. Assert:

```python
result = exporter.export_inputs(
    writer=fake_writer,
    artifact_loader=fake_artifact_loader,
    output_dir=tmp_path,
    start_date="2026-04-28",
    end_date="2026-07-23",
    page_size=1000,
)

assert result["tables"]["market_pick_evidence"]["rows"] == 1005
assert result["tables"]["live_market_display_state"]["rows"] == 1001
assert {call.table for call in fake_writer.select_calls} == {
    "market_pick_evidence",
    "live_market_display_state",
}
assert all(
    call.params["and"] == "(slate_date.gte.2026-04-28,slate_date.lte.2026-07-23)"
    for call in first_page_calls
)
assert not any(call.table == "market_snapshots" for call in fake_writer.select_calls)
```

Also assert offsets `0`, `1000`, stable `order`, and inclusive upper-date
filter are passed.

- [ ] **Step 2: Run exporter tests and verify RED**

Run:

```powershell
python -m pytest tests/test_export_market_agreement_inputs.py -q
```

Expected: collection/import failure because the exporter module does not exist.

- [ ] **Step 3: Implement page collection and artifact loading**

Create a small module with:

```python
COMPACT_TABLES = ("market_pick_evidence", "live_market_display_state")
DEFAULT_OUTPUT_DIR = ROOT / "analytics" / "output" / "market_agreement_inputs"
DEFAULT_PAGE_SIZE = 1000


def _table_params(start_date: str, end_date: str, limit: int, offset: int) -> dict[str, str]:
    return {
        "select": "*",
        "and": f"(slate_date.gte.{start_date},slate_date.lte.{end_date})",
        "order": "slate_date.asc,normalized_pitcher.asc,side.asc,provider.asc,observed_at.asc,id.asc",
        "limit": str(limit),
        "offset": str(offset),
    }
```

If PostgREST rejects the combined `and` expression in the observed project,
use distinct supported query keys produced by a dedicated request helper; pin
the final tested request shape in the unit test. Do not weaken either date
bound.

Count each table with identical filters before paging. Require every returned
item to be an object, deduplicate by `id` falling back to `dedupe_key`, and
require fetched unique rows to equal the exact count.

Load `picks_history` and `today` through the existing production artifact URL
contract. Filter history rows to the inclusive date range.

- [ ] **Step 4: Add failing atomicity, manifest, and secret-safety tests**

Assert:

- all fetches finish before any final file is replaced;
- a second-page exception leaves prior files byte-for-byte unchanged;
- manifest counts, min/max dates, hashes, and generation timestamp exist;
- manifest/log text excludes fake secret values;
- missing credentials make CLI `main()` exit before creating output; and
- malformed artifact/table payloads fail.

- [ ] **Step 5: Run the new tests and verify RED**

Run:

```powershell
python -m pytest tests/test_export_market_agreement_inputs.py -q
```

Expected: FAIL on missing atomic write/manifest/CLI behavior.

- [ ] **Step 6: Implement staged writes, manifest, and CLI**

Build every payload in memory first. Write all files into a temporary sibling
directory, validate their hashes/counts, then replace the five final files.
The manifest shape is:

```python
{
    "artifact": "market_agreement_inputs",
    "generated_at": generated_at,
    "shadow_only": True,
    "start_date": start_date,
    "end_date": end_date,
    "tables": {
        table: {"rows": len(rows), "min_date": ..., "max_date": ...}
        for table, rows in table_rows.items()
    },
    "artifacts": {
        "picks_history": {"rows": len(history_rows)},
        "today": {"slate_date": today_payload.get("slate_date")},
    },
    "files": {name: {"sha256": digest} for name, digest in hashes.items()},
    "guardrails": [
        "read_only",
        "compact_tables_only",
        "no_market_snapshots",
        "no_live_behavior_change",
    ],
}
```

CLI `main()` reads required credentials without printing them and constructs
`SupabaseMarketWriter`. Default end date uses `America/Phoenix`.

- [ ] **Step 7: Run exporter tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_export_market_agreement_inputs.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit Task 2**

```powershell
git add scripts/export_market_agreement_inputs.py tests/test_export_market_agreement_inputs.py
git commit -m "feat: export compact market agreement inputs"
```

---

### Task 3: Same-Run Post-Grading Orchestration

**Files:**
- Modify: `tests/test_post_grading_shadow_reports.py`
- Modify: `scripts/run_post_grading_shadow_reports.py`

**Interfaces:**
- Consumes Task 2's exporter and its fixed output filenames.
- Produces an explicit `--refresh-market-agreement-inputs` scheduled mode that
  exports, prebuilds agreement, builds Gate C once, then renders final
  agreement before downstream consumers.

- [ ] **Step 1: Preserve the existing flag-off contract**

Run the existing runner test before editing:

```powershell
python -m pytest tests/test_post_grading_shadow_reports.py -q
```

Expected: pass. Keep its exact call-order assertion unchanged for flag-off
behavior.

- [ ] **Step 2: Write a failing scheduled-export orchestration test**

Add a second test with monkeypatched exporter, tracker, builder, and downstream
audits. The exporter fake creates:

```text
market_pick_evidence.json
live_market_display_state.json
picks_history.json
today.json
manifest.json
```

Call:

```python
runner.main([
    "--refresh-market-agreement-inputs",
    "--market-agreement-input-dir", str(input_dir),
    "--output-dir", str(output_dir),
    "--market-agreement-output-md", str(agreement_md),
    "--market-agreement-output-jsonl", str(agreement_jsonl),
])
```

Assert call order begins:

```python
[
    "export_inputs",
    "market_agreement_prebuild",
    "gate_c_build",
]
```

Assert the builder receives:

```text
--market-agreement-tracker <agreement_jsonl>
--live-market-display <input_dir/live_market_display_state.json>
```

Assert the final tracker runs after the builder with the fresh Gate C JSONL,
then Shadow Signal Synthesis and no-drag consume those final paths.

- [ ] **Step 3: Run the scheduled-mode test and verify RED**

Run:

```powershell
python -m pytest tests/test_post_grading_shadow_reports.py -k "scheduled or refresh" -q
```

Expected: FAIL because the flag/export/order do not exist.

- [ ] **Step 4: Implement the explicit scheduled mode**

Import Task 2's exporter and add:

```python
parser.add_argument("--refresh-market-agreement-inputs", action="store_true")
parser.add_argument(
    "--market-agreement-input-dir",
    type=Path,
    default=export_market_agreement_inputs.DEFAULT_OUTPUT_DIR,
)
```

Extend `_market_agreement_args()` to accept explicit history and current
artifact paths.

When refresh is enabled:

1. invoke the exporter before the builder;
2. assign the four generated paths;
3. run the tracker once using production history/current artifact and the
   existing Gate C file when present;
4. pass the new tracker/display paths to the builder;
5. build Gate C once;
6. run the tracker again using the new Gate C JSONL; and
7. continue existing downstream reports.

When disabled, retain the current builder-first/single-tracker path.

- [ ] **Step 5: Run runner tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_post_grading_shadow_reports.py tests/test_market_agreement_tracker.py tests/test_pitcher_k_outcome_dataset.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 3**

```powershell
git add scripts/run_post_grading_shadow_reports.py tests/test_post_grading_shadow_reports.py
git commit -m "feat: refresh agreement evidence before Gate C"
```

---

### Task 4: Dedicated Market-Anchor Shadow Slice Review

**Files:**
- Modify: `tests/test_market_anchor_selector_canary_audit.py`
- Modify: `analytics/diagnostics/market_anchor_selector_canary_audit.py`

**Interfaces:**
- Consumes the unchanged Gate C row contract.
- Produces summary keys `clean_selector_rows`, `review_status`,
  `strict_windows`, `strict_fire_windows`, `strict_slices`,
  `strict_fire_slices`, `leave_one_slate_out`, and missing-coverage counts.

- [ ] **Step 1: Write failing slice/window tests**

Build rows across dates before/after 2026-06-24 and include:

- strict OVER/UNDER;
- 4.5/6.5 lines;
- clean/capped quality;
- pre-30/unknown timing;
- strong/weak pre-close proxy;
- normal/high workload;
- Path B real/mixed;
- provider/missing attribution;
- market-with-model/missing agreement; and
- one non-strict displayed FIRE.

Assert:

```python
summary["clean_selector_rows"] >= 1
summary["strict_windows"]["current_provider"]["rows"] == expected
summary["strict_fire_windows"]["recent_14_slates"]["rows"] == expected
summary["strict_slices"]["side"]["under"]["pnl"] == expected
summary["strict_slices"]["market_agreement"]["missing"]["rows"] == expected
summary["leave_one_slate_out"]["strict_all"]["minimum"]["pnl"] == expected
summary["strict_fire_all_over"] is True
summary["review_status"] == "separate_shadow_review_ready"
```

Add a render test requiring explicit raw-floor, all-OVER concentration,
blocking-slice, new-selector/fingerprint, and `enforce_downside`-closed
language.

- [ ] **Step 2: Run market-anchor tests and verify RED**

Run:

```powershell
python -m pytest tests/test_market_anchor_selector_canary_audit.py -q
```

Expected: FAIL because the expanded fields/sections do not exist.

- [ ] **Step 3: Implement stable bucket helpers and windows**

Add constants:

```python
CURRENT_PROVIDER_START_DATE = date(2026, 6, 24)
REVIEW_CLEAN_SELECTOR_FLOOR = 150
REVIEW_STRICT_FLOOR = 75
RECENT_SLATE_COUNT = 14
```

Implement explicit bucket functions for the mandatory dimensions. Reuse the
existing `strong_base_decision_lab` Path B/final-CLV/provider-era helpers and
`gate_f_preclose_clv_proxy_lab.preclose_clv_proxy_label`; do not import the
no-drag canary.

Build slices for strict-all and strict displayed FIRE, count `missing`
coverage, and calculate the latest 14 distinct strict dates.

For every slate date, score rows excluding that date. Store the minimum and
maximum PnL cases with excluded date, rows, W-L, PnL, and ROI.

Set:

```python
review_status = (
    "separate_shadow_review_ready"
    if clean_selector_rows >= 150
    and strict_all_score["rows"] >= 75
    and leave_one_out_min["pnl"] > 0
    else "collecting"
)
```

This status never means promotion-ready.

- [ ] **Step 4: Render the dedicated review**

Add concise sections:

- Executive Read;
- Review Floors And Windows;
- Strict Displayed FIRE Concentration;
- Mandatory Strict Slices;
- Leave-One-Slate-Out;
- Blocking Evidence;
- Promotion Gate.

Always state that a narrowed OVER-only candidate would require a new selector
id, fingerprint, baseline, plan, and prospective canary.

- [ ] **Step 5: Run market-anchor tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_market_anchor_selector_canary_audit.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit Task 4**

```powershell
git add analytics/diagnostics/market_anchor_selector_canary_audit.py tests/test_market_anchor_selector_canary_audit.py
git commit -m "feat: expand market anchor shadow review"
```

---

### Task 5: Integrated Research Verification And Handoffs

**Files:**
- Modify: `docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md`
- Modify: `docs/superpowers/plans/2026-06-07-market-agreement-tracker.md`
- Modify: `docs/superpowers/plans/2026-06-16-market-anchored-v2-selector-shadow-canary.md`
- Modify: `docs/current-state.md`

**Interfaces:**
- Consumes Tasks 1-4 and current production read-only evidence.
- Produces current controlling handoffs with every promotion gate still closed.

- [ ] **Step 1: Run focused research tests**

```powershell
python -m pytest tests/test_pitcher_k_outcome_dataset.py tests/test_build_pitcher_k_outcome_dataset.py tests/test_export_market_agreement_inputs.py tests/test_post_grading_shadow_reports.py tests/test_market_agreement_tracker.py tests/test_market_anchor_selector_canary_audit.py tests/test_no_drag_composite_canary_audit.py -q
```

Expected: zero failures.

- [ ] **Step 2: Run the complete test suites**

```powershell
python -m pytest tests -q
node --test dashboard/*.test.mjs tests/*.mjs
```

Expected: zero failures. If the known retired-BoltOdds timing test fails
identically on untouched `main`, document the base-branch reproduction and
rerun the full suite with only that exact test deselected; do not change
retired runtime behavior to satisfy it.

- [ ] **Step 3: Run a production-artifact Gate C verification build**

Use a temporary directory outside the repo:

```powershell
python scripts/build_pitcher_k_outcome_dataset.py --artifact-source hybrid --end-date 2026-07-22 --output-dir <validated-temp-dir>
```

Expected:

- zero duplicate dataset keys;
- `1,624/1,624` graded tracked picks reconciled;
- one exact archive outcome recovered;
- zero ambiguous recoveries.

- [ ] **Step 4: Run a live compact export/tracker verification**

Run the exporter against the linked production Supabase project without
printing credentials, writing only to a validated temporary directory. Then
run the tracker from those files and the temporary Gate C dataset.

Expected:

- both compact table exports are nonzero and date-bounded;
- raw `market_snapshots` is never queried;
- tracker output is nonzero;
- no Supabase write occurs.

- [ ] **Step 5: Regenerate the market-anchor and no-drag audits**

Run both diagnostics against the temporary Gate C JSONL.

Expected:

- market-anchor raw floors are met;
- strict displayed FIRE remains separately reported;
- negative/missing mandatory slices keep enforcement closed;
- no-drag selector fingerprint is unchanged;
- the counter changes only if newly graded normal rows legitimately qualify.

- [ ] **Step 6: Update controlling handoffs**

Append dated implementation evidence to the three controlling plans. Update
the Four-Lane Operating Board:

- pipeline/infrastructure: research cron input wiring repaired; production
  pipeline unchanged;
- model: market-anchor separate shadow review ready, enforcement closed;
- UI: unchanged;
- tracking/history: Gate C fully reconciled and scheduled agreement inputs
  restored, but Gate C/D/E/F/12E promotion gates remain closed.

- [ ] **Step 7: Commit Task 5**

```powershell
git add docs/current-state.md docs/superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md docs/superpowers/plans/2026-06-07-market-agreement-tracker.md docs/superpowers/plans/2026-06-16-market-anchored-v2-selector-shadow-canary.md
git commit -m "docs: record research evidence repair gates"
```

---

### Task 6: Push And Isolated Research-Cron Deployment

**Files:**
- No source-file changes unless verification finds a scoped defect.
- Update the automation memory outside the repo after deployment verification.

**Interfaces:**
- Consumes the reviewed branch and existing Render service
  `crn-d8mpcb0g4nts73fq5bv0`.
- Produces one verified research-cron deploy and no other service/config
  mutation.

- [ ] **Step 1: Verify Git state and push**

```powershell
git status --short --branch
git log --oneline origin/main..HEAD
git push origin codex/research-evidence-repair
```

Expected: only intended commits; local and remote branch SHAs match.

- [ ] **Step 2: Inspect the research cron environment names safely**

Read the complete environment-variable list through the authenticated Render
API or Dashboard. Output names/presence only, never values.

Expected:

- `SUPABASE_URL` present; and
- `SUPABASE_SERVICE_ROLE_KEY` present.

If either is missing, use Tyler's explicit approval of the reviewed design to
copy only the existing production values into this research cron through a
full-list preserve-and-verify update. Do not alter or omit any existing key.
Reread names after the update without printing values.

- [ ] **Step 3: Merge the reviewed branch**

After all tests and reviews pass:

```powershell
git switch main
git pull --ff-only
git merge --ff-only codex/research-evidence-repair
git push origin main
```

Expected: local `main`, `origin/main`, and remote main match.

- [ ] **Step 4: Update only the research cron command**

Preserve schedule, branch, plan, build command, and auto-deploy. Change only:

```text
python scripts/run_post_grading_shadow_reports.py
```

to:

```text
python scripts/run_post_grading_shadow_reports.py --refresh-market-agreement-inputs
```

- [ ] **Step 5: Deploy only the research cron**

Trigger a manual deploy of `crn-d8mpcb0g4nts73fq5bv0`, wait for `live`, then
run one manual job using the service command.

Expected: build and job succeed; no other service deploy is triggered.

- [ ] **Step 6: Verify deployed outputs**

Read job logs and generated report excerpts. Confirm:

- compact evidence export counts and date bounds are nonzero;
- Gate C reconciliation is complete;
- market-agreement rows are nonzero;
- market-anchor report contains the expanded review and keeps shadow;
- no-drag fingerprint/counter contract is preserved;
- no provider call, Supabase write, pipeline publication, notification, or
  lock action occurred.

- [ ] **Step 7: Verify production isolation**

Check fresh production `today`, published-artifact metadata, lock rows,
notification counts, provider posture, and latest pipeline deploys.

Expected: no change attributable to the research deployment.

- [ ] **Step 8: Update automation memory**

Record the final commit/deploy/job IDs, exact research counts, gate decisions,
and any remaining observation items with the current Phoenix timestamp.

---

## Rollback

If the research cron fails:

1. restore its prior command;
2. redeploy the prior known-good commit;
3. verify the next manual research job returns to its prior output;
4. preserve failure logs and input manifests for diagnosis; and
5. do not touch live pipeline, provider, notification, lock, UI, artifact, or
   retention configuration.

No Supabase data rollback or production artifact rollback is required because
this plan performs only reads and generated research-file writes.
