from scripts.compare_supabase_artifacts import compare_hashes, parse_supabase_cli_rows, resolve_npx_command


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
