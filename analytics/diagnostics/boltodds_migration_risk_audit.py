"""Assess BoltOdds live-odds migration readiness from shadow evidence.

This diagnostic is read-only. Core functions accept already-fetched rows so
tests and local review do not require a Supabase connection.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_EXACT_BOOKS = ("fanduel",)
REQUIRED_ONE_OF_BOOKS = ("betmgm", "betrivers")
OPTIONAL_BOOKS = ("draftkings", "scorebet", "caesars")
REQUIRED_MARKET_ALIASES = {
    "pitcher_strikeouts",
    "player_strikeouts",
    "player strikeouts",
    "pitcher strikeouts",
}
DEFAULT_HEARTBEAT_MAX_AGE_MINUTES = 15
DEFAULT_ARTIFACT_MAX_AGE_MINUTES = 60


def _as_int(value: Any) -> int:
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    return [value]


def _normalize_key(value: Any) -> str:
    return str(value or "").strip().casefold().replace(" ", "_").replace("-", "_")


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
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


def _now(value: str | datetime | None) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    parsed = _parse_timestamp(value)
    return parsed or datetime.now(timezone.utc)


def _row_timestamp(row: dict[str, Any]) -> datetime:
    for key in ("observed_at", "last_message_at", "completed_at", "created_at", "updated_at"):
        parsed = _parse_timestamp(row.get(key))
        if parsed:
            return parsed
    return datetime.min.replace(tzinfo=timezone.utc)


def _provider_rows(rows: list[dict[str, Any]], provider: str) -> list[dict[str, Any]]:
    provider_key = provider.casefold()
    return [
        row
        for row in rows
        if str(row.get("provider") or "").casefold() == provider_key
    ]


def _latest_row(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not rows:
        return None
    return max(rows, key=_row_timestamp)


def _slate_date(row: dict[str, Any] | None) -> str | None:
    if not row:
        return None
    value = str(row.get("slate_date") or "").strip()
    return value or None


def _current_slate_date(metadata: dict[str, Any]) -> str | None:
    for key in ("current_slate_date", "today_json_slate_date", "slate_date"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return None


def _book_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    result: dict[str, int] = {}
    for row in rows:
        metadata = row.get("metadata") or {}
        counts = metadata.get("target_book_group_counts") if isinstance(metadata, dict) else None
        if isinstance(counts, dict):
            for book, count in counts.items():
                result[_normalize_key(book)] = max(
                    result.get(_normalize_key(book), 0),
                    _as_int(count),
                )
        for book in _as_list(row.get("books_seen")):
            key = _normalize_key(book)
            if key and key not in result:
                result[key] = 1
    return result


def _coverage_totals(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "complete_pitcher_line_groups": sum(
            _as_int(row.get("complete_pitcher_line_groups")) for row in rows
        ),
        "same_line_overlap_count": sum(
            _as_int(row.get("same_line_overlap_count")) for row in rows
        ),
        "line_conflict_count": sum(_as_int(row.get("line_conflict_count")) for row in rows),
    }


def _book_status(book: str, counts: dict[str, int], *, optional: bool = False) -> str:
    if counts.get(book, 0) > 0:
        return "present"
    return "missing_optional" if optional else "missing"


def _add_market_values(values: set[str], raw_values: Any) -> None:
    for value in _as_list(raw_values):
        normalized = _normalize_key(value)
        if normalized:
            values.add(normalized)


def _selected_market_values(rows: list[dict[str, Any] | None]) -> set[str]:
    values: set[str] = set()
    for row in rows:
        if not row:
            continue
        metadata = row.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}
        for key in ("selected_markets", "market_aliases", "markets"):
            _add_market_values(values, metadata.get(key))
        probe_summary = metadata.get("probe_summary")
        if isinstance(probe_summary, dict):
            _add_market_values(values, probe_summary.get("selected_markets"))
            _add_market_values(values, probe_summary.get("market_aliases"))
        _add_market_values(values, row.get("selected_markets"))
    return values


def _age_minutes(timestamp: datetime | None, now_utc: datetime) -> float | None:
    if timestamp is None:
        return None
    return max((now_utc - timestamp).total_seconds() / 60, 0.0)


def audit_migration_risk(
    *,
    provider_run_rows: list[dict[str, Any]],
    coverage_audit_rows: list[dict[str, Any]],
    heartbeat_rows: list[dict[str, Any]],
    artifact_metadata: dict[str, Any] | None = None,
    provider: str = "boltodds",
    now: str | datetime | None = None,
    heartbeat_max_age_minutes: int = DEFAULT_HEARTBEAT_MAX_AGE_MINUTES,
    artifact_max_age_minutes: int = DEFAULT_ARTIFACT_MAX_AGE_MINUTES,
) -> dict[str, Any]:
    """Return a readiness/risk summary for a BoltOdds migration trial."""
    now_utc = _now(now)
    provider_runs = _provider_rows(provider_run_rows, provider)
    all_coverage_rows = _provider_rows(coverage_audit_rows, provider)
    heartbeats = _provider_rows(heartbeat_rows, provider)
    latest_run = _latest_row(provider_runs)
    latest_heartbeat = _latest_row(heartbeats)
    latest_coverage = _latest_row(all_coverage_rows)

    risk_flags: list[str] = []
    blocking_reasons: list[str] = []
    follow_up_items: list[str] = []
    artifact_metadata = artifact_metadata or {}
    current_slate_date = _current_slate_date(artifact_metadata)
    if current_slate_date:
        current_slate_coverage_rows = [
            row for row in all_coverage_rows if _slate_date(row) == current_slate_date
        ]
        coverage_rows = current_slate_coverage_rows
    else:
        current_slate_coverage_rows = []
        coverage_rows = all_coverage_rows
    slate_alignment = {
        "current_slate_date": current_slate_date,
        "latest_provider_run_slate_date": _slate_date(latest_run),
        "latest_heartbeat_slate_date": _slate_date(latest_heartbeat),
        "latest_coverage_audit_slate_date": _slate_date(latest_coverage),
        "current_slate_coverage_rows": len(current_slate_coverage_rows),
    }

    if current_slate_date:
        latest_run_slate = slate_alignment["latest_provider_run_slate_date"]
        if latest_run and latest_run_slate != current_slate_date:
            risk_flags.append("stale_slate:latest_provider_run")
            blocking_reasons.append(
                f"BoltOdds latest provider run is for {latest_run_slate or 'unknown slate'}, "
                f"not current slate {current_slate_date}."
            )
        latest_heartbeat_slate = slate_alignment["latest_heartbeat_slate_date"]
        if latest_heartbeat and latest_heartbeat_slate != current_slate_date:
            risk_flags.append("stale_slate:latest_heartbeat")
            blocking_reasons.append(
                f"BoltOdds latest heartbeat is for {latest_heartbeat_slate or 'unknown slate'}, "
                f"not current slate {current_slate_date}."
            )
        if all_coverage_rows and not current_slate_coverage_rows:
            latest_coverage_slate = slate_alignment["latest_coverage_audit_slate_date"]
            risk_flags.append("stale_slate:coverage_audit")
            blocking_reasons.append(
                f"BoltOdds coverage audit has no rows for current slate {current_slate_date}; "
                f"latest row is for {latest_coverage_slate or 'unknown slate'}."
            )

    if not latest_run:
        risk_flags.append("no_provider_runs")
        blocking_reasons.append("No BoltOdds provider run evidence was supplied.")
    elif str(latest_run.get("status") or "").casefold() == "failed":
        risk_flags.append("latest_provider_run_failed")
        blocking_reasons.append("Latest BoltOdds provider run failed.")
    failed_runs = [
        row for row in provider_runs if str(row.get("status") or "").casefold() == "failed"
    ]
    if failed_runs and "latest_provider_run_failed" not in risk_flags:
        risk_flags.append("historical_provider_run_failures")
        follow_up_items.append("Review non-latest BoltOdds provider run failures before promotion.")

    heartbeat_age = _age_minutes(
        _parse_timestamp((latest_heartbeat or {}).get("last_message_at"))
        or _parse_timestamp((latest_heartbeat or {}).get("observed_at")),
        now_utc,
    )
    if not latest_heartbeat:
        risk_flags.append("no_heartbeat")
        blocking_reasons.append("No BoltOdds websocket heartbeat evidence was supplied.")
    elif heartbeat_age is None or heartbeat_age > heartbeat_max_age_minutes:
        risk_flags.append("stale_heartbeat")
        blocking_reasons.append("BoltOdds websocket heartbeat is stale.")

    if not all_coverage_rows:
        risk_flags.append("no_coverage_audit")
        blocking_reasons.append("No BoltOdds provider coverage audit evidence was supplied.")

    counts = _book_counts(coverage_rows)
    required_book_status = {
        book: _book_status(book, counts) for book in REQUIRED_EXACT_BOOKS
    }
    one_of_present = any(counts.get(book, 0) > 0 for book in REQUIRED_ONE_OF_BOOKS)
    required_book_status["betmgm_or_betrivers"] = (
        "present" if one_of_present else "missing"
    )
    optional_book_status = {
        book: _book_status(book, counts, optional=True) for book in OPTIONAL_BOOKS
    }

    for book, status in required_book_status.items():
        if status == "missing":
            risk_flags.append(f"missing_required_book:{book}")
            blocking_reasons.append(f"Required BoltOdds book coverage is missing: {book}.")
    for book, status in optional_book_status.items():
        if status == "missing_optional":
            risk_flags.append(f"{book}_missing_optional")
            follow_up_items.append(f"Optional book missing or thin: {book}.")

    selected_markets = _selected_market_values([*provider_runs, *heartbeats])
    has_required_market = bool(selected_markets & REQUIRED_MARKET_ALIASES)
    if not has_required_market:
        risk_flags.append("missing_selected_market:pitcher_strikeouts")
        blocking_reasons.append("BoltOdds selected markets do not include pitcher strikeouts.")

    coverage_totals = _coverage_totals(coverage_rows)
    same_line_overlap = coverage_totals["same_line_overlap_count"]
    line_conflicts = coverage_totals["line_conflict_count"]
    complete_groups = coverage_totals["complete_pitcher_line_groups"]
    if complete_groups > 0 and same_line_overlap <= 0:
        risk_flags.append("no_same_line_overlap")
        blocking_reasons.append("BoltOdds has no useful same-line overlap with production artifacts.")
    if line_conflicts > 0:
        risk_flags.append("line_conflicts_present")
        follow_up_items.append("Inspect BoltOdds line-conflict examples before trial promotion.")

    app_freshness = _artifact_freshness(
        artifact_metadata,
        now_utc=now_utc,
        max_age_minutes=artifact_max_age_minutes,
        risk_flags=risk_flags,
        follow_up_items=follow_up_items,
    )

    caution_flags = [
        flag
        for flag in risk_flags
        if flag
        in {
            "historical_provider_run_failures",
            "line_conflicts_present",
            "stale_today_artifact",
            "stale_notification_path",
            "missing_today_artifact_metadata",
            "missing_notification_metadata",
        }
    ]
    if blocking_reasons:
        status = "not_ready"
    elif caution_flags:
        status = "proceed_with_caution"
    else:
        status = "ready_for_trial"

    return {
        "provider": provider,
        "status": status,
        "risk_flags": risk_flags,
        "blocking_reasons": blocking_reasons,
        "follow_up_items": follow_up_items,
        "book_coverage": {
            "required_books": required_book_status,
            "optional_books": optional_book_status,
            "target_book_group_counts": dict(sorted(counts.items())),
        },
        "heartbeat": {
            "latest_observed_at": (latest_heartbeat or {}).get("observed_at"),
            "latest_message_at": (latest_heartbeat or {}).get("last_message_at"),
            "age_minutes": None if heartbeat_age is None else round(heartbeat_age, 2),
            "max_age_minutes": heartbeat_max_age_minutes,
        },
        "provider_runs": {
            "rows": len(provider_runs),
            "failed_rows": len(failed_runs),
            "latest_status": (latest_run or {}).get("status"),
        },
        "coverage": {
            "rows": len(coverage_rows),
            "complete_pitcher_line_groups": complete_groups,
            "same_line_overlap_count": same_line_overlap,
            "line_conflict_count": line_conflicts,
        },
        "selected_markets": sorted(selected_markets),
        "app_freshness": app_freshness,
        "slate_alignment": slate_alignment,
    }


def _artifact_freshness(
    metadata: dict[str, Any],
    *,
    now_utc: datetime,
    max_age_minutes: int,
    risk_flags: list[str],
    follow_up_items: list[str],
) -> dict[str, Any]:
    if not metadata:
        risk_flags.append("missing_today_artifact_metadata")
        risk_flags.append("missing_notification_metadata")
        follow_up_items.append("Confirm today.json and notification freshness during trial review.")
        return {
            "today_json_updated_at": None,
            "today_json_age_minutes": None,
            "notifications_last_sent_at": None,
            "notifications_age_minutes": None,
            "max_age_minutes": max_age_minutes,
        }

    today_age = _age_minutes(_parse_timestamp(metadata.get("today_json_updated_at")), now_utc)
    notification_age = _age_minutes(
        _parse_timestamp(metadata.get("notifications_last_sent_at")), now_utc
    )
    if today_age is None:
        risk_flags.append("missing_today_artifact_metadata")
        follow_up_items.append("Confirm today.json freshness during the BoltOdds trial.")
    elif today_age > max_age_minutes:
        risk_flags.append("stale_today_artifact")
        follow_up_items.append("Refresh or decouple today.json before live-odds promotion.")

    if notification_age is None:
        risk_flags.append("missing_notification_metadata")
        follow_up_items.append("Confirm notification/app freshness dependency before promotion.")
    elif notification_age > max_age_minutes:
        risk_flags.append("stale_notification_path")
        follow_up_items.append("Verify notification freshness before live-odds promotion.")

    return {
        "today_json_updated_at": metadata.get("today_json_updated_at"),
        "today_json_age_minutes": None if today_age is None else round(today_age, 2),
        "notifications_last_sent_at": metadata.get("notifications_last_sent_at"),
        "notifications_age_minutes": (
            None if notification_age is None else round(notification_age, 2)
        ),
        "max_age_minutes": max_age_minutes,
    }


def _load_json_rows(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "data", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [row for row in value if isinstance(row, dict)]
    return []


def _load_json_object(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Assess BoltOdds websocket migration readiness from JSON rows."
    )
    parser.add_argument("--provider-runs", type=Path, help="JSON provider run rows")
    parser.add_argument("--coverage-audits", type=Path, help="JSON coverage audit rows")
    parser.add_argument("--heartbeats", type=Path, help="JSON heartbeat rows")
    parser.add_argument("--artifact-metadata", type=Path, help="JSON artifact metadata")
    parser.add_argument("--provider", default="boltodds")
    parser.add_argument("--now", help="Override current timestamp for deterministic review")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    result = audit_migration_risk(
        provider_run_rows=_load_json_rows(args.provider_runs),
        coverage_audit_rows=_load_json_rows(args.coverage_audits),
        heartbeat_rows=_load_json_rows(args.heartbeats),
        artifact_metadata=_load_json_object(args.artifact_metadata),
        provider=args.provider,
        now=args.now,
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
