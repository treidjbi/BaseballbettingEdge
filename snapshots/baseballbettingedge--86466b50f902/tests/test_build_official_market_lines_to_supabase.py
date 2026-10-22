from datetime import datetime, timezone

from scripts.build_official_market_lines_to_supabase import run


NOW = datetime(2026, 5, 13, 19, 0, tzinfo=timezone.utc)


class FakeWriter:
    def __init__(self, rows, official_rows=None, heartbeat_rows=None, live_rows=None):
        self.rows = rows
        self.official_rows = official_rows or []
        self.heartbeat_rows = heartbeat_rows or []
        self.live_rows = live_rows or []
        self.upserts = []
        self.inserts = []
        self.calls = []

    def select_rows(self, table, params):
        self.calls.append((table, dict(params)))
        assert params["slate_date"] == "eq.2026-05-13"
        if table == "current_market_lines":
            return _filter_provider_rows(self.rows, params)
        if table == "official_market_lines":
            return self.official_rows
        if table == "market_feed_heartbeats":
            return _filter_provider_rows(self.heartbeat_rows, params)
        if table == "live_pick_state":
            return self.live_rows
        raise AssertionError(f"unexpected table: {table}")

    def upsert_rows(self, table, rows, on_conflict):
        self.upserts.append((table, rows, on_conflict))
        return rows

    def insert_rows(self, table, rows):
        self.inserts.append((table, rows))
        return rows


def _line(line_id, *, provider="therundown", book_key="fanduel", book_name="FanDuel"):
    return {
        "id": line_id,
        "slate_date": "2026-05-13",
        "provider": provider,
        "book_key": book_key,
        "book_name": book_name,
        "game_time": "2026-05-13T23:05:00Z",
        "player_name": "Jose Berrios",
        "normalized_player_name": "jose berrios",
        "market_key": "pitcher_strikeouts",
        "line": 5.5,
        "over_odds": -110,
        "under_odds": -110,
        "freshness_seconds": 60,
        "last_seen_at": "2026-05-13T18:59:00+00:00",
        "is_complete": True,
        "quality_flags": [],
    }


def _filter_provider_rows(rows, params):
    provider_filter = params.get("provider")
    if not provider_filter:
        return rows
    if provider_filter.startswith("in.(") and provider_filter.endswith(")"):
        providers = {
            item.strip()
            for item in provider_filter[len("in.("):-1].split(",")
            if item.strip()
        }
        return [
            row
            for row in rows
            if str(row.get("provider") or "").strip().lower() in providers
        ]
    if provider_filter.startswith("eq."):
        provider = provider_filter[len("eq."):]
        return [
            row
            for row in rows
            if str(row.get("provider") or "").strip().lower() == provider
        ]
    return rows


def test_dry_run_reports_counts_without_writes():
    writer = FakeWriter([_line(1)])

    result = run(slate_date="2026-05-13", writer=writer, dry_run=True, now_utc=NOW)

    assert result["current_market_lines"] == 1
    assert result["official_market_lines"] == 1
    assert result["arbitration_decisions"] == 1
    assert result["written_official_rows"] == 0
    assert result["written_decisions"] == 0
    assert writer.upserts == []
    assert writer.inserts == []


def test_upsert_writes_official_lines_and_decision_audit_rows():
    writer = FakeWriter([_line(1), _line(2, provider="propline", book_key="draftkings", book_name="DraftKings")])

    result = run(slate_date="2026-05-13", writer=writer, dry_run=False, now_utc=NOW)

    assert result["written_official_rows"] == 1
    assert result["written_decisions"] == 1
    assert writer.upserts[0][0] == "official_market_lines"
    assert writer.upserts[0][2] == "slate_date,normalized_player_name,market_key"
    assert writer.inserts[0][0] == "provider_arbitration_decisions"
    official = writer.upserts[0][1][0]
    assert official["ref_book_key"] == "fanduel"
    assert official["book_odds"]["DraftKings"]["provider"] == "propline"
    current_line_call = next(call for call in writer.calls if call[0] == "current_market_lines")
    assert current_line_call[1]["provider"] == "in.(therundown,propline,the_odds)"


def test_run_enriches_missing_game_times_before_official_arbitration():
    line = _line(1)
    line["game_time"] = None
    writer = FakeWriter(
        [line],
        live_rows=[{
            "slate_date": "2026-05-13",
            "normalized_pitcher": "jose berrios",
            "game_time": "2026-05-13T23:05:00+00:00",
            "source_artifact_path": "https://example.test/today.json",
            "updated_at": "2026-05-13T18:59:30+00:00",
        }],
    )

    result = run(
        slate_date="2026-05-13",
        writer=writer,
        dry_run=False,
        now_utc=NOW,
        artifact_payload={"date": "2026-05-13", "pitchers": []},
    )

    assert result["game_time_enriched"] == 1
    assert result["ready_for_pipeline"] == 1
    official = writer.upserts[0][1][0]
    assert official["game_time"] == "2026-05-13T23:05:00+00:00"
    assert official["ready_for_pipeline"] is True


def test_active_builder_filters_out_retired_boltodds_heartbeat_hold():
    stale_line = _line(1, provider="boltodds")
    stale_line["freshness_seconds"] = 1800
    stale_line["last_seen_at"] = "2026-05-13T18:30:00+00:00"
    stale_line["quality_flags"] = ["stale"]
    writer = FakeWriter(
        [stale_line],
        heartbeat_rows=[{
            "provider": "boltodds",
            "mode": "shadow_stream",
            "slate_date": "2026-05-13",
            "observed_at": "2026-05-13T18:59:45+00:00",
            "last_message_at": "2026-05-13T18:59:40+00:00",
            "books_seen": ["fanduel"],
            "metadata": {"event": "message"},
        }],
    )

    result = run(slate_date="2026-05-13", writer=writer, dry_run=False, now_utc=NOW)

    assert result["current_market_lines"] == 0
    assert result["provider_heartbeats"] == 0
    assert result["ready_for_pipeline"] == 0
    current_line_call = next(call for call in writer.calls if call[0] == "current_market_lines")
    heartbeat_call = next(call for call in writer.calls if call[0] == "market_feed_heartbeats")
    assert current_line_call[1]["provider"] == "in.(therundown,propline,the_odds)"
    assert heartbeat_call[1]["provider"] == "in.(propline,therundown)"


def test_missing_existing_ready_rows_are_retired():
    writer = FakeWriter(
        [],
        official_rows=[{
            "slate_date": "2026-05-13",
            "normalized_player_name": "jose berrios",
            "player_name": "Jose Berrios",
            "market_key": "pitcher_strikeouts",
            "ready_for_pipeline": True,
            "current_market_line_ids": [123],
        }],
    )

    result = run(slate_date="2026-05-13", writer=writer, dry_run=False, now_utc=NOW)

    assert result["current_market_lines"] == 0
    assert result["official_market_lines"] == 1
    assert result["ready_for_pipeline"] == 0
    assert result["retired_missing_rows"] == 1
    official = writer.upserts[0][1][0]
    decision = writer.inserts[0][1][0]
    assert official["ready_for_pipeline"] is False
    assert official["quality_flags"] == ["not_ready_for_pipeline", "missing_from_current_market_lines"]
    assert decision["decision"] == "skip"
    assert decision["reasons"] == ["missing_from_current_market_lines"]
