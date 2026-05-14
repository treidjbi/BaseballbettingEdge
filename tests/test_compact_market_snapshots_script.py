from scripts import compact_market_snapshots


class FakeWriter:
    def __init__(self):
        self.selects = []
        self.upserts = []

    def select_rows(self, table, params):
        self.selects.append((table, dict(params)))
        if table == "market_provider_runs":
            return [{"id": "run-1", "provider": "boltodds", "slate_date": "2026-05-14"}]
        if table == "market_snapshots" and params["offset"] == "0":
            return [
                {
                    "id": "snap-1",
                    "run_id": "run-1",
                    "provider": "boltodds",
                    "bookmaker_key": "fanduel",
                    "player_name": "Example Pitcher",
                    "normalized_player_name": "example pitcher",
                    "market_key": "pitcher_strikeouts",
                    "side": "over",
                    "line": 5.5,
                    "american_odds": -110,
                    "observed_at": "2026-05-14T18:00:00Z",
                },
                {
                    "id": "snap-2",
                    "run_id": "run-1",
                    "provider": "boltodds",
                    "bookmaker_key": "fanduel",
                    "player_name": "Example Pitcher",
                    "normalized_player_name": "example pitcher",
                    "market_key": "pitcher_strikeouts",
                    "side": "over",
                    "line": 5.5,
                    "american_odds": -125,
                    "observed_at": "2026-05-14T18:05:00Z",
                },
            ]
        return []

    def upsert_rows(self, table, rows, on_conflict):
        self.upserts.append((table, rows, on_conflict))
        return rows


def test_compact_script_fetches_run_snapshots_and_upserts_compact_rows():
    writer = FakeWriter()

    result = compact_market_snapshots.run(
        slate_date="2026-05-14",
        writer=writer,
        dry_run=False,
    )

    assert result["snapshot_rows"] == 2
    assert result["compact_rows"] == 1
    compact_upsert = writer.upserts[0]
    assert compact_upsert[0] == "compact_market_line_movements"
    assert compact_upsert[2] == "slate_date,provider,book_key,normalized_player_name,market_key,side,line"
    assert compact_upsert[1][0]["odds_move_count"] == 1


class HeartbeatOnlyWriter(FakeWriter):
    def select_rows(self, table, params):
        self.selects.append((table, dict(params)))
        if table == "market_provider_runs" and "slate_date" in params:
            return []
        if table == "market_feed_heartbeats":
            return [{
                "provider": "boltodds",
                "slate_date": "2026-05-14",
                "run_id": "worker-run-1",
                "observed_at": "2026-05-14T19:00:00Z",
            }]
        if table == "market_provider_runs" and "id" in params:
            return [{"id": "worker-run-1", "provider": "boltodds"}]
        if table == "market_snapshots" and params["offset"] == "0":
            return [{
                "id": "snap-1",
                "run_id": "worker-run-1",
                "provider": "boltodds",
                "bookmaker_key": "fanduel",
                "player_name": "Example Pitcher",
                "market_key": "pitcher_strikeouts",
                "side": "over",
                "line": 5.5,
                "american_odds": -110,
                "observed_at": "2026-05-14T19:00:00Z",
            }]
        return []


def test_compact_script_includes_worker_runs_from_heartbeats():
    writer = HeartbeatOnlyWriter()

    result = compact_market_snapshots.run(
        slate_date="2026-05-14",
        writer=writer,
        dry_run=False,
    )

    assert result["provider_runs"] == 1
    assert result["snapshot_rows"] == 1
    compact_upsert = writer.upserts[0]
    assert compact_upsert[0] == "compact_market_line_movements"
    assert compact_upsert[1][0]["provider"] == "boltodds"


def test_compact_script_pages_past_supabase_rest_default_limit():
    writer = FakeWriter()

    def select_rows(table, params):
        writer.selects.append((table, dict(params)))
        if table == "market_provider_runs" and "slate_date" in params:
            return [{"id": "run-1", "provider": "boltodds", "slate_date": "2026-05-14"}]
        if table == "market_feed_heartbeats":
            return []
        if table == "market_snapshots" and params["offset"] == "0":
            return [
                {
                    "id": f"snap-{i}",
                    "run_id": "run-1",
                    "provider": "boltodds",
                    "bookmaker_key": "fanduel",
                    "player_name": "Example Pitcher",
                    "market_key": "pitcher_strikeouts",
                    "side": "over",
                    "line": 5.5,
                    "american_odds": -110,
                    "observed_at": "2026-05-14T19:00:00Z",
                }
                for i in range(1000)
            ]
        if table == "market_snapshots" and params["offset"] == "1000":
            return [{
                "id": "snap-1000",
                "run_id": "run-1",
                "provider": "boltodds",
                "bookmaker_key": "fanduel",
                "player_name": "Example Pitcher",
                "market_key": "pitcher_strikeouts",
                "side": "over",
                "line": 5.5,
                "american_odds": -105,
                "observed_at": "2026-05-14T19:05:00Z",
            }]
        return []

    writer.select_rows = select_rows

    result = compact_market_snapshots.run(
        slate_date="2026-05-14",
        writer=writer,
        dry_run=True,
    )

    assert result["snapshot_rows"] == 1001
    market_snapshot_calls = [call for call in writer.selects if call[0] == "market_snapshots"]
    assert [call[1]["offset"] for call in market_snapshot_calls] == ["0", "1000"]
