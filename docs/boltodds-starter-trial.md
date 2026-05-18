# BoltOdds Starter Trial Runbook

This runbook starts the BoltOdds trial in shadow mode only. It captures MLB pitcher strikeout market evidence into Supabase and must not change production picks, dashboard artifacts, provider order, or notifications without Tyler's approval.

Current deployment note as of 2026-05-18: the Render worker should deploy from
`main`. The original `codex/boltodds-starter-trial` branch is historical context
only and will miss the provider-runtime hardening fixes if Render still points
there.

## Trial Contract

- Production source of truth stays GitHub Actions + TheRundown.
- BoltOdds writes only shadow rows with `provider='boltodds'`.
- Render runs one background worker and one WebSocket connection.
- Starter is the decision boundary. Do not upgrade to Pro during this trial.
- FanDuel is required. At least one of BetMGM or BetRivers is required. DraftKings, theScore Bet, and Caesars are watched/reported but no longer block the trial after the 2026-05-07 discovery probe showed DraftKings listed with no exposed markets.
- As of 2026-05-12, Kalshi is intentionally excluded from active BoltOdds WebSocket capture to reduce row volume and keep the trial focused on mainstream-book line movement and CLV evidence. Revisit Kalshi only as part of a separate production-migration plan.

Record these when Tyler starts the free trial:

```text
Trial started at:
Cancel before:
BoltOdds plan:
Render service:
Supabase project:
```

## Files

- `render.yaml` defines the optional Render Blueprint worker.
- `requirements-live.txt` keeps the Render worker dependency set small:
  `requests` plus `websockets`, not the full SciPy/PyBaseball pipeline stack.
- `scripts/probe_boltodds_markets.py` checks Starter readiness before the worker runs.
- `scripts/boltodds_ws_worker.py` connects to the WebSocket and writes Supabase shadow evidence.
- `analytics/diagnostics/boltodds_trial_audit.py` summarizes provider coverage audits.
- `analytics/diagnostics/boltodds_migration_risk_audit.py` summarizes post-trial migration risk.
- `analytics/diagnostics/provider_value_decision_audit.py` compares provider value, shadow-primary coverage, movement flow, pick-evidence usefulness, and cost for the Friday keep/cut decision.

## Environment Variables

Set these in Render:

```text
BOLTODDS_API_KEY=<from BoltOdds trial>
SUPABASE_URL=<project url>
SUPABASE_SERVICE_ROLE_KEY=<service role key>
PYTHON_VERSION=3.11.9
BOLTODDS_TARGET_BOOKS=fanduel,betmgm,betrivers,caesars
BOLTODDS_MARKET_ALIASES=pitcher_strikeouts,player_strikeouts,pitcher strikeouts,player strikeouts
BOLTODDS_BATCH_SIZE=100
BOLTODDS_FLUSH_SECONDS=30
BOLTODDS_ARTIFACT_REFRESH_SECONDS=300
BOLTODDS_RAW_SAMPLE_LIMIT=5
BOLTODDS_WS_MAX_MESSAGES=0
```

Optional:

```text
SLATE_DATE=YYYY-MM-DD
BOLTODDS_WS_URL=wss://spro.agency/api
```

Use `SLATE_DATE` only for a manual dated trial or replay-style run. Normal Render operation should let the worker read the production artifact date. The worker refreshes the production artifact during the long-running WebSocket loop and rotates forward when `today.json` advances; it writes a `slate_rotated` heartbeat when that happens.

## Before Starting The Trial

1. Apply the Supabase migration:

```bash
supabase db push
```

2. Confirm the migration allows BoltOdds rows and creates heartbeat storage:

```sql
select table_name
from information_schema.tables
where table_schema = 'public'
  and table_name = 'market_feed_heartbeats';
```

3. Install live dependencies locally if running a local smoke test:

```bash
python -m pip install -r requirements-live.txt
```

4. Confirm protected production files are unchanged:

```bash
git diff -- .github/workflows/pipeline.yml pipeline/run_pipeline.py pipeline/fetch_odds.py dashboard/data/processed/today.json data/picks_history.json
```

Expected: no output.

## Discovery Probe

After Tyler starts the free trial and provides the key:

```powershell
$env:BOLTODDS_API_KEY = Read-Host "Enter BoltOdds API key"
python scripts/probe_boltodds_markets.py
```

Starter is ready only when:

- MLB is available.
- One pitcher strikeout market is selected.
- FanDuel is available and carries the selected market.
- At least one of BetMGM or BetRivers is available and carries the selected market.

Acceptable missing books:

- DraftKings
- Kalshi, because it is intentionally excluded from active capture for this week's movement-value test
- theScore Bet / scorebet
- Caesars

Blocking examples:

- no MLB sport
- no pitcher strikeout market
- missing FanDuel
- both BetMGM and BetRivers missing for the selected market

Do not start the Render worker if the probe returns `starter_ready=false`.

## Render Setup

Preferred path:

1. Create one private background worker from `render.yaml`, or manually create an equivalent worker.
2. Set the service branch to `main` and keep `autoDeploy` disabled during the trial.
3. Use this build command:

```bash
pip install -r requirements-live.txt
```

If Render tries to build SciPy during this worker deploy, the service is using
the wrong dependency file or missing `PYTHON_VERSION=3.11.9`. The BoltOdds
worker should not install `pipeline/requirements.txt`.

4. Use this start command:

```bash
python scripts/boltodds_ws_worker.py
```

5. Add the environment variables from this runbook.
6. Start the worker only after the discovery probe passes.

Render should run exactly one BoltOdds worker on Starter. Do not create a second service, shell session, or local long-running worker while Render is connected.

## Health Checks

Provider runs:

```sql
select provider, mode, slate_date, status, books_seen, error_message, created_at, completed_at
from market_provider_runs
where provider = 'boltodds'
order by created_at desc
limit 10;
```

Heartbeats:

```sql
select provider, mode, slate_date, observed_at, last_message_at, books_seen, metadata
from market_feed_heartbeats
where provider = 'boltodds'
order by observed_at desc
limit 20;
```

Expected: fresh `observed_at`, recent `last_message_at`, target books in `books_seen`, and current production `slate_date`. After a delayed GitHub full run advances `today.json`, expect a `metadata.event = slate_rotated` heartbeat.

Snapshots:

```sql
select provider, sport_key, market_key, bookmaker_key, player_name, side, line, american_odds, observed_at
from market_snapshots
where provider = 'boltodds'
order by observed_at desc
limit 20;
```

Coverage audits:

```sql
select slate_date, same_line_overlap_count, line_conflict_count, complete_pitcher_line_groups,
       missing_target_books, metadata, created_at
from provider_coverage_audits
where provider = 'boltodds'
order by created_at desc
limit 20;
```

## Daily Review Commands

Export recent rows from Supabase, then run:

```bash
python analytics/diagnostics/boltodds_trial_audit.py --input provider_coverage_audits.json
```

For migration risk:

```bash
python analytics/diagnostics/boltodds_migration_risk_audit.py \
  --provider-runs market_provider_runs.json \
  --coverage-audits provider_coverage_audits.json \
  --heartbeats market_feed_heartbeats.json \
  --artifact-metadata artifact_metadata.json
```

The migration audit result should be treated this way:

- `ready_for_trial`: shadow capture is healthy enough to keep observing.
- `proceed_with_caution`: continue trial, but do not promote anything.
- `not_ready`: stop or fix before spending more trial time.

For the Friday value decision, export the current production artifact,
`market_snapshots`, and `market_pick_evidence`, then run:

```bash
python analytics/diagnostics/provider_value_decision_audit.py \
  --production-artifact today.json \
  --market-snapshots market_snapshots.json \
  --market-pick-evidence market_pick_evidence.json
```

Use this audit to answer whether the paid stack should remain:

- TheRundown as book-of-record plus one live movement source.
- TheRundown plus BoltOdds if the WebSocket feed proves fresher and actionable.
- TheRundown plus PropLine if polling provides enough value and BoltOdds adds complexity.
- TheRundown only plus conservative The Odds fallback if neither paid shadow source changes decisions.

Main-provider sufficiency gate:

- A separate backup provider is optional, not required, if one source covers every slate pitcher/game with at least 3 main books.
- Main books for this decision: FanDuel, DraftKings, BetMGM, BetRivers, and Caesars. Kalshi is out of the active BoltOdds gate for this trial window.
- PropLine can be a main-source candidate at its lower cost if it hits this gate and its polling cadence captures useful line movement, even without working webhooks.
- BoltOdds should only beat that if its WebSocket feed proves meaningfully fresher, more complete, or more actionable than PropLine polling.

Do not keep both PropLine and BoltOdds after the trial unless the evidence shows they answer different valuable questions.

## Stop Procedure

1. Stop the Render worker.
2. Confirm no new BoltOdds snapshots are arriving. Run this query, wait 2 minutes, run it again, and confirm the timestamp is unchanged:

```sql
select max(observed_at) as latest_boltodds_snapshot
from market_snapshots
where provider = 'boltodds';
```

3. Leave Supabase rows in place for review.
4. Do not delete trial evidence until the audit is complete.
5. Cancel the BoltOdds trial before the recorded billing deadline if Starter is not worth keeping.

## Promotion Gates

Do not promote BoltOdds directly from shadow snapshots to production provider.

Next gates, in order:

1. Shadow `line_movement_events` with no pushes.
2. Notification queue with dedupe and stale-feed suppression.
3. Narrow live notifications for movement against current FIRE picks.
4. Fallback provider mode for missing target books only.
5. Selected-book primary mode after at least one paid month.

Production migration requires Tyler's explicit approval.
