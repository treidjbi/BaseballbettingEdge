# 2026 Season-End And Offseason Decision

**Status:** Decision-ready review. Empty-day contract repairs are implemented
and tested on `codex/season-end-empty-day-contracts`; no production deployment,
Render suspension, provider-account change, database write, retention action,
or model promotion has occurred.

**Decision date:** 2026-09-28 Phoenix time.

## Executive Recommendation

Approve suspension of the six provider-calling Render services after a final
read-only service-ID/settings capture. Keep grading, lock, and research jobs
available until the final research freeze and reconciliation are complete.
Keep Netlify and Supabase available read-only. Do not cancel shared provider
accounts, delete raw evidence, or change any model/provider/source-of-truth
gate.

The final regular-season slate is graded, its locks and notifications reconcile,
and the September 28 artifact is an explicit zero-pick slate. However,
`bbe-live-layer` is still polling every 10 minutes. At the 2026-09-28 21:10 MST
checkpoint it made one PropLine request and two TheRundown requests, returned
zero target events/props/snapshots, and wrote another no-op timing row. The
calls are healthy but have no BBE decision value in the offseason.

## Current Evidence

- September 27 grading completed through the hydrated Render/Supabase path:
  `19` tracked picks, `9-9-1`, `-1.660690u`.
- September 27 operational locks are `19/19` consumed with exact proof and no
  final miss or duplicate.
- September 27 notification events are `2/2` sent with no pending or failed
  row.
- September 28 `today` is current, `props_available=false`, with zero pitchers,
  tracked picks, locks, notifications, or data warnings.
- Provider/live-layer cycles continued through at least
  `2026-09-29T04:10:37Z` (`2026-09-28 21:10 MST`) with zero BBE targets.
- TheRundown's live header reports a current 25,000,000 monthly datapoint
  allowance, `578264` used, and `24421736` remaining. This corrects the stale
  5,000,000 allowance in the older cost note but does not justify broader
  polling.
- Supabase is approximately 5.704 GB / 66.40% of the nominal 8 GiB allocation,
  below the 70% review trigger. The September 28 physical backup completed;
  PITR remains off.
- PropLine webhook processing and writes remain retired. BoltOdds remains
  retired with no post-June runtime evidence.
- Public unbounded `picks_history` remains unsuitable for runtime reads; use
  the bounded/staged Supabase path for the final research freeze.

## Decision A — Provider-Calling Render Services

**Recommendation: YES, suspend after exact live inventory.**

Suspend only:

```text
bbe-pipeline-preview
bbe-pipeline-full
bbe-pipeline-refresh-day
bbe-pipeline-refresh-evening
bbe-pipeline-refresh-final
bbe-live-layer
```

Before changing state, record each service's current ID, branch, commit,
schedule, suspension state, and auto-deploy state without printing environment
values. If any service name or role differs from this list, stop and reconcile
it rather than broadening the target.

After suspension, observe two former live-layer windows and require:

- no new BBE PropLine or TheRundown `market_provider_runs` rows;
- no increase in BBE-attributed request usage;
- no new postseason dated artifact;
- the September 27 final artifact and September 28 empty artifact remain
  readable;
- no newly actionable notification event.

This action releases BBE polling capacity only. It does not cancel PropLine or
TheRundown, rotate keys, change provider order, or authorize another project's
use of the released capacity.

## Decision B — Remaining Seasonal Jobs

**Recommendation: HOLD temporarily.**

Keep these available until the final research freeze and reconciliation pass:

```text
bbe-pipeline-grading
bbe-pipeline-lock
bbe-gate-c-post-grading-review
```

Once the freeze is accepted, separately suspend them and verify the final
dashboard/artifacts remain readable. GitHub grading remains unsafe and is not
a fallback.

## Decision C — Final Research Freeze

**Recommendation: run one read-only staged build, then review before canonical
writes.**

Use a fresh temporary directory and fail-fast execution. Stage canonical
`picks_history` directly from linked Supabase, plus bounded compact market
evidence and the final dated artifact. Do not depend on the public unbounded
history endpoint and do not read raw snapshots when compact evidence suffices.

Require before accepting the freeze:

- nonzero Gate C and season-end row counts;
- equal Gate C and season-end row counts;
- zero duplicate `dataset_key` values;
- `matched_pick_rows == graded_pick_rows`;
- final source date `2026-09-27`;
- train/test and required-slice metadata for every candidate;
- missing provider, CLV, Path B, workload, market-agreement, price, side,
  K-line, or rolling-window evidence blocks promotion.

No candidate is approved for a live canary by this review. Confidence referee
and profit rescue stay bounded; Path B remains the live input canary;
market-shrink and market-anchor remain shadow/applied-zero; both Alt V2 paths
remain retired.

## Decision D — Retention And Storage

**Recommendation: HOLD.**

Do not delete raw snapshots, compact history, locks, notifications, accepted
bets, research artifacts, or webhook archives. Do not vacuum or physically
rewrite tables. Current utilization is below the review trigger, and the final
research freeze has not yet accepted its preservation inputs.

Any later cleanup must use the exact prepared one-provider/one-date executor,
a completed backup newer than the review packet, a fresh preview token, and a
separate approval for the exact command. No loop or broad age-based deletion is
authorized.

## Decision E — Empty-Day Contracts

The implementation branch makes three bounded changes:

1. Preview runs publish a dated empty `preview_lines` contract with
   `props_available=false` instead of republishing an older date. A transient
   empty retry preserves an already-good same-date baseline.
2. Full/refresh runs publish a dated empty `steam` contract when the canonical
   slate is empty, while preserving valid same-date output on a transient
   provider failure.
3. Alt V2 accepts a trusted current canonical artifact with
   `props_available=false` and zero pitchers as `ready` with zero candidates.
   Postureless artifacts that claim props were available still fail closed.

The Netlify function and pipeline tests must pass before merge. Merge/deploy is
separate from provider suspension. Because Render cron auto-deploy is off, a
merged pipeline change will not affect those services until a separately
approved Render redeploy; if the callers are suspended first, defer that
redeploy to the next-season restart plan.

## Decision F — Offseason Cost Posture

- Keep shared PropLine and TheRundown accounts; release only BBE polling
  capacity.
- Keep Supabase and Netlify for read-only artifact/history access.
- Keep the Netlify notification sender deployed as a no-op initially; changing
  its embedded schedule is a separate code/deploy decision.
- Keep BoltOdds retired and verify billing externally only if the prior
  cancellation confirmation changes.
- Recheck Supabase storage monthly or before any 2027 restart; do not pay for
  extra storage or activate deletion solely from current 66.40% utilization.

## Explicit Approval Boundaries

This review does not authorize:

- any Render suspension until Tyler approves the exact six-service action;
- suspension of grading, lock, or research jobs;
- provider cancellation, plan change, key rotation, or capacity reassignment;
- retention deletion, vacuum, compaction write, or database rewrite;
- model, threshold, staking, referee, Path B, market-anchor, market-shrink,
  Alt, notification, lock, or source-of-truth promotion;
- production deployment of the empty-day repair.

## Exact Next Approval

The next independently reversible step is:

> Approve a read-only Render inventory followed by suspension of only the six
> provider-calling services listed in Decision A, then verify two absent polling
> windows. Keep grading, lock, research, Netlify, Supabase, provider accounts,
> and every model/retention gate unchanged.
