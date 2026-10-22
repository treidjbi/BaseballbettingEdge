"""Small last-good cache for FanGraphs-derived model inputs.

The cache stores normalized leaderboard lookups, not raw FanGraphs payloads.
It is intentionally plain JSON so Render can publish/hydrate it with the same
artifact mirror used by the dashboard data.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CACHE_PATH = ROOT_DIR / "data" / "fangraphs_cache.json"
DEFAULT_MAX_AGE_DAYS = 7


def _cache_path() -> Path:
    override = os.environ.get("FANGRAPHS_CACHE_PATH", "").strip()
    return Path(override) if override else DEFAULT_CACHE_PATH


def _max_age_days(value: int | None = None) -> int:
    if value is not None:
        return value
    raw = os.environ.get("FANGRAPHS_CACHE_MAX_AGE_DAYS", "").strip()
    if not raw:
        return DEFAULT_MAX_AGE_DAYS
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_MAX_AGE_DAYS
    return max(0, parsed)


def _empty_cache() -> dict[str, Any]:
    return {"version": 1, "entries": {}}


def _read_cache() -> dict[str, Any]:
    path = _cache_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return _empty_cache()
    if not isinstance(payload, dict) or payload.get("version") != 1:
        return _empty_cache()
    if not isinstance(payload.get("entries"), dict):
        return _empty_cache()
    return payload


def _write_cache(payload: dict[str, Any]) -> None:
    path = _cache_path()
    payload["updated_at"] = _format_timestamp(_utc_now())
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temp_path.replace(path)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def _is_fresh(cached_at: str, *, max_age_days: int) -> bool:
    timestamp = _parse_timestamp(cached_at)
    if timestamp is None:
        return False
    return _utc_now() - timestamp <= timedelta(days=max_age_days)


def get_cached_payload(key: str, *, max_age_days: int | None = None) -> Any | None:
    cache = _read_cache()
    entry = cache["entries"].get(key)
    if not isinstance(entry, dict):
        return None
    if not _is_fresh(str(entry.get("cached_at") or ""), max_age_days=_max_age_days(max_age_days)):
        return None
    return entry.get("payload")


def set_cached_payload(key: str, payload: Any, *, metadata: dict[str, Any] | None = None) -> None:
    cache = _read_cache()
    cache["entries"][key] = {
        "cached_at": _format_timestamp(_utc_now()),
        "payload": payload,
        "metadata": metadata or {},
    }
    try:
        _write_cache(cache)
    except OSError:
        return
