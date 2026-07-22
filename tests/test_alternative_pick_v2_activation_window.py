from __future__ import annotations

from datetime import datetime, timezone

from scripts import check_alternative_pick_v2_activation_window as preflight


NOW = datetime(2026, 7, 22, 18, 0, tzinfo=timezone.utc)


def _artifact(*, game_time="2026-07-22T20:00:00+00:00", verdict="LEAN", date="2026-07-22", source="therundown"):
    return {
        "date": date, "generated_at": "2026-07-22T17:55:00+00:00",
        "pitchers": [{
            "pitcher": "Tarik Skubal", "team": "DET", "opp_team": "PIT",
            "game_time": game_time, "k_line": 6.5, "odds_source": source,
            "market_source_mode": source, "line_source_provider": "therundown",
            "tracked_picks": [{"pitcher": "Tarik Skubal", "side": "over", "display_verdict": verdict, "display_k_line": 6.5, "game_time": game_time}],
        }],
    }


def test_activation_preflight_uses_exact_artifact_candidates_not_v1_state():
    result = preflight.evaluate_activation_window(payload=_artifact(), raw_bytes=b"artifact", observed_at=NOW)
    assert result["status"] == "clean"
    assert result["candidate_count"] == 1


def test_activation_preflight_fails_at_or_past_first_candidate_t30():
    result = preflight.evaluate_activation_window(payload=_artifact(game_time="2026-07-22T18:30:00+00:00"), raw_bytes=b"artifact", observed_at=NOW)
    assert result["status"] == "too_late"
    assert result["ok"] is False


def test_activation_preflight_rejects_stale_wrong_date_or_retired_source():
    wrong = preflight.evaluate_activation_window(payload=_artifact(date="2026-07-21"), raw_bytes=b"artifact", observed_at=NOW)
    retired = preflight.evaluate_activation_window(payload=_artifact(source="boltodds"), raw_bytes=b"artifact", observed_at=NOW)
    stale = _artifact()
    stale["generated_at"] = "2026-07-21T17:55:00+00:00"
    assert wrong["ok"] is False
    assert retired["ok"] is False
    assert preflight.evaluate_activation_window(payload=stale, raw_bytes=b"artifact", observed_at=NOW)["ok"] is False


def test_activation_preflight_zero_candidates_is_safe_but_not_release_evidence():
    result = preflight.evaluate_activation_window(payload=_artifact(verdict="PASS"), raw_bytes=b"artifact", observed_at=NOW)
    assert result == {**result, "status": "no_candidates", "ok": True, "candidate_count": 0, "release_evidence": False}
