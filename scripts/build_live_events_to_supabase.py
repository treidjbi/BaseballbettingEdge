"""Build live pick events from the latest dashboard artifact into Supabase."""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))

from market_infra.live_events import (  # noqa: E402
    build_line_movement_events,
    build_line_movement_rows,
    build_missing_pick_state_events,
    build_pick_change_events,
    build_propline_webhook_movement_notification_events,
    build_reminder_events,
)
from market_infra.alternative_pick_selection_state import (  # noqa: E402
    APPROVED_ARTIFACT_PATH,
    UNIQUE_COLUMNS,
    aggregate_candidate_market_evidence,
    bind_candidate_observations,
    build_frozen_row,
    build_provisional_row,
    candidate_record,
    frozen_insert_on_conflict,
    resolve_candidate_became_current_at,
)
from market_infra.alternative_pick_selector import (  # noqa: E402
    BUNDLE_ID,
    derive_runtime_features,
    evaluate_alternative_pick,
)
from market_infra.live_market_display import build_live_market_display_rows  # noqa: E402
from market_infra.mainline_price_notifications import (  # noqa: E402
    build_mainline_best_price_notification_rows,
)
from market_infra.market_evidence import build_market_pick_evidence_rows  # noqa: E402
from market_infra.notification_coordinator import coordinate_notification_rows  # noqa: E402
from market_infra.operational_locks import build_operational_lock_rows  # noqa: E402
from market_infra.published_artifacts import canonical_payload_sha256  # noqa: E402
from market_infra.ready_to_bet_shadow import build_ready_to_bet_shadow  # noqa: E402
from market_infra.shadow_pipeline_timing import build_shadow_pipeline_timing_rows  # noqa: E402
from market_infra.shadow_notification_candidates import (  # noqa: E402
    build_shadow_notification_candidate_rows,
)
from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402
from scripts.build_current_market_lines_to_supabase import (  # noqa: E402
    run as build_current_market_lines_to_supabase,
)
from scripts.build_official_market_lines_to_supabase import (  # noqa: E402
    run as build_official_market_lines_to_supabase,
)
from scripts.compact_market_snapshots import (  # noqa: E402
    run as compact_market_snapshots_to_supabase,
)
from scripts.process_propline_webhooks import (  # noqa: E402
    run as process_propline_webhook_deliveries,
)
from scripts.shadow_propline_to_supabase import poll_propline_to_supabase  # noqa: E402
from scripts.shadow_therundown_mainline_to_supabase import (  # noqa: E402
    poll_therundown_mainline_to_supabase,
)

DEFAULT_ARTIFACT = ROOT / "dashboard" / "data" / "processed" / "today.json"
DEFAULT_ARTIFACT_URL = "https://baseballbettingedge.netlify.app/.netlify/functions/get-artifact?type=today"
DEFAULT_LOCK_ONLY_WORKFLOW_DISPATCH_URL = (
    "https://baseballbettingedge.netlify.app/.netlify/functions/trigger-pipeline"
)
LIVE_NOTIFICATION_MOVEMENT_PROVIDERS = {"propline"}
DEFAULT_PROPLINE_WEBHOOK_LIMIT = 100
DEFAULT_PROPLINE_WEBHOOK_MAX_AGE_MINUTES = 180
DEFAULT_PROPLINE_WEBHOOK_NOTIFICATION_MAX_AGE_MINUTES = 20


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _optional_env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _env_flag(name: str, *, default: bool) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    return value not in {"0", "false", "no", "off"}


def _env_int(name: str, *, default: int) -> int:
    value = os.environ.get(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        print(
            f"Warning: invalid integer for {name}={value!r}; using {default}",
            file=sys.stderr,
        )
        return default


def _notification_coordinator_mode() -> str:
    mode = _optional_env("LIVE_NOTIFICATION_COORDINATOR_MODE").lower()
    if mode in {"off", "shadow", "grouped"}:
        return mode
    if mode:
        print(
            f"Warning: invalid LIVE_NOTIFICATION_COORDINATOR_MODE={mode!r}; using off",
            file=sys.stderr,
        )
    return "off"


def _mainline_best_price_notification_mode() -> str:
    value = os.getenv("LIVE_MAINLINE_PRICE_NOTIFICATION_MODE", "off").strip().lower()
    return value if value in {"off", "shadow", "send"} else "off"


def _ready_to_bet_shadow_mode() -> str:
    value = str(os.getenv("LIVE_READY_TO_BET_SHADOW") or "off").strip().lower()
    return value if value in {"off", "record"} else "off"


def _alternative_pick_selection_mode() -> str:
    return "record" if os.environ.get(
        "ALTERNATIVE_PICK_SELECTION_MODE", "off"
    ).strip().lower() == "record" else "off"


def _alternative_remaining_timeout(started_at: float, budget_seconds: float) -> float:
    return budget_seconds - (time.monotonic() - started_at)


def _alternative_failure_summary(reason: str) -> dict[str, Any]:
    warning = "alternative pick selection recorder stopped for this cycle"
    print(f"Warning: {warning} ({reason})", file=sys.stderr)
    return {"skipped": True, "reason": reason, "rows": 0, "warning": warning[:200]}


def _alternative_summary_failed(value: Any) -> bool:
    if isinstance(value, dict):
        reason = str(value.get("reason") or "").strip().lower()
        if value.get("error") or reason == "failed" or reason.endswith("_failed"):
            return True
        return any(_alternative_summary_failed(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_alternative_summary_failed(item) for item in value)
    return False


def _alternative_prerequisite_failed(*summaries: dict[str, Any]) -> bool:
    return any(_alternative_summary_failed(summary) for summary in summaries)


def _alternative_american_odds(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or not parsed.is_integer() or parsed == 0:
        return None
    return int(parsed)


def _alternative_line(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0 else None


def _alternative_tracked_candidates(
    *,
    slate_date: str,
    payload: dict[str, Any],
    market_pick_evidence_rows: list[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
    """Return exact tracked picks with only approved already-built evidence."""
    del market_pick_evidence_rows  # Candidate identity comes only from the official artifact.

    candidates: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    seen: set[str] = set()
    for pitcher in payload.get("pitchers") or []:
        if not isinstance(pitcher, dict):
            continue
        mode = str(pitcher.get("market_source_mode") or "").strip().lower().replace("+", "_")
        odds_source = str(pitcher.get("odds_source") or "").strip().lower().replace("+", "_")
        if mode:
            if (
                mode not in {"therundown", "therundown_propline"}
                or odds_source not in {"therundown", "therundown_propline"}
                or mode != odds_source
            ):
                continue
            posture = mode
        elif odds_source in {"therundown", "therundown_propline"}:
            posture = odds_source
        else:
            continue
        tracked = pitcher.get("tracked_picks")
        if not isinstance(tracked, list):
            continue
        for pick in tracked:
            if not isinstance(pick, dict):
                continue
            side = str(pick.get("side") or "").strip().lower()
            if side not in {"over", "under"}:
                continue
            name = str(pitcher.get("pitcher") or pick.get("pitcher") or "").strip()
            raw_line = next(
                (pick.get(field) for field in ("display_k_line", "locked_k_line", "k_line")
                 if pick.get(field) is not None),
                None,
            )
            line = _alternative_line(raw_line)
            if line is None:
                continue
            candidate = candidate_record(
                slate_date=slate_date,
                pitcher=name,
                side=side,
                model_k_line=line,
                team=str(pitcher.get("team") or pick.get("team") or ""),
                opp_team=str(pitcher.get("opp_team") or pick.get("opp_team") or ""),
                game_time=str(pick.get("game_time") or pitcher.get("game_time") or ""),
                provider_posture=posture,
            )
            if candidate["candidate_identity"] not in seen:
                candidates.append((candidate, pitcher, pick))
                seen.add(candidate["candidate_identity"])
    return candidates


def _alternative_evaluation_inputs(
    *,
    pitcher: dict[str, Any],
    tracked_pick: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Use canonical side math, then overlay the tracked display/lock contract."""
    side = str(candidate.get("side") or "").strip().lower()
    side_payload = pitcher.get(f"ev_{side}")
    evaluation_pick = dict(side_payload) if isinstance(side_payload, dict) else {}
    overlay_fields = (
        "display_verdict", "locked_verdict", "actionable_verdict", "current_verdict",
        "verdict", "raw_verdict", "quality_actionable_verdict", "quality_gate_level",
        "edge", "ev", "adj_ev", "raw_adj_ev", "locked_adj_ev",
        "market_anchor_selector", "large_edge_skepticism_flag", "win_prob", "model_win_prob",
    )
    for field in overlay_fields:
        if tracked_pick.get(field) is not None:
            evaluation_pick[field] = tracked_pick[field]
    if tracked_pick.get("display_adj_ev") is not None:
        evaluation_pick["locked_adj_ev"] = tracked_pick["display_adj_ev"]
    tracked_odds = next(
        (tracked_pick.get(field) for field in ("display_odds", "locked_odds", "odds")
         if tracked_pick.get(field) is not None),
        None,
    )
    selected_odds = _alternative_american_odds(tracked_odds)
    tracked_book = next(
        (tracked_pick.get(field) for field in ("display_book", "locked_book", "book")
         if tracked_pick.get(field) not in {None, ""}),
        None,
    )
    evaluation_pick.update({
        "side": side,
        "official_k_line": candidate.get("model_k_line"),
        "odds": selected_odds,
    })

    evaluation_pitcher = dict(pitcher)
    evaluation_pitcher["game_time"] = candidate.get("game_time")
    evaluation_pitcher["k_line"] = candidate.get("model_k_line")
    for price_side in ("over", "under"):
        evaluation_pitcher[f"best_{price_side}_odds"] = _alternative_american_odds(
            pitcher.get(f"best_{price_side}_odds")
        )
    if tracked_odds is not None:
        evaluation_pitcher[f"best_{side}_odds"] = selected_odds
    if tracked_book is not None:
        evaluation_pitcher[f"best_{side}_book"] = str(tracked_book).strip() or None
    try:
        line_matches = abs(float(pitcher.get("k_line")) - float(candidate.get("model_k_line"))) < 0.001
    except (TypeError, ValueError):
        line_matches = False
    if not line_matches:
        evaluation_pitcher["best_over_odds"] = None
        evaluation_pitcher["best_under_odds"] = None
        evaluation_pitcher["best_over_book"] = None
        evaluation_pitcher["best_under_book"] = None
        if selected_odds is not None:
            evaluation_pitcher[f"best_{side}_odds"] = selected_odds
        if tracked_book is not None:
            evaluation_pitcher[f"best_{side}_book"] = str(tracked_book).strip() or None
    return evaluation_pitcher, evaluation_pick


def _alternative_persistence_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    return (
        candidate.get("slate_date"),
        candidate.get("game_identity"),
        candidate.get("normalized_pitcher"),
        candidate.get("side"),
        BUNDLE_ID,
    )


def _alternative_artifact_bindings(
    pitcher: dict[str, Any],
) -> tuple[list[Any], dict[str, list[Any]]]:
    snapshot_ids = pitcher.get("source_snapshot_ids")
    snapshots = list(snapshot_ids) if isinstance(snapshot_ids, (list, tuple)) else []
    events: dict[str, list[Any]] = {}
    field_map = {
        "propline": ("propline_event_id",),
        "therundown": ("therundown_event_id", "rundown_event_id", "the_rundown_event_id"),
    }
    for provider, fields in field_map.items():
        values = [pitcher.get(field) for field in fields if pitcher.get(field) not in {None, ""}]
        if values:
            events[provider] = values
    source_provider = str(pitcher.get("line_source_provider") or "").strip().lower()
    generic_event = pitcher.get("provider_event_id")
    if source_provider in {"therundown", "propline"} and generic_event not in {None, ""}:
        events.setdefault(source_provider, []).append(generic_event)
    return snapshots, events


def _postgrest_in_filter(values: list[str]) -> str:
    escaped = [str(value).replace("\\", "\\\\").replace('"', '\\"') for value in values]
    return "in.(" + ",".join(f'"{value}"' for value in escaped) + ")"


def _write_alternative_pick_selection_state(
    *,
    writer: SupabaseMarketWriter,
    slate_date: str,
    payload: dict[str, Any],
    snapshot_rows: list[dict[str, Any]],
    market_pick_evidence_rows: list[dict[str, Any]],
    observed_at: datetime,
    artifact_source: str,
    source_payload_sha256: str,
    source_artifact_byte_sha256: str,
    operational_pick_locks: dict[str, Any],
    market_line_build: dict[str, Any],
    shadow_pipeline_timing: dict[str, Any] | None = None,
    ready_to_bet_write: dict[str, Any] | None = None,
    budget_seconds: float = 5.0,
) -> dict[str, Any]:
    """Record isolated alternative state with bounded, single-attempt requests."""
    if _alternative_pick_selection_mode() != "record":
        return {"skipped": True, "reason": "disabled", "rows": 0}
    shadow_pipeline_timing = shadow_pipeline_timing or {"skipped": True, "reason": "disabled"}
    ready_to_bet_write = ready_to_bet_write or {"skipped": True, "reason": "disabled"}
    if _alternative_prerequisite_failed(
        operational_pick_locks,
        shadow_pipeline_timing,
        market_line_build,
        ready_to_bet_write,
    ):
        return {"skipped": True, "reason": "prerequisite_failed", "rows": 0}

    started_at = time.monotonic()
    candidates = _alternative_tracked_candidates(
        slate_date=slate_date,
        payload=payload,
        market_pick_evidence_rows=market_pick_evidence_rows,
    )
    if not candidates:
        return {"skipped": True, "reason": "no_candidates", "rows": 0}

    identities_by_key: dict[tuple[Any, ...], set[str]] = {}
    for candidate, _, _ in candidates:
        identities_by_key.setdefault(_alternative_persistence_key(candidate), set()).add(
            str(candidate.get("candidate_identity") or "")
        )
    collision_groups = {
        frozenset(identities)
        for identities in identities_by_key.values()
        if len(identities) > 1
    }
    identities_by_lock_key: dict[str, set[str]] = {}
    for candidate, _, _ in candidates:
        lock_key = f"{candidate['slate_date']}:{candidate['normalized_pitcher']}:{candidate['side']}"
        identities_by_lock_key.setdefault(lock_key, set()).add(str(candidate.get("candidate_identity") or ""))
    collision_groups.update(
        frozenset(identities)
        for identities in identities_by_lock_key.values()
        if len(identities) > 1
    )
    collisions = len(collision_groups)
    if collisions:
        return {
            "skipped": True,
            "reason": "candidate_key_collision",
            "rows": 0,
            "collisions": collisions,
        }

    def remaining() -> float:
        return _alternative_remaining_timeout(started_at, budget_seconds)

    try:
        timeout = remaining()
        if timeout <= 0:
            return _alternative_failure_summary("timeout")
        existing_rows = writer.select_rows(
            "alternative_pick_selection_state",
            {
                "slate_date": f"eq.{slate_date}",
                "bundle_id": f"eq.{BUNDLE_ID}",
                "checkpoint": "in.(provisional,frozen_pregame)",
                "select": (
                    "slate_date,game_identity,candidate_identity,candidate_became_current_at,"
                    "normalized_pitcher,side,bundle_id,checkpoint,observed_at,game_time"
                ),
            },
            timeout_seconds=timeout,
            attempts=1,
        )
        timeout = remaining()
        if timeout <= 0:
            return _alternative_failure_summary("timeout")
        dedupe_keys = sorted({
            f"{candidate['slate_date']}:{candidate['normalized_pitcher']}:{candidate['side']}"
            for candidate, _, _ in candidates
        })
        lock_rows = writer.select_rows(
            "operational_pick_locks",
            {
                "slate_date": f"eq.{slate_date}",
                "dedupe_key": _postgrest_in_filter(dedupe_keys),
                "select": (
                    "dedupe_key,slate_date,normalized_pitcher,side,locked_k_line,game_time,"
                    "locked_odds,locked_book,"
                    "status_at_capture,observed_at,locked_at,should_lock_at,minutes_until_start,"
                    "source_artifact_path,source_artifact_sha256,metadata"
                ),
            },
            timeout_seconds=timeout,
            attempts=1,
        )
    except Exception:
        return _alternative_failure_summary("failed")

    observed_at_iso = observed_at.astimezone(timezone.utc).isoformat()
    existing_rows = existing_rows if isinstance(existing_rows, list) else []
    lock_rows = lock_rows if isinstance(lock_rows, list) else []
    inserted_locks = operational_pick_locks.get("inserted_lock_rows")
    if isinstance(inserted_locks, list):
        lock_rows.extend(inserted_locks)
    artifact = {
        "path": APPROVED_ARTIFACT_PATH,
        "payload": payload,
        "payload_sha256": source_payload_sha256,
        "byte_sha256": source_artifact_byte_sha256,
        "generated_at": payload.get("generated_at"),
    }
    provisional_rows: list[dict[str, Any]] = []
    frozen_rows: list[dict[str, Any]] = []
    for candidate, pitcher, pick in candidates:
        key = _alternative_persistence_key(candidate)
        matching_existing = [
            row for row in existing_rows
            if isinstance(row, dict) and tuple(row.get(field) for field in UNIQUE_COLUMNS[:5]) == key
        ]
        if any(row.get("checkpoint") == "frozen_pregame" for row in matching_existing):
            continue
        first_current_at = resolve_candidate_became_current_at(
            candidate=candidate,
            existing_rows=matching_existing,
            observed_at=observed_at_iso,
        )
        if first_current_at is None:
            return _alternative_failure_summary("failed")
        candidate["frozen_exists"] = False
        try:
            artifact_snapshot_ids, artifact_provider_event_ids = _alternative_artifact_bindings(pitcher)
            evidence_window = bind_candidate_observations(
                candidate=candidate,
                snapshot_rows=snapshot_rows,
                market_evidence_rows=market_pick_evidence_rows,
                first_current_at=first_current_at,
                observed_at=observed_at_iso,
                artifact_snapshot_ids=artifact_snapshot_ids,
                artifact_provider_event_ids=artifact_provider_event_ids,
            )
            evidence = aggregate_candidate_market_evidence(
                candidate=candidate,
                market_evidence_rows=market_pick_evidence_rows,
                evidence_window=evidence_window,
            )
            evidence_window = {
                **evidence_window,
                "reason_codes": tuple(dict.fromkeys((
                    *evidence_window.get("reason_codes", ()),
                    *evidence.get("aggregation_reason_codes", ()),
                ))),
            }
            evaluation_pitcher, evaluation_pick = _alternative_evaluation_inputs(
                pitcher=pitcher,
                tracked_pick=pick,
                candidate=candidate,
            )
            evaluation = evaluate_alternative_pick(
                pitcher=evaluation_pitcher,
                pick=evaluation_pick,
                market_evidence=evidence,
                slate_date=slate_date,
                is_tracked=True,
                source_artifact_path=APPROVED_ARTIFACT_PATH,
                source_payload_sha256=source_payload_sha256,
                source_artifact_byte_sha256=source_artifact_byte_sha256,
                observed_at=observed_at_iso,
            )
        except Exception:
            return _alternative_failure_summary("failed")
        provisional = build_provisional_row(
            candidate=candidate,
            evaluation=evaluation,
            evidence_window=evidence_window,
            artifact=artifact,
            observed_at=observed_at_iso,
        )
        if provisional is None:
            continue
        candidate_lock_rows = [
            row for row in lock_rows
            if isinstance(row, dict)
            and row.get("dedupe_key") == f"{slate_date}:{candidate['normalized_pitcher']}:{candidate['side']}"
        ]
        current_lock = next(
            (
                row for row in candidate_lock_rows
                if _parse_timestamp(row.get("locked_at")) == observed_at.astimezone(timezone.utc)
                and _parse_timestamp(row.get("observed_at")) == observed_at.astimezone(timezone.utc)
            ),
            None,
        )
        if current_lock is not None:
            if evidence_window.get("ready") and evidence.get("freshness_status") == "fresh":
                frozen = build_frozen_row(
                    provisional_row=provisional,
                    lock_row=current_lock,
                    observed_at=observed_at_iso,
                )
                if frozen is not None:
                    frozen_rows.append(frozen)
                    continue
            provisional["reason_codes"] = list(dict.fromkeys([
                *provisional.get("reason_codes", []), "freeze_evidence_pending",
            ]))
        if candidate_lock_rows:
            provisional["reason_codes"] = list(dict.fromkeys([
                *provisional.get("reason_codes", []), "missed_freeze",
            ]))
        provisional_rows.append(provisional)
        if remaining() <= 0:
            return _alternative_failure_summary("timeout")

    try:
        for rows, method, conflict in (
            (provisional_rows, writer.upsert_rows, ",".join(UNIQUE_COLUMNS)),
            (frozen_rows, writer.insert_ignore_rows, frozen_insert_on_conflict()),
        ):
            if not rows:
                continue
            timeout = remaining()
            if timeout <= 0:
                return _alternative_failure_summary("timeout")
            method(
                "alternative_pick_selection_state",
                rows,
                on_conflict=conflict,
                timeout_seconds=timeout,
            )
    except Exception:
        return _alternative_failure_summary("failed")
    if remaining() <= 0:
        return _alternative_failure_summary("timeout")
    return {
        "skipped": False,
        "rows": len(provisional_rows) + len(frozen_rows),
        "provisional_rows": len(provisional_rows),
        "frozen_rows": len(frozen_rows),
        "collisions": 0,
    }


def _write_ready_to_bet_candidates(
    *,
    writer: SupabaseMarketWriter,
    rows: list[dict[str, Any]],
    mode: str,
) -> dict[str, Any]:
    if mode != "record":
        return {"skipped": True, "reason": "disabled", "rows": 0}
    if not rows:
        return {"skipped": True, "reason": "no_candidates", "rows": 0}
    try:
        inserted = writer.insert_ignore_rows(
            "shadow_notification_candidates",
            rows,
            on_conflict="dedupe_key",
        )
        inserted_count = len(inserted) if isinstance(inserted, list) else len(rows)
        return {"skipped": False, "rows": len(rows), "inserted_rows": inserted_count}
    except Exception as error:
        print(
            f"Warning: ready-to-bet shadow candidate write failed ({error})",
            file=sys.stderr,
        )
        return {
            "skipped": True,
            "reason": "write_failed",
            "rows": len(rows),
            "error": str(error)[:1000],
        }


def _mark_ready_to_bet_write_pending(
    state_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
) -> int:
    candidate_keys = {
        (
            str(candidate.get("normalized_pitcher") or "").strip(),
            str(candidate.get("side") or "").strip().lower(),
        )
        for candidate in candidate_rows
    }
    updated_count = 0
    for row in state_rows:
        key = (
            str(row.get("normalized_pitcher") or "").strip(),
            str(row.get("side") or "").strip().lower(),
        )
        metadata = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        if key not in candidate_keys or metadata.get("decision_state") != "ready":
            continue
        updated_metadata = dict(metadata)
        updated_metadata["candidate_write_pending"] = True
        updated_metadata["candidate_write_failure_reason"] = "write_failed"
        row["metadata"] = updated_metadata
        updated_count += 1
    return updated_count


def _mainline_best_price_min_cents() -> int:
    return max(1, _env_int("LIVE_MAINLINE_PRICE_MIN_CENTS", default=10))


def _source_artifact_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _previous_state(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    previous: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        slate_date = row.get("slate_date")
        normalized_pitcher = row.get("normalized_pitcher")
        side = row.get("side")
        if slate_date and normalized_pitcher and side:
            previous[(str(slate_date), str(normalized_pitcher), str(side))] = row
    return previous


def _load_artifact_bytes(artifact_bytes: bytes) -> tuple[dict[str, Any], str]:
    payload = json.loads(artifact_bytes.decode("utf-8"))
    return payload, hashlib.sha256(artifact_bytes).hexdigest()


def _load_artifact(path: Path, artifact_url: str | None = None) -> tuple[dict[str, Any], str, str]:
    if artifact_url:
        try:
            with urlopen(artifact_url, timeout=20) as response:
                payload, artifact_sha = _load_artifact_bytes(response.read())
                return payload, artifact_sha, artifact_url
        except Exception as error:
            print(
                f"Warning: remote artifact fetch failed ({error}); falling back to local {path}",
                file=sys.stderr,
            )

    artifact_bytes = path.read_bytes()
    payload, artifact_sha = _load_artifact_bytes(artifact_bytes)
    return payload, artifact_sha, _source_artifact_path(path)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fresh_webhook_movement_rows(
    rows: list[dict[str, Any]],
    *,
    observed_at: datetime,
    max_age_minutes: int,
) -> tuple[list[dict[str, Any]], int]:
    if max_age_minutes <= 0:
        return rows, 0
    cutoff = observed_at - timedelta(minutes=max_age_minutes)
    fresh_rows: list[dict[str, Any]] = []
    stale_count = 0
    for row in rows:
        movement_time = _parse_timestamp(row.get("observed_at"))
        if movement_time is None or movement_time < cutoff:
            stale_count += 1
            continue
        fresh_rows.append(row)
    return fresh_rows, stale_count


def _latest_table_timestamp(
    writer: SupabaseMarketWriter,
    table: str,
    slate_date: str,
    *,
    column: str = "updated_at",
) -> datetime | None:
    rows = writer.select_rows(
        table,
        {
            "slate_date": f"eq.{slate_date}",
            "select": column,
            "order": f"{column}.desc",
            "limit": "1",
        },
    )
    if not rows:
        return None
    return _parse_timestamp(rows[0].get(column))


def _build_due(
    latest_at: datetime | None,
    observed_at: datetime,
    min_interval_seconds: int,
) -> bool:
    if latest_at is None:
        return True
    return (observed_at - latest_at).total_seconds() >= min_interval_seconds


def _snapshot_pairs(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_key: dict[tuple[str, str, str, str], list[dict[str, Any]]] = {}
    by_key_line: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}
    for row in rows:
        provider_event_id = str(row.get("provider_event_id") or "").strip()
        book = str(row.get("bookmaker_key") or "").strip()
        normalized = str(row.get("normalized_player_name") or "").strip()
        side = str(row.get("side") or "").strip().lower()
        if provider_event_id and book and normalized and side in {"over", "under"}:
            base_key = (provider_event_id, book, normalized, side)
            by_key.setdefault(base_key, []).append(row)
            line = str(row.get("line") or "").strip()
            if line:
                by_key_line.setdefault((*base_key, line), []).append(row)

    previous: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    for snapshots in by_key_line.values():
        ordered = sorted(snapshots, key=lambda row: str(row.get("observed_at") or ""))
        if len(ordered) < 2:
            continue
        previous.append(ordered[-2])
        current.append(ordered[-1])

    for snapshots in by_key.values():
        ordered = sorted(snapshots, key=lambda row: str(row.get("observed_at") or ""))
        if len(ordered) < 2:
            continue
        distinct_lines = {str(row.get("line") or "").strip() for row in ordered if str(row.get("line") or "").strip()}
        if len(ordered) != 2 or len(distinct_lines) != 2:
            continue
        previous.append(ordered[-2])
        current.append(ordered[-1])

    return previous, current


def _live_notification_snapshots(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        row
        for row in rows
        if str(row.get("provider") or "").strip().lower() in LIVE_NOTIFICATION_MOVEMENT_PROVIDERS
    ]


def _fetch_provider_heartbeats(writer: SupabaseMarketWriter, slate_date: str) -> list[dict[str, Any]]:
    try:
        return writer.select_rows("market_feed_heartbeats", {
            "provider": "in.(propline,therundown)",
            "slate_date": f"eq.{slate_date}",
            "order": "observed_at.desc",
            "limit": "25",
        })
    except Exception as error:
        print(
            f"Warning: provider heartbeat read failed ({error}); continuing live build",
            file=sys.stderr,
        )
        return []


def _run_id_filter(run_rows: list[dict[str, Any]]) -> str:
    run_ids = [str(row.get("id")) for row in run_rows if row.get("id")]
    return f"in.({','.join(run_ids)})"


def _fetch_recent_provider_run_rows(
    writer: SupabaseMarketWriter,
    slate_date: str,
    *,
    limit: int = 100,
) -> list[dict[str, Any]]:
    return writer.select_rows(
        "market_provider_runs",
        {
            "slate_date": f"eq.{slate_date}",
            "provider": "in.(propline,therundown)",
            "order": "created_at.desc",
            "limit": str(limit),
        },
    )


def _fetch_live_market_snapshot_rows(
    writer: SupabaseMarketWriter,
    slate_date: str,
    observed_at: datetime,
    *,
    lookback_minutes: int | None = None,
    page_size: int = 1000,
    max_pages: int = 5,
) -> list[dict[str, Any]]:
    """Fetch bounded current-slate market rows without scanning all snapshots."""
    lookback = lookback_minutes
    if lookback is None:
        lookback = int(os.environ.get("LIVE_MARKET_SNAPSHOT_LOOKBACK_MINUTES", "720") or "720")
    lookback_start = (observed_at - timedelta(minutes=lookback)).isoformat()

    try:
        run_rows = _fetch_recent_provider_run_rows(writer, slate_date)
    except Exception as error:
        print(
            f"Warning: market provider run read failed ({error}); falling back to bounded snapshot read",
            file=sys.stderr,
        )
        run_rows = []

    rows: list[dict[str, Any]] = []
    if run_rows:
        run_rows = [row for row in run_rows if row.get("id")]
    if run_rows:
        run_filter = _run_id_filter(run_rows)
        for page in range(max_pages):
            page_rows = writer.select_rows(
                "market_snapshots",
                {
                    "run_id": run_filter,
                    "observed_at": f"gte.{lookback_start}",
                    "order": "observed_at.desc",
                    "limit": str(page_size),
                    "offset": str(page * page_size),
                },
            )
            rows.extend(page_rows)
            if len(page_rows) < page_size:
                break
        return rows

    return writer.select_rows(
        "market_snapshots",
        {
            "provider": "in.(propline,therundown)",
            "observed_at": f"gte.{lookback_start}",
            "order": "observed_at.desc",
            "limit": str(page_size),
        },
    )


def _shadow_pipeline_timing_enabled() -> bool:
    value = os.environ.get("ENABLE_SHADOW_PIPELINE_TIMING_LEDGER", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _operational_lock_ledger_enabled() -> bool:
    return _env_flag("ENABLE_SUPABASE_LOCK_LEDGER", default=False)


def _lock_only_workflow_dispatch_enabled() -> bool:
    return _env_flag("ENABLE_LOCK_ONLY_WORKFLOW_DISPATCH", default=False)


def _dispatch_lock_only_workflow(
    slate_date: str,
    *,
    inserted_lock_rows: int,
) -> dict[str, Any]:
    if inserted_lock_rows <= 0:
        return {"skipped": True, "reason": "no_new_lock_rows"}

    token = _optional_env("GITHUB_LOCK_DISPATCH_TOKEN") or _optional_env("GITHUB_PAT")
    if token:
        repo = (
            _optional_env("GITHUB_LOCK_DISPATCH_REPO")
            or _optional_env("GITHUB_REPO")
            or "treidjbi/BaseballBettingEdge"
        )
        workflow = (
            _optional_env("GITHUB_LOCK_DISPATCH_WORKFLOW")
            or _optional_env("GITHUB_WORKFLOW")
            or "pipeline.yml"
        )
        ref = _optional_env("GITHUB_LOCK_DISPATCH_REF") or "main"
        body = json.dumps({
            "ref": ref,
            "inputs": {
                "mode": "lock",
                "date": slate_date,
            },
        }).encode("utf-8")
        request = Request(
            f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "User-Agent": "bbe-live-layer-lock-dispatch",
            },
        )
        with urlopen(request, timeout=20) as response:
            status_code = int(getattr(response, "status", 0) or 0)
            if status_code != 204:
                response.read()
                raise RuntimeError(f"GitHub lock dispatch failed with HTTP {status_code}")
        return {"skipped": False, "status_code": status_code}

    proxy_url = _optional_env("LOCK_ONLY_WORKFLOW_DISPATCH_URL") or DEFAULT_LOCK_ONLY_WORKFLOW_DISPATCH_URL
    body = json.dumps({"mode": "lock", "date": slate_date}).encode("utf-8")
    request = Request(
        proxy_url,
        data=body,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "bbe-live-layer-lock-dispatch",
        },
    )
    with urlopen(request, timeout=20) as response:
        status_code = int(getattr(response, "status", 0) or 0)
        if status_code < 200 or status_code >= 300:
            response.read()
            raise RuntimeError(f"lock dispatch proxy failed with HTTP {status_code}")
    return {"skipped": False, "status_code": status_code, "via": "proxy"}


def _maybe_dispatch_lock_only_workflow(
    slate_date: str,
    *,
    inserted_lock_rows: int,
) -> dict[str, Any]:
    if not _lock_only_workflow_dispatch_enabled():
        return {"skipped": True, "reason": "disabled"}
    if inserted_lock_rows <= 0:
        return {"skipped": True, "reason": "no_new_lock_rows"}
    try:
        return _dispatch_lock_only_workflow(slate_date, inserted_lock_rows=inserted_lock_rows)
    except Exception as error:
        print(
            f"Warning: lock-only workflow dispatch failed ({error})",
            file=sys.stderr,
        )
        return {"skipped": True, "reason": "dispatch_failed", "error": str(error)[:1000]}


def _lock_build_summary(result: dict[str, Any]) -> str:
    locks = result.get("operational_pick_locks") or {"skipped": True, "reason": "missing"}
    if locks.get("skipped"):
        return f"locks=skipped:{locks.get('reason', 'unknown')}"
    dispatch = locks.get("dispatch") or {"skipped": True, "reason": "missing"}
    if dispatch.get("skipped"):
        dispatch_label = f"skipped:{dispatch.get('reason', 'unknown')}"
    else:
        dispatch_label = f"sent:{dispatch.get('status_code', 'unknown')}"
    return (
        f"locks=rows:{locks.get('rows', 0)} "
        f"inserted:{locks.get('inserted_rows', locks.get('rows', 0))} "
        f"dispatch:{dispatch_label}"
    )


def _public_operational_lock_summary(summary: dict[str, Any]) -> dict[str, Any]:
    allowed = ("skipped", "reason", "rows", "inserted_rows")
    public = {key: summary[key] for key in allowed if key in summary}
    dispatch = summary.get("dispatch")
    if isinstance(dispatch, dict):
        dispatch_allowed = ("skipped", "reason", "status_code", "via")
        public["dispatch"] = {
            key: dispatch[key]
            for key in dispatch_allowed
            if key in dispatch
        }
    return public


def _public_artifact_source(artifact_source: Any) -> str:
    return "remote" if str(artifact_source or "").lower().startswith("http") else APPROVED_ARTIFACT_PATH


def _write_operational_pick_locks(
    *,
    writer: SupabaseMarketWriter,
    slate_date: str,
    payload: dict[str, Any],
    observed_at: datetime,
    artifact_source: str,
    artifact_sha: str | None,
) -> dict[str, Any]:
    if not _operational_lock_ledger_enabled():
        return {"skipped": True, "reason": "disabled"}

    try:
        rows = build_operational_lock_rows(
            slate_date=slate_date,
            pitchers=payload.get("pitchers") or [],
            observed_at=observed_at,
            source_artifact_path=artifact_source,
            source_artifact_sha256=artifact_sha,
            artifact_generated_at=payload.get("generated_at"),
        )
        inserted = writer.insert_ignore_rows("operational_pick_locks", rows, on_conflict="dedupe_key")
        inserted_count = len(inserted) if isinstance(inserted, list) else len(rows)
        dispatch = _maybe_dispatch_lock_only_workflow(
            slate_date,
            inserted_lock_rows=inserted_count,
        )
        return {
            "skipped": False,
            "rows": len(rows),
            "inserted_rows": inserted_count,
            "lock_rows": rows,
            "inserted_lock_rows": inserted if isinstance(inserted, list) else [],
            "dispatch": dispatch,
        }
    except Exception as error:
        print(
            f"Warning: operational lock ledger write failed ({error})",
            file=sys.stderr,
        )
        return {"skipped": True, "reason": "write_failed", "error": str(error)[:1000]}


def _write_shadow_pipeline_timing(
    *,
    writer: SupabaseMarketWriter,
    slate_date: str,
    payload: dict[str, Any],
    observed_at: datetime,
    artifact_source: str,
    artifact_sha: str | None,
    metadata_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not _shadow_pipeline_timing_enabled():
        return {"skipped": True, "reason": "disabled"}

    try:
        run_row, observation_rows = build_shadow_pipeline_timing_rows(
            slate_date=slate_date,
            pitchers=payload.get("pitchers") or [],
            observed_at=observed_at,
            source_artifact_path=artifact_source,
            source_artifact_sha256=artifact_sha,
            artifact_generated_at=payload.get("generated_at"),
            metadata_extra=metadata_extra,
        )
        writer.upsert_rows("shadow_pipeline_runs", [run_row], on_conflict="run_key")
        writer.insert_ignore_rows(
            "shadow_pick_lock_observations",
            observation_rows,
            on_conflict="dedupe_key",
        )
        return {
            "skipped": False,
            "pipeline_runs": 1,
            "pick_lock_observations": len(observation_rows),
            "pipeline_run_row": run_row,
            "pick_lock_observation_rows": observation_rows,
        }
    except Exception as error:
        print(
            f"Warning: shadow pipeline timing write failed ({error})",
            file=sys.stderr,
        )
        return {"skipped": True, "error": str(error)}


def _build_shadow_market_state(
    *,
    writer: SupabaseMarketWriter,
    slate_date: str,
    observed_at: datetime,
    enabled: bool,
    compact_enabled: bool,
    market_line_min_interval_seconds: int,
    compact_market_min_interval_seconds: int,
    artifact_payload: dict[str, Any],
    artifact_source: str,
) -> dict[str, Any]:
    if not enabled:
        return {"skipped": True, "reason": "disabled"}

    try:
        latest_current_at = _latest_table_timestamp(writer, "current_market_lines", slate_date)
        latest_official_at = _latest_table_timestamp(writer, "official_market_lines", slate_date)
        latest_compact_at = _latest_table_timestamp(
            writer,
            "compact_market_line_movements",
            slate_date,
        )
        current_due = _build_due(
            latest_current_at,
            observed_at,
            market_line_min_interval_seconds,
        )
        official_due = _build_due(
            latest_official_at,
            observed_at,
            market_line_min_interval_seconds,
        )
        compact_due = compact_enabled and _build_due(
            latest_compact_at,
            observed_at,
            compact_market_min_interval_seconds,
        )
        if not current_due and not official_due and not compact_due:
            return {"skipped": True, "reason": "fresh"}

        result: dict[str, Any] = {
            "skipped": False,
            "latest_current_market_lines_at": (
                latest_current_at.isoformat() if latest_current_at else None
            ),
            "latest_official_market_lines_at": (
                latest_official_at.isoformat() if latest_official_at else None
            ),
            "latest_compact_market_lines_at": (
                latest_compact_at.isoformat() if latest_compact_at else None
            ),
        }
        if current_due:
            result["current"] = build_current_market_lines_to_supabase(
                slate_date=slate_date,
                writer=writer,
                dry_run=False,
                now_utc=observed_at,
                artifact_payload=artifact_payload,
                artifact_source=artifact_source,
            )
        if current_due or official_due:
            result["official"] = build_official_market_lines_to_supabase(
                slate_date=slate_date,
                writer=writer,
                dry_run=False,
                now_utc=observed_at,
                artifact_payload=artifact_payload,
                artifact_source=artifact_source,
            )
        if compact_due:
            result["compact"] = compact_market_snapshots_to_supabase(
                slate_date=slate_date,
                writer=writer,
                dry_run=False,
            )
        return result
    except Exception as error:
        print(
            f"Warning: shadow market-state build failed ({error}); continuing live build",
            file=sys.stderr,
        )
        return {"skipped": True, "reason": "build_failed", "error": str(error)[:1000]}


def run(
    *,
    slate_date: str,
    artifact_path: Path,
    supabase_url: str,
    service_role_key: str,
    poll_propline: bool = False,
    poll_therundown_mainline: bool = False,
    artifact_url: str | None = None,
    artifact_payload: dict[str, Any] | None = None,
    artifact_sha: str | None = None,
    artifact_source: str | None = None,
    build_market_lines: bool = False,
    compact_market_lines: bool = True,
    market_line_min_interval_seconds: int = 600,
    compact_market_min_interval_seconds: int = 1800,
    process_propline_webhooks: bool = False,
    propline_webhook_limit: int = DEFAULT_PROPLINE_WEBHOOK_LIMIT,
    propline_webhook_max_age_minutes: int = DEFAULT_PROPLINE_WEBHOOK_MAX_AGE_MINUTES,
    propline_webhook_notification_max_age_minutes: int = (
        DEFAULT_PROPLINE_WEBHOOK_NOTIFICATION_MAX_AGE_MINUTES
    ),
    send_propline_webhook_movement_notifications: bool = False,
) -> dict[str, Any]:
    if artifact_payload is None:
        payload, artifact_sha, artifact_source = _load_artifact(Path(artifact_path), artifact_url=artifact_url)
    else:
        payload = artifact_payload
        if not artifact_sha or not artifact_source:
            raise ValueError("artifact_sha and artifact_source are required with artifact_payload")

    writer = SupabaseMarketWriter(supabase_url, service_role_key)
    previous_rows = writer.select_rows("live_pick_state", {"slate_date": f"eq.{slate_date}"})
    observed_at = _now_utc()
    propline_result: dict[str, Any] | None = None
    therundown_result: dict[str, Any] | None = None
    propline_webhook_result: dict[str, Any] | None = None

    if poll_therundown_mainline:
        try:
            therundown_result = poll_therundown_mainline_to_supabase(
                slate_date,
                writer=writer,
                observed_at=observed_at.isoformat(),
                raise_on_error=False,
            )
        except Exception as error:
            print(
                f"Warning: optional TheRundown mainline poll failed ({error}); continuing live build",
                file=sys.stderr,
            )
            therundown_result = {
                "skipped": True,
                "reason": "poll_failed",
                "error": str(error)[:1000],
            }

    if poll_propline:
        try:
            propline_result = poll_propline_to_supabase(
                slate_date,
                writer=writer,
                observed_at=observed_at.isoformat(),
            )
        except Exception as error:
            print(
                f"Warning: optional PropLine poll failed ({error}); continuing live build",
                file=sys.stderr,
            )
            propline_result = {
                "skipped": True,
                "reason": "poll_failed",
                "error": str(error)[:1000],
            }

    if process_propline_webhooks:
        try:
            received_after = None
            if propline_webhook_max_age_minutes > 0:
                received_after = observed_at - timedelta(minutes=propline_webhook_max_age_minutes)
            propline_webhook_result = process_propline_webhook_deliveries(
                supabase_url=supabase_url,
                service_role_key=service_role_key,
                limit=max(1, propline_webhook_limit),
                received_after=received_after,
                return_movement_rows=send_propline_webhook_movement_notifications,
            )
        except Exception as error:
            print(
                f"Warning: optional PropLine webhook processing failed ({error}); continuing live build",
                file=sys.stderr,
            )
            propline_webhook_result = {
                "skipped": True,
                "reason": "webhook_processing_failed",
                "error": str(error)[:1000],
            }

    pick_notification_rows, state_rows = build_pick_change_events(
        slate_date=slate_date,
        pitchers=payload.get("pitchers") or [],
        previous_state=_previous_state(previous_rows),
        observed_at=observed_at,
        source_artifact_path=artifact_source,
        source_artifact_sha256=artifact_sha,
    )
    missing_notification_rows, missing_state_rows = build_missing_pick_state_events(
        slate_date=slate_date,
        previous_rows=previous_rows,
        current_state_rows=state_rows,
        observed_at=observed_at,
        source_artifact_path=artifact_source,
        source_artifact_sha256=artifact_sha,
    )
    state_rows.extend(missing_state_rows)

    provider_heartbeats = _fetch_provider_heartbeats(writer, slate_date)
    try:
        snapshot_rows = _fetch_live_market_snapshot_rows(writer, slate_date, observed_at)
    except Exception as error:
        print(
            f"Warning: market snapshot read failed ({error}); continuing without market evidence",
            file=sys.stderr,
        )
        snapshot_rows = []
    previous_snapshots, current_snapshots = _snapshot_pairs(_live_notification_snapshots(snapshot_rows))
    movement_notification_rows = build_line_movement_events(
        slate_date=slate_date,
        live_picks=state_rows,
        previous_snapshots=previous_snapshots,
        current_snapshots=current_snapshots,
    )
    line_movement_rows = build_line_movement_rows(movement_notification_rows)
    propline_webhook_movement_rows = []
    if isinstance(propline_webhook_result, dict):
        raw_webhook_rows = propline_webhook_result.get("movement_rows")
        if isinstance(raw_webhook_rows, list):
            propline_webhook_movement_rows = raw_webhook_rows
            propline_webhook_result = {
                key: value
                for key, value in propline_webhook_result.items()
                if key != "movement_rows"
            }
    propline_webhook_notification_rows = []
    stale_webhook_notification_candidates = 0
    if send_propline_webhook_movement_notifications and propline_webhook_movement_rows:
        propline_webhook_movement_rows, stale_webhook_notification_candidates = (
            _fresh_webhook_movement_rows(
                propline_webhook_movement_rows,
                observed_at=observed_at,
                max_age_minutes=propline_webhook_notification_max_age_minutes,
            )
        )
        propline_webhook_notification_rows = build_propline_webhook_movement_notification_events(
            slate_date=slate_date,
            live_picks=state_rows,
            webhook_movement_rows=propline_webhook_movement_rows,
        )
    previous_live_market_display_rows = writer.select_rows(
        "live_market_display_state",
        {"slate_date": f"eq.{slate_date}"},
    )
    market_pick_evidence_rows = build_market_pick_evidence_rows(
        slate_date=slate_date,
        live_picks=state_rows,
        snapshot_rows=snapshot_rows,
        observed_at=observed_at,
        source_artifact_path=artifact_source,
        source_artifact_sha256=artifact_sha,
        provider_heartbeats=provider_heartbeats,
    )
    live_market_display_rows = build_live_market_display_rows(
        slate_date=slate_date,
        live_picks=state_rows,
        snapshot_rows=snapshot_rows,
        observed_at=observed_at,
        source_artifact_path=artifact_source,
        source_artifact_sha256=artifact_sha,
        provider_heartbeats=provider_heartbeats,
    )
    mainline_best_price_result = build_mainline_best_price_notification_rows(
        slate_date=slate_date,
        previous_rows=previous_live_market_display_rows,
        current_rows=live_market_display_rows,
        observed_at=observed_at,
        min_price_move_cents=_mainline_best_price_min_cents(),
        mode=_mainline_best_price_notification_mode(),
    )
    shadow_notification_candidate_rows = build_shadow_notification_candidate_rows(
        market_pick_evidence_rows
    )

    existing_reminders = writer.select_rows("game_reminder_state", {"slate_date": f"eq.{slate_date}"})
    reminder_notification_rows, reminder_rows = build_reminder_events(
        slate_date=slate_date,
        live_picks=state_rows,
        existing_reminders=existing_reminders,
        observed_at=observed_at,
    )

    movement_rows_for_notifications = movement_notification_rows
    webhook_rows_for_notifications = propline_webhook_notification_rows
    if mainline_best_price_result.summary.get("mode") == "send":
        movement_rows_for_notifications = []
        webhook_rows_for_notifications = []

    notification_rows = [
        *pick_notification_rows,
        *missing_notification_rows,
        *movement_rows_for_notifications,
        *webhook_rows_for_notifications,
        *mainline_best_price_result.notification_rows,
        *reminder_notification_rows,
    ]
    ready_to_bet_mode = _ready_to_bet_shadow_mode()
    accepted_bets: list[dict[str, Any]] = []
    accepted_bets_available = True
    if ready_to_bet_mode == "record":
        try:
            accepted_bets = writer.select_rows(
                "accepted_bets",
                {
                    "slate_date": f"eq.{slate_date}",
                    "select": (
                        "slate_date,pitcher,normalized_pitcher,side,book,"
                        "k_line,odds,accepted_at"
                    ),
                },
            )
        except Exception as error:
            accepted_bets_available = False
            print(
                f"Warning: accepted-bet state read failed ({error}); "
                "ready shadow failing closed",
                file=sys.stderr,
            )

    ready_to_bet_result = build_ready_to_bet_shadow(
        slate_date=slate_date,
        pitchers=payload.get("pitchers") or [],
        state_rows=state_rows,
        previous_state_rows=previous_rows,
        live_market_rows=live_market_display_rows,
        accepted_bets=accepted_bets,
        accepted_bets_available=accepted_bets_available,
        notification_rows=notification_rows,
        observed_at=observed_at,
        mode=ready_to_bet_mode,
    )
    state_rows = ready_to_bet_result.state_rows
    notification_coordination = coordinate_notification_rows(
        notification_rows,
        mode=_notification_coordinator_mode(),
        observed_at=observed_at,
        group_start_windows=_env_flag("LIVE_NOTIFICATION_GROUP_START_WINDOWS", default=False),
        group_pick_changes=_env_flag("LIVE_NOTIFICATION_GROUP_PICK_CHANGES", default=False),
    )
    coordinated_notification_rows = notification_coordination.rows
    writer.insert_ignore_rows(
        "notification_events",
        coordinated_notification_rows,
        on_conflict="dedupe_key",
    )
    writer.upsert_rows("line_movement_events", line_movement_rows, on_conflict="dedupe_key")
    writer.upsert_rows(
        "market_pick_evidence",
        market_pick_evidence_rows,
        on_conflict="slate_date,normalized_pitcher,side,provider",
    )
    writer.upsert_rows(
        "live_market_display_state",
        live_market_display_rows,
        on_conflict="slate_date,normalized_pitcher,side,provider",
    )
    writer.upsert_rows(
        "shadow_notification_candidates",
        shadow_notification_candidate_rows,
        on_conflict="dedupe_key",
    )
    ready_to_bet_write = _write_ready_to_bet_candidates(
        writer=writer,
        rows=ready_to_bet_result.candidate_rows,
        mode=ready_to_bet_mode,
    )
    if ready_to_bet_write.get("reason") == "write_failed":
        _mark_ready_to_bet_write_pending(
            state_rows,
            ready_to_bet_result.candidate_rows,
        )
    writer.upsert_rows("game_reminder_state", reminder_rows, on_conflict="dedupe_key")
    writer.upsert_rows("live_pick_state", state_rows, on_conflict="slate_date,normalized_pitcher,side")
    operational_pick_locks = _write_operational_pick_locks(
        writer=writer,
        slate_date=slate_date,
        payload=payload,
        observed_at=observed_at,
        artifact_source=artifact_source,
        artifact_sha=artifact_sha,
    )
    shadow_pipeline_timing = _write_shadow_pipeline_timing(
        writer=writer,
        slate_date=slate_date,
        payload=payload,
        observed_at=observed_at,
        artifact_source=artifact_source,
        artifact_sha=artifact_sha,
        metadata_extra={
            "therundown": therundown_result or {"skipped": True},
            "propline_webhooks": propline_webhook_result or {"skipped": True},
            "mainline_best_price": mainline_best_price_result.summary,
            "notification_coordinator": notification_coordination.summary,
            "ready_to_bet_shadow": ready_to_bet_result.summary,
            "ready_to_bet_shadow_write": ready_to_bet_write,
        },
    )
    market_line_build = _build_shadow_market_state(
        writer=writer,
        slate_date=slate_date,
        observed_at=observed_at,
        enabled=build_market_lines,
        compact_enabled=compact_market_lines,
        market_line_min_interval_seconds=market_line_min_interval_seconds,
        compact_market_min_interval_seconds=compact_market_min_interval_seconds,
        artifact_payload=payload,
        artifact_source=artifact_source,
    )
    source_payload_sha256 = canonical_payload_sha256(payload)
    alternative_pick_selection = _write_alternative_pick_selection_state(
        writer=writer,
        slate_date=slate_date,
        payload=payload,
        snapshot_rows=snapshot_rows,
        market_pick_evidence_rows=market_pick_evidence_rows,
        observed_at=observed_at,
        artifact_source=artifact_source,
        source_payload_sha256=source_payload_sha256,
        source_artifact_byte_sha256=artifact_sha,
        operational_pick_locks=operational_pick_locks,
        shadow_pipeline_timing=shadow_pipeline_timing,
        market_line_build=market_line_build,
        ready_to_bet_write=ready_to_bet_write,
    )
    return {
        "state_rows": state_rows,
        "notification_rows": coordinated_notification_rows,
        "notification_source_rows": notification_rows,
        "notification_coordinator_shadow_rows": notification_coordination.shadow_rows,
        "notification_coordinator": notification_coordination.summary,
        "mainline_best_price": mainline_best_price_result.summary,
        "mainline_best_price_shadow_rows": mainline_best_price_result.shadow_rows,
        "mainline_best_price_notifications": len(mainline_best_price_result.notification_rows),
        "ready_to_bet_shadow": ready_to_bet_result.summary,
        "ready_to_bet_shadow_write": ready_to_bet_write,
        "ready_to_bet_candidate_rows": ready_to_bet_result.candidate_rows,
        "line_movement_rows": line_movement_rows,
        "propline_webhook_notification_rows": propline_webhook_notification_rows,
        "market_pick_evidence_rows": market_pick_evidence_rows,
        "live_market_display_rows": live_market_display_rows,
        "shadow_notification_candidate_rows": shadow_notification_candidate_rows,
        "provider_heartbeat_rows": provider_heartbeats,
        "reminder_rows": reminder_rows,
        "live_pick_state": len(state_rows),
        "notification_events": len(coordinated_notification_rows),
        "line_movement_events": len(line_movement_rows),
        "propline_webhook_notification_events": len(propline_webhook_notification_rows),
        "stale_propline_webhook_notification_candidates": stale_webhook_notification_candidates,
        "market_pick_evidence": len(market_pick_evidence_rows),
        "live_market_display_state": len(live_market_display_rows),
        "shadow_notification_candidates": len(shadow_notification_candidate_rows),
        "provider_heartbeats": len(provider_heartbeats),
        "game_reminders": len(reminder_rows),
        "therundown": therundown_result or {"skipped": True},
        "propline": propline_result or {"skipped": True},
        "propline_webhooks": propline_webhook_result or {"skipped": True},
        "artifact_source": _public_artifact_source(artifact_source),
        "operational_pick_locks": _public_operational_lock_summary(operational_pick_locks),
        "shadow_pipeline_timing": shadow_pipeline_timing,
        "market_line_build": market_line_build,
        "alternative_pick_selection": alternative_pick_selection,
    }


def main() -> int:
    artifact = DEFAULT_ARTIFACT
    artifact_url = _optional_env("LIVE_ARTIFACT_URL") or DEFAULT_ARTIFACT_URL
    requested_date = sys.argv[1] if len(sys.argv) > 1 else ""
    payload, artifact_sha, artifact_source = _load_artifact(artifact, artifact_url=artifact_url)
    artifact_date = str(payload["date"])
    if requested_date and requested_date != artifact_date:
        print(
            "Requested slate date "
            f"{requested_date} does not match artifact date {artifact_date} "
            f"from {artifact_source}",
            file=sys.stderr,
        )
        return 2
    slate_date = requested_date or artifact_date

    result = run(
        slate_date=slate_date,
        artifact_path=artifact,
        supabase_url=_env("SUPABASE_URL"),
        service_role_key=_env("SUPABASE_SERVICE_ROLE_KEY"),
        poll_propline=bool(_optional_env("PROPLINE_API_KEY")),
        poll_therundown_mainline=_env_flag("LIVE_CAPTURE_THERUNDOWN_MAINLINE", default=False),
        artifact_url=artifact_url,
        artifact_payload=payload,
        artifact_sha=artifact_sha,
        artifact_source=artifact_source,
        build_market_lines=_env_flag("LIVE_BUILD_MARKET_LINES", default=True),
        compact_market_lines=_env_flag("LIVE_COMPACT_MARKET_SNAPSHOTS", default=True),
        process_propline_webhooks=_env_flag("LIVE_PROCESS_PROPLINE_WEBHOOKS", default=True),
        send_propline_webhook_movement_notifications=_env_flag(
            "LIVE_SEND_PROPLINE_WEBHOOK_MOVEMENT_NOTIFICATIONS",
            default=False,
        ),
        propline_webhook_limit=_env_int(
            "LIVE_PROCESS_PROPLINE_WEBHOOK_LIMIT",
            default=DEFAULT_PROPLINE_WEBHOOK_LIMIT,
        ),
        propline_webhook_max_age_minutes=_env_int(
            "LIVE_PROCESS_PROPLINE_WEBHOOK_MAX_AGE_MINUTES",
            default=DEFAULT_PROPLINE_WEBHOOK_MAX_AGE_MINUTES,
        ),
        propline_webhook_notification_max_age_minutes=_env_int(
            "LIVE_PROPLINE_WEBHOOK_NOTIFICATION_MAX_AGE_MINUTES",
            default=DEFAULT_PROPLINE_WEBHOOK_NOTIFICATION_MAX_AGE_MINUTES,
        ),
        market_line_min_interval_seconds=_env_int(
            "LIVE_MARKET_LINE_BUILD_MIN_INTERVAL_SECONDS",
            default=600,
        ),
        compact_market_min_interval_seconds=_env_int(
            "LIVE_MARKET_COMPACTION_MIN_INTERVAL_SECONDS",
            default=1800,
        ),
    )
    propline = result["propline"]
    propline_summary = "propline=skipped"
    if not propline.get("skipped"):
        propline_summary = (
            f"propline_events={propline['target_event_count']} "
            f"propline_snapshots={propline['snapshot_count']}"
        )
    therundown = result.get("therundown") or {"skipped": True}
    therundown_summary = "therundown=skipped"
    if not therundown.get("skipped"):
        if therundown.get("status") == "failed":
            therundown_summary = "therundown=failed"
        else:
            therundown_summary = (
                f"therundown_events={therundown.get('target_event_count', 0)} "
                f"therundown_snapshots={therundown.get('snapshot_count', 0)} "
                f"therundown_datapoints={therundown.get('datapoints', 0)}"
            )
    webhooks = result.get("propline_webhooks") or {"skipped": True}
    webhook_summary = "propline_webhooks=skipped"
    if not webhooks.get("skipped"):
        webhook_summary = (
            f"propline_webhooks=processed:{webhooks.get('processed', 0)} "
            f"movements:{webhooks.get('line_movement_events', 0)}"
        )
    webhook_notification_summary = (
        f"webhook_notifications={result.get('propline_webhook_notification_events', 0)} "
        "stale_webhook_notification_candidates="
        f"{result.get('stale_propline_webhook_notification_candidates', 0)}"
    )
    market_line_build = result.get("market_line_build") or {"skipped": True}
    if market_line_build.get("skipped"):
        market_line_summary = f"market_lines=skipped:{market_line_build.get('reason', 'unknown')}"
    else:
        current_lines = (market_line_build.get("current") or {}).get("current_market_lines", 0)
        official_ready = (market_line_build.get("official") or {}).get("ready_for_pipeline", 0)
        compact_rows = (market_line_build.get("compact") or {}).get("compact_rows", 0)
        market_line_summary = (
            f"market_lines=current:{current_lines} "
            f"official_ready:{official_ready} compact:{compact_rows}"
        )
    print(
        "Live event build "
        f"date={slate_date} state_rows={result['live_pick_state']} "
        f"notification_events={result['notification_events']} "
        f"live_market_display={result.get('live_market_display_state', 0)} "
        f"{_lock_build_summary(result)} "
        "artifact_source="
        f"{'remote' if result.get('artifact_source') == 'remote' or str(result.get('artifact_source', artifact_source)).startswith('http') else 'local'} "
        f"{therundown_summary} "
        f"{propline_summary} "
        f"{webhook_summary} "
        f"{webhook_notification_summary} "
        f"{market_line_summary}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
