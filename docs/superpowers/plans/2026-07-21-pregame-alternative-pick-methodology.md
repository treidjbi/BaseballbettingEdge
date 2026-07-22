# Pregame Alternative Pick Methodology Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a same-day, pregame Alt Picks comparison tab backed by a versioned two-lane selector and immutable lock-linked state, without changing official picks or any production behavior while the feature remains default-off.

**Architecture:** A pure Python selector derives runtime-safe features from the canonical `today` artifact and approved TheRundown/PropLine market evidence. An optional, five-second post-lock sidecar records provisional and frozen rows in a new RLS-protected Supabase table. A sanitized Netlify function serves only validated current-slate rows to a separate browser adapter, and the v2 middle tab renders those rows without merging them into official pick or accepted-bet state.

**Tech Stack:** Python 3.11, pytest, Postgres/Supabase migrations and PostgREST, Netlify Functions on Node, vanilla browser JavaScript, React 18 UMD, Node's built-in test runner, and the existing Babel JSX build.

**Implementation status (2026-07-21):** Tasks 1-5 are implemented and
review-clean on `codex/pregame-alt-picks`. The frozen manifest fingerprint is
`f8f7ccf652b8eda4860d07798bc4673920b0b9d727552bc7e2e6547d478b4579`.
The additive migration is present but unapplied; the live-layer mode defaults
to `off`; record activation, off-mode deployment, and Netlify deployment are
separate closed gates. No prospective production rows/sample are claimed.

## Global Constraints

- Keep official artifacts, picks, verdicts, model math, thresholds, staking, grading, notifications, operational locks, provider order, accepted bets, and dashboard source-of-truth unchanged.
- Keep `ALTERNATIVE_PICK_SELECTION_MODE=off` as the code default. This implementation does not apply the migration, change Render variables, activate record mode, or deploy Netlify/Render.
- Use only canonical TheRundown official state plus approved PropLine fallback/live-movement evidence. Exclude BoltOdds and unknown providers from every prospective vote.
- Never read `result`, win/loss, PnL, closing line/price, final CLV, or postgame opportunity in the runtime selector.
- Missing, stale, mismatched, or immature inputs produce `pending`; they never become `disagree` or a qualifying vote by default.
- Keep the two lanes disjoint: `consensus_core = no_drag AND family_count >= 2`; `reentry_expansion = reentry_support AND NOT no_drag`.
- Invoke the optional recorder only after all existing notification, live-state, operational-lock, timing, and shadow-market-state work completes successfully. Catch every sidecar failure, stop that sidecar cycle after the first failure, and preserve the existing process result.
- Bound the sidecar to five seconds total with no retry and at most one provisional plus one frozen row per eligible pick/day.
- Direct anonymous/authenticated table access stays denied. The browser reads only the explicit Netlify response allow-list.
- The Alt Picks UI contains no bet action, Log Bet path, stake/units, PnL/history, notification control, or FIRE-red promotion styling.

---

## Task 1: Freeze the pure selector and runtime feature contract

**Files:**

- Create: `market_infra/alternative_pick_selector.py`
- Create: `market_infra/alternative_pick_selector_manifest_v1.json`
- Create: `tests/test_alternative_pick_selector.py`
- Modify: `analytics/diagnostics/pitcher_k_outcome_dataset.py`
- Modify: `analytics/diagnostics/no_drag_composite_canary_audit.py`
- Modify: `analytics/diagnostics/gate_f_fire_reentry_lab.py`
- Modify: `analytics/diagnostics/gate_f_preclose_clv_proxy_lab.py`
- Modify: `tests/test_no_drag_composite_canary_audit.py`
- Modify: `tests/test_gate_f_fire_reentry_lab.py`
- Modify: `tests/test_gate_f_preclose_clv_proxy_lab.py`

- [x] **Step 1: Write failing manifest and evaluator tests**

Add golden tests for:

- canonical sorted/compact JSON fingerprinting with explicit nulls and decimal thresholds stored as strings;
- display-verdict and source-FIRE precedence;
- the legacy truthy-or adjusted-EV precedence across `locked_adj_ev`, `adj_ev`, and `ev`;
- runtime derivation of line bucket, price sign, timing, market relationship, no-vig gap, opportunity/leash, archetype, and large-edge skepticism;
- eligible-universe rejection for wrong Phoenix slate date, untracked/PASS rows, started games, alternate/opposite-side searches, line or artifact-hash mismatch, and unsupported providers;
- explicit distinction between an absent anchor label and missing/malformed anchor metadata;
- Base, Anchor, Preclose, and Re-entry `agree|disagree|pending` states;
- one vote per family even when multiple labels in that family match;
- `pending` blocking qualification and unproved no-drag blocking expansion;
- the two lane predicates never both being true;
- forbidden result/CLV fields having no effect on prospective output; and
- the official-close parity anchors `+32.603u`, `+5.982u`, and `+38.585u` remaining research-only anchors while the prospective counter starts at zero.

Use a representative fixture shaped like:

```python
evaluation = evaluate_alternative_pick(
    pitcher={
        "pitcher": "Test Pitcher",
        "team": "ARI",
        "opp_team": "LAD",
        "game_time": "2026-07-21T23:10:00Z",
        "k_line": 5.5,
        "best_over_odds": -115,
        "best_under_odds": -105,
        "avg_ip": 5.8,
        "recent_start_count": 5,
        "season_k9": 9.4,
        "recent_k9": 9.7,
        "career_k9": 9.1,
    },
    pick={
        "side": "over",
        "display_verdict": "FIRE 1u",
        "edge": 0.035,
        "adj_ev": 0.09,
        "quality_gate_level": "clean",
        "market_anchor_selector": {"labels": ["market_anchor_core"]},
    },
    is_tracked=True,
    market_evidence={
        "provider": "therundown_propline",
        "toward_pick_count": 3,
        "away_from_pick_count": 0,
        "book_count": 3,
        "broad_confirmation": True,
        "best_is_off_market": False,
        "reversal_book_count": 0,
        "volatile_book_count": 0,
        "freshness_status": "fresh",
        "observation_ids": ["snap-a", "snap-b"],
        "first_observed_at": "2026-07-21T20:00:00Z",
        "last_observed_at": "2026-07-21T20:10:00Z",
    },
    slate_date="2026-07-21",
    source_artifact_path="dashboard/data/processed/today.json",
    source_payload_sha256="a" * 64,
    source_artifact_byte_sha256="b" * 64,
    observed_at="2026-07-21T20:10:00Z",
)
```

- [x] **Step 2: Run the focused tests and observe RED**

Run:

```powershell
python -m pytest tests/test_alternative_pick_selector.py tests/test_no_drag_composite_canary_audit.py tests/test_gate_f_fire_reentry_lab.py tests/test_gate_f_preclose_clv_proxy_lab.py -q
```

Expected: failure because the new selector module and manifest do not exist.

- [x] **Step 3: Implement the pure module and frozen manifest**

Expose these stable interfaces (the implementation supplies the concrete bodies):

```python
BUNDLE_ID = "pregame_alternative_pick_methodology_v1"
CONSENSUS_SELECTOR_ID = "no_drag_distinct_family_consensus_core_v1"
EXPANSION_SELECTOR_ID = "moderate_edge_quality_reentry_expansion_v1"

@dataclass(frozen=True)
class FamilyVote:
    state: Literal["agree", "disagree", "pending"]
    reason_codes: tuple[str, ...]

@dataclass(frozen=True)
class AlternativePickEvaluation:
    eligible: bool
    eligibility_reason_codes: tuple[str, ...]
    selector_fingerprint: str
    family_states: dict[str, FamilyVote]
    family_count: int
    no_drag: bool | None
    lane: Literal["consensus_core", "reentry_expansion"] | None
    selection_status: Literal["selected", "not_selected", "pending"]
    reason_codes: tuple[str, ...]
    normalized_inputs: dict[str, Any]

selector_fingerprint() -> str
derive_runtime_features(*, pitcher, pick, market_evidence, observed_at) -> dict[str, Any]
evaluate_alternative_pick(*, pitcher, pick, market_evidence, slate_date,
                          is_tracked, source_artifact_path,
                          source_payload_sha256, source_artifact_byte_sha256,
                          observed_at) -> AlternativePickEvaluation
```

The manifest must freeze IDs, field precedence, null behavior, enum normalization, thresholds, provider allow-list, family predicates, formulas, and timing/freeze rules. Load it with `json.loads`, serialize with `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, and hash UTF-8 bytes with SHA-256.

Move the reusable runtime-safe feature and predicate implementations behind public functions in this module. Keep compatibility wrappers in the diagnostics where useful, but make them call the shared functions. Historical diagnostics may still filter on result/tracked rows and calculate ledgers outside the shared prospective predicates.

Before calling the preclose scorer, explicitly require two distinct current-candidate observation IDs plus non-null reversal and volatility counts. Preserve the existing `strong_preclose_clv_proxy` score threshold only after completeness passes.

- [x] **Step 4: Prove green and parity**

Run the focused command from Step 2 plus:

```powershell
python analytics/diagnostics/no_drag_composite_canary_audit.py
python -m pytest tests/test_build_pitcher_k_outcome_dataset.py -q
```

Expected: all tests pass; the machine research ledger remains `+38.585u` combined and the prospective fixture reports zero graded picks.

- [x] **Step 5: Commit Task 1**

```powershell
git add market_infra/alternative_pick_selector.py market_infra/alternative_pick_selector_manifest_v1.json analytics/diagnostics/pitcher_k_outcome_dataset.py analytics/diagnostics/no_drag_composite_canary_audit.py analytics/diagnostics/gate_f_fire_reentry_lab.py analytics/diagnostics/gate_f_preclose_clv_proxy_lab.py tests/test_alternative_pick_selector.py tests/test_no_drag_composite_canary_audit.py tests/test_gate_f_fire_reentry_lab.py tests/test_gate_f_preclose_clv_proxy_lab.py
git commit -m "feat: freeze alternative pick selector contract"
```

---

## Task 2: Add bounded state shaping and the unapplied Supabase migration

**Files:**

- Create: `market_infra/alternative_pick_selection_state.py`
- Create: `tests/test_alternative_pick_selection_state.py`
- Create with Supabase CLI: `supabase/migrations/*_alternative_pick_selection_state.sql` (the CLI assigns the timestamp in Task 2)
- Create: `tests/test_alternative_pick_selection_schema.py`

- [x] **Step 1: Write failing pure state and schema tests**

Cover:

- deterministic game/candidate identity from slate, teams, game time, pitcher, side, model line, and supported-provider posture;
- provisional evidence windows starting only when that exact candidate first becomes current;
- identity changes resetting old snapshot membership;
- two distinct supported-provider snapshots no later than the checkpoint;
- stale/mismatched/unknown-provider evidence remaining pending;
- `due_now` and `missed_lock` pregame capture with actual timing fields;
- exact lock validation on dedupe key, slate, teams/game, pitcher, side, line, game time, and source SHA;
- a frozen row being allowed only from the lock written/first observed in the current evaluator cycle, with a missed-freeze reason rather than later reconstruction;
- no post-start freeze and no same-SHA or later-artifact reconstruction after a missed first valid lock cycle;
- provisional upserts stopping immediately when a valid frozen row exists or the game has started;
- at most one provisional and one frozen row for the unique candidate/day key;
- frozen insert-ignore behavior and migration-level update/delete immutability;
- RLS enabled, explicit anon/authenticated revoke, service-role grants, and the expected unique constraint.

- [x] **Step 2: Run the tests and observe RED**

```powershell
python -m pytest tests/test_alternative_pick_selection_state.py tests/test_alternative_pick_selection_schema.py -q
```

Expected: failure because the state module and migration are absent.

- [x] **Step 3: Implement pure state shaping**

Expose:

```python
UNIQUE_COLUMNS = (
    "slate_date", "game_identity", "normalized_pitcher",
    "side", "bundle_id", "checkpoint",
)

candidate_identity(*, slate_date, pitcher, side, model_k_line,
                   team, opp_team, game_time, provider_posture) -> str
associate_candidate_observations(*, candidate, snapshot_rows,
                                 first_current_at, observed_at) -> dict[str, Any]
build_provisional_row(*, candidate, evaluation, evidence_window,
                      artifact, observed_at) -> dict[str, Any]
build_frozen_row(*, provisional_row, lock_row, observed_at) -> dict[str, Any] | None
lock_matches_candidate(lock_row, candidate, artifact_sha256) -> bool
```

Store compact observation IDs/count/first/last timestamps and reason codes. Frozen rows copy the evaluated selection/provenance once and use the operational lock's `locked_at`, `should_lock_at`, `minutes_until_start`, `status_at_capture`, dedupe key, and byte-level lock source SHA. Once a matching frozen row exists, or once `observed_at >= game_time`, row shaping returns no provisional update.

Use two named hash domains without changing existing lock behavior:

- `source_artifact_sha256` is `market_infra.published_artifacts.canonical_payload_sha256(payload)` and must equal the canonical `published_pipeline_artifacts.payload_sha256` for provisional display;
- `lock_artifact_sha256` is the existing live-layer SHA-256 of the exact fetched artifact bytes and must equal `operational_pick_locks.source_artifact_sha256` for a frozen link.

Add an end-to-end golden test that starts from one JSON payload, proves key-order-insensitive canonical payload hashing, preserves the exact-byte lock hash, and carries both unchanged through candidate → provisional → lock → frozen row validation.

- [x] **Step 4: Create the migration through the linked CLI**

Run from the repo root:

```powershell
npx supabase migration new alternative_pick_selection_state
```

Edit only the file printed by that command. Define `public.alternative_pick_selection_state` with identity, display-safe official pick fields, lane/selection status, `family_states jsonb`, `reason_codes jsonb`, artifact provenance, evidence-window fields, and nullable lock/freeze fields.

Enforce:

```sql
unique (slate_date, game_identity, normalized_pitcher, side, bundle_id, checkpoint)
```

Add checks for the two checkpoints, two sides, allowed lanes/statuses, 64-character hashes, non-negative observation count, and all-or-none frozen provenance. Add a `before update or delete` trigger that raises when `old.checkpoint = 'frozen_pregame'`. Add a `before insert` frozen-link trigger that requires the exact `operational_pick_locks` row and `new.frozen_at < new.game_time`.

Enable RLS, revoke all privileges from `anon` and `authenticated`, and explicitly grant only `select, insert, update` to `service_role`. Do not create an anonymous policy and do not grant delete.

Do **not** run `supabase db push`, `migration up`, or any production SQL command.

- [x] **Step 5: Prove green**

```powershell
python -m pytest tests/test_alternative_pick_selection_state.py tests/test_alternative_pick_selection_schema.py tests/test_operational_pick_locks_schema.py -q
```

Expected: all tests pass and `git diff -- supabase/migrations` shows one additive, unapplied migration only.

- [x] **Step 6: Commit Task 2**

```powershell
git add market_infra/alternative_pick_selection_state.py tests/test_alternative_pick_selection_state.py tests/test_alternative_pick_selection_schema.py supabase/migrations
git commit -m "feat: add immutable alternative pick state"
```

---

## Task 3: Integrate the default-off post-lock sidecar

**Files:**

- Modify: `market_infra/supabase_writer.py`
- Modify: `scripts/build_live_events_to_supabase.py`
- Modify: `tests/test_market_infra_supabase_writer.py`
- Modify: `tests/test_live_layer_worker.py`

- [x] **Step 1: Write failing timeout, ordering, and isolation tests**

Add tests proving:

- mode is `off` for missing/invalid values and only `record` enables work;
- mode-off performs no alternative reads/writes;
- notifications, market/display state, reminders, live pick state, operational locks, shadow timing, and `_build_shadow_market_state` are complete before alternative work starts;
- any existing write/build failure summary skips all alternative reads and writes for the cycle;
- record mode uses the already loaded artifact, snapshots/evidence, and approved providers, with only narrow state/lock reads;
- provisional rows use merge-upsert; frozen rows use conflict-ignore on the six-column unique key;
- a timeout or first read/evaluation/write exception stops alternative work for that cycle, returns a bounded sanitized summary, and leaves the overall run successful;
- the writer supports a caller-supplied timeout and single-attempt select without changing existing defaults; and
- alternative writes never exceed two rows per eligible candidate/day.

- [x] **Step 2: Run focused tests and observe RED**

```powershell
python -m pytest tests/test_market_infra_supabase_writer.py tests/test_live_layer_worker.py -q
```

Expected: the new mode/order/timeout assertions fail.

- [x] **Step 3: Add backward-compatible request budgets**

Extend `select_rows`, `upsert_rows`, and `insert_ignore_rows` with keyword-only timeout controls whose defaults remain the existing 20 seconds. Let alternative reads pass `attempts=1`; do not alter retry behavior for current callers.

```python
select_rows(self, table, params, *, timeout_seconds=20, attempts=3)
upsert_rows(self, table, rows, on_conflict, *, timeout_seconds=20)
insert_ignore_rows(self, table, rows, on_conflict, *, timeout_seconds=20)
```

- [x] **Step 4: Add the optional recorder after lock and timing work**

Add:

```python
def _alternative_pick_selection_mode() -> str:
    return "record" if os.environ.get(
        "ALTERNATIVE_PICK_SELECTION_MODE", "off"
    ).strip().lower() == "record" else "off"

def _write_alternative_pick_selection_state(
    *, writer, slate_date, payload, snapshot_rows, market_pick_evidence_rows,
    observed_at, artifact_source, source_payload_sha256,
    source_artifact_byte_sha256, operational_pick_locks, market_line_build,
    budget_seconds: float = 5.0,
) -> dict[str, Any]:
    """Record isolated alternative state or return a bounded skipped summary."""
```

Call it only after `_write_operational_pick_locks`, `_write_shadow_pipeline_timing`, and `_build_shadow_market_state` return. If any prior existing responsibility returned a failure summary, return `{"skipped": True, "reason": "prerequisite_failed"}` before any alternative read/write. Use `time.monotonic()` and pass only the remaining positive budget to each no-retry request. On the first failure or exhausted budget, log a truncated non-secret warning, return `{"skipped": True, "reason": "failed"|"timeout"}`, and make no further alternative call that cycle.

Compute `source_payload_sha256 = canonical_payload_sha256(payload)` without altering the existing byte hash passed to notifications or locks. Read only current-slate provisional/frozen state and exact candidate lock rows. A freeze is eligible only when the current lock operation returned the row or the persisted lock's `locked_at` exactly matches this cycle's `observed_at`; an older lock without a frozen row becomes `missed_freeze` and is never reconstructed even if either hash did not change. Skip provisional mutation after freeze or game start. Do not make a provider/API call. Return an `alternative_pick_selection` summary in `run()` output without changing existing return keys.

- [x] **Step 5: Prove green and off-mode compatibility**

```powershell
python -m pytest tests/test_market_infra_supabase_writer.py tests/test_live_layer_worker.py tests/test_notification_coordinator.py tests/test_operational_pick_locks.py -q
```

Expected: all tests pass; existing call ordering and results are unchanged when the mode is off.

- [x] **Step 6: Commit Task 3**

```powershell
git add market_infra/supabase_writer.py scripts/build_live_events_to_supabase.py tests/test_market_infra_supabase_writer.py tests/test_live_layer_worker.py
git commit -m "feat: record alternative picks after live locks"
```

---

## Task 4: Add the sanitized current-slate Netlify endpoint

**Files:**

- Create: `netlify/functions/alternative-picks.mjs`
- Create: `tests/test_alternative_picks_function.mjs`

- [x] **Step 1: Write failing endpoint contract tests**

Cover OPTIONS, missing configuration, Phoenix current-date scope, service-role-only reads, explicit selected fields, stale provisional suppression, exact frozen lock-link validation, frozen preservation after artifact advance, malformed rows, and sanitized failure bodies with no key/raw metadata leakage.

The response shape is:

```json
{
  "slate_date": "2026-07-21",
  "generated_at": "2026-07-21T20:10:00Z",
  "status": "ready",
  "counts": {"provisional": 1, "frozen": 1, "selected": 1, "pending": 1},
  "rows": [],
  "error": null
}
```

- [x] **Step 2: Run and observe RED**

```powershell
node --test tests/test_alternative_picks_function.mjs
```

Expected: module-not-found failure.

- [x] **Step 3: Implement the fail-open endpoint**

Model headers/config handling on `live-market-display.mjs`, but always compute the Phoenix slate date server-side. A mismatched `date` query returns an empty current-slate-only response rather than exposing history.

Read fixed columns from:

1. `published_pipeline_artifacts` where the unique canonical key is exactly `artifact_key=eq.today`, selecting `artifact_key`, `payload_sha256`, slate date, generated time, source, and the minimal payload fields needed to verify an approved TheRundown or TheRundown+PropLine production posture; never select the latest arbitrary row by artifact type;
2. `alternative_pick_selection_state` for the current slate and bundle; and
3. the exact `operational_pick_locks` dedupe keys needed for frozen validation.

Keep a provisional row only when its canonical `source_artifact_sha256` equals the exact-key `today.payload_sha256`. Keep a frozen row only when lock key, slate, teams/game, pitcher, side, line, game time, status, and `lock_artifact_sha256` all match the operational lock. Set `artifact_advanced_after_freeze=true` when a valid frozen row's canonical payload SHA differs from the current exact-key artifact SHA. Add a recorder → lock → endpoint golden test for both hash domains.

Construct every returned row from this exact allow-list: `slate_date`, `pitcher`, `team`, `opp_team`, `game_time`, `side`, `model_k_line`, `official_odds`, `official_book`, `official_verdict`, `bundle_id`, `selector_id`, `lane`, `selection_status`, `family_states`, `family_count`, `checkpoint`, `reason_codes`, `source_artifact_generated_at`, `evidence_observation_count`, `evidence_first_observed_at`, `evidence_last_observed_at`, `evidence_freshness_status`, `frozen_at`, `should_lock_at`, `minutes_until_start`, `lock_status`, and `artifact_advanced_after_freeze`. Never return database IDs, game/candidate identities, hashes, raw metadata, observation IDs/payloads, internal URLs, error bodies, or credentials. Use `Cache-Control: no-store`. Missing config/read failure returns HTTP 200 with `status="unavailable"`, zero rows, and a short stable error code.

- [x] **Step 4: Prove green**

```powershell
node --test tests/test_alternative_picks_function.mjs tests/test_live_market_display_function.mjs
```

Expected: all tests pass.

- [x] **Step 5: Commit Task 4**

```powershell
git add netlify/functions/alternative-picks.mjs tests/test_alternative_picks_function.mjs
git commit -m "feat: expose sanitized alternative picks"
```

---

## Task 5: Replace the middle v2 tab with isolated Alt Picks UI

**Files:**

- Create: `dashboard/v2-alt-picks.js`
- Create: `dashboard/v2-alt-picks.test.mjs`
- Modify: `dashboard/v2-app.jsx`
- Regenerate: `dashboard/v2-app.js`
- Modify: `dashboard/v2-app.test.mjs`
- Modify: `dashboard/v2.html`
- Create: `tests/test_dashboard_alt_picks_ui.py`
- Modify: `tests/test_dashboard_accepted_bet_log.py`

- [x] **Step 1: Write failing adapter and UI contract tests**

Adapter tests must prove:

- it calls only `/.netlify/functions/alternative-picks` for the Phoenix current slate;
- it normalizes only allowed lanes/family states/checkpoints and rejects wrong-slate/malformed rows;
- it formats `Provisional`, `Frozen T-28`, and `Frozen T-21 (late)` from actual capture data;
- failure returns local `unavailable` state without mutating `V2_DATA`, `V2_PERF`, `V2_APP_STATE`, pitcher objects, or accepted-bet state.

UI tests must prove:

- navigation order is Picks / Alt Picks / Results;
- legacy `?tab=history` maps to `alt`, while canonical links use `?tab=alt`;
- Consensus Core renders before Re-entry Expansion;
- selected, pending, healthy-empty, stale/waiting, and unavailable copy matches the spec;
- family chips preserve `agree`, `disagree`, and `pending` semantics; and
- the Alt Picks component source contains no `Log Bet`, `Save Bet`, units/stakes, historical PnL, or notification action.

- [x] **Step 2: Run and observe RED**

```powershell
node --test dashboard/v2-alt-picks.test.mjs dashboard/v2-app.test.mjs
python -m pytest tests/test_dashboard_alt_picks_ui.py tests/test_dashboard_accepted_bet_log.py -q
```

Expected: failures because the adapter/tab do not exist and the middle tab is still History.

- [x] **Step 3: Implement the isolated browser adapter**

Expose:

```javascript
window.V2AltPicks = {
  fetchCurrentSlate,
  normalizeResponse,
  formatFreezeLabel,
};
```

This adapter owns its fetch/error state. Do not add the request to `window.__v2DataPromise` and do not modify `dashboard/v2-data.js`.

- [x] **Step 4: Implement the Alt Picks tab**

Remove the unused History component/archive helpers and replace them with `AltPicksTab`, `AltPickCard`, and a read-only `AltPickSheet`. Do not reuse `PickSheet`, because it owns wager controls.

Show the compact header/counts, Consensus Core group, Re-entry Expansion group, collapsed not-selected/pending summary, official pick comparison, four evidence chips, actual checkpoint label, and freshness/provenance. Use scoped `.v2-alt-*` blue/teal styles. Keep identity, official pick, lane, and freeze state at the top of a 390px card; let evidence chips wrap.

Load `v2-alt-picks.js` between `v2-data.js` and `v2-app.js`, and update both cache-bust tokens. Preserve Picks and Results render branches.

- [x] **Step 5: Regenerate the checked-in build**

From `dashboard/`:

```powershell
npx --yes -p @babel/core@7 -p @babel/cli@7 -p @babel/preset-react@7 babel v2-app.jsx --presets=@babel/preset-react -o v2-app.js
```

- [x] **Step 6: Prove green and run visual QA**

```powershell
node --test dashboard/v2-alt-picks.test.mjs dashboard/v2-app.test.mjs dashboard/v2-data.test.mjs dashboard/v2-movement-helpers.test.mjs
node --check dashboard/v2-app.js
python -m pytest tests/test_dashboard_alt_picks_ui.py tests/test_dashboard_accepted_bet_log.py -q
```

Serve `dashboard/` locally with intercepted endpoint fixtures. Inspect selected, pending, empty, stale, and unavailable states at 1280x900 and 390x844. At 390px verify no horizontal overflow, the primary identity/pick/lane/freeze content appears before supporting detail, chips wrap, and the read-only sheet remains inside the viewport.

- [x] **Step 7: Commit Task 5**

```powershell
git add dashboard/v2-alt-picks.js dashboard/v2-alt-picks.test.mjs dashboard/v2-app.jsx dashboard/v2-app.js dashboard/v2-app.test.mjs dashboard/v2.html tests/test_dashboard_alt_picks_ui.py tests/test_dashboard_accepted_bet_log.py
git commit -m "feat: add same-day alternative picks tab"
```

---

## Task 6: Update handoff docs and verify the complete default-off branch

**Files:**

- Modify: `docs/superpowers/specs/2026-07-21-pregame-alternative-pick-methodology-design.md`
- Modify: `docs/superpowers/plans/2026-07-21-pregame-alternative-pick-methodology.md`
- Modify: `docs/current-state.md`

The ignored local execution ledger `.superpowers/sdd/progress.md` is updated after every reviewed task but is not committed.

- [x] **Step 1: Document the implemented-but-not-activated posture**

Record the final manifest fingerprint, migration filename, tested failure boundary, UI behavior, and exact verification commands. Mark migration apply, Render mode activation, and deployments as still closed separate gates. Do not claim a prospective sample before record mode is separately approved and activated.

- [x] **Step 2: Run complete verification from a clean working tree candidate**

```powershell
python -m pytest tests/ -q
node --test dashboard/*.test.mjs tests/*.mjs
node --check dashboard/v2-app.js
git diff --check
git status --short
```

Expected: all suites pass; `git diff --check` is clean; only intentional documentation changes remain before the final commit.

- [x] **Step 3: Verify prohibited production changes are absent**

```powershell
git diff origin/main...HEAD -- render.yaml netlify.toml .github/workflows data/params.json pipeline dashboard/data data/picks_history.json
git grep -n "ALTERNATIVE_PICK_SELECTION_MODE" -- . ':!docs'
```

Expected: no production env/provider/model/artifact mutation; the mode helper defaults to `off`; Netlify configuration and workflows are unchanged; no generated dashboard data or model parameters are committed.

- [x] **Step 4: Commit the handoff**

```powershell
git add docs/superpowers/specs/2026-07-21-pregame-alternative-pick-methodology-design.md docs/superpowers/plans/2026-07-21-pregame-alternative-pick-methodology.md docs/current-state.md
git commit -m "docs: hand off default-off alternative picks"
```

- [ ] **Step 5: Request whole-branch review**

Generate the review package from the plan base through `HEAD`. Require both specification-compliance and code-quality review, with special attention to forbidden hindsight inputs, lock/artifact identity, RLS/grants, the five-second failure boundary, default-off behavior, and UI isolation. Fix every Critical or Important finding and rerun the relevant focused plus full verification before presenting branch-integration options.
