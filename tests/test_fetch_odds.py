import pytest
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

from fetch_odds import american_odds_from_line, parse_k_props


class TestAmericanOddsFromLine:
    def test_parses_negative(self):
        assert american_odds_from_line("-110") == -110

    def test_parses_positive(self):
        assert american_odds_from_line("+130") == 130

    def test_parses_int_string(self):
        assert american_odds_from_line("100") == 100

    def test_returns_none_on_invalid(self):
        assert american_odds_from_line("N/A") is None

    def test_returns_none_on_empty(self):
        assert american_odds_from_line("") is None


class TestParseKProps:
    def test_returns_list_of_dicts(self):
        mock_response = {
            "events": [
                {
                    "teams": [
                        {"name": "New York Yankees", "is_home": False},
                        {"name": "Boston Red Sox",   "is_home": True},
                    ],
                    "score": {
                        "event_status_detail": "Scheduled",
                        "start_time": "2026-04-01T23:05:00Z"
                    },
                    "lines": {
                        "1": {
                            "pitcher_strikeouts": {
                                "pitcher_name": "Gerrit Cole",
                                "over": 7.5,
                                "over_odds": -112,
                                "under_odds": -108,
                            },
                            "book_name": "FanDuel"
                        }
                    }
                }
            ]
        }
        result = parse_k_props(mock_response, opening_odds_map={})
        assert len(result) == 1
        assert result[0]["pitcher"] == "Gerrit Cole"
        assert result[0]["k_line"] == 7.5
        assert result[0]["best_over_odds"] == -112

    def test_skips_event_with_no_k_prop(self):
        mock_response = {
            "events": [
                {
                    "teams": [
                        {"name": "NYY", "is_home": False},
                        {"name": "BOS", "is_home": True},
                    ],
                    "score": {
                        "event_status_detail": "Scheduled",
                        "start_time": "2026-04-01T23:05:00Z"
                    },
                    "lines": {}
                }
            ]
        }
        result = parse_k_props(mock_response, opening_odds_map={})
        assert result == []

    def test_applies_opening_odds_from_map(self):
        mock_response = {
            "events": [
                {
                    "teams": [
                        {"name": "NYY", "is_home": False},
                        {"name": "BOS", "is_home": True},
                    ],
                    "score": {"start_time": "2026-04-01T23:05:00Z"},
                    "lines": {
                        "1": {
                            "pitcher_strikeouts": {
                                "pitcher_name": "Gerrit Cole",
                                "over": 7.5,
                                "over_odds": -120,
                                "under_odds": -100,
                            },
                            "book_name": "DraftKings"
                        }
                    }
                }
            ]
        }
        opening_map = {
            "Gerrit Cole": {
                "opening_over_odds": -110,
                "opening_under_odds": -110,
                "opening_line": 7.5,
            }
        }
        result = parse_k_props(mock_response, opening_odds_map=opening_map)
        assert result[0]["opening_over_odds"] == -110
        assert result[0]["opening_under_odds"] == -110
