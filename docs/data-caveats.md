# Data caveats for picks_history.json

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
  in commit [fill-in after your commit] via
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
