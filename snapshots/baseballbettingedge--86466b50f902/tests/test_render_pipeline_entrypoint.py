import json
from urllib.parse import parse_qs, urlparse

import pytest

from scripts import run_render_pipeline_mode as entrypoint


def test_publish_contract_for_grading_uses_prior_slate_and_grading_scope():
    contract = entrypoint.build_publish_contract("grading", "2026-05-26")

    assert contract.pipeline_args[-3:] == ["2026-05-26", "--run-type", "grading"]
    assert contract.publish_date == "2026-05-25"
    assert contract.publish_scope == "grading"
    assert contract.pipeline_run_type == "grading"


def test_publish_contract_for_pipeline_uses_current_slate_and_pipeline_scope():
    contract = entrypoint.build_publish_contract("pipeline", "2026-05-26")

    assert contract.pipeline_args[-1] == "2026-05-26"
    assert "--run-type" not in contract.pipeline_args
    assert contract.publish_date == "2026-05-26"
    assert contract.publish_scope == "pipeline"
    assert contract.pipeline_run_type == "full"


def test_publish_contract_for_preview_uses_current_slate_and_preview_scope():
    contract = entrypoint.build_publish_contract("preview", "2026-05-26")

    assert contract.pipeline_args[-3:] == ["2026-05-26", "--run-type", "preview"]
    assert contract.publish_date == "2026-05-26"
    assert contract.publish_scope == "preview"
    assert contract.pipeline_run_type == "preview"


def test_publish_contract_for_lock_uses_current_slate_and_lock_scope():
    contract = entrypoint.build_publish_contract("lock", "2026-05-26")

    assert contract.pipeline_args[-3:] == ["2026-05-26", "--run-type", "lock"]
    assert contract.publish_date == "2026-05-26"
    assert contract.publish_scope == "lock"
    assert contract.pipeline_run_type == "lock"


def test_shadow_prefix_uses_publish_date_not_run_date():
    contract = entrypoint.build_publish_contract("grading", "2026-05-26")

    assert entrypoint.resolve_artifact_key_prefix(contract, shadow_prefix=True, explicit_prefix="") == (
        "render_shadow:2026-05-25:"
    )


def test_shadow_runtime_overrides_disable_official_mutation_paths():
    overrides = entrypoint.shadow_runtime_env_overrides("render_shadow:2026-05-26:")

    assert overrides["ENABLE_SUPABASE_LOCK_CONSUMER"] == "false"
    assert overrides["SUPABASE_LOCK_CONSUMER_STRICT"] == "false"
    assert overrides["OFFICIAL_MARKET_SOURCE"] == "therundown"
    assert overrides["ENABLE_BOLTODDS_PIPELINE_SOURCE"] == "false"
    assert overrides["BATTER_SPLIT_COLLECTION_MAX_NEW"] == "0"


def test_shadow_provider_rehearsal_enables_provider_adapter_but_not_lock_consumer():
    overrides = entrypoint.shadow_runtime_env_overrides(
        "render_shadow:2026-05-26:",
        provider_rehearsal=True,
    )

    assert overrides["ENABLE_SUPABASE_LOCK_CONSUMER"] == "false"
    assert overrides["SUPABASE_LOCK_CONSUMER_STRICT"] == "false"
    assert overrides["OFFICIAL_MARKET_SOURCE"] == "boltodds_propline"
    assert overrides["ENABLE_BOLTODDS_PIPELINE_SOURCE"] == "true"
    assert overrides["OFFICIAL_MARKET_STRICT"] == "true"
    assert overrides["BATTER_SPLIT_COLLECTION_MAX_NEW"] == "0"


def test_shadow_runtime_overrides_are_empty_for_live_key_publish():
    assert entrypoint.shadow_runtime_env_overrides("") == {}


def test_live_official_provider_uses_therundown_plus_propline_for_live_preview_and_pipeline():
    for mode in ("preview", "pipeline"):
        overrides = entrypoint.runtime_env_overrides(mode, "")

        assert overrides["OFFICIAL_MARKET_SOURCE"] == "therundown_propline"
        assert overrides["OFFICIAL_MARKET_SOURCE_FALLBACK"] == "therundown"
        assert overrides["ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE"] == "true"
        assert overrides["ENABLE_BOLTODDS_PIPELINE_SOURCE"] == "false"
        assert overrides["OFFICIAL_MARKET_STRICT"] == "false"


def test_live_official_provider_does_not_touch_grading_lock_or_shadow_runs():
    assert entrypoint.runtime_env_overrides("grading", "") == {}
    assert entrypoint.runtime_env_overrides("lock", "") == {}

    shadow_overrides = entrypoint.runtime_env_overrides("pipeline", "render_shadow:2026-05-26:")
    assert shadow_overrides["OFFICIAL_MARKET_SOURCE"] == "therundown"
    assert shadow_overrides["ENABLE_BOLTODDS_PIPELINE_SOURCE"] == "false"


def test_shadow_provider_rehearsal_stays_strict_and_shadow_only():
    overrides = entrypoint.runtime_env_overrides(
        "pipeline",
        "render_shadow:2026-05-26:",
        provider_rehearsal=True,
    )

    assert overrides["OFFICIAL_MARKET_SOURCE"] == "boltodds_propline"
    assert overrides["ENABLE_BOLTODDS_PIPELINE_SOURCE"] == "true"
    assert overrides["OFFICIAL_MARKET_STRICT"] == "true"
    assert overrides["ENABLE_SUPABASE_LOCK_CONSUMER"] == "false"


def test_provider_rehearsal_requires_explicit_reopened_boltodds_trial(monkeypatch):
    monkeypatch.delenv("ALLOW_BOLTODDS_PROVIDER_REHEARSAL", raising=False)

    with pytest.raises(ValueError, match="BoltOdds provider rehearsal is retired"):
        entrypoint.validate_provider_rehearsal_allowed(provider_rehearsal=True)


def test_provider_rehearsal_validation_allows_explicit_reopened_trial(monkeypatch):
    monkeypatch.setenv("ALLOW_BOLTODDS_PROVIDER_REHEARSAL", "true")

    entrypoint.validate_provider_rehearsal_allowed(provider_rehearsal=True)


def test_live_artifact_hydration_runs_for_modes_that_consume_live_artifacts(monkeypatch):
    monkeypatch.delenv("RENDER_PIPELINE_HYDRATE_ARTIFACTS", raising=False)

    assert entrypoint.live_artifact_hydration_enabled("lock", "") is True
    assert entrypoint.live_artifact_hydration_enabled("pipeline", "") is True
    assert entrypoint.live_artifact_hydration_enabled("grading", "") is True
    assert entrypoint.live_artifact_hydration_enabled("preview", "") is False
    assert entrypoint.live_artifact_hydration_enabled("lock", "render_shadow:2026-05-30:") is False

    monkeypatch.setenv("RENDER_PIPELINE_HYDRATE_ARTIFACTS", "false")
    assert entrypoint.live_artifact_hydration_enabled("lock", "") is False


def test_hydration_artifacts_include_today_dated_and_history():
    artifacts = entrypoint.hydration_artifacts("2026-05-30")
    by_type = {artifact.artifact_type: artifact for artifact in artifacts}

    assert by_type["today"].path.as_posix() == "dashboard/data/processed/today.json"
    assert by_type["dated_slate"].path.as_posix() == "dashboard/data/processed/2026-05-30.json"
    assert by_type["dated_slate"].date == "2026-05-30"
    assert by_type["dated_slate"].required is False
    assert by_type["picks_history"].path.as_posix() == "data/picks_history.json"
    assert by_type["fangraphs_cache"].path.as_posix() == "data/fangraphs_cache.json"
    assert by_type["fangraphs_cache"].required is False


def test_hydrate_live_artifacts_from_api_writes_current_payloads(tmp_path, monkeypatch):
    seen_urls = []

    class Response:
        status_code = 200

        def __init__(self, url):
            self.url = url

        def raise_for_status(self):
            return None

        def json(self):
            return {"source_url": self.url}

    def fake_get(url, timeout):
        seen_urls.append((url, timeout))
        return Response(url)

    monkeypatch.setattr(entrypoint.requests, "get", fake_get)
    monkeypatch.setenv("RENDER_PIPELINE_ARTIFACT_API_URL", "https://example.test/artifact")

    count = entrypoint.hydrate_live_artifacts_from_api(root=tmp_path, slate_date="2026-05-30")

    assert count == len(entrypoint.hydration_artifacts("2026-05-30"))
    assert (tmp_path / "dashboard/data/processed/today.json").exists()
    assert (tmp_path / "dashboard/data/processed/2026-05-30.json").exists()
    assert (tmp_path / "data/picks_history.json").exists()
    assert any("type=dated_slate&date=2026-05-30" in url for url, _ in seen_urls)
    assert all(timeout == 20 for _, timeout in seen_urls)


def test_hydrate_live_artifacts_bypasses_shared_cache_with_one_run_token(tmp_path, monkeypatch):
    seen_urls = []

    class Response:
        status_code = 200

        def __init__(self, url):
            self.url = url

        def raise_for_status(self):
            return None

        def json(self):
            query = parse_qs(urlparse(self.url).query)
            return {
                "generation": "fresh" if query.get("hydrate_run") else "stale",
            }

    def fake_get(url, timeout):
        seen_urls.append(url)
        return Response(url)

    monkeypatch.setattr(entrypoint.requests, "get", fake_get)
    monkeypatch.setenv("RENDER_PIPELINE_ARTIFACT_API_URL", "https://example.test/artifact")

    entrypoint.hydrate_live_artifacts_from_api(root=tmp_path, slate_date="2026-08-20")

    history = json.loads((tmp_path / "data/picks_history.json").read_text(encoding="utf-8"))
    assert history["generation"] == "fresh"
    hydrate_tokens = {
        parse_qs(urlparse(url).query)["hydrate_run"][0]
        for url in seen_urls
    }
    assert len(hydrate_tokens) == 1


def test_hydrate_live_artifacts_reads_oversized_history_directly_from_supabase(tmp_path, monkeypatch):
    class Response:
        def __init__(self, url):
            self.url = url
            self.status_code = 502 if "type=picks_history" in url else 200

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"unexpected {self.status_code}")

        def json(self):
            return {"source_url": self.url}

    class Writer:
        def select_rows(self, table, params, **kwargs):
            return [
                {
                    "artifact_key": "picks_history",
                    "payload": {"generation": "fresh_supabase"},
                    "payload_sha256": "history-sha",
                }
            ]

    monkeypatch.setattr(entrypoint.requests, "get", lambda url, timeout: Response(url))
    monkeypatch.setenv("RENDER_PIPELINE_ARTIFACT_API_URL", "https://example.test/artifact")

    count = entrypoint.hydrate_live_artifacts_from_api(
        root=tmp_path,
        slate_date="2026-08-20",
        writer=Writer(),
    )

    history = json.loads((tmp_path / "data/picks_history.json").read_text(encoding="utf-8"))
    assert history == {"generation": "fresh_supabase"}
    assert count == len(entrypoint.hydration_artifacts("2026-08-20"))


def test_hydrate_live_artifacts_skips_missing_optional_fangraphs_cache(tmp_path, monkeypatch):
    seen_urls = []

    class Response:
        def __init__(self, url):
            self.url = url
            self.status_code = 404 if "type=fangraphs_cache" in url else 200

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"unexpected {self.status_code}")

        def json(self):
            return {"source_url": self.url}

    def fake_get(url, timeout):
        seen_urls.append((url, timeout))
        return Response(url)

    monkeypatch.setattr(entrypoint.requests, "get", fake_get)
    monkeypatch.setenv("RENDER_PIPELINE_ARTIFACT_API_URL", "https://example.test/artifact")

    count = entrypoint.hydrate_live_artifacts_from_api(root=tmp_path, slate_date="2026-05-30")

    assert count == len(entrypoint.hydration_artifacts("2026-05-30")) - 1
    assert (tmp_path / "data/fangraphs_cache.json").exists() is False
    assert any("type=fangraphs_cache" in url for url, _ in seen_urls)


def test_hydrate_live_artifacts_skips_missing_dated_slate_archive(tmp_path, monkeypatch):
    seen_urls = []

    class Response:
        def __init__(self, url):
            self.url = url
            self.status_code = 404 if "type=dated_slate" in url else 200

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"unexpected {self.status_code}")

        def json(self):
            return {"source_url": self.url}

    def fake_get(url, timeout):
        seen_urls.append((url, timeout))
        return Response(url)

    monkeypatch.setattr(entrypoint.requests, "get", fake_get)
    monkeypatch.setenv("RENDER_PIPELINE_ARTIFACT_API_URL", "https://example.test/artifact")

    count = entrypoint.hydrate_live_artifacts_from_api(root=tmp_path, slate_date="2026-07-13")

    assert count == len(entrypoint.hydration_artifacts("2026-07-13")) - 1
    assert (tmp_path / "dashboard/data/processed/2026-07-13.json").exists() is False
    assert (tmp_path / "dashboard/data/processed/today.json").exists()
    assert (tmp_path / "data/picks_history.json").exists()
    assert any("type=dated_slate&date=2026-07-13" in url for url, _ in seen_urls)


def test_hydrate_live_artifacts_raises_required_artifact_http_errors(tmp_path, monkeypatch):
    class Response:
        def __init__(self, url):
            self.url = url
            self.status_code = 404 if "type=today" in url else 200

        def raise_for_status(self):
            if self.status_code >= 400:
                raise RuntimeError(f"unexpected {self.status_code}")

        def json(self):
            return {"source_url": self.url}

    monkeypatch.setattr(entrypoint.requests, "get", lambda url, timeout: Response(url))
    monkeypatch.setenv("RENDER_PIPELINE_ARTIFACT_API_URL", "https://example.test/artifact")

    with pytest.raises(RuntimeError, match="unexpected 404"):
        entrypoint.hydrate_live_artifacts_from_api(root=tmp_path, slate_date="2026-07-13")


def test_main_hydrates_before_live_pipeline_run(monkeypatch):
    calls = []

    def fake_hydrate(*, root, slate_date):
        calls.append(("hydrate", slate_date))
        return 8

    def fake_pipeline_run(*args, **kwargs):
        calls.append(("pipeline", args[0]))

    def fake_publish_artifacts(**kwargs):
        calls.append(("publish", kwargs["scope"]))
        return {"artifact_count": 8}

    monkeypatch.setattr(entrypoint, "hydrate_live_artifacts_from_api", fake_hydrate)
    monkeypatch.setattr(entrypoint.subprocess, "run", fake_pipeline_run)
    monkeypatch.setattr(entrypoint, "publish_artifacts", fake_publish_artifacts)
    monkeypatch.setattr(entrypoint, "resolve_source_commit_sha", lambda: "sha")

    assert entrypoint.main(["--mode", "pipeline", "--date", "2026-05-30"]) == 0

    assert calls == [
        ("hydrate", "2026-05-30"),
        ("pipeline", entrypoint.build_publish_contract("pipeline", "2026-05-30").pipeline_args),
        ("publish", "pipeline"),
    ]


def test_main_execute_passes_supabase_writer_to_live_hydration(monkeypatch):
    calls = []
    writer = object()

    def fake_hydrate(*, root, slate_date, writer):
        calls.append(("hydrate", slate_date, writer))
        return 9

    def fake_pipeline_run(*args, **kwargs):
        calls.append(("pipeline", args[0]))

    def fake_publish_artifacts(**kwargs):
        calls.append(("publish", kwargs["writer"]))
        return {"artifact_count": 8}

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "service-role-test-key")
    monkeypatch.setattr(entrypoint, "SupabaseMarketWriter", lambda url, key: writer)
    monkeypatch.setattr(entrypoint, "hydrate_live_artifacts_from_api", fake_hydrate)
    monkeypatch.setattr(entrypoint.subprocess, "run", fake_pipeline_run)
    monkeypatch.setattr(entrypoint, "publish_artifacts", fake_publish_artifacts)
    monkeypatch.setattr(entrypoint, "resolve_source_commit_sha", lambda: "sha")

    assert entrypoint.main(["--mode", "lock", "--date", "2026-08-20", "--execute"]) == 0

    assert calls == [
        ("hydrate", "2026-08-20", writer),
        ("pipeline", entrypoint.build_publish_contract("lock", "2026-08-20").pipeline_args),
        ("publish", writer),
    ]


def test_main_hydrates_publish_date_before_grading_run(monkeypatch):
    calls = []

    def fake_hydrate(*, root, slate_date):
        calls.append(("hydrate", slate_date))
        return 8

    def fake_pipeline_run(*args, **kwargs):
        calls.append(("pipeline", args[0]))

    def fake_publish_artifacts(**kwargs):
        calls.append(("publish", kwargs["slate_date"], kwargs["scope"]))
        return {"artifact_count": 4}

    monkeypatch.setattr(entrypoint, "hydrate_live_artifacts_from_api", fake_hydrate)
    monkeypatch.setattr(entrypoint.subprocess, "run", fake_pipeline_run)
    monkeypatch.setattr(entrypoint, "publish_artifacts", fake_publish_artifacts)
    monkeypatch.setattr(entrypoint, "resolve_source_commit_sha", lambda: "sha")

    assert entrypoint.main(["--mode", "grading", "--date", "2026-06-03"]) == 0

    assert calls == [
        ("hydrate", "2026-06-02"),
        ("pipeline", entrypoint.build_publish_contract("grading", "2026-06-03").pipeline_args),
        ("publish", "2026-06-02", "grading"),
    ]
