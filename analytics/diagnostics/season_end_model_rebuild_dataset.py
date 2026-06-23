"""Build a no-leakage season-end research dataset for next-season model work."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = ROOT / "data" / "research" / "gate_c" / "pitcher_k_outcome_dataset.jsonl"
DEFAULT_OUTPUT = ROOT / "analytics" / "output" / "season_end_model_rebuild_dataset.jsonl"
DEFAULT_SUMMARY = ROOT / "analytics" / "output" / "season_end_model_rebuild_dataset_summary.md"

HINDSIGHT_FIELDS = {
    "actual_ks",
    "result",
    "pnl",
    "theoretical_pnl",
    "pick_history_pnl",
    "closing_odds",
    "closing_line",
    "beat_close_price",
    "beat_close_line",
    "price_clv_cents",
    "line_clv_delta",
    "actual_ip",
    "actual_pitch_count",
    "batters_faced",
}

LINEUP_HANDEDNESS_FIELDS = {
    "lineup_count",
    "lineup_used",
    "lineup_right_batters",
    "lineup_left_batters",
    "lineup_switch_batters",
    "handedness_matchup_bucket",
    "lineup_handedness_count_matches_existing",
    "lineup_handedness_game_pk",
    "lineup_handedness_source",
}

ACTUAL_OPPORTUNITY_FIELDS = {
    "opportunity_bucket",
    "actual_ip",
    "actual_pitch_count",
    "batters_faced",
    "actual_opportunity_game_pk",
    "actual_opportunity_pitcher_match_type",
    "actual_opportunity_source",
}

RUNTIME_FIELDS = {
    "slate_date",
    "pitcher",
    "normalized_pitcher",
    "team",
    "opp_team",
    "side",
    "k_line",
    "american_odds",
    "bookmaker_key",
    "model_win_prob",
    "projected_ks",
    "edge",
    "ev",
    "adj_ev",
    "verdict",
    "raw_verdict",
    "quality_gate_level",
    "model_market_relationship",
    "no_vig_side_probability",
    "opportunity_bucket",
    "leash_risk_bucket",
    "pitcher_throws",
    "lineup_used",
    "lineup_right_batters",
    "lineup_left_batters",
    "lineup_switch_batters",
    "handedness_matchup_bucket",
}

RUNTIME_FIELD_GROUPS = {
    "slate_date": "timing",
    "pitcher": "identity",
    "normalized_pitcher": "identity",
    "team": "identity",
    "opp_team": "identity",
    "side": "market",
    "k_line": "market",
    "american_odds": "market",
    "bookmaker_key": "market",
    "model_win_prob": "model",
    "projected_ks": "model",
    "edge": "model",
    "ev": "model",
    "adj_ev": "model",
    "verdict": "model",
    "raw_verdict": "model",
    "quality_gate_level": "quality",
    "model_market_relationship": "market",
    "no_vig_side_probability": "market",
    "opportunity_bucket": "workload",
    "leash_risk_bucket": "workload",
    "pitcher_throws": "baseball",
    "lineup_used": "baseball",
    "lineup_right_batters": "baseball",
    "lineup_left_batters": "baseball",
    "lineup_switch_batters": "baseball",
    "handedness_matchup_bucket": "baseball",
}


def season_bucket(date_str: str) -> str:
    month = int(str(date_str)[5:7])
    day = int(str(date_str)[8:10])
    if month <= 4:
        return "early_season"
    if month == 5 or (month == 6 and day <= 15):
        return "spring_midseason"
    if month in {6, 7, 8}:
        return "summer_midseason"
    return "late_season"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def is_explicitly_unsafe(value: Any) -> bool:
    return value is False or str(value).strip().lower() == "false"


def source_available_pre_lock(source: dict[str, Any]) -> bool:
    runtime_flags = [
        value
        for key, value in source.items()
        if key.endswith("_runtime_safe") and value is not None
    ]
    return not any(is_explicitly_unsafe(value) for value in runtime_flags)


def is_runtime_field_safe(key: str, source: dict[str, Any]) -> bool:
    if key in LINEUP_HANDEDNESS_FIELDS and is_explicitly_unsafe(
        source.get("lineup_handedness_runtime_safe")
    ):
        return False
    if key in ACTUAL_OPPORTUNITY_FIELDS and is_explicitly_unsafe(
        source.get("actual_opportunity_runtime_safe")
    ):
        return False
    return True


def build_row(source: dict[str, Any]) -> dict[str, Any]:
    slate_date = source.get("slate_date") or source.get("date")
    runtime_features = {
        key: source.get(key)
        for key in RUNTIME_FIELDS
        if key in source and is_runtime_field_safe(key, source)
    }
    hindsight_labels = {key: source.get(key) for key in HINDSIGHT_FIELDS if key in source}
    if is_explicitly_unsafe(source.get("lineup_handedness_runtime_safe")):
        for key in LINEUP_HANDEDNESS_FIELDS:
            if key in source:
                hindsight_labels[key] = source.get(key)
    if is_explicitly_unsafe(source.get("actual_opportunity_runtime_safe")):
        for key in ACTUAL_OPPORTUNITY_FIELDS:
            if key in source:
                hindsight_labels[key] = source.get(key)

    available_pre_lock = source_available_pre_lock(source)
    return {
        "dataset_key": source.get("dataset_key") or "|".join(
            str(part or "")
            for part in [
                slate_date,
                source.get("normalized_pitcher") or source.get("pitcher"),
                source.get("side"),
                source.get("k_line"),
            ]
        ),
        "slate_date": slate_date,
        "season_bucket": season_bucket(slate_date),
        "available_pre_lock": available_pre_lock,
        "runtime_features": runtime_features,
        "hindsight_labels": hindsight_labels,
        "runtime_feature_group": {
            key: RUNTIME_FIELD_GROUPS.get(key, "unknown") for key in sorted(runtime_features)
        },
        "hindsight_explanation_only": {key: True for key in sorted(hindsight_labels)},
        "source_confidence": "official_artifact" if available_pre_lock else "reconstructed_postgame",
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    season_counts = Counter(row.get("season_bucket") for row in rows)
    hindsight_counts: Counter[str] = Counter()
    for row in rows:
        for key, value in row.get("hindsight_labels", {}).items():
            if value is not None:
                hindsight_counts[key] += 1
    return {
        "rows": len(rows),
        "available_pre_lock_rows": sum(1 for row in rows if row.get("available_pre_lock") is True),
        "season_buckets": dict(sorted(season_counts.items())),
        "hindsight_label_counts": dict(sorted(hindsight_counts.items())),
    }


def render_summary(summary: dict[str, Any]) -> str:
    lines = [
        "# Season-End Model Rebuild Dataset Summary",
        "",
        "Research-only. This output does not change live lambda, thresholds, staking, providers, notifications, locks, retention, calibration, or dashboard source-of-truth.",
        "",
        f"- Rows: `{summary['rows']}`",
        f"- Available pre-lock rows: `{summary['available_pre_lock_rows']}`",
        "",
        "## Season Buckets",
    ]
    for bucket, count in summary["season_buckets"].items():
        lines.append(f"- `{bucket}`: `{count}`")
    lines.extend(["", "## Hindsight Label Coverage"])
    for label, count in summary["hindsight_label_counts"].items():
        lines.append(f"- `{label}`: `{count}`")
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    args = parser.parse_args(argv)

    rows = [build_row(row) for row in load_jsonl(args.input)]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + ("\n" if rows else ""),
        encoding="utf-8",
    )
    args.summary.write_text(render_summary(summarize(rows)), encoding="utf-8")
    print(f"Wrote {args.output} ({len(rows)} rows)")
    print(f"Wrote {args.summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
