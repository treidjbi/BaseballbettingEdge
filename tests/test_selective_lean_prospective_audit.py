from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from analytics.diagnostics import selective_lean_prospective_audit as audit


def _row(
    *,
    slate_date: str = "2026-08-15",
    pitcher: str = "Pitcher One",
    side: str = "under",
    price_sign: str = "plus",
    result: str = "win",
    pnl: float = 0.9,
) -> dict:
    slug = f"{slate_date}-{pitcher}-{side}".lower().replace(" ", "-")
    return {
        "dataset_key": slug,
        "slate_date": slate_date,
        "normalized_pitcher": pitcher.lower(),
        "pitcher": pitcher,
        "is_tracked_pick": True,
        "result": result,
        "pick_history_pnl": pnl,
        "display_verdict": "LEAN",
        "line_bucket": "2.5-3.5",
        "k_line": 3.5,
        "model_market_relationship": "model_fades_favorite",
        "quality_gate_level": "capped",
        "side": side,
        "price_sign": price_sign,
        "price_bucket": "plus_100_to_124" if price_sign == "plus" else "minus_101_to_124",
        "bet_timing_window": "pre_30",
        "bet_time_at": f"{slate_date}T18:30:00+00:00",
        "operational_lock_id": f"lock-{slug}",
        "operational_lock_consumed_at": f"{slate_date}T18:32:00+00:00",
        "operational_lock_source_artifact_path": f"dated_slate:{slate_date}",
        "source_artifact_path": f"dated_slate:{slate_date}",
        "provider": "therundown_propline",
        "market_agreement_label": "market_with_model",
        "batter_handedness_mode": "path_b",
        "lineup_real_split_count": 7,
        "leash_risk_bucket": "normal",
        "preclose_clv_proxy_label": "strong_preclose_clv_proxy",
        "clv_type": "beat_close_price",
    }


def test_frozen_definition_and_fingerprint_are_exact() -> None:
    assert audit.CANDIDATE_DEFINITION == {
        "display_verdict": "LEAN",
        "line_bucket": "2.5-3.5",
        "model_market_relationship": "model_fades_favorite",
        "quality_gate_level": "capped",
    }
    assert audit.RULE_FINGERPRINT == (
        "4e00a180e35fe75dc8889d47065a25c4351cb37ac55664eb42f01b77c07fd13a"
    )


def test_selector_uses_display_verdict_precedence_and_exact_fields() -> None:
    row = _row()
    assert audit.selector_matches(row)

    row["display_verdict"] = "PASS"
    row["locked_verdict"] = "LEAN"
    assert not audit.selector_matches(row)

    row["display_verdict"] = None
    assert audit.selector_matches(row)

    row["quality_gate_level"] = "clean"
    assert not audit.selector_matches(row)


def test_prospective_candidate_fails_closed_without_consumed_lock_proof() -> None:
    row = _row()
    row.pop("operational_lock_consumed_at")
    row.pop("operational_lock_source_artifact_path")

    summary = audit.build_audit([row], generated_at="test", enforce_baseline=False)

    assert summary["status"] == "blocked_input_gap"
    assert summary["windows"]["prospective_eligible"]["rows"] == 0
    assert summary["windows"]["prospective_blocked"]["rows"] == 1
    gaps = next(iter(summary["integrity"]["input_gaps"].values()))
    assert "operational_lock_consumed_at|consumed_at|lock_consumed_at" in gaps
    assert "operational_lock_source_artifact_path|lock_source_artifact_path" in gaps


def test_freeze_gap_never_receives_prospective_credit() -> None:
    summary = audit.build_audit(
        [_row(slate_date="2026-08-14")],
        generated_at="test",
        enforce_baseline=False,
    )

    assert summary["status"] == "collecting"
    assert summary["windows"]["freeze_gap"]["rows"] == 1
    assert summary["windows"]["prospective_eligible"]["rows"] == 0


def test_duplicate_candidate_keys_are_blocked_and_not_credited() -> None:
    first = _row()
    second = dict(first)
    second["dataset_key"] = "different-source-key"

    summary = audit.build_audit(
        [first, second], generated_at="test", enforce_baseline=False
    )

    assert summary["status"] == "blocked_duplicate_keys"
    assert len(summary["integrity"]["duplicate_keys"]) == 1
    assert summary["windows"]["prospective_eligible"]["rows"] == 0
    assert summary["windows"]["prospective_blocked"]["rows"] == 2


def test_ready_for_review_requires_diverse_positive_prospective_sample() -> None:
    rows = []
    start = date(2026, 8, 15)
    for index in range(75):
        slate = (start + timedelta(days=index // 3)).isoformat()
        rows.append(
            _row(
                slate_date=slate,
                pitcher=f"Pitcher {index}",
                side="under" if index < 20 else "over",
                price_sign="plus" if index < 10 else "minus",
                pnl=0.5,
            )
        )

    summary = audit.build_audit(rows, generated_at="test", enforce_baseline=False)

    assert summary["status"] == "ready_for_review"
    assert summary["decision"] == "ready_for_separate_shadow_design"
    assert summary["counter"] == {"rows": 75, "floor": 75, "remaining": 0}
    assert all(summary["gates"].values())
    assert summary["diversity"]["under_rows"] == 20
    assert summary["diversity"]["plus_price_rows"] == 10
    assert set(summary["slices"]) >= {
        "side",
        "price_sign",
        "k_line",
        "quality",
        "timing",
        "model_market",
        "path_b",
        "workload",
        "preclose_clv_proxy",
        "final_clv",
        "provider",
        "market_agreement",
    }


def test_locked_historical_baselines_reconcile_without_prospective_credit() -> None:
    rows = []
    for index in range(47):
        rows.append(
            _row(
                slate_date="2026-05-01",
                pitcher=f"Historical Pitcher {index}",
                result="win" if index < 27 else "loss",
                pnl=8.416259 if index == 0 else 0.0,
            )
        )
    for index in range(56):
        rows.append(
            _row(
                slate_date="2026-06-24",
                pitcher=f"Current Pitcher {index}",
                result="win" if index < 28 else "loss",
                pnl=2.999676 if index == 0 else 0.0,
            )
        )

    summary = audit.build_audit(rows, generated_at="test")

    assert summary["reconciliation"]["matches"] is True
    assert summary["windows"]["historical_nomination"] == audit.LOCKED_HISTORICAL
    assert (
        summary["windows"]["historical_current_provider"]
        == audit.LOCKED_CURRENT_PROVIDER
    )
    assert summary["windows"]["prospective_eligible"]["rows"] == 0
    assert summary["status"] == "collecting"


def test_cli_writes_bounded_markdown_and_json(tmp_path: Path) -> None:
    input_path = tmp_path / "rows.jsonl"
    md_path = tmp_path / "audit.md"
    json_path = tmp_path / "audit.json"
    input_path.write_text(json.dumps(_row()) + "\n", encoding="utf-8")

    result = audit.main(
        [
            "--input",
            str(input_path),
            "--output-md",
            str(md_path),
            "--output-json",
            str(json_path),
            "--skip-baseline-reconciliation",
        ]
    )

    assert result == 0
    assert "Selective LEAN Prospective Audit" in md_path.read_text(encoding="utf-8")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["windows"]["prospective_eligible"]["rows"] == 1
