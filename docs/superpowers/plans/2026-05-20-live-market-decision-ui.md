# Live Market Decision UI Plan

> **Status:** Phase 2 hidden live-read MVP plus existing Log Bet integration
> implemented 2026-06-07. Keep display-only and shadow-only; do not make
> default-on without Tyler approval.
>
> **Guardrail:** This plan must not change production provider order, model math,
> thresholds, staking, lock behavior, notification sends, retention, secrets, or
> source-of-truth rules. TheRundown-derived GitHub artifacts remain production
> truth until the provider cutover gates pass and Tyler approves the switch.
>
> **2026-06-04 update:** The active notification implementation child plan is
> `docs/superpowers/plans/2026-06-04-live-notification-digest-coordinator.md`.
> Build notification grouping and movement-strength labels first. This UI plan
> should consume the same decision labels and deep-link context rather than
> defining a separate market-action vocabulary.
>
> **2026-06-07 update:** Phase 1 is implemented behind `?marketSheet=1`.
> `dashboard/v2-data.js` accepts sanitized preloaded
> `window.V2_LIVE_MARKET_DISPLAY` rows and attaches them by slate date,
> normalized pitcher, and side. `dashboard/v2-app.jsx` adds a hidden
> actionable-card market strip and detail-sheet market panel. No live Supabase
> browser read, Netlify endpoint, provider/source-of-truth promotion,
> notification behavior, model math, thresholds, staking, lock behavior,
> retention, or dashboard default-on behavior changed.
>
> **2026-06-07 Phase 2 update:** `netlify/functions/live-market-display.mjs`
> now exposes a same-origin, server-side Supabase REST proxy for sanitized
> `live_market_display_state` rows. `dashboard/v2-data.js` fetches it only
> when `?marketSheet=1` is present, merges it with any preloaded fixture rows,
> and fails soft into normal dashboard rendering. The endpoint returns only an
> app-safe allow-list plus sanitized `book_rows` / `movement_events`; it does
> not expose raw provider payloads, service-role responses, secrets, unbounded
> snapshots, or production source-of-truth behavior. The market sheet remains
> hidden and display-only.
>
> **2026-06-07 bet-ticket update:** the existing `Log Bet` modal now pre-fills
> from a fresh live best-book row when the hidden market sheet has a playable /
> shop-price style row. The confirmed `accepted_bets` payload records
> `metadata.price_source` plus selected live provider/observed-at/action fields.
> Manual edits remain available and flip the price source to `manual_edit`.
> `/api/accepted-bets` also supports a secret-protected same-day read so the
> modal can show a read-only accepted-bet review and duplicate same-side warning.
> This is an audit/UI improvement only; it does not place bets or change stakes,
> picks, thresholds, provider order, notifications, locks, or source of truth.
>
> **2026-06-07 live-row review update:** real same-day rows showed two label
> consistency issues. `off_market` provider rows are now displayed as
> `Shop price` instead of generic `Monitor`, and fresh same-line live rows with
> a non-negative model fair-price cushion now display `Playable price` and can
> prefill the existing bet ticket. This remains a hidden UI/readout change only.
>
> **2026-06-07 alert-context update:** matched push/shadow-review deep links can
> now preserve `notification_event_id` / `shadow_candidate_id` into the manually
> confirmed `accepted_bets` payload. The URL context must match slate date,
> pitcher, and side before it is attached; it does not override ticket line,
> odds, book, units, or source-of-truth behavior.

## Goal

Use the new BoltOdds, PropLine polling, and PropLine webhook evidence to make
the dashboard answer one practical question faster:

**Can I still bet this pick at the current market, and where is the best price?**

The UI should improve decision speed and trust during the live slate without
turning shadow market evidence into live betting rules.

## Why This Now

The existing v2 dashboard already has a useful pick detail sheet, simple
open-to-current movement, accepted-bet logging, quality gates, and tracked-pick
lock display. That was enough when GitHub artifacts and TheRundown snapshots
were the only operational source.

The operational base is changing:

- `live_market_display_state` is now the app-ready shadow table for provider
  market state.
- `market_pick_evidence` rolls up per-pick provider movement.
- `current_market_lines` and `official_market_lines` exist for provider cutover
  rehearsal, but are not production.
- Real signed PropLine webhooks are landing, and the processor can write
  webhook movement into `line_movement_events` once observation is enabled.
- BoltOdds provides faster WebSocket movement for several target books, while
  PropLine remains useful for DraftKings/fallback/webhook comparison.

That combination supports a new read-only decision surface: a market execution
panel that sits beside the model pick.

## Recovered Prior UI Branch Context

The old UI branch appears to have been deleted, but reflog still shows its
intent:

- Branch: `codex/provider-market-sheet-ui`
- Commits:
  - `04b7a696` - preview provider market sheet UI
  - `371c5ab6` - validate live-shaped market sheet payload
  - `70a9f49d` - add provider market cue to pick cards
  - `4d248cf4` - add compact price movement to market popup
  - `b9c5459e` - fail soft on live market snapshot read failures

Do not cherry-pick that branch directly. Main has moved materially since then.
Use the branch as design reference only.

Useful ideas to preserve:

- Hidden feature flag such as `?marketSheet=1`.
- Card-level cue for best price / selected price / shop price.
- Detail-sheet market panel with best price, selected book, model fair price,
  cushion, market pulse, and compact movement.
- Fail-soft behavior when live market rows are unavailable.
- Tests around live-shaped payloads so the UI does not break on missing rows.

## Current Data Sources To Reuse

Use existing trackers first. Do not add a duplicate market tracker.

### Production artifact data

`dashboard/data/processed/today.json` and dated archives provide:

- official model pick side, line, odds, book, verdict, EV, win probability
- lock state and tracked-pick rows
- game time and game state
- input quality fields
- TheRundown official artifact provenance

`dashboard/data/processed/steam.json` provides:

- artifact-time per-book snapshots from GitHub refreshes
- historical open-to-current line/price movement for the current artifact path

### Supabase shadow/live data

`live_market_display_state` provides the best app-facing live read:

- `provider`
- `observed_at`
- `freshness_status`
- `actionable_state`
- `market_status`
- `market_consensus`
- `bet_value_consensus`
- `main_line`
- `best_book`, `best_line`, `best_odds`
- `book_count`, `books_seen`, `book_rows`
- `movement_events`
- `broad_confirmation`
- `source_artifact_path`, `source_artifact_sha256`

`market_pick_evidence` provides compact model-vs-market rollups:

- `toward_pick_count`
- `away_from_pick_count`
- `better_now_count`
- `worse_now_count`
- `touching_pick_line_count`
- `reversal_book_count`
- `volatile_book_count`
- `market_consensus`
- `bet_value_consensus`
- `time_window`

`line_movement_events` becomes more useful after PropLine webhook processor
observation is enabled:

- polling-derived and webhook-derived movement events
- bookmaker identity
- market/outcome IDs for PropLine webhook reconciliation
- durable event history without requiring the UI to scan raw snapshots

`current_market_lines` and `official_market_lines` should stay cutover evidence,
not UI truth, unless the provider cutover is approved.

## Product Shape

### MVP User Story

When Tyler opens a FIRE or LEAN pick detail sheet before lock, he should see:

1. The model pick and current production artifact line.
2. Whether the selected/current book is still playable by model fair price.
3. Whether another supported book is materially better.
4. Whether the broader market moved with or against the pick.
5. Whether the market read is fresh, stale, single-book noise, mixed, or broad
   confirmation.

The UI should answer this without making Tyler interpret raw provider rows.

### Card-Level Cue

Add one compact strip to actionable cards only, hidden behind the feature flag
at first:

- `Best DK -122`
- `FD -132`
- `Shop +10c` or `Playable`
- `LIVE 21s` / `Held 2m` / `Stale`

Do not add this to PASS cards in the MVP. PASS rows should stay visually quiet.

### Detail Sheet Market Panel

The detail sheet should add a market section inspired by the screenshot, but
adapted to the existing v2 app style:

1. **Decision row**
   - Best price
   - Selected/current book
   - Model fair price
   - Cushion at selected book
   - Action label: `Playable`, `Shop price`, `Wait`, `Market fade`, `Stale`

2. **Price movement**
   - Start with compact text and a simple existing-style chart.
   - Use `movement_events` or `live_market_display_state.movement_events` when
     available.
   - Fall back to `steam.json` when live rows are missing.
   - Do not query raw `market_snapshots` from the browser.

3. **Market pulse**
   - Line move
   - Books with movement
   - Juice move toward/away from pick
   - Market average
   - Book spread
   - Freshness/status
   - Broad confirmation

4. **Action window**
   - Best price cushion
   - Selected book cushion
   - Outlier/off-market read
   - Input quality
   - Final display verdict: e.g. `Playable, but shop price`

### Provider Comparison Add-On

After webhook processor observation is enabled and stable, add a compact
provider comparison block:

- BoltOdds consensus
- PropLine polling consensus
- PropLine webhook movement, if present
- Overlapping books: same line, line conflict, price difference
- Status: `agree`, `mixed`, `single-provider`, `stale`, `webhook-only`

This is a later phase. Do not block MVP on it.

### Bet Ticket Integration

The existing dashboard already has manual accepted-bet logging through
`/api/accepted-bets`. The live market panel should improve that flow rather than
creating a second bet logger:

Implemented 2026-06-07 on branch `codex/live-market-bet-ticket-prefill`:

- `dashboard/v2-app.jsx` / `dashboard/v2-app.js` select a fresh live market row
  for the currently displayed side only when it is suitable for prefill, then
  seed the existing `Log Bet` modal with best supported book, line, and odds.
- The modal labels whether the ticket is using `Live best`, `Artifact price`,
  or `Manual edit`.
- `buildAcceptedBetPayload` preserves selected live provider metadata and
  `price_source` in the existing `accepted_bets.metadata` object.
- `/api/accepted-bets?slate_date=YYYY-MM-DD` returns only sanitized same-day
  accepted-bet rows after the normal bet-log secret check; it does not expose
  dedupe keys, secrets, or raw service-role response bodies.
- The modal shows a read-only same-day accepted-bet review and duplicate
  same-side warning before save. Corrections/edit flows remain out of scope.
- Verified with accepted-bet function tests, dashboard accepted-bet static
  tests, adjacent live-market / notification tests, syntax checks, and
  `git diff --check`.

- When the market panel shows `Playable` or `Shop price`, the `Log Bet` ticket
  should be able to prefill from the selected live row: best supported book,
  line, odds, side, units, and model snapshot.
- If Tyler opens the app from a push deep link, preserve
  `notification_event_id` or `shadow_candidate_id` and write it into the
  accepted-bet payload.
- Keep manual edits available because books can move between alert, app open,
  and bet placement.
- Clearly show whether the ticket is using artifact price, live best price, or
  manually edited price.
- Do not auto-place bets, change stake size, or override FIRE/LEAN/PASS.

The ticket should accept an optional alert context object from push deep links or
shadow review links:

```json
{
  "slate_date": "2026-05-25",
  "pitcher": "Example Pitcher",
  "normalized_pitcher": "example pitcher",
  "side": "under",
  "source": "notification",
  "notification_event_id": "uuid-if-real-alert",
  "shadow_candidate_id": null,
  "decision_label": "shop_price",
  "selected_book": "FanDuel",
  "selected_line": 5.5,
  "selected_odds": -135,
  "best_book": "DraftKings",
  "best_line": 5.5,
  "best_odds": -122,
  "model_fair_odds": -130,
  "observed_at": "2026-05-25T20:15:00Z",
  "source_artifact_sha256": "..."
}
```

Persist only stable audit fields in `accepted_bets`: source,
`notification_event_id`, `shadow_candidate_id`, model snapshot, metadata, and
the final manually confirmed book/line/odds/units. Store the price origin in
metadata as `price_source=artifact|live_best|notification_context|manual_edit`.

### Accepted-Bet Review And Corrections

Before building complex editing, add a read-only same-day accepted-bet view or
debug panel so Tyler can verify what was logged. The minimum useful surface is:

- slate date, pitcher, side, book, line, odds, units, accepted time, and source;
- linked notification/candidate ID when present;
- model snapshot summary and generated artifact timestamp;
- duplicate/same-side warning when a second bet on the same pitcher/side is
  attempted.

Current browser-side duplicate suppression is intentionally simple. Future UI
work should distinguish "already logged this side" from a legitimate second
entry at a different book, line, odds, or unit size. Corrections should be
append-only or audit-preserving; do not silently mutate historical bet rows.

## Display Semantics

Use betting language, but keep it clearly informational:

- `Model fair price` instead of `threshold` when possible.
- `Cushion` means current odds minus model fair American odds.
- `Shop price` means another supported book is better by a material amount.
- `Market with pick` means broad movement toward the model side.
- `Market against pick` means broad movement away from the model side.
- `Single-book noise` means one book moved without broad confirmation.
- `Stale` means live provider state is too old to trust.

Avoid language that implies a new live rule:

- Do not say the system "recommends" a new bet because of provider movement.
- Do not show a new stake size.
- Do not override FIRE/LEAN/PASS.
- Do not call webhook movement "official".

## Proposed Architecture

### Phase 1 - Static/Preview Contract

Build a sanitized market-display payload and UI adapter without live production
dependency.

Implemented 2026-06-07 on branch `codex/live-market-decision-ui`:

- `dashboard/v2-data.js` builds `window.V2_MARKET_DISPLAY` and attaches
  normalized rows to `pitcher.market_display[OVER|UNDER]` only when
  `?marketSheet=1` is present.
- `dashboard/v2-data.test.mjs` covers disabled-by-default behavior, matching
  row attachment, wrong-date/malformed row fail-soft handling, unsupported
  provider suppression, stale labels, and malformed book-row cleanup.
- `dashboard/v2-app.jsx` / `dashboard/v2-app.js` render a compact market strip
  on actionable cards and a detail-sheet market decision panel with best live
  price, model ref, fair odds/cushion, market pulse, value, freshness, and book
  rows.
- `dashboard/v2.html` adds the scoped card/panel styles.
- Verified with `node --test dashboard/v2-data.test.mjs`,
  `node --check dashboard/v2-app.js`, and Playwright screenshots against a
  temporary local fixture server.

Preferred path:

- Add a small fixture or local export shaped like `live_market_display_state`.
- Extend `dashboard/v2-data.js` to accept `window.V2_LIVE_MARKET_DISPLAY` rows
  when present.
- Keep the UI behind `?marketSheet=1`.
- Add tests for missing rows, stale rows, unsupported provider rows, and
  malformed book rows.

This phase can be implemented before any operational cutover because it does
not read live Supabase from the browser.

### Phase 2 - Safe Live Read

Implemented 2026-06-07 on branch `codex/live-market-display-endpoint`:

- `netlify/functions/live-market-display.mjs` reads
  `live_market_display_state` with server-side Supabase credentials and returns
  `generated_at`, `slate_date`, `source`, and sanitized rows only.
- Supported providers are limited to BoltOdds and PropLine. Supported books are
  filtered to the app's target set before `book_rows`, `books_seen`, and
  `best_book` reach the browser.
- Missing Supabase configuration, invalid dates, and Supabase read failures
  fail closed with `rows: []` and a non-secret `error` value.
- `dashboard/v2-data.js` calls the endpoint only behind `?marketSheet=1`, after
  the slate artifact is loaded, and keeps the dashboard usable if the endpoint
  is unavailable.
- Follow-up live validation found multiple provider rows per pitcher/side. The
  adapter now chooses the displayed row deterministically instead of relying on
  payload order: fresh rows beat stale rows, then more informative action
  states, broad confirmation, supported-book count, observed time, and provider
  tie-breakers decide the single card/sheet row. Provider-comparison display is
  still a later phase.
- Verified with endpoint tests, hidden-flag adapter tests, adjacent v2 data /
  movement / factor-detail tests, Netlify notification and accepted-bet tests,
  syntax checks, and `git diff --check`.

Add a Netlify read endpoint for sanitized current-slate market display rows.

Suggested endpoint:

- `netlify/functions/live-market-display.mjs`

The endpoint should:

- Use server-side Supabase credentials only.
- Return only current-slate, app-safe fields.
- Filter to active slate rows and supported books.
- Include `generated_at`, `slate_date`, `rows`, and `source`.
- Fail closed with `rows: []` and a non-secret error summary.
- Set a short cache window, or no-store if testing shows stale responses are
  worse than extra function calls.

The browser should:

- Fetch this endpoint after `today.json`.
- Merge rows by `slate_date + normalized_pitcher + side`.
- Never let endpoint failure block normal dashboard rendering.
- Show `Shadow market unavailable` only inside the detail panel, not as a
  page-level alert.

### Phase 3 - Provider Agreement / Webhook Comparison

After `LIVE_PROCESS_PROPLINE_WEBHOOKS` observation is enabled and proves clean,
extend the endpoint to include a compact provider-comparison block:

- per-pick BoltOdds rows
- per-pick PropLine polling rows
- recent PropLine webhook movement events
- overlap summary for books both providers saw

This should be read-only. It should help decide whether BoltOdds and PropLine
agree, not choose production truth.

### Phase 4 - Promotion Review

Only after the operational base and provider cutover are approved, decide
whether the UI becomes default-on.

Promotion gates:

- Supabase lock ledger soak is clean.
- If enabled, lock consumer canary is clean.
- PropLine webhook processor observation is clean.
- Row-volume/retention dry-run is acceptable.
- Provider cutover comparison says the new provider stack is ready, or the UI
  is explicitly scoped as shadow display only.
- Tyler approves making the market panel visible without a query flag.

## Implementation Sequence

1. Create a branch such as `codex/live-market-decision-ui-plan` or
   `codex/live-market-decision-ui`.
2. Recover old branch intent from reflog, but do not cherry-pick wholesale.
3. Add tests for the UI adapter contract:
   - no live rows
   - one fresh BoltOdds row
   - one fresh PropLine row
   - both providers disagree
   - stale provider row
   - malformed `book_rows`
4. Add pure adapter helpers in `dashboard/v2-data.js` or a small
   `dashboard/v2-market-display.js` module:
   - normalize book keys
   - compute model fair American odds
   - compute selected-book cushion
   - compute best-book cushion
   - compute provider agreement label
   - compute display action
5. Add hidden card strip and detail sheet panel in `dashboard/v2-app.jsx`.
6. Rebuild `dashboard/v2-app.js` from JSX using the repo's existing build path.
7. Add CSS to `dashboard/v2.html`, keeping mobile dimensions stable.
8. Add the Netlify read endpoint only after the fixture path is proven.
9. Add endpoint tests and fail-soft browser tests.
10. DONE 2026-06-07 - Add accepted-bet ticket integration for live best-book rows and preserve
    `notification_event_id` / `shadow_candidate_id` when opened from a push or
    shadow-candidate review link.
11. DONE 2026-06-07 - Add a read-only accepted-bet review surface before any edit/correction UI.
12. Verify with local static dashboard, Playwright mobile screenshots, and
    existing v2 tests.
13. Keep the feature hidden behind query flag until Tyler reviews it.

## Suggested Data Contract For UI

The browser should receive a compact, sanitized shape:

```json
{
  "generated_at": "2026-05-20T18:40:21Z",
  "slate_date": "2026-05-20",
  "rows": [
    {
      "pitcher": "Example Pitcher",
      "normalized_pitcher": "example pitcher",
      "side": "under",
      "provider": "boltodds",
      "observed_at": "2026-05-20T18:40:21Z",
      "freshness_status": "fresh",
      "market_status": "market_confirmed_playable",
      "actionable_state": "playable_now",
      "market_consensus": "toward_pick",
      "bet_value_consensus": "worse_now",
      "main_line": 5.5,
      "best_book": "draftkings",
      "best_line": 5.5,
      "best_odds": -122,
      "book_count": 7,
      "books_seen": ["draftkings", "fanduel", "betmgm"],
      "broad_confirmation": true,
      "book_rows": [
        {
          "book": "draftkings",
          "line": 5.5,
          "odds": -122,
          "market_direction": "toward_pick",
          "bet_value_direction": "worse_now"
        }
      ],
      "movement_events": []
    }
  ]
}
```

Do not expose raw provider payloads, secrets, service-role responses, or
unbounded raw snapshot history.

## Decision Rules For Display Only

These labels are UI summaries, not model/pipeline rules.

- `Playable`: selected/current book is at or better than model fair price and
  market state is fresh.
- `Shop price`: selected/current book is worse than the best supported book by
  a material margin, but the best price is still playable.
- `Wait`: no available supported book clears model fair price.
- `Market fade`: broad market movement is away from the pick and best price is
  not playable.
- `Stale`: provider freshness is stale or missing.
- `Monitor`: evidence is mixed, sparse, or single-provider only.

Material shop margin should start display-only at 5-10 cents and must not alter
notifications or staking without a later approval.

When these labels prefill the bet ticket, the payload must preserve whether the
price came from artifact state, live display state, notification context, or
manual edit.

The UI should use the same `decision_label` vocabulary as the notification
coordinator, while display labels may stay friendlier:

| UI label | Coordinator label |
| --- | --- |
| `Playable` | `bet_now` or `monitor`, depending on confirmation |
| `Shop price` | `shop_price` |
| `Wait` | `wait` |
| `Market fade` | `wait` or `monitor` with adverse reason codes |
| `Stale` | `ignore_stale` |
| `Monitor` | `monitor` |

The notification digest coordinator is now the source for grouped alert context:

- start-window digest context should open the slate with the relevant start
  cluster highlighted;
- pick-change digest context should open the filtered set of upgraded,
  downgraded, or new FIRE rows;
- individual movement context should open the specific pitcher market panel;
- accepted-bet logging should preserve `notification_event_id` or
  `shadow_candidate_id` when a push or shadow-review link opened the app.

## Verification

Required before merge:

- `node --test dashboard/v2-data.test.mjs`
- existing dashboard/provider-market tests, if restored or recreated
- `python -m pytest tests/test_dashboard_accepted_bet_log.py -q`
- Netlify function tests if an endpoint is added
- Playwright mobile screenshot of:
  - normal cards with feature flag off
  - actionable card with feature flag on
  - detail sheet with live market rows
  - detail sheet with stale/missing market rows
  - dark mode if feasible

Manual review checklist:

- PASS cards remain quiet.
- FIRE/LEAN semantics are unchanged.
- The UI never shows shadow market data as official production truth.
- Long pitcher names and book names do not overflow on mobile.
- Stale provider rows are visually obvious.
- Endpoint failure does not break the dashboard.
- No secrets or service-role responses appear in browser output.

## Risks

- A `Playable` label can be mistaken for a new betting rule. Keep it clearly
  tied to `model fair price` and hidden behind the flag until reviewed.
- Direct browser reads from Supabase can create security and source-of-truth
  confusion. Use a sanitized Netlify endpoint if live reads are needed.
- Fetching raw snapshots for charts could create row-volume and latency
  problems. Use compact movement rows or `movement_events`.
- Provider disagreement can confuse the operator if it is not summarized.
  Prefer `agree`, `mixed`, `single-provider`, and `stale` labels over dumping
  every row.
- If the feature is launched before lock-ledger and webhook observation settle,
  the UI may look like a production cutover even though it is still shadow.

## Recommendation

Build this after the next lock-ledger check clears the active lock cluster.

Start with the hidden, fixture-backed card strip and detail-sheet market panel.
That gets the product shape right with almost no operational risk. Then add the
sanitized Netlify live endpoint. Add provider-vs-provider and webhook-specific
comparison only after webhook processor observation has soaked cleanly.

This is the right UI direction, but it should be staged behind a flag until the
operational base is stable.
