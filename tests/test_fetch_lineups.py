import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

from unittest.mock import patch, MagicMock
import fetch_lineups


SAMPLE_SCHEDULE_RESPONSE = {
    "dates": [{
        "games": [{
            "gamePk": 745000,
            "teams": {
                "away": {"team": {"name": "New York Yankees"}},
                "home": {"team": {"name": "Boston Red Sox"}},
            },
            "lineups": {
                "awayPlayers": [
                    {"person": {"fullName": "Aaron Judge", "batSide": {"code": "R"}},
                     "battingOrder": "100", "position": {"abbreviation": "CF"}},
                    {"person": {"fullName": "Giancarlo Stanton", "batSide": {"code": "R"}},
                     "battingOrder": "200", "position": {"abbreviation": "DH"}},
                ],
                "homePlayers": []
            }
        }]
    }]
}


def _make_mock_response(data):
    m = MagicMock()
    m.json.return_value = data
    m.raise_for_status.return_value = None
    return m


def test_fetch_lineups_returns_batters_for_team(monkeypatch):
    """fetch_lineups returns batter list for a given team."""
    monkeypatch.setattr("fetch_lineups.requests.get",
                        lambda *a, **kw: _make_mock_response(SAMPLE_SCHEDULE_RESPONSE))
    result = fetch_lineups.fetch_lineups("2026-04-15", "New York Yankees")
    assert result is not None
    names = [b["name"] for b in result]
    assert "Aaron Judge" in names
    assert "Giancarlo Stanton" in names


def test_fetch_lineups_returns_none_when_no_lineup(monkeypatch):
    """Returns None when no lineup posted for the team."""
    empty_response = {"dates": [{"games": [{
        "gamePk": 745001,
        "teams": {"away": {"team": {"name": "NYY"}}, "home": {"team": {"name": "BOS"}}},
        "lineups": {"awayPlayers": [], "homePlayers": []}
    }]}]}
    monkeypatch.setattr("fetch_lineups.requests.get",
                        lambda *a, **kw: _make_mock_response(empty_response))
    result = fetch_lineups.fetch_lineups("2026-04-15", "NYY")
    assert result is None


def test_fetch_lineups_returns_none_on_api_error(monkeypatch):
    """Returns None (not an exception) when API call fails."""
    def raise_error(*a, **kw):
        raise Exception("network error")
    monkeypatch.setattr("fetch_lineups.requests.get", raise_error)
    result = fetch_lineups.fetch_lineups("2026-04-15", "NYY")
    assert result is None


def test_fetch_lineups_includes_bats_field(monkeypatch):
    """Each batter dict should include a bats field (R/L/S), defaulting to R."""
    monkeypatch.setattr("fetch_lineups.requests.get",
                        lambda *a, **kw: _make_mock_response(SAMPLE_SCHEDULE_RESPONSE))
    result = fetch_lineups.fetch_lineups("2026-04-15", "New York Yankees")
    for batter in result:
        assert "bats" in batter
        assert batter["bats"] in ("R", "L", "S")
