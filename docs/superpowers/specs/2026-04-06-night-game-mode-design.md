# Night Game Mode — Design Spec

**Date:** 2026-04-06
**Status:** Draft

## Overview

Add a day/night theme toggle to the dashboard. Light mode ("day game") is the current cream/newsprint aesthetic. Dark mode ("night game") is a deep navy palette evoking a stadium at night. The toggle persists across page refreshes via localStorage.

This change also restructures the top bar layout: the freshness timestamp moves under the wordmark, the "60s delay" badge is removed, the date picker is centered, and the theme toggle sits in the top-right corner.

## Goals

- Comfortable dark viewing for night games without losing the app's visual identity
- Single mechanism: override 5 CSS variables on `<html>` + targeted overrides for hardcoded colors
- Persist preference in localStorage
- Simplify the top bar while making room for the toggle

## Color Palette

### Light (Day Game) — current, unchanged

```
--bg:       #f5f0e8  (cream/newsprint)
--surface:  #faf6ee  (warm off-white)
--border:   #d0c8b8  (warm tan)
--ink:      #1a1a1a  (near black)
--ink-dim:  #888888  (muted gray)
```

### Dark (Night Game) — new

```
--bg:       #0d1929  (deep navy, stadium sky)
--surface:  #132035  (slightly lighter navy, card surface)
--border:   #1e3050  (subtle navy border)
--ink:      #f0ede6  (warm white, not pure white)
--ink-dim:  #6b7f99  (muted blue-gray)
```

`--fire` (`#c0392b`) and `--positive` (`#27ae60`) stay identical in both modes — they're semantic colors with sufficient contrast against both palettes.

## Components

### 1. CSS: `[data-theme='dark']` overrides

Add a single `[data-theme='dark']` rule block in `<style>`, after the `:root` variables.

**Core variable overrides:**

```css
[data-theme='dark'] {
  --bg:      #0d1929;
  --surface: #132035;
  --border:  #1e3050;
  --ink:     #f0ede6;
  --ink-dim: #6b7f99;
}
```

These 5 variables cascade through ~90% of the UI automatically (surfaces, text, borders, cards, watchlist, performance table, stat labels, stat values, etc.).

**Targeted overrides for hardcoded colors:**

The following elements use hardcoded hex values that bypass CSS variables. Each needs an explicit dark-mode override:

```css
/* Top bar + nav */
[data-theme='dark'] #top-bar { background: #080f1a; border-bottom-color: #1e3050; }
[data-theme='dark'] #nav { background: #080f1a; border-top-color: #1e3050; }
[data-theme='dark'] .nav-btn { color: #6b7f99; }

/* Card header (diagonal stripe pattern) */
[data-theme='dark'] .card-header {
  background: repeating-linear-gradient(45deg, #080f1a, #080f1a 2px, #0d1929 2px, #0d1929 8px);
}

/* Pitcher card box-shadow (white inset glow → dark equivalent) */
[data-theme='dark'] .pitcher-card {
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.05), 0 1px 3px rgba(0,0,0,0.3);
}

/* Pitcher matchup text */
[data-theme='dark'] .pitcher-matchup { color: #6b7f99; }

/* Adjustment badges */
[data-theme='dark'] .adj-pos { background: #0d2b1a; border-color: #1a5c35; }
[data-theme='dark'] .adj-neg { background: #2b0d0d; border-color: #5c1a1a; }
[data-theme='dark'] .adj-neutral { background: #132035; border-color: #1e3050; color: #6b7f99; }

/* Verdict badges */
[data-theme='dark'] .verdict-pass { background: #1e3050; color: #6b7f99; }
[data-theme='dark'] .badge-started { background: #1e3050 !important; color: #6b7f99 !important; }

/* Banners (use border-bottom-color, not border-color — the base CSS uses border-bottom shorthand) */
[data-theme='dark'] .banner-info { background: #0d2b1a; border-bottom-color: #1a5c35; color: #f0ede6; }
[data-theme='dark'] .banner-warn { background: #2b1f0d; border-bottom-color: #5c3d1a; color: #f0ede6; }

/* Date selector border */
[data-theme='dark'] #date-select { border-color: #1e3050; }
[data-theme='dark'] #date-select:focus { border-color: #6b7f99; }
```

**Elements that already work in both modes (no override needed):**
- `.badge-ok` (green bg, white text) — fine on both
- `.badge-warn` (orange bg, white text) — fine on both
- `.verdict-fire` (red bg, white text, fire pulse) — fine on both
- `.verdict-lean` (transparent bg, orange border/text) — fine on both
- `.delta-over` / `.delta-under` — use `var(--fire)` / `var(--ink-dim)`, cascade handles it
- `.stat-value`, `.stat-label`, `.stat-sub` — use `var(--ink)` / `var(--ink-dim)`, cascade handles it
- `.card-pass` / `.card-started` — opacity-based, works on any background
- EV-tiered `border-left` — uses `var(--fire)` and `#e67e22`, both visible on dark navy
- `#date-select option` — hardcoded `background: #222; color: #fff`, works fine in both modes (dark dropdown on dark theme is natural)
- `.wordmark-bottom` — hardcoded `color: #ffffff`, sits inside the always-dark top bar

### 2. Top Bar Layout Restructure

**Current layout:**
```
┌──────────────────────────────────────────┐
│ [K] Betting Edge              [Apr 6 ▾] │
│                           [⚡12:03 60s]  │
└──────────────────────────────────────────┘
```

**New layout:**
```
┌──────────────────────────────────────────┐
│ [K] Betting Edge     [Apr 6 ▾]      [☽] │
│     Updated 12:03 PM                     │
└──────────────────────────────────────────┘
```

Changes:

**Move freshness badge under the wordmark:**
- The `#freshness-badge` element moves from inside `#top-right` to inside `#title-date`, below the `.wordmark-bottom` span
- Style it as a small muted status line: `font-size: 10px; color: #6b7f99; font-family: 'IBM Plex Mono', monospace;`
- Add a scoped CSS override so the `.badge-ok` / `.badge-warn` spans (which default to `font-size: 11px`) shrink to match: `#freshness-badge .badge-ok, #freshness-badge .badge-warn { font-size: 10px; padding: 1px 6px; }`

**Remove "60s delay" badge:**
- In `setFreshness()`, remove all `<span class="badge-delay">60s delay</span>` output (lines 569, 573)
- The `.badge-delay` CSS class can be deleted
- The stale-data branch (line 569) keeps the `badge-warn` span but drops the delay badge

**Center the date picker:**
- `#top-right` no longer holds the date row — it only holds the theme toggle
- `#date-row` moves to be a direct child of `#top-row`, positioned between the title cluster and `#top-right` via flex layout
- `#date-row` gets `flex: 1; display: flex; justify-content: center;` to center the date picker

**Theme toggle in `#top-right`:**
- `#top-right` now contains only the toggle button (no date, no freshness)
- Simplifies to `display: flex; align-items: center;`

**Updated HTML structure for `#top-row`:**
```html
<div id="top-row">
  <div id="title-date">
    <svg class="k-mark">...</svg>
    <div>
      <span class="wordmark-bottom">Betting Edge</span>
      <span id="freshness-badge"></span>
    </div>
  </div>
  <div id="date-row">
    <input type="date" id="date-select" onchange="onDateChange(this.value)" />
  </div>
  <div id="top-right">
    <button id="theme-toggle" onclick="toggleTheme()" title="Day game / Night game"></button>
  </div>
</div>
```

### 3. Toggle Button

**Icon:** Use Phosphor icons (already loaded via unpkg on line 10) instead of emoji. Emoji renders inconsistently across OS/browser; Phosphor icons inherit `color` and are always crisp.

- Light mode shows: `<i class="ph-bold ph-moon"></i>` (click to go dark)
- Dark mode shows: `<i class="ph-bold ph-sun"></i>` (click to go light)

**Style:** `background: none; border: none; cursor: pointer; font-size: 18px; padding: 0; line-height: 1; color: #fff;` — uses white since the top bar is always a dark background regardless of theme. (Using `var(--bg)` would make the icon invisible in dark mode, since `--bg` becomes dark navy.)

### 4. JavaScript

**Toggle function:**
```javascript
function toggleTheme() {
  const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
  const next = isDark ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  document.getElementById('theme-toggle').innerHTML =
    next === 'dark' ? '<i class="ph-bold ph-sun"></i>' : '<i class="ph-bold ph-moon"></i>';
  localStorage.setItem('theme', next);
}
```

**On-boot restore — placed in `<head>` (after `</style>`, before `</head>`) to prevent flash of light theme:**

```html
<script>
(function() {
  var saved = 'light';
  try { saved = localStorage.getItem('theme') || 'light'; } catch(e) {}
  document.documentElement.setAttribute('data-theme', saved);
  document.addEventListener('DOMContentLoaded', function() {
    document.getElementById('theme-toggle').innerHTML =
      saved === 'dark' ? '<i class="ph-bold ph-sun"></i>' : '<i class="ph-bold ph-moon"></i>';
  });
})();
</script>
```

**Critical placement note:** This `<script>` MUST be in `<head>`, not at the bottom of `<body>` where the other JS lives. If it runs after paint, the user sees a flash of light theme before dark mode applies. Placing it in `<head>` sets `data-theme` before the browser paints any content.

The `try/catch` around localStorage handles edge cases (private browsing in older Safari). The `toggleTheme()` function should similarly wrap `localStorage.setItem` in try/catch.

### 5. setFreshness() updates

The function currently outputs three badge variants (past, stale, fresh). All three change:

**Past date branch:**
```javascript
badge.innerHTML = '<span class="badge-ok">' + dateLabel + ' · ' + timeLabel + '</span>';
```
No change — this is fine as-is.

**Stale data branch (current):**
```javascript
badge.innerHTML = '<span class="badge-warn">Data may be outdated</span><span class="badge-delay">60s delay</span>';
```
**Changes to:**
```javascript
badge.innerHTML = '<span class="badge-warn">Data may be outdated</span>';
```

**Fresh data branch (current):**
```javascript
badge.innerHTML = '<span class="badge-ok">Updated ' + time + '</span><span class="badge-delay">60s delay</span>';
```
**Changes to:**
```javascript
badge.innerHTML = '<span class="badge-ok">Updated ' + time + '</span>';
```

## What Does Not Change

- Pipeline code — no changes
- GitHub Actions — no changes
- Data structures — no changes
- Calibration, performance tab logic — no changes
- `--fire` and `--positive` colors — semantic, same in both modes
- Verdict badge colors (fire, lean) — already work on both backgrounds
- Fire pulse animation — works on both backgrounds

## Verification

1. Toggle works: clicking switches between light and dark immediately, no flash
2. Persistence: refresh page in dark mode — stays dark
3. Top bar layout: wordmark + timestamp on left, date picker centered, toggle icon on right
4. "60s delay" badge no longer appears anywhere
5. All pitcher cards readable in dark mode — text, badges, adjustment pills, EV borders
6. Watchlist cards readable in dark mode
7. Performance table readable in dark mode
8. Banners (info/warn) readable in dark mode
9. Date picker usable in dark mode (border visible, dropdown readable)
10. Toggle icon is a Phosphor icon, not emoji — renders identically on all platforms

## Out of Scope

- Auto-switching based on time of day or OS preference (`prefers-color-scheme`) — possible follow-up but YAGNI for now
- Per-page or per-tab theme — global only
- Any pipeline or data changes
