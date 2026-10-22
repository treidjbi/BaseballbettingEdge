from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "scripts" / "supabase_retention_readiness.sql"


def test_retention_readiness_sql_exists_for_linked_cli_reads():
    assert SQL_PATH.exists()


def test_retention_readiness_sql_is_read_only():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()

    forbidden = [
        " insert ",
        " update ",
        " delete ",
        " truncate ",
        " drop ",
        " alter ",
        " create ",
        " grant ",
        " revoke ",
    ]
    assert not any(token in f" {sql} " for token in forbidden)


def test_retention_readiness_sql_reports_compact_coverage_and_size_fields():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()

    for expected in [
        "older_than_days",
        "cutoff_at",
        "raw_snapshot_rows",
        "estimated_raw_snapshot_bytes",
        "estimated_raw_snapshot_size",
        "coverage_exact",
        "sample_row_limit",
        "sampled_snapshot_rows",
        "sampled_snapshot_groups",
        "compact_covered_groups",
        "uncovered_snapshot_groups",
        "coverage_uncertain_rows",
        "sample_uncovered_groups",
        "eligible_for_execute",
        "retention_execution_closed",
        "approval_required_for_execute",
        "dry_run_only",
        "14",
        "30",
    ]:
        assert expected in sql


def test_retention_readiness_sql_documents_supabase_cli_command():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()

    assert "npx supabase db query --linked --file scripts\\supabase_retention_readiness.sql -o json" in sql


def test_retention_readiness_sql_uses_provider_observed_index_friendly_sampling():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()

    assert "target_providers(provider)" in sql
    assert "market_snapshots.provider = target_providers.provider" in sql
    assert "order by market_snapshots.observed_at desc" in sql
    assert "limit 5000" in sql
