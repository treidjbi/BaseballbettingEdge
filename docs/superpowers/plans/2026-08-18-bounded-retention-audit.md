# Bounded Season-Retention Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, read-only, resumable provider/date audit that proves exact season-retention coverage without another full-season database sort or any deletion authority.

**Architecture:** Generate SELECT-only SQL for one provider across one, three, or at most seven slate dates, execute it serially through the linked Supabase CLI, and checkpoint only validated aggregate output. A local assembler emits a fail-closed version 2 envelope only after the entire expected provider/date matrix and a separate narrow runtime-boundary read reconcile; the existing readiness reporter then consumes that envelope without changing production data or behavior.

**Tech Stack:** Python 3.11 standard library, PostgreSQL through `npx supabase db query --linked`, pytest

**Spec:** `docs/superpowers/specs/2026-08-18-bounded-retention-audit-design.md`

**Plan status (2026-08-19):** Tasks 1-5 and the single final whole-branch
review fix are implemented, independently reviewed, and merged locally to
`main` at `5b0cf17cec6d9c1950dcebad045221e49e95e782`. Task 5 added
fixture-only 1/3/7-day checkpoint coverage, local assembly, and both closed
reporter paths; the final review fix blocks retired-BoltOdds readiness when
any current runtime maximum is after suspension while preserving the closure
diagnostic. The merged tree passed all `2,391` tests. Nothing was pushed or
deployed, no live Supabase read ran, and every Phase 2/3, retention, deletion,
vacuum, sizing, and storage-reclamation gate remains separately closed.

## Global Constraints

- Candidate scope starts `2026-04-28` and ends at `as_of_date - 30 days`, inclusive, in `America/Phoenix`.
- Allowed providers are exactly `boltodds`, `propline`, `the_odds`, and `therundown`.
- Query cadence is serial `1 -> 3 -> 7` dates with a seven-date hard ceiling, 30-second cooldown, default one-chunk invocation, hard five-chunk invocation cap, and zero automatic retries.
- No database write, DDL, maintenance statement, timeout increase, provider API request, raw payload output, executable cleanup SQL, new dependency, migration, service, schedule, push, or deployment.
- `retention_execution_closed` remains `true`; `deletion_approved` remains `false`.
- Durable season evidence remains full-season/permanent: official picks/results/history, Gate C outcomes/manifests, accepted bets/corrections, exact market checkpoints/close/CLV, sent notifications, consumed locks, frozen Alt V2 decisions, provider provenance/cost summaries, and preserved incident/model-review pins. The bounded audit may identify raw cleanup candidates but cannot reduce this contract.
- `scripts/retire_market_snapshots.py` and `scripts/backfill_compact_market_movements_via_cli.py` are protected and must not change.
- Tasks 1-5 are local implementation and fixture verification only. No live Supabase read is authorized by this plan.
- A live one-date canary, retired-BoltOdds stress canary, runtime-boundary read, and capped multi-chunk read each require a fresh Tyler approval after implementation review.

## File Structure

- Create `scripts/retention_bounded_sql.py`: date/provider validation, stable query-contract hash, SELECT-only assertion, bounded chunk SQL, and narrow runtime-boundary SQL.
- Create `scripts/bounded_retention_audit.py`: scope/chunk models, adaptive cadence, linked-CLI subprocess wrapper, sanitized failure classification, atomic checkpoints, resume validation, final assembly, and CLI.
- Modify `scripts/build_season_retention_readiness.py`: validate and normalize explicit version 2 envelopes while preserving version 1 behavior.
- Create `tests/test_retention_bounded_sql.py`: query-shape, range, provider, output-field, and prohibited-token tests.
- Create `tests/test_bounded_retention_audit.py`: cadence, subprocess, checkpoint, resume, matrix, runtime, redaction, and CLI tests.
- Modify `tests/test_build_season_retention_readiness.py`: direct version 2 input, freshness, equality, decision, closure, and regression tests.
- Modify `docs/current-state.md` and this plan only after local implementation verification records actual commit and test evidence.

---

### Task 1: Bounded SELECT-only SQL builder

**Files:**
- Create: `scripts/retention_bounded_sql.py`
- Create: `tests/test_retention_bounded_sql.py`
- Reference only: `scripts/supabase_retention_exact_coverage.sql`
- Reference only: `scripts/backfill_compact_market_movements_via_cli.py`

**Interfaces:**
- Produces: `ALLOWED_PROVIDERS: tuple[str, ...]`
- Produces: `CLEAN_REGIME_START: date`
- Produces: `MAX_CHUNK_DAYS: int`
- Produces: `parse_iso_date(value: str, label: str) -> date`
- Produces: `validate_provider(value: str) -> str`
- Produces: `validate_chunk(provider: str, start_date: str, end_date: str) -> tuple[str, date, date]`
- Produces: `assert_select_only(sql: str) -> None`
- Produces: `query_contract_sha256() -> str`
- Produces: `build_chunk_sql(provider: str, start_date: str, end_date: str) -> str`
- Produces: `build_runtime_boundary_sql(candidate_end_date: str) -> str`

- [ ] **Step 1: Write the failing validation and query-shape tests**

Create `tests/test_retention_bounded_sql.py` with concrete coverage for valid and invalid providers, ISO dates, reversed dates, the clean-regime floor, and an eight-date rejection. Include these core assertions:

```python
from datetime import date

import pytest

from scripts import retention_bounded_sql as bounded_sql


FORBIDDEN = (
    " insert ", " update ", " delete ", " truncate ", " drop ",
    " alter ", " create ", " grant ", " revoke ", " vacuum ",
    " reindex ", " merge ", " call ", " do ",
)


def test_validate_chunk_accepts_only_allowlisted_provider_and_seven_dates():
    provider, start, end = bounded_sql.validate_chunk(
        "propline", "2026-05-01", "2026-05-07",
    )
    assert provider == "propline"
    assert start == date(2026, 5, 1)
    assert end == date(2026, 5, 7)


@pytest.mark.parametrize("provider", ["", "BOLTODDS", "unknown", "propline'; delete"])
def test_validate_chunk_rejects_non_allowlisted_provider(provider):
    with pytest.raises(ValueError, match="allowed provider"):
        bounded_sql.validate_chunk(provider, "2026-05-01", "2026-05-01")


def test_chunk_sql_is_one_bounded_select_using_run_and_compact_indexes():
    sql = bounded_sql.build_chunk_sql("propline", "2026-05-01", "2026-05-03")
    lowered = f" {sql.lower()} "
    assert sql.rstrip().endswith(";")
    assert sql.count(";") == 1
    assert not any(token in lowered for token in FORBIDDEN)
    assert "mpr.slate_date between date '2026-05-01' and date '2026-05-03'" in lowered
    assert "mpr.provider = 'propline'" in lowered
    assert "join public.market_snapshots ms on ms.run_id = mpr.id" in lowered
    assert "cmlm.slate_date between date '2026-05-01' and date '2026-05-03'" in lowered
    assert "cmlm.provider = 'propline'" in lowered
    assert "lower(trim(mpr.provider))" not in lowered
    assert "ms.*" not in lowered
    assert "source_payload" not in lowered
    assert lowered.count("order by observed_at asc, id asc") == 1
    assert "order by observed_at desc, id desc" not in lowered


def test_chunk_sql_emits_explicit_zeros_and_all_exact_metrics():
    sql = bounded_sql.build_chunk_sql("the_odds", "2026-05-01", "2026-05-01").lower()
    assert "generate_series" in sql
    assert "requested_partitions" in sql
    for field in (
        "raw_snapshot_rows", "raw_logical_bytes", "raw_group_count",
        "compact_group_count", "exact_group_count", "mismatched_group_count",
        "missing_compact_group_count", "unexpected_compact_group_count",
        "duplicate_compact_group_count", "first_seen_mismatch_count",
        "last_seen_mismatch_count", "first_odds_mismatch_count",
        "last_odds_mismatch_count", "min_odds_mismatch_count",
        "max_odds_mismatch_count", "odds_move_count_mismatch_count",
        "snapshot_count_mismatch_count", "coverage_exact",
        "rows_missing_run_id", "rows_missing_run_row",
        "rows_missing_group_key", "provider_run_mismatch_rows",
        "slate_date_mismatch_rows", "unknown_provider_rows",
        "candidate_runtime", "retention_bounded_chunk",
    ):
        assert field in sql
```

- [ ] **Step 2: Run the new tests and verify the missing module failure**

Run:

```powershell
python -m pytest tests/test_retention_bounded_sql.py -q
```

Expected: collection fails because `scripts.retention_bounded_sql` does not exist.

- [ ] **Step 3: Implement validation, hashing, and the read-only assertion**

Create `scripts/retention_bounded_sql.py` with this exact contract:

```python
from __future__ import annotations

import hashlib
import inspect
import re
from datetime import date


ALLOWED_PROVIDERS = ("boltodds", "propline", "the_odds", "therundown")
CLEAN_REGIME_START = date(2026, 4, 28)
MAX_CHUNK_DAYS = 7
BOLTODDS_SUSPENDED_AT = "2026-06-17T17:22:29Z"
_FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|truncate|drop|alter|create|grant|revoke|"
    r"vacuum|reindex|merge|call|copy|do)\b",
    re.IGNORECASE,
)


def parse_iso_date(value: str, label: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{label} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date") from exc


def validate_provider(value: str) -> str:
    if value not in ALLOWED_PROVIDERS:
        raise ValueError("provider must be an allowed provider")
    return value


def validate_chunk(provider: str, start_date: str, end_date: str) -> tuple[str, date, date]:
    checked_provider = validate_provider(provider)
    start = parse_iso_date(start_date, "start_date")
    end = parse_iso_date(end_date, "end_date")
    if start < CLEAN_REGIME_START:
        raise ValueError("start_date is before the clean regime")
    if start > end:
        raise ValueError("start_date must be on or before end_date")
    if (end - start).days + 1 > MAX_CHUNK_DAYS:
        raise ValueError("chunk may contain at most seven dates")
    return checked_provider, start, end


def assert_select_only(sql: str) -> None:
    scrubbed = re.sub(r"--[^\n]*", " ", sql)
    if sql.count(";") != 1 or not sql.rstrip().endswith(";"):
        raise ValueError("retention SQL must be exactly one statement")
    if not scrubbed.lstrip().lower().startswith(("with ", "select ")):
        raise ValueError("retention SQL must begin with SELECT or WITH")
    match = _FORBIDDEN_SQL.search(scrubbed)
    if match:
        raise ValueError(f"retention SQL contains prohibited token: {match.group(1).lower()}")


def query_contract_sha256() -> str:
    contract = "\n".join((
        inspect.getsource(build_chunk_sql),
        inspect.getsource(build_runtime_boundary_sql),
        ",".join(ALLOWED_PROVIDERS),
    ))
    return hashlib.sha256(contract.encode("utf-8")).hexdigest()
```

Do not add an execute flag, service-role client, cleanup builder, mutation-token exception, or provider normalization fallback.

- [ ] **Step 4: Implement `build_chunk_sql()` around bounded indexed sources**

Use this exact CTE order:

```text
settings
requested_partitions
target_runs
bounded_observed_source
bounded_run_source
valid_raw
windowed_raw
raw_groups
compact_groups
joined_groups
coverage_by_partition
coverage_with_exactness
anomaly_counts
source_anomalies
run_summary
book_summary
snapshot_summary
candidate_runtime
final SELECT jsonb_build_object(...) AS retention_bounded_chunk
```

Requirements:

- `requested_partitions` uses `generate_series` so every requested date is explicit even at zero rows.
- `target_runs` starts from exact indexed `market_provider_runs.slate_date` and `provider` predicates and projects `id`.
- `bounded_run_source` joins snapshots through `ms.run_id = mpr.id` and projects only required scalar fields plus `pg_column_size(ms)`.
- `bounded_observed_source` uses exact provider plus Phoenix-derived UTC boundaries and a left run join so missing/orphaned run IDs remain aggregate anomalies.
- Copy the canonical grouping and exact mismatch equations from `scripts/supabase_retention_exact_coverage.sql`; replace only the unbounded source and final explicit-zero join.
- Use one named ascending window, `ORDER BY observed_at ASC, id ASC ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING`, for first, last, and lag evidence.
- Emit one coverage, anomaly, and candidate-runtime row per requested provider/date, including zeros.
- Candidate-runtime rows use the existing reporter field names for run counts/status/request counts, books, snapshot counts/bytes, first/last run and snapshot times, and candidate-window heartbeat count/last heartbeat/last message. Heartbeat rows are bounded by exact provider and requested slate dates.
- Return only aggregate JSON with `chunk_version: 2`, exact scope, and `complete: true`.
- Call `assert_select_only(sql)` before returning.

- [ ] **Step 5: Implement `build_runtime_boundary_sql()` as narrow latest-row reads**

Return one `retention_runtime_boundary` JSON object with `runtime_version: 2`, database `generated_at`, candidate cutoff, and exactly one provider row containing current and candidate maximum run/snapshot/heartbeat/message timestamps. Use provider-indexed `ORDER BY ... DESC LIMIT 1` lateral reads; never aggregate or sort full history. Derive `post_boltodds_suspension` by comparing all four BoltOdds current maxima with `2026-06-17T17:22:29Z`.

- [ ] **Step 6: Run Task 1 tests and commit**

```powershell
python -m pytest tests/test_retention_bounded_sql.py -q
python -m py_compile scripts/retention_bounded_sql.py
git diff --check
git add scripts/retention_bounded_sql.py tests/test_retention_bounded_sql.py
git commit -m "feat: add bounded retention SQL builder"
```

---

### Task 2: Safe adaptive runner and atomic checkpoints

**Files:**
- Create: `scripts/bounded_retention_audit.py`
- Create: `tests/test_bounded_retention_audit.py`
- Use: `scripts/retention_bounded_sql.py`

**Interfaces:**
- Produces: frozen `AuditScope`, `ChunkSpec`, and `CheckpointRecord` dataclasses
- Produces: `build_scope(as_of_date: str) -> AuditScope`
- Produces: `expected_partitions(scope: AuditScope) -> tuple[tuple[str, str], ...]`
- Produces: `preferred_chunk_days(checkpoints: list[CheckpointRecord], provider: str) -> int`
- Produces: `select_next_chunk(scope: AuditScope, checkpoints: list[CheckpointRecord]) -> ChunkSpec | None`
- Produces: `run_linked_query(sql: str) -> subprocess.CompletedProcess[str]`
- Produces: `parse_supabase_object(stdout: str, column: str) -> dict[str, Any]`
- Produces: `validate_chunk_payload(payload: dict[str, Any], chunk: ChunkSpec) -> None`
- Produces: `write_json_atomic(path: Path, value: dict[str, Any]) -> None`
- Produces: `load_valid_checkpoints(output_dir: Path, scope: AuditScope) -> list[CheckpointRecord]`

- [ ] **Step 1: Write failing scope, matrix, and cadence tests**

Test the fixed clean start, `2026-08-18 -> 2026-07-19` candidate cutoff, first protected date `2026-07-20`, all date/provider pairs, a one-date first chunk for each new provider, and this exact cadence table:

```python
@pytest.mark.parametrize(
    ("previous_days", "elapsed", "expected"),
    [(1, 29.9, 3), (3, 30.0, 7), (7, 2.0, 7),
     (1, 30.1, 1), (3, 31.0, 1), (7, 31.0, 3)],
)
def test_preferred_chunk_days_promotes_fast_and_deescalates_slow(
    checkpoint_factory, previous_days, elapsed, expected,
):
    checkpoints = [checkpoint_factory("boltodds", previous_days, elapsed)]
    assert audit.preferred_chunk_days(checkpoints, "boltodds") == expected
```

Also prove `select_next_chunk()` chooses the earliest missing date, shortens before an existing checkpoint, never overlaps, and never returns more than seven dates.

- [ ] **Step 2: Run the tests and verify the missing module failure**

```powershell
python -m pytest tests/test_bounded_retention_audit.py -q
```

Expected: collection fails because `scripts.bounded_retention_audit` does not exist.

- [ ] **Step 3: Implement the immutable contracts and deterministic planner**

Use these exact constants and dataclasses:

```python
AUDIT_VERSION = 2
RAW_RETENTION_DAYS = 30
CHUNK_LADDER = (1, 3, 7)
SOFT_ELAPSED_SECONDS = 30.0
COOLDOWN_SECONDS = 30.0
DEFAULT_MAX_CHUNKS = 1
HARD_MAX_CHUNKS = 5
QUERY_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class AuditScope:
    as_of_date: date
    start_date: date
    candidate_end_date: date
    first_protected_date: date
    raw_retention_days: int
    providers: tuple[str, ...]


@dataclass(frozen=True)
class ChunkSpec:
    provider: str
    start_date: date
    end_date: date

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1


@dataclass(frozen=True)
class CheckpointRecord:
    path: Path
    provider: str
    start_date: date
    end_date: date
    elapsed_seconds: float
    query_contract_sha256: str
    rendered_sql_sha256: str
    scope_fingerprint: str
    cli_version: str
    payload: dict[str, Any]
```

- [ ] **Step 4: Write failing subprocess, redaction, and checkpoint tests**

Mock `shutil.which`, `NamedTemporaryFile`, `os.unlink`, and `subprocess.run` to prove the linked CLI uses an argv list, a temp SQL file, `shell=False`, captured text output, and fixed 120-second local timeout. Add failure fixtures for PostgreSQL `53100`, `57014`, `ECIRCUITBREAKER`, authentication failure, timeout, empty stdout, malformed JSON, and aggregate validation failure. Every failure must produce one stable code, zero checkpoint files, and one call only.

Add an atomic-write test proving `os.replace(temp_path, target_path)` happens only after valid JSON serialization and closed file handles.

- [ ] **Step 5: Implement the safe linked CLI wrapper and parser**

Resolve `shutil.which("npx") or shutil.which("npx.cmd") or "npx"`, create one temporary `.sql` file, and call:

```python
subprocess.run(
    [npx, "supabase", "db", "query", "--linked", "--file", sql_path, "-o", "json"],
    check=False,
    capture_output=True,
    text=True,
    shell=False,
    timeout=QUERY_TIMEOUT_SECONDS,
)
```

`parse_supabase_object()` requires a one-row list wrapper and a JSON object under the requested column. `classify_failure()` returns only `postgres_53100`, `postgres_57014`, `pooler_circuit_breaker`, `authentication_error`, `timeout`, `subprocess_failed`, `empty_stdout`, `malformed_json`, or `validation_failed`; never return raw stderr or command/environment values.

- [ ] **Step 6: Implement exact checkpoint validation and `run_chunks()`**

Each checkpoint records audit/as-of/cutoff/provider/date scope, ordered provider allowlist, query-contract and rendered-SQL SHA-256 values, scope fingerprint, CLI version, timezone-aware start/finish, elapsed seconds, `complete: true`, `sanitized_error: null`, and the validated aggregate payload.

`validate_chunk_payload()` requires one coverage/anomaly/runtime record for every requested date, exact provider/date scope, non-negative integers, no duplicates/gaps, valid count equations, and recomputed `coverage_exact`. `run_chunks()` writes a checkpoint only after validation, stops after a slow success, sleeps exactly 30 seconds only between successes, never retries, and respects default-one/hard-five invocation caps.

- [ ] **Step 7: Add the exact CLI and argument tests**

Implement:

```text
run --as-of YYYY-MM-DD [--output-dir PATH] --run-linked-read
    [--max-chunks 1..5] [--allow-multi-chunk]
runtime-boundary --as-of YYYY-MM-DD [--output-dir PATH] --run-linked-read
assemble --as-of YYYY-MM-DD [--output-dir PATH] --runtime-json PATH
```

`run` and `runtime-boundary` return `3` without `--run-linked-read`. Values above one require `--allow-multi-chunk`; values outside `1..5` fail. There is no execute/delete/backfill/vacuum/timeout/provider/SQL argument. `assemble` is local-only. Help returns `0`; malformed arguments return `3`.

- [ ] **Step 8: Run Task 2 tests and commit**

```powershell
python -m pytest tests/test_retention_bounded_sql.py tests/test_bounded_retention_audit.py -q
python -m py_compile scripts/retention_bounded_sql.py scripts/bounded_retention_audit.py
git diff --check
git add scripts/bounded_retention_audit.py tests/test_bounded_retention_audit.py
git commit -m "feat: add resumable retention audit runner"
```

---

### Task 3: Complete-matrix assembler and runtime boundary

**Files:**
- Modify: `scripts/bounded_retention_audit.py`
- Modify: `tests/test_bounded_retention_audit.py`

**Interfaces:**
- Produces: `aggregate_candidate_rows(checkpoints, scope) -> tuple[coverage, anomalies, runtime]`
- Produces: `validate_runtime_boundary(value, scope) -> None`
- Produces: `assemble_v2_envelope(scope, checkpoints, runtime_boundary, audit_generated_at) -> dict[str, Any]`

- [ ] **Step 1: Write failing complete-matrix tests**

Build a valid two-date/two-provider fixture, then separately mutate it to drop a partition, duplicate a partition, overlap ranges, change query hash, change scope fingerprint, change cutoff, change CLI version, contradict raw/compact equations, contradict candidate rows/bytes, or add an unattributed anomaly. Each mutation must raise a field-specific `ValueError`.

- [ ] **Step 2: Write the successful v2 envelope test**

```python
def test_assemble_v2_separates_candidate_and_current_runtime(
    complete_checkpoint_set, runtime_boundary,
):
    scope, checkpoints = complete_checkpoint_set
    envelope = audit.assemble_v2_envelope(
        scope, checkpoints, runtime_boundary,
        audit_generated_at=fixed_phoenix_timestamp(),
    )
    assert envelope["audit_version"] == 2
    assert envelope["as_of_date"] == "2026-08-18"
    assert envelope["candidate_scope"]["end_date"] == "2026-07-19"
    assert envelope["protected_scope"]["start_date"] == "2026-07-20"
    assert envelope["execution"]["complete"] is True
    assert envelope["complete"] is True
    assert envelope["retention_execution_closed"] is True
    assert envelope["deletion_approved"] is False
    assert len(envelope["coverage"]) == len(audit.expected_partitions(scope))
```

- [ ] **Step 3: Implement candidate aggregation and matrix equations**

Require exact equality with `expected_partitions(scope)`, no overlapping chunk ranges, one shared hash/scope/cutoff/provider-list/CLI contract, all existing raw/compact mismatch equations, exactness derived from blocker counts, and provider raw rows/bytes equal to candidate runtime when anomaly counts are zero. Non-zero anomalies remain visible and block completeness.

- [ ] **Step 4: Implement runtime-boundary execution and validation**

The `runtime-boundary` command performs exactly one safe linked read and writes `runtime-boundary-<as_of>.json` atomically. Validate runtime version, current Phoenix audit day, exact candidate cutoff, one row per provider, timezone-aware/null timestamps, current maxima not older than candidate maxima, and no BoltOdds maximum after `2026-06-17T17:22:29Z`.

- [ ] **Step 5: Implement the exact final envelope**

Use this top-level contract:

```python
envelope = {
    "audit_version": 2,
    "audit_generated_at": audit_generated_at.isoformat(),
    "as_of_date": scope.as_of_date.isoformat(),
    "timezone": "America/Phoenix",
    "candidate_scope": candidate_scope,
    "protected_scope": protected_scope,
    "execution": execution_contract,
    "coverage": coverage,
    "source_anomalies": source_anomalies,
    "candidate_runtime": candidate_runtime,
    "runtime_boundary": runtime_boundary["providers"],
    "complete": True,
    "retention_execution_closed": True,
    "deletion_approved": False,
}
```

`execution_contract` includes query hash, CLI version, `[1, 3, 7]`, both 30-second gates, seven-day ceiling, one/five invocation caps, expected/completed ranges, and `complete: true`. Write only the sanitized final envelope, never raw checkpoints or cleanup SQL, to `analytics/output/retention/bounded_retention_envelope.json` by default.

Define `expected_chunk_ranges` as four canonical ranges: one full candidate
start/end range per provider. Define `completed_chunk_ranges` as the actual
validated checkpoint ranges. Validation expands both lists to provider/date
partitions, requires exact set equality, and rejects overlap within completed
ranges; the lists are not required to have the same number of ranges.

- [ ] **Step 6: Run Task 3 tests and commit**

```powershell
python -m pytest tests/test_retention_bounded_sql.py tests/test_bounded_retention_audit.py -q
python -m py_compile scripts/retention_bounded_sql.py scripts/bounded_retention_audit.py
git diff --check
git add scripts/bounded_retention_audit.py tests/test_bounded_retention_audit.py
git commit -m "feat: assemble bounded retention evidence"
```

---

### Task 4: Version 2 readiness and BoltOdds closure compatibility

**Files:**
- Modify: `scripts/build_season_retention_readiness.py:82-427`
- Modify: `scripts/build_season_retention_readiness.py:641-977`
- Modify: `tests/test_build_season_retention_readiness.py`

**Interfaces:**
- Produces: direct v2 input support in `load_query_envelope()`
- Produces: `_normalize_envelope_for_decisions(envelope, as_of) -> dict[str, Any]`
- Preserves: v1 input, public report builders, filenames, decisions, redaction, and exit codes

- [ ] **Step 1: Add a complete v2 fixture and direct-input test**

Add `_v2_envelope()` beside `_envelope()`. Include two explicit BoltOdds dates, one zero partition, exact candidate runtime totals, current runtime boundaries before suspension, complete execution metadata, and closed posture fields. Verify `load_query_envelope()` accepts its direct JSON object while retaining the existing one-row v1 Supabase wrapper test.

- [ ] **Step 2: Write v2 success and fail-closed tests**

Success must prove candidate cutoff drives coverage while current boundaries drive freshness and BoltOdds retirement. Individual failures must cover a missing/duplicate matrix row, incomplete execution, expected/completed range mismatch, invalid query hash, runtime row/byte mismatch, unattributed anomaly, stale runtime boundary, missing/duplicate provider, current maximum older than candidate maximum, each post-suspension BoltOdds field, open retention execution, and approved deletion.

- [ ] **Step 3: Implement explicit v2 normalization**

Use this interface without faking version 1:

```python
def _normalize_envelope_for_decisions(
    envelope: dict[str, Any], *, as_of: date | None,
) -> dict[str, Any]:
    validate_envelope(envelope, as_of=as_of)
    if envelope["audit_version"] == 1:
        return envelope
    return {
        **envelope,
        "query_scope": {
            "start_date": envelope["candidate_scope"]["start_date"],
            "end_date": envelope["candidate_scope"]["end_date"],
            "providers": envelope["candidate_scope"]["providers"],
        },
        "provider_runtime": envelope["candidate_runtime"],
    }
```

Candidate runtime keeps candidate-window counts and timestamps internally
consistent. In `build_boltodds_closure()`, add the matching v2
`runtime_boundary` row as a separate `current_runtime_boundary` object and use
its `post_boltodds_suspension` plus all four current maxima for the operational
exception decision. Version 1 keeps using its existing provider-runtime fields.
Never overwrite candidate timestamps with current timestamps or infer a count
from a timestamp.

- [ ] **Step 4: Extend validation without weakening v1**

Keep all current v1 tests and checks. Add a v2 branch for complete matrix, execution metadata, candidate/runtime equality, current boundaries, and BoltOdds suspension. Define v2 anomaly fields as the existing four plus `slate_date_mismatch_rows` and `unknown_provider_rows`; either new field above zero blocks readiness and BoltOdds closure. Normalize at the start of both report builders, and make the v2 BoltOdds closure read current retirement evidence from `runtime_boundary`. Preserve the existing Gate C, decision-evidence, and pin requirements for every v2 provider/date. Do not change decision names, exit codes, output names, redaction, or deletion-closed language.

Keep the version 1 rule that `query_scope.end_date == as_of_date`. Replace that
rule only for version 2: require `candidate_scope.end_date == as_of_date - 30
days`, `protected_scope.start_date == candidate_end_date + 1 day`, and a
runtime-boundary generation timestamp on the requested Phoenix as-of date.

- [ ] **Step 5: Run focused reporter tests and commit**

```powershell
python -m pytest tests/test_build_season_retention_readiness.py tests/test_bounded_retention_audit.py tests/test_retention_bounded_sql.py -q
python -m py_compile scripts/build_season_retention_readiness.py scripts/bounded_retention_audit.py scripts/retention_bounded_sql.py
git diff --check
git add scripts/build_season_retention_readiness.py tests/test_build_season_retention_readiness.py
git commit -m "feat: support bounded retention envelope v2"
```

---

### Task 5: Local end-to-end proof, regression, and handoff

**Files:**
- Modify: `tests/test_bounded_retention_audit.py`
- Modify: `docs/current-state.md`
- Modify: `docs/superpowers/plans/2026-08-18-bounded-retention-audit.md`
- Do not modify: `scripts/retire_market_snapshots.py`
- Do not modify: `scripts/backfill_compact_market_movements_via_cli.py`

**Interfaces:**
- Produces: fixture-only end-to-end proof and exact local verification record
- Does not produce: live Supabase evidence, deletion authority, or production artifacts

- [ ] **Step 1: Add a fixture-only CLI integration test**

Create validated one-, three-, and seven-date checkpoints plus runtime-boundary JSON in `tmp_path`; run local assembly and both reporters. Assert assembly returns `0`, reports return `0` or evidence-blocked `2` but never `3`, closed posture remains true/false, serialized output contains no `delete from` or `service_role`, and subprocess call count remains zero.

- [ ] **Step 2: Run the complete focused retention suite**

```powershell
python -m pytest tests/test_retention_bounded_sql.py tests/test_bounded_retention_audit.py tests/test_build_season_retention_readiness.py tests/test_backfill_compact_market_movements_via_cli.py tests/test_retire_market_snapshots.py -q
```

Expected: all focused tests pass without a live CLI or network call.

- [ ] **Step 3: Verify protected files and prohibited capabilities**

```powershell
git diff --exit-code HEAD -- scripts/retire_market_snapshots.py scripts/backfill_compact_market_movements_via_cli.py
rg -n -- "--execute|--delete|--backfill|--vacuum|service.role|delete from|truncate table|insert into|update public" scripts/retention_bounded_sql.py scripts/bounded_retention_audit.py
```

Expected: protected-file diff is empty. Review every search result; runtime paths expose none of these capabilities.

- [ ] **Step 4: Run full repository verification on the exact implementation tree**

Record `git status --short` and tracked Gate F report contents, then run:

```powershell
python -m pytest tests/ -q
python -m py_compile scripts/retention_bounded_sql.py scripts/bounded_retention_audit.py scripts/build_season_retention_readiness.py
git diff --check
```

If tests rewrite a tracked Gate F report from fixture data, inspect the diff and restore only that report to exact pre-test content using `apply_patch`; do not commit the generated analytical rewrite. Rerun `git diff --check` and the focused retention suite.

- [ ] **Step 5: Run the requirements self-review**

Confirm every read is bounded, parallelism/retry are absent, cadence/caps are enforced, zeros and complete matrix are exact, checkpoints are atomic/sanitized, v2 separates candidate/current time, runtime equations and BoltOdds boundary hold, evidence/pins remain required, protected scripts are unchanged, and all production/retention/deletion/push/deployment gates remain closed. Any failed check requires a failing regression test and fix before completion.

- [ ] **Step 6: Update the operating handoff with verified facts only**

Record exact branch head, focused/full test counts, protected-file status, no live Supabase read, separate approval required for each live gate, and Phase 2/Phase 3 still closed in this plan and the Four-Lane board.

- [ ] **Step 7: Commit the integration proof and handoff**

```powershell
git add tests/test_bounded_retention_audit.py docs/current-state.md docs/superpowers/plans/2026-08-18-bounded-retention-audit.md
git commit -m "test: verify bounded retention audit workflow"
git show --check --stat HEAD
git status --short --branch
```

Expected: clean commit verification, no unintended worktree changes, and no push or deploy.

---

## Task 5 Local Verification Record — 2026-08-19

- The exact focused retention suite passed `378` tests.
- The exact full repository suite passed `2,387` tests on the pre-handoff
  implementation tree. The three retention modules also passed `py_compile`,
  and `git diff --check` was clean apart from informational Windows line-ending
  warnings.
- The fixture-only CLI integration test creates validated 1-day, 3-day, and
  7-day checkpoints plus a runtime-boundary checkpoint in `tmp_path`, runs the
  local assembler and both reporter commands, receives assembly success and
  evidence-blocked reporter exit `2` rather than validation exit `3`, and
  proves no query subprocess ran.
- `scripts/retire_market_snapshots.py` remained object-identical at blob
  `2b19e8f1b00838caa6e3feb949ec745ba97dc94f`; and
  `scripts/backfill_compact_market_movements_via_cli.py` remained
  object-identical at blob `a3627ebf61b95162a490034cdf7ccbcb35803c96`.
  Both objects match the Task 5 base and the whole-feature merge base
  `39a180bd2e59494ff96945ee72adef3453a30d3a`.
- The prohibited-capability search found no execute, delete, backfill, vacuum,
  service-role, mutation-flag, or mutation-SQL capability in the bounded audit
  runtime paths. Serialized local envelope and reporter outputs retained
  `retention_execution_closed: true`, `deletion_approved: false`, and exposed
  no cleanup SQL, service-role value, or raw source payload.
- This is static/local audit-tooling evidence only. No linked CLI, network,
  provider, or live Supabase read ran; no database row, schema, migration,
  backfill, delete, vacuum, service, schedule, artifact, provider, model,
  notification, lock, UI, push, deployment, or production behavior changed.
- Phase 2 remains closed: the one-date low-volume canary, retired-BoltOdds
  stress canary, and narrow runtime-boundary read each require separate Tyler
  approval and review. Phase 3 remains closed: any capped multi-chunk run needs
  another separate Tyler approval after those canaries. Durable-evidence
  finalization/backfill, sizing and table/provider retention decisions,
  retention activation, partition-specific deletion, and storage reclamation
  are not complete or authorized.

### Task 5 Review Round 1 Verification

- The fixture supplies complete valid zero-decision season evidence for every
  candidate date while deliberately omitting the pin manifest. All `332`
  provider/date partitions therefore report `blocked_pinned_evidence` with
  only `missing_pin_manifest_partition` partition reasons; the BoltOdds
  closure remains evidence-blocked with the explicit
  `missing_pin_manifest_partition` and `pin_manifest_missing` gaps.
- All four BoltOdds current runtime-boundary fields are explicit fixture values
  at `2026-04-28T12:01:00Z`, before the retirement cutoff. The closure records
  `post_boltodds_suspension: false` and contains no
  `post_suspension_runtime_evidence` gap or reason.
- Local assembly still exits `0`; both closed reporters exit `2`; no path exits
  `3`; no linked query or subprocess executes; and serialized outputs keep
  execution and deletion closed without cleanup SQL, service-role text, or raw
  source payload.
- After this proof correction, the exact focused retention suite still passes
  `378` tests and the exact full repository suite still passes `2,387` tests.
  The three retention modules pass `py_compile`; `git diff --check` passes; and
  the generated Gate F report was restored via `apply_patch` to its exact
  tracked object before the focused suite was rerun.
- The protected retirement/backfill scripts remain object-identical to Task 5
  base `810c21a9353776a7eb2754e80918283fa42dba3b` and whole-feature merge base
  `39a180bd2e59494ff96945ee72adef3453a30d3a`. No live Supabase read or any
  production behavior change occurred. All separate Phase 2, Phase 3,
  durable-evidence, sizing, retention, deletion, and reclamation gates remain
  closed.

### Final Whole-Branch Review Fix Verification

- Four direct-v2 regressions independently place the current BoltOdds run,
  snapshot, heartbeat, or message maximum one second after the documented
  suspension boundary. In each case every BoltOdds partition is blocked with
  `post_suspension_runtime_evidence`, the readiness CLI exits `2`, and the
  closure remains `operational_exception` with the corresponding boundary
  value. Pre-suspension BoltOdds and all non-Bolt provider readiness remain
  unchanged.
- The exact reporter suite passed `194` tests, the exact focused retention
  suite passed `382` tests, and the full repository suite passed `2,391` tests.
  The three retention modules passed `py_compile`; the known generated Gate F
  report was restored via `apply_patch` to its exact tracked object.
- Validation still accepts a correctly flagged operational-exception envelope
  so closure can report it. Retention execution and deletion remain closed;
  no live read, mutation, push, deploy, provider, model, notification, lock,
  UI, or production behavior changed. The final reviewed implementation is
  merged locally on `main` at
  `5b0cf17cec6d9c1950dcebad045221e49e95e782`.

### Phase 2 Gate 1 Attempt — 2026-08-19

- Tyler separately approved only the first live-validation gate. The runner
  issued exactly one linked, SELECT-only query for the deterministic first
  chunk, `boltodds` / `2026-04-28`, with `--max-chunks 1`. The query returned
  after `24.25` seconds, but the runner stopped with `malformed_json`; it wrote
  no checkpoint and did not retry.
- Root cause was local CLI-output compatibility, not a validated database
  result: Supabase CLI `2.115.0` wraps query rows in a safety envelope with a
  `rows` member, while `parse_supabase_object()` accepted only the legacy
  top-level list. Because the aggregate payload was not validated, this
  attempt supplies no provider/date coverage, equation, or retention-readiness
  evidence.
- A test-first local compatibility fix now accepts both the legacy row list and
  the current safety envelope while returning only the requested result object.
  Envelope metadata is not written to checkpoints or surfaced as evidence.
  The exact retention-focused suite passes `383` tests, the full repository
  suite passes `2,392`, all three retention modules pass `py_compile`, and
  `git diff --check` passes.
- No second live query, database write, deletion, vacuum, retention activation,
  backfill, migration, push, deploy, or production behavior change occurred.
  At the close of this attempt, Gate 1 remained incomplete and required fresh
  Tyler approval before one clean retry. Gates 2-4 remained separately closed.

### Phase 2 Gate 1 Clean Retry — 2026-08-19

- Tyler supplied fresh approval for exactly one retry of the same first gate.
  The runner issued one linked, SELECT-only `boltodds` / `2026-04-28` chunk
  with `--max-chunks 1`, completed successfully in `13.09` seconds, and wrote
  `checkpoint-boltodds-2026-04-28-2026-04-28.json`. No retry or second query
  ran.
- The local checkpoint is audit version 2, `complete: true`, status
  `completed`, validation `passed`, and integrity-valid under the current CLI,
  query-contract, rendered-SQL, result, scope, and checkpoint hashes. It has
  exactly one provider/date partition and passed the runner's full checkpoint
  loader after creation.
- This was a valid zero-row canary: raw snapshots/groups/logical bytes,
  compact/exact/missing/unexpected/mismatched groups, anomalies, provider runs,
  heartbeats, messages, and requests all reconcile at zero. Redaction checks
  found no secret, token, raw-payload, cleanup-SQL, deletion, or vacuum text.
  The result proves the bounded read, CLI envelope parsing, checkpoint,
  validation, equation, and redaction path. It does not supply non-zero
  compaction coverage or deletion-readiness evidence.
- Gate 1 is complete. Stop before Gate 2: the retired-BoltOdds active-trial
  provider/date canary still needs separate Tyler approval. Gate 3 runtime
  boundary and Gate 4 capped multi-chunk execution remain separately closed.
  No database write, deletion, vacuum, retention activation, backfill,
  migration, push, deploy, or production behavior change occurred.

### Phase 2 Gate 2 Stress Canary — 2026-08-19

- Tyler separately approved one retired-BoltOdds active-trial provider/date
  stress canary. The standard chronological resume path cannot jump from the
  first clean-regime checkpoint to the active trial, so the operator invoked
  the existing allowlisted SQL builder, linked-query wrapper, payload
  validator, checkpoint/hash builder, and atomic writer directly for
  `boltodds` / `2026-06-11`. No code or CLI capability changed.
- Exactly one linked, SELECT-only query completed in `23.74` seconds and wrote
  `checkpoint-boltodds-2026-06-11-2026-06-11.json`. It had no `53100`,
  `57014`, pooler, authentication, timeout, parsing, or validation failure; no
  retry or second query ran. The audit-v2 checkpoint is complete,
  integrity-valid, validation-passed, and redaction-clean.
- The high-volume preservation result failed closed. It found `7,139` raw
  snapshots / `5,414,880` logical bytes across `340` raw groups and `340`
  compact groups. `336` groups are exact, `4` are mismatched, and
  `coverage_exact` is false. There are no missing, unexpected, or duplicate
  compact groups, but all four mismatches differ on last-seen, last-odds,
  odds-move-count, and snapshot-count; three also differ on minimum odds and
  one on maximum odds. First-seen and first-odds match.
- Source anomalies also block readiness: `157` snapshots observed during the
  Phoenix-date window link to provider runs whose `slate_date` differs from the
  observed Phoenix date. Missing run IDs, missing run rows, missing group keys,
  provider/run mismatches, and unknown-provider counts are all zero. The
  aggregate runtime contains `235` runs (`232` completed / `3` failed), `470`
  requests, `751` heartbeats, four books, and the same `7,139` snapshots.
- Gate 2's query/infrastructure canary is complete, but exact retention
  coverage is blocked. Do not backfill or reinterpret the four compact
  mismatches or the `157` slate-date mismatches without a separate diagnostic
  and approval. Gate 3's narrow runtime-boundary read still needs separate
  Tyler approval; Gate 4 capped multi-chunk execution, retention activation,
  deletion, vacuum, and storage reclamation remain closed.

### Phase 2 Gate 3 Runtime Boundary — 2026-08-19

- Tyler separately approved exactly one narrow runtime-boundary read. The
  existing `runtime-boundary` command issued one linked, SELECT-only query for
  candidate cutoff `2026-07-20`, completed the database call in `16.03`
  seconds, and wrote `runtime-boundary-2026-08-19.json`. There was no retry or
  second query and no database, pooler, authentication, timeout, parsing, or
  validation failure.
- The audit-v2 checkpoint passed filename, integrity, CLI, query-contract,
  rendered-SQL, scope, result-hash, timestamp, exact-provider, freshness,
  candidate/current ordering, and redaction validation for BoltOdds, PropLine,
  The Odds API, and TheRundown.
- BoltOdds retirement is clean in database runtime evidence:
  `post_boltodds_suspension` is false. The current and candidate maxima are
  identical: run `2026-06-17T17:20:59.716833Z`, heartbeat
  `2026-06-17T17:20:59.652720Z`, message
  `2026-06-17T17:20:59.627200Z`, and snapshot
  `2026-06-16T13:37:44.405859Z`. All are at or before the documented
  `2026-06-17T17:22:29Z` suspension boundary; no accidental reactivation is
  present.
- A local post-check initially compared canonical UTC timestamps with the raw
  checkpoint's equivalent Phoenix-offset strings and failed its own overly
  exact textual assertion. The checkpoint's validator had already passed.
  Rechecking against canonical UTC values passed without another database
  call; no code or checkpoint correction was needed.
- Gate 3 is complete, but it does not clear Gate 2's four compact-group
  mismatches or `157` slate-date mismatch rows. Stop before Gate 4. Capped
  multi-chunk execution, mismatch diagnosis/backfill, retention activation,
  deletion, vacuum, and storage reclamation remain separately closed.

### Phase 2 Gate 2 Mismatch Diagnosis — 2026-08-19

- Tyler approved a read-only diagnosis of Gate 2's four compact-group
  mismatches and `157` slate-date mismatch rows. Two narrow linked,
  SELECT-only aggregate queries completed in `19.07` and `24.78` seconds.
  There was no retry, mutation, raw-payload output, backfill, retention
  activation, deletion, vacuum, push, deploy, or production behavior change.
- The four June 11 compact groups are genuinely stale rather than an audit
  definition mismatch. All four are Caesars / Anthony Kay groups. Their
  compact rows were last updated at `2026-06-12T12:40:56Z`, but six additional
  raw snapshots arrived at `13:08:07Z` through `13:17:53Z`. The missing deltas
  are `2`, `1`, `1`, and `2` snapshots and explain the last-seen, last-odds,
  movement-count, snapshot-count, minimum-odds, and maximum-odds differences.
- The `157` cross-date rows are also a real preservation gap. They cover `117`
  groups: `152` snapshots from a run labeled `2026-05-30` and `5` from a run
  labeled `2026-06-10`, all observed during the Phoenix `2026-06-11` window.
  None of the `157` snapshot IDs are present in compact `source_snapshot_ids`
  and none fall inside a matching compact row's first/last time bounds. `19`
  rows lack a matching compact group entirely; the other `138` match a group
  whose compact evidence predates the late snapshot.
- Root cause: historical persistent BoltOdds workers continued writing under
  older provider-run slate dates, while compact rollups completed before those
  late writes and did not perform a final reconciliation of the affected run
  dates. The exact audit correctly prevented raw deletion that would have lost
  end-of-season movement evidence.
- The smallest safe repair, if separately approved, is a bounded compact
  backfill for BoltOdds run-date partitions `2026-05-30`, `2026-06-10`, and
  `2026-06-11`, followed by fresh exact coverage and cross-date source-ID/time-
  bound checks. Do not alter provider/runtime rows, reinterpret observed dates,
  or delete raw snapshots. Gate 4, retention activation, deletion, vacuum, and
  storage reclamation remain closed until the repair and proof pass.

### Phase 2 Gate 2 Bounded Repair — 2026-08-19

- Tyler separately approved the bounded BoltOdds compact backfill and exact
  post-write proof for run dates `2026-05-30`, `2026-06-10`, and `2026-06-11`.
  Preflight rejected the legacy backfill CLI as too broad because it selects
  every provider in a date range. The executed statement instead hard-coded
  only `boltodds` and the three approved dates; it could only insert/update
  `compact_market_line_movements` and contained no delete, truncate, vacuum,
  schema, provider/runtime, raw-snapshot, or production-behavior mutation.
- The bounded dry-run completed in `11.33` seconds. It found `33,588`
  compactable raw snapshots, `1,743` candidate compact groups, zero
  non-compactable raw rows, and zero unexpected compact groups. Repair scope
  was `233` groups: May 30 had `13,146` snapshots / `779` candidate groups,
  with `13` missing and `138` mismatched; June 10 had `13,303` snapshots / `624`
  candidate groups, with `15` missing and `63` mismatched; June 11 had `7,139`
  snapshots / `340` groups, with zero missing and `4` mismatched.
- One atomic linked upsert completed in `8.88` seconds and changed exactly the
  predicted `233` BoltOdds compact groups: `151`, `78`, and `4` by date. No
  other provider/date was in scope. Raw snapshots and provider/runtime rows
  were not changed or removed.
- One combined SELECT-only verification completed in `6.38` seconds. Each
  partition now has exact candidate/current group equality (`779`, `624`, and
  `340`) with zero missing, unexpected, mismatched, or non-compactable rows.
  All `157` cross-date snapshots now have a matching compact group, appear in
  `source_snapshot_ids`, and fall inside the compact first/last time bounds;
  all three missing/unpreserved counters are zero.
- Historical lineage is preserved rather than rewritten: the `157` rows still
  link to provider runs labeled May 30 or June 10, so the current audit's raw
  `slate_date_mismatch_rows` rule will continue to block readiness even though
  preservation is now exact. Do not weaken or bypass that rule ad hoc. The next
  separately planned change should distinguish preserved historical cross-date
  lineage from unpreserved mismatch rows while keeping the latter fail-closed.
  Gate 4, retention activation, deletion, vacuum, and storage reclamation remain
  closed until that contract is implemented, reviewed, and verified.

### Phase 2 Preserved-Lineage Contract — 2026-08-19

- A local-only version 2 audit amendment now retains the original cross-date
  mismatch count and adds preserved/unpreserved counters with an exact sum
  equation. Preserved status requires the original run-date compact group,
  exact raw snapshot ID membership, and first/last time-bound coverage.
- Readiness and BoltOdds closure treat only the unpreserved counter as blocking;
  the total and preserved counters remain visible evidence. All other anomaly,
  coverage, runtime, decision-linkage, outcome, and pin blockers are unchanged,
  and version 1 behavior is unchanged.
- The rendered SQL change invalidates prior chunk checkpoints through the
  existing query-contract hash. No version bypass, checkpoint rewrite, schema
  migration, dependency, provider/runtime change, or production behavior change
  was introduced.
- Focused retention verification passed `380` tests. This is code-level proof
  only: no linked query, Gate 4 invocation, retention activation, deletion,
  vacuum, or storage reclamation was run. A fresh live audit remains a separate
  approval boundary.

### Phase 2 Preserved-Lineage Local Merge — 2026-08-19

- Tyler selected local merge. `codex/retention-preserved-lineage` fast-forwarded
  cleanly onto local `main` at `7507cebd97805a1047dbd43a925554a7ab796543`;
  the merged feature branch was then deleted.
- The exact merged commit passed all `2,399` repository tests in `60.77s`.
  Independent review had no remaining findings, and the known generated Gate F
  report was restored to its committed content.
- Nothing was pushed or deployed and no live query, retention activation,
  deletion, vacuum, or storage reclamation ran. Fresh checkpoints under the new
  query hash and Gate 4 remain separate approval boundaries.

### Phase 2 New-Hash Checkpoint Refresh — 2026-08-19

- Tyler approved the bounded read-only checkpoint refresh under query hash
  `217003a22a376b736da16302f9108d5a78ca8d30a828f0efe9e82b4adae66a12`.
  The three reads ran serially with no database retry and wrote only ignored
  local checkpoint files under
  `analytics/output/retention/preserved-lineage-2026-08-19/`.
- The April 28 low-volume BoltOdds checkpoint completed in `19.19s`: explicit
  zero raw/compact/runtime rows, exact coverage, and zero anomalies.
- The June 11 retired-BoltOdds checkpoint completed in `18.35s`: `7,139` raw
  snapshots, `340/340` exact raw/compact groups, `157` cross-date rows, all
  `157` preserved, and zero unpreserved rows. This is the intended proof that
  preserved historical lineage stays visible without weakening the blocker.
- The runtime-boundary checkpoint completed in `7.42s`, validated all four
  canonical providers, and again reported `post_boltodds_suspension=false`.
  BoltOdds current maxima remain unchanged and pre-suspension.
- Integrity, rendered-query hash, scope, equation, provider matrix, and local
  redaction checks passed. A post-check initially assumed the wrong local JSON
  nesting, then validated the already-written checkpoint correctly without a
  second database call.
- Stop before Gate 4. Capped multi-chunk execution, retention activation,
  deletion, vacuum, storage reclamation, push, deployment, and production
  behavior changes remain separately closed.

### Phase 2 Gate 4 Capped Invocation 1 — 2026-08-19

- Tyler approved one capped multi-chunk invocation with the existing hard limit
  of five linked SELECT-only queries. The runner resumed the validated new-hash
  checkpoint directory and selected BoltOdds `2026-04-29` through `2026-05-01`
  as the first missing bounded unit.
- The first three-date chunk completed in `11.10s` with explicit zero raw,
  compact, and runtime rows, exact coverage, and zero anomalies. After the
  required 30-second cooldown, the second chunk (`2026-05-02` through
  `2026-05-04`) completed in `31.83s` with the same exact zero-row result.
- Because the second successful query exceeded the 30-second soft ceiling, the
  runner stopped automatically after two queries and did not issue the three
  remaining queries allowed by the hard cap. There was no retry and no `53100`,
  `57014`, pooler, authentication, timeout, parsing, integrity, equation, or
  redaction failure.
- Four historical checkpoints plus the four-provider runtime checkpoint now
  validate under the new query hash. The next missing unit is BoltOdds
  `2026-05-05` through `2026-05-07`; the full provider/date matrix remains
  incomplete, so no envelope, readiness report, retention activation, or
  deletion decision is available.
- Stop before another invocation. Continuing the bounded matrix requires fresh
  approval. Deletion, vacuum, storage reclamation, push, deployment, and every
  production behavior change remain closed.

### Phase 2 Gate 4 Capped Invocation 2 — 2026-08-19

- Tyler approved a second capped multi-chunk invocation with the same hard
  limit of five linked SELECT-only queries. The runner resumed from the four
  validated historical checkpoints and selected BoltOdds `2026-05-05` through
  `2026-05-07` as the next missing bounded unit.
- The first three-date chunk completed in `18.11s` and reconciled `4,662` raw
  snapshots across `928/928` exact raw/compact groups, with zero missing,
  unexpected, mismatched, or blocking-anomaly rows.
- After the required cooldown, the second chunk (`2026-05-08` through
  `2026-05-10`) completed in `64.96s` and reconciled `175,746` raw snapshots
  across `3,495/3,495` exact raw/compact groups. All `4,800` cross-date rows
  were preserved by compact lineage and zero were unpreserved. This large
  historical slice is positive proof that the preserved-lineage contract is
  retaining the evidence needed for end-of-season analysis.
- Because the second successful query exceeded the 30-second soft ceiling, the
  runner stopped automatically after two queries and did not issue the three
  remaining queries allowed by the hard cap. There was no retry and no
  database, pooler, authentication, timeout, parsing, integrity, equation, or
  redaction failure.
- Six historical checkpoints plus the four-provider runtime checkpoint now
  validate under the current query hash. The next missing unit is BoltOdds
  `2026-05-11` through `2026-05-13`; the full provider/date matrix remains
  incomplete, so no envelope, readiness report, retention activation, or
  deletion decision is available.
- Stop before another invocation. Continuing the bounded matrix requires fresh
  approval. Deletion, vacuum, storage reclamation, push, deployment, and every
  production behavior change remain closed.

### Phase 2 Gate 4 Capped Invocation 3 — 2026-08-19

- Tyler approved a third capped multi-chunk invocation with the same hard limit
  of five linked SELECT-only queries. Preflight revalidated the repo/remote,
  Supabase CLI `2.115.0` command contract, six historical checkpoints, the
  four-provider runtime checkpoint, current query hash, and redaction safety.
- The invocation used its full five-query cap and issued no sixth query. The
  five BoltOdds chunks completed serially without retry or database error:
  - `2026-05-11` through `2026-05-13`: `28.83s`, `57,388` raw snapshots,
    `1,799/1,799` exact raw/compact groups;
  - `2026-05-14` through `2026-05-16`: `13.44s`, `31,972` raw snapshots,
    `2,077/2,077` exact groups;
  - `2026-05-17` through `2026-05-19`: `23.51s`, `55,066` raw snapshots,
    `3,421` raw groups, `4,276` compact groups, and all `3,421` paired groups
    exact, but `855` compact groups are unexpected and make coverage false;
  - `2026-05-20` through `2026-05-22`: `17.92s`, `36,601` raw snapshots,
    `1,740/1,740` exact groups; and
  - `2026-05-23` through `2026-05-25`: `16.84s`, `29,474` raw snapshots,
    `2,084/2,084` exact groups.
- Across the invocation, `210,501` raw snapshots and all `11,121` raw groups
  reconcile exactly to a compact group. The compact side has `11,976` groups
  because May 17 contains `220` and May 18 contains `635` unexpected compact
  groups. There are zero missing, mismatched, or duplicate groups and zero
  first/last/odds/movement/count mismatches.
- The invocation also reports `20,176` preserved cross-date rows (`19,457` on
  May 18 and `719` on May 23-25), zero unpreserved cross-date rows, and zero
  missing-run, missing-key, provider/run, unknown-provider, or other blocking
  anomalies. That proves the preserved-lineage rule is working but does not
  excuse the separate unexpected-compact blocker.
- Eleven historical checkpoints plus the four-provider runtime checkpoint now
  pass integrity, scope, equation, and redaction validation. The next missing
  matrix unit is BoltOdds `2026-05-26` through `2026-05-28`, but the safer next
  decision is a separately approved, aggregate-only diagnosis of the `855`
  unexpected compact groups before running more broad matrix slices.
- Stop here. The full matrix remains incomplete and coverage is not exact for
  May 17-18, so no envelope, readiness report, retention activation, deletion,
  vacuum, or storage-reclamation decision is available. Push, deployment, and
  every production behavior change remain closed.

### Phase 2 Unexpected-Compact Diagnosis 1 — 2026-08-19

- Tyler approved one bounded aggregate-only diagnosis of the `855` compact-only
  groups from May 17-18. A first local attempt was rejected by Windows because
  the SQL was too long for a command-line argument; it did not connect to the
  database. The same validated CTE SELECT then ran once through the documented
  Supabase CLI `--file` transport, completed in `31.11s`, and returned only two
  date-level aggregate rows. No retry, raw row, credential, source payload,
  write, repair, or deletion occurred; the temporary ignored SQL file was
  removed immediately afterward.
- The query disproves a simple orphaned-compact explanation. All `21,761`
  listed source snapshot IDs resolve to existing raw snapshots, every compact
  `snapshot_count` equals its listed source-ID count, and every source links to
  an existing provider run.
- May 18 is mostly, but not completely, explained by the historical heartbeat
  compaction path introduced in commit `cf8c37f9`: all `635` groups / `19,276`
  sources match their compact market key and link to an actual May 17 run,
  while `612` groups also have a May 18 heartbeat alias. The remaining `23`
  groups have valid source/run/key lineage but lack current heartbeat-table
  proof of that alias.
- May 17 remains unresolved. All `220` groups / `2,485` listed sources resolve
  and the source counts agree, but zero groups have every source snapshot match
  the compact row's canonical provider/book/player/market/side/line key. Actual
  run dates span May 16-17, observed dates span May 16-17, `183` groups contain
  only earlier-run sources, and only `37` groups have heartbeat-alias evidence.
  This is consistent with historical relabel/overwrite behavior but does not
  prove one benign cause.
- Keep all `855` groups as a hard exact-coverage blocker. Do not delete them,
  reclassify them as harmless, modify the audit contract, repair compact rows,
  or continue the broad matrix from May 26 until a separately approved
  aggregate-only diagnostic identifies which key dimensions disagree on May 17
  and explains the `23` May 18 groups without heartbeat proof.
- Retention activation, raw deletion, vacuum, storage reclamation, provider/
  model/notification/lock/UI changes, push, and deployment remain closed.

### Phase 2 Unexpected-Compact Diagnosis 2 — 2026-08-19

- Tyler approved one further bounded aggregate-only diagnosis to identify the
  May 17 key mismatch dimensions and split the `23` May 18 groups without full
  heartbeat proof. The one CTE SELECT ran through Supabase CLI `--file` under
  SHA-256 `30197b6fb8cf53515d0e036363a2d45f65d1b748a7302feef0e6940bd3524d29`,
  completed in `26.77s`, returned two date-level rows plus anonymous mismatch
  pattern counts, and was not retried. No individual market value, snapshot ID,
  player, book, payload, credential, write, repair, or deletion was returned or
  performed; the temporary ignored SQL file was removed.
- May 17 is isolated to market-key alias drift rather than broad grouping
  corruption. Every one of the `2,485` source rows in all `220` groups differs
  only on `market_key`; provider, book, normalized player, side, and line have
  zero mismatches. All `220` groups are single-run. `37` groups / `55` sources
  retain full heartbeat-alias evidence; the other `183` groups have none and
  link to earlier May 16 runs. All compact rows were inserted at the same
  `2026-05-17T16:32:08.700389Z` timestamp and updated only through
  `2026-05-17T16:53:43.470986Z`, supporting a narrow historical boundary.
- Repo history independently confirms a known BoltOdds market-key alias change
  in this period: commit `5a836a26` added `Strikeouts` as an accepted canonical
  pitcher-strikeouts alias, and migration
  `20260516152310_normalize_boltodds_strikeouts_in_shadow_movement_tracking.sql`
  maps `Strikeouts` to `pitcher_strikeouts` for shadow movement tracking. That
  supports the alias-drift hypothesis, but the intentionally anonymous live
  query did not expose the exact compact/source value pair, so reclassification
  is not yet authorized.
- May 18 has no key mismatch at all. `612/635` groups and `19,176/19,276`
  sources retain complete heartbeat aliases. The remaining `23` groups / `100`
  sources have no heartbeat alias rather than a partial one; `17` are
  single-run and `6` are multi-run. Their compact rows were inserted from
  `2026-05-18T16:41:12.866270Z` through `2026-05-18T18:53:26.527274Z` and some
  were updated through `2026-05-19T15:40:42.398127Z`. Valid source/run/key
  lineage is proven, but the missing heartbeat linkage remains unexplained.
- Keep all `855` groups blocking exact coverage. The smallest next evidence gate
  is a separately approved aggregate query that reports only the exact May 17
  compact/source market-key alias pairs and the May 18 no-heartbeat run/compact
  timing cohorts. Do not repair, normalize, reclassify, delete, weaken the audit,
  or resume the broad matrix before that proof is reviewed.
- Retention activation, raw deletion, vacuum, storage reclamation, provider/
  model/notification/lock/UI changes, push, and deployment remain closed.

### Phase 2 Unexpected-Compact Diagnosis 3 — 2026-08-19

- Tyler approved one final bounded aggregate-only diagnosis for the exact May 17
  market alias pair and the May 18 no-heartbeat timing cohorts. The one CTE
  SELECT ran once through Supabase CLI `--file` under SHA-256
  `8dd98540830fade34a3cf1445754a3559916f7da9d11471de22ca0bf8f897ae0`,
  completed in `46.12s`, and exited successfully without retry. It returned only
  market-key labels, counts, relationship classes, and timestamp extrema; no
  player, book, snapshot/run ID, payload, credential, write, repair, or deletion
  was returned or performed. The temporary ignored SQL file was removed.
- May 17 is now causally isolated to the exact historical alias pair. All `220`
  groups / `2,485` sources carry compact `pitcher_strikeouts` against source
  `Strikeouts`. Together with the earlier proof that every source exists, counts
  agree, and provider/book/player/side/line dimensions match, plus commit
  `5a836a26` and the contemporaneous SQL normalization, this closes the broad
  corruption hypothesis. It is an explicit canonical-market alias class, not a
  missing-source or mixed-key class. It still does not authorize weakening the
  general unexpected-compact invariant.
- The `23` May 18 groups / `100` sources also collapse into two internally
  consistent prior-day cohorts. The `17` single-run groups contain `35` sources;
  the `6` multi-run groups contain `65` sources across `18` group/run links. In
  both cohorts every actual run is dated May 17, every source snapshot and every
  surviving heartbeat is before the May 18 Phoenix boundary, compact insertion
  occurred `6-24h` after the final source observation, and compact updates
  completed within one hour. The rows have heartbeat proof for the source runs
  only on the prior day, not a same-day heartbeat alias. This is consistent with
  a historical requested-date compaction replay/carryover, but the exact trigger
  that admitted those prior-day runs is not retained in current heartbeat state.
- All `635` May 18 extras are therefore bounded: `612` retain direct same-slate
  heartbeat-alias proof and the remaining `23` have one uniform prior-day
  source/run/heartbeat and next-morning-compaction shape. The evidence explains
  the shape but does not yet prove that every unexpected row's derived movement
  metrics equal its listed sources or that every listed source group is already
  preserved by an exact actual-date compact row.
- Keep all `855` groups blocking the generic exact-coverage contract. The
  smallest next gate is a separately approved aggregate-only equivalence read:
  reconstruct first/last/min/max odds, movement count, time bounds, and source
  count from each unexpected row's listed source IDs; compare those values with
  the compact row; and prove the sources also belong to exact actual-date compact
  groups. Only after that proof should a separately reviewed, date/provider/
  alias-bounded exception contract be designed and tested. Do not repair,
  normalize, reclassify, delete, weaken the audit, or resume the broad matrix.
- Retention activation, raw deletion, vacuum, storage reclamation, provider/
  model/notification/lock/UI changes, push, and deployment remain closed.

### Phase 2 Unexpected-Compact Equivalence Gate — 2026-08-19

- Tyler approved one final aggregate-only equivalence read for the `855`
  unexpected May 17-18 compact groups. The statically validated CTE SELECT ran
  exactly once through Supabase CLI `--file` under SHA-256
  `b1406ad7ec1c2752728f2eac2a17f5935f3ddf3a02a2d19d0c82c9cbe12156bd`,
  completed in `59.55s`, and exited successfully without retry. It returned
  counts, dates, mismatch classes, and booleans only; no identifier, player,
  book, payload, credential, write, repair, or deletion was returned or
  performed. The temporary ignored SQL file was removed.
- The strict unexpected-row equivalence gate did **not** pass: only `703/855`
  extra compact groups reproduce every listed-source invariant. On May 17,
  `103/220` extras are fully equivalent and the other `117` differ only on
  `odds_move_count`; first/last seen, first/last/min/max odds, snapshot count,
  source set, run linkage, and every non-market key dimension have zero
  mismatch. On May 18, `600/635` extras are fully equivalent and the other
  `35` have duplicate listed source IDs; every time, odds, movement, count,
  source-set, and non-market key comparison otherwise has zero mismatch.
- The underlying preservation proof is exact despite those noncanonical
  extras. The May 17 sources belong to `220` actual-date groups containing
  `5,103` raw snapshots, and the May 18 sources belong to `635` actual-date
  groups containing `20,117` raw snapshots. All `855/855` actual-date groups
  have exact compact matches with zero time, odds, movement, count, or source-
  set mismatch. All `21,761/21,761` source IDs listed by the extras map to those
  exact actual-date compact groups. The extras are therefore redundant
  historical artifacts; they are not canonical season evidence.
- Local code/history review provides a high-confidence code-path explanation,
  not a separate row-level database proof. `scripts/compact_market_snapshots.py`
  pages by non-unique `observed_at` with offset pagination and no `id`
  tiebreaker. `market_infra/market_snapshot_compaction.py` also sorts only by
  `observed_at` and neither deduplicates nor fails closed on duplicate source
  IDs. Both behaviors originated in commit `71ab4d2e`; later commit `7c1564e9`
  changed page size but not ordering. Unstable tied-timestamp ordering explains
  the May 17 movement-count-only class, while repeated/omitted rows at offset
  page boundaries plus no dedupe is consistent with the May 18 duplicate-ID
  class. Existing tests do not cover tied timestamps, stable
  `(observed_at, id)` ordering, or duplicate source IDs.
- No further database diagnosis is needed for the retention decision. The next
  separately approved work should design and test deterministic ordering,
  duplicate handling, and a date/provider/alias-bounded historical-extra rule
  that can classify an extra only after exact actual-date preservation passes.
  Do not treat the extras as season truth or weaken the generic invariant.
  Broad May 26-28 matrix work remains paused until that contract is reviewed.
- Raw deletion, retention activation, repair/normalization/reclassification,
  vacuum, storage reclamation, provider/model/notification/lock/UI changes,
  push, and deployment remain closed. This read changed no database space.

---

## Separate Live-Validation Gates — Not Authorized by This Plan

After Tasks 1-5 pass independent review, stop and request fresh Tyler approval for each boundary:

1. One old provider/date chunk from the closed candidate window; review duration, query shape, aggregate equations, redaction, and checkpoint.
2. One retired-BoltOdds provider/date chunk from its active trial interval; require no `53100`, `57014`, pooler, or authentication failure.
3. One narrow runtime-boundary read; confirm no post-suspension BoltOdds evidence.
4. Only after reviewing those outputs, consider a separately approved capped multi-chunk invocation.

Any error stops immediately without retry. No live validation step authorizes backfill, deletion, vacuum, retention activation, timeout changes, schema changes, push, deployment, or production behavior changes.

---

### Retention Compaction and Historical-Extras Local Handoff — 2026-08-20

- **Local implementation status:** Stages 1-4 are implemented and independently
  reviewed on `codex/retention-compaction-historical-extras`; local merge review
  is the next decision. This handoff does not authorize a linked audit, mutation,
  retention activation, deletion, vacuum, storage reclamation, push, deployment,
  or any production behavior change.
- **Final review fix:** the final fix commit is this commit, subject
  `fix: close final retention compaction review findings`. Canonical compact
  source expansion now CASE-guards non-array JSON before
  `jsonb_array_elements_text`, strict compact coverage again groups on normalized
  provider/book/player/market/side/line keys, and only the raw compact market key
  is retained for the two literal historical allowlist checks. The provider/date
  index predicates remain raw and unchanged.
- **Deterministic compaction:** snapshot paging now requests
  `observed_at.asc,id.asc`, and compaction orders source rows by
  `(_parse_datetime(observed_at), str(id))`. Missing source IDs fail closed;
  exact duplicate mappings collapse, while conflicting duplicate mappings fail
  closed. First/last odds, movement count, snapshot count, and source IDs derive
  from the validated unique deterministic sequence.
- **Version 2 preservation contract:** the audit now enforces
  `unexpected_compact_group_count = preserved_unexpected_compact_group_count + unpreserved_unexpected_compact_group_count`.
  Strict `coverage_exact` is unchanged and remains false for any compact-only
  group, including a proven redundant historical extra.
  `retention_preservation_complete` is a separately recomputed decision: it is
  true only when missing, duplicate, mismatched, and unpreserved-unexpected
  counts are all zero. Readiness and retired-BoltOdds closure use that narrow
  preservation decision while continuing to report strict coverage and all three
  extra counts.
- **Historical allowlist:** preservation is limited exactly to BoltOdds May 17
  compact `pitcher_strikeouts` rows whose listed sources are `Strikeouts` with
  May 16-17 run/Phoenix observation dates, and BoltOdds May 18 carryover rows
  whose run/Phoenix observation dates are all May 17. Both classes require exact
  provider/book/player/market/side/line dimensions and exact canonical
  correct-date compact preservation; all other dates, providers, aliases, and
  timing patterns remain unpreserved and blocking.
- **Checkpoint invalidation:** the current code-derived query-contract SHA-256
  is `748ebd215769b49bffeb255dd9a147349ba0939b47d75a885832d49271776a2a`.
  The runner is version `3` under query-contract version
  `supabase-db-query-linked-json-v1`; all prior-contract checkpoints fail
  closed and cannot be resumed or mixed with this contract.
- **Reviewed local commits:** Task 1 `525bea29` (deterministic compaction;
  12 focused / 2406 full-suite tests); Task 2 `598f5369` and `ebe21b20`
  (historical-extra SQL and null/malformed-source fail-closed fix; 28 focused /
  2412 full-suite tests); Task 3 `19cd05fc` (runner/envelope validation and
  runner v3); and Task 4 `1607befe` (readiness, closure, reporting, and the
  reporter-version seam; 408 focused / 2434 full-suite tests). The final fix is
  this commit (`fix: close final retention compaction review findings`) and the
  final exact tree passes 31 SQL-contract tests, 423 five-file focused tests,
  and 2,437 full-repository tests. The full suite's generated Gate F report was
  restored to committed blob `1ef07b8332e2f3dd040317592950e909b1e852ae`.
  Task 3's
  temporary reporter failure was a sequencing seam resolved by Task 4; the
  final branch must be fully green before any merge decision.
- **Closed gates:** no live query, database mutation, deletion, retention
  execution, repair, normalization, backfill, vacuum, storage reclamation,
  secret/configuration change, push, deployment, or merge occurred in this
  local handoff. After separately approved local merge, a fresh bounded audit
  remains a distinct approval gate; deletion remains separately closed.

### June 16 BoltOdds Compact-Partition Blocker and Repair Preview — 2026-08-20

- Fresh read-only evidence under query-contract SHA-256
  `e3091876ffe253d948c83e3e31c89f1a4fbde54381f91695f3963f2208866e05`
  now covers `21` continuous BoltOdds checkpoints from April 28 through July 9.
  The June 16 partition is the first hard blocker: `172` raw rows in `107`
  groups compare with `107` compact groups, of which `90` are exact and `17`
  are mismatched. Missing, unexpected, duplicate, and source-anomaly counts are
  all zero. The raw logical footprint is only `131,160` bytes, about `0.125`
  MiB, so this date must not be deleted around or excused for capacity reasons.
- Tyler separately approved one aggregate-only June 16 diagnosis. The one
  SELECT-only query ran once under SHA-256
  `f93a9d2198d20826e053272119063af42021fdaa91e7ab0928bb2936437de7e5`,
  completed in `19s`, and was not retried. Across the `17` mismatched groups,
  raw snapshot count is `46` while the compact source arrays contain `18`
  distinct IDs. Every compact source array is internally valid and agrees with
  its stored compact snapshot count, but none represents the full raw group.
  Compact first-seen time is later in every group by `126.849694` to
  `817.097145` seconds; the aggregate snapshot-count and movement-count deltas
  are both `-28`. Last-seen time and last odds remain exact. There are zero
  timestamp-tie groups and zero duplicate raw IDs.
- The evidence isolates stale/truncated historical compaction rather than a
  retention-predicate defect: the stored compact rows faithfully describe a
  partial set ending at the correct final observation while omitting `28`
  earlier snapshots. The broad all-provider compactor is also called by the
  live layer and is therefore unchanged.
- Tyler approved a bounded code-only repair-preflight tool. Local commits
  `d98411e7` and `8e619bb1` add
  `scripts/repair_compact_market_snapshot_partition.py` plus tests. Preview is
  aggregate-only and exact-provider/date scoped. It validates run UUIDs,
  heartbeat linkage, and the Phoenix midnight-to-midnight observation window;
  selects no raw payloads; performs one-attempt reads; never writes provider
  usage; never deletes; and refuses to overwrite prior evidence.
- Database execution is hard-limited in code to BoltOdds June 16 and requires
  both `ALLOW_COMPACT_MARKET_PARTITION_REPAIR=true` and the exact current
  preview SHA-256. Any unexpected compact row, no-op/empty partition, or raw or
  compact partition requiring offset pagination blocks execution. An approved
  write could upsert only missing/mismatched compact rows on the existing exact
  unique key, then it must reread raw inputs and compact state and prove the
  preview remained current. Ambiguous request failures remain unconfirmed
  unless that bounded post-state is exact.
- Tyler approved one read-only repair preview. Two local transport attempts
  stopped before the database because the select-only guard requires the
  literal `WITH ` prefix and the isolated worktree does not carry the ignored
  Supabase link metadata. The approved SELECT was then run once from the linked
  main clone while importing the reviewed worktree code. It returned data, but
  preview generation failed closed before writing a report because one or more
  same-provider/same-slate heartbeats had observation timestamps outside the
  June 16 Phoenix day. No database mutation occurred and the read was not
  retried.
- Tyler then approved a code-only correction, committed locally as `e6416fc1`.
  Valid BoltOdds/June 16 heartbeats outside the Phoenix day are now quarantined
  and counted, and their run IDs cannot expand repair lineage. Provider/date
  drift and malformed timestamps still fail closed. The preview fingerprint is
  version `2` and binds total, in-window, and out-of-window heartbeat counts.
  A separate source-state digest also binds provider runs, those heartbeat
  counts, raw snapshots, and rebuilt compact state so an approved future upsert
  cannot be reported exact if any source input changes during execution.
- Test-first verification passed `40` focused repair tests, `204` combined
  repair/retention tests, and `2,476` complete repository tests. Python
  compilation and `git diff --check` passed, the generated Gate F report was
  restored to committed blob `1ef07b8332e2f3dd040317592950e909b1e852ae`,
  and independent rereview found no Critical, Important, or Minor issue. This
  is still a local branch handoff only; no database write, deletion, vacuum,
  reclamation, push, deployment, or production behavior change has occurred.
- Tyler approved that next read-only preview. Local preflight confirmed the
  reviewed branch, a fresh output destination, one-attempt SELECT behavior, and
  no execute flag. The linked CLI invocation used SELECT-only query SHA-256
  `e943b90da134317e6b4c8d0d8b6bb18d047a158b09c1a289f404f86c5c16cf44`
  and exited once with code `1`. The wrapper intentionally did not retry. It
  produced no evidence directory or preview report and could not expose the
  underlying CLI error text, so no preview facts or fingerprint are available.
  Tyler separately approved one replacement attempt under the same query hash;
  it also exited once with code `1`, this time classified as `sql_contract`,
  and was not retried. The queries were read-only and no database mutation,
  repair, deletion, vacuum, reclamation, provider-usage write, push, deployment,
  or production behavior change occurred.
- The failed invocation does not reopen execution. The one-use local wrapper
  now retains only a sanitized CLI error class on a future failure; local
  classifier checks cover circuit breaker, authentication, statement timeout,
  connection, SQL-contract, and unclassified failures without exposing raw CLI
  output. The next local query shape is simplified and fully schema-qualified,
  drops the unnecessary parameter joins and `created_at` dependency, preserves
  the exact BoltOdds/June 16/Phoenix-window scope, and passed local contract
  assertions at SHA-256
  `062aafdc67521d1ee4f282a1321c3177f8fe8c8bd6ae88a31bf21b397016ce4b`.
  Tyler separately approved one live attempt under that exact hash. It exited
  once with code `1`, classified as `sql_contract`, was not retried, and again
  produced no evidence directory or preview report. Fully qualifying the tables
  and simplifying the joins therefore did not resolve the hosted SQL contract;
  do not keep guessing at preview SQL.
- The next gate is one separately approved, aggregate-only
  `information_schema.columns` read for the four referenced tables. It should
  return only table, column, and data-type metadata, retain a sanitized CLI
  failure detail if it fails, and make no data-row read. Tyler approved the
  metadata-only query at SHA-256
  `639f6cfb88cea1fb3860ef80340acb7159dc964f708dac9aee6f524bea8c9e23`.
  It exited once with code `1`, was classified as `sql_contract`, was not
  retried, and produced no evidence directory. Because even this simple hosted
  catalog read failed the same way, the coarse classifier may be masking a
  CLI/link/control-plane error rather than proving a schema mismatch.
- Tyler approved one linked `select now()` connectivity read at query SHA-256
  `03bb88f628780fe2325cf7a763a1e2494004b8ffbc0fb5061064dda0736db146`.
  The CLI exited successfully without retry, proving the linked database path
  is reachable. The temporary wrapper then rejected the CLI's successful JSON
  envelope before writing its local report, so the exact returned timestamp is
  not retained. This was a decoder-only local failure after a successful
  read-only query; no database write or application-table read occurred.
- Do not query application tables again yet. The metadata wrapper now accepts
  list, `rows`, `result`, and `data` envelopes and, on CLI failure, persists only
  an aggressively redacted error excerpt. Local envelope/redaction checks pass.
  Tyler approved one replacement `information_schema.columns` read under the
  unchanged metadata query hash `639f6cfb...`. It exited once with code `1`,
  was not retried, and retained PostgreSQL error `42601`: syntax error at end of
  input on line `0`. This proves the multiline SQL arrived empty through the
  Windows inline `npx.cmd` argument; it is not evidence of a hosted schema
  mismatch.
- The exact same metadata-only SQL is now stored in a fresh temporary file and
  the wrapper uses CLI `--file`, matching the transport used by earlier
  successful bounded reads in this plan. The exact file SHA-256 is
  `0911a036c28b53eeff0bd3708b31bb883c2b83848f7fffc6e3eccfcec610b5f8`;
  local select-only and redaction checks pass. Tyler approved continuing the
  remaining read-only diagnosis without repeated approval prompts. The linked
  file-transport metadata read succeeded once without retry and retained `63`
  columns across all four expected tables (`20` compact, `10` heartbeat, `14`
  provider-run, `19` snapshot); hosted names and data types match the preview
  contract. No database write occurred.
- The same `--file` transport then ran the exact June 16 preview query at
  SHA-256 `2f88ae7838cb54971b91061b09abf805411e111e6b098440270bafb11c4c6bd1`.
  It succeeded once without retry and wrote aggregate-only local report SHA-256
  `47b381cbabebd52bf136c4678a922f6e4af7f09911cd7ae4da2da9c09fee3832`.
  The preview finds `285` provider runs and `791` same-slate heartbeats: `580`
  in-window and `211` quarantined outside the Phoenix day. `172` raw snapshots
  deterministically rebuild `107` compact groups against `107` existing rows;
  `17` are mismatched, `0` missing, and `0` unexpected, so exactly `17` rows
  would be upserted. The preview is blocker-free and execution-eligible under
  preview fingerprint
  `320c254d958d52f24a29ab75db980273ad3e9b4651fc6a3e3f4e7762a142399f`
  and source-state SHA-256
  `4c7c44839d7ef7bad3498adc45a836c8192c09b1f9252b82b24c445740d1c3b0`.
  It performed no write and keeps deletion and retention execution closed.
- Tyler explicitly approved the bounded repair. A fresh pre-read reproduced
  preview fingerprint
  `320c254d958d52f24a29ab75db980273ad3e9b4651fc6a3e3f4e7762a142399f`
  and the reviewed one-attempt wrapper upserted exactly the `17` canonical
  BoltOdds June 16 compact rows on the existing unique key. The execution
  report SHA-256 is
  `c8feae95bf052e26b985625083862615eebb14427964568e64eb7d6c4e051cd7`.
  Its fresh post-read found `0` missing, `0` mismatched, and `0` unexpected
  groups, confirmed that the source state was still current, and recorded no
  deletion. No other provider/date partition or table was mutated.
- A separate fresh, read-only bounded checkpoint then completed under query
  contract SHA-256
  `e3091876ffe253d948c83e3e31c89f1a4fbde54381f91695f3963f2208866e05`.
  Checkpoint file SHA-256
  `150734f5db762d083885d9faec93431e433ced47695211797326f81ecbc6330b`
  proves `107/107` exact groups, `retention_preservation_complete: true`, zero
  missing/mismatched/unexpected/duplicate groups, zero source anomalies, and
  `131,160` raw logical bytes. The checkpoint integrity SHA-256 is
  `30c0d67bc534ae8fd2ba6b5fd53878a111fc1af12ad85660e017bd6c8cc668c2`.
  The June 16 compact-integrity blocker is therefore closed. The upsert repaired
  historical compact evidence but reclaimed no database space.
- One subsequent read-only BoltOdds checkpoint for July 10-16 initially failed
  closed as `subprocess_failed`. Instrumented diagnosis proved the exact local
  cause: the isolated worktree has no `supabase/.temp/project-ref`, so the CLI
  reported `Cannot find project ref` and never queried the database. This was
  not a pooler, authentication, statement-timeout, SQL-contract, or database
  pressure failure. The unchanged reviewed worktree code was then run from the
  linked main clone, matching the successful June 16 transport.
- The linked July 10-16 checkpoint completed in `13.79s`. All seven requested
  partitions have zero raw/compact rows, zero candidate runtime, zero source
  anomalies, `coverage_exact: true`, and
  `retention_preservation_complete: true`. Checkpoint file SHA-256 is
  `25655f8eec984018dbe54184b2e828ca7a0bf80a830b9033073596d72dc0124e`;
  integrity SHA-256 is
  `93c1a48d4c257b53f417d1c787b7f2e6428bff507a7f4242776f3b5bcbfa9268`.
- After the normal 30-second cooldown, the linked July 17-22 checkpoint
  completed in `11.96s`. All six partitions have the same exact zero state.
  Checkpoint file SHA-256 is
  `c13ed95d79b3f52751f63617e64869738883c3fc5ef97e22da4c2bfe2b652f77`;
  integrity SHA-256 is
  `c762e4113381a0505733fb816b9556140147e36b3521f0213f5896794049c3b5`.
  Together with the documented April 28-July 9 checkpoint sequence, this
  closes retired-BoltOdds candidate-date coverage through July 22 and confirms
  no fresh retired-provider runtime after June 16.
- One aggregate-only sizing read then completed under SELECT-only query SHA-256
  `ed83774953eb0e2c7148bebd2bdf93460438210828de5d1cb6615a4204e81519`.
  Sanitized local evidence SHA-256 is
  `e91942fb81b27a306c4e027d6132fea91900a27e6ad7cd811250ee077b23fe05`.
  The database is `5,046,348,947` bytes, about `4.70 GiB` or `58.75%` of the
  included 8 GiB. `market_snapshots` occupies `3,513,262,080` total bytes.
  The exact retired-BoltOdds candidate scope contains `611,972` raw rows and
  `461,536,160` logical bytes, about `440 MiB`; its preserved compact evidence
  is `26,726` rows and `28,600,016` logical bytes. There are zero raw BoltOdds
  rows after `2026-06-17T17:22:29Z`. This is a meaningful cleanup candidate,
  but ordinary deletion would create reusable table space and would not by
  itself guarantee an immediate fall in physical database bytes.
- No explicit normalized season-evidence or pin manifest is present in the
  repository. The existing readiness contract therefore remains blocked on
  outcome-linked evidence, incident/accepted-bet/alert/provider-transition
  pins, and recovery/export proof even though compact coverage is now exact.
- Gate C covers `40/41` BoltOdds-era dates from May 7 through June 16. June 3
  is absent even though aggregate-only evidence records `14` accepted bets,
  `73` sent notifications, and `24` consumed locks that day. The compact
  archive itself is healthy for June 3 (`13,801` raw rows preserved into `627`
  compact rows), so this is a season-evidence gap rather than a compaction
  failure. Across the same period, `652/844` tracked rows lack explicit
  provider metadata. Both gaps must be resolved or explicitly pinned before
  any raw deletion proposal can pass readiness.
- The current backup inventory shows completed physical backups through
  `2026-08-21T05:32:59.453Z`, with `pitr_enabled: false`. That latest backup
  predates the June 16 compact repair and this closure evidence. A completed
  post-repair backup is therefore still required; backup inventory alone is
  not proof of a tested restore.
- The repository documents the earlier April 28-July 9 checkpoint sequence,
  but those older checkpoint files are not present in the current local
  evidence directory. Do not claim a freshly assembled canonical
  four-provider envelope until the existing artifacts are recovered or the
  matrix is regenerated through separately bounded reads.
- Stop before any additional mutation. Recoverability proof, recoverable-space
  estimate, season-evidence pins, retention execution, deletion, vacuum,
  reclamation, push, merge, deployment, and production behavior remain closed
  and separately gated. Provider, model, notification, lock, UI, artifact, and
  source-of-truth behavior are unchanged.

## 2026-08-21 Gate C Transport Closure Overlay

- The bounded `picks_history` date-window transport was merged and pushed on
  `main` at `016f0676`, then deployed to Netlify production as deploy
  `6a88b9462f9c4a8071b3d91f` after a successful preview.
- Production proof for June 3 returned `24` rows in `33,196` bytes, preserved
  Robert Gasser as the official `UNDER 3.5` loss with `5` actual strikeouts,
  rejected a reversed window with HTTP `400`, and left the normal `today`
  artifact healthy.
- The canonical April 28-June 16 Gate C rebuild now covers all `50` dates with
  `2,070` rows, `1,075` tracked rows, zero duplicate keys, and `1,075/1,075`
  reconciliation. June 3 is present, and Gasser's archived `4.5` market is
  recovered through `picks_history_pitcher_game` without mutating the archive
  or official history.
- Semantic comparison against the prior canonical JSONL found `48` added June
  3 rows, `2` late June 16 Adrian Houser rows, zero removed keys, and only the
  explicit archive-reconciliation source plus the null
  `projection_challenger` schema field added to pre-existing rows.
- This closes the Gate C date-coverage blocker. It does not close provider
  attribution or explicit unknown pins, normalized season/pin manifests, the
  canonical checkpoint envelope, or the post-repair backup gate. Retention
  execution, deletion, vacuum, and reclamation remain closed and require a
  separate exact proposal and approval.

## 2026-08-21 Attribution And Aggregate-Manifest Closure Overlay

- The additive Gate C provenance repair preserves archived `odds_source`,
  `market_source_mode`, and `line_source_provider` in separate official-source
  fields. It never infers a provider and does not repurpose the live-movement
  `provider` field.
- The canonical April 28-June 16 dataset remains `2,070` rows, `1,075` tracked,
  zero duplicates, and `1,075/1,075` reconciled. The exact May 7-June 16 raw
  deletion candidate has explicit official odds-source coverage on all
  `869/869` tracked rows. The `65` explicit unknowns are confined to April
  28-30 and are outside the candidate.
- One bounded SELECT-only aggregate read produced `41` date rows with no bet
  identity, notification text, lock identity, provider payload, or credential.
  The normalized season manifest records `869` official tracked picks, `317`
  accepted bets, `1,778` sent notifications, `535` consumed locks, zero frozen
  Alt V2 rows in this older window, and four repository-linked incident pins.
- The pin manifest contains all `41/41` BoltOdds candidate partitions, all
  reconciled under the existing version-1 consumer contract. Detailed accepted
  bets, notifications, locks, and Alt state remain in their untouched Supabase
  tables and are not part of the proposed raw `market_snapshots` deletion.
- This closes the candidate-window official-source and normalized season/pin
  blockers. The canonical four-provider checkpoint envelope and a completed
  post-repair physical backup remain open. Retention execution, deletion,
  vacuum, and reclamation remain separately closed.

## 2026-08-24 Nine-Partition Repair Preview Overlay

- Fresh comparison of the saved August 20/21 checkpoints proved that nine
  BoltOdds partitions were already non-exact in the retained evidence; this is
  not new provider runtime. The dates are June 2, 3, 5, 6, 9, 12, 13, 14, and
  15. Together they contain `317` missing and `1,721` mismatched compact groups,
  or exactly `2,038` rows requiring bounded upsert repair. BoltOdds remains
  retired and has no role in production artifacts, picks, models, alerts,
  locks, UI, or provider order.
- The manual repair tool now uses deterministic keyset pagination instead of
  offset pagination. Snapshot paging orders on `(observed_at, id)` and compact
  paging orders on the positive compact row ID; both fail closed if the cursor
  does not advance or the page ceiling is reached. Execution remains limited
  to the exact reviewed BoltOdds dates, including the already repaired June 16
  regression partition, and still requires the environment gate plus the exact
  current preview fingerprint.
- A first v3 preview exposed a contract mismatch on June 6 and was stopped
  before further reads: the repair tool clipped snapshots to the Phoenix day,
  while the controlling retention audit groups all snapshots by verified
  provider-run slate date. The corrected v4 contract reads only snapshots tied
  to the exact provider/date run IDs, separately counts cross-boundary rows,
  and binds those counts plus rebuilt compact hashes into the source-state and
  preview fingerprints. This preserves `109` legitimate cross-boundary rows:
  two on the June 3 run partition and `107` on June 6.
- Nine fresh v4 previews completed without retries or mutation. They cover
  `106,997` raw snapshots, `5,102` rebuilt groups, and `4,785` existing groups.
  Every date matches its saved missing/mismatch counts, has zero unexpected
  rows, is execution-eligible, and records `database_write_performed: false`.
  The aggregate-only reports are under ignored local directory
  `analytics/output/retention/repair-preview-nine-partitions-2026-08-24-v4`.
- Test-first verification passed `40` focused repair tests, `466` combined
  repair/retention tests, and `2,514` full-repository tests. Python compilation
  and `git diff --check` passed; the full suite's generated Gate F report was
  restored to committed blob `1ef07b8332e2f3dd040317592950e909b1e852ae`.
- This evidence approves no write by itself. Repair execution remains a
  separate Tyler decision and, if approved, must run one fingerprint-bound date
  at a time with exact post-read verification. Deletion, retention activation,
  vacuum, reclamation, and production behavior remain closed. After all
  approved repairs, regenerate the exact checkpoints and canonical envelope,
  then verify a completed physical backup newer than every repair before any
  deletion proposal can be drafted.

## 2026-08-24 Nine-Partition Repair Execution Overlay

- Tyler explicitly approved the exact nine-date Supabase compact repair after
  reviewing the v4 previews. Execution used pushed branch commit `e2a9d5f3`
  with a clean worktree and the unchanged v4 preview fingerprint for each date.
  The tool processed one date at a time and stopped between dates until the
  prior execution report proved a confirmed write, current source state, and
  exact post-read.
- The nine confirmed upserts were June 2 `141`, June 3 `164`, June 5 `87`,
  June 6 `14`, June 9 `380`, June 12 `385`, June 13 `473`, June 14 `225`, and
  June 15 `169`: exactly `2,038` compact rows. Every report records
  `database_write_outcome: confirmed`, `database_write_performed: true`,
  `post_write_preview_still_current: true`, and `post_write_exact: true`.
  Aggregate post-state is zero missing, mismatched, and unexpected groups.
  Execution evidence is retained in ignored local directory
  `analytics/output/retention/repair-execution-nine-partitions-2026-08-24-v4`.
- Two separate SELECT-only checkpoints then completed under canonical query
  contract SHA-256
  `e3091876ffe253d948c83e3e31c89f1a4fbde54381f91695f3963f2208866e05`.
  June 2-8 checkpoint SHA-256 is
  `89a70eb4f60993342d747669fa4bdd08049f3ad89cfabf0134063862561a4a06`;
  all seven partitions are coverage-exact and retention-complete, with `109`
  preserved cross-date rows and zero unpreserved rows. June 9-15 checkpoint
  SHA-256 is
  `77c4831a9a99e9fad6733986ccb28037a564f0d89b3cede4f1b0bd12d2d957ef`;
  all seven partitions are also exact and complete, with `187` preserved
  cross-date rows and zero unpreserved rows. Both ranges have zero
  missing/mismatched/unexpected/duplicate groups and zero other blocking source
  anomalies.
- Fresh runtime-boundary evidence SHA-256
  `80be0989cbe93d8124ec7cd175b5e959526cc7cb11d8af703709aa4220d49c88`
  keeps BoltOdds at the documented retirement boundary: latest snapshot June
  16 and latest heartbeat/message/run June 17. The compact repair did not
  reactivate the worker or create fresh raw snapshots.
- The latest completed physical backup remains
  `2026-08-24T05:33:11.108Z`, before the final execution evidence at
  `2026-08-24T17:57:48Z`; PITR is disabled. Therefore recoverability remains
  open even though compact coverage is now exact. Wait for a completed physical
  backup newer than every repair, then assemble or regenerate the complete
  canonical four-provider checkpoint envelope.
- No raw snapshot was deleted. Retention activation, deletion, vacuum,
  reclamation, provider/runtime changes, model changes, notification changes,
  lock changes, UI changes, and source-of-truth changes remain closed.
