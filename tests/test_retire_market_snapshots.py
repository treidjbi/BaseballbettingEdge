import pytest

from scripts import retire_market_snapshots


class FakeWriter:
    def __init__(self, *, snapshot_count=10, compact_count=2, deleted_count=7):
        self.snapshot_count = snapshot_count
        self.compact_count = compact_count
        self.deleted_count = deleted_count
        self.count_calls = []
        self.delete_calls = []

    def count_rows(self, table, params=None):
        self.count_calls.append((table, params))
        if table == "market_snapshots":
            return self.snapshot_count
        if table == "compact_market_line_movements":
            return self.compact_count
        raise AssertionError(f"unexpected table {table}")

    def delete_rows(self, table, params):
        self.delete_calls.append((table, params))
        return self.deleted_count


def test_dry_run_never_deletes():
    writer = FakeWriter()

    result = retire_market_snapshots.run(
        writer=writer,
        cutoff_iso="2026-05-01T00:00:00+00:00",
        execute=False,
    )

    assert result["snapshot_rows_before_cutoff"] == 10
    assert result["compact_rows_before_cutoff"] == 2
    assert result["eligible_to_delete"] is True
    assert result["deleted_rows"] == 0
    assert result["execute"] is False
    assert writer.delete_calls == []


def test_execute_requires_delete_environment_flag(monkeypatch):
    writer = FakeWriter()
    monkeypatch.delenv("ALLOW_MARKET_SNAPSHOT_DELETE", raising=False)

    with pytest.raises(RuntimeError, match="ALLOW_MARKET_SNAPSHOT_DELETE=true"):
        retire_market_snapshots.run(
            writer=writer,
            cutoff_iso="2026-05-01T00:00:00+00:00",
            execute=True,
        )

    assert writer.delete_calls == []


def test_execute_with_compact_rows_and_allow_env_deletes(monkeypatch):
    writer = FakeWriter(deleted_count=7)
    monkeypatch.setenv("ALLOW_MARKET_SNAPSHOT_DELETE", "true")

    result = retire_market_snapshots.run(
        writer=writer,
        cutoff_iso="2026-05-01T00:00:00+00:00",
        execute=True,
    )

    assert result["deleted_rows"] == 7
    assert writer.delete_calls == [
        ("market_snapshots", {"observed_at": "lt.2026-05-01T00:00:00+00:00"})
    ]


def test_zero_compact_rows_blocks_deletion(monkeypatch):
    writer = FakeWriter(snapshot_count=10, compact_count=0)
    monkeypatch.setenv("ALLOW_MARKET_SNAPSHOT_DELETE", "true")

    result = retire_market_snapshots.run(
        writer=writer,
        cutoff_iso="2026-05-01T00:00:00+00:00",
        execute=True,
    )

    assert result["eligible_to_delete"] is False
    assert result["deleted_rows"] == 0
    assert writer.delete_calls == []
