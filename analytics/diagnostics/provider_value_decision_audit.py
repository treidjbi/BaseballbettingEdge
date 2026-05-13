"""Compare live provider value against cost and freshness goals.

This diagnostic is read-only. It simulates a provider as the primary odds
source from already-collected shadow rows, then keeps the cost and
source-of-truth guardrails visible for the Friday provider decision.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.name_utils import normalize


BOOK_PREFERENCE = (
    "fanduel",
    "draftkings",
    "betmgm",
    "betrivers",
    "scorebet",
    "caesars",
)

MAIN_PROVIDER_CANDIDATE_BOOKS = (
    "fanduel",
    "draftkings",
    "betmgm",
    "betrivers",
    "caesars",
)
MAIN_PROVIDER_REQUIRED_BOOKS = 3

PROVIDER_PROFILES: dict[str, dict[str, Any]] = {
    "therundown": {
        "monthly_cost": 49,
        "role": "production_book_of_record",
        "capability": "scheduled official artifacts",
        "friday_decision": "keep_as_book_of_record_until_replaced",
        "known_limit": "not a cheap high-frequency live polling source",
    },
    "propline": {
        "monthly_cost": 40,
        "role": "shadow_fallback_live_polling",
        "capability": "10-minute polling and fallback evidence",
        "friday_decision": "prove_incremental_value_vs_boltodds_or_cut",
        "known_limit": "real provider webhooks are still unproven",
    },
    "boltodds": {
        "monthly_cost": 99,
        "role": "shadow_websocket_trial",
        "capability": "persistent websocket line movement",
        "friday_decision": "continue_shadow_primary_test",
        "known_limit": "stale-slate rollover and book gaps must be proven solved",
    },
    "the_odds": {
        "monthly_cost": 0,
        "role": "limited_fallback",
        "capability": "low-volume FD/DK fallback probe",
        "friday_decision": "keep_limited_fallback_only",
        "known_limit": "credit-limited and not a broad live provider",
    },
}

RENDER_BOLTODDS_WORKER_COST = 7


def _normalize_book(value: Any) -> str:
    return str(value or "").strip().casefold().replace(" ", "").replace("-", "")


def _to_float(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int:
    try:
        if value is None or isinstance(value, bool):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def _parse_timestamp(value: Any) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    if not text:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _latest_text(values: list[Any]) -> str | None:
    usable = [str(value) for value in values if str(value or "").strip()]
    if not usable:
        return None
    return max(usable, key=_parse_timestamp)


def _production_pitchers(production_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    pitchers: dict[str, dict[str, Any]] = {}
    for row in production_payload.get("pitchers") or []:
        pitcher = str(row.get("pitcher") or "").strip()
        normalized = normalize(pitcher)
        line = _to_float(row.get("k_line"))
        if not pitcher or not normalized or line is None:
            continue
        pitchers[normalized] = {
            "pitcher": pitcher,
            "line": line,
            "ref_book": row.get("ref_book"),
        }
    return pitchers


def _provider_snapshots(provider: str, snapshot_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    provider_key = provider.casefold()
    return [
        row
        for row in snapshot_rows
        if str(row.get("provider") or "").casefold() == provider_key
    ]


def _complete_snapshot_groups(
    provider: str,
    snapshot_rows: list[dict[str, Any]],
    book_preference: tuple[str, ...],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, float], dict[str, Any]] = {}
    allowed_books = set(book_preference)

    for row in _provider_snapshots(provider, snapshot_rows):
        book = _normalize_book(row.get("bookmaker_key") or row.get("bookmaker_title"))
        if book not in allowed_books:
            continue
        player = str(row.get("player_name") or "").strip()
        normalized = str(row.get("normalized_player_name") or "").strip() or normalize(player)
        side = str(row.get("side") or "").strip().lower()
        line = _to_float(row.get("line"))
        odds = row.get("american_odds")
        observed_at = str(row.get("observed_at") or "").strip()
        if not normalized or side not in {"over", "under"} or line is None:
            continue

        key = (normalized, book, line)
        group = grouped.setdefault(
            key,
            {
                "normalized_pitcher": normalized,
                "pitcher": player,
                "bookmaker_key": book,
                "provider_line": line,
                "sides": set(),
                "first_observed_at": observed_at,
                "latest_observed_at": observed_at,
                "rows": 0,
                "latest_odds": {},
            },
        )
        group["sides"].add(side)
        group["rows"] += 1
        group["first_observed_at"] = min(
            [value for value in [group["first_observed_at"], observed_at] if value],
            key=_parse_timestamp,
            default=observed_at,
        )
        group["latest_observed_at"] = max(
            [value for value in [group["latest_observed_at"], observed_at] if value],
            key=_parse_timestamp,
            default=observed_at,
        )
        if odds is not None:
            group["latest_odds"][side] = odds

    return [
        {key: value for key, value in group.items() if key != "sides"}
        for group in grouped.values()
        if {"over", "under"} <= group["sides"]
    ]


def shadow_primary_summary(
    *,
    provider: str,
    production_payload: dict[str, Any],
    snapshot_rows: list[dict[str, Any]],
    book_preference: tuple[str, ...] = BOOK_PREFERENCE,
) -> dict[str, Any]:
    """Simulate which production pitchers a shadow provider could cover."""
    production_pitchers = _production_pitchers(production_payload)
    complete_groups = _complete_snapshot_groups(provider, snapshot_rows, book_preference)
    rank = {book: index for index, book in enumerate(book_preference)}
    groups_by_pitcher: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in complete_groups:
        normalized = str(group["normalized_pitcher"])
        if normalized in production_pitchers:
            groups_by_pitcher[normalized].append(group)

    primary_lines: list[dict[str, Any]] = []
    missing_pitchers: list[str] = []
    same_line_count = 0
    line_conflict_count = 0
    target_books_seen = set()
    for group in complete_groups:
        if str(group["normalized_pitcher"]) in production_pitchers:
            target_books_seen.add(str(group["bookmaker_key"]))

    for normalized, production in sorted(
        production_pitchers.items(),
        key=lambda item: item[1]["pitcher"],
    ):
        candidates = groups_by_pitcher.get(normalized) or []
        if not candidates:
            missing_pitchers.append(str(production["pitcher"]))
            continue

        chosen = sorted(
            candidates,
            key=lambda row: (
                rank.get(str(row["bookmaker_key"]), len(rank)),
                -_parse_timestamp(row.get("latest_observed_at")).timestamp(),
            ),
        )[0]
        provider_line = _to_float(chosen["provider_line"])
        production_line = _to_float(production["line"])
        line_match = provider_line == production_line
        if line_match:
            same_line_count += 1
        else:
            line_conflict_count += 1
        primary_lines.append(
            {
                "pitcher": production["pitcher"],
                "bookmaker_key": chosen["bookmaker_key"],
                "provider_line": provider_line,
                "production_line": production_line,
                "line_match": line_match,
                "latest_observed_at": chosen.get("latest_observed_at"),
            }
        )

    covered_pitchers = len(primary_lines)
    production_count = len(production_pitchers)
    main_books_seen = sorted(
        book for book in target_books_seen if book in MAIN_PROVIDER_CANDIDATE_BOOKS
    )
    covers_all_pitchers = production_count > 0 and covered_pitchers == production_count
    return {
        "provider": provider,
        "production_pitchers": production_count,
        "covered_pitchers": covered_pitchers,
        "coverage_rate": round(covered_pitchers / production_count, 3)
        if production_count
        else 0.0,
        "missing_pitchers": missing_pitchers,
        "same_line_count": same_line_count,
        "line_conflict_count": line_conflict_count,
        "target_books_seen": sorted(target_books_seen),
        "main_provider_gate": {
            "required_main_books": MAIN_PROVIDER_REQUIRED_BOOKS,
            "main_books_seen": main_books_seen,
            "main_book_count": len(main_books_seen),
            "covers_all_pitchers": covers_all_pitchers,
            "meets_gate": (
                covers_all_pitchers
                and len(main_books_seen) >= MAIN_PROVIDER_REQUIRED_BOOKS
            ),
        },
        "complete_line_groups": len(complete_groups),
        "primary_lines": primary_lines,
    }


def summarize_movement_flow(
    provider: str,
    snapshot_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Summarize how much actual line/price movement a provider captured."""
    provider_rows = _provider_snapshots(provider, snapshot_rows)
    paths: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in provider_rows:
        book = _normalize_book(row.get("bookmaker_key") or row.get("bookmaker_title"))
        normalized = str(row.get("normalized_player_name") or "").strip() or normalize(
            str(row.get("player_name") or "")
        )
        side = str(row.get("side") or "").strip().lower()
        if book and normalized and side in {"over", "under"}:
            paths[(book, normalized, side)].append(row)

    paths_with_multiple = 0
    line_move_paths = 0
    odds_move_paths = 0
    books_with_movement = set()

    for (book, _, _), rows in paths.items():
        lines = {_to_float(row.get("line")) for row in rows}
        odds = {row.get("american_odds") for row in rows if row.get("american_odds") is not None}
        if len(rows) > 1:
            paths_with_multiple += 1
        moved = False
        if len(lines) > 1:
            line_move_paths += 1
            moved = True
        if len(odds) > 1:
            odds_move_paths += 1
            moved = True
        if moved:
            books_with_movement.add(book)

    return {
        "provider": provider,
        "snapshot_rows": len(provider_rows),
        "priced_paths": len(paths),
        "paths_with_multiple_observations": paths_with_multiple,
        "line_move_paths": line_move_paths,
        "odds_move_paths": odds_move_paths,
        "books_with_movement": sorted(books_with_movement),
        "latest_snapshot_at": _latest_text([row.get("observed_at") for row in provider_rows]),
    }


def summarize_pick_evidence(
    provider: str,
    pick_evidence_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Summarize compact per-pick market evidence by provider."""
    provider_key = provider.casefold()
    rows = [
        row
        for row in pick_evidence_rows
        if str(row.get("provider") or "").casefold() == provider_key
    ]
    pitchers = {str(row.get("pitcher") or "").strip() for row in rows if row.get("pitcher")}
    market_consensus = Counter(str(row.get("market_consensus") or "unknown") for row in rows)
    bet_value_consensus = Counter(
        str(row.get("bet_value_consensus") or "unknown") for row in rows
    )
    decision_value_rows = 0
    for row in rows:
        if any(
            _to_int(row.get(key)) > 0
            for key in (
                "toward_pick_count",
                "away_from_pick_count",
                "better_now_count",
                "worse_now_count",
            )
        ):
            decision_value_rows += 1

    return {
        "provider": provider,
        "rows": len(rows),
        "pitchers": len(pitchers),
        "decision_value_rows": decision_value_rows,
        "market_consensus_counts": dict(sorted(market_consensus.items())),
        "bet_value_consensus_counts": dict(sorted(bet_value_consensus.items())),
        "latest_observed_at": _latest_text([row.get("observed_at") for row in rows]),
    }


def _provider_cost(profile_key: str, profile: dict[str, Any]) -> int:
    cost = _to_int(profile.get("monthly_cost"))
    if profile_key == "boltodds":
        cost += RENDER_BOLTODDS_WORKER_COST
    return cost


def build_decision_matrix(
    *,
    production_payload: dict[str, Any],
    snapshot_rows: list[dict[str, Any]],
    pick_evidence_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build the Friday provider value matrix from exported evidence rows."""
    providers: dict[str, dict[str, Any]] = {}
    for provider, profile in PROVIDER_PROFILES.items():
        card = {
            "monthly_cost": _provider_cost(provider, profile),
            "role": profile["role"],
            "capability": profile["capability"],
            "known_limit": profile["known_limit"],
            "friday_decision": profile["friday_decision"],
        }
        if provider in {"boltodds", "propline"}:
            card["shadow_primary"] = shadow_primary_summary(
                provider=provider,
                production_payload=production_payload,
                snapshot_rows=snapshot_rows,
            )
            card["movement_flow"] = summarize_movement_flow(provider, snapshot_rows)
            card["pick_evidence"] = summarize_pick_evidence(provider, pick_evidence_rows)
        providers[provider] = card

    active_paid_provider_cost = sum(
        card["monthly_cost"]
        for key, card in providers.items()
        if key in {"therundown", "propline", "boltodds"}
    )

    return {
        "goal": "most_up_to_date_data_per_dollar",
        "guardrails": [
            "TheRundown remains production until Tyler explicitly approves a change.",
            "Prefer one book-of-record source plus one live movement source.",
            "A backup provider is optional if one provider covers every slate pitcher with at least 3 main books.",
            "Do not pay overlapping providers unless they change picks, locks, alerts, or confidence.",
            "The Odds API should stay limited fallback unless its credit model is explicitly approved.",
        ],
        "cost_summary": {
            "active_paid_provider_cost": active_paid_provider_cost,
            "boltodds_cost_includes_render_worker": True,
            "app_runtime_cost_watch_line": 200,
            "backup_required_when_main_gate_met": False,
        },
        "main_provider_gate": {
            "required_main_books": MAIN_PROVIDER_REQUIRED_BOOKS,
            "candidate_books": list(MAIN_PROVIDER_CANDIDATE_BOOKS),
            "backup_required_when_gate_met": False,
        },
        "providers": providers,
        "friday_questions": [
            "Did BoltOdds stay on the current slate every morning without manual restart?",
            "Did PropLine or BoltOdds cover every slate pitcher with at least 3 main books?",
            "Did BoltOdds beat PropLine on movement freshness or useful book coverage?",
            "Did either live source change a pick, alert, lock read, or confidence read?",
            "Can one paid shadow/live provider be cut without losing useful signal?",
        ],
    }


def render_markdown(matrix: dict[str, Any]) -> str:
    lines = [
        "# Provider Value Decision Audit",
        "",
        (
            "Goal: choose the cheapest stack that still gives the freshest useful line "
            "movement for Tyler's private decision support."
        ),
        "",
        "Shadow-only: this report must not change picks, locks, alerts, staking, thresholds, or provider order.",
        "",
        "## Cost Lens",
        "",
        f"- Active paid provider cost: ${matrix['cost_summary']['active_paid_provider_cost']}/mo",
        "- Preferred shape: one book-of-record source plus one live movement source.",
        "- Main-provider gate: 3 main books across every slate pitcher; backup is optional if this gate is met.",
        "- TheRundown remains production unless Tyler explicitly approves a change.",
        "",
        "## Friday Decision",
    ]

    for provider, card in matrix["providers"].items():
        lines.extend(
            [
                "",
                f"### {provider}",
                f"- Cost: ${card['monthly_cost']}/mo",
                f"- Role: {card['role']}",
                f"- Capability: {card['capability']}",
                f"- Known limit: {card['known_limit']}",
                f"- Friday decision: `{card['friday_decision']}`",
            ]
        )
        shadow_primary = card.get("shadow_primary")
        if shadow_primary:
            gate = shadow_primary["main_provider_gate"]
            lines.append(
                "- Shadow-primary coverage: "
                f"{shadow_primary['covered_pitchers']}/{shadow_primary['production_pitchers']} "
                f"pitchers, same-line={shadow_primary['same_line_count']}, "
                f"conflicts={shadow_primary['line_conflict_count']}"
            )
            lines.append(
                "- Main-provider gate: "
                f"{gate['main_book_count']}/{gate['required_main_books']} main books, "
                f"covers_all_pitchers={gate['covers_all_pitchers']}, "
                f"meets_gate={gate['meets_gate']}"
            )
        movement = card.get("movement_flow")
        if movement:
            lines.append(
                "- Movement flow: "
                f"{movement['line_move_paths']} line paths, "
                f"{movement['odds_move_paths']} odds paths, "
                f"latest={movement['latest_snapshot_at']}"
            )
        evidence = card.get("pick_evidence")
        if evidence:
            lines.append(
                "- Pick evidence: "
                f"{evidence['decision_value_rows']} decision-value rows across "
                f"{evidence['pitchers']} pitchers"
            )

    lines.extend(["", "## Questions To Answer"])
    for question in matrix["friday_questions"]:
        lines.append(f"- {question}")
    return "\n".join(lines)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json_rows(path: Path | None) -> list[dict[str, Any]]:
    if path is None:
        return []
    payload = _load_json(path)
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("rows", "data", "items"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a cost-aware provider value decision audit."
    )
    parser.add_argument("--production-artifact", type=Path, required=True)
    parser.add_argument("--market-snapshots", type=Path, required=True)
    parser.add_argument("--market-pick-evidence", type=Path)
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    matrix = build_decision_matrix(
        production_payload=_load_json(args.production_artifact),
        snapshot_rows=_load_json_rows(args.market_snapshots),
        pick_evidence_rows=_load_json_rows(args.market_pick_evidence),
    )
    if args.format == "json":
        print(json.dumps(matrix, indent=2, sort_keys=True))
    else:
        print(render_markdown(matrix))


if __name__ == "__main__":
    main()
