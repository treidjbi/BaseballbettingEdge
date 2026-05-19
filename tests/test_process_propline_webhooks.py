from unittest.mock import Mock, patch

from scripts import process_propline_webhooks


def _delivery(payload, **overrides):
    row = {
        "id": "delivery-row-1",
        "prop_line_delivery_id": "6094",
        "prop_line_event": "line_movement",
        "prop_line_timestamp": "2026-05-19T20:37:50+00:00",
        "signature_valid": True,
        "processed": False,
        "processing_error": None,
        "payload": payload,
        "received_at": "2026-05-19T20:37:52.924673+00:00",
    }
    row.update(overrides)
    return row


def _line_movement_payload():
    return {
        "event": {
            "id": 24491,
            "away_team": "Cincinnati Reds",
            "home_team": "Philadelphia Phillies",
            "external_id": "pm-481011",
            "commence_time": "2026-05-19T22:40:00+00:00",
        },
        "current": {"point": 5.5, "price_american": 112},
        "previous": {"point": 6.5, "price_american": -150},
        "sport_key": "baseball_mlb",
        "timestamp": "2026-05-19T20:37:42.982116+00:00",
        "event_type": "line_movement",
        "market_key": "pitcher_strikeouts",
        "player_name": "Chase Burns",
        "outcome_name": "Under",
        "price_change_pct": 27.2,
    }


def test_processor_skips_invalid_signature_rows():
    writer = Mock()
    writer.select_rows.return_value = [
        _delivery(_line_movement_payload(), signature_valid=False)
    ]

    with patch.object(process_propline_webhooks, "SupabaseMarketWriter", return_value=writer):
        result = process_propline_webhooks.run(
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result == {
        "deliveries": 1,
        "processed": 0,
        "line_movement_events": 0,
        "unsupported": 1,
    }
    writer.upsert_rows.assert_called_once_with(
        "propline_webhook_deliveries",
        [{
            "id": "delivery-row-1",
            "processed": True,
            "processing_error": "invalid_signature",
        }],
        on_conflict="id",
    )


def test_processor_marks_unknown_payload_shape():
    writer = Mock()
    writer.select_rows.return_value = [_delivery({"unexpected": True})]

    with patch.object(process_propline_webhooks, "SupabaseMarketWriter", return_value=writer):
        result = process_propline_webhooks.run(
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result["processed"] == 0
    assert result["line_movement_events"] == 0
    assert result["unsupported"] == 1
    writer.upsert_rows.assert_called_once_with(
        "propline_webhook_deliveries",
        [{
            "id": "delivery-row-1",
            "processed": True,
            "processing_error": "unsupported_payload_shape",
        }],
        on_conflict="id",
    )


def test_processor_writes_neutral_line_movement_event_from_real_payload_shape():
    writer = Mock()
    writer.select_rows.return_value = [_delivery(_line_movement_payload())]

    with patch.object(process_propline_webhooks, "SupabaseMarketWriter", return_value=writer):
        result = process_propline_webhooks.run(
            supabase_url="https://example.supabase.co",
            service_role_key="secret",
        )

    assert result == {
        "deliveries": 1,
        "processed": 1,
        "line_movement_events": 1,
        "unsupported": 0,
    }
    movement_call = writer.upsert_rows.call_args_list[0]
    assert movement_call.args[0] == "line_movement_events"
    assert movement_call.kwargs == {"on_conflict": "dedupe_key"}
    assert movement_call.args[1] == [{
        "slate_date": "2026-05-19",
        "normalized_pitcher": "chase burns",
        "pitcher": "Chase Burns",
        "side": "under",
        "bookmaker_key": "propline_webhook",
        "previous_line": 6.5,
        "current_line": 5.5,
        "previous_odds": -150,
        "current_odds": 112,
        "movement_direction": "neutral",
        "movement_kind": "line_and_odds",
        "observed_at": "2026-05-19T20:37:42.982116+00:00",
        "dedupe_key": "2026-05-19:propline_webhook:6094",
        "source_snapshot_id": None,
        "metadata": {
            "bookmaker_key_missing": True,
            "event_type": "line_movement",
            "market_key": "pitcher_strikeouts",
            "price_change_pct": 27.2,
            "prop_line_delivery_id": "6094",
            "prop_line_event_id": 24491,
            "provider_event_id": "pm-481011",
            "source": "propline_webhook",
            "sport_key": "baseball_mlb",
            "teams": {
                "away": "Cincinnati Reds",
                "home": "Philadelphia Phillies",
            },
        },
    }]

    delivery_call = writer.upsert_rows.call_args_list[1]
    assert delivery_call.args[0] == "propline_webhook_deliveries"
    assert delivery_call.args[1] == [{
        "id": "delivery-row-1",
        "processed": True,
        "processing_error": None,
    }]
    assert delivery_call.kwargs == {"on_conflict": "id"}
