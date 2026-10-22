# Steam Feed — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the synthesized steam data (derived from single best-odds delta) with a real per-book time series. Unlocks accurate `books_moved` counts on the Steam tab and a real line-movement sparkline in the pitcher detail sheet. Zero extra API quota cost — the data is already being fetched in `fetch_odds.py`.

**Why zero extra quota:** `fetch_odds.py` already pulls per-book odds for every game. The `chosen["over"]` and `chosen["under"]` dicts contain every book's price. We're currently discarding all books except the ref book. This plan surfaces that data.

**Target books:** FanDuel (23), BetMGM (22), DraftKings (19), BetRivers (30).

**File size:** ~15 pitchers × 4 books × 20 refresh runs/day × 2 sides × ~15 bytes = **≤100KB/day**. Resets fresh each morning. No accumulation across days.

---

## New file: `dashboard/data/processed/steam.json`

Shape committed by pipeline on every refresh run (8am–6pm cadence):

```json
{
  "date": "2026-04-21",
  "updated_at": "2026-04-21T14:30:00Z",
  "snapshots": [
    {
      "t": "2026-04-21T08:00:00Z",
      "pitchers": {
        "Gerrit Cole": {
          "k_line": 6.5,
          "FanDuel":    { "over": -120, "under": -105 },
          "BetMGM":     { "over": -115, "under": -110 },
          "DraftKings": { "over": -118, "under": -107 },
          "BetRivers":  { "over": -122, "under": -103 }
        }
      }
    }
  ]
}
```

`snapshots` is an append-only array for the day. Each refresh run reads the existing file, appends one snapshot, and rewrites it. On a new calendar day (Phoenix time) the file is reset to a single snapshot.

---

## Phase A — Emit per-book snapshot, unlock `books_moved` count

**What changes:** Each refresh run writes/appends to `steam.json`. The Steam tab shows real `books_moved / 4` counts. No sparkline yet — that needs multiple snapshots (Phase B).

**Files touched:** `pipeline/fetch_odds.py`, `pipeline/run_pipeline.py`, `dashboard/v2-data.js`, `dashboard/v2-app.jsx`, `netlify.toml` ignore rule.

### Task A.1: Surface per-book odds in `fetch_odds.py`

**File:** `pipeline/fetch_odds.py`

- [ ] **Step 1:** Define the target book IDs at the top of the file alongside `REF_BOOK_PRIORITY`:

```python
TRACKED_BOOKS = {
    "23": "FanDuel",
    "22": "BetMGM",
    "19": "DraftKings",
    "30": "BetRivers",
}
```

- [ ] **Step 2:** In `_parse_event_k_props`, after building `chosen`, capture per-book odds for tracked books:

```python
book_odds = {}
for book_id, book_name in TRACKED_BOOKS.items():
    if book_id in chosen["over"] and book_id in chosen["under"]:
        book_odds[book_name] = {
            "over":  chosen["over"][book_id]["price"],
            "under": chosen["under"][book_id]["price"],
        }
```

- [ ] **Step 3:** Add `"book_odds": book_odds` to the result dict emitted by `_parse_event_k_props`. This field passes through `build_features.py` and lands in `today.json` on each pitcher record.

### Task A.2: Write `steam.json` in `run_pipeline.py`

**File:** `pipeline/run_pipeline.py`

- [ ] **Step 1:** Add a `STEAM_PATH` constant alongside `OUTPUT_PATH`:

```python
STEAM_PATH = Path(__file__).parent.parent / "dashboard" / "data" / "processed" / "steam.json"
```

- [ ] **Step 2:** Add a `_write_steam(pitchers, run_date_str)` function:

```python
def _write_steam(pitchers: list, run_date_str: str) -> None:
    """Append a per-book odds snapshot to steam.json. Resets on new day."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Load existing file if same day, otherwise start fresh
    existing = {}
    try:
        with open(STEAM_PATH) as f:
            existing = json.load(f)
    except Exception:
        pass

    if existing.get("date") != run_date_str:
        existing = {"date": run_date_str, "snapshots": []}

    # Build pitcher snapshot for this run
    pitcher_snap = {}
    for p in pitchers:
        book_odds = p.get("book_odds")
        if not book_odds:
            continue
        pitcher_snap[p["pitcher"]] = {
            "k_line": p.get("k_line"),
            **book_odds,
        }

    if pitcher_snap:
        existing["snapshots"].append({"t": now_iso, "pitchers": pitcher_snap})

    existing["updated_at"] = now_iso

    try:
        with open(STEAM_PATH, "w") as f:
            json.dump(existing, f, indent=2)
        log.info("Wrote steam.json (%d snapshots, %d pitchers)",
                 len(existing["snapshots"]), len(pitcher_snap))
    except Exception as e:
        log.warning("Failed to write steam.json: %s", e)
```

- [ ] **Step 3:** Call `_write_steam(output["pitchers"], date_str)` at the end of `_run_full` (the main refresh/full run path). Do **not** call it from preview or grading — steam is only meaningful during the live refresh window.

### Task A.3: Add `steam.json` to `netlify.toml` deploy-trigger list

**File:** `netlify.toml`

- [ ] **Step 1:** Add `dashboard/data/processed/steam.json` to the `ignore` command's file list. Without this, pipeline commits that only update `steam.json` won't trigger a Netlify redeploy.

### Task A.4: Update `v2-data.js` to read `steam.json`

**File:** `dashboard/v2-data.js`

- [ ] **Step 1:** Add a `STEAM_URL` constant:

```javascript
const STEAM_URL = IS_LOCAL
  ? 'data/processed/steam.json'
  : 'https://raw.githubusercontent.com/treidjbi/baseballbettingedge/main/dashboard/data/processed/steam.json';
```

- [ ] **Step 2:** Add `fetchJSON(STEAM_URL).catch(() => null)` to the `Promise.all` in `__v2DataPromise`.

- [ ] **Step 3:** Replace `buildV2Steam(todayJson)` with a new `buildV2SteamFromFile(steamJson, todayJson)` function that:
  - Falls back to the existing synthetic steam if `steamJson` is null (graceful degradation)
  - When `steamJson` is present, computes `books_moved` by counting which tracked books have moved their odds from the first snapshot to the latest
  - Returns rows in the same shape `v2-app.jsx` already expects, so no UI changes are needed for Phase A beyond showing the count

Shape of a returned row (add `books_moved` and `books_total`):
```javascript
{
  pitcher, team, opp, game_time, k_line, open_line,
  direction, cents, open_odds, cur_odds,
  books_moved: 3,   // was null before
  books_total: 4,
  note, my_pick,
}
```

### Task A.5: Show `books_moved` in the Steam tab UI

**Files:** `dashboard/v2-app.jsx`, `dashboard/v2.html`

- [ ] **Step 1:** In `SteamTab`, find the row rendering and add a `books_moved` badge where `books_total` is now shown as `null`. Current fallback text is "Odds only" / "Line X → Y" in the `note` field. Show `3/4 books` when available.

- [ ] **Step 2:** Recompile `v2-app.jsx → v2-app.js`.

### Rollback for Phase A

Remove the `_write_steam` call from `_run_full`. `steam.json` won't be written; `v2-data.js` falls back to synthetic steam. Zero user-visible impact beyond losing the books-moved count.

---

## Phase B — Real sparkline in the detail sheet

**Do not proceed until Phase A has run for at least 3 days** so there's real time-series data to render.

**What changes:** The detail sheet's line-movement sparkline (currently a 12-step sine-noise fake) is replaced with real per-book odds history from `steam.json`.

### Task B.1: Parse time series from `steam.json` in `v2-data.js`

- [ ] **Step 1:** For each pitcher in `buildV2SteamFromFile`, extract the time series from `snapshots`:

```javascript
// For the picked side (e.g. OVER), collect {t, over} from each snapshot that has this pitcher
const series = steamJson.snapshots
  .filter(s => s.pitchers[pitcher])
  .map(s => ({ t: s.t, over: s.pitchers[pitcher].FanDuel?.over ?? null, under: s.pitchers[pitcher].FanDuel?.under ?? null }));
```

- [ ] **Step 2:** Attach `series` to the steam row. `v2-app.jsx` already expects a `series` field on each row for the sparkline — currently it's synthesized in `buildV2Steam`.

### Task B.2: Render real sparkline in the detail sheet

**File:** `dashboard/v2-app.jsx`

- [ ] **Step 1:** In the detail sheet's line-movement section, replace the synthetic 12-step sparkline with the real `series` array. The rendering code doesn't need to change — it already maps over the series array to draw SVG path points. Just ensure the `series` field is populated from Phase B.1.

- [ ] **Step 2:** Recompile.

### Rollback for Phase B

Pass `null` for `series` on each row. The sheet falls back to the synthetic sparkline.

---

## What we are NOT doing in this plan

- Real-time WebSocket odds updates (not in Starter plan)
- Storing steam history across multiple days
- Tracking more than 4 books
- Line movement alerts / push notifications for steam (could be a future phase)

---

## File map

| File | Change |
|------|--------|
| `pipeline/fetch_odds.py` | Add `TRACKED_BOOKS`, emit `book_odds` per pitcher |
| `pipeline/run_pipeline.py` | Add `STEAM_PATH`, `_write_steam()`, call it from full/refresh runs |
| `netlify.toml` | Add `steam.json` to deploy-trigger ignore list |
| `dashboard/data/processed/steam.json` | New file, written by pipeline |
| `dashboard/v2-data.js` | Fetch steam.json, `buildV2SteamFromFile()` |
| `dashboard/v2-app.jsx` | Show books_moved count (Phase A), real sparkline (Phase B) |
| `dashboard/v2-app.js` | Recompiled output |
| `dashboard/v2.html` | Minor CSS for books-moved badge if needed |
