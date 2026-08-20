from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pipeline.name_utils import normalize


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _numeric(value: Any) -> float:
    return float(value)


def _integer(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def deduplicate_snapshot_rows(
    snapshot_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows_by_id: dict[str, dict[str, Any]] = {}
    for raw_row in snapshot_rows:
        row = dict(raw_row)
        snapshot_id = str(row.get("id") or "").strip()
        if not snapshot_id:
            raise ValueError("snapshot id is required for compaction")
        existing = rows_by_id.get(snapshot_id)
        if existing is None:
            rows_by_id[snapshot_id] = row
        elif existing != row:
            raise ValueError(f"conflicting duplicate snapshot id: {snapshot_id}")
    return list(rows_by_id.values())


def _snapshot_key(row: dict[str, Any]) -> tuple[str, str, str, str, str, str, str, float]:
    player_name = str(row.get("player_name") or "").strip()
    normalized_player = str(row.get("normalized_player_name") or "").strip() or normalize(player_name)
    return (
        str(row.get("slate_date") or "").strip(),
        str(row.get("provider") or "").strip().lower(),
        str(row.get("book_key") or row.get("bookmaker_key") or "").strip().lower(),
        normalized_player,
        str(row.get("market_key") or "pitcher_strikeouts").strip(),
        str(row.get("side") or "").strip().lower(),
        player_name,
        _numeric(row.get("line")),
    )


def _odds_move_count(ordered_rows: list[dict[str, Any]]) -> int:
    moves = 0
    previous_odds: int | None = None
    for row in ordered_rows:
        odds = _integer(row.get("american_odds", row.get("odds")))
        if previous_odds is not None and odds is not None and odds != previous_odds:
            moves += 1
        if odds is not None:
            previous_odds = odds
    return moves


def compact_snapshot_rows(snapshot_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    validated_rows = deduplicate_snapshot_rows(snapshot_rows)
    grouped: dict[tuple[str, str, str, str, str, str, str, float], list[dict[str, Any]]] = {}
    for row in validated_rows:
        if not row.get("observed_at"):
            continue
        side = str(row.get("side") or "").strip().lower()
        if side not in {"over", "under"}:
            continue
        grouped.setdefault(_snapshot_key(row), []).append(row)

    compact_rows: list[dict[str, Any]] = []
    for key, rows in grouped.items():
        (
            slate_date,
            provider,
            book_key,
            normalized_player,
            market_key,
            side,
            player_name,
            line,
        ) = key
        ordered = sorted(
            rows,
            key=lambda row: (
                _parse_datetime(row["observed_at"]),
                str(row["id"]),
            ),
        )
        odds_values = [
            odds
            for odds in (_integer(row.get("american_odds", row.get("odds"))) for row in ordered)
            if odds is not None
        ]
        first_row = ordered[0]
        last_row = ordered[-1]
        compact_rows.append({
            "slate_date": slate_date,
            "provider": provider,
            "book_key": book_key,
            "normalized_player_name": normalized_player,
            "player_name": player_name,
            "market_key": market_key,
            "side": side,
            "line": line,
            "first_seen_at": _parse_datetime(first_row["observed_at"]).isoformat(),
            "last_seen_at": _parse_datetime(last_row["observed_at"]).isoformat(),
            "first_odds": _integer(first_row.get("american_odds", first_row.get("odds"))),
            "last_odds": _integer(last_row.get("american_odds", last_row.get("odds"))),
            "min_odds": min(odds_values) if odds_values else None,
            "max_odds": max(odds_values) if odds_values else None,
            "odds_move_count": _odds_move_count(ordered),
            "snapshot_count": len(ordered),
            "source_snapshot_ids": [row.get("id") for row in ordered if row.get("id") is not None],
        })

    return sorted(
        compact_rows,
        key=lambda row: (
            row["slate_date"],
            row["provider"],
            row["book_key"],
            row["normalized_player_name"],
            row["side"],
            row["line"],
        ),
    )
