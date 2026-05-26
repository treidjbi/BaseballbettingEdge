"""Audit Path B batter-handedness readiness.

This diagnostic is shadow-only. It reports whether real batter handedness split
coverage is ready for deeper research. It must not change live lambda, verdicts,
thresholds, staking, provider order, notifications, or calibration.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "analytics" / "output" / "pitcher_k_outcome_dataset.jsonl"
CACHE_PATH = ROOT / "data" / "batter_splits_2026.json"
PARAMS_PATH = ROOT / "data" / "params.json"
OUTPUT_PATH = ROOT / "analytics" / "output" / "batter_handedness_shadow_audit.md"


def load_jsonl(path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _is_true(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def _to_int(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _has_value(value: Any) -> bool:
    return value is not None and value != ""


def _has_lineup_hand_counts(row: dict[str, Any]) -> bool:
    return all(
        _has_value(row.get(field))
        for field in (
            "lineup_right_batters",
            "lineup_left_batters",
            "lineup_switch_batters",
        )
    )


def _split_pa(split: Any) -> int:
    if not isinstance(split, dict):
        return 0
    return _to_int(split.get("pa")) or 0


def _cache_summary(cache: dict[str, Any], *, min_split_pa: int = 30) -> dict[str, Any]:
    batters = cache.get("batters")
    if not isinstance(batters, dict):
        batters = {}

    both_splits = 0
    both_splits_min_pa = 0
    one_split_only = 0
    no_split = 0
    handedness_counts: Counter[str] = Counter()

    for batter in batters.values():
        if not isinstance(batter, dict):
            continue
        if batter.get("bats"):
            handedness_counts[str(batter.get("bats"))] += 1
        has_vs_r = isinstance(batter.get("vs_R"), dict)
        has_vs_l = isinstance(batter.get("vs_L"), dict)
        if has_vs_r and has_vs_l:
            both_splits += 1
            if _split_pa(batter.get("vs_R")) >= min_split_pa and _split_pa(batter.get("vs_L")) >= min_split_pa:
                both_splits_min_pa += 1
        elif has_vs_r or has_vs_l:
            one_split_only += 1
        else:
            no_split += 1

    return {
        "cache_batters": len(batters),
        "cache_batters_with_both_splits": both_splits,
        "cache_batters_with_both_splits_min_pa": both_splits_min_pa,
        "cache_batters_with_one_split_only": one_split_only,
        "cache_batters_without_splits": no_split,
        "cache_batter_hands": dict(handedness_counts),
    }


def summarize_path_b_readiness(
    rows: list[dict[str, Any]],
    cache: dict[str, Any],
    *,
    params: dict[str, Any] | None = None,
    current_date: str | None = None,
    min_split_pa: int = 30,
) -> dict[str, Any]:
    params = params or {}
    current_date = current_date or datetime.now(UTC).strftime("%Y-%m-%d")
    sample_size = _to_int(params.get("sample_size"))
    date_or_sample_trigger_met = bool(
        (sample_size is not None and sample_size >= 400) or current_date >= "2026-05-25"
    )

    official_rows = [
        row
        for row in rows
        if row.get("context_snapshot") in {None, "", "official_close"}
    ]
    tracked_rows = [row for row in official_rows if _is_true(row.get("is_tracked_pick"))]
    clean_rows = official_rows or rows
    slate_count = len({str(row.get("slate_date") or "") for row in clean_rows if row.get("slate_date")})
    hand_count_slates = len(
        {
            str(row.get("slate_date") or "")
            for row in clean_rows
            if row.get("slate_date") and _has_lineup_hand_counts(row)
        }
    )

    summary = {
        "total_rows": len(clean_rows),
        "tracked_rows": len(tracked_rows),
        "slate_count": slate_count,
        "slates_with_lineup_hand_counts": hand_count_slates,
        "params_sample_size": sample_size,
        "current_date": current_date,
        "date_or_sample_trigger_met": date_or_sample_trigger_met,
        "pitcher_throws_rows": sum(1 for row in clean_rows if _has_value(row.get("pitcher_throws"))),
        "lineup_count_rows": sum(1 for row in clean_rows if (_to_int(row.get("lineup_count")) or 0) > 0),
        "lineup_hand_count_rows": sum(1 for row in clean_rows if _has_lineup_hand_counts(row)),
        "handedness_bucket_rows": sum(1 for row in clean_rows if _has_value(row.get("handedness_matchup_bucket"))),
    }
    summary.update(_cache_summary(cache, min_split_pa=min_split_pa))

    last_run = cache.get("last_run") if isinstance(cache.get("last_run"), dict) else {}
    summary["last_collection_requested_batters"] = _to_int(last_run.get("requested_batters"))
    summary["last_collection_already_cached"] = _to_int(last_run.get("already_cached"))
    summary["last_collection_attempted"] = _to_int(last_run.get("attempted"))
    summary["last_collection_collected"] = _to_int(last_run.get("collected"))
    summary["last_collection_failed"] = _to_int(last_run.get("failed"))
    summary["last_collection_queued_not_attempted"] = _to_int(last_run.get("queued_not_attempted"))

    blockers: list[str] = []
    if not date_or_sample_trigger_met:
        blockers.append("date/sample trigger has not been met")
    if summary["lineup_hand_count_rows"] == 0:
        blockers.append("lineup hand counts are not populated")
    if summary["handedness_bucket_rows"] == 0:
        blockers.append("handedness matchup buckets are not populated")
    if summary["cache_batters_with_both_splits"] == 0:
        blockers.append("split cache has no batters with both vs_R and vs_L samples")

    shadow_ready = (
        date_or_sample_trigger_met
        and summary["lineup_hand_count_rows"] > 0
        and summary["cache_batters_with_both_splits"] > 0
    )
    if shadow_ready:
        blockers.append("holdout lift versus Path A has not been proven")

    summary["path_b_shadow_audit_ready"] = shadow_ready
    summary["path_b_live_lambda_ready"] = False
    summary["blockers"] = blockers
    return summary


def _pct(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "--"
    return f"{(numerator / denominator):.1%}"


def _fmt(value: Any) -> str:
    return "none" if value is None else str(value)


def build_report(
    rows: list[dict[str, Any]],
    cache: dict[str, Any],
    *,
    params: dict[str, Any] | None = None,
    current_date: str | None = None,
) -> str:
    summary = summarize_path_b_readiness(
        rows,
        cache,
        params=params,
        current_date=current_date,
    )

    lines = [
        "# Batter Handedness Path B Shadow Audit",
        "",
        "Shadow-only: this report does not change live lambda, verdicts, thresholds, staking, provider order, notifications, or calibration.",
        "",
        f"- Generated at: `{datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ')}`",
        f"- Current date checked: `{summary['current_date']}`",
        f"- Params sample size: `{_fmt(summary['params_sample_size'])}`",
        "",
        "## Status",
        "",
        "- Path A is already live: pitcher handedness plus aggregate batter K% with conservative league-average platoon deltas.",
        "- Path B is the candidate: real per-batter vs-RHP/vs-LHP split samples with regression toward league averages.",
        f"- Date/sample trigger met: `{'yes' if summary['date_or_sample_trigger_met'] else 'no'}`",
        f"- Path B shadow audit status: `{'ready for deeper audit' if summary['path_b_shadow_audit_ready'] else 'not ready'}`",
        "- Path B live lambda status: `not ready`",
        "",
        "## Compact Row Coverage",
        "",
        f"- Official/compact rows checked: `{summary['total_rows']}`",
        f"- Tracked rows checked: `{summary['tracked_rows']}`",
        f"- Slates checked: `{summary['slate_count']}`",
        f"- Slates with lineup hand counts: `{summary['slates_with_lineup_hand_counts']}`",
        f"- Pitcher hand coverage: `{summary['pitcher_throws_rows']}/{summary['total_rows']}` ({_pct(summary['pitcher_throws_rows'], summary['total_rows'])})",
        f"- Lineup count coverage: `{summary['lineup_count_rows']}/{summary['total_rows']}` ({_pct(summary['lineup_count_rows'], summary['total_rows'])})",
        f"- R/L/S lineup hand-count coverage: `{summary['lineup_hand_count_rows']}/{summary['total_rows']}` ({_pct(summary['lineup_hand_count_rows'], summary['total_rows'])})",
        f"- Handedness matchup bucket coverage: `{summary['handedness_bucket_rows']}/{summary['total_rows']}` ({_pct(summary['handedness_bucket_rows'], summary['total_rows'])})",
        "",
        "## Split Cache",
        "",
        f"- Cached batters: `{summary['cache_batters']}`",
        f"- Batters with both split samples: `{summary['cache_batters_with_both_splits']}`",
        f"- Batters with both split samples and >=30 PA each side: `{summary['cache_batters_with_both_splits_min_pa']}`",
        f"- Batters with one split only: `{summary['cache_batters_with_one_split_only']}`",
        f"- Last collection requested batters: `{_fmt(summary['last_collection_requested_batters'])}`",
        f"- Last collection already cached: `{_fmt(summary['last_collection_already_cached'])}`",
        f"- Last collection attempted: `{_fmt(summary['last_collection_attempted'])}`",
        f"- Last collection collected: `{_fmt(summary['last_collection_collected'])}`",
        f"- Last collection failed: `{_fmt(summary['last_collection_failed'])}`",
        f"- Last collection queued not attempted: `{_fmt(summary['last_collection_queued_not_attempted'])}`",
        "",
        "## Blockers",
        "",
    ]

    if summary["blockers"]:
        lines.extend(f"- {blocker}" for blocker in summary["blockers"])
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Decision",
            "",
            "- Promote now: active shadow collection/audit for Path B coverage and simulated lift.",
            "- Do not promote now: live projection math, thresholds, staking, verdicts, or calibration.",
            "- Next useful implementation: populate compact row R/L/S lineup counts and matchup buckets, then run a holdout comparison of Path B versus Path A.",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit Path B batter handedness readiness.")
    parser.add_argument("--dataset", default=str(DATASET_PATH))
    parser.add_argument("--cache", default=str(CACHE_PATH))
    parser.add_argument("--params", default=str(PARAMS_PATH))
    parser.add_argument("--output", default=str(OUTPUT_PATH))
    parser.add_argument("--current-date")
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    report = build_report(
        load_jsonl(Path(args.dataset)),
        load_json(Path(args.cache)),
        params=load_json(Path(args.params)),
        current_date=args.current_date,
    )
    if not args.no_write:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report + "\n", encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
