# Shadow Model Review Checkpoint

Scheduled decision date: **2026-08-10**

This is a read-only, shadow-only review. It does not authorize changes to
lambda, verdict thresholds, staking, providers, notifications, locks,
artifacts, dashboard behavior, or retention.

## Current decision

**Keep all four candidates in their present evidence posture.** The review is
scheduled because the signals are worth preserving, not because any promotion
gate is open.

The no-drag early-review trigger fired on July 28. The read-only packet is
`docs/research/2026-07-28-no-drag-strict-runtime-core-review-packet.md`. It
does not replace this August 10 checkpoint or open a live gate.

| Candidate | Current high-signal evidence | Blocking evidence |
| --- | --- | --- |
| Market-anchor strict | July 28 selector audit: all strict `152`, `92-60`, `+4.27u`; strict displayed FIRE `28`, `20-8`, `+6.14u` | FIRE result remains all `OVER`; K-line, CLV, workload, provider, agreement, and rolling-window slices remain incomplete or mixed |
| Market-shrink | Live-metadata audit: `581`, `287-294`, `-41.50u`, with zero applied rows | Negative graded metadata result; paired projection-error and decision-changing proof remains insufficient |
| Moderate-edge / CLV | CLV-supported full slice `276`, `155-121`, `+20.01u`; current provider `55`, `33-22`, `+6.52u` | Recent slice is `14-16/-4.64u`; CLV remains post-close validation and needs timing, side, price, K-line, quality, provider, and rolling balance |
| No-drag composite | Canonical audit is `ready_for_review` at `75/75`; prospective July 21-27 is `23`, `15-8`, `+2.621u`, and all leave-one-slate-out reads remain positive | All prospective prices are minus money; FIRE 2u has zero rows; `-130` to `-149`, K=4.5, capped-quality, provider-attribution, and market-agreement gates remain weak or incomplete |

The July 28 figures use the scheduled full-corpus reports for canonical totals
and a complete public production-artifact reconstruction only for the July
21-27 prospective slices. The August 10 packet must rebuild from the approved
full production index with fresh compact provider/agreement enrichment.

Comparison/control breakout watch: `strict_runtime_core_flat` is `95`,
`63-32`, `+17.05u`; current provider is `19`, `14-5`, `+5.19u`; recent is
`17`, `14-3`, `+7.19u`. It remains `watch_more` because all 19 current-provider
rows are OVER at minus money and the controlling provider/agreement sample is
still small. The broader strict-plus-selective control has a negative recent
window at `16-18/-5.36u`.

## Review triggers

Run the packet on August 10, or earlier only if one of these objective triggers
fires:

1. no-drag reaches its controlling prospective sample floor with the frozen
   baseline and fingerprint fully reconciled (**fired July 28; packet written,
   live promotion still closed**);
2. market-anchor adds another complete 14-slate rolling window with materially
   better provider and market-agreement attribution;
3. market-shrink reaches the controlling holdout floor and a paired
   decision-changing counterfactual exists; or
4. moderate-edge / CLV adds enough prospective rows to evaluate all mandatory
   slices without a single-side or single-era concentration.

## Required packet

Rebuild or read the existing Gate C, market-anchor, market-shrink, Strong Base,
CLV-proxy, market-agreement, and no-drag outputs. Present four independent
decisions rather than one blended promotion recommendation. For each candidate,
report:

- exact sample and date range;
- prospective versus retrospective rows;
- over/under, plus/minus, K-line, FIRE 1u/FIRE 2u, quality, timing,
  model/market, Path B, workload, CLV, provider, agreement, and rolling-window
  slices;
- leave-one-slate-out or equivalent concentration control;
- current mode, applied rows, would-change rows, and paired-control result; and
- a blunt `keep soaking`, `draft separate plan`, or `retire candidate` result.

No candidate may move beyond shadow from this checkpoint. Any candidate that
survives the packet requires a separate Tyler-approved promotion plan with its
own rollback and production verification.

