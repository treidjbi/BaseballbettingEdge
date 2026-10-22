from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, TextIO


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GATE_C_JSONL = ROOT / "data/research/gate_c/pitcher_k_outcome_dataset.jsonl"
DEFAULT_GATE_C_MANIFEST = ROOT / "data/research/gate_c/pitcher_k_outcome_dataset_manifest.json"
DEFAULT_OUTPUT_DIR = ROOT / "data/research/retention"
DEFAULT_QUERY_SQL = ROOT / "scripts/supabase_retention_season_counts.sql"
ALLOWED_PROVIDERS = {"boltodds", "propline", "the_odds", "therundown"}
AGGREGATE_COUNT_PAIRS = (
    ("accepted_bets", "accepted_bets_complete"),
    ("sent_notifications", "sent_notifications_complete"),
    ("consumed_locks", "consumed_locks_complete"),
    ("frozen_alt_v2_rows", "frozen_alt_v2_rows_complete"),
)
PIN_REASONS = {
    "official_tracked_picks": "official_tracked_pick",
    "accepted_bets": "accepted_bet",
    "sent_notifications": "sent_notification",
    "consumed_locks": "consumed_lock",
    "frozen_alt_v2_rows": "frozen_alt_v2",
    "operator_incidents": "operator_incident",
    "model_review_pins": "model_review",
}


def _parse_date(value: Any, field: str) -> date:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be an ISO date")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"{field} must be an ISO date") from error


def _parse_timestamp(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a timezone-aware timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{field} must be a timezone-aware timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must be a timezone-aware timestamp")
    return value


def _nonnegative_int(value: Any, field: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def _is_repo_relative(path_value: str) -> bool:
    normalized = path_value.strip().replace("\\", "/")
    return bool(normalized) and not (
        normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized) is not None
        or any(segment in {"", ".", ".."} for segment in normalized.split("/"))
    )


def parse_manual_pin(value: str) -> tuple[str, str]:
    if "=" not in value:
        raise ValueError("manual pins must use DATE=REPO_PATH")
    slate_date, artifact = value.split("=", 1)
    slate_date = _parse_date(slate_date.strip(), "manual pin date").isoformat()
    artifact = artifact.strip().replace("\\", "/")
    if not _is_repo_relative(artifact):
        raise ValueError("manual pin artifact must be repository-relative")
    return slate_date, artifact


def load_query_counts(
    path_or_dash: str, *, stdin: TextIO | None = None,
) -> dict[str, Any]:
    raw = (stdin or sys.stdin).read() if path_or_dash == "-" else Path(path_or_dash).read_text(encoding="utf-8")
    wrapper = json.loads(raw)
    rows = wrapper.get("rows") if isinstance(wrapper, dict) else wrapper
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError("Supabase query output must contain exactly one row")
    value = rows[0].get("retention_season_counts")
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("retention_season_counts must be a JSON object")
    return value


def _validate_aggregate_counts(value: dict[str, Any]) -> list[dict[str, Any]]:
    if value.get("schema_version") != 1:
        raise ValueError("aggregate schema_version must be 1")
    _parse_timestamp(value.get("generated_at"), "aggregate generated_at")
    scope = value.get("scope")
    if not isinstance(scope, dict):
        raise ValueError("aggregate scope must be an object")
    start = _parse_date(scope.get("start_date"), "aggregate scope.start_date")
    end = _parse_date(scope.get("end_date"), "aggregate scope.end_date")
    if start > end:
        raise ValueError("aggregate scope dates are reversed")
    providers = scope.get("providers")
    if (
        not isinstance(providers, list)
        or not providers
        or any(provider not in ALLOWED_PROVIDERS for provider in providers)
        or len(set(providers)) != len(providers)
    ):
        raise ValueError("aggregate scope.providers are invalid")
    rows = value.get("dates")
    if not isinstance(rows, list):
        raise ValueError("aggregate dates must be a list")
    indexed: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"aggregate dates[{index}] must be an object")
        slate_date = _parse_date(row.get("slate_date"), f"aggregate dates[{index}].slate_date").isoformat()
        if slate_date in indexed:
            raise ValueError("aggregate dates must be unique")
        for count_field, complete_field in AGGREGATE_COUNT_PAIRS:
            count = _nonnegative_int(row.get(count_field), f"aggregate {slate_date}.{count_field}")
            complete = _nonnegative_int(row.get(complete_field), f"aggregate {slate_date}.{complete_field}")
            if complete != count:
                raise ValueError(
                    f"{complete_field} must equal {count_field} for {slate_date}"
                )
        indexed[slate_date] = row
    expected_dates = []
    cursor = start
    while cursor <= end:
        expected_dates.append(cursor.isoformat())
        cursor += timedelta(days=1)
    if sorted(indexed) != expected_dates:
        raise ValueError("aggregate dates must exactly cover the requested scope")
    return [indexed[slate_date] for slate_date in expected_dates]


def _manual_pin_map(values: list[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for value in values:
        slate_date, artifact = parse_manual_pin(value)
        if artifact not in result[slate_date]:
            result[slate_date].append(artifact)
    return {key: sorted(paths) for key, paths in sorted(result.items())}


def build_manifests(
    *,
    aggregate_counts: dict[str, Any],
    gate_c_rows: list[dict[str, Any]],
    gate_c_jsonl_sha256: str,
    query_sql_sha256: str,
    gate_c_artifact: str,
    season_evidence_artifact: str,
    operator_incident_pins: dict[str, list[str]],
    model_review_pins: dict[str, list[str]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    rows = _validate_aggregate_counts(aggregate_counts)
    if re.fullmatch(r"[0-9a-fA-F]{64}", gate_c_jsonl_sha256) is None:
        raise ValueError("gate_c_jsonl_sha256 must be a SHA-256 digest")
    if re.fullmatch(r"[0-9a-fA-F]{64}", query_sql_sha256) is None:
        raise ValueError("query_sql_sha256 must be a SHA-256 digest")
    for field, path_value in (
        ("gate_c_artifact", gate_c_artifact),
        ("season_evidence_artifact", season_evidence_artifact),
    ):
        if not _is_repo_relative(path_value):
            raise ValueError(f"{field} must be repository-relative")

    scoped_dates = {row["slate_date"] for row in rows}
    for label, pin_map in (
        ("operator incident", operator_incident_pins),
        ("model review", model_review_pins),
    ):
        for slate_date, artifacts in pin_map.items():
            _parse_date(slate_date, f"{label} date")
            if slate_date not in scoped_dates:
                raise ValueError(f"{label} date falls outside aggregate scope")
            if not artifacts or any(not _is_repo_relative(path) for path in artifacts):
                raise ValueError(f"{label} artifacts must be repository-relative")

    tracked_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in gate_c_rows:
        slate_date = str(row.get("slate_date") or "").strip()
        if row.get("is_tracked_pick") is True and slate_date in scoped_dates:
            tracked_by_date[slate_date].append(row)

    season_dates: list[dict[str, Any]] = []
    pin_partitions: list[dict[str, Any]] = []
    providers = list(aggregate_counts["scope"]["providers"])
    for aggregate_row in rows:
        slate_date = aggregate_row["slate_date"]
        tracked = tracked_by_date.get(slate_date, [])
        official_count = len(tracked)
        operator_artifacts = operator_incident_pins.get(slate_date, [])
        model_artifacts = model_review_pins.get(slate_date, [])
        evidence_counts = {
            "official_tracked_picks": official_count,
            "accepted_bets": aggregate_row["accepted_bets"],
            "sent_notifications": aggregate_row["sent_notifications"],
            "consumed_locks": aggregate_row["consumed_locks"],
            "frozen_alt_v2_rows": aggregate_row["frozen_alt_v2_rows"],
            "operator_incidents": len(operator_artifacts),
            "model_review_pins": len(model_artifacts),
        }
        decision_linked = any(evidence_counts.values())
        outcome_required = any(
            evidence_counts[field] > 0
            for field in (
                "official_tracked_picks", "accepted_bets",
                "frozen_alt_v2_rows", "model_review_pins",
            )
        )
        tracked_results_complete = bool(tracked) and all(
            row.get("result") in {"win", "loss"} for row in tracked
        )
        tracked_checkpoint_complete = bool(tracked) and all(
            row.get("closing_line") is not None and row.get("american_odds") is not None
            for row in tracked
        )
        tracked_clv_complete = bool(tracked) and all(
            row.get("price_clv_cents") is not None for row in tracked
        )
        tracked_provider_complete = bool(tracked) and all(
            bool(str(row.get("official_odds_source") or "").strip()) for row in tracked
        )
        required_evidence = {
            "results": (not outcome_required) or tracked_results_complete,
            "bet_timing": True,
            "checkpoint_market": (
                not decision_linked
                or tracked_checkpoint_complete
                or evidence_counts["consumed_locks"] > 0
            ),
            "close_clv": (not outcome_required) or tracked_clv_complete,
            "provider_metadata": (not decision_linked) or tracked_provider_complete,
        }
        season_dates.append({
            "slate_date": slate_date,
            "decision_linked": decision_linked,
            "evidence_counts": evidence_counts,
            "required_evidence": required_evidence,
        })

        pin_rows: list[dict[str, str]] = []
        if official_count:
            pin_rows.append({
                "reason": PIN_REASONS["official_tracked_picks"],
                "status": "preserved",
                "preserved_artifact": gate_c_artifact,
            })
        for count_field in (
            "accepted_bets", "sent_notifications", "consumed_locks",
            "frozen_alt_v2_rows",
        ):
            if evidence_counts[count_field] > 0:
                pin_rows.append({
                    "reason": PIN_REASONS[count_field],
                    "status": "preserved",
                    "preserved_artifact": season_evidence_artifact,
                })
        for artifact in operator_artifacts:
            pin_rows.append({
                "reason": PIN_REASONS["operator_incidents"],
                "status": "preserved",
                "preserved_artifact": artifact,
            })
        for artifact in model_artifacts:
            pin_rows.append({
                "reason": PIN_REASONS["model_review_pins"],
                "status": "preserved",
                "preserved_artifact": artifact,
            })
        for provider in providers:
            pin_partitions.append({
                "slate_date": slate_date,
                "provider": provider,
                "reconciled": all(required_evidence.values()),
                "pins": pin_rows,
            })

    source_evidence = {
        "aggregate_generated_at": aggregate_counts["generated_at"],
        "gate_c_jsonl_sha256": gate_c_jsonl_sha256.lower(),
        "query_sql_sha256": query_sql_sha256.lower(),
        "scope": aggregate_counts["scope"],
        "privacy_boundary": "aggregate_counts_and_repository_relative_pins_only",
        "manual_pin_categories": ["operator_incidents", "model_review_pins"],
        "retained_detail_sources": {
            "accepted_bets": "public.accepted_bets",
            "consumed_locks": "public.operational_pick_locks",
            "frozen_alt_v2_rows": "public.alternative_pick_selection_state",
            "sent_notifications": "public.notification_events",
        },
        "raw_deletion_scope": "public.market_snapshots provider=boltodds only",
    }
    season = {
        "schema_version": 1,
        "generated_at": aggregate_counts["generated_at"],
        "dates": season_dates,
        "source_evidence": source_evidence,
        "retention_execution_closed": True,
        "deletion_approved": False,
        "production_authority": "none",
    }
    pins = {
        "schema_version": 1,
        "generated_at": aggregate_counts["generated_at"],
        "partitions": pin_partitions,
        "source_evidence": source_evidence,
        "retention_execution_closed": True,
        "deletion_approved": False,
        "production_authority": "none",
    }
    return season, pins


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(value)
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError as error:
        raise ValueError("output files must stay inside the repository") from error


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build aggregate-only season-evidence and pin manifests."
    )
    parser.add_argument("--query-json", required=True)
    parser.add_argument("--gate-c-jsonl", type=Path, default=DEFAULT_GATE_C_JSONL)
    parser.add_argument("--gate-c-manifest", type=Path, default=DEFAULT_GATE_C_MANIFEST)
    parser.add_argument("--query-sql", type=Path, default=DEFAULT_QUERY_SQL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--operator-incident-pin", action="append", default=[])
    parser.add_argument("--model-review-pin", action="append", default=[])
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        aggregate_counts = load_query_counts(args.query_json)
        scope = aggregate_counts.get("scope") or {}
        start_date = _parse_date(scope.get("start_date"), "aggregate scope.start_date").isoformat()
        end_date = _parse_date(scope.get("end_date"), "aggregate scope.end_date").isoformat()
        output_dir = args.output_dir.resolve()
        season_path = output_dir / f"season-evidence-{start_date}-{end_date}.json"
        pins_path = output_dir / f"pins-{start_date}-{end_date}.json"
        gate_c_manifest = json.loads(args.gate_c_manifest.read_text(encoding="utf-8"))
        gate_c_digest = _sha256(args.gate_c_jsonl)
        if gate_c_manifest.get("jsonl_sha256") != gate_c_digest:
            raise ValueError("Gate C JSONL hash does not match its manifest")
        season, pins = build_manifests(
            aggregate_counts=aggregate_counts,
            gate_c_rows=_load_jsonl(args.gate_c_jsonl),
            gate_c_jsonl_sha256=gate_c_digest,
            query_sql_sha256=_sha256(args.query_sql),
            gate_c_artifact=_repo_relative(args.gate_c_jsonl),
            season_evidence_artifact=_repo_relative(season_path),
            operator_incident_pins=_manual_pin_map(args.operator_incident_pin),
            model_review_pins=_manual_pin_map(args.model_review_pin),
        )
        _write_json(season_path, season)
        _write_json(pins_path, pins)
        print(
            "Retention season manifests written: "
            f"dates={len(season['dates'])} partitions={len(pins['partitions'])} "
            f"output_dir={output_dir}"
        )
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
