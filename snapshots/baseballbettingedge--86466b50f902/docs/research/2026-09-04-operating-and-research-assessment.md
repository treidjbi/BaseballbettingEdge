# BaseballBettingEdge operating and research assessment

Reviewed September 4, 2026. Starting repository: clean Mac `main`, pulled and
verified at `f948ccc000e4c05e55a53b8ea9c2357934a9628f`.
Companion: [concise operating brief](../operating-brief.md).

Later September 4 correction: the [lineage follow-up](2026-09-04-research-lineage-decision.md)
reproduces the Gate C JSONL and summary manifest hashes exactly by restoring
Windows CRLF in memory. It supersedes this assessment's unresolved-hash
conclusion. The historical corpus, original observations and results below
remain preserved; current candidate eligibility still requires newer evidence.

## Decisions supported now

**Operational reliability: Watch.** Current artifact publication and the
previous slate's lock consumption work. The repaired grading path has fresh
publication evidence. Storage remains above its review trigger, the GitHub
grading fallback is unsafe, and research attribution remains incomplete.
Successful delivery does not establish betting value.

**Predictive/selection value: no new production promotion is justified.**
There is useful projection-error evidence, but no demonstrated candidate
profit after execution and allocated operating costs. The strongest complete
new prospective read is negative: Alt V2's 113 selected frozen rows are
49–63 with one void, **-24.889187u** at recorded odds. Its formal paired review
is due; repeated generic soak messages no longer answer the decision.

This review makes documentation recommendations only. It changes no model,
stake, threshold, provider, notification, lock, retention, scheduler,
production setting, or historical record. Existing child plans still control
every detailed gate; no floor, fingerprint, or approval is changed here.

## Evidence boundaries and reproducibility

| Evidence class | Source and scope | Permitted interpretation |
| --- | --- | --- |
| Current primary read | [captured SELECT-only evidence](evidence/2026-09-04-operating-review/read-only-evidence.json), operations observed `2026-09-04T21:38:36Z`; Alt V2 bounded July 24–September 3 | Live records, with the query and actual captured rows preserved. No September 4 outcomes included. |
| Current durable operating decisions | [current-state](../current-state.md), September 2 grading repair and September 4 cleanup completion overlays | Supersede older blocked-cleanup and provider-trial summaries. Completion is not authority for another cleanup. |
| Frozen historical or counterfactual packets | Candidate-specific dated links below | Nomination, controls, or paired hypothetical changes; never post-freeze credit. |
| Hosted research checkpoint recorded in repository | September 2 overlay: 4,638 source rows and 2,436 tracked graded rows through September 1 | Latest durable hosted checkpoint found; full current hosted report/slice bodies were not retrieved in this review. Do not manufacture refreshed counters. |
| Local Gate C and diagnostic files | [manifest](../../data/research/gate_c/pitcher_k_outcome_dataset_manifest.json): generated August 21, **data ends June 16**, 2,070 sides / 1,075 tracked | Historical snapshot. Its generation date is not its outcome cutoff. June reports under `analytics/output` do not replace September hosted evidence. |

[Reproduction script](evidence/2026-09-04-operating-review/check_evidence.py),
[executed notebook](evidence/2026-09-04-operating-review/evidence-checks.ipynb),
[Alt summary](evidence/2026-09-04-operating-review/alt-summary.json), and
[HTTP/manifest checks](evidence/2026-09-04-operating-review/verification.json)
preserve the audit path. The SQL returns research identity and outcome fields,
not secrets, accepted-bet details, or subscription endpoints.

The local Gate C manifest also fails its byte-hash check: recorded JSONL hash
`e8c7c6d53ca51610213d1b168af58e831f5f8e079f2e28f88944856c3316a0da`
versus actual
`6f5745a290b12ab3976a81f5231084eb8619adc855384d1107187ad5c51ff66b`.
There are no CRLF line endings; normalization does not resolve it. Actual row
count (2,070) and date range (April 28–June 16) match the manifest. This is a
local provenance discrepancy, not evidence of a live artifact failure. Preserve
the files and reconcile the intended serialization/hash in a separate review
before using this manifest as byte-integrity proof. No candidate counter was
recomputed from this local file.

Grains differ: Gate C uses pitcher-game/side/checkpoint rows; projection MAE
should use paired unique pitcher-games; candidate PnL uses selected graded
sides; operational locks and raw ticks are not independent predictive samples.
The April 28 clean boundary does not remove subsequent provider, Path B, cap,
calibration, or collection changes. June 24 marks the current provider era,
not exact provider attribution. [Data caveats](../data-caveats.md) and the
[Gate C parent plan](../superpowers/plans/2026-05-12-pitcher-k-outcome-research-dataset.md)
remain controlling. History-recovered outcomes cannot repair missing pre-lock
selection evidence or be back-credited to frozen prospective counters.

## Assessment 1: operational reliability

| Surface | Evidence and reliability read | Next decision and revisit trigger |
| --- | --- | --- |
| Artifact delivery | Live Supabase `today` generated 21:38:08Z and published 21:38:12Z. September 3 dated slate, performance and params published September 4 10:17:53Z; preview published 07:18:04Z. Exact hashes/run IDs are captured. | Retain ordinary freshness/hash checks after natural runs. Investigate missing expected mode output or served/published mismatch. A `manual-render-*` run ID alone does not establish a human-triggered run. |
| Grading and recovery | September 2 hydrated Render repair is complete. Fresh September 4 grading publication is present. GitHub run `33650131043` had selected stale May 30 history; its failure before publication prevented damage. | Retain hydrated Render as repair path. Keep GitHub grading out of rollback recommendations until a separate hydration design and proof exists; staging `index.json` is not a fix. |
| Locks | Live September 3 ledger: 12 locks, all consumed, zero duplicate keys. All 113 selected frozen Alt rows also join consumed exact line/price/artifact locks. | Retain due/consumed/started-unlocked and wrong-date checks. One clean day does not satisfy the separate five-active-slate strict-lock discussion gate. |
| Provider posture | Current controlling record is non-strict TheRundown+PropLine with direct TheRundown fallback; BoltOdds retired. Older AGENTS/synthesis paragraphs describing the May trial or 2M quota are superseded by dated current-state/cost records. | Retain coverage, freshness, exact provider/book provenance and request usage. Investigate actual missing coverage or overage pressure; do not reopen old provider promotion reviews. No live environment audit or provider billing audit was performed here. |
| Storage and recovery | Fixed cleanup finished: 82/82 partitions, 1,816,265 raw rows deleted, all observations retained in 36,507 compact groups. Ordinary vacuum completed. Live size is 6,143,741,075 bytes (~71.52% of 8 GiB); snapshots 4,168,032,256 bytes; webhook relation 640,876,544 bytes. | Fixed queue is complete; retire its pending-action reminders. Retain periodic growth/coverage checks. Existing 70% trigger remains crossed, but another scope, physical rewrite, webhook cleanup or automatic retention needs its own plan. Logical deletion did not release physical quota. |
| Research delivery | September 2 research retry completed after an index-read timeout. Gate C attribution/consumed-lock gaps can block candidates even when the job succeeds. Local files lag the hosted corpus. | Retain successful-build date, actual data-through date, source hash, duplicates, reconciliation, recoveries and eligibility counts. On repeated transport failures, review bounded retry design separately; do not repeatedly dispatch jobs. |
| Notifications and UI | Current docs record grouped reminders/pick changes and approved mainline best-price notifications; Alt V2 is comparison-only. No new sender delivery/log or mobile interaction audit was performed here. | Retain sent/failed/deduped/stale-action evidence and UI freshness/contract checks. Review reported webhook backlog by age and supported class before proposing processing work; inbox age alone is not an official-feed outage. |

The storage completion proof is
[the immutable consolidated record](../../data/research/retention/prepared-active-provider-deletion-execution-2026-09-04.json).
The [risk register](../operational-risk-register.md),
[provider cost ledger](../provider-cost-ledger.md),
[artifact-exit plan](../superpowers/plans/2026-05-22-github-artifact-exit.md), and
[tracker ownership map](market-tracker-map.md) define the boundaries. The
September 4 completion overlay supersedes earlier deletion NO-GO descriptions
for that fixed scope only. PITR remains disabled in the completion record;
a completed physical backup is not a demonstrated restore exercise.

## Assessment 2: predictive and selection value

### Cost convention and baseline

All unit results below include the payout at recorded American odds: a win
earns `odds/100` at positive odds or `100/abs(odds)` at negative odds; a loss
costs one unit. This incorporates the offered price, but **not a separately
measured execution-cost model**. No commission, exchange fee, slippage,
rejected-fill, tax, or candidate-level infrastructure allocation is documented
in the reviewed scoreboards. Therefore “after all costs” profitability is
**not established** for any candidate. Missing costs are not assumed zero.

Alt results below are flat one-unit paper exposures at frozen official odds;
voids return zero and are excluded from ROI risk. Other packets retain their
original flat/risk-weighted conventions. Avoided-loss deltas are hypothetical
exposure reductions, not realized profits. No double subtraction of sportsbook
vig is appropriate; no-vig probabilities are comparison features, not cash PnL.

The dated [cost ledger](../provider-cost-ledger.md) estimates ~$120/month
runtime/data and $20–$100/month operator tooling. These are old planning
estimates, not verified current invoices, and the research-cron total is not
separately allocated. For a documented unit value `U` dollars and allocated
cost `C` dollars, net units would be `paper units - execution costs/U - C/U`.
Neither `U` nor a defensible candidate allocation is supplied. Negative paper
results already fail before adding such costs; positive historical results
cannot be called net profit. No spend change is recommended.

The live performance artifact has 2,380 closed tracked picks and a 1,911-row
complete-data calibration sample. Average actual/predicted Ks are 4.95/4.97;
this near-zero mean bias is not a holdout, discrimination, distribution-tail,
or betting-value test. Its six published side/verdict ROI buckets are all
negative: OVER/UNDER FIRE 2u -23.52%/-1.70%, FIRE 1u -1.15%/-14.28%, and LEAN
-7.64%/-6.91%. These are mixed-era tracked-bookkeeping results, including
unstaked LEANs, not Tyler's accepted-bet account or the current cap stack's
isolated causal effect. Production calibration continues changing under its
existing policy; this review did not change it.

### Active candidate: strict runtime core

**Frozen hypothesis:** retain existing FIRE with market-agreed moderate EV
or OVER/moderate EV/normal leash, excluding high raw edge, market fade and
FIRE-under-fade drag. Selector `strict_runtime_core_flat`, fingerprint
`6d07a98031a8b26915ad34fc031def76d26519850dc476db723d37f25a8d9905`.
[Controlling plan](../superpowers/plans/2026-07-29-no-drag-and-strict-runtime-prospective-review.md)
and [issued decision](2026-08-10-no-drag-strict-runtime-decision.md).

- Eligibility: post-July-29 unique graded pre-start rows, immutable baseline,
  runtime-safe critical fields and provider/agreement/proxy attribution;
  recovered history earns no prospective credit.
- Floors: standalone audit 50 current-provider graded rows, including 10
  UNDER and 10 plus-price; all mandatory slices, rolling and leave-one-slate-out
  checks. **The FIRE matrix separately requires 75 prospective rows for the
  same policy. These are two review contracts, not two independent signals.**
- Historical results at quoted-price cost basis: 96, 64–32, +17.727u; current
  provider 20, 15–5, +5.864u; recent 17, 14–3, +7.106u. Historical
  leave-one-slate-out minimum +4.290u.
- Prospective result: last explicit issued count is zero credited post-freeze
  rows; September 2 durable checkpoint remains blocked at 20/50. UNDER and
  plus-price are zero. Do not replace that with a guessed new count.
- Attribution: August 27 reader fix accepts official provider fields, but no
  fresh complete attributed slice table was obtained here. Agreement, proxy,
  CLV and diversity remain unresolved; provider era alone is insufficient.
- Decision: **narrow specialist review only**. Revisit upon new attributable
  post-freeze evidence and actual diversity, not additional copies of the
  historical OVER/minus profile. Full execution/operating-cost result unknown.

### Active candidate: incremental high-raw-edge FIRE cap

**Frozen hypothesis:** existing displayed FIRE at raw probability edge
`edge_6_plus` is overconfident; a downgrade may avoid losses beyond the
quality/referee/profit-rescue stack. Preserve `cap_high_raw_edge` and the
[frozen matrix specifications](../../analytics/diagnostics/strong_base_fire_policy_matrix.py).
[Plan](../superpowers/plans/2026-07-29-strong-base-fire-policy-shadow-matrix.md);
[shortlist](strong-base-fire-policy-shortlist.md).

- Eligibility: fully graded July 30+ rows satisfying the frozen rule; separate
  already-capped rows from genuinely incremental displayed FIRE. Never promote
  LEAN/PASS. Require pre-start proof and complete critical attribution.
- Floors: 75 prospective rows, positive current-provider/latest-14 value,
  positive prospective leave-one-slate-out minimum, no negative mandatory
  slice with at least 10 rows, complete provider/agreement/CLV.
- Historical: broad label 926 rows, -122.20u. Exact incremental subset 429,
  205–224, **-51.360u flat**; hypothetical cap **+64.719u risk-weighted avoided
  loss**. These numbers have different stake denominators and cannot be added.
- Prospective: shortlist started 0/75. No newer auditable matrix counter or
  cost-adjusted incremental result was retrieved; current value is unknown,
  not assumed zero or passed.
- Attribution/decision: high overlap with existing caps and mixed eras must be
  resolved on identical rows. **Retain one frozen downside candidate**, review
  only upon eligible counter/slice change. Net after execution/allocated costs
  remains unmeasured; no live cap change.

### Active candidate: market-anchor downside

**Frozen hypothesis:** apply the existing stored selector's downside action
only where it would further reduce current displayed FIRE after earlier caps.
Use stored pre-start metadata, not a postgame rerun. June 16 shadow boundary;
July 29 paired protocol. [Plan](../superpowers/plans/2026-07-29-market-anchor-downside-review.md)
and [packet](market-anchor-downside-review-packet.md).

- Floors: 50 exact graded would-change rows, at least 10 each side,
  non-negative current-provider and latest-14 reads, provider/agreement/CLV
  attribution and all mandatory slices. Aggregate strict success is not this
  cohort's result.
- Counterfactual through July 28: 48, all OVER/FIRE 1u/minus, 27–21;
  displayed -0.763u, cap delta +0.763u. Avoided losses 21.000u minus foregone
  wins 20.237u; current-provider delta +4.632u/41, recent +1.714u/24.
  One post-start row excluded; provider absent on 48/48, agreement absent on
  45/48. The August 27 provider-reader repair does not prove those gaps closed.
- Later bounded counterfactual, August 25–26: five would-change rows, 4–1;
  cap delta **-1.804u**. This two-day packet is not an updated full cohort and
  is not actual enforced PnL. [Source](2026-08-27-clv-close-packet-dry-run.md).
- Strict displayed FIRE's August 21 47-row +2.92u headline is breakout-watch
  context only. It neither supplies UNDER would-change evidence nor proves
  incremental downside value.
- Decision: **keep_shadow**. Refresh the exact paired packet when a complete
  14-slate window and missing attribution/diversity can be evaluated. No
  documented execution-cost adjustment exists; the thin positive historical
  delta is not sufficient margin for a production plan.

### Active candidate: selective LEAN

**Frozen hypothesis:** displayed LEAN, K line 2.5–3.5, capped quality and
model-fades-market-favorite is a narrow expansion opportunity.
`expand_lean_low_line_capped_model_fade`, fingerprint
`4e00a180e35fe75dc8889d47065a25c4351cb37ac55664eb42f01b77c07fd13a`.
[Plan](../superpowers/plans/2026-08-14-selective-lean-prospective-audit.md);
[review](selective-lean-preclose-review.md).

- Eligibility: August 15+ only; August 13–14 is a non-credit freeze gap.
  Unique tracked win/loss rows need exact pre-30 timing, consumed operational
  lock ID/time/artifact proof, provider/agreement and required slice fields.
  Post-start, recovered, duplicate and missing-proof rows fail closed.
- Floors: 75 eligible, 20 UNDER, 10 plus-price, positive prospective/latest-14
  PnL and leave-one-slate-out minimum; no negative mandatory slice at n>=10.
- Historical through August 12: 103, 55–48, +11.415935u (+11.08%); current
  provider 56, 28–28, +2.999676u (+5.36%), at quoted odds only.
- Prospective: last explicit eligible count 0/75; September 2 remains input
  blocked. Missing consumed-ledger fields cannot be fixed by waiting for more
  games. No prospective or fully costed selection return is established.
- Decision: **retain frozen definition, pause repeated performance narration**.
  Next useful decision is a separately scoped Gate C consumed-lock enrichment.
  Revisit after proof exists, not after an arbitrary number of calendar days.

### Active comparison candidates: Alt V2 Consensus Core and Re-entry Expansion

[V2 design](../superpowers/specs/2026-07-22-alt-picks-dependency-aware-v2-design.md)
freezes bundle `pregame_alternative_pick_methodology_v2` and fingerprint
`23bacff0fa923685ae52c5a9cfbadfb9f5902fb64d91759cfe9b4b1169a221c4`.
Consensus requires no-drag support and at least two agreeing evidence
families. Re-entry requires source-FIRE moderate-edge/quality support and
no-drag=false; lanes are disjoint. Pending nonessential families are allowed
only through the frozen dependency logic, never counted as affirmative votes.

Eligibility is immutable selected `frozen_pregame` V2 rows, before start,
with exact candidate/artifact and consumed-lock lineage. Provisional, pending,
V1 and reconstructed missed freezes receive no V2 credit. First selected V2
freeze is July 24. The [review cadence](../superpowers/specs/2026-07-21-pregame-alternative-pick-methodology-design.md#review-cadence)
calls for a directional read at 25 frozen picks and formal paired review at
75 or season end, across side, line, price, verdict, provider era, Path B,
workload, quality, timing, model/market, CLV and rolling windows. It supplies
no automatic profitability/promotion threshold or universal side-count floor.

| Lane | Historical official-close nomination (hindsight-capable) | Current prospective selected-frozen result through September 3 |
| --- | --- | --- |
| Consensus Core | 152, 106–46, +32.603u | 77 frozen: 38–38, one void, **-11.089692u**, -14.592% on 76 risked units |
| Re-entry Expansion | 80, 42–38, +5.982u | 36 frozen: 11–25, **-13.799495u**, -38.332% |
| Disjoint total | 232, 148–84, +38.585u | 113 frozen: 49–63, one void, **-24.889187u**, -22.222% on 112 risked units |

The notebook independently verifies 113 unique identities, one history match
each, exact line/odds/game time, consistent result versus actual Ks, matching
fingerprint, pre-start capture and consumed-lock linkage. No mismatches were
found in these checks. This does not revalidate every evaluation-proof primitive.

Both sides lose: OVER -15.112082u/56; UNDER -9.777106u/57 including the void.
Plus-price rows lose -12.36u/27; minus-price lose -12.529187u/86. Latest 14
selected slate dates: 39, 14–25, -14.069724u. Every leave-one-selected-slate-out
total is negative (-27.654785u to -19.889187u). K=4.5 contributes -16.680807u;
the positive 5.5 slice (+2.965436u/28) is retrospective and cannot define a new
prospective candidate without a new freeze.

On these same selected rows, displayed FIRE exposure is only 26 FIRE 1u rows,
-1.979032u; hypothetically adding the 87 LEAN rows contributes -22.910156u
(86 nonvoid units). This is a paired exposure comparison, **not** the full
mainline portfolio, equal-risk experiment, or causal estimate.

Attribution limitations: 111/113 recorded books are FanDuel; provider posture
is a routing label, not exact execution-provider identity. The captured narrow
read does not complete Path B/workload/quality/model-market/final-CLV slices
or accepted-fill attribution. The 17-row direct-TheRundown posture slice
at +0.345116u cannot identify a provider advantage. No execution fees or
infrastructure costs are allocated; the shown negative paper result worsens
under positive costs.

**Decision: no promotion; formal paired review due now.** Recommend pausing
expansion/re-entry promotion work and routine celebration of the +38.585u
historical comparator. Retain immutable V2 collection/comparison behavior as
currently configured. Complete the named missing slices for a formal
retain/retire research decision; do not wait for another generic volume floor.

### Active process candidate: final-CLV target and pre-close proxy

**Hypothesis:** runtime-safe pre-lock proxy strength predicts beating the
official close. Final CLV is the outcome label, never a selector input.
[Plan](../superpowers/plans/2026-07-29-clv-process-target-validation.md);
[current review](clv-process-target-review.md).

- Eligibility: explicit bounded close packet with exact consumed lock and
  same provider/book/event quote; close strictly after lock, before start,
  fresh within 20 minutes. Missing close is unknown. Movement rollups are not
  close packets; accepted-bet execution CLV is a separate metric.
- Floors: 100 attributed current-provider targets and positive strong-proxy
  lift in two consecutive complete 14-slate windows, plus mandatory slices.
- Current packet: August 25–26, 42 locks -> 33 eligible targets and nine exact
  pre-lock quote exclusions. All 33 resolve to TheRundown. Two beat, 29
  neutral, two worse; strong proxy has six rows, two beat/four neutral.
  Zero complete 14-slate windows. Logan Webb's Gate C book disagreement stays
  a descriptive warning; exact lock line/odds/time match.
- Historical CLV-supported 277, 155–122, +19.01u is outcome-selected process
  context; recent 30 lose -4.64u. Neither is a prospective trading result or
  profit after execution costs.
- Decision: **keep_as_process_kpi**, no proxy-design promotion. Retain exact
  exclusions; revisit only with a separately approved bounded packet meeting
  coverage/window criteria. Repeated runner `proxy_failed` without a supplied
  packet is expected missing input, not evidence to keep rerunning it.

### Projection and interaction research inventory

| Candidate/family and frozen hypothesis | Eligibility and requirements | Results, costs, attribution and justified decision |
| --- | --- | --- |
| `market_shrink_25`: lambda 25% toward posted K line | Stored runtime-safe shadow metadata; paired unique pitcher-game error. [Retirement plan](../superpowers/plans/2026-07-29-market-shrink-retirement-decision.md) supersedes the old betting-promotion path. | July 28: 578 paired games, MAE 1.9472 -> 1.8932 (+0.0540 K lift). Associated tracked metadata portfolio 605, 300–305, -42.56u; current provider -39.81u and recent -27.47u. Zero applied rows; no verdict-change metadata, so this is not an enforced challenger portfolio. Zero marginal provider calls/new DB rows, ~10 microseconds/calculation; measured history payload +5.2%, today +9.5%. **Retain diagnostic-only; betting path closed.** Revisit only if error lift disappears or metadata cost becomes material. [Evidence](market-shrink-retirement-review.md). |
| `market_shrink_15` / `market_shrink_35`: 15%/35% market-line shrink | [Gate F plan](../superpowers/plans/2026-06-03-gate-f-projection-challenger-shadow-plan.md): 800 clean official-close sides or explicit waiver; holdout MAE improvement >=0.025, RMSE deterioration <=0.010, side-accuracy deterioration <=0.5pp; two nonnegative rolling windows, all slices/no FIRE 2u harm. Runtime freeze must precede prospective credit. | June 22 historical holdout 219 rows: MAE deltas -0.030/-0.063, side accuracy unchanged; no new frozen prospective betting portfolio or after-cost return documented. **Retain as projection controls, pause competing promotion narratives.** A later separate candidate definition/plan is required; historical holdout approval is not current live authority. |
| `high_line_temper`: subtract 0.55 K when line>=7.5 and projection above line | Same Gate F holdout/diversity rules; pre-lock features only. | June report MAE lift insufficient; no documented prospective freeze/after-cost performance. **Pause promotion work**, retain benchmark; revisit only on fresh holdout materiality/slice evidence. |
| `leash_cap`: subtract 0.55 K high/short leash or 0.25 medium | Same Gate F rules; forecast workload only, never actual IP/BF. | Historical lift insufficient and slice failures; no eligible prospective or cost-adjusted return established. **Pause promotion work**, retain miss-attribution diagnostic. |
| `handedness_bucket_adjust`: train-only matchup adjustment | Runtime-confirmed lineup proof required; reconstructed boxscore handedness is hindsight. Gate F requirements above. | Hindsight-blocked, no prospective/after-cost record. **Pause promotion**, retain historical explanatory analysis. Do not confuse it with the existing live Path B canary. |
| Workload/no-vig/referee-v2 interactions | [Synthesis plan](../superpowers/plans/2026-06-08-workload-no-vig-k-projection-ev-synthesis.md); frozen runtime-safe rule and Gate E/F before selection credit. Gate E: 500 sides, 30 slates, 75 checkpoint rows, 50 per OVER/UNDER FIRE/LEAN group, 25 each price sign. | These are candidate families/slice labels, not additional frozen profitable strategies. No current separately attributed prospective after-cost result found. Actual opportunity is postgame explanation. **Retain one shared decomposition, pause broad repeated searches** until a specific input or hypothesis changes. |
| Market agreement | [Tracker plan](../superpowers/plans/2026-06-07-market-agreement-tracker.md): 75 movement-backed graded rows overall, 50 per bucket; pre-lock timing, era/source attribution and Gate E/F still apply. | A reusable attribution label, not a standalone live selector. Unknowns and correlated book/provider observations cannot be counted as independent confirmation. No after-cost incremental execution result established. **Retain bounded compact enrichment**, not duplicate raw trackers. |

### Existing live controls and retired candidates

| Item | Current justified treatment |
| --- | --- |
| Quality gates, market-favorite confidence referee and profit rescue | Existing live downside controls, not new promotion candidates. Retain applied-count and cap-chain integrity plus paired avoided-loss/foregone-win evaluation. The [referee plan](../superpowers/plans/2026-06-05-market-favorite-confidence-referee-production-canary.md) had a documented 16-row waiver (234/250 validation); do not generalize that waiver. The [rescue plan](../superpowers/plans/2026-06-10-profit-rescue-and-strict-provider-readiness.md) caps remaining 2u, UNDER and market-fade FIRE. Historical rescue +42.42u avoided exposure is not independent prospective net profit; effects overlap earlier caps. No control is altered here. |
| Path B | [Approved existing live canary](../superpowers/plans/2026-06-07-batter-handedness-path-b-canary.md): trusted PA-backed real splits, per-batter Path A fallback, no double platoon adjustment. Retain coverage/fallback integrity. Promotion-quality causal value still needs paired Path A/B confirmed-lineup holdout lift and parent Gate F diversity; no separately allocated after-cost effect is established. Morning missing lineups are not failed splits. |
| No-drag v1 | **Retired promotion path**, immutable audit/control retained. Frozen July 21+ test: 75, 41–34, -4.883u; latest 14 selected dates -7.361u; every leave-one-slate-out negative. Historical 186/+29.200u and current-provider baseline 52/+9.170u are separate. Issued [August 19 decision](2026-08-10-no-drag-strict-runtime-decision.md) overrides older `ready_for_review` counters. Baseline drift must stay visible without reopening a failed experiment. Revisit only under an approved materially different frozen hypothesis. |
| Four non-shortlisted FIRE-matrix controls | `cap_market_fade`, OVER/moderate-EV/normal-leash, market-agreed/moderate-EV/pre-30, and Strong Base/anchor union remain controls. Market-fade has only one incremental current-era row; union overlaps strict core 85.7% and adds only 16 historical rows/+2.801u. The two specialists' +21.259u/+20.057u historical results are nomination evidence. No separate new prospective/after-cost success. Keep comparisons on demand; no parallel promotion work. |
| Other LEAN/PASS expansions, next-season simulation/stuff/arsenal ideas | Exploratory/watchlist only; no current frozen eligible prospective candidate established in the controlling map. Broad PASS expansion was negative. Preserve catalogs and historical tests, defer new searches until a distinct decision and prospective design exist. |

## Work to retain, pause or retire from routine attention

These are proposed attention/cadence changes, **not changes to the running
research command, provider collection, or production flags**.

| Treatment | Work | Decision it still informs / trigger |
| --- | --- | --- |
| Retain daily, concise | Fresh artifact hashes and data-through dates; grading/lock reconciliation; sender failures/dedupe; live-source age; Gate C integrity and candidate eligibility delta | Detect actual operational failure or newly usable evidence. Show missing/unavailable checks explicitly. |
| Retain bounded/on changed evidence | Exact market-anchor paired audit; two frozen FIRE policies; strict specialist and selective-LEAN eligibility; compact agreement enrichment | A gate, input, diversity or incremental-value change. Do not count overlapping controls as independent discoveries. |
| Retain periodic | Storage/row growth, exact compact coverage, provider usage, billing/cost reconciliation | Existing 70%/cost triggers, material growth or missing source coverage. Completed cleanup is not physical shrink. |
| Retain one diagnostic | Pitcher-level market-shrink MAE and workload/Path B miss attribution | Explain projection error or detect loss of previously measured error lift. |
| Review now; pause expansion narrative | Alt V2, especially Re-entry | 75-freeze trigger already passed; negative prospective and recent results. Complete formal paired/slice decision rather than collect indefinitely. |
| Pause repetitive output | CLV target invocation/reporting with no explicit close packet; selective LEAN performance discussion with no lock-proof fields | Resume upon an approved valid input packet/enrichment. A repeated expected blocker is not new evidence. |
| Pause broad recurring discovery | Multiple Strong Base/portfolio/synthesis/hindsight-ceiling reports narrating the same corpus; weak Gate F challenger promotion reads | Keep dependency-producing steps until mapped; move redundant narrative to on-demand only after a separate runner review. Resume for new frozen hypothesis or materially changed holdout. |
| Retire from active brief | No-drag promotion progress; market-shrink betting promotion; BoltOdds cutover readiness; old GitHub-vs-Render scheduled-timing race | Decisions already made. Retain code, raw historical records and control outputs; revisit only on explicit new hypothesis/trial or actual regression. |
| Retire completed actions | First Mac transfer checks, September 2 grading-repair dispatch, first-partition/tranche cleanup approvals, completed 82-partition queue | Closure evidence already exists. Keep archive links, not daily requests to repeat work. |

The runner currently invokes overlapping reports and emits a CLV failure when
its separate packet is absent. This review recommends a later dependency-aware
runner simplification, not immediate skip-flag or cron edits. Keep the canonical
Gate C build and compact inputs even when downstream narrative is paused.

## Next decisions by lane

| Lane | Next decision | Evidence needed | Revisit trigger |
| --- | --- | --- | --- |
| Pipeline / infrastructure | Continue ordinary operation; scope recovery/transport work only on failure | Natural-run outputs, served hashes, due/consumed locks, sender outcomes; separate GitHub grading hydration proof if fallback is reopened | Missing/stale expected artifact, unconsumed due lock, repeat timeout, sender error, usage pressure |
| Model | Formal Alt V2 paired retain/retire review; keep all new promotions closed | Existing 113-row proof plus full mainline comparator and missing quality/Path B/workload/model-market/CLV slices; current hosted counters for other candidates | Alt review is due now; others only when eligible attribution/diversity or frozen-window evidence changes |
| UI | Retain display/comparison function; assess integrity and usefulness separately from profit | Current mobile/desktop interaction, exact proof/asset/endpoint contract, stale/missing-input clarity | User confusion, contract mismatch or missing/incorrect freeze; no redesign triggered by a winning/losing day |
| Tracking / data collection / history | Prioritize consumed-lock research linkage and bounded backlog diagnosis; monitor storage after completed cleanup | Exact lineage fields, supported-class backlog age, capture/processing rates, current size and per-scope compact coverage | Eligibility remains zero because of missing fields; continued backlog/growth; separately scoped collection/retention decision |

September is an AGENTS umpire-name-audit trigger. Retain a YTD **name/coverage**
review against the [July 30 audit](2026-07-30-umpire-ytd-name-audit.md); do not
re-seed the production cache or promote noisy YTD deltas. Current `ump_scale=0`
means this is coverage/preparation work, not an immediate projected-profit fix.

Confidence is high in the preserved current Alt/lock/storage/publication
records and cited frozen decisions; limited for current hosted candidate slice
counts, provider invoices, execution costs, sender delivery and mobile UX.
Those limits identify the next evidence to obtain, not a reason to change a
production rule.
