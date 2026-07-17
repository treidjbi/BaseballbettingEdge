from datetime import datetime, timezone

import pytest

from market_infra.ready_to_bet_shadow import build_ready_to_bet_shadow


NOW = datetime(2026, 7, 17, 18, 0, tzinfo=timezone.utc)


def _pitcher(**overrides):
    row = {
        "pitcher": "Tarik Skubal",
        "k_line": 6.5,
        "game_time": "2026-07-17T23:10:00Z",
        "game_state": "scheduled",
        "quality_gate_level": "clean",
        "ev_over": {"verdict": "FIRE 1u", "quality_gate_level": "clean"},
    }
    row.update(overrides)
    return row


def _state(**overrides):
    row = {
        "slate_date": "2026-07-17",
        "pitcher": "Tarik Skubal",
        "normalized_pitcher": "tarik skubal",
        "side": "over",
        "current_verdict": "FIRE 1u",
        "k_line": 6.5,
        "game_time": "2026-07-17T23:10:00Z",
        "game_state": "scheduled",
        "is_locked": False,
        "metadata": {},
    }
    row.update(overrides)
    return row


def _market(**overrides):
    row = {
        "slate_date": "2026-07-17",
        "pitcher": "Tarik Skubal",
        "normalized_pitcher": "tarik skubal",
        "side": "over",
        "provider": "therundown_propline",
        "k_line": 6.5,
        "best_book": "fanduel",
        "best_line": 6.5,
        "best_odds": 105,
        "freshness_status": "fresh",
        "market_consensus": "toward_pick",
        "bet_value_consensus": "better_now",
        "book_count": 3,
        "books_seen": ["fanduel", "draftkings", "betrivers"],
        "broad_confirmation": True,
        "dedupe_key": "market-row",
    }
    row.update(overrides)
    return row


def _build(**overrides):
    args = {
        "slate_date": "2026-07-17",
        "pitchers": [_pitcher()],
        "state_rows": [_state()],
        "previous_state_rows": [],
        "live_market_rows": [_market()],
        "accepted_bets": [],
        "accepted_bets_available": True,
        "notification_rows": [],
        "observed_at": NOW,
        "mode": "record",
    }
    args.update(overrides)
    return build_ready_to_bet_shadow(**args)


def test_clean_unlocked_fire_with_fresh_same_line_becomes_ready():
    result = _build()

    assert result.state_rows[0]["metadata"]["decision_state"] == "ready"
    assert result.summary["state_counts"] == {"ready": 1}
    assert len(result.candidate_rows) == 1
    assert result.candidate_rows[0]["candidate_type"] == "ready_to_bet"
    assert result.candidate_rows[0]["dedupe_key"] == "2026-07-17:ready_to_bet:tarik skubal:over"


@pytest.mark.parametrize(
    ("changes", "expected_state", "expected_reason"),
    [
        ({"state_rows": [_state(current_verdict="LEAN")]}, "watching", "not_fire"),
        ({"pitchers": [_pitcher(quality_gate_level="capped", ev_over={"verdict": "FIRE 1u", "quality_gate_level": "capped"})]}, "watching", "quality_not_clean"),
        ({"live_market_rows": [_market(freshness_status="stale")]}, "watching", "same_line_market_unavailable"),
        ({"live_market_rows": [_market(best_line=2.5)]}, "watching", "same_line_market_unavailable"),
        ({"accepted_bets": [{"slate_date": "2026-07-17", "normalized_pitcher": "tarik skubal", "side": "over"}]}, "logged", "accepted_bet_logged"),
        ({"state_rows": [_state(is_locked=True)]}, "locked", "pick_locked"),
        ({"state_rows": [_state(game_state="in_progress")]}, "started", "game_started"),
        ({"accepted_bets_available": False}, "watching", "accepted_bet_state_unavailable"),
    ],
)
def test_non_ready_states_fail_closed(changes, expected_state, expected_reason):
    result = _build(**changes)

    metadata = result.state_rows[0]["metadata"]
    assert metadata["decision_state"] == expected_state
    assert expected_reason in metadata["decision_reasons"]
    assert result.candidate_rows == []


def test_only_transition_into_ready_creates_candidate():
    previous = [_state(metadata={"decision_state": "ready"})]

    result = _build(previous_state_rows=previous)

    assert result.state_rows[0]["metadata"]["decision_state"] == "ready"
    assert result.candidate_rows == []


def test_boltodds_cannot_qualify():
    result = _build(live_market_rows=[_market(provider="boltodds")])

    assert result.state_rows[0]["metadata"]["decision_state"] == "watching"
    assert result.candidate_rows == []


def test_off_mode_is_noop():
    source = [_state()]

    result = _build(state_rows=source, mode="off")

    assert result.state_rows == source
    assert result.candidate_rows == []
    assert result.summary["mode"] == "off"
