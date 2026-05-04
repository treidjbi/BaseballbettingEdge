from market_infra.provider_audit import build_provider_coverage_audit


def _snapshot(player, book, line, side, price=-110):
    book_titles = {
        "fanduel": "FanDuel",
        "draftkings": "DraftKings",
        "betrivers": "BetRivers",
        "kalshi": "Kalshi",
    }
    return {
        "provider": "propline",
        "bookmaker_key": book,
        "bookmaker_title": book_titles.get(book, book),
        "player_name": player,
        "normalized_player_name": player.lower(),
        "line": line,
        "side": side,
        "american_odds": price,
    }


def _complete_snapshot_group(player, book, line):
    return [
        _snapshot(player, book, line, "over", -115),
        _snapshot(player, book, line, "under", -105),
    ]


def test_provider_audit_counts_same_line_overlap_and_fillable_gaps():
    production = {
        "date": "2026-05-04",
        "pitchers": [
            {
                "pitcher": "Gerrit Cole",
                "k_line": 7.5,
                "book_odds": {
                    "BetMGM": {"over": -110, "under": -110},
                },
            },
            {
                "pitcher": "Tarik Skubal",
                "k_line": 6.5,
                "book_odds": {
                    "FanDuel": {"over": -120, "under": 100},
                },
            },
        ],
    }
    snapshots = (
        _complete_snapshot_group("Gerrit Cole", "fanduel", 7.5)
        + _complete_snapshot_group("Gerrit Cole", "betrivers", 7.5)
        + _complete_snapshot_group("Tarik Skubal", "fanduel", 6.5)
    )

    audit = build_provider_coverage_audit(snapshots, production)

    assert audit["same_line_overlap_count"] == 1
    assert audit["line_conflict_count"] == 0
    assert audit["missing_target_books"] == ["draftkings", "kalshi"]
    assert audit["parsed_pitcher_prop_count"] == 2
    assert audit["complete_pitcher_line_groups"] == 3
    assert audit["metadata"]["fillable_missing_book_counts"] == {
        "betrivers": 1,
        "draftkings": 0,
        "fanduel": 1,
        "kalshi": 0,
    }
    assert audit["metadata"]["target_book_group_counts"]["fanduel"] == 2
    assert audit["metadata"]["production_book_group_counts"]["fanduel"] == 1


def test_provider_audit_counts_line_conflicts_by_pitcher_and_book():
    production = {
        "pitchers": [
            {
                "pitcher": "Gerrit Cole",
                "k_line": 7.5,
                "book_odds": {
                    "FanDuel": {"over": -110, "under": -110},
                },
            },
        ],
    }
    snapshots = _complete_snapshot_group("Gerrit Cole", "fanduel", 8.5)

    audit = build_provider_coverage_audit(snapshots, production)

    assert audit["same_line_overlap_count"] == 0
    assert audit["line_conflict_count"] == 1
    assert audit["metadata"]["line_conflict_examples"] == [{
        "bookmaker_key": "fanduel",
        "pitcher": "Gerrit Cole",
        "production_line": 7.5,
        "provider_line": 8.5,
    }]


def test_provider_audit_ignores_incomplete_snapshot_groups():
    production = {
        "pitchers": [
            {
                "pitcher": "Gerrit Cole",
                "k_line": 7.5,
                "book_odds": {},
            },
        ],
    }
    snapshots = [_snapshot("Gerrit Cole", "fanduel", 7.5, "over")]

    audit = build_provider_coverage_audit(snapshots, production)

    assert audit["parsed_pitcher_prop_count"] == 0
    assert audit["complete_pitcher_line_groups"] == 0
    assert audit["metadata"]["target_book_group_counts"]["fanduel"] == 0


def test_provider_audit_counts_all_overlaps_even_when_examples_are_capped():
    pitchers = [
        {
            "pitcher": f"Pitcher {idx}",
            "k_line": 5.5,
            "book_odds": {
                "FanDuel": {"over": -110, "under": -110},
            },
        }
        for idx in range(30)
    ]
    snapshots = []
    for pitcher in pitchers:
        snapshots.extend(_complete_snapshot_group(pitcher["pitcher"], "fanduel", 5.5))

    audit = build_provider_coverage_audit(snapshots, {"pitchers": pitchers})

    assert audit["same_line_overlap_count"] == 30
    assert len(audit["metadata"]["same_line_overlap_examples"]) == 25
