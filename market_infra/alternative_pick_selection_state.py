"""Pure, bounded state shaping for the default-off alternative-picks recorder.

This module deliberately keeps the canonical published-payload hash separate
from the exact fetched-artifact hash used by ``operational_pick_locks``.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timezone
from typing import Any

from market_infra.alternative_pick_selector import (
    BUNDLE_ID,
    CONSENSUS_SELECTOR_ID,
    EXPANSION_SELECTOR_ID,
)
from market_infra.published_artifacts import canonical_payload_sha256
from pipeline.name_utils import normalize


UNIQUE_COLUMNS = (
    "slate_date",
    "game_identity",
    "normalized_pitcher",
    "side",
    "bundle_id",
    "checkpoint",
)
SUPPORTED_PROVIDER_POSTURES = frozenset({"therundown", "propline", "therundown_propline"})
SUPPORTED_SNAPSHOT_PROVIDERS = frozenset({"therundown", "propline", "therundown_propline"})
APPROVED_ARTIFACT_PATH = "dashboard/data/processed/today.json"
SELECTOR_IDS_BY_LANE = {
    "consensus_core": CONSENSUS_SELECTOR_ID,
    "reentry_expansion": EXPANSION_SELECTOR_ID,
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _iso(value: Any) -> str | None:
    parsed = _utc(value)
    return parsed.isoformat() if parsed else None


def _line(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0 else None


def _integer(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return int(parsed) if math.isfinite(parsed) and parsed.is_integer() else None


def _nonnegative_integer(value: Any) -> int | None:
    parsed = _integer(value)
    return parsed if parsed is not None and parsed >= 0 else None


def _nonnegative_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0 else None


def _hash(value: Any) -> str | None:
    text = _text(value).lower()
    return text if len(text) == 64 and all(char in "0123456789abcdef" for char in text) else None


def _digest(parts: tuple[str, ...]) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def game_identity(*, slate_date: str, team: str, opp_team: str, game_time: str) -> str:
    """Stable Phoenix-slate game identity; not a lock-ledger dedupe key."""
    timestamp = _iso(game_time)
    return _digest((_text(slate_date), _text(team).upper(), _text(opp_team).upper(), timestamp or ""))


def candidate_identity(
    *, slate_date: str, pitcher: str, side: str, model_k_line: float,
    team: str, opp_team: str, game_time: str, provider_posture: str,
) -> str:
    game = game_identity(slate_date=slate_date, team=team, opp_team=opp_team, game_time=game_time)
    line = _line(model_k_line)
    return _digest((
        game, normalize(_text(pitcher)), _text(side).lower(),
        "" if line is None else f"{line:.3f}", _text(provider_posture).lower(),
    ))


def candidate_record(
    *, slate_date: str, pitcher: str, side: str, model_k_line: float,
    team: str, opp_team: str, game_time: str, provider_posture: str,
) -> dict[str, Any]:
    """Return the complete candidate identity used by the state rows."""
    normalized_pitcher = normalize(_text(pitcher))
    normalized_time = _iso(game_time)
    line = _line(model_k_line)
    return {
        "slate_date": _text(slate_date),
        "pitcher": _text(pitcher),
        "normalized_pitcher": normalized_pitcher,
        "side": _text(side).lower(),
        "model_k_line": line,
        "team": _text(team).upper(),
        "opp_team": _text(opp_team).upper(),
        "game_time": normalized_time,
        "provider_posture": _text(provider_posture).lower(),
        "game_identity": game_identity(
            slate_date=slate_date, team=team, opp_team=opp_team, game_time=game_time,
        ),
        "candidate_identity": candidate_identity(
            slate_date=slate_date, pitcher=pitcher, side=side, model_k_line=model_k_line,
            team=team, opp_team=opp_team, game_time=game_time,
            provider_posture=provider_posture,
        ),
    }


def _candidate_is_canonical(candidate: dict[str, Any]) -> bool:
    """Never trust a supplied identity from a prior payload or evaluator cycle."""
    if not isinstance(candidate, dict):
        return False
    line = _line(candidate.get("model_k_line"))
    if not all((
        _text(candidate.get("slate_date")), _text(candidate.get("pitcher")),
        candidate.get("side") in {"over", "under"}, line is not None,
        _text(candidate.get("team")), _text(candidate.get("opp_team")),
        _iso(candidate.get("game_time")) is not None,
        candidate.get("provider_posture") in SUPPORTED_PROVIDER_POSTURES,
    )):
        return False
    expected_game = game_identity(
        slate_date=candidate["slate_date"], team=candidate["team"],
        opp_team=candidate["opp_team"], game_time=candidate["game_time"],
    )
    expected_candidate = candidate_identity(
        slate_date=candidate["slate_date"], pitcher=candidate["pitcher"],
        side=candidate["side"], model_k_line=line, team=candidate["team"],
        opp_team=candidate["opp_team"], game_time=candidate["game_time"],
        provider_posture=candidate["provider_posture"],
    )
    return (
        _text(candidate.get("normalized_pitcher")) == normalize(_text(candidate["pitcher"]))
        and _text(candidate.get("game_identity")) == expected_game
        and _text(candidate.get("candidate_identity")) == expected_candidate
    )


def associate_candidate_observations(
    *, candidate: dict[str, Any], snapshot_rows: list[dict[str, Any]],
    first_current_at: str, observed_at: str,
) -> dict[str, Any]:
    """Compact only current-candidate, fresh, supported snapshots.

    Invalid current-candidate evidence makes the window pending. Snapshots for
    a replaced identity never enter the new candidate window.
    """
    start, checkpoint = _utc(first_current_at), _utc(observed_at)
    reasons: list[str] = []
    accepted: dict[str, datetime] = {}
    if not _candidate_is_canonical(candidate):
        reasons.append("candidate_identity_invalid")
    elif start is None or checkpoint is None:
        reasons.append("evidence_window_invalid")
    elif candidate.get("provider_posture") not in SUPPORTED_PROVIDER_POSTURES:
        reasons.append("candidate_provider_posture_unsupported")
    else:
        for snapshot in snapshot_rows if isinstance(snapshot_rows, list) else []:
            if not isinstance(snapshot, dict):
                reasons.append("evidence_malformed")
                continue
            if _text(snapshot.get("candidate_identity")) != _text(candidate.get("candidate_identity")):
                reasons.append("evidence_candidate_mismatch")
                continue
            if _text(snapshot.get("provider")).lower() not in SUPPORTED_SNAPSHOT_PROVIDERS:
                reasons.append("evidence_provider_unsupported")
                continue
            if _text(snapshot.get("freshness_status")).lower() != "fresh":
                reasons.append("evidence_stale")
                continue
            identifier, timestamp = _text(snapshot.get("id")), _utc(snapshot.get("observed_at"))
            if not identifier or timestamp is None:
                reasons.append("evidence_malformed")
            elif timestamp < start:
                reasons.append("evidence_before_current_candidate")
            elif timestamp > checkpoint:
                reasons.append("evidence_after_checkpoint")
            else:
                accepted[identifier] = timestamp
    # A stale/unknown/malformed current-candidate row is a fail-closed window;
    # a replaced identity alone is merely ignored so a fully new window can grow.
    if any(reason != "evidence_candidate_mismatch" for reason in reasons):
        accepted = {}
    if len(accepted) < 2:
        reasons.append("evidence_immature")
    timestamps = list(accepted.values())
    return {
        "observation_ids": sorted(accepted),
        "observation_count": len(accepted),
        "first_observed_at": min(timestamps).isoformat() if timestamps else None,
        "last_observed_at": max(timestamps).isoformat() if timestamps else None,
        "first_current_at": _iso(first_current_at),
        "freshness_status": "fresh" if not reasons else "pending",
        "ready": not reasons and len(accepted) >= 2,
        "reason_codes": tuple(dict.fromkeys(reasons)),
    }


def resolve_candidate_became_current_at(
    *, candidate: dict[str, Any], existing_rows: list[dict[str, Any]], observed_at: str,
) -> str | None:
    """Keep the window start only while the exact candidate identity is current."""
    current = _iso(observed_at)
    if current is None:
        return None
    identity = _text(candidate.get("candidate_identity"))
    for row in existing_rows if isinstance(existing_rows, list) else []:
        if (
            isinstance(row, dict)
            and row.get("checkpoint") == "provisional"
            and _text(row.get("candidate_identity")) == identity
        ):
            persisted = _iso(row.get("candidate_became_current_at"))
            if persisted is not None:
                return persisted
    return current


def bind_candidate_observations(
    *,
    candidate: dict[str, Any],
    snapshot_rows: list[dict[str, Any]],
    market_evidence_rows: list[dict[str, Any]],
    first_current_at: str,
    observed_at: str,
    artifact_snapshot_ids: list[Any] | tuple[Any, ...],
    artifact_provider_event_ids: dict[str, list[Any] | tuple[Any, ...]],
) -> dict[str, Any]:
    """Bind raw rows only when artifact, event, line, timing, and freshness agree."""
    start, checkpoint = _utc(first_current_at), _utc(observed_at)
    reasons: list[str] = []
    if not _candidate_is_canonical(candidate):
        reasons.append("candidate_identity_invalid")
    if start is None or checkpoint is None:
        reasons.append("evidence_window_invalid")

    snapshot_ids = {_text(value) for value in artifact_snapshot_ids if _text(value)}
    event_ids = {
        _text(provider).lower(): {_text(value) for value in values if _text(value)}
        for provider, values in (artifact_provider_event_ids or {}).items()
        if isinstance(values, (list, tuple, set))
    }
    required_providers = {
        "therundown": {"therundown"},
        "propline": {"propline"},
        "therundown_propline": {"therundown", "propline"},
    }.get(_text(candidate.get("provider_posture")).lower(), set())
    if not snapshot_ids and any(not event_ids.get(provider) for provider in required_providers):
        reasons.append("evidence_event_unbound")
    exact_evidence: dict[str, dict[str, Any]] = {}
    for row in market_evidence_rows if isinstance(market_evidence_rows, list) else []:
        if not isinstance(row, dict):
            continue
        provider = _text(row.get("provider")).lower()
        if provider not in SUPPORTED_SNAPSHOT_PROVIDERS:
            continue
        if (
            _text(row.get("slate_date")) == _text(candidate.get("slate_date"))
            and normalize(_text(row.get("normalized_pitcher") or row.get("pitcher")))
            == candidate.get("normalized_pitcher")
            and _text(row.get("side")).lower() == candidate.get("side")
            and _line(row.get("k_line")) == _line(candidate.get("model_k_line"))
            and _iso(row.get("game_time")) == _iso(candidate.get("game_time"))
        ):
            exact_evidence[provider] = row

    bound_rows: list[dict[str, Any]] = []
    for snapshot in snapshot_rows if isinstance(snapshot_rows, list) else []:
        if not isinstance(snapshot, dict):
            reasons.append("evidence_malformed")
            continue
        normalized = normalize(_text(snapshot.get("normalized_player_name") or snapshot.get("player_name")))
        side = _text(snapshot.get("side")).lower()
        if normalized != candidate.get("normalized_pitcher") or side != candidate.get("side"):
            continue
        provider = _text(snapshot.get("provider")).lower()
        if provider not in SUPPORTED_SNAPSHOT_PROVIDERS:
            reasons.append("evidence_provider_unsupported")
            continue
        if _line(snapshot.get("line")) != _line(candidate.get("model_k_line")):
            reasons.append("evidence_line_mismatch")
            continue
        snapshot_game_time = _iso(snapshot.get("game_time"))
        if snapshot_game_time and snapshot_game_time != _iso(candidate.get("game_time")):
            reasons.append("evidence_event_mismatch")
            continue
        snapshot_id = _text(snapshot.get("id"))
        provider_event_id = _text(snapshot.get("provider_event_id"))
        provider_artifact_events = event_ids.get(provider, set())
        if not snapshot_ids and not provider_artifact_events:
            reasons.append("evidence_event_unbound")
            continue
        if snapshot_id not in snapshot_ids and provider_event_id not in provider_artifact_events:
            reasons.append("evidence_event_mismatch")
            continue
        evidence = exact_evidence.get(provider)
        metadata = (
            evidence.get("metadata")
            if isinstance(evidence, dict) and isinstance(evidence.get("metadata"), dict)
            else {}
        )
        if not evidence or _text(metadata.get("freshness_status")).lower() != "fresh":
            reasons.append("evidence_stale")
            continue
        native_freshness = _text(snapshot.get("freshness_status")).lower()
        if native_freshness and native_freshness != "fresh":
            reasons.append("evidence_stale")
            continue
        timestamp = _utc(snapshot.get("observed_at"))
        bookmaker_key = _text(snapshot.get("bookmaker_key")).lower()
        american_odds = _integer(snapshot.get("american_odds"))
        if not snapshot_id or timestamp is None or not bookmaker_key or american_odds in {None, 0}:
            reasons.append("evidence_malformed")
        elif start is None or checkpoint is None:
            continue
        elif timestamp < start:
            reasons.append("evidence_before_current_candidate")
        elif timestamp > checkpoint:
            reasons.append("evidence_after_checkpoint")
        else:
            bound_rows.append({
                "id": snapshot_id,
                "provider": provider,
                "candidate_identity": candidate["candidate_identity"],
                "bookmaker_key": bookmaker_key,
                "american_odds": american_odds,
                "observed_at": timestamp.isoformat(),
                "freshness_status": "fresh",
            })

    if reasons:
        bound_rows = []
    window = associate_candidate_observations(
        candidate=candidate,
        snapshot_rows=bound_rows,
        first_current_at=first_current_at,
        observed_at=observed_at,
    )
    combined_reasons = tuple(dict.fromkeys((*reasons, *window.get("reason_codes", ()))))
    return {
        **window,
        "ready": not combined_reasons and bool(window.get("ready")),
        "reason_codes": combined_reasons,
        "bound_observations": [
            {
                "id": row["id"],
                "provider": row["provider"],
                "bookmaker_key": row["bookmaker_key"],
                "american_odds": row["american_odds"],
                "observed_at": row["observed_at"],
            }
            for row in bound_rows
        ],
    }


def aggregate_candidate_market_evidence(
    *,
    candidate: dict[str, Any],
    market_evidence_rows: list[dict[str, Any]],
    evidence_window: dict[str, Any],
) -> dict[str, Any]:
    """Deterministically combine complete, exact-current approved-provider rows."""
    reasons: list[str] = []
    rows_by_provider: dict[str, list[dict[str, Any]]] = {}
    for row in market_evidence_rows if isinstance(market_evidence_rows, list) else []:
        if not isinstance(row, dict):
            continue
        provider = _text(row.get("provider")).lower()
        if provider not in SUPPORTED_SNAPSHOT_PROVIDERS:
            continue
        if (
            _text(row.get("slate_date")) != _text(candidate.get("slate_date"))
            or normalize(_text(row.get("normalized_pitcher") or row.get("pitcher")))
            != candidate.get("normalized_pitcher")
            or _text(row.get("side")).lower() != candidate.get("side")
            or _line(row.get("k_line")) != _line(candidate.get("model_k_line"))
            or _iso(row.get("game_time")) != _iso(candidate.get("game_time"))
        ):
            continue
        rows_by_provider.setdefault(provider, []).append(row)

    posture = _text(candidate.get("provider_posture")).lower()
    declared_by_posture = {
        "therundown": {"therundown"},
        "propline": {"propline"},
        "therundown_propline": {"therundown", "propline"},
    }
    declared = declared_by_posture.get(posture, set())
    if not declared:
        reasons.append("candidate_provider_posture_unsupported")
    required = (
        "book_count",
        "toward_pick_count",
        "away_from_pick_count",
        "reversal_book_count",
        "volatile_book_count",
    )
    bound_by_provider: dict[str, list[dict[str, Any]]] = {}
    for observation in evidence_window.get("bound_observations", []):
        if not isinstance(observation, dict):
            reasons.append("provider_observations_malformed")
            continue
        provider = _text(observation.get("provider")).lower()
        if provider in declared:
            bound_by_provider.setdefault(provider, []).append(observation)

    provider_stats: dict[str, dict[str, Any]] = {}
    for provider in sorted(declared):
        provider_rows = rows_by_provider.get(provider, [])
        if len(provider_rows) != 1:
            reasons.append("provider_evidence_missing" if not provider_rows else "provider_evidence_duplicate")
            continue
        row = provider_rows[0]
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if _text(metadata.get("freshness_status")).lower() != "fresh":
            reasons.append("provider_evidence_stale")
        reported = {field: _nonnegative_integer(row.get(field)) for field in required}
        if any(value is None for value in reported.values()):
            reasons.append("provider_evidence_incomplete")
            continue

        observations = bound_by_provider.get(provider, [])
        if not observations:
            reasons.append("provider_observations_missing")
            continue
        by_book: dict[str, list[tuple[datetime, int]]] = {}
        malformed = False
        for observation in observations:
            book = _text(observation.get("bookmaker_key")).lower()
            timestamp = _utc(observation.get("observed_at"))
            odds = _integer(observation.get("american_odds"))
            if not book or timestamp is None or odds in {None, 0}:
                malformed = True
                continue
            by_book.setdefault(book, []).append((timestamp, odds))
        if malformed or not by_book:
            reasons.append("provider_observations_malformed")
            continue

        toward_count = 0
        away_count = 0
        reversal_count = 0
        for values in by_book.values():
            ordered = sorted(values)
            first_odds, current_odds = ordered[0][1], ordered[-1][1]
            if current_odds < first_odds:
                toward_count += 1
            elif current_odds > first_odds:
                away_count += 1
            directions = [
                "toward" if current < previous else "away"
                for (_, previous), (_, current) in zip(ordered, ordered[1:])
                if current != previous
            ]
            if any(previous != current for previous, current in zip(directions, directions[1:])):
                reversal_count += 1

        derived = {
            "book_count": len(by_book),
            "toward_pick_count": toward_count,
            "away_from_pick_count": away_count,
            "reversal_book_count": reversal_count,
            "volatile_book_count": reversal_count,
        }
        row_books = row.get("books_seen")
        if isinstance(row_books, (list, tuple, set)):
            reported_books = {_text(book).lower() for book in row_books if _text(book)}
        else:
            summaries = metadata.get("book_summaries") if isinstance(metadata.get("book_summaries"), dict) else {}
            reported_books = {_text(book).lower() for book in summaries if _text(book)}
        if reported != derived or reported_books != set(by_book):
            reasons.append("provider_evidence_conflict")
        provider_stats[provider] = {**derived, "books_seen": sorted(by_book)}

    if not evidence_window.get("ready"):
        reasons.append("candidate_observations_pending")
    directions = set()
    for stats in provider_stats.values():
        toward = stats["toward_pick_count"]
        away = stats["away_from_pick_count"]
        if toward > away:
            directions.add("toward")
        elif away > toward:
            directions.add("away")
    if directions == {"toward", "away"}:
        reasons.append("provider_disagreement")

    books = {
        book
        for stats in provider_stats.values()
        for book in stats["books_seen"]
    }
    toward_count = sum(stats["toward_pick_count"] for stats in provider_stats.values())
    away_count = sum(stats["away_from_pick_count"] for stats in provider_stats.values())
    reason_codes = list(dict.fromkeys(reasons))
    observations = sorted(
        [
            {"id": row.get("id"), "observed_at": row.get("observed_at")}
            for row in evidence_window.get("bound_observations", [])
            if isinstance(row, dict)
        ],
        key=lambda row: (_text(row.get("observed_at")), _text(row.get("id"))),
    )
    return {
        "provider": posture,
        "declared_providers": sorted(declared),
        "candidate_identity": {
            "slate_date": candidate.get("slate_date"),
            "game_time": candidate.get("game_time"),
            "pitcher": candidate.get("normalized_pitcher"),
            "side": candidate.get("side"),
            "k_line": candidate.get("model_k_line"),
            "provider": posture,
        },
        "candidate_became_current_at": evidence_window.get("first_current_at"),
        "observations": observations,
        "observation_ids": list(evidence_window.get("observation_ids", [])),
        "first_observed_at": evidence_window.get("first_observed_at"),
        "last_observed_at": evidence_window.get("last_observed_at"),
        "freshness_status": "fresh" if not reason_codes else "pending",
        "aggregation_reason_codes": reason_codes,
        "book_count": len(books),
        "books_seen": sorted(books),
        "toward_pick_count": toward_count,
        "away_from_pick_count": away_count,
        "side_price_movement": (
            "with_side" if toward_count > away_count else "against_side" if away_count > toward_count else "neutral"
        ),
        "broad_confirmation": len(books) >= 3,
        "reversal_book_count": sum(stats["reversal_book_count"] for stats in provider_stats.values()),
        "volatile_book_count": sum(stats["volatile_book_count"] for stats in provider_stats.values()),
        "best_is_off_market": False,
    }


def _evaluation_value(evaluation: Any, key: str, default: Any = None) -> Any:
    return evaluation.get(key, default) if isinstance(evaluation, dict) else getattr(evaluation, key, default)


def _family_states(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, Any] = {}
    for name, vote in value.items():
        if isinstance(vote, dict):
            result[str(name)] = vote
        else:
            result[str(name)] = {
                "state": getattr(vote, "state", "pending"),
                "reason_codes": list(getattr(vote, "reason_codes", ())),
            }
    return result


def build_provisional_row(
    *, candidate: dict[str, Any], evaluation: Any, evidence_window: dict[str, Any],
    artifact: dict[str, Any], observed_at: str,
) -> dict[str, Any] | None:
    """Build a current provisional row, or stop once frozen/start-invalid."""
    checkpoint, start = _utc(observed_at), _utc(candidate.get("game_time"))
    payload = artifact.get("payload") if isinstance(artifact, dict) else None
    canonical_sha = canonical_payload_sha256(payload) if payload is not None else None
    expected_sha = _hash(artifact.get("payload_sha256")) if isinstance(artifact, dict) else None
    byte_sha = _hash(artifact.get("byte_sha256")) if isinstance(artifact, dict) else None
    lane = _evaluation_value(evaluation, "lane")
    selector_fingerprint = _hash(_evaluation_value(evaluation, "selector_fingerprint"))
    if (not _candidate_is_canonical(candidate) or checkpoint is None or start is None or checkpoint >= start
            or candidate.get("frozen_exists") or _text(artifact.get("path")) != APPROVED_ARTIFACT_PATH
            or canonical_sha != expected_sha or byte_sha is None or selector_fingerprint is None):
        return None
    inputs = _evaluation_value(evaluation, "normalized_inputs", {}) or {}
    reason_codes = list(_evaluation_value(evaluation, "reason_codes", ()) or ())
    reason_codes.extend((evidence_window or {}).get("reason_codes", ()) or ())
    return {
        **{key: candidate[key] for key in (
            "slate_date", "game_identity", "candidate_identity", "pitcher", "normalized_pitcher",
            "team", "opp_team", "game_time", "side", "model_k_line", "provider_posture",
        )},
        "bundle_id": BUNDLE_ID,
        "selector_id": SELECTOR_IDS_BY_LANE.get(lane),
        "selector_fingerprint": selector_fingerprint,
        "checkpoint": "provisional",
        "candidate_became_current_at": (
            _iso((evidence_window or {}).get("first_current_at")) or checkpoint.isoformat()
        ),
        "official_odds": inputs.get("odds"),
        "official_book": inputs.get("official_book"),
        "official_verdict": inputs.get("official_verdict"),
        "lane": lane,
        "selection_status": _evaluation_value(evaluation, "selection_status", "pending"),
        "family_states": _family_states(_evaluation_value(evaluation, "family_states", {})),
        "family_count": _evaluation_value(evaluation, "family_count", 0),
        "reason_codes": list(dict.fromkeys(reason_codes)),
        "source_artifact_path": _text(artifact.get("path")),
        "source_artifact_generated_at": _iso(artifact.get("generated_at")),
        "source_artifact_sha256": canonical_sha,
        "source_artifact_byte_sha256": byte_sha,
        "lock_artifact_sha256": None,
        "lock_source_artifact_path": None,
        "evidence_observation_ids": list((evidence_window or {}).get("observation_ids", [])),
        "evidence_observation_count": int((evidence_window or {}).get("observation_count", 0)),
        "evidence_first_observed_at": (evidence_window or {}).get("first_observed_at"),
        "evidence_last_observed_at": (evidence_window or {}).get("last_observed_at"),
        "evidence_freshness_status": (evidence_window or {}).get("freshness_status", "pending"),
        "observed_at": checkpoint.isoformat(),
        "frozen_at": None,
        "lock_dedupe_key": None,
        "locked_at": None,
        "should_lock_at": None,
        "minutes_until_start": None,
        "lock_status": None,
    }


def lock_matches_candidate(lock_row: dict[str, Any], candidate: dict[str, Any], artifact_sha256: str) -> bool:
    """Validate every frozen-link field; lock dedupe is lookup-only."""
    if (not isinstance(lock_row, dict) or not _candidate_is_canonical(candidate)
            or _hash(artifact_sha256) is None
            or not _text(candidate.get("lock_source_artifact_path"))):
        return False
    expected_dedupe = f"{candidate.get('slate_date')}:{candidate.get('normalized_pitcher')}:{candidate.get('side')}"
    metadata = lock_row.get("metadata") if isinstance(lock_row.get("metadata"), dict) else {}
    return all((
        _text(lock_row.get("dedupe_key")) == expected_dedupe,
        _text(lock_row.get("slate_date")) == _text(candidate.get("slate_date")),
        normalize(_text(lock_row.get("normalized_pitcher"))) == _text(candidate.get("normalized_pitcher")),
        _text(lock_row.get("side")).lower() == _text(candidate.get("side")).lower(),
        _line(lock_row.get("locked_k_line")) == _line(candidate.get("model_k_line")),
        _integer(lock_row.get("locked_odds")) == _integer(candidate.get("official_odds")),
        _text(lock_row.get("locked_book")).lower() == _text(candidate.get("official_book")).lower(),
        _iso(lock_row.get("game_time")) == _iso(candidate.get("game_time")),
        _text(metadata.get("team")).upper() == _text(candidate.get("team")).upper(),
        _text(metadata.get("opp_team")).upper() == _text(candidate.get("opp_team")).upper(),
        _text(lock_row.get("source_artifact_path")) == _text(candidate.get("lock_source_artifact_path")),
        _hash(lock_row.get("source_artifact_sha256")) == _hash(artifact_sha256),
    ))


def frozen_link_reason(*, provisional_row: dict[str, Any], lock_row: dict[str, Any], observed_at: str) -> str | None:
    candidate = {key: provisional_row.get(key) for key in (
        "slate_date", "pitcher", "normalized_pitcher", "side", "model_k_line", "game_time", "team", "opp_team",
        "provider_posture", "game_identity", "candidate_identity", "source_artifact_path",
        "official_odds", "official_book",
    )}
    checkpoint, start = _utc(observed_at), _utc(candidate["game_time"])
    locked_at, lock_observed_at = _utc(lock_row.get("locked_at")), _utc(lock_row.get("observed_at"))
    if checkpoint is None or start is None or checkpoint >= start:
        return "post_start"
    if not _candidate_is_canonical(candidate):
        return "candidate_identity_invalid"
    if _text(lock_row.get("status_at_capture")) not in {"due_now", "missed_lock"}:
        return "lock_status_invalid"
    if (locked_at != checkpoint or lock_observed_at != checkpoint
            or _utc(provisional_row.get("observed_at")) != checkpoint):
        return "missed_freeze"
    should_lock_at = _utc(lock_row.get("should_lock_at"))
    minutes_until_start = _nonnegative_number(lock_row.get("minutes_until_start"))
    if should_lock_at is None or minutes_until_start is None or should_lock_at > locked_at or should_lock_at >= start:
        return "lock_timing_invalid"
    saved_lock_source_path = _text(provisional_row.get("lock_source_artifact_path"))
    lock_source_path = _text(lock_row.get("source_artifact_path"))
    if saved_lock_source_path and saved_lock_source_path != lock_source_path:
        return "lock_mismatch"
    candidate["lock_source_artifact_path"] = lock_source_path
    if not lock_matches_candidate(
        lock_row, candidate, _text(provisional_row.get("source_artifact_byte_sha256")),
    ):
        return "lock_mismatch"
    return None


def build_frozen_row(*, provisional_row: dict[str, Any], lock_row: dict[str, Any], observed_at: str) -> dict[str, Any] | None:
    """Copy an already-evaluated provisional row into immutable lock state."""
    if not isinstance(provisional_row, dict) or not isinstance(lock_row, dict):
        return None
    if frozen_link_reason(provisional_row=provisional_row, lock_row=lock_row, observed_at=observed_at):
        return None
    frozen = {**provisional_row}
    frozen.update({
        "checkpoint": "frozen_pregame",
        "frozen_at": _iso(lock_row.get("locked_at")),
        "lock_dedupe_key": lock_row.get("dedupe_key"),
        "lock_artifact_sha256": _hash(lock_row.get("source_artifact_sha256")),
        "lock_source_artifact_path": _text(lock_row.get("source_artifact_path")),
        "locked_at": _iso(lock_row.get("locked_at")),
        "should_lock_at": _iso(lock_row.get("should_lock_at")),
        "minutes_until_start": lock_row.get("minutes_until_start"),
        "lock_status": lock_row.get("status_at_capture"),
    })
    return frozen


def frozen_insert_on_conflict() -> str:
    """The recorder must use this insert-ignore key for frozen rows."""
    return ",".join(UNIQUE_COLUMNS)
