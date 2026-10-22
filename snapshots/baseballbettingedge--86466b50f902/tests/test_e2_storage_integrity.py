from analytics.diagnostics.e2_storage_integrity import (
    build_storage_integrity_report,
    field_presence_rate,
)


def test_field_presence_rate_counts_none_as_missing():
    rows = [{"park_factor": 1.02}, {"park_factor": None}, {}]

    assert field_presence_rate(rows, "park_factor") == 1 / 3


def test_field_presence_rate_accepts_false_boolean_as_present():
    rows = [{"is_opener": False}, {"is_opener": True}, {}]

    assert field_presence_rate(rows, "is_opener") == 2 / 3


def test_build_storage_integrity_report_includes_required_sections():
    rows = [
        {
            "date": "2026-04-27",
            "locked_at": "2026-04-27T16:00:00Z",
            "park_factor": 1.01,
            "opening_odds_source": "preview",
            "pitcher_throws": "R",
            "career_swstr_pct": 0.114,
            "swstr_delta_k9": 0.4,
            "days_since_last_start": 5,
            "last_pitch_count": 92,
            "rest_k9_delta": -0.2,
            "edge": 0.08,
        },
        {
            "date": "2026-04-28",
            "locked_at": None,
            "park_factor": 0.98,
            "opening_odds_source": "first_seen",
            "pitcher_throws": "L",
            "career_swstr_pct": 0.108,
            "swstr_delta_k9": 0.5,
            "days_since_last_start": 6,
            "last_pitch_count": 87,
            "rest_k9_delta": 0.0,
            "edge": 0.05,
        },
    ]

    report = build_storage_integrity_report(rows)

    assert "## Persisted Field Matrix By Regime" in report
    assert "## Locked Vs Unlocked Field Population Comparison" in report
    assert "## Same-Day Transition-Slate Exceptions" in report
    assert "## History Fields That Are Safe For Future Modeling" in report
    assert "## History Fields That Are Too Regime-Fragile For Naive Reuse" in report
    assert "good enough for season learning" in report
