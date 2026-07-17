from analytics.diagnostics.shadow_notification_candidate_audit import (
    build_report,
    summarize_candidates,
    summarize_ready_to_bet,
)


def test_summarize_candidates_counts_candidate_actions_and_noise():
    rows = [
        {
            "provider": "boltodds",
            "candidate_type": "market_confirmed_playable",
            "candidate_action": "would_send_shadow",
            "betrivers_only": False,
            "suppression_reasons": [],
            "metadata": {"movement_strength_labels": ["broad_confirmation", "boltodds_confirmed"]},
        },
        {
            "provider": "boltodds",
            "candidate_type": "market_confirmed_playable",
            "candidate_action": "suppress_shadow",
            "betrivers_only": True,
            "suppression_reasons": ["betrivers_only", "volatile_or_reversed"],
            "metadata": {"movement_strength_labels": ["single_book", "volatile_or_reversed"]},
        },
        {
            "provider": "propline",
            "candidate_type": "market_confirmed_worse_number",
            "candidate_action": "suppress_shadow",
            "betrivers_only": False,
            "suppression_reasons": ["number_worse"],
            "metadata": {"movement_strength_labels": ["propline_polling_confirmed"]},
        },
    ]

    summary = summarize_candidates(rows)

    assert summary[("boltodds", "market_confirmed_playable")] == {
        "rows": 2,
        "would_send_shadow": 1,
        "suppress_shadow": 1,
        "betrivers_only": 1,
        "volatile_or_reversed": 1,
        "number_worse": 0,
        "movement_strength_labels": {
            "boltodds_confirmed": 1,
            "broad_confirmation": 1,
            "single_book": 1,
            "volatile_or_reversed": 1,
        },
    }
    assert summary[("propline", "market_confirmed_worse_number")]["number_worse"] == 1
    assert summary[("propline", "market_confirmed_worse_number")]["movement_strength_labels"] == {
        "propline_polling_confirmed": 1
    }


def test_build_report_keeps_candidates_shadow_only():
    report = build_report([
        {
            "provider": "boltodds",
            "candidate_type": "market_confirmed_playable",
            "candidate_action": "would_send_shadow",
            "betrivers_only": False,
            "suppression_reasons": [],
            "metadata": {"movement_strength_labels": ["broad_confirmation", "boltodds_confirmed"]},
        }
    ])

    assert "# Shadow Notification Candidate Audit" in report
    assert "shadow-only" in report
    assert "does not send notifications" in report
    assert "| `boltodds` | `market_confirmed_playable` |" in report
    assert "## Movement Strength Labels" in report
    assert "| `boltodds_confirmed` | 1 |" in report


def test_ready_to_bet_summary_counts_dates_windows_and_overlap():
    rows = [
        {
            "slate_date": "2026-07-17",
            "provider": "therundown_propline",
            "candidate_type": "ready_to_bet",
            "time_window": "pre_60",
            "metadata": {"same_run_notification_types": ["pick_upgraded"]},
        },
        {
            "slate_date": "2026-07-18",
            "provider": "therundown",
            "candidate_type": "ready_to_bet",
            "time_window": "pre_30",
            "metadata": {"same_run_notification_types": []},
        },
    ]

    assert summarize_ready_to_bet(rows) == {
        "rows": 2,
        "by_date": {"2026-07-17": 1, "2026-07-18": 1},
        "by_provider": {"therundown": 1, "therundown_propline": 1},
        "by_time_window": {"pre_30": 1, "pre_60": 1},
        "notification_overlap": {"pick_upgraded": 1},
    }
