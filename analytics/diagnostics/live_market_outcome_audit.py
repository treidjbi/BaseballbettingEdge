"""Shadow audit joining live-market evidence to graded outcomes.

This diagnostic is analysis-only. It does not change live picks, locks,
thresholds, staking, provider order, notification sends, or calibration.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from pipeline.name_utils import normalize  # noqa: E402


HISTORY_PATH = ROOT / "data" / "picks_history.json"
DEFAULT_CHECKPOINTS_MINUTES = (120, 60, 30, 15, 5, 0)
MOVEMENT_NOISE_CENTS = 10


def _to_float(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _isoformat(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _normalized_pitcher(row: dict[str, Any]) -> str:
    return str(
        row.get("normalized_pitcher")
        or row.get("normalized_player_name")
        or normalize(row.get("pitcher") or row.get("player_name") or "")
    ).strip()


def _evidence_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("slate_date") or row.get("date") or "").strip(),
        _normalized_pitcher(row),
        str(row.get("side") or "").strip().lower(),
    )


def _is_fire(row: dict[str, Any]) -> bool:
    return bool(row.get("is_fire")) or str(row.get("current_verdict") or row.get("verdict") or "").startswith(
        "FIRE"
    )


def _line_market_direction(side: str, previous_line: float, current_line: float) -> str:
    if previous_line == current_line:
        return "neutral"
    if side == "over":
        return "toward_pick" if current_line > previous_line else "away_from_pick"
    return "toward_pick" if current_line < previous_line else "away_from_pick"


def _line_bet_value_direction(side: str, previous_line: float, current_line: float) -> str:
    if previous_line == current_line:
        return "neutral"
    if side == "over":
        return "better_now" if current_line < previous_line else "worse_now"
    return "better_now" if current_line > previous_line else "worse_now"


def _odds_market_direction(odds_delta: int) -> str:
    if abs(odds_delta) < MOVEMENT_NOISE_CENTS:
        return "neutral"
    return "away_from_pick" if odds_delta > 0 else "toward_pick"


def _odds_bet_value_direction(odds_delta: int) -> str:
    if abs(odds_delta) < MOVEMENT_NOISE_CENTS:
        return "neutral"
    return "better_now" if odds_delta > 0 else "worse_now"


def _direction_summary(
    *,
    side: str,
    first_line: float,
    current_line: float,
    first_odds: int,
    current_odds: int,
) -> tuple[str, str]:
    if first_line != current_line:
        return (
            _line_market_direction(side, first_line, current_line),
            _line_bet_value_direction(side, first_line, current_line),
        )

    odds_delta = current_odds - first_odds
    return _odds_market_direction(odds_delta), _odds_bet_value_direction(odds_delta)


def _consensus(
    *,
    positive_count: int,
    negative_count: int,
    positive_label: str,
    negative_label: str,
) -> str:
    if positive_count and negative_count:
        return "mixed"
    if positive_count:
        return positive_label
    if negative_count:
        return negative_label
    return "none"


def _market_reversal_count(side: str, ordered: list[dict[str, Any]]) -> int:
    directions: list[str] = []
    for previous, current in zip(ordered, ordered[1:]):
        market_direction, _ = _direction_summary(
            side=side,
            first_line=float(previous["line"]),
            current_line=float(current["line"]),
            first_odds=int(previous["american_odds"]),
            current_odds=int(current["american_odds"]),
        )
        if market_direction != "neutral":
            directions.append(market_direction)
    if len(directions) < 2:
        return 0
    return sum(
        1
        for previous_direction, current_direction in zip(directions, directions[1:])
        if previous_direction != current_direction
    )


def load_json_rows(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "data", "items", "result"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def join_evidence_to_results(
    evidence_rows: list[dict[str, Any]],
    history_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    results_by_key = {
        _evidence_key(row): row
        for row in history_rows
        if row.get("result") in {"win", "loss"}
    }
    joined: list[dict[str, Any]] = []
    for row in evidence_rows:
        result_row = results_by_key.get(_evidence_key(row), {})
        joined.append({
            **row,
            "result": result_row.get("result"),
            "pnl": result_row.get("pnl"),
            "actual_ks": result_row.get("actual_ks"),
        })
    return joined


def summarize_buckets(
    rows: list[dict[str, Any]],
    fields: tuple[str, ...],
) -> dict[tuple[Any, ...], dict[str, Any]]:
    buckets: dict[tuple[Any, ...], dict[str, Any]] = defaultdict(
        lambda: {
            "rows": 0,
            "fire_rows": 0,
            "graded": 0,
            "wins": 0,
            "losses": 0,
            "pnl": 0.0,
            "roi": None,
        }
    )
    for row in rows:
        key = tuple(row.get(field) or "unknown" for field in fields)
        bucket = buckets[key]
        bucket["rows"] += 1
        if _is_fire(row):
            bucket["fire_rows"] += 1

        result = row.get("result")
        if result not in {"win", "loss"}:
            continue
        bucket["graded"] += 1
        if result == "win":
            bucket["wins"] += 1
        else:
            bucket["losses"] += 1
        bucket["pnl"] += float(row.get("pnl") or 0.0)

    for bucket in buckets.values():
        bucket["pnl"] = round(bucket["pnl"], 2)
        bucket["roi"] = round(bucket["pnl"] / bucket["graded"], 4) if bucket["graded"] else None

    return dict(sorted(buckets.items()))


def _checkpoint_label(minutes: int) -> str:
    return "final_pre_start" if minutes == 0 else f"pre_{minutes}"


def _valid_snapshot(row: dict[str, Any], cutoff: datetime) -> dict[str, Any] | None:
    observed_at = _parse_datetime(row.get("observed_at"))
    line = _to_float(row.get("line"))
    odds = _to_int(row.get("american_odds"))
    if observed_at is None or line is None or odds is None or observed_at > cutoff:
        return None
    return {
        **row,
        "line": line,
        "american_odds": odds,
        "_observed_at_dt": observed_at,
    }


def _book_summary(
    *,
    side: str,
    book: str,
    snapshots: list[dict[str, Any]],
    cutoff: datetime,
) -> dict[str, Any] | None:
    valid = [
        snapshot
        for row in snapshots
        if (snapshot := _valid_snapshot(row, cutoff)) is not None
    ]
    if not valid:
        return None

    ordered = sorted(valid, key=lambda row: row["_observed_at_dt"])
    first = ordered[0]
    current = ordered[-1]
    market_direction, bet_value_direction = _direction_summary(
        side=side,
        first_line=float(first["line"]),
        current_line=float(current["line"]),
        first_odds=int(first["american_odds"]),
        current_odds=int(current["american_odds"]),
    )
    reversal_count = _market_reversal_count(side, ordered)
    return {
        "book": book,
        "snapshot_count": len(ordered),
        "first_observed_at": _isoformat(first["_observed_at_dt"]),
        "current_observed_at": _isoformat(current["_observed_at_dt"]),
        "first_line": first["line"],
        "current_line": current["line"],
        "line_delta": round(float(current["line"]) - float(first["line"]), 3),
        "first_odds": first["american_odds"],
        "current_odds": current["american_odds"],
        "odds_delta": int(current["american_odds"]) - int(first["american_odds"]),
        "market_direction": market_direction,
        "bet_value_direction": bet_value_direction,
        "reversal_count": reversal_count,
        "has_reversal": reversal_count > 0,
    }


def _group_snapshots(
    snapshot_rows: list[dict[str, Any]],
) -> dict[tuple[str, str, str], dict[str, list[dict[str, Any]]]]:
    grouped: dict[tuple[str, str, str], dict[str, list[dict[str, Any]]]] = {}
    for row in snapshot_rows:
        provider = str(row.get("provider") or "").strip().lower()
        normalized = _normalized_pitcher(row)
        side = str(row.get("side") or "").strip().lower()
        book = str(row.get("bookmaker_key") or row.get("bookmaker_title") or "").strip().lower()
        if not provider or not normalized or side not in {"over", "under"} or not book:
            continue
        grouped.setdefault((provider, normalized, side), {}).setdefault(book, []).append(row)
    return grouped


def build_checkpoint_evidence_rows(
    *,
    pick_rows: list[dict[str, Any]],
    snapshot_rows: list[dict[str, Any]],
    checkpoints_minutes: list[int] | tuple[int, ...] = DEFAULT_CHECKPOINTS_MINUTES,
) -> list[dict[str, Any]]:
    grouped_snapshots = _group_snapshots(snapshot_rows)
    rows: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str, str]] = set()

    for pick in pick_rows:
        slate_date = str(pick.get("slate_date") or pick.get("date") or "").strip()
        normalized = _normalized_pitcher(pick)
        side = str(pick.get("side") or "").strip().lower()
        game_time = _parse_datetime(pick.get("game_time"))
        if not slate_date or not normalized or side not in {"over", "under"} or game_time is None:
            continue

        pick_key = (slate_date, normalized, side, str(pick.get("provider") or ""))
        if pick_key in seen_keys:
            continue
        seen_keys.add(pick_key)

        providers = sorted(
            provider
            for provider, row_normalized, row_side in grouped_snapshots
            if row_normalized == normalized and row_side == side
        )
        for provider in providers:
            book_groups = grouped_snapshots.get((provider, normalized, side), {})
            for minutes in checkpoints_minutes:
                cutoff = game_time - timedelta(minutes=minutes)
                label = _checkpoint_label(int(minutes))
                book_summaries = {
                    book: summary
                    for book, snapshots in sorted(book_groups.items())
                    if (summary := _book_summary(
                        side=side,
                        book=book,
                        snapshots=snapshots,
                        cutoff=cutoff,
                    ))
                    is not None
                }
                if not book_summaries:
                    continue

                toward_pick_count = sum(
                    1 for summary in book_summaries.values() if summary["market_direction"] == "toward_pick"
                )
                away_from_pick_count = sum(
                    1 for summary in book_summaries.values() if summary["market_direction"] == "away_from_pick"
                )
                better_now_count = sum(
                    1 for summary in book_summaries.values() if summary["bet_value_direction"] == "better_now"
                )
                worse_now_count = sum(
                    1 for summary in book_summaries.values() if summary["bet_value_direction"] == "worse_now"
                )
                reversal_book_count = sum(
                    1 for summary in book_summaries.values() if summary["has_reversal"]
                )
                snapshot_count = sum(int(summary["snapshot_count"]) for summary in book_summaries.values())

                rows.append({
                    "slate_date": slate_date,
                    "pitcher": pick.get("pitcher"),
                    "normalized_pitcher": normalized,
                    "side": side,
                    "provider": provider,
                    "checkpoint": label,
                    "checkpoint_minutes": minutes,
                    "checkpoint_cutoff": _isoformat(cutoff),
                    "current_verdict": pick.get("current_verdict") or pick.get("verdict"),
                    "k_line": pick.get("k_line"),
                    "game_time": pick.get("game_time"),
                    "is_fire": _is_fire(pick),
                    "book_count": len(book_summaries),
                    "books_seen": sorted(book_summaries),
                    "snapshot_count": snapshot_count,
                    "toward_pick_count": toward_pick_count,
                    "away_from_pick_count": away_from_pick_count,
                    "better_now_count": better_now_count,
                    "worse_now_count": worse_now_count,
                    "reversal_book_count": reversal_book_count,
                    "volatile_book_count": reversal_book_count,
                    "market_consensus": _consensus(
                        positive_count=toward_pick_count,
                        negative_count=away_from_pick_count,
                        positive_label="toward_pick",
                        negative_label="away_from_pick",
                    ),
                    "bet_value_consensus": _consensus(
                        positive_count=better_now_count,
                        negative_count=worse_now_count,
                        positive_label="better_now",
                        negative_label="worse_now",
                    ),
                    "broad_confirmation": toward_pick_count >= 2,
                    "metadata": {"book_summaries": book_summaries},
                })

    return rows


def _rollup_rows(rows: list[dict[str, Any]], checkpoint: str) -> list[dict[str, Any]]:
    normalized_rows: list[dict[str, Any]] = []
    for row in rows:
        normalized_rows.append({
            **row,
            "normalized_pitcher": _normalized_pitcher(row),
            "checkpoint": row.get("time_window") or row.get("checkpoint") or checkpoint,
        })
    return normalized_rows


def _format_roi(value: float | None) -> str:
    return "--" if value is None else f"{value:+.1%}"


def _render_table(
    lines: list[str],
    *,
    summary: dict[tuple[Any, ...], dict[str, Any]],
    headers: tuple[str, ...],
    max_rows: int = 30,
) -> None:
    lines.append("| " + " | ".join(headers) + " | Rows | FIRE | Graded | W-L | PnL | ROI |")
    lines.append("| " + " | ".join(["---"] * len(headers)) + " | ---: | ---: | ---: | ---: | ---: | ---: |")
    if not summary:
        lines.append("| " + " | ".join(["--"] * len(headers)) + " | 0 | 0 | 0 | 0-0 | +0.00 | -- |")
        return

    sorted_rows = sorted(
        summary.items(),
        key=lambda item: (item[1]["graded"], item[1]["rows"]),
        reverse=True,
    )
    for key, bucket in sorted_rows[:max_rows]:
        key_values = [f"`{value}`" for value in key]
        lines.append(
            "| "
            + " | ".join(key_values)
            + f" | {bucket['rows']} | {bucket['fire_rows']} | {bucket['graded']} | "
            + f"{bucket['wins']}-{bucket['losses']} | {bucket['pnl']:+.2f} | "
            + f"{_format_roi(bucket['roi'])} |"
        )


def build_report(rows: list[dict[str, Any]], title: str = "Live Market Outcome Audit") -> str:
    consensus_summary = summarize_buckets(
        rows,
        ("provider", "checkpoint", "market_consensus", "bet_value_consensus"),
    )
    side_summary = summarize_buckets(
        rows,
        ("provider", "checkpoint", "side", "market_consensus"),
    )
    volatility_summary = summarize_buckets(
        [
            {
                **row,
                "volatility": "volatile_or_reversed"
                if int(row.get("volatile_book_count") or row.get("reversal_book_count") or 0) > 0
                else "clean_path",
            }
            for row in rows
        ],
        ("provider", "checkpoint", "volatility"),
    )
    graded = sum(1 for row in rows if row.get("result") in {"win", "loss"})
    fire_rows = sum(1 for row in rows if _is_fire(row))

    lines = [
        f"# {title}",
        "",
        "Shadow-only: this report does not change picks, locks, thresholds, staking, provider order, notifications, or calibration.",
        "",
        f"- Evidence rows: `{len(rows)}`",
        f"- FIRE rows: `{fire_rows}`",
        f"- Graded rows: `{graded}`",
        "",
        "## Consensus Outcome Buckets",
        "",
    ]
    _render_table(
        lines,
        summary=consensus_summary,
        headers=("Provider", "Checkpoint", "Market Consensus", "Bet Value Consensus"),
    )

    lines.extend(["", "## Side Buckets", ""])
    _render_table(
        lines,
        summary=side_summary,
        headers=("Provider", "Checkpoint", "Side", "Market Consensus"),
    )

    lines.extend(["", "## Volatility Buckets", ""])
    _render_table(
        lines,
        summary=volatility_summary,
        headers=("Provider", "Checkpoint", "Volatility"),
    )

    lines.extend([
        "",
        "## Read Rule",
        "",
        "- `market_consensus` asks whether live market movement went toward or away from our pick.",
        "- `bet_value_consensus` asks whether the available number got better or worse to bet now.",
        "- `checkpoint` can be a live rollup window or a rebuilt pregame checkpoint from raw snapshots.",
        "- Treat every bucket as evidence gathering until it survives more graded slates.",
    ])
    return "\n".join(lines)


def build_rows_from_inputs(
    *,
    market_pick_evidence_rows: list[dict[str, Any]],
    live_market_display_rows: list[dict[str, Any]],
    market_snapshot_rows: list[dict[str, Any]],
    history_rows: list[dict[str, Any]],
    checkpoints_minutes: list[int] | tuple[int, ...] = DEFAULT_CHECKPOINTS_MINUTES,
) -> list[dict[str, Any]]:
    evidence_rollups = _rollup_rows(market_pick_evidence_rows, "latest_evidence")
    display_rollups = _rollup_rows(live_market_display_rows, "latest_display")
    checkpoint_rows = []
    if market_snapshot_rows and (market_pick_evidence_rows or live_market_display_rows):
        checkpoint_rows = build_checkpoint_evidence_rows(
            pick_rows=market_pick_evidence_rows or live_market_display_rows,
            snapshot_rows=market_snapshot_rows,
            checkpoints_minutes=checkpoints_minutes,
        )
    return join_evidence_to_results(
        [*evidence_rollups, *display_rollups, *checkpoint_rows],
        history_rows,
    )


def _parse_checkpoints(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit live market evidence against graded outcomes."
    )
    parser.add_argument("--history", type=Path, default=HISTORY_PATH)
    parser.add_argument("--market-pick-evidence", type=Path)
    parser.add_argument("--live-market-display", type=Path)
    parser.add_argument("--market-snapshots", type=Path)
    parser.add_argument("--checkpoints", default="120,60,30,15,5,0")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    rows = build_rows_from_inputs(
        market_pick_evidence_rows=load_json_rows(args.market_pick_evidence),
        live_market_display_rows=load_json_rows(args.live_market_display),
        market_snapshot_rows=load_json_rows(args.market_snapshots),
        history_rows=load_json_rows(args.history),
        checkpoints_minutes=_parse_checkpoints(args.checkpoints),
    )
    print(build_report(rows))


if __name__ == "__main__":
    main()
