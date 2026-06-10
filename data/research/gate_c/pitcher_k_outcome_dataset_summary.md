# Pitcher K Outcome Dataset Summary

Shadow-only: this dataset does not change live picks, locks, thresholds, staking, provider order, notifications, or calibration.

- Total rows: `1718`
- Clean-window rows: `1718`
- Graded rows: `1718`
- Rows missing result: `0`
- Duplicate dataset keys: `0`
- Missing team/opponent: `0`
- Missing book odds: `0`
- Missing model fields: `2`
- Tracked pick rows: `886`
- Rows with price CLV: `886`
- Beat-close price rows: `138`
- Beat-close line rows: `17`
- Rows with lineup hand counts: `1174`
- Rows with actual IP: `1718`
- Rows with actual pitch count: `1718`
- Rows with batters faced: `1718`
- Rows with market agreement labels: `195`
- Rows with market book counts: `281`
- Rows with toward/away counts: `195`
- Rows with live display book-board fields: `223`
- Broad market confirmation rows: `42`
- Best off-market rows: `75`
- Large-edge skepticism rows: `390`
- Clean graded picks reconciled: `887/887`
- Unique side fallback reconciliations: `29`
- Unmatched clean graded picks: `0`

## Context Snapshots

- `official_close`: `1718`

## Model Vs Market Relationship

- `model_agrees_with_favorite`: `790`
- `model_fades_favorite`: `866`
- `unknown`: `62`

## CLV Types

- `line_only`: `17`
- `no_clv_edge`: `731`
- `not_tracked`: `832`
- `price_only`: `138`

## Process Outcome Buckets

- `good_process_loss`: `68`
- `good_process_win`: `87`
- `unknown`: `832`
- `weak_process_loss`: `372`
- `weak_process_win`: `359`

## Bet Timing Windows

- `post_start`: `46`
- `pre_120`: `5`
- `pre_15`: `165`
- `pre_30`: `603`
- `pre_5`: `49`
- `unknown`: `850`

## Opportunity Buckets

- `deep_starter`: `190`
- `normal`: `1392`
- `short_leash`: `136`

## Leash Risk Buckets

- `high`: `136`
- `medium`: `64`
- `normal`: `1518`

## Pitcher Archetype Buckets

- `deep_starter`: `122`
- `high_k_deep_starter`: `68`
- `high_k_standard`: `420`
- `low_k_standard`: `100`
- `short_leash`: `136`
- `standard_starter`: `872`

## Lineup Handedness Sources

- `missing`: `544`
- `mlb_boxscore_reconstructed`: `1174`

## Actual Opportunity Sources

- `mlb_boxscore_reconstructed`: `1718`

## Market Agreement Labels

- `market_against_model`: `32`
- `market_mixed`: `62`
- `market_no_signal`: `63`
- `market_with_model`: `38`
- `missing`: `1523`

## Movement Strength Labels

- `broad_against_model`: `7`
- `broad_with_model`: `6`
- `missing`: `1523`
- `mixed_or_reversed`: `108`
- `no_movement_signal`: `63`
- `single_book_against_model`: `6`
- `single_book_with_model`: `5`

## Live Display States

- `market_fade`: `16`
- `missing`: `1495`
- `mixed`: `17`
- `monitor`: `66`
- `off_market`: `30`
- `playable_now`: `22`
- `stale`: `72`