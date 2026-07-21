# No-Drag Composite Prospective Canary Packet

Date: 2026-07-21

Status: frozen post-grading research canary. This is not live promotion approval.

## Executive Decision

Track `combined_runtime_broad_no_hindsight_no_drag_v1` as the lead research candidate beginning with the 2026-07-21 slate. Preserve `strict_runtime_core_plus_selective_lean` as the comparison/control.

## Locked Baseline

| Read | Rows | Record | Units | ROI |
| --- | ---: | ---: | ---: | ---: |
| Clean window through 2026-07-20 | 186 | 124-62 | +29.20u | +15.7% |
| Current-provider starting point | 52 | 36-16 | +9.17u | +17.6% |
| Recent 14-slate reference | 35 | 24-11 | +5.68u | +16.2% |

The review floor is 75 current-provider candidate rows, so the prospective canary begins with 23 additional rows required.

## Frozen Contract

Record selector fingerprint `22b03ecea02aa83e9174c24f5f05878823cb67766fe1c75102d34bfe5c3b4aa4` and state that any semantic change requires a new ID, fingerprint, baseline, and counter.

## Daily Read

Read the Markdown/JSON audit after Gate C and Shadow Signal Synthesis. Treat duplicate keys, baseline drift, and prospective critical-input gaps as blocking integrity states. A stale committed Gate C file is expected to block locally; the scheduled post-grading builder must refresh the corpus before the production audit.

## Review Floor

At 75 rows the strongest allowed status is `ready_for_review`. Promotion still requires a separate Tyler-approved plan and survival across FIRE/LEAN, side, K-line, price, quality, Path B, model/market, workload, market agreement, pre-close proxy, final CLV, provider, and rolling-window slices.

## Live Boundary

The canary cannot change model math, verdicts, thresholds, staking, providers, notifications, locks, UI, retention, artifacts, calibration, source-of-truth behavior, environment variables, or `formula_change_date`.
