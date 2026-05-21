# Supabase Operational Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Start migrating BaseballBettingEdge operations toward Supabase + BoltOdds + PropLine while keeping GitHub artifacts and TheRundown as rollback surfaces.

**Architecture:** Promote Supabase from shadow evidence into a gated operational control plane for lock intent, provider market state, and storage guardrails. Keep all production-facing changes behind explicit flags so the first phase can run as a canary without changing model math, thresholds, staking, grading, or provider order.

**Tech Stack:** Python 3.11, GitHub Actions, Supabase Postgres/REST, Render live-layer cron, existing BoltOdds/PropLine market tables, pytest.

---

Date: 2026-05-19
Owner: Tyler + Codex
Status: Implementation plan

## Operating Decision

Tyler approved starting the operational migration on 2026-05-19. This plan does
not remove TheRundown, does not remove GitHub artifact publishing, and does not
flip the provider-source flags by default. It makes the first production-shaped
Supabase control-plane pieces real and gated.

## Non-Goals

- Do not change EV formulas, thresholds, staking, calibration, or
  `formula_change_date`.
- Do not turn off TheRundown.
- Do not enable `OFFICIAL_MARKET_SOURCE=boltodds_propline` by default.
- Do not send BoltOdds-sourced live notifications by default.
- Do not delete raw Supabase rows without an explicit `--execute` command and
  a second safety environment flag.
- Do not make dashboard artifacts read directly from raw `market_snapshots`.

## File Map

- `supabase/migrations/20260519_operational_pick_locks.sql`
  - New gated operational lock-intent table written by the live layer and later
    consumed by the GitHub pipeline.
- `market_infra/operational_locks.py`
  - Pure builder for lock-intent rows from `today.json` pitchers.
- `scripts/build_live_events_to_supabase.py`
  - Optional writer for `operational_pick_locks`, disabled by default.
- `pipeline/fetch_results.py`
  - SQLite helper that applies external lock rows to open picks.
- `pipeline/run_pipeline.py`
  - Optional Supabase lock consumer behind `ENABLE_SUPABASE_LOCK_CONSUMER=true`.
- `.github/workflows/pipeline.yml`
  - Manual `lock` dispatch mode for emergency lock-only artifact publishing.
- `market_infra/supabase_writer.py`
  - Add REST helpers for exact counts and guarded deletes.
- `scripts/audit_supabase_row_volume.py`
  - Read-only row-volume report for Supabase operational tables.
- `scripts/retire_market_snapshots.py`
  - Dry-run-first raw snapshot retention tool with compact-before-delete guards.
- `docs/current-state.md`
  - Update the operating posture from pure shadow to gated operational migration.
- `docs/operational-risk-register.md`
  - Add operational lock-ledger and retention execution guardrails.
- Tests:
  - `tests/test_operational_locks.py`
  - `tests/test_operational_pick_locks_schema.py`
  - `tests/test_live_layer_worker.py`
  - `tests/test_fetch_results.py`
  - `tests/test_run_pipeline.py`
  - `tests/test_pipeline_workflow_contract.py`
  - `tests/test_market_infra_supabase_writer.py`
  - `tests/test_audit_supabase_row_volume.py`
  - `tests/test_retire_market_snapshots.py`

## Phase 1 Acceptance Criteria

- Render/live-layer can write first-seen lock-intent rows to Supabase when
  `ENABLE_SUPABASE_LOCK_LEDGER=true`.
- GitHub pipeline can consume Supabase lock rows when
  `ENABLE_SUPABASE_LOCK_CONSUMER=true`.
- Both flags default to off in code.
- Manual GitHub `mode=lock` dispatch works and commits only lock-related
  artifact changes.
- Row-volume audit is read-only.
- Raw snapshot retention defaults to dry-run and refuses deletion unless compact
  summaries exist, `--execute` is passed, and
  `ALLOW_MARKET_SNAPSHOT_DELETE=true` is set.
- Provider cutover remains separate: existing `OFFICIAL_MARKET_SOURCE` and
  `ENABLE_BOLTODDS_PIPELINE_SOURCE` flags are not changed by this plan.

## Task 1: Operational Lock Ledger Schema And Builder

**Files:**
- Create: `supabase/migrations/20260519_operational_pick_locks.sql`
- Create: `market_infra/operational_locks.py`
- Create: `tests/test_operational_pick_locks_schema.py`
- Create: `tests/test_operational_locks.py`

- [ ] **Step 1: Add failing schema tests**

Add `tests/test_operational_pick_locks_schema.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "supabase" / "migrations" / "20260519_operational_pick_locks.sql"


def test_operational_pick_locks_schema_has_required_contract():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "create table if not exists public.operational_pick_locks" in sql
    assert "dedupe_key text not null unique" in sql
    assert "slate_date date not null" in sql
    assert "normalized_pitcher text not null" in sql
    assert "side text not null check (side in ('over', 'under'))" in sql
    assert "locked_at timestamptz not null" in sql
    assert "game_time timestamptz not null" in sql
    assert "should_lock_at timestamptz not null" in sql
    assert "source_artifact_sha256 text" in sql
    assert "metadata jsonb not null default '{}'::jsonb" in sql


def test_operational_pick_locks_schema_is_rls_guarded():
    sql = MIGRATION.read_text(encoding="utf-8")

    assert "alter table public.operational_pick_locks enable row level security" in sql
    assert "grant select on public.operational_pick_locks to bbe_ops_readonly" in sql
    assert "bbe_ops_readonly_select_operational_pick_locks" in sql
```

- [ ] **Step 2: Add failing builder tests**

Add `tests/test_operational_locks.py`:

```python
from datetime import datetime

from market_infra.operational_locks import build_operational_lock_rows


def _pitcher(*, game_time="2026-05-19T20:00:00Z", locked_at=None, verdict="FIRE 1u"):
    return {
        "pitcher": "Tarik Skubal",
        "team": "DET",
        "opp_team": "BOS",
        "ref_book": "FanDuel",
        "game_time": game_time,
        "tracked_picks": [
            {
                "pitcher": "Tarik Skubal",
                "side": "over",
                "display_verdict": verdict,
                "display_k_line": 6.5,
                "display_odds": -115,
                "locked_at": locked_at,
                "game_time": game_time,
            }
        ],
    }


def test_build_operational_lock_rows_captures_first_due_unlocked_pick():
    rows = build_operational_lock_rows(
        slate_date="2026-05-19",
        pitchers=[_pitcher()],
        observed_at=datetime.fromisoformat("2026-05-19T19:32:00+00:00"),
        source_artifact_path="https://raw.example/today.json",
        source_artifact_sha256="sha",
        artifact_generated_at="2026-05-19T19:20:00Z",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["dedupe_key"] == "2026-05-19:tarik skubal:over"
    assert row["status_at_capture"] == "due_now"
    assert row["locked_at"] == "2026-05-19T19:32:00+00:00"
    assert row["should_lock_at"] == "2026-05-19T19:30:00+00:00"
    assert row["locked_k_line"] == 6.5
    assert row["locked_odds"] == -115
    assert row["locked_verdict"] == "FIRE 1u"
    assert row["locked_book"] == "FanDuel"
    assert row["metadata"]["artifact_generated_at"] == "2026-05-19T19:20:00+00:00"


def test_build_operational_lock_rows_skips_not_due_locked_started_and_pass():
    rows = build_operational_lock_rows(
        slate_date="2026-05-19",
        pitchers=[
            _pitcher(game_time="2026-05-19T21:30:00Z"),
            _pitcher(locked_at="2026-05-19T19:28:00Z"),
            _pitcher(game_time="2026-05-19T19:20:00Z"),
            _pitcher(verdict="PASS"),
        ],
        observed_at=datetime.fromisoformat("2026-05-19T19:32:00+00:00"),
        source_artifact_path="today.json",
        source_artifact_sha256="sha",
    )

    assert rows == []


def test_build_operational_lock_rows_captures_missed_before_game_start():
    rows = build_operational_lock_rows(
        slate_date="2026-05-19",
        pitchers=[_pitcher()],
        observed_at=datetime.fromisoformat("2026-05-19T19:45:00+00:00"),
        source_artifact_path="today.json",
        source_artifact_sha256="sha",
    )

    assert rows[0]["status_at_capture"] == "missed_lock"
    assert rows[0]["minutes_until_start"] == 15.0
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_operational_pick_locks_schema.py tests/test_operational_locks.py -q
```

Expected: fail because the migration and module do not exist yet.

- [ ] **Step 4: Add migration**

Create `supabase/migrations/20260519_operational_pick_locks.sql`:

```sql
create table if not exists public.operational_pick_locks (
  id uuid primary key default gen_random_uuid(),
  dedupe_key text not null unique,
  slate_date date not null,
  source text not null default 'live_layer',
  status_at_capture text not null check (status_at_capture in ('due_now', 'missed_lock')),
  observed_at timestamptz not null,
  locked_at timestamptz not null,
  pitcher text not null,
  normalized_pitcher text not null,
  side text not null check (side in ('over', 'under')),
  locked_verdict text not null,
  locked_k_line numeric not null,
  locked_odds integer not null,
  locked_adj_ev numeric,
  locked_book text,
  game_time timestamptz not null,
  should_lock_at timestamptz not null,
  minutes_until_start numeric,
  source_artifact_path text not null,
  source_artifact_sha256 text,
  consumed_at timestamptz,
  metadata jsonb not null default '{}'::jsonb,
  inserted_at timestamptz not null default now()
);

create index if not exists idx_operational_pick_locks_slate
  on public.operational_pick_locks (slate_date desc, inserted_at desc);

create index if not exists idx_operational_pick_locks_pick
  on public.operational_pick_locks (slate_date desc, normalized_pitcher, side);

alter table public.operational_pick_locks enable row level security;

comment on table public.operational_pick_locks is
  'Gated operational lock intent rows captured by the live layer before first pitch. Consumed by GitHub pipeline only when ENABLE_SUPABASE_LOCK_CONSUMER=true.';

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'bbe_ops_readonly') then
    execute 'grant select on public.operational_pick_locks to bbe_ops_readonly';
    execute 'drop policy if exists bbe_ops_readonly_select_operational_pick_locks on public.operational_pick_locks';
    execute 'create policy bbe_ops_readonly_select_operational_pick_locks on public.operational_pick_locks for select to bbe_ops_readonly using (true)';
  end if;
end $$;
```

- [ ] **Step 5: Add pure builder**

Create `market_infra/operational_locks.py` with:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from pipeline.name_utils import normalize


TRACKED_VERDICT_RANK = {
    "PASS": 0,
    "LEAN": 1,
    "FIRE 1u": 2,
    "FIRE 2u": 3,
}
LOCK_WINDOW_MINUTES = 30
MISSED_LOCK_GRACE_MINUTES = 5


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).isoformat()


def _numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _tracked_pick_rows(pitcher: dict[str, Any]) -> list[dict[str, Any]]:
    tracked = pitcher.get("tracked_picks")
    if isinstance(tracked, list):
        return [row for row in tracked if isinstance(row, dict)]
    return []


def _pick_verdict(pick: dict[str, Any]) -> str:
    return str(
        pick.get("display_verdict")
        or pick.get("locked_verdict")
        or pick.get("actionable_verdict")
        or pick.get("verdict")
        or "PASS"
    ).strip() or "PASS"


def _capture_status(observed_at: datetime, game_time: datetime) -> tuple[str | None, datetime, float]:
    should_lock_at = game_time - timedelta(minutes=LOCK_WINDOW_MINUTES)
    minutes_until_start = round((game_time - observed_at).total_seconds() / 60.0, 2)
    if observed_at >= game_time:
        return None, should_lock_at, minutes_until_start
    if observed_at >= should_lock_at + timedelta(minutes=MISSED_LOCK_GRACE_MINUTES):
        return "missed_lock", should_lock_at, minutes_until_start
    if observed_at >= should_lock_at:
        return "due_now", should_lock_at, minutes_until_start
    return None, should_lock_at, minutes_until_start


def build_operational_lock_rows(
    *,
    slate_date: str,
    pitchers: list[dict[str, Any]],
    observed_at: datetime,
    source_artifact_path: str,
    source_artifact_sha256: str | None,
    artifact_generated_at: str | datetime | None = None,
) -> list[dict[str, Any]]:
    observed_utc = _parse_datetime(observed_at)
    if observed_utc is None:
        raise ValueError("observed_at must be parseable")

    artifact_generated = _parse_datetime(artifact_generated_at)
    rows: list[dict[str, Any]] = []
    for pitcher in pitchers:
        pitcher_name = str(pitcher.get("pitcher") or "").strip()
        if not pitcher_name:
            continue
        normalized_pitcher = normalize(pitcher_name)
        for pick in _tracked_pick_rows(pitcher):
            side = str(pick.get("side") or "").strip().lower()
            if side not in {"over", "under"}:
                continue
            if _parse_datetime(pick.get("locked_at")) is not None:
                continue
            verdict = _pick_verdict(pick)
            if TRACKED_VERDICT_RANK.get(verdict, 0) <= TRACKED_VERDICT_RANK["PASS"]:
                continue
            game_time = _parse_datetime(pick.get("game_time") or pitcher.get("game_time"))
            if game_time is None:
                continue
            status, should_lock_at, minutes_until_start = _capture_status(observed_utc, game_time)
            if status is None:
                continue
            line = _numeric(pick.get("display_k_line") or pick.get("locked_k_line") or pick.get("k_line"))
            odds = _integer(pick.get("display_odds") or pick.get("locked_odds") or pick.get("odds"))
            if line is None or odds is None:
                continue
            book = (
                pick.get("book")
                or pick.get("current_book")
                or pitcher.get(f"best_{side}_book")
                or pitcher.get("ref_book")
            )
            rows.append({
                "dedupe_key": f"{slate_date}:{normalized_pitcher}:{side}",
                "slate_date": slate_date,
                "source": "live_layer",
                "status_at_capture": status,
                "observed_at": _isoformat(observed_utc),
                "locked_at": _isoformat(observed_utc),
                "pitcher": str(pick.get("pitcher") or pitcher_name),
                "normalized_pitcher": normalized_pitcher,
                "side": side,
                "locked_verdict": verdict,
                "locked_k_line": line,
                "locked_odds": odds,
                "locked_adj_ev": _numeric(pick.get("display_adj_ev") or pick.get("locked_adj_ev") or pick.get("adj_ev")),
                "locked_book": str(book).strip() if book else None,
                "game_time": _isoformat(game_time),
                "should_lock_at": _isoformat(should_lock_at),
                "minutes_until_start": minutes_until_start,
                "source_artifact_path": source_artifact_path,
                "source_artifact_sha256": source_artifact_sha256,
                "metadata": {
                    "team": pitcher.get("team"),
                    "opp_team": pitcher.get("opp_team"),
                    "artifact_generated_at": _isoformat(artifact_generated),
                    "lock_window_minutes": LOCK_WINDOW_MINUTES,
                    "missed_lock_grace_minutes": MISSED_LOCK_GRACE_MINUTES,
                },
            })
    return rows
```

- [ ] **Step 6: Run tests**

Run:

```bash
python -m pytest tests/test_operational_pick_locks_schema.py tests/test_operational_locks.py -q
```

Expected: pass.

## Task 2: Live-Layer Operational Lock Writer

**Files:**
- Modify: `scripts/build_live_events_to_supabase.py`
- Modify: `tests/test_live_layer_worker.py`

- [ ] **Step 1: Add failing live-layer tests**

Add tests to `tests/test_live_layer_worker.py`:

```python
def test_worker_skips_operational_lock_ledger_by_default(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "market_feed_heartbeats": [],
        "game_reminder_state": [],
    })

    with patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["operational_pick_locks"] == {"skipped": True, "reason": "disabled"}
    assert not any(call[0] == "operational_pick_locks" for call in writer.insert_ignores)


def test_worker_writes_operational_lock_rows_when_enabled(tmp_path, monkeypatch):
    pitcher = _fire_pitcher()
    pitcher["game_time"] = "2026-05-06T18:30:00Z"
    pitcher["tracked_picks"][0]["game_time"] = "2026-05-06T18:30:00Z"
    today = _write_artifact(tmp_path, [pitcher])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "market_feed_heartbeats": [],
        "game_reminder_state": [],
    })
    monkeypatch.setenv("ENABLE_SUPABASE_LOCK_LEDGER", "true")

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:02:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["operational_pick_locks"]["skipped"] is False
    assert result["operational_pick_locks"]["rows"] == 1
    lock_call = next(call for call in writer.insert_ignores if call[0] == "operational_pick_locks")
    assert lock_call[2] == "dedupe_key"
```

If the fake writer uses a different attribute name, adapt assertions to the
existing fake writer shape in the same file.

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python -m pytest tests/test_live_layer_worker.py -q
```

Expected: fail because operational lock writer is missing.

- [ ] **Step 3: Implement gated writer**

Modify `scripts/build_live_events_to_supabase.py`:

```python
from market_infra.operational_locks import build_operational_lock_rows
```

Add:

```python
def _operational_lock_ledger_enabled() -> bool:
    return _env_flag("ENABLE_SUPABASE_LOCK_LEDGER", default=False)


def _write_operational_pick_locks(
    *,
    writer: SupabaseMarketWriter,
    slate_date: str,
    payload: dict[str, Any],
    observed_at: datetime,
    artifact_source: str,
    artifact_sha: str | None,
) -> dict[str, Any]:
    if not _operational_lock_ledger_enabled():
        return {"skipped": True, "reason": "disabled"}
    try:
        rows = build_operational_lock_rows(
            slate_date=slate_date,
            pitchers=payload.get("pitchers") or [],
            observed_at=observed_at,
            source_artifact_path=artifact_source,
            source_artifact_sha256=artifact_sha,
            artifact_generated_at=payload.get("generated_at"),
        )
        writer.insert_ignore_rows("operational_pick_locks", rows, on_conflict="dedupe_key")
        return {"skipped": False, "rows": len(rows)}
    except Exception as error:
        print(f"Warning: operational lock ledger write failed ({error})", file=sys.stderr)
        return {"skipped": True, "reason": "write_failed", "error": str(error)[:1000]}
```

Call it after `live_pick_state` is upserted and before market-line rebuild:

```python
operational_pick_locks = _write_operational_pick_locks(
    writer=writer,
    slate_date=slate_date,
    payload=payload,
    observed_at=observed_at,
    artifact_source=artifact_source,
    artifact_sha=artifact_sha,
)
```

Add it to the returned dict:

```python
"operational_pick_locks": operational_pick_locks,
```

- [ ] **Step 4: Run tests**

Run:

```bash
python -m pytest tests/test_live_layer_worker.py tests/test_operational_locks.py -q
```

Expected: pass.

## Task 3: GitHub Pipeline Consumer For Supabase Lock Rows

**Files:**
- Modify: `pipeline/fetch_results.py`
- Modify: `pipeline/run_pipeline.py`
- Modify: `tests/test_fetch_results.py`
- Modify: `tests/test_run_pipeline.py`

- [ ] **Step 1: Add failing SQLite helper tests**

Append to `tests/test_fetch_results.py`:

```python
def test_apply_external_lock_rows_locks_open_pick_after_game_started(tmp_db):
    db_path, fr = tmp_db
    with fr.get_db() as conn:
        _seed_pick_with_game_time(conn, "2026-04-15T17:10:00Z", side="over", adj_ev=0.05, odds=-115)
    rows = [{
        "slate_date": "2026-04-15",
        "pitcher": "Test Pitcher",
        "side": "over",
        "locked_at": "2026-04-15T16:42:00Z",
        "locked_k_line": 7.5,
        "locked_odds": -120,
        "locked_adj_ev": 0.07,
        "locked_verdict": "FIRE 1u",
    }]

    with fr.get_db() as conn:
        count = fr.apply_external_lock_rows(conn, rows)

    assert count == 1
    with fr.get_db() as conn:
        row = conn.execute("SELECT locked_at, locked_odds, locked_adj_ev, locked_verdict FROM picks").fetchone()
    assert row["locked_at"] == "2026-04-15T16:42:00Z"
    assert row["locked_odds"] == -120
    assert abs(row["locked_adj_ev"] - 0.07) < 0.001
    assert row["locked_verdict"] == "FIRE 1u"


def test_apply_external_lock_rows_is_idempotent_and_does_not_unlock(tmp_db):
    db_path, fr = tmp_db
    with fr.get_db() as conn:
        _seed_pick_with_game_time(conn, "2026-04-15T17:10:00Z", side="over")
    rows = [{
        "slate_date": "2026-04-15",
        "pitcher": "Test Pitcher",
        "side": "over",
        "locked_at": "2026-04-15T16:42:00Z",
        "locked_k_line": 7.5,
        "locked_odds": -120,
        "locked_adj_ev": 0.07,
        "locked_verdict": "FIRE 1u",
    }]
    with fr.get_db() as conn:
        assert fr.apply_external_lock_rows(conn, rows) == 1
        assert fr.apply_external_lock_rows(conn, rows) == 0
```

- [ ] **Step 2: Add helper implementation**

In `pipeline/fetch_results.py`, add:

```python
def apply_external_lock_rows(conn: sqlite3.Connection, lock_rows: list[dict]) -> int:
    """Apply pregame lock snapshots captured outside the GitHub pipeline."""
    updated = 0
    for row in lock_rows:
        pitcher = str(row.get("pitcher") or "").strip()
        side = str(row.get("side") or "").strip().lower()
        locked_at = str(row.get("locked_at") or "").strip()
        if not pitcher or side not in {"over", "under"} or not locked_at:
            continue
        conn.execute("""
            UPDATE picks
            SET locked_at = ?,
                locked_k_line = COALESCE(?, k_line),
                locked_odds = COALESCE(?, odds),
                locked_adj_ev = COALESCE(?, adj_ev),
                locked_verdict = COALESCE(?, verdict)
            WHERE pitcher = ?
              AND side = ?
              AND locked_at IS NULL
              AND result IS NULL
        """, (
            locked_at,
            row.get("locked_k_line"),
            row.get("locked_odds"),
            row.get("locked_adj_ev"),
            row.get("locked_verdict"),
            pitcher,
            side,
        ))
        updated += conn.execute("SELECT changes()").fetchone()[0]
    conn.commit()
    log.info("apply_external_lock_rows: locked %d picks from external lock ledger", updated)
    return updated
```

- [ ] **Step 3: Add pipeline consumer tests**

In `tests/test_run_pipeline.py`, add a focused test around a new helper:

```python
def test_supabase_lock_consumer_disabled_by_default(monkeypatch):
    import run_pipeline

    monkeypatch.delenv("ENABLE_SUPABASE_LOCK_CONSUMER", raising=False)
    assert run_pipeline._supabase_lock_consumer_enabled() is False


def test_fetch_supabase_operational_lock_rows_reads_expected_table(monkeypatch):
    import run_pipeline

    calls = []

    class FakeWriter:
        def select_rows(self, table, params):
            calls.append((table, params))
            return [{"pitcher": "Test Pitcher", "side": "over"}]

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    rows = run_pipeline._fetch_supabase_operational_lock_rows("2026-05-19", writer=FakeWriter())

    assert rows == [{"pitcher": "Test Pitcher", "side": "over"}]
    assert calls[0][0] == "operational_pick_locks"
    assert calls[0][1]["slate_date"] == "eq.2026-05-19"
```

- [ ] **Step 4: Wire consumer behind flag**

In `pipeline/run_pipeline.py`:

- Import `apply_external_lock_rows`.
- Add `_supabase_lock_consumer_enabled()`.
- Add `_fetch_supabase_operational_lock_rows(date_str, writer=None)`.
- Add `_apply_supabase_operational_locks(date_str)` that:
  - returns 0 when disabled;
  - fetches rows from `operational_pick_locks`;
  - opens SQLite connection;
  - calls `apply_external_lock_rows`;
  - logs count;
  - never raises unless strict env `SUPABASE_LOCK_CONSUMER_STRICT=true`.

Use:

```python
def _supabase_lock_consumer_enabled() -> bool:
    return os.environ.get("ENABLE_SUPABASE_LOCK_CONSUMER", "false").strip().lower() in {"1", "true", "yes", "on"}
```

Fetch rows with:

```python
writer.select_rows(
    "operational_pick_locks",
    {
        "slate_date": f"eq.{date_str}",
        "order": "locked_at.asc",
        "limit": "1000",
    },
)
```

Call `_apply_supabase_operational_locks(date_str)`:

- in `_run_lock_only`, after `load_history_into_db()` and before
  `lock_due_picks`;
- in the full/refresh path after `seed_picks(...)` and before
  `lock_due_picks(...)`.

- [ ] **Step 5: Export history when external locks apply**

In `_run_lock_only`, treat external locks like normal locks:

```python
external_locked = _apply_supabase_operational_locks(date_str)
locked = lock_due_picks(...)
if external_locked + locked > 0:
    export_db_to_history()
    _enrich_archives_with_tracked_picks()
```

In the full/refresh path, no extra export call is needed if the existing flow
already exports history after normal locking. If not, add the same count to the
existing lock count path.

- [ ] **Step 6: Run tests**

Run:

```bash
python -m pytest tests/test_fetch_results.py::test_apply_external_lock_rows_locks_open_pick_after_game_started tests/test_fetch_results.py::test_apply_external_lock_rows_is_idempotent_and_does_not_unlock tests/test_run_pipeline.py -q
```

Expected: pass.

## Task 4: Manual Lock-Only Workflow Dispatch

**Files:**
- Modify: `.github/workflows/pipeline.yml`
- Modify: `tests/test_pipeline_workflow_contract.py`

- [ ] **Step 1: Add failing workflow-contract test**

Add to `tests/test_pipeline_workflow_contract.py`:

```python
def test_pipeline_workflow_exposes_manual_lock_mode():
    workflow_text = _read_workflow()
    run_block = _extract_step_block(workflow_text, "Run pipeline")

    assert "- lock" in workflow_text
    assert 'if [ "$MODE" = "lock" ]; then' in run_block
    assert "python pipeline/run_pipeline.py $TODAY --run-type lock" in run_block
    assert "exit 0" in run_block
```

- [ ] **Step 2: Update workflow**

In `.github/workflows/pipeline.yml`, add `lock` to `workflow_dispatch.inputs.mode.options`.

In the `Run pipeline` shell block, after the `propline_probe` branch and before
scheduled-run mapping, add:

```bash
if [ "$MODE" = "lock" ]; then
  python pipeline/run_pipeline.py $TODAY --run-type lock
  exit 0
fi
```

Do not add more scheduled cron entries in this task. The Supabase lock ledger is
the lock-independence path; the manual mode is an operator escape hatch.

- [ ] **Step 3: Run tests**

Run:

```bash
python -m pytest tests/test_pipeline_workflow_contract.py tests/test_workflow_schedule.py -q
```

Expected: pass.

## Task 5: Row-Volume Audit And Dry-Run Retention Guardrails

**Files:**
- Modify: `market_infra/supabase_writer.py`
- Create: `scripts/audit_supabase_row_volume.py`
- Create: `scripts/retire_market_snapshots.py`
- Modify: `tests/test_market_infra_supabase_writer.py`
- Create: `tests/test_audit_supabase_row_volume.py`
- Create: `tests/test_retire_market_snapshots.py`

- [ ] **Step 1: Add writer tests**

Add tests in `tests/test_market_infra_supabase_writer.py` for:

```python
def test_count_rows_reads_content_range(monkeypatch):
    from market_infra.supabase_writer import SupabaseMarketWriter

    captured = {}

    class Response:
        headers = {"Content-Range": "0-0/42"}
        status_code = 206
        def raise_for_status(self): pass

    def fake_get(url, headers, params, timeout):
        captured["headers"] = headers
        captured["params"] = params
        return Response()

    monkeypatch.setattr("market_infra.supabase_writer.requests.get", fake_get)
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret")

    assert writer.count_rows("market_snapshots", {"provider": "eq.boltodds"}) == 42
    assert captured["headers"]["Prefer"] == "count=exact"
    assert captured["params"]["limit"] == "1"


def test_delete_rows_requires_params(monkeypatch):
    from market_infra.supabase_writer import SupabaseMarketWriter

    writer = SupabaseMarketWriter("https://example.supabase.co", "secret")
    try:
        writer.delete_rows("market_snapshots", {})
    except ValueError as error:
        assert "delete params are required" in str(error)
    else:
        raise AssertionError("delete_rows should reject empty params")
```

- [ ] **Step 2: Implement writer helpers**

In `market_infra/supabase_writer.py`, add:

```python
    def count_rows(self, table: str, params: dict[str, str] | None = None) -> int:
        query = dict(params or {})
        query.setdefault("select", "id")
        query["limit"] = "1"
        response = requests.get(
            f"{self.supabase_url}/rest/v1/{table}",
            headers=self._headers("count=exact"),
            params=query,
            timeout=20,
        )
        response.raise_for_status()
        content_range = response.headers.get("Content-Range", "")
        if "/" not in content_range:
            return 0
        total = content_range.rsplit("/", 1)[-1]
        return 0 if total == "*" else int(total)

    def delete_rows(self, table: str, params: dict[str, str]) -> int:
        if not params:
            raise ValueError("delete params are required")
        response = requests.delete(
            f"{self.supabase_url}/rest/v1/{table}",
            headers=self._headers("return=minimal"),
            params=params,
            timeout=20,
        )
        response.raise_for_status()
        return int(response.headers.get("Content-Range", "0-0/0").rsplit("/", 1)[-1] or 0)
```

- [ ] **Step 3: Add row-volume audit script**

Create `scripts/audit_supabase_row_volume.py` with a read-only `run(writer)`
that reports exact counts for:

```python
TABLES = [
    "market_snapshots",
    "market_feed_heartbeats",
    "line_movement_events",
    "shadow_notification_candidates",
    "shadow_pipeline_runs",
    "shadow_pick_lock_observations",
    "operational_pick_locks",
    "current_market_lines",
    "official_market_lines",
    "compact_market_line_movements",
    "provider_request_usage_daily",
]
```

Each table result should be:

```python
{
    "table": table,
    "rows": writer.count_rows(table, {}),
}
```

The CLI should print one line per table:

```text
row_volume table=market_snapshots rows=356851
```

- [ ] **Step 4: Add dry-run retention script**

Create `scripts/retire_market_snapshots.py` with:

- default dry-run behavior;
- required `--older-than-days`;
- optional `--execute`;
- delete allowed only when `--execute` is passed and
  `ALLOW_MARKET_SNAPSHOT_DELETE=true`;
- compact guard: if `compact_market_line_movements` has zero rows older than the
  cutoff, return `eligible_to_delete=False` and do not delete.

Core run contract:

```python
def run(*, writer, cutoff_iso: str, execute: bool) -> dict:
    snapshot_count = writer.count_rows("market_snapshots", {"observed_at": f"lt.{cutoff_iso}"})
    compact_count = writer.count_rows("compact_market_line_movements", {"updated_at": f"lt.{cutoff_iso}"})
    eligible = snapshot_count > 0 and compact_count > 0
    deleted = 0
    if execute:
        if os.environ.get("ALLOW_MARKET_SNAPSHOT_DELETE", "").lower() not in {"1", "true", "yes", "on"}:
            raise RuntimeError("ALLOW_MARKET_SNAPSHOT_DELETE=true is required for deletion")
        if eligible:
            deleted = writer.delete_rows("market_snapshots", {"observed_at": f"lt.{cutoff_iso}"})
    return {
        "snapshot_rows_before_cutoff": snapshot_count,
        "compact_rows_before_cutoff": compact_count,
        "eligible_to_delete": eligible,
        "deleted_rows": deleted,
        "execute": execute,
    }
```

- [ ] **Step 5: Add script tests**

`tests/test_audit_supabase_row_volume.py` should use a fake writer with
`count_rows` returning table-specific counts and assert the script is read-only.

`tests/test_retire_market_snapshots.py` should cover:

- dry-run does not call `delete_rows`;
- `--execute` without `ALLOW_MARKET_SNAPSHOT_DELETE=true` raises;
- `--execute` with compact rows and allow env calls `delete_rows`;
- zero compact rows blocks deletion.

- [ ] **Step 6: Run tests**

Run:

```bash
python -m pytest tests/test_market_infra_supabase_writer.py tests/test_audit_supabase_row_volume.py tests/test_retire_market_snapshots.py -q
```

Expected: pass.

## Task 6: Docs And Operational Runbook Update

**Files:**
- Modify: `docs/current-state.md`
- Modify: `docs/operational-risk-register.md`
- Modify: `docs/provider-cost-ledger.md`

- [ ] **Step 1: Update current state**

In `docs/current-state.md`, add a section under current operating mode:

```markdown
## Supabase Operational Foundation Migration

As of 2026-05-19, Tyler approved starting the migration from pure shadow
evidence toward Supabase as the operational control plane. This does not remove
TheRundown or GitHub artifacts yet.

Phase 1 promotes only gated foundations:

- `operational_pick_locks` can store first-seen lock snapshots captured by the
  live layer before first pitch.
- `ENABLE_SUPABASE_LOCK_LEDGER=true` lets Render write lock-intent rows.
- `ENABLE_SUPABASE_LOCK_CONSUMER=true` lets the GitHub pipeline apply those
  lock rows to artifacts/history.
- Both flags default off in code until Tyler explicitly enables them.
- BoltOdds + PropLine provider-source promotion still uses the existing
  `OFFICIAL_MARKET_SOURCE=boltodds_propline` and
  `ENABLE_BOLTODDS_PIPELINE_SOURCE=true` gates.
```

- [ ] **Step 2: Update risk register**

In `docs/operational-risk-register.md`, add:

```markdown
| Supabase lock ledger writes bad row | A pick locks at an incorrect line/side/time | Artifact lock trust drops | `operational_pick_locks`, source artifact hash, game_time, should_lock_at | Disable `ENABLE_SUPABASE_LOCK_CONSUMER`; continue GitHub lock path; inspect row lineage | Any consumed lock row disagrees with the source artifact |
```

Add retention note:

```markdown
Raw snapshot deletion requires three conditions: compact summaries exist for the
affected window, `scripts/retire_market_snapshots.py --execute` is used, and
`ALLOW_MARKET_SNAPSHOT_DELETE=true` is set. Dry-run output should be reviewed
before every execute run.
```

- [ ] **Step 3: Update cost ledger**

In `docs/provider-cost-ledger.md`, under Supabase, add:

```markdown
As Supabase becomes the operational foundation, the cost guardrail changes from
"can we store shadow evidence" to "can this remain the low-friction control
plane." The first required guardrails are row-volume audit, compact movement
summaries, and dry-run retention. A Supabase Pro upgrade is acceptable only if
the operational value is clear and raw tick retention is bounded.
```

- [ ] **Step 4: Run docs grep**

Run:

```bash
rg -n "ENABLE_SUPABASE_LOCK|operational_pick_locks|retire_market_snapshots" docs tests scripts pipeline market_infra
```

Expected: references exist in code, tests, and docs.

## Final Verification

Run:

```bash
python -m pytest tests/test_operational_pick_locks_schema.py tests/test_operational_locks.py tests/test_live_layer_worker.py tests/test_fetch_results.py tests/test_run_pipeline.py tests/test_pipeline_workflow_contract.py tests/test_workflow_schedule.py tests/test_market_infra_supabase_writer.py tests/test_audit_supabase_row_volume.py tests/test_retire_market_snapshots.py -q
git diff --check
git status --short
```

Expected:

- targeted tests pass;
- whitespace check passes;
- only intentional files are modified.

## Promotion Steps After Merge

These are not part of this implementation unless Tyler explicitly approves
after review:

1. Apply the Supabase migration to hosted Supabase.
2. Set `ENABLE_SUPABASE_LOCK_LEDGER=true` on Render `bbe-live-layer`.
3. Observe one slate of `operational_pick_locks` without pipeline consumption.
4. Set `ENABLE_SUPABASE_LOCK_CONSUMER=true` for one canary slate.
5. Compare consumed locks against source artifacts and `shadow_pick_lock_observations`.
6. Only after lock foundation is stable, schedule a provider-source canary with
   `OFFICIAL_MARKET_SOURCE=boltodds_propline` and
   `ENABLE_BOLTODDS_PIPELINE_SOURCE=true`.

## Promotion Status Update, 2026-05-21

Tyler approved the non-strict lock consumer canary after the first full
lock-ledger soak. GitHub repository variables are now:

- `ENABLE_SUPABASE_LOCK_CONSUMER=true`
- `SUPABASE_LOCK_CONSUMER_STRICT=false`

This is still a lock-layer canary only. The next validation step is to compare
GitHub-applied artifact locks against `operational_pick_locks`, source artifact
hashes, `shadow_pipeline_runs`, and `shadow_pick_lock_observations` after the
current slate's lock windows. The table has a `consumed_at` column, but the
current consumer does not mark it yet, so validate from GitHub logs/artifacts
until a separate observability patch writes consumed markers. Strict lock
consumption, PropLine webhook processing, provider-source promotion,
row-retention execution, model changes, thresholds, staking, and dashboard
behavior remain separate decisions.

