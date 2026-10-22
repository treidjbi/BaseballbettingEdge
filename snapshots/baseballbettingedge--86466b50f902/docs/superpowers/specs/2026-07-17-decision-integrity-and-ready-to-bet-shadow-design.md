# Decision Integrity And Ready-To-Bet Shadow Design

## Purpose

Improve betting-decision trust and timing without changing model outputs,
provider order, staking, locks, grading, or current notification delivery.

This design has two coordinated parts:

1. keep alternate lines visible as market context while preventing them from
   becoming the compact actionable price or automatic accepted-bet default;
2. record a shadow-only `ready_to_bet` decision transition that can be reviewed
   before any new push notification or suppression behavior is considered.

## Approved Scope

Tyler approved both parts on 2026-07-17 after the first normal post-break slate
showed a clear operator-confusion case: a tracked 7.5K pick displayed a 2.5K
different-line offer as `Shop price`, and the Log Bet ticket automatically
defaulted to that different line.

The approved in-season posture is trust first, timing second:

- make the UI same-line safe now;
- collect timing evidence in shadow;
- do not add a live notification class or suppress an existing notification
  until the shadow sample is reviewed separately.

## Approaches Considered

### A. UI-only guard

Change labels and ticket prefill behavior but leave notification timing alone.
This is the lowest-risk option, but it does not measure whether a coordinated
`ready_to_bet` state would improve action timing.

### B. Direct live notification change

Immediately send a new `Ready to Bet` push and suppress reminders after an
accepted bet. This could improve timing faster, but it would test notification
behavior on Tyler rather than in shadow and could create redundant or missed
alerts.

### C. Same-line UI guard plus shadow timing state

Ship the trust fix as display/ticket behavior and add timing only as auditable
shadow evidence. This is the selected approach because it addresses the proven
confusion while preserving the current live sender until decision value is
demonstrated.

## Part 1: Same-Line UI Trust Boundary

### Row selection

The dashboard market adapter should preserve all supported-book rows, including
alternate lines. When choosing the single compact row for a pitcher and side,
it should rank a fresh row with `best_line == model_line` above a fresh row whose
best offer is on another K line.

The normalized live-market row should retain both concepts explicitly:

- `model_line`: the pick's artifact K line from the source row's `k_line`;
- `main_line`: the provider/book consensus line already used for market context.

Freshness remains the first gate. Within fresh rows, same-model-line availability
outranks recency, action label, book count, and provider preference. This keeps a
slightly newer alternate-line row from displacing an available same-line offer.

### Compact card copy

If the selected row's `best_line` differs from the model line:

- show `Alt-line context` instead of `Shop price`;
- use a neutral or warning tone, not a positive/action tone;
- keep the book, line, and odds visible so Tyler can still sanity-check the
  market;
- do not describe the row as playable or actionable.

If a fresh same-line offer exists, the existing same-line playable/shop-price
copy may continue to apply.

### Accepted-bet default

The automatic Log Bet prefill may use a live row only when all of these are true:

- the row is fresh;
- `best_book`, `best_line`, and `best_odds` are present;
- `best_line` matches the selected model side's K line;
- the existing playable-price/action checks pass.

If those checks fail, the ticket defaults to the artifact line, odds, and book
with `price_source=artifact`. Different-line book-board buttons remain available
for an explicit manual selection and must retain their `Different line` tag.

This changes only the default and labeling. It does not prevent Tyler from
manually logging an alternate-line bet.

## Part 2: Ready-To-Bet Shadow State

### State vocabulary

Each displayed tracked pitcher/side gets one current decision state:

- `watching`: not all readiness gates pass;
- `ready`: the shadow candidate qualifies now;
- `logged`: an accepted bet exists for the same slate, pitcher, and side;
- `locked`: the artifact/live pick is locked before game start;
- `started`: the game is in progress or final.

State precedence is:

```text
started > locked > logged > ready > watching
```

The precedence prevents a logged, locked, or started pick from reappearing as a
new timing opportunity.

### Ready qualification

A pitcher/side is `ready` only when every gate below passes:

- the displayed verdict starts with `FIRE`;
- `quality_gate_level == clean`;
- the game has not started;
- the pick is not locked;
- no accepted bet exists for the same slate, normalized pitcher, and side;
- a fresh supported live-market row has a non-null book and odds on exactly the
  model K line.

LEAN and PASS rows remain `watching`. Capped or blocked quality remains
`watching`. A better-looking alternate line does not satisfy readiness.

### Inputs

The pure decision-state builder consumes:

- current artifact pitcher rows for verdict and quality metadata;
- current `live_pick_state` rows for side, lock, and prior decision state;
- current `live_market_display_state` rows for fresh same-line availability;
- current-slate `accepted_bets` rows;
- the live-layer observation time.

The preferred market row for this shadow read uses the same trust rule as the
UI: fresh same-line combined TheRundown+PropLine first when available, then fresh
same-line TheRundown, then fresh same-line PropLine. Historical BoltOdds rows are
excluded.

### Outputs and persistence

The builder returns:

- current decision-state metadata for each `live_pick_state` row;
- a per-run summary with state counts and suppression reasons;
- a `ready_to_bet` shadow candidate only when a row transitions into `ready`.

Current state is stored inside the existing `live_pick_state.metadata` JSON.
The run summary is stored in
`shadow_pipeline_runs.metadata.ready_to_bet_shadow`. Transition candidates reuse
`shadow_notification_candidates`; no new table is added.

The shadow-candidate constraint must be extended to allow:

- `candidate_type='ready_to_bet'`;
- `provider='therundown_propline'` for a combined same-line row.

The candidate keeps the existing `candidate_action='would_send_shadow'` and
`playable_state='playable_now'` values. Its dedupe key is stable for the slate,
pitcher, and side:

```text
{slate_date}:ready_to_bet:{normalized_pitcher}:{side}
```

That permits at most one shadow opportunity per pitcher/side/slate and avoids a
new row every ten minutes.

### Feature mode

Add:

```text
LIVE_READY_TO_BET_SHADOW=off|record
```

- `off` is the code default and returns no candidates while leaving existing
  notification behavior untouched;
- `record` writes decision-state metadata and shadow candidates but never
  inserts `notification_events` rows.

The existing `LIVE_NOTIFICATION_COORDINATOR_MODE=grouped`, mainline best-price
notification policy, reminder behavior, and sender behavior remain unchanged.

## Data Flow

```text
today artifact + existing live state + live market rows + accepted bets
                              |
                              v
                 pure decision-state builder
                    |                    |
                    v                    v
       live_pick_state.metadata    ready transition only
                    |                    |
                    v                    v
       shadow_pipeline_runs       shadow_notification_candidates

No path writes notification_events or changes the artifact/model/lock.
```

## Failure Handling

The timing layer must fail closed and must not interrupt the existing live
layer:

- if `accepted_bets` cannot be read, record
  `accepted_bet_state_unavailable`, produce no `ready` transition, and continue
  existing notifications;
- if live-market rows are missing, stale, or lack a same-line offer, keep the
  row in `watching`;
- if artifact quality metadata is missing, treat quality as not ready;
- if the shadow-candidate upsert fails, report the shadow write error without
  changing or suppressing current notification rows;
- never infer `no accepted bet` from a failed database read.

The UI remains fail-soft: if the market endpoint fails, current artifact values
remain the ticket default.

## Testing Strategy

Implementation must use red-green TDD.

### UI tests

- a fresh same-line row outranks a newer fresh different-line row;
- an off-line row normalizes to `alt_line_context`;
- compact copy says `Alt-line context` and uses non-action tone;
- a different-line row cannot satisfy live ticket prefill;
- the fallback ticket uses artifact line/odds/book and
  `price_source=artifact`;
- a manually selected `Different line` book-board row still fills the editable
  ticket.

### Shadow-state unit tests

- clean, unlocked FIRE plus fresh same-line price becomes `ready`;
- LEAN, capped quality, stale market, different line, accepted bet, locked pick,
  and started game each fail the ready gate for the expected reason;
- state precedence is deterministic;
- only a transition into `ready` creates a candidate;
- the dedupe key is stable across live-layer ticks;
- BoltOdds-only evidence cannot qualify.

### Worker and schema tests

- default `off` mode is a no-op;
- `record` mode leaves `notification_rows` byte-for-byte unchanged;
- accepted-bet read failure produces no candidate and does not fail the worker;
- current state and summary metadata are persisted;
- the migration permits `ready_to_bet` and combined provider rows;
- existing notification coordinator, mainline-price, lock, accepted-bet, and
  live-market-display tests remain green.

### Dashboard verification

- rebuild `dashboard/v2-app.js` from `dashboard/v2-app.jsx`;
- run JavaScript syntax checks and focused Node/Python tests;
- smoke desktop and 390px mobile cards with both same-line and alternate-line
  fixtures;
- verify the detail book board still shows `Same line` and `Different line`;
- verify the Log Bet ticket defaults to artifact values when only an alternate
  live line exists.

## Rollout And Review

Deployment remains split by surface:

1. deploy and smoke the dashboard trust fix;
2. apply the additive Supabase constraint migration;
3. deploy the live-layer code with `LIVE_READY_TO_BET_SHADOW=off`;
4. verify existing notifications and locks are unchanged;
5. set `LIVE_READY_TO_BET_SHADOW=record` and redeploy the live layer;
6. review at least five normal slates before discussing a live timing change.

The shadow review should report:

- ready transitions by date and time-to-game;
- how often a same-line price was available;
- how often accepted-bet state would have prevented a redundant alert;
- overlap with existing `new_fire_pick`, `pick_upgraded`, start-window reminder,
  and mainline best-price notifications;
- false opportunities caused by late lineup changes, stale prices, or reversals;
- whether Tyler actually would have changed timing or action.

## Promotion Gate

No live `Ready to Bet` notification and no accepted-bet-based suppression is
approved by this design.

A later production review requires all of the following:

- at least five normal slates of shadow evidence;
- no stale, post-start, locked, different-line, or accepted-bet false candidate;
- evidence that the state would reduce confusion or improve timing beyond the
  existing notification classes;
- explicit Tyler approval of the exact send and suppression behavior;
- a separate rollback plan for the new notification class.

## Non-Goals

- No model, lambda, threshold, staking, calibration, or `formula_change_date`
  change.
- No provider-order, strict-provider, polling-cadence, or source-of-truth
  change.
- No lock timing or strict-lock change.
- No new live notification event type or sender behavior.
- No suppression of current FIRE, digest, reminder, or best-price alerts.
- No hidden removal of alternate-line context.
- No automatic bet placement.
- No new Supabase table or retention deletion.
- No BoltOdds runtime or evidence reactivation.

