# V2 Line Movement And Card Cues Design

## Goal

Improve the v2 pick-detail sheet so line movement reflects real stored market history instead of fabricated interpolation, and tighten directional visual cues on the card/detail UI.

## Scope

This design covers four UI changes only:

1. Replace the fake line-movement bars in the v2 detail sheet with a real chart sourced from `dashboard/data/processed/steam.json`
2. Default the chart to the model-picked side's `FanDuel` odds history
3. Include K-line movement in the same movement module so line changes are visible alongside odds movement
4. Add visual directional parity and one more evidence cue:
   - blue left rail for `OVER` cards
   - park factor shown in the "Why this bet" section

This design does **not** change:

- pipeline storage contracts
- model logic
- verdict thresholds
- staking
- the overall card layout beyond the directional cue update

## Current Problem

The current v2 sheet shows a synthetic bar strip that interpolates from opening to current values. It is visually nice, but it is not truthful. We now have better opening-line tracking and persisted intraday snapshots in `steam.json`, so the UI should show the real movement path.

At the same time, the card language is visually asymmetric:

- `UNDER` picks already read strongly because of the red left rail
- `OVER` picks do not have an equally strong directional cue

And the "Why this bet" section now surfaces lineup, ump, opponent K-rate, and recent K/9, but it is missing park factor even though that is now part of the live model context.

## Data Contract

### Source of truth

Use `dashboard/data/processed/steam.json` as the line-history source.

Current structure is sufficient for this UI pass:

- top-level `snapshots`
- each snapshot has:
  - `t`
  - `pitchers`
- `pitchers` is keyed by pitcher name
- each pitcher entry includes:
  - `k_line`
  - `FanDuel.over`
  - `FanDuel.under`
  - optionally other books

### Charted series

For the currently opened pitcher detail sheet:

- main series: picked-side `FanDuel` odds over time
- secondary series: K-line over time

If the model pick is `OVER`, use `FanDuel.over`.
If the model pick is `UNDER`, use `FanDuel.under`.

### Empty-state rules

If there are fewer than two usable `FanDuel` snapshots for the selected pitcher:

- do not fabricate movement
- show a clean empty state such as `Not enough FanDuel history yet`

If snapshots exist but the picked-side odds are missing:

- show the same empty state
- keep the opening/current text rows above the chart

## UI Design

### Detail-sheet movement section

Keep the current textual rows:

- Opening line
- Current line

Replace the fake bars below them with a compact chart module:

- header text like `FanDuel · picked side · open to now`
- primary line: picked-side odds history
- secondary stepped track: K-line history
- if the K-line changed, show a small helper badge:
  - `line moved 4.5 -> 5.5`

This should stay mobile-first:

- compact height
- no heavy axis chrome
- timestamps can be sparse/minimal
- emphasis on shape and endpoint, not charting complexity

### Card directional cue parity

Update the card rail styling so:

- `UNDER` keeps the existing red cue
- `OVER` gets a blue cue of comparable visual weight

This should affect the main pick card only and preserve current verdict badge behavior.

### "Why this bet" addition

Add a park factor row to the detail sheet evidence section alongside lineup and ump.

Suggested display shape:

- label: `Park factor`
- value:
  - numeric park factor
  - small delta or interpretation cue if it supports the picked direction

The park factor row should follow the same tone rules as the other evidence rows:

- positive tone if it supports the pick
- negative tone if it works against the pick
- neutral/dim if unavailable

## Behavior Rules

### Picked-side chart logic

The chart is intentionally opinionated:

- it follows the side the model actually picked
- it does not try to show both over and under odds at once

That keeps the view aligned with the model decision instead of turning the sheet into a generic sportsbook explorer.

### K-line visualization

K-line movement should be shown as a stepped series because line values change discretely.

Odds should be shown as a continuous line between snapshots for readability, even though the source is sampled.

### Reliability principle

Never synthesize historical points.

If `steam.json` history is sparse, we prefer a modest empty state over a misleading visual.

## Files expected to change

- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2-app.jsx`
- `C:/Users/TylerReid/Desktop/Claude-Work/BaseballBettingEdge/dashboard/v2-app.js`

Possible supporting change only if needed:

- movement helper logic inside the same files
- CSS rules already co-located in the dashboard UI bundle if this app keeps styling there

No pipeline or storage changes are required for this scoped UI pass unless implementation reveals a concrete missing field.

## Testing / Verification

Implementation should verify:

1. A pitcher with at least two `FanDuel` snapshots shows a real chart
2. A pitcher with insufficient history shows the empty state instead of fake bars
3. `OVER` cards render a blue left rail
4. `UNDER` cards keep the red left rail
5. Park factor appears in the "Why this bet" section without breaking mobile layout
6. The sheet still works for live, pregame, and final states

## Recommendation

Implement this as a tight UI truthfulness pass, not a broader dashboard redesign.

The highest-value outcome is making movement honest and readable now that opening tracking is better, while also making directional cues and evidence display feel more complete.
