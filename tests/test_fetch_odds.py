import pytest
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

from fetch_odds import american_odds_from_line, parse_k_props, _parse_line_value, _select_ref_book


# ── Helper fixtures ────────────────────────────────────────────────────────────

def _make_event(pitcher_name, line_val, over_price, under_price,
                over_delta=0, under_delta=0, is_main=False,
                away="New York Yankees", home="Boston Red Sox",
                event_date="2026-04-01T23:05:00Z"):
    """Build a minimal TheRundown v2 markets-format event."""
    return {
        "event_id": f"evt-{pitcher_name.replace(' ', '')}",
        "event_date": event_date,
        "teams": [
            {"name": away, "is_away": True,  "is_home": False},
            {"name": home, "is_away": False, "is_home": True},
        ],
        "markets": [
            {
                "market_id": 19,
                "name": "pitcher_strikeouts",
                "participants": [
                    {
                        "name": pitcher_name,
                        "lines": [
                            {
                                "value": f"Over {line_val}",
                                "prices": {
                                    "22": {
                                        "price": over_price,
                                        "price_delta": over_delta,
                                        "is_main_line": is_main,
                                    }
                                },
                            },
                            {
                                "value": f"Under {line_val}",
                                "prices": {
                                    "22": {
                                        "price": under_price,
                                        "price_delta": under_delta,
                                        "is_main_line": is_main,
                                    }
                                },
                            },
                        ],
                    }
                ],
            }
        ],
    }


# ── Tests: american_odds_from_line ────────────────────────────────────────────

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


# ── Tests: _parse_line_value ──────────────────────────────────────────────────

class TestParseLineValue:
    def test_parses_over(self):
        assert _parse_line_value("Over 5.5") == ("over", 5.5)

    def test_parses_under(self):
        assert _parse_line_value("Under 6.5") == ("under", 6.5)

    def test_case_insensitive(self):
        assert _parse_line_value("OVER 7.5") == ("over", 7.5)

    def test_returns_none_on_garbage(self):
        assert _parse_line_value("garbage") is None

    def test_returns_none_on_empty(self):
        assert _parse_line_value("") is None


# ── Tests: parse_k_props ──────────────────────────────────────────────────────

class TestParseKProps:
    def test_returns_list_of_dicts(self):
        data = {"events": [_make_event("Gerrit Cole", 7.5, -112, -108)]}
        result = parse_k_props(data)
        assert len(result) == 1
        assert result[0]["pitcher"] == "Gerrit Cole"
        assert result[0]["k_line"] == 7.5
        assert result[0]["best_over_odds"] == -112

    def test_skips_event_with_no_k_prop_market(self):
        data = {
            "events": [
                {
                    "event_id": "no-market",
                    "event_date": "2026-04-01T23:05:00Z",
                    "teams": [
                        {"name": "NYY", "is_away": True,  "is_home": False},
                        {"name": "BOS", "is_away": False, "is_home": True},
                    ],
                    "markets": [
                        {"market_id": 1, "name": "moneyline", "participants": []}
                    ],
                }
            ]
        }
        result = parse_k_props(data)
        assert result == []

    def test_opening_odds_derived_from_price_delta(self):
        # price_delta = current - opening → opening = current - delta
        # over: current=-120, delta=10 → opening=-130
        # under: current=-100, delta=-5 → opening=-95
        data = {"events": [
            _make_event("Logan Webb", 6.5,
                        over_price=-120, under_price=-100,
                        over_delta=10,  under_delta=-5)
        ]}
        result = parse_k_props(data)
        assert result[0]["opening_over_odds"]  == -130   # -120 - 10
        assert result[0]["opening_under_odds"] == -95    # -100 - (-5)

    def test_opening_odds_equal_current_when_no_delta(self):
        data = {"events": [_make_event("Max Fried", 5.5, 115, -155)]}
        result = parse_k_props(data)
        assert result[0]["opening_over_odds"]  == 115
        assert result[0]["opening_under_odds"] == -155

    def test_team_names_empty_in_fetch_odds(self):
        """fetch_odds cannot determine home/away per pitcher — team fields are empty strings.
        Team resolution happens in fetch_stats via the MLB schedule API."""
        data = {"events": [
            _make_event("Tarik Skubal", 7.5, 120, -160,
                        away="Detroit Tigers", home="San Diego Padres")
        ]}
        result = parse_k_props(data)
        assert result[0]["team"]     == ""
        assert result[0]["opp_team"] == ""

    def test_multiple_pitchers_same_event(self):
        event = {
            "event_id": "evt-multi",
            "event_date": "2026-04-01T23:05:00Z",
            "teams": [
                {"name": "NYY", "is_away": True,  "is_home": False},
                {"name": "BOS", "is_away": False, "is_home": True},
            ],
            "markets": [
                {
                    "market_id": 19,
                    "name": "pitcher_strikeouts",
                    "participants": [
                        {
                            "name": "Gerrit Cole",
                            "lines": [
                                {"value": "Over 7.5",  "prices": {"1": {"price": -112, "is_main_line": False}}},
                                {"value": "Under 7.5", "prices": {"1": {"price": -108, "is_main_line": False}}},
                            ],
                        },
                        {
                            "name": "Chris Sale",
                            "lines": [
                                {"value": "Over 6.5",  "prices": {"1": {"price": 100, "is_main_line": False}}},
                                {"value": "Under 6.5", "prices": {"1": {"price": -130, "is_main_line": False}}},
                            ],
                        },
                    ],
                }
            ],
        }
        result = parse_k_props({"events": [event]})
        assert len(result) == 2
        names = {r["pitcher"] for r in result}
        assert names == {"Gerrit Cole", "Chris Sale"}

    def test_selects_ref_book_by_priority(self):
        """Selects FanDuel (book 11) over a better-priced unknown book."""
        event = {
            "event_id": "evt-refbook",
            "event_date": "2026-04-01T23:05:00Z",
            "teams": [
                {"name": "NYY", "is_away": True,  "is_home": False},
                {"name": "BOS", "is_away": False, "is_home": True},
            ],
            "markets": [{
                "market_id": 19,
                "name": "pitcher_strikeouts",
                "participants": [{
                    "name": "Gerrit Cole",
                    "lines": [
                        {
                            "value": "Over 7.5",
                            "prices": {
                                "25": {"price": -105, "is_main_line": True, "price_delta": 0},
                                "11": {"price": -115, "is_main_line": True, "price_delta": 0},
                            },
                        },
                        {
                            "value": "Under 7.5",
                            "prices": {
                                "25": {"price": -115, "is_main_line": True, "price_delta": 0},
                                "11": {"price": -105, "is_main_line": True, "price_delta": 0},
                            },
                        },
                    ],
                }],
            }],
        }
        result = parse_k_props({"events": [event]})
        assert result[0]["best_over_odds"] == -115   # FanDuel (11), not best price (-105)
        assert result[0]["ref_book"] == "FanDuel"

    def test_falls_back_to_any_book_when_no_priority_book(self):
        """Uses first available book when no priority book is present."""
        event = {
            "event_id": "evt-fallback",
            "event_date": "2026-04-01T23:05:00Z",
            "teams": [
                {"name": "NYY", "is_away": True,  "is_home": False},
                {"name": "BOS", "is_away": False, "is_home": True},
            ],
            "markets": [{
                "market_id": 19,
                "name": "pitcher_strikeouts",
                "participants": [{
                    "name": "Gerrit Cole",
                    "lines": [
                        {
                            "value": "Over 7.5",
                            "prices": {"25": {"price": -110, "is_main_line": True, "price_delta": 0}},
                        },
                        {
                            "value": "Under 7.5",
                            "prices": {"25": {"price": -110, "is_main_line": True, "price_delta": 0}},
                        },
                    ],
                }],
            }],
        }
        result = parse_k_props({"events": [event]})
        assert len(result) == 1
        assert result[0]["ref_book"] == "Book25"

    def test_prefers_main_line_when_multiple_lines(self):
        # Pitcher has 4.5 and 5.5 lines; 5.5 is marked main
        event = {
            "event_id": "evt-multiline",
            "event_date": "2026-04-01T23:05:00Z",
            "teams": [
                {"name": "MIN", "is_away": True,  "is_home": False},
                {"name": "BAL", "is_away": False, "is_home": True},
            ],
            "markets": [
                {
                    "market_id": 19,
                    "name": "pitcher_strikeouts",
                    "participants": [
                        {
                            "name": "Trevor Rogers",
                            "lines": [
                                {"value": "Over 4.5",  "prices": {"1": {"price": -160, "is_main_line": False}}},
                                {"value": "Under 4.5", "prices": {"1": {"price":  125, "is_main_line": False}}},
                                {"value": "Over 5.5",  "prices": {"1": {"price":  120, "is_main_line": True}}},
                                {"value": "Under 5.5", "prices": {"1": {"price": -160, "is_main_line": True}}},
                            ],
                        }
                    ],
                }
            ],
        }
        result = parse_k_props({"events": [event]})
        assert len(result) == 1
        assert result[0]["k_line"] == 5.5   # main line selected

def test_home_pitcher_gets_empty_team_not_away():
    """fetch_odds cannot determine home/away per pitcher — team fields must be empty strings."""
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))
    from fetch_odds import _parse_event_k_props
    event = {
        "teams": [
            {"name": "Yankees", "is_away": True, "is_home": False},
            {"name": "Red Sox", "is_away": False, "is_home": True},
        ],
        "event_date": "2026-04-01T23:05:00Z",
        "markets": [{
            "market_id": 19,
            "participants": [
                {
                    "name": "Away Pitcher",
                    "lines": [
                        {"value": "Over 6.5", "prices": {"1": {"price": -110, "is_main_line": True, "price_delta": 0}}},
                        {"value": "Under 6.5", "prices": {"1": {"price": -110, "is_main_line": True, "price_delta": 0}}}
                    ]
                },
                {
                    "name": "Home Pitcher",
                    "lines": [
                        {"value": "Over 5.5", "prices": {"1": {"price": -115, "is_main_line": True, "price_delta": 0}}},
                        {"value": "Under 5.5", "prices": {"1": {"price": -105, "is_main_line": True, "price_delta": 0}}}
                    ]
                },
            ]
        }]
    }
    results = _parse_event_k_props(event)
    assert len(results) == 2
    for r in results:
        assert r["team"] == "", f"Expected empty team, got {r['team']!r}"
        assert r["opp_team"] == "", f"Expected empty opp_team, got {r['opp_team']!r}"


    def test_skips_pitcher_with_only_over_no_under(self):
        event = {
            "event_id": "evt-missing-under",
            "event_date": "2026-04-01T23:05:00Z",
            "teams": [
                {"name": "NYY", "is_away": True,  "is_home": False},
                {"name": "BOS", "is_away": False, "is_home": True},
            ],
            "markets": [
                {
                    "market_id": 19,
                    "name": "pitcher_strikeouts",
                    "participants": [
                        {
                            "name": "Gerrit Cole",
                            "lines": [
                                {"value": "Over 7.5", "prices": {"1": {"price": -112, "is_main_line": False}}},
                                # No Under line
                            ],
                        }
                    ],
                }
            ],
        }
        result = parse_k_props({"events": [event]})
        assert result == []


class TestSelectRefBook:
    def test_prefers_fanduel(self):
        books = {
            "11": {"price": -110, "is_main": True, "delta": 0},
            "3":  {"price": -108, "is_main": True, "delta": 0},
        }
        book_id, name = _select_ref_book(books)
        assert book_id == "11"
        assert name == "FanDuel"

    def test_falls_back_to_betmgm(self):
        books = {
            "6": {"price": -112, "is_main": True, "delta": 0},
            "3": {"price": -108, "is_main": True, "delta": 0},
        }
        book_id, name = _select_ref_book(books)
        assert book_id == "6"
        assert name == "BetMGM"

    def test_falls_back_to_draftkings(self):
        books = {"3": {"price": -108, "is_main": True, "delta": 0}}
        book_id, name = _select_ref_book(books)
        assert book_id == "3"
        assert name == "DraftKings"

    def test_falls_back_to_any_book(self):
        books = {"25": {"price": -110, "is_main": True, "delta": 0}}
        book_id, name = _select_ref_book(books)
        assert book_id == "25"
        assert name == "Book25"

    def test_returns_none_for_empty_books(self):
        book_id, name = _select_ref_book({})
        assert book_id is None
        assert name is None
