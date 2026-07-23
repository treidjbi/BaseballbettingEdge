# Alt Picks V2 Final Contract Repairs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Repair the remaining Alt Picks V2 proof, evidence-read, ambiguity, endpoint, and browser contracts without changing any official betting behavior or V1 response behavior.

**Architecture:** Keep the repair inside the existing comparison-only V2 path. A bounded keyset-paged Supabase read will return rows plus explicit completeness metadata; V2 Preclose consumes that metadata and stays pending whenever the provider-run set, snapshot suffix, or requested time window is incomplete. The selector and proof bind raw workload/leash inputs and independently recompute pending votes, while the V2 endpoint/browser reject PASS, coalesce exact-lock frozen rows over provisional rows, and omit unbound top-level reasons.

**Tech Stack:** Python 3.11, pytest, vanilla JavaScript/ES modules, Node test runner, Netlify Functions, Supabase PostgREST, Render cron.

**Status:** Complete and deployed on 2026-07-23; prospective soak remains, with every official promotion gate closed.

## Global Constraints

- Alt Picks V2 remains comparison-only; do not change official picks, model math, staking, provider order, notifications, locks, accepted bets, artifacts, history, or source of truth.
- Do not add a schema migration, worker, cadence, provider-cost change, backfill, reconstruction, or deletion.
- Preserve TheRundown as official and PropLine as fallback/live-movement sidecar; BoltOdds remains retired.
- Preserve V1 and unversioned endpoint behavior byte-for-byte except for nondeterministic response ordering that existing tests already ignore.
- Every production-code change in Task 1 requires its named regression test to be observed failing before the implementation edit.
- Frozen V2 rows are immutable and must never be rewritten or reconstructed. Provisional V2 rows retain the controlling design's existing merge-upsert behavior until freeze or game start; incompatible old proofs stay suppressed until a normal prospective cycle re-evaluates that mutable provisional checkpoint.
- Tyler's existing approval in this task authorizes the reviewed merge and Task 3 deployments. Do not roll back the current rollout; if verification fails, stop, diagnose, and fix forward inside the isolated V2 path.

---

## File map

**V2 selector and proof**

- Modify: `market_infra/alternative_pick_selector_v2.py` — validate raw workload inputs and make only their dependent votes pending.
- Modify: `market_infra/alternative_pick_evaluation_proof_v2.py` — bind raw workload values/status and recompute the same pending semantics.
- Test: `tests/test_alternative_pick_selector_v2.py`
- Test: `tests/test_alternative_pick_evaluation_proof_v2.py`

**Exact evidence and live-layer read contract**

- Modify: `scripts/build_live_events_to_supabase.py` — deterministic keyset paging, explicit read completeness, parent-run/provider verification, and V2-only dispatch metadata.
- Modify: `market_infra/alternative_pick_recording_v2.py` — pass read completeness to exact Preclose.
- Modify: `market_infra/alternative_pick_preclose_v2.py` — fail Preclose to pending for incomplete reads/windows and same-checkpoint alternate-line ambiguity.
- Test: `tests/test_live_layer_worker.py`
- Test: `tests/test_alternative_pick_live_layer_v2.py`
- Test: `tests/test_alternative_pick_preclose_v2.py`

**V2 public contract**

- Modify: `netlify/functions/alternative-picks.mjs` — V2-only PASS rejection, exact-lock frozen preference, and omission of raw top-level reasons.
- Modify: `dashboard/v2-alt-picks.js` — independently reject PASS and stop accepting/exposing raw top-level reasons.
- Test: `tests/test_alternative_picks_function.mjs`
- Test: `dashboard/v2-alt-picks.test.mjs`

**Handoff**

- Modify after deployment evidence: `docs/superpowers/specs/2026-07-22-alt-picks-dependency-aware-v2-design.md`
- Modify after deployment evidence: `docs/superpowers/plans/2026-07-22-alt-picks-dependency-aware-v2.md`
- Modify after deployment evidence: `docs/current-state.md`

---

### Task 1: Implement the integrated V2 contract-repair wave

**Files:**

- Modify: `market_infra/alternative_pick_selector_v2.py`
- Modify: `market_infra/alternative_pick_evaluation_proof_v2.py`
- Modify: `market_infra/alternative_pick_preclose_v2.py`
- Modify: `market_infra/alternative_pick_recording_v2.py`
- Modify: `scripts/build_live_events_to_supabase.py`
- Modify: `netlify/functions/alternative-picks.mjs`
- Modify: `dashboard/v2-alt-picks.js`
- Test: `tests/test_alternative_pick_selector_v2.py`
- Test: `tests/test_alternative_pick_evaluation_proof_v2.py`
- Test: `tests/test_alternative_pick_preclose_v2.py`
- Test: `tests/test_alternative_pick_live_layer_v2.py`
- Test: `tests/test_live_layer_worker.py`
- Test: `tests/test_alternative_picks_function.mjs`
- Test: `dashboard/v2-alt-picks.test.mjs`

**Interfaces:**

- `SnapshotReadResult(rows: list[dict[str, Any]], v2_rows: list[dict[str, Any]], complete: bool, window_started_at: str, reason_codes: tuple[str, ...])` is produced by `_fetch_live_market_snapshot_rows`. `rows` preserves the legacy newest-suffix contract; `v2_rows` contains only parent-run/provider-verified rows.
- `_fetch_recent_provider_run_rows(...) -> tuple[list[dict[str, Any]], bool]` performs one newest-first read of `101` rows, returns the first `100` downstream, and uses only the 101st row as the explicit overflow sentinel.
- `record_alternative_pick_selection_v2(..., snapshot_read_complete: bool, snapshot_window_started_at: str, snapshot_read_reason_codes: Sequence[str], ...)` passes the read contract without changing V1 arguments.
- `build_exact_preclose_evidence_v2(..., snapshot_read_complete: bool, snapshot_window_started_at: str, snapshot_read_reason_codes: Sequence[str], ...)` returns pending evidence when the read or candidate window is incomplete.
- V2 proof `normalized_inputs` adds `is_opener`, `starter_mismatch`, `last_pitch_count`, `days_since_last_start`, and `workload_input_status`. The four raw values are canonical `bool | None`, `bool | None`, `int | None`, and `int | None`; status is exactly `complete`, `missing`, or `malformed`.
- V2 endpoint coalescing keys on the persisted `candidate_identity`; among already validated and visible rows it chooses a valid `frozen_pregame` row over a provisional row. V1 skips this coalescer.

- [x] **Step 1: Add the workload/leash red tests**

Add parameterized selector cases proving that missing and malformed values for each of `is_opener`, `starter_mismatch`, `last_pitch_count`, and `days_since_last_start` cannot produce an affirmative Base or Re-entry vote. Assert the affected vote is `pending`, explicit `False` and `0` remain valid inputs, and the unaffected strict Anchor branch can still short-circuit independently.

Add proof cases asserting the five new normalized fields are required, their exact scalar types are enforced, `workload_input_status != "complete"` recomputes Base/Re-entry as pending, and changing a bound raw value without changing the persisted family decision invalidates the proof.

Run:

```powershell
python -m pytest tests/test_alternative_pick_selector_v2.py tests/test_alternative_pick_evaluation_proof_v2.py -q
```

Expected: FAIL because workload fields are neither validated nor bound and proof recomputation still accepts the derived optimistic buckets.

- [x] **Step 2: Implement workload validation and proof binding**

In `validate_runtime_primitives_v2`, validate the raw fields before calling the V1 feature adapter:

```python
for name in ("is_opener", "starter_mismatch"):
    scalar(name, pitcher.get(name), kind="bool")
for name in ("last_pitch_count", "days_since_last_start"):
    value = pitcher.get(name)
    values[name] = value
    if value is None:
        missing.append(name)
    elif isinstance(value, bool) or not isinstance(value, int) or value < 0:
        malformed.append(name)
```

Always derive the existing normalized features when the current non-workload prerequisites are complete, then add canonical raw values and status:

```python
workload_fields = {
    "is_opener", "starter_mismatch", "last_pitch_count", "days_since_last_start",
}
workload_status = (
    "malformed" if workload_fields.intersection(presence.malformed)
    else "missing" if workload_fields.intersection(presence.missing)
    else "complete"
)
features.update({
    "is_opener": presence.values["is_opener"] if isinstance(presence.values["is_opener"], bool) else None,
    "starter_mismatch": presence.values["starter_mismatch"] if isinstance(presence.values["starter_mismatch"], bool) else None,
    "last_pitch_count": presence.values["last_pitch_count"] if isinstance(presence.values["last_pitch_count"], int) and not isinstance(presence.values["last_pitch_count"], bool) else None,
    "days_since_last_start": presence.values["days_since_last_start"] if isinstance(presence.values["days_since_last_start"], int) and not isinstance(presence.values["days_since_last_start"], bool) else None,
    "workload_input_status": workload_status,
})
```

When `workload_input_status` is not `complete`, construct `FamilyVote("pending", ("workload_inputs_missing",))` or `FamilyVote("pending", ("workload_inputs_malformed",))` for Base and Re-entry. Continue composing Anchor, Preclose, no-drag, and lanes through the existing three-valued functions; do not globally force every family pending.

Add the five fields to the Python proof field/type sets. Permit `None` only for the four raw workload fields, require status in `{"complete", "missing", "malformed"}`, and mirror the selector's Base/Re-entry override in `_recompute_semantics`. Add the same fields and rules to the Netlify proof validator/recomputer so Python and JavaScript independently reach the same decision.

Run the Step 1 command again.

Expected: PASS.

- [x] **Step 3: Add the complete-read, parent-provider, and ambiguity red tests**

In `tests/test_live_layer_worker.py`, add deterministic fake-page tests proving:

- provider runs read newest `101` rows once, expose only the first `100`, and use the 101st as an overflow sentinel;
- snapshots retain the existing bounded read of up to five descending
  `1,000`-row keyset pages, forming a deterministic newest-`5,000` suffix;
- an overflow sentinel or full snapshot cap returns `complete=False` with a bounded reason;
- a query lookback later than the candidate window is reported as incomplete for that candidate; and
- a snapshot is stamped with the parent `slate_date` only when its normalized provider equals the parent run provider.

In `tests/test_alternative_pick_preclose_v2.py`, add permutation tests where one provider/book/side/timestamp has two alternate lines. Every permutation must return pending with `same_checkpoint_alternate_line_ambiguity`; neither the exact-line movement series nor the ladder may choose a row by UUID/input order.

In `tests/test_alternative_pick_live_layer_v2.py`, assert an incomplete snapshot read still permits a bounded provisional/frozen V2 row but its Preclose family is pending and its proof binds the incompleteness reason.

Run:

```powershell
python -m pytest tests/test_live_layer_worker.py tests/test_alternative_pick_preclose_v2.py tests/test_alternative_pick_live_layer_v2.py -q
```

Expected: FAIL because reads use fixed limits/offsets, parent provider is not checked, and alternate lines at one timestamp can enter the ladder.

- [x] **Step 4: Implement deterministic reads and fail-closed Preclose**

Add the immutable result type in `scripts/build_live_events_to_supabase.py`:

```python
@dataclass(frozen=True)
class SnapshotReadResult:
    rows: list[dict[str, Any]]
    v2_rows: list[dict[str, Any]]
    complete: bool
    window_started_at: str
    reason_codes: tuple[str, ...]
```

Read provider runs once in descending `created_at,id` order with limit `101`;
use the newest `100` downstream and mark the read incomplete when the overflow
sentinel exists. Retain the existing snapshot budget of up to five descending
`observed_at,id` keyset pages of `1,000` rows each, validate deterministic
ordering/identity, and mark a full newest-`5,000` suffix incomplete. This does
not add a recurring snapshot query, provider call, worker, or cadence.

Build `run_id -> (slate_date, normalized_provider)` from the complete or partial run rows. Stamp a snapshot only when both run ID and normalized provider match. Leave mismatches unstamped and add `snapshot_parent_provider_mismatch`, making the V2 read incomplete. If there is no trustworthy run provenance, preserve the existing broad fallback rows for non-V2 consumers but return `complete=False` with `provider_run_provenance_unavailable`.

Pass `SnapshotReadResult.rows` to all existing non-V2 consumers and
`SnapshotReadResult.v2_rows` only to the V2 recorder. Pass the completeness
metadata only through the explicit V2 interface. In
`build_exact_preclose_evidence_v2`, append the bounded read reasons when
`snapshot_read_complete` is false and append `snapshot_window_incomplete` when
any bound provider window begins before `snapshot_window_started_at`.

Before `_coalesce_exact_checkpoints`, group candidate-relevant rows by provider, event, normalized pitcher, market, side, book, and exact timestamp, deliberately excluding line and price. If a group has more than one distinct `(line, american_odds)` pair, append `same_checkpoint_alternate_line_ambiguity` and return pending evidence. Identical duplicates still collapse deterministically.

Run the Step 3 command again.

Expected: PASS.

- [x] **Step 5: Add the V2 endpoint/browser red tests**

In `tests/test_alternative_picks_function.mjs`, add tests proving:

- the same V2 candidate returned as current provisional plus exact-lock frozen appears once and uses the frozen row;
- an invalid frozen row does not suppress a valid current provisional row;
- V2 rejects `official_verdict: "PASS"` even when the rest of the proof is self-consistent;
- unversioned/V1 still accepts its current verdict universe and does not use V2 coalescing; and
- a malicious but regex-safe top-level `reason_codes` value never appears in a V2 response, while family states and the sanitized decision proof remain.

In `dashboard/v2-alt-picks.test.mjs`, add cases proving PASS makes the entire V2 response unavailable and raw top-level reason codes are neither required nor copied into the normalized row.

Run:

```powershell
node --test tests/test_alternative_picks_function.mjs dashboard/v2-alt-picks.test.mjs
```

Expected: FAIL because V2 currently accepts PASS, exposes raw row reasons, and returns both checkpoints.

- [x] **Step 6: Implement the V2-only endpoint/browser repair**

In `validStateBase`, keep the existing `OFFICIAL_VERDICTS` rule for V1 and require `LEAN`, `FIRE 1u`, or `FIRE 2u` when `contract.requiresProof` is true. Make `dashboard/v2-alt-picks.js::normalizeRow` enforce the same non-PASS set independently.

Build visible rows in two phases: validate provisional/frozen rows and exact locks first, then for V2 only coalesce by `candidate_identity`. Use a deterministic priority of valid frozen `2`, valid provisional `1`; if two items have the same priority and identity, retain the first only when their public response JSON is identical, otherwise suppress that candidate as ambiguous. V1 returns its existing visible list unchanged.

In `responseRow`, include `reason_codes` only when `contract.requiresProof` is false:

```javascript
if (!contract.requiresProof) output.reason_codes = safeReasonCodes(row.reason_codes);
```

Remove the V2 adapter's `row.reason_codes` requirement and do not add that property to its normalized return. UI supporting copy continues to use proof-bound `family_states[*].reason_codes`.

Run the Step 5 command again.

Expected: PASS.

- [x] **Step 7: Run the integrated repair suite and commit the reviewable wave**

```powershell
python -m pytest tests/test_alternative_pick_selector_v2.py tests/test_alternative_pick_evaluation_proof_v2.py tests/test_alternative_pick_preclose_v2.py tests/test_alternative_pick_live_layer_v2.py tests/test_live_layer_worker.py tests/test_alternative_pick_selection_v2.py -q
node --test tests/test_alternative_picks_function.mjs dashboard/v2-alt-picks.test.mjs dashboard/v2-app.test.mjs
node --check netlify/functions/alternative-picks.mjs
node --check dashboard/v2-alt-picks.js
git diff --check
```

Expected: all focused Python/Node tests pass, both JavaScript files parse, and `git diff --check` is clean.

Before committing, verify the diff contains only the Task 1 files and no schema, artifact, data, environment, or generated-bundle change.

```powershell
git add market_infra/alternative_pick_selector_v2.py market_infra/alternative_pick_evaluation_proof_v2.py market_infra/alternative_pick_preclose_v2.py market_infra/alternative_pick_recording_v2.py scripts/build_live_events_to_supabase.py netlify/functions/alternative-picks.mjs dashboard/v2-alt-picks.js tests/test_alternative_pick_selector_v2.py tests/test_alternative_pick_evaluation_proof_v2.py tests/test_alternative_pick_preclose_v2.py tests/test_alternative_pick_live_layer_v2.py tests/test_live_layer_worker.py tests/test_alternative_picks_function.mjs dashboard/v2-alt-picks.test.mjs
git commit -m "fix: close alternative picks v2 contract gaps"
```

---

### Task 2: Review and release-gate the integrated wave

**Files:** Review the exact Task 1 commit; do not edit production state.

- [x] **Step 1: Run full local verification**

```powershell
python -m pytest tests/ -q
node --test tests/test_*.mjs dashboard/*.test.mjs
git diff --check HEAD^ HEAD
git status --short
```

Expected: full Python and Node suites pass, the commit has no whitespace errors, and the worktree is clean.

- [x] **Step 2: Review the eight contracts as one gate**

Reject the wave if any of these is not directly covered by a passing regression:

1. missing/malformed workload inputs cannot affirm dependent votes and are proof-bound;
2. provider-run/snapshot truncation and window gaps force Preclose pending;
3. same-timestamp alternate-line ambiguity is input-order invariant and pending;
4. V2 endpoint prefers a valid exact-lock frozen row over provisional;
5. V2 endpoint and adapter reject PASS while V1/unversioned remain unchanged;
6. snapshot provider must match parent run before slate stamping;
7. V2 omits raw top-level reasons; and
8. no prohibited official, provider, notification, lock, accepted-bet, artifact, history, migration, worker, cadence, cost, reconstruction, or deletion change exists.

- [x] **Step 3: Push only after review approval**

```powershell
git push -u origin codex/alt-v2-final-review-fixes
git status --short --branch
```

Expected: the reviewed commit is on the named remote branch and the worktree is clean. Tyler's existing approval authorizes Task 3 after the review gate passes.

---

### Task 3: Separately deploy the reviewed core and web repairs

**Requires:** A clean Task 2 review. Tyler has already approved the Render and Netlify production deploys for this rollout. Do not alter environment keys, scheduler cadence, providers, or database schema.

- [x] **Step 1: Record pre-deploy controls**

Record the reviewed commit, current `bbe-live-layer` deploy ID, current Netlify production deploy ID, V2/V1 row counts by checkpoint, duplicate candidate groups, alternative notification count, operational lock count/duplicates, accepted-bet count, official artifact hash, and provider posture.

- [x] **Step 2: Hold Netlify with a release-control commit and deploy Render first**

Fast-forward the reviewed tree to `main` through an empty `[skip netlify]`
release-control commit, verify its tree exactly matches the reviewed commit, and
deploy that exact commit to `bbe-live-layer` with the existing environment
unchanged. Wait for `live`, then one normal scheduled cycle. If the partial
slate has no remaining eligible future candidate, treat the absence of a new
proof as `no_candidates`; never reconstruct an old proof. Verify frozen rows
were not rewritten and all isolation controls from Step 1 are unchanged.

If the cycle fails, stop before Netlify, preserve the existing environment, diagnose the V2-only failure, and fix forward on the repair branch. Do not roll back or alter the official pipeline.

- [x] **Step 3: Deploy Netlify only after the recorder cycle passes**

After the Render cycle passes, trigger exactly one normal cached Netlify
production deploy for the release-control commit. Do not clear cache or create a
second deploy. Verify:

- unversioned and explicit V1 return the existing V1 bundle/fingerprint;
- explicit V2 rejects PASS, emits at most one row per candidate, prefers exact-lock frozen, and omits top-level `reason_codes`;
- invalid bundle versions remain unavailable;
- desktop `1280x900` and mobile `390x844` show comparison-only cards with no wager controls; and
- Picks, Results, accepted bets, official artifacts, provider posture, notifications, and locks match the pre-deploy controls.

If the V2 endpoint/browser contract fails, preserve official behavior, diagnose the V2-only failure, and fix forward through the same review gate. Do not roll back or rewrite V2 rows.

---

### Task 4: Update the design status and production handoff

**Files:**

- Modify: `docs/superpowers/specs/2026-07-22-alt-picks-dependency-aware-v2-design.md:5`
- Modify: `docs/superpowers/plans/2026-07-22-alt-picks-dependency-aware-v2.md`
- Modify: `docs/current-state.md`

- [x] **Step 1: Replace the stale design status**

Replace the obsolete “implementation not started” line with:

```markdown
**Status:** Comparison-only V2 is implemented and deployed; the 2026-07-23 final contract-repair wave is deployed and remains in prospective soak, with every official promotion gate closed
```

Use that exact line only after Task 3 production verification.

- [x] **Step 2: Record exact evidence in the controlling plan and operating board**

Append the repair commit, Render/Netlify deploy IDs, scheduled-cycle timestamp, row counts, maximum proof size, coalescing/PASS/reason-code endpoint checks, and unchanged isolation controls to `docs/superpowers/plans/2026-07-22-alt-picks-dependency-aware-v2.md`. Update only the July 21 Alt Picks overlay in `docs/current-state.md`; keep the four primary lanes and all promotion gates unchanged.

- [x] **Step 3: Verify and commit the handoff**

```powershell
git diff --check
git diff -- docs/superpowers/specs/2026-07-22-alt-picks-dependency-aware-v2-design.md docs/superpowers/plans/2026-07-22-alt-picks-dependency-aware-v2.md docs/current-state.md
git add docs/superpowers/specs/2026-07-22-alt-picks-dependency-aware-v2-design.md docs/superpowers/plans/2026-07-22-alt-picks-dependency-aware-v2.md docs/current-state.md
git commit -m "docs: record alternative picks v2 contract repairs"
git push origin main
git status --short --branch
```

Expected: the handoff distinguishes reviewed code from observed production evidence, the stale status is gone, `main` and `origin/main` match, and the worktree is clean.

### 2026-07-23 observed production evidence

- Reviewed repair tree: `cb2224f1`.
- Tree-identical release-control/main commit: `6ab9fcf2`.
- Full verification: `1,925` Python and `167` Node tests; Sol High review had
  no findings and the final Sol Ultra whole-branch/live review returned GO.
- Render deploy `dep-d9h8u9sm0tmc738cfmqg` reached live. Its normal
  `22:10:06Z` cycle completed successfully at `22:10:59Z` with the environment,
  provider posture, worker set, and cadence unchanged.
- The current partial slate had no eligible future tracked candidate after the
  repair became live, so no new workload-bound proof could legitimately be
  created. The immutable Brandon Pfaadt frozen proof stayed unchanged at MD5
  `efa7e0484981aa26b976b0bd897b7dea`; no proof was reconstructed.
- Netlify deploy `6a62955898bec52cde5903ae` is ready on `6ab9fcf2`.
  Explicit V2 is `ready` with zero current rows; explicit V1 and unversioned
  compatibility each return three rows; invalid versions are unavailable; V2
  emits no top-level `reason_codes`.
- Desktop and `390x844` checks show comparison-only waiting copy with no wager
  controls. Picks remain eight props and Results remain `1,648` graded rows.
  Supabase remains at zero notification rows, four unique locks all consumed,
  two unique accepted bets, and zero V2 duplicate groups.

The first new workload-bound proof and immutable freeze must be observed on the
next normal prospective slate. That is soak evidence only; every official model,
selection, staking, provider, notification, lock, accepted-bet, artifact,
history, retention, and source-of-truth gate remains closed.
