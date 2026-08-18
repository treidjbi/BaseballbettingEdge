from __future__ import annotations

import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "scripts" / "supabase_retention_exact_coverage.sql"
REPORTER_PATH = ROOT / "scripts" / "build_season_retention_readiness.py"


def test_exact_coverage_sql_exists_and_is_read_only():
    assert SQL_PATH.exists()
    sql = SQL_PATH.read_text(encoding="utf-8").lower()
    forbidden = (
        " insert ", " update ", " delete ", " truncate ", " drop ",
        " alter ", " create ", " grant ", " revoke ", " vacuum ",
    )
    assert not any(token in f" {sql} " for token in forbidden)
    assert "retention_execution_closed" in sql
    assert "deletion_approved" in sql


def test_exact_coverage_sql_uses_the_canonical_group_and_ordering_contract():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()
    for field in (
        "slate_date", "provider", "book_key", "normalized_player_name",
        "market_key", "side", "line",
    ):
        assert field in sql
    assert "order by observed_at asc, id asc" in sql
    assert "order by observed_at desc, id desc" in sql
    assert "lag(american_odds)" in sql
    assert "pg_column_size" in sql


def test_exact_coverage_sql_emits_all_blocking_metrics_and_runtime_boundaries():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()
    expected = (
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
        "first_run_at", "last_run_at", "failed_run_count", "books_seen",
        "first_snapshot_at", "last_snapshot_at", "last_heartbeat_at",
        "last_message_at", "heartbeat_count",
    )
    for field in expected:
        assert field in sql


def test_exact_coverage_sql_documents_one_linked_cli_read():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()
    assert (
        "npx supabase db query --linked --file "
        "scripts\\supabase_retention_exact_coverage.sql -o json"
    ) in sql
