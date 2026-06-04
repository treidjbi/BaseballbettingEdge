import json

from scripts import shadow_propline_to_supabase
from scripts.shadow_propline_to_supabase import (
    _coverage_audit_row,
    _production_artifact_for_slate,
    poll_propline_to_supabase,
)
from scripts.create_propline_webhook_subscription import _parse_args


class FakeWriter:
    def __init__(self):
        self.inserts = []
        self.upserts = []

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


def test_create_propline_webhook_subscription_defaults_to_low_movement_threshold(monkeypatch):
    monkeypatch.setattr("sys.argv", ["create_propline_webhook_subscription.py"])

    args = _parse_args()

    assert args.min_price_change_pct == 2.0


def test_production_artifact_for_slate_prefers_dated_archive(tmp_path):
    dated = tmp_path / "dashboard" / "data" / "processed" / "2026-05-04.json"
    today = tmp_path / "dashboard" / "data" / "processed" / "today.json"
    dated.parent.mkdir(parents=True)
    dated.write_text(json.dumps({"date": "2026-05-04", "pitchers": [{"pitcher": "Dated"}]}))
    today.write_text(json.dumps({"date": "2026-05-04", "pitchers": [{"pitcher": "Today"}]}))

    payload, artifact_path = _production_artifact_for_slate("2026-05-04", root=tmp_path)

    assert artifact_path == "dashboard/data/processed/2026-05-04.json"
    assert payload["pitchers"][0]["pitcher"] == "Dated"


def test_production_artifact_for_slate_prefers_remote_over_stale_committed_today(
    tmp_path,
    monkeypatch,
):
    today = tmp_path / "dashboard" / "data" / "processed" / "today.json"
    today.parent.mkdir(parents=True)
    today.write_text(
        json.dumps({
            "date": "2026-05-30",
            "pitchers": [{"pitcher": f"Stale {index}"} for index in range(29)],
        })
    )
    remote_payload = {
        "date": "2026-06-04",
        "pitchers": [{"pitcher": f"Current {index}"} for index in range(16)],
    }
    artifact_url = "https://example.test/.netlify/functions/get-artifact?type=today"

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(remote_payload).encode("utf-8")

    def fake_urlopen(url, timeout):
        assert url == artifact_url
        assert timeout == 20
        return FakeResponse()

    monkeypatch.setattr(shadow_propline_to_supabase, "urlopen", fake_urlopen)

    payload, artifact_path = _production_artifact_for_slate(
        "2026-06-04",
        root=tmp_path,
        artifact_url=artifact_url,
    )

    assert artifact_path == artifact_url
    assert payload["date"] == "2026-06-04"
    assert len(payload["pitchers"]) == 16


def test_coverage_audit_row_includes_comparison_metrics():
    production = {
        "pitchers": [{
            "pitcher": "Gerrit Cole",
            "k_line": 7.5,
            "book_odds": {"BetMGM": {"over": -110, "under": -110}},
        }],
    }
    snapshots = [
        {
            "bookmaker_key": "fanduel",
            "player_name": "Gerrit Cole",
            "normalized_player_name": "gerrit cole",
            "line": 7.5,
            "side": "over",
            "american_odds": -115,
        },
        {
            "bookmaker_key": "fanduel",
            "player_name": "Gerrit Cole",
            "normalized_player_name": "gerrit cole",
            "line": 7.5,
            "side": "under",
            "american_odds": -105,
        },
    ]

    row = _coverage_audit_row(
        run_id="run-1",
        slate_date="2026-05-04",
        snapshots=snapshots,
        books_seen={"fanduel", "bovada"},
        target_event_count=1,
        observed_at="2026-05-04T18:22:00+00:00",
        production_payload=production,
        production_artifact_path="dashboard/data/processed/2026-05-04.json",
    )

    assert row["same_line_overlap_count"] == 0
    assert row["line_conflict_count"] == 0
    assert row["missing_target_books"] == ["draftkings", "betrivers", "kalshi"]
    assert row["parsed_pitcher_prop_count"] == 1
    assert row["complete_pitcher_line_groups"] == 1
    assert row["metadata"]["snapshot_rows"] == 2
    assert row["metadata"]["books_seen_raw"] == ["bovada", "fanduel"]
    assert row["metadata"]["non_target_books_seen"] == ["bovada"]
    assert row["metadata"]["production_artifact_path"] == "dashboard/data/processed/2026-05-04.json"
    assert row["metadata"]["fillable_missing_book_counts"]["fanduel"] == 1


def test_poll_propline_uses_default_netlify_production_artifact(monkeypatch):
    writer = FakeWriter()
    artifact_urls = []

    def fake_propline_get(*args, **kwargs):
        return []

    def fake_production_artifact(slate_date, **kwargs):
        artifact_urls.append(kwargs.get("artifact_url"))
        return {"date": slate_date, "pitchers": []}, kwargs.get("artifact_url")

    monkeypatch.setattr(
        "scripts.shadow_propline_to_supabase.propline_get",
        fake_propline_get,
    )
    monkeypatch.setattr(
        "scripts.shadow_propline_to_supabase._production_artifact_for_slate",
        fake_production_artifact,
    )

    poll_propline_to_supabase(
        "2026-06-04",
        writer=writer,
        observed_at="2026-06-04T15:00:00+00:00",
    )

    assert artifact_urls == [
        shadow_propline_to_supabase.DEFAULT_PRODUCTION_ARTIFACT_URL,
    ]
    coverage_insert = [
        rows[0]
        for table, rows in writer.inserts
        if table == "provider_coverage_audits"
    ][0]
    assert (
        coverage_insert["metadata"]["production_artifact_path"]
        == shadow_propline_to_supabase.DEFAULT_PRODUCTION_ARTIFACT_URL
    )


def test_poll_propline_can_record_shadow_failure_without_raising(monkeypatch):
    writer = FakeWriter()

    def fail_propline_get(*args, **kwargs):
        raise TimeoutError("PropLine read timed out")

    monkeypatch.setattr(
        "scripts.shadow_propline_to_supabase.propline_get",
        fail_propline_get,
    )
    monkeypatch.setattr(
        "scripts.shadow_propline_to_supabase._production_artifact_for_slate",
        lambda slate_date, **kwargs: (None, None),
    )

    result = poll_propline_to_supabase(
        "2026-05-29",
        writer=writer,
        raise_on_error=False,
    )

    assert result["status"] == "failed"
    assert result["error"] == "PropLine read timed out"
    assert writer.inserts[0][0] == "market_provider_runs"
    assert writer.inserts[0][1][0]["status"] == "started"
    failed = writer.upserts[-1][1][0]
    assert failed["status"] == "failed"
    assert failed["error_message"] == "PropLine read timed out"
