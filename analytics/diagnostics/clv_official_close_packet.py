"""Build an offline official-close evidence packet from bounded table exports.

The producer is deliberately disconnected from scheduled jobs and database
writes. It infers lock provenance only from an exact, recent pre-lock market
snapshot, then selects the latest same-provider/book/event observation after
the lock and before first pitch. Missing, ambiguous, stale, and retired-source
evidence fails closed into an exclusions file.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.name_utils import normalize  # noqa: E402


DEFAULT_ALLOWED_PROVIDERS = ("propline", "therundown")
DEFAULT_MAX_LOCK_PROVENANCE_AGE_MINUTES = 20
DEFAULT_MAX_CLOSE_AGE_MINUTES = 20


def _timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _iso(value: datetime) -> str:
    return value.isoformat()


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _same_number(left: Any, right: Any) -> bool:
    left_number = _number(left)
    right_number = _number(right)
    return (
        left_number is not None
        and right_number is not None
        and abs(left_number - right_number) < 1e-9
    )


def _normalized_name(row: dict[str, Any], *fields: str) -> str:
    for field in fields:
        value = str(row.get(field) or "").strip()
        if value:
            return normalize(value).strip()
    return ""


def _book_key(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").strip().lower())


def _snapshot_book(snapshot: dict[str, Any]) -> str:
    return _book_key(
        snapshot.get("bookmaker_key")
        or snapshot.get("bookmaker_title")
        or snapshot.get("bookmaker")
    )


def _same_game_time(lock: dict[str, Any], snapshot: dict[str, Any]) -> bool:
    lock_game = _timestamp(lock.get("game_time"))
    snapshot_game = _timestamp(snapshot.get("game_time"))
    return lock_game is not None and snapshot_game is not None and lock_game == snapshot_game


def _same_identity(lock: dict[str, Any], snapshot: dict[str, Any]) -> bool:
    lock_name = _normalized_name(lock, "normalized_pitcher", "pitcher")
    snapshot_name = _normalized_name(
        snapshot,
        "normalized_player_name",
        "player_name",
        "normalized_pitcher",
        "pitcher",
    )
    return (
        bool(lock_name)
        and lock_name == snapshot_name
        and str(lock.get("side") or "").strip().lower()
        == str(snapshot.get("side") or "").strip().lower()
        and _book_key(lock.get("locked_book")) == _snapshot_book(snapshot)
        and _same_game_time(lock, snapshot)
    )


def _exclusion(lock: dict[str, Any], reason: str, **details: Any) -> dict[str, Any]:
    return {
        "details": details,
        "lock_reference": str(lock.get("id") or lock.get("dedupe_key") or ""),
        "normalized_pitcher": _normalized_name(lock, "normalized_pitcher", "pitcher"),
        "pitcher": str(lock.get("pitcher") or "").strip(),
        "reason": reason,
        "side": str(lock.get("side") or "").strip().lower(),
        "slate_date": str(lock.get("slate_date") or "")[:10],
    }


def _fingerprint(rows: Iterable[dict[str, Any]]) -> str:
    payload = json.dumps(
        list(rows),
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _bounded_date(value: str, label: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be YYYY-MM-DD") from exc


def build_close_packet(
    lock_rows: list[dict[str, Any]],
    snapshot_rows: list[dict[str, Any]],
    *,
    official_rows: list[dict[str, Any]] | None = None,
    start_date: str,
    end_date: str,
    max_lock_provenance_age_minutes: int = DEFAULT_MAX_LOCK_PROVENANCE_AGE_MINUTES,
    max_close_age_minutes: int = DEFAULT_MAX_CLOSE_AGE_MINUTES,
    allowed_providers: Iterable[str] = DEFAULT_ALLOWED_PROVIDERS,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Return packet rows, explicit exclusions, and a read-only manifest."""

    start = _bounded_date(start_date, "start_date")
    end = _bounded_date(end_date, "end_date")
    if end < start:
        raise ValueError("end_date must be on or after start_date")
    if max_lock_provenance_age_minutes <= 0 or max_close_age_minutes <= 0:
        raise ValueError("freshness windows must be positive")

    allowed = {str(provider).strip().lower() for provider in allowed_providers if str(provider).strip()}
    official_input = [row for row in (official_rows or []) if isinstance(row, dict)]
    official_provider_by_key: dict[tuple[str, str, str], set[str]] = {}
    for row in official_input:
        provider = str(
            row.get("official_line_source_provider")
            or row.get("official_odds_source")
            or ""
        ).strip().lower()
        if provider not in allowed:
            continue
        key = (
            str(row.get("slate_date") or row.get("game_date") or row.get("date") or "")[:10],
            _normalized_name(row, "normalized_pitcher", "pitcher", "player_name"),
            str(row.get("side") or "").strip().lower(),
        )
        if all(key):
            official_provider_by_key.setdefault(key, set()).add(provider)
    bounded_locks = [
        row
        for row in lock_rows
        if isinstance(row, dict)
        and start.isoformat() <= str(row.get("slate_date") or "")[:10] <= end.isoformat()
    ]
    snapshots = [row for row in snapshot_rows if isinstance(row, dict)]
    packet_rows: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    official_provider_resolved_locks = 0

    for lock in sorted(
        bounded_locks,
        key=lambda row: (
            str(row.get("slate_date") or ""),
            _normalized_name(row, "normalized_pitcher", "pitcher"),
            str(row.get("side") or ""),
        ),
    ):
        locked_at = _timestamp(lock.get("locked_at") or lock.get("observed_at"))
        game_time = _timestamp(lock.get("game_time"))
        lock_line = _number(lock.get("locked_k_line"))
        lock_odds = _number(lock.get("locked_odds"))
        lock_name = _normalized_name(lock, "normalized_pitcher", "pitcher")
        side = str(lock.get("side") or "").strip().lower()
        lock_book = _book_key(lock.get("locked_book"))
        missing_fields = [
            label
            for label, present in (
                ("locked_at", locked_at is not None),
                ("game_time", game_time is not None),
                ("normalized_pitcher", bool(lock_name)),
                ("side", bool(side)),
                ("locked_book", bool(lock_book)),
                ("locked_k_line", lock_line is not None),
                ("locked_odds", lock_odds is not None),
            )
            if not present
        ]
        if missing_fields:
            exclusions.append(_exclusion(lock, "missing_lock_fields", fields=missing_fields))
            continue
        if locked_at >= game_time:
            exclusions.append(_exclusion(lock, "lock_not_before_game"))
            continue

        official_key = (str(lock.get("slate_date"))[:10], lock_name, side)
        official_providers = official_provider_by_key.get(official_key, set())
        if len(official_providers) > 1:
            exclusions.append(
                _exclusion(
                    lock,
                    "ambiguous_official_provider_attribution",
                    providers=sorted(official_providers),
                )
            )
            continue
        official_provider = next(iter(official_providers), None)
        if official_provider:
            official_provider_resolved_locks += 1

        earliest_provenance = locked_at - timedelta(minutes=max_lock_provenance_age_minutes)
        provenance = [
            snapshot
            for snapshot in snapshots
            if str(snapshot.get("provider") or "").strip().lower() in allowed
            and (
                official_provider is None
                or str(snapshot.get("provider") or "").strip().lower() == official_provider
            )
            and _same_identity(lock, snapshot)
            and (observed_at := _timestamp(snapshot.get("observed_at"))) is not None
            and earliest_provenance <= observed_at <= locked_at
            and _same_number(snapshot.get("line"), lock_line)
            and _same_number(snapshot.get("american_odds"), lock_odds)
        ]
        if not provenance:
            exclusions.append(
                _exclusion(
                    lock,
                    "missing_lock_provenance_snapshot",
                    max_age_minutes=max_lock_provenance_age_minutes,
                )
            )
            continue

        provider_events = {
            (
                str(snapshot.get("provider") or "").strip().lower(),
                str(snapshot.get("provider_event_id") or snapshot.get("event_id") or "").strip(),
            )
            for snapshot in provenance
        }
        if len(provider_events) != 1:
            exclusions.append(
                _exclusion(
                    lock,
                    "ambiguous_lock_provider_or_event",
                    candidates=sorted(f"{provider}:{event_id}" for provider, event_id in provider_events),
                )
            )
            continue
        provider, event_id = next(iter(provider_events))
        if not event_id:
            exclusions.append(_exclusion(lock, "missing_lock_event_id", provider=provider))
            continue

        close_candidates = [
            snapshot
            for snapshot in snapshots
            if str(snapshot.get("provider") or "").strip().lower() == provider
            and str(snapshot.get("provider_event_id") or snapshot.get("event_id") or "").strip() == event_id
            and _same_identity(lock, snapshot)
            and (observed_at := _timestamp(snapshot.get("observed_at"))) is not None
            and locked_at < observed_at < game_time
            and _number(snapshot.get("line")) is not None
            and _number(snapshot.get("american_odds")) is not None
        ]
        if not close_candidates:
            exclusions.append(_exclusion(lock, "missing_pregame_close_snapshot", provider=provider, event_id=event_id))
            continue

        latest_at = max(_timestamp(snapshot.get("observed_at")) for snapshot in close_candidates)
        latest = [
            snapshot
            for snapshot in close_candidates
            if _timestamp(snapshot.get("observed_at")) == latest_at
        ]
        close_signatures = {
            (_number(snapshot.get("line")), _number(snapshot.get("american_odds")))
            for snapshot in latest
        }
        if len(close_signatures) != 1:
            exclusions.append(
                _exclusion(
                    lock,
                    "ambiguous_close_snapshot",
                    provider=provider,
                    event_id=event_id,
                    observed_at=_iso(latest_at),
                )
            )
            continue
        close = min(latest, key=lambda snapshot: str(snapshot.get("id") or snapshot.get("dedupe_key") or ""))
        observation_id = str(close.get("id") or close.get("dedupe_key") or "").strip()
        if not observation_id:
            exclusions.append(
                _exclusion(
                    lock,
                    "missing_close_observation_id",
                    provider=provider,
                    event_id=event_id,
                    observed_at=_iso(latest_at),
                )
            )
            continue
        if game_time - latest_at > timedelta(minutes=max_close_age_minutes):
            exclusions.append(
                _exclusion(
                    lock,
                    "stale_close_snapshot",
                    age_minutes=round((game_time - latest_at).total_seconds() / 60, 3),
                    max_age_minutes=max_close_age_minutes,
                )
            )
            continue

        bookmaker = str(close.get("bookmaker_title") or lock.get("locked_book") or "").strip()
        bookmaker_key = str(close.get("bookmaker_key") or "").strip().lower()
        packet_rows.append(
            {
                "american_odds": int(_number(close.get("american_odds"))),
                "bookmaker": bookmaker,
                "bookmaker_key": bookmaker_key,
                "event_id": event_id,
                "freshness": "fresh",
                "game_time": _iso(game_time),
                "line": _number(close.get("line")),
                "lock_observed_at": _iso(locked_at),
                "normalized_pitcher": lock_name,
                "observation_id": observation_id,
                "observation_type": "official_close",
                "observed_at": _iso(latest_at),
                "official_lock_reference": str(lock.get("id") or lock.get("dedupe_key") or "").strip(),
                "pitcher": str(lock.get("pitcher") or close.get("player_name") or "").strip(),
                "provider": provider,
                "side": side,
                "slate_date": str(lock.get("slate_date"))[:10],
            }
        )

    exclusions.sort(key=lambda row: (row["slate_date"], row["normalized_pitcher"], row["side"], row["reason"]))
    reason_counts = Counter(row["reason"] for row in exclusions)
    manifest = {
        "allowed_providers": sorted(allowed),
        "bounded_lock_rows": len(bounded_locks),
        "database_writes": 0,
        "eligible_close_rows": len(packet_rows),
        "end_date": end.isoformat(),
        "excluded_lock_rows": len(exclusions),
        "exclusion_reason_counts": dict(sorted(reason_counts.items())),
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "input_lock_fingerprint": _fingerprint(lock_rows),
        "input_lock_rows": len(lock_rows),
        "input_official_fingerprint": _fingerprint(official_input),
        "input_official_rows": len(official_input),
        "input_snapshot_fingerprint": _fingerprint(snapshot_rows),
        "input_snapshot_rows": len(snapshot_rows),
        "max_close_age_minutes": max_close_age_minutes,
        "max_lock_provenance_age_minutes": max_lock_provenance_age_minutes,
        "mode": "offline_dry_run",
        "official_provider_resolved_locks": official_provider_resolved_locks,
        "packet_fingerprint": _fingerprint(packet_rows),
        "start_date": start.isoformat(),
    }
    return {"packet_rows": packet_rows, "exclusions": exclusions, "manifest": manifest}


def _load_rows(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix.lower() == ".json":
        payload = json.loads(text)
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict) and isinstance(payload.get("rows"), list):
            return [row for row in payload["rows"] if isinstance(row, dict)]
        if isinstance(payload, dict):
            return [payload]
        return []
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
    path.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a bounded, offline official-close packet from lock and snapshot exports."
    )
    parser.add_argument("--locks-input", type=Path, required=True)
    parser.add_argument("--snapshots-input", type=Path, required=True)
    parser.add_argument(
        "--gate-c-input",
        type=Path,
        help="Optional Gate C JSON/JSONL used only for official_line_source_provider attribution.",
    )
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--packet-output", type=Path, required=True)
    parser.add_argument("--exclusions-output", type=Path, required=True)
    parser.add_argument("--manifest-output", type=Path, required=True)
    parser.add_argument(
        "--max-lock-provenance-age-minutes",
        type=int,
        default=DEFAULT_MAX_LOCK_PROVENANCE_AGE_MINUTES,
    )
    parser.add_argument(
        "--max-close-age-minutes",
        type=int,
        default=DEFAULT_MAX_CLOSE_AGE_MINUTES,
    )
    parser.add_argument("--allowed-provider", action="append")
    args = parser.parse_args(argv)

    result = build_close_packet(
        _load_rows(args.locks_input),
        _load_rows(args.snapshots_input),
        official_rows=_load_rows(args.gate_c_input) if args.gate_c_input else None,
        start_date=args.start_date,
        end_date=args.end_date,
        max_lock_provenance_age_minutes=args.max_lock_provenance_age_minutes,
        max_close_age_minutes=args.max_close_age_minutes,
        allowed_providers=args.allowed_provider or DEFAULT_ALLOWED_PROVIDERS,
    )
    _write_jsonl(args.packet_output, result["packet_rows"])
    _write_jsonl(args.exclusions_output, result["exclusions"])
    args.manifest_output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_output.write_text(
        json.dumps(result["manifest"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
