# CLV Process Target Review

Date: 2026-07-30

## Decision

`keep_as_process_kpi`.

Final CLV remains an offline target for testing pre-lock evidence. It is not a
selector, verdict, price, stake, provider, notification, lock, dashboard, or
retention input. No proxy-design plan is warranted yet.

## What the post-grading review now does

After the market-agreement report and the existing pre-close proxy report, the
research runner builds the canonical CLV target from only:

- the Gate C pitcher-outcome dataset; and
- the bounded read-only compact `market_pick_evidence` export.

It writes ignored research output only. The runner log is deliberately limited
to coverage, strong-proxy lift, current-provider drift, and readiness. It
never prints rows or recommends a pick action. The explicit
`--skip-clv-process-target-validation` flag is for a separately run review.

## Current evidence status

The local checkout has a Gate C corpus, but it did not have the paired bounded
compact `market_pick_evidence` export at review time. The local Gate C manifest
also names an older source window through 2026-06-16. Running the target against
that missing input would create zero eligible targets, which is an availability
failure, not a CLV result. Therefore this review does not infer close provenance
from archive fields or claim a new coverage, lift, PnL, or calibration result.

The next normal post-grading run with
`--refresh-market-agreement-inputs` is the first valid packet for this report.
Missing close evidence must remain `unknown`; it must never be treated as a
loss, neutral close, or reconstructed value.

## Compact operator scoreboard

| Review surface | Current verified state | Required before a proxy-design discussion |
| --- | --- | --- |
| Fully attributed current-provider targets | Not measured from a paired current packet | At least 100 eligible targets since 2026-06-24 |
| Strong pre-close proxy lift | Not measured from a paired current packet | Positive in two consecutive complete 14-slate windows |
| Provider drift | Not measured from a paired current packet | Current-provider review must not be hidden by historical-era results |
| Final-close provenance | Paired compact export unavailable locally | Same provider, same book, fresh timestamped official close |
| Slices | Not measured from a paired current packet | Side, price, K line, timing, quality, Path B, workload, provider, agreement, and rolling windows all reviewed |

The historical `evidence_clv_supported` reference (`277`, `155-122`, `+19.01u`,
`+6.9%`) is a process benchmark only. The recent 30-row `-4.64u` result blocks a
performance claim from CLV support alone.

## Read rule

Only a valid `ready_for_proxy_design` output can justify drafting a separate,
Tyler-approved proxy-design plan. That later plan must still keep final CLV,
closing line/price, graded result, actual Ks, and actual workload out of runtime
selector inputs. It does not authorize a runtime change by itself.
