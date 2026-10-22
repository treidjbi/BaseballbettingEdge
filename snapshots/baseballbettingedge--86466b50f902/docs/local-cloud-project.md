# Local Cloud Project Setup

This repo is already shaped like a small cloud app:

- a Python MLB prop pipeline that writes JSON artifacts
- a static dashboard in `dashboard/`
- Netlify functions in `netlify/functions/`
- optional Supabase sidecar tables for market snapshots and artifact history
- GitHub Actions schedules for production pipeline automation

## Recommended Local Shape

Use local development in layers:

1. Dashboard only
2. Pipeline plus dashboard
3. Supabase sidecar
4. Netlify functions

That keeps the project useful even when paid/live provider keys are not available.

## Required Local Tools

- Python 3.11
- pip / venv
- Node.js with npm
- Git

Optional cloud emulators:

- Supabase CLI, if testing `supabase/migrations/`
- Netlify CLI, if testing `netlify/functions/`

## Environment

Create a local env file from the template:

```bash
cp .env.example .env
```

Fill only the values needed for the layer you are running.

Live pipeline runs need at least:

```bash
RUNDOWN_API_KEY=...
```

Fallback or shadow provider work may also need:

```bash
ODDS_API_KEY=...
PROPLINE_API_KEY=...
```

Supabase sidecar scripts need:

```bash
SUPABASE_URL=...
SUPABASE_SERVICE_ROLE_KEY=...
```

## Dashboard Only

The dashboard already supports local data paths. Start a static server from the
dashboard folder:

```bash
cd dashboard
python3 -m http.server 8000
```

Open:

```text
http://127.0.0.1:8000/v2.html
```

This reads local files from `dashboard/data/processed/` and
`dashboard/data/performance.json`.

## Pipeline Plus Dashboard

Create a Python environment:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r pipeline/requirements.txt
pip install pytest
```

Run tests:

```bash
python -m pytest tests/ -v
```

Run the pipeline for a date:

```bash
python pipeline/run_pipeline.py YYYY-MM-DD
python pipeline/run_pipeline.py YYYY-MM-DD --run-type preview
python pipeline/run_pipeline.py YYYY-MM-DD --run-type grading
```

The pipeline writes dashboard artifacts under:

```text
dashboard/data/processed/
```

## Supabase Sidecar

This repo includes local Supabase config and migrations.

Start Supabase:

```bash
supabase start
supabase db reset
```

Use the local API URL and service role key printed by the CLI in `.env`.

Then run the sidecar scripts:

```bash
python scripts/shadow_artifacts_to_supabase.py
python scripts/shadow_propline_to_supabase.py YYYY-MM-DD
```

These scripts are observation-only. They should not change production pipeline
outputs such as `today.json` or `picks_history.json`.

## Netlify Functions

Install function dependencies:

```bash
cd netlify/functions
npm install
cd ../..
```

Run the local Netlify dev server:

```bash
netlify dev
```

The static dashboard publishes from `dashboard/`, and functions are served from
`netlify/functions/`.

## Production Cloud Mapping

- GitHub Actions runs `pipeline/run_pipeline.py` on the Phoenix-time schedule in
  `.github/workflows/pipeline.yml`.
- Netlify serves the dashboard and functions configured by `netlify.toml`.
- Supabase stores optional sidecar market and artifact history from the shadow
  workflow in `.github/workflows/shadow-market-infra.yml`.

## Local Gaps To Resolve

- Add a root `README.md` once the preferred local workflow is settled.
- Decide whether local Supabase is required for everyday development or only
  for market-infrastructure work.
- Install Python 3.11 locally; the GitHub workflow and Netlify config expect it.
- Install `npm`, `netlify`, and `supabase` CLIs if testing the full cloud stack.
