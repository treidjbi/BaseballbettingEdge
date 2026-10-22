from datetime import datetime, timezone

from scripts.build_current_market_lines_to_supabase import (
    DEFAULT_ARTIFACT_URL,
    _enrich_game_times_from_artifact,
    _enrich_game_times_from_live_pick_state,
    _fetch_inputs,
    _fetch_snapshot_pages,
    run,
)


NOW = datetime(2026, 5, 14, 16, 20, tzinfo=timezone.utc)


class FakeWriter:
    def __init__(self, *, stale_run_from_heartbeat=False, live_game_times=None):
        self.calls = []
        self.stale_run_from_heartbeat = stale_run_from_heartbeat
        self.live_game_times = live_game_times or []
        self.upserts = []
        self.insert_ignores = []

    def select_rows(self, table, params):
        self.calls.append((table, dict(params)))
        if table == "live_pick_state":
            return self.live_game_times
        if self.stale_run_from_heartbeat:
            if table == "market_provider_runs" and "slate_date" in params:
                return []
            if table == "market_feed_heartbeats":
                return [{"run_id": "run-rotated", "provider": "propline", "slate_date": "2026-05-14"}]
            if table == "market_provider_runs" and "id" in params:
                return [{"id": "run-rotated", "provider": "propline", "slate_date": "2026-05-13"}]
            if table == "market_snapshots" and params["offset"] == "0":
                return [{"id": "snap-rotated"}]
            return []
        if table == "market_provider_runs":
            return [{"id": "run-1", "provider": "propline", "slate_date": "2026-05-13"}]
        if table == "market_snapshots" and params["offset"] == "0":
            return [{"id": "snap-1"}]
        return []

    def upsert_rows(self, table, rows, on_conflict):
        self.upserts.append((table, rows, on_conflict))
        return rows

    def insert_ignore_rows(self, table, rows, on_conflict):
        self.insert_ignores.append((table, rows, on_conflict))
        return rows


def test_fetch_inputs_pages_market_snapshots_without_market_key_filter():
    writer = FakeWriter()

    snapshot_rows, run_rows = _fetch_inputs(writer, "2026-05-13")

    assert run_rows == [{"id": "run-1", "provider": "propline", "slate_date": "2026-05-13"}]
    assert snapshot_rows == [{"id": "snap-1"}]
    snapshot_call = next(call for call in writer.calls if call[0] == "market_snapshots")
    assert snapshot_call[0] == "market_snapshots"
    assert snapshot_call[1]["run_id"] == "in.(run-1)"
    assert snapshot_call[1]["limit"] == "1000"
    assert snapshot_call[1]["offset"] == "0"
    assert "market_key" not in snapshot_call[1]
    run_call = next(call for call in writer.calls if call[0] == "market_provider_runs")
    assert run_call[1]["provider"] == "in.(propline,the_odds,therundown)"


def test_fetch_snapshot_pages_uses_rest_api_sized_pages():
    class PagingWriter:
        def __init__(self):
            self.calls = []

        def select_rows(self, table, params):
            self.calls.append((table, dict(params)))
            if params["offset"] == "0":
                return [{"id": f"snap-{i}"} for i in range(1000)]
            if params["offset"] == "1000":
                return [{"id": "snap-1000"}]
            return []

    writer = PagingWriter()

    rows = _fetch_snapshot_pages(writer, [{"id": "run-1"}])

    assert len(rows) == 1001
    assert [call[1]["offset"] for call in writer.calls] == ["0", "1000"]


def test_fetch_inputs_uses_current_slate_heartbeat_when_run_row_did_not_rotate():
    writer = FakeWriter(stale_run_from_heartbeat=True)

    snapshot_rows, run_rows = _fetch_inputs(writer, "2026-05-14")

    assert run_rows == [{"id": "run-rotated", "provider": "propline", "slate_date": "2026-05-14"}]
    assert snapshot_rows == [{"id": "snap-rotated"}]
    assert ("market_feed_heartbeats", {
        "slate_date": "eq.2026-05-14",
        "provider": "in.(propline,the_odds,therundown)",
        "order": "observed_at.desc",
        "limit": "250",
    }) in writer.calls


def test_default_market_line_artifact_url_uses_get_artifact():
    assert "baseballbettingedge.netlify.app/.netlify/functions/get-artifact" in DEFAULT_ARTIFACT_URL
    assert "type=today" in DEFAULT_ARTIFACT_URL
    assert "raw.githubusercontent.com" not in DEFAULT_ARTIFACT_URL


def test_enrich_game_times_from_live_pick_state_fills_missing_rows_by_pitcher():
    current_rows = [{
        "normalized_player_name": "jose berrios",
        "player_name": "Jose Berrios",
        "game_time": None,
        "raw_payload": {"over": {"id": 1}, "under": {"id": 2}},
    }]
    live_rows = [{
        "normalized_pitcher": "jose berrios",
        "pitcher": "Jose Berrios",
        "game_time": "2026-05-14T23:05:00+00:00",
        "source_artifact_path": "https://raw.githubusercontent.com/example/today.json",
    }]

    enriched = _enrich_game_times_from_live_pick_state(current_rows, live_rows)

    assert enriched == 1
    assert current_rows[0]["game_time"] == "2026-05-14T23:05:00+00:00"
    assert current_rows[0]["raw_payload"]["game_time_source"] == {
        "source": "live_pick_state",
        "source_artifact_path": "https://raw.githubusercontent.com/example/today.json",
    }


def test_enrich_game_times_from_artifact_fills_rows_when_live_state_is_missing():
    current_rows = [{
        "normalized_player_name": "jose berrios",
        "player_name": "Jose Berrios",
        "game_time": None,
        "raw_payload": {"over": {"id": 1}, "under": {"id": 2}},
    }]
    artifact_payload = {
        "date": "2026-05-14",
        "pitchers": [{
            "pitcher": "Jose Berrios",
            "game_time": "2026-05-14T23:05:00Z",
        }],
    }

    enriched = _enrich_game_times_from_artifact(
        current_rows,
        artifact_payload,
        source_artifact_path="dashboard/data/processed/2026-05-14.json",
    )

    assert enriched == 1
    assert current_rows[0]["game_time"] == "2026-05-14T23:05:00Z"
    assert current_rows[0]["raw_payload"]["game_time_source"] == {
        "source": "production_artifact",
        "source_artifact_path": "dashboard/data/processed/2026-05-14.json",
    }


def test_run_enriches_missing_game_times_before_writing_current_lines():
    writer = FakeWriter(live_game_times=[{
        "normalized_pitcher": "jose berrios",
        "pitcher": "Jose Berrios",
        "game_time": "2026-05-14T23:05:00+00:00",
        "source_artifact_path": "https://raw.githubusercontent.com/example/today.json",
    }])

    def select_rows(table, params):
        writer.calls.append((table, dict(params)))
        if table == "market_provider_runs":
            return [{"id": "run-1", "provider": "propline", "slate_date": "2026-05-14"}]
        if table == "market_feed_heartbeats":
            return []
        if table == "live_pick_state":
            return writer.live_game_times
        if table == "market_snapshots" and params["offset"] == "0":
            return [
                {
                    "id": "snap-over",
                    "run_id": "run-1",
                    "provider": "propline",
                    "bookmaker_key": "fanduel",
                    "bookmaker_title": "FanDuel",
                    "player_name": "Jose Berrios",
                    "market_key": "pitcher_strikeouts",
                    "side": "over",
                    "line": 5.5,
                    "american_odds": -115,
                    "observed_at": "2026-05-14T16:19:00+00:00",
                },
                {
                    "id": "snap-under",
                    "run_id": "run-1",
                    "provider": "propline",
                    "bookmaker_key": "fanduel",
                    "bookmaker_title": "FanDuel",
                    "player_name": "Jose Berrios",
                    "market_key": "pitcher_strikeouts",
                    "side": "under",
                    "line": 5.5,
                    "american_odds": -105,
                    "observed_at": "2026-05-14T16:19:10+00:00",
                },
            ]
        return []

    writer.select_rows = select_rows

    result = run(slate_date="2026-05-14", writer=writer, dry_run=False, now_utc=NOW)

    assert result["game_time_enriched"] == 1
    written = writer.upserts[0][1][0]
    assert written["game_time"] == "2026-05-14T23:05:00+00:00"
    assert ("live_pick_state", {
        "slate_date": "eq.2026-05-14",
        "order": "updated_at.desc",
        "limit": "1000",
    }) in writer.calls


def test_run_falls_back_to_artifact_game_times_before_writing_current_lines():
    writer = FakeWriter()

    def select_rows(table, params):
        writer.calls.append((table, dict(params)))
        if table == "market_provider_runs":
            return [{"id": "run-1", "provider": "propline", "slate_date": "2026-05-14"}]
        if table == "market_feed_heartbeats":
            return []
        if table == "live_pick_state":
            return []
        if table == "market_snapshots" and params["offset"] == "0":
            return [
                {
                    "id": "snap-over",
                    "run_id": "run-1",
                    "provider": "propline",
                    "bookmaker_key": "fanduel",
                    "bookmaker_title": "FanDuel",
                    "player_name": "Jose Berrios",
                    "market_key": "pitcher_strikeouts",
                    "side": "over",
                    "line": 5.5,
                    "american_odds": -115,
                    "observed_at": "2026-05-14T16:19:00+00:00",
                },
                {
                    "id": "snap-under",
                    "run_id": "run-1",
                    "provider": "propline",
                    "bookmaker_key": "fanduel",
                    "bookmaker_title": "FanDuel",
                    "player_name": "Jose Berrios",
                    "market_key": "pitcher_strikeouts",
                    "side": "under",
                    "line": 5.5,
                    "american_odds": -105,
                    "observed_at": "2026-05-14T16:19:10+00:00",
                },
            ]
        return []

    writer.select_rows = select_rows

    result = run(
        slate_date="2026-05-14",
        writer=writer,
        dry_run=False,
        now_utc=NOW,
        artifact_payload={
            "date": "2026-05-14",
            "pitchers": [{
                "pitcher": "Jose Berrios",
                "game_time": "2026-05-14T23:05:00Z",
            }],
        },
        artifact_source="dashboard/data/processed/2026-05-14.json",
    )

    assert result["game_time_enriched"] == 1
    assert result["game_time_live_state_enriched"] == 0
    assert result["game_time_artifact_enriched"] == 1
    written = writer.upserts[0][1][0]
    assert written["game_time"] == "2026-05-14T23:05:00Z"
    assert written["raw_payload"]["game_time_source"] == {
        "source": "production_artifact",
        "source_artifact_path": "dashboard/data/processed/2026-05-14.json",
    }


def test_run_writes_provider_usage_rows_from_fetched_runs_and_snapshots():
    writer = FakeWriter()

    def select_rows(table, params):
        writer.calls.append((table, dict(params)))
        if table == "market_provider_runs":
            return [{
                "id": "run-1",
                "provider": "propline",
                "mode": "shadow_poll",
                "slate_date": "2026-05-14",
                "request_count": 5,
                "metadata": {"script": "scripts/shadow_propline_to_supabase.py"},
            }]
        if table == "market_feed_heartbeats":
            return []
        if table == "live_pick_state":
            return []
        if table == "market_snapshots" and params["offset"] == "0":
            return [{
                "id": "snap-1",
                "run_id": "run-1",
                "provider": "propline",
                "bookmaker_key": "draftkings",
                "bookmaker_title": "DraftKings",
                "player_name": "Jose Berrios",
                "market_key": "pitcher_strikeouts",
                "side": "over",
                "line": 5.5,
                "american_odds": -115,
                "observed_at": "2026-05-14T16:19:00+00:00",
            }]
        return []

    writer.select_rows = select_rows

    result = run(slate_date="2026-05-14", writer=writer, dry_run=False, now_utc=NOW)

    assert result["provider_usage_rows"] == 1
    usage_upsert = next(call for call in writer.upserts if call[0] == "provider_request_usage_daily")
    assert usage_upsert == (
        "provider_request_usage_daily",
        [{
            "usage_date": "2026-05-14",
            "provider": "propline",
            "source": "scripts/shadow_propline_to_supabase.py",
            "request_count": 5,
            "snapshot_count": 1,
        }],
        "usage_date,provider,source",
    )
