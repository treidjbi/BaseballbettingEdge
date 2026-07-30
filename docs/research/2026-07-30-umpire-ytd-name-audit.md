# 2026 Umpire YTD Name-Set Audit

Date: 2026-07-30

Status: **Coverage gap confirmed; production cache unchanged.**

## Scope

The read-only seed audit covered 2026-03-26 through 2026-07-30. It collected
1,627 completed MLB games across 127 dates, found 91 home-plate umpires, and
used a 2026 YTD league mean of 16.776 strikeouts per game. The audit output was
written only to ignored `analytics/output` paths. It did not overwrite
`data/umpires/career_k_rates.json`.

## Coverage

- Production cache names: 87
- 2026 YTD active names: 91
- Shared names: 83
- Active-name coverage: 83/91 (91.2%)
- Assignment coverage: 1,535/1,627 (94.3%)
- Active umpires missing from the production cache: 8, representing 92 games
- Production-cache names with no 2026 YTD assignments: Larry Vanover, Mark
  Carlson, Phil Cuzzi, and Tony Randazzo

| Missing active umpire | 2026 HP games | YTD K/game delta | Current maturity if added with sample metadata |
| --- | ---: | ---: | --- |
| Dexter Kelley | 13 | -0.622 | Developing |
| Dillon Wilson | 8 | +1.974 | Thin |
| Felix Neon | 6 | -0.776 | Thin |
| Jen Pawol | 11 | -0.231 | Developing |
| Louie Krupa | 8 | -0.401 | Thin |
| Steven Jaschinski | 10 | -0.976 | Developing |
| Tyler Jones | 14 | -0.991 | Developing |
| Willie Traynor | 22 | -0.549 | Developing |

No missing umpire reaches the existing 50-game mature threshold. Three remain
below 10 games and would be thin; the other five would still be developing.

## Stability warning

This audit is useful for name coverage, not for a wholesale coefficient
refresh. Among the 83 shared names, the median absolute difference between the
production delta and the 2026-only delta was 0.799 K/game; 32 differed by at
least 1.0 K/game and 46 changed sign. CB Bucknor's two-game YTD sample produced
an extreme +7.224 delta, which is a direct example of the small-sample risk.

These differences can reflect sampling noise, season/run-environment changes,
and differences between a career/multi-season prior and a partial-season
estimate. They do not justify replacing the live cache from this audit alone.

## Decision

Keep the production cache unchanged. The system is not broken: it recognizes
94.3% of 2026 assignments by game, and confirmed-but-unrated umpires already
fail closed to neutral input with an `unrated_umpire` quality flag.

The eight-name gap is large enough to warrant a separate, Tyler-approved input
review. That review should choose between continuing the current neutral
fallback and adding prior-smoothed multi-season entries with explicit sample
metadata. It must test quality-gate/cap effects and normal-slate outcomes before
any cache change. A one-season YTD reseed or direct use of the deltas above is
not recommended.
