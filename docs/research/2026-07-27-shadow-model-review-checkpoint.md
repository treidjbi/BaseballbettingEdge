# Shadow Model Review Checkpoint

Scheduled decision date: **2026-08-10**

This is a read-only, shadow-only review. It does not authorize changes to
lambda, verdict thresholds, staking, providers, notifications, locks,
artifacts, dashboard behavior, or retention.

## Current decision

**Keep all four candidates in their present evidence posture.** The review is
scheduled because the signals are worth preserving, not because any promotion
gate is open.

| Candidate | Current high-signal evidence | Blocking evidence |
| --- | --- | --- |
| Market-anchor strict | Partial through July 26: `147` graded rows, `90-57`, `+6.01u`; strict FIRE remains `27`, `20-7`, `+7.14u` | FIRE result remains all `OVER`; K-line, CLV, workload, provider, agreement, and rolling-window slices remain incomplete or mixed |
| Market-shrink | Partial rebuild: all Gate F shrink candidates improved MAE/RMSE on a `305`-row holdout, with `7` positive windows and zero bad slices | Below the default `800`-row discussion floor; no paired decision-changing profitability proof |
| Moderate-edge / CLV | Partial rebuild: moderate-edge-clean `39`, `29-10`, `+10.51u`; CLV-supported `111`, `62-49`, `+3.95u` | CLV is post-close validation evidence and the cohorts need provider, timing, side, price, K-line, quality, and rolling-window balance |
| No-drag composite | Partial prospective read: `19`, `13-6`, `+3.09u` | Audit was `blocked_baseline_drift`; the fail-closed operational counter and frozen fingerprint must reconcile before results are trusted |

The partial figures above are a scheduling baseline only. The August 10 packet
must rebuild from the approved full production index and must not overwrite the
canonical full-clean counts with a partial archive window.

## Review triggers

Run the packet on August 10, or earlier only if one of these objective triggers
fires:

1. no-drag reaches its controlling prospective sample floor with the frozen
   baseline and fingerprint fully reconciled;
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

