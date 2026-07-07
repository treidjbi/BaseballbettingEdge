from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


TRACKED_SEND_MODES = {"shadow", "send"}
LOCKED_GAME_STATES = {"locked", "in_progress", "final", "completed", "postponed"}


@dataclass(frozen=True)
class MainlineBestPriceResult:
    notification_rows: list[dict[str, Any]]
    shadow_rows: list[dict[str, Any]]
    summary: dict[str, Any]


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


def _numeric(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _matches_line(value: float, target: float) -> bool:
    return abs(value - target) < 0.001


def _format_odds(value: int) -> str:
    return f"{value:+d}"


def _row_key(row: dict[str, Any], slate_date: str) -> tuple[str, str, str, str] | None:
    row_slate = str(row.get("slate_date") or slate_date or "").strip()
    normalized = str(row.get("normalized_pitcher") or "").strip()
    side = str(row.get("side") or "").strip().lower()
    provider = str(row.get("provider") or "").strip().lower()
    if row_slate and normalized and side in {"over", "under"} and provider:
        return row_slate, normalized, side, provider
    return None


def _is_post_start(row: dict[str, Any], observed_at: datetime) -> bool:
    game_time = _parse_datetime(row.get("game_time"))
    return bool(game_time and observed_at >= game_time)


def _best_same_line_price(row: dict[str, Any]) -> dict[str, Any] | None:
    pick_line = _numeric(row.get("k_line"))
    book_rows = row.get("book_rows")
    if pick_line is None or not isinstance(book_rows, list):
        return None

    same_line: list[dict[str, Any]] = []
    for book_row in book_rows:
        if not isinstance(book_row, dict):
            continue
        line = _numeric(book_row.get("line"))
        odds = _integer(book_row.get("odds"))
        book = str(book_row.get("book") or "").strip().lower()
        if line is None or odds is None or not book:
            continue
        if _matches_line(line, pick_line):
            same_line.append({"book": book, "line": line, "odds": odds})

    if not same_line:
        return None
    return sorted(same_line, key=lambda item: (-int(item["odds"]), item["book"]))[0]


def _book_line_odds_map(row: dict[str, Any]) -> dict[tuple[str, float], int]:
    book_rows = row.get("book_rows")
    if not isinstance(book_rows, list):
        return {}

    mapping: dict[tuple[str, float], int] = {}
    for book_row in book_rows:
        if not isinstance(book_row, dict):
            continue
        book = str(book_row.get("book") or "").strip().lower()
        line = _numeric(book_row.get("line"))
        odds = _integer(book_row.get("odds"))
        if book and line is not None and odds is not None:
            mapping[(book, line)] = odds
    return mapping


def _has_off_line_price_change(previous: dict[str, Any] | None, current: dict[str, Any], pick_line: float) -> bool:
    if previous is None:
        return False

    previous_map = _book_line_odds_map(previous)
    current_map = _book_line_odds_map(current)

    keys = set(previous_map) | set(current_map)
    for key in keys:
        book, line = key
        if _matches_line(line, pick_line):
            continue
        if previous_map.get(key) != current_map.get(key):
            return True
    return False


def _body(
    *,
    pitcher: str,
    side: str,
    line: float,
    previous_odds: int,
    current_odds: int,
    current_book: str,
    better: bool,
) -> str:
    label = "better" if better else "worse"
    return (
        f"{pitcher} {side.upper()} {line:g} best price "
        f"{_format_odds(previous_odds)}->{_format_odds(current_odds)} at {current_book}; "
        f"same main line, price {label}"
    )


def build_mainline_best_price_notification_rows(
    *,
    slate_date: str,
    previous_rows: list[dict[str, Any]],
    current_rows: list[dict[str, Any]],
    observed_at: datetime | str,
    min_price_move_cents: int,
    mode: str,
) -> MainlineBestPriceResult:
    observed = _parse_datetime(observed_at) or datetime.now(timezone.utc)
    normalized_mode = str(mode or "off").strip().lower()
    summary: dict[str, Any] = {
        "mode": normalized_mode,
        "input_count": len(current_rows),
        "candidate_count": 0,
        "notification_count": 0,
        "first_seen_count": 0,
        "unchanged_count": 0,
        "below_threshold_count": 0,
        "off_line_ignored_count": 0,
        "suppressed_stale_count": 0,
        "suppressed_locked_count": 0,
        "suppressed_post_start_count": 0,
    }
    if normalized_mode not in TRACKED_SEND_MODES:
        return MainlineBestPriceResult([], [], summary)

    previous_by_key = {
        key: row
        for row in previous_rows
        if (key := _row_key(row, slate_date)) is not None
    }
    notification_rows: list[dict[str, Any]] = []
    shadow_rows: list[dict[str, Any]] = []

    for current in current_rows:
        key = _row_key(current, slate_date)
        if key is None:
            continue
        row_slate, normalized, side, provider = key
        if row_slate != slate_date:
            continue
        if not str(current.get("current_verdict") or "").startswith("FIRE"):
            continue
        if str(current.get("freshness_status") or "fresh") != "fresh":
            summary["suppressed_stale_count"] += 1
            continue
        if current.get("is_locked") or str(current.get("game_state") or "").strip().lower() in LOCKED_GAME_STATES:
            summary["suppressed_locked_count"] += 1
            continue
        if _is_post_start(current, observed):
            summary["suppressed_post_start_count"] += 1
            continue

        current_best = _best_same_line_price(current)
        if current_best is None:
            summary["off_line_ignored_count"] += 1
            continue

        previous = previous_by_key.get(key)
        previous_best = _best_same_line_price(previous) if previous else None
        if previous_best is None:
            summary["first_seen_count"] += 1
            shadow_rows.append({
                "candidate_action": "first_seen_shadow",
                "slate_date": slate_date,
                "normalized_pitcher": normalized,
                "side": side,
                "provider": provider,
                "current_best": current_best,
            })
            continue

        price_delta = int(current_best["odds"]) - int(previous_best["odds"])
        pick_line = _numeric(current.get("k_line"))
        if pick_line is not None and _has_off_line_price_change(previous, current, pick_line):
            summary["off_line_ignored_count"] += 1
            continue
        if price_delta == 0:
            summary["unchanged_count"] += 1
            continue
        if abs(price_delta) < max(1, int(min_price_move_cents)):
            summary["below_threshold_count"] += 1
            continue

        summary["candidate_count"] += 1
        better = price_delta > 0
        pitcher = str(current.get("pitcher") or normalized).strip()
        line = float(current_best["line"])
        shadow_rows.append({
            "candidate_action": "would_send" if normalized_mode == "send" else "would_send_shadow",
            "slate_date": slate_date,
            "pitcher": pitcher,
            "normalized_pitcher": normalized,
            "side": side,
            "provider": provider,
            "previous_best": previous_best,
            "current_best": current_best,
            "price_delta": price_delta,
            "observed_at": observed.isoformat(),
        })
        if normalized_mode != "send":
            continue

        dedupe_key = (
            f"{slate_date}:mainline_best_price:{provider}:{normalized}:{side}:"
            f"{line:g}:{previous_best['odds']}:{current_best['book']}:{current_best['odds']}"
        )
        notification_rows.append({
            "slate_date": slate_date,
            "event_type": "mainline_best_price_changed",
            "severity": "watch" if better else "action",
            "title": "Best Price Better Now" if better else "Best Price Worse Now",
            "body": _body(
                pitcher=pitcher,
                side=side,
                line=line,
                previous_odds=int(previous_best["odds"]),
                current_odds=int(current_best["odds"]),
                current_book=str(current_best["book"]),
                better=better,
            ),
            "url": "/",
            "dedupe_key": dedupe_key,
            "payload": {
                "pitcher": pitcher,
                "normalized_pitcher": normalized,
                "side": side,
                "provider": provider,
                "k_line": line,
                "previous_best_book": previous_best["book"],
                "previous_best_odds": previous_best["odds"],
                "current_best_book": current_best["book"],
                "current_best_odds": current_best["odds"],
                "price_delta": price_delta,
                "game_time": current.get("game_time"),
                "game_state": current.get("game_state"),
                "is_locked": current.get("is_locked"),
            },
            "occurred_at": observed.isoformat(),
        })

    summary["notification_count"] = len(notification_rows)
    return MainlineBestPriceResult(notification_rows, shadow_rows, summary)
