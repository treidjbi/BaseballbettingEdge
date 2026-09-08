# 2026 Season-End Freeze And Provider Shutdown Plan

**Status:** Preparation and read-only rehearsal are complete. Production
execution remains closed until the final regular-season checkpoint and a fresh
Tyler approval.

**Goal:** Finish the 2026 regular season with a complete, reproducible research
record, then stop BaseballBettingEdge's PropLine and TheRundown polling so the
same provider accounts can support other projects during the offseason.

**Regular-season boundary:** [MLB's published 2026 schedule](https://www.mlb.com/press-release/press-release-mlb-announces-2026-regular-season-schedule)
ends on Sunday, September 27. Postseason polling is off by default. If a
regular-season game is suspended, postponed, or officially moved beyond
September 27, stop this plan and identify the exact affected game before
suspending the provider callers.

**Companion evidence:**
`docs/research/2026-09-08-season-end-read-only-preflight.md`.

## Approval Boundary

Tyler approved this plan and a read-only rehearsal on September 8. That approval
does not itself authorize a future Render suspension, provider subscription
change, webhook change, database write, compaction write, deletion, deployment,
or model promotion.

At the end of the season, show the current evidence and obtain a fresh approval
immediately before changing external service state. Keep these scopes separate:

1. Provider-calling Render cron suspension.
2. Final hydrated grading run or repair.
3. Compact-only movement-history finalization.
4. PropLine webhook subscription or receiver change.
5. Any raw-row deletion, vacuum, physical rewrite, provider cancellation, or
   secret rotation.

## Non-Goals

- No live lambda, probability, threshold, staking, formula date, referee,
  quality-gate, Path B, market-anchor, market-shrink, or Alt Picks change.
- No new provider, polling increase, or postseason collection.
- No provider account cancellation or API-key rotation. The accounts remain
  available for other projects.
- No raw snapshot or webhook deletion.
- No conversion of a scaffold-only candidate into a 2027 canary.
- No historical accepted-bet reconstruction without an original receipt and
  exact accepted time.

## Service Disposition

Resolve current service IDs and settings from Render immediately before the
shutdown. Do not rely on old deploy IDs in historical plans.

| Surface | Calls PropLine/TheRundown? | End-of-season action | Timing |
| --- | --- | --- | --- |
| `bbe-pipeline-preview` | yes | suspend | after final regular-season slate; before the next 12:17 AM Phoenix preview |
| `bbe-pipeline-full` | yes | suspend | with provider-calling group |
| `bbe-pipeline-refresh-day` | yes | suspend | after the final useful refresh/lock window |
| `bbe-pipeline-refresh-evening` | yes | suspend | after the final useful refresh/lock window |
| `bbe-pipeline-refresh-final` | yes | suspend | after the last scheduled final refresh completes |
| `bbe-live-layer` | yes | suspend | after all final-day locks and notifications are accounted for |
| `bbe-pipeline-grading` | no provider polling | keep temporarily | through final successful grading and verification |
| `bbe-pipeline-lock` | no provider polling | keep temporarily, then suspend | until final-day operational locks are consumed or explicitly reconciled |
| `bbe-gate-c-post-grading-review` | reads stored evidence | keep temporarily, then suspend | through one final successful research build |
| Netlify `send-live-notifications` | no provider polling | leave deployed/no-op initially | verify no actionable queued events after live-layer suspension |
| Netlify dashboard and `get-artifact` | no provider polling | keep read-only | offseason archive access |
| Netlify `propline-webhook` | inbound only | separate decision | it does not spend polling quota, but it can keep growing storage |
| Supabase | no provider polling by itself | keep | frozen artifacts and research evidence |
| GitHub manual workflows | scheduled runs already disabled | keep manual-only | never use GitHub grading without a separately proven hydration repair |

Suspending the provider-calling group also stops the pipeline's emergency The
Odds API fallback because that fallback is invoked inside the same pipeline
runs. It does not cancel or reassign any provider account.

## Stage 0 — September 8 Preparation

- [x] Confirm the Mac clone, canonical origin, branch, and clean working tree.
- [x] Preserve the unrelated decision-time research branch and create the
  separate `codex/season-end-runbook` branch from `origin/main`.
- [x] Run a read-only research rehearsal with temporary outputs.
- [x] Stage current production history directly from linked Supabase after the
  public full-history endpoint returned HTTP 502.
- [x] Stage compact `market_pick_evidence`, `live_market_display_state`, and the
  current artifact without reading raw `market_snapshots`.
- [x] Prove the hybrid Gate C builder, market-agreement tracker, season-end
  dataset, workload/no-vig audit, seasonal audit, candidate lab, and decision
  packet all execute without changing repository or production state.

The rehearsal proves plumbing only. It is not the final freeze and it does not
make either of the two scaffold candidates decision-ready.

## Stage 1 — September 8 Through September 26

Keep normal production behavior unchanged.

Once per week, the existing BBE Operations Brief should report:

- current database bytes and percentage of the nominal 8 GiB allocation;
- `market_snapshots`, `compact_market_line_movements`, and
  `propline_webhook_deliveries` relation sizes;
- exact active-provider compact coverage for a bounded completed-date sample;
- latest completed physical backup and PITR status;
- current PropLine/TheRundown request usage;
- canonical artifact freshness and last successful grading date;
- any accepted bets entered from original receipts.

Escalate before September 27 only if storage approaches 80%, growth no longer
leaves credible end-of-season headroom, a completed slate cannot be graded, a
canonical artifact is missing/stale, or provider evidence needed for the final
freeze is being lost. Do not respond to ordinary growth by deleting more data.

## Stage 2 — Final Regular-Season Slate, September 27

### A. Before games

- [ ] Confirm MLB still lists September 27 as the last regular-season date.
- [ ] Confirm there is no officially scheduled makeup game after September 27.
- [ ] Record current Render service names, IDs, branch, commit, schedule,
  suspension state, and auto-deploy state without printing environment values.
- [ ] Record current provider usage counters and latest provider-run timestamps.
- [ ] Confirm the preview/full artifact is fresh and the final slate date is
  `2026-09-27`.
- [ ] Confirm expected tracked picks, game times, and final-day lock count.

### B. After games and the final refresh

- [ ] Wait until every September 27 game is final, cancelled, or explicitly
  accounted for. A suspended/postponed game is a stop condition.
- [ ] Confirm every September 27 operational lock is consumed or has a reviewed
  explanation. Do not require the global historical unconsumed-lock count to be
  zero; legacy May/August rows are a separate record.
- [ ] Confirm all actionable notification events are sent, suppressed by an
  existing rule, or explicitly documented.
- [ ] Capture the last PropLine/TheRundown provider-run IDs, timestamps, request
  counts, and coverage summaries.
- [ ] Obtain Tyler's fresh approval for the exact six-service provider-calling
  suspension.

### C. Suspend the provider-calling group

Suspend only:

```text
bbe-pipeline-preview
bbe-pipeline-full
bbe-pipeline-refresh-day
bbe-pipeline-refresh-evening
bbe-pipeline-refresh-final
bbe-live-layer
```

Perform the suspension after the last useful final-day cycle and before the
September 28 12:17 AM Phoenix preview. Do not suspend grading, the research
cron, Netlify, Supabase, or provider accounts in this step.

### D. Prove polling stopped

Observe at least two former 10-minute live-layer windows and verify:

- no new BBE PropLine or TheRundown `market_provider_runs` rows;
- no increase in BBE-attributed provider request usage;
- no new `dated_slate:2026-09-28` or postseason artifact;
- the September 27 dashboard artifact remains readable;
- the Netlify notification sender has no newly actionable events.

If any provider run continues, stop and identify its source before claiming the
API capacity was released.

## Stage 3 — Final Grading And Artifact Freeze

The primary grading path is the hydrated Render service. GitHub grading is not
an approved fallback.

- [ ] Allow the September 28 3:17 AM Phoenix `bbe-pipeline-grading` run to grade
  September 27, or wait until every delayed final result is available.
- [ ] Require one completed publication run containing the final dated slate,
  `picks_history`, `performance`, `params`, and `index`.
- [ ] Verify all five artifacts through cache-busted Netlify `get-artifact`
  reads with matching hashes and publication timestamps.
- [ ] Confirm every actionable September 27 pick is `win`, `loss`, `void`, or
  `cancelled`. Result-unset PASS rows are allowed and must not be mistaken for
  grading failures.
- [ ] Record final clean-regime rows, complete-data calibration rows, lambda
  bias, actual/predicted mean Ks, verdict/side results, and accepted-bet count.

If scheduled grading fails, obtain separate approval for one manual hydrated
Render grading run and repeat the same five-artifact verification. Do not run
GitHub grading.

## Stage 4 — Season-End Research Freeze

Run this only after Stage 3 passes. Use `set -euo pipefail` or equivalent so a
failed source step cannot be followed by empty reports that look successful.

### A. Stage current inputs read-only

Use a fresh temporary directory. Stage:

- bounded `picks_history` from the canonical Supabase artifact row;
- bounded `market_pick_evidence`;
- bounded `live_market_display_state`;
- the final `today`/dated artifact;
- any accepted-bet export authorized for research;
- existing handedness and actual-opportunity backfills.

Do not use the public unbounded full-history response as the only history path.
Do not read raw market snapshots when the compact evidence is sufficient.

### B. Build and verify in temporary output first

Use the sequence proven in the September 8 rehearsal:

1. Build Gate C with staged history.
2. Build market agreement from Gate C plus the staged compact evidence.
3. Rebuild Gate C with that fresh agreement tracker and live-display export.
4. Build the season-end no-leakage dataset.
5. Run workload/no-vig and seasonality audits.
6. Run the next-season candidate lab.
7. Run the decision packet only after its canonical context reports are fresh.

The temporary run must satisfy:

- nonzero Gate C and season-end row counts;
- equal Gate C and season-end row counts;
- zero duplicate `dataset_key` values;
- `matched_pick_rows == graded_pick_rows`;
- final source date equals the last graded regular-season date;
- every candidate carries train/test metrics and required slice metadata;
- missing source/slice evidence blocks rather than promotes.

### C. Write the canonical freeze

Only after the temporary packet is reviewed, rerun the approved Task 7 outputs
to the canonical paths named in
`2026-06-23-next-season-k-model-rebuild-master-plan.md`. Record hashes, row
counts, source windows, and generation times. Update that master plan with the
season-end review, but draft no child canary unless Tyler separately approves a
specific candidate.

## Stage 5 — Finalize Compact Market History

This stage uses stored Supabase data and does not require resumed provider
polling.

- [ ] Inventory every PropLine/TheRundown provider-date partition after the
  last previously exact interval through September 27.
- [ ] Run the existing finalizer in preview mode one date at a time.
- [ ] Require both providers, complete source evidence, exact rebuilt-versus-
  existing comparison, and stable repeated previews.
- [ ] Present the fixed compact-only write scope and obtain separate approval.
- [ ] Execute one date at a time using the existing double gate.
- [ ] Require a zero-upsert post-write preview for each date.
- [ ] Obtain a completed physical backup newer than the last compact write.

No raw deletion follows automatically. Any deletion, webhook cleanup, vacuum,
or physical rewrite needs a new bounded plan and approval.

## Stage 6 — Suspend Remaining Seasonal Jobs

After grading, research freeze, and final lock reconciliation are complete,
suspend:

```text
bbe-pipeline-grading
bbe-pipeline-lock
bbe-gate-c-post-grading-review
```

Verify that the static dashboard, final artifacts, and Supabase evidence remain
readable. The Netlify sender may remain deployed as a no-op; changing its
embedded schedule would require a separate code/deploy decision.

## PropLine Webhook Decision

The webhook is inbound and does not consume the polling quota being released.
It can still grow `propline_webhook_deliveries` after the Render pollers stop.

After the research freeze, choose separately between:

- keep the subscription briefly for final delivery reconciliation; or
- disable only the BBE webhook subscription/receiver and verify arrivals stop.

Do not cancel the shared PropLine account, rotate the shared key, or disturb
another project's subscription. Do not leave an active inbound subscription
writing indefinitely with no processor plan.

## Rollback And Early-Resume Rule

If the provider-calling group was suspended too early:

1. Confirm the exact missing regular-season game or slate.
2. Obtain approval to resume only the six named services.
3. Restore each service's recorded branch, commit, schedule, environment-key
   names, auto-deploy state, and prior suspension state. Do not introduce a new
   deployment while resuming.
4. Observe one successful provider run and one fresh official artifact.
5. Reapply the shutdown checkpoint after the game is final.

A 2027 restart is not this rollback. Before next season, create a new canary and
provider-budget review, refresh park/umpire inputs, decide the calibration
window, and prove the first slate before restoring normal polling.

## Completion Evidence

The final handoff must record:

- final regular-season date and any exceptions;
- exact services suspended and timestamps;
- last and first-absent provider-run timestamps;
- final provider usage counters;
- final grading publication run and five artifact hashes;
- Gate C/season-end row counts, date range, duplicate count, and reconciliation;
- candidate decisions and blocked slices;
- compact-history exactness by provider/date;
- latest completed backup after the final compact write;
- webhook disposition;
- branch, commit, and clean working tree.

Do not call the season closed if provider polling continues, the final
actionable picks are ungraded, the research dataset is empty/stale, or recent
market history lacks an explicit preservation decision.
