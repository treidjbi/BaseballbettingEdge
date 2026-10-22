# CLV Process Target Review

Date: 2026-07-30

Updated: 2026-08-27

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

An approved offline producer exists at
`analytics/diagnostics/clv_official_close_packet.py`. It consumes bounded lock
and market-snapshot exports, optionally uses Gate C's exact official-provider
field to resolve otherwise ambiguous TheRundown/PropLine matches, and writes a
packet, exclusions, and manifest with zero database writes. It is not wired to
the recurring runner. Passing a movement export to the target would still
create a permanently unusable close source, not a CLV result.

The first bounded current-provider dry run covered August 25-26. It reconciled
`42` consumed operational locks to `33` exact official-close observations and
`9` fail-closed exclusions. The approved contract anchors process CLV to the
consumed operational lock. The packet now carries its exact provider, book,
line, odds, timestamp, source artifact path, and artifact hash. The validator
accepted all `33` targets. Logan Webb UNDER retains a descriptive Gate C
DraftKings-versus-FanDuel book warning, while line, odds, and timestamp agree
exactly. The result is `33/100` fully attributed current-provider targets
across only two slates, so readiness remains `keep_as_process_kpi`; no complete
14-slate window or performance claim exists.

Accepted-bet CLV is a separate future execution metric, not a substitute for
the operational-lock process target. The bounded read found no accepted bets
in the August 25-26 packet window. Any accepted-bet analysis needs its own
pairing and review contract.

Each target run still requires its own explicitly validated packet. A valid
explicit empty packet is allowed; it creates `unknown` targets. Missing
close evidence must remain `unknown`; it must never be treated as a loss,
neutral close, or reconstructed value.

## Compact operator scoreboard

| Review surface | Current verified state | Required before a proxy-design discussion |
| --- | --- | --- |
| Fully attributed current-provider targets | `33/100` from the August 25-26 packet | At least 100 eligible targets since 2026-06-24 |
| Strong pre-close proxy lift | Six evaluated rows: `2` beat / `4` neutral / `0` worse; only two slates | Positive in two consecutive complete 14-slate windows |
| Provider drift | All 33 eligible targets are current-era TheRundown observations | Current-provider review must not be hidden by historical-era results |
| Final-close provenance | `33/42` exact packet rows; nine exact pre-lock quote gaps; all 33 reconcile to the consumed lock; one descriptive Gate C book warning | Same provider, same book, same event, fresh timestamped official close after lock |
| Slices | Generated for the bounded packet, but the sample/window floors are not met and agreement is uninformative | Side, price, K line, timing, quality, Path B, workload, provider, agreement, and rolling windows all reviewed |

The historical `evidence_clv_supported` reference (`277`, `155-122`, `+19.01u`,
`+6.9%`) is a process benchmark only. The recent 30-row `-4.64u` result blocks a
performance claim from CLV support alone.

## Read rule

Only a valid `ready_for_proxy_design` output can justify drafting a separate,
Tyler-approved proxy-design plan. That later plan must still keep final CLV,
closing line/price, graded result, actual Ks, and actual workload out of runtime
selector inputs. It does not authorize a runtime change by itself.
