from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SQL_PATH = ROOT / "scripts" / "supabase_strict_provider_readiness.sql"


def test_strict_provider_readiness_sql_exists_for_linked_cli_reads():
    assert SQL_PATH.exists()


def test_strict_provider_readiness_sql_is_read_only():
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


def test_strict_provider_readiness_sql_covers_artifact_provider_and_lock_evidence():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()

    for expected in [
        "published_pipeline_artifacts",
        "official_market_lines",
        "current_market_lines",
        "provider_coverage_audits",
        "market_provider_runs",
        "market_feed_heartbeats",
        "provider_request_usage_daily",
        "operational_pick_locks",
        "notification_events",
        "live_market_display_state",
        "propline_webhook_deliveries",
        "strict_provider_readiness",
        "readiness_status",
        "blocking_reasons",
        "watch_reasons",
        "official_line_summary",
        "latest_coverage_audits",
        "latest_heartbeats",
    ]:
        assert expected in sql


def test_strict_provider_readiness_sql_documents_supabase_cli_command():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()

    assert "npx supabase db query --linked --file scripts\\supabase_strict_provider_readiness.sql -o json" in sql
