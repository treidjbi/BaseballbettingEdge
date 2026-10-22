# Alt Picks Evidence-Binding Repair Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` and `superpowers:test-driven-development` to execute this plan. Complete RED before implementation, then request an independent task review and whole-branch review.

**Goal:** Restore prospective Alt Picks evidence binding when the official artifact carries numeric `current_market_lines.id` values in `source_snapshot_ids`, without changing official picks, locks, notifications, providers, model behavior, or previously frozen alternative rows.

**Architecture:** Keep the existing fail-safe post-lock recorder and five-second budget. Add one bounded, current-slate `current_market_lines` read for numeric artifact source-line IDs. Translate only exact matching rows into their side-specific `market_snapshots` UUID and approved provider event ID, then pass those verified identities through the existing observation binder. Direct UUID snapshot IDs and explicit artifact event IDs remain supported. Missing, malformed, stale, mismatched, or unsupported mappings stay pending.

**Tech Stack:** Python 3.11, pytest, existing Supabase/PostgREST writer, existing Render `bbe-live-layer` service. No migration, provider request, new worker, UI code, environment-variable change, or backfill.

**Production verification (2026-07-22 11:21 Phoenix):** The reviewed repair
merged to `main` at `f39f438b` and is live only on `bbe-live-layer` deploy
`dep-d9ggi9jrjlhs739nihl0`. The first scheduled run on that deploy started at
`18:20:31Z` and finished successfully at `18:21:48Z` with the fresh remote
artifact, zero notification events, zero new locks, and normal TheRundown plus
PropLine processing. Before that run, all 22 provisional and three immutable
frozen rows had zero bound observations. After it, 12 current provisional rows
had five to 45 exact bound observations; the three existing frozen rows were
unchanged, duplicate alternative keys remained zero, and alternative
notification events remained zero. The public endpoint returned 15 current
provisional plus three frozen rows, 12 mature evidence rows, zero selected,
and 18 pending. Numeric artifact-ID translation is therefore fixed. Selection
remains honestly closed because strict preclose/provider completeness and
same-line consistency checks still report missing or conflicting provider
evidence. No gate, threshold, provider, notification, lock, model, UI, or
official-pick behavior was relaxed.

Independent task and whole-branch reviews ended PASS with no remaining
findings. Final merged-main verification passed 1,585 Python tests and all 99
Node tests. One retired-BoltOdds timing test failed
identically on the untouched base and remains an explicitly isolated,
out-of-scope baseline flake.

## Non-negotiable boundaries

- Change only the isolated alternative-selection recorder and its tests, plus handoff documentation.
- Keep official artifacts, verdicts, model math, thresholds, staking, grading, provider order, notifications, operational locks, accepted bets, and dashboard source-of-truth unchanged.
- Do not mutate or reconstruct the existing frozen rows. They remain immutable historical evidence of the pre-repair cycle.
- Do not guess from pitcher/line semantics alone. Numeric source-line translation must be anchored to the exact current-slate `current_market_lines.id`, normalized pitcher, model line, approved provider, market key, and side-specific snapshot UUID.
- Exclude BoltOdds and unknown providers.
- Use one batched read, `attempts=1`, and the recorder's remaining five-second budget. A read or mapping failure stops only the alternative sidecar cycle and leaves the live-layer process result intact.
- Deploy only `bbe-live-layer`. No Netlify deployment is required because the endpoint and UI contract are unchanged.

---

## Task 1: Bind numeric artifact source-line IDs safely

**Files:**

- Modify: `scripts/build_live_events_to_supabase.py`
- Modify: `tests/test_live_layer_worker.py`
- Modify after production verification: `docs/superpowers/plans/2026-07-21-pregame-alternative-pick-methodology.md`
- Modify after production verification: `docs/current-state.md`

- [x] **Step 1: Write the production-shaped failing regression**

Add an integration-level sidecar test whose artifact contains numeric `source_snapshot_ids` shaped like production `current_market_lines.id` values and no direct provider event IDs. Mock the bounded reads in production order:

1. existing alternative state;
2. exact operational locks;
3. the batched `current_market_lines` mapping.

Return exact current-line rows with `id`, `slate_date`, approved `provider`, `provider_event_id`, `normalized_player_name`, `market_key`, `line`, `game_time`, `over_snapshot_id`, and `under_snapshot_id`. Supply matching raw `market_snapshots` rows and provider evidence. Assert the persisted alternative row contains at least two bound observation UUIDs and can resolve beyond `pending` when all existing family inputs are complete.

Also add fail-closed cases proving that wrong pitcher, wrong line, wrong game time, wrong market, unsupported provider, missing side-specific UUID, and unmapped numeric IDs do not bind. Confirm the mapping is fetched in one current-slate read rather than one query per candidate.

- [x] **Step 2: Run focused tests and observe RED**

```powershell
python -m pytest tests/test_live_layer_worker.py -q
```

Expected: the new production-shaped test fails because numeric line IDs are currently passed directly to the UUID snapshot binder and no `current_market_lines` translation read exists.

- [x] **Step 3: Implement one bounded translation read**

In the recorder, separate direct snapshot UUIDs from numeric source-line IDs. Before candidate evaluation:

- collect unique numeric source-line IDs from eligible artifact candidates;
- use the remaining sidecar budget for one `current_market_lines` select with `attempts=1`, current `slate_date`, and an `id=in.(...)` filter;
- select only the fields required for exact identity validation and translation;
- index rows by numeric ID without mutating the artifact payload.

For each candidate, accept a mapped row only when all of these match:

- current slate;
- normalized pitcher;
- `market_key = pitcher_strikeouts`;
- exact model K line;
- approved provider (`therundown` or `propline`);
- exact game time when the row supplies one; and
- a non-empty side-specific snapshot UUID (`over_snapshot_id` for an over candidate, `under_snapshot_id` for an under candidate).

Add the verified side-specific UUID to artifact snapshot IDs and the verified provider event ID to that provider's event IDs. Preserve already valid direct UUID snapshot IDs and explicit artifact provider event IDs. Do not fall back to semantic-only matching or query any external provider.

If numeric IDs exist but the mapping read fails, times out, returns malformed data, or yields conflicting duplicate IDs, return the existing sanitized sidecar failure/pending boundary without affecting the rest of the live-layer run.

- [x] **Step 4: Prove focused green and compatibility**

```powershell
python -m pytest tests/test_live_layer_worker.py tests/test_alternative_pick_selection_state.py tests/test_market_infra_supabase_writer.py tests/test_notification_coordinator.py tests/test_operational_locks.py -q
```

Expected: all tests pass. Mode-off still performs no alternative reads, valid direct-ID fixtures remain compatible, and official notification/lock behavior is unchanged.

- [x] **Step 5: Run full verification and prohibited-change checks**

```powershell
python -m pytest tests/ -q
node --test dashboard/*.test.mjs tests/*.mjs
node --check dashboard/v2-app.js
git diff --check
git diff origin/main...HEAD -- render.yaml netlify.toml .github/workflows data/params.json pipeline dashboard/data data/picks_history.json
git status --short
```

Expected: all suites pass and there are no provider, model, artifact, UI, workflow, environment, lock, notification, or generated-data changes.

- [x] **Step 6: Review, merge, and deploy only the live layer**

Require an independent task review followed by an independent whole-branch review. Resolve every Critical or Important finding, rerun focused and full verification, merge to `main`, and push `origin/main`.

Deploy only `bbe-live-layer` at the verified repair commit. Do not change Render environment variables or deploy Netlify. Confirm the service is live on the new commit and the next scheduled cycle completes successfully.

- [x] **Step 7: Verify prospective production behavior**

Using current-slate Supabase and the public Alt Picks endpoint, verify:

- fresh post-deploy provisional rows bind real observation UUIDs for eligible mapped candidates;
- selection status resolves when all existing family inputs are complete, while genuinely incomplete candidates remain pending;
- the pre-deploy frozen pending rows remain byte-for-byte immutable and are not reconstructed;
- no duplicate alternative keys or alternative notification rows appear;
- official locks, notifications, artifacts, picks, and the main Picks tab remain unchanged; and
- the existing Alt Picks UI renders the new prospective state without a Netlify deployment.

Update the controlling alternative-pick plan and Four-Lane Operating Board with the verified commit/deploy/cycle evidence. If no qualifying candidate is available in the first post-deploy cycle, report the binding counts honestly and keep the prospective selected-lane sample gate open.
