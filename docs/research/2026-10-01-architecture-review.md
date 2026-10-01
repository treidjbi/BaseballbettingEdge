# 2026 architecture review and TheRundown-only 2027 target

Date: October 1, 2026. Offline review of repository code and saved operational receipts. No provider requests, service changes, database writes, or restarts. Tyler reports PropLine canceled and directs TheRundown as the sole future odds provider. All services remain dormant; this is a recommendation, not restart approval.

## Finding

Keep the core architecture: Python batch pipeline → persisted canonical artifacts/evidence → Netlify dashboard/functions. Calculation, persistent history, and presentation are sensibly separated. There is no evidence here of insufficient capacity. Eleven named Render services overstate the necessary production footprint: eight operational cron jobs, two research jobs, and one retired BoltOdds worker. They were not eleven continuously running app servers.

Recommend **six operational Render jobs** after a reviewed 2027 release, with research on demand. The safe no-refactor alternative is the existing eight operational jobs, excluding research and BoltOdds. Six is a simplicity target, not a proven performance optimum. Runtime, overlap and invoice evidence would be needed to claim exact savings. Do not restart any today.

## Inventory and recommendation

The saved authenticated October 1 inventory in the [season-end plan](../superpowers/plans/2026-09-28-season-end-offseason-decision.md) records all eleven suspended.

| Existing service | Responsibility | 2027 recommendation |
| --- | --- | --- |
| bbe-pipeline-preview | Opening/current-day baseline | Keep separately: distinct baseline contract |
| bbe-pipeline-grading | Prior-day outcomes/history and calibration | Keep separately; decide whether calibration stays automatic |
| bbe-pipeline-full | Morning picks/model publication | Keep separately |
| bbe-pipeline-refresh-day | Intraday refresh | Consolidate three refresh schedules into one guarded job |
| bbe-pipeline-refresh-evening | Same mode, UTC rollover window | Consolidate |
| bbe-pipeline-refresh-final | Same mode, final window | Consolidate |
| bbe-live-layer | Mainline evidence, operational locks, events, optional research | Keep; narrow to required operational work and TheRundown evidence |
| bbe-pipeline-lock | Consume lock rows and publish canonical locked artifacts | Keep separately initially |
| bbe-gate-c-post-grading-review | Research diagnostics | On demand unless an approved prospective test requires scheduling |
| bbe-pipeline-shadow-runner-hosted | Hosted research experiment | Remain off; deferred timing-proof experiment is not a March dependency |
| bbe-boltodds-shadow-worker | Retired trial | Remain retired |

Current refresh schedules cover 08:07–18:07 Phoenix: `7,37 15-23 * * *`, `7,37 0 * * *`, and `7 1 * * *` UTC. One `7,37 0-1,15-23 * * *` schedule with a Phoenix-time guard excluding 18:37 could preserve those 21 daily refresh slots. This proposed change requires schedule/date tests; it is not applied. The guard must precede hydration, API calls and writes. Include early games, UTC rollover and late starts in restart acceptance.

Do not merge locks and provider polling merely to reduce count: `scripts/build_live_events_to_supabase.py:1449` produces operational lock rows; `scripts/run_render_pipeline_mode.py:74` defines separate lock publication. A polling failure must not prevent due locks becoming canonical. Expensive research should not extend this critical path.

## TheRundown-only is not implemented yet

Cancellation alone does not change BBE routing. Concrete release tasks:

1. **Wrapper posture:** `scripts/run_render_pipeline_mode.py:132` forcibly selects `therundown_propline`, enables that adapter and sets non-strict fallback for preview/pipeline. Ordinary environment preference is insufficient. Select TheRundown explicitly and disable combined/BoltOdds modes while preserving historical readers.
2. **Hidden fallback:** `pipeline/fetch_odds.py:789` tries PropLine when its key exists and coverage is incomplete; the following block does the same for The Odds API. Enforce a provider allow-list at call boundaries, tested even with legacy keys present. Remove inactive BBE credentials from approved runtime configuration during the later release without altering shared accounts.
3. **Live polling:** `scripts/build_live_events_to_supabase.py:2050` enables PropLine merely from key presence. TheRundown capture is independently flag-controlled. Keep webhook retirement and all historical data intact.
4. **Evidence consumers:** live-layer queries at lines 1090, 1120 and 1264 explicitly include both providers. Audit freshness/provider contracts for market agreement, best-price display and notification candidates. Historical PropLine observations remain useful research; they must not count as fresh 2027 coverage.
5. **Coverage:** display missing target-book coverage honestly; never substitute stale PropLine lines. Direct fetch target affiliates are in `pipeline/fetch_odds.py:55`. Verify coverage only after an authorized restart. TheRundown-only describes odds; MLB stats/results and other model inputs are separate dependencies also requiring restart authorization.

TheRundown mainline collection already exists (`scripts/build_live_events_to_supabase.py:1671`). Movement collection need not be rebuilt from scratch. But one less source may reduce sportsbook coverage; historical cross-provider performance is not automatically reproducible under the new regime.

## Cost and capacity

The [cost ledger](../provider-cost-ledger.md) records September 28 headers showing 25M monthly data points, 578,264 used at that observation, two requests/second and a 60-second delay. Older 2M/5M figures are historical. These are saved observations, not verified 2027 allowances or a current invoice. Do not subtract an obsolete PropLine price from the old ~$120 stack estimate to invent savings.

Preserve scoped mainline polling, usage accounting and no-target early exits. A single provider does not authorize higher cadence or alternate-line expansion. The ledger's June measurements found mainline queries much lighter than broad capture. Preserve decision/lock/closing checkpoints; any retention change needs its own approved archive/recovery plan.

The [July operations packet](all-star-break-operations-packet.md#cost-and-row-volume-read) attributed most observed Render bandwidth to lock (4.63 GB) and live-layer (1.78 GB) paths, with small estimated dollar exposure. Examine repeated hydration and bounded reads before buying capacity. This evidence establishes neither current billing nor overload; no additional service is justified.

## Bounded pre-March checklist

- Reviewed release manifest: code SHA, jobs, flags, provider allow-list, schedules, artifact contracts and rollback.
- Deploy-version reconciliation before unsuspending. Five preview/full/refresh services are recorded at `a12fa988` with auto-deploy off; live-layer receipt records `0299493f`. Netlify's dormant sender release is `6abe83f00cc497e8c1d138aa`. Main also contains the signed Preclose reader fix. Clean Git does not prove runtime parity. See [branch closeout](2026-10-01-branch-closeout-review.md).
- Fixed model/version policy: `pipeline/run_pipeline.py:1809` grades and calibrates together; line 1844 invokes calibration. Decide how automatic updates interact with a frozen prospective model test.
- One owner per job; idempotent retries; no publication races; locks before start; no started-game mutations; dated empty slates; clear coverage-failure behavior; recoverable artifacts. Preserve grading hydration safeguards; old GitHub grading fallback remains unsafe until separately repaired.
- Notifications restart only if explicitly wanted, with the dormant sender deliberately released and one deduplicated event path.
- Distinct accepted-bet ledger with actual stake, price, time, book and stable identity. Published exposure and research simulations cannot stand in for account results.

This checklist does not require finishing every historical experiment. Six operational jobs plus existing storage/dashboard is the recommended target. Dormancy remains the correct present state.
