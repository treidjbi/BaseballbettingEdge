from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "scripts" / "supabase_row_volume_guardrail.sql"


def test_row_volume_guardrail_sql_exists_for_cli_reads():
    assert SQL_PATH.exists()


def test_row_volume_guardrail_sql_is_read_only_and_covers_operational_tables():
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

    for table in [
        "market_snapshots",
        "market_feed_heartbeats",
        "operational_pick_locks",
        "line_movement_events",
        "current_market_lines",
        "official_market_lines",
        "provider_request_usage_daily",
        "compact_market_line_movements",
        "shadow_pipeline_runs",
        "shadow_pick_lock_observations",
        "notification_events",
        "live_market_display_state",
        "market_pick_evidence",
        "propline_webhook_deliveries",
        "published_pipeline_artifacts",
        "market_provider_runs",
        "provider_coverage_audits",
    ]:
        assert table in sql


def test_row_volume_guardrail_sql_reports_retention_and_provider_readiness_fields():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()

    for expected in [
        "database_bytes",
        "pct_of_pro_included_8gb",
        "raw_rows_older_14d",
        "raw_rows_older_30d",
        "oldest_observed_at",
        "newest_observed_at",
        "ready_for_pipeline",
        "latest_provider_audits",
        "latest_heartbeats",
    ]:
        assert expected in sql
