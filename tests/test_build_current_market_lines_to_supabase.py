from scripts.build_current_market_lines_to_supabase import _fetch_inputs


class FakeWriter:
    def __init__(self):
        self.calls = []

    def select_rows(self, table, params):
        self.calls.append((table, dict(params)))
        if table == "market_provider_runs":
            return [{"id": "run-1", "provider": "boltodds", "slate_date": "2026-05-13"}]
        if table == "market_snapshots" and params["offset"] == "0":
            return [{"id": "snap-1"}]
        return []


def test_fetch_inputs_pages_market_snapshots_without_market_key_filter():
    writer = FakeWriter()

    snapshot_rows, run_rows = _fetch_inputs(writer, "2026-05-13")

    assert run_rows == [{"id": "run-1", "provider": "boltodds", "slate_date": "2026-05-13"}]
    assert snapshot_rows == [{"id": "snap-1"}]
    snapshot_call = writer.calls[1]
    assert snapshot_call[0] == "market_snapshots"
    assert snapshot_call[1]["run_id"] == "in.(run-1)"
    assert snapshot_call[1]["limit"] == "10000"
    assert snapshot_call[1]["offset"] == "0"
    assert "market_key" not in snapshot_call[1]
