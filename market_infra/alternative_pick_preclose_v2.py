"""Exact, in-memory Preclose evidence for the dependency-aware V2 selector."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from uuid import UUID

from market_infra.current_market_lines import normalize_market_key
from market_infra.live_market_display import (
    ACTIVE_PROVIDERS,
    MAIN_BOOKS,
    build_exact_event_book_ladder,
)
from market_infra.provider_freshness import (
    effective_book_freshness,
    normalize_book_key,
    provider_heartbeat_health,
)
from pipeline.name_utils import normalize


PROOF_SCHEMA_VERSION = "alternative_pick_preclose_v2"


@dataclass(frozen=True)
class ExactPrecloseResult:
    market_evidence: dict[str, Any]
    evidence_window: dict[str, Any]
    proof_fragment: dict[str, Any]


def _text(value: Any) -> str:
    return str(value or "").strip()


def _provider(value: Any) -> str:
    return _text(value).lower()


def _side(value: Any) -> str:
    return _text(value).lower()


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _integer(value: Any) -> int | None:
    parsed = _number(value)
    return int(parsed) if parsed is not None and parsed.is_integer() else None


def _utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        text = _text(value)
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: Any) -> str | None:
    parsed = _utc(value)
    return parsed.isoformat() if parsed is not None else None


def _values(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple, set)) else []


def _unique(values: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _current_line_id(value: Any) -> str | None:
    if isinstance(value, bool):
        return None
    maximum = 2**63 - 1
    if isinstance(value, int):
        return str(value) if 0 < value <= maximum else None
    if isinstance(value, str):
        text = value.strip()
        if not text.isascii() or not text.isdigit():
            return None
        parsed = int(text)
        return text if 0 < parsed <= maximum else None
    if isinstance(value, float) and math.isfinite(value) and value.is_integer() and 0 < value <= 2**53 - 1:
        return str(int(value))
    return None


def _snapshot_uuid(value: Any) -> str | None:
    text = _text(value)
    try:
        parsed = UUID(text)
    except (ValueError, TypeError, AttributeError):
        return None
    canonical = str(parsed)
    return canonical if text == canonical else None


def artifact_current_line_ids_v2(pitcher: Mapping[str, Any]) -> tuple[str, ...]:
    """Return exact bigint current-line IDs without conflating snapshot UUIDs."""
    ids: list[str] = []
    for field in ("source_current_market_line_ids", "source_line_ids", "source_snapshot_ids"):
        for value in _values(pitcher.get(field)):
            identifier = _current_line_id(value)
            if identifier is not None:
                ids.append(identifier)
    return tuple(_unique(ids))


def _artifact_seed_snapshot_ids(pitcher: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(_unique([
        identifier
        for value in _values(pitcher.get("source_snapshot_ids"))
        if (identifier := _snapshot_uuid(value)) is not None
    ]))


def _binding_key(binding: Mapping[str, Any], candidate: Mapping[str, Any]) -> str:
    payload = {
        "provider": binding.get("provider"),
        "provider_event_id": binding.get("provider_event_id"),
        "current_line_ids": binding.get("current_line_ids", []),
        "seed_snapshot_ids": binding.get("seed_snapshot_ids", []),
        "candidate_identity": candidate.get("candidate_identity"),
        "side": candidate.get("side"),
        "model_k_line": _number(candidate.get("model_k_line")),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _snapshot_semantics_match(
    row: Mapping[str, Any], *, candidate: Mapping[str, Any], provider: str,
    provider_event_id: str, snapshot_id: str,
) -> bool:
    return all((
        _snapshot_uuid(row.get("id")) == snapshot_id,
        _provider(row.get("provider")) == provider,
        _text(row.get("provider_event_id")) == provider_event_id,
        bool(_text(row.get("slate_date"))),
        _text(row.get("slate_date")) == _text(candidate.get("slate_date")),
        normalize(_text(row.get("normalized_player_name") or row.get("player_name")))
        == _text(candidate.get("normalized_pitcher")),
        normalize_market_key(row.get("market_key")) == "pitcher_strikeouts",
        _side(row.get("side")) == _side(candidate.get("side")),
        _number(row.get("line")) == _number(candidate.get("model_k_line")),
        normalize_book_key(row.get("bookmaker_key") or row.get("bookmaker_title")) in MAIN_BOOKS,
    ))


def resolve_candidate_bindings_v2(
    *, candidate: Mapping[str, Any], pitcher: Mapping[str, Any],
    current_lines_by_id: Mapping[str, Mapping[str, Any]],
    snapshot_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Resolve official and optional sidecar bindings through exact artifact sources."""
    official_provider = _provider(pitcher.get("line_source_provider")) or None
    reasons: list[str] = []
    if official_provider not in ACTIVE_PROVIDERS:
        reasons.append("official_provider_missing" if official_provider is None else "official_provider_unsupported")
        official_provider = None

    line_ids = artifact_current_line_ids_v2(pitcher)
    direct_seed_ids = set(_artifact_seed_snapshot_ids(pitcher))
    current_line_lookup = {
        identifier: row
        for key, row in current_lines_by_id.items()
        if (identifier := _current_line_id(key)) is not None
    }
    snapshots_by_token, conflicting_tokens = _group_snapshot_rows(snapshot_rows)
    candidates_by_provider: dict[str, list[dict[str, Any]]] = {}
    candidate_side_snapshot_tokens: set[tuple[str, str]] = set()
    candidate_bound_events: dict[str, set[str]] = {}
    current_line_source_providers: set[str] = set()
    for line_id in line_ids:
        row = current_line_lookup.get(line_id)
        if not isinstance(row, Mapping):
            reasons.append("current_line_missing")
            continue
        provider = _provider(row.get("provider"))
        if provider in ACTIVE_PROVIDERS:
            current_line_source_providers.add(provider)
        event_id = _text(row.get("provider_event_id"))
        mapped_time = _utc(row.get("game_time"))
        exact_line = all((
            _current_line_id(row.get("id")) == line_id,
            _text(row.get("slate_date")) == _text(candidate.get("slate_date")),
            provider in ACTIVE_PROVIDERS,
            bool(event_id),
            normalize(_text(row.get("normalized_player_name") or row.get("player_name")))
            == _text(candidate.get("normalized_pitcher")),
            normalize_market_key(row.get("market_key")) == "pitcher_strikeouts",
            _number(row.get("line")) == _number(candidate.get("model_k_line")),
            mapped_time is not None,
        ))
        if not exact_line:
            reasons.append("current_line_mismatch")
            continue
        snapshot_id = _snapshot_uuid(row.get(f"{_side(candidate.get('side'))}_snapshot_id"))
        if snapshot_id is not None:
            candidate_side_snapshot_tokens.add((provider, snapshot_id))
        candidate_bound_events.setdefault(provider, set()).add(event_id)
        snapshot = snapshots_by_token.get((provider, snapshot_id)) if snapshot_id else None
        if snapshot_id is None or snapshot is None or not _snapshot_semantics_match(
            snapshot, candidate=candidate, provider=provider,
            provider_event_id=event_id, snapshot_id=snapshot_id,
        ):
            reasons.append("side_snapshot_mismatch")
            continue
        candidates_by_provider.setdefault(provider, []).append({
            "provider": provider,
            "provider_event_id": event_id,
            "current_line_id": line_id,
            "seed_snapshot_id": snapshot_id,
            "mapped_game_time": _iso(row.get("game_time")),
        })

    declared_events: dict[str, set[str]] = {
        "therundown": {
            _text(pitcher.get(field)) for field in
            ("therundown_event_id", "rundown_event_id", "the_rundown_event_id")
            if _text(pitcher.get(field))
        },
        "propline": {
            _text(pitcher.get("propline_event_id"))
        } if _text(pitcher.get("propline_event_id")) else set(),
    }
    generic_event = _text(pitcher.get("provider_event_id"))
    if official_provider and generic_event:
        declared_events.setdefault(official_provider, set()).add(generic_event)
    artifact_seed_tokens = {
        (provider, identifier)
        for row in snapshot_rows
        if (identifier := _snapshot_uuid(row.get("id"))) in direct_seed_ids
        and (provider := _provider(row.get("provider"))) in ACTIVE_PROVIDERS
        and (event_id := _text(row.get("provider_event_id")))
        and (not declared_events.get(provider) or event_id in declared_events[provider])
        and _snapshot_semantics_match(
            row, candidate=candidate, provider=provider,
            provider_event_id=event_id, snapshot_id=identifier,
        )
    }
    artifact_seed_source_providers = {
        _provider(row.get("provider"))
        for row in snapshot_rows
        if _snapshot_uuid(row.get("id")) in direct_seed_ids
        and _provider(row.get("provider")) in ACTIVE_PROVIDERS
    }
    for seed_id in direct_seed_ids:
        matches = [
            (provider, row) for (provider, identifier), row in snapshots_by_token.items()
            if identifier == seed_id and provider in ACTIVE_PROVIDERS
        ]
        for provider, snapshot in matches:
            event_id = _text(snapshot.get("provider_event_id"))
            if declared_events.get(provider) and event_id not in declared_events[provider]:
                continue
            if not event_id or not _snapshot_semantics_match(
                snapshot, candidate=candidate, provider=provider,
                provider_event_id=event_id, snapshot_id=seed_id,
            ):
                continue
            candidates_by_provider.setdefault(provider, []).append({
                "provider": provider,
                "provider_event_id": event_id,
                "current_line_id": "",
                "seed_snapshot_id": seed_id,
                "mapped_game_time": _iso(snapshot.get("game_time")) or _iso(candidate.get("game_time")),
            })

    for provider in sorted(ACTIVE_PROVIDERS):
        events = set(declared_events.get(provider, set()))
        if len(events) > 1:
            reasons.append(f"{provider}_binding_conflict")
            continue
        if (
            len(events) != 1
            or provider in candidates_by_provider
            or provider in candidate_bound_events
            or provider in current_line_source_providers
            or provider in artifact_seed_source_providers
        ):
            continue
        event_id = next(iter(events))
        candidate_bound_events.setdefault(provider, set()).add(event_id)
        event_rows = [
            snapshot
            for (snapshot_provider, snapshot_id), snapshot in snapshots_by_token.items()
            if snapshot_provider == provider
            and _snapshot_semantics_match(
                snapshot, candidate=candidate, provider=provider,
                provider_event_id=event_id, snapshot_id=snapshot_id,
            )
        ]
        for snapshot in event_rows:
            candidates_by_provider.setdefault(provider, []).append({
                "provider": provider,
                "provider_event_id": event_id,
                "current_line_id": "",
                "seed_snapshot_id": "",
                "mapped_game_time": _iso(snapshot.get("game_time")) or _iso(candidate.get("game_time")),
            })

    relevant_conflicting_tokens = _candidate_relevant_conflicts(
        conflicts=conflicting_tokens,
        candidate=candidate,
        direct_seed_tokens=artifact_seed_tokens,
        side_snapshot_tokens=candidate_side_snapshot_tokens,
        bound_events=candidate_bound_events,
    )
    if relevant_conflicting_tokens:
        reasons.append("duplicate_snapshot_conflict")

    bindings_by_provider: dict[str, dict[str, Any]] = {}
    for provider, rows in candidates_by_provider.items():
        events = {
            _text(row.get("provider_event_id")) for row in rows
        } | set(declared_events.get(provider, set()))
        if len(events) != 1:
            reasons.append(f"{provider}_binding_conflict")
            continue
        event_id = next(iter(events))
        binding = {
            "provider": provider,
            "provider_event_id": event_id,
            "current_line_ids": sorted({_text(row["current_line_id"]) for row in rows if _text(row["current_line_id"])}),
            "seed_snapshot_ids": sorted({_text(row["seed_snapshot_id"]) for row in rows if _text(row["seed_snapshot_id"])}),
            "mapped_game_times": sorted({_text(row["mapped_game_time"]) for row in rows}),
        }
        extra_seeds = [
            seed_id for seed_id in direct_seed_ids
            if (seed := snapshots_by_token.get((provider, seed_id))) is not None
            and _snapshot_semantics_match(
                seed, candidate=candidate, provider=provider,
                provider_event_id=event_id, snapshot_id=seed_id,
            )
        ]
        binding["seed_snapshot_ids"] = sorted(set(binding["seed_snapshot_ids"]) | set(extra_seeds))
        binding["binding_key"] = _binding_key(binding, candidate)
        bindings_by_provider[provider] = binding

    official_binding = bindings_by_provider.get(official_provider or "")
    if official_provider and official_binding is None:
        reasons.append("official_binding_missing")
    sidecar_bindings = {
        provider: binding for provider, binding in bindings_by_provider.items()
        if provider != official_provider
    }
    return {
        "ready": official_binding is not None and not relevant_conflicting_tokens,
        "official_provider": official_provider,
        "official_binding": official_binding,
        "official_binding_key": official_binding.get("binding_key") if official_binding else None,
        "sidecar_bindings": sidecar_bindings,
        "sidecar_binding_keys": {
            provider: binding["binding_key"] for provider, binding in sidecar_bindings.items()
        },
        "bindings_by_provider": bindings_by_provider,
        "reason_codes": tuple(dict.fromkeys(reasons)),
    }


def _proof_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def resolve_candidate_windows_v2(
    *, candidate: Mapping[str, Any], bindings: Mapping[str, Any],
    existing_state_row: Mapping[str, Any] | None,
    observed_at: datetime | str,
) -> dict[str, Any]:
    checkpoint = _iso(observed_at)
    if checkpoint is None:
        return {"ready": False, "reason_codes": ("evaluation_time_invalid",)}
    row = existing_state_row if isinstance(existing_state_row, Mapping) else {}
    proof = _proof_object(row.get("evaluation_proof"))
    prior = proof.get("exact_preclose") if isinstance(proof.get("exact_preclose"), dict) else {}
    same_candidate = _text(row.get("candidate_identity")) == _text(candidate.get("candidate_identity"))
    prior_start = _iso(row.get("candidate_became_current_at"))
    official_unchanged = bool(
        same_candidate and prior_start
        and _text(prior.get("official_binding_key"))
        == _text(bindings.get("official_binding_key"))
        and _text(bindings.get("official_binding_key"))
    )
    candidate_start = prior_start if official_unchanged else checkpoint
    official_provider = _provider(bindings.get("official_provider"))
    prior_provider_starts = prior.get("provider_window_started_at")
    if not isinstance(prior_provider_starts, dict):
        prior_provider_starts = {}
    provider_starts: dict[str, str] = {}
    if official_provider:
        provider_starts[official_provider] = (
            _iso(prior_provider_starts.get(official_provider)) or candidate_start
            if official_unchanged else checkpoint
        )
    prior_sidecars = prior.get("sidecar_binding_keys")
    if not isinstance(prior_sidecars, dict):
        prior_sidecars = {}
    for provider, key in (bindings.get("sidecar_binding_keys") or {}).items():
        unchanged = official_unchanged and _text(prior_sidecars.get(provider)) == _text(key)
        provider_starts[provider] = (
            _iso(prior_provider_starts.get(provider)) or candidate_start
            if unchanged else checkpoint
        )
    return {
        "ready": bool(bindings.get("ready")),
        "candidate_became_current_at": candidate_start,
        "provider_window_started_at": provider_starts,
        "official_binding_changed": bool(same_candidate and prior_start and not official_unchanged),
        "reason_codes": () if bindings.get("ready") else ("official_binding_pending",),
    }


def _snapshot_signature(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        _provider(row.get("provider")), _text(row.get("slate_date")),
        _text(row.get("provider_event_id")),
        normalize(_text(row.get("normalized_player_name") or row.get("player_name"))),
        normalize_market_key(row.get("market_key")), _side(row.get("side")),
        _number(row.get("line")), normalize_book_key(row.get("bookmaker_key") or row.get("bookmaker_title")),
        _integer(row.get("american_odds")), _iso(row.get("observed_at")), _iso(row.get("game_time")),
    )


def _group_snapshot_rows(
    rows: Sequence[Mapping[str, Any]],
) -> tuple[
    dict[tuple[str, str], Mapping[str, Any]],
    dict[tuple[str, str], tuple[Mapping[str, Any], ...]],
]:
    """Pre-group provider-qualified UUIDs and invalidate every content collision."""
    grouped: dict[tuple[str, str], list[tuple[tuple[Any, ...], Mapping[str, Any]]]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        provider = _provider(row.get("provider"))
        identifier = _snapshot_uuid(row.get("id"))
        if not provider or identifier is None:
            continue
        grouped.setdefault((provider, identifier), []).append((_snapshot_signature(row), row))

    conflicting = {
        token: tuple(row for _signature, row in values)
        for token, values in grouped.items()
        if len({signature for signature, _row in values}) > 1
    }
    representatives = {
        token: values[0][1] for token, values in grouped.items()
        if token not in conflicting
    }
    return representatives, conflicting


def _candidate_relevant_conflicts(
    *,
    conflicts: Mapping[tuple[str, str], Sequence[Mapping[str, Any]]],
    candidate: Mapping[str, Any],
    direct_seed_tokens: set[tuple[str, str]],
    side_snapshot_tokens: set[tuple[str, str]],
    bound_events: Mapping[str, set[str]],
) -> set[tuple[str, str]]:
    relevant: set[tuple[str, str]] = set()
    for token, versions in conflicts.items():
        provider, _identifier = token
        if token in direct_seed_tokens or token in side_snapshot_tokens:
            relevant.add(token)
            continue
        provider_events = bound_events.get(provider, set())
        if not provider_events:
            continue
        if any(
            _text(row.get("slate_date")) == _text(candidate.get("slate_date"))
            and _text(row.get("provider_event_id")) in provider_events
            and normalize(_text(row.get("normalized_player_name") or row.get("player_name")))
            == _text(candidate.get("normalized_pitcher"))
            and _side(row.get("side")) == _side(candidate.get("side"))
            and normalize_market_key(row.get("market_key")) == "pitcher_strikeouts"
            and normalize_book_key(row.get("bookmaker_key") or row.get("bookmaker_title")) in MAIN_BOOKS
            for row in versions
        ):
            relevant.add(token)
    return relevant


def _coalesce_exact_checkpoints(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return one deterministic row per exact book/line/timestamp checkpoint.

    Identical semantic duplicates collapse to a single identity. Conflicting
    prices at the same exact checkpoint contribute no observation, so neither
    UUID order nor input order can invent movement or ladder state.
    """
    grouped: dict[tuple[Any, ...], list[Mapping[str, Any]]] = {}
    for row in rows:
        key = (
            _provider(row.get("provider")),
            _text(row.get("provider_event_id")),
            normalize(_text(row.get("normalized_player_name") or row.get("player_name"))),
            normalize_market_key(row.get("market_key")),
            _side(row.get("side")),
            _number(row.get("line")),
            normalize_book_key(row.get("bookmaker_key") or row.get("bookmaker_title")),
            _iso(row.get("observed_at")),
        )
        grouped.setdefault(key, []).append(row)

    checkpoints: list[dict[str, Any]] = []
    for values in grouped.values():
        prices = {_integer(row.get("american_odds")) for row in values}
        if None in prices or len(prices) != 1:
            continue
        representative = min(values, key=lambda row: _text(row.get("id")))
        checkpoints.append(dict(representative))
    return sorted(
        checkpoints,
        key=lambda row: (
            _utc(row.get("observed_at")),
            _provider(row.get("provider")),
            normalize_book_key(row.get("bookmaker_key") or row.get("bookmaker_title")),
            _number(row.get("line")),
            _text(row.get("id")),
        ),
    )


def _direction(ordered: Sequence[Mapping[str, Any]]) -> tuple[str, bool]:
    first = _integer(ordered[0].get("american_odds"))
    last = _integer(ordered[-1].get("american_odds"))
    direction = "toward" if last < first else "away" if last > first else "neutral"
    steps: list[str] = []
    for previous, current in zip(ordered, ordered[1:]):
        prior_odds = _integer(previous.get("american_odds"))
        current_odds = _integer(current.get("american_odds"))
        if current_odds == prior_odds:
            continue
        steps.append("toward" if current_odds < prior_odds else "away")
    reversal = any(left != right for left, right in zip(steps, steps[1:]))
    return direction, reversal


def _direction_change_pivot_tokens(
    ordered: Sequence[Mapping[str, Any]], *, provider: str,
) -> list[str]:
    pivots: list[str] = []
    previous_direction: str | None = None
    for previous, current in zip(ordered, ordered[1:]):
        prior_odds = _integer(previous.get("american_odds"))
        current_odds = _integer(current.get("american_odds"))
        if current_odds == prior_odds:
            continue
        direction = "toward" if current_odds < prior_odds else "away"
        if previous_direction is not None and direction != previous_direction:
            pivots.append(f"{provider}:{_text(current.get('id'))}")
        previous_direction = direction
    return pivots


def _pending_evidence(
    *, candidate: Mapping[str, Any], official_provider: str | None,
    windows: Mapping[str, Any], reasons: Sequence[str], observations: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "provider": official_provider,
        "participating_providers": [],
        "candidate_identity": {
            "slate_date": candidate.get("slate_date"), "game_time": _iso(candidate.get("game_time")),
            "pitcher": candidate.get("normalized_pitcher"), "side": candidate.get("side"),
            "k_line": _number(candidate.get("model_k_line")), "provider": official_provider,
        },
        "candidate_became_current_at": windows.get("candidate_became_current_at"),
        "observations": list(observations),
        "observation_ids": [row["id"] for row in observations],
        "first_observed_at": observations[0]["observed_at"] if observations else None,
        "last_observed_at": observations[-1]["observed_at"] if observations else None,
        "freshness_status": "pending",
        "aggregation_reason_codes": list(dict.fromkeys(reasons)),
        "book_count": None, "books_seen": [], "toward_pick_count": None,
        "away_from_pick_count": None, "side_price_movement": None,
        "broad_confirmation": None, "reversal_book_count": None,
        "volatile_book_count": None, "best_is_off_market": None,
    }


def build_exact_preclose_evidence_v2(
    *, candidate: Mapping[str, Any], bindings: Mapping[str, Any],
    windows: Mapping[str, Any], snapshot_rows: Sequence[Mapping[str, Any]],
    provider_heartbeats: Sequence[Mapping[str, Any]],
    observed_at: datetime | str, source_artifact_path: str,
    source_artifact_byte_sha256: str, stale_after_seconds: int = 900,
) -> ExactPrecloseResult:
    checkpoint = _utc(observed_at)
    game_time = _utc(candidate.get("game_time"))
    official_provider = _provider(bindings.get("official_provider")) or None
    reasons: list[str] = []
    if not bindings.get("ready") or not official_provider:
        reasons.append("official_binding_pending")
    if "duplicate_snapshot_conflict" in _values(bindings.get("reason_codes")):
        reasons.append("duplicate_snapshot_conflict")
    if checkpoint is None or game_time is None or checkpoint >= game_time:
        reasons.append("pregame_checkpoint_invalid")
    provider_starts = windows.get("provider_window_started_at")
    if not isinstance(provider_starts, Mapping):
        provider_starts = {}
        reasons.append("candidate_window_missing")
    bindings_by_provider = bindings.get("bindings_by_provider")
    if not isinstance(bindings_by_provider, Mapping):
        bindings_by_provider = {}

    provider_health = provider_heartbeat_health(
        list(provider_heartbeats), checkpoint or datetime.now(timezone.utc), stale_after_seconds,
    )
    exact_event_rows: dict[str, list[dict[str, Any]]] = {}
    normalized_rows, conflicting_tokens = _group_snapshot_rows(snapshot_rows)
    bound_events = {
        provider: {_text(binding.get("provider_event_id"))}
        for provider, binding in bindings_by_provider.items()
        if isinstance(binding, Mapping) and _text(binding.get("provider_event_id"))
    }
    bound_seed_tokens = {
        (provider, identifier)
        for provider, binding in bindings_by_provider.items()
        if isinstance(binding, Mapping)
        for value in _values(binding.get("seed_snapshot_ids"))
        if (identifier := _snapshot_uuid(value)) is not None
    }
    relevant_conflicting_tokens = _candidate_relevant_conflicts(
        conflicts=conflicting_tokens,
        candidate=candidate,
        direct_seed_tokens=bound_seed_tokens,
        side_snapshot_tokens=bound_seed_tokens,
        bound_events=bound_events,
    )
    if relevant_conflicting_tokens:
        reasons.append("duplicate_snapshot_conflict")
    for raw in normalized_rows.values():
        if not isinstance(raw, Mapping):
            continue
        provider = _provider(raw.get("provider"))
        binding = bindings_by_provider.get(provider)
        if not isinstance(binding, Mapping):
            continue
        if _text(raw.get("slate_date")) != _text(candidate.get("slate_date")):
            continue
        if _text(raw.get("provider_event_id")) != _text(binding.get("provider_event_id")):
            continue
        if normalize(_text(raw.get("normalized_player_name") or raw.get("player_name"))) != _text(candidate.get("normalized_pitcher")):
            continue
        if normalize_market_key(raw.get("market_key")) != "pitcher_strikeouts" or _side(raw.get("side")) != _side(candidate.get("side")):
            continue
        identifier = _snapshot_uuid(raw.get("id"))
        timestamp = _utc(raw.get("observed_at"))
        line = _number(raw.get("line"))
        odds = _integer(raw.get("american_odds"))
        book = normalize_book_key(raw.get("bookmaker_key") or raw.get("bookmaker_title"))
        start = _utc(provider_starts.get(provider))
        if not identifier or timestamp is None or line is None or odds is None or not book or book not in MAIN_BOOKS or start is None:
            continue
        if timestamp < start or checkpoint is None or timestamp > checkpoint or timestamp >= game_time:
            continue
        line_age = max(int((checkpoint - timestamp).total_seconds()), 0)
        freshness = effective_book_freshness(
            provider=provider, slate_date=_text(candidate.get("slate_date")),
            book_key=book, line_freshness_seconds=line_age,
            provider_health=provider_health, stale_after_seconds=stale_after_seconds,
        )
        if int(freshness["freshness_seconds"]) > stale_after_seconds:
            continue
        exact_event_rows.setdefault(provider, []).append({
            **dict(raw), "id": identifier, "provider": provider,
            "bookmaker_key": book, "line": line, "american_odds": odds,
            "observed_at": timestamp.isoformat(), "freshness": freshness,
        })

    exact_event_rows = {
        provider: _coalesce_exact_checkpoints(rows)
        for provider, rows in exact_event_rows.items()
    }

    provider_stats: dict[str, dict[str, Any]] = {}
    participating: list[str] = []
    for provider, binding in bindings_by_provider.items():
        movement_rows = [
            row for row in exact_event_rows.get(provider, [])
            if _number(row.get("line")) == _number(candidate.get("model_k_line"))
        ]
        movement_rows.sort(key=lambda row: (_utc(row.get("observed_at")), _text(row.get("id"))))
        ids = {row["id"] for row in movement_rows}
        times = {_iso(row["observed_at"]) for row in movement_rows}
        by_book: dict[str, list[dict[str, Any]]] = {}
        for row in movement_rows:
            by_book.setdefault(row["bookmaker_key"], []).append(row)
        mature = (
            len(ids) >= 2
            and len(times) >= 2
            and any(
                len({_iso(row.get("observed_at")) for row in rows}) >= 2
                for rows in by_book.values()
            )
        )
        if not mature:
            if provider == official_provider:
                reasons.append("official_provider_immature")
            continue
        participating.append(provider)
        directions: dict[str, str] = {}
        reversals: set[str] = set()
        direction_change_pivots: list[str] = []
        for book, rows in by_book.items():
            rows.sort(key=lambda row: _utc(row.get("observed_at")))
            direction, reversal = _direction(rows)
            directions[book] = direction
            if reversal:
                reversals.add(book)
            direction_change_pivots.extend(
                _direction_change_pivot_tokens(rows, provider=provider)
            )
        toward = sum(value == "toward" for value in directions.values())
        away = sum(value == "away" for value in directions.values())
        provider_stats[provider] = {
            "rows": movement_rows, "directions": directions,
            "reversal_books": reversals,
            "direction_change_pivots": direction_change_pivots,
            "majority": "toward" if toward > away else "away" if away > toward else "neutral",
        }

    if official_provider and official_provider not in participating and "official_provider_immature" not in reasons:
        reasons.append("official_provider_immature")
    non_neutral_majorities = {
        stats["majority"] for stats in provider_stats.values() if stats["majority"] != "neutral"
    }
    if non_neutral_majorities == {"toward", "away"}:
        reasons.append("provider_majority_disagreement")

    reconciled: dict[str, str] = {}
    reversals: set[str] = set()
    all_books = {
        book for stats in provider_stats.values() for book in stats["directions"]
    }
    for book in all_books:
        directions = {
            stats["directions"][book]
            for stats in provider_stats.values()
            if book in stats["directions"] and stats["directions"][book] != "neutral"
        }
        if directions == {"toward", "away"}:
            reasons.append("provider_book_disagreement")
            continue
        reconciled[book] = next(iter(directions)) if directions else "neutral"
        if any(book in stats["reversal_books"] for stats in provider_stats.values()):
            reversals.add(book)

    ladder_rows = [
        row for provider in participating for row in exact_event_rows.get(provider, [])
    ]
    ladder_observation_ids = [
        f"{row['provider']}:{row['id']}"
        for row in sorted(
            ladder_rows, key=lambda row: (_utc(row.get("observed_at")), _text(row.get("id")))
        )
    ]
    latest_ladder_observation_tokens = [
        f"{row['provider']}:{row['id']}"
        for row in sorted(
            {
                (row["provider"], row["bookmaker_key"]): row
                for row in sorted(
                    ladder_rows,
                    key=lambda item: (_utc(item.get("observed_at")), _text(item.get("id"))),
                )
            }.values(),
            key=lambda item: (item["provider"], item["bookmaker_key"]),
        )
    ]
    ladder = build_exact_event_book_ladder(
        slate_date=_text(candidate.get("slate_date")), side=_side(candidate.get("side")),
        pick_line=float(_number(candidate.get("model_k_line")) or 0),
        exact_event_snapshots=ladder_rows, observed_at=checkpoint or observed_at,
        provider_heartbeats=list(provider_heartbeats), stale_after_seconds=stale_after_seconds,
    ) if ladder_rows and _number(candidate.get("model_k_line")) is not None else None
    if ladder is None or ladder.get("freshness_status") != "fresh" or not isinstance(ladder.get("best_is_off_market"), bool):
        reasons.append("exact_ladder_missing")

    observation_rows = sorted(
        [row for stats in provider_stats.values() for row in stats["rows"]],
        key=lambda row: (_utc(row.get("observed_at")), _text(row.get("id"))),
    )
    observations = [
        {"id": f"{row['provider']}:{row['id']}", "observed_at": row["observed_at"]}
        for row in observation_rows
    ]
    reason_codes = list(dict.fromkeys(reasons))
    if reason_codes:
        market_evidence = _pending_evidence(
            candidate=candidate, official_provider=official_provider,
            windows=windows, reasons=reason_codes, observations=observations,
        )
    else:
        toward = sum(value == "toward" for value in reconciled.values())
        away = sum(value == "away" for value in reconciled.values())
        market_evidence = {
            "provider": official_provider,
            "participating_providers": sorted(participating),
            "candidate_identity": {
                "slate_date": candidate.get("slate_date"), "game_time": _iso(candidate.get("game_time")),
                "pitcher": candidate.get("normalized_pitcher"), "side": candidate.get("side"),
                "k_line": _number(candidate.get("model_k_line")), "provider": official_provider,
            },
            "candidate_became_current_at": windows.get("candidate_became_current_at"),
            "observations": observations,
            "observation_ids": [row["id"] for row in observations],
            "first_observed_at": observations[0]["observed_at"],
            "last_observed_at": observations[-1]["observed_at"],
            "freshness_status": "fresh", "aggregation_reason_codes": [],
            "book_count": len(reconciled), "books_seen": sorted(reconciled),
            "toward_pick_count": toward, "away_from_pick_count": away,
            "side_price_movement": "with_side" if toward > away else "against_side" if away > toward else "neutral",
            "broad_confirmation": len(reconciled) >= 3,
            "reversal_book_count": len(reversals), "volatile_book_count": len(reversals),
            "best_is_off_market": ladder["best_is_off_market"],
        }

    evidence_window = {
        "ready": market_evidence["freshness_status"] == "fresh",
        "first_current_at": windows.get("candidate_became_current_at"),
        "provider_window_started_at": dict(provider_starts),
        "observation_ids": market_evidence["observation_ids"],
        "observation_count": len(market_evidence["observation_ids"]),
        "first_observed_at": market_evidence["first_observed_at"],
        "last_observed_at": market_evidence["last_observed_at"],
        "freshness_status": market_evidence["freshness_status"],
        "reason_codes": tuple(reason_codes),
        "bound_observations": observations,
    }
    proof_fragment = {
        "schema_version": PROOF_SCHEMA_VERSION,
        "exact_preclose": {
            "official_provider": official_provider,
            "official_binding_key": bindings.get("official_binding_key"),
            "sidecar_binding_keys": dict(bindings.get("sidecar_binding_keys") or {}),
            "bindings_by_provider": dict(bindings_by_provider),
            "provider_window_started_at": dict(provider_starts),
            "movement_observation_ids": market_evidence["observation_ids"],
            "ladder_observation_ids": ladder_observation_ids,
            "direction_change_pivot_tokens": sorted({
                token
                for stats in provider_stats.values()
                for token in stats["direction_change_pivots"]
            }),
            "latest_ladder_observation_tokens": latest_ladder_observation_tokens,
            "ladder_observation_token_sha256": hashlib.sha256(
                "|".join(ladder_observation_ids).encode("utf-8")
            ).hexdigest(),
            "provider_freshness": {
                provider: {
                    "latest_snapshot_at": max(row["observed_at"] for row in stats["rows"]),
                    "freshness_status": "fresh",
                }
                for provider, stats in provider_stats.items()
            },
            "ladder": ladder,
            "source_artifact_path": source_artifact_path,
            "source_artifact_byte_sha256": source_artifact_byte_sha256,
            "reason_codes": reason_codes,
        },
    }
    return ExactPrecloseResult(market_evidence, evidence_window, proof_fragment)
