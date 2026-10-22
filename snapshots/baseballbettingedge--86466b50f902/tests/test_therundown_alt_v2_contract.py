from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))

from build_features import build_pitcher_record
from fetch_odds import _parse_event_k_props
from market_infra.alternative_pick_preclose_v2 import resolve_candidate_bindings_v2
from market_infra.therundown_snapshot import snapshots_from_therundown_events


SLATE_DATE = "2026-07-23"
GAME_TIME = "2026-07-23T23:05:00Z"
EVENT_ID = "tr-event-exact"


def _event() -> dict:
    return {
        "event_id": f"  {EVENT_ID}  ",
        "event_date": GAME_TIME,
        "markets": [{
            "market_id": 19,
            "participants": [{
                "id": "pitcher-1",
                "name": "Gerrit Cole",
                "lines": [
                    {
                        "value": "Over 7.5",
                        "prices": {
                            "23": {
                                "price": -115,
                                "is_main_line": True,
                                "price_delta": 0,
                            },
                        },
                    },
                    {
                        "value": "Under 7.5",
                        "prices": {
                            "23": {
                                "price": -105,
                                "is_main_line": True,
                                "price_delta": 0,
                            },
                        },
                    },
                ],
            }],
        }],
    }


def _stats() -> dict:
    return {
        "team": "NYY",
        "opp_team": "BOS",
        "season_k9": 9.0,
        "recent_k9": 9.0,
        "career_k9": 9.0,
        "starts_count": 5,
        "innings_pitched_season": 30.0,
        "avg_ip_last5": 6.0,
        "recent_start_ips": [6.0, 6.0, 6.0, 6.0, 6.0],
        "opp_k_rate": 0.227,
    }


def _candidate() -> dict:
    return {
        "slate_date": SLATE_DATE,
        "pitcher": "Gerrit Cole",
        "normalized_pitcher": "gerrit cole",
        "side": "over",
        "model_k_line": 7.5,
        "game_time": GAME_TIME,
        "candidate_identity": "candidate-exact-event",
        "provider_posture": "therundown",
    }


def _persisted_snapshots(event: dict) -> list[dict]:
    rows = snapshots_from_therundown_events(
        [event],
        observed_at="2026-07-23T20:00:00+00:00",
    )
    identifiers = (
        "11111111-1111-4111-8111-111111111111",
        "22222222-2222-4222-8222-222222222222",
    )
    return [
        {**row, "id": identifier, "slate_date": SLATE_DATE}
        for row, identifier in zip(rows, identifiers, strict=True)
    ]


def test_direct_therundown_event_identity_survives_artifact_and_binds_exact_v2_evidence():
    event = _event()
    odds = _parse_event_k_props(event)
    assert len(odds) == 1

    pitcher = build_pitcher_record(odds[0], _stats(), ump_k_adj=0.0)
    snapshots = _persisted_snapshots(event)
    exact = resolve_candidate_bindings_v2(
        candidate=_candidate(),
        pitcher=pitcher,
        current_lines_by_id={},
        snapshot_rows=snapshots,
    )

    assert pitcher["line_source_provider"] == "therundown"
    assert pitcher["therundown_event_id"] == EVENT_ID
    assert {row["provider_event_id"] for row in snapshots} == {EVENT_ID}
    assert exact["ready"] is True
    assert exact["official_provider"] == "therundown"
    assert exact["official_binding"]["provider_event_id"] == EVENT_ID

    for invalid_pitcher in (
        {key: value for key, value in pitcher.items() if key != "therundown_event_id"},
        {**pitcher, "therundown_event_id": "different-event"},
    ):
        invalid = resolve_candidate_bindings_v2(
            candidate=_candidate(),
            pitcher=invalid_pitcher,
            current_lines_by_id={},
            snapshot_rows=snapshots,
        )
        assert invalid["ready"] is False
        assert invalid["official_binding"] is None
