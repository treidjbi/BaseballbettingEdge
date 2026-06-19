"""Choose official provider-market lines from current supported-book lines."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


REF_BOOK_PRIORITY = ("fanduel", "draftkings", "betmgm", "betrivers", "caesars")
DEFAULT_PROVIDER_PRIORITY = ("therundown", "propline", "the_odds", "boltodds")
DRAFTKINGS_PROVIDER_PRIORITY = ("therundown", "propline", "the_odds", "boltodds")
THE_ODDS_EMERGENCY_BOOKS = {"fanduel", "draftkings"}
WEBSOCKET_HOLD_PROVIDERS = {"boltodds"}
UNKNOWN_FRESHNESS_SECONDS = 1_000_000_000


def choose_official_lines(
    current_lines: list[dict[str, Any]],
    now_utc: datetime,
    stale_after_seconds: int = 900,
    allow_the_odds_emergency: bool = False,
    boltodds_draftkings_enabled: bool = False,
    provider_heartbeats: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return official market-line rows and per-player arbitration decisions."""
    observed_now = _ensure_utc(now_utc)
    provider_health = _provider_heartbeat_health(
        provider_heartbeats or [],
        observed_now,
        stale_after_seconds,
    )
    observed_rows = [
        _with_observed_freshness(
            row,
            observed_now,
            provider_health=provider_health,
            stale_after_seconds=stale_after_seconds,
        )
        for row in current_lines
    ]
    grouped = _group_by_player(observed_rows)
    mainline_rows, mainline_metadata = select_mainline_current_lines(
        observed_rows,
        observed_now,
        stale_after_seconds=stale_after_seconds,
        allow_the_odds_emergency=allow_the_odds_emergency,
        provider_health=provider_health,
    )
    mainline_grouped = _group_by_player(mainline_rows)
    official_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []

    for player_key in sorted(grouped):
        rows = grouped[player_key]
        slate_date, normalized_player_name, market_key = player_key
        player_name = _display_player_name(rows)
        supported_rows = [row for row in rows if _book_key(row) in REF_BOOK_PRIORITY]
        fresh_complete_rows = [
            row for row in mainline_grouped.get(player_key, [])
            if _is_usable_current_line(row, stale_after_seconds, allow_the_odds_emergency)
        ]
        stale_count = sum(
            1
            for row in supported_rows
            if _is_complete(row) and not _is_effectively_fresh(row, stale_after_seconds)
        )
        missing_books = [
            book_key for book_key in REF_BOOK_PRIORITY
            if not any(_book_key(row) == book_key for row in fresh_complete_rows)
        ]
        mainline_meta = mainline_metadata.get(player_key, {})
        mainline_skip_reasons = (
            ["ambiguous_mainline"]
            if mainline_meta.get("ambiguous_line_ids") and not fresh_complete_rows
            else []
        )

        if not fresh_complete_rows:
            skip_reasons = mainline_skip_reasons or _skip_reasons(supported_rows, stale_after_seconds)
            source_line_ids = (
                list(mainline_meta.get("raw_candidate_ids") or [])
                if mainline_skip_reasons
                else _line_ids(supported_rows)
            )
            official_rows.append(_inactive_official_row(
                slate_date=slate_date,
                normalized_player_name=normalized_player_name,
                player_name=player_name,
                market_key=market_key,
                reasons=skip_reasons,
                stale_after_seconds=stale_after_seconds,
                now_utc=observed_now,
                current_line_ids=source_line_ids,
            ))
            decision_rows.append(_decision_row(
                slate_date=slate_date,
                normalized_player_name=normalized_player_name,
                market_key=market_key,
                decision="skip",
                reasons=skip_reasons,
                candidate_count=len(supported_rows),
                stale_candidate_count=stale_count,
                missing_book_keys=missing_books,
                source_line_ids=source_line_ids,
            ))
            continue

        selected_by_book = {
            book_key: selected
            for book_key in REF_BOOK_PRIORITY
            if (
                selected := _select_book_line(
                    fresh_complete_rows,
                    book_key,
                    boltodds_draftkings_enabled=boltodds_draftkings_enabled,
                )
            ) is not None
        }
        if not selected_by_book:
            official_rows.append(_inactive_official_row(
                slate_date=slate_date,
                normalized_player_name=normalized_player_name,
                player_name=player_name,
                market_key=market_key,
                reasons=["no_supported_ref_book"],
                stale_after_seconds=stale_after_seconds,
                now_utc=observed_now,
                current_line_ids=_line_ids(supported_rows),
            ))
            decision_rows.append(_decision_row(
                slate_date=slate_date,
                normalized_player_name=normalized_player_name,
                market_key=market_key,
                decision="skip",
                reasons=["no_supported_ref_book"],
                candidate_count=len(supported_rows),
                stale_candidate_count=stale_count,
                missing_book_keys=missing_books,
                source_line_ids=_line_ids(supported_rows),
            ))
            continue

        ref_book_key = next(book_key for book_key in REF_BOOK_PRIORITY if book_key in selected_by_book)
        ref_row = selected_by_book[ref_book_key]
        book_odds = _book_odds(selected_by_book)
        coverage = {
            book_key: {
                "provider": row.get("provider"),
                "line": row.get("line"),
                "freshness_seconds": _effective_freshness(row),
                "line_freshness_seconds": _freshness(row),
                "heartbeat_hold": _heartbeat_hold(row),
            }
            for book_key, row in selected_by_book.items()
        }
        quality_flags = _official_quality_flags(selected_by_book)
        reasons = _selection_reasons(selected_by_book, missing_books, quality_flags, ref_book_key, ref_row)
        current_line_ids = _line_ids(selected_by_book.values())
        if "cross_book_line_conflict" in quality_flags:
            official_rows.append(_inactive_official_row(
                slate_date=slate_date,
                normalized_player_name=normalized_player_name,
                player_name=player_name,
                market_key=market_key,
                reasons=["cross_book_line_conflict"],
                stale_after_seconds=stale_after_seconds,
                now_utc=observed_now,
                current_line_ids=current_line_ids,
            ))
            decision_rows.append(_decision_row(
                slate_date=slate_date,
                normalized_player_name=normalized_player_name,
                market_key=market_key,
                decision="skip",
                reasons=["cross_book_line_conflict"],
                candidate_count=len(supported_rows),
                stale_candidate_count=stale_count,
                missing_book_keys=missing_books,
                source_line_ids=current_line_ids,
            ))
            continue

        game_time = _selected_game_time(selected_by_book, ref_book_key)
        if not game_time:
            official_rows.append(_inactive_official_row(
                slate_date=slate_date,
                normalized_player_name=normalized_player_name,
                player_name=player_name,
                market_key=market_key,
                reasons=["missing_game_time"],
                stale_after_seconds=stale_after_seconds,
                now_utc=observed_now,
                current_line_ids=current_line_ids,
            ))
            decision_rows.append(_decision_row(
                slate_date=slate_date,
                normalized_player_name=normalized_player_name,
                market_key=market_key,
                decision="skip",
                reasons=["missing_game_time"],
                candidate_count=len(supported_rows),
                stale_candidate_count=stale_count,
                missing_book_keys=missing_books,
                source_line_ids=current_line_ids,
            ))
            continue

        official_rows.append({
            "slate_date": slate_date,
            "normalized_player_name": normalized_player_name,
            "player_name": player_name,
            "market_key": market_key,
            "game_time": game_time,
            "ref_book_key": ref_book_key,
            "ref_book_name": _book_name(ref_row),
            "ref_line": ref_row.get("line"),
            "ref_over_odds": ref_row.get("over_odds"),
            "ref_under_odds": ref_row.get("under_odds"),
            "selected_provider": ref_row.get("provider"),
            "selected_source": "provider_arbitration",
            "book_odds": book_odds,
            "provider_coverage": coverage,
            "arbitration_reasons": reasons,
            "quality_flags": quality_flags,
            "freshness_seconds": min(_effective_freshness(row) for row in selected_by_book.values()),
            "stale_after_seconds": stale_after_seconds,
            "current_market_line_ids": current_line_ids,
            "ready_for_pipeline": True,
            "updated_at": _isoformat(observed_now),
        })
        decision_rows.append(_decision_row(
            slate_date=slate_date,
            normalized_player_name=normalized_player_name,
            market_key=market_key,
            decision="use",
            reasons=reasons,
            candidate_count=len(supported_rows),
            stale_candidate_count=stale_count,
            missing_book_keys=missing_books,
            source_line_ids=current_line_ids,
            selected_provider=str(ref_row.get("provider") or ""),
            selected_book_key=ref_book_key,
            selected_line=ref_row.get("line"),
        ))

    return official_rows, decision_rows


def select_mainline_current_lines(
    current_lines: list[dict[str, Any]],
    now_utc: datetime,
    stale_after_seconds: int = 900,
    allow_the_odds_emergency: bool = False,
    provider_heartbeats: list[dict[str, Any]] | None = None,
    provider_health: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[tuple[str, str, str], dict[str, Any]]]:
    """Select conservative mainline candidates while preserving raw rows elsewhere."""
    observed_now = _ensure_utc(now_utc)
    heartbeat_health = provider_health
    if heartbeat_health is None:
        heartbeat_health = _provider_heartbeat_health(
            provider_heartbeats or [],
            observed_now,
            stale_after_seconds,
        )
    observed_rows = [
        _with_observed_freshness(
            row,
            observed_now,
            provider_health=heartbeat_health,
            stale_after_seconds=stale_after_seconds,
        )
        for row in current_lines
    ]
    grouped = _group_by_player(observed_rows)
    selected_rows: list[dict[str, Any]] = []
    metadata: dict[tuple[str, str, str], dict[str, Any]] = {}

    for player_key, rows in grouped.items():
        supported_rows = [row for row in rows if _book_key(row) in REF_BOOK_PRIORITY]
        eligible_rows = [
            row for row in supported_rows
            if _is_mainline_eligible(row, stale_after_seconds, allow_the_odds_emergency)
        ]
        provider_book_groups = _group_by_provider_book(eligible_rows)
        player_selected: list[dict[str, Any]] = []
        ambiguous_line_ids: list[Any] = []
        reasons: list[str] = []

        for group_key in sorted(provider_book_groups):
            candidates = provider_book_groups[group_key]
            distinct_lines = {_line_value(row) for row in candidates}
            if len(distinct_lines) <= 1:
                selected = min(candidates, key=lambda row: (_freshness(row), str(row.get("id") or "")))
                player_selected.append(_with_mainline_selection(selected, []))
                continue

            selected, selected_reasons = _choose_mainline_candidate(candidates, eligible_rows)
            if selected is None:
                ambiguous_line_ids.extend(_line_ids(candidates))
                reasons.append("ambiguous_mainline")
                continue

            player_selected.append(_with_mainline_selection(selected, selected_reasons))
            reasons.extend(selected_reasons)

        selected_rows.extend(player_selected)
        metadata[player_key] = {
            "raw_candidate_ids": _line_ids(supported_rows),
            "mainline_line_ids": _line_ids(player_selected),
            "ambiguous_line_ids": ambiguous_line_ids,
            "reasons": _unique_preserving_order(reasons),
        }

    return selected_rows, metadata


def retire_missing_official_lines(
    *,
    official_rows: list[dict[str, Any]],
    existing_official_rows: list[dict[str, Any]],
    now_utc: datetime,
    stale_after_seconds: int = 900,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fail closed for previously ready official rows missing from this build."""
    observed_now = _ensure_utc(now_utc)
    active_keys = {_official_key(row) for row in official_rows}
    retired_rows: list[dict[str, Any]] = []
    decision_rows: list[dict[str, Any]] = []

    for row in existing_official_rows:
        key = _official_key(row)
        if not all(key):
            continue
        if key in active_keys:
            continue
        if not row.get("ready_for_pipeline"):
            continue

        slate_date, normalized_player_name, market_key = key
        source_line_ids = _json_list(row.get("current_market_line_ids"))
        retired_rows.append(_inactive_official_row(
            slate_date=slate_date,
            normalized_player_name=normalized_player_name,
            player_name=str(row.get("player_name") or normalized_player_name),
            market_key=market_key,
            reasons=["missing_from_current_market_lines"],
            stale_after_seconds=stale_after_seconds,
            now_utc=observed_now,
            current_line_ids=source_line_ids,
        ))
        decision_rows.append(_decision_row(
            slate_date=slate_date,
            normalized_player_name=normalized_player_name,
            market_key=market_key,
            decision="skip",
            reasons=["missing_from_current_market_lines"],
            candidate_count=0,
            stale_candidate_count=0,
            missing_book_keys=list(REF_BOOK_PRIORITY),
            source_line_ids=source_line_ids,
        ))

    return retired_rows, decision_rows


def _group_by_provider_book(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in rows:
        key = (str(row.get("provider") or "").strip().lower(), _book_key(row))
        if all(key):
            grouped.setdefault(key, []).append(row)
    return grouped


def _group_by_player(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        slate_date = str(row.get("slate_date") or "").strip()
        normalized = str(row.get("normalized_player_name") or "").strip()
        market_key = str(row.get("market_key") or "pitcher_strikeouts").strip()
        if not slate_date or not normalized:
            continue
        grouped.setdefault((slate_date, normalized, market_key), []).append(row)
    return grouped


def _official_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("slate_date") or "").strip(),
        str(row.get("normalized_player_name") or "").strip(),
        str(row.get("market_key") or "pitcher_strikeouts").strip(),
    )


def _select_book_line(
    rows: list[dict[str, Any]],
    book_key: str,
    *,
    boltodds_draftkings_enabled: bool,
) -> dict[str, Any] | None:
    candidates = [row for row in rows if _book_key(row) == book_key]
    if not candidates:
        return None
    provider_priority = (
        DEFAULT_PROVIDER_PRIORITY
        if book_key != "draftkings" or boltodds_draftkings_enabled
        else DRAFTKINGS_PROVIDER_PRIORITY
    )
    return min(
        candidates,
        key=lambda row: (
            _provider_rank(str(row.get("provider") or ""), provider_priority),
            _freshness(row),
            str(row.get("id") or ""),
        ),
    )


def _is_mainline_eligible(
    row: dict[str, Any],
    stale_after_seconds: int,
    allow_the_odds_emergency: bool,
) -> bool:
    if row.get("provider") == "the_odds":
        if not allow_the_odds_emergency or _book_key(row) not in THE_ODDS_EMERGENCY_BOOKS:
            return False
    flags = set(_flags(row))
    return (
        _is_complete(row)
        and _is_effectively_fresh(row, stale_after_seconds)
        and ("stale" not in flags or _heartbeat_hold(row))
    )


def _is_usable_current_line(
    row: dict[str, Any],
    stale_after_seconds: int,
    allow_the_odds_emergency: bool,
) -> bool:
    flags = set(_flags(row))
    if row.get("provider") == "the_odds":
        if not allow_the_odds_emergency or _book_key(row) not in THE_ODDS_EMERGENCY_BOOKS:
            return False
    return (
        _is_complete(row)
        and _is_effectively_fresh(row, stale_after_seconds)
        and ("stale" not in flags or _heartbeat_hold(row))
        and "line_conflict" not in flags
    )


def _choose_mainline_candidate(
    candidates: list[dict[str, Any]],
    eligible_rows: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[str]]:
    scored = []
    for row in candidates:
        line = _line_value(row)
        same_book_provider_support = [
            other for other in eligible_rows
            if other is not row
            and _book_key(other) == _book_key(row)
            and str(other.get("provider") or "").strip().lower() != str(row.get("provider") or "").strip().lower()
            and _line_value(other) == line
        ]
        cross_book_support = [
            other for other in eligible_rows
            if other is not row
            and _book_key(other) != _book_key(row)
            and _line_value(other) == line
        ]
        scored.append({
            "row": row,
            "provider_overlap_count": len(same_book_provider_support),
            "cross_book_support_count": len(cross_book_support),
            "balance_score": _price_balance_score(row),
            "freshness": _freshness(row),
        })

    supported = [
        item for item in scored
        if item["provider_overlap_count"] > 0 or item["cross_book_support_count"] > 0
    ]
    if supported:
        best = min(
            supported,
            key=lambda item: (
                -item["provider_overlap_count"],
                -item["cross_book_support_count"],
                -item["balance_score"],
                item["freshness"],
                str(item["row"].get("id") or ""),
            ),
        )
        tied = [
            item for item in supported
            if (
                item["provider_overlap_count"],
                item["cross_book_support_count"],
                item["balance_score"],
            ) == (
                best["provider_overlap_count"],
                best["cross_book_support_count"],
                best["balance_score"],
            )
        ]
        if len(tied) > 1 and len({_line_value(item["row"]) for item in tied}) > 1:
            return None, []
        return best["row"], _mainline_reasons(best)

    best_balance = max((item["balance_score"] for item in scored), default=0)
    if best_balance >= 2:
        balanced = [item for item in scored if item["balance_score"] == best_balance]
        unbalanced = [item for item in scored if item["balance_score"] <= 0]
        if len(balanced) == 1 and len(unbalanced) == len(scored) - 1:
            return balanced[0]["row"], _mainline_reasons(balanced[0])

    return None, []


def _mainline_reasons(scored_item: dict[str, Any]) -> list[str]:
    row = scored_item["row"]
    book_key = _book_key(row)
    line = _format_line(row.get("line"))
    reasons = [f"mainline_selected:{book_key}:{line}"]
    if scored_item["provider_overlap_count"]:
        reasons.append(f"mainline_overlap_provider:{book_key}:{line}")
    if scored_item["cross_book_support_count"]:
        reasons.append(f"mainline_cross_book_support:{book_key}:{line}")
    if scored_item["balance_score"] >= 2:
        reasons.append(f"mainline_balanced_prices:{book_key}:{line}")
    return reasons


def _with_mainline_selection(row: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    selected = dict(row)
    flags = [flag for flag in _flags(row) if flag != "line_conflict"]
    if reasons and "mainline_selected" not in flags:
        flags.append("mainline_selected")
    selected["quality_flags"] = flags
    selected["_mainline_reasons"] = list(reasons)
    return selected


def _line_value(row: dict[str, Any]) -> float | str:
    value = row.get("line")
    try:
        return float(value)
    except (TypeError, ValueError):
        return str(value)


def _price_balance_score(row: dict[str, Any]) -> int:
    odds = [row.get("over_odds"), row.get("under_odds")]
    parsed: list[int] = []
    for value in odds:
        try:
            parsed.append(int(value))
        except (TypeError, ValueError):
            return 0
    max_abs = max(abs(value) for value in parsed)
    if max_abs <= 150:
        return 2
    if max_abs <= 200:
        return 1
    return 0


def _format_line(value: Any) -> str:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return str(value)
    if parsed.is_integer():
        return str(int(parsed))
    return str(parsed)


def _is_complete(row: dict[str, Any]) -> bool:
    return bool(row.get("is_complete")) and row.get("over_odds") is not None and row.get("under_odds") is not None


def _skip_reasons(rows: list[dict[str, Any]], stale_after_seconds: int) -> list[str]:
    if not rows:
        return ["no_supported_rows"]
    reasons: list[str] = []
    if not any(_is_complete(row) for row in rows):
        reasons.append("no_complete_line")
    if any(_is_complete(row) and not _is_effectively_fresh(row, stale_after_seconds) for row in rows):
        reasons.append("stale")
    if any("line_conflict" in _flags(row) for row in rows):
        reasons.append("line_conflict")
    if not reasons:
        reasons.append("no_fresh_complete_line")
    return reasons


def _selection_reasons(
    selected_by_book: dict[str, dict[str, Any]],
    missing_books: list[str],
    quality_flags: list[str],
    ref_book_key: str,
    ref_row: dict[str, Any],
) -> list[str]:
    reasons = [
        "fresh_complete_supported_line",
        f"selected_ref_book:{ref_book_key}",
        f"selected_provider:{ref_row.get('provider')}",
    ]
    if selected_by_book.get("draftkings", {}).get("provider") == "propline":
        reasons.append("propline_draftkings")
    if any(row.get("provider") == "therundown" for row in selected_by_book.values()):
        reasons.append("therundown_primary")
    for row in selected_by_book.values():
        if _heartbeat_hold(row):
            reason = f"provider_heartbeat_hold:{row.get('provider')}"
            if reason not in reasons:
                reasons.append(reason)
    for row in selected_by_book.values():
        for reason in row.get("_mainline_reasons") or []:
            if reason not in reasons:
                reasons.append(str(reason))
    if "cross_book_line_conflict" in quality_flags:
        reasons.append("cross_book_line_conflict")
    if missing_books:
        reasons.append("missing_books:" + ",".join(missing_books))
    return reasons


def _official_quality_flags(selected_by_book: dict[str, dict[str, Any]]) -> list[str]:
    flags: list[str] = []
    lines = {str(row.get("line")) for row in selected_by_book.values()}
    if len(lines) > 1:
        flags.append("cross_book_line_conflict")
    return flags


def _book_odds(selected_by_book: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        _book_name(row): {
            "line": row.get("line"),
            "over": row.get("over_odds"),
            "under": row.get("under_odds"),
            "provider": row.get("provider"),
            "book_key": book_key,
            "current_market_line_id": row.get("id"),
            "freshness_seconds": _effective_freshness(row),
            "line_freshness_seconds": _freshness(row),
            "heartbeat_hold": _heartbeat_hold(row),
        }
        for book_key, row in selected_by_book.items()
    }


def _inactive_official_row(
    *,
    slate_date: str,
    normalized_player_name: str,
    player_name: str,
    market_key: str,
    reasons: list[str],
    stale_after_seconds: int,
    now_utc: datetime,
    current_line_ids: list[Any],
) -> dict[str, Any]:
    return {
        "slate_date": slate_date,
        "normalized_player_name": normalized_player_name,
        "player_name": player_name,
        "market_key": market_key,
        "game_time": None,
        "ref_book_key": None,
        "ref_book_name": None,
        "ref_line": None,
        "ref_over_odds": None,
        "ref_under_odds": None,
        "selected_provider": None,
        "selected_source": "provider_arbitration",
        "book_odds": {},
        "provider_coverage": {},
        "arbitration_reasons": reasons,
        "quality_flags": ["not_ready_for_pipeline", *reasons],
        "freshness_seconds": None,
        "stale_after_seconds": stale_after_seconds,
        "current_market_line_ids": current_line_ids,
        "ready_for_pipeline": False,
        "updated_at": _isoformat(now_utc),
    }


def _decision_row(
    *,
    slate_date: str,
    normalized_player_name: str,
    market_key: str,
    decision: str,
    reasons: list[str],
    candidate_count: int,
    stale_candidate_count: int,
    missing_book_keys: list[str],
    source_line_ids: list[Any],
    selected_provider: str | None = None,
    selected_book_key: str | None = None,
    selected_line: Any = None,
) -> dict[str, Any]:
    return {
        "slate_date": slate_date,
        "normalized_player_name": normalized_player_name,
        "market_key": market_key,
        "selected_provider": selected_provider,
        "selected_book_key": selected_book_key,
        "selected_line": selected_line,
        "decision": decision,
        "reasons": reasons,
        "candidate_count": candidate_count,
        "stale_candidate_count": stale_candidate_count,
        "missing_book_keys": missing_book_keys,
        "source_line_ids": source_line_ids,
    }


def _line_ids(rows: Any) -> list[Any]:
    ids = []
    for row in rows:
        line_id = row.get("id")
        if line_id is not None:
            ids.append(line_id)
    return ids


def _book_key(row: dict[str, Any]) -> str:
    return str(row.get("book_key") or "").strip().lower()


def _book_name(row: dict[str, Any]) -> str:
    return str(row.get("book_name") or row.get("book_key") or "").strip()


def _display_player_name(rows: list[dict[str, Any]]) -> str:
    return str(rows[0].get("player_name") or rows[0].get("normalized_player_name") or "").strip()


def _game_time(row: dict[str, Any]) -> str | None:
    value = str(row.get("game_time") or "").strip()
    if value:
        return value
    return None


def _selected_game_time(selected_by_book: dict[str, dict[str, Any]], ref_book_key: str) -> str | None:
    ref_time = _game_time(selected_by_book[ref_book_key])
    if ref_time:
        return ref_time
    for row in selected_by_book.values():
        game_time = _game_time(row)
        if game_time:
            return game_time
    return None


def _provider_heartbeat_health(
    rows: list[dict[str, Any]],
    observed_now: datetime,
    stale_after_seconds: int,
) -> dict[tuple[str, str], dict[str, Any]]:
    health: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        provider = str(row.get("provider") or "").strip().lower()
        slate_date = str(row.get("slate_date") or "").strip()
        if provider not in WEBSOCKET_HOLD_PROVIDERS or not slate_date:
            continue

        metadata = _json_object(row.get("metadata"))
        if str(metadata.get("event") or "").strip().lower() in {"failed", "completed"}:
            continue

        observed_at = _parse_datetime(row.get("observed_at"))
        last_message_at = _parse_datetime(row.get("last_message_at"))
        if observed_at is None or last_message_at is None:
            continue

        observed_age = max(int((observed_now - observed_at).total_seconds()), 0)
        message_age = max(int((observed_now - last_message_at).total_seconds()), 0)
        freshness_seconds = max(observed_age, message_age)
        if freshness_seconds > stale_after_seconds:
            continue

        books_seen = _heartbeat_books(row, metadata)
        if not books_seen:
            continue

        key = (provider, slate_date)
        existing = health.get(key)
        if existing is None or freshness_seconds < int(existing.get("freshness_seconds") or UNKNOWN_FRESHNESS_SECONDS):
            health[key] = {
                "freshness_seconds": freshness_seconds,
                "observed_age_seconds": observed_age,
                "message_age_seconds": message_age,
                "books_seen": books_seen,
            }
    return health


def _with_observed_freshness(
    row: dict[str, Any],
    observed_now: datetime,
    *,
    provider_health: dict[tuple[str, str], dict[str, Any]] | None = None,
    stale_after_seconds: int = 900,
) -> dict[str, Any]:
    enriched = dict(row)
    last_seen_at = _parse_datetime(row.get("last_seen_at"))
    if last_seen_at is None:
        enriched["_computed_freshness_seconds"] = UNKNOWN_FRESHNESS_SECONDS
        return enriched
    enriched["_computed_freshness_seconds"] = max(int((observed_now - last_seen_at).total_seconds()), 0)
    heartbeat_health = provider_health or {}
    heartbeat_hold = _heartbeat_hold_health(enriched, heartbeat_health, stale_after_seconds)
    if heartbeat_hold is not None:
        enriched["_provider_heartbeat_hold"] = True
        enriched["_provider_heartbeat_freshness_seconds"] = heartbeat_hold["freshness_seconds"]
    return enriched


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return _ensure_utc(value)
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return _ensure_utc(datetime.fromisoformat(text))
    except ValueError:
        return None


def _provider_rank(provider: str, provider_priority: tuple[str, ...]) -> int:
    try:
        return provider_priority.index(provider)
    except ValueError:
        return len(provider_priority)


def _freshness(row: dict[str, Any]) -> int:
    try:
        if row.get("_computed_freshness_seconds") is not None:
            return int(row.get("_computed_freshness_seconds"))
        if row.get("freshness_seconds") is None:
            return UNKNOWN_FRESHNESS_SECONDS
        return int(row.get("freshness_seconds"))
    except (TypeError, ValueError):
        return UNKNOWN_FRESHNESS_SECONDS


def _effective_freshness(row: dict[str, Any]) -> int:
    if _heartbeat_hold(row):
        try:
            return int(row.get("_provider_heartbeat_freshness_seconds"))
        except (TypeError, ValueError):
            return _freshness(row)
    return _freshness(row)


def _is_effectively_fresh(row: dict[str, Any], stale_after_seconds: int) -> bool:
    return _effective_freshness(row) <= stale_after_seconds


def _heartbeat_hold(row: dict[str, Any]) -> bool:
    return bool(row.get("_provider_heartbeat_hold"))


def _heartbeat_hold_health(
    row: dict[str, Any],
    provider_health: dict[tuple[str, str], dict[str, Any]],
    stale_after_seconds: int,
) -> dict[str, Any] | None:
    provider = str(row.get("provider") or "").strip().lower()
    if provider not in WEBSOCKET_HOLD_PROVIDERS:
        return None
    if not _is_complete(row):
        return None
    if _freshness(row) <= stale_after_seconds and "stale" not in _flags(row):
        return None

    slate_date = str(row.get("slate_date") or "").strip()
    health = provider_health.get((provider, slate_date))
    if not health:
        return None

    book_key = _book_key(row)
    books_seen = set(health.get("books_seen") or [])
    if book_key not in books_seen:
        return None
    try:
        if int(health.get("freshness_seconds")) > stale_after_seconds:
            return None
    except (TypeError, ValueError):
        return None
    return health


def _flags(row: dict[str, Any]) -> list[str]:
    flags = row.get("quality_flags") or []
    if isinstance(flags, str):
        try:
            parsed = json.loads(flags)
            if isinstance(parsed, list):
                return [str(flag) for flag in parsed]
        except json.JSONDecodeError:
            return [flags]
    if isinstance(flags, list):
        return [str(flag) for flag in flags]
    return []


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


def _heartbeat_books(row: dict[str, Any], metadata: dict[str, Any]) -> set[str]:
    raw_books = row.get("books_seen")
    if not raw_books:
        raw_books = metadata.get("target_books") or metadata.get("books_seen")
    if isinstance(raw_books, str):
        text = raw_books.strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                parsed = []
            raw_books = parsed
        elif text.startswith("{") and text.endswith("}"):
            raw_books = [item.strip() for item in text[1:-1].split(",")]
        else:
            raw_books = [item.strip() for item in text.split(",")]
    if not isinstance(raw_books, list):
        return set()
    return {
        str(book).strip().lower()
        for book in raw_books
        if str(book).strip()
    }


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


def _unique_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _isoformat(value: datetime) -> str:
    return _ensure_utc(value).isoformat()
