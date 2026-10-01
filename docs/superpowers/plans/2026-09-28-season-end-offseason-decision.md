# 2026 Season-End And Offseason Decision

## October 1 full dormancy directive — controlling overlay

Tyler explicitly requested no more grading, API pulling, or automatic data work;
existing results are for offline review and 2027 diagnosis. This supersedes the
narrow six-service approval and HOLD language below. No restart is authorized.

The authenticated Render project inventory showed the six provider callers and
BoltOdds already suspended. This session suspended and verified these four:

| Service | ID | Verified state |
| --- | --- | --- |
| bbe-pipeline-grading | crn-d8as4pdckfvc73dgpme0 | Suspended by you |
| bbe-pipeline-lock | crn-d8dgp6q8qa3s739n80s0 | Suspended by you |
| bbe-gate-c-post-grading-review | crn-d8mpcb0g4nts73fq5bv0 | Suspended by you |
| bbe-pipeline-shadow-runner-hosted | crn-d89jpvdckfvc738nfla0 | Suspended by you |

All 11 BBE Render services are suspended. BBE Operations Brief automation
`sync-baseballbettingedge-repo` is PAUSED, preserving its existing prompt.
The Netlify scheduled sender is replaced by an unscheduled no-network dormant
response. Production deploy `6abe83f00cc497e8c1d138aa` is live; its public sender returns
`{"status":"offseason_dormant","sent":0}`. The Git-triggered deploy was canceled
by the build-ignore check, so this release used the authenticated linked CLI.
All 17 notification tests passed, including a network-forbidden dormant-handler
check. Supabase read-only extension inventory returned no pg_cron extension.
No database records were changed by this shutdown.
GitHub workflows contain no active schedule triggers and no queued/running
workflow was reported in the current run listing. Manual dispatch is prohibited
without a new explicit restart/repair request. Preserve data and shared provider
accounts. Read-only dashboard/history access remains available.

### Offline 2027 diagnosis queue

Use the October 1 research freeze unchanged. Do not rebuild it from live APIs.
1. Establish the accepted-bet ledger and actual stake definition; published
   model exposure and the incomplete July 27 accepted-bet table cannot explain
   the user-reported approximately -57u.
2. Decompose losses into projection calibration, price/juice, side/line, and
   selection/exposure. Compare paired identical populations and time windows.
3. Test market shrink 15/25/35 against current model and market-only baselines
   on frozen data. Projection MAE improvement alone is insufficient: reconstruct
   explicit would-bet decisions and report turnover, price, risk and ROI.
4. Treat moderate-edge and retained-FIRE positives as exploratory hypotheses.
   Use chronological holdouts and stability slices; 2026 has already informed
   discovery and cannot become an untouched confirmation set retroactively.
5. Audit decision-time provenance before designing a 2027 prospective test.
   Preserve the unmerged decision-time adapter branch; its passive-receipt
   review blocks hosted capture because by-lock proof/seed continuity is absent.
6. Draft a separately reviewed 2027 protocol only after the offline comparisons:
   frozen candidate, realistic available prices, fixed stakes, loss/exposure
   limits, minimum sample, and explicit stop/reject criteria. No live promotion.

### Git closeout audit

Mac canonical clone: clean main, synced to origin at audit; no stashes or extra
worktrees, no open PRs. Two local branches retain unique committed/pushed work:
`codex/research-decision-time-adapter` (8 commits, offline evidence tooling and
review; paused at timing barrier), and `codex/season-end-runbook` (2 historical
documentation commits). Neither is uncommitted work. Preserve both; do not merge
stale operating-board text or discard evidence as routine branch cleanup.
Seven remote branches are not ancestors of main (which can include already
cherry-picked/superseded work): aug20-history-repair, no-drag-strict-runtime-decision,
research-decision-time-adapter, retention-nine-partition-repair, season-end-runbook,
strict-runtime-model-market-slice, supabase-pressure-repairs (all under codex/).
These require content reconciliation before deletion; there are no open PRs.


**Status:** Decision A executed on 2026-10-01. The empty-day contract repairs
are merged, the Netlify Alt V2 contract is deployed, and exactly the six
approved provider-calling Render services are suspended. Two former live-layer
windows passed with no provider runs, usage increase, artifact publication, or
notification event. No provider-account change, database write, retention
action, model promotion, or additional service suspension occurred.

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

**Recommendation: EXECUTED.**

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

### October 1 execution receipt

The authenticated Render inventory matched the approved target exactly:

| Service | Service ID | Branch / deployed commit | Schedule UTC | Auto-deploy | Final state |
| --- | --- | --- | --- | --- | --- |
| `bbe-pipeline-preview` | `crn-d8as4l1akrks738ngep0` | `main` / `a12fa98879d860c367569056db0b8fb4db463c0d` | `17 7 * * *` | off | suspended by Tyler |
| `bbe-pipeline-full` | `crn-d8as4r8g4nts73b5f510` | `main` / `a12fa98879d860c367569056db0b8fb4db463c0d` | `17 13 * * *` | off | suspended by Tyler |
| `bbe-pipeline-refresh-day` | `crn-d8asbonavr4c73drnrhg` | `main` / `a12fa98879d860c367569056db0b8fb4db463c0d` | `7,37 15-23 * * *` | off | suspended by Tyler |
| `bbe-pipeline-refresh-evening` | `crn-d8asbrel51nc73ahmh60` | `main` / `a12fa98879d860c367569056db0b8fb4db463c0d` | `7,37 0 * * *` | off | suspended by Tyler |
| `bbe-pipeline-refresh-final` | `crn-d8asbv0jo6nc7381gma0` | `main` / `a12fa98879d860c367569056db0b8fb4db463c0d` | `7 1 * * *` | off | suspended by Tyler |
| `bbe-live-layer` | `crn-d7tpb19o3t8c739p3qig` | `main` / `0299493fff63cc8bd642f1c718a2c605b6c7b3ce` | `*/10 * * * *` | on commit | suspended by Tyler |

The project inventory then showed all six as `Suspended by you`.
`bbe-pipeline-grading`, `bbe-pipeline-lock`,
`bbe-gate-c-post-grading-review`, and
`bbe-pipeline-shadow-runner-hosted` remained unsuspended. The retired
`bbe-boltodds-shadow-worker` remained separately suspended.

Read-only Supabase checkpoints at `2026-10-01T15:41:29Z` and
`2026-10-01T15:51:33Z`, covering the former 08:40 and 08:50 Phoenix windows,
proved:

- zero new PropLine or TheRundown `market_provider_runs` after the
  `15:36:00Z` cutoff;
- the latest provider run remained at `15:30:48Z`;
- PropLine and TheRundown daily request counts remained `28` each, with the
  same `15:30:54Z` update timestamp;
- zero new published pipeline artifacts;
- zero new notification events, including zero actionable events; and
- HTTP 200 reads for `dated_slate:2026-09-27` and
  `dated_slate:2026-09-28` through the production Netlify artifact function.

## Decision B — Remaining Seasonal Jobs

**Recommendation: HOLD unless separately approved.**

The final research freeze and reconciliation pass is complete, but Decision A
did not authorize these services. Keep them available until Tyler separately
chooses an offseason posture:

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

The merged and production-deployed Netlify contract plus the merged pipeline
code make three bounded changes:

1. Preview runs publish a dated empty `preview_lines` contract with
   `props_available=false` instead of republishing an older date. A transient
   empty retry preserves an already-good same-date baseline.
2. Full/refresh runs publish a dated empty `steam` contract when the canonical
   slate is empty, while preserving valid same-date output on a transient
   provider failure.
3. Alt V2 accepts a trusted current canonical artifact with
   `props_available=false` and zero pitchers as `ready` with zero candidates.
   Postureless artifacts that claim props were available still fail closed.

The focused Netlify and pipeline tests passed before merge. Netlify production
deploy `6abe7622c429c5921a017519` now serves the Alt V2 empty-slate contract.
The five suspended pipeline jobs remain on pre-merge commit `a12fa988`; their
auto-deploy setting is off. Defer their merged pipeline-code deployment to a
separately approved next-season restart plan rather than resuming them now.

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

- any additional Render suspension or any resumption; the six-service Decision
  A receipt exhausts Tyler's approval;
- suspension of grading, lock, or research jobs;
- provider cancellation, plan change, key rotation, or capacity reassignment;
- retention deletion, vacuum, compaction write, or database rewrite;
- model, threshold, staking, referee, Path B, market-anchor, market-shrink,
  Alt, notification, lock, or source-of-truth promotion;
- production deployment of the empty-day repair.

## Exact Next Approval

No immediate production action is required. Any later suspension of grading,
lock, research, or the hosted shadow runner requires a new exact-scope
approval. Any 2027 restart requires a separate plan that explicitly inventories
and resumes the intended services, deploys the merged pipeline code where
needed, and revalidates provider, artifact, notification, lock, and cost
posture before games.
