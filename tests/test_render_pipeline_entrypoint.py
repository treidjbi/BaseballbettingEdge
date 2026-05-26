from scripts import run_render_pipeline_mode as entrypoint


def test_publish_contract_for_grading_uses_prior_slate_and_grading_scope():
    contract = entrypoint.build_publish_contract("grading", "2026-05-26")

    assert contract.pipeline_args[-3:] == ["2026-05-26", "--run-type", "grading"]
    assert contract.publish_date == "2026-05-25"
    assert contract.publish_scope == "grading"
    assert contract.pipeline_run_type == "grading"


def test_publish_contract_for_pipeline_uses_current_slate_and_all_artifacts():
    contract = entrypoint.build_publish_contract("pipeline", "2026-05-26")

    assert contract.pipeline_args[-1] == "2026-05-26"
    assert "--run-type" not in contract.pipeline_args
    assert contract.publish_date == "2026-05-26"
    assert contract.publish_scope == "all"
    assert contract.pipeline_run_type == "full"


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


def test_shadow_runtime_overrides_are_empty_for_live_key_publish():
    assert entrypoint.shadow_runtime_env_overrides("") == {}
