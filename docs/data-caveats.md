# Data caveats for picks_history.json

## 2026-04-17 — ump.news to MLB Stats API cutover

Prior to 2026-04-17, the pipeline scraped `www.ump.news` for HP umpire
assignments. That domain has been NXDOMAIN for the entire season (see
`analytics/diagnostics/a3_ump_adj.py` and the old
`pipeline/fetch_umpires.py` header). Every scrape raised, the warn-and-
return-empty path ran, and `fetch_umpires` returned `0.0` for every
pitcher. Net result: **100% (447/447) of historical picks have
`ump_k_adj == 0.0` exactly.**

On 2026-04-17 we swapped the source to the MLB Stats API schedule
endpoint with `hydrate=officials`
(`statsapi.mlb.com/api/v1/schedule?sportId=1&date={date}&hydrate=officials`)
and fixed a latent logic bug: `ump_ok` was previously `True` whenever
`fetch_umpires` didn't raise, even if every returned value was 0. After
2026-04-17, `ump_ok` is `True` only when at least one pitcher got a
real (nonzero) ump adjustment.

### Impact on stored fields

- **`ump_k_adj` in picks_history (pre-cutover):** 0.0 everywhere. This
  is accurate — the model saw a neutral ump signal because the source
  was dead.
- **`data_complete` in picks_history (pre-cutover):** `True` for rows
  that met the other-source checks (swstr_ok, etc.) even though the
  ump input was silently absent. **These rows were not rewritten.**
- **`data_complete` post-cutover:** reflects the corrected logic. On
  days where officials aren't posted yet or no HP ump is in the local
  career-rates table, `data_complete` will be `False`.

### Why the historical rows were not rewritten

Calibration uses `residual = actual_ks - stored_lambda`. Because
`ump_k_adj = 0` contributes 0 to `lambda`, residuals are identical
whether the pre-cutover `data_complete` flag said the pick had a real
ump signal or not. `lambda_bias` (~-0.55 and actively converging) is
therefore valid regardless of the flag bug; rewriting flags would only
reshape the `n` in the data_complete-filtered subset without changing
any calibrated parameter.

### Follow-up resolved: career_k_rates.json expansion (2026-04-20)

Originally noted: the pre-expansion table held 30 umps (including
retired names) against 62 live 2026 HP umps → ~21% match.

On 2026-04-20 we ran `scripts/seed_umpire_career_rates.py` against
the 2024-03-28 → 2025-10-01 regular-season window. The seeder pulls
every Final game's HP umpire via the `/schedule?hydrate=officials`
endpoint and per-game strikeout totals via `/game/{pk}/boxscore`,
then computes `delta = ump_mean_K_per_game - league_mean_K_per_game`.
Filter: `--min-games 20` to drop small-sample noise.

Result:
- 4,855 games aggregated, 96 unique HP umps seen
- 87 umps met the n≥20 filter and were written to `career_k_rates.json`
- League mean K/game across the window: 16.855
- Delta range: -1.40 (Shane Livensparger) to +1.93 (Ron Kulpa)
- Live 2026 match rate: 22% (11/51) → 94% (59/63 umps in the past week)
- Still missing (4): Felix Neon, Jen Pawol, Tyler Jones, Willie Traynor —
  likely AAA call-ups without enough 2024-25 MLB HP games to survive the
  min-games filter. They'll populate as their sample sizes grow.

Scale note: pre-expansion hand-curated deltas ranged ±0.52. Seeder-
derived deltas range ~±1.9 — wider because the hand-curated file was
conservatively scaled by the original author. This is **not** a unit
change — both are in "K per game vs league average." The calibrated
`ump_scale` parameter in `data/params.json` (currently 1.0) will shrink
to compensate during phase-2 calibration as more ump-signal residuals
land in the dataset. This is the same self-healing behavior that handles
any source-signal change.

## 2026-04-11 to 2026-04-17 — pitcher_throws bug window

A bug in `pipeline/fetch_stats.py` (fixed by commit `0407846`) caused the MLB
`/schedule` endpoint's `hydrate=probablePitcher` to silently fail to return
`pitchHand`. Every pitcher's `pitcher_throws` was forced to `"R"`.

### Impact
- **Model lambda at decision time:** computed with `pitcher_throws = "R"` for
  every pick in this window, regardless of actual handedness. The stored
  `lambda` field reflects this.
- **Platoon delta:** `calc_lineup_k_rate` applied the R-vs-lineup platoon
  delta uniformly. For LHPs facing lineups with above-average R/L split, this
  nudged `lambda` a few tenths of a K off.
- **Calibration:** `lambda_bias` has been converging against residuals
  computed from the (mis-handed) `lambda`. This is fine — calibration uses
  residual = actual − stored_lambda, which doesn't depend on pitcher_throws.

### Remediation
- **Fix:** commit `0407846` added a `/people/{id}` fallback.
- **Historical None rows (pre-2026-04-11):** backfilled in commit `517f473`
  via `/people/search`.
- **Post-cutover "R" rows (this window):** rewritten to correct handedness
  in commit `8463f8e` via
  `analytics/diagnostics/a1_rewrite_post_cutover_throws.py`. The stored
  `lambda` for these rows was NOT recomputed — it still reflects the value
  the model produced at decision time (with R-assumed platoon delta).

### Implication for analytics
- `pitcher_throws` in `picks_history.json` is now correct for the full
  history. Slicing by handedness (RHP vs LHP ROI, platoon-delta analytics)
  can treat the full dataset uniformly.
- BUT: `lambda` for picks in this window was computed with R-assumption.
  If an analysis recomputes lambda from inputs (rare), it should note this
  discrepancy. Most analytics only read the stored `lambda`, which is fine.
