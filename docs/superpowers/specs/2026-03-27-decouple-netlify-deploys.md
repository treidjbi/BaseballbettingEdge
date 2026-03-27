# Spec: Decouple Data Updates from Netlify Deploys

## Problem

The GitHub Actions pipeline commits updated JSON files to `main` 3× per day. Netlify watches `main` and triggers a full redeploy on every push, consuming deployment credits even though only data files changed — not the app code.

## Goal

Stop Netlify from redeploying on data-only commits. The dashboard should always show fresh data without needing a Netlify deploy.

## Approach

Two minimal changes — one to `netlify.toml`, one to `dashboard/index.html`:

### 1. Netlify ignore rule (`netlify.toml`)

Add an `ignore` command that exits 0 (skip deploy) when only data files changed:

```toml
[build]
  publish = "dashboard"
  functions = "netlify/functions"
  ignore = "git diff --quiet ${CACHED_COMMIT_REF:-HEAD^1} HEAD -- dashboard/index.html netlify/functions/ netlify.toml"

[build.environment]
  PYTHON_VERSION = "3.11"
```

Netlify skips the build when `index.html`, `netlify/functions/`, and `netlify.toml` are all unchanged. Deploys proceed normally when app code is modified.

`CACHED_COMMIT_REF` is a Netlify-provided env var pointing to the last successfully deployed commit. On the very first deploy it is empty, so `${CACHED_COMMIT_REF:-HEAD^1}` falls back to `HEAD^1` — which doesn't exist, causing `git diff` to exit non-zero and proceed with the initial deploy as expected.

### 2. Fetch data from GitHub raw CDN (`dashboard/index.html`)

Replace relative fetch paths with absolute `raw.githubusercontent.com` URLs so the browser always pulls the latest committed JSON — independent of Netlify's deployed snapshot.

There are 3 URL values across 2 fetch() call sites (lines 375-420). The fix is to add a `RAW_BASE` constant in the Config block (line 375) and update the two constants plus one inline template:

**Config block (lines 375-376) — add RAW_BASE, update constants:**
```js
const RAW_BASE   = 'https://raw.githubusercontent.com/treidjbi/baseballbettingedge/main/dashboard/data/processed';
const INDEX_URL  = `${RAW_BASE}/index.json`;
const TODAY_URL  = `${RAW_BASE}/today.json`;
```

**loadDate() (line 420) — update inline template:**
```js
// Before:
const url = dateStr ? `data/processed/${dateStr}.json` : TODAY_URL;
// After:
const url = dateStr ? `${RAW_BASE}/${dateStr}.json` : TODAY_URL;
```

The existing `?t=${Date.now()}` cache-busting param on both fetch() calls is preserved unchanged. GitHub raw has a ~5-minute CDN TTL, so data appears shortly after each pipeline push. `raw.githubusercontent.com` returns `Access-Control-Allow-Origin: *`, so there are no CORS concerns.

## What Does Not Change

- Pipeline code (`pipeline/run_pipeline.py`) — no changes
- GitHub Actions workflow — no changes
- Data file structure and locations — no changes
- Netlify still deploys when `index.html` or functions change

## Verification

1. Push a data-only commit (e.g., touch `dashboard/data/processed/today.json`) and confirm Netlify does **not** trigger a new deploy in the Netlify dashboard.
2. Push a code change to `dashboard/index.html` and confirm Netlify **does** deploy.
3. Open the deployed dashboard and confirm data loads correctly from `raw.githubusercontent.com` (check Network tab — requests should go to `raw.githubusercontent.com`, not the Netlify origin).
4. Navigate to a past date on the date picker and confirm archive files load.
