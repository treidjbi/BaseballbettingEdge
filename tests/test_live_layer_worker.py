import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import ANY, Mock, patch

import pytest
import requests

from scripts import build_live_events_to_supabase

THERUNDOWN_OVER_SNAPSHOT_ID = "11111111-1111-4111-8111-111111111111"
THERUNDOWN_UNDER_SNAPSHOT_ID = "11111111-1111-4111-8111-111111111112"
PROPLINE_OVER_SNAPSHOT_ID = "22222222-2222-4222-8222-222222222221"
PROPLINE_UNDER_SNAPSHOT_ID = "22222222-2222-4222-8222-222222222222"


def _ordered_uuid(value):
    return f"00000000-0000-4000-8000-{value:012d}"


def _writer_with_selects(table_rows):
    writer = Mock()

    def select_rows(table, params):
        return table_rows.get(table, [])

    writer.select_rows.side_effect = select_rows
    return writer


def _write_artifact(tmp_path, pitchers):
    today = tmp_path / "today.json"
    today.write_text(
        json.dumps({
            "date": "2026-05-06",
            "pitchers": pitchers,
        }),
        encoding="utf-8",
    )
    return today


def _fire_pitcher(game_time="2026-05-06T22:10:00Z", pitcher="Tarik Skubal"):
    return {
        "pitcher": pitcher,
        "team": "DET",
        "opp_team": "BOS",
        "k_line": 6.5,
        "game_time": game_time,
        "game_state": "scheduled",
        "best_over_odds": -110,
        "best_over_book": "FanDuel",
        "ev_over": {"verdict": "FIRE 1u", "adj_ev": 0.09, "edge": 0.05},
    }


def _previous_fire_state(pitcher, *, game_time):
    return {
        "slate_date": "2026-05-06",
        "pitcher": pitcher,
        "normalized_pitcher": pitcher.lower(),
        "side": "over",
        "current_verdict": "FIRE 1u",
        "previous_verdict": "FIRE 1u",
        "k_line": 6.5,
        "current_odds": -110,
        "current_book": "FanDuel",
        "game_time": game_time,
        "game_state": "scheduled",
        "is_fire": True,
        "is_locked": False,
        "source_artifact_path": "test",
        "source_artifact_sha256": "sha",
        "last_model_seen_at": "2026-05-06T17:50:00+00:00",
        "metadata": {},
    }


def _alternative_artifact_payload(*, tracked_line=6.5, odds_source="therundown", market_source_mode=None):
    pitcher = _fire_pitcher()
    pitcher.update({
        "odds_source": odds_source,
        "market_source_mode": market_source_mode,
        "propline_event_id": "pl-game-current",
        "therundown_event_id": "tr-game-current",
        "ev_over": {
            "verdict": "FIRE 1u",
            "raw_verdict": "FIRE 1u",
            "actionable_verdict": "FIRE 1u",
            "adj_ev": 0.09,
            "edge": 0.05,
            "win_prob": 0.61,
            "quality_gate_level": "clean",
            "market_anchor_selector": {"labels": ["market_anchor_core"]},
        },
    })
    pitcher["tracked_picks"] = [{
        "pitcher": "Tarik Skubal",
        "side": "over",
        "display_verdict": "LEAN",
        "display_k_line": tracked_line,
        "display_odds": -108,
        "display_book": "FanDuel",
        "display_adj_ev": 0.07,
        "game_time": "2026-05-06T22:10:00+00:00",
    }]
    return {"date": "2026-05-06", "pitchers": [pitcher]}


def _alternative_market_evidence(provider, *, observed_at="2026-05-06T21:45:00+00:00"):
    book = "fanduel" if provider == "therundown" else "draftkings"
    return {
        "slate_date": "2026-05-06",
        "pitcher": "Tarik Skubal",
        "normalized_pitcher": "tarik skubal",
        "side": "over",
        "provider": provider,
        "k_line": 6.5,
        "game_time": "2026-05-06T22:10:00+00:00",
        "observed_at": observed_at,
        "book_count": 1,
        "books_seen": [book],
        "toward_pick_count": 0,
        "away_from_pick_count": 0,
        "reversal_book_count": 0,
        "volatile_book_count": 0,
        "metadata": {"freshness_status": "fresh"},
    }


def _current_alternative_lock():
    return {
        "dedupe_key": "2026-05-06:tarik skubal:over",
        "slate_date": "2026-05-06",
        "normalized_pitcher": "tarik skubal",
        "side": "over",
        "locked_k_line": 6.5,
        "locked_odds": -108,
        "locked_book": "FanDuel",
        "game_time": "2026-05-06T22:10:00+00:00",
        "status_at_capture": "due_now",
        "observed_at": "2026-05-06T21:45:00Z",
        "locked_at": "2026-05-06T21:45:00Z",
        "should_lock_at": "2026-05-06T21:40:00+00:00",
        "minutes_until_start": 25,
        "source_artifact_path": "https://example.netlify.app/.netlify/functions/get-artifact?type=today",
        "source_artifact_sha256": "b" * 64,
        "metadata": {"team": "DET", "opp_team": "BOS"},
    }


def _mixed_alternative_artifact_payload():
    payload = _alternative_artifact_payload()
    second = json.loads(json.dumps(payload["pitchers"][0]))
    second.update({
        "pitcher": "Second Pitcher",
        "team": "SEA",
        "opp_team": "OAK",
        "therundown_event_id": "tr-game-second",
    })
    second["tracked_picks"][0]["pitcher"] = "Second Pitcher"
    payload["pitchers"].append(second)
    return payload


def test_alternative_candidate_uses_official_posture_not_available_evidence():
    payload = _alternative_artifact_payload()
    without_evidence = build_live_events_to_supabase._alternative_tracked_candidates(
        slate_date="2026-05-06", payload=payload, market_pick_evidence_rows=[],
    )
    with_propline = build_live_events_to_supabase._alternative_tracked_candidates(
        slate_date="2026-05-06",
        payload=payload,
        market_pick_evidence_rows=[{"provider": "propline", "normalized_pitcher": "tarik skubal", "side": "over"}],
    )
    assert without_evidence[0][0]["provider_posture"] == "therundown"
    assert with_propline[0][0]["provider_posture"] == "therundown"
    assert without_evidence[0][0]["candidate_identity"] == with_propline[0][0]["candidate_identity"]

    unsupported = _alternative_artifact_payload(odds_source="boltodds")
    assert build_live_events_to_supabase._alternative_tracked_candidates(
        slate_date="2026-05-06", payload=unsupported, market_pick_evidence_rows=[],
    ) == []

    explicit_therundown = _alternative_artifact_payload(
        odds_source="therundown+propline", market_source_mode="therundown",
    )
    assert build_live_events_to_supabase._alternative_tracked_candidates(
        slate_date="2026-05-06", payload=explicit_therundown, market_pick_evidence_rows=[],
    ) == []

    combined_fallback = _alternative_artifact_payload(
        odds_source="therundown", market_source_mode="therundown_propline",
    )
    assert build_live_events_to_supabase._alternative_tracked_candidates(
        slate_date="2026-05-06", payload=combined_fallback, market_pick_evidence_rows=[],
    ) == []

    matching_combined = _alternative_artifact_payload(
        odds_source="therundown+propline", market_source_mode="therundown_propline",
    )
    candidates = build_live_events_to_supabase._alternative_tracked_candidates(
        slate_date="2026-05-06", payload=matching_combined, market_pick_evidence_rows=[],
    )
    assert candidates[0][0]["provider_posture"] == "therundown_propline"

    conflicting = _alternative_artifact_payload(
        odds_source="therundown", market_source_mode="boltodds_propline",
    )
    assert build_live_events_to_supabase._alternative_tracked_candidates(
        slate_date="2026-05-06", payload=conflicting, market_pick_evidence_rows=[],
    ) == []

    for malformed_line in (True, float("nan"), float("inf"), -1):
        malformed = _alternative_artifact_payload(tracked_line=malformed_line)
        assert build_live_events_to_supabase._alternative_tracked_candidates(
            slate_date="2026-05-06", payload=malformed, market_pick_evidence_rows=[],
        ) == []


def test_alternative_evaluation_uses_real_side_payload_and_normalized_game_instant():
    payload = _alternative_artifact_payload()
    candidate, pitcher, tracked = build_live_events_to_supabase._alternative_tracked_candidates(
        slate_date="2026-05-06", payload=payload, market_pick_evidence_rows=[],
    )[0]
    evaluation_pitcher, evaluation_pick = build_live_events_to_supabase._alternative_evaluation_inputs(
        pitcher=pitcher, tracked_pick=tracked, candidate=candidate,
    )
    assert evaluation_pick["win_prob"] == 0.61
    assert evaluation_pick["display_verdict"] == "LEAN"
    assert evaluation_pick["locked_adj_ev"] == 0.07
    assert evaluation_pitcher["game_time"] == "2026-05-06T22:10:00+00:00"
    assert evaluation_pitcher["k_line"] == 6.5
    assert evaluation_pitcher["best_over_odds"] == -108
    assert evaluation_pitcher["best_over_book"] == "FanDuel"

    tracked["display_odds"] = -108.5
    malformed_pitcher, malformed_pick = build_live_events_to_supabase._alternative_evaluation_inputs(
        pitcher=pitcher, tracked_pick=tracked, candidate=candidate,
    )
    assert malformed_pick["odds"] is None
    assert malformed_pitcher["best_over_odds"] is None


def test_alternative_evaluation_never_pairs_locked_line_with_current_line_odds():
    payload = _alternative_artifact_payload(tracked_line=7.5)
    candidate, pitcher, tracked = build_live_events_to_supabase._alternative_tracked_candidates(
        slate_date="2026-05-06", payload=payload, market_pick_evidence_rows=[],
    )[0]
    evaluation_pitcher, evaluation_pick = build_live_events_to_supabase._alternative_evaluation_inputs(
        pitcher=pitcher, tracked_pick=tracked, candidate=candidate,
    )
    features = build_live_events_to_supabase.derive_runtime_features(
        pitcher=evaluation_pitcher,
        pick=evaluation_pick,
        market_evidence={},
        observed_at="2026-05-06T18:00:00+00:00",
    )
    assert evaluation_pitcher["k_line"] == 7.5
    assert evaluation_pitcher["best_over_odds"] == -108
    assert evaluation_pitcher["best_under_odds"] is None
    assert features["model_no_vig_gap"] is None


def test_alternative_sidecar_passes_canonical_side_payload_with_tracked_overlay(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _alternative_artifact_payload()
    writer = Mock()
    writer.select_rows.side_effect = [[], []]

    with patch.object(
        build_live_events_to_supabase,
        "evaluate_alternative_pick",
        wraps=build_live_events_to_supabase.evaluate_alternative_pick,
    ) as evaluate:
        result = build_live_events_to_supabase._write_alternative_pick_selection_state(
            writer=writer,
            slate_date="2026-05-06",
            payload=payload,
            snapshot_rows=[],
            market_pick_evidence_rows=[],
            observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
            artifact_source="test",
            source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
            source_artifact_byte_sha256="b" * 64,
            operational_pick_locks={"skipped": True, "reason": "disabled"},
            market_line_build={"skipped": True, "reason": "fresh"},
        )

    call = evaluate.call_args.kwargs
    assert call["pick"]["win_prob"] == 0.61
    assert call["pick"]["display_verdict"] == "LEAN"
    assert call["pick"]["locked_adj_ev"] == 0.07
    assert call["pitcher"]["best_over_odds"] == -108
    assert result["provisional_rows"] == 1


def test_alternative_sidecar_binds_numeric_current_market_line_ids_in_one_read(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    observed_at = build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00")
    payload = _alternative_artifact_payload(
        odds_source="therundown+propline",
        market_source_mode="therundown_propline",
    )
    pitcher = payload["pitchers"][0]
    pitcher.pop("therundown_event_id")
    pitcher.pop("propline_event_id")
    pitcher["source_snapshot_ids"] = [9007199254740992, 9007199254740993]
    pitcher.update({
        "best_over_odds": -115, "best_under_odds": -105, "avg_ip": 5.8,
        "recent_start_count": 5, "season_k9": 9.4, "recent_k9": 9.7, "career_k9": 9.1,
    })
    pitcher["ev_over"].update({"edge": 0.035, "adj_ev": 0.09, "win_prob": 0.56})
    pitcher["tracked_picks"][0].update({"display_verdict": "FIRE 1u", "display_adj_ev": 0.09})
    writer = Mock()
    current_lines = [
        {
            "id": 9007199254740992, "slate_date": "2026-05-06", "provider": "therundown",
            "provider_event_id": "tr-game-current", "normalized_player_name": "tarik skubal",
            "market_key": "pitcher_strikeouts", "line": 6.5,
            "game_time": "2026-05-06T22:10:00Z", "over_snapshot_id": THERUNDOWN_OVER_SNAPSHOT_ID,
            "under_snapshot_id": THERUNDOWN_UNDER_SNAPSHOT_ID,
        },
        {
            "id": 9007199254740993, "slate_date": "2026-05-06", "provider": "propline",
            "provider_event_id": "pl-game-current", "normalized_player_name": "tarik skubal",
            "market_key": "pitcher_strikeouts", "line": 6.5,
            "game_time": "2026-05-06T22:10:00Z", "over_snapshot_id": PROPLINE_OVER_SNAPSHOT_ID,
            "under_snapshot_id": PROPLINE_UNDER_SNAPSHOT_ID,
        },
    ]
    writer.select_rows.side_effect = [[], [], current_lines]
    with patch.object(
        build_live_events_to_supabase,
        "evaluate_alternative_pick",
        wraps=build_live_events_to_supabase.evaluate_alternative_pick,
    ) as evaluate:
        result = build_live_events_to_supabase._write_alternative_pick_selection_state(
            writer=writer,
            slate_date="2026-05-06",
            payload=payload,
            snapshot_rows=[
                {
                    "id": THERUNDOWN_OVER_SNAPSHOT_ID, "provider": "therundown", "provider_event_id": "tr-game-current",
                    "normalized_player_name": "tarik skubal", "side": "over", "line": 6.5,
                    "bookmaker_key": "fanduel", "american_odds": -108,
                    "game_time": "2026-05-06T22:10:00Z", "observed_at": observed_at.isoformat(),
                },
                {
                    "id": PROPLINE_OVER_SNAPSHOT_ID, "provider": "propline", "provider_event_id": "pl-game-current",
                    "normalized_player_name": "tarik skubal", "side": "over", "line": 6.5,
                    "bookmaker_key": "draftkings", "american_odds": -110,
                    "game_time": "2026-05-06T22:10:00Z", "observed_at": observed_at.isoformat(),
                },
            ],
            market_pick_evidence_rows=[
                _alternative_market_evidence("therundown", observed_at=observed_at.isoformat()),
                _alternative_market_evidence("propline", observed_at=observed_at.isoformat()),
            ],
            live_market_display_rows=[{
                "slate_date": "2026-05-06", "normalized_pitcher": "tarik skubal", "side": "over",
                "k_line": 6.5, "provider": "therundown_propline",
                "game_time": "2026-05-06T22:10:00Z", "game_state": "scheduled",
                "observed_at": observed_at.isoformat(), "updated_at": observed_at.isoformat(),
                "latest_snapshot_at": observed_at.isoformat(), "freshness_status": "fresh",
                "source_artifact_path": "https://example.netlify.app/.netlify/functions/get-artifact?type=today",
                "source_artifact_sha256": "b" * 64, "best_is_off_market": False,
            }],
            observed_at=observed_at,
            artifact_source="https://example.netlify.app/.netlify/functions/get-artifact?type=today",
            source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
            source_artifact_byte_sha256="b" * 64,
            operational_pick_locks={"skipped": True, "reason": "disabled"},
            market_line_build={"skipped": True, "reason": "fresh"},
        )

    assert result["provisional_rows"] == 1
    persisted = writer.upsert_rows.call_args.args[1][0]
    assert persisted["evidence_observation_ids"] == [THERUNDOWN_OVER_SNAPSHOT_ID, PROPLINE_OVER_SNAPSHOT_ID]
    assert persisted["evidence_observation_count"] == 2
    assert persisted["selection_status"] == "selected"
    evaluation_evidence = evaluate.call_args.kwargs["market_evidence"]
    assert evaluation_evidence["provider"] == "therundown_propline"
    assert evaluation_evidence["observation_ids"] == [THERUNDOWN_OVER_SNAPSHOT_ID, PROPLINE_OVER_SNAPSHOT_ID]
    assert evaluation_evidence["freshness_status"] == "fresh"
    assert writer.select_rows.call_count == 3
    mapping_params = writer.select_rows.call_args_list[2].args[1]
    assert writer.select_rows.call_args_list[2].args[0] == "current_market_lines"
    assert mapping_params["slate_date"] == "eq.2026-05-06"
    assert mapping_params["id"] == 'in.("9007199254740992","9007199254740993")'
    assert set(mapping_params["select"].split(",")) == {
        "id", "slate_date", "provider", "provider_event_id", "normalized_player_name",
        "market_key", "line", "game_time", "over_snapshot_id", "under_snapshot_id",
    }
    assert writer.select_rows.call_args_list[2].kwargs["attempts"] == 1
    assert 0 < writer.select_rows.call_args_list[2].kwargs["timeout_seconds"] <= 5


@pytest.mark.parametrize(("overrides", "snapshot_id"), [
    ({"normalized_player_name": "wrong pitcher"}, THERUNDOWN_OVER_SNAPSHOT_ID),
    ({"line": 7.5}, THERUNDOWN_OVER_SNAPSHOT_ID),
    ({"game_time": "2026-05-06T23:10:00Z"}, THERUNDOWN_OVER_SNAPSHOT_ID),
    ({"market_key": "batter_hits"}, THERUNDOWN_OVER_SNAPSHOT_ID),
    ({"provider": "boltodds"}, THERUNDOWN_OVER_SNAPSHOT_ID),
    ({"over_snapshot_id": ""}, THERUNDOWN_OVER_SNAPSHOT_ID),
    ({"over_snapshot_id": "not-a-uuid"}, "not-a-uuid"),
    (None, THERUNDOWN_OVER_SNAPSHOT_ID),
])
def test_alternative_sidecar_does_not_bind_invalid_numeric_current_market_line_mapping(monkeypatch, overrides, snapshot_id):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _alternative_artifact_payload()
    pitcher = payload["pitchers"][0]
    pitcher.pop("therundown_event_id")
    pitcher.pop("propline_event_id")
    pitcher["source_snapshot_ids"] = [101]
    mapping = {
        "id": 101, "slate_date": "2026-05-06", "provider": "therundown",
        "provider_event_id": "tr-game-current", "normalized_player_name": "tarik skubal",
        "market_key": "pitcher_strikeouts", "line": 6.5,
        "game_time": "2026-05-06T22:10:00Z", "over_snapshot_id": THERUNDOWN_OVER_SNAPSHOT_ID,
        "under_snapshot_id": THERUNDOWN_UNDER_SNAPSHOT_ID,
    }
    writer = Mock()
    writer.select_rows.side_effect = [[], [], [] if overrides is None else [{**mapping, **overrides}]]

    result = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload=payload,
        snapshot_rows=[{
            "id": snapshot_id, "provider": "therundown", "provider_event_id": "tr-game-current",
            "normalized_player_name": "tarik skubal", "side": "over", "line": 6.5,
            "bookmaker_key": "fanduel", "american_odds": -108,
            "game_time": "2026-05-06T22:10:00Z", "observed_at": "2026-05-06T18:00:00Z",
        }],
        market_pick_evidence_rows=[_alternative_market_evidence("therundown", observed_at="2026-05-06T18:00:00Z")],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        artifact_source="test",
        source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": True, "reason": "disabled"},
        market_line_build={"skipped": True, "reason": "fresh"},
    )

    assert result["provisional_rows"] == 1
    persisted = writer.upsert_rows.call_args.args[1][0]
    assert persisted["evidence_observation_ids"] == []
    assert persisted["evidence_observation_count"] == 0
    assert persisted["evidence_freshness_status"] == "pending"
    assert writer.select_rows.call_count == 3


def test_alternative_sidecar_does_not_bind_numeric_mapping_to_the_wrong_side_uuid(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _alternative_artifact_payload()
    pitcher = payload["pitchers"][0]
    pitcher.pop("therundown_event_id")
    pitcher.pop("propline_event_id")
    pitcher["source_snapshot_ids"] = [101]
    writer = Mock()
    writer.select_rows.side_effect = [[], [], [{
        "id": 101, "slate_date": "2026-05-06", "provider": "therundown",
        "provider_event_id": "tr-game-current", "normalized_player_name": "tarik skubal",
        "market_key": "pitcher_strikeouts", "line": 6.5,
        "game_time": "2026-05-06T22:10:00Z", "over_snapshot_id": THERUNDOWN_UNDER_SNAPSHOT_ID,
        "under_snapshot_id": THERUNDOWN_UNDER_SNAPSHOT_ID,
    }]]

    result = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload=payload,
        snapshot_rows=[{
            "id": THERUNDOWN_UNDER_SNAPSHOT_ID, "provider": "therundown", "provider_event_id": "tr-game-current",
            "normalized_player_name": "tarik skubal", "side": "under", "line": 6.5,
            "bookmaker_key": "fanduel", "american_odds": -108,
            "game_time": "2026-05-06T22:10:00Z", "observed_at": "2026-05-06T18:00:00Z",
        }],
        market_pick_evidence_rows=[_alternative_market_evidence("therundown", observed_at="2026-05-06T18:00:00Z")],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        artifact_source="test",
        source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": True, "reason": "disabled"},
        market_line_build={"skipped": True, "reason": "fresh"},
    )

    persisted = writer.upsert_rows.call_args.args[1][0]
    assert result["provisional_rows"] == 1
    assert persisted["evidence_observation_ids"] == []
    assert persisted["evidence_freshness_status"] == "pending"


def test_alternative_current_line_id_preserves_adjacent_bigints_and_rejects_unsafe_floats():
    first = 9007199254740992
    second = first + 1
    assert build_live_events_to_supabase._alternative_current_line_id(first) == str(first)
    assert build_live_events_to_supabase._alternative_current_line_id(second) == str(second)
    assert build_live_events_to_supabase._alternative_current_line_id(first) != build_live_events_to_supabase._alternative_current_line_id(second)
    assert build_live_events_to_supabase._alternative_current_line_id(9007199254740991.0) == "9007199254740991"
    assert build_live_events_to_supabase._alternative_current_line_id(float(first)) is None
    assert build_live_events_to_supabase._alternative_current_line_id(2**63) is None


@pytest.mark.parametrize("mapping_result", [
    RuntimeError("mapping read failed"),
    {"not": "a list"},
    [{"id": 101}],
    [
        {
            "id": 101, "slate_date": "2026-05-06", "provider": "therundown",
            "provider_event_id": "tr-game-current", "normalized_player_name": "tarik skubal",
            "market_key": "pitcher_strikeouts", "line": 6.5,
            "game_time": "2026-05-06T22:10:00Z", "over_snapshot_id": THERUNDOWN_OVER_SNAPSHOT_ID,
            "under_snapshot_id": THERUNDOWN_UNDER_SNAPSHOT_ID,
        },
        {
            "id": 101, "slate_date": "2026-05-06", "provider": "therundown",
            "provider_event_id": "different-event", "normalized_player_name": "tarik skubal",
            "market_key": "pitcher_strikeouts", "line": 6.5,
            "game_time": "2026-05-06T22:10:00Z", "over_snapshot_id": THERUNDOWN_OVER_SNAPSHOT_ID,
            "under_snapshot_id": THERUNDOWN_UNDER_SNAPSHOT_ID,
        },
    ],
])
def test_alternative_sidecar_stops_on_invalid_numeric_mapping_read(monkeypatch, mapping_result):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _alternative_artifact_payload()
    pitcher = payload["pitchers"][0]
    pitcher.pop("therundown_event_id")
    pitcher.pop("propline_event_id")
    pitcher["source_snapshot_ids"] = [101]
    writer = Mock()
    writer.select_rows.side_effect = [[], [], mapping_result]

    result = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload=payload,
        snapshot_rows=[],
        market_pick_evidence_rows=[],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        artifact_source="test",
        source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": True, "reason": "disabled"},
        market_line_build={"skipped": True, "reason": "fresh"},
    )

    assert result["reason"] == "failed"
    assert writer.select_rows.call_count == 3
    assert writer.select_rows.call_args_list[2].kwargs["attempts"] == 1
    writer.upsert_rows.assert_not_called()
    writer.insert_ignore_rows.assert_not_called()


def test_alternative_sidecar_stops_before_numeric_mapping_read_when_budget_is_exhausted(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _alternative_artifact_payload()
    pitcher = payload["pitchers"][0]
    pitcher.pop("therundown_event_id")
    pitcher.pop("propline_event_id")
    pitcher["source_snapshot_ids"] = [101]
    writer = Mock()
    writer.select_rows.side_effect = [[], []]

    with patch.object(
        build_live_events_to_supabase.time,
        "monotonic",
        side_effect=[0.0, 0.0, 0.0, 5.0],
    ):
        result = build_live_events_to_supabase._write_alternative_pick_selection_state(
            writer=writer,
            slate_date="2026-05-06",
            payload=payload,
            snapshot_rows=[],
            market_pick_evidence_rows=[],
            observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
            artifact_source="test",
            source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
            source_artifact_byte_sha256="b" * 64,
            operational_pick_locks={"skipped": True, "reason": "disabled"},
            market_line_build={"skipped": True, "reason": "fresh"},
        )

    assert result["reason"] == "timeout"
    assert writer.select_rows.call_count == 2
    writer.upsert_rows.assert_not_called()
    writer.insert_ignore_rows.assert_not_called()


def test_alternative_sidecar_contains_unhashable_artifact_event_id_during_numeric_prescan(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _alternative_artifact_payload()
    pitcher = payload["pitchers"][0]
    pitcher["source_snapshot_ids"] = [101]
    pitcher["therundown_event_id"] = []
    writer = Mock()

    result = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload=payload,
        snapshot_rows=[],
        market_pick_evidence_rows=[],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        artifact_source="test",
        source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": True, "reason": "disabled"},
        market_line_build={"skipped": True, "reason": "fresh"},
    )

    assert result["skipped"] is True
    assert result["reason"] == "failed"
    writer.upsert_rows.assert_not_called()
    writer.insert_ignore_rows.assert_not_called()


def test_alternative_pick_selection_mode_fails_closed_except_exact_record(monkeypatch):
    for value in (None, "", "RECORDING", "shadow", " true "):
        if value is None:
            monkeypatch.delenv("ALTERNATIVE_PICK_SELECTION_MODE", raising=False)
        else:
            monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", value)
        assert build_live_events_to_supabase._alternative_pick_selection_mode() == "off"

    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", " ReCoRd ")
    assert build_live_events_to_supabase._alternative_pick_selection_mode() == "record"


def test_bundle_version_unset_or_blank_defaults_to_v1(monkeypatch):
    monkeypatch.delenv("ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION", raising=False)
    assert build_live_events_to_supabase._alternative_pick_selection_bundle_version() == "v1"
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION", "   ")
    assert build_live_events_to_supabase._alternative_pick_selection_bundle_version() == "v1"


def test_bundle_version_accepts_exact_v1_and_v2(monkeypatch):
    for value, expected in (("v1", "v1"), (" V2 ", "v2")):
        monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION", value)
        assert build_live_events_to_supabase._alternative_pick_selection_bundle_version() == expected


def test_worker_module_import_never_touches_v2_recorder_chain():
    repo_root = Path(__file__).resolve().parents[1]
    script = r'''
import importlib.abc
import sys

class BlockV2Recorder(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "market_infra.alternative_pick_recording_v2":
            raise RuntimeError("V2 recorder chain must not load during worker startup")
        return None

sys.meta_path.insert(0, BlockV2Recorder())
from scripts import build_live_events_to_supabase
assert "market_infra.alternative_pick_recording_v2" not in sys.modules
'''
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def test_explicit_invalid_bundle_version_skips_sidecar_cycle(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION", "v3")
    result = build_live_events_to_supabase._dispatch_alternative_pick_selection_state(
        writer=Mock(), slate_date="2026-07-22", payload={}, snapshot_rows=[],
        provider_heartbeats=[], market_pick_evidence_rows=[], live_market_display_rows=[],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-07-22T18:00:00+00:00"),
        artifact_source="test", source_payload_sha256="a" * 64,
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={}, market_line_build={}, shadow_pipeline_timing={}, ready_to_bet_write={},
    )
    assert result == {"skipped": True, "reason": "invalid_bundle_version", "rows": 0}


def test_v2_capable_deploy_with_default_gate_writes_zero_v2_rows(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    monkeypatch.delenv("ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION", raising=False)
    with patch.object(build_live_events_to_supabase, "_write_alternative_pick_selection_state", return_value={"version": "v1"}) as v1, patch.object(build_live_events_to_supabase, "_load_alternative_pick_v2_recorder") as v2:
        result = build_live_events_to_supabase._dispatch_alternative_pick_selection_state(
            writer=Mock(), slate_date="2026-07-22", payload={}, snapshot_rows=[], provider_heartbeats=[],
            market_pick_evidence_rows=[], live_market_display_rows=[], observed_at=build_live_events_to_supabase.datetime.now(build_live_events_to_supabase.timezone.utc),
            artifact_source="test", source_payload_sha256="a" * 64, source_artifact_byte_sha256="b" * 64,
            operational_pick_locks={}, market_line_build={}, shadow_pipeline_timing={}, ready_to_bet_write={},
        )
    assert result == {"version": "v1"}
    v1.assert_called_once()
    v2.assert_not_called()


def test_v1_dispatch_retains_existing_arguments_and_output(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION", "v1")
    expected = {"skipped": False, "rows": 1}
    with patch.object(build_live_events_to_supabase, "_write_alternative_pick_selection_state", return_value=expected) as v1:
        result = build_live_events_to_supabase._dispatch_alternative_pick_selection_state(
            writer=Mock(), slate_date="2026-07-22", payload={},
            snapshot_rows=[{"id": "legacy"}],
            v2_snapshot_rows=[{"id": "v2-filtered"}],
            provider_heartbeats=[{"provider": "therundown"}],
            market_pick_evidence_rows=[{"broad": True}], live_market_display_rows=[{"persisted": True}], observed_at=build_live_events_to_supabase.datetime.now(build_live_events_to_supabase.timezone.utc),
            artifact_source="test", source_payload_sha256="a" * 64, source_artifact_byte_sha256="b" * 64,
            operational_pick_locks={"locks": 1}, market_line_build={"market": 1}, shadow_pipeline_timing={"timing": 1}, ready_to_bet_write={"ready": 1},
        )
    assert result is expected
    assert v1.call_args.kwargs["snapshot_rows"] == [{"id": "legacy"}]
    assert v1.call_args.kwargs["market_pick_evidence_rows"] == [{"broad": True}]
    assert v1.call_args.kwargs["live_market_display_rows"] == [{"persisted": True}]


def test_v2_writer_receives_existing_snapshots_and_heartbeats_without_new_provider_reads(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION", "v2")
    legacy_snapshots = [{"id": "legacy"}]
    snapshots, heartbeats = [{"id": "v2-filtered"}], [{"provider": "therundown"}]
    v2 = Mock(return_value={"version": "v2"})
    with patch.object(build_live_events_to_supabase, "_load_alternative_pick_v2_recorder", return_value=v2):
        result = build_live_events_to_supabase._dispatch_alternative_pick_selection_state(
            writer=Mock(), slate_date="2026-07-22", payload={},
            snapshot_rows=legacy_snapshots, v2_snapshot_rows=snapshots,
            provider_heartbeats=heartbeats,
            market_pick_evidence_rows=[{"broad": True}], live_market_display_rows=[{"persisted": True}], observed_at=build_live_events_to_supabase.datetime.now(build_live_events_to_supabase.timezone.utc),
            artifact_source="test", source_payload_sha256="a" * 64, source_artifact_byte_sha256="b" * 64,
            operational_pick_locks={}, market_line_build={}, shadow_pipeline_timing={}, ready_to_bet_write={},
        )
    assert result == {"version": "v2"}
    assert v2.call_args.kwargs["snapshot_rows"] is snapshots
    assert v2.call_args.kwargs["provider_heartbeats"] is heartbeats
    assert "market_pick_evidence_rows" not in v2.call_args.kwargs
    assert "live_market_display_rows" not in v2.call_args.kwargs


@pytest.mark.parametrize("error,reason", [(ValueError("bad payload"), "failed"), (TimeoutError(), "timeout")])
def test_v2_dispatcher_contains_recorder_exception_without_touching_other_work(monkeypatch, error, reason):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION", "v2")
    writer = Mock()
    v2 = Mock(side_effect=error)
    with patch.object(
        build_live_events_to_supabase,
        "_load_alternative_pick_v2_recorder",
        return_value=v2,
    ):
        result = build_live_events_to_supabase._dispatch_alternative_pick_selection_state(
            writer=writer, slate_date="2026-07-22", payload={}, snapshot_rows=[],
            provider_heartbeats=[], market_pick_evidence_rows=[], live_market_display_rows=[],
            observed_at=build_live_events_to_supabase.datetime.now(build_live_events_to_supabase.timezone.utc),
            artifact_source="test", source_payload_sha256="a" * 64,
            source_artifact_byte_sha256="b" * 64,
            operational_pick_locks={}, market_line_build={}, shadow_pipeline_timing={}, ready_to_bet_write={},
        )
    assert result["skipped"] is True
    assert result["reason"] == reason
    assert result["rows"] == 0
    assert len(result["warning"]) <= 200
    writer.assert_not_called()


def test_explicit_v2_contains_lazy_recorder_import_failure(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION", "v2")
    monkeypatch.setattr(
        build_live_events_to_supabase,
        "_load_alternative_pick_v2_recorder",
        Mock(side_effect=ValueError("invalid V2 manifest")),
    )

    result = build_live_events_to_supabase._dispatch_alternative_pick_selection_state(
        writer=Mock(), slate_date="2026-07-22", payload={}, snapshot_rows=[],
        provider_heartbeats=[], market_pick_evidence_rows=[], live_market_display_rows=[],
        observed_at=build_live_events_to_supabase.datetime.now(build_live_events_to_supabase.timezone.utc),
        artifact_source="test", source_payload_sha256="a" * 64,
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={}, market_line_build={}, shadow_pipeline_timing={}, ready_to_bet_write={},
    )

    assert result["skipped"] is True
    assert result["reason"] == "failed"
    assert result["rows"] == 0
    assert len(result["warning"]) <= 200


def test_explicit_v2_import_time_counts_against_sidecar_budget(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION", "v2")
    recorder = Mock(return_value={"version": "v2"})
    monkeypatch.setattr(
        build_live_events_to_supabase,
        "_load_alternative_pick_v2_recorder",
        Mock(return_value=recorder),
    )
    monkeypatch.setattr(
        build_live_events_to_supabase.time,
        "monotonic",
        Mock(side_effect=[100.0, 102.0]),
    )

    result = build_live_events_to_supabase._dispatch_alternative_pick_selection_state(
        writer=Mock(), slate_date="2026-07-22", payload={}, snapshot_rows=[],
        provider_heartbeats=[], market_pick_evidence_rows=[], live_market_display_rows=[],
        observed_at=build_live_events_to_supabase.datetime.now(build_live_events_to_supabase.timezone.utc),
        artifact_source="test", source_payload_sha256="a" * 64,
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={}, market_line_build={}, shadow_pipeline_timing={}, ready_to_bet_write={},
        budget_seconds=5.0,
    )

    assert result == {"version": "v2"}
    assert recorder.call_args.kwargs["budget_seconds"] == pytest.approx(3.0)


def test_alternative_sidecar_off_performs_no_state_reads_or_writes(monkeypatch):
    monkeypatch.delenv("ALTERNATIVE_PICK_SELECTION_MODE", raising=False)
    writer = Mock()

    result = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload={"date": "2026-05-06", "pitchers": []},
        snapshot_rows=[],
        market_pick_evidence_rows=[],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        artifact_source="https://example.netlify.app/.netlify/functions/get-artifact?type=today",
        source_payload_sha256="a" * 64,
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": True, "reason": "disabled"},
        market_line_build={"skipped": True, "reason": "fresh"},
    )

    assert result == {"skipped": True, "reason": "disabled", "rows": 0}
    writer.select_rows.assert_not_called()
    writer.upsert_rows.assert_not_called()
    writer.insert_ignore_rows.assert_not_called()


def test_alternative_sidecar_filters_pass_before_any_state_read_or_write(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _alternative_artifact_payload()
    payload["pitchers"][0]["tracked_picks"][0].update({
        "display_verdict": "PASS",
        "locked_verdict": "FIRE 1u",
        "verdict": "FIRE 2u",
    })
    writer = Mock()

    result = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload=payload,
        snapshot_rows=[],
        market_pick_evidence_rows=[],
        live_market_display_rows=[],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        artifact_source="https://example.netlify.app/.netlify/functions/get-artifact?type=today",
        source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": True, "reason": "disabled"},
        market_line_build={"skipped": True, "reason": "fresh"},
    )

    assert result == {"skipped": True, "reason": "no_candidates", "rows": 0}
    writer.select_rows.assert_not_called()
    writer.upsert_rows.assert_not_called()
    writer.insert_ignore_rows.assert_not_called()


def test_alternative_sidecar_defensively_skips_ineligible_evaluations(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _alternative_artifact_payload()
    writer = Mock()
    writer.select_rows.side_effect = [[], []]
    ineligible = {
        "eligible": False,
        "selector_fingerprint": "c" * 64,
        "family_states": {"base": {"state": "pending", "reason_codes": ["pass_verdict"]}},
        "family_count": 0,
        "lane": None,
        "selection_status": "pending",
        "reason_codes": ("pass_verdict",),
        "normalized_inputs": {"official_verdict": "PASS", "odds": -108, "official_book": "fanduel"},
    }

    with patch.object(build_live_events_to_supabase, "evaluate_alternative_pick", return_value=ineligible):
        result = build_live_events_to_supabase._write_alternative_pick_selection_state(
            writer=writer,
            slate_date="2026-05-06",
            payload=payload,
            snapshot_rows=[],
            market_pick_evidence_rows=[],
            live_market_display_rows=[],
            observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
            artifact_source="https://example.netlify.app/.netlify/functions/get-artifact?type=today",
            source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
            source_artifact_byte_sha256="b" * 64,
            operational_pick_locks={"skipped": True, "reason": "disabled"},
            market_line_build={"skipped": True, "reason": "fresh"},
        )

    assert result["rows"] == 0
    writer.upsert_rows.assert_not_called()
    writer.insert_ignore_rows.assert_not_called()


def test_alternative_sidecar_uses_narrow_allowlisted_state_and_lock_reads(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _alternative_artifact_payload()
    writer = Mock()
    writer.select_rows.side_effect = [[], []]

    result = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload=payload,
        snapshot_rows=[],
        market_pick_evidence_rows=[],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        artifact_source="https://private.example/get-artifact?token=never-return",
        source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": True, "reason": "disabled"},
        market_line_build={"skipped": True, "reason": "fresh"},
    )

    state_params = writer.select_rows.call_args_list[0].args[1]
    assert state_params["slate_date"] == "eq.2026-05-06"
    assert state_params["bundle_id"] == f"eq.{build_live_events_to_supabase.BUNDLE_ID}"
    assert "candidate_became_current_at" in state_params["select"]
    lock_params = writer.select_rows.call_args_list[1].args[1]
    assert lock_params["slate_date"] == "eq.2026-05-06"
    assert lock_params["dedupe_key"].startswith('in.("')
    assert "source_artifact_sha256" in lock_params["select"]
    assert "locked_odds" in lock_params["select"]
    assert "locked_book" in lock_params["select"]
    assert "artifact_source" not in result
    assert "private.example" not in repr(result)


def test_public_lock_and_artifact_summaries_use_strict_privacy_allowlists():
    summary = build_live_events_to_supabase._public_operational_lock_summary({
        "skipped": True,
        "reason": "write_failed",
        "rows": 0,
        "error": "https://private.example/locks?token=never-return",
        "future_private": {"secret": "never-return"},
        "lock_rows": [{"source_artifact_path": "https://private.example/today"}],
        "dispatch": {
            "skipped": True,
            "reason": "dispatch_failed",
            "error": "credential=never-return",
        },
    })
    assert summary == {
        "skipped": True,
        "reason": "write_failed",
        "rows": 0,
        "dispatch": {"skipped": True, "reason": "dispatch_failed"},
    }
    assert "private.example" not in repr(summary)
    assert "never-return" not in repr(summary)
    assert build_live_events_to_supabase._public_artifact_source(
        "https://private.example/get-artifact?token=never-return"
    ) == "remote"
    assert build_live_events_to_supabase._public_artifact_source(
        "C:/private/worktree/dashboard/data/processed/today.json"
    ) == build_live_events_to_supabase.APPROVED_ARTIFACT_PATH


def test_alternative_sidecar_skips_each_failed_prerequisite_without_io(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _alternative_artifact_payload()
    variants = (
        ({"skipped": True, "reason": "write_failed"}, {"skipped": True, "reason": "disabled"}, {"skipped": True, "reason": "fresh"}, {"skipped": True, "reason": "disabled"}),
        ({"skipped": True, "reason": "failed"}, {"skipped": True, "reason": "disabled"}, {"skipped": True, "reason": "fresh"}, {"skipped": True, "reason": "disabled"}),
        ({"skipped": True, "reason": "disabled"}, {"skipped": True, "reason": "write_failed"}, {"skipped": True, "reason": "fresh"}, {"skipped": True, "reason": "disabled"}),
        ({"skipped": True, "reason": "disabled"}, {"skipped": True, "reason": "disabled"}, {"skipped": False, "current": {"reason": "build_failed"}}, {"skipped": True, "reason": "disabled"}),
        ({"skipped": True, "reason": "disabled"}, {"skipped": True, "reason": "disabled"}, {"skipped": True, "reason": "fresh"}, {"skipped": True, "reason": "write_failed"}),
    )
    for locks, timing, market, ready_write in variants:
        writer = Mock()
        result = build_live_events_to_supabase._write_alternative_pick_selection_state(
            writer=writer,
            slate_date="2026-05-06",
            payload=payload,
            snapshot_rows=[],
            market_pick_evidence_rows=[],
            observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
            artifact_source="test",
            source_payload_sha256="a" * 64,
            source_artifact_byte_sha256="b" * 64,
            operational_pick_locks=locks,
            shadow_pipeline_timing=timing,
            market_line_build=market,
            ready_to_bet_write=ready_write,
        )
        assert result == {"skipped": True, "reason": "prerequisite_failed", "rows": 0}
        writer.select_rows.assert_not_called()
        writer.upsert_rows.assert_not_called()
        writer.insert_ignore_rows.assert_not_called()


def test_alternative_sidecar_reports_timeout_after_evaluation_even_without_rows(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _alternative_artifact_payload()
    writer = Mock()
    writer.select_rows.side_effect = [[], []]
    with patch.object(
        build_live_events_to_supabase.time,
        "monotonic",
        side_effect=[0.0, 0.5, 1.0, 6.0],
    ):
        result = build_live_events_to_supabase._write_alternative_pick_selection_state(
            writer=writer,
            slate_date="2026-05-06",
            payload=payload,
            snapshot_rows=[],
            market_pick_evidence_rows=[],
            observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T23:00:00+00:00"),
            artifact_source="test",
            source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
            source_artifact_byte_sha256="b" * 64,
            operational_pick_locks={"skipped": True, "reason": "disabled"},
            market_line_build={"skipped": True, "reason": "fresh"},
        )
    assert result["reason"] == "timeout"
    writer.upsert_rows.assert_not_called()
    writer.insert_ignore_rows.assert_not_called()


def test_alternative_sidecar_skips_colliding_candidate_identities(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _alternative_artifact_payload()
    second = dict(payload["pitchers"][0]["tracked_picks"][0])
    second["display_k_line"] = 7.5
    payload["pitchers"][0]["tracked_picks"].append(second)
    writer = Mock()

    result = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload=payload,
        snapshot_rows=[],
        market_pick_evidence_rows=[],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        artifact_source="test",
        source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": True, "reason": "disabled"},
        market_line_build={"skipped": True, "reason": "fresh"},
    )
    assert result == {"skipped": True, "reason": "candidate_key_collision", "rows": 0, "collisions": 1}
    writer.select_rows.assert_not_called()
    writer.upsert_rows.assert_not_called()
    writer.insert_ignore_rows.assert_not_called()


def test_alternative_sidecar_skips_doubleheader_lock_key_collisions(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _alternative_artifact_payload()
    second_pitcher = json.loads(json.dumps(payload["pitchers"][0]))
    second_pitcher["team"] = "BOS"
    second_pitcher["opp_team"] = "DET"
    second_pitcher["game_time"] = "2026-05-07T01:10:00Z"
    second_pitcher["tracked_picks"][0]["game_time"] = "2026-05-07T01:10:00Z"
    payload["pitchers"].append(second_pitcher)
    writer = Mock()

    result = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload=payload,
        snapshot_rows=[],
        market_pick_evidence_rows=[],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        artifact_source="test",
        source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": True, "reason": "disabled"},
        market_line_build={"skipped": True, "reason": "fresh"},
    )
    assert result == {"skipped": True, "reason": "candidate_key_collision", "rows": 0, "collisions": 1}
    writer.select_rows.assert_not_called()


def test_alternative_sidecar_stops_after_first_read_failure(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    writer = Mock()
    writer.select_rows.side_effect = RuntimeError("database password=do-not-leak")
    pitcher = _fire_pitcher()
    pitcher["odds_source"] = "therundown"
    pitcher["tracked_picks"] = [{
        "pitcher": "Tarik Skubal",
        "side": "over",
        "display_verdict": "FIRE 1u",
        "display_k_line": 6.5,
        "display_odds": -110,
        "display_adj_ev": 0.09,
        "game_time": "2026-05-06T22:10:00Z",
    }]

    result = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload={"date": "2026-05-06", "pitchers": [pitcher]},
        snapshot_rows=[],
        market_pick_evidence_rows=[],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        artifact_source="https://example.netlify.app/.netlify/functions/get-artifact?type=today",
        source_payload_sha256="a" * 64,
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": True, "reason": "disabled"},
        market_line_build={"skipped": True, "reason": "fresh"},
    )

    assert result["skipped"] is True
    assert result["reason"] == "failed"
    assert "do-not-leak" not in result["warning"]
    assert writer.select_rows.call_count == 1
    writer.upsert_rows.assert_not_called()
    writer.insert_ignore_rows.assert_not_called()


def test_alternative_sidecar_stops_after_lock_read_failure(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _alternative_artifact_payload()
    writer = Mock()
    writer.select_rows.side_effect = [[], RuntimeError("private lock read failure")]

    result = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload=payload,
        snapshot_rows=[],
        market_pick_evidence_rows=[],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        artifact_source="test",
        source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": True, "reason": "disabled"},
        market_line_build={"skipped": True, "reason": "fresh"},
    )

    assert result["reason"] == "failed"
    assert "private lock" not in result["warning"]
    assert writer.select_rows.call_count == 2
    writer.upsert_rows.assert_not_called()
    writer.insert_ignore_rows.assert_not_called()


def test_alternative_sidecar_contains_evaluation_exception(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    writer = Mock()
    writer.select_rows.side_effect = [[], []]
    pitcher = _fire_pitcher()
    pitcher["odds_source"] = "therundown"
    pitcher["tracked_picks"] = [{
        "pitcher": "Tarik Skubal",
        "side": "over",
        "display_verdict": "FIRE 1u",
        "display_k_line": 6.5,
        "display_odds": -110,
        "display_adj_ev": 0.09,
        "game_time": "2026-05-06T22:10:00Z",
    }]
    with patch.object(
        build_live_events_to_supabase,
        "evaluate_alternative_pick",
        side_effect=RuntimeError("evaluation secret=never-return"),
    ):
        result = build_live_events_to_supabase._write_alternative_pick_selection_state(
            writer=writer,
            slate_date="2026-05-06",
            payload={"date": "2026-05-06", "pitchers": [pitcher]},
            snapshot_rows=[],
            market_pick_evidence_rows=[],
            observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
            artifact_source="https://example.netlify.app/.netlify/functions/get-artifact?type=today",
            source_payload_sha256="a" * 64,
            source_artifact_byte_sha256="b" * 64,
            operational_pick_locks={"skipped": True, "reason": "disabled"},
            market_line_build={"skipped": True, "reason": "fresh"},
        )

    assert result["reason"] == "failed"
    assert "never-return" not in result["warning"]
    writer.upsert_rows.assert_not_called()
    writer.insert_ignore_rows.assert_not_called()


def test_alternative_sidecar_stops_after_first_write_failure(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _alternative_artifact_payload()
    writer = Mock()
    writer.select_rows.side_effect = [[], []]
    writer.upsert_rows.side_effect = RuntimeError("private provisional write failure")

    result = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload=payload,
        snapshot_rows=[],
        market_pick_evidence_rows=[],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        artifact_source="test",
        source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": True, "reason": "disabled"},
        market_line_build={"skipped": True, "reason": "fresh"},
    )

    assert result["reason"] == "failed"
    assert "private provisional" not in result["warning"]
    writer.upsert_rows.assert_called_once()
    writer.insert_ignore_rows.assert_not_called()


def test_alternative_sidecar_never_writes_duplicate_provisional_candidates(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    writer = Mock()
    writer.select_rows.side_effect = [[], []]
    pitcher = _fire_pitcher()
    pitcher["odds_source"] = "therundown"
    pick = {
        "pitcher": "Tarik Skubal",
        "side": "over",
        "display_verdict": "FIRE 1u",
        "display_k_line": 6.5,
        "display_odds": -110,
        "display_adj_ev": 0.09,
        "game_time": "2026-05-06T22:10:00Z",
    }
    pitcher["tracked_picks"] = [pick, dict(pick)]
    payload = {"date": "2026-05-06", "pitchers": [pitcher]}

    result = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload=payload,
        snapshot_rows=[],
        market_pick_evidence_rows=[],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        artifact_source="https://example.netlify.app/.netlify/functions/get-artifact?type=today",
        source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": True, "reason": "disabled"},
        market_line_build={"skipped": True, "reason": "fresh"},
    )

    assert result["provisional_rows"] == 1
    assert writer.upsert_rows.call_args.args[1] and len(writer.upsert_rows.call_args.args[1]) == 1


def test_alternative_sidecar_inserts_current_cycle_freeze_without_provisional_update(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    observed_at = build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T21:45:00+00:00")
    payload = _alternative_artifact_payload(
        odds_source="therundown+propline",
        market_source_mode="therundown_propline",
    )
    lock = _current_alternative_lock()
    candidate = build_live_events_to_supabase._alternative_tracked_candidates(
        slate_date="2026-05-06", payload=payload, market_pick_evidence_rows=[],
    )[0][0]
    existing = {
        "slate_date": candidate["slate_date"],
        "game_identity": candidate["game_identity"],
        "candidate_identity": candidate["candidate_identity"],
        "candidate_became_current_at": "2026-05-06T21:15:00Z",
        "normalized_pitcher": candidate["normalized_pitcher"],
        "side": candidate["side"],
        "bundle_id": build_live_events_to_supabase.BUNDLE_ID,
        "checkpoint": "provisional",
        "observed_at": "2026-05-06T21:30:00Z",
        "game_time": candidate["game_time"],
    }
    writer = Mock()
    writer.select_rows.side_effect = [[existing], [lock]]

    result = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload=payload,
        snapshot_rows=[
            {
                "id": "tr-1", "provider": "therundown", "provider_event_id": "tr-game-current",
                "normalized_player_name": "tarik skubal", "side": "over", "line": 6.5,
                "bookmaker_key": "fanduel", "american_odds": -108,
                "game_time": "2026-05-06T22:10:00Z", "observed_at": "2026-05-06T21:20:00Z",
            },
            {
                "id": "pl-1", "provider": "propline", "provider_event_id": "pl-game-current",
                "normalized_player_name": "tarik skubal", "side": "over", "line": 6.5,
                "bookmaker_key": "draftkings", "american_odds": -110,
                "game_time": "2026-05-06T22:10:00Z", "observed_at": "2026-05-06T21:30:00Z",
            },
        ],
        market_pick_evidence_rows=[
            _alternative_market_evidence("therundown"),
            _alternative_market_evidence("propline"),
        ],
        observed_at=observed_at,
        artifact_source=lock["source_artifact_path"],
        source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": False, "lock_rows": [lock], "inserted_lock_rows": []},
        market_line_build={"skipped": True, "reason": "fresh"},
    )

    assert result["provisional_rows"] == 0
    assert result["frozen_rows"] == 1
    writer.upsert_rows.assert_not_called()
    writer.insert_ignore_rows.assert_called_once_with(
        "alternative_pick_selection_state",
        ANY,
        on_conflict="slate_date,game_identity,normalized_pitcher,side,bundle_id,checkpoint",
        timeout_seconds=ANY,
    )
    frozen = writer.insert_ignore_rows.call_args.args[1][0]
    assert frozen["official_odds"] == lock["locked_odds"] == -108
    assert frozen["official_book"] == lock["locked_book"] == "FanDuel"


def test_alternative_sidecar_freezes_pending_at_lock_and_never_changes_it_next_cycle(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _alternative_artifact_payload()
    lock = _current_alternative_lock()
    observed_at = build_live_events_to_supabase.datetime.fromisoformat(
        "2026-05-06T21:45:00+00:00"
    )
    writer = Mock()
    writer.select_rows.side_effect = [[], [lock]]

    first = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload=payload,
        snapshot_rows=[{
            "id": "tr-1", "provider": "therundown",
            "provider_event_id": "tr-game-current",
            "normalized_player_name": "tarik skubal", "side": "over",
            "line": 6.5, "bookmaker_key": "fanduel", "american_odds": -108,
            "game_time": "2026-05-06T22:10:00Z",
            "observed_at": "2026-05-06T21:45:00Z",
        }],
        market_pick_evidence_rows=[_alternative_market_evidence("therundown")],
        observed_at=observed_at,
        artifact_source=lock["source_artifact_path"],
        source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": False, "lock_rows": [lock]},
        market_line_build={"skipped": True, "reason": "fresh"},
    )

    assert first["frozen_rows"] == 1
    assert first["provisional_rows"] == 0
    frozen = writer.insert_ignore_rows.call_args.args[1][0]
    assert frozen["selection_status"] == "pending"
    assert frozen["evidence_observation_ids"] == ["tr-1"]
    assert frozen["evidence_observation_count"] == 1
    assert frozen["family_states"]
    assert "evidence_immature" in frozen["reason_codes"]
    assert "freeze_evidence_pending" in frozen["reason_codes"]

    later_writer = Mock()
    later_writer.select_rows.side_effect = [[frozen], [lock]]
    second = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=later_writer,
        slate_date="2026-05-06",
        payload=payload,
        snapshot_rows=[
            {
                "id": "tr-1", "provider": "therundown",
                "provider_event_id": "tr-game-current",
                "normalized_player_name": "tarik skubal", "side": "over",
                "line": 6.5, "bookmaker_key": "fanduel", "american_odds": -108,
                "game_time": "2026-05-06T22:10:00Z",
                "observed_at": "2026-05-06T21:48:00Z",
            },
            {
                "id": "tr-2", "provider": "therundown",
                "provider_event_id": "tr-game-current",
                "normalized_player_name": "tarik skubal", "side": "over",
                "line": 6.5, "bookmaker_key": "fanduel", "american_odds": -112,
                "game_time": "2026-05-06T22:10:00Z",
                "observed_at": "2026-05-06T21:49:00Z",
            },
        ],
        market_pick_evidence_rows=[_alternative_market_evidence(
            "therundown", observed_at="2026-05-06T21:50:00Z",
        )],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat(
            "2026-05-06T21:50:00+00:00"
        ),
        artifact_source=lock["source_artifact_path"],
        source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": False, "lock_rows": [lock]},
        market_line_build={"skipped": True, "reason": "fresh"},
    )

    assert second["rows"] == 0
    later_writer.insert_ignore_rows.assert_not_called()
    later_writer.upsert_rows.assert_not_called()
    assert frozen["selection_status"] == "pending"


def test_alternative_sidecar_does_not_mutate_provisional_after_an_old_lock(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _alternative_artifact_payload()
    lock = _current_alternative_lock()
    writer = Mock()
    writer.select_rows.side_effect = [[], [lock]]

    result = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload=payload,
        snapshot_rows=[],
        market_pick_evidence_rows=[],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat(
            "2026-05-06T21:50:00+00:00"
        ),
        artifact_source=lock["source_artifact_path"],
        source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": False, "lock_rows": [lock]},
        market_line_build={"skipped": True, "reason": "fresh"},
    )

    assert result["rows"] == 0
    writer.insert_ignore_rows.assert_not_called()
    writer.upsert_rows.assert_not_called()


def test_alternative_sidecar_writes_frozen_rows_before_provisional_rows(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _mixed_alternative_artifact_payload()
    lock = _current_alternative_lock()
    writes = []
    writer = Mock()
    writer.select_rows.side_effect = [[], [lock]]
    writer.insert_ignore_rows.side_effect = lambda *args, **kwargs: writes.append("frozen")
    writer.upsert_rows.side_effect = lambda *args, **kwargs: writes.append("provisional")

    result = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload=payload,
        snapshot_rows=[],
        market_pick_evidence_rows=[],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat(
            "2026-05-06T21:45:00+00:00"
        ),
        artifact_source=lock["source_artifact_path"],
        source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": False, "lock_rows": [lock]},
        market_line_build={"skipped": True, "reason": "fresh"},
    )

    assert result["frozen_rows"] == 1
    assert result["provisional_rows"] == 1
    assert writes == ["frozen", "provisional"]


def test_alternative_sidecar_frozen_failure_prevents_provisional_write(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _mixed_alternative_artifact_payload()
    lock = _current_alternative_lock()
    writer = Mock()
    writer.select_rows.side_effect = [[], [lock]]
    writer.insert_ignore_rows.side_effect = RuntimeError("private frozen failure")

    result = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload=payload,
        snapshot_rows=[],
        market_pick_evidence_rows=[],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat(
            "2026-05-06T21:45:00+00:00"
        ),
        artifact_source=lock["source_artifact_path"],
        source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": False, "lock_rows": [lock]},
        market_line_build={"skipped": True, "reason": "fresh"},
    )

    assert result["reason"] == "failed"
    assert "private frozen" not in result["warning"]
    writer.insert_ignore_rows.assert_called_once()
    writer.upsert_rows.assert_not_called()


def test_alternative_sidecar_preserves_freeze_when_provisional_write_fails(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _mixed_alternative_artifact_payload()
    lock = _current_alternative_lock()
    writes = []
    writer = Mock()
    writer.select_rows.side_effect = [[], [lock]]
    writer.insert_ignore_rows.side_effect = lambda *args, **kwargs: writes.append("frozen")
    writer.upsert_rows.side_effect = RuntimeError("private provisional failure")

    result = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload=payload,
        snapshot_rows=[],
        market_pick_evidence_rows=[],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat(
            "2026-05-06T21:45:00+00:00"
        ),
        artifact_source=lock["source_artifact_path"],
        source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": False, "lock_rows": [lock]},
        market_line_build={"skipped": True, "reason": "fresh"},
    )

    assert result["reason"] == "failed"
    assert "private provisional" not in result["warning"]
    assert writes == ["frozen"]
    writer.insert_ignore_rows.assert_called_once()
    writer.upsert_rows.assert_called_once()


def test_alternative_sidecar_timeout_between_batches_stops_after_freeze(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    payload = _mixed_alternative_artifact_payload()
    lock = _current_alternative_lock()
    clock = {"now": 0.0}
    writer = Mock()
    writer.select_rows.side_effect = [[], [lock]]
    writer.insert_ignore_rows.side_effect = lambda *args, **kwargs: clock.update(now=6.0)
    monkeypatch.setattr(
        build_live_events_to_supabase.time, "monotonic", lambda: clock["now"],
    )

    result = build_live_events_to_supabase._write_alternative_pick_selection_state(
        writer=writer,
        slate_date="2026-05-06",
        payload=payload,
        snapshot_rows=[],
        market_pick_evidence_rows=[],
        observed_at=build_live_events_to_supabase.datetime.fromisoformat(
            "2026-05-06T21:45:00+00:00"
        ),
        artifact_source=lock["source_artifact_path"],
        source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
        source_artifact_byte_sha256="b" * 64,
        operational_pick_locks={"skipped": False, "lock_rows": [lock]},
        market_line_build={"skipped": True, "reason": "fresh"},
    )

    assert result["reason"] == "timeout"
    writer.insert_ignore_rows.assert_called_once()
    writer.upsert_rows.assert_not_called()


def test_alternative_sidecar_freezes_unbound_or_stale_raw_evidence_as_pending(monkeypatch):
    monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", "record")
    observed_at = build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T21:45:00+00:00")
    payload = _alternative_artifact_payload(
        odds_source="therundown+propline",
        market_source_mode="therundown_propline",
    )
    valid_snapshots = [
        {
            "id": "tr-1", "provider": "therundown", "provider_event_id": "tr-game-current",
            "normalized_player_name": "tarik skubal", "side": "over", "line": 6.5,
            "bookmaker_key": "fanduel", "american_odds": -108,
            "game_time": "2026-05-06T22:10:00Z", "observed_at": observed_at.isoformat(),
        },
        {
            "id": "pl-1", "provider": "propline", "provider_event_id": "pl-game-current",
            "normalized_player_name": "tarik skubal", "side": "over", "line": 6.5,
            "bookmaker_key": "draftkings", "american_odds": -110,
            "game_time": "2026-05-06T22:10:00Z", "observed_at": observed_at.isoformat(),
        },
    ]
    valid_evidence = [
        _alternative_market_evidence("therundown"),
        _alternative_market_evidence("propline"),
    ]
    cases = (
        (
            valid_snapshots,
            [valid_evidence[0], {**valid_evidence[1], "metadata": {"freshness_status": "stale"}}],
        ),
        ([{**row, "line": 7.5} for row in valid_snapshots], valid_evidence),
        ([{**row, "provider_event_id": "old-game"} for row in valid_snapshots], valid_evidence),
        ([{**row, "provider": "boltodds"} for row in valid_snapshots], valid_evidence),
    )

    for snapshots, evidence in cases:
        writer = Mock()
        writer.select_rows.side_effect = [[], [_current_alternative_lock()]]
        result = build_live_events_to_supabase._write_alternative_pick_selection_state(
            writer=writer,
            slate_date="2026-05-06",
            payload=payload,
            snapshot_rows=snapshots,
            market_pick_evidence_rows=evidence,
            observed_at=observed_at,
            artifact_source=_current_alternative_lock()["source_artifact_path"],
            source_payload_sha256=build_live_events_to_supabase.canonical_payload_sha256(payload),
            source_artifact_byte_sha256="b" * 64,
            operational_pick_locks={"skipped": False, "lock_rows": [_current_alternative_lock()]},
            market_line_build={"skipped": True, "reason": "fresh"},
        )

        assert result["provisional_rows"] == 0
        assert result["frozen_rows"] == 1
        writer.upsert_rows.assert_not_called()
        writer.insert_ignore_rows.assert_called_once()
        frozen = writer.insert_ignore_rows.call_args.args[1][0]
        assert frozen["selection_status"] == "pending"
        assert "freeze_evidence_pending" in frozen["reason_codes"]


@pytest.mark.parametrize(
    "mode,bundle",
    [
        (None, "v2"),
        ("record", None),
        ("record", "v1"),
    ],
)
def test_worker_calls_alternative_sidecar_only_after_prior_work_when_v2_import_is_broken(
    tmp_path, monkeypatch, mode, bundle,
):
    calls = []
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "market_feed_heartbeats": [],
        "game_reminder_state": [],
    })

    if mode is None:
        monkeypatch.delenv("ALTERNATIVE_PICK_SELECTION_MODE", raising=False)
    else:
        monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_MODE", mode)
    if bundle is None:
        monkeypatch.delenv("ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION", raising=False)
    else:
        monkeypatch.setenv("ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION", bundle)

    original_evidence = build_live_events_to_supabase.build_market_pick_evidence_rows
    original_display = build_live_events_to_supabase.build_live_market_display_rows
    original_coordinate = build_live_events_to_supabase.coordinate_notification_rows

    def evidence(**kwargs):
        calls.append("evidence")
        return original_evidence(**kwargs)

    def display(**kwargs):
        calls.append("display")
        return original_display(**kwargs)

    def notifications(*args, **kwargs):
        calls.append("notifications")
        return original_coordinate(*args, **kwargs)

    def locks(**kwargs):
        calls.append("locks")
        return {"skipped": True, "reason": "disabled"}

    def timing(**kwargs):
        calls.append("timing")
        return {"skipped": True, "reason": "disabled"}

    def market(**kwargs):
        calls.append("market")
        return {"skipped": True, "reason": "fresh"}

    def alternative(**kwargs):
        calls.append("alternative")
        assert kwargs["live_market_display_rows"] == []
        return {"skipped": True, "reason": "disabled", "rows": 0}

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(build_live_events_to_supabase, "build_market_pick_evidence_rows", side_effect=evidence),
        patch.object(build_live_events_to_supabase, "build_live_market_display_rows", side_effect=display),
        patch.object(build_live_events_to_supabase, "coordinate_notification_rows", side_effect=notifications),
        patch.object(build_live_events_to_supabase, "_write_operational_pick_locks", side_effect=locks),
        patch.object(build_live_events_to_supabase, "_write_shadow_pipeline_timing", side_effect=timing),
        patch.object(build_live_events_to_supabase, "_build_shadow_market_state", side_effect=market),
        patch.object(build_live_events_to_supabase, "_write_alternative_pick_selection_state", side_effect=alternative),
        patch.object(
            build_live_events_to_supabase,
            "_load_alternative_pick_v2_recorder",
            side_effect=RuntimeError("invalid V2 manifest"),
        ) as v2_loader,
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert calls == [
        "evidence", "display", "notifications", "locks", "timing", "market", "alternative",
    ]
    v2_loader.assert_not_called()
    assert result["alternative_pick_selection"] == {"skipped": True, "reason": "disabled", "rows": 0}
    assert result["artifact_source"] == build_live_events_to_supabase.APPROVED_ARTIFACT_PATH


def test_worker_writes_state_and_notification_events(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])

    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["live_pick_state"] == 1
    assert result["notification_events"] == 1
    assert result["line_movement_events"] == 0
    assert result["game_reminders"] == 0
    assert result["state_rows"][0]["source_artifact_sha256"]
    assert Path(result["state_rows"][0]["source_artifact_path"]).name == "today.json"
    assert result["shadow_pipeline_timing"]["pipeline_runs"] == 1
    assert result["shadow_pipeline_timing"]["pick_lock_observations"] == 1
    writer.upsert_rows.assert_any_call(
        "live_pick_state",
        result["state_rows"],
        on_conflict="slate_date,normalized_pitcher,side",
    )
    writer.insert_ignore_rows.assert_any_call(
        "notification_events",
        result["notification_rows"],
        on_conflict="dedupe_key",
    )
    upsert_tables = [call.args[0] for call in writer.upsert_rows.call_args_list]
    assert upsert_tables == [
        "line_movement_events",
        "market_pick_evidence",
        "live_market_display_state",
        "shadow_notification_candidates",
        "game_reminder_state",
        "live_pick_state",
        "shadow_pipeline_runs",
    ]
    writer.insert_ignore_rows.assert_any_call(
        "shadow_pick_lock_observations",
        result["shadow_pipeline_timing"]["pick_lock_observation_rows"],
        on_conflict="dedupe_key",
    )


def test_ready_to_bet_shadow_record_preserves_notification_rows(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_READY_TO_BET_SHADOW", "record")
    pitcher = _fire_pitcher()
    pitcher["quality_gate_level"] = "clean"
    pitcher["ev_over"]["quality_gate_level"] = "clean"
    today = _write_artifact(tmp_path, [pitcher])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "accepted_bets": [],
        "market_snapshots": [{
            "id": "snapshot-1",
            "provider": "propline",
            "provider_event_id": "game-1",
            "normalized_player_name": "tarik skubal",
            "player_name": "Tarik Skubal",
            "bookmaker_key": "fanduel",
            "side": "over",
            "line": 6.5,
            "american_odds": 105,
            "observed_at": "2026-05-06T18:00:00+00:00",
        }],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat(
                "2026-05-06T18:00:00+00:00"
            ),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert [row["event_type"] for row in result["notification_rows"]] == ["new_fire_pick"]
    assert result["ready_to_bet_shadow"]["candidate_count"] == 1
    assert result["state_rows"][0]["metadata"]["decision_state"] == "ready"
    writer.insert_ignore_rows.assert_any_call(
        "shadow_notification_candidates",
        result["ready_to_bet_candidate_rows"],
        on_conflict="dedupe_key",
    )
    notification_event_rows = next(
        call.args[1]
        for call in writer.insert_ignore_rows.call_args_list
        if call.args[0] == "notification_events"
    )
    assert notification_event_rows == result["notification_rows"]
    assert not any(row.get("candidate_type") == "ready_to_bet" for row in notification_event_rows)
    assert (
        result["shadow_pipeline_timing"]["pipeline_run_row"]["metadata"]
        ["ready_to_bet_shadow"]["mode"]
        == "record"
    )


def test_ready_to_bet_shadow_accepted_bet_read_failure_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_READY_TO_BET_SHADOW", "record")
    pitcher = _fire_pitcher()
    pitcher["quality_gate_level"] = "clean"
    pitcher["ev_over"]["quality_gate_level"] = "clean"
    today = _write_artifact(tmp_path, [pitcher])
    writer = Mock()

    def select_rows(table, params):
        if table == "accepted_bets":
            raise RuntimeError("accepted bets unavailable")
        if table == "market_snapshots":
            return []
        return []

    writer.select_rows.side_effect = select_rows

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat(
                "2026-05-06T18:00:00+00:00"
            ),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["ready_to_bet_shadow"]["accepted_bets_available"] is False
    assert result["ready_to_bet_candidate_rows"] == []
    assert [row["event_type"] for row in result["notification_rows"]] == ["new_fire_pick"]
    notification_event_rows = next(
        call.args[1]
        for call in writer.insert_ignore_rows.call_args_list
        if call.args[0] == "notification_events"
    )
    assert notification_event_rows == result["notification_rows"]


def test_ready_to_bet_shadow_candidate_write_failure_stays_retryable(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_READY_TO_BET_SHADOW", "record")
    pitcher = _fire_pitcher()
    pitcher["quality_gate_level"] = "clean"
    pitcher["ev_over"]["quality_gate_level"] = "clean"
    today = _write_artifact(tmp_path, [pitcher])
    failed_writer = _writer_with_selects({
        "live_pick_state": [],
        "accepted_bets": [],
        "market_snapshots": [{
            "id": "snapshot-1",
            "provider": "propline",
            "provider_event_id": "game-1",
            "normalized_player_name": "tarik skubal",
            "player_name": "Tarik Skubal",
            "bookmaker_key": "fanduel",
            "side": "over",
            "line": 6.5,
            "american_odds": 105,
            "observed_at": "2026-05-06T18:00:00+00:00",
        }],
        "game_reminder_state": [],
    })

    def fail_ready_candidate_write(table, rows, **kwargs):
        if table == "shadow_notification_candidates" and rows and rows[0].get("candidate_type") == "ready_to_bet":
            raise RuntimeError("shadow candidate write unavailable")
        return []

    failed_writer.insert_ignore_rows.side_effect = fail_ready_candidate_write
    observed_at = build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00")

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=failed_writer),
        patch.object(build_live_events_to_supabase, "_now_utc", return_value=observed_at),
    ):
        failed_result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert failed_result["ready_to_bet_shadow_write"]["reason"] == "write_failed"
    assert failed_result["state_rows"][0]["metadata"]["decision_state"] == "ready"
    assert failed_result["state_rows"][0]["metadata"]["candidate_write_pending"] is True
    assert failed_result["state_rows"][0]["metadata"]["candidate_write_failure_reason"] == "write_failed"
    assert set(failed_result["ready_to_bet_shadow"]["state_counts"]) <= {
        "ready",
        "watching",
        "started",
        "locked",
        "logged",
    }
    persisted_rows = next(
        call.args[1]
        for call in failed_writer.upsert_rows.call_args_list
        if call.args[0] == "live_pick_state"
    )
    assert persisted_rows[0]["metadata"]["decision_state"] == "ready"
    assert persisted_rows[0]["metadata"]["candidate_write_pending"] is True

    retry_writer = _writer_with_selects({
        "live_pick_state": persisted_rows,
        "accepted_bets": [],
        "market_snapshots": [{
            "id": "snapshot-2",
            "provider": "propline",
            "provider_event_id": "game-1",
            "normalized_player_name": "tarik skubal",
            "player_name": "Tarik Skubal",
            "bookmaker_key": "fanduel",
            "side": "over",
            "line": 6.5,
            "american_odds": 105,
            "observed_at": "2026-05-06T18:00:00+00:00",
        }],
        "game_reminder_state": [],
    })
    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=retry_writer),
        patch.object(build_live_events_to_supabase, "_now_utc", return_value=observed_at),
    ):
        retry_result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert retry_result["ready_to_bet_shadow"]["candidate_count"] == 1
    assert retry_result["state_rows"][0]["metadata"]["decision_state"] == "ready"
    assert "candidate_write_pending" not in retry_result["state_rows"][0]["metadata"]
    assert "candidate_write_failure_reason" not in retry_result["state_rows"][0]["metadata"]
    retry_writer.insert_ignore_rows.assert_any_call(
        "shadow_notification_candidates",
        retry_result["ready_to_bet_candidate_rows"],
        on_conflict="dedupe_key",
    )


def test_ready_to_bet_shadow_default_off_skips_accepted_bet_read(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVE_READY_TO_BET_SHADOW", raising=False)
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "game_reminder_state": [],
    })

    with patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["ready_to_bet_shadow"]["mode"] == "off"
    assert not any(call.args[0] == "accepted_bets" for call in writer.select_rows.call_args_list)
    assert not any(
        call.args[0] == "shadow_notification_candidates"
        for call in writer.insert_ignore_rows.call_args_list
    )


def test_ready_to_bet_shadow_unknown_mode_fails_closed_to_off(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_READY_TO_BET_SHADOW", "send")
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "game_reminder_state": [],
    })

    with patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["ready_to_bet_shadow"]["mode"] == "off"
    assert not any(call.args[0] == "accepted_bets" for call in writer.select_rows.call_args_list)
    assert not any(
        call.args[0] == "shadow_notification_candidates"
        for call in writer.insert_ignore_rows.call_args_list
    )


def test_env_int_invalid_value_falls_back(monkeypatch):
    monkeypatch.setenv("LIVE_TEST_INVALID_INT", "bad")

    assert build_live_events_to_supabase._env_int("LIVE_TEST_INVALID_INT", default=7) == 7


def test_notification_coordinator_default_is_noop_for_reminders(tmp_path, monkeypatch):
    monkeypatch.delenv("LIVE_NOTIFICATION_COORDINATOR_MODE", raising=False)
    monkeypatch.delenv("LIVE_NOTIFICATION_GROUP_START_WINDOWS", raising=False)
    today = _write_artifact(tmp_path, [
        _fire_pitcher(game_time="2026-05-06T18:20:00Z", pitcher="Sandy Alcantara"),
        _fire_pitcher(game_time="2026-05-06T18:24:00Z", pitcher="Spencer Strider"),
    ])
    writer = _writer_with_selects({
        "live_pick_state": [
            _previous_fire_state("Sandy Alcantara", game_time="2026-05-06T18:20:00Z"),
            _previous_fire_state("Spencer Strider", game_time="2026-05-06T18:24:00Z"),
        ],
        "market_snapshots": [],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert [row["event_type"] for row in result["notification_rows"]] == [
        "game_reminder_due",
        "game_reminder_due",
    ]
    assert result["notification_events"] == 2
    assert result["notification_coordinator"]["mode"] == "off"
    writer.insert_ignore_rows.assert_any_call(
        "notification_events",
        result["notification_rows"],
        on_conflict="dedupe_key",
    )


def test_notification_coordinator_shadow_records_summary_only(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_NOTIFICATION_COORDINATOR_MODE", "shadow")
    monkeypatch.setenv("LIVE_NOTIFICATION_GROUP_START_WINDOWS", "true")
    today = _write_artifact(tmp_path, [
        _fire_pitcher(game_time="2026-05-06T18:20:00Z", pitcher="Sandy Alcantara"),
        _fire_pitcher(game_time="2026-05-06T18:24:00Z", pitcher="Spencer Strider"),
    ])
    writer = _writer_with_selects({
        "live_pick_state": [
            _previous_fire_state("Sandy Alcantara", game_time="2026-05-06T18:20:00Z"),
            _previous_fire_state("Spencer Strider", game_time="2026-05-06T18:24:00Z"),
        ],
        "market_snapshots": [],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert [row["event_type"] for row in result["notification_rows"]] == [
        "game_reminder_due",
        "game_reminder_due",
    ]
    assert [row["event_type"] for row in result["notification_coordinator_shadow_rows"]] == [
        "start_window_digest"
    ]
    assert result["notification_coordinator"]["input_count"] == 2
    assert result["notification_coordinator"]["grouped_count"] == 1
    assert (
        result["shadow_pipeline_timing"]["pipeline_run_row"]["metadata"]["notification_coordinator"]["mode"]
        == "shadow"
    )


def test_notification_coordinator_grouped_inserts_digest(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_NOTIFICATION_COORDINATOR_MODE", "grouped")
    monkeypatch.setenv("LIVE_NOTIFICATION_GROUP_START_WINDOWS", "true")
    today = _write_artifact(tmp_path, [
        _fire_pitcher(game_time="2026-05-06T18:20:00Z", pitcher="Sandy Alcantara"),
        _fire_pitcher(game_time="2026-05-06T18:24:00Z", pitcher="Spencer Strider"),
    ])
    writer = _writer_with_selects({
        "live_pick_state": [
            _previous_fire_state("Sandy Alcantara", game_time="2026-05-06T18:20:00Z"),
            _previous_fire_state("Spencer Strider", game_time="2026-05-06T18:24:00Z"),
        ],
        "market_snapshots": [],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert [row["event_type"] for row in result["notification_rows"]] == [
        "start_window_digest"
    ]
    assert result["notification_events"] == 1
    writer.insert_ignore_rows.assert_any_call(
        "notification_events",
        result["notification_rows"],
        on_conflict="dedupe_key",
    )


def test_worker_keeps_shadow_timing_failures_from_breaking_live_layer(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "game_reminder_state": [],
    })
    writer.upsert_rows.side_effect = [
        [],
        [],
        [],
        [],
        [],
        [],
        RuntimeError("shadow table missing"),
    ]

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["live_pick_state"] == 1
    assert result["shadow_pipeline_timing"]["skipped"] is True
    assert "shadow table missing" in result["shadow_pipeline_timing"]["error"]


def test_worker_skips_operational_lock_ledger_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("ENABLE_SUPABASE_LOCK_LEDGER", raising=False)
    pitcher = _fire_pitcher(game_time="2026-05-06T18:30:00Z")
    pitcher["tracked_picks"] = [{
        "pitcher": "Tarik Skubal",
        "side": "over",
        "display_verdict": "FIRE 1u",
        "display_k_line": 6.5,
        "display_odds": -110,
        "display_adj_ev": 0.09,
        "locked_at": None,
        "game_time": "2026-05-06T18:30:00Z",
    }]
    today = _write_artifact(tmp_path, [pitcher])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "market_feed_heartbeats": [],
        "game_reminder_state": [],
    })

    with patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["operational_pick_locks"] == {"skipped": True, "reason": "disabled"}
    insert_tables = [call.args[0] for call in writer.insert_ignore_rows.call_args_list]
    assert "operational_pick_locks" not in insert_tables


def test_worker_writes_operational_lock_rows_when_enabled(tmp_path, monkeypatch):
    pitcher = _fire_pitcher(game_time="2026-05-06T18:30:00Z")
    pitcher["tracked_picks"] = [{
        "pitcher": "Tarik Skubal",
        "side": "over",
        "display_verdict": "FIRE 1u",
        "display_k_line": 6.5,
        "display_odds": -110,
        "display_adj_ev": 0.09,
        "locked_at": None,
        "game_time": "2026-05-06T18:30:00Z",
    }]
    today = _write_artifact(tmp_path, [pitcher])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "market_feed_heartbeats": [],
        "game_reminder_state": [],
    })
    monkeypatch.setenv("ENABLE_SUPABASE_LOCK_LEDGER", "true")

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:02:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["operational_pick_locks"]["skipped"] is False
    assert result["operational_pick_locks"]["rows"] == 1
    assert "lock_rows" not in result["operational_pick_locks"]
    assert "inserted_lock_rows" not in result["operational_pick_locks"]
    lock_call = next(
        call
        for call in writer.insert_ignore_rows.call_args_list
        if call.args[0] == "operational_pick_locks"
    )
    assert lock_call.kwargs["on_conflict"] == "dedupe_key"
    lock_rows = lock_call.args[1]
    assert lock_rows[0]["dedupe_key"] == "2026-05-06:tarik skubal:over"
    assert lock_rows[0]["status_at_capture"] == "due_now"


def test_operational_lock_write_dispatches_lock_workflow_for_new_rows(monkeypatch):
    writer = Mock()
    writer.insert_ignore_rows.return_value = [{"dedupe_key": "2026-05-06:tarik skubal:over"}]
    pitcher = _fire_pitcher(game_time="2026-05-06T18:30:00Z")
    pitcher["tracked_picks"] = [{
        "pitcher": "Tarik Skubal",
        "side": "over",
        "display_verdict": "FIRE 1u",
        "display_k_line": 6.5,
        "display_odds": -110,
        "display_adj_ev": 0.09,
        "locked_at": None,
        "game_time": "2026-05-06T18:30:00Z",
    }]
    monkeypatch.setenv("ENABLE_SUPABASE_LOCK_LEDGER", "true")
    monkeypatch.setenv("ENABLE_LOCK_ONLY_WORKFLOW_DISPATCH", "true")

    with patch.object(
        build_live_events_to_supabase,
        "_dispatch_lock_only_workflow",
        return_value={"skipped": False, "status_code": 204},
    ) as dispatch:
        result = build_live_events_to_supabase._write_operational_pick_locks(
            writer=writer,
            slate_date="2026-05-06",
            payload={"pitchers": [pitcher]},
            observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:02:00+00:00"),
            artifact_source="https://example.com/today.json",
            artifact_sha="abc123",
        )

    assert result["rows"] == 1
    assert result["inserted_rows"] == 1
    assert result["dispatch"] == {"skipped": False, "status_code": 204}
    dispatch.assert_called_once_with("2026-05-06", inserted_lock_rows=1)


def test_operational_lock_write_does_not_dispatch_without_new_rows(monkeypatch):
    writer = Mock()
    writer.insert_ignore_rows.return_value = []
    pitcher = _fire_pitcher(game_time="2026-05-06T18:30:00Z")
    pitcher["tracked_picks"] = [{
        "pitcher": "Tarik Skubal",
        "side": "over",
        "display_verdict": "FIRE 1u",
        "display_k_line": 6.5,
        "display_odds": -110,
        "display_adj_ev": 0.09,
        "locked_at": None,
        "game_time": "2026-05-06T18:30:00Z",
    }]
    monkeypatch.setenv("ENABLE_SUPABASE_LOCK_LEDGER", "true")
    monkeypatch.setenv("ENABLE_LOCK_ONLY_WORKFLOW_DISPATCH", "true")

    with patch.object(build_live_events_to_supabase, "_dispatch_lock_only_workflow") as dispatch:
        result = build_live_events_to_supabase._write_operational_pick_locks(
            writer=writer,
            slate_date="2026-05-06",
            payload={"pitchers": [pitcher]},
            observed_at=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:02:00+00:00"),
            artifact_source="https://example.com/today.json",
            artifact_sha="abc123",
        )

    assert result["rows"] == 1
    assert result["inserted_rows"] == 0
    assert result["dispatch"] == {"skipped": True, "reason": "no_new_lock_rows"}
    dispatch.assert_not_called()


def test_dispatch_lock_only_workflow_sends_lock_mode_without_logging_token(monkeypatch):
    captured = {}

    class Response:
        status = 204

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b""

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setenv("GITHUB_LOCK_DISPATCH_TOKEN", "ghp_secret")
    monkeypatch.setenv("GITHUB_LOCK_DISPATCH_REPO", "treidjbi/BaseballBettingEdge")
    monkeypatch.setattr(build_live_events_to_supabase, "urlopen", fake_urlopen)

    result = build_live_events_to_supabase._dispatch_lock_only_workflow(
        "2026-05-06",
        inserted_lock_rows=2,
    )

    assert result == {"skipped": False, "status_code": 204}
    assert captured["url"] == (
        "https://api.github.com/repos/treidjbi/BaseballBettingEdge/"
        "actions/workflows/pipeline.yml/dispatches"
    )
    assert captured["body"] == {
        "ref": "main",
        "inputs": {"mode": "lock", "date": "2026-05-06"},
    }
    assert captured["headers"]["Authorization"] == "Bearer ghp_secret"
    assert "ghp_secret" not in repr(captured["body"])
    assert captured["timeout"] == 20


def test_dispatch_lock_only_workflow_uses_proxy_when_github_token_missing(monkeypatch):
    captured = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b'{"status":"triggered"}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["headers"] = dict(request.header_items())
        captured["body"] = json.loads(request.data.decode("utf-8"))
        captured["timeout"] = timeout
        return Response()

    monkeypatch.delenv("GITHUB_LOCK_DISPATCH_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_PAT", raising=False)
    monkeypatch.setenv(
        "LOCK_ONLY_WORKFLOW_DISPATCH_URL",
        "https://baseballbettingedge.netlify.app/.netlify/functions/trigger-pipeline",
    )
    monkeypatch.setattr(build_live_events_to_supabase, "urlopen", fake_urlopen)

    result = build_live_events_to_supabase._dispatch_lock_only_workflow(
        "2026-05-06",
        inserted_lock_rows=2,
    )

    assert result == {"skipped": False, "status_code": 200, "via": "proxy"}
    assert captured["url"] == "https://baseballbettingedge.netlify.app/.netlify/functions/trigger-pipeline"
    assert captured["body"] == {"mode": "lock", "date": "2026-05-06"}
    assert "Authorization" not in captured["headers"]
    assert captured["timeout"] == 20


def test_worker_marks_missing_previous_fire_pass_after_notifications(tmp_path):
    today = _write_artifact(tmp_path, [])
    previous = [{
        "slate_date": "2026-05-06",
        "pitcher": "Tarik Skubal",
        "normalized_pitcher": "tarik skubal",
        "side": "over",
        "current_verdict": "FIRE 1u",
        "k_line": 6.5,
        "current_odds": -110,
        "current_book": "FanDuel",
        "game_time": "2026-05-06T22:10:00Z",
        "game_state": "scheduled",
        "is_locked": False,
    }]
    writer = _writer_with_selects({
        "live_pick_state": previous,
        "market_snapshots": [],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["notification_events"] == 1
    assert result["live_pick_state"] == 1
    assert result["notification_rows"][0]["event_type"] == "pick_downgraded"
    assert result["state_rows"][0]["current_verdict"] == "PASS"
    write_order = [
        (call[0], call.args[0])
        for call in writer.mock_calls
        if call[0] in {"insert_ignore_rows", "upsert_rows"}
    ]
    assert (
        write_order.index(("insert_ignore_rows", "notification_events"))
        < write_order.index(("upsert_rows", "live_pick_state"))
    )


def test_worker_writes_line_movement_events_from_snapshot_history(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [
            {
                "id": "snapshot-old",
                "provider": "propline",
                "provider_event_id": "game-1",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "snapshot-new",
                "provider": "propline",
                "provider_event_id": "game-1",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 5.5,
                "american_odds": -112,
                "observed_at": "2026-05-06T18:00:00+00:00",
            },
        ],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["line_movement_events"] == 1
    assert result["line_movement_rows"][0]["source_snapshot_id"] == "snapshot-new"
    assert result["line_movement_rows"][0]["metadata"]["provider_event_id"] == "game-1"
    movement_notification = next(
        row
        for row in result["notification_rows"]
        if row["event_type"] == "line_moved_with_us"
    )
    assert movement_notification["payload"]["game_time"] == "2026-05-06T22:10:00Z"
    assert movement_notification["payload"]["game_state"] == "scheduled"
    writer.upsert_rows.assert_any_call(
        "line_movement_events",
        result["line_movement_rows"],
        on_conflict="dedupe_key",
    )


def test_worker_ignores_multi_line_ladder_as_line_movement(tmp_path):
    pitcher = _fire_pitcher(pitcher="Joey Cantillo")
    pitcher["k_line"] = 4.5
    pitcher["best_over_odds"] = -170
    today = _write_artifact(tmp_path, [pitcher])
    previous_state = _previous_fire_state("Joey Cantillo", game_time="2026-05-06T22:10:00Z")
    previous_state["normalized_pitcher"] = "joey cantillo"
    previous_state["k_line"] = 4.5
    previous_state["current_odds"] = -170
    writer = _writer_with_selects({
        "live_pick_state": [previous_state],
        "market_snapshots": [
            {
                "id": "snapshot-old-alt",
                "provider": "propline",
                "provider_event_id": "game-1",
                "normalized_player_name": "joey cantillo",
                "player_name": "Joey Cantillo",
                "bookmaker_key": "kalshi",
                "side": "over",
                "line": 2.5,
                "american_odds": -900,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "snapshot-old-pick",
                "provider": "propline",
                "provider_event_id": "game-1",
                "normalized_player_name": "joey cantillo",
                "player_name": "Joey Cantillo",
                "bookmaker_key": "kalshi",
                "side": "over",
                "line": 4.5,
                "american_odds": -170,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "snapshot-current-pick",
                "provider": "propline",
                "provider_event_id": "game-1",
                "normalized_player_name": "joey cantillo",
                "player_name": "Joey Cantillo",
                "bookmaker_key": "kalshi",
                "side": "over",
                "line": 4.5,
                "american_odds": -170,
                "observed_at": "2026-05-06T18:00:00+00:00",
            },
            {
                "id": "snapshot-current-alt",
                "provider": "propline",
                "provider_event_id": "game-1",
                "normalized_player_name": "joey cantillo",
                "player_name": "Joey Cantillo",
                "bookmaker_key": "kalshi",
                "side": "over",
                "line": 3.5,
                "american_odds": -355,
                "observed_at": "2026-05-06T18:00:00+00:00",
            },
        ],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["line_movement_events"] == 0
    assert all(
        row["event_type"] not in {"line_moved_with_us", "line_moved_against_us"}
        for row in result["notification_rows"]
    )


def test_worker_suppresses_post_start_line_movement_notifications(tmp_path):
    pitcher = _fire_pitcher(game_time="2026-05-06T17:55:00Z")
    today = _write_artifact(tmp_path, [pitcher])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [
            {
                "id": "snapshot-old",
                "provider": "propline",
                "provider_event_id": "game-1",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "snapshot-new",
                "provider": "propline",
                "provider_event_id": "game-1",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 5.5,
                "american_odds": -112,
                "observed_at": "2026-05-06T18:00:00+00:00",
            },
        ],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["line_movement_events"] == 0
    assert result["line_movement_rows"] == []
    assert all(
        row["event_type"] not in {"line_moved_with_us", "line_moved_against_us"}
        for row in result["notification_rows"]
    )


def test_worker_fetches_market_snapshots_by_recent_run_ids_when_available(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    calls = []
    writer = Mock()

    def select_rows(table, params):
        calls.append((table, dict(params)))
        if table == "live_pick_state":
            return []
        if table == "market_feed_heartbeats":
            return []
        if table == "market_provider_runs":
            return [{
                "id": "run-1", "created_at": "2026-05-06T17:40:00+00:00",
                "provider": "propline", "slate_date": "2026-05-06",
            }]
        if table == "market_snapshots":
            return [
                {
                    "id": "snapshot-new",
                    "run_id": "run-1",
                    "provider": "propline",
                    "provider_event_id": "game-1",
                    "normalized_player_name": "tarik skubal",
                    "player_name": "Tarik Skubal",
                    "bookmaker_key": "fanduel",
                    "side": "over",
                    "line": 5.5,
                    "american_odds": -112,
                    "observed_at": "2026-05-06T18:00:00+00:00",
                },
                {
                    "id": "snapshot-old",
                    "run_id": "run-1",
                    "provider": "propline",
                    "provider_event_id": "game-1",
                    "normalized_player_name": "tarik skubal",
                    "player_name": "Tarik Skubal",
                    "bookmaker_key": "fanduel",
                    "side": "over",
                    "line": 6.5,
                    "american_odds": -110,
                    "observed_at": "2026-05-06T17:50:00+00:00",
                },
            ]
        if table == "game_reminder_state":
            return []
        return []

    writer.select_rows.side_effect = select_rows

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    snapshot_call = next(call for call in calls if call[0] == "market_snapshots")
    assert snapshot_call[1]["run_id"] == "in.(run-1)"
    assert snapshot_call[1]["observed_at"].startswith("gte.")
    assert snapshot_call[1]["limit"] == "1000"
    assert result["line_movement_events"] == 1


def test_snapshot_fetch_annotates_only_rows_bound_to_exact_slate_runs():
    writer = Mock()

    def select_rows(table, params):
        if table == "market_provider_runs":
            return [{
                "id": "run-1",
                "created_at": "2026-05-06T17:40:00+00:00",
                "provider": "therundown",
                "slate_date": "2026-05-06",
            }]
        if table == "market_snapshots":
            return [
                {
                    "id": "snapshot-unbound", "run_id": "unknown-run",
                    "provider": "therundown",
                    "observed_at": "2026-05-06T17:51:00+00:00",
                },
                {
                    "id": "snapshot-bound", "run_id": "run-1",
                    "provider": "therundown",
                    "observed_at": "2026-05-06T17:50:00+00:00",
                },
            ]
        raise AssertionError(table)

    writer.select_rows.side_effect = select_rows

    result = build_live_events_to_supabase._fetch_live_market_snapshot_rows(
        writer,
        "2026-05-06",
        build_live_events_to_supabase.datetime.fromisoformat(
            "2026-05-06T18:00:00+00:00"
        ),
    )

    rows_by_id = {row["id"]: row for row in result.rows}
    assert rows_by_id["snapshot-bound"]["slate_date"] == "2026-05-06"
    assert "slate_date" not in rows_by_id["snapshot-unbound"]
    assert [row["id"] for row in result.v2_rows] == ["snapshot-bound"]
    assert result.complete is False
    assert result.reason_codes == ("provider_run_provenance_unavailable",)


def test_snapshot_fetch_does_not_invent_slate_date_on_broad_fallback_rows():
    writer = Mock()

    def select_rows(table, params):
        if table == "market_provider_runs":
            return []
        if table == "market_snapshots":
            return [{
                "id": "snapshot-fallback",
                "run_id": "run-without-provenance",
                "provider": "therundown",
            }]
        raise AssertionError(table)

    writer.select_rows.side_effect = select_rows

    result = build_live_events_to_supabase._fetch_live_market_snapshot_rows(
        writer,
        "2026-05-06",
        build_live_events_to_supabase.datetime.fromisoformat(
            "2026-05-06T18:00:00+00:00"
        ),
    )

    assert "slate_date" not in result.rows[0]
    assert result.v2_rows == []
    assert result.complete is False
    assert result.reason_codes == ("provider_run_provenance_unavailable",)


def test_provider_run_fetch_retains_one_read_latest_100_scope_and_detects_older_rows():
    writer = Mock()
    writer.select_rows.return_value = [
        {
            "id": _ordered_uuid(index),
            "created_at": f"2026-05-06T{(index // 60):02d}:{(index % 60):02d}:00+00:00",
            "provider": "therundown",
            "slate_date": "2026-05-06",
        }
        for index in range(101, 0, -1)
    ]

    rows, complete = build_live_events_to_supabase._fetch_recent_provider_run_rows(
        writer, "2026-05-06",
    )

    assert [row["id"] for row in rows] == [
        _ordered_uuid(index) for index in range(101, 1, -1)
    ]
    assert complete is False
    assert _ordered_uuid(1) not in build_live_events_to_supabase._run_id_filter(rows)
    writer.select_rows.assert_called_once()
    params = writer.select_rows.call_args.args[1]
    assert params["order"] == "created_at.desc,id.desc"
    assert params["limit"] == "101"
    assert "or" not in params and "offset" not in params


def test_provider_run_fetch_reports_complete_below_latest_100_scope():
    writer = Mock()
    writer.select_rows.return_value = [
        {"id": "run-2", "created_at": "2026-05-06T10:01:00+00:00", "provider": "propline", "slate_date": "2026-05-06"},
        {"id": "run-1", "created_at": "2026-05-06T10:00:00+00:00", "provider": "therundown", "slate_date": "2026-05-06"},
    ]

    rows, complete = build_live_events_to_supabase._fetch_recent_provider_run_rows(
        writer, "2026-05-06",
    )

    assert len(rows) == 2
    assert complete is True


def test_snapshot_fetch_uses_descending_keyset_pages_for_newest_suffix(monkeypatch):
    run_rows = [{
        "id": _ordered_uuid(9000), "created_at": "2026-05-06T10:00:00+00:00",
        "provider": "therundown", "slate_date": "2026-05-06",
    }]
    monkeypatch.setattr(
        build_live_events_to_supabase,
        "_fetch_recent_provider_run_rows",
        lambda *_args, **_kwargs: (run_rows, True),
    )
    writer = Mock()
    pages = [
        [
            {"id": _ordered_uuid(3), "run_id": _ordered_uuid(9000), "provider": "therundown", "observed_at": "2026-05-06T11:00:00+00:00"},
            {"id": _ordered_uuid(2), "run_id": _ordered_uuid(9000), "provider": "therundown", "observed_at": "2026-05-06T10:00:00+00:00"},
        ],
        [
            {"id": _ordered_uuid(1), "run_id": _ordered_uuid(9000), "provider": "therundown", "observed_at": "2026-05-06T10:00:00+00:00"},
        ],
    ]
    writer.select_rows.side_effect = lambda _table, _params: pages.pop(0)

    result = build_live_events_to_supabase._fetch_live_market_snapshot_rows(
        writer, "2026-05-06",
        build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        page_size=2, max_pages=3,
    )

    assert [row["id"] for row in result.rows] == [
        _ordered_uuid(3), _ordered_uuid(2), _ordered_uuid(1),
    ]
    assert len({row["id"] for row in result.rows}) == 3
    assert result.v2_rows == result.rows
    assert result.complete is True
    first, second = [call.args[1] for call in writer.select_rows.call_args_list]
    assert first["order"] == "observed_at.desc,id.desc"
    assert "or" not in first and "offset" not in first
    assert second["or"] == (
        "(observed_at.lt.2026-05-06T10:00:00+00:00,"
        "and(observed_at.eq.2026-05-06T10:00:00+00:00,"
        f"id.lt.{_ordered_uuid(2)}))"
    )
    assert "offset" not in second


def test_snapshot_full_final_page_reports_incomplete_cap(monkeypatch):
    run_rows = [{
        "id": _ordered_uuid(9000), "created_at": "2026-05-06T10:00:00+00:00",
        "provider": "therundown", "slate_date": "2026-05-06",
    }]
    monkeypatch.setattr(
        build_live_events_to_supabase,
        "_fetch_recent_provider_run_rows",
        lambda *_args, **_kwargs: (run_rows, True),
    )
    writer = Mock()
    writer.select_rows.return_value = [
        {"id": "snapshot-2", "run_id": _ordered_uuid(9000), "provider": "therundown", "observed_at": "2026-05-06T10:01:00+00:00"},
        {"id": "snapshot-1", "run_id": _ordered_uuid(9000), "provider": "therundown", "observed_at": "2026-05-06T10:00:00+00:00"},
    ]

    result = build_live_events_to_supabase._fetch_live_market_snapshot_rows(
        writer, "2026-05-06",
        build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        page_size=2, max_pages=1,
    )

    assert [row["id"] for row in result.rows] == ["snapshot-2", "snapshot-1"]
    assert result.v2_rows == result.rows
    assert result.complete is False
    assert result.reason_codes == ("snapshot_page_cap_reached",)


def test_snapshot_default_cap_returns_exact_newest_5000_suffix_and_v2_incomplete(
    monkeypatch,
):
    run_rows = [{
        "id": _ordered_uuid(9000), "created_at": "2026-05-06T10:00:00+00:00",
        "provider": "therundown", "slate_date": "2026-05-06",
    }]
    monkeypatch.setattr(
        build_live_events_to_supabase,
        "_fetch_recent_provider_run_rows",
        lambda *_args, **_kwargs: (run_rows, True),
    )
    writer = Mock()
    pages = [
        [
            {
                "id": _ordered_uuid(index),
                "run_id": _ordered_uuid(9000),
                "provider": "therundown",
                "observed_at": "2026-05-06T10:00:00+00:00",
            }
            for index in range(page_end, page_end - 1000, -1)
        ]
        for page_end in (5000, 4000, 3000, 2000, 1000)
    ]
    writer.select_rows.side_effect = lambda _table, _params: pages.pop(0)

    result = build_live_events_to_supabase._fetch_live_market_snapshot_rows(
        writer,
        "2026-05-06",
        build_live_events_to_supabase.datetime.fromisoformat(
            "2026-05-06T18:00:00+00:00"
        ),
    )

    assert len(result.rows) == 5000
    assert result.rows[0]["id"] == _ordered_uuid(5000)
    assert result.rows[-1]["id"] == _ordered_uuid(1)
    assert len({row["id"] for row in result.rows}) == 5000
    assert result.v2_rows == result.rows
    assert result.complete is False
    assert result.reason_codes == ("snapshot_page_cap_reached",)
    assert writer.select_rows.call_count == 5


def test_snapshot_slate_stamp_requires_matching_parent_provider():
    writer = Mock()

    def select_rows(table, params):
        if table == "market_provider_runs":
            return [{
                "id": "run-1", "created_at": "2026-05-06T10:00:00+00:00",
                "provider": "TheRundown", "slate_date": "2026-05-06",
            }]
        if table == "market_snapshots":
            return [{
                "id": "snapshot-1", "run_id": "run-1",
                "provider": "propline", "observed_at": "2026-05-06T10:01:00+00:00",
            }]
        raise AssertionError(table)

    writer.select_rows.side_effect = select_rows

    result = build_live_events_to_supabase._fetch_live_market_snapshot_rows(
        writer, "2026-05-06",
        build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
    )

    assert result.rows[0]["slate_date"] == "2026-05-06"
    assert result.v2_rows == []
    assert result.complete is False
    assert result.reason_codes == ("snapshot_parent_provider_mismatch",)


def test_worker_keeps_capped_newest_suffix_for_legacy_consumers_and_fails_v2_closed(
    tmp_path, monkeypatch,
):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    legacy_rows = [
        {
            "id": "snapshot-newest",
            "provider": "propline",
            "provider_event_id": "game-1",
            "normalized_player_name": "tarik skubal",
            "bookmaker_key": "fanduel",
            "side": "over",
            "line": 6.5,
            "american_odds": -105,
            "observed_at": "2026-05-06T18:00:00+00:00",
        },
        {
            "id": "snapshot-older",
            "provider": "propline",
            "provider_event_id": "game-1",
            "normalized_player_name": "tarik skubal",
            "bookmaker_key": "fanduel",
            "side": "over",
            "line": 6.5,
            "american_odds": -110,
            "observed_at": "2026-05-06T17:50:00+00:00",
        },
    ]
    v2_rows = [legacy_rows[0]]
    snapshot_read = build_live_events_to_supabase.SnapshotReadResult(
        rows=legacy_rows,
        v2_rows=v2_rows,
        complete=False,
        window_started_at="2026-05-06T06:00:00+00:00",
        reason_codes=("snapshot_page_cap_reached",),
    )
    fetch = Mock(return_value=snapshot_read)
    movement = Mock(return_value=[])
    display = Mock(return_value=[])
    dispatch = Mock(return_value={"skipped": False, "rows": 0})
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_feed_heartbeats": [],
        "live_market_display_state": [],
        "game_reminder_state": [],
    })

    monkeypatch.setattr(build_live_events_to_supabase, "_fetch_live_market_snapshot_rows", fetch)
    monkeypatch.setattr(build_live_events_to_supabase, "build_line_movement_events", movement)
    monkeypatch.setattr(build_live_events_to_supabase, "build_market_pick_evidence_rows", lambda **_kwargs: [])
    monkeypatch.setattr(build_live_events_to_supabase, "build_live_market_display_rows", display)
    monkeypatch.setattr(build_live_events_to_supabase, "_dispatch_alternative_pick_selection_state", dispatch)

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat(
                "2026-05-06T18:00:00+00:00"
            ),
        ),
    ):
        build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    fetch.assert_called_once()
    assert [
        row["id"]
        for row in (
            movement.call_args.kwargs["previous_snapshots"]
            + movement.call_args.kwargs["current_snapshots"]
        )
    ] == ["snapshot-older", "snapshot-newest"]
    assert display.call_args.kwargs["snapshot_rows"] == legacy_rows
    assert dispatch.call_args.kwargs["snapshot_rows"] == legacy_rows
    assert dispatch.call_args.kwargs["v2_snapshot_rows"] == v2_rows
    assert dispatch.call_args.kwargs["snapshot_read_complete"] is False
    assert dispatch.call_args.kwargs["snapshot_read_reason_codes"] == (
        "snapshot_page_cap_reached",
    )


def test_worker_ignores_boltodds_shadow_snapshots_for_notifications(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [
            {
                "id": "bolt-snapshot-old",
                "provider": "boltodds",
                "provider_event_id": "game-1",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "betrivers",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "bolt-snapshot-new",
                "provider": "boltodds",
                "provider_event_id": "game-1",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "betrivers",
                "side": "over",
                "line": 5.5,
                "american_odds": -112,
                "observed_at": "2026-05-06T18:00:00+00:00",
            },
        ],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["line_movement_events"] == 0
    assert result["line_movement_rows"] == []


def test_worker_writes_market_pick_evidence_for_shadow_providers(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [
            {
                "id": "propline-old",
                "provider": "propline",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "propline-new",
                "provider": "propline",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 5.5,
                "american_odds": -112,
                "observed_at": "2026-05-06T18:00:00+00:00",
            },
            {
                "id": "rundown-old",
                "provider": "therundown",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "betrivers",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "rundown-new",
                "provider": "therundown",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "betrivers",
                "side": "over",
                "line": 5.5,
                "american_odds": -112,
                "observed_at": "2026-05-06T18:00:00+00:00",
            },
        ],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
    )

    assert result["market_pick_evidence"] == 2
    assert result["live_market_display_state"] == 3
    assert {row["provider"] for row in result["market_pick_evidence_rows"]} == {"propline", "therundown"}
    assert {row["provider"] for row in result["live_market_display_rows"]} == {
        "propline",
        "therundown",
        "therundown_propline",
    }
    combined_row = next(
        row for row in result["live_market_display_rows"]
        if row["provider"] == "therundown_propline"
    )
    individual_rows = [
        row for row in result["live_market_display_rows"]
        if row["provider"] != "therundown_propline"
    ]
    assert {row["actionable_state"] for row in individual_rows} == {"monitor"}
    assert combined_row["actionable_state"] == "market_fade"
    assert combined_row["book_count"] == 2
    assert combined_row["books_seen"] == ["betrivers", "fanduel"]
    writer.upsert_rows.assert_any_call(
        "market_pick_evidence",
        result["market_pick_evidence_rows"],
        on_conflict="slate_date,normalized_pitcher,side,provider",
    )
    writer.upsert_rows.assert_any_call(
        "live_market_display_state",
        result["live_market_display_rows"],
        on_conflict="slate_date,normalized_pitcher,side,provider",
    )
    writer.upsert_rows.assert_any_call(
        "shadow_notification_candidates",
        result["shadow_notification_candidate_rows"],
        on_conflict="dedupe_key",
    )
    assert result["shadow_notification_candidates"] == 2


def test_mainline_best_price_shadow_mode_records_summary(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_MAINLINE_PRICE_NOTIFICATION_MODE", "shadow")
    monkeypatch.setenv("LIVE_MAINLINE_PRICE_MIN_CENTS", "10")
    pitcher = _fire_pitcher(pitcher="Jacob Misiorowski")
    pitcher["k_line"] = 7.5
    today = _write_artifact(tmp_path, [pitcher])
    previous_state = _previous_fire_state("Jacob Misiorowski", game_time="2026-05-06T22:10:00Z")
    previous_state["normalized_pitcher"] = "jacob misiorowski"
    previous_state["k_line"] = 7.5

    previous_display = {
        "slate_date": "2026-05-06",
        "pitcher": "Jacob Misiorowski",
        "normalized_pitcher": "jacob misiorowski",
        "side": "over",
        "provider": "propline",
        "current_verdict": "FIRE 1u",
        "k_line": 7.5,
        "game_time": "2026-05-06T22:10:00Z",
        "game_state": "scheduled",
        "is_locked": False,
        "freshness_status": "fresh",
        "book_rows": [{"book": "fanduel", "line": 7.5, "odds": -120}],
    }
    writer = _writer_with_selects({
        "live_pick_state": [previous_state],
        "market_snapshots": [
            {
                "id": "snapshot-1",
                "provider": "propline",
                "provider_event_id": "game-1",
                "normalized_player_name": "jacob misiorowski",
                "player_name": "Jacob Misiorowski",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 7.5,
                "american_odds": -105,
                "observed_at": "2026-05-06T18:00:00+00:00",
            },
        ],
        "live_market_display_state": [previous_display],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["mainline_best_price_notifications"] == 0
    assert result["mainline_best_price"]["mode"] == "shadow"
    assert result["mainline_best_price"]["candidate_count"] == 1
    assert result["shadow_pipeline_timing"]["pipeline_run_row"]["metadata"]["mainline_best_price"]["candidate_count"] == 1


def test_mainline_best_price_send_mode_replaces_raw_movement_notifications(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_MAINLINE_PRICE_NOTIFICATION_MODE", "send")
    monkeypatch.setenv("LIVE_MAINLINE_PRICE_MIN_CENTS", "10")
    pitcher = _fire_pitcher(pitcher="Jacob Misiorowski")
    pitcher["k_line"] = 7.5
    today = _write_artifact(tmp_path, [pitcher])
    previous_state = _previous_fire_state("Jacob Misiorowski", game_time="2026-05-06T22:10:00Z")
    previous_state["normalized_pitcher"] = "jacob misiorowski"
    previous_state["k_line"] = 7.5

    previous_display = {
        "slate_date": "2026-05-06",
        "pitcher": "Jacob Misiorowski",
        "normalized_pitcher": "jacob misiorowski",
        "side": "over",
        "provider": "propline",
        "current_verdict": "FIRE 1u",
        "k_line": 7.5,
        "game_time": "2026-05-06T22:10:00Z",
        "game_state": "scheduled",
        "is_locked": False,
        "freshness_status": "fresh",
        "book_rows": [{"book": "fanduel", "line": 7.5, "odds": -120}],
    }
    writer = _writer_with_selects({
        "live_pick_state": [previous_state],
        "market_snapshots": [
            {
                "id": "snapshot-old",
                "provider": "propline",
                "provider_event_id": "game-1",
                "normalized_player_name": "jacob misiorowski",
                "player_name": "Jacob Misiorowski",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 7.5,
                "american_odds": -120,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "snapshot-new",
                "provider": "propline",
                "provider_event_id": "game-1",
                "normalized_player_name": "jacob misiorowski",
                "player_name": "Jacob Misiorowski",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 7.5,
                "american_odds": -105,
                "observed_at": "2026-05-06T18:00:00+00:00",
            },
        ],
        "live_market_display_state": [previous_display],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["line_movement_events"] == 1
    assert result["mainline_best_price_notifications"] == 1
    assert [row["event_type"] for row in result["notification_rows"]] == [
        "mainline_best_price_changed"
    ]


def test_worker_filters_retired_boltodds_from_active_market_builders(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    calls = []
    writer = Mock()

    def select_rows(table, params):
        calls.append((table, dict(params)))
        if table == "market_feed_heartbeats":
            assert params["provider"] == "in.(propline,therundown)"
            return []
        if table == "market_snapshots":
            assert params["provider"] == "in.(propline,therundown)"
            return [
                {
                    "id": "bolt-fd-old",
                    "provider": "boltodds",
                    "normalized_player_name": "tarik skubal",
                    "player_name": "Tarik Skubal",
                    "bookmaker_key": "fanduel",
                    "side": "over",
                    "line": 6.5,
                    "american_odds": -110,
                    "observed_at": "2026-05-06T17:00:00+00:00",
                },
                {
                    "id": "bolt-mgm-old",
                    "provider": "boltodds",
                    "normalized_player_name": "tarik skubal",
                    "player_name": "Tarik Skubal",
                    "bookmaker_key": "betmgm",
                    "side": "over",
                    "line": 6.5,
                    "american_odds": -105,
                    "observed_at": "2026-05-06T17:00:00+00:00",
                },
            ]
        return {
            "live_pick_state": [],
            "game_reminder_state": [],
        }.get(table, [])

    writer.select_rows.side_effect = select_rows

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:10:30+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["provider_heartbeats"] == 0
    assert result["market_pick_evidence_rows"] == []
    assert result["live_market_display_rows"] == []
    assert ("market_feed_heartbeats", {
        "provider": "in.(propline,therundown)",
        "slate_date": "eq.2026-05-06",
        "order": "observed_at.desc",
        "limit": "25",
    }) in calls


def test_worker_uses_active_provider_heartbeats_for_shadow_market_builders(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_feed_heartbeats": [{
            "provider": "therundown",
            "slate_date": "2026-05-06",
            "observed_at": "2026-05-06T18:10:15+00:00",
            "last_message_at": "2026-05-06T18:10:10+00:00",
            "books_seen": ["fanduel", "betmgm"],
            "metadata": {"event": "flush", "target_books": ["fanduel", "betmgm"]},
        }],
        "market_snapshots": [
            {
                "id": "rundown-fd-old",
                "provider": "therundown",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-06T17:00:00+00:00",
            },
            {
                "id": "rundown-mgm-old",
                "provider": "therundown",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "betmgm",
                "side": "over",
                "line": 6.5,
                "american_odds": -105,
                "observed_at": "2026-05-06T17:00:00+00:00",
            },
        ],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:10:30+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["live_market_display_rows"][0]["freshness_status"] == "stale"
    assert result["live_market_display_rows"][0]["metadata"]["heartbeat_hold"] is False
    assert result["market_pick_evidence_rows"][0]["metadata"]["freshness_status"] == "stale"
    assert result["market_pick_evidence_rows"][0]["metadata"]["heartbeat_hold"] is False
    assert writer.select_rows.call_args_list[1].args[0] == "market_feed_heartbeats"
    assert writer.select_rows.call_args_list[1].args[1]["slate_date"] == "eq.2026-05-06"
    assert writer.select_rows.call_args_list[1].args[1]["provider"] == "in.(propline,therundown)"


def test_worker_keeps_heartbeat_read_failures_from_breaking_live_layer(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = Mock()

    def select_rows(table, params):
        if table == "market_feed_heartbeats":
            raise RuntimeError("heartbeat table unavailable")
        return {
            "live_pick_state": [],
            "market_snapshots": [],
            "game_reminder_state": [],
        }.get(table, [])

    writer.select_rows.side_effect = select_rows

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:10:30+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["live_pick_state"] == 1
    assert result["provider_heartbeats"] == 0


def test_worker_does_not_turn_shadow_candidates_into_notifications(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher(game_time="2026-05-06T18:05:00+00:00")])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [
            {
                "id": "propline-old",
                "provider": "propline",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "propline-new",
                "provider": "propline",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 7.5,
                "american_odds": 120,
                "observed_at": "2026-05-06T17:58:00+00:00",
            },
        ],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T17:58:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["shadow_notification_candidates"] == 1
    assert all(row["event_type"] != "line_moved_with_us" for row in result["notification_rows"])


def test_worker_can_poll_propline_before_building_live_events(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    calls = []
    table_rows = {
        "live_pick_state": [],
        "market_snapshots": [
            {
                "id": "snapshot-old",
                "provider": "propline",
                "provider_event_id": "game-1",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "snapshot-new",
                "provider": "propline",
                "provider_event_id": "game-1",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 5.5,
                "american_odds": -112,
                "observed_at": "2026-05-06T18:00:00+00:00",
            },
        ],
        "game_reminder_state": [],
    }

    writer = Mock()

    def select_rows(table, params):
        calls.append(("select", table))
        return table_rows.get(table, [])

    writer.select_rows.side_effect = select_rows

    def poll_propline(*args, **kwargs):
        calls.append(("poll", "propline"))
        return {"target_event_count": 1, "snapshot_count": 2}

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "poll_propline_to_supabase",
            side_effect=poll_propline,
        ) as poll,
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            poll_propline=True,
        )

    poll.assert_called_once()
    assert calls.index(("poll", "propline")) < calls.index(("select", "market_snapshots"))
    assert result["propline"]["snapshot_count"] == 2
    assert result["line_movement_events"] == 1


def test_worker_can_poll_therundown_mainline_before_market_reads(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    calls = []
    table_rows = {
        "live_pick_state": [],
        "market_snapshots": [],
        "game_reminder_state": [],
    }
    writer = Mock()

    def select_rows(table, params):
        calls.append(("select", table))
        return table_rows.get(table, [])

    writer.select_rows.side_effect = select_rows

    def poll_therundown(*args, **kwargs):
        calls.append(("poll", "therundown"))
        return {
            "status": "completed",
            "target_event_count": 2,
            "snapshot_count": 4,
            "datapoints": 199,
        }

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "poll_therundown_mainline_to_supabase",
            side_effect=poll_therundown,
        ) as poll,
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            poll_therundown_mainline=True,
        )

    poll.assert_called_once_with(
        "2026-05-06",
        writer=writer,
        observed_at=ANY,
        raise_on_error=False,
    )
    assert calls.index(("poll", "therundown")) < calls.index(("select", "market_snapshots"))
    assert result["therundown"]["snapshot_count"] == 4
    assert result["therundown"]["datapoints"] == 199


def test_worker_can_process_propline_webhooks_before_market_reads(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    calls = []
    table_rows = {
        "live_pick_state": [],
        "market_snapshots": [],
        "game_reminder_state": [],
    }

    writer = Mock()

    def select_rows(table, params):
        calls.append(("select", table))
        return table_rows.get(table, [])

    writer.select_rows.side_effect = select_rows

    def process_webhooks(*args, **kwargs):
        calls.append(("process", "propline_webhooks"))
        return {
            "deliveries": 2,
            "processed": 2,
            "line_movement_events": 2,
            "unsupported": 0,
        }

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "process_propline_webhook_deliveries",
            side_effect=process_webhooks,
        ) as processor,
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            process_propline_webhooks=True,
        )

    processor.assert_called_once_with(
        supabase_url="https://example.supabase.co",
        service_role_key="secret",
        limit=100,
        received_after=ANY,
        return_movement_rows=False,
    )
    received_after = processor.call_args.kwargs["received_after"]
    assert received_after is not None
    assert calls.index(("process", "propline_webhooks")) < calls.index(("select", "market_snapshots"))
    assert result["propline_webhooks"]["line_movement_events"] == 2


def test_worker_can_send_book_level_propline_webhook_movement_notifications(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "game_reminder_state": [],
    })

    webhook_row = {
        "slate_date": "2026-05-06",
        "normalized_pitcher": "tarik skubal",
        "pitcher": "Tarik Skubal",
        "side": "over",
        "bookmaker_key": "fanduel",
        "previous_line": 6.5,
        "current_line": 5.5,
        "previous_odds": -130,
        "current_odds": -125,
        "movement_direction": "neutral",
        "movement_kind": "line_and_odds",
        "observed_at": "2026-05-06T18:00:00+00:00",
        "dedupe_key": "2026-05-06:propline_webhook:delivery-1",
        "source_snapshot_id": None,
        "metadata": {
            "bookmaker_key_missing": False,
            "prop_line_delivery_id": "delivery-1",
            "prop_line_event_id": "game-1",
            "source": "propline_webhook",
        },
    }
    non_target_webhook_row = {
        **webhook_row,
        "bookmaker_key": "underdog",
        "dedupe_key": "2026-05-06:propline_webhook:delivery-2",
        "metadata": {
            **webhook_row["metadata"],
            "prop_line_delivery_id": "delivery-2",
        },
    }

    def process_webhooks(*args, **kwargs):
        return {
            "deliveries": 1,
            "processed": 1,
            "line_movement_events": 2,
            "unsupported": 0,
            "movement_rows": [webhook_row, non_target_webhook_row],
        }

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "process_propline_webhook_deliveries",
            side_effect=process_webhooks,
        ) as processor,
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            process_propline_webhooks=True,
            send_propline_webhook_movement_notifications=True,
        )

    assert processor.call_args.kwargs["return_movement_rows"] is True
    assert result["propline_webhook_notification_events"] == 1
    webhook_event = result["propline_webhook_notification_rows"][0]
    assert webhook_event["event_type"] == "line_moved_with_us"
    assert webhook_event["dedupe_key"] == (
        "2026-05-06:line:game-1:fanduel:tarik skubal:over:6.5:-130:5.5:-125"
    )
    assert webhook_event["payload"]["source"] == "propline_webhook"
    assert "movement_rows" not in result["propline_webhooks"]


def test_mainline_send_mode_suppresses_webhook_movement_notifications(tmp_path, monkeypatch):
    monkeypatch.setenv("LIVE_MAINLINE_PRICE_NOTIFICATION_MODE", "send")
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "live_market_display_state": [],
        "game_reminder_state": [],
    })

    webhook_row = {
        "slate_date": "2026-05-06",
        "normalized_pitcher": "tarik skubal",
        "pitcher": "Tarik Skubal",
        "side": "over",
        "bookmaker_key": "fanduel",
        "previous_line": 6.5,
        "current_line": 5.5,
        "previous_odds": -130,
        "current_odds": -125,
        "movement_direction": "neutral",
        "movement_kind": "line_and_odds",
        "observed_at": "2026-05-06T18:00:00+00:00",
        "dedupe_key": "2026-05-06:propline_webhook:delivery-1",
        "source_snapshot_id": None,
        "metadata": {
            "bookmaker_key_missing": False,
            "prop_line_delivery_id": "delivery-1",
            "prop_line_event_id": "game-1",
            "source": "propline_webhook",
        },
    }

    def process_webhooks(*args, **kwargs):
        return {
            "deliveries": 1,
            "processed": 1,
            "line_movement_events": 1,
            "unsupported": 0,
            "movement_rows": [webhook_row],
        }

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "process_propline_webhook_deliveries",
            side_effect=process_webhooks,
        ) as processor,
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            process_propline_webhooks=True,
            send_propline_webhook_movement_notifications=True,
        )

    assert processor.call_args.kwargs["return_movement_rows"] is True
    assert result["mainline_best_price"]["mode"] == "send"
    assert result["propline_webhook_notification_events"] == 1
    assert all(
        row["event_type"] not in {"line_moved_with_us", "line_moved_against_us"}
        for row in result["notification_source_rows"]
    )
    assert all(
        row["event_type"] not in {"line_moved_with_us", "line_moved_against_us"}
        for row in result["notification_rows"]
    )


def test_worker_processes_old_propline_webhooks_without_queuing_stale_notifications(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "game_reminder_state": [],
    })

    stale_webhook_row = {
        "slate_date": "2026-05-06",
        "normalized_pitcher": "tarik skubal",
        "pitcher": "Tarik Skubal",
        "side": "over",
        "bookmaker_key": "fanduel",
        "previous_line": 6.5,
        "current_line": 5.5,
        "previous_odds": -130,
        "current_odds": -125,
        "movement_direction": "neutral",
        "movement_kind": "line_and_odds",
        "observed_at": "2026-05-06T17:35:00+00:00",
        "dedupe_key": "2026-05-06:propline_webhook:delivery-1",
        "source_snapshot_id": None,
        "metadata": {
            "bookmaker_key_missing": False,
            "prop_line_delivery_id": "delivery-1",
            "prop_line_event_id": "game-1",
            "source": "propline_webhook",
        },
    }

    def process_webhooks(*args, **kwargs):
        return {
            "deliveries": 1,
            "processed": 1,
            "line_movement_events": 1,
            "unsupported": 0,
            "movement_rows": [stale_webhook_row],
        }

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "process_propline_webhook_deliveries",
            side_effect=process_webhooks,
        ) as processor,
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            process_propline_webhooks=True,
            send_propline_webhook_movement_notifications=True,
            propline_webhook_max_age_minutes=180,
            propline_webhook_notification_max_age_minutes=20,
        )

    assert processor.call_args.kwargs["received_after"] is not None
    assert result["propline_webhooks"]["line_movement_events"] == 1
    assert result["propline_webhook_notification_events"] == 0


def test_worker_suppresses_post_start_propline_webhook_movement_notifications(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher(game_time="2026-05-06T17:55:00Z")])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "game_reminder_state": [],
    })

    webhook_row = {
        "slate_date": "2026-05-06",
        "normalized_pitcher": "tarik skubal",
        "pitcher": "Tarik Skubal",
        "side": "over",
        "bookmaker_key": "fanduel",
        "previous_line": 6.5,
        "current_line": 5.5,
        "previous_odds": -130,
        "current_odds": -125,
        "movement_direction": "neutral",
        "movement_kind": "line_and_odds",
        "observed_at": "2026-05-06T18:00:00+00:00",
        "dedupe_key": "2026-05-06:propline_webhook:delivery-1",
        "source_snapshot_id": None,
        "metadata": {
            "bookmaker_key_missing": False,
            "prop_line_delivery_id": "delivery-1",
            "prop_line_event_id": "game-1",
            "source": "propline_webhook",
        },
    }

    def process_webhooks(*args, **kwargs):
        return {
            "deliveries": 1,
            "processed": 1,
            "line_movement_events": 1,
            "unsupported": 0,
            "movement_rows": [webhook_row],
        }

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "process_propline_webhook_deliveries",
            side_effect=process_webhooks,
        ),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            process_propline_webhooks=True,
            send_propline_webhook_movement_notifications=True,
        )

    assert result["propline_webhook_notification_events"] == 0
    assert result["propline_webhook_notification_rows"] == []


def test_worker_can_build_shadow_market_lines_after_live_state(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    calls = []
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "market_feed_heartbeats": [],
        "game_reminder_state": [],
        "official_market_lines": [],
        "current_market_lines": [],
        "compact_market_line_movements": [],
    })

    def record_upsert(table, *args, **kwargs):
        calls.append(("upsert", table))
        return []

    def current_build(**kwargs):
        calls.append(("current_lines", kwargs["artifact_source"]))
        return {"current_market_lines": 3, "written_rows": 3}

    def official_build(**kwargs):
        calls.append(("official_lines", kwargs["artifact_source"]))
        return {"official_market_lines": 2, "ready_for_pipeline": 2}

    def compact_build(**kwargs):
        calls.append(("compact", kwargs["slate_date"]))
        return {"compact_rows": 4, "written_rows": 4}

    writer.upsert_rows.side_effect = record_upsert

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
        patch.object(
            build_live_events_to_supabase,
            "build_current_market_lines_to_supabase",
            side_effect=current_build,
        ),
        patch.object(
            build_live_events_to_supabase,
            "build_official_market_lines_to_supabase",
            side_effect=official_build,
        ),
        patch.object(
            build_live_events_to_supabase,
            "compact_market_snapshots_to_supabase",
            side_effect=compact_build,
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            build_market_lines=True,
        )

    current_call = next(call for call in calls if call[0] == "current_lines")
    official_call = next(call for call in calls if call[0] == "official_lines")
    assert result["artifact_source"] == build_live_events_to_supabase.APPROVED_ARTIFACT_PATH
    assert current_call[1] == official_call[1]
    assert calls.index(("upsert", "live_pick_state")) < calls.index(current_call)
    assert calls.index(current_call) < calls.index(official_call)
    assert calls.index(official_call) < calls.index(("compact", "2026-05-06"))
    assert result["market_line_build"]["skipped"] is False
    assert result["market_line_build"]["current"]["current_market_lines"] == 3
    assert result["market_line_build"]["official"]["ready_for_pipeline"] == 2
    assert result["market_line_build"]["compact"]["compact_rows"] == 4


def test_worker_skips_shadow_market_line_build_when_official_rows_are_fresh(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "market_feed_heartbeats": [],
        "game_reminder_state": [],
        "official_market_lines": [{"updated_at": "2026-05-06T17:59:30+00:00"}],
        "current_market_lines": [{"updated_at": "2026-05-06T17:59:30+00:00"}],
        "compact_market_line_movements": [{"updated_at": "2026-05-06T17:45:00+00:00"}],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
        patch.object(build_live_events_to_supabase, "build_current_market_lines_to_supabase") as current_build,
        patch.object(build_live_events_to_supabase, "build_official_market_lines_to_supabase") as official_build,
        patch.object(build_live_events_to_supabase, "compact_market_snapshots_to_supabase") as compact_build,
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            build_market_lines=True,
            market_line_min_interval_seconds=600,
            compact_market_min_interval_seconds=1800,
        )

    current_build.assert_not_called()
    official_build.assert_not_called()
    compact_build.assert_not_called()
    assert result["market_line_build"] == {"skipped": True, "reason": "fresh"}


def test_worker_continues_when_optional_propline_poll_times_out(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    calls = []
    writer = Mock()

    def select_rows(table, params):
        calls.append(("select", table))
        return {
            "live_pick_state": [],
            "market_snapshots": [],
            "game_reminder_state": [],
        }.get(table, [])

    writer.select_rows.side_effect = select_rows

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "poll_propline_to_supabase",
            side_effect=requests.ReadTimeout("PropLine timed out"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            poll_propline=True,
        )

    assert result["live_pick_state"] == 1
    assert result["propline"]["skipped"] is True
    assert result["propline"]["reason"] == "poll_failed"
    assert "PropLine timed out" in result["propline"]["error"]
    assert ("select", "market_snapshots") in calls


def test_worker_continues_when_optional_therundown_poll_times_out(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    calls = []
    writer = Mock()

    def select_rows(table, params):
        calls.append(("select", table))
        return {
            "live_pick_state": [],
            "market_snapshots": [],
            "game_reminder_state": [],
        }.get(table, [])

    writer.select_rows.side_effect = select_rows

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "poll_therundown_mainline_to_supabase",
            side_effect=requests.ReadTimeout("TheRundown timed out"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
            poll_therundown_mainline=True,
        )

    assert result["live_pick_state"] == 1
    assert result["therundown"]["skipped"] is True
    assert result["therundown"]["reason"] == "poll_failed"
    assert "TheRundown timed out" in result["therundown"]["error"]
    assert ("select", "market_snapshots") in calls


def test_worker_continues_when_market_snapshot_read_fails(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = Mock()

    def select_rows(table, params):
        if table == "market_snapshots":
            raise RuntimeError("Supabase market_snapshots read failed")
        return {
            "live_pick_state": [],
            "market_feed_heartbeats": [],
            "game_reminder_state": [],
        }.get(table, [])

    writer.select_rows.side_effect = select_rows

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["live_pick_state"] == 1
    assert result["notification_events"] == 1
    assert result["line_movement_events"] == 0
    assert result["market_pick_evidence"] == 0
    assert result["live_market_display_state"] == 0
    writer.upsert_rows.assert_any_call(
        "live_pick_state",
        result["state_rows"],
        on_conflict="slate_date,normalized_pitcher,side",
    )


def test_worker_does_not_compare_snapshots_across_provider_events(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher()])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [
            {
                "id": "snapshot-old",
                "provider_event_id": "old-game",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "snapshot-new",
                "provider_event_id": "new-game",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 5.5,
                "american_odds": -112,
                "observed_at": "2026-05-06T18:00:00+00:00",
            },
        ],
        "game_reminder_state": [],
    })

    with patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["line_movement_events"] == 0
    assert result["line_movement_rows"] == []


def test_worker_writes_fire_1u_game_reminder_state(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher(game_time="2026-05-06T18:25:00+00:00")])
    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        result = build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["game_reminders"] == 1
    assert result["reminder_rows"][0]["reminder_window"] == "25_min"
    writer.upsert_rows.assert_any_call(
        "game_reminder_state",
        result["reminder_rows"],
        on_conflict="dedupe_key",
    )


def test_worker_upserts_non_empty_tables_in_retry_safe_order(tmp_path):
    today = _write_artifact(tmp_path, [_fire_pitcher(game_time="2026-05-06T18:25:00+00:00")])

    writer = _writer_with_selects({
        "live_pick_state": [],
        "market_snapshots": [
            {
                "id": "snapshot-old",
                "provider_event_id": "game-1",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 6.5,
                "american_odds": -110,
                "observed_at": "2026-05-06T17:50:00+00:00",
            },
            {
                "id": "snapshot-new",
                "provider_event_id": "game-1",
                "normalized_player_name": "tarik skubal",
                "player_name": "Tarik Skubal",
                "bookmaker_key": "fanduel",
                "side": "over",
                "line": 5.5,
                "american_odds": -112,
                "observed_at": "2026-05-06T18:00:00+00:00",
            },
        ],
        "game_reminder_state": [],
    })

    with (
        patch.object(build_live_events_to_supabase, "SupabaseMarketWriter", return_value=writer),
        patch.object(
            build_live_events_to_supabase,
            "_now_utc",
            return_value=build_live_events_to_supabase.datetime.fromisoformat("2026-05-06T18:00:00+00:00"),
        ),
    ):
        build_live_events_to_supabase.run(
            slate_date="2026-05-06",
            artifact_path=today,
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    upsert_tables = [call.args[0] for call in writer.upsert_rows.call_args_list]
    assert upsert_tables == [
        "line_movement_events",
        "market_pick_evidence",
        "live_market_display_state",
        "shadow_notification_candidates",
        "game_reminder_state",
        "live_pick_state",
        "shadow_pipeline_runs",
    ]
    writer.insert_ignore_rows.assert_any_call(
        "notification_events",
        ANY,
        on_conflict="dedupe_key",
    )


def test_render_entrypoint_uses_propline_env_and_gated_therundown_capture():
    script = Path(build_live_events_to_supabase.__file__).read_text(encoding="utf-8")

    assert "PROPLINE_API_KEY" in script
    assert "poll_propline_to_supabase" in script
    assert "LIVE_CAPTURE_THERUNDOWN_MAINLINE" in script
    assert "poll_therundown_mainline_to_supabase" in script
    assert "fetch_odds(" not in script


def test_render_entrypoint_passes_therundown_flag_only_when_enabled(tmp_path, monkeypatch):
    stale_local = _write_artifact(tmp_path, [])
    remote_payload = {
        "date": "2026-05-07",
        "pitchers": [_fire_pitcher(game_time="2026-05-07T22:10:00Z")],
    }
    run_calls = []

    monkeypatch.setattr(build_live_events_to_supabase, "DEFAULT_ARTIFACT", stale_local)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.setenv("LIVE_CAPTURE_THERUNDOWN_MAINLINE", "true")
    monkeypatch.delenv("PROPLINE_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["build_live_events_to_supabase.py"])
    monkeypatch.setattr(
        build_live_events_to_supabase,
        "_load_artifact",
        lambda path, artifact_url=None: (
            remote_payload,
            "remote-sha",
            build_live_events_to_supabase.DEFAULT_ARTIFACT_URL,
        ),
    )

    def run(**kwargs):
        run_calls.append(kwargs)
        return {
            "live_pick_state": 1,
            "notification_events": 1,
            "line_movement_events": 0,
            "game_reminders": 0,
            "propline": {"skipped": True},
            "therundown": {"status": "completed", "datapoints": 199},
        }

    monkeypatch.setattr(build_live_events_to_supabase, "run", run)

    assert build_live_events_to_supabase.main() == 0

    assert run_calls[0]["poll_therundown_mainline"] is True


def test_render_entrypoint_leaves_therundown_capture_off_by_default(tmp_path, monkeypatch):
    stale_local = _write_artifact(tmp_path, [])
    remote_payload = {
        "date": "2026-05-07",
        "pitchers": [_fire_pitcher(game_time="2026-05-07T22:10:00Z")],
    }
    run_calls = []

    monkeypatch.setattr(build_live_events_to_supabase, "DEFAULT_ARTIFACT", stale_local)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.delenv("LIVE_CAPTURE_THERUNDOWN_MAINLINE", raising=False)
    monkeypatch.delenv("PROPLINE_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["build_live_events_to_supabase.py"])
    monkeypatch.setattr(
        build_live_events_to_supabase,
        "_load_artifact",
        lambda path, artifact_url=None: (
            remote_payload,
            "remote-sha",
            build_live_events_to_supabase.DEFAULT_ARTIFACT_URL,
        ),
    )

    def run(**kwargs):
        run_calls.append(kwargs)
        return {
            "live_pick_state": 1,
            "notification_events": 1,
            "line_movement_events": 0,
            "game_reminders": 0,
            "propline": {"skipped": True},
            "therundown": {"skipped": True},
        }

    monkeypatch.setattr(build_live_events_to_supabase, "run", run)

    assert build_live_events_to_supabase.main() == 0

    assert run_calls[0]["poll_therundown_mainline"] is False


def test_load_artifact_prefers_remote_url(tmp_path, monkeypatch):
    local = _write_artifact(tmp_path, [])
    remote_bytes = json.dumps({
        "date": "2026-05-07",
        "pitchers": [_fire_pitcher(game_time="2026-05-07T22:10:00Z")],
    }).encode("utf-8")

    class RemoteResponse:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return remote_bytes

    monkeypatch.setattr(
        build_live_events_to_supabase,
        "urlopen",
        lambda url, timeout: RemoteResponse(),
    )

    payload, artifact_sha, source = build_live_events_to_supabase._load_artifact(
        local,
        artifact_url="https://example.test/today.json",
    )

    assert payload["date"] == "2026-05-07"
    assert artifact_sha
    assert source == "https://example.test/today.json"


def test_load_artifact_falls_back_to_local_when_remote_url_fails(tmp_path, monkeypatch, capsys):
    local = _write_artifact(tmp_path, [_fire_pitcher()])

    def fail_remote(url, timeout):
        raise OSError("network unavailable")

    monkeypatch.setattr(build_live_events_to_supabase, "urlopen", fail_remote)

    payload, artifact_sha, source = build_live_events_to_supabase._load_artifact(
        local,
        artifact_url="https://example.test/today.json",
    )

    assert payload["date"] == "2026-05-06"
    assert artifact_sha
    assert Path(source).name == "today.json"
    assert "remote artifact fetch failed" in capsys.readouterr().err


def test_render_entrypoint_uses_remote_today_artifact_when_no_date_argument(tmp_path, monkeypatch, capsys):
    stale_local = _write_artifact(tmp_path, [])
    remote_payload = {
        "date": "2026-05-07",
        "pitchers": [_fire_pitcher(game_time="2026-05-07T22:10:00Z")],
    }
    run_calls = []

    monkeypatch.setattr(build_live_events_to_supabase, "DEFAULT_ARTIFACT", stale_local)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.delenv("PROPLINE_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["build_live_events_to_supabase.py"])

    def load_artifact(path, artifact_url=None):
        assert path == stale_local
        assert artifact_url == build_live_events_to_supabase.DEFAULT_ARTIFACT_URL
        return remote_payload, "remote-sha", build_live_events_to_supabase.DEFAULT_ARTIFACT_URL

    def run(**kwargs):
        run_calls.append(kwargs)
        return {
            "live_pick_state": 1,
            "notification_events": 1,
            "line_movement_events": 0,
            "game_reminders": 0,
            "propline": {"skipped": True},
            "alternative_pick_selection": {
                "skipped": False,
                "rows": 1,
                "provisional_rows": 0,
                "frozen_rows": 1,
            },
        }

    monkeypatch.setattr(build_live_events_to_supabase, "_load_artifact", load_artifact)
    monkeypatch.setattr(build_live_events_to_supabase, "run", run)

    assert build_live_events_to_supabase.main() == 0

    assert run_calls[0]["slate_date"] == "2026-05-07"
    assert run_calls[0]["artifact_url"] == build_live_events_to_supabase.DEFAULT_ARTIFACT_URL
    output = capsys.readouterr().out
    assert "date=2026-05-07" in output
    assert "artifact_source=remote" in output
    assert "alt_picks=rows:1 provisional:0 frozen:1" in output


def test_default_live_artifact_url_uses_get_artifact():
    assert "baseballbettingedge.netlify.app/.netlify/functions/get-artifact" in (
        build_live_events_to_supabase.DEFAULT_ARTIFACT_URL
    )
    assert "type=today" in build_live_events_to_supabase.DEFAULT_ARTIFACT_URL
    assert "raw.githubusercontent.com" not in build_live_events_to_supabase.DEFAULT_ARTIFACT_URL


def test_render_entrypoint_uses_remote_artifact_when_date_argument_matches(tmp_path, monkeypatch, capsys):
    stale_local = _write_artifact(tmp_path, [])
    remote_payload = {
        "date": "2026-05-07",
        "pitchers": [_fire_pitcher(game_time="2026-05-07T22:10:00Z")],
    }
    run_calls = []

    monkeypatch.setattr(build_live_events_to_supabase, "DEFAULT_ARTIFACT", stale_local)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.delenv("PROPLINE_API_KEY", raising=False)
    monkeypatch.setattr(sys, "argv", ["build_live_events_to_supabase.py", "2026-05-07"])

    def load_artifact(path, artifact_url=None):
        assert path == stale_local
        assert artifact_url == build_live_events_to_supabase.DEFAULT_ARTIFACT_URL
        return remote_payload, "remote-sha", build_live_events_to_supabase.DEFAULT_ARTIFACT_URL

    def run(**kwargs):
        run_calls.append(kwargs)
        return {
            "live_pick_state": 1,
            "notification_events": 1,
            "line_movement_events": 0,
            "game_reminders": 0,
            "propline": {"skipped": True},
        }

    monkeypatch.setattr(build_live_events_to_supabase, "_load_artifact", load_artifact)
    monkeypatch.setattr(build_live_events_to_supabase, "run", run)

    assert build_live_events_to_supabase.main() == 0

    assert run_calls[0]["slate_date"] == "2026-05-07"
    assert run_calls[0]["artifact_payload"] == remote_payload
    assert run_calls[0]["artifact_url"] == build_live_events_to_supabase.DEFAULT_ARTIFACT_URL
    assert "artifact_source=remote" in capsys.readouterr().out


def test_render_entrypoint_rejects_date_argument_when_remote_artifact_date_differs(tmp_path, monkeypatch, capsys):
    stale_local = _write_artifact(tmp_path, [])
    remote_payload = {"date": "2026-05-07", "pitchers": []}

    monkeypatch.setattr(build_live_events_to_supabase, "DEFAULT_ARTIFACT", stale_local)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "secret")
    monkeypatch.setattr(sys, "argv", ["build_live_events_to_supabase.py", "2026-05-08"])
    monkeypatch.setattr(
        build_live_events_to_supabase,
        "_load_artifact",
        lambda path, artifact_url=None: (
            remote_payload,
            "remote-sha",
            build_live_events_to_supabase.DEFAULT_ARTIFACT_URL,
        ),
    )

    assert build_live_events_to_supabase.main() == 2
    assert "does not match artifact date" in capsys.readouterr().err
