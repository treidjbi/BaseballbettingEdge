from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping


PICK_CHANGE_EVENT_TYPES = {
    "new_fire_pick": "new_fire_pick_digest",
    "pick_upgraded": "pick_upgraded_digest",
    "pick_downgraded": "pick_downgraded_digest",
}


@dataclass(frozen=True)
class CoordinationResult:
    rows: list[dict[str, Any]]
    shadow_rows: list[dict[str, Any]]
    source_rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def floor_datetime_to_bucket(value: Any, *, minutes: int) -> str | None:
    parsed = _parse_datetime(value)
    if parsed is None or minutes <= 0:
        return None
    bucket_minute = (parsed.minute // minutes) * minutes
    bucket = parsed.replace(minute=bucket_minute, second=0, microsecond=0)
    return bucket.isoformat()


def _bucket_end_label(bucket: str, *, minutes: int) -> str:
    parsed = _parse_datetime(bucket)
    if parsed is None:
        return bucket
    return (parsed + timedelta(minutes=minutes)).strftime("%H:%M")


def _payload(row: Mapping[str, Any]) -> dict[str, Any]:
    payload = row.get("payload")
    return payload if isinstance(payload, dict) else {}


def _pitcher(row: Mapping[str, Any]) -> str:
    payload = _payload(row)
    return str(payload.get("pitcher") or row.get("pitcher") or "").strip()


def _verdict(row: Mapping[str, Any]) -> str:
    return str(_payload(row).get("verdict") or row.get("verdict") or "").strip()


def _dedupe_keys(rows: list[dict[str, Any]]) -> list[str]:
    return [str(row.get("dedupe_key") or "") for row in rows if str(row.get("dedupe_key") or "")]


def _count_verdicts(rows: list[dict[str, Any]]) -> tuple[int, int]:
    fire_count = 0
    lean_count = 0
    for row in rows:
        verdict = _verdict(row)
        if verdict.startswith("FIRE"):
            fire_count += 1
        elif verdict.startswith("LEAN"):
            lean_count += 1
    return fire_count, lean_count


def _source_context(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    context: list[dict[str, Any]] = []
    for row in rows:
        payload = _payload(row)
        context.append({
            "dedupe_key": row.get("dedupe_key"),
            "event_type": row.get("event_type"),
            "pitcher": _pitcher(row),
            "side": payload.get("side") or row.get("side"),
            "verdict": payload.get("verdict") or row.get("verdict"),
            "previous_verdict": payload.get("previous_verdict") or row.get("previous_verdict"),
            "k_line": payload.get("k_line") or row.get("k_line"),
            "game_time": payload.get("game_time") or row.get("game_time"),
        })
    return context


def _start_window_group_key(row: Mapping[str, Any]) -> tuple[str, str] | None:
    if row.get("event_type") != "game_reminder_due":
        return None
    payload = _payload(row)
    slate_date = str(row.get("slate_date") or payload.get("slate_date") or "").strip()
    bucket = floor_datetime_to_bucket(payload.get("game_time") or row.get("game_time"), minutes=30)
    if not slate_date or not bucket:
        return None
    return slate_date, bucket


def _pick_change_group_key(row: Mapping[str, Any], observed_at: str) -> tuple[str, str, str] | None:
    event_type = str(row.get("event_type") or "")
    if event_type not in PICK_CHANGE_EVENT_TYPES:
        return None
    payload = _payload(row)
    slate_date = str(row.get("slate_date") or payload.get("slate_date") or "").strip()
    bucket = floor_datetime_to_bucket(observed_at, minutes=10)
    if not slate_date or not bucket:
        return None
    return slate_date, event_type, bucket


def _start_window_digest(
    *,
    slate_date: str,
    bucket: str,
    rows: list[dict[str, Any]],
    occurred_at: str,
) -> dict[str, Any]:
    source_keys = _dedupe_keys(rows)
    pitchers = [_pitcher(row) for row in rows if _pitcher(row)]
    fire_count, lean_count = _count_verdicts(rows)
    count = len(rows)
    return {
        "slate_date": slate_date,
        "event_type": "start_window_digest",
        "severity": "action",
        "title": f"{count} tracked pitchers start by {_bucket_end_label(bucket, minutes=30)}",
        "body": f"{fire_count} FIRE, {lean_count} LEAN. Open app for final prices.",
        "url": "/",
        "dedupe_key": f"{slate_date}:start_window_digest:{bucket}",
        "payload": {
            "source_event_count": count,
            "source_dedupe_keys": source_keys,
            "pitchers": pitchers,
            "fire_count": fire_count,
            "lean_count": lean_count,
            "start_window_bucket": bucket,
            "source_events": _source_context(rows),
        },
        "occurred_at": occurred_at,
    }


def _pick_change_digest(
    *,
    slate_date: str,
    event_type: str,
    bucket: str,
    rows: list[dict[str, Any]],
    occurred_at: str,
) -> dict[str, Any]:
    digest_type = PICK_CHANGE_EVENT_TYPES[event_type]
    source_keys = _dedupe_keys(rows)
    pitchers = [_pitcher(row) for row in rows if _pitcher(row)]
    fire_count, lean_count = _count_verdicts(rows)
    titles = {
        "new_fire_pick_digest": f"{len(rows)} new FIRE picks",
        "pick_upgraded_digest": f"{len(rows)} picks upgraded",
        "pick_downgraded_digest": f"{len(rows)} picks downgraded",
    }
    return {
        "slate_date": slate_date,
        "event_type": digest_type,
        "severity": "action",
        "title": titles[digest_type],
        "body": f"{fire_count} FIRE, {lean_count} LEAN. Open app to review.",
        "url": "/",
        "dedupe_key": f"{slate_date}:{digest_type}:{bucket}",
        "payload": {
            "source_event_count": len(rows),
            "source_dedupe_keys": source_keys,
            "pitchers": pitchers,
            "fire_count": fire_count,
            "lean_count": lean_count,
            "observed_bucket": bucket,
            "source_events": _source_context(rows),
        },
        "occurred_at": occurred_at,
    }


def _group_rows(
    rows: list[dict[str, Any]],
    *,
    observed_at: str,
    group_start_windows: bool,
    group_pick_changes: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    groups: dict[tuple[Any, ...], list[tuple[int, dict[str, Any]]]] = {}
    group_kind: dict[tuple[Any, ...], str] = {}

    for index, row in enumerate(rows):
        key: tuple[Any, ...] | None = None
        if group_start_windows:
            start_key = _start_window_group_key(row)
            if start_key is not None:
                key = ("start_window", *start_key)
                group_kind[key] = "start_window"
        if key is None and group_pick_changes:
            pick_key = _pick_change_group_key(row, observed_at)
            if pick_key is not None:
                key = ("pick_change", *pick_key)
                group_kind[key] = "pick_change"
        if key is not None:
            groups.setdefault(key, []).append((index, row))

    digest_by_first_index: dict[int, dict[str, Any]] = {}
    skipped_indices: set[int] = set()
    suppressed_source_count = 0

    for key, indexed_rows in groups.items():
        source_rows = [row for _, row in indexed_rows]
        source_keys = _dedupe_keys(source_rows)
        if len(source_rows) < 2 or len(source_keys) != len(source_rows):
            continue

        first_index = indexed_rows[0][0]
        skipped_indices.update(index for index, _ in indexed_rows[1:])
        suppressed_source_count += len(source_rows) - 1
        kind = group_kind[key]
        if kind == "start_window":
            _, slate_date, bucket = key
            digest = _start_window_digest(
                slate_date=str(slate_date),
                bucket=str(bucket),
                rows=source_rows,
                occurred_at=observed_at,
            )
        else:
            _, slate_date, event_type, bucket = key
            digest = _pick_change_digest(
                slate_date=str(slate_date),
                event_type=str(event_type),
                bucket=str(bucket),
                rows=source_rows,
                occurred_at=observed_at,
            )
        digest_by_first_index[first_index] = digest

    output: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if index in digest_by_first_index:
            output.append(digest_by_first_index[index])
        elif index in skipped_indices:
            continue
        else:
            output.append(row)

    shadow_rows = [digest_by_first_index[index] for index in sorted(digest_by_first_index)]
    return output, shadow_rows, suppressed_source_count


def coordinate_notification_rows(
    rows: list[dict[str, Any]],
    *,
    mode: str,
    observed_at: datetime | str,
    group_start_windows: bool = False,
    group_pick_changes: bool = False,
) -> CoordinationResult:
    normalized_mode = str(mode or "off").strip().lower()
    if normalized_mode not in {"off", "shadow", "grouped"}:
        normalized_mode = "off"
    observed_at_iso = observed_at.isoformat() if isinstance(observed_at, datetime) else str(observed_at)

    if normalized_mode == "off":
        return CoordinationResult(
            rows=rows,
            shadow_rows=[],
            source_rows=rows,
            summary={
                "mode": "off",
                "input_count": len(rows),
                "output_count": len(rows),
                "grouped_count": 0,
                "suppressed_source_count": 0,
            },
        )

    grouped_rows, shadow_rows, suppressed_source_count = _group_rows(
        rows,
        observed_at=observed_at_iso,
        group_start_windows=group_start_windows,
        group_pick_changes=group_pick_changes,
    )
    output_rows = grouped_rows if normalized_mode == "grouped" else rows
    return CoordinationResult(
        rows=output_rows,
        shadow_rows=shadow_rows,
        source_rows=rows,
        summary={
            "mode": normalized_mode,
            "input_count": len(rows),
            "output_count": len(output_rows),
            "candidate_output_count": len(grouped_rows),
            "grouped_count": len(shadow_rows),
            "suppressed_source_count": suppressed_source_count,
            "group_start_windows": bool(group_start_windows),
            "group_pick_changes": bool(group_pick_changes),
        },
    )
