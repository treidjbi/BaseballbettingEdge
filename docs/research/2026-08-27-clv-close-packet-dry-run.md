# Bounded Current-Provider CLV Close-Packet Dry Run

Date: 2026-08-27

Slate window: 2026-08-25 through 2026-08-26

Decision: `keep_as_process_kpi`

## Executive read

The offline close-packet path works on current TheRundown/PropLine-era data,
but it is not ready for recurring use or proxy design. Forty-two consumed
operational locks produced 33 exact official-close observations; the CLV
validator accepted 32. Nine locks had no exact pre-lock quote match in the
20-minute provenance window, and one accepted packet row exposed a real
operational-lock versus bet-time-book conflict. All exclusions remain
fail-closed.

This was read-only evidence synthesis. Database writes were zero. No model,
verdict, threshold, stake, provider order, notification, lock, artifact, UI,
retention, environment, or source-of-truth behavior changed.

## Inputs and packet integrity

| Evidence | Count |
| --- | ---: |
| Consumed operational locks | 42 |
| TheRundown/PropLine market snapshots | 339 |
| Gate C side rows / tracked rows | 84 / 45 |
| Eligible official-close packet rows | 33 |
| Fail-closed exclusions | 9 |
| BoltOdds packet rows | 0 |
| Database writes | 0 |

All 33 packet rows resolved to TheRundown. Independent reconciliation found 33
unique packet keys, 33 unique close observations, nine unique exclusion lock
references, zero packet/exclusion overlap, and complete coverage of all 42
bounded locks. Every packet row matched its operational lock, exact
provider/book/event/line/price provenance snapshot, official Gate C provider,
and timestamp order: strictly after lock, strictly before first pitch, and no
more than 20 minutes old at game time.

The packet fingerprint is
`882a84849586a1f45efb1d8e7f059a59814e44a4cf24bb49b8ce437322911d36`.
The ignored local dry-run outputs are under
`analytics/output/clv_close_dry_run_2026-08-25_2026-08-26/`.

## Exclusions

The nine exclusions are Bryce Elder OVER, Ethan Pecko OVER, Gage Jump UNDER,
Michael King OVER, Tyler Glasnow OVER, Peter Lambert UNDER, Robert Stock UNDER,
Roki Sasaki OVER, and Sean Burke UNDER. Eight had a same-line price mismatch
against the operational lock; Peter Lambert had a different line. These are
real exact-quote gaps, not missing pitcher/event identity rows. The producer's
exact match was not weakened.

## Validator result

The target validator classified 32 rows as eligible, one as `book_mismatch`,
and the remaining 51 Gate C rows as `identity_mismatch` because no close packet
row existed for that pitcher/side identity. Eligible final-CLV labels were two
`beat_close_price`, 28 `neutral_close`, and two `worse_close_price`.

The one book mismatch is Logan Webb UNDER on August 26. The operational lock
ledger and close packet use FanDuel, while Gate C's `bet_time_book` is
DraftKings at the same 5.5 line and -106 price. The validator correctly kept
the row unknown. A wider packet needs an explicit contract decision about
whether final CLV follows the operational lock or the accepted/bet-time book;
the code must not guess or weaken same-book matching.

The validator needed one narrow research-reader correction: when legacy
provider fields are absent, it now accepts Gate C's exact single-provider
`official_line_source_provider` or `official_odds_source`. Composite provider
values remain ineligible as exact lock attribution.

## Readiness and affected audits

- Fully attributed current-provider targets: `32/100`.
- Complete 14-slate windows: zero; this packet spans two slates.
- Strong pre-close bucket: six evaluated, two beat / four neutral / zero worse.
  Its apparent 27.1-point lift is a tiny-sample observation, not a breakout or
  promotion signal.
- Market-anchor bounded read: seven strict rows, `5-2`, `+1.71u`; strict
  displayed FIRE was `2-0`, `+1.57u`. The sample is tiny, strict FIRE is all
  OVER, agreement is missing, and negative K-line/pre-close slices remain.
- Market-anchor downside: five would-change rows, `4-1`; applying the cap would
  have reduced PnL by `1.804u`. Decision remains `keep_shadow`.
- Strict runtime: the two-day partial input intentionally failed the frozen
  baseline and lacked the canonical enrichment needed for a meaningful
  candidate read. Its existing hosted status and `20/50` counter are unchanged.

## Next gate

Do not schedule or widen the producer yet. First review the operational-lock
versus bet-time-book definition. Any later wider validation still requires at
least 100 fully attributed current-provider targets, positive strong-proxy lift
in two consecutive complete 14-slate windows, and side, price, K-line, timing,
quality, Path B, workload, provider, agreement, rolling-window, and
leave-one-slate-out survival. All model and behavior-changing gates remain
closed.
