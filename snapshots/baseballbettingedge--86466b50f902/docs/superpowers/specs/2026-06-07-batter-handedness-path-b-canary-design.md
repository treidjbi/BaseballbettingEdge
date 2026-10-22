# Batter Handedness Path B Canary Design

## Purpose

Promote batter handedness from collection-only research into a reversible live
canary that can use real batter split samples when they are available before
lock.

This is a model-input change, so it must stay feature-flagged and auditable.
It does not change global thresholds, staking, provider order, notifications,
locks, retention, calibration, or dashboard source-of-truth behavior.

## Mode

Add:

```text
BATTER_HANDEDNESS_MODE=path_a|path_b
```

- `path_a`: current behavior. Use aggregate batter K% plus the existing
  league-average platoon adjustment.
- `path_b`: use real cached batter split samples for batters with the needed
  `vs_R` or `vs_L` PA-backed `k_rate`. Fall back per batter to Path A when the
  trusted split is missing.

The code default remains `path_a` so rollback is one environment-variable
change.

## Runtime Data Rule

Path B may use `data/batter_splits_YYYY.json` only when rows came from the live
split-sample collector. It must not read the historical lineup-handedness
backfill as a live model input. The backfill remains research evidence.

Trusted split sample:

- cache row exists for the batter's `mlbam_id`
- needed split key exists for the pitcher's hand: `vs_R` for RHP, `vs_L` for
  LHP
- split object has numeric `k_rate`
- split object has `pa > 0`

## Projection Rule

For each confirmed lineup batter:

- If Path B has a trusted real split for the needed side, use that `k_rate`
  directly and do not add `PLATOON_K_DELTA` again.
- Otherwise, use the existing Path A fallback:
  aggregate batter K% or league average plus `PLATOON_K_DELTA`.

This avoids double-counting handedness. Real splits already include the
handedness matchup.

## Artifact Metadata

Pitcher rows should expose:

- `batter_handedness_mode`
- `lineup_split_source`
- `lineup_real_split_count`
- `lineup_path_a_fallback_count`

These fields let the daily brief distinguish true Path B usage from fallback
rows.

## Promotion Read

Once enabled, the first clean full slate is a canary, not proof. Keep watching:

- count of rows using `real_split_cache`
- count of fallback rows
- result impact by over/under, K-line, FIRE/LEAN, and confidence-referee cap
- whether Path B changes pick count or verdict mix unexpectedly
