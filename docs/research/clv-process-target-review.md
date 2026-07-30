# CLV Process Target Review

Date: 2026-07-30

## Decision

`keep_as_process_kpi`.

Final CLV remains an offline target for testing pre-lock evidence. It is not a
selector, verdict, price, stake, provider, notification, lock, dashboard, or
retention input. No proxy-design plan is warranted yet.

## What the post-grading review now does

After the market-agreement report and the existing pre-close proxy report, the
research runner can build the canonical CLV target only from:

- the Gate C pitcher-outcome dataset; and
- a separately supplied bounded read-only official-close provenance packet.

`market_pick_evidence` is a movement rollup for agreement/pre-close research,
not close evidence. `--refresh-market-agreement-inputs` continues to refresh
only that movement/agreement export and does not create or imply a close
packet. The runner validates an explicit JSON/JSONL close packet before
invoking the target diagnostic. Missing, unreadable, malformed, or
wrong-schema packets leave the bounded runner result at `proxy_failed` and do
not stop later shadow reports.

It writes ignored research output only. The runner log is deliberately limited
to coverage, strong-proxy lift, current-provider drift, and readiness. It
never prints rows or recommends a pick action. The explicit
`--skip-clv-process-target-validation` flag is for a separately run review.

## Current evidence status

There is no approved producer for the paired official-close packet. The local
Gate C manifest also names an older source window through 2026-06-16. Passing a
movement export to the target would create a permanently unusable close source,
not a CLV result. Therefore the default runner readiness is `proxy_failed`, and
this review does not infer close provenance from archive fields or claim a new
coverage, lift, PnL, or calibration result.

An explicitly approved close-packet producer and validated packet are required
before the target can run. A valid explicit empty packet is allowed; it creates
`unknown` targets. Missing close evidence must remain `unknown`; it must never
be treated as a loss, neutral close, or reconstructed value.

## Compact operator scoreboard

| Review surface | Current verified state | Required before a proxy-design discussion |
| --- | --- | --- |
| Fully attributed current-provider targets | Not measured from a paired current packet | At least 100 eligible targets since 2026-06-24 |
| Strong pre-close proxy lift | Not measured from a paired current packet | Positive in two consecutive complete 14-slate windows |
| Provider drift | Not measured from a paired current packet | Current-provider review must not be hidden by historical-era results |
| Final-close provenance | No approved paired close-packet producer; refreshed movement exports are insufficient | Same provider, same book, fresh timestamped official close after lock |
| Slices | Not measured from a paired current packet | Side, price, K line, timing, quality, Path B, workload, provider, agreement, and rolling windows all reviewed |

The historical `evidence_clv_supported` reference (`277`, `155-122`, `+19.01u`,
`+6.9%`) is a process benchmark only. The recent 30-row `-4.64u` result blocks a
performance claim from CLV support alone.

## Read rule

Only a valid `ready_for_proxy_design` output can justify drafting a separate,
Tyler-approved proxy-design plan. That later plan must still keep final CLV,
closing line/price, graded result, actual Ks, and actual workload out of runtime
selector inputs. It does not authorize a runtime change by itself.
