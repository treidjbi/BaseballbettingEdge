# Input Quality Gates and Data Maturity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent high-conviction picks from being emitted when the projection is built on unsafe or immature inputs, while preserving the raw model output for auditing and model improvement.

**Architecture:** Add a pure quality-gate layer after feature construction and before pick seeding. The layer annotates each pitcher with input flags, maturity states, projection safety, raw verdicts, and actionable verdicts. Severe issues force actionable `PASS`; soft issues cap conviction without deleting the underlying projection.

**Tech Stack:** Python 3.11, pytest, vanilla dashboard JS, SQLite-backed `data/picks_history.json`, `dashboard/data/processed/today.json`, `dashboard/v2-data.js`, `dashboard/v2-app.js`.

---

## Why This Exists

The model is now pulling more data and using better sources, but better inputs also create a new risk: a single unresolved starter, opener, unrated umpire, thin pitcher profile, or weak market baseline can make a pick look more confident than it really is.

The goal is not to make the model timid. The goal is to make it scalable:

1. Keep raw projections visible so we can learn.
2. Keep staking/actionable verdicts conservative when critical inputs are weak.
3. Track when new pitchers, umpires, lineups, and market feeds become trustworthy enough to graduate.
4. Make FIRE 2u require a clean projection stack, not merely a large EV number.

---

## Product Rules

### Severe Gates

Any severe flag forces both sides to actionable `PASS`.

Severe flags:

- `no_pitcher_k_profile`
- `starter_mismatch`
- `opener`
- `missing_game_time`
- `unresolved_probable`
- `malformed_line_or_odds`
- `invalid_lambda_inputs`
- `missing_team_or_opp_team`

Important nuance:

- `no_target_book` usually happens before a pitcher record exists because `fetch_odds` skips props with no trusted target book. Track those as top-level skip counts first. Only use a per-pitcher `no_target_book` flag if a future fetch path returns an otherwise buildable record with missing trusted odds.

### Soft Caps

Soft flags do not block the projection, but they cap betting conviction.

Soft flags:

- `projected_lineup`
- `partial_lineup`
- `unrated_umpire`
- `thin_umpire_sample`
- `missing_career_swstr`
- `neutral_park_fallback`
- `first_seen_opening`
- `thin_recent_start_sample`
- `developing_pitcher_sample`
- `partial_movement_history`

Cap rules:

- 0 meaningful soft flags: no cap; FIRE 2u is allowed if thresholds support it.
- 1 meaningful soft flag: max actionable verdict is `FIRE 1u`.
- 2 or more meaningful soft flags: max actionable verdict is `LEAN`.
- FIRE 2u requires clean major data: no severe flags and no meaningful soft flags.

### Data Maturity

Each pitcher record should expose:

```json
{
  "data_maturity": {
    "pitcher": "none | thin | developing | mature",
    "umpire": "unknown | thin | developing | mature",
    "lineup": "projected | partial | confirmed",
    "market": "missing | first_seen | preview_open | full_movement"
  }
}
```

Pitcher maturity:

- `none`: no usable season, recent, or career K profile. Severe PASS.
- `thin`: 1-2 true starts and no strong prior profile. Max LEAN.
- `developing`: 3-4 true starts or 1-2 true starts with reliable prior MLB profile. Max FIRE 1u.
- `mature`: 5+ true starts and usable season/career profile. Eligible for FIRE 2u if all other major data is clean.

Umpire maturity:

- `unknown`: confirmed umpire has no career-rate entry. Soft cap via `unrated_umpire`.
- `thin`: fewer than 10 HP games in the rating seed. Treat as neutral or heavily shrunk; no FIRE 2u boost from ump signal.
- `developing`: 10-49 HP games. Use a shrunk adjustment; no FIRE 2u boost from ump signal.
- `mature`: 50+ HP games. Normal adjustment.

Lineup maturity:

- `projected`: no confirmed batting order; use team/projection fallback and cap.
- `partial`: batting order exists but has fewer than 9 hitters; cap.
- `confirmed`: ordered 9-man lineup was fetched.

Market maturity:

- `missing`: no trusted current target-book odds; block if a record exists.
- `first_seen`: current-day first-seen opening only; soft cap.
- `preview_open`: midnight preview/opening baseline is attached; clean enough for normal betting if other inputs are clean.
- `full_movement`: preview baseline plus enough same-book snapshots for steam/CLV tracking.

---

## Output Contract

Add the following top-level fields to each pitcher record in `today.json` and archives:

```json
{
  "input_quality_flags": ["projected_lineup", "first_seen_opening"],
  "projection_safe": true,
  "quality_gate_level": "clean | capped | blocked",
  "quality_gate_reasons": ["..."],
  "verdict_cap_reason": "1 soft input flag: projected_lineup",
  "data_maturity": {
    "pitcher": "mature",
    "umpire": "unknown",
    "lineup": "projected",
    "market": "preview_open"
  }
}
```

Add the following side-level fields inside `ev_over` and `ev_under`:

```json
{
  "raw_verdict": "FIRE 2u",
  "actionable_verdict": "FIRE 1u",
  "verdict": "FIRE 1u",
  "raw_adj_ev": 0.19,
  "quality_gate_level": "capped",
  "quality_gate_reasons": ["1 soft input flag: unrated_umpire"]
}
```

Backward compatibility rule:

- Existing dashboard and grading paths can keep reading `ev_*["verdict"]`.
- After this implementation, `ev_*["verdict"]` is the actionable verdict.
- `ev_*["raw_verdict"]` stores what the model would have emitted without quality gates.
- `ev_*["raw_adj_ev"]` stores pre-gate adjusted EV.
- Severe gates set actionable `verdict` to `PASS`. They should also set actionable `adj_ev` to `0.0` to keep existing ranking and seeding paths safe.
- Soft caps may keep numeric `adj_ev` unchanged, but `verdict` must be capped. The dashboard should display the capped verdict as the betting decision.

Top-level slate summary:

```json
{
  "quality_gate_summary": {
    "clean": 12,
    "capped": 5,
    "blocked": 1,
    "severe_flags": {
      "opener": 1
    },
    "soft_flags": {
      "projected_lineup": 4,
      "unrated_umpire": 2
    },
    "pre_record_skips": {
      "no_target_book": 3,
      "unresolved_probable": 2
    }
  }
}
```

---

## File Plan

Create:

- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/pipeline/quality_gates.py`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/tests/test_quality_gates.py`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/analytics/diagnostics/e5_quality_gate_audit.py`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/tests/test_e5_quality_gate_audit.py`

Modify:

- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/pipeline/build_features.py`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/pipeline/run_pipeline.py`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/pipeline/fetch_results.py`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/scripts/seed_umpire_career_rates.py`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2-data.js`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2-app.js`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2-data.test.mjs`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/AGENTS.md`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/docs/current-state.md`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/docs/superpowers/plans/2026-04-28-one-week-evaluation-cadence.md`

---

## Task 1: Add Pure Quality Gate Logic

**Files:**

- Create: `pipeline/quality_gates.py`
- Create: `tests/test_quality_gates.py`

- [ ] **Step 1: Define verdict ordering and caps**

Implement:

```python
VERDICT_ORDER = {
    "PASS": 0,
    "LEAN": 1,
    "FIRE 1u": 2,
    "FIRE 2u": 3,
}

SEVERE_FLAGS = {
    "no_pitcher_k_profile",
    "starter_mismatch",
    "opener",
    "missing_game_time",
    "unresolved_probable",
    "malformed_line_or_odds",
    "invalid_lambda_inputs",
    "missing_team_or_opp_team",
    "no_target_book",
}

SOFT_CAP_FLAGS = {
    "projected_lineup",
    "partial_lineup",
    "unrated_umpire",
    "thin_umpire_sample",
    "missing_career_swstr",
    "neutral_park_fallback",
    "first_seen_opening",
    "thin_recent_start_sample",
    "developing_pitcher_sample",
    "partial_movement_history",
}
```

Expected behavior:

- Unknown flags are preserved for visibility but do not affect caps unless added to one of the known sets.
- The module has no file, network, date, or dashboard dependencies.

- [ ] **Step 2: Implement maturity helpers**

Implement:

```python
def pitcher_maturity(record: dict) -> tuple[str, list[str]]:
    ...

def umpire_maturity(record: dict) -> tuple[str, list[str]]:
    ...

def lineup_maturity(record: dict) -> tuple[str, list[str]]:
    ...

def market_maturity(record: dict) -> tuple[str, list[str]]:
    ...
```

Inputs to support:

- `season_k9`, `recent_k9`, `career_k9`
- `recent_start_count` if present
- `is_opener`
- `starter_mismatch`
- `game_time`
- `team`, `opp_team`
- `lineup_used`
- `lineup_count` if present
- `umpire`, `umpire_has_rating`, `umpire_rating_games` if present
- `opening_odds_source`
- `book_odds`
- `best_over_odds`, `best_under_odds`, `k_line`, `lambda`

Expected maturity outputs:

- Missing profile -> `pitcher: none` plus `no_pitcher_k_profile`.
- Recent starts 1-2 -> `pitcher: thin` plus `thin_recent_start_sample`.
- Recent starts 3-4 -> `pitcher: developing` plus `developing_pitcher_sample`.
- Confirmed but unrated umpire -> `umpire: unknown` plus `unrated_umpire`.
- No confirmed lineup -> `lineup: projected` plus `projected_lineup`.
- First-seen opening -> `market: first_seen` plus `first_seen_opening`.

- [ ] **Step 3: Implement record evaluator**

Implement:

```python
def evaluate_record_quality(record: dict) -> dict:
    """Return quality metadata without mutating record."""
```

Return shape:

```python
{
    "input_quality_flags": [...],
    "projection_safe": True,
    "quality_gate_level": "clean",
    "quality_gate_reasons": [],
    "verdict_cap_reason": "",
    "data_maturity": {
        "pitcher": "mature",
        "umpire": "mature",
        "lineup": "confirmed",
        "market": "preview_open",
    },
    "max_actionable_verdict": "FIRE 2u",
}
```

Expected:

- Severe flags -> `projection_safe=False`, `quality_gate_level="blocked"`, max verdict `PASS`.
- 1 soft flag -> `quality_gate_level="capped"`, max verdict `FIRE 1u`.
- 2+ soft flags -> `quality_gate_level="capped"`, max verdict `LEAN`.
- Clean -> max verdict `FIRE 2u`.

- [ ] **Step 4: Implement side verdict application**

Implement:

```python
def cap_verdict(raw_verdict: str, max_actionable_verdict: str) -> str:
    ...

def apply_quality_to_record(record: dict) -> dict:
    """Return a copied record with quality metadata and capped ev_over/ev_under."""
```

Expected:

- Preserve raw verdicts before mutating side verdicts.
- Preserve raw adjusted EV as `raw_adj_ev`.
- For blocked records, set side `verdict` and `actionable_verdict` to `PASS`.
- For blocked records, set side `adj_ev` to `0.0`.
- For capped records, cap side `verdict` and `actionable_verdict`; preserve raw `adj_ev` and `raw_adj_ev`.

- [ ] **Step 5: Test the pure logic**

Tests to add:

```python
def test_severe_gate_blocks_fire_two():
    record = clean_fire_record()
    record["starter_mismatch"] = True
    gated = apply_quality_to_record(record)
    assert gated["quality_gate_level"] == "blocked"
    assert gated["ev_over"]["raw_verdict"] == "FIRE 2u"
    assert gated["ev_over"]["verdict"] == "PASS"
    assert gated["ev_over"]["adj_ev"] == 0.0


def test_one_soft_flag_caps_fire_two_to_fire_one():
    record = clean_fire_record()
    record["umpire"] = "Dexter Kelley"
    record["umpire_has_rating"] = False
    gated = apply_quality_to_record(record)
    assert gated["quality_gate_level"] == "capped"
    assert gated["ev_over"]["verdict"] == "FIRE 1u"
    assert gated["ev_over"]["raw_verdict"] == "FIRE 2u"


def test_two_soft_flags_cap_to_lean():
    record = clean_fire_record()
    record["lineup_used"] = False
    record["opening_odds_source"] = "first_seen"
    gated = apply_quality_to_record(record)
    assert gated["ev_over"]["verdict"] == "LEAN"


def test_clean_record_keeps_fire_two():
    record = clean_fire_record()
    gated = apply_quality_to_record(record)
    assert gated["quality_gate_level"] == "clean"
    assert gated["ev_over"]["verdict"] == "FIRE 2u"
```

Run:

```bash
python -m pytest tests/test_quality_gates.py -q
```

---

## Task 2: Feed Required Metadata Into Pitcher Records

**Files:**

- Modify: `pipeline/build_features.py`
- Modify: `pipeline/run_pipeline.py`
- Modify: `tests/test_build_features.py`
- Modify or create focused `tests/test_run_pipeline.py` cases if an existing file covers orchestration.

- [ ] **Step 1: Add record metadata needed by gates**

Add fields without changing lambda math:

```python
"recent_start_count": len(stats.get("recent_start_ips") or []),
"lineup_count": len(lineup) if lineup else 0,
"umpire_rating_games": umpire_rating_games_or_none,
```

Expected:

- Existing consumers continue working if they ignore these fields.
- Missing metadata defaults to safe conservative values in `quality_gates.py`.

- [ ] **Step 2: Apply gates after all metadata is attached**

In `run_pipeline.py`, call quality gates after:

- stats have resolved `team` / `opp_team`
- park factor has resolved
- umpire and `umpire_has_rating` are attached
- lineup status is known
- preview openings have been applied
- movement/book snapshots are attached

Target structure:

```python
from quality_gates import apply_quality_to_record

record = build_pitcher_record(...)
record["umpire"] = ...
record["umpire_has_rating"] = ...
record["park_factor_source"] = ...
record = apply_quality_to_record(record)
model_props.append(record)
```

Expected:

- Gates do not hide records from `today.json`.
- Gates only affect actionable verdicts and safe ranking/seeding behavior.

- [ ] **Step 3: Count pre-record skips**

Where a prop cannot become a pitcher record, count the reason:

- no trusted target book
- unresolved probable
- build exception
- missing stats

Expected output:

```json
"quality_gate_summary": {
  "pre_record_skips": {
    "no_target_book": 2,
    "unresolved_probable": 1,
    "build_exception": 0,
    "missing_stats": 1
  }
}
```

Minimal viable implementation:

- Reuse existing `connection_health` and `build_failures` where possible.
- Add explicit counts only where the reason is already knowable.
- Do not add placeholder PASS cards for skipped props in the first implementation.

- [ ] **Step 4: Build top-level quality summary**

Add a pure helper, either in `quality_gates.py` or `run_pipeline.py`:

```python
def summarize_quality_gates(records: list[dict], pre_record_skips: dict | None = None) -> dict:
    ...
```

Expected:

- Counts `clean`, `capped`, and `blocked`.
- Counts severe and soft flags separately.
- Includes `pre_record_skips`.
- Is stable when records have no quality fields yet.

- [ ] **Step 5: Test integration**

Add tests for:

- opener record is blocked and raw verdict preserved
- starter mismatch is blocked
- projected lineup caps a FIRE 2u to FIRE 1u
- projected lineup plus first-seen opening caps FIRE 2u to LEAN
- unrated confirmed umpire caps but does not display as TBA
- summary counts clean/capped/blocked correctly

Run:

```bash
python -m pytest tests/test_build_features.py tests/test_quality_gates.py -q
```

---

## Task 3: Persist Actionable and Raw Verdicts Correctly

**Files:**

- Modify: `pipeline/fetch_results.py`
- Modify: `tests/test_fetch_results.py`

- [ ] **Step 1: Extend SQLite schema safely**

Add nullable columns to the picks table:

```sql
raw_verdict TEXT,
actionable_verdict TEXT,
quality_gate_level TEXT,
input_quality_flags_json TEXT,
verdict_cap_reason TEXT,
data_maturity_json TEXT,
raw_adj_ev REAL
```

Expected:

- `init_db()` should create these columns for fresh DBs.
- Existing ephemeral DB rebuild flow remains safe.
- JSON export should include the new fields if present.

- [ ] **Step 2: Seed using actionable verdicts**

Change `seed_picks()` so it decides whether to seed a side from:

```python
side_verdict = ev.get("actionable_verdict") or ev.get("verdict")
```

Expected:

- Blocked records are not staked/tracked as FIRE or LEAN.
- Capped records are seeded under the capped verdict.
- Raw verdict remains available in exported history.

- [ ] **Step 3: Preserve locked pick behavior**

When updating unlocked rows:

- update actionable verdict and quality fields
- do not mutate locked rows after T-30
- retain raw verdict fields for analysis

Expected:

- This does not reintroduce the premature-lock bug.
- Locked snapshots remain decision-time truth.

- [ ] **Step 4: Test persistence**

Tests:

- blocked FIRE 2u is not inserted as FIRE 2u
- capped FIRE 2u inserts as FIRE 1u or LEAN as appropriate
- exported history includes `raw_verdict`, `actionable_verdict`, and quality metadata
- locked row keeps its quality metadata after later refresh

Run:

```bash
python -m pytest tests/test_fetch_results.py -q
```

---

## Task 4: Surface Quality Without Cluttering The Dashboard

**Files:**

- Modify: `dashboard/v2-data.js`
- Modify: `dashboard/v2-app.js`
- Modify: `dashboard/v2-data.test.mjs`

- [ ] **Step 1: Pass quality fields through the adapter**

In `dashboard/v2-data.js`, normalize:

```js
input_quality_flags
projection_safe
quality_gate_level
quality_gate_reasons
verdict_cap_reason
data_maturity
ev_over.raw_verdict
ev_over.actionable_verdict
ev_under.raw_verdict
ev_under.actionable_verdict
```

Expected:

- Missing fields default cleanly for old archives.
- Old archives do not break the date browser.

- [ ] **Step 2: Display a compact quality cue**

In `dashboard/v2-app.js`, add a small cue near the verdict/factors area:

- Clean: no prominent badge needed.
- Capped: show a restrained `Capped` cue with the reason in details.
- Blocked: show `Blocked` and actionable PASS.

Expected UX:

- The main card still tells Tyler what to bet or pass.
- The details explain why a raw FIRE was capped or blocked.
- No tutorial text or bulky explanatory panels.

- [ ] **Step 3: Show raw vs actionable only when different**

Display pattern:

```text
Actionable: FIRE 1u
Raw model: FIRE 2u
Reason: unrated umpire
```

Expected:

- Clean cards stay uncluttered.
- Capped/blocked cards are auditable.

- [ ] **Step 4: Test dashboard adapter behavior**

Add tests:

- old archive record with no quality fields normalizes to clean defaults
- capped record preserves raw/actionable verdicts
- blocked record surfaces projection unsafe

Run:

```bash
node dashboard/v2-data.test.mjs
node --check dashboard/v2-data.js
node --check dashboard/v2-app.js
```

---

## Task 5: Add Quality Gate Audit For The Weekly Review

**Files:**

- Create: `analytics/diagnostics/e5_quality_gate_audit.py`
- Create: `tests/test_e5_quality_gate_audit.py`
- Modify: `docs/superpowers/plans/2026-04-28-one-week-evaluation-cadence.md`

- [ ] **Step 1: Build the audit**

The audit should load `data/picks_history.json` and summarize only clean-window rows by default:

```bash
python analytics/diagnostics/e5_quality_gate_audit.py --since 2026-04-28
```

Report sections:

- raw verdict counts
- actionable verdict counts
- raw FIRE 2u capped/blocked counts
- flag frequency
- quality gate level by result
- FIRE 2u outcomes split by clean/capped/blocked hypothetical
- examples of capped/blocked picks

- [ ] **Step 2: Keep clean and transition regimes separated**

Default behavior:

- `--since 2026-04-28`
- no mixing transition-era rows into the primary read

Optional:

- `--all-history` for context only, clearly labeled.

- [ ] **Step 3: Test the audit**

Tests:

- raw vs actionable counts differ when a FIRE 2u is capped
- blocked rows are excluded from actionable staked counts
- default since date filters out transition rows
- report includes flag names and gate levels

Run:

```bash
python -m pytest tests/test_e5_quality_gate_audit.py -q
```

- [ ] **Step 4: Add the audit to the active cadence**

Update the weekly plan so daily review includes:

```bash
python analytics/diagnostics/e5_quality_gate_audit.py --since 2026-04-28 > analytics/output/e5_quality_gate_audit.md
```

Expected synthesis question:

```markdown
- Did gates/caps protect the bad outliers without hiding clean winners?
```

---

## Task 6: Add Scalable Thresholds For New Pitchers, Umpires, And Lineups

**Files:**

- Modify: `pipeline/fetch_stats.py` if needed
- Modify: `pipeline/fetch_umpires.py`
- Modify: `scripts/seed_umpire_career_rates.py`
- Modify: `pipeline/fetch_lineups.py` if needed
- Modify: `AGENTS.md`

- [ ] **Step 1: Pitcher graduation**

Expose enough metadata to graduate pitchers:

```json
{
  "recent_start_count": 5,
  "has_pitcher_k_profile": true,
  "pitcher_maturity": "mature"
}
```

Policy:

- No K profile: PASS.
- 1-2 starts, no reliable prior: max LEAN.
- 3-4 starts: max FIRE 1u.
- 5+ starts: FIRE 2u eligible.

- [ ] **Step 2: Umpire graduation**

Update the umpire seed output to preserve sample size.

Backward-compatible acceptable shapes:

```json
{
  "John Libka": 0.42
}
```

or:

```json
{
  "John Libka": {
    "delta": 0.42,
    "hp_games": 214
  }
}
```

Required reader behavior:

- Existing numeric entries still work.
- Object entries expose `delta` and `hp_games`.
- New umpires with fewer than 10 HP games stay neutral/thin.
- 10-49 HP games get shrunk adjustment and cannot contribute to FIRE 2u confidence.
- 50+ HP games use normal adjustment.

- [ ] **Step 3: Lineup graduation**

Expose:

```json
{
  "lineup_status": "projected | partial | confirmed",
  "lineup_count": 9
}
```

Policy:

- `projected`: soft cap.
- `partial`: soft cap.
- `confirmed`: no lineup cap.

- [ ] **Step 4: Market graduation**

Expose:

```json
{
  "market_maturity": "first_seen | preview_open | full_movement"
}
```

Policy:

- `first_seen`: soft cap.
- `preview_open`: eligible.
- `full_movement`: eligible and preferred for steam/CLV analysis.

Do not block all same-day picks just because full steam history is unavailable. That would be too strict for the current product.

- [ ] **Step 5: Document the graduation contract**

Add an `Input Quality Gates` section to `AGENTS.md` after verdict thresholds:

- gates are forward-only
- raw model output is preserved
- actionable verdict is the betting decision
- FIRE 2u requires clean major inputs
- new pitcher/umpire/lineup signals graduate through the maturity states above

---

## Task 7: Verification And Rollout

**Files:**

- All modified implementation and test files.

- [ ] **Step 1: Run focused Python tests**

```bash
python -m pytest tests/test_quality_gates.py -q
python -m pytest tests/test_build_features.py tests/test_fetch_results.py -q
python -m pytest tests/test_e5_quality_gate_audit.py -q
```

- [ ] **Step 2: Run dashboard tests and syntax checks**

```bash
node dashboard/v2-data.test.mjs
node --check dashboard/v2-data.js
node --check dashboard/v2-app.js
```

- [ ] **Step 3: Run full test suite**

```bash
python -m pytest tests/ -q
```

- [ ] **Step 4: Run whitespace check**

```bash
git diff --check
```

- [ ] **Step 5: Run one local dry data pass if environment allows**

If `RUNDOWN_API_KEY` is available:

```bash
python pipeline/run_pipeline.py 2026-04-29 --run-type preview
python pipeline/run_pipeline.py 2026-04-29
```

If the API key is not available locally, skip and rely on tests plus manual pipeline after push.

- [ ] **Step 6: Manual production validation after push**

After GitHub Actions completes:

- Open `dashboard/data/processed/today.json`.
- Confirm `quality_gate_summary` exists.
- Confirm capped/blocked records preserve raw verdicts.
- Confirm actionable FIRE 2u records have no severe flags and no meaningful soft flags.
- Confirm dashboard no longer displays capped/blocked records as full-strength FIRE 2u.

---

## Rollout Policy

Phase 1 should be conservative and forward-only.

- Do not backfill historical `today.json` archives with invented gate fields.
- Do not recompute old model output.
- Use old rows as historical context only.
- Start interpreting quality gates from the first production run after deployment.
- Use `e5_quality_gate_audit.py` to compare raw vs actionable decisions during the one-week review.

If the first day caps too many picks:

1. Check whether the issue is true data quality or an overly strict threshold.
2. Adjust soft-cap thresholds only after reviewing examples.
3. Do not relax severe gates unless the flag itself is wrong.

---

## Success Criteria

This plan is complete when:

- Each pitcher record has quality flags, maturity states, and projection safety.
- FIRE 2u cannot survive severe flags or meaningful soft-cap flags.
- Raw model verdict and raw adjusted EV remain available for analysis.
- Pick history stores actionable and raw verdicts.
- Dashboard displays capped/blocked picks without cluttering clean picks.
- Weekly review includes a quality gate audit.
- New pitchers, umpires, and lineups have clear graduation thresholds.
- Full Python and dashboard tests pass.
