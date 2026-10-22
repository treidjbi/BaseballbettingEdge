# No-Drag and Strict Runtime Prospective Decision

- Scheduled review date: 2026-08-10
- Issued: 2026-08-19
- Evidence through: fully graded 2026-08-18 slate
- Status: **No live promotion.**

This is the delayed packet required by the July 29 review plan. The filename
preserves the scheduled checkpoint; the issue date and evidence window above
prevent the decision from being mistaken for an August 10 contemporaneous
read.

## Executive Decision

- No-drag v1 outcome: **`retire`** from the active promotion path. Preserve the
  frozen audit and selector as a read-only research/control comparison; do not
  delete its code or evidence.
- Strict-runtime-core outcome: **`narrow_specialist_review`**. Its historical
  current-provider record is strong, but it is an OVER/minus-money profile
  with no credited post-freeze prospective evidence and does not justify a
  live or metadata-promotion plan.
- No candidate from this packet survives into runtime or environment work.
  Gate C/D/E/F/12E and every model, threshold, staking, provider,
  notification, lock, artifact, UI, retention, and source-of-truth promotion
  gate remain closed.

## Evidence Hierarchy and Integrity

The scheduled 2026-08-19 Render research run is canonical for counter and
integrity status. It rebuilt `4,164` Gate C source rows and `2,184` tracked
rows, reconciled `2,115/2,115` graded picks with zero duplicate keys, and
reported no-drag `ready_for_review` at `127/75`. Strict runtime remained
input-blocked at `20/50`.

A separate production-artifact reconstruction through August 18 loaded
`3,184` source rows and `1,679` tracked rows, reconciled `1,610/1,610` loaded
graded picks, and had zero duplicates. It could not load 23 early dated
artifacts, so its blocked full-history reconciliation is not canonical and
does not replace the hosted counter. Its July 21-August 18 prospective window
is complete, its 52-row current-provider starting baseline reconciles, and it
is used below only for prospective, rolling-window, and mandatory-slice reads.

Both reads preserve the frozen selector id
`combined_runtime_broad_no_hindsight_no_drag_v1`, fingerprint
`22b03ecea02aa83e9174c24f5f05878823cb67766fe1c75102d34bfe5c3b4aa4`,
and the exclusion of 25 history-recovered rows from candidate credit.

## No-Drag v1

### Scoreboard

| Read | Rows | Record | PnL | ROI |
| --- | ---: | ---: | ---: | ---: |
| Locked historical baseline through July 20 | 186 | 124-62 | +29.200u | +15.7% |
| Locked current-provider starting baseline | 52 | 36-16 | +9.170u | +17.6% |
| Genuine prospective, July 21-August 18 | 75 | 41-34 | -4.883u | -6.5% |
| Current-provider baseline plus prospective | 127 | 77-50 | +4.283u | +3.4% |
| Latest 14 selected slate dates | 38 | 18-20 | -7.361u | -19.4% |

The genuinely prospective test reversed the locked historical result. Across
28 prospective slate dates, leave-one-slate-out PnL was negative in every
case: the range was `-7.101u` to `-1.883u`. The count floor therefore opens a
decision review; it does not produce a pass.

### Mandatory Slices

| Dimension | Prospective evidence | Decision read |
| --- | --- | --- |
| Verdict / stake | FIRE 1u `15`, `9-6`, `+0.432u`; LEAN `60`, `32-28`, `-5.315u`; FIRE 2u `0` | Small FIRE gain does not offset broad LEAN drag; FIRE 2u is untested. |
| Side | OVER `27`, `15-12`, `-1.182u`; UNDER `48`, `26-22`, `-3.701u` | Both sides are negative. |
| Price | All `75` are minus money. `-100` to `-129`: `-1.890u`; `-130` to `-149`: `-3.991u`; `-150` to `-200`: `+0.998u` | Plus-price survival is absent and two of three populated price buckets lose. |
| K line | `2.5-3.5` `+3.689u`; `4.5` `-9.074u`; `5.5` `-0.967u`; `6.5` `+1.469u` on two rows | The 33-row 4.5-K bucket is the dominant failure. |
| Quality | Clean `52`, `29-23`, `-1.767u`; capped `23`, `12-11`, `-3.116u` | Both quality states are negative. |
| Timing | Pre-30 `74`, `40-34`, `-5.716u`; one unknown-timing win | The approved timing profile does not rescue the result. |
| Model / market | Model-agrees `72`, `40-32`, `-3.768u`; unknown `3`, `1-2`, `-1.115u` | The intended agreement profile is negative. |
| Path B | Real-or-mixed `71`, `40-31`, `-2.532u`; no-real-splits `4`, `1-3`, `-2.351u` | Neither observed Path B bucket supports promotion. |
| Workload / leash | Normal `68`, `38-30`, `-2.961u`; high `4`, `2-2`, `-0.647u`; medium `3`, `1-2`, `-1.275u` | The normal-workload majority is negative. |
| Market anchor | Strict `49`, `27-22`, `-2.744u`; core `21`, `12-9`, `-0.819u`; none `5`, `2-3`, `-1.320u` | No anchor bucket is positive. |
| Pre-close proxy | Strong `64`, `37-27`, `-0.574u`; medium `11`, `4-7`, `-4.309u` | Strong proxy is near flat; medium proxy is materially negative. |
| Final CLV | Beat-close `8`, `3-5`, `-2.675u`; neutral/unknown `63`, `34-29`, `-5.020u`; worse-close `4`, `4-0`, `+2.812u` | Sparse, internally inverted CLV evidence fails the process gate. |
| Provider / agreement | All rows are in the approved TheRundown+PropLine era, but exact provider attribution and market-agreement labels are missing for all `75` reconstruction rows | Required attribution remains unresolved and cannot be inferred. |
| Rolling / concentration | Latest 14 selected slate dates `18-20`, `-7.361u`; every leave-one-slate-out result is negative | Deterioration is sustained rather than one-slate noise. |

### No-Drag Decision

Assign **`retire`**. The candidate reached the exact prospective count floor
and failed the prospective, recent-window, leave-one-slate-out, side, K-line,
quality, model/market, workload, anchor, and attribution tests. Continuing to
accumulate the same profile would not repair the failed frozen experiment.

Retirement here closes only the active promotion path. Keep the selector,
fingerprint, locked baselines, and audit available as a comparison/control so
future research can detect whether a genuinely new candidate merely recreates
the same drag.

## Strict Runtime Core

Strict runtime is frozen as `strict_runtime_core_flat`, fingerprint
`6d07a98031a8b26915ad34fc031def76d26519850dc476db723d37f25a8d9905`, with
prospective credit beginning July 30.

| Read | Rows | Record | PnL | ROI |
| --- | ---: | ---: | ---: | ---: |
| Current-provider history | 20/50 | 15-5 | +5.864u | +29.3% |
| Latest 14 selected slate dates | 17 | 14-3 | +7.106u | +41.8% |
| Credited post-July-29 prospective | 0 | 0-0 | +0.000u | 0.0% |

The current-provider history is concentrated: all 20 rows are OVER, minus
money, FIRE 1u, pre-30, and Path B. K-line results are `4-3/-0.266u` at
2.5-3.5, `6-2/+2.398u` at 4.5, `2-0/+1.434u` at 5.5, and `3-0/+2.298u` at
6.5. Clean quality is `7-2/+3.178u`; capped quality is `8-3/+2.686u`.
Normal workload is `15-4/+6.864u`; the only medium-workload row lost.
Model/market is `13-5/+4.094u` across `18` model-agrees rows; the `2`
unknown rows are `2-0/+1.770u`, and no model-fades rows are present.

Historical leave-one-slate-out PnL stays positive with a `+4.290u` minimum,
but that evidence predates the July 30 prospective boundary. The audit still
has zero UNDER, zero plus-price, zero FIRE 2u, zero provider-attributed, and
zero market-agreement-attributed rows; final CLV and pre-close proxy coverage
are also missing. The floor remains 30 rows short, and input gaps block fresh
prospective credit.

### Strict Runtime Decision

Assign **`narrow_specialist_review`**. Preserve the finding as a descriptive
OVER/minus retained-FIRE specialist, exactly as the controlling plan requires
when the product does not present the missing contexts. Do not weaken the
50-row, 10-UNDER, 10-plus-price, provider/agreement, CLV, rolling-window, or
leave-one-slate-out gates. Do not draft or activate a runtime selector from
this evidence.

## Closed Gates and Next Treatment

- Do not create a new no-drag implementation branch, selector version, model
  rule, threshold, stake rule, or environment flag.
- Keep the existing audits read-only. No redeploy is required for this
  documentation decision.
- Compress no-drag to a retired comparison/control line in routine briefs.
  Reopen only under a separately approved research design with a materially
  different frozen hypothesis and new prospective baseline.
- Keep strict runtime labeled as a narrow specialist observation, not a live
  candidate. Missing diversity and attribution are blockers, not optional
  gates.
- Keep market-anchor, Strong Base, selective LEAN, CLV-process, Alt V2, and
  other research trackers under their own controlling plans. This decision
  grants none of them promotion authority.

This packet changes documentation only. It does not change model behavior,
verdicts, thresholds, staking, providers, notifications, locks, artifacts,
dashboard behavior, accepted bets, history, retention, calibration,
`formula_change_date`, environment variables, or source-of-truth rules.
