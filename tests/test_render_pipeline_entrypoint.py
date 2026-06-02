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


def test_live_provider_canary_enables_provider_for_live_preview_and_pipeline():
    for mode in ("preview", "pipeline"):
        overrides = entrypoint.runtime_env_overrides(mode, "")

        assert overrides["OFFICIAL_MARKET_SOURCE"] == "boltodds_propline"
        assert overrides["ENABLE_BOLTODDS_PIPELINE_SOURCE"] == "true"
        assert overrides["OFFICIAL_MARKET_STRICT"] == "false"


def test_live_provider_canary_does_not_touch_grading_lock_or_shadow_runs():
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
    assert by_type["picks_history"].path.as_posix() == "data/picks_history.json"


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
