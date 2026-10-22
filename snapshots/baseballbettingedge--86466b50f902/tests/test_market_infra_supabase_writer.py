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


def test_upsert_rows_can_request_minimal_return_without_decoding_a_body():
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")
    response = Mock(status_code=204, text="")
    response.raise_for_status.return_value = None
    response.json.side_effect = AssertionError("minimal responses must not be decoded")

    with patch("market_infra.supabase_writer.requests.post", return_value=response) as post:
        result = writer.upsert_rows(
            "published_pipeline_artifacts",
            [{"artifact_key": "today"}],
            on_conflict="artifact_key",
            return_representation=False,
        )

    assert result == []
    assert post.call_args.kwargs["headers"]["Prefer"] == "resolution=merge-duplicates,return=minimal"


def test_upsert_rows_retries_one_selected_transient_database_error():
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")
    failing = Mock(status_code=500, text='{"code":"57014","message":"statement timeout"}')
    failing.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
    succeeding = Mock(status_code=204, text="")
    succeeding.raise_for_status.return_value = None

    with (
        patch("market_infra.supabase_writer.requests.post", side_effect=[failing, succeeding]) as post,
        patch("market_infra.supabase_writer.time.sleep") as sleep,
    ):
        result = writer.upsert_rows(
            "published_pipeline_artifacts",
            [{"artifact_key": "today"}],
            on_conflict="artifact_key",
            return_representation=False,
            attempts=2,
            retry_database_codes={"57014"},
        )

    assert result == []
    assert post.call_count == 2
    sleep.assert_called_once_with(0.5)


def test_upsert_rows_does_not_retry_selected_database_code_on_non_transient_status():
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")
    failing = Mock(status_code=400, text='{"code":"57014","message":"statement timeout"}')
    failing.raise_for_status.side_effect = requests.HTTPError("400 Client Error")

    with (
        patch("market_infra.supabase_writer.requests.post", return_value=failing) as post,
        patch("market_infra.supabase_writer.time.sleep") as sleep,
    ):
        try:
            writer.upsert_rows(
                "published_pipeline_artifacts",
                [{"artifact_key": "today"}],
                on_conflict="artifact_key",
                return_representation=False,
                attempts=2,
                retry_database_codes={"57014"},
            )
        except requests.HTTPError as error:
            assert "57014" in str(error)
        else:
            raise AssertionError("a non-transient status must fail without retrying")

    assert post.call_count == 1
    sleep.assert_not_called()


def test_upsert_rows_stops_after_one_retry_when_selected_error_repeats():
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")
    first = Mock(status_code=500, text='{"code":"57014","message":"statement timeout"}')
    first.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
    second = Mock(status_code=500, text='{"code":"57014","message":"statement timeout"}')
    second.raise_for_status.side_effect = requests.HTTPError("500 Server Error")

    with (
        patch("market_infra.supabase_writer.requests.post", side_effect=[first, second]) as post,
        patch("market_infra.supabase_writer.time.sleep") as sleep,
    ):
        try:
            writer.upsert_rows(
                "published_pipeline_artifacts",
                [{"artifact_key": "today"}],
                on_conflict="artifact_key",
                return_representation=False,
                attempts=2,
                retry_database_codes={"57014"},
            )
        except requests.HTTPError as error:
            assert "57014" in str(error)
        else:
            raise AssertionError("the second selected timeout must surface after one retry")

    assert post.call_count == 2
    sleep.assert_called_once_with(0.5)


def test_upsert_rows_does_not_retry_an_unselected_database_error():
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")
    failing = Mock(status_code=500, text='{"code":"23505","message":"duplicate key"}')
    failing.raise_for_status.side_effect = requests.HTTPError("500 Server Error")

    with (
        patch("market_infra.supabase_writer.requests.post", return_value=failing) as post,
        patch("market_infra.supabase_writer.time.sleep") as sleep,
    ):
        try:
            writer.upsert_rows(
                "published_pipeline_artifacts",
                [{"artifact_key": "today"}],
                on_conflict="artifact_key",
                return_representation=False,
                attempts=2,
                retry_database_codes={"57014"},
            )
        except requests.HTTPError as error:
            assert "23505" in str(error)
        else:
            raise AssertionError("an unselected database error must fail without retrying")

    assert post.call_count == 1
    sleep.assert_not_called()


def test_upsert_rows_error_includes_supabase_body_without_secret():
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")
    response = Mock()
    response.status_code = 400
    response.text = '{"message":"duplicate key in batch"}'
    response.raise_for_status.side_effect = requests.HTTPError("400 Client Error")

    with patch("market_infra.supabase_writer.requests.post", return_value=response):
        try:
            writer.upsert_rows(
                "market_pick_evidence",
                [{"dedupe_key": "abc"}, {"dedupe_key": "def"}],
                on_conflict="slate_date,normalized_pitcher,side,provider",
            )
        except requests.HTTPError as error:
            message = str(error)
        else:
            raise AssertionError("upsert_rows should raise HTTPError")

    assert "market_pick_evidence" in message
    assert "slate_date,normalized_pitcher,side,provider" in message
    assert "rows=2" in message
    assert "duplicate key in batch" in message
    assert "secret-key" not in message


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


def test_select_rows_accepts_a_single_attempt_budget_without_retrying():
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")
    response = Mock(status_code=500)
    error = requests.HTTPError("500 Server Error")
    error.response = response
    response.raise_for_status.side_effect = error

    with (
        patch("market_infra.supabase_writer.requests.get", return_value=response) as get,
        patch("market_infra.supabase_writer.time.sleep") as sleep,
    ):
        try:
            writer.select_rows(
                "alternative_pick_selection_state",
                {"slate_date": "eq.2026-05-06"},
                timeout_seconds=1.25,
                attempts=1,
            )
        except requests.HTTPError:
            pass
        else:
            raise AssertionError("single-attempt select should raise its first failure")

    assert get.call_count == 1
    assert get.call_args.kwargs["timeout"] == 1.25
    sleep.assert_not_called()


def test_write_methods_accept_caller_supplied_timeout():
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = []

    with patch("market_infra.supabase_writer.requests.post", return_value=response) as post:
        writer.upsert_rows(
            "alternative_pick_selection_state",
            [{"checkpoint": "provisional"}],
            on_conflict="slate_date,game_identity,normalized_pitcher,side,bundle_id,checkpoint",
            timeout_seconds=2.5,
        )
        writer.insert_ignore_rows(
            "alternative_pick_selection_state",
            [{"checkpoint": "frozen_pregame"}],
            on_conflict="slate_date,game_identity,normalized_pitcher,side,bundle_id,checkpoint",
            timeout_seconds=2.5,
        )

    assert [call.kwargs["timeout"] for call in post.call_args_list] == [2.5, 2.5]


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


def test_update_rows_calls_patch_with_supplied_params(monkeypatch):
    captured = {}

    class Response:
        headers = {"Content-Range": "0-0/1"}

        def raise_for_status(self):
            return None

    def fake_patch(url, headers, params, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["params"] = params
        captured["json"] = json
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr("market_infra.supabase_writer.requests.patch", fake_patch)
    writer = SupabaseMarketWriter("https://example.supabase.co", "secret-key")

    updated = writer.update_rows(
        "operational_pick_locks",
        {"dedupe_key": "eq.2026-05-21:casey mize:under"},
        {"consumed_at": "2026-05-21T17:00:31+00:00"},
    )

    assert updated == 1
    assert captured["url"] == "https://example.supabase.co/rest/v1/operational_pick_locks"
    assert captured["headers"]["Prefer"] == "return=minimal,count=exact"
    assert captured["params"] == {"dedupe_key": "eq.2026-05-21:casey mize:under"}
    assert captured["json"] == {"consumed_at": "2026-05-21T17:00:31+00:00"}
    assert captured["timeout"] == 20
