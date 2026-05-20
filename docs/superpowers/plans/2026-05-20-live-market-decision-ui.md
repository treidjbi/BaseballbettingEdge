# Live Market Decision UI Plan

> **Status:** Proposal / shadow-only UI plan. Do not implement or promote without Tyler approval.
>
> **Guardrail:** This plan must not change production provider order, model math,
> thresholds, staking, lock behavior, notification sends, retention, secrets, or
> source-of-truth rules. TheRundown-derived GitHub artifacts remain production
> truth until the provider cutover gates pass and Tyler approves the switch.

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
10. Verify with local static dashboard, Playwright mobile screenshots, and
    existing v2 tests.
11. Keep the feature hidden behind query flag until Tyler reviews it.

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
