from scripts.compare_supabase_artifacts import (
    compare_hashes,
    compare_local_to_remote_rows,
    parse_supabase_cli_rows,
    resolve_npx_command,
)


def test_compare_hashes_reports_match():
    assert compare_hashes(local_sha="abc", remote_sha="abc") == {
        "matches": True,
        "local_sha": "abc",
        "remote_sha": "abc",
    }


def test_compare_hashes_reports_mismatch():
    assert compare_hashes(local_sha="abc", remote_sha="def") == {
        "matches": False,
        "local_sha": "abc",
        "remote_sha": "def",
    }


def test_parse_supabase_cli_rows_returns_rows():
    output = '{"boundary":"x","rows":[{"artifact_key":"today","payload_sha256":"abc"}]}'

    assert parse_supabase_cli_rows(output) == [{"artifact_key": "today", "payload_sha256": "abc"}]


def test_resolve_npx_command_prefers_discovered_path(monkeypatch):
    monkeypatch.setattr("scripts.compare_supabase_artifacts.shutil.which", lambda name: "C:/node/npx.cmd")

    assert resolve_npx_command() == "C:/node/npx.cmd"


def test_compare_local_to_remote_rows_can_use_remote_key_prefix():
    local_rows = [{"artifact_key": "today", "payload_sha256": "abc"}]
    remote_rows = [{"artifact_key": "render_shadow:2026-05-22:today", "payload_sha256": "abc", "published_at": "now"}]

    comparisons = compare_local_to_remote_rows(
        local_rows,
        remote_rows,
        remote_key_prefix="render_shadow:2026-05-22:",
    )

    assert comparisons[0]["status"] == "match"
    assert comparisons[0]["artifact_key"] == "today"
    assert comparisons[0]["remote_artifact_key"] == "render_shadow:2026-05-22:today"
