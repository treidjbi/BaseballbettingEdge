# Research Evidence Reconciliation And Market-Anchor Review Design

**Date:** 2026-07-23

**Status:** Tyler approved the recommended direction; written design awaiting
review before implementation planning

## Executive decision

Repair two research-only evidence gaps and expand the existing market-anchor
shadow audit without changing any live BaseballBettingEdge behavior.

The implementation will:

1. allow the Gate C builder to recover a missing archive outcome from one
   unique exact graded `picks_history` row before the archive row is filtered;
2. export the existing compact Supabase `market_pick_evidence` and
   `live_market_display_state` rows into bounded research inputs;
3. run the market-agreement tracker early enough for the same post-grading Gate
   C build and downstream canaries to consume the refreshed labels; and
4. expand the existing market-anchor selector audit with the mandatory
   promotion-review slices and leave-one-slate-out checks.

The implementation will not mutate a historical production artifact, export
raw `market_snapshots`, add a table, change a provider call, or alter a live
model, verdict, threshold, stake, notification, lock, UI, retention rule,
artifact source, or source-of-truth rule.

## Evidence behind the design

The 2026-07-23 post-grading run produced:

- `3,176` Gate C rows and `1,658` tracked rows;
- zero duplicate dataset keys;
- `1,623/1,624` graded tracked picks reconciled; and
- zero scheduled market-agreement rows.

The sole Gate C miss is Adrian Houser UNDER 3.5 on 2026-06-16.
`picks_history` contains the graded win and two actual strikeouts, while the
June 16 dated archive contains the complete pitcher/market row with
`actual_ks` and `result` still null. The current builder filters that row
before history enrichment, so reconciliation cannot recover it later.

The market-agreement tracker is healthy when input files are supplied. The
scheduled Render command supplies none, so its optional evidence loaders return
empty lists. Supabase currently holds approximately `3,105`
`market_pick_evidence` rows and `3,251` `live_market_display_state` rows in the
clean regime. Those compact rollups are sufficient for the existing tracker;
the roughly 2.4 million raw snapshot rows are not required for this repair.

Market-anchor strict is strong enough for a dedicated shadow review but not
promotion:

- `330` clean tracked rows have selector metadata;
- `130` strict tracked rows are 80-50, +5.94u;
- strict displayed FIRE is 20-7, +7.14u;
- current-provider strict displayed FIRE is 15-5, +5.71u; and
- strict performance remains positive after excluding any one slate.

The result is concentrated in displayed OVER FIRE rows. All-strict UNDER,
6.5-line, weak/medium pre-close, and elevated workload slices are negative or
near breakeven, while provider attribution and market agreement remain
incomplete. The audit needs to make those limits impossible to miss.

## Alternatives considered

### 1. Rewrite or republish the June 16 production archive

This would repair the source artifact directly, but it risks invoking an old
grading/calibration path against a historical date and would mutate production
truth for a research-only discrepancy. It also does nothing to prevent a
future incomplete archive from disappearing before reconciliation.

**Decision:** rejected.

### 2. Synthesize a missing Gate C row from `picks_history` after the dataset is built

This would make reconciliation pass, but `picks_history` alone does not contain
the full official-close market and model context. A synthetic row could quietly
invent or omit odds, projection, quality, and source provenance.

**Decision:** rejected.

### 3. Enrich an existing complete archive row from one exact graded history row

The archive continues to supply the official-close market/model context.
History supplies only the missing outcome fields, and only when the match is
unique and exact. Ambiguity fails closed and remains visible in reconciliation.

**Decision:** chosen.

### 4. Export all raw market snapshots for the scheduled tracker

This would support reconstructed T-120/T-60/T-30/T-15/T-5 checkpoints, but it
would move a multi-million-row table through a daily research cron and add
cost, timeout, and retention pressure.

**Decision:** rejected for this repair. Raw checkpoint reconstruction remains a
separate opt-in research operation.

### 5. Continue relying on manual or committed market-evidence exports

This preserves the current code but repeats the exact failure: scheduled
reports silently become stale or empty when an operator does not refresh the
files.

**Decision:** rejected.

### 6. Export only existing compact Supabase rollups

The two existing derived tables contain the live consensus, value direction,
book coverage, movement counts, freshness, and provenance fields already used
by the tracker and Gate C display enrichment. The scheduled read is small,
bounded, idempotent, and adds no storage table.

**Decision:** chosen.

## Architecture and data flow

The isolated `bbe-gate-c-post-grading-review` service remains the only deployed
consumer changed by this work.

```text
Supabase compact rollups              Netlify/Supabase artifacts
  market_pick_evidence                  picks_history
  live_market_display_state             today
             \                           /
              -> bounded research input export
                         |
                         v
              market-agreement tracker
                         |
                         v
        Gate C build with fresh agreement/display inputs
                         |
                         v
     existing post-grading audits + expanded anchor review
```

The exporter runs before the Gate C build. The tracker runs once before the
build so Gate C receives fresh agreement labels. It may run once more after the
build to render the final report with the newest Gate C metadata; the movement
labels themselves must remain identical across both passes. The Gate C dataset
is built only once.

When scheduled export is disabled, existing explicit file arguments continue
to work for local diagnostics. Render enables the export with one explicit
cron-command flag so a local command without Supabase credentials does not
unexpectedly contact production.

## Gate C outcome reconciliation contract

The archive loader will build one history index before iterating dated
artifacts.

An archive pitcher row may receive a missing `actual_ks` only when exactly one
history row matches:

```text
slate date
normalized pitcher
archive K line == locked history K line, falling back to history K line
history result in {win, loss}
numeric history actual_ks
```

The builder then derives the winning side from the recovered actual strikeouts
and the unchanged archive line.

Rules:

- Never overwrite a non-null archive `actual_ks` or `result`.
- Never use side-only or pitcher-only fallback for outcome recovery.
- Never create a market row that does not already exist in the archive.
- More than one exact candidate is ambiguous and must fail closed.
- A recovered row records research-only provenance indicating an exact history
  outcome reconciliation.
- Summary/manifest output reports recovered and ambiguous counts.
- The normal reconciliation stage remains authoritative and must reach
  `1,624/1,624` on the verified 2026-07-22 corpus.

No dated production archive, `picks_history`, grading database, params file, or
dashboard artifact is written by this path.

## Compact market-agreement export contract

Create one small research exporter used only by the post-grading runner.

Inputs:

- `SUPABASE_URL`;
- `SUPABASE_SERVICE_ROLE_KEY`, held only by the server-side Render cron;
- the production artifact API URL already used by the Gate C builder;
- clean-regime start date, default `2026-04-28`; and
- an inclusive end date, defaulting to the current Phoenix slate date.

Outputs under `analytics/output/market_agreement_inputs/`:

- `market_pick_evidence.json`;
- `live_market_display_state.json`;
- `picks_history.json`;
- `today.json`; and
- `manifest.json`.

Behavior:

- Query only `market_pick_evidence` and `live_market_display_state`.
- Filter each Supabase read by inclusive `slate_date`.
- Page deterministically in batches of at most 1,000 rows.
- Use stable ordering and deduplicate by existing table identity.
- Fetch `picks_history` and `today` through the approved production
  `get-artifact` path.
- Filter the exported history to the requested clean-regime dates.
- Write a manifest containing source names, filters, counts, min/max dates,
  generation time, and file hashes.
- Never include credentials, request headers, or secret-bearing URLs in output
  or logs.
- Treat missing credentials, a partial page, malformed JSON, a non-2xx
  response, or an empty export when bounded source rows exist as a failed
  research run. Do not silently replace the prior evidence with empty files.
- Use the existing idempotent GET retry behavior for transient Data API
  failures; do not add writes or schema changes.

Raw `market_snapshots` remains excluded. If exact historical checkpoints are
needed later, they require a separate bounded export plan and cost review.

## Post-grading runner contract

Add an explicit scheduled flag such as:

```text
--refresh-market-agreement-inputs
```

With the flag on, the runner:

1. exports the compact Supabase inputs and current production artifacts;
2. runs the tracker from those inputs and the current/previous Gate C metadata;
3. builds Gate C once, consuming the refreshed tracker and live-display files;
4. reruns the tracker for the final report using the fresh Gate C dataset;
5. runs existing downstream reports in their current order; and
6. prints counts, date bounds, and the normal shadow-only excerpts.

With the flag off, the runner preserves its current file-driven behavior.

The runner must not:

- call a provider;
- write Supabase;
- publish a dashboard artifact;
- grade a pick;
- change params;
- send a notification;
- create or consume a lock; or
- advance a canary counter from ungraded, duplicated, or unreconciled data.

## Market-anchor shadow review contract

Keep the selector fingerprint, live mode, labels, and candidate logic
unchanged. Expand only
`analytics/diagnostics/market_anchor_selector_canary_audit.py`.

Report strict tracked rows and strict displayed FIRE separately for:

- overall and current-provider windows;
- latest 14 distinct strict slate dates;
- leave-one-slate-out minimum and maximum;
- over/under;
- K-line;
- price sign and price bucket;
- quality;
- timing;
- final CLV and pre-close CLV proxy;
- workload/leash;
- Path B coverage;
- provider era and provider attribution; and
- market agreement, including missing coverage.

The report must explicitly say:

- all current strict displayed FIRE rows are OVERs when that remains true;
- raw sample floors are met;
- meeting raw floors opens a separate shadow review only;
- negative or missing mandatory slices keep `enforce_downside` closed; and
- a later candidate narrowed to OVERs would be a new selector requiring a new
  fingerprint, baseline, plan, and prospective canary.

No audit result may change `MARKET_ANCHOR_SELECTOR_MODE=shadow`.

## No-drag interaction

The no-drag selector and locked baseline do not change.

Fresh market-agreement and provider-display coverage may enrich current and
future Gate C rows. This can improve mandatory slice completeness, but it must
not:

- backfill a prospective qualification;
- rewrite the locked 52-row base;
- reduce the 75-row review floor;
- alter the selector fingerprint; or
- move `collecting` to anything except `ready_for_review` when the existing
  contract permits.

The current 58/75 counter remains authoritative until the next normal
post-grading run.

## Render deployment boundary

Only `bbe-gate-c-post-grading-review` may be deployed.

The service currently runs:

```text
python scripts/run_post_grading_shadow_reports.py
```

Deployment will update only that cron command to add the explicit compact
export flag. Its schedule, branch, plan, build command, and auto-deploy posture
remain unchanged.

Before deployment, inspect the complete environment-variable name list without
printing values.

- If `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` already exist, preserve the
  entire list unchanged.
- If either is missing, stop. Adding or copying those existing secrets into
  the research service is a separate Render environment-variable mutation and
  requires Tyler's explicit approval after reviewing this spec.
- Never print or store either secret.

No pipeline cron, live-layer service, Netlify function, dashboard deployment,
provider flag, model flag, notification flag, lock flag, or retention flag may
change.

## Error handling

- Gate C ambiguity remains visible as an unmatched reconciliation row.
- Export failures terminate the research job before new empty inputs replace
  good files.
- Temporary output files are promoted only after every export succeeds and
  validates.
- Tracker zero-row output with nonzero exported compact inputs is a failed
  acceptance check.
- A failed research deploy rolls back to the prior service deploy/command. No
  data rollback is required because the implementation is read-only.
- Production pipeline health does not depend on this cron and remains
  unaffected by a research-job failure.

## Test-driven implementation strategy

Write and observe failing tests before each behavior change.

### Gate C tests

1. Recover Adrian-shaped missing outcome fields from one exact graded history
   row.
2. Preserve an archive-provided outcome.
3. Refuse pitcher-only, side-only, line-mismatched, ungraded, missing-actual,
   and ambiguous matches.
4. Preserve official-close odds/model fields and record recovery provenance.
5. Reconcile the resulting tracked row.

### Export tests

1. Page both compact tables beyond 1,000 rows.
2. Apply inclusive date bounds and stable ordering.
3. Fetch and date-filter production history.
4. Write complete files and a hashed manifest atomically.
5. Redact secrets from logs and manifest.
6. Fail without credentials, on partial/malformed responses, and before
   replacing prior good output.
7. Assert that raw `market_snapshots` is never queried.

### Runner tests

1. Scheduled export runs before the tracker and Gate C build.
2. Gate C receives the refreshed tracker/display paths.
3. The final tracker report uses the fresh Gate C dataset.
4. Flag-off behavior remains file-driven and backwards compatible.
5. No production writer/provider/notification/lock path is imported or called.

### Market-anchor tests

1. Pin current strict and strict-FIRE totals.
2. Test every mandatory slice and missing-coverage count.
3. Test current-provider and rolling windows.
4. Test leave-one-slate-out calculations.
5. Test the explicit all-OVER concentration warning.
6. Test that the report keeps `enforce_downside` closed.

### Verification

- Focused research tests pass.
- The complete Python and Node suites pass.
- A local production-artifact build reaches zero duplicate keys and full
  reconciliation.
- A local compact export/tracker run produces nonzero date-bounded rows.
- The research cron deploy is live and one manual verification job succeeds.
- The deployed Gate C summary reconciles fully.
- The deployed market-agreement report is nonzero.
- The deployed no-drag report preserves its selector fingerprint and counter
  contract.
- The deployed market-anchor report includes all mandatory slices and still
  recommends shadow review only.
- Production artifacts, locks, notification counts, provider posture, and
  dashboard source remain unchanged.

## Documentation updates

After live research verification:

1. update the Gate C controlling plan with the outcome-recovery contract;
2. update the market-agreement controlling plan with scheduled compact-input
   refresh behavior;
3. update the market-anchor selector plan with the dedicated slice-review
   result;
4. update the Four-Lane Operating Board without opening Gate C/D/E/F/12E; and
5. update the BBE Operations Brief automation memory.

## Acceptance criteria

The work is complete only when:

1. the verified clean-regime dataset reconciles every graded tracked pick;
2. no production archive was mutated to achieve that reconciliation;
3. scheduled market-agreement output is nonzero, bounded, and sourced only
   from existing compact rollups plus approved production artifacts;
4. Gate C and downstream reports consume the refreshed evidence in the same
   run;
5. the no-drag counter/fingerprint remain unchanged except for future normal
   graded rows;
6. the market-anchor report exposes the breakout and every blocking slice
   without changing selector behavior;
7. only the research cron is deployed; and
8. no live model, provider, notification, lock, UI, artifact, retention, or
   source-of-truth behavior changes.

## Non-goals

- repairing or republishing historical production archives;
- exporting raw market snapshots on the daily schedule;
- adding a Supabase table, migration, provider request, worker, or cadence;
- promoting market anchor or narrowing it to an OVER-only live selector;
- backfilling no-drag prospective rows;
- changing publisher timeout behavior before its recurrence tripwire fires;
- changing pipeline, grading, calibration, params, thresholds, staking,
  notifications, locks, UI, accepted bets, retention, or source-of-truth
  behavior; or
- reviving BoltOdds.
