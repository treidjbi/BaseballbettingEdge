from analytics.diagnostics import market_agreement_tracker as tracker


def _movement_row(**overrides):
    row = {
        "slate_date": "2026-06-07",
        "pitcher": "Example Starter",
        "normalized_pitcher": "example starter",
        "side": "over",
        "provider": "boltodds",
        "checkpoint": "pre_30",
        "current_verdict": "LEAN",
        "market_consensus": "toward_pick",
        "bet_value_consensus": "worse_now",
        "toward_pick_count": 2,
        "away_from_pick_count": 0,
        "better_now_count": 0,
        "worse_now_count": 2,
        "reversal_book_count": 0,
        "broad_confirmation": True,
        "metadata": {
            "book_summaries": {
                "fanduel": {"odds_delta": -24, "line_delta": 0.0},
                "betmgm": {"odds_delta": -18, "line_delta": 0.0},
            }
        },
    }
    row.update(overrides)
    return row


def test_movement_labels_translate_consensus_to_model_agreement():
    assert tracker.movement_agreement_label(_movement_row(market_consensus="toward_pick")) == "market_with_model"
    assert tracker.movement_agreement_label(_movement_row(market_consensus="away_from_pick")) == "market_against_model"
    assert tracker.movement_agreement_label(_movement_row(market_consensus="mixed")) == "market_mixed"
    assert tracker.movement_agreement_label(_movement_row(market_consensus="none")) == "market_no_signal"

    assert tracker.movement_value_label(_movement_row(bet_value_consensus="better_now")) == "number_better_now"
    assert tracker.movement_value_label(_movement_row(bet_value_consensus="worse_now")) == "number_worse_now"
    assert tracker.movement_value_label(_movement_row(bet_value_consensus="mixed")) == "value_mixed"
    assert tracker.movement_value_label(_movement_row(bet_value_consensus="none")) == "value_no_signal"


def test_strength_and_magnitude_use_existing_book_summaries():
    broad = _movement_row()
    assert tracker.movement_strength_label(broad) == "broad_with_model"
    assert tracker.movement_magnitude_bucket(broad) == "odds_20c_plus"

    single = _movement_row(toward_pick_count=1, away_from_pick_count=0, broad_confirmation=False)
    assert tracker.movement_strength_label(single) == "single_book_with_model"

    line_move = _movement_row(
        metadata={"book_summaries": {"fanduel": {"odds_delta": -5, "line_delta": 0.5}}}
    )
    assert tracker.movement_magnitude_bucket(line_move) == "line_half_plus"

    mixed = _movement_row(market_consensus="mixed", toward_pick_count=1, away_from_pick_count=1)
    assert tracker.movement_strength_label(mixed) == "mixed_or_reversed"


def test_tracker_bucket_prioritizes_referee_caps_before_lean_label():
    lean = tracker.annotate_row(_movement_row(current_verdict="LEAN"))
    assert lean["tracker_bucket"] == "lean_market_with_us"

    capped = tracker.annotate_row(
        _movement_row(
            current_verdict="LEAN",
            raw_verdict="FIRE 2u",
            market_consensus="away_from_pick",
            toward_pick_count=0,
            away_from_pick_count=2,
            confidence_referee={
                "mode": "enforce",
                "applied": True,
                "relationship": "model_fades_favorite",
                "would_cap_to": "LEAN",
            },
        )
    )
    assert capped["tracker_bucket"] == "referee_cap_market_against_us"
    assert capped["confidence_referee_applied"] is True


def test_build_tracker_rows_overlays_current_artifact_referee_metadata():
    rows = tracker.build_tracker_rows(
        market_pick_evidence_rows=[
            _movement_row(
                current_verdict="LEAN",
                raw_verdict=None,
                confidence_referee=None,
            )
        ],
        live_market_display_rows=[],
        market_snapshot_rows=[],
        history_rows=[],
        current_pick_rows=[
            {
                "date": "2026-06-07",
                "pitcher": "Example Starter",
                "side": "over",
                "verdict": "LEAN",
                "raw_verdict": "FIRE 1u",
                "actionable_verdict": "LEAN",
                "confidence_referee": {
                    "mode": "enforce",
                    "applied": True,
                    "relationship": "model_fades_favorite",
                    "would_cap_to": "LEAN",
                },
            }
        ],
    )

    assert len(rows) == 1
    assert rows[0]["raw_verdict"] == "FIRE 1u"
    assert rows[0]["confidence_referee_applied"] is True
    assert rows[0]["tracker_bucket"] == "referee_cap_market_with_us"


def test_build_tracker_rows_uses_gate_c_history_pnl_fields():
    rows = tracker.build_tracker_rows(
        market_pick_evidence_rows=[_movement_row()],
        live_market_display_rows=[],
        market_snapshot_rows=[],
        history_rows=[
            {
                "slate_date": "2026-06-07",
                "pitcher": "Example Starter",
                "side": "over",
                "result": "win",
                "pick_history_pnl": 0.91,
            }
        ],
    )

    assert rows[0]["result"] == "win"
    assert rows[0]["pnl"] == 0.91


def test_load_pick_metadata_rows_accepts_gate_c_jsonl(tmp_path):
    path = tmp_path / "pitcher_k_outcome_dataset.jsonl"
    path.write_text(
        '{"slate_date":"2026-06-07","pitcher":"Example Starter","side":"over","confidence_referee":{"applied":true}}\n',
        encoding="utf-8",
    )

    rows = tracker.load_pick_metadata_rows(path)

    assert len(rows) == 1
    assert rows[0]["pitcher"] == "Example Starter"
    assert rows[0]["confidence_referee"] == {"applied": True}


def test_build_report_keeps_market_agreement_shadow_only():
    report = tracker.build_report([
        tracker.annotate_row(
            _movement_row(
                current_verdict="LEAN",
                result="win",
                pnl=0.91,
            )
        )
    ])

    assert "# Market Agreement Tracker" in report
    assert "Shadow-only" in report
    assert "does not change picks, locks, thresholds, staking, provider order, notifications, or calibration" in report
    assert "## Referee Cap Buckets" in report
    assert "`lean_market_with_us`" in report


def test_sample_gate_is_watch_only_below_overall_threshold():
    rows = [
        tracker.annotate_row(
            _movement_row(
                current_verdict="LEAN",
                result="win",
                pnl=0.91,
            )
        )
        for _ in range(74)
    ]

    gate = tracker.sample_gate(rows)

    assert gate["overall_status"] == "watch_only"
    assert gate["graded_rows"] == 74
    assert gate["overall_min_rows"] == 75
    assert gate["bucket_min_rows"] == 50


def test_sample_gate_allows_review_only_when_overall_and_bucket_thresholds_pass():
    rows = [
        tracker.annotate_row(
            _movement_row(
                current_verdict="LEAN",
                result="win",
                pnl=0.91,
            )
        )
        for _ in range(50)
    ]
    rows.extend(
        tracker.annotate_row(
            _movement_row(
                current_verdict="FIRE 1u",
                market_consensus="away_from_pick",
                toward_pick_count=0,
                away_from_pick_count=2,
                result="loss",
                pnl=-1.0,
            )
        )
        for _ in range(25)
    )

    gate = tracker.sample_gate(rows)

    assert gate["overall_status"] == "review_ready"
    assert gate["bucket_statuses"]["lean_market_with_us"]["status"] == "review_ready"
    assert gate["bucket_statuses"]["fire_market_against_us"]["status"] == "watch_only"


def test_build_report_includes_sample_gate_section():
    report = tracker.build_report([
        tracker.annotate_row(
            _movement_row(
                current_verdict="LEAN",
                result="win",
                pnl=0.91,
            )
        )
    ])

    assert "## Sample Gate" in report
    assert "Overall status: `watch_only`" in report
    assert "Minimum overall graded rows: `75`" in report
    assert "Minimum bucket graded rows: `50`" in report
