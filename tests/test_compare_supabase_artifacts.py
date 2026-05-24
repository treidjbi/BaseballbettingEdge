from scripts.compare_supabase_artifacts import compare_hashes


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
