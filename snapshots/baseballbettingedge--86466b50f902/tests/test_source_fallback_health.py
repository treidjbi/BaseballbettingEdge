from analytics.diagnostics.source_fallback_health import (
    render_summary,
    summarize_artifact,
)


def test_summarize_artifact_counts_sources_books_openings_and_warnings():
    artifact = {
        "date": "2026-05-05",
        "generated_at": "2026-05-05T13:00:00Z",
        "data_warnings": ["sample warning"],
        "tracked_picks": [{"pitcher": "A"}],
        "pitchers": [
            {
                "pitcher": "A",
                "odds_source": "therundown",
                "ref_book": "BetMGM",
                "opening_odds_source": "preview",
            },
            {
                "pitcher": "B",
                "odds_source": "therundown+propline",
                "ref_book": "FanDuel",
                "opening_odds_source": "first_seen",
            },
            {
                "pitcher": "C",
                "odds_source": "",
                "ref_book": None,
                "opening_odds_source": "",
            },
        ],
    }

    summary = summarize_artifact(artifact)

    assert summary == {
        "date": "2026-05-05",
        "generated_at": "2026-05-05T13:00:00Z",
        "pitchers": 3,
        "tracked_picks": 1,
        "source_counts": {
            "therundown": 1,
            "therundown+propline": 1,
            "unknown": 1,
        },
        "book_counts": {"BetMGM": 1, "FanDuel": 1, "unknown": 1},
        "opening_counts": {"first_seen": 1, "preview": 1, "unknown": 1},
        "data_warnings": ["sample warning"],
    }


def test_render_summary_includes_supabase_sidecar_note_and_empty_warnings():
    summary = {
        "date": "2026-05-05",
        "generated_at": "2026-05-05T13:00:00Z",
        "pitchers": 2,
        "tracked_picks": 0,
        "source_counts": {"therundown": 2},
        "book_counts": {"FanDuel": 2},
        "opening_counts": {"preview": 2},
        "data_warnings": [],
    }

    rendered = render_summary(summary)

    assert "# Source Fallback Health" in rendered
    assert "Supabase sidecar already stores provider-run and snapshot history" in rendered
    assert "local artifact health only" in rendered
    assert "- Date: 2026-05-05" in rendered
    assert "- Pitcher records: 2" in rendered
    assert "- Tracked picks: 0" in rendered
    assert "- `therundown`: 2" in rendered
    assert "- none" in rendered
