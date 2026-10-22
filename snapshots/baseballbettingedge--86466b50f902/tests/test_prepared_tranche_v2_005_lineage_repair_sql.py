from pathlib import Path
import re

from scripts.retention_bounded_sql import assert_select_only


ROOT = Path(__file__).resolve().parent.parent
PREVIEW = ROOT / "scripts/supabase_prepared_tranche_v2_005_lineage_repair_preview.sql"
REPAIR = ROOT / "scripts/supabase_prepared_tranche_v2_005_lineage_repair.sql"
POSTCHECK = ROOT / "scripts/supabase_prepared_tranche_v2_005_lineage_repair_postcheck.sql"


def _normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").lower().split())


def test_preview_and_postcheck_are_select_only():
    assert_select_only(PREVIEW.read_text(encoding="utf-8"))
    assert_select_only(POSTCHECK.read_text(encoding="utf-8"))


def test_repair_is_one_bounded_compact_upsert_and_never_mutates_raw_rows():
    sql = REPAIR.read_text(encoding="utf-8")
    normalized = _normalized(REPAIR)

    assert sql.count(";") == 1
    assert normalized.startswith("-- one-shot")
    assert normalized.count("insert into public.compact_market_line_movements") == 1
    assert "on conflict ( slate_date, provider, book_key," in normalized
    assert "from rebuilt cross join execution_gate" in normalized
    assert "where execution_gate.source_state_matches" in normalized
    assert normalized.count("do update set") == 1
    assert "upserted_groups" in normalized
    assert "raw_rows_updated', 0" in normalized
    assert "raw_rows_deleted', 0" in normalized
    assert not re.search(
        r"\b(delete|truncate|drop|alter|create|grant|revoke|vacuum|reindex|merge|call|copy)\b",
        re.sub(r"--[^\n]*", " ", sql),
        re.IGNORECASE,
    )
    assert "insert into public.market_snapshots" not in normalized
    assert "update public.market_snapshots" not in normalized


def test_repair_binds_the_approved_partition_timestamp_counts_and_hashes():
    normalized = _normalized(REPAIR)

    for value in (
        "mpr.slate_date = date '2026-07-15'",
        "ms.observed_at = timestamptz '2026-07-16t13:10:41.076339z'",
        "late_source_rows = 17",
        "unpreserved_late_source_rows = 17",
        "affected_group_count = 17",
        "source_rows_in_affected_groups = 1323",
        "old_represented_rows = 1306",
        "rebuilt_represented_rows = 1323",
        "missing_existing_groups = 0",
        "existing_group_count = 17",
        "435501093251177170e5def7f3d8bfde5085c35b67d265cd184c79a9aa4988c9",
        "debd07cfce0c8ab203dbc590f75c0582ba18675750c76861cca16b124c3863be",
        "95d756156996d9b732f106f12e0c90dfd603de074597ad0f45ace87aecc418a3",
    ):
        assert value in normalized


def test_postcheck_requires_all_seventeen_rows_and_groups_to_be_exact():
    normalized = _normalized(POSTCHECK)

    for value in (
        "late_source_rows = 17",
        "preserved_late_source_rows = 17",
        "affected_group_count = 17",
        "source_rows_in_affected_groups = 1323",
        "existing_group_count = 17",
        "current_represented_rows = 1323",
        "mismatched_groups = 0",
        "current_rows_sha256 = rebuilt_rows_sha256",
    ):
        assert value in normalized
