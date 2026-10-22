import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SQL_PATH = ROOT / "scripts" / "supabase_prepared_market_snapshot_deletion_preview.sql"


def _scrub_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", " ", sql)


def test_preview_is_one_select_only_statement():
    sql = SQL_PATH.read_text(encoding="utf-8")
    scrubbed = _scrub_comments(sql).lower()

    assert scrubbed.lstrip().startswith("with ")
    assert sql.count(";") == 1
    assert sql.rstrip().endswith(";")
    for forbidden in (
        " insert ", " update ", " delete ", " truncate ", " drop ",
        " alter ", " create ", " grant ", " revoke ", " vacuum ",
        " reindex ", " merge ", " call ", " copy ", " do ",
    ):
        assert forbidden not in f" {scrubbed} "


def test_preview_has_only_the_reviewed_active_provider_dates():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()

    for start_date, end_date in (
        ("2026-06-12", "2026-06-30"),
        ("2026-07-02", "2026-07-12"),
        ("2026-07-16", "2026-07-26"),
    ):
        assert f"date '{start_date}'" in sql
        assert f"date '{end_date}'" in sql

    assert "mpr.provider in ('propline', 'therundown')" in sql
    assert "ms.provider = mpr.provider" in sql
    assert "cmlm.provider in ('propline', 'therundown')" in sql
    assert "current_date" not in sql
    assert "now()" not in sql
    assert "older_than" not in sql


def test_preview_reports_review_fields_without_raw_payloads():
    sql = SQL_PATH.read_text(encoding="utf-8").lower()

    for required in (
        "raw_snapshot_rows",
        "raw_logical_bytes",
        "compact_groups",
        "represented_snapshot_rows",
        "first_snapshot_at",
        "last_snapshot_at",
        "latest_compact_update",
        "representation_count_matches",
        "retention_execution_closed",
        "deletion_approved",
        "prepared_active_provider_scope_v1",
    ):
        assert required in sql

    for prohibited_payload in (
        "source_payload",
        "raw_payload",
        "request_payload",
        "response_payload",
    ):
        assert prohibited_payload not in sql
