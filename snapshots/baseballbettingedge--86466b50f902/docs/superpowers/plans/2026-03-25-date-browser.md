# Date Browser Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users browse historical K-prop data by date — the pipeline archives each run as a dated JSON file and maintains an index, and the dashboard gets a date selector dropdown.

**Architecture:** Three changes: (1) `run_pipeline.py` gains two new functions — a pure `_update_index_dates()` (TDD) and `_write_archive()` that writes a dated copy and updates `index.json`; (2) the GitHub Actions workflow `git add` path is fixed to stage all files under `dashboard/data/processed/`; (3) `dashboard/index.html` boots by fetching `index.json`, populates a date dropdown, and re-fetches the appropriate dated file on selection.

**Tech Stack:** Python 3.11 (pipeline), vanilla JS/HTML (dashboard), GitHub Actions, Netlify static hosting.

---

## File Map

| File | Change |
|---|---|
| `pipeline/run_pipeline.py` | Add `_update_index_dates()` + `_write_archive()`, call archive after each write |
| `tests/test_run_pipeline.py` | **New** — unit tests for `_update_index_dates()` |
| `.github/workflows/pipeline.yml` | Fix `git add` path; rename step |
| `dashboard/index.html` | Add date selector HTML/CSS/JS; update boot sequence + freshness logic |

---

## Task 1: TDD — _update_index_dates (run_pipeline.py)

**Files:**
- Create: `tests/test_run_pipeline.py`
- Modify: `pipeline/run_pipeline.py`

`_update_index_dates` is a pure function — no I/O, fully unit-testable. Build it test-first.

- [ ] **Step 1: Create tests/test_run_pipeline.py with failing tests**

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

from run_pipeline import _update_index_dates


class TestUpdateIndexDates:
    def test_prepends_new_date(self):
        result = _update_index_dates(["2026-03-26", "2026-03-25"], "2026-03-27")
        assert result[0] == "2026-03-27"

    def test_existing_dates_preserved_in_order(self):
        result = _update_index_dates(["2026-03-26", "2026-03-25"], "2026-03-27")
        assert result == ["2026-03-27", "2026-03-26", "2026-03-25"]

    def test_deduplicates_same_date(self):
        # Running pipeline twice on same day should not duplicate the date
        result = _update_index_dates(["2026-03-27", "2026-03-26"], "2026-03-27")
        assert result.count("2026-03-27") == 1
        assert len(result) == 2

    def test_caps_at_max_entries(self):
        existing = [f"2026-01-{i:02d}" for i in range(1, 61)]  # 60 dates
        result = _update_index_dates(existing, "2026-03-27", max_entries=60)
        assert len(result) == 60
        assert result[0] == "2026-03-27"
        assert "2026-01-01" not in result  # oldest entry dropped

    def test_empty_existing_returns_single_entry(self):
        result = _update_index_dates([], "2026-03-27")
        assert result == ["2026-03-27"]

    def test_respects_custom_max_entries(self):
        existing = ["2026-03-26", "2026-03-25", "2026-03-24"]
        result = _update_index_dates(existing, "2026-03-27", max_entries=3)
        assert len(result) == 3
        assert "2026-03-24" not in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge
pytest tests/test_run_pipeline.py -v
```

Expected: `ImportError: cannot import name '_update_index_dates'`

- [ ] **Step 3: Add _update_index_dates to pipeline/run_pipeline.py**

Add this function after the `OUTPUT_PATH` constant (before `run()`):

```python
def _update_index_dates(existing_dates: list, new_date: str,
                        max_entries: int = 60) -> list:
    """
    Pure function. Prepends new_date, deduplicates, caps at max_entries.
    Returns a new list, most recent date first.
    Two pipeline runs on the same date produce exactly one entry.
    """
    updated = [new_date] + [d for d in existing_dates if d != new_date]
    return updated[:max_entries]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_run_pipeline.py -v
```

Expected: 6 tests PASS.

- [ ] **Step 5: Run full suite to check nothing broke**

```bash
pytest tests/ -v
```

Expected: 52 tests PASS (46 existing + 6 new).

- [ ] **Step 6: Commit**

```bash
git add pipeline/run_pipeline.py tests/test_run_pipeline.py
git commit -m "feat(date-browser): _update_index_dates pure function (TDD, 52 passing)"
```

---

## Task 2: Add _write_archive to run_pipeline.py

**Files:**
- Modify: `pipeline/run_pipeline.py`

Writes the dated archive file and updates `index.json`. Called after every `_write_output`. Failures are caught and logged — they never crash the pipeline or affect `today.json`.

- [ ] **Step 1: Add _write_archive function to run_pipeline.py**

Add this function immediately after `_write_output`:

```python
def _write_archive(output: dict, date_str: str) -> None:
    """
    Writes a dated archive copy (YYYY-MM-DD.json) and updates index.json.
    Both files live alongside today.json in dashboard/data/processed/.
    Failures are logged but do not affect today.json or crash the pipeline.
    """
    base_dir = OUTPUT_PATH.parent

    # 1. Write dated archive file
    dated_path = base_dir / f"{date_str}.json"
    try:
        with open(dated_path, "w") as f:
            json.dump(output, f, indent=2)
        log.info("Wrote archive: %s", dated_path)
    except Exception as e:
        log.warning("Failed to write dated archive %s: %s", dated_path, e)
        return   # if dated write fails, skip index update too

    # 2. Load existing index.json (create fresh if missing or corrupt)
    index_path = base_dir / "index.json"
    existing_dates = []
    if index_path.exists():
        try:
            with open(index_path, "r") as f:
                existing_dates = json.load(f).get("dates", [])
        except Exception as e:
            log.warning("Could not read index.json: %s — rebuilding", e)

    # 3. Update and write index.json
    new_dates = _update_index_dates(existing_dates, date_str)
    try:
        with open(index_path, "w") as f:
            json.dump({"dates": new_dates}, f, indent=2)
        log.info("Updated index.json (%d entries)", len(new_dates))
    except Exception as e:
        log.warning("Failed to write index.json: %s", e)
```

- [ ] **Step 2: Call _write_archive from _write_output**

In `_write_output`, add the archive call after the existing `log.info` line:

```python
def _write_output(date_str: str, records: list, props_available: bool) -> None:
    output = {
        "generated_at":    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date":            date_str,
        "props_available": props_available,
        "pitchers":        records,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    log.info("Wrote %s (%d pitchers)", OUTPUT_PATH, len(records))

    # Archive dated copy + update index
    _write_archive(output, date_str)
```

- [ ] **Step 3: Run full test suite to verify nothing broke**

```bash
pytest tests/ -v
```

Expected: 52 PASS.

- [ ] **Step 4: Smoke test locally to verify files are created**

```bash
python pipeline/run_pipeline.py 2026-03-25
```

Expected output includes:
```
Wrote archive: ...dashboard/data/processed/2026-03-25.json
Updated index.json (1 entries)
```

Check files exist:
```bash
ls dashboard/data/processed/
```

Expected: `today.json`, `2026-03-25.json`, `index.json`

- [ ] **Step 5: Commit**

```bash
git add pipeline/run_pipeline.py dashboard/data/processed/
git commit -m "feat(date-browser): _write_archive writes dated file + maintains index.json"
```

---

## Task 3: Fix GitHub Actions workflow git add path

**Files:**
- Modify: `.github/workflows/pipeline.yml`

The current `git add data/processed/today.json` is wrong (old path before the Netlify fix) and would miss the new dated files and index.json. Fix both.

- [ ] **Step 1: Update the Commit step in .github/workflows/pipeline.yml**

Replace the entire "Commit today.json" step:

```yaml
      - name: Commit pipeline output
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add dashboard/data/processed/
          git diff --staged --quiet || git commit -m "chore: pipeline update $(date +%Y-%m-%dT%H:%M:%SZ)"
          git push
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/pipeline.yml
git commit -m "fix(ci): update git add path to dashboard/data/processed/ + rename step"
```

---

## Task 4: Dashboard — date selector UI + updated boot sequence

**Files:**
- Modify: `dashboard/index.html`

Three sub-changes: (1) CSS for the date dropdown, (2) HTML for the selector in the top bar, (3) JS boot sequence and freshness updates.

- [ ] **Step 1: Add date selector CSS**

In the `<style>` block, add after the `#top-bar` section:

```css
/* ── Date selector ──────────────────────────────────────── */
#date-select {
  display: none;   /* shown by JS once index.json loads */
  background: #333;
  color: var(--bg);
  border: 1px solid #555;
  border-radius: 3px;
  padding: 3px 8px;
  font-size: 12px;
  font-weight: 700;
  font-family: 'Courier New', monospace;
  cursor: pointer;
  letter-spacing: .03em;
}
#date-select:focus { outline: none; border-color: #888; }
#date-select option { background: #222; color: #fff; }
```

- [ ] **Step 2: Add date selector to the top bar HTML**

Replace the existing `<div id="top-bar">` element:

```html
  <div id="top-bar">
    <span id="title-date">⚾ BaseballBettingEdge</span>
    <select id="date-select" onchange="onDateChange(this.value)"></select>
    <span id="freshness-badge"></span>
  </div>
```

- [ ] **Step 3: Update the JavaScript**

Replace the entire `<script>` block's Config + Boot sections. Find the existing lines:

```javascript
  // ── Config ────────────────────────────────────────────────
  const DATA_URL    = 'data/processed/today.json';
  const STALE_HOURS = 6;

  // ── Boot ──────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', loadData);

  async function loadData() {
    try {
      const res  = await fetch(DATA_URL + '?t=' + Date.now());
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      renderAll(data);
    } catch (e) {
      showBanner('Could not load data — check network or pipeline status. (' + e.message + ')', 'warn');
      document.getElementById('panel-props').innerHTML =
        '<p class="empty">No data available.</p>';
    }
  }
```

Replace with:

```javascript
  // ── Config ────────────────────────────────────────────────
  const INDEX_URL   = 'data/processed/index.json';
  const TODAY_URL   = 'data/processed/today.json';
  const STALE_HOURS = 6;

  // ── Boot ──────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', boot);

  async function boot() {
    try {
      const res = await fetch(INDEX_URL + '?t=' + Date.now());
      if (!res.ok) throw new Error('no index');
      const index = await res.json();
      const dates = Array.isArray(index.dates) ? index.dates : [];
      populateDateSelector(dates);
      const selected = dates.length > 0 ? dates[0] : null;
      await loadDate(selected);
    } catch (e) {
      // index.json not found — degrade gracefully to today.json
      await loadDate(null);
    }
  }

  function populateDateSelector(dates) {
    const sel   = document.getElementById('date-select');
    const today = new Date().toISOString().slice(0, 10);
    sel.innerHTML = '';
    dates.forEach((d, i) => {
      const opt   = document.createElement('option');
      opt.value   = d;
      const label = new Date(d + 'T12:00:00').toLocaleDateString('en-US', {
        weekday: 'short', month: 'short', day: 'numeric'
      });
      opt.textContent = (i === 0 && d === today) ? 'Today  ·  ' + label : label;
      sel.appendChild(opt);
    });
    // Only show dropdown if there are multiple dates to choose from
    sel.style.display = dates.length > 1 ? 'inline-block' : 'none';
  }

  async function loadDate(dateStr) {
    // Clear any existing banners
    const banner = document.getElementById('freshness-banner');
    banner.style.display = 'none';

    const today  = new Date().toISOString().slice(0, 10);
    const isPast = !!(dateStr && dateStr !== today);
    const url    = dateStr ? `data/processed/${dateStr}.json` : TODAY_URL;

    try {
      const res  = await fetch(url + '?t=' + Date.now());
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      renderAll(data, isPast);
    } catch (e) {
      if (isPast) {
        showBanner('No data available for this date.', 'info');
        document.getElementById('panel-props').innerHTML =
          '<p class="empty">No data available for this date.</p>';
        document.getElementById('panel-watch').innerHTML = '';
      } else {
        showBanner('Could not load data — check network or pipeline status. (' + e.message + ')', 'warn');
        document.getElementById('panel-props').innerHTML =
          '<p class="empty">No data available.</p>';
      }
    }
  }

  function onDateChange(dateStr) {
    loadDate(dateStr);
  }
```

- [ ] **Step 4: Update renderAll to accept isPast and pass to setFreshness**

Find the existing `renderAll` function:

```javascript
  function renderAll(data) {
    // Update title with date
    const dt = data.date
      ? new Date(data.date + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
      : '';
    document.getElementById('title-date').textContent = '⚾ BaseballBettingEdge' + (dt ? '  ·  ' + dt : '');

    setFreshness(data.generated_at);
```

Replace with:

```javascript
  function renderAll(data, isPast = false) {
    // Update title with date
    const dt = data.date
      ? new Date(data.date + 'T12:00:00').toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' })
      : '';
    document.getElementById('title-date').textContent = '⚾ BaseballBettingEdge' + (dt ? '  ·  ' + dt : '');

    setFreshness(data.generated_at, isPast);
```

- [ ] **Step 5: Update setFreshness to handle past dates**

Find the existing `setFreshness` function:

```javascript
  function setFreshness(generatedAt) {
    if (!generatedAt) return;
    const gen   = new Date(generatedAt);
    const now   = new Date();
    const hrs   = (now - gen) / 36e5;
    const time  = gen.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
    const badge = document.getElementById('freshness-badge');

    if (hrs > STALE_HOURS) {
      badge.innerHTML = '<span class="badge-warn">Data may be outdated</span><span class="badge-delay">60s delay</span>';
      showBanner('Pipeline may have failed — data is more than 6 hours old.', 'warn');
    } else {
      badge.innerHTML = '<span class="badge-ok">Updated ' + time + '</span><span class="badge-delay">60s delay</span>';
    }
  }
```

Replace with:

```javascript
  function setFreshness(generatedAt, isPast) {
    if (!generatedAt) return;
    const gen   = new Date(generatedAt);
    const now   = new Date();
    const hrs   = (now - gen) / 36e5;
    const badge = document.getElementById('freshness-badge');

    if (isPast) {
      // Past date — show date + time, no stale warning
      const dateLabel = gen.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      const timeLabel = gen.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
      badge.innerHTML = '<span class="badge-ok">' + dateLabel + ' · ' + timeLabel + '</span><span class="badge-delay">60s delay</span>';
    } else if (hrs > STALE_HOURS) {
      badge.innerHTML = '<span class="badge-warn">Data may be outdated</span><span class="badge-delay">60s delay</span>';
      showBanner('Pipeline may have failed — data is more than 6 hours old.', 'warn');
    } else {
      const time = gen.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
      badge.innerHTML = '<span class="badge-ok">Updated ' + time + '</span><span class="badge-delay">60s delay</span>';
    }
  }
```

- [ ] **Step 6: Verify locally with test fixture**

Open `dashboard/index.html` in a browser. It will fetch `data/processed/index.json` — if that doesn't exist yet, it falls back to `today.json`. Create a quick test index to verify the dropdown:

```bash
cat > dashboard/data/processed/index.json << 'EOF'
{"dates": ["2026-03-25", "2026-03-24", "2026-03-23"]}
EOF
```

Then verify:
- Dropdown appears with 3 options
- First option shows "Today · Tue Mar 25" (or similar based on actual today's date)
- Switching dates shows "No data available for this date" (since only today.json has content)
- Freshness badge shows `Mar 24 · 9:00 AM` format for past dates (not stale warning)

- [ ] **Step 7: Run full test suite**

```bash
pytest tests/ -v
```

Expected: 52 PASS.

- [ ] **Step 8: Commit**

```bash
git add dashboard/index.html dashboard/data/processed/index.json
git commit -m "feat(date-browser): date selector dropdown + updated boot sequence + past-date freshness"
```

---

## Task 5: Push and end-to-end verify

- [ ] **Step 1: Push to GitHub**

```bash
git pull --rebase && git push
```

- [ ] **Step 2: Trigger a manual pipeline run**

Go to: `https://github.com/treidjbi/BaseballbettingEdge/actions`
Select "Baseball Pipeline" → "Run workflow" → Run.

Watch logs for:
```
Wrote archive: .../dashboard/data/processed/2026-03-25.json
Updated index.json (1 entries)
```

- [ ] **Step 3: Verify all three files are committed**

After the run, check `https://github.com/treidjbi/BaseballbettingEdge/tree/main/dashboard/data/processed/`

Expected files: `today.json`, `2026-03-25.json` (or today's date), `index.json`

- [ ] **Step 4: Verify Netlify dashboard shows the date selector**

Open the Netlify URL. With only one date in index.json, the dropdown is hidden (single date = no choice to make). After a second pipeline run, it will show.

To force the dropdown visible for testing, manually update `index.json` in the repo with 2+ dates, push, and confirm the selector appears.
