import json
from types import SimpleNamespace

import pytest

from scripts import deploy_render_pipeline_crons as deployer


SAMPLE_SERVICES = [
    {
        "id": "crn-preview",
        "name": "bbe-pipeline-preview",
        "slug": "bbe-pipeline-preview-shadow",
    },
    {
        "id": "crn-grading",
        "name": "bbe-pipeline-grading",
        "slug": "bbe-pipeline-grading-shadow",
    },
    {
        "id": "crn-full",
        "name": "bbe-pipeline-full",
        "slug": "bbe-pipeline-full-shadow",
    },
    {
        "id": "crn-refresh-day",
        "name": "bbe-pipeline-refresh-day",
        "slug": "bbe-pipeline-refresh-shadow-day",
    },
    {
        "id": "crn-refresh-evening",
        "name": "bbe-pipeline-refresh-evening",
        "slug": "bbe-pipeline-refresh-shadow-evening",
    },
    {
        "id": "crn-refresh-final",
        "name": "bbe-pipeline-refresh-final",
        "slug": "bbe-pipeline-refresh-shadow-final",
    },
    {
        "id": "crn-lock",
        "name": "bbe-pipeline-lock",
        "slug": "bbe-pipeline-lock",
    },
]

WRAPPED_SAMPLE_SERVICES = [
    {"service": service, "project": {"name": "My project"}, "environment": {"name": "Production"}}
    for service in SAMPLE_SERVICES
]


def test_target_services_match_pipeline_cron_group_order():
    assert deployer.TARGET_SERVICE_NAMES == (
        "bbe-pipeline-preview",
        "bbe-pipeline-grading",
        "bbe-pipeline-full",
        "bbe-pipeline-refresh-day",
        "bbe-pipeline-refresh-evening",
        "bbe-pipeline-refresh-final",
        "bbe-pipeline-lock",
    )


def test_resolve_target_services_uses_render_names_not_shadow_slugs():
    service_ids = deployer.resolve_target_services(SAMPLE_SERVICES)

    assert service_ids == {
        "bbe-pipeline-preview": "crn-preview",
        "bbe-pipeline-grading": "crn-grading",
        "bbe-pipeline-full": "crn-full",
        "bbe-pipeline-refresh-day": "crn-refresh-day",
        "bbe-pipeline-refresh-evening": "crn-refresh-evening",
        "bbe-pipeline-refresh-final": "crn-refresh-final",
        "bbe-pipeline-lock": "crn-lock",
    }


def test_resolve_target_services_fails_before_deploy_when_service_is_missing():
    with pytest.raises(ValueError, match="bbe-pipeline-lock"):
        deployer.resolve_target_services(SAMPLE_SERVICES[:-1])


def test_build_deploy_command_uses_service_id_without_commit_pin():
    assert deployer.build_deploy_command("render", "crn-lock") == [
        "render",
        "deploys",
        "create",
        "crn-lock",
        "--wait",
        "--confirm",
        "--output",
        "json",
    ]


def test_main_dry_run_lists_services_but_does_not_deploy(monkeypatch, capsys):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        assert args == ["render", "services", "--output", "json"]
        return SimpleNamespace(stdout=json.dumps(SAMPLE_SERVICES))

    monkeypatch.setattr(deployer.subprocess, "run", fake_run)

    assert deployer.main([]) == 0

    assert calls == [["render", "services", "--output", "json"]]
    output = capsys.readouterr().out
    assert "DRY RUN" in output
    assert "bbe-pipeline-lock" in output


def test_main_dry_run_handles_render_cli_wrapped_service_rows(monkeypatch, capsys):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        assert args == ["render", "services", "--output", "json"]
        return SimpleNamespace(stdout=json.dumps(WRAPPED_SAMPLE_SERVICES))

    monkeypatch.setattr(deployer.subprocess, "run", fake_run)

    assert deployer.main([]) == 0

    assert calls == [["render", "services", "--output", "json"]]
    output = capsys.readouterr().out
    assert "DRY RUN" in output
    assert "bbe-pipeline-preview" in output


def test_main_execute_deploys_services_in_stable_order(monkeypatch):
    calls = []

    def fake_run(args, **kwargs):
        calls.append(args)
        if args == ["render", "services", "--output", "json"]:
            return SimpleNamespace(stdout=json.dumps(SAMPLE_SERVICES))
        assert args[:3] == ["render", "deploys", "create"]
        return SimpleNamespace(stdout=json.dumps({"id": f"deploy-{args[3]}"}))

    monkeypatch.setattr(deployer.subprocess, "run", fake_run)

    assert deployer.main(["--execute"]) == 0

    expected_deploy_commands = [
        deployer.build_deploy_command("render", service_id)
        for service_id in (
            "crn-preview",
            "crn-grading",
            "crn-full",
            "crn-refresh-day",
            "crn-refresh-evening",
            "crn-refresh-final",
            "crn-lock",
        )
    ]
    assert calls == [["render", "services", "--output", "json"], *expected_deploy_commands]
