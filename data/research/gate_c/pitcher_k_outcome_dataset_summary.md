# Pitcher K Outcome Dataset Summary

Shadow-only: this dataset does not change live picks, locks, thresholds, staking, provider order, notifications, or calibration.

- Total rows: `2070`
- Clean-window rows: `2070`
- Graded rows: `2070`
- Rows missing result: `0`
- Duplicate dataset keys: `0`
- Missing team/opponent: `0`
- Missing book odds: `0`
- Missing model fields: `2`
- Tracked pick rows: `1075`
- Rows with price CLV: `1075`
- Beat-close price rows: `181`
- Beat-close line rows: `18`
- Rows with lineup hand counts: `1174`
- Rows with actual IP: `1718`
- Rows with actual pitch count: `1718`
- Rows with batters faced: `1718`
- Rows with market agreement labels: `0`
- Rows with market book counts: `300`
- Rows with toward/away counts: `0`
- Rows with live display book-board fields: `300`
- Rows with explicit official odds source: `1944`
- Rows with explicit official market-source mode: `594`
- Rows with explicit official line-source provider: `594`
- Broad market confirmation rows: `63`
- Best off-market rows: `101`
- Large-edge skepticism rows: `466`
- Clean graded picks reconciled: `1075/1075`
- Unique side fallback reconciliations: `32`
- Unmatched clean graded picks: `0`
- Archive outcomes recovered from one exact graded history row: `25`
- Ambiguous archive outcome matches left excluded: `0`

## Context Snapshots

- `official_close`: `2070`

## Model Vs Market Relationship

- `model_agrees_with_favorite`: `958`
- `model_fades_favorite`: `1034`
- `unknown`: `78`

## CLV Types

- `line_only`: `18`
- `no_clv_edge`: `876`
- `not_tracked`: `995`
- `price_only`: `181`

## Process Outcome Buckets

- `good_process_loss`: `87`
- `good_process_win`: `112`
- `unknown`: `995`
- `weak_process_loss`: `455`
- `weak_process_win`: `421`

## Bet Timing Windows

- `post_start`: `46`
- `pre_120`: `5`
- `pre_15`: `166`
- `pre_30`: `747`
- `pre_5`: `49`
- `unknown`: `1057`

## Opportunity Buckets

- `deep_starter`: `232`
- `normal`: `1678`
- `short_leash`: `160`

## Leash Risk Buckets

- `high`: `160`
- `medium`: `78`
- `normal`: `1832`

## Pitcher Archetype Buckets

- `deep_starter`: `144`
- `high_k_deep_starter`: `88`
- `high_k_standard`: `492`
- `low_k_standard`: `122`
- `short_leash`: `160`
- `standard_starter`: `1064`

## Lineup Handedness Sources

- `missing`: `896`
- `mlb_boxscore_reconstructed`: `1174`

## Actual Opportunity Sources

- `missing`: `352`
- `mlb_boxscore_reconstructed`: `1718`

## Market Agreement Labels

- `missing`: `2070`

## Movement Strength Labels

- `missing`: `2070`

## Live Display States

- `market_fade`: `20`
- `missing`: `1770`
- `mixed`: `22`
- `monitor`: `89`
- `off_market`: `42`
- `playable_now`: `31`
- `stale`: `96`

## Official Odds Sources

- `boltodds+propline`: `594`
- `missing`: `126`
- `propline`: `4`
- `therundown`: `1208`
- `therundown+propline`: `60`
- `therundown+the_odds`: `78`

## Official Market-Source Modes

- `boltodds_propline`: `594`
- `missing`: `1476`

## Official Line-Source Providers

- `boltodds`: `568`
- `missing`: `1476`
- `propline`: `22`
- `therundown`: `4`