import pytest
import sys
import os
from unittest.mock import patch
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'pipeline'))

from fetch_odds import american_odds_from_line, parse_k_props, _parse_line_value, _select_ref_book, _headers


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


class TestHeaders:
    def test_headers_raises_if_missing_api_key(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(EnvironmentError) as exc:
                _headers()
            assert "RUNDOWN_API_KEY not set" in str(exc.value)

    def test_headers_uses_api_key_from_env(self):
        with patch.dict("os.environ", {"RUNDOWN_API_KEY": "abc123"}):
            headers = _headers()
            assert headers["X-TheRundown-Key"] == "abc123"
            assert headers["Accept"] == "application/json"

    def test_headers_strip_whitespace_from_api_key(self):
        with patch.dict("os.environ", {"RUNDOWN_API_KEY": "  abc123 \n"}):
            headers = _headers()
            assert headers["X-TheRundown-Key"] == "abc123"


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
                                {"value": "Over 7.5",  "prices": {"23": {"price": -112, "is_main_line": False}}},
                                {"value": "Under 7.5", "prices": {"23": {"price": -108, "is_main_line": False}}},
                            ],
                        },
                        {
                            "name": "Chris Sale",
                            "lines": [
                                {"value": "Over 6.5",  "prices": {"23": {"price": 100, "is_main_line": False}}},
                                {"value": "Under 6.5", "prices": {"23": {"price": -130, "is_main_line": False}}},
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
        """Selects FanDuel (book 23) over a better-priced unknown book."""
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
                                "23": {"price": -115, "is_main_line": True, "price_delta": 0},
                            },
                        },
                        {
                            "value": "Under 7.5",
                            "prices": {
                                "25": {"price": -115, "is_main_line": True, "price_delta": 0},
                                "23": {"price": -105, "is_main_line": True, "price_delta": 0},
                            },
                        },
                    ],
                }],
            }],
        }
        result = parse_k_props({"events": [event]})
        assert result[0]["best_over_odds"] == -115   # FanDuel (23), not best price (-105)
        assert result[0]["ref_book"] == "FanDuel"

    def test_skips_pitcher_when_no_target_book_offered(self):
        """Option B: when only an untracked book (e.g. Book25) offers the line,
        skip the pitcher entirely rather than falling back. The user can't
        place those picks, so surfacing them is worse than surfacing nothing."""
        event = {
            "event_id": "evt-no-target-book",
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
        assert result == []

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
                                {"value": "Over 4.5",  "prices": {"23": {"price": -160, "is_main_line": False}}},
                                {"value": "Under 4.5", "prices": {"23": {"price":  125, "is_main_line": False}}},
                                {"value": "Over 5.5",  "prices": {"23": {"price":  120, "is_main_line": True}}},
                                {"value": "Under 5.5", "prices": {"23": {"price": -160, "is_main_line": True}}},
                            ],
                        }
                    ],
                }
            ],
        }
        result = parse_k_props({"events": [event]})
        assert len(result) == 1
        assert result[0]["k_line"] == 5.5   # main line selected

    def test_skips_participant_marked_as_position_player(self):
        """Obvious non-pitchers should be dropped when the payload itself tags
        them as a position player."""
        event = {
            "event_id": "evt-position-player",
            "event_date": "2026-04-01T23:05:00Z",
            "teams": [
                {"name": "LAA", "is_away": True, "is_home": False},
                {"name": "CLE", "is_away": False, "is_home": True},
            ],
            "markets": [{
                "market_id": 19,
                "name": "pitcher_strikeouts",
                "participants": [{
                    "name": "Mike Trout",
                    "primaryPosition": {"abbreviation": "CF", "code": "8"},
                    "lines": [
                        {"value": "Over 0.5", "prices": {"23": {"price": -110, "is_main_line": True, "price_delta": 0}}},
                        {"value": "Under 0.5", "prices": {"23": {"price": -110, "is_main_line": True, "price_delta": 0}}},
                    ],
                }],
            }],
        }
        result = parse_k_props({"events": [event]})
        assert result == []

    def test_skips_obviously_bad_sub_one_point_five_k_props(self):
        """A starter-only model should never accept sub-1.5 strikeout lines."""
        data = {"events": [_make_event("Jose Ramirez", 0.5, -110, -110)]}
        result = parse_k_props(data)
        assert result == []

    def test_keeps_one_point_five_strikeout_line(self):
        """The low-line guard must stay conservative and still allow 1.5 props."""
        data = {"events": [_make_event("Ryan Pepiot", 1.5, -118, -102)]}
        result = parse_k_props(data)
        assert len(result) == 1
        assert result[0]["pitcher"] == "Ryan Pepiot"
        assert result[0]["k_line"] == 1.5

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
                        {"value": "Over 6.5", "prices": {"23": {"price": -110, "is_main_line": True, "price_delta": 0}}},
                        {"value": "Under 6.5", "prices": {"23": {"price": -110, "is_main_line": True, "price_delta": 0}}}
                    ]
                },
                {
                    "name": "Home Pitcher",
                    "lines": [
                        {"value": "Over 5.5", "prices": {"23": {"price": -115, "is_main_line": True, "price_delta": 0}}},
                        {"value": "Under 5.5", "prices": {"23": {"price": -105, "is_main_line": True, "price_delta": 0}}}
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


def test_skips_pitcher_with_only_over_no_under():
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
                            {"value": "Over 7.5", "prices": {"23": {"price": -112, "is_main_line": False}}},
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
            "23": {"price": -110, "is_main": True, "delta": 0},
            "19": {"price": -108, "is_main": True, "delta": 0},
        }
        book_id, name = _select_ref_book(books)
        assert book_id == "23"
        assert name == "FanDuel"

    def test_falls_back_to_betmgm(self):
        books = {
            "22": {"price": -112, "is_main": True, "delta": 0},
            "19": {"price": -108, "is_main": True, "delta": 0},
        }
        book_id, name = _select_ref_book(books)
        assert book_id == "22"
        assert name == "BetMGM"

    def test_falls_back_to_draftkings(self):
        books = {"19": {"price": -108, "is_main": True, "delta": 0}}
        book_id, name = _select_ref_book(books)
        assert book_id == "19"
        assert name == "DraftKings"

    def test_falls_back_to_betrivers(self):
        books = {"30": {"price": -110, "is_main": True, "delta": 0}}
        book_id, name = _select_ref_book(books)
        assert book_id == "30"
        assert name == "BetRivers"

    def test_falls_back_to_caesars(self):
        books = {"20": {"price": -110, "is_main": True, "delta": 0}}
        book_id, name = _select_ref_book(books)
        assert book_id == "20"
        assert name == "Caesars"

    def test_falls_back_to_fanatics(self):
        books = {"38": {"price": -110, "is_main": True, "delta": 0}}
        book_id, name = _select_ref_book(books)
        assert book_id == "38"
        assert name == "Fanatics"

    def test_returns_none_when_only_untracked_book(self):
        """Option B: no fallback to unknown books. Book25 is not in the
        priority list, so _select_ref_book returns (None, None) and the
        caller skips the pitcher."""
        books = {"25": {"price": -110, "is_main": True, "delta": 0}}
        book_id, name = _select_ref_book(books)
        assert book_id is None
        assert name is None

    def test_returns_none_for_empty_books(self):
        book_id, name = _select_ref_book({})
        assert book_id is None
        assert name is None

    def test_priority_order_fanduel_over_all(self):
        """FanDuel wins over every other target book when all are present."""
        books = {
            "23": {"price": -110, "is_main": True, "delta": 0},
            "22": {"price": -108, "is_main": True, "delta": 0},
            "19": {"price": -105, "is_main": True, "delta": 0},
            "30": {"price": -100, "is_main": True, "delta": 0},
            "20": {"price": -102, "is_main": True, "delta": 0},
            "38": {"price": -104, "is_main": True, "delta": 0},
        }
        book_id, name = _select_ref_book(books)
        assert book_id == "23"
        assert name == "FanDuel"

    def test_caesars_beats_fanatics(self):
        """When only Caesars and Fanatics are present, Caesars wins
        (it's earlier in REF_BOOK_PRIORITY)."""
        books = {
            "38": {"price": -110, "is_main": True, "delta": 0},
            "20": {"price": -110, "is_main": True, "delta": 0},
        }
        book_id, name = _select_ref_book(books)
        assert book_id == "20"
        assert name == "Caesars"


# ── Tests: book_odds in parse output ────────────────────────────────��────────

def _multi_book_event(pitcher="Gerrit Cole", line_val=7.5,
                      books=("23", "22", "19", "30", "20", "38")):
    """Event with multiple tracked books, all with over and under on same line."""
    prices_over  = {b: {"price": -110, "is_main_line": True, "price_delta": 0} for b in books}
    prices_under = {b: {"price": -110, "is_main_line": True, "price_delta": 0} for b in books}
    return {
        "event_id": "evt-multibook",
        "event_date": "2026-04-01T23:05:00Z",
        "teams": [
            {"name": "NYY", "is_away": True,  "is_home": False},
            {"name": "BOS", "is_away": False, "is_home": True},
        ],
        "markets": [{
            "market_id": 19,
            "participants": [{
                "name": pitcher,
                "lines": [
                    {"value": f"Over {line_val}",  "prices": prices_over},
                    {"value": f"Under {line_val}", "prices": prices_under},
                ],
            }],
        }],
    }


class TestBookOdds:
    def test_book_odds_populated_for_tracked_books(self):
        result = parse_k_props({"events": [_multi_book_event()]})
        assert len(result) == 1
        bo = result[0]["book_odds"]
        assert bo is not None
        assert "FanDuel"    in bo   # book 23
        assert "BetMGM"     in bo   # book 22
        assert "DraftKings" in bo   # book 19
        assert "BetRivers"  in bo   # book 30
        assert "Caesars"    in bo   # book 20
        assert "Fanatics"   in bo   # book 38

    def test_book_odds_entry_has_over_and_under(self):
        result = parse_k_props({"events": [_multi_book_event()]})
        fd = result[0]["book_odds"]["FanDuel"]
        assert fd["over"]  == -110
        assert fd["under"] == -110

    def test_pitcher_skipped_when_no_target_book(self):
        # Option B: only untracked book "1" present → pitcher is skipped
        # entirely (no fallback). Previously book_odds was None; now the
        # whole prop is dropped.
        result = parse_k_props({"events": [_multi_book_event(books=["1"])]})
        assert result == []

    def test_book_odds_excludes_book_missing_one_side(self):
        # BetRivers (30) has over but no under → should not appear in book_odds
        event = _multi_book_event(books=["23", "22"])
        # Manually add a book with only over
        event["markets"][0]["participants"][0]["lines"][0]["prices"]["30"] = {
            "price": -112, "is_main_line": True, "price_delta": 0
        }
        result = parse_k_props({"events": [event]})
        bo = result[0]["book_odds"]
        assert "BetRivers" not in (bo or {})


# ── Tests: opening_odds_source (Task A2) ──────────────────────────────────────

class TestOpeningOddsSource:
    """fetch_odds has no knowledge of overnight preview — every prop it emits
    starts life labeled 'first_seen'. Promotion to 'preview' happens later in
    run_pipeline._apply_preview_openings."""

    def test_parse_k_props_tags_source_first_seen(self):
        result = parse_k_props({"events": [_multi_book_event()]})
        assert len(result) == 1
        assert result[0]["opening_odds_source"] == "first_seen"

    def test_parse_k_props_tags_source_first_seen_with_delta(self):
        # Even when price_delta is non-zero (within-day movement), source is
        # still 'first_seen' — the delta-based opening is a within-day opening,
        # not an overnight opening.
        event = _make_event("Shane Bieber", 6.5, -115, -105,
                            over_delta=-5, under_delta=5, is_main=True)
        result = parse_k_props({"events": [event]})
        assert len(result) == 1
        assert result[0]["opening_odds_source"] == "first_seen"


# ── Tests: Option B skip logging ──────────────────────────────────────────────

class TestOptionBSkipLogging:
    """Option B emits an INFO log when a pitcher is dropped for having no
    target-book offer. That keeps the behavior visible in pipeline logs
    without blowing up verbosity (expected to fire on a handful of outliers
    per day per historical data)."""

    def test_logs_when_no_target_book_offers_over(self, caplog):
        import logging
        caplog.set_level(logging.INFO, logger="fetch_odds")
        event = {
            "event_id": "evt-skip",
            "event_date": "2026-04-01T23:05:00Z",
            "teams": [
                {"name": "NYY", "is_away": True,  "is_home": False},
                {"name": "BOS", "is_away": False, "is_home": True},
            ],
            "markets": [{
                "market_id": 19,
                "participants": [{
                    "name": "Gerrit Cole",
                    "lines": [
                        {"value": "Over 7.5",  "prices": {"25": {"price": -110, "is_main_line": True, "price_delta": 0}}},
                        {"value": "Under 7.5", "prices": {"25": {"price": -110, "is_main_line": True, "price_delta": 0}}},
                    ],
                }],
            }],
        }
        result = parse_k_props({"events": [event]})
        assert result == []
        assert any("Gerrit Cole" in r.getMessage() and "skipping" in r.getMessage()
                   for r in caplog.records)
