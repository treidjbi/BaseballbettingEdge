# Model Audit & Gap Closure Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the three buckets of issues surfaced by the post-4/8 performance inspection — data-plumbing bugs silently degrading existing signals, analytics-tool additions that let us measure where the model bleeds, and model-signal additions (opener detection, park factors, rest, K-variance) the current pipeline is missing.

**Architecture:** Three-phase rollout with hard pause checkpoints between phases. Phase A (plumbing) is investigation-first: cheap diagnostic scripts confirm scope, then we fix or document — ordered by leverage (A1 pitcher_throws → A3 ump → A2 opening_odds → A4 bookmaker). Phase B extends `analytics/performance.py` with measurement slices (B1–B4) AND sustainability instruments (B5 signal-activation rates, B6 feature-contribution audit) so silent feature death and calibration drift are visible going forward. Phase C adds new model signals (C1 opener, C2 park, C3 rest, C4 K-variance) one at a time so the adaptive calibrator can absorb each cleanly, then C5 surfaces data-source degradation in `today.json` and the dashboard. User can stop at any checkpoint.

**Tech Stack:** Python 3.11, pytest, pandas, matplotlib, requests, scipy (Poisson). No new external dependencies.

---

## Scope Note

Phase C's four items (opener, park, rest, K-variance) are each substantial enough to warrant their own plan. This plan sequences them after A+B so data from Phase B can confirm they're worth building *and* inform how to build them. **Strong recommendation: pause after Phase B** and either continue into Phase C here, or split Phase C into a dedicated plan informed by B's findings.

Phase A tasks are investigation-first. Each starts with a diagnostic that quantifies the issue before writing a fix, because the root cause isn't yet known — the fix pattern (retry? backfill? schema bug? feature legitimately dormant?) depends on what the diagnostic reveals.

---

## Pre-work

- [ ] **Step 0.1: Confirm tests pass on the starting branch**

```bash
git status
python -m pytest tests/ -q
```

Expected: **pytest exits 0** (currently 242 passing). The working tree may contain untracked plan files under `docs/superpowers/plans/` and modified pipeline files from in-flight work — both are OK. The hard gate is a green test suite, not a clean tree. If tests fail, stop and diagnose before starting Phase A.

- [ ] **Step 0.2: Snapshot the current metrics baseline**

Run the analytics once and save the output for later comparison:

```bash
python analytics/performance.py --since 2026-04-08 > analytics/output/baseline_2026-04-16.txt
```

Expected: file created. This is our reference point for detecting regressions during Phase C.

---

## Global policies (apply to every phase)

**P1 — Don't backfill in ways that change historical audit meaning.** The model's `formula_change_date` and calibration window depend on historical picks reflecting the state of the model *at the time they were made*. Safe backfills: filling a field that was None due to a plumbing bug (A1 pitcher_throws). Unsafe backfills: retroactively applying a new lambda multiplier (park factors, rest deltas) to already-graded picks — this would make the pre- and post-change data look artificially consistent and break calibration. When in doubt: don't backfill; start the signal forward-only from its deploy date.

**P2 — Diagnostics that read `picks_history.json` must guard for its absence.** A fresh clone or CI runner doesn't have the file. Every diagnostic script in this plan should begin with:

```python
HIST = ROOT / "data" / "picks_history.json"
if not HIST.exists():
    print(f"ERROR: {HIST} not found. Run the pipeline at least once to generate it.")
    raise SystemExit(1)
```

**P3 — Use `is not None` over truthiness for odds/numeric fields in diagnostics.** American odds won't be 0, but `if p.get("opening_over_odds"):` is a correctness smell. Prefer `if p.get("opening_over_odds") is not None:` consistently.

**P4 — Preserve the live calibration state and grading history. Improvements are forward-only.** The adaptive calibrator has been running for weeks; `lambda_bias` (currently ~-0.55) is actively converging. Historical grades in `picks_history.json` encode the decisions the model made at the time they were made. This implementation **must not**:

1. Reset, zero, or manually edit `lambda_bias` or any other field in [data/params.json](data/params.json). Let the calibrator keep adjusting it. This holds at merge-to-main boundaries too (Phase A → B, B → C, C → done): merging formula changes does NOT reset the bias.
2. Wipe, regrade, or retroactively modify existing rows in [data/picks_history.json](data/picks_history.json). New fields land as absent-on-historical (see P1); existing results and graded outcomes stay exactly as they are.
3. Delete or rebuild [data/results.db](data/results.db) manually — it's ephemeral and rebuilt from `picks_history.json` every run; leave that mechanism alone.
4. **Do NOT bump `formula_change_date` in `params.json` anywhere in this plan — not in Phase A, not in Phase B, not in Phase C.** User decision (2026-04-17): `lambda_bias` is an additive self-healing scalar that will drift to absorb whatever small mean-lambda shift each new signal introduces. Resetting the calibration window would throw away the ~200+ graded picks of convergence momentum currently powering fast re-calibration — a bigger loss than the small transient distortion from stale residuals. C-phase signals (park factors, rest deltas, tail-risk haircut) activate forward-only via their deploy dates and let the bias self-heal through drift. **If any implementer for any future task thinks `formula_change_date` needs a bump, stop and ask the user first — do not assume precedent.**

If any task in this plan appears to require touching those live files beyond schema-additive migrations (new nullable columns, new optional JSON fields), **stop and ask the user before proceeding.** The whole point of this plan is to let every signal we add earn its weight against the existing calibrated baseline.

---

## PHASE A — Data Plumbing Verification

### Execution log (update as tasks complete)

Branch: `model-audit-phase-a` (off `main` at `30ddb01`).
Merge-to-main strategy: fold the whole branch back to `main` at the Phase A→B
HARD STOP checkpoint.

**Calibration handling at merge (IMPORTANT — user decision, policy P4):**
- **Do NOT bump `formula_change_date`.** `lambda_bias` (currently ~`-0.55` and
  converging) stays untouched. The bias scalar is additive and self-healing:
  if Path A + A1 shift mean lambda by a few hundredths, lambda_bias will drift
  to absorb that over the next 1–2 weeks of fresh picks. Resetting would cost
  the ~200+ graded picks of residual history powering current convergence
  speed, which is a larger loss than the small formula-drift distortion.
- **Do NOT reset grading.** Grades are boolean facts about actual K counts; they
  don't depend on the formula that produced the line.
- **Do** note the formula tightening in the merge commit body as a breadcrumb
  for future debugging.

| Task | Status | Commits | Notes |
|---|---|---|---|
| Pre-work 0.1–0.3 | ✅ done | `30ddb01` | Tests green (242), baseline snapshot captured in commit body. |
| A1 — pitcher_throws | ✅ done | `0407846`, `517f473`, `8a76f30`, `8463f8e`, `16d513e`, `cbbce97` | See A1 block below. Tests 242→243. Bug window docs in `docs/data-caveats.md`, pointer in CLAUDE.md (`8c4210c`). |
| Path A platoon delta | ✅ done | `e824447` | Latently dormant before A1 (every pitcher was `"R"`). Tests 97/97 in build_features. |
| A3 — ump_k_adj (investigation) | ✅ done (path A3.5) | `7d9f11b`, `2760244`, `0b1c066` | Finding: **ump.news domain is NXDOMAIN** — permanently dead. 447/447 historical picks have `ump_k_adj = 0.0`. Documented + pinned contract tests. Tests 243→251. |
| A3-fix — source replacement | ✅ done | `0142b0f`, `f09a4ee`, `9507dd0`, `0308536` | **User picked option (a): replace source.** Swapped to MLB Stats API `/schedule?hydrate=officials` (same API we already use for pitcher stats). `scrape_hp_assignments` renamed to `fetch_hp_assignments(date_str)`; `fetch_umpires(props, date_str)` threads the date through; `_abbr_for_team_name` helper added for reverse lookup. Fixed latent `ump_ok` logic bug (was staying True on silent empty dict — now `ump_ok = len(ump_map) > 0 and any(v != 0.0 for v in ump_map.values())`) **Option W**: forward-only, historical `data_complete=True` rows preserved (P4 — calibration momentum protected). Code-review fixes in `0308536`: docstring accuracy + **OAK abbreviation updated to `"Athletics"`** (A's relocated — both TheRundown and MLB API now return "Athletics" with no city prefix, was silently skipping every A's game in the reverse lookup) + unknown-team log level `info → warning`. Tests 251→259. Caveat note added to `docs/data-caveats.md`. **Known coverage cap flagged as follow-up:** `data/umpires/career_k_rates.json` only has 30 umpires (includes retired names); actual 2026 HP umpire match rate is ~21% (13/62 unique umps). Expanding the file is A3b below. |
| A3b.0 — source spike | ✅ done | `c326deb` | Evaluated 4 sources. Picked MLB Stats API `/game/{pk}/boxscore` aggregation. Rejected: umpscorecards.com (accuracy-focused metrics, cross-checked anti-correlated with hand-curated K-rates), pybaseball statcast (`umpire` column deprecated, always NaN), BR/FanGraphs/Savant (403/404). Full rationale in `analytics/diagnostics/a3b_source_spike.py` docstring. |
| A3b.1 — seeder script | ✅ done | `f54f184` | `scripts/seed_umpire_career_rates.py` — resumable (progress persisted per-day to `analytics/output/seed_progress.json`, gitignored), exponential-backoff retries on transient failures, individual game errors logged but don't stop the run. |
| A3b.2 — seed run | ✅ done | — | Started 2026-04-17 14:32 local; laptop sleep stopped it at day 492/553 ~4:41pm Friday. Resumed Monday 2026-04-20 08:56 via resumable progress file (no data loss). Completed 09:13. Total: 4,855 games aggregated, 96 unique HP umps seen, league mean 16.86 K/game. |
| A3b.3 — write + verify + commit | ✅ done | *(see git log — commit after `0c57be1` on phase-a)* | 87 umps written (filtered at n≥20). Live 2026 match rate jumped **22% → 94%** (59/63 umps seen in past week). 4 umps still missing (Felix Neon, Jen Pawol, Tyler Jones, Willie Traynor) — AAA call-ups without enough 2024-25 MLB sample. `docs/data-caveats.md` updated. Scale: seeder deltas range ±1.9 K/game (vs hand-curated ±0.52), `ump_scale` (currently 1.0) will shrink during phase-2 calibration as ump-signal residuals accumulate. |
| A2 — opening_odds | ✅ done (Option 2 — premise refuted, enum added) | `0ff1699` (diag), `0496053` (final polish), `3922ebf` (impl, pre-rebase SHA) | **Diagnostic refuted the plan's null-writer premise.** Of 306 null-opening rows, ALL have null `best_*_odds` too — they're pre-ALTER-TABLE-ADD-COLUMN legacy rows that couldn't be back-filled by `seed_picks` UPDATE (locked/graded rows). Post-migration cohort (141 picks since 2026-04-11): opening_*_odds populated 141/141 (100%), movement_conf != 1.0 fires on 9.2%. No live null-writer bug. **Still shipped Option 2** to fix the remaining semantic gap: `fetch_odds` always computes opening from `best - price_delta` (within-day), but `_apply_preview_openings` can upgrade to overnight 7pm baseline — previously indistinguishable to `calc_movement_confidence`. Added `opening_odds_source` ∈ {"preview", "first_seen", None}; gated haircut to only fire when source=="preview". Full plumbing: fetch_odds tags "first_seen", preview-merge promotes to "preview", schema+migration in fetch_results, INSERT captures/UPDATE freezes, export round-trips, build_features gates. 14 new tests. Tests 280→294. **Also included: rebase of phase-a onto origin/main** (brought in steam Phase A per-book odds tracking + v2 UI finalization; 1 trivial .gitignore conflict resolved; 1 pre-existing `test_write_dated_archive_only_creates_dated_file` failure on main is NOT ours — index-schema drift, flagged by steam authors). Spec-review + code-review both passed. |
| A4 — bookmaker breakdown | ✅ done | `d2c27b3` | Added `by_bookmaker(df)` to `analytics/performance.py` + wired into `main()`. Smoke-tested with `--since 2026-04-08`: 6 book rows, FanDuel dominates at 132/231 staked (57%), 63 `<unknown>` rows are pre-column-migration legacy. Follow-up flagged (not A4-scope): `ref_book` values are stored as raw TheRundown numeric IDs (`Book25`, `Book3`, etc.) except FanDuel which resolves to a name — worth wiring `fetch_odds.TRACKED_BOOKS` through the display path in a later Phase B refinement. Added defensive `ref_book not in columns` guard since `analytics/` isn't in pytest coverage. |
| A→B checkpoint — merge | ✅ done (2026-04-21) | `phase-a` → `main` | Full branch merged. Book-scoping finalized as Option B (priority-only, no fallback — `fetch_odds._select_ref_book` returns `(None, None)` when no target book is available, caller skips pick). Post-merge live run confirmed 25/28 picks on FanDuel, `opening_odds_source` split 20 preview / 5 first_seen / 3 missing — all correct per A2 design. V2 UI smoke-tested OK. Companion infra work folded in same sitting: branch tree cleaned (21 stale remotes + 2 local + 2 tags pruned), preview cron moved 7pm → midnight (cron `0 2 * * *` → `0 7 * * *`, date arg `TOMORROW` → `TODAY`, CLAUDE.md schedule block updated), `pipeline/run_pipeline.py` + `pipeline/fetch_odds.py` + tests doc-drift "7pm" → "midnight" sweep. `lambda_bias` and `formula_change_date` untouched per P4. |
| A→B checkpoint — soak re-audit | ⏳ pending | — | **Re-audit Phase A diagnostics after a couple of slates have run under the post-Option-B + midnight-preview pipeline.** Re-run `a1_pitcher_throws.py`, `a2_opening_odds.py`, `a3_ump_adj.py` against the fresh sample; confirm activation rates moved (pitcher_throws null → ~0% forward-only, ump_k_adj nonzero rate ≥ expected, movement_conf != 1.0 rate tracks A2's 9.2% baseline). Only proceed to Phase B after re-audit confirms clean signals — see `⏸️ Checkpoint A → B` section for the re-audit checklist. |

---

### Monday-pickup checklist (2026-04-20, after weekend break)

**Context on return:** Friday afternoon (2026-04-17) we kicked off the A3b.2 seed
run in the background and stepped away. Multiple things to check before continuing:

1. **Is the seeder still running?** In a fresh shell, check for the python process
   or the log file tail:
   ```bash
   tail -5 analytics/output/seed_umpire_career_rates.log
   # If the last line is "Wrote N umpires to ..." → done, move to step 2.
   # If the last line is a "day X/553" progress line within the last few min → still running, wait.
   # If nothing has been logged in hours and no "Wrote" line → it died. Resume with:
   #   python scripts/seed_umpire_career_rates.py --start 2024-03-28 --end 2025-10-01 --min-games 20
   #   (no --fresh — it will resume from progress file)
   ```

2. **If the seeder finished:**
   ```bash
   # Verify output file populated
   python -c "import json; d = json.load(open('data/umpires/career_k_rates.json')); print(f'{len(d)} umps; range {min(d.values()):+.3f} .. {max(d.values()):+.3f}; mean {sum(d.values())/len(d):+.4f}')"

   # Verify 2026 match rate rose to ≥75%
   python analytics/diagnostics/a3_ump_adj.py 2>&1 | grep "Totals:"

   # If both look right, commit:
   git add data/umpires/career_k_rates.json
   git commit -m "feat(a3b): expand career_k_rates.json (30 → N umps, 22% → X% match rate)"

   # Then mark A3b.3 ✅ in this plan + append caveat note to docs/data-caveats.md.
   ```

3. **After A3b is fully ✅:** proceed to **Task A2** (opening_*_odds nulls). The
   plan body below has A2 fully specified — no more scoping needed.

4. **Branch state reminder:** work is on `model-audit-phase-a`. `main` has an
   extra commit (`6fec2e9` — v2 UI coexistence note in CLAUDE.md) that is NOT
   on phase-a yet. No need to merge that back into phase-a; it'll come in
   naturally when phase-a merges to main at the A→B checkpoint.

**Expected wall time:** 1–2 hours active work (diagnostics + fixes + tests), plus ~24h of fresh pipeline runs before the A→B checkpoint to confirm activation rates move.

Each of A1–A3 has the same shape: (1) write a diagnostic, (2) interpret, (3) if broken, write a failing test + fix; if dormant-by-design, document in a comment. A4 is a straight analytics addition.

**Phase A success criteria (verify before checkpoint):**
- `pitcher_throws` null rate drops from ~28% → near 0% on picks made after the fix commit ✅
- `ump_k_adj` nonzero rate rises from 0% → expected range. After A3b: 94% coverage against live 2026 HP umpires (59/63 past week). ✅
- `opening_*_odds` null rate drops meaningfully (exact target depends on A2.3 finding)
- A4 produces a per-bookmaker row, even if mostly `<unknown>` until B runs against cleaner data

If those rates don't move after the fixes land and a day of fresh data flows, something is still wrong — re-diagnose before moving to Phase B.

**Execution order (by leverage, highest first):**

1. **A1 — pitcher_throws nulls** ✅ done (28% blind spot on the platoon delta shipped 2026-04-16)
2. **A3 — ump_k_adj all zero** ✅ done — investigation + A3-fix source replacement complete (100% of post-4/8 picks had dead signal; new source live, ~21% coverage via stale career_k_rates.json)
3. **A3b — career_k_rates expansion** ⏳ next — get career_k_rates match rate from 21% → ≥75% before moving on (user preference 2026-04-17: finish fixing the ump pipeline before opening_odds work so nothing stays broken)
4. **A2 — opening_*_odds nulls** (affects movement_conf haircut, not core lambda)
5. **A4 — per-bookmaker analytics** (measurement; do last so B phase has the column available)

Tasks are numbered stably (A1/A2/A3/A4 = pitcher_throws/opening_odds/ump/bookmaker; A3b inserted after A3 for data-coverage expansion) for cross-reference purposes, but **work them in the 1→3→3b→2→4 order above.**

### Task A1: pitcher_throws null-rate investigation  *(execute 1st — highest leverage)*

> **✅ COMPLETE (2026-04-17)** — 5 commits on branch `model-audit-phase-a`:
> `0407846` fix → `517f473` backfill 307 None rows → `8a76f30` polish →
> `8463f8e` rewrite 43 post-cutover R→L rows → `16d513e` docs SHA fill-in.
>
> **Root cause (discovered, plan's hypothesis was wrong):** MLB `/schedule`
> hydrate never returned `pitchHand` — every pitcher silently defaulted to
> `"R"`. Fix added a `/people/{id}` fallback. Backfill filled 307 historical
> nulls via `/people/search`.
>
> **P1 advisory resolved:** 133 post-cutover rows (2026-04-11..2026-04-17)
> were also forced to `"R"` by the bug. Rewrote 43 rows R→L (128 unique
> pitchers looked up; 0 lookup failures). Calibration math unaffected —
> `calibrate.py` reads stored `lambda`, not `pitcher_throws`. Bug window
> documented in [docs/data-caveats.md](../../data-caveats.md).
>
> **Tests:** 242 → 243 passing (one new test for /people fallback).

**Files:**
- Inspect: [pipeline/fetch_stats.py:177](pipeline/fetch_stats.py), [pipeline/build_features.py:346](pipeline/build_features.py), [pipeline/fetch_results.py:164](pipeline/fetch_results.py)
- Possibly modify: [pipeline/fetch_stats.py](pipeline/fetch_stats.py) and/or [pipeline/fetch_results.py](pipeline/fetch_results.py)
- Test: [tests/test_fetch_stats.py](tests/test_fetch_stats.py) and/or [tests/test_build_features.py](tests/test_build_features.py)

Known facts before starting:
- `build_features.py:346` sets `"pitcher_throws": stats.get("throws", "R")` — defaults to "R" when throws missing.
- `fetch_stats.py:177` does `throws = pitcher.get("pitchHand", {}).get("code", "R")` — also defaults.
- Yet ~28% of post-4/8 staked picks have `pitcher_throws: None` in `picks_history.json`.
- Most likely cause: picks existed before defaults were added and were never backfilled; OR `build_features.build_pitcher_record` is sometimes called without `stats` containing `throws` and an older write path wrote None.

- [ ] **Step A1.1: Write a one-off diagnostic**

Create `analytics/diagnostics/a1_pitcher_throws.py`:

```python
"""Diagnose pitcher_throws null pattern in picks_history.json."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HIST = ROOT / "data" / "picks_history.json"
if not HIST.exists():  # global policy P2
    print(f"ERROR: {HIST} not found. Run the pipeline at least once to generate it.")
    raise SystemExit(1)
picks = json.loads(HIST.read_text())

null_rows = [p for p in picks if p.get("pitcher_throws") is None]
non_null = [p for p in picks if p.get("pitcher_throws") is not None]

print(f"Total: {len(picks)}  null pitcher_throws: {len(null_rows)}")
print(f"Null by date:")
by_date = Counter(p.get("date", "unknown") for p in null_rows)
for d, n in sorted(by_date.items()):
    print(f"  {d}  n={n}")

print(f"\nFirst non-null date: {min((p['date'] for p in non_null), default='none')}")
print(f"Last null date:      {max((p['date'] for p in null_rows), default='none')}")

# Is there a pitcher pattern?
print("\nTop-10 pitchers with null pitcher_throws:")
for pitcher, n in Counter(p["pitcher"] for p in null_rows).most_common(10):
    print(f"  {pitcher:<30} n={n}")
```

- [ ] **Step A1.2: Run the diagnostic and interpret**

```bash
mkdir -p analytics/diagnostics
python analytics/diagnostics/a1_pitcher_throws.py
```

Expected: clear date cutover pattern (null before some date, populated after) OR a specific set of pitchers with systematic misses.

- [ ] **Step A1.3: Branch based on finding**

**If the nulls are historical-only (a cutover date exists):** the current write path works; existing picks just predate the fix. Skip A1.4–A1.7 and go straight to A1.8 to document.

**If nulls are still occurring post-cutover:** there's a live bug in the write path. Proceed to A1.4.

- [ ] **Step A1.4: Identify the exact null-producing path**

Before writing any test, trace which write path (seed, update, or the JSON-export round-trip) is producing None.

1. Take one null-pitcher_throws pitcher/date from the diagnostic.
2. Read [pipeline/fetch_results.py](pipeline/fetch_results.py) `seed_picks` (around line 146) and `update_picks` (around line 192) — check whether each writes `pitcher_throws` at all and what default it uses.
3. Read [pipeline/fetch_results.py:277-288](pipeline/fetch_results.py) — the DB-to-JSON export path. Check it selects and writes `pitcher_throws`.
4. Check whether [pipeline/build_features.py:346](pipeline/build_features.py)'s default-to-"R" ever gets bypassed (e.g., if `build_pitcher_record` is called from a path that skips the default).

Record in a comment in your diagnostic file which specific function is writing None. This finding drives A1.5's test and A1.6's fix location.

- [ ] **Step A1.5: Write a failing test for that specific path**

Once you know which function writes None (from A1.4), write a test that reproduces it. Example patterns (adapt to your finding):

**If `seed_picks` writes None when input pick dict lacks `pitcher_throws`:**

```python
# In tests/test_fetch_results.py, mirroring the tmp_db + today_json fixture pattern
# at test_seeds_correct_fields (line 143).
def test_seed_picks_defaults_pitcher_throws_to_R_when_missing(tmp_db, today_json):
    """seed_picks must write 'R' (not None) when the record lacks pitcher_throws."""
    pick_without_throws = {**MINIMAL_PICK, "pitcher_throws": None}  # use existing MINIMAL_PICK fixture
    # Write the pick to today.json, seed into tmp_db, read back, assert pitcher_throws == 'R'
    ...  # mirror the existing seed test's fixture flow
```

**If the bug is in the JSON export:**

```python
# test_export_db_to_history writes 'R' default for pitcher_throws
def test_export_preserves_pitcher_throws_default(tmp_db):
    # insert a row with pitcher_throws=NULL directly, call export, assert exported json has 'R'
    ...
```

Run: `python -m pytest tests/test_fetch_results.py::<your_test_name> -v`. Expected: **FAIL** (current code writes None).

- [ ] **Step A1.6: Apply the fix for whichever path has the bug**

Most likely fix locations:
- [pipeline/fetch_results.py:164](pipeline/fetch_results.py): `p.get("pitcher_throws")` → `p.get("pitcher_throws") or "R"` (coalesce None to default).
- Or add a validation in `build_pitcher_record` that raises if critical fields are missing.

Pick the smallest change that makes the nulls stop. Run the test to confirm green.

- [ ] **Step A1.7: Commit the code fix alone**

```bash
git add tests/test_fetch_results.py pipeline/
git commit -m "fix(a1): prevent None pitcher_throws in [identified path]"
```

Keep the fix commit separate from the backfill commit (A1.8) so either can be reverted independently.

- [ ] **Step A1.8: Backfill or document**

**If bug was real:** write a one-off script `analytics/diagnostics/a1_backfill_throws.py` that reads `picks_history.json`, looks up each null-throws pitcher via `fetch_stats`, and updates the JSON. Run it, confirm nulls drop to zero. The script's top docstring must include: run date, number of rows updated, and the scope (date range of picks touched) — this script is the audit trail for the data mutation.

Commit the script AND the JSON change together. **Keep the script permanently** — do not delete it. Future archaeologists need to be able to answer "what changed in this commit and how?" from the repo alone:

```bash
git add data/picks_history.json analytics/diagnostics/a1_backfill_throws.py
git commit -m "chore(a1): backfill pitcher_throws for historical picks (N rows)"
```

**If nulls are historical-only:** add a comment above [pipeline/build_features.py:346](pipeline/build_features.py) noting the default behavior and cutover date. Do not backfill history (would invalidate the `formula_change_date` audit trail — see global policy P1). Commit the comment change.

(Adjust commit message to reflect whether you fixed a live bug, backfilled history, or documented as historical-only.)

---

### Task A3b: career_k_rates expansion  *(execute 3rd — finish the ump pipeline before opening_odds)*

**Goal:** Raise `data/umpires/career_k_rates.json` match rate against the live 2026 HP umpire pool from ~21% (13/62 unique umps) to ≥75%. Without this, the A3-fix source replacement ships a working pipeline that still mostly returns `ump_k_adj = 0` because most assignments don't hit the lookup table.

**Background (2026-04-17):** A3-fix replaced ump.news with MLB Stats API, which now correctly delivers an HP umpire name for every game. But `data/umpires/career_k_rates.json` was seeded 2026-03-24 with 30 hand-curated entries, several of whom are retired (Angel Hernandez, Ted Barrett, Paul Nauert, Bill Miller, CB Bucknor). Measured match rate against 2026 assignments: 13/62 unique umps = 21%. Target: ≥47/62 = 75%.

**Files:**
- Modify: `data/umpires/career_k_rates.json`
- Optional: `scripts/seed_umpire_career_rates.py` (new, if we write a seeder)

**Design constraints:**
- Format must stay: `{ "Umpire Name": delta_vs_league_avg_K_pct }` — `build_features` reads this as an additive signal.
- Name-matching is accent-insensitive via `name_utils.normalize_name`; store canonical form with accents if possible, match will handle strip.
- Deltas are signed decimals (K% above/below league avg), typically in range ±0.5.
- Don't include pitchers or other names — this is HP-only career career-K-rate-delta data.

**Open investigation questions (answer in A3b.0 spike before coding):**
1. Does MLB Stats API expose pitching-by-umpire splits we can derive a K% from? (If yes, we can programmatically seed all active umps with no manual curation.)
2. Is Baseball Savant's umpire scorecard data public enough to scrape? (Has actual PA-weighted K% per ump.)
3. Does `umpscorecards.com` expose structured data or just HTML? (May need parse.)
4. Would Retrosheet event files be easier (historical, won't pick up 2026 rookies)?

**Step A3b.0: Spike — identify easiest data source**

Investigate in roughly this order (cheapest → hardest):
- MLB Stats API `/teams/stats` with umpire filter → probably doesn't exist
- MLB Stats API `/people/{ump_id}` for officials → check whether career stats field exists for umpires
- Baseball Savant — search for umpire K% leaderboard
- umpscorecards.com — check for JSON endpoint (`/api/...`)
- Pybaseball — check if any function exposes umpire data
- Retrosheet raw event files

Write a quick script in `analytics/diagnostics/a3b_source_spike.py` that prints the first ~5 umpires + their K% from whichever source works. Commit the spike with findings.

**Step A3b.1: Spec the seeder (or manual file)**

Based on A3b.0, decide:
- **Path 1 (programmatic):** Write `scripts/seed_umpire_career_rates.py` to fetch all active umps + K% from the chosen source, compute delta vs league-avg-K%, write JSON. Add a pytest smoke test.
- **Path 2 (manual if programmatic fails):** Hand-expand the 30-entry file to ~100 by cross-referencing the 62 unique umps already seen in 2026 assignments. Less durable (need to redo yearly) but acceptable as a stopgap.

**Step A3b.2: Run + verify**

```bash
# After seeder or manual edit
python analytics/diagnostics/a3_ump_adj.py
# Expect: Section 3 career_rates lookup rate ≥75% on 2026 HP assignments
```

**Step A3b.3: Commit**

```bash
git add data/umpires/career_k_rates.json [scripts/seed_umpire_career_rates.py] [tests/...]
git commit -m "feat(a3b): expand career_k_rates.json to N umps (was 30; match rate X% → Y%)"
```

**Step A3b.4: Update plan + caveats**

Mark A3b ✅ done in the execution log table. Note the match rate movement in `docs/data-caveats.md` under the 2026-04-17 cutover section.

**Backward-compat:** Pure data file expansion. No schema change. `build_features` reads the same JSON the same way. v1 / v2 dashboards unaffected.

---

### Task A2: opening_*_odds null-rate investigation  *(execute 4th, after A3b)*

**Files:**
- Inspect: [pipeline/fetch_odds.py:195-196](pipeline/fetch_odds.py), [pipeline/run_pipeline.py:340-341](pipeline/run_pipeline.py), [pipeline/fetch_results.py:193-196](pipeline/fetch_results.py)
- Possibly modify: [pipeline/run_pipeline.py](pipeline/run_pipeline.py) or [pipeline/fetch_odds.py](pipeline/fetch_odds.py)

Known facts:
- `fetch_odds.py:195-196` writes `opening_over_odds` / `opening_under_odds` into each prop dict — these appear to be the *current* fetch's odds.
- `run_pipeline.py:340-341` overwrites them with `prev["over_odds"]` from `preview_lines.json` when preview data exists.
- Preview runs at 7pm the night before; any pitcher added to the lineup *after* the preview run (late scratch replacement, trade, call-up) has no preview entry → opening odds are whatever the current fetch provided.
- Yet analysis showed `opening_*_odds` is None on most picks, which means the write path isn't filling it at all for many picks.
- Hypothesis: fields are only set on the 6am full run (which reads preview), not on mid-day refresh runs. Mid-day refreshes that add new picks then leave opening_*_odds None.

- [ ] **Step A2.1: Diagnostic — which runs populate opening odds?**

Create `analytics/diagnostics/a2_opening_odds.py`:

```python
"""Diagnose opening_*_odds null pattern."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HIST = ROOT / "data" / "picks_history.json"
if not HIST.exists():  # global policy P2
    print(f"ERROR: {HIST} not found. Run the pipeline at least once to generate it.")
    raise SystemExit(1)
picks = json.loads(HIST.read_text())

# Split by population status (use `is not None` — 0 is a legal numeric but not a legal American odds value)
def _set(p, k): return p.get(k) is not None
has_both    = [p for p in picks if _set(p, "opening_over_odds") and _set(p, "opening_under_odds")]
has_neither = [p for p in picks if not _set(p, "opening_over_odds") and not _set(p, "opening_under_odds")]
partial     = [p for p in picks if _set(p, "opening_over_odds") != _set(p, "opening_under_odds")]

print(f"Total: {len(picks)}")
print(f"  Both opening odds set: {len(has_both)}")
print(f"  Neither:               {len(has_neither)}")
print(f"  Partial (one, not other): {len(partial)}")

print("\nPopulated-vs-null by date:")
dates = sorted({p["date"] for p in picks if p.get("date")})
for d in dates:
    day = [p for p in picks if p.get("date") == d]
    pop = sum(1 for p in day if p.get("opening_over_odds") is not None)
    print(f"  {d}  populated={pop}/{len(day)}")

print("\nPopulated-vs-null by fetched_at hour (UTC):")
by_hour = Counter()
pop_by_hour = Counter()
for p in picks:
    ts = p.get("fetched_at", "") or ""
    hour = ts[11:13] if len(ts) >= 13 else "??"
    by_hour[hour] += 1
    if p.get("opening_over_odds") is not None:
        pop_by_hour[hour] += 1
for h in sorted(by_hour):
    print(f"  {h}  populated={pop_by_hour[h]}/{by_hour[h]}")
```

- [ ] **Step A2.2: Run and interpret**

```bash
python analytics/diagnostics/a2_opening_odds.py
```

Expected: opening odds are populated only for picks first seen during the 6am full run (Phoenix time, ~13:00 UTC). Picks added in later refresh runs never get opening odds. If that's the pattern, move to A2.3.

- [ ] **Step A2.3: Locate the null-writing function**

Trace each path that could write opening_*_odds as None. Record the specific function and line number where the null originates.

Candidate locations to inspect (in order):

1. [pipeline/fetch_odds.py:195-196](pipeline/fetch_odds.py) — Is this inside a conditional block? Are there prop paths that skip it (e.g., props with only one side's odds available)?
2. [pipeline/run_pipeline.py:340-341](pipeline/run_pipeline.py) — Only overwrites when `prev` exists. Does it leave the prop's existing `opening_*_odds` intact otherwise, or overwrite with None?
3. [pipeline/fetch_results.py:146-170](pipeline/fetch_results.py) `seed_picks` INSERT path — writes `p.get("opening_over_odds")` which returns None if field is missing.
4. [pipeline/fetch_results.py:192-210](pipeline/fetch_results.py) UPDATE path — uses `COALESCE(opening_over_odds, ?)` which preserves existing values but never fills a pre-existing None from a later fetch.

**Deliverable of this step:** one sentence in the diagnostic file, e.g., "Bug is in fetch_odds.py:195 — opening_*_odds is only set inside the `if ref_book_id in chosen['under']` block; the alternate path at line 166 does not attach opening odds." A2.4 and A2.5 tests/fixes target that specific location.

- [ ] **Step A2.4: Write failing test for the identified path**

Mirror the existing fixture pattern in [tests/test_fetch_results.py](tests/test_fetch_results.py) (see `test_seeds_correct_fields` at line 143 for the `tmp_db` + `today_json` fixtures and `test_seeds_ref_book` at line 164 for field-round-trip style).

Example if the bug is in `seed_picks` leaving opening_*_odds null:

```python
def test_seed_picks_captures_current_odds_as_opening_when_no_preview(tmp_db, today_json):
    """When a pick's record has no opening_*_odds (late scratch / no preview
    coverage), seed_picks must fall back to the current odds so movement
    confidence has a baseline. Otherwise the feature is silently dormant."""
    # today_json contains picks (follow test_seeds_correct_fields for shape).
    # Construct a today-json dict whose single pick has opening_over_odds=None,
    # opening_under_odds=None, but best_over_odds=-110 and best_under_odds=-105.
    today = {
        "picks": [{
            "date": "2026-04-17",
            "pitcher": "Test Pitcher",
            "team": "XYZ",
            "side": "over",
            "k_line": 6.5,
            "odds": -110,
            "verdict": "FIRE 1u",
            "ev": 0.04,
            "opening_over_odds": None,
            "opening_under_odds": None,
            "best_over_odds": -110,
            "best_under_odds": -105,
            # ... any other required fields visible in test_seeds_correct_fields
        }]
    }
    today_json.write_text(json.dumps(today))

    from fetch_results import seed_picks, get_db
    seed_picks(tmp_db, today_json)

    with get_db(tmp_db) as conn:
        row = conn.execute(
            "SELECT opening_over_odds, opening_under_odds, opening_odds_source FROM picks"
        ).fetchone()
    assert row["opening_over_odds"] == -110   # fell back to best_over_odds
    assert row["opening_under_odds"] == -105  # fell back to best_under_odds
    assert row["opening_odds_source"] == "first_seen"  # NOT labeled as preview
```

Also add a test for the preview case — when preview data IS present, source must be `"preview"`, not `"first_seen"`.

If the actual bug is in `fetch_odds.py` (propping out None before seed ever runs), adapt the test to `test_fetch_odds.py` style — assert the prop dict has non-None opening fields AND `opening_odds_source == "first_seen"` for a prop that uses the alternate book-selection branch.

Run: `python -m pytest tests/test_fetch_results.py::test_seed_picks_captures_current_odds_as_opening_when_no_preview -v`
Expected: **FAIL** (current code stores None).

- [ ] **Step A2.5: Apply the fix — preserving semantic distinction between "true opening" and "first-seen fallback"**

**Critical:** do not silently fall back to current odds and leave `opening_*_odds` looking authoritative. That hides the missing-data state — later analytics and `movement_conf` would read "opened at current price = no movement" for late-scratch pitchers when really we just have no baseline.

Introduce a new field `opening_odds_source` (string enum, nullable):

- `"preview"` — opening odds came from the 7pm preview run (authoritative baseline)
- `"first_seen"` — no preview existed; opening odds fell back to the current/first-seen price. **Movement confidence must not be computed against these.**
- `null` or field absent — no data at all (treat as dormant for this pick)

Pick the smallest change that makes A2.4's test pass AND sets `opening_odds_source` correctly:

- **If bug is in `fetch_odds.py`:** attach `opening_over_odds` / `opening_under_odds` + `opening_odds_source="first_seen"` on every prop path. The preview-merge step later upgrades `opening_odds_source` to `"preview"` when a preview row is matched.
- **If bug is in `run_pipeline.py:340-341`:** change the merge to:
  ```python
  if prev:
      prop["opening_over_odds"]  = prev["over_odds"]
      prop["opening_under_odds"] = prev["under_odds"]
      prop["opening_odds_source"] = "preview"
  else:
      prop["opening_over_odds"]  = prop.get("over_odds")
      prop["opening_under_odds"] = prop.get("under_odds")
      prop["opening_odds_source"] = "first_seen"
  ```
- **If bug is in `seed_picks` INSERT:** coalesce the same way and write `opening_odds_source` into the INSERT params.

**Downstream:** update [pipeline/build_features.py](pipeline/build_features.py) `calc_movement_confidence` (or wherever movement_conf is computed) so it returns neutral 1.0 (no haircut) when `opening_odds_source != "preview"`. A "first_seen" opening carries no movement signal.

Run A2.4's failing test: expect PASS. Also run `TestCalcMovementConfidence` to confirm it still honors the source flag. Run full suite for regressions.

- [ ] **Step A2.6: Verify no regression in movement_conf logic + schema migration**

```bash
python -m pytest tests/test_build_features.py::TestCalcMovementConfidence -v
```

Expected: all movement tests still pass — plus new test(s) confirming haircut is only applied when `opening_odds_source == "preview"`.

**Schema migration note:** existing rows in `picks_history.json` predate the field and have no `opening_odds_source`. Per global policy P1, do NOT retroactively label them — leaving the field absent for historical picks is correct (it signals "unknown provenance"). `calc_movement_confidence` must treat missing (not just `"first_seen"`) as "no haircut." Update the SQLite schema in `seed_picks` to include the column with a NULL default.

- [ ] **Step A2.6a: Audit the DB→JSON export path for `opening_odds_source`**

**Critical round-trip check** — otherwise new rows land in SQLite *with* provenance, but the JSON exporter drops the column and `picks_history.json` silently loses it. B-phase analytics would then see `opening_odds_source=None` on every row and conclude the field is dormant.

Mirror the A1.4 export-path audit pattern:

1. Read [pipeline/fetch_results.py:277-288](pipeline/fetch_results.py) — the DB-to-JSON export path. Confirm the SELECT list includes `opening_odds_source` AND the row serializer writes it into each pick dict.
2. If the export uses `SELECT *`, verify the new column appears in the dict keys after a round-trip.
3. If the export hand-lists columns, add `opening_odds_source` to the SELECT and to the dict construction.
4. Add a test at the export layer:
   ```python
   # tests/test_fetch_results.py
   def test_export_roundtrips_opening_odds_source(tmp_db):
       """seed_picks → export_db_to_history preserves opening_odds_source."""
       # seed a pick with opening_odds_source="first_seen"
       # call the export function
       # assert the resulting picks_history.json row has opening_odds_source == "first_seen"
       # also test a "preview" row and a NULL/absent row
   ```
   Run: FAIL if the export drops the column; PASS once fixed.

**Also check:** any in-memory round-trip in `run_pipeline.py` that reads DB → writes today.json (e.g., post-grade snapshot rebuilds) needs the same audit. Grep for reads of `picks` table columns.

- [ ] **Step A2.7: Commit**

```bash
git add tests/test_fetch_results.py pipeline/run_pipeline.py pipeline/fetch_results.py analytics/diagnostics/
git commit -m "fix(a2): fall back to current odds for opening_*_odds when no preview + preserve source through export"
```

---

### Task A3: ump_k_adj all-zero investigation  *(execute 2nd — signal dead across every pick)*

**Files:**
- Inspect: [pipeline/fetch_umpires.py](pipeline/fetch_umpires.py), [pipeline/run_pipeline.py](pipeline/run_pipeline.py) (where `ump_map` is built and looked up), [pipeline/build_features.py](pipeline/build_features.py) (ump_k_adj usage)
- Possibly modify: [pipeline/fetch_umpires.py](pipeline/fetch_umpires.py) or name-normalization in run_pipeline

Known facts:
- `run_pipeline` looks up ump adjustment via `ump_map.get(hp_umpire_name, 0.0)` — default 0 when the umpire assigned to the game isn't matched in the map.
- 100% of 145 staked post-4/8 picks show `ump_k_adj = 0` in the analytics — suspicious. Either (a) ump data legitimately has near-zero adjustment for every game, (b) name-matching is failing and everything is hitting the default, or (c) `fetch_umpires` is returning an empty dict.

- [ ] **Step A3.1: Diagnostic**

Create `analytics/diagnostics/a3_ump_adj.py`:

```python
"""Diagnose ump_k_adj zero-distribution."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HIST = ROOT / "data" / "picks_history.json"
if not HIST.exists():  # global policy P2
    print(f"ERROR: {HIST} not found. Run the pipeline at least once to generate it.")
    raise SystemExit(1)
picks = json.loads(HIST.read_text())

vals = [p.get("ump_k_adj") for p in picks]
nonzero = [v for v in vals if v is not None and abs(v) > 1e-6]
zero = [v for v in vals if v == 0.0]
null = [v for v in vals if v is None]

print(f"Total: {len(vals)}")
print(f"  exactly 0.0: {len(zero)}")
print(f"  null:        {len(null)}")
print(f"  nonzero:     {len(nonzero)}")
if nonzero:
    print(f"  nonzero range: {min(nonzero):+.3f} .. {max(nonzero):+.3f}")
    print(f"  nonzero mean:  {sum(nonzero)/len(nonzero):+.3f}")

# Check: does fetch_umpires actually return anything for today?
import sys
sys.path.insert(0, str(ROOT / "pipeline"))
from fetch_umpires import fetch_umpires
try:
    result = fetch_umpires("2026-04-16")
    print(f"\nLive fetch_umpires for 2026-04-16: {len(result)} entries")
    for k, v in list(result.items())[:5]:
        print(f"  {k}: {v}")
except Exception as e:
    print(f"\nLive fetch_umpires failed: {e}")
```

- [ ] **Step A3.2: Run and interpret**

```bash
python analytics/diagnostics/a3_ump_adj.py
```

Three outcomes:
- **All zero AND live fetch returns empty dict:** `fetch_umpires` is silently failing (network, selector change on ump.news). Proceed to A3.3.
- **All zero AND live fetch returns populated dict with varied values:** name-matching is the bug. Proceed to A3.4.
- **All zero AND live fetch returns dict with all ~0 values:** legitimate — umpires are near-neutral on average. Document in A3.5 and move on.

- [ ] **Step A3.3: Fix — fetch_umpires silent failure path**

First read [pipeline/fetch_umpires.py](pipeline/fetch_umpires.py) imports to confirm the patch target. Current imports use `import requests` (line 10), so `patch("fetch_umpires.requests.get", ...)` is correct. If the import style has changed by the time you execute this task, adjust the patch target accordingly.

If the function catches broad exceptions and returns `{}` silently, replace with:

```python
except Exception as e:
    log.warning("fetch_umpires failed: %s", e)
    return {}
```

(Ensure it logs loudly so silent failures are visible in pipeline logs.) Then add a test in [tests/](tests/):

```python
def test_fetch_umpires_logs_warning_on_failure(caplog):
    """Network/parser failures should log a warning, not silently return empty."""
    with patch("fetch_umpires.requests.get", side_effect=Exception("boom")):
        with caplog.at_level("WARNING"):
            result = fetch_umpires("2026-04-16")
    assert result == {}
    assert any("fetch_umpires failed" in rec.message for rec in caplog.records)
```

- [ ] **Step A3.4: Fix — name-matching mismatch**

If the live fetch returns `{"Angel Hernandez": 0.05, ...}` but the lookup never hits, the keys differ. Likely suspects: case, accent stripping, middle initials. Use `name_utils.normalize` to normalize both sides.

Change `fetch_umpires.py` to normalize keys on build, and `run_pipeline.py` lookup to normalize the query name. **The lookup key is the HP umpire for the game, not the pitcher** — the pipeline already fetches today's assigned umpires per game:

```python
# in fetch_umpires.py — normalize keys on build
from name_utils import normalize as _norm
return {_norm(k): v for k, v in raw_result.items()}

# in run_pipeline.py (or wherever lookup happens per game) —
# normalize the HP umpire name for today's game, not the pitcher
hp_umpire_name = game["hp_umpire"]  # or whatever field carries it
ump_k_adj = ump_map.get(_norm(hp_umpire_name), 0.0)
```

Add a failing test that covers the accent/case mismatch pathway, apply the fix, confirm green.

- [ ] **Step A3.5: If legitimate (all ~0), document**

Add a comment at the ump lookup site in `run_pipeline.py` explaining that ump K adjustments are typically near-zero in MLB (most umps are within ±2% of league K rate) and that the feature only fires meaningfully on ~5-10% of games with known extreme umps.

- [ ] **Step A3.6: Commit**

```bash
git add tests/ pipeline/ analytics/diagnostics/
git commit -m "fix(a3): [chosen remediation for ump_k_adj]"
```

---

### Task A4: Add bookmaker breakdown to analytics  *(execute 4th — measurement)*

**Files:**
- Modify: [analytics/performance.py](analytics/performance.py)

- [ ] **Step A4.1: Add `by_bookmaker` function**

After `by_lineup` in [analytics/performance.py](analytics/performance.py), add:

```python
def by_bookmaker(df: pd.DataFrame) -> None:
    """Per-reference-book performance. Which book's line is most/least predictive?"""
    print("\n-- By reference book (staked only) -----------------------------------")
    s = staked(df)
    books = s["ref_book"].fillna("<unknown>").value_counts().index.tolist()
    for book in books:
        sub = s[s["ref_book"].fillna("<unknown>") == book]
        print(_row(f"book = {book}", sub))
```

- [ ] **Step A4.2: Wire into main**

In the `main()` function, add `by_bookmaker(df)` after `by_lineup(df)`.

- [ ] **Step A4.3: Smoke-run the full analytics script**

`analytics/` is a script directory, not a Python package — it doesn't expose clean imports for pytest. Rather than restructure it, the smoke check is the script running end-to-end without crashing, even when `ref_book` is mostly null:

```bash
python analytics/performance.py --since 2026-04-08
```

**Pass criteria:** exits 0, prints a "By reference book" section (possibly dominated by `<unknown>` until the A2/C commits land). If it crashes on `ref_book` missing / all-null, wrap the column access in `df.get("ref_book", pd.Series([None] * len(df)))` inside `by_bookmaker`.

- [ ] **Step A4.4: Commit**

```bash
git add analytics/performance.py
git commit -m "feat(a4): add per-bookmaker slice to analytics/performance.py"
```

---

### ⏸️ Checkpoint A → B (HARD STOP)

**STOP HERE. Do not proceed to Phase B automatically, even in auto mode.** Post the findings from A1/A2/A3 diagnostics to the user and explicitly wait for a "proceed" reply.

Discuss with the user:
- What did each diagnostic reveal? Were the plumbing bugs real, or were those features dormant-by-design?
- If bugs were real and fixed, wait ~24h for new picks to flow with corrected data before Phase B — otherwise B's new slices will still see the broken state.
- If nothing actionable was found, fine — continue to Phase B once confirmed.

**Merge status (2026-04-21):** ✅ Phase A branch merged to main. Book-scoping Option B live, midnight preview live, branch tree cleaned. `lambda_bias` and `formula_change_date` untouched (P4). See execution-log row "A→B checkpoint — merge" above for commit scope.

**Soak re-audit step (BLOCKS Phase B kickoff):** the user explicitly wants Phase A diagnostics re-run against a fresh post-merge sample before Phase B starts. The merge day's data is mixed (pre- and post-Option-B picks in the same slate via `INSERT OR IGNORE` semantics); re-auditing now would still see that transition state. Wait until at least **2 full slates** have graded under the new pipeline, then:

1. Re-run each diagnostic with `--since <merge_date>`:
   ```bash
   python analytics/diagnostics/a1_pitcher_throws.py
   python analytics/diagnostics/a2_opening_odds.py
   python analytics/diagnostics/a3_ump_adj.py
   python analytics/performance.py --since <merge_date>   # verify by_bookmaker row counts
   ```
2. Compare against the Phase A success criteria (line 150 block):
   - `pitcher_throws` null rate on post-merge picks: should be ~0% (forward-only, historical window stays as documented in `docs/data-caveats.md`).
   - `ump_k_adj` nonzero rate: should be ≥ ~90% now that career_k_rates covers 87 umps and A3-fix source swap is live.
   - `opening_*_odds` null rate on post-merge picks: should be ~0% (A2 plumbing is confirmed working; null rows are legacy pre-migration).
   - `movement_conf != 1.0` rate: should track the ~9% baseline established by A2 diagnostic, now gated by `opening_odds_source == "preview"` → will only fire on picks where midnight preview actually captured a baseline.
3. If any metric regressed or stayed stuck, **re-diagnose before Phase B** — do not paper over with a Phase B measurement addition, because B's slices assume the plumbing is clean.
4. Once the re-audit passes, post the numbers to the user and wait for explicit "proceed to Phase B" reply before starting B1.

**Backward-compat check for Phase A:**
- **A1 (`pitcher_throws`)** — field already exists and was None-tolerant; dashboard and analytics stay compatible whether A1 backfilled or not.
- **A2 adds one new field: `opening_odds_source`** (enum string, nullable). Existing rows predate the field and will have it absent; `calc_movement_confidence` must treat both missing-field and `"first_seen"` identically (no haircut). SQLite `picks` table gains a nullable column. Dashboard ignores unknown fields and reads `opening_*_odds` as before — no dashboard change needed. Analytics (B1–B6, `analytics/performance.py`) must use defensive column access (`_col()` pattern from B5) when reading `opening_odds_source` since older pick rows lack it.
- **A3 / A4** — no new fields added.

**V2 dashboard compatibility check (added 2026-04-17):** A v2 dashboard UI landed on `main` 2026-04-17 (commit `4bb54a8`, `dashboard/v2.html` + `v2-app.jsx` + `v2-data.js`, served at `/v2.html`). V1 (`dashboard/index.html`) remains the default. Before merging phase-a back to main:
- **Do not rename or remove** any `today.json` field. V2 adapter (`dashboard/v2-data.js`) reads, non-exhaustively: `pitcher, team, opp_team, pitcher_throws, game_time, k_line, opening_line, best_over_odds, best_under_odds, opening_over_odds, opening_under_odds, lambda, avg_ip, opp_k_rate, ump_k_adj, season_k9, recent_k9, career_k9, ev_over, ev_under, game_state, best_over_book, swstr_pct, swstr_delta_k9, data_complete`. Adding new nullable fields (like A2's `opening_odds_source`) is safe.
- **Manual smoke test before merge:** after deploying a phase-a-driven pipeline run to Netlify, load `/` (v1) AND `/v2.html` (v2) and confirm cards render. Check browser console for `v2-data.js` field-access errors. No pipeline change in phase A renames fields, but verify anyway — the whole point of the rollout plan is to not break v2.
- See `CLAUDE.md` → "In-Flight Work: V2 Dashboard UI" and `docs/superpowers/plans/2026-04-17-v2-ui-rollout.md` for the full rollout context.

---

## PHASE B — Analytics Tool Extensions

**Expected wall time:** 30–60 minutes active work (six pure function additions to `analytics/performance.py` with inline run-and-inspect commits). No pipeline-wide effects — can be done in one sitting.

Goal: add the measurement slices we need before any Phase C model change is attributable, plus sustainability instruments that make silent failures self-evident going forward. Each is a pure addition to `analytics/performance.py`.

**Phase B success criteria (produce concrete next-step decisions):**
- B1 → if over-side residual mean is >0.3 K more negative than under-side, the over-bleed is side-asymmetric and Phase C should prioritize a per-side bias term over new signals
- B2 → if high-lambda (>7) bucket residual mean is much more negative than low-lambda bucket, prioritize C4 (tail haircut) OR bucketed `lambda_bias` over C2/C3
- B3 → if a recognizable pitcher archetype dominates the over-predicted list (e.g., all high-velocity starters), that's the archetype Phase C needs to model
- B4 → if dead-zone picks have systematically higher season_k9 + lower opp_k_rate than sweet-spot picks, EV is stacking correlated signals — C4 or an explicit de-correlation becomes a higher priority than C2
- B5/B6 → establish the baseline signal-activation and feature-contribution means. Going forward, run weekly; any drop >10 percentage points or any mean shift >2σ is a signal to investigate

### Task B1: Residual mean by over/under side

**Files:**
- Modify: [analytics/performance.py](analytics/performance.py)

Purpose: tests whether the over-bleed survives lambda_bias convergence. If overs have negative residual mean (actual < predicted) significantly more than unders, the bias is side-asymmetric and lambda_bias alone will not fix it.

- [ ] **Step B1.1: Add `residuals_by_side` function**

```python
def residuals_by_side(df: pd.DataFrame) -> None:
    """Residual (actual_ks - applied_lambda) mean/stdev, split by side.
    If the means diverge meaningfully between over and under picks, the
    remaining prediction bias is side-asymmetric and lambda_bias alone
    won't close it."""
    print("\n-- Residuals by bet side (graded only) -------------------------------")
    d = df.dropna(subset=["applied_lambda", "actual_ks"])
    d = d[d["result"].isin(["win", "loss"])]
    d = d.assign(resid=d["actual_ks"] - d["applied_lambda"])
    for side in ["over", "under"]:
        sub = d[d["side"] == side]
        if len(sub) == 0:
            print(f"  side={side:<6}  n=0   (no data)")
            continue
        print(f"  side={side:<6}  n={len(sub):<4}  "
              f"mean={sub['resid'].mean():+6.3f}  "
              f"stdev={sub['resid'].std():5.3f}  "
              f"median={sub['resid'].median():+6.3f}")
```

- [ ] **Step B1.2: Wire into main and run**

Add `residuals_by_side(df)` to `main()` before the `-- Plots --` section. Run with `--since 2026-04-08`.

Expected: two rows, mean residuals visible. If over-mean is much more negative than under-mean, we have structural evidence the over bias is side-specific.

- [ ] **Step B1.3: Commit**

```bash
git add analytics/performance.py
git commit -m "feat(b1): add residual-by-side slice to analytics"
```

---

### Task B2: Residual by predicted-lambda bucket

Purpose: tests whether `lambda_bias` is uniform across low-K and high-K pitchers. If high-lambda picks have much more negative residuals, the bias is concentrated in the top end — likely the K-variance issue predicted in Phase C.

- [ ] **Step B2.1: Add `residuals_by_lambda_bucket`**

```python
def residuals_by_lambda_bucket(df: pd.DataFrame) -> None:
    """Residual mean by predicted lambda bucket. Reveals whether bias is
    uniform or concentrated (e.g., high-K pitchers systematically over-predicted)."""
    print("\n-- Residuals by predicted lambda bucket (graded only) ----------------")
    d = df.dropna(subset=["applied_lambda", "actual_ks"])
    d = d[d["result"].isin(["win", "loss"])].copy()
    d["resid"] = d["actual_ks"] - d["applied_lambda"]
    bins = [0, 4.0, 5.0, 6.0, 7.0, 8.0, 99]
    labels = ["<4", "4-5", "5-6", "6-7", "7-8", ">8"]
    d["bucket"] = pd.cut(d["applied_lambda"], bins=bins, labels=labels)
    for lbl in labels:
        sub = d[d["bucket"] == lbl]
        if len(sub) == 0:
            print(f"  lambda {lbl:<5}  n=0")
            continue
        print(f"  lambda {lbl:<5}  n={len(sub):<4}  "
              f"mean_resid={sub['resid'].mean():+6.3f}  "
              f"stdev={sub['resid'].std():5.3f}")
```

- [ ] **Step B2.2: Wire and run, commit**

Add to `main()` after `residuals_by_side`. Run and inspect. Commit.

```bash
git add analytics/performance.py
git commit -m "feat(b2): add residual-by-lambda-bucket slice"
```

---

### Task B3: Per-pitcher track record

Purpose: find pitchers the model systematically over- or under-predicts. Reveals archetypes (e.g., "high-K veterans" or "young fastball-heavy SPs") that may signal a missing feature.

- [ ] **Step B3.1: Add `by_pitcher_performance`**

```python
def by_pitcher_performance(df: pd.DataFrame, min_n: int = 3) -> None:
    """Per-pitcher residual mean, sorted. Pitchers with persistent negative
    residuals are being over-predicted; positive means under-predicted. Reveals
    model blind spots at the individual level."""
    print(f"\n-- Per-pitcher residual mean (n>={min_n}, graded only) ---------------")
    d = df.dropna(subset=["applied_lambda", "actual_ks"])
    d = d[d["result"].isin(["win", "loss"])].copy()
    d["resid"] = d["actual_ks"] - d["applied_lambda"]
    agg = d.groupby("pitcher").agg(
        n=("resid", "size"),
        mean_resid=("resid", "mean"),
        wins=("result", lambda x: (x == "win").sum()),
    )
    agg = agg[agg["n"] >= min_n].sort_values("mean_resid")
    print("  Most over-predicted (actual < predicted):")
    for name, row in agg.head(10).iterrows():
        print(f"    {name:<28} n={int(row.n):<3}  mean_resid={row.mean_resid:+.2f}  W={int(row.wins)}")
    print("  Most under-predicted (actual > predicted):")
    for name, row in agg.tail(10).iloc[::-1].iterrows():
        print(f"    {name:<28} n={int(row.n):<3}  mean_resid={row.mean_resid:+.2f}  W={int(row.wins)}")
```

- [ ] **Step B3.2: Wire and run, commit**

```bash
git add analytics/performance.py
git commit -m "feat(b3): add per-pitcher residual ranking"
```

---

### Task B4: 9-15% EV dead-zone investigation

Purpose: the analytics already shows the 9-15% EV bucket is the worst-performing FIRE tier. This task asks *what's driving EV in that band* — is it correlated signal stacking (high-K pitcher + low-K lineup + ump + SwStr all pointing same way)?

- [ ] **Step B4.1: Add `dead_zone_profile`**

```python
def dead_zone_profile(df: pd.DataFrame) -> None:
    """Profile picks in the 9-15% EV band vs the 5-9% 'sweet spot' band.
    If dead-zone picks have systematically different driver profiles
    (e.g., much higher season_k9, lower opp_k_rate), that points at
    correlated-signal over-stacking."""
    print("\n-- Dead zone vs sweet spot profile (staked only) ---------------------")
    s = staked(df).copy()
    sweet = s[(s["ev"] >= 0.05) & (s["ev"] < 0.09)]
    dead  = s[(s["ev"] >= 0.09) & (s["ev"] < 0.15)]
    cols = ["applied_lambda", "season_k9", "recent_k9", "career_k9",
            "opp_k_rate", "ump_k_adj", "avg_ip"]
    print(f"  {'':<18} sweet (n={len(sweet)})   dead (n={len(dead)})")
    for c in cols:
        sv = sweet[c].dropna()
        dv = dead[c].dropna()
        if sv.empty or dv.empty:
            continue
        print(f"  {c:<18} mean={sv.mean():+6.3f}   mean={dv.mean():+6.3f}  "
              f"delta={dv.mean() - sv.mean():+.3f}")
```

- [ ] **Step B4.2: Wire and run**

Add to `main()`. Run and read the profile. Delta values point at which signals dominate in the dead zone.

- [ ] **Step B4.3: Commit**

```bash
git add analytics/performance.py
git commit -m "feat(b4): add dead-zone vs sweet-spot profile diagnostic"
```

---

### Task B5: Signal-activation-rate slice *(sustainability — detect silent feature death)*

**Files:**
- Modify: [analytics/performance.py](analytics/performance.py)

Purpose: the plumbing fixes in Phase A will silently regress if an upstream data source changes format (ump.news selector change, MLB API field rename, etc.). A one-line report of `% of picks where each signal fires` makes that visible. Run it weekly; if a column drops to 0% that's a dead signal.

- [ ] **Step B5.1: Add `signal_activation_rates` function**

After `by_bookmaker` in [analytics/performance.py](analytics/performance.py), add:

```python
def signal_activation_rates(df: pd.DataFrame) -> None:
    """% of picks where each feature is firing (non-default). A sudden drop
    in any column is the earliest signal that upstream data silently broke."""
    print("\n-- Signal activation rates (all picks) -------------------------------")
    n = len(df)
    if n == 0:
        print("  (no picks)")
        return

    # Defensive column accessors — older picks_history.json rows or partial
    # loads may not have every column. Return a null-series of the right length
    # so activation rate degrades to 0% for that signal rather than crashing.
    def _col(name, fill=None):
        if name in df.columns:
            return df[name]
        return pd.Series([fill] * n, index=df.index)

    checks = [
        ("pitcher_throws non-null",  _col("pitcher_throws").notna()),
        ("ump_k_adj != 0",           _col("ump_k_adj").fillna(0).abs() > 1e-6),
        ("opening_over_odds set",    _col("opening_over_odds").notna()),
        ("opening_under_odds set",   _col("opening_under_odds").notna()),
        ("ref_book set",             _col("ref_book").notna() & (_col("ref_book") != "")),
        ("swstr_delta_k9 != 0",      _col("swstr_delta_k9").fillna(0).abs() > 1e-6),
        ("movement_conf < 1.0",      _col("movement_conf").fillna(1.0) < 1.0),
    ]
    # Phase C additions — include once the fields exist
    if "park_factor" in df.columns:
        checks.append(("park_factor populated", df["park_factor"].notna()))
        checks.append(("park_factor != 1.0",    df["park_factor"].fillna(1.0).sub(1.0).abs() > 1e-6))
    if "is_opener" in df.columns:
        checks.append(("is_opener flagged", df["is_opener"].fillna(False).astype(bool)))

    # Signals where low activation is expected (Phase C fields before they ramp,
    # or features that fire on only a minority of picks by design).
    low_is_ok = {"park_factor != 1.0", "is_opener flagged", "movement_conf < 1.0"}

    for label, mask in checks:
        pct = 100.0 * mask.sum() / n
        warn = ""
        if label not in low_is_ok and n >= 20:
            if pct < 1:
                warn = "  <-- FEATURE DEAD"
            elif pct < 50 and "pitcher_throws" in label:
                warn = "  <-- suspiciously low"
        print(f"  {label:<28}  {pct:5.1f}%{warn}")
```

- [ ] **Step B5.2: Wire into main and run**

Add `signal_activation_rates(df)` to `main()` after `by_bookmaker`. Run:

```bash
python analytics/performance.py --since 2026-04-08
```

Expected: ~100% on pitcher_throws (after A1), ~80-95% on ump_k_adj (after A3 fix, depending on ump.news daily coverage), etc. This is your new weekly health check.

- [ ] **Step B5.3: Commit**

```bash
git add analytics/performance.py
git commit -m "feat(b5): add signal-activation-rate slice for silent-failure detection"
```

---

### Task B6: Feature-contribution mean audit *(sustainability — detect calibration drift)*

**Files:**
- Modify: [analytics/performance.py](analytics/performance.py)

Purpose: `lambda_bias` is a global scalar. If any single feature (park factor, platoon delta, ump adj) miscalibrates uniformly in one direction, `lambda_bias` silently absorbs it — and you lose the ability to attribute accuracy to a signal. This audit reports the mean magnitude each feature contributes to lambda, so drift is visible.

- [ ] **Step B6.1: Add `feature_contributions` function**

```python
def feature_contributions(df: pd.DataFrame) -> None:
    """Mean additive/multiplicative contribution of each lambda feature.
    If one column's mean drifts far from expectation (e.g., park_factor mean
    wanders from ~1.0), the static data is stale OR calibration is absorbing
    miscalibration. Run monthly."""
    print("\n-- Feature contribution means (graded picks) -------------------------")
    d = df[df["result"].isin(["win", "loss"])]
    if len(d) == 0:
        print("  (no graded picks)")
        return

    # Additive contributors (signed K/9 or K delta)
    additive = [
        ("swstr_delta_k9",   "K/9 delta"),
        ("ump_k_adj",        "K delta"),
        ("lambda_bias",      "K delta (global)"),
    ]
    for col, unit in additive:
        if col not in d.columns:
            continue
        s = d[col].dropna()
        if s.empty:
            continue
        print(f"  {col:<20} mean={s.mean():+.3f}  stdev={s.std():.3f}  [{unit}]")

    # Multiplicative contributors (factor on lambda)
    multiplicative = [
        ("park_factor",      "lambda multiplier"),
        ("opp_k_rate",       "opponent K% (raw)"),
        ("movement_conf",    "EV haircut factor"),
    ]
    for col, unit in multiplicative:
        if col not in d.columns:
            continue
        s = d[col].dropna()
        if s.empty:
            continue
        print(f"  {col:<20} mean={s.mean():+.3f}  stdev={s.std():.3f}  [{unit}]")
```

- [ ] **Step B6.2: Wire and run**

Add to `main()` after `signal_activation_rates`. Run and inspect. Expected example: `park_factor mean=1.002` (near neutral, good), `lambda_bias mean=-0.45` (converging from -0.551 as expected).

- [ ] **Step B6.3: Commit**

```bash
git add analytics/performance.py
git commit -m "feat(b6): add feature-contribution audit to detect calibration drift"
```

---

### ⏸️ Checkpoint B → C (HARD STOP)

**STOP HERE. Do not proceed to Phase C automatically, even in auto mode.** Share the four slice outputs with the user and explicitly wait for a "proceed" reply (or a redirect).

Discuss:
- Which slices showed meaningful patterns?
- Is the over-bleed side-asymmetric or not? (B1 answer)
- Is bias uniform or concentrated at high lambda? (B2 answer)
- Is there an over-predicted archetype? (B3 answer)
- Is the dead zone driven by signal stacking? (B4 answer)
- Are all signals firing at their expected rates, or is something silently dead? (B5 answer)
- Is any feature's mean contribution drifting, suggesting stale data or hidden miscalibration? (B6 answer)

**Strongly consider** splitting Phase C into a dedicated plan informed by these findings. Park factors may matter less than expected; rest/opener may matter more. Do not proceed to C blindly.

**Backward-compat check for Phase B:** Phase B only modifies `analytics/performance.py`. No pipeline, picks schema, or dashboard changes. Safe to stop here permanently — the analytics tool is strictly additive.

---

## PHASE C — Model Signal Additions

**Expected wall time per C task:** 1–3 hours active work (TDD cycle + wiring + test run) + ~48h production soak before the activation gate is checked. Spread across days, not one sitting — each signal needs time in production before the next lands so calibration can attribute changes cleanly. C2 has extra manual load from C2.1b (park factor research, ~1h).

⚠️ **Do not start until Phase B's findings have been reviewed.** Each C item is a separate change. Commit each independently so calibration can absorb each signal over several days before the next lands.

Tasks in this phase follow strict TDD: test first, fail, implement, pass, commit.

**Phase C success criteria (per task — gated at merge + 48h):**
- Each C task has a 48h activation gate (steps C1.9 / C2.6 / C3.6) that confirms the new signal is actually firing in production. If activation target isn't met, the signal is dormant and the commit's impact is zero — revert or re-diagnose before moving to the next C task.
- No C task should cause `lambda_bias` to diverge by more than 0.15 from its pre-C value over any 7-day window. If it does, the new signal is miscalibrated — consult B6 feature-contribution audit and consider revert.
- See global policy **P1**: do not retro-backfill `park_factor`, `rest_k9_delta`, or `is_opener` onto graded picks. All new features are forward-only from their deploy date.

### Task C1: Opener / bullpen-game detection

**Files:**
- Modify: [pipeline/fetch_stats.py](pipeline/fetch_stats.py) (return recent-start IP data if not already), [pipeline/build_features.py](pipeline/build_features.py) (add opener flag + lambda adjustment)
- Test: [tests/test_build_features.py](tests/test_build_features.py)

Approach: detect if the listed SP's recent starts have mean IP below a threshold (e.g., <2.5 IP). Flag as opener. Choose between (a) exclude from staking (verdict → PASS), or (b) scale predicted lambda down proportionally. Default to (a) — excluding — since opener K totals are fundamentally different distribution.

- [ ] **Step C1.1: Verify recent-start data already available**

Read [pipeline/fetch_stats.py:177-199](pipeline/fetch_stats.py). Confirm whether recent-start IP (per start, not just avg) is returned. If not, the test will catch it.

- [ ] **Step C1.2: Write failing test for opener detection**

In [tests/test_build_features.py](tests/test_build_features.py):

```python
class TestOpenerDetection:
    def test_opener_flagged_when_recent_starts_short(self):
        """A pitcher with <2.5 avg IP across recent starts is flagged as opener."""
        from build_features import is_opener
        assert is_opener([1.0, 1.1, 2.0]) is True
        assert is_opener([5.2, 6.0, 5.5]) is False

    def test_opener_requires_minimum_starts(self):
        """<2 starts is insufficient evidence; not an opener by default."""
        from build_features import is_opener
        assert is_opener([1.0]) is False
        assert is_opener([]) is False

    def test_opener_verdict_forced_to_pass(self):
        """When flagged as opener, build_pitcher_record should force verdict=PASS."""
        stats = {**SAMPLE_STATS, "throws": "R", "recent_start_ips": [1.0, 1.1, 2.0]}
        record = build_pitcher_record(SAMPLE_ODDS, stats, ump_k_adj=0.0)
        assert record.get("is_opener") is True
        assert record["ev_over"]["verdict"] == "PASS"
        assert record["ev_under"]["verdict"] == "PASS"
```

Run: `python -m pytest tests/test_build_features.py::TestOpenerDetection -v` → expect FAIL (`is_opener` doesn't exist, `is_opener` key not in record).

- [ ] **Step C1.3: Implement `is_opener` helper**

In [pipeline/build_features.py](pipeline/build_features.py), near `calc_lineup_k_rate`:

```python
OPENER_IP_THRESHOLD = 2.5
OPENER_MIN_STARTS = 2


def is_opener(recent_start_ips: list[float] | None) -> bool:
    """Flag a listed SP as an opener if recent mean IP is below threshold.
    Needs at least OPENER_MIN_STARTS starts of evidence."""
    if not recent_start_ips or len(recent_start_ips) < OPENER_MIN_STARTS:
        return False
    return (sum(recent_start_ips) / len(recent_start_ips)) < OPENER_IP_THRESHOLD
```

Run the first two sub-tests: pass.

- [ ] **Step C1.3a: Read `build_pitcher_record` structure before wiring**

Open [pipeline/build_features.py](pipeline/build_features.py) and locate `build_pitcher_record`. Identify:
1. The exact variable name of the record dict being assembled.
2. Where `ev_over` and `ev_under` are assigned their verdict (look for `"verdict":` keys).
3. The last line before `return record` (so the flag can be attached at the right point).

Record these coordinates (function line range, record-var name, verdict assignment line) in a short comment at the top of your working scratch — C1.4 relies on all three being accurate.

- [ ] **Step C1.4: Wire opener flag into `build_pitcher_record`**

Using the coordinates identified in C1.3a, in `build_pitcher_record`, after the record dict is built but before verdicts are finalized:

```python
opener = is_opener(stats.get("recent_start_ips"))
record["is_opener"] = opener
if opener:
    record["ev_over"]["verdict"]  = "PASS"
    record["ev_under"]["verdict"] = "PASS"
    record["opener_note"] = "Opener/bullpen game — K props unreliable; forced to PASS."
```

Run the third sub-test: pass.

- [ ] **Step C1.5: Ensure fetch_stats returns recent_start_ips**

If [pipeline/fetch_stats.py](pipeline/fetch_stats.py) doesn't already include per-start IP data in the `stats` dict, add it.

TDD: first write a test in [tests/test_fetch_stats.py](tests/test_fetch_stats.py) that mocks the MLB API response and asserts `recent_start_ips` is a list of floats in the return value. Run it — **expected: FAIL** (field doesn't exist yet). Then modify `fetch_stats` to extract per-game IP from the MLB Stats API game log, returning as `stats["recent_start_ips"]`. Re-run the test — expected: PASS.

- [ ] **Step C1.6: Run full test suite**

```bash
python -m pytest tests/ -q
```

Expected: all pass.

- [ ] **Step C1.7: Commit**

```bash
git add tests/ pipeline/
git commit -m "feat(c1): detect openers and force PASS verdict on their props"
```

- [ ] **Step C1.8: Dashboard schema check**

The `is_opener` and `opener_note` fields are new in `today.json`. Check [dashboard/index.html](dashboard/index.html) does not blow up on missing fields (it should already handle missing — the dashboard uses JS `?.` and `||` patterns, but verify by reading the rendering code). If it surfaces opener in the UI, great; if not, no harm.

- [ ] **Step C1.9: 48h activation gate**

Wait ~48h after C1 merges, then re-run `python analytics/performance.py --since <c1-deploy-date>`. **Gate:** `is_opener` field should be populated (True or False, not missing) for ≥98% of picks. `is_opener=True` itself should fire for ~0-5% of picks per day on average (genuinely rare). If activation is 0% everywhere, the wiring's bypassed somewhere — re-diagnose before moving on.

---

### Task C2: Park factors

**Files:**
- Create: `data/park_factors.json`
- Modify: [pipeline/fetch_odds.py](pipeline/fetch_odds.py) or [pipeline/fetch_stats.py](pipeline/fetch_stats.py) to attach home-park to each prop (via `team` and an MLB team→park map), [pipeline/build_features.py](pipeline/build_features.py) (apply multiplier in `calc_lambda`)
- Test: [tests/test_build_features.py](tests/test_build_features.py)

Approach: static multiplier on lambda based on the ballpark's historic K-environment factor (from FanGraphs park factors, multi-season average). Simple lookup.

- [ ] **Step C2.1a: Scaffold `data/park_factors.json` with schema + 5 seeds**

Park factors are a model input — they need provenance so future audits can answer "where did 0.93 for COL come from?" Create the file with full source metadata. Note the nested `factors` key: it separates lookup data from metadata so `_source` can evolve without touching the numbers.

```json
{
  "_schema_version": 1,
  "_notes": "K park factor (1.00 = neutral). >1.00 = more Ks than average; <1.00 = fewer.",
  "_defaults_to": 1.0,
  "_source": {
    "provider": "FanGraphs",
    "url": "https://www.fangraphs.com/guts.aspx?type=pf&teamid=0&season=2025",
    "metric": "K% park factor, 3-year regressed",
    "season_range": "2023-2025",
    "fetched_at": "2026-04-16T00:00:00Z",
    "fetched_by": "manual research; cross-checked vs Baseball Savant park factors"
  },
  "factors": {
    "COL": 0.93,
    "BOS": 0.96,
    "LAD": 1.04,
    "NYY": 1.02,
    "ARI": 1.02
  }
}
```

The loader in C2.4 reads `data["factors"].get(team, 1.0)`. Teams absent from `factors` fall back to 1.00. Commit just the scaffold so later steps can test against it:

```bash
git add data/park_factors.json
git commit -m "feat(c2): scaffold park_factors.json with provenance + 5 seed teams"
```

- [ ] **Step C2.1b: Fill remaining 25 teams (human-in-the-loop research task)**

This step is the hour-long manual work. Sources:
- FanGraphs park factors page (filter: K%, 3-season aggregate) — primary
- Baseball Savant park factors — cross-check

For each of the 25 remaining teams, record the K park factor to 2 decimal places. Add to the `factors` dict keeping keys sorted. **Also update `_source.fetched_at` to the actual research date.**

**Verify team codes at fill time** against the pipeline's current team lookup — grep `pipeline/run_pipeline.py` and `pipeline/fetch_odds.py` for the canonical code set. The reviewer flagged "ATH" (Oakland move) as an example of why the code list can drift; match whatever the pipeline actually uses in 2026, not last year's abbreviations.

**Use a WebFetch for FanGraphs park factors** to gather them in one pass, or do it manually and paste values. Either way, ensure the `_source.url` and `_source.fetched_at` are filled.

Commit:

```bash
git add data/park_factors.json
git commit -m "feat(c2): populate all 30 teams in park_factors.json"
```

- [ ] **Step C2.1c: Team-code resolution test**

Add a test that proves every team code the pipeline emits resolves to a park factor. This catches code drift when MLB renames a team — *without* dragging the entire pipeline into the test's import graph.

**First, create a lightweight constants module** at `pipeline/team_codes.py` (no other imports, no side effects):

```python
"""Canonical set of MLB 3-letter team codes the pipeline emits.
Single source of truth — imported by run_pipeline.py AND by the
park-factor resolution test. This module intentionally has zero
imports so tests can load it without pulling in the orchestrator."""

TEAM_CODES: frozenset[str] = frozenset({
    "ARI", "ATH", "ATL", "BAL", "BOS", "CHC", "CHW", "CIN", "CLE",
    "COL", "DET", "HOU", "KC",  "LAA", "LAD", "MIA", "MIL", "MIN",
    "NYM", "NYY", "PHI", "PIT", "SD",  "SEA", "SF",  "STL", "TB",
    "TEX", "TOR", "WSH",
})
```

(Verify the set matches what the pipeline actually emits — grep for team abbreviations in `run_pipeline.py` / `fetch_odds.py`. If the pipeline currently derives codes from a different source like an MLB API response, have `run_pipeline.py` import `TEAM_CODES` from this new module and validate its own output against it.)

**Update `run_pipeline.py`** to import from the new module instead of hardcoding:

```python
from team_codes import TEAM_CODES
```

**Then add the test** in [tests/test_park_factors.py](tests/test_park_factors.py) (new file — pure data-integrity test, keeps it out of the heavyweight `test_build_features.py`).

**Match the repo's existing test-import convention** (see `tests/test_fetch_stats.py`): pipeline isn't a package on `PYTHONPATH`, so tests prepend `pipeline/` to `sys.path` and import bare module names. Use that same pattern here — do NOT write `from pipeline.team_codes import TEAM_CODES`:

```python
"""Data-integrity tests for data/park_factors.json. Intentionally
imports only the lightweight team_codes module, NOT run_pipeline,
to keep this a fast unit test."""
import sys
import os
import json
from pathlib import Path

# Match the repo's existing test-import pattern (see tests/test_fetch_stats.py).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

from team_codes import TEAM_CODES  # noqa: E402 — path-insert required first


def test_every_pipeline_team_code_resolves_to_park_factor():
    """Every team code the pipeline emits must have a factor in park_factors.json.
    Catches code drift when MLB renames a team (e.g., OAK -> ATH)."""
    ROOT = Path(__file__).resolve().parent.parent
    data = json.loads((ROOT / "data" / "park_factors.json").read_text())
    factors = data["factors"]

    unresolved = sorted(t for t in TEAM_CODES if t not in factors)
    assert unresolved == [], (
        f"Park factor missing for: {unresolved}. "
        f"Add to data/park_factors.json factors dict or update TEAM_CODES."
    )


def test_park_factor_source_metadata_present():
    """The _source block exists and names a provider, URL, and fetched_at."""
    ROOT = Path(__file__).resolve().parent.parent
    data = json.loads((ROOT / "data" / "park_factors.json").read_text())
    src = data.get("_source", {})
    assert src.get("provider"), "park_factors.json must record _source.provider"
    assert src.get("url"),      "park_factors.json must record _source.url"
    assert src.get("fetched_at"), "park_factors.json must record _source.fetched_at"
```

Run: PASS after C2.1b completes. FAIL if a code ever drifts — early warning the next time MLB renames a franchise.

```bash
git add pipeline/team_codes.py pipeline/run_pipeline.py tests/test_park_factors.py
git commit -m "feat(c2): team_codes module + park_factors resolution + provenance tests"
```

- [ ] **Step C2.2: Write failing test**

```python
class TestParkFactor:
    def test_park_factor_applied_multiplicatively(self):
        """calc_lambda multiplies by park_factor when provided."""
        base = calc_lambda(k9=9.0, opp_k_rate=0.227, ump_adj=0.0,
                           innings=6.0, lambda_bias=0.0, park_factor=1.0)
        boosted = calc_lambda(k9=9.0, opp_k_rate=0.227, ump_adj=0.0,
                              innings=6.0, lambda_bias=0.0, park_factor=1.10)
        assert boosted > base
        assert abs(boosted - base * 1.10) < 0.01

    def test_park_factor_defaults_to_1(self):
        """Missing park_factor leaves lambda unchanged."""
        a = calc_lambda(k9=9.0, opp_k_rate=0.227, ump_adj=0.0, innings=6.0, lambda_bias=0.0)
        b = calc_lambda(k9=9.0, opp_k_rate=0.227, ump_adj=0.0, innings=6.0, lambda_bias=0.0, park_factor=1.0)
        assert abs(a - b) < 0.001
```

Run: FAIL (calc_lambda doesn't accept `park_factor`).

- [ ] **Step C2.3: Modify calc_lambda signature**

In [pipeline/build_features.py](pipeline/build_features.py), add `park_factor: float = 1.0` parameter and multiply into the lambda computation. Update docstring.

Run: tests pass.

- [ ] **Step C2.4: Load park factors in run_pipeline**

In [pipeline/run_pipeline.py](pipeline/run_pipeline.py), load `data/park_factors.json` once at startup and pass each pitcher's home-team factor into `build_pitcher_record` (which passes it to `calc_lambda`). Map pitcher's team → park factor via a team-code mapping (use MLB standard 3-letter codes).

Add a test that verifies a pitcher from COL (pitcher factor <1) gets lower applied_lambda than a neutral-park pitcher with identical other stats.

- [ ] **Step C2.5: Run full suite, commit**

**Commit plan for C2 (non-overlapping edits to `run_pipeline.py`):**
- **Commit 1 — C2.1a:** scaffold `data/park_factors.json` (5 seeds + `_source`).
- **Commit 2 — C2.1b:** fill remaining 25 teams in `data/park_factors.json`.
- **Commit 3 — C2.1c:** add `pipeline/team_codes.py` + `tests/test_park_factors.py` + the *import-only* edit to `run_pipeline.py` (replace any hardcoded team-code set with `from team_codes import TEAM_CODES`).
- **Commit 4 — C2.5 (this step):** the *behavioral* edits — `calc_lambda` signature change in `build_features.py` (C2.3) and the park-factor loader + lookup in `run_pipeline.py` (C2.4). These touch `run_pipeline.py` in a **different region** than C2.1c (new code, not the team-code import), so no merge conflict with the earlier commit.

```bash
python -m pytest tests/ -q
git add pipeline/build_features.py pipeline/run_pipeline.py tests/
git commit -m "feat(c2): apply ballpark K-factor multiplier to lambda"
```

Prefer listing the specific files rather than `pipeline/` / `tests/` globs so an accidental `data/park_factors.json` re-add (already committed in C2.1a/b) doesn't show up in this commit.

- [ ] **Step C2.6: 48h activation gate**

Wait ~48h, then check B5 slice. **Gate:** `park_factor` should be **populated** (non-null, numeric) for **≥98% of picks** — any missing value means team→park lookup is broken for that team code. A secondary-but-optional signal: `park_factor != 1.0` fires for ≥60% of picks; a park rounded to exactly 1.00 is legitimate, so don't hard-gate on this. If populated rate is <50%, the mapping is returning defaults too often — re-diagnose. Do NOT backfill historical picks with park factors — see global policy P1.

---

### Task C3: Pitcher rest / recent workload

**Files:**
- Modify: [pipeline/fetch_stats.py](pipeline/fetch_stats.py) (return `days_since_last_start`, `last_pitch_count`), [pipeline/build_features.py](pipeline/build_features.py) (apply K rate penalty for short rest or high recent pitch count)

Approach: additive K/9 delta based on rest days and recent pitch count. Short rest (< 5 days) or very high recent pitch count (>110) correlates with ~0.3-0.5 K/9 reduction. Conservative initial table; refine with B2/B3 data.

- [ ] **Step C3.1: Diagnostic — verify MLB Stats API exposes per-start dates + pitch counts**

Before building, confirm the data exists on the API surface `fetch_stats` already uses. Write `analytics/diagnostics/c3_rest_data_probe.py`:

```python
"""Probe whether MLB Stats API exposes per-start dates and pitch counts
via the same endpoint fetch_stats already hits.

Note: this diagnostic reads from MLB Stats API, not picks_history.json,
so global policy P2 doesn't apply. Instead we guard for network / import
failures so a missing RUNDOWN_API_KEY or a transient API outage produces
a readable error, not a silent traceback."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))

try:
    from fetch_stats import fetch_pitcher_stats  # or whichever entry point fetch_stats uses
except ImportError as e:
    print(f"ERROR: could not import fetch_stats: {e}. Run from repo root with pipeline deps installed.")
    raise SystemExit(1)

# Pick any known active SP with a current-season id
pitcher_id = 663362  # example: Framber Valdez — swap for a confirmed live id
try:
    stats = fetch_pitcher_stats(pitcher_id)
except Exception as e:
    print(f"ERROR: fetch_pitcher_stats failed: {e}. Check API key env vars and network.")
    raise SystemExit(1)

print("Top-level keys:", list(stats.keys()))
# Look for something like gameLog, stats[].splits[].date, numberOfPitches
for k, v in stats.items():
    if isinstance(v, list) and v and isinstance(v[0], dict):
        print(f"{k}[0] keys:", list(v[0].keys())[:20])
```

Run it. **Exit criterion (concrete):** if the output shows per-game entries with both a `gameDate`-like field AND a `numberOfPitches` / `pitchesThrown` field, proceed to C3.2. If either is missing from the endpoint `fetch_stats` currently uses, **STOP Phase C3** — do not scope-back inside this plan. Flag it for a separate data-source plan (adding a new endpoint call is out of scope here) and skip to C4.

- [ ] **Step C3.2: Write failing test**

```python
class TestRestAdjustment:
    def test_short_rest_reduces_k9(self):
        from build_features import calc_rest_k9_delta
        assert calc_rest_k9_delta(days_since_last=3, last_pitch_count=95) < 0

    def test_normal_rest_no_adjustment(self):
        from build_features import calc_rest_k9_delta
        assert calc_rest_k9_delta(days_since_last=5, last_pitch_count=95) == 0

    def test_high_pitch_count_reduces_k9(self):
        from build_features import calc_rest_k9_delta
        assert calc_rest_k9_delta(days_since_last=5, last_pitch_count=120) < 0

    def test_missing_data_neutral(self):
        from build_features import calc_rest_k9_delta
        assert calc_rest_k9_delta(None, None) == 0
```

- [ ] **Step C3.3: Implement**

Add `calc_rest_k9_delta` in [pipeline/build_features.py](pipeline/build_features.py) with a conservative additive table:

```python
def calc_rest_k9_delta(days_since_last: int | None,
                       last_pitch_count: int | None) -> float:
    """Additive K/9 delta for short rest or high recent workload.
    Conservative values; refine once Phase B data justifies larger penalties."""
    delta = 0.0
    if days_since_last is not None and days_since_last < 4:
        delta -= 0.3
    if last_pitch_count is not None and last_pitch_count > 110:
        delta -= 0.2
    return delta
```

- [ ] **Step C3.4: Wire into build_pitcher_record**

Apply delta additively to the blended K/9 in `build_pitcher_record` (mirror the pattern already used for `swstr_delta_k9`).

- [ ] **Step C3.5: Run suite and commit**

```bash
git add tests/ pipeline/
git commit -m "feat(c3): apply rest/workload K/9 delta"
```

- [ ] **Step C3.6: 48h activation gate**

Wait ~48h, then check the data via B5 / a quick script. **Gate:** `days_since_last_start` and `last_pitch_count` populated for ≥90% of starting pitchers. Non-zero `rest_k9_delta` will be rarer (fires only on short rest or high recent pitch count — expect ~10-25% of picks). If the populated-fields rate is <50%, the MLB API fetch isn't working and C3 is effectively dormant — re-diagnose.

---

### Task C4: K-variance / Poisson tail haircut

**Files:**
- Modify: [pipeline/build_features.py](pipeline/build_features.py) (apply EV haircut at extreme tiers)

Approach: empirically the >15% EV bucket underperforms. The Poisson model under-states K variance for fatter-tailed real distributions, so extreme-tail probability mass is overestimated. Haircut applied EV for very high raw EV.

- [ ] **Step C4.1: Review Phase B data first, and schedule the alternative if you skip**

If B1/B2 already explain the >15% underperformance (e.g., it's all high-lambda-bucket picks and the issue was lambda-bucket-specific bias, not Poisson tail), **skip C4 entirely** — a uniform haircut would mask the real problem, not fix it.

**Skipping C4 does not mean the problem is solved.** Before moving to Completion, create a follow-up plan stub so the root cause is scheduled, not forgotten:

```bash
# Create the placeholder file now so the problem isn't dropped.
# Real content can be brainstormed/written in a later session.
```

Create `docs/superpowers/plans/2026-04-XX-bucketed-lambda-calibration.md` (use today's date) with this minimal outline:

```markdown
# Bucketed Lambda Calibration — Follow-up to C4 Skip

**Spawned from:** 2026-04-16 model audit plan, C4.1 skip decision.

**Problem:** Phase B (B1/B2) showed that prediction bias is NOT uniform across
the lambda range. High-lambda picks underperform while low-lambda picks do not.
A global `lambda_bias` scalar will never close a bias that is bucket-shaped.

**Approach to design:** extend `calibrate.py` to fit a piecewise lambda_bias
(e.g., one value for lambda<5, another for 5-7, another for >7) with minimum
sample size per bucket (>=20) and a fallback to the global value when thin.

**Open questions to resolve before implementing:**
- Bucket boundaries (fixed or data-driven)?
- How to avoid bucket-boundary discontinuities in lambda?
- Does this interact with C1 opener detection (which removes high-variance picks)?

**Status:** placeholder — not scheduled for work. Revisit after Phase C1–C3 settle.
```

Commit the placeholder so the follow-up work is discoverable from git log:

```bash
git add docs/superpowers/plans/
git commit -m "docs(c4): placeholder plan for bucketed lambda calibration (C4 skip)"
```

**Then** proceed to the Completion section (Z.1–Z.4). Prior C commits (C1, C2, C3) still stand independently. Note the skip decision and the placeholder in the Z.3 CLAUDE.md update.

- [ ] **Step C4.2: Write failing test**

```python
class TestEVHaircut:
    def test_low_ev_unchanged(self):
        from build_features import apply_ev_haircut
        assert apply_ev_haircut(0.03) == 0.03

    def test_extreme_ev_reduced(self):
        from build_features import apply_ev_haircut
        # >15% haircut: scale down linearly toward 15%
        result = apply_ev_haircut(0.25)
        assert 0.10 < result < 0.20  # haircut but still high
```

- [ ] **Step C4.3: Implement and wire**

Add `apply_ev_haircut` and apply to `ev_over["ev"]` / `ev_under["ev"]` before verdict calculation in `build_pitcher_record`. Be conservative; document the expected effect.

- [ ] **Step C4.4: Run and commit**

```bash
git add tests/ pipeline/
git commit -m "feat(c4): apply EV haircut to extreme-tail picks"
```

---

### Task C5: Surface data-source warnings in today.json *(self-healing — make silent failures visible at a glance)*

**Files:**
- Modify: [pipeline/run_pipeline.py](pipeline/run_pipeline.py) (collect warnings from each fetch step), [pipeline/fetch_umpires.py](pipeline/fetch_umpires.py) and others (return empty-result signals), [dashboard/index.html](dashboard/index.html) (display badge)
- Test: [tests/test_run_pipeline.py](tests/test_run_pipeline.py) or appropriate existing test file

Purpose: once A3 adds logging for fetch_umpires failures, those warnings still only live in GitHub Actions logs — nobody notices until performance tanks. This surfaces them as a `data_warnings` array in `today.json` so the dashboard can badge a degraded run.

- [ ] **Step C5.1: Define warning contract — with explicit units convention**

In [pipeline/run_pipeline.py](pipeline/run_pipeline.py), agree on a simple string-list contract.

**Units convention (applied consistently across every warning string):**
- **"games"** — counts each scheduled game once. Used for HP umpire (one ump per game).
- **"lineups"** — counts each *opposing* lineup relevant to the model. Every game has TWO lineups (one per pitcher's opponent). A 15-game slate has 30 lineups. A game with one confirmed + one projected lineup is half-covered, not fully covered — per-game counting would hide exactly the partial degradation this warning system exists to surface.

```python
# data_warnings examples written into today.json (15-game slate):
# "fetch_umpires returned 0 entries for 15 scheduled games"
# "fetch_batter_stats missing splits for 8/30 opposing lineups"
# "fetch_swstr: pybaseball call failed, using neutral 0.0 delta"
# "fetch_lineups: confirmed 18/30 opposing lineups (12 still projected)"
```

Each warning is one user-readable string. Array is empty on a clean run. **Do not mix units inside a single warning** (e.g., "9/15 games; 6 teams still projected" — that was the draft version; it conflates games vs teams and undercounts partial coverage).

- [ ] **Step C5.2: Write failing test for pure `collect_data_warnings` helper**

Extracting the collection logic into a pure function avoids mocking `run_pipeline` end-to-end. In [tests/test_run_pipeline.py](tests/test_run_pipeline.py) (or a new `tests/test_data_warnings.py`):

```python
def test_collect_data_warnings_flags_empty_ump_map():
    from run_pipeline import collect_data_warnings
    games = [{"id": 1}, {"id": 2}]
    warnings = collect_data_warnings(
        games=games,
        ump_map={},
        swstr_map={"pitcher_a": 0.01},
        batter_stats={"pitcher_a": {"lineup": []}},
        confirmed_opponent_lineups=4,  # 2 games * 2 lineups = fully covered
    )
    assert any("fetch_umpires" in w and "2" in w for w in warnings)

def test_collect_data_warnings_clean_run_returns_empty():
    from run_pipeline import collect_data_warnings
    warnings = collect_data_warnings(
        games=[{"id": 1}],
        ump_map={"Joe Umpire": 0.03},
        swstr_map={"pitcher_a": 0.01},
        batter_stats={"pitcher_a": {}},
        confirmed_opponent_lineups=2,  # 1 game * 2 lineups = fully covered
    )
    assert warnings == []

def test_collect_data_warnings_flags_partial_lineup_coverage():
    """3-game slate has 6 opposing lineups. Only 1 confirmed → half-covered
    games would be HIDDEN by per-game counting; per-lineup counting surfaces it."""
    from run_pipeline import collect_data_warnings
    warnings = collect_data_warnings(
        games=[{"id": 1}, {"id": 2}, {"id": 3}],
        ump_map={"Joe Umpire": 0.03},
        swstr_map={"pitcher_a": 0.01},
        batter_stats={"pitcher_a": {}},
        confirmed_opponent_lineups=1,  # 1 of 6 opposing lineups confirmed
    )
    assert any("fetch_lineups" in w and "1/6" in w for w in warnings)

def test_collect_data_warnings_flags_half_covered_game():
    """The critical case: every game has one lineup up and one projected.
    Per-game counting would mark every game as 'covered'; per-lineup
    counting correctly reports 3/6 lineups."""
    from run_pipeline import collect_data_warnings
    warnings = collect_data_warnings(
        games=[{"id": 1}, {"id": 2}, {"id": 3}],
        ump_map={"Joe Umpire": 0.03},
        swstr_map={"pitcher_a": 0.01},
        batter_stats={"pitcher_a": {}},
        confirmed_opponent_lineups=3,  # each game half-covered
    )
    assert any("fetch_lineups" in w and "3/6" in w for w in warnings)
```

Run: FAIL (`collect_data_warnings` doesn't exist).

- [ ] **Step C5.3: Implement the pure helper, then wire it into run_full**

In [pipeline/run_pipeline.py](pipeline/run_pipeline.py), add a pure function with no I/O:

```python
def collect_data_warnings(*, games: list, ump_map: dict, swstr_map: dict,
                          batter_stats: dict,
                          confirmed_opponent_lineups: int) -> list[str]:
    """Pure function: given the outputs of today's fetches, return a list of
    user-readable degradation warnings. Empty list = clean run.

    Units convention (see C5.1):
    - n_games   = len(games)        — used for HP umpire coverage
    - n_lineups = 2 * n_games       — used for opposing-lineup coverage.
                                      Every game has TWO relevant opposing lineups
                                      (one per pitcher). A game with one lineup
                                      confirmed + one projected contributes 1
                                      (not 2) to confirmed_opponent_lineups,
                                      correctly surfacing half-coverage.

    confirmed_opponent_lineups: integer in [0, 2*n_games]. Caller must count
    per-pitcher (per opposing lineup), NOT per-game, or partial coverage will
    be silently hidden.
    """
    warnings: list[str] = []
    n_games   = len(games)
    n_lineups = 2 * n_games
    if n_games == 0:
        return warnings
    if not ump_map:
        warnings.append(f"fetch_umpires returned 0 entries for {n_games} scheduled games")
    if confirmed_opponent_lineups < n_lineups:
        missing = n_lineups - confirmed_opponent_lineups
        warnings.append(
            f"fetch_lineups: confirmed {confirmed_opponent_lineups}/{n_lineups} "
            f"opposing lineups ({missing} still projected)"
        )
    if not swstr_map:
        warnings.append("fetch_swstr returned empty map; neutral 0.0 delta applied")
    if not batter_stats:
        warnings.append("fetch_batter_stats returned empty; falling back to team aggregate K%")
    return warnings
```

Then at the end of `run_full`, call it and attach the result. **Count per-pitcher (per opposing lineup), not per-game** — otherwise a game with one team up and the other projected is hidden:

```python
# Count confirmed lineups per-pitcher: each game has two pitchers, each
# facing the OPPOSING team's lineup. Adapt field names to whatever
# fetch_lineups actually emits on the game dict (e.g. home_lineup_confirmed
# and away_lineup_confirmed). If the schema stores lineup status keyed by
# team abbreviation, iterate those instead.
confirmed_opponent_lineups = sum(
    1
    for g in games
    for side in ("home_lineup_confirmed", "away_lineup_confirmed")
    if g.get(side)
)

today["data_warnings"] = collect_data_warnings(
    games=games, ump_map=ump_map, swstr_map=swstr_map,
    batter_stats=batter_stats,
    confirmed_opponent_lineups=confirmed_opponent_lineups,
)
```

**Pre-wire check:** grep [pipeline/fetch_lineups.py](pipeline/fetch_lineups.py) for the actual field names on each game dict that indicate per-team lineup confirmation. If the current schema only exposes a single `lineup_confirmed` bool per game, extend `fetch_lineups` first to expose per-side status — otherwise `confirmed_opponent_lineups` collapses to `2 * games_with_confirmed` and you're back to per-game counting with a misleading denominator.

Run the test file: PASS. Because the helper is pure, no pipeline-wide mock is needed.

- [ ] **Step C5.4: Dashboard badge**

In [dashboard/index.html](dashboard/index.html), find where `today.json` is loaded and add a badge render:

```javascript
if (data.data_warnings && data.data_warnings.length > 0) {
    // small muted badge near the header: "⚠ N data warnings"
    // clicking expands a details panel listing the warning strings
}
```

Keep it subtle — users should see "something's degraded today" without panic. Degraded runs still show picks.

- [ ] **Step C5.5: Backward-compat check**

`data_warnings` is new in `today.json`. Older cached JSONs lack it. Dashboard must treat `data_warnings` as optional (`data.data_warnings?.length > 0`) so historical archive views don't break.

- [ ] **Step C5.6: Run full suite and commit**

```bash
python -m pytest tests/ -q
git add tests/ pipeline/ dashboard/index.html
git commit -m "feat(c5): surface data-source warnings in today.json and dashboard"
```

---

## Completion

After all phases:

- [ ] **Step Z.1: Run full suite, confirm green**

```bash
python -m pytest tests/ -q
```

- [ ] **Step Z.2: Re-run analytics and diff against baseline**

```bash
python analytics/performance.py --since 2026-04-08 > analytics/output/post_2026-04-16.txt
git diff --no-index analytics/output/baseline_2026-04-16.txt analytics/output/post_2026-04-16.txt
```

(`analytics/output/` is gitignored, so the baseline and post files are local-only by design. `git diff --no-index` is used instead of `diff` because `diff` isn't available by default in PowerShell / cmd on Windows; `git` ships with both Git Bash and Windows PowerShell so this works across environments.)

**Expected diff character:** the post file will have six new sections (B1 residuals-by-side, B2 residuals-by-lambda-bucket, B3 per-pitcher, B4 dead-zone, B5 signal activation, B6 feature contributions) that don't exist in baseline — those diffs are **expected**. The signal to watch for is **regression in pre-existing sections** (overall ROI, by-verdict, by-side, by-bookmaker) — those should match baseline or improve, not degrade.

- [ ] **Step Z.3: Update CLAUDE.md**

Add notes about:
- Opener detection (new `is_opener` field in `today.json`)
- Park factors file location and **a staleness reminder** (refresh `data/park_factors.json` at end of each season; add to the existing end-of-season review block)
- Rest adjustment (if C3 landed)
- New analytics slices (B1–B6): what each shows, when to run
- `data_warnings` field in `today.json` and dashboard badge (C5)
- Weekly health-check habit: run `python analytics/performance.py --since <recent-date>` and eyeball B5 activation rates; anything dropping to ~0% means a silent fetch break

Keep the data-volume reminder about per-batter handedness splits intact.

- [ ] **Step Z.4: Final commit**

```bash
git add CLAUDE.md
git commit -m "docs: document Phase C additions in CLAUDE.md"
```

---

## Rollback strategy

Each task is one or two focused commits. To back out any individual change: `git revert <sha>`. No schema changes are destructive — `picks_history.json` only gains optional fields (`is_opener`, etc.) which older dashboard code ignores gracefully via JS optional-chaining.

**Commits that are split on purpose (revert independently):**
- A1.7 (code fix) vs A1.8 (history backfill) — revert the backfill without losing the code fix if the backfill introduced bad pitcher_throws values.
- C2.1a (scaffold) vs C2.1b (full 30-team fill) — if a specific team's park factor is suspect, revert just C2.1b and the file falls back to the 5-seed scaffold plus defaults.

**If lambda_bias starts diverging after Phase C lands, prime suspects in order:**
1. Park factors (C2) — double-applies if team→park lookup is wrong
2. Rest adjustment (C3) — delta table too aggressive
3. Opener detection (C1) — if it wrongly flags real starters, excludes good picks

Revert the suspect commit, let calibration re-converge for 3-5 days, then re-approach with tighter thresholds.
