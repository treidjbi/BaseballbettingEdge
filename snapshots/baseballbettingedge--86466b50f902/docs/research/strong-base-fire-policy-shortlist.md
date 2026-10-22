# Strong Base FIRE Policy Shortlist

Date: 2026-07-29

Status: **Two research candidates frozen; prospective counters start July 30; no live selector.**

This packet does not authorize verdict, threshold, stake, provider,
notification, lock, artifact, UI, retention, environment-variable, or
source-of-truth changes.

## Frozen prospective shortlist

| Family | Candidate | Historical reason | Prospective counter |
| --- | --- | --- | ---: |
| Downside cap | `cap_high_raw_edge` | `926`, `428-498`, `-122.20u`; `429` rows remain genuinely incremental after the current cap stack | 0/75 |
| Retained FIRE | `strict_runtime_core_flat` | `96`, `64-32`, `+17.727u`; current provider `15-5/+5.864u`; recent `14-3/+7.106u` | 0/75 |

Only fully graded rows dated July 30 or later advance these counters.
Historical results identify the policies and remain locked context.

## Why these two

`cap_high_raw_edge` has more incremental downside value than the market-fade
control. Its `429` incremental FIRE rows are `205-224`, flat `-51.360u`; using
the existing FIRE unit exposure, a hypothetical cap would have avoided
`64.719u`. `cap_market_fade` remains a control at `272` incremental rows,
`111-161`, flat `-40.767u`, and `49.934u` of risk-weighted avoided loss. It has
only one current-provider incremental row because the active confidence
referee already handles almost all market-fade FIRE exposure.

`strict_runtime_core_flat` is the simplest high-quality retained-FIRE rule.
The Strong Base/market-anchor union is `112`, `75-37`, `+20.528u`, but overlaps
the strict core on `96/112` rows (`85.7%`). Its 16 unique historical rows add
`+2.801u`, which is promising but too small to justify the more complex rule.
Under the plan's overlap rule, the union remains a control.

The two broader retained-FIRE specialists also remain controls:

- OVER/moderate-EV/normal-leash: `198`, `120-78`, `+21.259u`; current provider
  `+3.268u`; recent `+1.581u`.
- Market-agreed/moderate-EV/pre-30: `170`, `110-60`, `+20.057u`; current
  provider `+0.498u`; recent `-0.137u`.

## Readiness rule

Each frozen candidate must independently reach `75` prospective graded rows,
positive current-provider and latest-14 value, positive prospective
leave-one-slate-out minimum, complete provider/agreement/CLV attribution, and
no negative mandatory slice with at least 10 rows. The retained policy may
only keep an existing FIRE; it cannot promote LEAN or PASS. The downside policy
may only reduce existing FIRE exposure.

Reaching `75` opens a Tyler review, not activation. Any survivor needs a
separate behavior-changing canary plan and explicit approval.
