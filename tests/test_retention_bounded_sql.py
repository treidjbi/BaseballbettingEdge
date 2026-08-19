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


@pytest.mark.parametrize("value", ["2026-5-01", "2026-02-30", 20260501, ""])
def test_parse_iso_date_rejects_noncanonical_or_impossible_dates(value):
    with pytest.raises(ValueError, match="as_of_date must be an ISO date"):
        bounded_sql.parse_iso_date(value, "as_of_date")


@pytest.mark.parametrize(
    ("start_date", "end_date", "message"),
    [
        ("2026-04-27", "2026-04-27", "before the clean regime"),
        ("2026-05-02", "2026-05-01", "on or before"),
        ("2026-05-01", "2026-05-08", "at most seven"),
    ],
)
def test_validate_chunk_rejects_out_of_contract_date_ranges(start_date, end_date, message):
    with pytest.raises(ValueError, match=message):
        bounded_sql.validate_chunk("therundown", start_date, end_date)


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
        "slate_date_mismatch_rows", "preserved_slate_date_mismatch_rows",
        "unpreserved_slate_date_mismatch_rows", "unknown_provider_rows",
        "candidate_runtime", "retention_bounded_chunk",
    ):
        assert field in sql


def test_chunk_sql_requires_source_id_and_time_bounds_for_preserved_cross_date_lineage():
    sql = bounded_sql.build_chunk_sql("boltodds", "2026-06-11", "2026-06-11").lower()
    lineage_sql = sql.split("bounded_observed_lineage as (", 1)[1].split(
        "bounded_run_source as (", 1
    )[0]

    assert "cmlm.slate_date = bounded_observed_source.run_slate_date" in sql
    assert "cmlm.provider = lower(trim(bounded_observed_source.run_provider))" in sql
    assert "cmlm.book_key = lower(trim(bounded_observed_source.bookmaker_key))" in sql
    assert (
        "cmlm.normalized_player_name = "
        "trim(bounded_observed_source.normalized_player_name)"
    ) in sql
    assert "lower(trim(cmlm.provider))" not in lineage_sql
    assert "lower(trim(cmlm.book_key))" not in lineage_sql
    assert "trim(cmlm.normalized_player_name)" not in lineage_sql
    assert "jsonb_typeof(cmlm.source_snapshot_ids) = 'array'" in sql
    assert "cmlm.source_snapshot_ids ? bounded_observed_source.snapshot_id::text" in sql
    assert (
        "bounded_observed_source.observed_at between cmlm.first_seen_at "
        "and cmlm.last_seen_at"
    ) in sql


def test_assert_select_only_rejects_multiple_statements_and_mutations():
    with pytest.raises(ValueError, match="exactly one statement"):
        bounded_sql.assert_select_only("select 1; select 2;")
    with pytest.raises(ValueError, match="prohibited token: delete"):
        bounded_sql.assert_select_only("with x as (delete from x returning 1) select 1;")


def test_runtime_boundary_sql_uses_actual_run_boundary_for_old_slate_post_suspension_activity():
    sql = bounded_sql.build_runtime_boundary_sql("2026-07-19").lower()
    assert sql.count("max(coalesce(mpr.completed_at, mpr.started_at))") == 2
    assert "order by mpr.slate_date desc, mpr.started_at desc, mpr.id desc limit 1" not in sql


def test_runtime_boundary_sql_uses_index_bounded_snapshot_and_heartbeat_scans():
    sql = bounded_sql.build_runtime_boundary_sql("2026-07-19").lower()
    assert sql.count("order by ms.observed_at desc, ms.id desc limit 1") == 2
    assert sql.count("order by h.observed_at desc, h.id desc limit 1") == 2
    assert "ms.observed_at >= settings.candidate_observed_start" in sql
    assert "ms.observed_at < settings.candidate_observed_end" in sql
    assert "h.observed_at >= settings.candidate_observed_start" in sql
    assert "h.observed_at < settings.candidate_observed_end" in sql
    assert "from public.market_provider_runs mpr\n    join public.market_snapshots ms" not in sql


def test_runtime_boundary_sql_uses_aggregate_message_maxima_without_unindexed_sorts():
    sql = bounded_sql.build_runtime_boundary_sql("2026-07-19").lower()
    assert sql.count("max(h.last_message_at)") == 2
    assert "order by h.last_message_at" not in sql


def test_runtime_boundary_sql_is_narrow_select_only_with_boltodds_closure_check():
    sql = bounded_sql.build_runtime_boundary_sql("2026-07-19")
    lowered = f" {sql.lower()} "
    assert sql.rstrip().endswith(";")
    assert sql.count(";") == 1
    assert not any(token in lowered for token in FORBIDDEN)
    assert "order by ms.observed_at desc, ms.id desc limit 1" in lowered
    assert "order by h.observed_at desc, h.id desc limit 1" in lowered
    assert "post_boltodds_suspension" in lowered
    assert "retention_runtime_boundary" in lowered


def test_query_contract_hash_is_stable_lowercase_sha256():
    digest = bounded_sql.query_contract_sha256()
    assert len(digest) == 64
    assert digest == digest.lower()
    assert int(digest, 16) >= 0
