from unittest.mock import Mock, patch

from market_infra.supabase_writer import SupabaseMarketWriter


def test_writer_uses_service_role_header_without_logging_secret():
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = [{"id": "run-1"}]

    with patch("market_infra.supabase_writer.requests.post", return_value=response) as post:
        result = writer.insert_rows("market_provider_runs", [{"provider": "propline", "mode": "manual_probe"}])

    assert result == [{"id": "run-1"}]
    kwargs = post.call_args.kwargs
    assert kwargs["headers"]["apikey"] == "secret-key"
    assert kwargs["headers"]["Authorization"] == "Bearer secret-key"
    assert "secret-key" not in repr(kwargs["json"])


def test_upsert_rows_sets_conflict_target():
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = []

    with patch("market_infra.supabase_writer.requests.post", return_value=response) as post:
        writer.upsert_rows("market_snapshots", [{"dedupe_key": "abc"}], on_conflict="dedupe_key")

    assert post.call_args.kwargs["params"] == {"on_conflict": "dedupe_key"}
    assert post.call_args.kwargs["headers"]["Prefer"] == "resolution=merge-duplicates,return=representation"


def test_select_rows_passes_query_params_and_service_role_auth():
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = [{"current_verdict": "FIRE 1u"}]

    with patch("market_infra.supabase_writer.requests.get", return_value=response) as get:
        result = writer.select_rows("live_pick_state", {"slate_date": "eq.2026-05-06"})

    assert result == [{"current_verdict": "FIRE 1u"}]
    assert get.call_args.args == ("https://example.supabase.co/rest/v1/live_pick_state",)
    assert get.call_args.kwargs["params"] == {"slate_date": "eq.2026-05-06"}
    assert get.call_args.kwargs["headers"]["Authorization"] == "Bearer secret-key"
    assert get.call_args.kwargs["timeout"] == 20
