import json
import os
import subprocess
import sys

import pytest

from scripts.probe_boltodds_markets import (
    _env,
    build_probe_summary,
    main,
)


TARGET_BOOKS = {
    "fanduel": "FanDuel",
    "draftkings": "DraftKings",
    "betmgm": "BetMGM",
    "betrivers": "BetRivers",
    "scorebet": "theScore Bet",
    "caesars": "Caesars",
}


def _info(sportsbooks):
    return {
        "sports": ["MLB", "NBA"],
        "sportsbooks": sportsbooks,
    }


def _markets():
    return {
        "fanduel": {
            "MLB": [
                "Pitcher Strikeouts",
                "Pitcher Outs",
            ]
        },
        "draftkings": {
            "MLB": [
                "Pitcher Strikeouts",
                "Player Hits",
            ]
        },
        "betmgm": {
            "MLB": [
                "Pitcher Strikeouts",
                "Pitcher Outs",
            ]
        },
    }


def test_summary_ready_with_fanduel_and_one_secondary_book():
    summary = build_probe_summary(
        _info(["FanDuel", "DraftKings", "BetMGM"]),
        _markets(),
        TARGET_BOOKS,
        ["Pitcher Strikeouts"],
    )

    assert summary == {
        "starter_ready": True,
        "selected_markets": ["Pitcher Strikeouts"],
        "missing_books": ["betrivers", "scorebet", "caesars"],
        "available_target_books": ["fanduel", "draftkings", "betmgm"],
        "books_with_selected_market": ["fanduel", "draftkings", "betmgm"],
        "blocking_reasons": [],
    }


def test_summary_blocks_when_pitcher_market_missing():
    summary = build_probe_summary(
        _info(["FanDuel", "DraftKings", "BetMGM"]),
        {"fanduel": {"MLB": ["Pitcher Outs"]}},
        TARGET_BOOKS,
        ["Pitcher Strikeouts"],
    )

    assert summary["starter_ready"] is False
    assert summary["selected_markets"] == []
    assert summary["blocking_reasons"] == [
        "No MLB pitcher strikeout market matched configured aliases"
    ]


def test_summary_allows_draftkings_missing_selected_market_after_partial_approval():
    markets = {
        "fanduel": {"MLB": ["Pitcher Strikeouts"]},
        "draftkings": {"MLB": ["Pitcher Outs"]},
        "betmgm": {"MLB": ["Pitcher Strikeouts"]},
    }

    summary = build_probe_summary(
        _info(["FanDuel", "DraftKings", "BetMGM"]),
        markets,
        TARGET_BOOKS,
        ["Pitcher Strikeouts"],
    )

    assert summary["starter_ready"] is True
    assert summary["books_with_selected_market"] == ["fanduel", "betmgm"]
    assert summary["blocking_reasons"] == []


def test_summary_blocks_when_selected_market_only_appears_under_optional_book():
    markets = {
        "fanduel": {"MLB": ["Pitcher Outs"]},
        "draftkings": {"MLB": ["Pitcher Outs"]},
        "betmgm": {"MLB": ["Pitcher Outs"]},
        "caesars": {"MLB": ["Pitcher Strikeouts"]},
    }

    summary = build_probe_summary(
        _info(["FanDuel", "DraftKings", "BetMGM", "Caesars"]),
        markets,
        TARGET_BOOKS,
        ["Pitcher Strikeouts"],
    )

    assert summary["starter_ready"] is False
    assert summary["selected_markets"] == ["Pitcher Strikeouts"]
    assert summary["books_with_selected_market"] == ["caesars"]
    assert (
        "FanDuel must expose the selected pitcher strikeout market"
        in summary["blocking_reasons"]
    )
    assert (
        "At least one of BetMGM or BetRivers must expose the selected pitcher strikeout market"
        in summary["blocking_reasons"]
    )


def test_summary_blocks_when_mlb_missing_from_get_info_sports():
    info = {
        "sports": ["NBA", "NFL"],
        "sportsbooks": ["FanDuel", "DraftKings", "BetMGM"],
    }

    summary = build_probe_summary(
        info,
        _markets(),
        TARGET_BOOKS,
        ["Pitcher Strikeouts"],
    )

    assert summary["starter_ready"] is False
    assert "MLB is not listed in BoltOdds get_info sports" in summary[
        "blocking_reasons"
    ]


def test_summary_allows_draftkings_unavailable_after_partial_approval():
    summary = build_probe_summary(
        _info(["FanDuel", "BetMGM"]),
        _markets(),
        TARGET_BOOKS,
        ["Pitcher Strikeouts"],
    )

    assert summary["starter_ready"] is True
    assert summary["blocking_reasons"] == []


def test_summary_blocks_when_fanduel_missing():
    summary = build_probe_summary(
        _info(["DraftKings", "BetMGM"]),
        _markets(),
        TARGET_BOOKS,
        ["Pitcher Strikeouts"],
    )

    assert summary["starter_ready"] is False
    assert "FanDuel is a required priority book" in summary[
        "blocking_reasons"
    ]


def test_summary_blocks_when_both_secondary_books_missing():
    summary = build_probe_summary(
        _info(["FanDuel", "DraftKings", "Caesars"]),
        _markets(),
        TARGET_BOOKS,
        ["Pitcher Strikeouts"],
    )

    assert summary["starter_ready"] is False
    assert "At least one of BetMGM or BetRivers must be available" in summary[
        "blocking_reasons"
    ]


def test_optional_missing_books_do_not_block_readiness():
    summary = build_probe_summary(
        _info(["FANDUEL", "BetMGM"]),
        _markets(),
        TARGET_BOOKS,
        ["Pitcher Strikeouts"],
    )

    assert summary["starter_ready"] is True
    assert summary["missing_books"] == [
        "draftkings",
        "betrivers",
        "scorebet",
        "caesars",
    ]
    assert summary["blocking_reasons"] == []


@pytest.mark.parametrize("value", [None, "", "   "])
def test_env_raises_when_required_value_missing_or_blank(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("BOLTODDS_API_KEY", raising=False)
    else:
        monkeypatch.setenv("BOLTODDS_API_KEY", value)

    with pytest.raises(EnvironmentError, match="BOLTODDS_API_KEY is required"):
        _env("BOLTODDS_API_KEY")


def test_env_returns_required_value(monkeypatch):
    monkeypatch.setenv("BOLTODDS_API_KEY", "  secret-key  ")

    assert _env("BOLTODDS_API_KEY") == "secret-key"


def test_main_returns_zero_and_prints_summary_when_ready(monkeypatch, capsys):
    monkeypatch.setenv("BOLTODDS_API_KEY", "secret-key")
    monkeypatch.setattr(
        "scripts.probe_boltodds_markets.target_books_from_env",
        lambda: TARGET_BOOKS,
    )
    monkeypatch.setattr(
        "scripts.probe_boltodds_markets.market_aliases_from_env",
        lambda: ["Pitcher Strikeouts"],
    )
    calls = []

    def fake_get_json(path, api_key, params=None):
        calls.append((path, api_key, params))
        if path == "get_info":
            return _info(["FanDuel", "DraftKings", "BetMGM"])
        return _markets()

    monkeypatch.setattr("scripts.probe_boltodds_markets.get_json", fake_get_json)

    assert main() == 0

    assert calls == [
        ("get_info", "secret-key", None),
        (
            "get_markets",
            "secret-key",
            {
                "sports": "MLB",
                "sportsbooks": "fanduel,draftkings,betmgm,betrivers,scorebet,caesars",
            },
        ),
    ]
    printed = json.loads(capsys.readouterr().out)
    assert printed["starter_ready"] is True


def test_main_returns_one_when_probe_blocks(monkeypatch, capsys):
    monkeypatch.setenv("BOLTODDS_API_KEY", "secret-key")
    monkeypatch.setattr(
        "scripts.probe_boltodds_markets.target_books_from_env",
        lambda: TARGET_BOOKS,
    )
    monkeypatch.setattr(
        "scripts.probe_boltodds_markets.market_aliases_from_env",
        lambda: ["Pitcher Strikeouts"],
    )

    def fake_get_json(path, api_key, params=None):
        if path == "get_info":
            return _info(["DraftKings", "BetMGM"])
        return _markets()

    monkeypatch.setattr("scripts.probe_boltodds_markets.get_json", fake_get_json)

    assert main() == 1

    printed = json.loads(capsys.readouterr().out)
    assert printed["starter_ready"] is False


def test_direct_script_execution_reaches_env_check_without_repo_path_env():
    env = os.environ.copy()
    env.pop("BOLTODDS_API_KEY", None)

    result = subprocess.run(
        [sys.executable, "scripts/probe_boltodds_markets.py"],
        capture_output=True,
        env=env,
        text=True,
    )

    assert result.returncode != 0
    assert "BOLTODDS_API_KEY is required" in result.stderr
    assert "ModuleNotFoundError" not in result.stderr
