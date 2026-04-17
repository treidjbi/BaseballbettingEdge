# v2 UI — Deferred Pipeline Work

The v2 preview at [`dashboard/v2.html`](../../dashboard/v2.html) uses real
pipeline data through an adapter ([`dashboard/v2-data.js`](../../dashboard/v2-data.js))
but several v2 features are either stubbed or show a "not wired" fallback
because the underlying data doesn't exist yet. If we ship v2 and want to
close the gaps, here's the wishlist.

Source: [`docs/ui-redesign/handoff/project/v2/HANDOFF.md`](handoff/project/v2/HANDOFF.md).

## 1. `best_under_book` on each pitcher

**Status now.** Pipeline emits `best_over_book` but not `best_under_book`.
Adapter falls back to `best_over_book` for display on UNDER picks — the book
name shown on UNDER cards/CTAs may be wrong.

**Fix.** In [`pipeline/fetch_odds.py`](../../pipeline/fetch_odds.py), track
which book owns the best UNDER price alongside the existing OVER tracking.
Add `best_under_book` to the pitcher record emitted to `today.json`.

## 2. Live in-game hydrate (`live.*` object)

**Status now.** Cards with `game_state === "in_progress"` show a generic
"LIVE · game in progress" block with no K count. No per-pitch/inning data
in `today.json`.

**Needed fields per v2 contract:**

```ts
live: {
  current_k: number,      // K's recorded
  innings: string,        // "5.1"
  pitches: number,
  proj_final_k: number,   // model-updated projection
  updated_at: string
}
```

**Fix.** New pipeline module, something like `pipeline/fetch_live.py`, that
hits MLB Stats API's live game feed for any game in progress and merges
`{current_k, innings, pitches, proj_final_k}` onto the matching pitcher in
`today.json`. Only runs during the 8 AM–6 PM refresh cadence (skip it in
preview/grading runs). `proj_final_k` = a quick on-the-fly Poisson update
using remaining expected IP at current pace.

## 3. Per-pick `result` object for finalized games in `today.json`

**Status now.** When a pitcher's game goes final, today.json keeps the
pregame snapshot but doesn't embed grading. The detail sheet's FINAL state
block falls back to a generic "grading not available" message and points
users to the Results tab.

**Needed fields per v2 contract:**

```ts
result: {
  final_k: number,
  side_taken: "over" | "under" | null,
  line_at_bet: number | null,
  odds_at_bet: number | null,
  outcome: "win" | "loss" | "push" | "pass",
  units_won: number,
  units_risked: number
}
```

**Fix.** After `fetch_results.py` grades a day, write each graded record's
outcome back onto that date's `YYYY-MM-DD.json` under `pitchers[].result`.
Data already exists in `data/picks_history.json` (fields `result`, `pnl`,
`side`, `locked_k_line`, `locked_odds`) — just a matter of plumbing it
onto the per-date archive.

## 4. Standalone steam feed

**Status now.** Adapter derives steam inline from each pitcher's
`opening_*_odds` → `best_*_odds` delta. Shows cents moved + direction.
Missing: `books_moved / books_total` counts and any kind of descriptive
note beyond "Odds only" / "Line X → Y".

**Fix.** TheRundown plan we're on (Starter) exposes all bookmakers. Two
options:

- **A, cheaper.** Compute books-moved client-side by fetching per-book
  odds history rather than the current "best line" summary. Would require
  a new `dashboard/data/processed/steam.json` written by the pipeline,
  shape `{updated_at, rows:[{pitcher, k_line, open_line, direction, cents,
  books_moved, books_total, note}]}` — 12h trailing window.

- **B, richer.** Poll TheRundown's per-book odds every refresh, keep a
  time-series per pitcher+book, and publish a real steam feed that can
  show bar charts of movement. More quota spend.

## 5. Sportsbook deep links on CTA

**Status now.** Sheet CTA says "Bet UNDER 5.5 on FanDuel" but the button
has no `onClick`.

**Fix.** Either (a) affiliate deep-link table keyed on book + event-id, or
(b) hand-maintained book URLs keyed on book name. Needs the `best_*_book`
field from item 1.

## 6. Date-pill win/loss dots

**Status now.** Date scroller shows 3 days back → 3 forward from today but
the dots are omitted. V2 prototype had `past-win` / `past-loss` classes
showing colored dots on each past date.

**Fix.** Add a small per-date summary to `dashboard/data/processed/index.json`:
`{date, wins, losses}`. Adapter can then mark pills as `past-win` when wins
> losses, `past-loss` otherwise. Cheap win — computable from picks_history.

## 7. Real "line movement" chart in detail sheet

**Status now.** Sheet renders a 12-step synthetic sparkline faked from
`opening_line → k_line` with sine noise.

**Fix.** Needs the time-series steam feed from item 4. Shape:
`{t: iso, line: number, over_odds: number, under_odds: number}[]`.

## 8. Push notifications + service worker

**Status now.** v2 preview has no service worker registration. Index.html
still owns `sw.js` and `manifest.json`.

**Fix if we ship v2.** Port the push subscription / notify-bell plumbing
from `index.html` into v2-app.jsx, and point the SW scope appropriately.
Straightforward copy-paste; no pipeline changes needed.

---

## What to tackle first if we go forward

Ordered by user-visible value vs. effort:

1. **Item 6 (date-pill dots)** — trivial, lives entirely in the adapter.
2. **Item 3 (per-pick result embed)** — smallest pipeline change, unlocks
   the FINAL state sheet and makes the Results tab narrative-consistent
   with the Picks tab.
3. **Item 1 (`best_under_book`)** — small pipeline change, removes a wrong
   book name from ~half the UNDER CTAs.
4. **Item 5 (deep-link CTA)** — needs item 1, then is just a URL table.
5. **Item 4A (simple steam.json)** — unlocks books-moved counts, real
   time-series for item 7.
6. **Item 2 (live hydrate)** — biggest lift, biggest product payoff.
7. **Item 8 (PWA port)** — only if/when we cut over from index.html.
