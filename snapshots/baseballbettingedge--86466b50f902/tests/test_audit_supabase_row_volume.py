import re
from pathlib import Path

from scripts import audit_supabase_row_volume

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT / "supabase" / "migrations"


class FakeWriter:
    def __init__(self):
        self.count_calls = []
        self.delete_calls = []

    def count_rows(self, table, params=None):
        self.count_calls.append((table, params))
        return {
            "market_snapshots": 42,
            "operational_pick_locks": 3,
        }.get(table, 0)

    def delete_rows(self, table, params):
        self.delete_calls.append((table, params))
        raise AssertionError("row-volume audit must be read-only")


def test_run_counts_operational_tables_read_only():
    writer = FakeWriter()

    rows = audit_supabase_row_volume.run(writer)

    assert [row["table"] for row in rows] == audit_supabase_row_volume.TABLES
    assert {"table": "market_snapshots", "rows": 42} in rows
    assert {"table": "operational_pick_locks", "rows": 3} in rows
    assert all(params == {} for _, params in writer.count_calls)
    assert writer.delete_calls == []


def test_audit_tables_exist_in_supabase_migrations():
    sql = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(MIGRATIONS_DIR.glob("*.sql"))
    )
    migrated_tables = {
        match.group(1)
        for match in re.finditer(
            r"create\s+table\s+if\s+not\s+exists\s+(?:public\.)?([a-z_]+)",
            sql,
            flags=re.IGNORECASE,
        )
    }

    assert "line_movement_events" in audit_supabase_row_volume.TABLES
    assert "shadow_provider_movement_events" not in audit_supabase_row_volume.TABLES
    assert set(audit_supabase_row_volume.TABLES).issubset(migrated_tables)


def test_cli_prints_row_volume_lines(monkeypatch, capsys):
    writer = FakeWriter()
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret-key")
    monkeypatch.setattr(audit_supabase_row_volume, "SupabaseMarketWriter", lambda url, key: writer)

    assert audit_supabase_row_volume.main([]) == 0

    output = capsys.readouterr().out
    assert "row_volume table=market_snapshots rows=42" in output
    assert "row_volume table=operational_pick_locks rows=3" in output
    assert writer.delete_calls == []
