import json

from scripts.shadow_propline_to_supabase import (
    _coverage_audit_row,
    _production_artifact_for_slate,
)


def test_production_artifact_for_slate_prefers_dated_archive(tmp_path):
    dated = tmp_path / "dashboard" / "data" / "processed" / "2026-05-04.json"
    today = tmp_path / "dashboard" / "data" / "processed" / "today.json"
    dated.parent.mkdir(parents=True)
    dated.write_text(json.dumps({"date": "2026-05-04", "pitchers": [{"pitcher": "Dated"}]}))
    today.write_text(json.dumps({"date": "2026-05-04", "pitchers": [{"pitcher": "Today"}]}))

    payload, artifact_path = _production_artifact_for_slate("2026-05-04", root=tmp_path)

    assert artifact_path == "dashboard/data/processed/2026-05-04.json"
    assert payload["pitchers"][0]["pitcher"] == "Dated"


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
