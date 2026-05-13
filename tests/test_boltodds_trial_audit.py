import json

from analytics.diagnostics.boltodds_trial_audit import main, summarize_provider_audits


def test_summarize_provider_audits_counts_trial_review_fields():
    rows = [
        {
            "provider": "boltodds",
            "slate_date": "2026-05-04",
            "created_at": "2026-05-04T20:00:00Z",
            "complete_pitcher_line_groups": 3,
            "same_line_overlap_count": 2,
            "line_conflict_count": 1,
            "missing_target_books": ["kalshi"],
            "metadata": {
                "target_book_group_counts": {
                    "betrivers": 1,
                    "draftkings": 0,
                    "fanduel": 2,
                    "kalshi": 0,
                },
                "production_book_group_counts": {
                    "draftkings": 1,
                    "fanduel": 2,
                },
                "fillable_missing_book_counts": {
                    "betrivers": 1,
                    "draftkings": 0,
                    "fanduel": 1,
                    "kalshi": 0,
                },
                "non_target_books_seen": ["bovada", "pinnacle"],
            },
        },
        {
            "provider": "boltodds",
            "slate_date": "2026-05-05",
            "created_at": "2026-05-05T20:00:00Z",
            "complete_pitcher_line_groups": 4,
            "same_line_overlap_count": 3,
            "line_conflict_count": 0,
            "missing_target_books": ["betrivers", "kalshi"],
            "metadata": {
                "target_book_group_counts": {
                    "betrivers": 0,
                    "draftkings": 2,
                    "fanduel": 2,
                    "kalshi": 0,
                },
                "production_book_group_counts": {
                    "draftkings": 2,
                    "fanduel": 1,
                },
                "fillable_missing_book_counts": {
                    "betrivers": 0,
                    "draftkings": 1,
                    "fanduel": 0,
                    "kalshi": 0,
                },
                "non_target_books_seen": ["bovada"],
            },
        },
    ]

    summary = summarize_provider_audits(rows)

    assert summary["provider"] == "boltodds"
    assert summary["input_rows"] == 2
    assert summary["provider_rows"] == 2
    assert summary["deduped_rows"] == 2
    assert summary["slates"] == 2
    assert summary["total_complete_pitcher_line_groups"] == 7
    assert summary["total_same_line_overlap_count"] == 5
    assert summary["total_line_conflict_count"] == 1
    assert summary["missing_target_books_by_slate"] == {
        "2026-05-04": ["kalshi"],
        "2026-05-05": ["betrivers", "kalshi"],
    }
    assert summary["target_book_group_counts"] == {
        "betrivers": 1,
        "draftkings": 2,
        "fanduel": 4,
        "kalshi": 0,
    }
    assert summary["production_book_group_counts"] == {
        "draftkings": 3,
        "fanduel": 3,
    }
    assert summary["fillable_missing_book_counts"] == {
        "betrivers": 1,
        "draftkings": 1,
        "fanduel": 1,
        "kalshi": 0,
    }
    assert summary["non_target_books_seen"] == ["bovada", "pinnacle"]
    assert summary["row_counted_totals"] == {
        "complete_pitcher_line_groups": 7,
        "same_line_overlap_count": 5,
        "line_conflict_count": 1,
    }


def test_summarize_provider_audits_filters_other_providers():
    rows = [
        {
            "slate_date": "2026-05-04",
            "complete_pitcher_line_groups": 88,
            "same_line_overlap_count": 88,
            "line_conflict_count": 88,
            "missing_target_books": ["draftkings"],
            "metadata": {
                "target_book_group_counts": {"draftkings": 88},
                "production_book_group_counts": {"draftkings": 88},
                "fillable_missing_book_counts": {"draftkings": 88},
                "non_target_books_seen": ["pinnacle"],
            },
        },
        {
            "provider": "propline",
            "slate_date": "2026-05-04",
            "complete_pitcher_line_groups": 99,
            "same_line_overlap_count": 99,
            "line_conflict_count": 99,
            "missing_target_books": ["fanduel"],
            "metadata": {
                "target_book_group_counts": {"fanduel": 99},
                "production_book_group_counts": {"fanduel": 99},
                "fillable_missing_book_counts": {"fanduel": 99},
                "non_target_books_seen": ["bovada"],
            },
        },
        {
            "provider": "boltodds",
            "slate_date": "2026-05-04",
            "complete_pitcher_line_groups": 2,
            "same_line_overlap_count": 1,
            "line_conflict_count": 0,
            "missing_target_books": ["kalshi"],
            "metadata": {
                "target_book_group_counts": {"fanduel": 2},
                "production_book_group_counts": {"fanduel": 2},
                "fillable_missing_book_counts": {"fanduel": 0},
                "non_target_books_seen": [],
            },
        },
    ]

    summary = summarize_provider_audits(rows)

    assert summary["input_rows"] == 3
    assert summary["provider_rows"] == 1
    assert summary["total_complete_pitcher_line_groups"] == 2
    assert summary["total_same_line_overlap_count"] == 1
    assert summary["target_book_group_counts"] == {"fanduel": 2}
    assert summary["missing_target_books_by_slate"] == {"2026-05-04": ["kalshi"]}


def test_summarize_provider_audits_uses_latest_row_per_slate():
    rows = [
        {
            "provider": "boltodds",
            "slate_date": "2026-05-04",
            "created_at": "2026-05-04T18:00:00Z",
            "complete_pitcher_line_groups": 1,
            "same_line_overlap_count": 1,
            "line_conflict_count": 0,
            "missing_target_books": ["fanduel"],
            "metadata": {
                "snapshot_rows": 10,
                "target_book_group_counts": {"fanduel": 0},
                "production_book_group_counts": {"fanduel": 1},
                "fillable_missing_book_counts": {"fanduel": 1},
            },
        },
        {
            "provider": "boltodds",
            "slate_date": "2026-05-04",
            "created_at": "2026-05-04T19:00:00Z",
            "complete_pitcher_line_groups": 3,
            "same_line_overlap_count": 2,
            "line_conflict_count": 0,
            "missing_target_books": ["kalshi"],
            "metadata": {
                "snapshot_rows": 20,
                "target_book_group_counts": {"fanduel": 2},
                "production_book_group_counts": {"fanduel": 2},
                "fillable_missing_book_counts": {"fanduel": 0},
            },
        },
    ]

    summary = summarize_provider_audits(rows)

    assert summary["provider_rows"] == 2
    assert summary["deduped_rows"] == 1
    assert summary["total_complete_pitcher_line_groups"] == 3
    assert summary["missing_target_books_by_slate"] == {"2026-05-04": ["kalshi"]}
    assert summary["row_counted_totals"] == {
        "complete_pitcher_line_groups": 4,
        "same_line_overlap_count": 3,
        "line_conflict_count": 0,
    }


def test_summarize_provider_audits_handles_empty_input():
    assert summarize_provider_audits([]) == {
        "provider": "boltodds",
        "input_rows": 0,
        "provider_rows": 0,
        "deduped_rows": 0,
        "slates": 0,
        "total_complete_pitcher_line_groups": 0,
        "total_same_line_overlap_count": 0,
        "total_line_conflict_count": 0,
        "missing_target_books_by_slate": {},
        "target_book_group_counts": {},
        "production_book_group_counts": {},
        "fillable_missing_book_counts": {},
        "non_target_books_seen": [],
        "row_counted_totals": {
            "complete_pitcher_line_groups": 0,
            "same_line_overlap_count": 0,
            "line_conflict_count": 0,
        },
    }


def test_main_prints_sorted_indented_json(tmp_path, capsys):
    input_path = tmp_path / "provider_audits.json"
    input_path.write_text(
        json.dumps(
            [
                {
                    "provider": "boltodds",
                    "slate_date": "2026-05-04",
                    "complete_pitcher_line_groups": 1,
                    "same_line_overlap_count": 1,
                    "line_conflict_count": 0,
                    "missing_target_books": ["kalshi"],
                    "metadata": {},
                }
            ]
        ),
        encoding="utf-8",
    )

    main(["--input", str(input_path)])

    output = capsys.readouterr().out
    assert json.loads(output)["missing_target_books_by_slate"] == {
        "2026-05-04": ["kalshi"]
    }
    assert output.startswith("{\n  ")
