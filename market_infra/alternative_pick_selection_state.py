"""Pure, bounded state shaping for the default-off alternative-picks recorder.

This module deliberately keeps the canonical published-payload hash separate
from the exact fetched-artifact hash used by ``operational_pick_locks``.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from market_infra.alternative_pick_selector import BUNDLE_ID
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
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


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
    if start is None or checkpoint is None:
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
    valid_candidate = all((
        _text(candidate.get("slate_date")), _text(candidate.get("normalized_pitcher")),
        candidate.get("side") in {"over", "under"}, candidate.get("model_k_line") is not None,
        _text(candidate.get("team")), _text(candidate.get("opp_team")), start is not None,
        candidate.get("provider_posture") in SUPPORTED_PROVIDER_POSTURES,
    ))
    if (not valid_candidate or checkpoint is None or start is None or checkpoint >= start
            or candidate.get("frozen_exists") or canonical_sha != expected_sha or byte_sha is None):
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
        "selector_id": _evaluation_value(evaluation, "selector_fingerprint"),
        "checkpoint": "provisional",
        "official_odds": inputs.get("odds"),
        "official_book": inputs.get("official_book"),
        "official_verdict": inputs.get("official_verdict"),
        "lane": _evaluation_value(evaluation, "lane"),
        "selection_status": _evaluation_value(evaluation, "selection_status", "pending"),
        "family_states": _family_states(_evaluation_value(evaluation, "family_states", {})),
        "family_count": _evaluation_value(evaluation, "family_count", 0),
        "reason_codes": list(dict.fromkeys(reason_codes)),
        "source_artifact_path": _text(artifact.get("path")),
        "source_artifact_generated_at": _iso(artifact.get("generated_at")),
        "source_artifact_sha256": canonical_sha,
        "source_artifact_byte_sha256": byte_sha,
        "lock_artifact_sha256": None,
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
    if not isinstance(lock_row, dict) or _hash(artifact_sha256) is None:
        return False
    expected_dedupe = f"{candidate.get('slate_date')}:{candidate.get('normalized_pitcher')}:{candidate.get('side')}"
    metadata = lock_row.get("metadata") if isinstance(lock_row.get("metadata"), dict) else {}
    return all((
        _text(lock_row.get("dedupe_key")) == expected_dedupe,
        _text(lock_row.get("slate_date")) == _text(candidate.get("slate_date")),
        normalize(_text(lock_row.get("normalized_pitcher"))) == _text(candidate.get("normalized_pitcher")),
        _text(lock_row.get("side")).lower() == _text(candidate.get("side")).lower(),
        _line(lock_row.get("locked_k_line")) == _line(candidate.get("model_k_line")),
        _iso(lock_row.get("game_time")) == _iso(candidate.get("game_time")),
        _text(metadata.get("team")).upper() == _text(candidate.get("team")).upper(),
        _text(metadata.get("opp_team")).upper() == _text(candidate.get("opp_team")).upper(),
        _hash(lock_row.get("source_artifact_sha256")) == _hash(artifact_sha256),
    ))


def frozen_link_reason(*, provisional_row: dict[str, Any], lock_row: dict[str, Any], observed_at: str) -> str | None:
    candidate = {key: provisional_row.get(key) for key in (
        "slate_date", "normalized_pitcher", "side", "model_k_line", "game_time", "team", "opp_team",
    )}
    checkpoint, start, locked_at = _utc(observed_at), _utc(candidate["game_time"]), _utc(lock_row.get("locked_at"))
    if checkpoint is None or start is None or checkpoint >= start:
        return "post_start"
    if _text(lock_row.get("status_at_capture")) not in {"due_now", "missed_lock"}:
        return "lock_status_invalid"
    if locked_at != checkpoint or _utc(provisional_row.get("observed_at")) != checkpoint:
        return "missed_freeze"
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
        "locked_at": _iso(lock_row.get("locked_at")),
        "should_lock_at": _iso(lock_row.get("should_lock_at")),
        "minutes_until_start": lock_row.get("minutes_until_start"),
        "lock_status": lock_row.get("status_at_capture"),
    })
    return frozen


def frozen_insert_on_conflict() -> str:
    """The recorder must use this insert-ignore key for frozen rows."""
    return ",".join(UNIQUE_COLUMNS)
