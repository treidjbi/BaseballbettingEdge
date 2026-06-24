from datetime import datetime

from market_infra.shadow_pipeline_timing import build_shadow_pipeline_timing_rows


def _pitcher(
    *,
    game_time="2026-05-14T19:00:00Z",
    locked_at=None,
    verdict="FIRE 1u",
):
    return {
        "pitcher": "Tarik Skubal",
        "team": "DET",
        "opp_team": "BOS",
        "ref_book": "FanDuel",
        "game_time": game_time,
        "game_state": "pregame",
        "tracked_picks": [
            {
                "pitcher": "Tarik Skubal",
                "side": "over",
                "display_verdict": verdict,
                "display_k_line": 6.5,
                "display_odds": -110,
                "locked_at": locked_at,
                "game_time": game_time,
            }
        ],
    }


def test_shadow_timing_marks_unlocked_pick_inside_lock_window_as_due_now():
    run_row, observation_rows = build_shadow_pipeline_timing_rows(
        slate_date="2026-05-14",
        pitchers=[_pitcher()],
        observed_at=datetime.fromisoformat("2026-05-14T18:32:00+00:00"),
        source_artifact_path="https://raw.example/today.json",
        source_artifact_sha256="sha",
        artifact_generated_at="2026-05-14T18:25:00Z",
    )

    assert run_row["tracked_pick_count"] == 1
    assert run_row["due_now_count"] == 1
    assert run_row["missed_lock_count"] == 0
    assert run_row["started_unlocked_count"] == 0
    assert observation_rows[0]["status"] == "due_now"
    assert observation_rows[0]["should_lock_at"] == "2026-05-14T18:30:00+00:00"
    assert observation_rows[0]["dedupe_key"] == "2026-05-14:tarik skubal:over:due_now"


def test_shadow_timing_marks_late_unlocked_pick_as_missed_lock():
    run_row, observation_rows = build_shadow_pipeline_timing_rows(
        slate_date="2026-05-14",
        pitchers=[_pitcher()],
        observed_at=datetime.fromisoformat("2026-05-14T18:45:00+00:00"),
        source_artifact_path="today.json",
        source_artifact_sha256="sha",
    )

    assert run_row["due_now_count"] == 0
    assert run_row["missed_lock_count"] == 1
    assert observation_rows[0]["status"] == "missed_lock"
    assert observation_rows[0]["minutes_until_start"] == 15.0


def test_shadow_timing_honors_configured_operational_lock_grace(monkeypatch):
    monkeypatch.setenv("OPERATIONAL_LOCK_GRACE_MINUTES", "10")

    run_row, observation_rows = build_shadow_pipeline_timing_rows(
        slate_date="2026-05-14",
        pitchers=[_pitcher()],
        observed_at=datetime.fromisoformat("2026-05-14T18:36:00+00:00"),
        source_artifact_path="today.json",
        source_artifact_sha256="sha",
    )

    assert run_row["due_now_count"] == 1
    assert run_row["missed_lock_count"] == 0
    assert run_row["metadata"]["missed_lock_grace_minutes"] == 10
    assert observation_rows[0]["status"] == "due_now"


def test_shadow_timing_distinguishes_artifact_locked_from_started_unlocked():
    locked = _pitcher(locked_at="2026-05-14T18:28:00Z")
    unlocked_started = _pitcher(game_time="2026-05-14T18:20:00Z")
    unlocked_started["pitcher"] = "Chris Sale"
    unlocked_started["tracked_picks"][0]["pitcher"] = "Chris Sale"

    run_row, observation_rows = build_shadow_pipeline_timing_rows(
        slate_date="2026-05-14",
        pitchers=[locked, unlocked_started],
        observed_at=datetime.fromisoformat("2026-05-14T18:45:00+00:00"),
        source_artifact_path="today.json",
        source_artifact_sha256="sha",
    )

    statuses = {row["normalized_pitcher"]: row["status"] for row in observation_rows}
    assert statuses == {
        "tarik skubal": "artifact_locked",
        "chris sale": "started_unlocked",
    }
    assert run_row["artifact_locked_pick_count"] == 1
    assert run_row["started_unlocked_count"] == 1


def test_shadow_timing_skips_pass_rows_to_match_seeded_pick_scope():
    run_row, observation_rows = build_shadow_pipeline_timing_rows(
        slate_date="2026-05-14",
        pitchers=[_pitcher(verdict="PASS")],
        observed_at=datetime.fromisoformat("2026-05-14T18:32:00+00:00"),
        source_artifact_path="today.json",
        source_artifact_sha256="sha",
    )

    assert run_row["tracked_pick_count"] == 0
    assert observation_rows == []


def test_shadow_timing_persists_extra_metadata_for_operational_probes():
    run_row, _ = build_shadow_pipeline_timing_rows(
        slate_date="2026-05-14",
        pitchers=[_pitcher()],
        observed_at=datetime.fromisoformat("2026-05-14T18:32:00+00:00"),
        source_artifact_path="today.json",
        source_artifact_sha256="sha",
        metadata_extra={
            "propline_webhooks": {
                "processed": 12,
                "errors": 0,
            }
        },
    )

    assert run_row["metadata"]["propline_webhooks"] == {
        "processed": 12,
        "errors": 0,
    }
    assert run_row["metadata"]["lock_window_minutes"] == 30
