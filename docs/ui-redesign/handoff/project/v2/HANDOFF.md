# Betting Edge — v2 Design Handoff

Mobile-first React app that surfaces daily MLB K-prop picks with model-derived edge, line-movement (steam), and results tracking.

## Files

| File | Purpose |
|---|---|
| `v2.html` | Shell. Contains **all CSS inlined** (critical — see [Gotchas](#gotchas)), the design-system CSS variables, the `#root` mount, and React/Babel loaders. |
| `v2-app.jsx` | Single-file React app. All components live here. |
| `v2-data.js` | Mock data fixtures. Three globals: `window.V2_DATA` (picks), `window.V2_PERF` (results), `window.V2_STEAM` (line movement). |

No build step. It's intentionally plain — React 18 + Babel standalone, loaded via `<script>` tags with pinned integrity hashes. When you port this to a real framework, the JSX translates 1:1.

## Architecture

```
App (root)
├── renderPicks()             ← state machine for appState (ready | loading | error | empty)
│   ├── PicksTab              ← default view
│   │   ├── Header (brand + day strip)
│   │   ├── DigestStrip       ← summary card: "5 FIRE PICKS TODAY · avg EV +9.6%"
│   │   ├── FilterChips       ← ALL / FIRE / LEAN / LIVE
│   │   ├── PickCard[]        ← one per pitcher, grouped by UPCOMING vs LIVE & FINAL
│   │   └── PickDetail        ← bottom sheet portal, opened on card tap
│   ├── LoadingState
│   ├── EmptyState
│   └── ErrorState
├── PerfTab                   ← Results: season units + ROI by tier
├── SteamTab                  ← Line movement feed, filterable (ALL / OVER / UNDER / MINE)
└── TabBar                    ← PICKS / STEAM / RESULTS
```

## Data shape

### Pick (`V2_DATA.pitchers[]`)

```ts
{
  pitcher: string,              // "Tarik Skubal"
  team: string,                 // full team name — card abbreviates via ab()
  opp_team: string,
  pitcher_throws: "L" | "R",
  game_time: string,            // ISO — shown as local time
  k_line: number,               // current book line (e.g. 7.5)
  opening_line: number,         // for line-move display
  best_over_odds: number,       // American odds — e.g. -115, +100
  best_under_odds: number,
  opening_over_odds: number,
  opening_under_odds: number,
  lambda: number,               // model's projected K count
  avg_ip: number,
  opp_k_rate: number,           // 0..1 (e.g. 0.257 = 25.7%)
  ump_k_adj: number,            // -1..+1 ish, umpire K-tendency adjustment
  season_k9: number,
  recent_k9: number,            // last 5 starts
  career_k9: number,

  ev_over:  { ev, adj_ev, verdict: "FIRE 2u"|"FIRE 1u"|"LEAN"|"PASS", win_prob, movement_conf },
  ev_under: { ev, adj_ev, verdict,                                     win_prob, movement_conf },

  game_state: "pregame" | "in_progress" | "final",

  // Only when game_state === "in_progress":
  live?: {
    current_k: number,          // K's right now
    innings: string,            // "5.1"
    pitches: number,
    proj_final_k: number,       // updated live projection
    updated_at: string
  },

  // Only when game_state === "final":
  result?: {
    final_k: number,
    side_taken: "over" | "under" | null,  // null = model said PASS, no bet
    line_at_bet: number | null,
    odds_at_bet: number | null,
    outcome: "win" | "loss" | "push" | "pass",
    units_won: number,          // net (e.g. +1.56 or -2.0)
    units_risked: number
  }
}
```

### Perf (`V2_PERF`)

```ts
{
  total_picks, total_units, total_roi, record: "86-85-0",
  rows: [{ verdict, side: "over"|"under", picks, wins, losses, win_pct, roi, avg_ev }]
}
```

### Steam (`V2_STEAM`)

```ts
{
  updated_at,
  rows: [{
    pitcher, team, opp, game_time,
    k_line, open_line,
    direction: "over" | "under",  // which side is getting steam
    cents: number,                 // total cents moved
    open_odds, cur_odds,
    books_moved: number,           // e.g. 6 (of 7)
    books_total: number,
    note: string,
    my_pick: string | null         // "OVER FIRE 2u" if you're on it, else null
  }]
}
```

## Design-system tokens

All in the `:root` block at the top of `v2.html`. Dark theme overrides under `body[data-theme="dark"]`.

Semantic colors:
- `--ink` / `--ink-2` / `--ink-dim` — text hierarchy
- `--bg` / `--surface` / `--chip` — background layers
- `--border` — hairlines
- `--accent` (#c6321f fire red) — primary brand/CTA
- `--accent-2` (#1e3a5f deep blue) — secondary, used for OVER tier badges
- `--pos` (green) / `--neg` (red) / `--warn` (amber) / `--live` (hot pink) — status
- `--radius-sm|md|lg|xl` — 4/8/12/18 px
- `--shadow-1` — single card shadow

Type stack:
- **Inter** — body/UI
- **Oswald** — condensed display (tier badges, buttons, section heads)
- **JetBrains Mono** — numeric/code (odds, timestamps, raw stats)

## Verdict vocabulary

| Label | Meaning | Visual |
|---|---|---|
| `FIRE 2u` | Strong edge — 2 unit bet | Deep blue (OVER) or fire red (UNDER) solid badge |
| `FIRE 1u` | Solid edge — 1 unit bet | Same colors, slightly dialed down |
| `LEAN` | Weak edge — informational, not actionable | Outlined badge |
| `PASS` | No edge, no bet | Dimmed, greyed out |

Pick grouping: `UPCOMING` (pregame) vs `LIVE & FINAL` (in_progress + final).

## Pick detail sheet states

The sheet (`PickDetail`) renders one of four state blocks near the top, plus a state-appropriate CTA at the bottom:

| State | When | Block | CTA |
|---|---|---|---|
| Pregame + actionable | `pregame` + verdict ≥ LEAN | (no state block) | "Bet OVER 7.5 on FanDuel ↗" |
| Pregame + PASS | `pregame` + both sides `PASS` | "NO EDGE" explainer | "No actionable edge" (disabled) |
| LIVE | `in_progress` | Live K count, innings, projected final, over/under pace chip | "Live · Track in-game" (disabled) |
| FINAL + bet | `final` + `result.outcome` in `win/loss/push` | Outcome badge, units won, bet details | "View grade details →" |
| FINAL + pass | `final` + `result.outcome === "pass"` | "NO BET" + final K context | "No bet placed" (disabled) |

## Responsive behavior

Mobile-first. On **viewport ≥ 520px** a media query clamps `#root` to `414px` wide and gives it a phone-frame treatment (rounded corners, drop shadow, warm page background). This is cosmetic only — the app is designed for mobile. The tabbar, sheet, and sheet backdrop are `position: fixed` and clamp to the same 414px column on desktop.

## Placeholders / things to wire up

These are mocked on the frontend and need real data in handoff:

1. **Sportsbook CTA** — hardcoded to **"FanDuel"**. Data model has `best_over_odds`/`best_under_odds` but doesn't track which book owns the best price. Add `best_over_book` / `best_under_book` fields so the CTA can point at the actual best-price sportsbook. The CTA's `onClick` currently does nothing — wire it to a deep-link or affiliate URL.
2. **Line-movement bars** — `PickDetail` fakes a 12-step sparkline from `opening_line → k_line`. Replace with a real time series from your odds feed (ideal shape: `{t: timestamp, line: number, over_odds: number, under_odds: number}[]`).
3. **Steam data** — currently static. Should be a live feed of price-moves across books in a trailing window (e.g. last 12h).
4. **Live updates** — the `live` object has a snapshot. In prod this should update from a websocket or poll the odds API every N seconds. Consider optimistic UI (show current K count prominently, lambda projection updates as game progresses).
5. **Steam ↔ picks linking** — `my_pick` on steam rows is a string; could be a foreign key to the pitcher pick for deep linking.
6. **Notification bell / refresh** — buttons in the header don't do anything yet.
7. **Performance "View grade details" CTA** — on a finalized pick, this should open a modal with the full grade breakdown (projected vs actual K, EV realized, CLV, etc.). Not designed yet.
8. **Filter persistence** — active tab survives nav (stored in component state only). Consider localStorage if users switch tabs often.

## Gotchas

- **CSS is inlined in `v2.html`.** Earlier, the external `v2-styles.css` was being silently truncated by the preview server around the midpoint of the file, dropping every rule past ~line 470 (including all sheet styles). If you pull the CSS back out into a separate file in prod, verify the full file is served — otherwise the sheet renders `position: static` below the fold and appears invisible.
- **Style object collisions.** This file uses inline styles, not a `const styles = {}` object, to avoid the global-scope collision issue with Babel standalone across multiple `<script type="text/babel">` tags.
- **Sheet animation on desktop** uses a separate `@keyframes v2-slide-up-desktop` because the frame centers the sheet with `translateX(-50%)` and the base mobile keyframe only translates Y, which would override the X centering.
- **`game_state === "in_progress"` vs `"final"`** — these drive both the card visual treatment (in the `LIVE & FINAL` group) and the sheet's state block. Keep them in sync with the odds-feed's source of truth.
- **Tier badge colors encode side**: OVER picks get deep blue (`--accent-2`), UNDER picks get fire red (`--accent`). This is load-bearing throughout the app — don't repurpose those colors.

## Next design work

Loose threads I didn't tackle:
- Onboarding / first-run
- Settings (theme toggle exists but nothing else — bankroll config, unit size, notification prefs)
- Per-pitcher history detail (link from card → full prop history)
- Parlay / same-game tools (out of scope for now?)
- iPad / tablet layouts
