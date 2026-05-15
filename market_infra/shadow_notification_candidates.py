from __future__ import annotations

from typing import Any


NEAR_GAME_WINDOWS = {"pre_5", "pre_15"}


def _books_seen(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(str(book).strip().lower() for book in value if str(book).strip())


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _candidate_type(row: dict[str, Any]) -> str:
    market_consensus = str(row.get("market_consensus") or "none")
    bet_value_consensus = str(row.get("bet_value_consensus") or "none")
    if market_consensus == "toward_pick" and bet_value_consensus == "worse_now":
        return "market_confirmed_worse_number"
    if market_consensus == "toward_pick":
        return "market_confirmed_playable"
    if market_consensus == "away_from_pick" and bet_value_consensus == "better_now":
        return "better_number_market_fade"
    if market_consensus == "mixed" or bet_value_consensus == "mixed":
        return "mixed_market"
    return "no_clear_signal"


def _playable_state(row: dict[str, Any]) -> str:
    bet_value_consensus = str(row.get("bet_value_consensus") or "none")
    if bet_value_consensus == "worse_now":
        return "number_worse"
    if int(row.get("touching_pick_line_count") or 0) <= 0:
        return "line_not_seen"
    if bet_value_consensus == "better_now":
        return "playable_now"
    return "line_seen"


def _suppression_reasons(
    *,
    row: dict[str, Any],
    candidate_type: str,
    broad_confirmation: bool,
    betrivers_only: bool,
    volatile_or_reversed: bool,
) -> list[str]:
    reasons: list[str] = []
    if candidate_type != "market_confirmed_playable":
        if candidate_type == "market_confirmed_worse_number":
            reasons.append("number_worse")
        elif candidate_type == "better_number_market_fade":
            reasons.append("market_not_confirmed")
        elif candidate_type == "mixed_market":
            reasons.append("mixed_market")
        else:
            reasons.append("no_clear_signal")

    if str(row.get("time_window") or "") not in NEAR_GAME_WINDOWS:
        reasons.append("not_near_game")
    if not broad_confirmation:
        reasons.append("not_broad_confirmation")
    if betrivers_only:
        reasons.append("betrivers_only")
    if volatile_or_reversed:
        reasons.append("volatile_or_reversed")
    if str(_metadata(row).get("freshness_status") or "fresh") != "fresh":
        reasons.append("stale_market_evidence")
    return reasons


def build_shadow_notification_candidate_rows(
    market_evidence_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for evidence in market_evidence_rows:
        if not str(evidence.get("current_verdict") or "").startswith("FIRE"):
            continue

        books_seen = _books_seen(evidence.get("books_seen"))
        candidate_type = _candidate_type(evidence)
        broad_confirmation = int(evidence.get("toward_pick_count") or 0) >= 2
        single_book = int(evidence.get("book_count") or 0) == 1
        betrivers_only = books_seen == ["betrivers"]
        volatile_or_reversed = (
            int(evidence.get("reversal_book_count") or 0) > 0
            or int(evidence.get("volatile_book_count") or 0) > 0
        )
        suppression_reasons = _suppression_reasons(
            row=evidence,
            candidate_type=candidate_type,
            broad_confirmation=broad_confirmation,
            betrivers_only=betrivers_only,
            volatile_or_reversed=volatile_or_reversed,
        )
        candidate_action = "suppress_shadow" if suppression_reasons else "would_send_shadow"
        observed_at = str(evidence.get("observed_at") or "")

        rows.append({
            "slate_date": evidence.get("slate_date"),
            "pitcher": evidence.get("pitcher"),
            "normalized_pitcher": evidence.get("normalized_pitcher"),
            "side": evidence.get("side"),
            "provider": evidence.get("provider"),
            "current_verdict": evidence.get("current_verdict"),
            "k_line": evidence.get("k_line"),
            "candidate_type": candidate_type,
            "candidate_action": candidate_action,
            "playable_state": _playable_state(evidence),
            "market_consensus": evidence.get("market_consensus"),
            "bet_value_consensus": evidence.get("bet_value_consensus"),
            "time_window": evidence.get("time_window"),
            "minutes_to_game": evidence.get("minutes_to_game"),
            "book_count": evidence.get("book_count"),
            "books_seen": books_seen,
            "broad_confirmation": broad_confirmation,
            "single_book": single_book,
            "betrivers_only": betrivers_only,
            "reversal_book_count": evidence.get("reversal_book_count") or 0,
            "volatile_book_count": evidence.get("volatile_book_count") or 0,
            "suppression_reasons": suppression_reasons,
            "evidence_dedupe_key": evidence.get("dedupe_key"),
            "occurred_at": observed_at,
            "dedupe_key": (
                f"{evidence.get('slate_date')}:shadow_candidate:{evidence.get('provider')}:"
                f"{evidence.get('normalized_pitcher')}:{evidence.get('side')}:"
                f"{candidate_type}:{observed_at}"
            ),
            "metadata": {
                "market_evidence": {
                    "toward_pick_count": evidence.get("toward_pick_count"),
                    "away_from_pick_count": evidence.get("away_from_pick_count"),
                    "better_now_count": evidence.get("better_now_count"),
                    "worse_now_count": evidence.get("worse_now_count"),
                    "touching_pick_line_count": evidence.get("touching_pick_line_count"),
                    "freshness_status": _metadata(evidence).get("freshness_status"),
                    "freshness_seconds": _metadata(evidence).get("freshness_seconds"),
                    "line_freshness_seconds": _metadata(evidence).get("line_freshness_seconds"),
                    "heartbeat_hold": _metadata(evidence).get("heartbeat_hold"),
                    "heartbeat_hold_books": _metadata(evidence).get("heartbeat_hold_books"),
                    "heartbeat_freshness_seconds": _metadata(evidence).get(
                        "heartbeat_freshness_seconds"
                    ),
                    "book_summaries": _metadata(evidence).get("book_summaries", {}),
                }
            },
        })

    return rows
