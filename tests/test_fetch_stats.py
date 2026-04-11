import sys
import os
import pytest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

from fetch_stats import fetch_stats, _parse_ip, _k9_from_splits, _normalize_name


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_schedule(pitcher_name, pitcher_id, pitch_hand_code="R"):
    """Build a minimal MLB schedule API response with one game."""
    pitcher_obj = {
        "id": pitcher_id,
        "fullName": pitcher_name,
    }
    if pitch_hand_code is not None:
        pitcher_obj["pitchHand"] = {"code": pitch_hand_code}

    return {
        "dates": [
            {
                "games": [
                    {
                        "teams": {
                            "away": {
                                "probablePitcher": pitcher_obj,
                                "team": {"id": 147, "name": "New York Yankees"},
                            },
                            "home": {
                                "team": {"id": 111, "name": "Boston Red Sox"},
                            },
                        }
                    }
                ]
            }
        ]
    }


def _make_pitcher_stats_response(so=45, ip="45.0"):
    """Build a minimal MLB pitcher stats API response."""
    return {
        "stats": [
            {
                "splits": [
                    {
                        "stat": {
                            "strikeOuts": so,
                            "inningsPitched": ip,
                            "gamesPlayed": 8,
                        }
                    }
                ]
            }
        ]
    }


def _make_team_stats_response(pa=1500, so=360):
    """Build a minimal MLB team hitting stats API response."""
    return {
        "stats": [
            {
                "splits": [
                    {
                        "stat": {
                            "plateAppearances": pa,
                            "strikeOuts": so,
                            "gamesPlayed": 10,
                        }
                    }
                ]
            }
        ]
    }


def _make_requests_get_side_effect(pitcher_name, pitcher_id, pitch_hand_code="R"):
    """
    Return a side_effect function for requests.get that serves different
    responses based on the URL being called.
    """
    schedule = _make_schedule(pitcher_name, pitcher_id, pitch_hand_code)
    pitcher_stats = _make_pitcher_stats_response()
    team_stats = _make_team_stats_response()

    def side_effect(url, params=None, timeout=None):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        if "/schedule" in url:
            mock_resp.json.return_value = schedule
        elif f"/people/{pitcher_id}/stats" in url:
            mock_resp.json.return_value = pitcher_stats
        elif f"/teams/" in url:
            mock_resp.json.return_value = team_stats
        else:
            mock_resp.json.return_value = {"stats": []}
        return mock_resp

    return side_effect


# ── Tests: _parse_ip ───────────────────────────────────────────────────────────

class TestParseIp:
    def test_whole_innings(self):
        assert _parse_ip("6.0") == pytest.approx(6.0)

    def test_one_out(self):
        assert _parse_ip("6.1") == pytest.approx(6 + 1/3)

    def test_two_outs(self):
        assert _parse_ip("6.2") == pytest.approx(6 + 2/3)

    def test_zero(self):
        assert _parse_ip("0") == 0.0

    def test_none(self):
        assert _parse_ip(None) == 0.0

    def test_integer_value(self):
        assert _parse_ip(5) == pytest.approx(5.0)


# ── Tests: _k9_from_splits ────────────────────────────────────────────────────

class TestK9FromSplits:
    def test_basic_k9(self):
        splits = [{"stat": {"strikeOuts": 9, "inningsPitched": "9.0"}}]
        assert _k9_from_splits(splits) == pytest.approx(9.0)

    def test_returns_none_on_empty(self):
        assert _k9_from_splits([]) is None

    def test_returns_none_when_no_ip(self):
        splits = [{"stat": {"strikeOuts": 5, "inningsPitched": "0.0"}}]
        assert _k9_from_splits(splits) is None


# ── Tests: fetch_stats (integration via mocked HTTP) ──────────────────────────

def test_fetch_stats_returns_expected_keys():
    """fetch_stats should return a dict with expected stat keys."""
    pitcher_id = 543037
    with patch("requests.get", side_effect=_make_requests_get_side_effect(
        "Gerrit Cole", pitcher_id, pitch_hand_code="R"
    )):
        stats = fetch_stats("2026-04-15", ["Gerrit Cole"])

    assert "Gerrit Cole" in stats
    result = stats["Gerrit Cole"]
    for key in ("season_k9", "career_k9", "recent_k9", "avg_ip_last5", "opp_k_rate", "team", "opp_team"):
        assert key in result, f"Missing key: {key}"


def test_fetch_stats_returns_throws_field():
    """fetch_stats should include throws (R/L) for each pitcher."""
    pitcher_id = 543037
    with patch("requests.get", side_effect=_make_requests_get_side_effect(
        "Gerrit Cole", pitcher_id, pitch_hand_code="R"
    )):
        stats = fetch_stats("2026-04-15", ["Gerrit Cole"])

    assert "throws" in stats.get("Gerrit Cole", {}), "throws key missing from stats"
    assert stats["Gerrit Cole"]["throws"] in ("R", "L"), "throws should be R or L"


def test_fetch_stats_throws_value_matches_api():
    """throws should reflect the actual pitchHand.code from the API."""
    pitcher_id = 605483
    with patch("requests.get", side_effect=_make_requests_get_side_effect(
        "Clayton Kershaw", pitcher_id, pitch_hand_code="L"
    )):
        stats = fetch_stats("2026-04-15", ["Clayton Kershaw"])

    assert stats.get("Clayton Kershaw", {}).get("throws") == "L"


def test_fetch_stats_throws_defaults_to_R_when_missing():
    """When pitchHand is absent from API, throws should default to 'R'."""
    pitcher_id = 999999
    with patch("requests.get", side_effect=_make_requests_get_side_effect(
        "Test Pitcher", pitcher_id, pitch_hand_code=None  # None means pitchHand key omitted
    )):
        stats = fetch_stats("2026-04-15", ["Test Pitcher"])

    assert stats.get("Test Pitcher", {}).get("throws") == "R"


def test_fetch_stats_skips_unknown_pitchers():
    """fetch_stats should not return entries for pitchers not in the schedule."""
    pitcher_id = 543037
    with patch("requests.get", side_effect=_make_requests_get_side_effect(
        "Gerrit Cole", pitcher_id
    )):
        stats = fetch_stats("2026-04-15", ["Unknown Pitcher"])

    assert "Unknown Pitcher" not in stats
    assert "Gerrit Cole" not in stats


# ── Tests: _normalize_name ─────────────────────────────────────────────────────

class TestNormalizeName:
    def test_strips_accents(self):
        assert _normalize_name("José Berríos") == "jose berrios"

    def test_lowercase(self):
        assert _normalize_name("Gerrit Cole") == "gerrit cole"

    def test_strips_tildes(self):
        assert _normalize_name("Julio Urías") == "julio urias"

    def test_strips_cedilla(self):
        assert _normalize_name("Félix Hernández") == "felix hernandez"

    def test_unaccented_unchanged(self):
        assert _normalize_name("Zack Wheeler") == "zack wheeler"

    def test_strips_leading_trailing_whitespace(self):
        assert _normalize_name("  Gerrit Cole  ") == "gerrit cole"


# ── Tests: accent-insensitive name matching ────────────────────────────────────

def test_fetch_stats_matches_accented_mlb_name_to_plain_rundown_name():
    """MLB API may return 'José Berríos' while TheRundown sends 'Jose Berrios'.
    fetch_stats must match them and return stats under the TheRundown name."""
    pitcher_id = 621244
    # MLB schedule returns accented name; pitcher_names list has plain TheRundown name.
    with patch("requests.get", side_effect=_make_requests_get_side_effect(
        "José Berríos", pitcher_id, pitch_hand_code="R"
    )):
        stats = fetch_stats("2026-04-15", ["Jose Berrios"])

    # Stats should be keyed by TheRundown name (no accent) so run_pipeline lookups work
    assert "Jose Berrios" in stats, "Expected TheRundown name 'Jose Berrios' as key"
    assert "José Berríos" not in stats, "Accented MLB name should not be the key"


def test_fetch_stats_matches_plain_rundown_name_with_accented_mlb_name():
    """Inverse: TheRundown sends 'Julio Urías' (accented) and MLB API has 'Julio Urias'."""
    pitcher_id = 650556
    with patch("requests.get", side_effect=_make_requests_get_side_effect(
        "Julio Urias", pitcher_id, pitch_hand_code="L"
    )):
        stats = fetch_stats("2026-04-15", ["Julio Urías"])

    assert "Julio Urías" in stats, "Expected TheRundown name 'Julio Urías' as key"
    assert "Julio Urias" not in stats


def test_fetch_stats_accent_match_preserves_stats_content():
    """Accent-matched pitcher should have all expected stat keys."""
    pitcher_id = 621244
    with patch("requests.get", side_effect=_make_requests_get_side_effect(
        "José Berríos", pitcher_id, pitch_hand_code="R"
    )):
        stats = fetch_stats("2026-04-15", ["Jose Berrios"])

    result = stats.get("Jose Berrios", {})
    for key in ("season_k9", "career_k9", "recent_k9", "avg_ip_last5", "opp_k_rate",
                "team", "opp_team", "throws"):
        assert key in result, f"Missing key after accent match: {key}"
