from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, TextIO


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GATE_C_MANIFEST = ROOT / "data/research/gate_c/pitcher_k_outcome_dataset_manifest.json"
DEFAULT_OUTPUT_DIR = ROOT / "analytics/output/retention"
ALLOWED_PROVIDERS = {"boltodds", "propline", "the_odds", "therundown"}
MISMATCH_FIELDS = (
    "missing_compact_group_count", "unexpected_compact_group_count",
    "duplicate_compact_group_count", "first_seen_mismatch_count",
    "last_seen_mismatch_count", "first_odds_mismatch_count",
    "last_odds_mismatch_count", "min_odds_mismatch_count",
    "max_odds_mismatch_count", "odds_move_count_mismatch_count",
    "snapshot_count_mismatch_count",
)
REQUIRED_DECISION_EVIDENCE = (
    "results", "bet_timing", "checkpoint_market", "close_clv", "provider_metadata",
)
BOLTODDS_SUSPENDED_AT = datetime.fromisoformat("2026-06-17T17:22:29+00:00")
SECRET_KEY = re.compile(
    r"(?:authorization|password|secret|token|api[_-]?key|service[_-]?role)", re.IGNORECASE
)

_COVERAGE_INTEGER_FIELDS = (
    "raw_snapshot_rows", "raw_logical_bytes", "raw_group_count",
    "compact_group_count", "exact_group_count", "mismatched_group_count",
    *MISMATCH_FIELDS,
)
_ANOMALY_INTEGER_FIELDS = (
    "rows_missing_run_id", "rows_missing_run_row", "rows_missing_group_key",
    "provider_run_mismatch_rows",
)
_RUNTIME_INTEGER_FIELDS = (
    "run_count", "completed_run_count", "failed_run_count", "request_count",
    "snapshot_count", "snapshot_logical_bytes", "heartbeat_count",
)
_RUNTIME_TIMESTAMP_FIELDS = (
    "first_run_at", "last_run_at", "first_snapshot_at", "last_snapshot_at",
    "last_heartbeat_at", "last_message_at",
)
_SEASON_EVIDENCE_COUNT_FIELDS = (
    "official_tracked_picks", "accepted_bets", "sent_notifications",
    "consumed_locks", "frozen_alt_v2_rows", "operator_incidents",
    "model_review_pins",
)


def load_query_envelope(
    path_or_dash: str, *, stdin: TextIO | None = None,
) -> dict[str, Any]:
    raw = (stdin or sys.stdin).read() if path_or_dash == "-" else Path(path_or_dash).read_text(encoding="utf-8")
    wrapper = json.loads(raw)
    if not isinstance(wrapper, list) or len(wrapper) != 1 or not isinstance(wrapper[0], dict):
        raise ValueError("Supabase query output must contain exactly one row")
    value = wrapper[0].get("retention_exact_coverage")
    if isinstance(value, str):
        value = json.loads(value)
    if not isinstance(value, dict):
        raise ValueError("retention_exact_coverage must be a JSON object")
    return value


def load_json_object(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    return value


def _require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _require_bool(value: Any, label: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{label} must be a boolean")
    return value


def _require_nonnegative_int(value: Any, label: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{label} must be a non-negative integer")
    return value


def _parse_date(value: Any, label: str) -> date:
    try:
        return date.fromisoformat(_require_string(value, label))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO date") from exc


def _parse_timestamp(value: Any, label: str, *, nullable: bool = False) -> datetime | None:
    if value is None and nullable:
        return None
    try:
        parsed = datetime.fromisoformat(_require_string(value, label).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed


def _require_provider(value: Any, label: str) -> str:
    provider = _require_string(value, label)
    if provider not in ALLOWED_PROVIDERS:
        raise ValueError(f"{label} is not an allowed provider")
    return provider


def validate_envelope(envelope: dict[str, Any]) -> None:
    """Validate the versioned SQL envelope before any retention decision."""
    envelope = _require_mapping(envelope, "envelope")
    if type(envelope.get("audit_version")) is not int or envelope["audit_version"] != 1:
        raise ValueError("audit_version must be 1")
    _parse_timestamp(envelope.get("audit_generated_at"), "audit_generated_at")
    if envelope.get("complete") is not True:
        raise ValueError("complete must be true")
    if envelope.get("retention_execution_closed") is not True:
        raise ValueError("retention_execution_closed must be true")
    if envelope.get("deletion_approved") is not False:
        raise ValueError("deletion_approved must be false")

    scope = _require_mapping(envelope.get("query_scope"), "query_scope")
    start_date = _parse_date(scope.get("start_date"), "query_scope.start_date")
    end_date = _parse_date(scope.get("end_date"), "query_scope.end_date")
    if start_date > end_date:
        raise ValueError("query_scope dates are reversed")
    providers = scope.get("providers")
    if not isinstance(providers, list) or not providers:
        raise ValueError("query_scope.providers must be a non-empty list")
    scope_providers = [_require_provider(provider, "query_scope.providers") for provider in providers]
    if len(set(scope_providers)) != len(scope_providers):
        raise ValueError("query_scope.providers must be unique")

    for key in ("coverage", "source_anomalies", "provider_runtime"):
        if not isinstance(envelope.get(key), list):
            raise ValueError(f"{key} must be a list")

    anomalies_by_provider: dict[str, dict[str, Any]] = {}
    for index, raw_row in enumerate(envelope["source_anomalies"]):
        row = _require_mapping(raw_row, f"source_anomalies[{index}]")
        provider = _require_provider(row.get("provider"), f"source_anomalies[{index}].provider")
        if provider in anomalies_by_provider:
            raise ValueError("source_anomalies providers must be unique")
        for field in _ANOMALY_INTEGER_FIELDS:
            _require_nonnegative_int(row.get(field), f"source_anomalies[{index}].{field}")
        anomalies_by_provider[provider] = row
    if set(anomalies_by_provider) != set(scope_providers):
        raise ValueError("source_anomalies must contain every query scope provider exactly once")

    runtime_by_provider: dict[str, dict[str, Any]] = {}
    for index, raw_row in enumerate(envelope["provider_runtime"]):
        row = _require_mapping(raw_row, f"provider_runtime[{index}]")
        provider = _require_provider(row.get("provider"), f"provider_runtime[{index}].provider")
        if provider in runtime_by_provider:
            raise ValueError("provider_runtime providers must be unique")
        for field in _RUNTIME_INTEGER_FIELDS:
            _require_nonnegative_int(row.get(field), f"provider_runtime[{index}].{field}")
        books_seen = row.get("books_seen")
        if not isinstance(books_seen, list) or not all(isinstance(book, str) for book in books_seen):
            raise ValueError(f"provider_runtime[{index}].books_seen must be a string list")
        for field in _RUNTIME_TIMESTAMP_FIELDS:
            _parse_timestamp(row.get(field), f"provider_runtime[{index}].{field}", nullable=True)
        runtime_by_provider[provider] = row
    if set(runtime_by_provider) != set(scope_providers):
        raise ValueError("provider_runtime must contain every query scope provider exactly once")

    seen_partitions: set[tuple[str, str]] = set()
    for index, raw_row in enumerate(envelope["coverage"]):
        row = _require_mapping(raw_row, f"coverage[{index}]")
        slate_date = _parse_date(row.get("slate_date"), f"coverage[{index}].slate_date")
        provider = _require_provider(row.get("provider"), f"coverage[{index}].provider")
        if provider not in scope_providers:
            raise ValueError("coverage provider is outside query scope")
        if not start_date <= slate_date <= end_date:
            raise ValueError("coverage slate_date is outside query scope")
        partition = (slate_date.isoformat(), provider)
        if partition in seen_partitions:
            raise ValueError("coverage provider/date partitions must be unique")
        seen_partitions.add(partition)
        for field in _COVERAGE_INTEGER_FIELDS:
            _require_nonnegative_int(row.get(field), f"coverage[{index}].{field}")
        _parse_timestamp(row.get("first_raw_seen_at"), f"coverage[{index}].first_raw_seen_at")
        _parse_timestamp(row.get("last_raw_seen_at"), f"coverage[{index}].last_raw_seen_at")
        _require_bool(row.get("coverage_exact"), f"coverage[{index}].coverage_exact")


def _index_season_evidence(season_evidence: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if season_evidence is None:
        return {}
    manifest = _require_mapping(season_evidence, "season_evidence")
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ValueError("season_evidence.schema_version must be 1")
    _parse_timestamp(manifest.get("generated_at"), "season_evidence.generated_at")
    dates = manifest.get("dates")
    if not isinstance(dates, list):
        raise ValueError("season_evidence.dates must be a list")
    indexed: dict[str, dict[str, Any]] = {}
    for index, value in enumerate(dates):
        row = _require_mapping(value, f"season_evidence.dates[{index}]")
        slate_date = _parse_date(row.get("slate_date"), f"season_evidence.dates[{index}].slate_date").isoformat()
        if slate_date in indexed:
            raise ValueError("season_evidence dates must be unique")
        decision_linked = _require_bool(row.get("decision_linked"), f"season_evidence.dates[{index}].decision_linked")
        evidence_counts = _require_mapping(row.get("evidence_counts"), f"season_evidence.dates[{index}].evidence_counts")
        for field in _SEASON_EVIDENCE_COUNT_FIELDS:
            _require_nonnegative_int(evidence_counts.get(field), f"season_evidence.dates[{index}].evidence_counts.{field}")
        required_evidence = row.get("required_evidence")
        if decision_linked:
            required_evidence = _require_mapping(required_evidence, f"season_evidence.dates[{index}].required_evidence")
        if required_evidence is not None:
            required_evidence = _require_mapping(required_evidence, f"season_evidence.dates[{index}].required_evidence")
            for field in REQUIRED_DECISION_EVIDENCE:
                _require_bool(required_evidence.get(field), f"season_evidence.dates[{index}].required_evidence.{field}")
        indexed[slate_date] = row
    return indexed


def _validate_gate_c_manifest(gate_c: dict[str, Any] | None) -> dict[str, Any] | None:
    if gate_c is None:
        return None
    manifest = _require_mapping(gate_c, "gate_c")
    _require_string(manifest.get("artifact"), "gate_c.artifact")
    _parse_timestamp(manifest.get("generated_at"), "gate_c.generated_at")
    for field in ("jsonl_sha256", "summary_sha256"):
        digest = _require_string(manifest.get(field), f"gate_c.{field}")
        if re.fullmatch(r"[0-9A-Fa-f]{64}", digest) is None:
            raise ValueError(f"gate_c.{field} must be a SHA-256 digest")
    loaded_dates = manifest.get("loaded_slate_dates")
    if not isinstance(loaded_dates, list):
        raise ValueError("gate_c.loaded_slate_dates must be a list")
    normalized_dates = [_parse_date(value, "gate_c.loaded_slate_dates").isoformat() for value in loaded_dates]
    if len(set(normalized_dates)) != len(normalized_dates):
        raise ValueError("gate_c.loaded_slate_dates must be unique")
    reconciliation = _require_mapping(manifest.get("reconciliation"), "gate_c.reconciliation")
    for field in ("graded_pick_rows", "matched_pick_rows", "unmatched_pick_rows"):
        _require_nonnegative_int(reconciliation.get(field), f"gate_c.reconciliation.{field}")
    summary_counts = _require_mapping(manifest.get("summary_counts"), "gate_c.summary_counts")
    for field in ("rows_missing_result", "tracked_pick_rows"):
        _require_nonnegative_int(summary_counts.get(field), f"gate_c.summary_counts.{field}")
    snapshots = _require_mapping(summary_counts.get("context_snapshot_counts"), "gate_c.summary_counts.context_snapshot_counts")
    _require_nonnegative_int(snapshots.get("official_close"), "gate_c.summary_counts.context_snapshot_counts.official_close")
    return manifest


def _index_pins(pins: dict[str, Any] | None) -> dict[tuple[str, str], dict[str, Any]]:
    if pins is None:
        return {}
    manifest = _require_mapping(pins, "pins")
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ValueError("pins.schema_version must be 1")
    _parse_timestamp(manifest.get("generated_at"), "pins.generated_at")
    partitions = manifest.get("partitions")
    if not isinstance(partitions, list):
        raise ValueError("pins.partitions must be a list")
    indexed: dict[tuple[str, str], dict[str, Any]] = {}
    for index, value in enumerate(partitions):
        row = _require_mapping(value, f"pins.partitions[{index}]")
        slate_date = _parse_date(row.get("slate_date"), f"pins.partitions[{index}].slate_date").isoformat()
        provider = _require_provider(row.get("provider"), f"pins.partitions[{index}].provider")
        key = (slate_date, provider)
        if key in indexed:
            raise ValueError("pin manifest partitions must be unique")
        _require_bool(row.get("reconciled"), f"pins.partitions[{index}].reconciled")
        pin_rows = row.get("pins")
        if not isinstance(pin_rows, list):
            raise ValueError(f"pins.partitions[{index}].pins must be a list")
        for pin_index, pin in enumerate(pin_rows):
            pin = _require_mapping(pin, f"pins.partitions[{index}].pins[{pin_index}]")
            _require_string(pin.get("reason"), f"pins.partitions[{index}].pins[{pin_index}].reason")
            _require_string(pin.get("status"), f"pins.partitions[{index}].pins[{pin_index}].status")
            _require_string(pin.get("preserved_artifact"), f"pins.partitions[{index}].pins[{pin_index}].preserved_artifact")
        indexed[key] = row
    return indexed


def _has_preserved_pins(pin_record: dict[str, Any] | None) -> tuple[bool, list[str]]:
    if pin_record is None:
        return False, ["missing_pin_manifest_partition"]
    reasons: list[str] = []
    if pin_record["reconciled"] is not True:
        reasons.append("pin_reconciliation_incomplete")
    for pin in pin_record["pins"]:
        if not isinstance(pin, dict):
            reasons.append("unpreserved_pin_evidence")
            continue
        artifact = pin.get("preserved_artifact")
        is_relative = isinstance(artifact, str) and bool(artifact.strip()) and _is_repo_relative(artifact)
        if pin.get("status") != "preserved" or not is_relative:
            reasons.append("unpreserved_pin_evidence")
    return not reasons, reasons


def _is_repo_relative(path_value: str) -> bool:
    normalized = path_value.strip().replace("\\", "/")
    return not (
        normalized.startswith("/")
        or re.match(r"^[A-Za-z]:", normalized) is not None
        or any(segment in {".", ".."} for segment in normalized.split("/"))
    )


def _outcome_reason_codes(
    slate_date: str,
    gate_c: dict[str, Any] | None,
    season_record: dict[str, Any] | None,
) -> list[str]:
    if gate_c is None:
        return ["missing_gate_c_manifest"]
    if season_record is None:
        return ["missing_season_evidence_date"]
    if season_record["decision_linked"] is False:
        return []

    reasons: list[str] = []
    evidence_counts = season_record.get("evidence_counts")
    if not isinstance(evidence_counts, dict):
        return ["missing_required_outcome_evidence"]
    tracked_picks = evidence_counts.get("official_tracked_picks")
    if type(tracked_picks) is not int or tracked_picks < 0:
        return ["missing_required_outcome_evidence"]
    if tracked_picks <= 0:
        return []

    loaded_dates = gate_c.get("loaded_slate_dates")
    if not isinstance(loaded_dates, list) or slate_date not in loaded_dates:
        reasons.append("gate_c_date_not_loaded")
    reconciliation = gate_c.get("reconciliation")
    if not isinstance(reconciliation, dict) or reconciliation.get("unmatched_pick_rows") != 0:
        reasons.append("gate_c_unmatched_picks")
    summary_counts = gate_c.get("summary_counts")
    if not isinstance(summary_counts, dict) or summary_counts.get("rows_missing_result") != 0:
        reasons.append("gate_c_missing_results")
    required = season_record.get("required_evidence")
    if not isinstance(required, dict):
        reasons.append("missing_required_outcome_evidence")
    else:
        for field in REQUIRED_DECISION_EVIDENCE:
            if required.get(field) is not True:
                reasons.append(f"required_evidence_{field}_incomplete")
    return reasons


def _coverage_reason_codes(row: dict[str, Any], anomalies: dict[str, Any]) -> list[str]:
    reasons = [field for field in MISMATCH_FIELDS if row[field] > 0]
    if row["mismatched_group_count"] > 0:
        reasons.append("mismatched_group_count")
    if row["coverage_exact"] is not True:
        reasons.append("coverage_not_exact")
    reasons.extend(field for field in _ANOMALY_INTEGER_FIELDS if anomalies[field] > 0)
    return reasons


def build_readiness_report(
    *,
    envelope: dict[str, Any],
    gate_c: dict[str, Any] | None,
    season_evidence: dict[str, Any] | None,
    pins: dict[str, Any] | None,
    as_of: str,
    raw_retention_days: int,
) -> dict[str, Any]:
    """Return evidence-only retention decisions; this function has no execution authority."""
    validate_envelope(envelope)
    gate_c = _validate_gate_c_manifest(gate_c)
    as_of_date = _parse_date(as_of, "as_of")
    if type(raw_retention_days) is not int or raw_retention_days <= 0:
        raise ValueError("raw_retention_days must be a positive integer")
    if envelope["query_scope"]["end_date"] != as_of_date.isoformat():
        raise ValueError("query scope is stale for requested as-of date")

    season_by_date = _index_season_evidence(season_evidence)
    pins_by_partition = _index_pins(pins)
    anomalies_by_provider = {row["provider"]: row for row in envelope["source_anomalies"]}
    partitions: list[dict[str, Any]] = []

    for coverage in envelope["coverage"]:
        slate_date = _parse_date(coverage["slate_date"], "coverage.slate_date")
        provider = coverage["provider"]
        age_days = (as_of_date - slate_date).days
        coverage_reasons = _coverage_reason_codes(coverage, anomalies_by_provider[provider])
        outcome_reasons = _outcome_reason_codes(coverage["slate_date"], gate_c, season_by_date.get(coverage["slate_date"]))
        _, pin_reasons = _has_preserved_pins(pins_by_partition.get((coverage["slate_date"], provider)))
        all_reasons = coverage_reasons + outcome_reasons + pin_reasons
        record = {
            "slate_date": coverage["slate_date"],
            "provider": provider,
            "age_days": age_days,
            "raw_snapshot_rows": coverage["raw_snapshot_rows"],
            "raw_logical_bytes": coverage["raw_logical_bytes"],
            "raw_group_count": coverage["raw_group_count"],
            "exact_group_count": coverage["exact_group_count"],
            "missing_compact_group_count": coverage["missing_compact_group_count"],
            "mismatched_group_count": coverage["mismatched_group_count"],
        }
        if age_days < raw_retention_days:
            record["decision"] = "not_in_policy_window"
            record["deferred_reason_codes"] = all_reasons
        elif coverage_reasons:
            record["decision"] = "blocked_compaction"
            record["reason_codes"] = all_reasons
        elif outcome_reasons:
            record["decision"] = "blocked_outcome_evidence"
            record["reason_codes"] = all_reasons
        elif pin_reasons:
            record["decision"] = "blocked_pinned_evidence"
            record["reason_codes"] = all_reasons
        else:
            record["decision"] = "ready_for_retention_review"
            record["reason_codes"] = []
        partitions.append(record)

    partitions.sort(key=lambda row: (row["slate_date"], row["provider"]))
    decision_counts: dict[str, int] = {}
    for partition in partitions:
        decision = partition["decision"]
        decision_counts[decision] = decision_counts.get(decision, 0) + 1

    gate_c_summary = gate_c if isinstance(gate_c, dict) else {}
    return {
        "report_type": "season_retention_readiness",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of": as_of_date.isoformat(),
        "raw_retention_days": raw_retention_days,
        "source_date_range": {
            "start_date": envelope["query_scope"]["start_date"],
            "end_date": envelope["query_scope"]["end_date"],
        },
        "gate_c": {
            "jsonl_sha256": gate_c_summary.get("jsonl_sha256"),
            "summary_sha256": gate_c_summary.get("summary_sha256"),
            "loaded_slate_dates": gate_c_summary.get("loaded_slate_dates", []),
        },
        "retention_execution_closed": True,
        "deletion_approved": False,
        "production_authority": "none",
        "summary": {"decision_counts": decision_counts},
        "partitions": partitions,
        "provider_summaries": _provider_summaries(partitions, raw_retention_days),
    }


def _provider_summaries(
    partitions: list[dict[str, Any]], raw_retention_days: int,
) -> list[dict[str, Any]]:
    summaries: dict[str, dict[str, Any]] = {}
    for partition in partitions:
        if partition["age_days"] < raw_retention_days:
            continue
        summary = summaries.setdefault(partition["provider"], {
            "provider": partition["provider"], "partition_count": 0,
            "raw_snapshot_rows": 0, "raw_logical_bytes": 0, "raw_group_count": 0,
            "exact_group_count": 0, "missing_compact_group_count": 0,
            "mismatched_group_count": 0, "decision_counts": {},
        })
        summary["partition_count"] += 1
        for field in (
            "raw_snapshot_rows", "raw_logical_bytes", "raw_group_count",
            "exact_group_count", "missing_compact_group_count", "mismatched_group_count",
        ):
            summary[field] += partition[field]
        decision = partition["decision"]
        summary["decision_counts"][decision] = summary["decision_counts"].get(decision, 0) + 1
    return [summaries[provider] for provider in sorted(summaries)]


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: redact_sensitive(child)
            for key, child in value.items()
            if not SECRET_KEY.search(str(key))
        }
    if isinstance(value, list):
        return [redact_sensitive(child) for child in value]
    return value


def render_readiness_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]["decision_counts"]
    source_range = report["source_date_range"]
    gate_c = report["gate_c"]
    loaded_dates = gate_c["loaded_slate_dates"]
    gate_c_dates = (
        f"{min(loaded_dates)} through {max(loaded_dates)}"
        if loaded_dates else "none"
    )
    lines = [
        "# Season Retention Readiness",
        "",
        "**Deletion status: CLOSED**",
        "",
        f"- Generated: `{report['generated_at']}`",
        f"- As of: `{report['as_of']}`",
        f"- Source date range: `{source_range['start_date']} through {source_range['end_date']}`",
        f"- Gate C loaded dates: `{gate_c_dates}`",
        f"- Gate C JSONL SHA-256: `{gate_c['jsonl_sha256']}`",
        f"- Gate C summary SHA-256: `{gate_c['summary_sha256']}`",
        f"- Raw retention candidate window: `{report['raw_retention_days']} days`",
        f"- Decision counts: `{json.dumps(summary, sort_keys=True)}`",
        "",
        "| Slate | Provider | Raw rows | Raw MB | Exact / Raw groups | Missing | Mismatched | Decision | Reasons |",
        "|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for row in report["partitions"]:
        lines.append(
            "| {slate_date} | {provider} | {raw_snapshot_rows} | {raw_mb:.2f} | "
            "{exact_group_count} / {raw_group_count} | {missing_compact_group_count} | "
            "{mismatched_group_count} | {decision} | {reasons} |".format(
                **row,
                raw_mb=row["raw_logical_bytes"] / 1024 / 1024,
                reasons=", ".join(row.get("reason_codes", ())) or "none",
            )
        )
    lines.extend([
        "",
        "`ready_for_retention_review` is evidence status only and does not authorize deletion.",
    ])
    return "\n".join(lines)


def write_report_pair(
    *, report: dict[str, Any], output_dir: Path, stem: str,
    renderer: Callable[[dict[str, Any]], str] = render_readiness_markdown,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    clean = redact_sensitive(report)
    json_path = output_dir / f"{stem}.json"
    markdown_path = output_dir / f"{stem}.md"
    json_path.write_text(
        json.dumps(clean, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    markdown_path.write_text(renderer(clean).rstrip() + "\n", encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build closed season-retention evidence reports.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for command in ("readiness", "boltodds-closure"):
        subparser = subcommands.add_parser(command)
        subparser.add_argument("--query-json", required=True)
        subparser.add_argument("--gate-c-manifest", required=True)
        subparser.add_argument("--season-evidence")
        subparser.add_argument("--pins")
        subparser.add_argument("--as-of", required=True)
        subparser.add_argument("--output-dir", required=True)
        if command == "readiness":
            subparser.add_argument("--raw-retention-days", type=int, default=30)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        envelope = load_query_envelope(args.query_json)
        gate_c = load_json_object(Path(args.gate_c_manifest))
        season_evidence = load_json_object(Path(args.season_evidence)) if args.season_evidence else None
        pins = load_json_object(Path(args.pins)) if args.pins else None
        if args.command != "readiness":
            raise ValueError("boltodds-closure is not available until its closure report is implemented")
        report = build_readiness_report(
            envelope=envelope, gate_c=gate_c, season_evidence=season_evidence, pins=pins,
            as_of=args.as_of, raw_retention_days=args.raw_retention_days,
        )
        paths = write_report_pair(
            report=report, output_dir=Path(args.output_dir), stem="season_retention_readiness",
        )
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        print(f"retention_audit_error: {exc}", file=sys.stderr)
        return 3

    print(f"json={paths['json']}")
    print(f"markdown={paths['markdown']}")
    print(f"decision_counts={json.dumps(report['summary']['decision_counts'], sort_keys=True)}")
    if any(row["decision"].startswith("blocked_") for row in report["partitions"]):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
