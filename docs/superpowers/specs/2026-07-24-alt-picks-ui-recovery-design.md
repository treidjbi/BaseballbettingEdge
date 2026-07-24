# Alt Picks UI Recovery Design

**Date:** 2026-07-24

**Status:** Approved for design; implementation remains pending written-spec review

## Executive decision

Repair the comparison-only Alt Picks tab so a temporary endpoint failure or
artifact handoff cannot leave the page stuck on `Alternative methodology
unavailable` after valid current-slate evidence becomes available.

The fix is intentionally limited to browser resilience:

- fetch immediately when the Alt tab mounts;
- refresh every 60 seconds while the tab remains mounted;
- allow only one request at a time;
- preserve the last valid response if a later refresh fails;
- distinguish initial unavailability from a temporary retry state; and
- update both Alt asset version tokens so deployed clients receive the repair.

The existing V2 endpoint, data contract, selector, evidence ledger, provider
posture, and operational runtime remain unchanged.

## Confirmed problem

On 2026-07-24, the production V2 endpoint returned a valid `ready` response
with current provisional and frozen rows, including one selected frozen row,
while Tyler's app continued to show `Alternative methodology unavailable`.

The browser adapter successfully normalizes the same live response outside the
stuck page. The tab currently requests data only once when it mounts. A
transient network failure, artifact transition, or stale cached asset can
therefore strand the page until a successful full reload. The current Alt
adapter and app script references also use older version tokens.

This is a dashboard recovery defect. It is not evidence of missing Alt
methodology state, a failed selector, or an official-model problem.

## Alternatives considered

1. **Cache-bust only.** Smallest immediate change, but it does not recover from
   future transient failures or artifact transitions. Rejected as incomplete.
2. **Cache-bust plus mounted polling and last-good preservation.** Chosen. It
   repairs the current client and provides bounded automatic recovery without
   changing the API or production pipeline.
3. **Add a second `/api/alternative-picks` route plus polling.** Rejected.
   Current evidence does not show that the existing route is unavailable; a
   diagnostic browser blocked direct navigation to both function and `/api`
   routes while independent requests to the production endpoint returned
   `200`. A second route would add an unproven contract and maintenance path.

### Production correction: neutral route required

The initial recovery deployment supplied stronger evidence that supersedes the
third alternative above. Netlify served the exact reviewed commit, both new
assets returned `200`, and the V2 endpoint returned a valid current response,
but both the in-app browser and Chrome rendered the retrying unavailable state.
Direct Chrome navigation to
`/.netlify/functions/alternative-picks?bundle_version=v2` then failed with
`ERR_BLOCKED_BY_CLIENT`.

The approved endpoint contract remains unchanged, but the browser adapter now
uses the neutral same-origin alias `/api/slate-comparison?bundle_version=v2`.
Netlify internally rewrites that exact path to the existing function. The
original function route remains available for compatibility and operational
checks. No second function, data source, selector, provider call, table, or
runtime worker is added.

## Scope and boundaries

The change may modify only the Alt Picks browser adapter, Alt tab rendering,
asset version references, and their tests.

It must not change:

- official Picks, verdicts, lambda, EV, thresholds, staking, or grading;
- the V2 selector fingerprint, methodology, family rules, or freeze logic;
- operational locks or accepted-bet writes;
- notifications or notification classes;
- providers, provider order, polling workers, or source-of-truth behavior;
- the Netlify endpoint response contract or Supabase evidence;
- dashboard artifact publication or model/history data; or
- any other dashboard tab's behavior.

Alt Picks remains comparison-only and contains no wager, stake, Log Bet, or
notification controls.

## Client state and refresh behavior

The Alt tab owns one mounted refresh loop:

1. Fetch immediately after mount.
2. If the request finishes, schedule the next refresh so requests cannot
   overlap.
3. Continue at a 60-second cadence only while the component is mounted.
4. Cancel the pending timer and ignore late results during unmount.

The visible state follows these rules:

- **Initial loading:** show the existing loading treatment.
- **Initial valid response:** render the normal `ready`, `waiting`, or
  contract-defined empty state.
- **Initial request/validation failure:** show methodology unavailable plus a
  concise automatic-retry message.
- **Later valid response:** replace the displayed state normally.
- **Later failure after a valid response:** retain the last valid cards and
  counts, mark the evidence temporarily stale/retrying, and do not replace it
  with methodology unavailable.
- **Recovery:** clear the retry/stale marker on the next valid response.

A valid endpoint response that honestly says `waiting` remains valid; the
client must not manufacture selected rows or preserve cards across a valid
slate/contract transition. Last-good preservation applies only when the later
attempt itself fails or is rejected, not when the endpoint returns a valid new
state.

## User-facing copy

The repair should use plain, comparison-safe language:

- initial failure: `Alternative methodology unavailable. Retrying
  automatically.`
- later failure with preserved data: `Last update retained; retrying current
  evidence.`

The normal comparison-only disclosure remains visible. No copy may imply an
official pick or wager recommendation.

## Asset delivery

Both `v2-alt-picks.js` and `v2-app.js` receive new version query tokens in the
dashboard HTML. Updating only the adapter was initially insufficient because
the refresh loop lives in the app bundle. After the client-blocked route was
confirmed, the adapter receives the later
`2026-07-24-alt-route-recovery` token so clients cannot retain the blocked URL;
the already-current app bundle keeps `2026-07-24-alt-ui-recovery`.

The deployed HTML and both script bodies must be verified from production
after Netlify reports the deploy ready. A hard refresh should not be required
once the new HTML is loaded.

## Verification

Tests are written before implementation and cover:

- an immediate request on mount;
- a later request after the 60-second interval;
- no overlapping requests;
- timer cleanup and ignored late results on unmount;
- initial failure rendering unavailable plus automatic retry;
- later failure preserving the last valid data and showing retry/stale copy;
- successful recovery clearing that copy;
- a valid new `waiting` state replacing an older valid `ready` state;
- unchanged V2 bundle/fingerprint validation;
- updated version tokens for both Alt assets;
- continued absence of wager controls and official-state writes; and
- unchanged rendering for other dashboard tabs.

Run the focused Alt browser/UI tests, the complete JavaScript suite, and the
existing UI-isolation checks. Then deploy the exact reviewed commit to Netlify
and verify:

- the endpoint still returns the unchanged reviewed V2 contract;
- the production HTML references both new asset versions;
- the Alt tab recovers without a full reload;
- a temporary refresh failure does not erase valid cards; and
- Picks, Results, accepted bets, notifications, locks, and official artifacts
  remain unchanged.

## Rollback

Rollback is a Netlify frontend rollback to the prior reviewed deploy. No
database, Render, provider, environment-variable, artifact, or model rollback
is required because the repair changes none of those surfaces.

## Acceptance criteria

The repair is complete when Tyler's Alt tab displays the current valid V2
state, automatically recovers from a temporary failed read while open, retains
the last valid view during later failures, receives fresh app and adapter
assets, and leaves every official and operational boundary unchanged.
