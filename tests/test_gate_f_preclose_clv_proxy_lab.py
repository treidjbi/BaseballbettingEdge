from analytics.diagnostics import gate_f_preclose_clv_proxy_lab as lab


def _row(**overrides):
    row = {
        "slate_date": "2026-05-20",
        "is_tracked_pick": True,
        "result": "win",
        "side": "over",
        "display_verdict": "FIRE 1u",
        "raw_verdict": "FIRE 1u",
        "edge": 0.015,
        "adj_ev": 0.05,
        "model_no_vig_gap": 0.015,
        "model_market_relationship": "model_agrees_with_favorite",
        "quality_gate_level": "clean",
        "line_bucket": "5.5",
        "price_sign": "minus",
        "bet_timing_window": "pre_30",
        "side_price_movement": "with_side",
        "toward_pick_count": 3,
        "away_from_pick_count": 0,
        "better_now_count": 2,
        "worse_now_count": 0,
        "book_count": 4,
        "broad_confirmation": True,
        "best_is_off_market": False,
        "reversal_book_count": 0,
        "volatile_book_count": 0,
        "provider": "boltodds",
        "market_agreement_label": "market_agrees_with_model",
        "beat_close_price": True,
        "beat_close_line": False,
        "price_clv_cents": 8,
        "line_clv_delta": 0.0,
        "pick_history_pnl": 0.91,
    }
    row.update(overrides)
    return row


def test_proxy_score_does_not_use_post_close_clv_fields():
    base = _row(
        beat_close_price=False,
        beat_close_line=False,
        price_clv_cents=-12,
        line_clv_delta=-1.0,
    )
    positive_clv = {
        **base,
        "beat_close_price": True,
        "beat_close_line": True,
        "price_clv_cents": 24,
        "line_clv_delta": 1.0,
    }

    assert lab.preclose_clv_proxy_score(base) == lab.preclose_clv_proxy_score(positive_clv)
    assert lab.preclose_clv_proxy_label(base) == lab.preclose_clv_proxy_label(positive_clv)


def test_proxy_score_rewards_runtime_safe_positive_market_evidence():
    row = _row()

    scored = lab.preclose_clv_proxy_score(row)

    assert scored["score"] >= 6
    assert "movement_toward_pick" in scored["positive_reasons"]
    assert "low_edge_market_validation" in scored["positive_reasons"]
    assert "low_ev_market_validation" in scored["positive_reasons"]
    assert "thin_or_price_only_no_vig_gap" in scored["positive_reasons"]
    assert "multi_book_support" in scored["positive_reasons"]
    assert scored["label"] == "strong_preclose_clv_proxy"


def test_proxy_score_penalizes_runtime_safe_market_risk():
    row = _row(
        side="under",
        side_price_movement="against_side",
        model_market_relationship="model_fades_favorite",
        best_is_off_market=True,
        reversal_book_count=2,
        volatile_book_count=3,
        bet_timing_window="pre_5",
        model_no_vig_gap=0.005,
        edge=0.08,
        adj_ev=0.2,
        price_sign="plus",
        broad_confirmation=False,
        book_count=1,
    )

    scored = lab.preclose_clv_proxy_score(row)

    assert scored["score"] < 2
    assert "movement_against_pick" in scored["risk_reasons"]
    assert "off_market_best_book" in scored["risk_reasons"]
    assert "reversal_or_volatility" in scored["risk_reasons"]
    assert "under_market_fade" in scored["risk_reasons"]
    assert scored["label"] == "weak_preclose_clv_proxy"


def test_positive_clv_target_is_separate_from_proxy_score():
    assert lab.positive_clv_target(_row(beat_close_price=True, beat_close_line=False))
    assert lab.positive_clv_target(_row(beat_close_price=False, beat_close_line=True))
    assert not lab.positive_clv_target(
        _row(
            beat_close_price=False,
            beat_close_line=False,
            price_clv_cents=-4,
            line_clv_delta=0,
        )
    )


def test_build_summary_measures_proxy_capture_and_profit():
    rows = []
    for idx in range(80):
        rows.append(
            _row(
                result="win" if idx % 4 != 0 else "loss",
                pick_history_pnl=0.91 if idx % 4 != 0 else -1.0,
                beat_close_price=idx % 2 == 0,
                price_clv_cents=8 if idx % 2 == 0 else 0,
                line_clv_delta=0.0,
            )
        )
    for idx in range(40):
        rows.append(
            _row(
                side_price_movement="against_side",
                model_no_vig_gap=0.0,
                edge=0.08,
                adj_ev=0.2,
                price_sign="plus",
                broad_confirmation=False,
                book_count=1,
                result="loss" if idx % 2 == 0 else "win",
                pick_history_pnl=-1.0 if idx % 2 == 0 else 0.91,
                beat_close_price=False,
                price_clv_cents=0,
                line_clv_delta=0.0,
            )
        )

    summary = lab.build_summary(rows)
    strong = summary["proxy_buckets"]["strong_preclose_clv_proxy"]
    weak = summary["proxy_buckets"]["weak_preclose_clv_proxy"]

    assert strong["rows"] == 80
    assert strong["positive_clv_rows"] == 40
    assert strong["pnl"] > 0
    assert strong["candidate_readiness"] in {"watch_more", "ready_for_plan"}
    assert weak["rows"] == 40


def test_render_report_names_clv_target_and_runtime_proxy_boundary():
    summary = lab.build_summary([_row()])

    rendered = lab.render_report(summary)

    assert "# Gate F Pre-Close CLV Proxy Lab" in rendered
    assert "CLV is the validation target" in rendered
    assert "not a live selector" in rendered
    assert "Proxy Scoreboard" in rendered


def test_current_verdict_wrapper_keeps_display_precedence():
    assert lab.current_verdict(_row(display_verdict="LEAN", verdict="FIRE 1u")) == "LEAN"
