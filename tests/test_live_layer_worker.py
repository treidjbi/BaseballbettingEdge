import json
from pathlib import Path
from unittest.mock import Mock, patch

from scripts import build_live_events_to_supabase


def test_worker_writes_state_and_notification_events(tmp_path):
    today = tmp_path / "today.json"
    today.write_text(
        json.dumps({
            "date": "2026-05-06",
            "pitchers": [{
                "pitcher": "Tarik Skubal",
                "team": "DET",
                "opp_team": "BOS",
                "k_line": 6.5,
                "game_time": "2026-05-06T22:10:00Z",
                "game_state": "scheduled",
                "best_over_odds": -110,
                "best_over_book": "FanDuel",
                "ev_over": {"verdict": "FIRE 1u", "adj_ev": 0.09, "edge": 0.05},
            }],
        }),
        encoding="utf-8",
    )

    writer = Mock()
    writer.select_rows.return_value = []

    with patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["live_pick_state"] == 1
    assert result["notification_events"] == 1
    assert result["state_rows"][0]["source_artifact_sha256"]
    assert Path(result["state_rows"][0]["source_artifact_path"]).name == "today.json"
    writer.select_rows.assert_called_once_with(
        "live_pick_state",
        {"slate_date": "eq.2026-05-06"},
    )
    writer.upsert_rows.assert_any_call(
        "live_pick_state",
        result["state_rows"],
        on_conflict="slate_date,normalized_pitcher,side",
    )
    writer.upsert_rows.assert_any_call(
        "notification_events",
        result["notification_rows"],
        on_conflict="dedupe_key",
    )
