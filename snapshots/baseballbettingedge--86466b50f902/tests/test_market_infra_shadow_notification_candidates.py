from market_infra.shadow_notification_candidates import build_shadow_notification_candidate_rows


def _evidence(**overrides):
    row = {
        "slate_date": "2026-05-08",
        "pitcher": "Tarik Skubal",
        "normalized_pitcher": "tarik skubal",
        "side": "over",
        "provider": "boltodds",
        "current_verdict": "FIRE 1u",
        "k_line": 6.5,
        "game_time": "2026-05-08T18:05:00+00:00",
        "game_state": "scheduled",
        "is_fire": True,
        "is_locked": False,
        "observed_at": "2026-05-08T17:58:00+00:00",
        "latest_snapshot_at": "2026-05-08T17:58:00+00:00",
        "book_count": 3,
        "books_seen": ["betmgm", "fanduel", "caesars"],
        "toward_pick_count": 3,
        "away_from_pick_count": 0,
        "better_now_count": 2,
        "worse_now_count": 0,
        "touching_pick_line_count": 2,
        "market_consensus": "toward_pick",
        "bet_value_consensus": "better_now",
        "minutes_to_game": 7,
        "time_window": "pre_15",
        "reversal_book_count": 0,
        "volatile_book_count": 0,
        "dedupe_key": "2026-05-08:market_evidence:boltodds:tarik skubal:over",
        "metadata": {"book_summaries": {}},
    }
    row.update(overrides)
    return row


def test_confirmed_playable_broad_near_game_candidate_would_send_in_shadow():
    rows = build_shadow_notification_candidate_rows([_evidence()])

    assert len(rows) == 1
    row = rows[0]
    assert row["candidate_type"] == "market_confirmed_playable"
    assert row["candidate_action"] == "would_send_shadow"
    assert row["playable_state"] == "playable_now"
    assert row["broad_confirmation"] is True
    assert row["single_book"] is False
    assert row["betrivers_only"] is False
    assert row["suppression_reasons"] == []
    assert row["dedupe_key"] == (
        "2026-05-08:shadow_candidate:boltodds:tarik skubal:over:"
        "market_confirmed_playable:2026-05-08T17:58:00+00:00"
    )


def test_betrivers_only_confirmed_worse_number_is_suppressed():
    rows = build_shadow_notification_candidate_rows([
        _evidence(
            provider="propline",
            books_seen=["betrivers"],
            book_count=1,
            toward_pick_count=1,
            better_now_count=0,
            worse_now_count=1,
            touching_pick_line_count=1,
            bet_value_consensus="worse_now",
            dedupe_key="2026-05-08:market_evidence:propline:tarik skubal:over",
        )
    ])

    assert len(rows) == 1
    row = rows[0]
    assert row["candidate_type"] == "market_confirmed_worse_number"
    assert row["candidate_action"] == "suppress_shadow"
    assert row["playable_state"] == "number_worse"
    assert row["single_book"] is True
    assert row["betrivers_only"] is True
    assert row["suppression_reasons"] == [
        "number_worse",
        "not_broad_confirmation",
        "betrivers_only",
    ]


def test_reversal_or_volatility_suppresses_otherwise_sendable_candidate():
    rows = build_shadow_notification_candidate_rows([
        _evidence(reversal_book_count=1, volatile_book_count=1)
    ])

    assert len(rows) == 1
    row = rows[0]
    assert row["candidate_type"] == "market_confirmed_playable"
    assert row["candidate_action"] == "suppress_shadow"
    assert "volatile_or_reversed" in row["suppression_reasons"]


def test_market_fade_with_better_number_is_tracked_but_not_sendable():
    rows = build_shadow_notification_candidate_rows([
        _evidence(
            market_consensus="away_from_pick",
            bet_value_consensus="better_now",
            toward_pick_count=0,
            away_from_pick_count=2,
        )
    ])

    assert len(rows) == 1
    row = rows[0]
    assert row["candidate_type"] == "better_number_market_fade"
    assert row["candidate_action"] == "suppress_shadow"
    assert "market_not_confirmed" in row["suppression_reasons"]


def test_stale_market_evidence_suppresses_otherwise_sendable_candidate():
    rows = build_shadow_notification_candidate_rows([
        _evidence(
            metadata={
                "freshness_status": "stale",
                "freshness_seconds": 3600,
                "line_freshness_seconds": 3600,
                "heartbeat_hold": False,
                "book_summaries": {},
            }
        )
    ])

    assert len(rows) == 1
    row = rows[0]
    assert row["candidate_type"] == "market_confirmed_playable"
    assert row["candidate_action"] == "suppress_shadow"
    assert "stale_market_evidence" in row["suppression_reasons"]
    assert row["metadata"]["market_evidence"]["freshness_status"] == "stale"


def test_movement_strength_labels_describe_boltodds_broad_confirmation():
    rows = build_shadow_notification_candidate_rows([_evidence(provider="boltodds")])

    labels = rows[0]["metadata"]["movement_strength_labels"]

    assert "broad_confirmation" in labels
    assert "boltodds_confirmed" in labels
    assert "single_book" not in labels
    assert "stale_or_heartbeat_missing" not in labels


def test_movement_strength_labels_describe_propline_noise_and_webhook_confirmation():
    rows = build_shadow_notification_candidate_rows([
        _evidence(
            provider="propline",
            book_count=1,
            books_seen=["betrivers"],
            toward_pick_count=1,
            metadata={
                "freshness_status": "stale",
                "propline_webhook_confirmed": True,
                "book_summaries": {},
            },
        )
    ])

    labels = rows[0]["metadata"]["movement_strength_labels"]

    assert "single_book" in labels
    assert "propline_polling_confirmed" in labels
    assert "propline_webhook_confirmed" in labels
    assert "stale_or_heartbeat_missing" in labels


def test_movement_strength_labels_include_provider_conflict_for_mixed_market():
    rows = build_shadow_notification_candidate_rows([
        _evidence(
            market_consensus="mixed",
            bet_value_consensus="mixed",
            toward_pick_count=1,
            away_from_pick_count=1,
        )
    ])

    assert "provider_conflict" in rows[0]["metadata"]["movement_strength_labels"]
