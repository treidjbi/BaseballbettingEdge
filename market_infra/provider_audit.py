from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from pipeline.name_utils import normalize

TARGET_BOOKS = {
    "draftkings": "DraftKings",
    "fanduel": "FanDuel",
    "betrivers": "BetRivers",
    "kalshi": "Kalshi",
}
BOOK_TITLE_TO_KEY = {title.lower(): key for key, title in TARGET_BOOKS.items()}
MAX_EXAMPLES = 25


def _book_key(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text in TARGET_BOOKS:
        return text
    return BOOK_TITLE_TO_KEY.get(text)


def _line(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _complete_provider_groups(snapshots: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, float, str], dict] = {}

    for snapshot in snapshots:
        book_key = _book_key(snapshot.get("bookmaker_key") or snapshot.get("bookmaker_title"))
        line = _line(snapshot.get("line"))
        player = str(snapshot.get("player_name") or "").strip()
        normalized = snapshot.get("normalized_player_name") or normalize(player)
        side = str(snapshot.get("side") or "").strip().lower()
        if not book_key or line is None or not normalized or side not in {"over", "under"}:
            continue

        key = (normalized, line, book_key)
        group = grouped.setdefault(
            key,
            {
                "normalized_player_name": normalized,
                "player_name": player,
                "line": line,
                "bookmaker_key": book_key,
                "sides": set(),
            },
        )
        group["sides"].add(side)

    return [
        {
            "normalized_player_name": group["normalized_player_name"],
            "player_name": group["player_name"],
            "line": group["line"],
            "bookmaker_key": group["bookmaker_key"],
        }
        for group in grouped.values()
        if {"over", "under"} <= group["sides"]
    ]


def _production_groups(production_payload: dict | None) -> dict[tuple[str, str], dict]:
    groups: dict[tuple[str, str], dict] = {}
    for record in (production_payload or {}).get("pitchers") or []:
        pitcher = str(record.get("pitcher") or "").strip()
        normalized = normalize(pitcher)
        line = _line(record.get("k_line"))
        if not normalized or line is None:
            continue

        for book_title in (record.get("book_odds") or {}):
            book_key = _book_key(book_title)
            if not book_key:
                continue
            groups[(normalized, book_key)] = {
                "pitcher": pitcher,
                "normalized_player_name": normalized,
                "bookmaker_key": book_key,
                "line": line,
            }
    return groups


def _production_pitcher_lines(production_payload: dict | None) -> set[tuple[str, float]]:
    pitcher_lines = set()
    for record in (production_payload or {}).get("pitchers") or []:
        pitcher = normalize(str(record.get("pitcher") or ""))
        line = _line(record.get("k_line"))
        if pitcher and line is not None:
            pitcher_lines.add((pitcher, line))
    return pitcher_lines


def build_provider_coverage_audit(
    snapshots: list[dict],
    production_payload: dict | None,
) -> dict:
    complete_groups = _complete_provider_groups(snapshots)
    production_groups = _production_groups(production_payload)
    production_pitcher_lines = _production_pitcher_lines(production_payload)

    target_book_group_counts = Counter(group["bookmaker_key"] for group in complete_groups)
    production_book_group_counts = Counter(group["bookmaker_key"] for group in production_groups.values())
    provider_pitcher_lines = {
        (group["normalized_player_name"], group["line"])
        for group in complete_groups
    }

    overlap_examples = []
    conflict_examples = []
    same_line_overlap_count = 0
    line_conflict_count = 0
    fillable_missing_book_counts = Counter({book: 0 for book in TARGET_BOOKS})
    fillable_missing_book_examples: dict[str, list[dict]] = defaultdict(list)

    for group in complete_groups:
        production_group = production_groups.get((group["normalized_player_name"], group["bookmaker_key"]))
        if production_group:
            if production_group["line"] == group["line"]:
                same_line_overlap_count += 1
                if len(overlap_examples) < MAX_EXAMPLES:
                    overlap_examples.append({
                        "bookmaker_key": group["bookmaker_key"],
                        "pitcher": production_group["pitcher"],
                        "line": group["line"],
                    })
            else:
                line_conflict_count += 1
                if len(conflict_examples) < MAX_EXAMPLES:
                    conflict_examples.append({
                        "bookmaker_key": group["bookmaker_key"],
                        "pitcher": production_group["pitcher"],
                        "production_line": production_group["line"],
                        "provider_line": group["line"],
                    })
            continue

        if (group["normalized_player_name"], group["line"]) in production_pitcher_lines:
            book_key = group["bookmaker_key"]
            fillable_missing_book_counts[book_key] += 1
            if len(fillable_missing_book_examples[book_key]) < MAX_EXAMPLES:
                fillable_missing_book_examples[book_key].append({
                    "pitcher": group["player_name"],
                    "line": group["line"],
                })

    missing_target_books = [
        book_key
        for book_key in TARGET_BOOKS
        if target_book_group_counts[book_key] == 0
    ]

    return {
        "target_books": list(TARGET_BOOKS),
        "missing_target_books": missing_target_books,
        "parsed_pitcher_prop_count": len(provider_pitcher_lines),
        "complete_pitcher_line_groups": len(complete_groups),
        "same_line_overlap_count": same_line_overlap_count,
        "line_conflict_count": line_conflict_count,
        "metadata": {
            "production_pitcher_count": len((production_payload or {}).get("pitchers") or []),
            "production_pitcher_line_count": len(production_pitcher_lines),
            "target_book_group_counts": {
                book_key: target_book_group_counts[book_key]
                for book_key in TARGET_BOOKS
            },
            "production_book_group_counts": {
                book_key: production_book_group_counts[book_key]
                for book_key in TARGET_BOOKS
            },
            "fillable_missing_book_counts": {
                book_key: fillable_missing_book_counts[book_key]
                for book_key in TARGET_BOOKS
            },
            "fillable_missing_book_examples": dict(fillable_missing_book_examples),
            "same_line_overlap_examples": overlap_examples,
            "line_conflict_examples": conflict_examples,
        },
    }
