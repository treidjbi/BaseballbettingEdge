"""Fetch provider-arbitrated official market lines from Supabase."""
from __future__ import annotations

import json
import os
from typing import Any

from market_infra.supabase_writer import SupabaseMarketWriter
from name_utils import normalize


THERUNDOWN_PROPLINE_MARKET_SOURCE = "therundown_propline"
LEGACY_BOLTODDS_PROPLINE_MARKET_SOURCE = "boltodds_propline"
THERUNDOWN_PROPLINE_ODDS_SOURCE = "therundown+propline"
LEGACY_BOLTODDS_PROPLINE_ODDS_SOURCE = "boltodds+propline"
MARKET_KEY = "pitcher_strikeouts"
MIN_REASONABLE_PITCHER_K_LINE = 1.5
DEFAULT_MIN_PROPS = 12


class OfficialMarketSourceError(RuntimeError):
    """Raised when strict provider-market mode should block the pipeline."""


def official_market_source_mode() -> str:
    return os.environ.get("OFFICIAL_MARKET_SOURCE", "therundown").strip().lower() or "therundown"


def official_market_strict_mode() -> bool:
    return _truthy(os.environ.get("OFFICIAL_MARKET_STRICT", "false"))


def official_market_min_props() -> int:
    raw = os.environ.get("OFFICIAL_MARKET_MIN_PROPS", str(DEFAULT_MIN_PROPS)).strip()
    if not raw:
        return DEFAULT_MIN_PROPS
    try:
        parsed = int(raw)
    except ValueError:
        return DEFAULT_MIN_PROPS
    if parsed <= 0:
        return DEFAULT_MIN_PROPS
    return parsed


def official_market_enabled() -> bool:
    mode = official_market_source_mode()
    if mode == THERUNDOWN_PROPLINE_MARKET_SOURCE:
        return _truthy(os.environ.get("ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE", "false"))
    if mode == LEGACY_BOLTODDS_PROPLINE_MARKET_SOURCE:
        return (
            _truthy(os.environ.get("ALLOW_BOLTODDS_PROVIDER_REHEARSAL", "false"))
            and _truthy(os.environ.get("ENABLE_BOLTODDS_PIPELINE_SOURCE", "false"))
        )
    return False


def official_market_source_label() -> str:
    mode = official_market_source_mode()
    if mode == THERUNDOWN_PROPLINE_MARKET_SOURCE:
        return THERUNDOWN_PROPLINE_MARKET_SOURCE
    if mode == LEGACY_BOLTODDS_PROPLINE_MARKET_SOURCE:
        return LEGACY_BOLTODDS_PROPLINE_MARKET_SOURCE
    return mode


def official_odds_source_label() -> str:
    mode = official_market_source_mode()
    if mode == THERUNDOWN_PROPLINE_MARKET_SOURCE:
        return THERUNDOWN_PROPLINE_ODDS_SOURCE
    if mode == LEGACY_BOLTODDS_PROPLINE_MARKET_SOURCE:
        return LEGACY_BOLTODDS_PROPLINE_ODDS_SOURCE
    return mode


def official_market_writer_from_env() -> SupabaseMarketWriter:
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not supabase_url or not service_role_key:
        raise EnvironmentError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required")
    return SupabaseMarketWriter(supabase_url, service_role_key)


def fetch_official_market_odds(
    date_str: str,
    *,
    writer: SupabaseMarketWriter | None = None,
    min_props: int | None = None,
) -> list[dict[str, Any]]:
    """Return K-prop rows converted to the existing pipeline odds shape."""
    writer = writer or official_market_writer_from_env()
    official_rows = _fetch_official_rows(writer, date_str)
    if not official_rows:
        return []

    baseline_rows = _fetch_opening_baselines(writer, date_str)
    baselines = _baseline_index(baseline_rows)
    props = [
        prop
        for row in official_rows
        if (prop := official_row_to_prop(row, baselines)) is not None
    ]
    required = min_props if min_props is not None else official_market_min_props()
    if len(props) < required:
        return []
    return props


def official_row_to_prop(
    row: dict[str, Any],
    baselines: dict[tuple[str, str, str, str, str], dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if not row.get("ready_for_pipeline"):
        return None

    player_name = str(row.get("player_name") or "").strip()
    normalized_player = str(row.get("normalized_player_name") or normalize(player_name)).strip()
    ref_book_name = str(row.get("ref_book_name") or "").strip()
    ref_book_key = str(row.get("ref_book_key") or "").strip().lower()
    market_key = str(row.get("market_key") or MARKET_KEY).strip()
    ref_line = _float_or_none(row.get("ref_line"))
    over_odds = _int_or_none(row.get("ref_over_odds"))
    under_odds = _int_or_none(row.get("ref_under_odds"))
    game_time = str(row.get("game_time") or "").strip()

    if not player_name or not ref_book_name or not ref_book_key:
        return None
    if not game_time:
        return None
    if market_key != MARKET_KEY or ref_line is None or ref_line < MIN_REASONABLE_PITCHER_K_LINE:
        return None
    if over_odds is None or under_odds is None:
        return None

    book_odds = _normalize_book_odds(row.get("book_odds"))
    if ref_book_name not in book_odds:
        book_odds[ref_book_name] = {
            "line": ref_line,
            "over": over_odds,
            "under": under_odds,
            "provider": row.get("selected_provider"),
        }

    baseline = _matching_baseline(
        baselines or {},
        normalized_player=normalized_player,
        market_key=market_key,
        book_key=ref_book_key,
        book_name=ref_book_name,
        line=ref_line,
    )
    opening_over = _int_or_none(baseline.get("opening_over_odds") if baseline else None)
    opening_under = _int_or_none(baseline.get("opening_under_odds") if baseline else None)
    opening_source = str(baseline.get("opening_source") or "") if baseline else ""
    opening_odds_source = "preview" if opening_source == "preview" else "first_seen"
    opening_line = _float_or_none(baseline.get("line") if baseline else None)

    current_line_ids = _json_list(row.get("current_market_line_ids"))
    provider_coverage = _json_object(row.get("provider_coverage"))
    arbitration_reasons = _json_list(row.get("arbitration_reasons"))

    return {
        "pitcher": player_name,
        "team": "",
        "opp_team": "",
        "game_time": game_time,
        "k_line": ref_line,
        "opening_line": opening_line if opening_line is not None else ref_line,
        "ref_book": ref_book_name,
        "best_over_book": ref_book_name,
        "best_under_book": ref_book_name,
        "best_over_odds": over_odds,
        "best_under_odds": under_odds,
        "opening_over_odds": opening_over if opening_over is not None else over_odds,
        "opening_under_odds": opening_under if opening_under is not None else under_odds,
        "opening_odds_source": opening_odds_source,
        "book_odds": book_odds or None,
        "odds_source": official_odds_source_label(),
        "market_source_mode": official_market_source_label(),
        "line_source_provider": row.get("selected_provider"),
        "source_snapshot_ids": current_line_ids,
        "source_current_market_line_ids": current_line_ids,
        "official_market_line_id": row.get("id"),
        "provider_coverage": provider_coverage,
        "provider_arbitration_reasons": arbitration_reasons,
    }


def _fetch_official_rows(writer: SupabaseMarketWriter, date_str: str) -> list[dict[str, Any]]:
    return writer.select_rows(
        "official_market_lines",
        {
            "slate_date": f"eq.{date_str}",
            "market_key": f"eq.{MARKET_KEY}",
            "ready_for_pipeline": "eq.true",
            "order": "normalized_player_name.asc",
            "limit": "10000",
        },
    )


def _fetch_opening_baselines(writer: SupabaseMarketWriter, date_str: str) -> list[dict[str, Any]]:
    return writer.select_rows(
        "market_opening_baselines",
        {
            "slate_date": f"eq.{date_str}",
            "market_key": f"eq.{MARKET_KEY}",
            "order": "first_seen_at.asc",
            "limit": "10000",
        },
    )


def _baseline_index(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str, str, str], dict[str, Any]]:
    indexed: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for row in rows:
        normalized_player = str(row.get("normalized_player_name") or "").strip()
        market_key = str(row.get("market_key") or MARKET_KEY).strip()
        book_key = str(row.get("book_key") or "").strip().lower()
        book_name = str(row.get("book_name") or "").strip()
        line = _line_key(row.get("line"))
        if not normalized_player or not book_key or not book_name or not line:
            continue
        indexed.setdefault((normalized_player, market_key, book_key, book_name, line), row)
        indexed.setdefault((normalized_player, market_key, book_key, book_name, ""), row)
    return indexed


def _matching_baseline(
    baselines: dict[tuple[str, str, str, str, str], dict[str, Any]],
    *,
    normalized_player: str,
    market_key: str,
    book_key: str,
    book_name: str,
    line: float,
) -> dict[str, Any] | None:
    return (
        baselines.get((normalized_player, market_key, book_key, book_name, _line_key(line)))
        or baselines.get((normalized_player, market_key, book_key, book_name, ""))
    )


def _normalize_book_odds(value: Any) -> dict[str, dict[str, Any]]:
    raw = _json_object(value)
    book_odds: dict[str, dict[str, Any]] = {}
    for book_name, odds in raw.items():
        if not isinstance(odds, dict):
            continue
        over = _int_or_none(odds.get("over"))
        under = _int_or_none(odds.get("under"))
        if over is None or under is None:
            continue
        book_odds[str(book_name)] = {
            "line": _float_or_none(odds.get("line")),
            "over": over,
            "under": under,
            "provider": odds.get("provider"),
        }
    return book_odds


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return parsed
    return {}


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return parsed
    return []


def _line_key(value: Any) -> str:
    line = _float_or_none(value)
    if line is None:
        return ""
    return f"{line:.1f}"


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}
