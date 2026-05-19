import pytest

from scripts import retire_market_snapshots


class FakeWriter:
    def __init__(
        self,
        *,
        snapshot_count=10,
        compact_count=2,
        deleted_count=7,
        snapshot_groups=None,
        run_rows=None,
        compact_groups=None,
    ):
        self.snapshot_count = snapshot_count
        self.compact_count = compact_count
        self.deleted_count = deleted_count
        self.snapshot_groups = (
            snapshot_groups
            if snapshot_groups is not None
            else [{"run_id": "run-1", "provider": "boltodds"}]
        )
        self.run_rows = (
            run_rows
            if run_rows is not None
            else [{"id": "run-1", "slate_date": "2026-04-30", "provider": "boltodds"}]
        )
        self.compact_groups = compact_groups if compact_groups is not None else {("2026-04-30", "boltodds")}
        self.count_calls = []
        self.select_calls = []
        self.delete_calls = []

    def count_rows(self, table, params=None):
        self.count_calls.append((table, params))
        if table == "market_snapshots":
            return self.snapshot_count
        if table == "compact_market_line_movements":
            return self.compact_count
        raise AssertionError(f"unexpected table {table}")

    def select_rows(self, table, params):
        self.select_calls.append((table, params))
        if table == "market_snapshots":
            return list(self.snapshot_groups)
        if table == "market_provider_runs":
            requested = str(params["id"]).removeprefix("in.(").removesuffix(")").split(",")
            return [row for row in self.run_rows if row["id"] in requested]
        if table == "compact_market_line_movements":
            slate_date = str(params["slate_date"]).replace("eq.", "", 1)
            provider = str(params["provider"]).replace("eq.", "", 1)
            if (slate_date, provider) in self.compact_groups:
                return [{"slate_date": slate_date, "provider": provider, "last_seen_at": "2026-05-01T00:00:00+00:00"}]
            return []
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
    assert result["uncovered_snapshot_groups"] == []
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
    writer = FakeWriter(snapshot_count=10, compact_count=0, compact_groups=set())
    monkeypatch.setenv("ALLOW_MARKET_SNAPSHOT_DELETE", "true")

    result = retire_market_snapshots.run(
        writer=writer,
        cutoff_iso="2026-05-01T00:00:00+00:00",
        execute=True,
    )

    assert result["eligible_to_delete"] is False
    assert result["deleted_rows"] == 0
    assert writer.delete_calls == []


def test_unrelated_compact_rows_do_not_allow_snapshot_deletion(monkeypatch):
    writer = FakeWriter(
        snapshot_count=10,
        compact_count=3,
        snapshot_groups=[{"run_id": "run-1", "provider": "boltodds"}],
        run_rows=[{"id": "run-1", "slate_date": "2026-04-30", "provider": "boltodds"}],
        compact_groups={("2026-04-29", "propline")},
    )
    monkeypatch.setenv("ALLOW_MARKET_SNAPSHOT_DELETE", "true")

    result = retire_market_snapshots.run(
        writer=writer,
        cutoff_iso="2026-05-01T00:00:00+00:00",
        execute=True,
    )

    assert result["eligible_to_delete"] is False
    assert result["uncovered_snapshot_groups"] == [{"slate_date": "2026-04-30", "provider": "boltodds"}]
    assert result["deleted_rows"] == 0
    assert writer.delete_calls == []
    assert ("compact_market_line_movements", {
        "slate_date": "eq.2026-04-30",
        "provider": "eq.boltodds",
        "last_seen_at": "lte.2026-05-01T00:00:00+00:00",
        "select": "slate_date,provider,last_seen_at",
        "limit": "1",
    }) in writer.select_calls
