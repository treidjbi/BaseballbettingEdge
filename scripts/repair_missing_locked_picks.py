"""Recover missing official history rows from immutable pregame lock evidence.

The repair is fail-closed. A row is reconstructed only when a consumed
``operational_pick_locks`` row and a frozen Alt V2 evaluation proof agree on
the exact pick, line, price, verdict, adjusted EV, and lock time. The retained
dated archive supplies stable pitcher/model fields. Recovered rows remain
visible in official performance but are marked ``data_complete=0`` so they do
not alter calibration from partially reconstructed model inputs.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipeline.name_utils import normalize  # noqa: E402
from scripts.compare_supabase_artifacts import (  # noqa: E402
    parse_supabase_cli_rows,
    resolve_npx_command,
)


RECOVERY_FLAG = "history_recovered_from_lock_evidence"
PUBLICATION_SOURCE = "manual_backfill"
NUMERIC_TOLERANCE = 0.00015
EV_TOLERANCE = 0.0015


def _timestamp(value: Any) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        raise ValueError("required timestamp is missing")
    return datetime.fromisoformat(text)


def _same_timestamp(left: Any, right: Any) -> bool:
    return _timestamp(left) == _timestamp(right)


def _number(value: Any, label: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be numeric") from error


def _same_number(left: Any, right: Any, tolerance: float = NUMERIC_TOLERANCE) -> bool:
    try:
        return abs(float(left) - float(right)) <= tolerance
    except (TypeError, ValueError):
        return False


def _implied_probability(odds: int) -> float:
    if odds == 0:
        raise ValueError("American odds cannot be zero")
    if odds > 0:
        return 100.0 / (odds + 100.0)
    return abs(odds) / (abs(odds) + 100.0)


def _flat_unit_ev(*, odds: int, edge: float) -> float:
    win_probability = _implied_probability(odds) + edge
    if not 0.0 <= win_probability <= 1.0:
        raise ValueError("lock-time edge implies an invalid win probability")
    payout = odds / 100.0 if odds > 0 else 100.0 / abs(odds)
    return win_probability * payout - (1.0 - win_probability)


def _effective_verdict(side_data: dict[str, Any]) -> str:
    return str(
        side_data.get("actionable_verdict")
        or side_data.get("verdict")
        or ""
    ).strip()


def _key(pitcher: Any, side: Any) -> tuple[str, str]:
    return normalize(str(pitcher or "")), str(side or "").strip().lower()


def _exactly_one(rows: list[dict[str, Any]], *, label: str) -> dict[str, Any]:
    if len(rows) != 1:
        raise ValueError(f"expected exactly one {label}; found {len(rows)}")
    return rows[0]


def _validate_lock(lock: dict[str, Any]) -> None:
    if not lock.get("consumed_at"):
        raise ValueError("expected exactly one consumed lock; lock is unconsumed")
    if not _same_timestamp(lock.get("observed_at"), lock.get("locked_at")):
        raise ValueError("consumed lock observed_at and locked_at disagree")
    if _timestamp(lock.get("locked_at")) >= _timestamp(lock.get("game_time")):
        raise ValueError("consumed lock was not captured before game time")
    source_sha = str(lock.get("source_artifact_sha256") or "")
    if len(source_sha) != 64:
        raise ValueError("consumed lock is missing a valid source artifact hash")


def _validate_frozen_proof(
    *,
    lock: dict[str, Any],
    state: dict[str, Any],
) -> dict[str, Any]:
    proof = state.get("evaluation_proof") or {}
    inputs = proof.get("normalized_inputs") if isinstance(proof, dict) else None
    if not isinstance(inputs, dict):
        raise ValueError("frozen proof does not match lock: normalized inputs missing")

    text_checks = (
        (inputs.get("pitcher"), lock.get("normalized_pitcher")),
        (inputs.get("side"), lock.get("side")),
        (inputs.get("official_verdict"), lock.get("locked_verdict")),
        (state.get("official_verdict"), lock.get("locked_verdict")),
    )
    numeric_checks = (
        (inputs.get("k_line"), lock.get("locked_k_line")),
        (inputs.get("odds"), lock.get("locked_odds")),
        (inputs.get("adjusted_ev"), lock.get("locked_adj_ev")),
        (state.get("official_odds"), lock.get("locked_odds")),
    )
    timestamp_checks = (
        (inputs.get("game_time"), lock.get("game_time")),
        (inputs.get("observed_at"), lock.get("locked_at")),
        (state.get("locked_at"), lock.get("locked_at")),
    )
    if any(str(left or "").strip().lower() != str(right or "").strip().lower() for left, right in text_checks):
        raise ValueError("frozen proof does not match lock")
    if any(not _same_number(left, right) for left, right in numeric_checks):
        raise ValueError("frozen proof does not match lock")
    if any(not _same_timestamp(left, right) for left, right in timestamp_checks):
        raise ValueError("frozen proof does not match lock")
    if state.get("lock_artifact_sha256") != lock.get("source_artifact_sha256"):
        raise ValueError("frozen proof does not match lock")

    edge = _number(inputs.get("edge"), "frozen proof edge")
    adjusted_ev = _number(inputs.get("adjusted_ev"), "frozen proof adjusted_ev")
    exact_ev = _flat_unit_ev(odds=int(lock["locked_odds"]), edge=edge)
    if abs(exact_ev - adjusted_ev) > EV_TOLERANCE:
        raise ValueError("frozen proof adjusted EV is inconsistent with its edge and price")
    if not str(inputs.get("source_fire_verdict") or "").strip():
        raise ValueError("frozen proof is missing source_fire_verdict")
    return inputs


def _validate_archive_identity(
    *,
    archive: dict[str, Any],
    pitcher_row: dict[str, Any],
    lock: dict[str, Any],
) -> None:
    archive_date = str(archive.get("date") or archive.get("slate_date") or "")
    if archive_date != str(lock.get("slate_date") or ""):
        raise ValueError("dated archive does not match lock slate date")
    if not _same_number(pitcher_row.get("k_line"), lock.get("locked_k_line")):
        raise ValueError("dated archive line does not match lock")
    if not _same_timestamp(pitcher_row.get("game_time"), lock.get("game_time")):
        raise ValueError("dated archive game time does not match lock")
    metadata = lock.get("metadata") or {}
    for field in ("team", "opp_team"):
        if str(pitcher_row.get(field) or "").strip().lower() != str(metadata.get(field) or "").strip().lower():
            raise ValueError(f"dated archive {field} does not match lock metadata")
    if pitcher_row.get("lambda") is None or pitcher_row.get("raw_lambda") is None:
        raise ValueError("dated archive is missing required lambda fields")


def _archive_core_matches(
    *,
    pitcher_row: dict[str, Any],
    side_data: dict[str, Any],
    lock: dict[str, Any],
    proof_inputs: dict[str, Any],
) -> bool:
    selected_odds = pitcher_row.get(
        "best_over_odds" if lock["side"] == "over" else "best_under_odds"
    )
    return all(
        (
            _same_number(pitcher_row.get("k_line"), lock.get("locked_k_line")),
            _same_number(selected_odds, lock.get("locked_odds")),
            _same_number(side_data.get("adj_ev"), lock.get("locked_adj_ev")),
            _same_number(side_data.get("edge"), proof_inputs.get("edge")),
            _effective_verdict(side_data) == str(lock.get("locked_verdict") or ""),
            str(side_data.get("raw_verdict") or "")
            == str(proof_inputs.get("source_fire_verdict") or ""),
        )
    )


def _history_row(
    *,
    archive: dict[str, Any],
    pitcher_row: dict[str, Any],
    side_data: dict[str, Any],
    lock: dict[str, Any],
    proof_inputs: dict[str, Any],
    archive_core_match: bool,
) -> dict[str, Any]:
    side = str(lock["side"])
    flags = [
        str(value)
        for value in (pitcher_row.get("input_quality_flags") or [])
        if str(value).strip()
    ]
    if RECOVERY_FLAG not in flags:
        flags.append(RECOVERY_FLAG)
    selected_adj_ev = _number(lock.get("locked_adj_ev"), "locked_adj_ev")
    selected_edge = _number(proof_inputs.get("edge"), "frozen proof edge")
    selected_odds = int(lock["locked_odds"])
    selected_ev = _flat_unit_ev(odds=selected_odds, edge=selected_edge)
    best_over_odds = pitcher_row.get("best_over_odds")
    best_under_odds = pitcher_row.get("best_under_odds")
    if side == "over":
        best_over_odds = selected_odds
    else:
        best_under_odds = selected_odds

    return {
        "date": str(lock["slate_date"]),
        "pitcher": str(lock["pitcher"]),
        "team": pitcher_row.get("team"),
        "opp_team": pitcher_row.get("opp_team"),
        "pitcher_throws": pitcher_row.get("pitcher_throws"),
        "side": side,
        "k_line": float(lock["locked_k_line"]),
        "verdict": str(lock["locked_verdict"]),
        "raw_verdict": str(proof_inputs["source_fire_verdict"]),
        "actionable_verdict": str(lock["locked_verdict"]),
        "edge": selected_edge,
        "ev": selected_ev,
        "adj_ev": selected_adj_ev,
        "raw_adj_ev": selected_adj_ev,
        "raw_lambda": pitcher_row.get("raw_lambda"),
        "applied_lambda": pitcher_row.get("lambda"),
        "odds": selected_odds,
        "movement_conf": 1.0,
        "season_k9": pitcher_row.get("season_k9"),
        "recent_k9": pitcher_row.get("recent_k9"),
        "career_k9": pitcher_row.get("career_k9"),
        "avg_ip": pitcher_row.get("avg_ip"),
        "ump_k_adj": pitcher_row.get("ump_k_adj"),
        "opp_k_rate": pitcher_row.get("opp_k_rate"),
        "swstr_delta_k9": pitcher_row.get("swstr_delta_k9"),
        "swstr_pct": pitcher_row.get("swstr_pct"),
        "career_swstr_pct": pitcher_row.get("career_swstr_pct"),
        "ref_book": lock.get("locked_book") or pitcher_row.get("ref_book"),
        "best_over_odds": best_over_odds,
        "best_under_odds": best_under_odds,
        "opening_over_odds": pitcher_row.get("opening_over_odds"),
        "opening_under_odds": pitcher_row.get("opening_under_odds"),
        "opening_odds_source": pitcher_row.get("opening_odds_source"),
        "is_opener": int(bool(pitcher_row.get("is_opener", False))),
        "opener_note": pitcher_row.get("opener_note"),
        "days_since_last_start": proof_inputs.get(
            "days_since_last_start", pitcher_row.get("days_since_last_start")
        ),
        "last_pitch_count": proof_inputs.get(
            "last_pitch_count", pitcher_row.get("last_pitch_count")
        ),
        "rest_k9_delta": pitcher_row.get("rest_k9_delta"),
        "park_factor": pitcher_row.get("park_factor"),
        "result": None,
        "actual_ks": None,
        "pnl": None,
        "fetched_at": None,
        "game_time": pitcher_row.get("game_time"),
        "lineup_used": int(bool(pitcher_row.get("lineup_used", False))),
        "locked_at": lock.get("locked_at"),
        "locked_k_line": float(lock["locked_k_line"]),
        "locked_odds": selected_odds,
        "locked_adj_ev": selected_adj_ev,
        "locked_verdict": str(lock["locked_verdict"]),
        "data_complete": 0,
        "quality_gate_level": proof_inputs.get("quality_gate_level"),
        "input_quality_flags": flags,
        "verdict_cap_reason": pitcher_row.get("verdict_cap_reason"),
        "data_maturity": pitcher_row.get("data_maturity"),
        "confidence_referee": side_data.get("confidence_referee") if archive_core_match else None,
        "market_anchor_selector": side_data.get("market_anchor_selector") if archive_core_match else None,
        "projection_challenger": side_data.get("projection_challenger") if archive_core_match else None,
    }


def reconstruct_missing_history_rows(
    *,
    history: list[dict[str, Any]],
    archive: dict[str, Any],
    locks: list[dict[str, Any]],
    frozen_states: list[dict[str, Any]],
    expected_keys: list[tuple[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return reconstructed rows and an audit without mutating the inputs."""
    existing_keys = {
        (str(row.get("date") or row.get("slate_date") or ""), *_key(row.get("pitcher"), row.get("side")))
        for row in history
        if isinstance(row, dict)
    }
    archive_rows = [row for row in archive.get("pitchers", []) if isinstance(row, dict)]
    reconstructed: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []

    for expected_pitcher, expected_side in expected_keys:
        normalized_pitcher, side = _key(expected_pitcher, expected_side)
        if not normalized_pitcher or side not in {"over", "under"}:
            raise ValueError(f"invalid expected pick: {expected_pitcher}|{expected_side}")

        matching_locks = [
            row
            for row in locks
            if _key(row.get("pitcher"), row.get("side")) == (normalized_pitcher, side)
            and row.get("consumed_at")
        ]
        lock = _exactly_one(matching_locks, label="consumed lock")
        slate_date = str(lock.get("slate_date") or "")
        if (slate_date, normalized_pitcher, side) in existing_keys:
            raise ValueError(f"history row already exists for {slate_date}:{normalized_pitcher}:{side}")
        _validate_lock(lock)

        state = _exactly_one(
            [
                row
                for row in frozen_states
                if row.get("checkpoint") == "frozen_pregame"
                and _key(row.get("pitcher"), row.get("side")) == (normalized_pitcher, side)
            ],
            label="frozen state",
        )
        proof_inputs = _validate_frozen_proof(lock=lock, state=state)

        pitcher_row = _exactly_one(
            [row for row in archive_rows if normalize(str(row.get("pitcher") or "")) == normalized_pitcher],
            label="dated archive pitcher",
        )
        _validate_archive_identity(archive=archive, pitcher_row=pitcher_row, lock=lock)
        side_data = pitcher_row.get(f"ev_{side}")
        if not isinstance(side_data, dict):
            raise ValueError("dated archive is missing selected-side model data")
        core_match = _archive_core_matches(
            pitcher_row=pitcher_row,
            side_data=side_data,
            lock=lock,
            proof_inputs=proof_inputs,
        )
        reconstructed.append(
            _history_row(
                archive=archive,
                pitcher_row=pitcher_row,
                side_data=side_data,
                lock=lock,
                proof_inputs=proof_inputs,
                archive_core_match=core_match,
            )
        )
        audit.append(
            {
                "date": slate_date,
                "pitcher": str(lock["pitcher"]),
                "side": side,
                "archive_core_match": core_match,
                "calibration_quarantined": True,
            }
        )

    return reconstructed, audit


def load_live_evidence_with_writer(writer: Any, slate_date: str) -> dict[str, Any]:
    """Load full canonical artifacts plus bounded lock/proof evidence for execution."""
    artifact_keys = (
        "picks_history",
        f"dated_slate:{slate_date}",
        "performance",
        "params",
        "index",
    )
    artifact_rows = writer.select_rows(
        "published_pipeline_artifacts",
        {
            "artifact_key": f"in.({','.join(artifact_keys)})",
            "select": "artifact_key,payload,payload_sha256,published_at",
            "limit": str(len(artifact_keys)),
        },
        timeout_seconds=60,
    )
    by_key = {
        str(row.get("artifact_key")): row.get("payload")
        for row in artifact_rows
        if isinstance(row, dict)
    }
    missing_keys = [key for key in artifact_keys if key not in by_key]
    if missing_keys:
        raise ValueError(f"canonical repair artifacts are missing: {','.join(missing_keys)}")
    if not isinstance(by_key["picks_history"], list):
        raise ValueError("canonical picks_history artifact is malformed")
    if not isinstance(by_key[f"dated_slate:{slate_date}"], dict):
        raise ValueError("canonical dated archive artifact is malformed")
    for key in ("performance", "params", "index"):
        if not isinstance(by_key[key], dict):
            raise ValueError(f"canonical {key} artifact is malformed")

    locks = writer.select_rows(
        "operational_pick_locks",
        {
            "slate_date": f"eq.{slate_date}",
            "select": "*",
            "order": "normalized_pitcher.asc,side.asc",
            "limit": "100",
        },
    )
    frozen_states = writer.select_rows(
        "alternative_pick_selection_state",
        {
            "slate_date": f"eq.{slate_date}",
            "checkpoint": "eq.frozen_pregame",
            "select": "*",
            "order": "normalized_pitcher.asc,side.asc",
            "limit": "200",
        },
    )
    return {
        "history": by_key["picks_history"],
        "archive": by_key[f"dated_slate:{slate_date}"],
        "performance": by_key["performance"],
        "params": by_key["params"],
        "index": by_key["index"],
        "locks": locks,
        "frozen_states": frozen_states,
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def stage_repair_artifacts(
    *,
    root: Path,
    slate_date: str,
    evidence: dict[str, Any],
    reconstructed_rows: list[dict[str, Any]],
) -> None:
    """Stage canonical inputs and reconstructed open rows for normal grading."""
    combined_history = [*evidence["history"], *reconstructed_rows]
    combined_history.sort(
        key=lambda row: (
            str(row.get("date") or row.get("slate_date") or ""),
            normalize(str(row.get("pitcher") or "")),
            str(row.get("side") or ""),
        )
    )
    _write_json(root / "data/picks_history.json", combined_history)
    _write_json(
        root / "dashboard/data/processed" / f"{slate_date}.json",
        evidence["archive"],
    )
    _write_json(root / "dashboard/data/performance.json", evidence["performance"])
    _write_json(root / "data/params.json", evidence["params"])
    _write_json(root / "dashboard/data/processed/index.json", evidence["index"])


def verify_graded_recoveries(
    *,
    history: list[dict[str, Any]],
    slate_date: str,
    expected_keys: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for expected_pitcher, expected_side in expected_keys:
        normalized_pitcher, side = _key(expected_pitcher, expected_side)
        matches = [
            row
            for row in history
            if str(row.get("date") or row.get("slate_date") or "") == slate_date
            and _key(row.get("pitcher"), row.get("side")) == (normalized_pitcher, side)
        ]
        row = _exactly_one(matches, label="graded recovered history row")
        if row.get("result") not in {"win", "loss", "push", "void"}:
            raise ValueError(f"recovered history row did not grade: {expected_pitcher}|{side}")
        if row.get("actual_ks") is None and row.get("result") != "void":
            raise ValueError(f"recovered history row is missing actual Ks: {expected_pitcher}|{side}")
        if not row.get("locked_at") or row.get("locked_odds") is None:
            raise ValueError(f"recovered history row lost lock fields: {expected_pitcher}|{side}")
        if RECOVERY_FLAG not in (row.get("input_quality_flags") or []):
            raise ValueError(f"recovered history row lost provenance flag: {expected_pitcher}|{side}")
        summaries.append(
            {
                "date": slate_date,
                "pitcher": row.get("pitcher"),
                "side": side,
                "result": row.get("result"),
                "actual_ks": row.get("actual_ks"),
                "pnl": row.get("pnl"),
            }
        )
    return summaries


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _source_commit_sha(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def execute_repair(
    *,
    writer: Any,
    slate_date: str,
    expected_keys: list[tuple[str, str]],
    evidence: dict[str, Any],
    reconstructed_rows: list[dict[str, Any]],
    source_run_id: str,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Grade, rebuild, and atomically publish only the approved artifact scope."""
    if root.resolve() != ROOT.resolve():
        raise ValueError("execute_repair must run from its checked-out repository root")
    stage_repair_artifacts(
        root=root,
        slate_date=slate_date,
        evidence=evidence,
        reconstructed_rows=reconstructed_rows,
    )

    pipeline_dir = str(root / "pipeline")
    if pipeline_dir not in sys.path:
        sys.path.insert(0, pipeline_dir)
    import calibrate  # noqa: PLC0415
    import fetch_results  # noqa: PLC0415
    import run_pipeline  # noqa: PLC0415
    from scripts.publish_pipeline_artifacts_to_supabase import run as publish_artifacts  # noqa: PLC0415

    fetch_results.reset_db()
    fetch_results.init_db()
    loaded = fetch_results.load_history_into_db(root / "data/picks_history.json")
    expected_loaded = len(evidence["history"]) + len(reconstructed_rows)
    if loaded != expected_loaded:
        raise ValueError(
            f"staged history load mismatch: expected {expected_loaded}, loaded {loaded}"
        )
    closed = fetch_results.fetch_and_close_results()
    fetch_results.export_db_to_history(root / "data/picks_history.json")
    graded_history = json.loads(
        (root / "data/picks_history.json").read_text(encoding="utf-8")
    )
    graded_rows = verify_graded_recoveries(
        history=graded_history,
        slate_date=slate_date,
        expected_keys=expected_keys,
    )

    calibrate.run()
    run_pipeline._enrich_archives_with_results()
    tracked_archives = run_pipeline._enrich_archives_with_tracked_picks(
        date_filter=slate_date,
        include_today=False,
    )
    run_pipeline._refresh_index_json()
    if tracked_archives != 1:
        raise ValueError(
            f"expected one tracked dated archive rebuild; rebuilt {tracked_archives}"
        )

    previous_run_type = os.environ.get("PIPELINE_RUN_TYPE")
    os.environ["PIPELINE_RUN_TYPE"] = "grading"
    try:
        publication = publish_artifacts(
            root=root,
            writer=writer,
            slate_date=slate_date,
            source=PUBLICATION_SOURCE,
            source_run_id=source_run_id,
            source_commit_sha=_source_commit_sha(root),
            execute=True,
            scope="grading",
        )
    finally:
        if previous_run_type is None:
            os.environ.pop("PIPELINE_RUN_TYPE", None)
        else:
            os.environ["PIPELINE_RUN_TYPE"] = previous_run_type
    return {
        "reconstructed_rows": len(reconstructed_rows),
        "graded_rows": graded_rows,
        "closed_rows_during_repair": closed,
        "publication": publication,
    }


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def load_live_evidence_with_cli(
    slate_date: str,
    *,
    linked_root: Path = ROOT,
) -> dict[str, Any]:
    """Read only the bounded repair evidence through the linked Supabase CLI."""
    date_literal = _sql_literal(slate_date)
    history_date = (
        "coalesce(history_row.value->>'date', history_row.value->>'slate_date')"
    )
    sql = " ".join(
        (
            "with history as (",
            "select coalesce(jsonb_agg(history_row.value), '[]'::jsonb) as rows",
            "from public.published_pipeline_artifacts artifact",
            "cross join lateral jsonb_array_elements(artifact.payload) history_row(value)",
            "where artifact.artifact_key = 'picks_history'",
            f"and {history_date} = {date_literal}),",
            "archive as (select payload from public.published_pipeline_artifacts",
            f"where artifact_key = 'dated_slate:' || {date_literal} limit 1),",
            "locks as (select coalesce(jsonb_agg(to_jsonb(lock_row)), '[]'::jsonb) as rows",
            "from public.operational_pick_locks lock_row",
            f"where lock_row.slate_date = {date_literal}::date),",
            "states as (select coalesce(jsonb_agg(to_jsonb(state_row)), '[]'::jsonb) as rows",
            "from public.alternative_pick_selection_state state_row",
            f"where state_row.slate_date = {date_literal}::date",
            "and state_row.checkpoint = 'frozen_pregame')",
            "select history.rows as history, archive.payload as archive,",
            "locks.rows as locks, states.rows as frozen_states",
            "from history cross join archive cross join locks cross join states;",
        )
    )
    result = subprocess.run(
        [
            resolve_npx_command(),
            "supabase",
            "db",
            "query",
            "--linked",
            "-o",
            "json",
            sql,
        ],
        cwd=linked_root,
        check=True,
        capture_output=True,
        text=True,
    )
    rows = parse_supabase_cli_rows(result.stdout)
    if len(rows) != 1:
        raise ValueError(f"expected one Supabase repair evidence row; found {len(rows)}")
    evidence = rows[0]
    if not isinstance(evidence.get("history"), list):
        raise ValueError("Supabase repair evidence history is malformed")
    if not isinstance(evidence.get("archive"), dict):
        raise ValueError("Supabase repair evidence archive is missing or malformed")
    if not isinstance(evidence.get("locks"), list):
        raise ValueError("Supabase repair evidence locks are malformed")
    if not isinstance(evidence.get("frozen_states"), list):
        raise ValueError("Supabase repair evidence frozen states are malformed")
    return evidence


def _expected_pick(value: str) -> tuple[str, str]:
    pitcher, separator, side = value.rpartition("|")
    if not separator or not normalize(pitcher) or side.strip().lower() not in {"over", "under"}:
        raise argparse.ArgumentTypeError("expected pick must use 'Pitcher Name|over' or 'Pitcher Name|under'")
    return pitcher.strip(), side.strip().lower()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    parser.add_argument(
        "--linked-root",
        type=Path,
        default=ROOT,
        help="Repo root containing the linked Supabase CLI metadata.",
    )
    parser.add_argument(
        "--expected-pick",
        action="append",
        type=_expected_pick,
        required=True,
        help="Exact missing pick as 'Pitcher Name|over' or 'Pitcher Name|under'.",
    )
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--source-run-id")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    writer = None
    if args.execute:
        from market_infra.supabase_writer import SupabaseMarketWriter

        writer = SupabaseMarketWriter(
            _required_env("SUPABASE_URL"),
            _required_env("SUPABASE_SERVICE_ROLE_KEY"),
        )
        evidence = load_live_evidence_with_writer(writer, args.date)
    else:
        evidence = load_live_evidence_with_cli(args.date, linked_root=args.linked_root)
    rows, audit = reconstruct_missing_history_rows(
        history=evidence["history"],
        archive=evidence["archive"],
        locks=evidence["locks"],
        frozen_states=evidence["frozen_states"],
        expected_keys=args.expected_pick,
    )
    if args.execute:
        source_run_id = args.source_run_id or (
            "manual-missing-lock-history-repair-"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        )
        result = execute_repair(
            writer=writer,
            slate_date=args.date,
            expected_keys=args.expected_pick,
            evidence=evidence,
            reconstructed_rows=rows,
            source_run_id=source_run_id,
        )
        print(
            json.dumps(
                {
                    "mode": "execute",
                    "date": args.date,
                    "source_run_id": source_run_id,
                    "audit": audit,
                    **result,
                },
                indent=2,
            )
        )
        return 0

    print(
        json.dumps(
            {
                "mode": "dry_run",
                "date": args.date,
                "reconstructed_rows": len(rows),
                "archive_core_matches": sum(bool(row["archive_core_match"]) for row in audit),
                "calibration_quarantined": sum(bool(row["calibration_quarantined"]) for row in audit),
                "rows": audit,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
