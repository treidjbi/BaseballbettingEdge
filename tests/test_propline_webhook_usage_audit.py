from analytics.diagnostics.propline_webhook_usage_audit import summarize_webhook_usage


def test_summarize_webhook_rows_counts_signed_processed_and_book_metadata():
    summary = summarize_webhook_usage(
        deliveries=[
            {
                "id": "1",
                "signature_valid": True,
                "processed": True,
                "processing_error": None,
                "received_at": "2026-06-19T16:00:00+00:00",
                "payload": {
                    "event_type": "line_movement",
                    "bookmaker_key": "draftkings",
                    "bookmaker_title": "DraftKings",
                    "market_id": "m1",
                    "outcome_id": "o1",
                },
            }
        ],
        movement_events=[],
        notification_events=[],
        market_pick_evidence=[],
        accepted_bets=[],
    )

    assert summary["deliveries"] == 1
    assert summary["signed_deliveries"] == 1
    assert summary["processed_deliveries"] == 1
    assert summary["with_bookmaker_key"] == 1
    assert summary["with_stable_market_ids"] == 1


def test_summarize_webhook_rows_recommends_dashboard_badge_not_source_switch_for_webhook_only_moves():
    summary = summarize_webhook_usage(
        deliveries=[],
        movement_events=[
            {
                "source": "propline_webhook",
                "bookmaker_key": "fanduel",
                "movement_kind": "odds",
                "observed_at": "2026-06-19T16:00:00+00:00",
            }
        ],
        notification_events=[],
        market_pick_evidence=[],
        accepted_bets=[],
    )

    assert "dashboard_webhook_confirmed_badge" in summary["recommended_uses"]
    assert "official_odds_source" not in summary["recommended_uses"]


def test_summarize_webhook_rows_keeps_blocked_uses_closed():
    summary = summarize_webhook_usage(
        deliveries=[],
        movement_events=[],
        notification_events=[],
        market_pick_evidence=[],
        accepted_bets=[],
    )

    assert summary["blocked_uses"] == [
        "official_odds_source",
        "model_input",
        "staking_input",
        "automatic_bet_trigger",
    ]


def test_summarize_webhook_rows_counts_duplicates_stale_and_confirmed_overlap():
    summary = summarize_webhook_usage(
        deliveries=[],
        movement_events=[
            {
                "dedupe_key": "same",
                "metadata": {"source": "propline_webhook", "polling_confirmed": True},
            },
            {
                "dedupe_key": "same",
                "metadata": {"source": "propline_webhook", "freshness_status": "stale"},
            },
            {
                "dedupe_key": "other",
                "metadata": {"source": "propline_polling"},
            },
        ],
        notification_events=[
            {"event_type": "line_movement", "payload": {"source": "propline_webhook"}},
            {"event_type": "lock_reminder", "payload": {"source": "scheduler"}},
        ],
        market_pick_evidence=[
            {"metadata": {"propline_webhook_confirmed": True}},
        ],
        accepted_bets=[
            {"metadata": {"propline_webhook_confirmed": True}},
            {"metadata": {"source": "manual"}},
        ],
    )

    assert summary["duplicate_dedupe_keys"] == 1
    assert summary["post_start_or_stale_events"] == 1
    assert summary["polling_confirmed_movement_events"] == 1
    assert summary["webhook_only_movement_events"] == 1
    assert summary["webhook_notification_events"] == 1
    assert summary["accepted_bet_overlap_count"] == 1
    assert "movement_strength_label" in summary["recommended_uses"]
    assert "notification_priority_boost" in summary["recommended_uses"]
    assert "accepted_bet_context_tag" in summary["recommended_uses"]
    assert "provider_refresh_trigger_shadow" in summary["recommended_uses"]
