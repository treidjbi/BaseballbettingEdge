import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "pipeline"))

from fetch_provider_market_odds import (
    fetch_official_market_odds,
    official_market_enabled,
    official_market_min_props,
    official_row_to_prop,
)


class FakeWriter:
    def __init__(self, official_rows=None, baseline_rows=None):
        self.official_rows = official_rows or []
        self.baseline_rows = baseline_rows or []
        self.calls = []

    def select_rows(self, table, params):
        self.calls.append((table, dict(params)))
        if table == "official_market_lines":
            return self.official_rows
        if table == "market_opening_baselines":
            return self.baseline_rows
        raise AssertionError(f"unexpected table: {table}")


def _official_row(**overrides):
    row = {
        "id": 88,
        "slate_date": "2026-05-13",
        "normalized_player_name": "jose berrios",
        "player_name": "Jose Berrios",
        "market_key": "pitcher_strikeouts",
        "ref_book_key": "fanduel",
        "ref_book_name": "FanDuel",
        "ref_line": 5.5,
        "ref_over_odds": -115,
        "ref_under_odds": -105,
        "game_time": "2026-05-13T23:05:00Z",
        "selected_provider": "boltodds",
        "book_odds": {
            "FanDuel": {"line": 5.5, "over": -115, "under": -105, "provider": "boltodds"},
            "DraftKings": {"line": 5.5, "over": -112, "under": -108, "provider": "propline"},
        },
        "provider_coverage": {
            "fanduel": {"provider": "boltodds", "line": 5.5},
            "draftkings": {"provider": "propline", "line": 5.5},
        },
        "arbitration_reasons": ["fresh_complete_supported_line", "boltodds_primary"],
        "current_market_line_ids": [11, 12],
        "ready_for_pipeline": True,
    }
    row.update(overrides)
    return row


def _baseline_row(**overrides):
    row = {
        "slate_date": "2026-05-13",
        "normalized_player_name": "jose berrios",
        "player_name": "Jose Berrios",
        "market_key": "pitcher_strikeouts",
        "book_key": "fanduel",
        "book_name": "FanDuel",
        "line": 5.5,
        "opening_over_odds": -110,
        "opening_under_odds": -110,
        "opening_provider": "boltodds",
        "opening_source": "provider_first_seen",
    }
    row.update(overrides)
    return row


def test_official_row_to_prop_returns_existing_fetch_odds_shape(monkeypatch):
    monkeypatch.setenv("OFFICIAL_MARKET_SOURCE", "therundown_propline")
    prop = official_row_to_prop(_official_row(selected_provider="therundown"), {})

    required_fields = {
        "pitcher",
        "team",
        "opp_team",
        "k_line",
        "opening_line",
        "ref_book",
        "best_over_book",
        "best_under_book",
        "best_over_odds",
        "best_under_odds",
        "opening_over_odds",
        "opening_under_odds",
        "opening_odds_source",
        "book_odds",
        "odds_source",
    }
    assert required_fields.issubset(prop)
    assert prop["pitcher"] == "Jose Berrios"
    assert prop["team"] == ""
    assert prop["opp_team"] == ""
    assert prop["game_time"] == "2026-05-13T23:05:00Z"
    assert prop["k_line"] == 5.5
    assert prop["ref_book"] == "FanDuel"
    assert prop["best_over_odds"] == -115
    assert prop["best_under_odds"] == -105
    assert prop["opening_over_odds"] == -115
    assert prop["opening_under_odds"] == -105
    assert prop["opening_odds_source"] == "first_seen"
    assert prop["odds_source"] == "therundown+propline"
    assert prop["market_source_mode"] == "therundown_propline"
    assert prop["line_source_provider"] == "therundown"
    assert prop["source_snapshot_ids"] == [11, 12]


def test_multiple_books_are_preserved_in_book_odds():
    prop = official_row_to_prop(_official_row(), {})

    assert prop["book_odds"] == {
        "FanDuel": {"line": 5.5, "over": -115, "under": -105, "provider": "boltodds"},
        "DraftKings": {"line": 5.5, "over": -112, "under": -108, "provider": "propline"},
    }
    assert prop["provider_coverage"]["draftkings"]["provider"] == "propline"


def test_opening_baselines_match_preview_opening_assumptions():
    writer = FakeWriter([_official_row()], [_baseline_row()])

    props = fetch_official_market_odds("2026-05-13", writer=writer, min_props=1)

    assert len(props) == 1
    prop = props[0]
    assert prop["opening_over_odds"] == -110
    assert prop["opening_under_odds"] == -110
    assert prop["opening_line"] == 5.5
    assert prop["opening_odds_source"] == "first_seen"
    assert writer.calls[0] == (
        "official_market_lines",
        {
            "slate_date": "eq.2026-05-13",
            "market_key": "eq.pitcher_strikeouts",
            "ready_for_pipeline": "eq.true",
            "order": "normalized_player_name.asc",
            "limit": "10000",
        },
    )


def test_missing_official_rows_return_empty_for_fallback():
    writer = FakeWriter([], [])

    assert fetch_official_market_odds("2026-05-13", writer=writer) == []


def test_minimum_coverage_gate_returns_empty_for_fallback():
    writer = FakeWriter([_official_row()], [])

    assert fetch_official_market_odds("2026-05-13", writer=writer, min_props=2) == []


def test_disabled_rows_bad_lines_and_missing_game_times_are_skipped():
    writer = FakeWriter(
        [
            _official_row(ready_for_pipeline=False),
            _official_row(player_name="Bad Line", normalized_player_name="bad line", ref_line=1.0),
            _official_row(player_name="No Time", normalized_player_name="no time", game_time=""),
        ],
        [],
    )

    assert fetch_official_market_odds("2026-05-13", writer=writer) == []


def test_official_market_enabled_requires_explicit_mode_and_enable_flag(monkeypatch):
    monkeypatch.delenv("OFFICIAL_MARKET_SOURCE", raising=False)
    monkeypatch.delenv("ENABLE_BOLTODDS_PIPELINE_SOURCE", raising=False)
    monkeypatch.delenv("ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE", raising=False)
    assert official_market_enabled() is False

    monkeypatch.setenv("OFFICIAL_MARKET_SOURCE", "therundown_propline")
    assert official_market_enabled() is False

    monkeypatch.setenv("ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE", "true")
    assert official_market_enabled() is True


def test_retired_boltodds_mode_stays_closed_without_rehearsal_approval(monkeypatch):
    monkeypatch.setenv("OFFICIAL_MARKET_SOURCE", "boltodds_propline")
    monkeypatch.setenv("ENABLE_BOLTODDS_PIPELINE_SOURCE", "true")
    monkeypatch.delenv("ALLOW_BOLTODDS_PROVIDER_REHEARSAL", raising=False)
    assert official_market_enabled() is False


def test_blank_or_invalid_min_props_uses_conservative_default(monkeypatch):
    monkeypatch.setenv("OFFICIAL_MARKET_MIN_PROPS", "")
    assert official_market_min_props() == 12

    monkeypatch.setenv("OFFICIAL_MARKET_MIN_PROPS", "not-a-number")
    assert official_market_min_props() == 12

    monkeypatch.setenv("OFFICIAL_MARKET_MIN_PROPS", "0")
    assert official_market_min_props() == 12

    monkeypatch.setenv("OFFICIAL_MARKET_MIN_PROPS", "-5")
    assert official_market_min_props() == 12

    monkeypatch.setenv("OFFICIAL_MARKET_MIN_PROPS", "1")
    assert official_market_min_props() == 1


def test_opening_baseline_can_match_when_current_line_moves():
    writer = FakeWriter(
        [_official_row(ref_line=5.5)],
        [_baseline_row(line=4.5, opening_over_odds=105, opening_under_odds=-135)],
    )

    props = fetch_official_market_odds("2026-05-13", writer=writer, min_props=1)

    assert props[0]["k_line"] == 5.5
    assert props[0]["opening_line"] == 4.5
    assert props[0]["opening_over_odds"] == 105
    assert props[0]["opening_under_odds"] == -135
