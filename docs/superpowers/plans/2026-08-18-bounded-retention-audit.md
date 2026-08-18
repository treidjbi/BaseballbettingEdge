# Bounded Season-Retention Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local, read-only, resumable provider/date audit that proves exact season-retention coverage without another full-season database sort or any deletion authority.

**Architecture:** Generate SELECT-only SQL for one provider across one, three, or at most seven slate dates, execute it serially through the linked Supabase CLI, and checkpoint only validated aggregate output. A local assembler emits a fail-closed version 2 envelope only after the entire expected provider/date matrix and a separate narrow runtime-boundary read reconcile; the existing readiness reporter then consumes that envelope without changing production data or behavior.

**Tech Stack:** Python 3.11 standard library, PostgreSQL through `npx supabase db query --linked`, pytest

**Spec:** `docs/superpowers/specs/2026-08-18-bounded-retention-audit-design.md`

**Plan status (2026-08-18):** Ready for execution-path selection. No implementation or live Supabase read has run from this plan.

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

## Separate Live-Validation Gates — Not Authorized by This Plan

After Tasks 1-5 pass independent review, stop and request fresh Tyler approval for each boundary:

1. One old provider/date chunk from the closed candidate window; review duration, query shape, aggregate equations, redaction, and checkpoint.
2. One retired-BoltOdds provider/date chunk from its active trial interval; require no `53100`, `57014`, pooler, or authentication failure.
3. One narrow runtime-boundary read; confirm no post-suspension BoltOdds evidence.
4. Only after reviewing those outputs, consider a separately approved capped multi-chunk invocation.

Any error stops immediately without retry. No live validation step authorizes backfill, deletion, vacuum, retention activation, timeout changes, schema changes, push, deployment, or production behavior changes.
