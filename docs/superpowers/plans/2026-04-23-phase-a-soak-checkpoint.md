# Phase A Soak Checkpoint — 2026-04-23 → 2026-04-24

> **Purpose:** Handoff note for the next Claude who picks up after the 2026-04-24
> slate grades. Written 2026-04-23 at the end of Phase A shipping. Everything
> actionable is in the "When you come back" section at the bottom.

---

## Current state (as of 2026-04-23, UTC-end-of-day)

**Phase A is done pending 24h soak.** All seven tasks (A1–A7) have landed on
`origin/main`. User explicitly wants to wait for the 2026-04-24 slate to
grade before kicking off Phase B.

### Commits pushed this session (tip of `origin/main`)

```
ee5d44c  feat(a7): flag starter_mismatch when MLB probablePitcher != odds pitcher
1438481  fix(a5): use /game/{pk}/boxscore for lineups instead of schedule hydrate
144a5c3  feat(a6): collapse pre-Option-B BookN placeholders in by_bookmaker slice
a1c7ed0  docs(plan): add A5/A6/A7 tasks from 2026-04-23 soak re-audit
```

Earlier this week (still load-bearing for the soak):

```
1ac976c  fix(a3): populate team/opp_team on props before fetch_umpires
(chore commits between)
...
6be5c22  feat(a2): add opening_odds_source enum + gate movement_conf to preview-sourced openings
b134fd5  fix: flip ump_ok=False when ump_map is empty or all-zero
```

### What each shipped fix does

| Task | Signal | Pre-fix state | Fix | Expected post-fix |
|---|---|---|---|---|
| **A1** | `pitcher_throws` | 28% null on post-4/8 staked | `/people/{id}` fallback when schedule hydrate omits `pitchHand` | Near-zero null rate |
| **A2** | `movement_conf` | 3/145 non-1.0 (dormant) | `opening_odds_source` enum; haircut gates on `preview` only | Real haircuts only when we have real opening snapshots |
| **A3** | `ump_k_adj` | 601/601 == 0.0 (dead signal) | Backfill `team`/`opp_team` on props before `fetch_umpires` | ≥90% nonzero on staked picks |
| **A4** | analytics | no per-book slice | `by_bookmaker` table in `analytics/performance.py` | New slice visible |
| **A5** | `lineup_used` | 602/602 == False (dead signal) | Two-call flow: `/schedule` → `/game/{pk}/boxscore` for battingOrder | Morning-run `lineup_used` rate climbs to ≥80% |
| **A6** | analytics cosmetic | BookN placeholders cluttered output | Collapse to `<untracked-legacy>` bucket | Cleaner by_bookmaker output |
| **A7** | `starter_mismatch` | silent phantom picks (Chad Patrick, Martin Perez 4/22) | `fetch_stats` returns `(stats_by_name, probables_by_team)`; `_restamp_starter_mismatch` in run_pipeline | Phantoms flagged BEFORE void, dashboard can hide |

### Key architectural decisions (precedents to honor in Phase B)

1. **A3 precedent = forward-only fixes.** No `picks_history.json` rewrites, no
   regrading, no `formula_change_date` bump. `lambda_bias` self-heals via
   normal calibration. Applied verbatim to A5 and A7.

2. **`data_complete` untouched for starter_mismatch.** A7 deliberately does NOT
   set `data_complete=False` on mismatched picks. We want soak data first
   before deciding whether to exclude from calibration. The follow-up task is
   **A7.5b** (still pending).

3. **A7 safe defaults:**
   - `stats.probable_name` missing → `starter_mismatch=False` (no false
     positives on preview path or older cached entries)
   - `probables_by_team[team] is None` → leave flag alone (MLB hasn't posted)
   - `probables_by_team == {}` (API down) → re-stamp is a no-op

### Test state

- **321 passed**, 1 pre-existing failure:
  `test_write_dated_archive_only_creates_dated_file` — unrelated `index.json`
  schema drift (list-of-strings vs list-of-dicts). Confirmed pre-existing
  by stashing A5 changes and re-running.
- 10 new A7 tests: 4 in `test_build_features.py::TestBuildPitcherRecord`,
  6 in `test_run_pipeline.py::test_restamp_starter_mismatch_*`.
- 7 new/rewritten A5 tests in `test_fetch_lineups.py` (URL-routed mock
  dispatching schedule vs boxscore responses).
- 9 `fetch_stats(...)` call sites in `test_fetch_stats.py` updated to unpack
  the new 2-tuple return shape.

### Schema changes to watch (v1/v2 dashboard compat)

Per CLAUDE.md, `today.json` must stay backward-compatible with both v1 and v2
dashboards. A7 ADDS one nullable field:

- `starter_mismatch: bool` — new, safe addition (nullable-on-read for v2)

No renames, no removals. v2 adapter (`dashboard/v2-data.js`) doesn't read this
field yet; that's A7.5b.

---

## When you come back (after 2026-04-24 slate grades)

**User's explicit instruction:** *"well let it soak tomorrow before finalzing
A7 and engaging Phase B"* and *"then Phase A might actually be done"*.

### Step 1: Re-measure the four soak metrics

The grading run fires at 3 AM PT on 2026-04-25, after 2026-04-24's games are
final. Once that's done:

```powershell
python analytics/performance.py --since 2026-04-08
```

Look for these four numbers (baseline from re-audit at end of this session):

| Metric | Pre-A fixes (all-time) | Target post-fix | How to read it |
|---|---|---|---|
| **M1: `pitcher_throws` null rate** | 28% | ~0% | Staked picks only |
| **M2: `ump_k_adj` nonzero rate** | 0/601 all-time, 0/145 post-4/8 | ≥90% on staked 2026-04-24+ | THE key soak metric |
| **M3: `opening_odds_source=="preview"` rate** | <3% historical | climbing per slate | Shows real preview data flowing |
| **M4: `lineup_used=True` rate on morning runs** | 0/602 all-time | ≥80% on staked 2026-04-24+ | New this session (A5) |

Also check the analytics output for:
- **`by_bookmaker` slice** — should now show `<untracked-legacy>` n drop over
  time as BookN placeholders age out (49 historical, 38 all-time, 2 in soak
  window, should stay 2 since ref_book UPDATE path doesn't touch legacy rows).
- **`starter_mismatch` prevalence** — count of picks with the flag set.
  Calibration-safe as long as it's not pervasive. If 2026-04-24 shows 2+
  mismatches same as 4/22, that's a signal but not alarming.

### Step 2: Present findings to user and ask for Phase B greenlight

**Plan checkpoint A → B is a HARD STOP.** From the plan (line 1081-1088 of
`docs/superpowers/plans/2026-04-16-model-audit-and-gaps.md`):

> STOP HERE. Do not proceed to Phase B automatically, even in auto mode.
> Post the findings from A1/A2/A3 diagnostics to the user and explicitly wait
> for a "proceed" reply.

Even though auto mode is active, this checkpoint was user-mandated before auto
mode was enabled. Respect it. The correct next message after running analytics
is a summary of M1-M4 + `starter_mismatch` prevalence + an explicit "ready to
engage Phase B?"

### Step 3: If user says "go" — Phase B

Phase B adds analytics slices (not pipeline changes):
- B1: Residual mean split by over/under side
- B2: Residual by predicted-lambda bucket
- B3: Per-bookmaker performance breakdown (A4 extended)
- B4: Per-pitcher track record
- B5: Signal-activation rates over time
- B6: Feature-contribution audit

All Phase B work is in `analytics/performance.py` — no pipeline or today.json
schema touches. Low-risk. Can run in parallel with continued soaking.

### Step 4: If M2 is still degraded

If M2 ump_k_adj nonzero rate is <90% on 2026-04-24 staked picks, the A3 fix
didn't fully close. Check the props enrichment order in `pipeline/run_pipeline.py`
around line 739-743 (the `team`/`opp_team` backfill loop). Likely cause: a
pitcher whose `stats_map` lookup failed (no MLB probable match) — those props
stay with empty-string team, and `fetch_umpires` silently returns 0 for them.
This overlaps with the A7 phantom case and may indicate the phantom guard
needs calibration-safety promotion (A7.5b).

---

## Open follow-ups after Phase A soak

- **A7.5b** (deferred): wire `starter_mismatch` into `v2-data.js` banner +
  optionally `data_complete=False` for calibration exclusion. Need soak data
  first (see A7 plan block line 1060-1062).
- **Pre-existing test failure**: `test_write_dated_archive_only_creates_dated_file`
  — low-priority cleanup. The test expects `index.json["dates"]` to be a
  list of strings, but the production writer produces list of dicts.
  Either the test or the writer is stale; worth investigating when touching
  that module.
- **Phase B pre-work**: baseline snapshot was captured in
  `analytics/output/baseline_2026-04-16.txt` per plan step 0.2. Diff against
  it after 2026-04-24 to show Phase A effect.

---

## Files touched this session (quick recall)

```
pipeline/fetch_lineups.py          — A5 rewrite (boxscore two-call)
pipeline/fetch_stats.py            — A7 return tuple + probable_name per entry
pipeline/build_features.py         — A7 starter_mismatch emit
pipeline/run_pipeline.py           — A7 unpack tuple + _restamp_starter_mismatch pass
analytics/performance.py           — A6 _normalize_ref_book for BookN cosmetic
tests/test_fetch_lineups.py        — A5 rewritten with real API shape
tests/test_fetch_stats.py          — A7 tuple unpack in 9 call sites
tests/test_build_features.py       — A7 4 starter_mismatch tests
tests/test_run_pipeline.py         — A7 6 _restamp tests + mock tuple fixups
docs/data-caveats.md               — A5 dead-signal-window entry
docs/superpowers/plans/2026-04-16-model-audit-and-gaps.md  — A5/A6/A7 task blocks
```

## Files explicitly NOT touched (per precedent)

```
data/picks_history.json            — no backfill, no regrading
data/params.json                   — no formula_change_date bump, lambda_bias unchanged
dashboard/v2-data.js               — A7.5b scope, not A7
dashboard/index.html               — v1 stays stable
```

---

*Written by Claude Opus 4.7 at end of 2026-04-23 session. If this doc is >2
weeks old when you're reading it, the soak has probably already been resolved
and this file is safe to delete.*
