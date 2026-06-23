# Next Season K Model Feature Catalog

This document is research-only. It does not change live lambda, thresholds, staking, providers, notifications, locks, retention, calibration, or dashboard source-of-truth.

## Feature Classes

| Class | Examples | Runtime-safe? | Hindsight-only? | Current source |
| --- | --- | --- | --- | --- |
| Identity | slate_date, pitcher, team, opponent, home_away, game_time | yes | no | Gate C dataset |
| Market price | side, K line, book, odds, no-vig side probability, market favorite side | yes when captured before lock | closing price is hindsight | TheRundown artifacts, PropLine sidecar, Gate C |
| Model state | lambda, model_lambda, edge, EV, adjusted EV, raw verdict, displayed verdict | yes | no | today/dated artifacts, Gate C |
| Quality and availability | lineup_used, quality_gate_level, data warnings, split source, umpire availability | yes | no | pipeline artifacts |
| Live movement | pregame movement with/against model, book count, better/worse now, broad confirmation | yes if timestamped pre-start | post-start movement is hindsight | market_pick_evidence, live_market_display_state |
| Timing and CLV | locked_at, accepted_bet_time, beat_close_price, beat_close_line | lock/accepted time is runtime context | close result and CLV are hindsight labels | picks_history, accepted_bets, Gate C |
| Baseball skill | season K/9, recent K/9, career K/9, SwStr, handedness, lineup K rate | yes when fetched pre-lock | actual result is hindsight | pipeline stats, FanGraphs cache, Path B |
| Workload and leash | rest, last pitch count, opener flag, pregame workload bucket | yes if known pre-lock | actual IP/pitches/batters faced are hindsight | pipeline stats, actual_opportunity_backfill |
| Context | park, umpire, weather/roof, run environment, game total | yes if known pre-lock | postgame environment adjustments are hindsight | pipeline + future source review |
| Seasonality | month, week, early/mid/late season, league K environment, starter ramp period | yes as shrunk prior if validated | using same-row result to assign effect is hindsight | seasonal audit + MLB-wide validation |

## Required Availability Labels

Every season-end row must carry:

- `available_pre_lock`: true when all fields in the candidate were knowable before lock.
- `runtime_feature_group`: one of `market`, `model`, `baseball`, `workload`, `quality`, `seasonality`, `timing`.
- `hindsight_explanation_only`: true for result, PnL, actual Ks, CLV, close price, actual opportunity, or post-start movement.
- `source_confidence`: one of `official_artifact`, `sidecar_pregame`, `manual_accepted_bet`, `reconstructed_postgame`, `missing`.

## Seasonality Rules

- Preserve early season, April/May/June/July/August/September, and final-month buckets separately.
- Compare app-picked rows to MLB-wide starter K/start before using month effects.
- Treat early-season under strength as a candidate regime, not as a permanent under bias.
- Treat later-season over/mixed behavior as separate from April.
- Include starter ramp-up, innings caps, call-ups, IL return, and team shutdown risk as possible seasonality explanations.
