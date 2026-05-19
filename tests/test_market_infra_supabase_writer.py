from unittest.mock import Mock, patch

import requests

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


def test_insert_ignore_rows_sets_conflict_target_without_merging():
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = []

    with patch("market_infra.supabase_writer.requests.post", return_value=response) as post:
        writer.insert_ignore_rows(
            "market_opening_baselines",
            [{"slate_date": "2026-05-13"}],
            on_conflict="slate_date,normalized_player_name,market_key,book_key,line",
        )

    assert post.call_args.kwargs["params"] == {
        "on_conflict": "slate_date,normalized_player_name,market_key,book_key,line"
    }
    assert post.call_args.kwargs["headers"]["Prefer"] == "resolution=ignore-duplicates,return=representation"


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


def test_select_rows_retries_transient_server_errors():
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")
    failing = Mock(status_code=500)
    error = requests.HTTPError("500 Server Error")
    error.response = failing
    failing.raise_for_status.side_effect = error
    succeeding = Mock(status_code=200)
    succeeding.raise_for_status.return_value = None
    succeeding.json.return_value = [{"id": "snap-1"}]

    with (
        patch("market_infra.supabase_writer.requests.get", side_effect=[failing, succeeding]) as get,
        patch("market_infra.supabase_writer.time.sleep") as sleep,
    ):
        result = writer.select_rows("market_snapshots", {"limit": "2500"})

    assert result == [{"id": "snap-1"}]
    assert get.call_count == 2
    sleep.assert_called_once()


def test_count_rows_reads_content_range(monkeypatch):
    captured = {}

    class Response:
        headers = {"Content-Range": "0-0/42"}
        status_code = 206

        def raise_for_status(self):
            return None

    def fake_get(url, headers, params, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["params"] = params
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("market_infra.supabase_writer.requests.get", fake_get)
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")

    assert writer.count_rows("market_snapshots", {"provider": "eq.boltodds"}) == 42
    assert captured["url"] == "https://example.supabase.co/rest/v1/market_snapshots"
    assert captured["headers"]["Prefer"] == "count=exact"
    assert captured["params"]["provider"] == "eq.boltodds"
    assert captured["params"]["select"] == "*"
    assert captured["params"]["limit"] == "1"
    assert captured["timeout"] == 20


def test_count_rows_uses_wildcard_select_for_no_id_tables(monkeypatch):
    captured = {}

    class Response:
        headers = {"Content-Range": "0-0/5"}

        def raise_for_status(self):
            return None

    def fake_get(url, headers, params, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["params"] = params
        return Response()

    monkeypatch.setattr("market_infra.supabase_writer.requests.get", fake_get)
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")

    assert writer.count_rows("provider_request_usage_daily", {}) == 5
    assert captured["url"] == "https://example.supabase.co/rest/v1/provider_request_usage_daily"
    assert captured["headers"]["Prefer"] == "count=exact"
    assert captured["params"]["select"] == "*"
    assert captured["params"]["limit"] == "1"


def test_delete_rows_requires_params():
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")

    try:
        writer.delete_rows("market_snapshots", {})
    except ValueError as error:
        assert "delete params are required" in str(error)
    else:
        raise AssertionError("delete_rows should reject empty params")


def test_delete_rows_calls_delete_with_supplied_params(monkeypatch):
    captured = {}

    class Response:
        headers = {"Content-Range": "0-2/3"}

        def raise_for_status(self):
            return None

    def fake_delete(url, headers, params, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["params"] = params
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("market_infra.supabase_writer.requests.delete", fake_delete)
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")

    deleted = writer.delete_rows("market_snapshots", {"observed_at": "lt.2026-05-01T00:00:00+00:00"})

    assert deleted == 3
    assert captured["url"] == "https://example.supabase.co/rest/v1/market_snapshots"
    assert captured["headers"]["Prefer"] == "return=minimal,count=exact"
    assert captured["params"] == {"observed_at": "lt.2026-05-01T00:00:00+00:00"}
    assert captured["timeout"] == 20
