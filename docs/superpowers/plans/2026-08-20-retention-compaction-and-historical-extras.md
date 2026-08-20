# Retention Compaction and Historical Extras Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make snapshot compaction deterministic and let the bounded retention audit distinguish proven redundant May 17-18 BoltOdds extras from unpreserved compact-only evidence without weakening strict coverage truth.

**Architecture:** Stage 1 validates and deduplicates source rows, then uses one canonical `(observed_at, id)` order from REST fetch through compact output. Stage 2 extends the version 2 bounded SQL, runner, and reporters with total/preserved/unpreserved unexpected-group counts plus a separately derived retention-preservation decision; literal `coverage_exact` remains unchanged.

**Tech Stack:** Python 3.11, pytest, generated PostgreSQL/JSONB SELECTs, Supabase/PostgREST request parameters, Markdown handoff docs

**Spec:** `docs/superpowers/specs/2026-08-20-retention-compaction-and-historical-extras-design.md`

## Global Constraints

- Work only in the isolated branch/worktree `codex/retention-compaction-historical-extras`.
- Use red-green TDD for every behavior change; no production code before its failing test.
- Do not run a linked Supabase query or make any database write.
- Do not change a schema, migration, dependency, timeout, cadence, provider flag, provider order, source of truth, model, notification, lock, UI, artifact, retention window, or deletion path.
- Do not modify `scripts/retire_market_snapshots.py` or `scripts/backfill_compact_market_movements_via_cli.py`.
- Keep `unexpected_compact_group_count` and `coverage_exact` literal and visible.
- Only `boltodds` on `2026-05-17` and `2026-05-18` can enter the historical preserved-extra proof.
- Every other provider/date/alias/timing class remains unpreserved and blocking.
- Version 1 reporter behavior remains byte-for-byte compatible at the JSON contract level.
- Increment `RUNNER_VERSION` so old version 2 checkpoints cannot mix with the new exact-field contract.
- No push, deploy, merge, retention activation, deletion, vacuum, or storage reclamation.

---

### Task 1: Deterministic Snapshot Compaction

**Files:**
- Modify: `market_infra/market_snapshot_compaction.py:1-112`
- Modify: `scripts/compact_market_snapshots.py:12-128`
- Test: `tests/test_market_snapshot_compaction.py`
- Test: `tests/test_compact_market_snapshots_script.py`

**Interfaces:**
- Consumes: raw snapshot mappings with required non-empty `id` and `observed_at` fields.
- Produces: `deduplicate_snapshot_rows(snapshot_rows: list[dict[str, Any]]) -> list[dict[str, Any]]`; `compact_snapshot_rows()` retains its current return type and conflict key.
- Invariant: compact movement order is `(_parse_datetime(row["observed_at"]), str(row["id"]))`.

- [ ] **Step 1: Add failing pure-compactor ordering and ID-contract tests**

Append these behaviors to `tests/test_market_snapshot_compaction.py`:

```python
import pytest


def _same_time_row(snapshot_id, odds):
    return {
        "slate_date": "2026-05-17",
        "provider": "boltodds",
        "bookmaker_key": "fanduel",
        "player_name": "Example Pitcher",
        "normalized_player_name": "example pitcher",
        "market_key": "pitcher_strikeouts",
        "side": "over",
        "line": 5.5,
        "american_odds": odds,
        "observed_at": "2026-05-17T18:00:00Z",
        "id": snapshot_id,
    }


def test_compaction_tie_breaks_equal_timestamps_by_source_id():
    compact = compact_snapshot_rows([
        _same_time_row("b", -120),
        _same_time_row("c", -130),
        _same_time_row("a", -110),
    ])[0]
    assert compact["first_odds"] == -110
    assert compact["last_odds"] == -130
    assert compact["odds_move_count"] == 2
    assert compact["source_snapshot_ids"] == ["a", "b", "c"]


def test_compaction_collapses_identical_duplicate_source_ids():
    first = _same_time_row("a", -110)
    compact = compact_snapshot_rows([first, dict(first), _same_time_row("b", -120)])[0]
    assert compact["snapshot_count"] == 2
    assert compact["source_snapshot_ids"] == ["a", "b"]


def test_compaction_rejects_conflicting_duplicate_source_ids():
    first = _same_time_row("a", -110)
    conflict = {**first, "american_odds": -125}
    with pytest.raises(ValueError, match="conflicting duplicate snapshot id: a"):
        compact_snapshot_rows([first, conflict])


def test_compaction_rejects_missing_source_id():
    row = _same_time_row("a", -110)
    row.pop("id")
    with pytest.raises(ValueError, match="snapshot id is required"):
        compact_snapshot_rows([row])
```

- [ ] **Step 2: Run the pure-compactor tests and verify RED**

Run:

```powershell
python -m pytest tests/test_market_snapshot_compaction.py -q
```

Expected: the tied-timestamp assertion fails under arrival-order sorting, duplicate rows are counted twice, and missing/conflicting IDs do not raise.

- [ ] **Step 3: Implement one reusable source-ID validator/deduper and canonical sort**

Add this helper to `market_infra/market_snapshot_compaction.py` and call it at the start of `compact_snapshot_rows()`:

```python
def deduplicate_snapshot_rows(
    snapshot_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows_by_id: dict[str, dict[str, Any]] = {}
    for raw_row in snapshot_rows:
        row = dict(raw_row)
        snapshot_id = str(row.get("id") or "").strip()
        if not snapshot_id:
            raise ValueError("snapshot id is required for compaction")
        existing = rows_by_id.get(snapshot_id)
        if existing is None:
            rows_by_id[snapshot_id] = row
        elif existing != row:
            raise ValueError(f"conflicting duplicate snapshot id: {snapshot_id}")
    return list(rows_by_id.values())
```

Replace the opening grouping loop and timestamp-only sorting with:

```python
validated_rows = deduplicate_snapshot_rows(snapshot_rows)
grouped: dict[
    tuple[str, str, str, str, str, str, str, float],
    list[dict[str, Any]],
] = {}
for row in validated_rows:
    if not row.get("observed_at"):
        continue
    side = str(row.get("side") or "").strip().lower()
    if side not in {"over", "under"}:
        continue
    grouped.setdefault(_snapshot_key(row), []).append(row)

# Inside `for key, rows in grouped.items():`
ordered = sorted(
    rows,
    key=lambda row: (
        _parse_datetime(row["observed_at"]),
        str(row["id"]),
    ),
)
```

Do not change grouping keys or output fields.

- [ ] **Step 4: Run the pure-compactor tests and verify GREEN**

Run:

```powershell
python -m pytest tests/test_market_snapshot_compaction.py -q
```

Expected: all tests pass and existing ordinary unique-row output remains unchanged.

- [ ] **Step 5: Add failing script-level REST-order and page-duplicate tests**

In `tests/test_compact_market_snapshots_script.py`, add `import pytest`, extend
the paging test, and add these tests:

```python
def test_compact_script_uses_unique_deterministic_rest_order():
    writer = FakeWriter()
    compact_market_snapshots.run(
        slate_date="2026-05-14", writer=writer, dry_run=True,
    )
    snapshot_calls = [params for table, params in writer.selects if table == "market_snapshots"]
    assert snapshot_calls[0]["order"] == "observed_at.asc,id.asc"


def test_snapshot_pages_collapse_identical_boundary_duplicate():
    writer = FakeWriter()
    duplicate = {
        "id": "snap-999",
        "run_id": "run-1",
        "provider": "boltodds",
        "bookmaker_key": "fanduel",
        "player_name": "Example Pitcher",
        "normalized_player_name": "example pitcher",
        "market_key": "pitcher_strikeouts",
        "side": "over",
        "line": 5.5,
        "american_odds": -110,
        "observed_at": "2026-05-14T19:00:00Z",
    }
    pages = {
        "0": [{**duplicate, "id": f"snap-{i}"} for i in range(999)] + [duplicate],
        "1000": [dict(duplicate)],
    }
    writer.select_rows = lambda table, params: (
        [{"id": "run-1", "provider": "boltodds", "slate_date": "2026-05-14"}]
        if table == "market_provider_runs" and "slate_date" in params
        else [] if table == "market_feed_heartbeats"
        else pages.get(params.get("offset"), []) if table == "market_snapshots"
        else []
    )
    rows = compact_market_snapshots._fetch_snapshot_pages(
        writer, [{"id": "run-1"}], slate_date="2026-05-14",
    )
    assert len(rows) == 1000


def test_snapshot_pages_reject_conflicting_boundary_duplicate():
    writer = FakeWriter()
    duplicate = {
        "id": "snap-999",
        "run_id": "run-1",
        "provider": "boltodds",
        "bookmaker_key": "fanduel",
        "player_name": "Example Pitcher",
        "normalized_player_name": "example pitcher",
        "market_key": "pitcher_strikeouts",
        "side": "over",
        "line": 5.5,
        "american_odds": -110,
        "observed_at": "2026-05-14T19:00:00Z",
    }
    pages = {
        "0": [{**duplicate, "id": f"snap-{i}"} for i in range(999)] + [duplicate],
        "1000": [{**duplicate, "american_odds": -125}],
    }

    def select_rows(table, params):
        writer.selects.append((table, dict(params)))
        if table == "market_snapshots":
            return pages.get(params.get("offset"), [])
        return []

    writer.select_rows = select_rows
    with pytest.raises(
        ValueError, match="conflicting duplicate snapshot id: snap-999",
    ):
        compact_market_snapshots._fetch_snapshot_pages(
            writer, [{"id": "run-1"}], slate_date="2026-05-14",
        )
```

- [ ] **Step 6: Run the script tests and verify RED**

Run:

```powershell
python -m pytest tests/test_compact_market_snapshots_script.py -q
```

Expected: the order assertion sees `observed_at.asc`, the identical duplicate remains, and the conflicting duplicate does not raise.

- [ ] **Step 7: Apply deterministic REST order and dedupe after page assembly**

Import `deduplicate_snapshot_rows` beside `compact_snapshot_rows`, change the REST parameter, and validate after all pages are collected:

```python
from market_infra.market_snapshot_compaction import (  # noqa: E402
    compact_snapshot_rows,
    deduplicate_snapshot_rows,
)

# In _fetch_snapshot_pages:
"order": "observed_at.asc,id.asc",

# After the page loop:
return deduplicate_snapshot_rows(rows)
```

Keep the existing per-row `slate_date` default before deduplication so equality uses the complete effective mapping.

- [ ] **Step 8: Run Stage 1 focused verification**

Run:

```powershell
python -m pytest tests/test_market_snapshot_compaction.py tests/test_compact_market_snapshots_script.py -q
python -m py_compile market_infra/market_snapshot_compaction.py scripts/compact_market_snapshots.py
git diff --check
```

Expected: all tests pass, compilation exits `0`, and the diff check is clean.

- [ ] **Step 9: Commit Stage 1**

```powershell
git add -- market_infra/market_snapshot_compaction.py scripts/compact_market_snapshots.py tests/test_market_snapshot_compaction.py tests/test_compact_market_snapshots_script.py
git commit -m "fix: make market compaction deterministic"
```

---

### Task 2: Proof-Based Historical-Extra SQL Contract

**Files:**
- Modify: `scripts/retention_bounded_sql.py:54-506`
- Test: `tests/test_retention_bounded_sql.py`

**Interfaces:**
- Consumes: existing bounded provider/date inputs and indexed raw/compact tables.
- Produces: three new coverage integers and one boolean in every explicit provider/date row: `preserved_unexpected_compact_group_count`, `unpreserved_unexpected_compact_group_count`, and `retention_preservation_complete` alongside unchanged `coverage_exact`.
- Invariant: `unexpected = preserved + unpreserved`; only the two exact BoltOdds historical classes can be preserved.

- [ ] **Step 1: Add failing static SQL-contract tests**

Add to `tests/test_retention_bounded_sql.py`:

```python
def test_chunk_sql_separates_strict_extras_from_retention_preservation():
    sql = bounded_sql.build_chunk_sql("boltodds", "2026-05-17", "2026-05-19").lower()
    for field in (
        "preserved_unexpected_compact_group_count",
        "unpreserved_unexpected_compact_group_count",
        "retention_preservation_complete",
    ):
        assert field in sql
    assert (
        "unexpected_compact_group_count = "
        "preserved_unexpected_compact_group_count + "
        "unpreserved_unexpected_compact_group_count"
    ) in " ".join(sql.split())
    assert "coverage_exact" in sql


def test_historical_extra_proof_is_boltodds_date_and_alias_bounded():
    sql = bounded_sql.build_chunk_sql("boltodds", "2026-05-17", "2026-05-19").lower()
    for required in (
        "date '2026-05-17'",
        "date '2026-05-18'",
        "'boltodds'",
        "'strikeouts'",
        "'pitcher_strikeouts'",
        "jsonb_typeof",
        "jsonb_array_elements_text",
        "observed_at asc, id asc",
    ):
        assert required in sql
    assert "historical_extra_candidates" in sql
    assert "canonical_actual_groups" in sql
    assert "historical_extra_proof" in sql


def test_historical_extra_proof_remains_select_only_and_aggregate_only():
    sql = bounded_sql.build_chunk_sql("boltodds", "2026-05-17", "2026-05-19")
    bounded_sql.assert_select_only(sql)
    final_select = sql.lower().rsplit("select jsonb_build_object", 1)[1]
    for forbidden in (
        "source_snapshot_ids", "snapshot_id", "player_name", "book_key",
        "source_payload", "authorization",
    ):
        assert forbidden not in final_select
```

- [ ] **Step 2: Run the SQL tests and verify RED**

Run:

```powershell
python -m pytest tests/test_retention_bounded_sql.py -q
```

Expected: new field/CTE assertions fail because the current query only reports total unexpected groups.

- [ ] **Step 3: Add bounded individual compact rows and candidate keys**

In `build_chunk_sql()`, introduce `bounded_compact_rows` before `compact_groups` using the existing raw index boundary:

```sql
bounded_compact_rows as (
  select
    cmlm.id, cmlm.slate_date, cmlm.provider, cmlm.book_key,
    cmlm.normalized_player_name, cmlm.market_key, cmlm.side,
    cmlm.line::numeric as line, cmlm.first_seen_at, cmlm.last_seen_at,
    cmlm.first_odds, cmlm.last_odds, cmlm.min_odds, cmlm.max_odds,
    cmlm.odds_move_count, cmlm.snapshot_count, cmlm.source_snapshot_ids
  from public.compact_market_line_movements cmlm
  where cmlm.slate_date between date '{start_literal}' and date '{end_literal}'
    and cmlm.provider = '{checked_provider}'
),
```

Build `compact_groups` from this CTE. Carry all seven canonical key columns through `joined_groups`; do not wrap the date/provider predicates.

- [ ] **Step 4: Add the exact historical candidate and source-resolution CTEs**

After `joined_groups`, add these units:

```sql
unexpected_compact_rows as (
  select compact.*
  from bounded_compact_rows compact
  where not exists (
    select 1 from raw_groups raw
    where raw.slate_date = compact.slate_date
      and raw.provider = compact.provider
      and raw.book_key = compact.book_key
      and raw.normalized_player_name = compact.normalized_player_name
      and raw.market_key = compact.market_key
      and raw.side = compact.side
      and raw.line = compact.line
  )
),
historical_extra_candidates as (
  select
    unexpected.*,
    case
      when unexpected.provider = 'boltodds'
       and unexpected.slate_date = date '2026-05-17'
       and unexpected.market_key = 'pitcher_strikeouts'
      then 'may17_alias'
      when unexpected.provider = 'boltodds'
       and unexpected.slate_date = date '2026-05-18'
      then 'may18_carryover'
      else null
    end as historical_class
  from unexpected_compact_rows unexpected
),
historical_extra_source_ids as (
  select
    candidate.id as compact_id,
    candidate.historical_class,
    candidate.slate_date as compact_slate_date,
    candidate.provider, candidate.book_key, candidate.normalized_player_name,
    candidate.market_key, candidate.side, candidate.line,
    source.value as source_id_text
  from historical_extra_candidates candidate
  cross join lateral jsonb_array_elements_text(
    case
      when jsonb_typeof(candidate.source_snapshot_ids) = 'array'
      then candidate.source_snapshot_ids
      else '[]'::jsonb
    end
  ) source(value)
  where candidate.historical_class is not null
),
```

Resolve IDs with an indexable UUID comparison. Guard the cast with the canonical UUID regex; malformed IDs remain unresolved rather than erroring:

```sql
left join public.market_snapshots source_snapshot
  on source_snapshot.id = case
    when source_id_text ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    then source_id_text::uuid
    else null
  end
left join public.market_provider_runs source_run
  on source_run.id = source_snapshot.run_id
```

The source-shape aggregate must count listed rows, distinct IDs, resolved IDs,
linked runs, and class-specific dimension/date matches per `compact_id`.

- [ ] **Step 5: Rebuild and compare canonical correct-date groups**

Add `canonical_actual_rows`, `windowed_canonical_actual`,
`canonical_actual_groups`, and `canonical_actual_compact` CTEs. Use the resolved
source run IDs and canonical group keys to fetch the full raw group, then apply:

```sql
window canonical_order as (
  partition by slate_date, provider, book_key, normalized_player_name,
               market_key, side, line
  order by observed_at asc, id asc
  rows between unbounded preceding and unbounded following
)
```

`canonical_actual_groups` must compute the same first/last/min/max/movement/
count metrics as `raw_groups` plus `array_agg(id::text order by observed_at, id)`.
`canonical_actual_compact` must require exactly one correct-date compact and
compare all metrics plus distinct source membership. Preserve an extra only
when every distinct listed source maps to an exact canonical group and every
class-specific count equals its expected total.

The final proof CTE has one row per unexpected `compact_id`:

```sql
historical_extra_proof as (
  select
    candidate.id as compact_id,
    coalesce(proof.all_source_shape_checks_pass, false)
      and coalesce(proof.all_canonical_groups_exact, false)
      and coalesce(proof.all_listed_sources_preserved, false)
      as preserved
  from historical_extra_candidates candidate
  left join historical_extra_proof_components proof
    on proof.compact_id = candidate.id
)
```

For `may17_alias`, require source market key `Strikeouts` and source run and
Phoenix observation dates in `{2026-05-16, 2026-05-17}`. For
`may18_carryover`, require exact market-key equality and source run and Phoenix
observation dates equal `2026-05-17`.

- [ ] **Step 6: Emit strict and preservation counts without redefining coverage**

Join the proof aggregate into `coverage_by_partition` and emit:

```sql
count(*) filter (
  where compact_present and not raw_present
)::bigint as unexpected_compact_group_count,
count(*) filter (
  where compact_present and not raw_present
    and coalesce(historical_extra_proof.preserved, false)
)::bigint as preserved_unexpected_compact_group_count,
count(*) filter (
  where compact_present and not raw_present
    and not coalesce(historical_extra_proof.preserved, false)
)::bigint as unpreserved_unexpected_compact_group_count,
```

Keep `coverage_exact` based on total unexpected groups. Add:

```sql
(
  coalesce(missing_compact_group_count, 0) = 0
  and coalesce(duplicate_compact_group_count, 0) = 0
  and coalesce(mismatched_group_count, 0) = 0
  and coalesce(unpreserved_unexpected_compact_group_count, 0) = 0
) as retention_preservation_complete
```

Also expose an SQL-side equation boolean or enforce the literal equation in a
downstream CTE so a contradictory row cannot report complete.

- [ ] **Step 7: Run Stage 2 SQL verification**

Run:

```powershell
python -m pytest tests/test_retention_bounded_sql.py -q
python -m py_compile scripts/retention_bounded_sql.py
git diff --check
```

Expected: tests pass, generated SQL remains one SELECT, and compilation/diff
checks exit `0`.

- [ ] **Step 8: Commit the SQL contract**

```powershell
git add -- scripts/retention_bounded_sql.py tests/test_retention_bounded_sql.py
git commit -m "feat: classify preserved historical compact extras"
```

---

### Task 3: Checkpoint and Envelope Validation

**Files:**
- Modify: `scripts/bounded_retention_audit.py:22-140,421-543,903-1039`
- Test: `tests/test_bounded_retention_audit.py`

**Interfaces:**
- Consumes: the extended version 2 chunk rows from Task 2.
- Produces: exact-field checkpoints/envelopes with runner version `3` and a fail-closed preservation equation.
- Invariant: assembly accepts `coverage_exact=False` only when `retention_preservation_complete=True`.

- [ ] **Step 1: Extend the valid fixture and add failing validator tests**

Update `valid_payload()` coverage defaults in
`tests/test_bounded_retention_audit.py`:

```python
"preserved_unexpected_compact_group_count": 0,
"unpreserved_unexpected_compact_group_count": 0,
"retention_preservation_complete": True,
```

Add:

```python
def test_validate_chunk_accepts_strict_extra_when_canonical_preservation_is_complete():
    chunk = audit.ChunkSpec("boltodds", date(2026, 5, 17), date(2026, 5, 17))
    payload = valid_payload(chunk)
    payload["coverage"][0].update({
        "compact_group_count": 2,
        "unexpected_compact_group_count": 1,
        "preserved_unexpected_compact_group_count": 1,
        "unpreserved_unexpected_compact_group_count": 0,
        "coverage_exact": False,
        "retention_preservation_complete": True,
    })
    audit.validate_chunk_payload(payload, chunk)


@pytest.mark.parametrize(
    "updates",
    [
        {"unexpected_compact_group_count": 1},
        {
            "unexpected_compact_group_count": 1,
            "preserved_unexpected_compact_group_count": 2,
        },
        {"unpreserved_unexpected_compact_group_count": 1},
        {"retention_preservation_complete": False},
    ],
)
def test_validate_chunk_rejects_preservation_equation_or_boolean_contradiction(updates):
    chunk = audit.ChunkSpec("boltodds", date(2026, 5, 17), date(2026, 5, 17))
    payload = valid_payload(chunk)
    payload["coverage"][0].update(updates)
    with pytest.raises(ValueError, match="preservation"):
        audit.validate_chunk_payload(payload, chunk)
```

Use fully consistent raw/compact equations in each parametrized case so the
expected failure is the preservation rule, not an earlier unrelated equation.

- [ ] **Step 2: Run the new validator slice and verify RED**

Run:

```powershell
python -m pytest tests/test_bounded_retention_audit.py -q -k "preservation_equation or strict_extra"
```

Expected: unknown-field or missing-field failures occur because the runner has
not adopted the new contract.

- [ ] **Step 3: Extend runner fields and recompute both booleans**

In `scripts/bounded_retention_audit.py`:

```python
RUNNER_VERSION = "3"

_COVERAGE_COUNTS = (
    "raw_snapshot_rows",
    "raw_logical_bytes",
    "raw_group_count",
    "compact_group_count",
    "exact_group_count",
    "mismatched_group_count",
    "missing_compact_group_count",
    "unexpected_compact_group_count",
    "preserved_unexpected_compact_group_count",
    "unpreserved_unexpected_compact_group_count",
    "duplicate_compact_group_count",
    "first_seen_mismatch_count",
    "last_seen_mismatch_count",
    "first_odds_mismatch_count",
    "last_odds_mismatch_count",
    "min_odds_mismatch_count",
    "max_odds_mismatch_count",
    "odds_move_count_mismatch_count",
    "snapshot_count_mismatch_count",
)

_COVERAGE_FIELDS = (
    "slate_date", "provider", *_COVERAGE_COUNTS,
    "first_raw_seen_at", "last_raw_seen_at", "coverage_exact",
    "retention_preservation_complete",
)
```

In `validate_chunk_payload()` enforce:

```python
if row["unexpected_compact_group_count"] != (
    row["preserved_unexpected_compact_group_count"]
    + row["unpreserved_unexpected_compact_group_count"]
):
    raise ValueError("unexpected compact preservation equation is inconsistent")

recomputed_exact = all(row[field] == 0 for field in (
    "mismatched_group_count", "missing_compact_group_count",
    "unexpected_compact_group_count", "duplicate_compact_group_count",
))
recomputed_preservation = all(row[field] == 0 for field in (
    "mismatched_group_count", "missing_compact_group_count",
    "unpreserved_unexpected_compact_group_count", "duplicate_compact_group_count",
))
```

Require both booleans to be actual `bool` values equal to their recomputed
values.

- [ ] **Step 4: Change final assembly to block on preservation completeness**

Replace the `coverage_exact=false blocks completeness` loop in
`aggregate_candidate_rows()` with:

```python
for row in coverage:
    if row["retention_preservation_complete"] is not True:
        raise ValueError(
            "retention_preservation_complete=false blocks completeness for "
            f"{row['provider']} {row['slate_date']}"
        )
```

Do not overwrite or drop `coverage_exact`; `_COVERAGE_FIELDS` carries strict
truth into the final envelope.

- [ ] **Step 5: Add assembly and stale-checkpoint regressions**

Replace the old test that expects any `coverage_exact=False` row to block with
two tests:

```python
def test_assembly_accepts_preserved_extra_with_strict_coverage_false():
    scope = audit.build_scope("2026-08-18")
    checkpoints = complete_checkpoints(scope)
    coverage = checkpoints[0].payload["coverage"][0]
    coverage.update({
        "compact_group_count": coverage["compact_group_count"] + 1,
        "unexpected_compact_group_count": 1,
        "preserved_unexpected_compact_group_count": 1,
        "unpreserved_unexpected_compact_group_count": 0,
        "coverage_exact": False,
        "retention_preservation_complete": True,
    })
    assembled = audit.aggregate_candidate_rows(checkpoints, scope)
    assert assembled[0][0]["coverage_exact"] is False
    assert assembled[0][0]["retention_preservation_complete"] is True


def test_assembly_rejects_unpreserved_extra():
    scope = audit.build_scope("2026-08-18")
    checkpoints = complete_checkpoints(scope)
    coverage = checkpoints[0].payload["coverage"][0]
    coverage.update({
        "compact_group_count": coverage["compact_group_count"] + 1,
        "unexpected_compact_group_count": 1,
        "preserved_unexpected_compact_group_count": 0,
        "unpreserved_unexpected_compact_group_count": 1,
        "coverage_exact": False,
        "retention_preservation_complete": False,
    })
    with pytest.raises(
        ValueError,
        match="retention_preservation_complete=false blocks completeness",
    ):
        audit.aggregate_candidate_rows(checkpoints, scope)
```

Add a checkpoint test that writes `runner_version="2"` and confirms
`load_valid_checkpoints()` rejects it before issuing any query.

- [ ] **Step 6: Run Stage 3 focused verification**

Run:

```powershell
python -m pytest tests/test_bounded_retention_audit.py tests/test_retention_bounded_sql.py -q
python -m py_compile scripts/bounded_retention_audit.py scripts/retention_bounded_sql.py
git diff --check
```

Expected: all tests pass and old/mixed checkpoints fail closed.

- [ ] **Step 7: Commit runner and envelope changes**

```powershell
git add -- scripts/bounded_retention_audit.py tests/test_bounded_retention_audit.py
git commit -m "feat: validate retained historical extra evidence"
```

---

### Task 4: Readiness and Retired-BoltOdds Reporting

**Files:**
- Modify: `scripts/build_season_retention_readiness.py:19-137,760-840,1170-1264,1414-1461,1600-1680`
- Test: `tests/test_build_season_retention_readiness.py`

**Interfaces:**
- Consumes: version 1 envelopes unchanged and extended version 2 envelopes from Task 3.
- Produces: readiness and closure reports that show strict extras and preserved extras, while only unpreserved extras block version 2 compaction readiness.
- Invariant: `ready_for_retention_review` remains evidence status only and never authorizes deletion.

- [ ] **Step 1: Extend version 2 fixtures and write failing decision tests**

Keep `_coverage()` unchanged because version 1 uses it. Add a
`_v2_coverage(**overrides)` helper that starts from `_coverage()`, inserts zero
preserved/unpreserved counts plus `retention_preservation_complete=True`, and
then applies overrides. Change only `_v2_envelope()` to call `_v2_coverage()`.
Then add this mutation helper and the decision tests:

```python
def _set_v2_unexpected_group(envelope, *, preserved):
    row = next(
        item for item in envelope["coverage"]
        if item["provider"] == "boltodds" and item["slate_date"] == "2026-04-28"
    )
    row.update({
        "compact_group_count": row["compact_group_count"] + 1,
        "unexpected_compact_group_count": 1,
        "preserved_unexpected_compact_group_count": int(preserved),
        "unpreserved_unexpected_compact_group_count": int(not preserved),
        "coverage_exact": False,
        "retention_preservation_complete": preserved,
    })
    return row


def test_v2_preserved_unexpected_group_is_visible_but_not_a_compaction_blocker():
    envelope = _v2_envelope()
    _set_v2_unexpected_group(envelope, preserved=True)
    report = retention.build_readiness_report(
        envelope=envelope,
        gate_c=_v2_gate_c_manifest(),
        season_evidence=_v2_season_evidence(),
        pins=_v2_pins(),
        as_of="2026-05-29",
        raw_retention_days=envelope["candidate_scope"]["raw_retention_days"],
    )
    partition = next(
        item for item in report["partitions"]
        if item["provider"] == "boltodds" and item["slate_date"] == "2026-04-28"
    )
    assert partition["unexpected_compact_group_count"] == 1
    assert partition["preserved_unexpected_compact_group_count"] == 1
    assert "unexpected_compact_group_count" not in partition["reason_codes"]
    assert "coverage_not_exact" not in partition["reason_codes"]


def test_v2_unpreserved_unexpected_group_blocks_compaction():
    envelope = _v2_envelope()
    _set_v2_unexpected_group(envelope, preserved=False)
    report = retention.build_readiness_report(
        envelope=envelope,
        gate_c=_v2_gate_c_manifest(),
        season_evidence=_v2_season_evidence(),
        pins=_v2_pins(),
        as_of="2026-05-29",
        raw_retention_days=envelope["candidate_scope"]["raw_retention_days"],
    )
    partition = next(
        item for item in report["partitions"]
        if item["provider"] == "boltodds" and item["slate_date"] == "2026-04-28"
    )
    assert partition["decision"] == "blocked_compaction"
    assert (
        "unpreserved_unexpected_compact_group_count"
        in partition["reason_codes"]
    )


def test_v2_boltodds_closure_keeps_preserved_extra_visible_without_blocking():
    envelope = _v2_envelope()
    _set_v2_unexpected_group(envelope, preserved=True)
    closure = retention.build_boltodds_closure(
        envelope=envelope,
        gate_c=_v2_gate_c_manifest(),
        season_evidence=_v2_season_evidence(),
        pins=_v2_pins(),
        as_of="2026-05-29",
    )
    partition = next(
        item for item in closure["partitions"]
        if item["slate_date"] == "2026-04-28"
    )
    assert closure["coverage_totals"]["unexpected_compact_group_count"] == 1
    assert closure["coverage_totals"]["preserved_unexpected_compact_group_count"] == 1
    assert partition["preserved_unexpected_compact_group_count"] == 1
    assert "compaction_not_preserved" not in closure["unresolved_evidence_gaps"]


def test_v2_boltodds_closure_blocks_unpreserved_extra():
    envelope = _v2_envelope()
    _set_v2_unexpected_group(envelope, preserved=False)
    closure = retention.build_boltodds_closure(
        envelope=envelope,
        gate_c=_v2_gate_c_manifest(),
        season_evidence=_v2_season_evidence(),
        pins=_v2_pins(),
        as_of="2026-05-29",
    )
    assert closure["status"] == "incomplete_evidence"
    assert "compaction_not_preserved" in closure["unresolved_evidence_gaps"]
    assert (
        "unpreserved_unexpected_compact_group_count"
        in closure["unresolved_evidence_gaps"]
    )
```

- [ ] **Step 2: Run the new reporter slice and verify RED**

Run:

```powershell
python -m pytest tests/test_build_season_retention_readiness.py -q -k "preserved_unexpected or unpreserved_unexpected"
```

Expected: exact-key validation rejects the fields or current reason logic
blocks on total unexpected/strict coverage.

- [ ] **Step 3: Extend exact version 2 validation**

Add the new integer fields to `_COVERAGE_INTEGER_FIELDS`, the boolean to
`_V2_COVERAGE_FIELDS`, and enforce:

```python
if row["unexpected_compact_group_count"] != (
    row["preserved_unexpected_compact_group_count"]
    + row["unpreserved_unexpected_compact_group_count"]
):
    raise ValueError("unexpected compact preservation equation is invalid")

expected_strict = not any(row[field] > 0 for field in (
    "missing_compact_group_count", "unexpected_compact_group_count",
    "duplicate_compact_group_count", "mismatched_group_count",
))
expected_preserved = not any(row[field] > 0 for field in (
    "missing_compact_group_count", "unpreserved_unexpected_compact_group_count",
    "duplicate_compact_group_count", "mismatched_group_count",
))
```

Reject either boolean when its type or value contradicts the recomputation.
Leave version 1 normalization and validation unchanged.

- [ ] **Step 4: Separate strict diagnostics from version 2 blockers**

In `_coverage_reason_codes()`:

```python
if audit_version == 2:
    blocking_fields = (
        "missing_compact_group_count",
        "unpreserved_unexpected_compact_group_count",
        "duplicate_compact_group_count",
        "first_seen_mismatch_count", "last_seen_mismatch_count",
        "first_odds_mismatch_count", "last_odds_mismatch_count",
        "min_odds_mismatch_count", "max_odds_mismatch_count",
        "odds_move_count_mismatch_count", "snapshot_count_mismatch_count",
    )
    reasons = [field for field in blocking_fields if row[field] > 0]
    if row["mismatched_group_count"] > 0:
        reasons.append("mismatched_group_count")
    if row["retention_preservation_complete"] is not True:
        reasons.append("retention_preservation_incomplete")
else:
    # Preserve the existing version 1 MISMATCH_FIELDS and coverage_not_exact logic.
```

Add total/preserved/unpreserved and both booleans to each version 2 partition
record. Do not put preserved totals in `reason_codes`.

- [ ] **Step 5: Update BoltOdds closure totals, gaps, and Markdown visibility**

Carry the new fields through `coverage_totals` and per-date closure partitions.
For version 2 replace:

```python
if any(row["coverage_exact"] is not True for row in coverage_rows):
    gaps.append("compaction_not_exact")
```

with:

```python
if any(row["retention_preservation_complete"] is not True for row in coverage_rows):
    gaps.append("compaction_not_preserved")
```

Do not append `unexpected_compact_group_count` to version 2 gaps. Append
`unpreserved_unexpected_compact_group_count` when positive. Version 1 retains
the existing gap logic.

In `render_boltodds_markdown()`, add this bullet immediately after the existing
missing/mismatched bullet, guarded so version 1 output does not access absent
version 2 fields:

```python
*([
    "- Strict unexpected / preserved / unpreserved groups: "
    f"`{totals['unexpected_compact_group_count']} / "
    f"{totals['preserved_unexpected_compact_group_count']} / "
    f"{totals['unpreserved_unexpected_compact_group_count']}`",
] if "preserved_unexpected_compact_group_count" in totals else []),
```

In `render_readiness_markdown()`, detect version 2 with
`has_preservation_fields = all("preserved_unexpected_compact_group_count" in row for row in report["partitions"])`.
When true, use this exact table header and row layout:

```text
| Slate | Provider | Raw rows | Raw MB | Exact / Raw groups | Missing | Mismatched | Unexpected | Preserved | Unpreserved | Decision | Reasons |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
```

Populate the three added cells from `unexpected_compact_group_count`,
`preserved_unexpected_compact_group_count`, and
`unpreserved_unexpected_compact_group_count`. When false, keep the existing
version 1 header and row format exactly.

- [ ] **Step 6: Run Stage 4 focused verification**

Run:

```powershell
python -m pytest tests/test_build_season_retention_readiness.py tests/test_bounded_retention_audit.py tests/test_retention_bounded_sql.py -q
python -m py_compile scripts/build_season_retention_readiness.py scripts/bounded_retention_audit.py scripts/retention_bounded_sql.py
git diff --check
```

Expected: version 2 preserved extras remain visible/nonblocking, unpreserved
extras block, version 1 tests pass, and compilation/diff checks are clean.

- [ ] **Step 7: Commit reporter changes**

```powershell
git add -- scripts/build_season_retention_readiness.py tests/test_build_season_retention_readiness.py
git commit -m "feat: report preserved compact extras separately"
```

---

### Task 5: Handoff Documentation and Exact-Commit Verification

**Files:**
- Modify: `docs/superpowers/specs/2026-08-20-retention-compaction-and-historical-extras-design.md`
- Modify: `docs/superpowers/plans/2026-08-18-bounded-retention-audit.md`
- Modify: `docs/current-state.md`
- Verify: all Stage 1-4 source and test files

**Interfaces:**
- Consumes: reviewed local commits from Tasks 1-4.
- Produces: a local-only implementation handoff with exact verification evidence and all live/deletion gates closed.

- [ ] **Step 1: Update the controlling documentation**

Set the design status to `Implemented locally; merge review pending`. Append a
dated section to `2026-08-18-bounded-retention-audit.md` containing:

- the deterministic `(observed_at, id)` and duplicate-ID rules;
- the new total/preserved/unpreserved equation;
- the fact that strict `coverage_exact` is unchanged;
- the separate `retention_preservation_complete` decision rule;
- the exact May 17-18 BoltOdds allowlist;
- the new runner/query hash and invalidation of old checkpoints;
- test counts and exact commit SHAs; and
- explicit confirmation that no live query, mutation, deletion, push, or
  deployment occurred.

Update the Four-Lane Tracking / data collection / history row in
`docs/current-state.md` with the same concise stage and next decision: local
merge review first, then a separately approved fresh bounded audit; deletion
remains closed.

- [ ] **Step 2: Run focused retention and compaction verification**

Run:

```powershell
python -m pytest tests/test_market_snapshot_compaction.py tests/test_compact_market_snapshots_script.py tests/test_retention_bounded_sql.py tests/test_bounded_retention_audit.py tests/test_build_season_retention_readiness.py -q
python -m py_compile market_infra/market_snapshot_compaction.py scripts/compact_market_snapshots.py scripts/retention_bounded_sql.py scripts/bounded_retention_audit.py scripts/build_season_retention_readiness.py
git diff --check
```

Expected: all focused tests pass, compilation exits `0`, and the diff check is
clean.

- [ ] **Step 3: Run the complete repository suite on the exact tree**

Run:

```powershell
python -m pytest tests -q
```

Expected: the complete suite passes. If it rewrites
`analytics/output/gate_f_preclose_clv_proxy_lab.md`, restore that file to the
exact committed blob `1ef07b8332e2f3dd040317592950e909b1e852ae` using
`apply_patch`, then verify its working-tree hash matches HEAD. Do not retain any
other generated output.

- [ ] **Step 4: Inspect the exact branch scope**

Run:

```powershell
git status --short --branch
git diff --check main...HEAD
git diff --name-status main...HEAD
git log --oneline main..HEAD
```

Expected: only the approved spec, plan, Stage 1-4 source/tests, controlling plan,
and current-state files differ. No migration, retirement script, backfill
script, generated output, secret, dashboard, or production configuration is
present.

- [ ] **Step 5: Commit the handoff docs**

```powershell
git add -- docs/superpowers/specs/2026-08-20-retention-compaction-and-historical-extras-design.md docs/superpowers/plans/2026-08-18-bounded-retention-audit.md docs/current-state.md
git commit -m "docs: record retention compaction hardening"
```

- [ ] **Step 6: Re-run post-commit verification and stop before integration**

Run:

```powershell
git show --check --stat HEAD
git status --short --branch
python -m pytest tests/test_market_snapshot_compaction.py tests/test_compact_market_snapshots_script.py tests/test_retention_bounded_sql.py tests/test_bounded_retention_audit.py tests/test_build_season_retention_readiness.py -q
```

Expected: the branch is clean, the focused suite passes on the exact commit, and
the handoff is ready for code review and a separate local-merge decision.

Do not merge, push, deploy, run a linked audit, activate retention, delete,
vacuum, or reclaim storage in this task.

## Post-merge May 18 carryover predicate correction — 2026-08-20

The reviewed implementation was merged and pushed on `main` at `f6550337`.
Tyler then separately approved bounded read-only matrix evidence. The fresh
runner-v3 May 17-19 checkpoint reproduced all `855` historical BoltOdds extras,
but its preservation decision accepted `220/220` May 17 extras and only
`25/635` May 18 extras. One separately approved aggregate-only diagnostic,
SHA-256 `1a52788c1dcaf17c6d09260ab944dbf5a1af611ee0f0657664fc166457cc003e`,
proved that the other `610` May 18 groups had valid source arrays, resolved
every listed source, linked every provider run, and failed only the historical
class-dimension predicate.

The live evidence and the earlier reviewed lineage proof isolate the false
negative: May 18 carryover compacts correctly link to May 17 provider runs, but
many source snapshots were observed on May 18 Phoenix time. The SQL required
both the run and observation date to be May 17. The narrow correction keeps the
May 17 run-date pin and every provider/book/player/market/side/line, source-ID,
canonical-compact, and listed-source-preservation check, while allowing the
source observation date to be May 17 or May 18.

Implementation is isolated on `codex/retention-may18-carryover-fix`. TDD proved
the new regression fails on the old one-day predicate and passes on the bounded
two-day predicate. Focused compaction/retention verification passed `424`
tests, the full repository suite passed `2,441` tests, Python compilation and
`git diff --check` passed, and the known generated Gate F report was restored
to its committed contents.
The generated query-contract SHA changes from
`748ebd215769b49bffeb255dd9a147349ba0939b47d75a885832d49271776a2a` to
`c95139e3822cbce108f6e6136fd0540e0a79e6623952b84915d473b4798ca310`,
so every old-hash checkpoint remains fail-closed. This code task authorizes no
linked re-read, merge, push, deployment, database mutation, repair,
reclassification, retention activation, deletion, vacuum, or reclamation.

## Local integration checkpoint — 2026-08-20

Tyler selected branch-finishing option 1. After confirming local `main` was
clean and current with `origin/main` at `f6550337`, the reviewed correction was
fast-forwarded into local `main` at `0bbc5957`. The complete merged repository
suite passed `2,441` tests. The known generated Gate F pre-close report was
restored to its exact committed blob after the suite ran.

This checkpoint is local integration only. It does not authorize a push,
deployment, linked Supabase audit, database mutation, retention execution,
deletion, vacuum, or storage reclamation. The next decisions remain separate:
publish local `main`, approve a new-hash linked read, finish the full matrix,
and only then review any bounded deletion proposal.

## Targeted chunk optimization after the 120-second stop — 2026-08-20

The May 18 carryover correction and its handoff are now published on `main` at
`2e5299aa`. One separately approved, read-only May 17-19 BoltOdds query under
query hash `c95139e3` reached the unchanged 120-second ceiling. It produced no
checkpoint, was not retried, and performed no database write, deletion,
vacuum, or reclamation.

Tyler then approved a code-only optimization phase. Commit `8c8d590f` on
`codex/retention-targeted-chunk-optimization` adds a separate `run-chunk`
command that requires an explicit provider, start date, end date, as-of date,
output directory, and linked-read acknowledgement. The requested range must
remain inside the fixed candidate scope, prior checkpoints must pass all
current runner/query/CLI/hash checks, and any same-provider overlap stops
before a query. The 120-second timeout and zero-retry behavior are unchanged.

The preservation proof now builds exact canonical source membership once and
joins on provider, book, player, market, side, line, slate date, and source
snapshot UUID. This is the same preservation rule without the repeated
per-source array scan that became expensive when the 610 May 18 carryover
groups qualified. The query-contract SHA is now
`e3091876ffe253d948c83e3e31c89f1a4fbde54381f91695f3963f2208866e05`,
so all earlier checkpoints remain fail-closed.

Test-first verification passed `431` focused retention/compaction tests and
`2,448` complete repository tests. Python compilation and `git diff --check`
passed, and independent read-only review found no remaining Critical or
Important issue. The known generated Gate F report was restored to its exact
committed blob. No post-optimization linked read, merge, push, deployment,
database mutation, retention activation, deletion, vacuum, or reclamation has
occurred. The next gate is local merge review; a new-hash linked read and any
deletion proposal remain separate approvals.

## Targeted optimization local integration checkpoint — 2026-08-20

Tyler selected branch-finishing option 1. After local `main` was verified clean
and current with `origin/main` at `2e5299aa`, the reviewed optimization branch
was fast-forwarded into local `main` at `ebef1f39`. The complete merged-tree
suite passed `2,448` tests, and the known generated Gate F report was restored
to its exact committed blob.

This is local integration only. No push, deployment, linked Supabase read,
database mutation, retention activation, deletion, vacuum, or reclamation has
occurred. Publishing local `main`, running one explicit new-hash chunk, and
reviewing any bounded deletion proposal remain separate decisions in that
order.
