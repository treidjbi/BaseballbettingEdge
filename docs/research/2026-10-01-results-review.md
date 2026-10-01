# 2026 season results: time and team review

Built October 1, 2026. Review only; no provider calls, grading, model rebuild, or production change.

## Finding

The clean April 28–September 27 published FIRE population lost **45.03 flat units on 797 settled picks (-5.65% ROI)**. June alone contributed 21.06 units of that loss; May added 15.24. July and September were positive, but only 53 and 73 settled FIRE rows. Smaller volume and changed selection mean those months are not evidence that the same system became reliably profitable.

LEAN lost **140.96 units on 1,980 settled rows (-7.12% ROI)**. This is a separate model exposure population, not proof those bets were taken. All tracked exposure was 1,384 wins, 1,393 losses, and 80 voids, totaling -185.99 units. Tyler's account PnL remains unresolved; none of these figures represents his accepted-bet ledger.

## Scope and reproducibility

The controlling data is `analytics/reviews/2026-10-01/sources/published_history.json`, a read-only copy of an already stored October 1 15:08Z publication, later than the 13:17Z freeze. It is **not byte-identical to the freeze**. The copy contains 4,102 rows, spans March 25–September 27, and exactly reconciles the freeze's clean-period counts, published-verdict FIRE/LEAN wins/losses, and PnL. This validates those aggregates, not every field against the earlier unavailable file.

Local file SHA-256: `8bf31bab45755358caae6092936116e81fb8c0ddd42adfb622f12b2efc833741`. The separately recorded source payload hash uses its own serialization; see source provenance. Gate C SHA-256: `4b44d70d1bcae23be35354ec9ea9b84886f62642c4900fd56c4e65817748a8cd`.

Run from the repository root:

```sh
python3 analytics/reviews/2026-10-01/results/analyze_results.py
```

The stdlib-only script reads local files and writes `results_summary.json` plus month, ISO-week, pitcher-team, opponent-team, side, and month-by-side CSVs for FIRE, LEAN, and their union, both all-published and clean-period scopes. Every partition reconciles to its parent totals; all 2,777 clean settled history identities match the research corpus. It imports no pipeline module and contains no network or grading call.

**Accounting:** published `pnl` is flat 1u risk per settled selection. Every settled row matches the win/loss formula at `locked_odds` when present, otherwise `odds`; there are zero mismatches. FIRE 2u labels do not mean this published PnL was doubled. ROI denominator is settled picks (1u each); void/cancelled rows return zero and are excluded from risk. This is not actual stake-weighted performance.

**Classification:** tables use published `verdict`, matching the freeze. Substituting `locked_verdict` moves Kevin Gausman's May 22 loss from FIRE to LEAN and Cade Cavalli's August 19 win from LEAN to FIRE. Locked FIRE becomes -43.31u, 410-387 on the same 797 settled count. This is a classification sensitivity, not a changed outcome. Before 2027, the dashboard and research should explicitly name their verdict basis.

**Teams:** exact date/pitcher/side links to Gate C supply unambiguous full pitcher-team and opponent-team names. This avoids ambiguous early history labels such as “New York.” All clean settled rows are linked. Unmatched/void rows remain UNKNOWN; historical pre-April-28 team tables have substantial UNKNOWN coverage and must not be interpreted as complete team rankings.

## Month by month

April below means April 28–30 only; September ends September 27.

| Month | FIRE settled | FIRE W-L | FIRE PnL | FIRE ROI | LEAN settled | LEAN PnL |
|---|---:|---|---:|---:|---:|---:|
| 2026-04 | 48 | 22-26 | -5.80u | -12.09% | 17 | -13.62u |
| 2026-05 | 413 | 211-202 | -15.24u | -3.69% | 238 | +15.06u |
| 2026-06 | 136 | 63-73 | -21.06u | -15.49% | 477 | -66.29u |
| 2026-07 | 53 | 32-21 | +2.33u | +4.40% | 418 | -35.83u |
| 2026-08 | 74 | 39-35 | -6.01u | -8.12% | 464 | -13.21u |
| 2026-09 | 73 | 42-31 | +0.75u | +1.03% | 366 | -27.07u |

## Week by week

ISO weeks begin Monday; boundary weeks are clipped to the analysis window. Ten of 22 weeks were positive. The May 4–10 and June 1–7 weeks together lost 31.72u, about 70% of net FIRE loss. Weekly picks vary from 8 to 112, so raw weekly totals also measure exposure.

| ISO week | Settled | W-L | PnL | ROI |
|---|---:|---|---:|---:|
| 2026-W18 | 96 | 50-46 | -1.37u | -1.42% |
| 2026-W19 | 93 | 42-51 | -16.32u | -17.55% |
| 2026-W20 | 94 | 50-44 | +1.22u | +1.30% |
| 2026-W21 | 112 | 58-54 | +1.76u | +1.57% |
| 2026-W22 | 66 | 33-33 | -6.33u | -9.59% |
| 2026-W23 | 85 | 37-48 | -15.40u | -18.12% |
| 2026-W24 | 25 | 10-15 | -7.38u | -29.53% |
| 2026-W25 | 12 | 9-3 | +3.94u | +32.86% |
| 2026-W26 | 10 | 5-5 | -1.55u | -15.50% |
| 2026-W27 | 17 | 10-7 | +0.28u | +1.68% |
| 2026-W28 | 15 | 10-5 | +2.26u | +15.09% |
| 2026-W29 | 12 | 7-5 | +0.09u | +0.76% |
| 2026-W30 | 8 | 4-4 | -1.21u | -15.17% |
| 2026-W31 | 10 | 7-3 | +2.22u | +22.18% |
| 2026-W32 | 15 | 8-7 | -1.15u | -7.65% |
| 2026-W33 | 17 | 5-12 | -8.08u | -47.51% |
| 2026-W34 | 17 | 9-8 | -1.39u | -8.18% |
| 2026-W35 | 19 | 13-6 | +3.62u | +19.08% |
| 2026-W36 | 20 | 9-11 | -4.49u | -22.44% |
| 2026-W37 | 21 | 14-7 | +3.44u | +16.37% |
| 2026-W38 | 15 | 11-4 | +4.45u | +29.68% |
| 2026-W39 | 18 | 8-10 | -3.65u | -20.27% |

## Team concentration

Pitcher team and opposing lineup team answer different questions. Do not conflate them. Full 30-team tables are in JSON/CSV.

| Dimension | Team | Settled FIRE | PnL |
|---|---|---:|---:|
| Pitcher team | San Diego Padres | 35 | -13.75u |
| Pitcher team | Los Angeles Angels | 22 | -9.74u |
| Pitcher team | St. Louis Cardinals | 31 | -7.58u |
| Pitcher team | New York Yankees | 30 | +7.33u |
| Pitcher team | Washington Nationals | 27 | +8.60u |
| Pitcher team | Philadelphia Phillies | 20 | +9.18u |
| Opponent team | Pittsburgh Pirates | 31 | -13.35u |
| Opponent team | Houston Astros | 25 | -9.65u |
| Opponent team | Athletics | 25 | -6.67u |
| Opponent team | Milwaukee Brewers | 25 | +4.83u |
| Opponent team | Atlanta Braves | 29 | +5.29u |
| Opponent team | Chicago Cubs | 28 | +6.10u |

These are descriptive concentration checks, not team blacklist rules. Each FIRE team slice has fewer than 50 observations, repeated pitchers, varying prices, and time/selection confounding. Ranking 30 teams after the season creates multiple-comparison bias.

## Interpretation and next comparison

UNDER contributed -34.30u on 316 settled FIRE picks; OVER contributed -10.72u on 481. This directs paired projection/price diagnosis toward UNDER, but does not establish an OVER-only rule. Every table carries sample size, ROI, and descriptive 95% Wilson win-rate bounds. Those bounds assume independent outcomes, do not adjust for correlated slates/pitchers or many comparisons, and are not a profit-confidence interval.

The full published March 25–September 27 FIRE scope is -35.30u on 1,339 settled rows (-2.64% ROI). Its pre-clean-regime history must remain separate; pooling it improves the headline while mixing older model/data behavior.

Next: pair the exact same rows across projection error, line, side, price, movement, and realized outcome; then test candidate rules chronologically with realistic price availability. Keep post-hoc team and winning-month patterns as hypotheses. Reconcile actual accepted stakes externally before making any account-return claim.
