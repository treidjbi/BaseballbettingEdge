from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "20260814175128_optimize_propline_webhook_inbox.sql"
)


def test_webhook_inbox_index_matches_live_partial_ordered_query():
    sql = " ".join(MIGRATION.read_text(encoding="utf-8").lower().split())

    assert (
        "create index concurrently if not exists "
        "idx_propline_webhook_deliveries_unprocessed_received_at "
        "on public.propline_webhook_deliveries (received_at asc) "
        "where processed is false"
    ) in sql
