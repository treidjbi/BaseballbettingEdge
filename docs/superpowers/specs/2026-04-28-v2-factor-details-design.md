# V2 Factor Details Design

Date: 2026-04-28
Status: Proposed

## Goal

Improve the v2 pick detail sheet so it does two jobs well:

1. Explain a pick clearly to a bettor in the default view.
2. Expose enough structured factor detail to spot missing, neutral, or suspicious lambda inputs without turning the whole sheet into a debug dump.

This design adds a collapsible `Factor details` section beneath the existing `Why this bet` summary.

## Problem

The current `Why this bet` section is helpful but incomplete:

- It shows only a few contextual signals.
- It does not clearly distinguish between `active`, `neutral`, and `missing` factors.
- It makes it harder to debug whether a pick is strong because of real supporting inputs or because many factors silently fell back to neutral.

At the same time, a full always-open debug panel would overwhelm the mobile sheet and make the product feel internal rather than polished.

## Chosen Approach

Use a hybrid detail model:

- Keep the current short `Why this bet` section visible by default.
- Add a collapsed `Factor details` block under it.
- When expanded, show all major lambda drivers and data-health signals in one structured list.

This gives us bettor-readable explanation first, and model-debug visibility on demand.

## Alternatives Considered

### 1. Minimal expansion

Add only a few more visible rows to `Why this bet`.

Why not chosen:
- Too weak for debugging.
- Still leaves us guessing which factors were neutral or missing.

### 2. Hybrid summary + collapsible details

Keep the summary compact, add a deeper panel on demand.

Why chosen:
- Best balance of readability and debugging value.
- Works well on mobile.
- Lets us spot broken inputs without cluttering every card.

### 3. Always-open debug panel

Show every factor all the time.

Why not chosen:
- Too noisy for normal use.
- Hurts scanability and visual hierarchy.
- Makes the sheet feel like an internal dashboard instead of a product.

## User Experience

### Default visible section

The existing `Why this bet` section remains compact and human-readable. It should keep showing the short list of signals most useful at a glance:

- Lineup
- Umpire
- Park factor
- Opp. K-rate (bats)
- Recent K/9 (L5)
- Season K/9
- Career K/9

This section answers: "Why does the model like this pick?" in a clean, non-technical way.

### Collapsible factor details

Below that, add a collapsed disclosure row:

- Closed label: `Show factor details`
- Open label: `Hide factor details`

When expanded, render a grouped factor list covering all major model inputs that materially inform lambda or pick confidence.

## Factor Details Content

The expanded section should include all major factors every time, not just active ones.

Each row should show:

- factor label
- factor value
- direction/tone for the picked side when meaningful
- status badge: `active`, `neutral`, or `missing`

### Groups

#### 1. Projection core

- Line
- Model lambda
- Raw EV ROI
- Adjusted EV ROI
- Edge

#### 2. Opponent context

- Opp. K-rate (bats)
- Handedness split context if available in the current model payload

If handedness detail is not currently present in v2 data, do not invent it in the UI. Mark it as deferred.

#### 3. Pitcher form

- Season K/9
- Recent K/9 (L5)
- Career K/9
- SwStr %
- SwStr delta K/9

#### 4. Environment

- Park factor
- Umpire assignment / ump K adjustment
- Lineup confirmation status

#### 5. Workload and rest

- Days since last start
- Last pitch count
- Rest K/9 delta

#### 6. Data health

- Overall `data_complete`
- Any major factor that is missing or neutral-fallback should visibly show that state

## Status Rules

Status badges should be deterministic and simple.

### `active`

Use when the factor is populated and materially participating in the model.

Examples:
- non-null park factor
- confirmed lineup
- nonzero SwStr delta K/9
- nonzero ump K adjustment
- populated days since last start

### `neutral`

Use when the factor is present but not moving the pick materially, or intentionally resolves to a neutral/default value.

Examples:
- park factor very close to 1.00
- rest K adjustment exactly 0
- SwStr delta K/9 exactly 0 with valid source data

### `missing`

Use when data is absent, unavailable, or still projected/unconfirmed.

Examples:
- umpire not assigned yet
- lineup still projected
- null park factor
- null recent rest/workload field

## Visual Design

The detail rows should remain consistent with the existing v2 sheet style:

- no large new cards
- no extra charts in this panel
- use the same stat-row rhythm and typography
- status badges should be compact pills aligned to the right or attached to the value

Suggested behavior:

- summary rows stay lightweight
- expanded panel uses subtle group headers
- negative/missing states should be visible but not alarming

## Data and Architecture

### Existing data

The current v2 flow already carries most of the required data or is close to it:

- lineup status
- ump K adjustment / umpire
- park factor
- opponent K-rate
- season/recent/career K/9
- SwStr fields
- days since last start
- last pitch count
- rest K/9 delta
- data_complete

### Expected implementation shape

- Keep `PickDetail` as the rendering owner.
- Add a helper that normalizes factor rows into a single display structure.
- Prefer a pure helper function over embedding large conditional trees directly in JSX.
- Use one source of truth for status derivation so summary and debug views cannot drift.

## Error Handling

The expanded section must degrade gracefully:

- If a factor is unavailable, render `missing` rather than omitting the row.
- If a factor is present but not meaningful, render `neutral`.
- Never crash or hide the whole section because one field is absent.

## Testing

Implementation should include small focused tests around:

- factor-row normalization
- status derivation (`active` / `neutral` / `missing`)
- rendering of missing fields
- collapse/expand behavior

Visual spot checks should confirm:

- compact summary still reads cleanly
- expanded view is scrollable and readable on mobile
- mixed healthy/degraded picks show the correct states

## Out of Scope

This design does not include:

- changing lambda math
- adding new model factors
- adding new charts to the factor panel
- rewriting the existing summary rows into a totally different layout

## Success Criteria

This change is successful if:

- a normal user still sees a clean explanation by default
- we can expand one card and quickly tell which major factors are populated, neutral, or missing
- debugging missing inputs no longer requires hunting through raw JSON for common cases
- the detail sheet remains mobile-friendly
