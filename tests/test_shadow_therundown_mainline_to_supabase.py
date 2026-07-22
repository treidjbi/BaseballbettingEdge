from scripts import shadow_therundown_mainline_to_supabase
from scripts.shadow_therundown_mainline_to_supabase import poll_therundown_mainline_to_supabase


class FakeWriter:
    def __init__(self):
        self.inserts = []
        self.upserts = []
        self.selects = []

    def insert_rows(self, table, rows):
        if table == "market_provider_runs":
            rows = [
                {
                    **row,
                    "id": row.get("id") or f"run-{len(self.inserts) + index + 1}",
                }
                for index, row in enumerate(rows)
            ]
        self.inserts.append((table, rows))
        return rows

    def upsert_rows(self, table, rows, on_conflict):
        self.upserts.append((table, rows, on_conflict))
        return rows

    def select_rows(self, table, params):
        self.selects.append((table, dict(params)))
        return []


def _event():
    return {
        "event_id": "tr-evt-1",
        "event_date": "2026-06-12T23:05:00Z",
        "markets": [
            {
                "market_id": 19,
                "participants": [
                    {
                        "name": "Gerrit Cole",
                        "lines": [
                            {
                                "value": "Over 7.5",
                                "prices": {
                                    "23": {
                                        "price": -115,
                                        "is_main_line": True,
                                        "updated_at": "2026-06-12T15:02:00Z",
                                    }
                                },
                            },
                            {
                                "value": "Under 7.5",
                                "prices": {
                                    "23": {
                                        "price": -105,
                                        "is_main_line": True,
                                        "updated_at": "2026-06-12T15:02:00Z",
                                    }
                                },
                            },
                        ],
                    }
                ],
            }
        ],
    }


def _fetch_result(events, datapoints, fetch_date):
    return {
        "fetch_date": fetch_date,
        "events": events,
        "datapoints": datapoints,
        "headers": {
            "X-Datapoints": str(datapoints),
            "X-Datapoints-Limit": "5000000",
            "X-Datapoints-Remaining": "4999000",
            "X-Tier": "starter",
            "X-Rate-Limit": "2",
            "X-Data-Delay-Seconds": "60",
            "X-Websocket-Access": "false",
        },
        "params": {
            "market_ids": "19",
            "affiliate_ids": "19,22,23,24,25",
            "main_line": "true",
        },
    }


def test_poll_therundown_mainline_writes_shadow_rows_and_datapoint_metadata(monkeypatch):
    writer = FakeWriter()
    fetch_calls = []

    def fake_fetch(fetch_date, *, main_line, hide_closed_markets):
        fetch_calls.append((fetch_date, main_line, hide_closed_markets))
        events = [_event()] if fetch_date == "2026-06-12" else []
        return _fetch_result(events, 140 if events else 8, fetch_date)

    monkeypatch.setattr(
        shadow_therundown_mainline_to_supabase,
        "fetch_therundown_events",
        fake_fetch,
    )
    monkeypatch.setattr(
        shadow_therundown_mainline_to_supabase,
        "_production_artifact_for_slate",
        lambda slate_date, **kwargs: (
            {
                "date": slate_date,
                "pitchers": [
                    {
                        "pitcher": "Gerrit Cole",
                        "k_line": 7.5,
                        "book_odds": {"FanDuel": {"over": -115, "under": -105}},
                    }
                ],
            },
            "https://example.test/.netlify/functions/get-artifact?type=today",
        ),
    )

    result = poll_therundown_mainline_to_supabase(
        "2026-06-12",
        writer=writer,
        observed_at="2026-06-12T15:03:00+00:00",
    )

    assert fetch_calls == [
        ("2026-06-12", True, True),
        ("2026-06-13", True, True),
    ]
    assert result["snapshot_count"] == 2
    assert result["datapoints"] == 148
    assert result["request_count"] == 2

    assert writer.inserts[0][0] == "market_provider_runs"
    started = writer.inserts[0][1][0]
    assert started["provider"] == "therundown"
    assert started["mode"] == "shadow_poll"
    assert started["metadata"]["script"] == "scripts/shadow_therundown_mainline_to_supabase.py"
    assert started["metadata"]["query_mode"] == "main_line"

    snapshot_upsert = [entry for entry in writer.upserts if entry[0] == "market_snapshots"][0]
    assert snapshot_upsert[2] == "dedupe_key"
    assert {row["provider"] for row in snapshot_upsert[1]} == {"therundown"}
    assert {row["bookmaker_key"] for row in snapshot_upsert[1]} == {"fanduel"}

    audit_insert = [entry for entry in writer.inserts if entry[0] == "provider_coverage_audits"][0]
    audit = audit_insert[1][0]
    assert audit["provider"] == "therundown"
    assert audit["target_books"] == ["draftkings", "betmgm", "fanduel", "thescore", "kalshi"]
    assert audit["same_line_overlap_count"] == 1
    assert audit["metadata"]["datapoints_total"] == 148
    assert audit["metadata"]["query_mode"] == "main_line"

    completed = writer.upserts[-1][1][0]
    assert completed["status"] == "completed"
    assert completed["request_count"] == 2
    assert completed["parsed_pitcher_prop_count"] == 1
    assert completed["metadata"]["datapoints_total"] == 148
    assert completed["metadata"]["production_artifact_path"] == "https://example.test/.netlify/functions/get-artifact?type=today"


def test_poll_therundown_mainline_can_record_failure_without_raising(monkeypatch):
    writer = FakeWriter()

    def fail_fetch(*args, **kwargs):
        raise TimeoutError("TheRundown read timed out")

    monkeypatch.setattr(
        shadow_therundown_mainline_to_supabase,
        "fetch_therundown_events",
        fail_fetch,
    )
    monkeypatch.setattr(
        shadow_therundown_mainline_to_supabase,
        "_production_artifact_for_slate",
        lambda slate_date, **kwargs: (None, None),
    )

    result = poll_therundown_mainline_to_supabase(
        "2026-06-12",
        writer=writer,
        raise_on_error=False,
    )

    assert result["status"] == "failed"
    assert result["error"] == "TheRundown read timed out"
    failed = writer.upserts[-1][1][0]
    assert failed["provider"] == "therundown"
    assert failed["status"] == "failed"
    assert failed["error_message"] == "TheRundown read timed out"


def test_poll_deduplicates_cross_date_events_before_market_writes(monkeypatch):
    writer = FakeWriter()

    def fake_fetch(fetch_date, *, main_line, hide_closed_markets):
        return _fetch_result([_event()], 65, fetch_date)

    monkeypatch.setattr(
        shadow_therundown_mainline_to_supabase,
        "fetch_therundown_events",
        fake_fetch,
    )
    monkeypatch.setattr(
        shadow_therundown_mainline_to_supabase,
        "_production_artifact_for_slate",
        lambda slate_date, **kwargs: (None, None),
    )

    result = poll_therundown_mainline_to_supabase(
        "2026-06-12",
        writer=writer,
        observed_at="2026-06-12T15:03:00+00:00",
    )

    event_upsert = [entry for entry in writer.upserts if entry[0] == "market_events"][0]
    snapshot_upsert = [entry for entry in writer.upserts if entry[0] == "market_snapshots"][0]
    assert len(event_upsert[1]) == 1
    assert len(snapshot_upsert[1]) == 2
    assert len({row["dedupe_key"] for row in snapshot_upsert[1]}) == 2

    assert result["target_event_count"] == 2
    assert result["unique_event_count"] == 1
    assert result["duplicate_event_count"] == 1

    completed = writer.upserts[-1][1][0]
    assert completed["metadata"]["unique_event_count"] == 1
    assert completed["metadata"]["duplicate_event_count"] == 1
    assert completed["metadata"]["duplicate_event_ids"] == ["tr-evt-1"]
