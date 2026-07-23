"""Bounded, fail-open runtime recorder for dependency-aware Alt Picks V2."""

from __future__ import annotations

import math
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from market_infra.alternative_pick_evaluation_proof_v2 import build_evaluation_proof_v2
from market_infra.alternative_pick_preclose_v2 import (
    artifact_current_line_ids_v2,
    build_exact_preclose_evidence_v2,
    resolve_candidate_bindings_v2,
    resolve_candidate_windows_v2,
)
from market_infra.alternative_pick_selection_state import (
    APPROVED_ARTIFACT_PATH,
    UNIQUE_COLUMNS,
    build_frozen_row,
    candidate_record,
    frozen_insert_on_conflict,
)
from market_infra.alternative_pick_selection_v2 import build_provisional_row_v2
from market_infra.alternative_pick_selector import display_verdict
from market_infra.alternative_pick_selector_v2 import BUNDLE_ID, evaluate_alternative_pick_v2
from market_infra.supabase_writer import SupabaseMarketWriter


ACTIVE_POSTURES = frozenset({"therundown", "propline", "therundown_propline"})
ACTIVE_PROVIDERS = frozenset({"therundown", "propline"})
PHOENIX = ZoneInfo("America/Phoenix")
MAX_ARTIFACT_AGE = timedelta(minutes=90)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _line(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0 else None


def _american_odds(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return int(parsed) if math.isfinite(parsed) and parsed.is_integer() and parsed != 0 else None


def _utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _postgrest_in(values: list[str]) -> str:
    escaped = [value.replace("\\", "\\\\").replace('"', '\\"') for value in values]
    return "in.(" + ",".join(f'"{value}"' for value in escaped) + ")"


def _summary_failed(value: Any) -> bool:
    if isinstance(value, dict):
        reason = _text(value.get("reason")).lower()
        if value.get("error") or reason == "failed" or reason.endswith("_failed"):
            return True
        return any(_summary_failed(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_summary_failed(item) for item in value)
    return False


def _failure(reason: str) -> dict[str, Any]:
    return {
        "skipped": True,
        "reason": reason,
        "rows": 0,
        "warning": "alternative pick V2 recorder stopped for this cycle",
    }


def _source_posture(pitcher: dict[str, Any]) -> str | None:
    mode = _text(pitcher.get("market_source_mode")).lower().replace("+", "_")
    source = _text(pitcher.get("odds_source")).lower().replace("+", "_")
    if mode:
        if mode not in ACTIVE_POSTURES or source not in ACTIVE_POSTURES or mode != source:
            return None
        return mode
    return source if source in ACTIVE_POSTURES else None


def extract_alternative_pick_candidates_v2(
    *, slate_date: str, payload: dict[str, Any],
) -> list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]]:
    """Extract exact tracked non-PASS candidates from one current official artifact."""
    if not isinstance(payload, dict) or _text(payload.get("date")) != _text(slate_date):
        return []
    candidates: list[tuple[dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    seen: set[str] = set()
    for pitcher in payload.get("pitchers") or []:
        if not isinstance(pitcher, dict):
            continue
        posture = _source_posture(pitcher)
        if posture is None:
            continue
        line_source_provider = _text(pitcher.get("line_source_provider")).lower()
        if line_source_provider not in ACTIVE_PROVIDERS:
            continue
        tracked = pitcher.get("tracked_picks")
        if not isinstance(tracked, list):
            continue
        for pick in tracked:
            if not isinstance(pick, dict) or display_verdict(pick).upper() == "PASS":
                continue
            side = _text(pick.get("side")).lower()
            if side not in {"over", "under"}:
                continue
            raw_line = next((pick.get(field) for field in ("display_k_line", "locked_k_line", "k_line") if pick.get(field) is not None), None)
            line = _line(raw_line)
            game_time = _text(pick.get("game_time") or pitcher.get("game_time"))
            if line is None or _utc(game_time) is None:
                continue
            candidate = candidate_record(
                slate_date=slate_date,
                pitcher=_text(pitcher.get("pitcher") or pick.get("pitcher")),
                side=side,
                model_k_line=line,
                team=_text(pitcher.get("team") or pick.get("team")),
                opp_team=_text(pitcher.get("opp_team") or pick.get("opp_team")),
                game_time=game_time,
                provider_posture=posture,
            )
            candidate.update({
                "line_source_provider": line_source_provider,
                "source_artifact_path": APPROVED_ARTIFACT_PATH,
                "lock_source_artifact_path": APPROVED_ARTIFACT_PATH,
            })
            if candidate["candidate_identity"] in seen:
                continue
            seen.add(candidate["candidate_identity"])
            candidates.append((candidate, pitcher, pick))
    return candidates


def assess_alternative_pick_artifact_v2(
    *, slate_date: str, payload: dict[str, Any], observed_at: datetime,
    require_before_t30: bool,
) -> dict[str, Any]:
    """Pure shared runtime/preflight check for the exact official artifact."""
    observed = observed_at.astimezone(timezone.utc)
    expected_slate_date = observed.astimezone(PHOENIX).date().isoformat()
    if (
        not isinstance(payload, dict)
        or _text(slate_date) != expected_slate_date
        or _text(payload.get("date")) != expected_slate_date
    ):
        return {"ok": False, "reason": "wrong_phoenix_slate_date", "candidates": []}
    generated_at = _utc(payload.get("generated_at"))
    if generated_at is None or generated_at > observed + timedelta(minutes=5):
        return {"ok": False, "reason": "invalid_artifact", "candidates": []}
    if observed - generated_at > MAX_ARTIFACT_AGE:
        return {"ok": False, "reason": "stale_artifact", "candidates": []}

    for pitcher in payload.get("pitchers") or []:
        if not isinstance(pitcher, dict):
            continue
        tracked = pitcher.get("tracked_picks")
        if not isinstance(tracked, list):
            continue
        relevant = [
            pick for pick in tracked
            if isinstance(pick, dict) and display_verdict(pick).upper() != "PASS"
        ]
        if not relevant:
            continue
        if (
            _source_posture(pitcher) is None
            or _text(pitcher.get("line_source_provider")).lower() not in ACTIVE_PROVIDERS
        ):
            return {"ok": False, "reason": "invalid_source_posture", "candidates": []}
        if any(_utc(pick.get("game_time") or pitcher.get("game_time")) is None for pick in relevant):
            return {"ok": False, "reason": "invalid_artifact", "candidates": []}

    candidates = extract_alternative_pick_candidates_v2(slate_date=slate_date, payload=payload)
    if not candidates:
        return {
            "ok": True, "reason": "no_candidates", "candidates": [],
            "candidate_t30": {}, "generated_at": generated_at,
        }
    candidate_t30: dict[str, datetime] = {}
    for candidate, _, _ in candidates:
        game_time = _utc(candidate.get("game_time"))
        if game_time is None:
            return {"ok": False, "reason": "invalid_artifact", "candidates": []}
        candidate_t30[candidate["candidate_identity"]] = game_time - timedelta(minutes=30)
    if require_before_t30 and any(observed >= t30 for t30 in candidate_t30.values()):
        return {
            "ok": False, "reason": "too_late", "candidates": candidates,
            "candidate_t30": candidate_t30, "generated_at": generated_at,
        }
    return {
        "ok": True, "reason": "clean", "candidates": candidates,
        "candidate_t30": candidate_t30, "generated_at": generated_at,
    }


def _evaluation_inputs(
    *, pitcher: dict[str, Any], tracked_pick: dict[str, Any], candidate: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    side = candidate["side"]
    side_payload = pitcher.get(f"ev_{side}")
    pick = dict(side_payload) if isinstance(side_payload, dict) else {}
    for field in (
        "display_verdict", "locked_verdict", "actionable_verdict", "current_verdict",
        "verdict", "raw_verdict", "quality_actionable_verdict", "quality_gate_level",
        "edge", "ev", "adj_ev", "raw_adj_ev", "locked_adj_ev", "market_anchor_selector",
        "large_edge_skepticism_flag", "win_prob", "model_win_prob",
    ):
        if tracked_pick.get(field) is not None:
            pick[field] = tracked_pick[field]
    if tracked_pick.get("display_adj_ev") is not None:
        pick["locked_adj_ev"] = tracked_pick["display_adj_ev"]
    odds = next((tracked_pick.get(field) for field in ("display_odds", "locked_odds", "odds") if tracked_pick.get(field) is not None), None)
    book = next((tracked_pick.get(field) for field in ("display_book", "locked_book", "book") if tracked_pick.get(field) not in {None, ""}), None)
    pick.update({"side": side, "official_k_line": candidate["model_k_line"], "odds": _american_odds(odds)})
    pitcher_input = dict(pitcher)
    pitcher_input.update({"game_time": candidate["game_time"], "k_line": candidate["model_k_line"]})
    for price_side in ("over", "under"):
        pitcher_input[f"best_{price_side}_odds"] = _american_odds(
            pitcher.get(f"best_{price_side}_odds")
        )
    if odds is not None:
        pitcher_input[f"best_{side}_odds"] = _american_odds(odds)
    if book is not None:
        pitcher_input[f"best_{side}_book"] = _text(book)
    try:
        line_matches = abs(float(pitcher.get("k_line")) - float(candidate["model_k_line"])) < 0.001
    except (TypeError, ValueError):
        line_matches = False
    if not line_matches:
        pitcher_input.update({
            "best_over_odds": None, "best_under_odds": None,
            "best_over_book": None, "best_under_book": None,
        })
        if odds is not None:
            pitcher_input[f"best_{side}_odds"] = _american_odds(odds)
        if book is not None:
            pitcher_input[f"best_{side}_book"] = _text(book)
    candidate.update({
        "official_odds": _american_odds(odds),
        "official_book": _text(book).lower(),
        "official_verdict": display_verdict(tracked_pick),
    })
    return pitcher_input, pick


def _persistence_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    return (
        candidate.get("slate_date"), candidate.get("game_identity"),
        candidate.get("normalized_pitcher"), candidate.get("side"), BUNDLE_ID,
    )


def _window_state_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """Adapt the persisted full proof to the pure window resolver's compact prior shape."""
    if not isinstance(row, dict):
        return None
    proof = row.get("evaluation_proof")
    if isinstance(proof, str):
        try:
            proof = json.loads(proof)
        except json.JSONDecodeError:
            proof = {}
    if not isinstance(proof, dict) or "exact_preclose" in proof:
        return row
    bindings = proof.get("bindings")
    if not isinstance(bindings, dict):
        return row
    official_key = None
    sidecar_keys: dict[str, str] = {}
    starts: dict[str, str] = {}
    for provider, binding in bindings.items():
        if not isinstance(binding, dict):
            continue
        key = _text(binding.get("binding_key"))
        started_at = _text(binding.get("window_started_at"))
        if key and binding.get("role") == "official":
            official_key = key
        elif key and binding.get("role") == "sidecar":
            sidecar_keys[_text(provider).lower()] = key
        if started_at:
            starts[_text(provider).lower()] = started_at
    return {
        **row,
        "evaluation_proof": {
            "exact_preclose": {
                "official_binding_key": official_key,
                "sidecar_binding_keys": sidecar_keys,
                "provider_window_started_at": starts,
            },
        },
    }


def _record_alternative_pick_selection_v2_impl(
    *, writer: SupabaseMarketWriter, slate_date: str, payload: dict[str, Any],
    snapshot_rows: list[dict[str, Any]], provider_heartbeats: list[dict[str, Any]],
    observed_at: datetime, artifact_source: str, source_payload_sha256: str,
    source_artifact_byte_sha256: str, operational_pick_locks: dict[str, Any],
    market_line_build: dict[str, Any], shadow_pipeline_timing: dict[str, Any],
    ready_to_bet_write: dict[str, Any], budget_seconds: float = 5.0,
) -> dict[str, Any]:
    """Record V2 state with one-attempt reads and no provider or broad-evidence input."""
    del artifact_source
    if any(_summary_failed(summary) for summary in (
        operational_pick_locks, market_line_build, shadow_pipeline_timing, ready_to_bet_write,
    )):
        return {"skipped": True, "reason": "prerequisite_failed", "rows": 0}
    started = time.monotonic()

    def remaining() -> float:
        return budget_seconds - (time.monotonic() - started)

    assessment = assess_alternative_pick_artifact_v2(
        slate_date=slate_date, payload=payload, observed_at=observed_at,
        require_before_t30=False,
    )
    if not assessment["ok"] or assessment["reason"] == "no_candidates":
        return {"skipped": True, "reason": assessment["reason"], "rows": 0}
    candidates = assessment["candidates"]
    candidate_t30 = assessment["candidate_t30"]
    by_key: dict[tuple[Any, ...], set[str]] = {}
    by_lock: dict[str, set[str]] = {}
    for candidate, _, _ in candidates:
        identity = candidate["candidate_identity"]
        by_key.setdefault(_persistence_key(candidate), set()).add(identity)
        lock_key = f"{slate_date}:{candidate['normalized_pitcher']}:{candidate['side']}"
        by_lock.setdefault(lock_key, set()).add(identity)
    collisions = sum(len(values) > 1 for values in by_key.values()) + sum(len(values) > 1 for values in by_lock.values())
    if collisions:
        return {"skipped": True, "reason": "candidate_key_collision", "rows": 0, "collisions": collisions}

    line_ids = sorted({identifier for _, pitcher, _ in candidates for identifier in artifact_current_line_ids_v2(pitcher)})
    dedupe_keys = sorted(by_lock)
    try:
        if remaining() <= 0:
            return _failure("timeout")
        existing_rows = writer.select_rows(
            "alternative_pick_selection_state",
            {"slate_date": f"eq.{slate_date}", "bundle_id": f"eq.{BUNDLE_ID}",
             "checkpoint": "in.(provisional,frozen_pregame)",
             "select": "slate_date,game_identity,candidate_identity,candidate_became_current_at,normalized_pitcher,side,bundle_id,checkpoint,observed_at,game_time,evaluation_proof"},
            timeout_seconds=remaining(), attempts=1,
        )
        if remaining() <= 0:
            return _failure("timeout")
        lock_rows = writer.select_rows(
            "operational_pick_locks",
            {"slate_date": f"eq.{slate_date}", "dedupe_key": _postgrest_in(dedupe_keys),
             "select": "dedupe_key,slate_date,normalized_pitcher,side,locked_k_line,game_time,locked_odds,locked_book,status_at_capture,observed_at,locked_at,should_lock_at,minutes_until_start,source_artifact_path,source_artifact_sha256,metadata"},
            timeout_seconds=remaining(), attempts=1,
        )
        current_line_rows: list[dict[str, Any]] = []
        if line_ids:
            if remaining() <= 0:
                return _failure("timeout")
            current_line_rows = writer.select_rows(
                "current_market_lines",
                {"slate_date": f"eq.{slate_date}", "id": _postgrest_in(line_ids),
                 "select": "id,slate_date,provider,provider_event_id,normalized_player_name,market_key,line,game_time,over_snapshot_id,under_snapshot_id"},
                timeout_seconds=remaining(), attempts=1,
            )
    except TimeoutError:
        return _failure("timeout")
    except Exception:
        return _failure("failed")

    if not isinstance(existing_rows, list) or not isinstance(lock_rows, list) or not isinstance(current_line_rows, list):
        return _failure("failed")
    inserted = operational_pick_locks.get("inserted_lock_rows") or operational_pick_locks.get("lock_rows")
    if isinstance(inserted, list):
        lock_rows = [*lock_rows, *inserted]
    current_lines_by_id: dict[str, dict[str, Any]] = {}
    for row in current_line_rows:
        identifier = _text(row.get("id")) if isinstance(row, dict) else ""
        if identifier not in line_ids or identifier in current_lines_by_id:
            return _failure("failed")
        current_lines_by_id[identifier] = row

    observed_utc = observed_at.astimezone(timezone.utc)
    observed_iso = observed_utc.isoformat()
    artifact = {
        "path": APPROVED_ARTIFACT_PATH, "payload": payload,
        "payload_sha256": source_payload_sha256, "byte_sha256": source_artifact_byte_sha256,
        "generated_at": payload.get("generated_at"),
    }
    provisional_rows: list[dict[str, Any]] = []
    frozen_rows: list[dict[str, Any]] = []
    too_late_without_lock = 0
    for candidate, pitcher, tracked_pick in candidates:
        matching = [
            row for row in existing_rows if isinstance(row, dict)
            and tuple(row.get(field) for field in UNIQUE_COLUMNS[:5]) == _persistence_key(candidate)
        ]
        if any(row.get("checkpoint") == "frozen_pregame" for row in matching):
            continue
        lock_key = f"{slate_date}:{candidate['normalized_pitcher']}:{candidate['side']}"
        candidate_locks = [row for row in lock_rows if isinstance(row, dict) and row.get("dedupe_key") == lock_key]
        current_lock = next((row for row in candidate_locks if _utc(row.get("locked_at")) == observed_utc and _utc(row.get("observed_at")) == observed_utc), None)
        if candidate_locks and current_lock is None:
            continue
        if current_lock is None and observed_utc >= candidate_t30[candidate["candidate_identity"]]:
            too_late_without_lock += 1
            continue
        prior = next((row for row in matching if row.get("checkpoint") == "provisional"), None)
        try:
            bindings = resolve_candidate_bindings_v2(
                candidate=candidate, pitcher=pitcher,
                current_lines_by_id=current_lines_by_id, snapshot_rows=snapshot_rows,
            )
            windows = resolve_candidate_windows_v2(
                candidate=candidate, bindings=bindings,
                existing_state_row=_window_state_row(prior), observed_at=observed_at,
            )
            exact = build_exact_preclose_evidence_v2(
                candidate=candidate, bindings=bindings, windows=windows,
                snapshot_rows=snapshot_rows, provider_heartbeats=provider_heartbeats,
                observed_at=observed_at, source_artifact_path=APPROVED_ARTIFACT_PATH,
                source_artifact_byte_sha256=source_artifact_byte_sha256,
            )
            pitcher_input, pick_input = _evaluation_inputs(
                pitcher=pitcher, tracked_pick=tracked_pick, candidate=candidate,
            )
            evaluation = evaluate_alternative_pick_v2(
                pitcher=pitcher_input, pick=pick_input, exact_evidence=exact.market_evidence,
                slate_date=slate_date, is_tracked=True,
                source_artifact_path=APPROVED_ARTIFACT_PATH,
                source_payload_sha256=source_payload_sha256,
                source_artifact_byte_sha256=source_artifact_byte_sha256,
                observed_at=observed_iso,
            )
            if evaluation.eligible is not True:
                continue
            proof = build_evaluation_proof_v2(
                candidate=candidate, evaluation=evaluation, exact_preclose=exact, artifact=artifact,
            )
            provisional = build_provisional_row_v2(
                candidate=candidate, evaluation=evaluation, exact_preclose=exact,
                proof_build=proof, artifact=artifact, observed_at=observed_iso,
            )
        except Exception:
            return _failure("failed")
        if provisional is None:
            continue
        if current_lock is not None:
            frozen = build_frozen_row(
                provisional_row=provisional, lock_row=current_lock, observed_at=observed_iso,
            )
            if frozen is None:
                return _failure("failed")
            frozen_rows.append(frozen)
        else:
            provisional_rows.append(provisional)
        if remaining() <= 0:
            return _failure("timeout")

    try:
        if frozen_rows:
            timeout = remaining()
            if timeout <= 0:
                return _failure("timeout")
            writer.insert_ignore_rows(
                "alternative_pick_selection_state", frozen_rows,
                on_conflict=frozen_insert_on_conflict(), timeout_seconds=timeout,
            )
        if provisional_rows:
            timeout = remaining()
            if timeout <= 0:
                return _failure("timeout")
            writer.upsert_rows(
                "alternative_pick_selection_state", provisional_rows,
                on_conflict=",".join(UNIQUE_COLUMNS), timeout_seconds=timeout,
            )
    except TimeoutError:
        return _failure("timeout")
    except Exception:
        return _failure("failed")
    if not provisional_rows and not frozen_rows and too_late_without_lock:
        return {"skipped": True, "reason": "too_late", "rows": 0}
    return {
        "skipped": False, "rows": len(provisional_rows) + len(frozen_rows),
        "provisional_rows": len(provisional_rows), "frozen_rows": len(frozen_rows),
        "collisions": 0,
    }


def record_alternative_pick_selection_v2(
    *, writer: SupabaseMarketWriter, slate_date: str, payload: dict[str, Any],
    snapshot_rows: list[dict[str, Any]], provider_heartbeats: list[dict[str, Any]],
    observed_at: datetime, artifact_source: str, source_payload_sha256: str,
    source_artifact_byte_sha256: str, operational_pick_locks: dict[str, Any],
    market_line_build: dict[str, Any], shadow_pipeline_timing: dict[str, Any],
    ready_to_bet_write: dict[str, Any], budget_seconds: float = 5.0,
) -> dict[str, Any]:
    """Contain every V2 sidecar failure, including candidate preparation and dispatch."""
    try:
        return _record_alternative_pick_selection_v2_impl(
            writer=writer, slate_date=slate_date, payload=payload,
            snapshot_rows=snapshot_rows, provider_heartbeats=provider_heartbeats,
            observed_at=observed_at, artifact_source=artifact_source,
            source_payload_sha256=source_payload_sha256,
            source_artifact_byte_sha256=source_artifact_byte_sha256,
            operational_pick_locks=operational_pick_locks,
            market_line_build=market_line_build,
            shadow_pipeline_timing=shadow_pipeline_timing,
            ready_to_bet_write=ready_to_bet_write, budget_seconds=budget_seconds,
        )
    except TimeoutError:
        return _failure("timeout")
    except Exception:
        return _failure("failed")
