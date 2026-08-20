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
    assert lowered.count("order by observed_at asc, id asc") == 2
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
    assert (
        "coalesce(coverage_by_partition.preservation_equation_exact, true)"
        in " ".join(sql.split())
    )
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

    source_ids_sql = " ".join(sql.split("historical_extra_source_ids as (", 1)[1].split(
        "historical_extra_distinct_source_ids as (", 1
    )[0].split())
    assert "when candidate.historical_class is not null and jsonb_typeof(candidate.source_snapshot_ids) = 'array'" in source_ids_sql
    assert "where candidate.historical_class is not null" in source_ids_sql

    candidate_sql = " ".join(sql.split("historical_extra_candidates as (", 1)[1].split(
        "historical_extra_source_ids as (", 1
    )[0].split())
    assert "unexpected.provider = 'boltodds' and unexpected.slate_date = date '2026-05-17' and unexpected.market_key = 'pitcher_strikeouts' then 'may17_alias'" in candidate_sql
    assert "unexpected.provider = 'boltodds' and unexpected.slate_date = date '2026-05-18' then 'may18_carryover' else null" in candidate_sql

    source_proof_sql = " ".join(sql.split("historical_extra_resolved_sources as (", 1)[1].split(
        "historical_extra_listed_counts as (", 1
    )[0].split())
    assert "candidate.historical_class = 'may17_alias' and source_snapshot.market_key = 'strikeouts'" in source_proof_sql
    assert "source_run.slate_date in (date '2026-05-16', date '2026-05-17')" in source_proof_sql
    assert "candidate.historical_class = 'may18_carryover' and source_snapshot.market_key = candidate.market_key" in source_proof_sql
    assert "source_run.slate_date = date '2026-05-17'" in source_proof_sql


def test_historical_extra_proof_remains_select_only_and_aggregate_only():
    sql = bounded_sql.build_chunk_sql("boltodds", "2026-05-17", "2026-05-19")
    bounded_sql.assert_select_only(sql)
    final_select = sql.lower().rsplit("select jsonb_build_object", 1)[1]
    for forbidden in (
        "source_snapshot_ids", "snapshot_id", "player_name", "book_key",
        "source_payload", "authorization", "compact_id", "source_id_text",
        "historical_class", "preservation_equation_exact",
    ):
        assert forbidden not in final_select


def test_historical_extra_proof_fails_closed_on_all_nine_requirements():
    sql = bounded_sql.build_chunk_sql("boltodds", "2026-05-17", "2026-05-19").lower()
    proof_sql = sql.split("historical_extra_source_shape as (", 1)[1].split(
        "historical_extra_proof as (", 1
    )[0]
    normalized_proof = " ".join(proof_sql.split())

    for required in (
        "source_ids_json_array",
        "listed_source_count > 0",
        "distinct_listed_source_count",
        "resolved_source_count",
        "linked_run_count",
        "class_dimension_match_count",
        "coalesce(canonical_summary.canonical_group_count, 0) > 0",
        "canonical_compact_count",
        "exact_canonical_group_count",
        "listed_source_preserved_count",
    ):
        assert required in normalized_proof
    assert "candidate.historical_class is not null" in sql


def test_historical_extra_source_resolution_keeps_index_driving_predicates_raw():
    sql = bounded_sql.build_chunk_sql("boltodds", "2026-05-17", "2026-05-19").lower()
    normalized_sql = " ".join(sql.split())
    assert "source_snapshot.id = case" in normalized_sql
    assert "source_run.id = source_snapshot.run_id" in normalized_sql
    assert "source_snapshot.provider = candidate.provider" in normalized_sql
    assert "source_run.provider = candidate.provider" in normalized_sql
    assert "canonical_compact.slate_date = canonical_group.slate_date" in normalized_sql
    assert "canonical_compact.provider = canonical_group.provider" in normalized_sql
    assert "canonical_compact.book_key = canonical_group.book_key" in normalized_sql
    assert "canonical_compact.normalized_player_name = canonical_group.normalized_player_name" in normalized_sql
    assert "canonical_compact.market_key = canonical_group.market_key" in normalized_sql
    assert "canonical_compact.side = canonical_group.side" in normalized_sql
    assert "canonical_compact.line = canonical_group.line" in normalized_sql


def test_canonical_actual_rows_reuse_raw_group_normalization_and_validity():
    sql = bounded_sql.build_chunk_sql("boltodds", "2026-05-17", "2026-05-19").lower()
    canonical_sql = " ".join(sql.split("canonical_actual_rows as (", 1)[1].split(
        "windowed_canonical_actual as (", 1
    )[0].split())
    assert "coalesce(nullif(trim(canonical_snapshot.market_key), ''), 'pitcher_strikeouts') = canonical_key.market_key" in canonical_sql
    assert "nullif(trim(canonical_snapshot.bookmaker_key), '') is not null" in canonical_sql
    assert "nullif(trim(canonical_snapshot.normalized_player_name), '') is not null" in canonical_sql
    assert "lower(trim(canonical_snapshot.side)) in ('over', 'under')" in canonical_sql


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
