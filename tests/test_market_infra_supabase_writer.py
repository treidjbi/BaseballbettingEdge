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
