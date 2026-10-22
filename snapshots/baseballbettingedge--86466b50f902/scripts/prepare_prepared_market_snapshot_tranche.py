"""Build fixed, SELECT-only approval packets for prepared snapshot cleanup.

This module cannot execute a database mutation. It freezes the remaining
provider/date queue, runs exact single-partition previews, and packages at most
five existing executor commands for later human approval and manual execution.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import retire_prepared_market_snapshots as executor  # noqa: E402


QUEUE_VERSION = 2
TRANCHE_VERSION = 2
TRANCHE_SCOPE_ID = "prepared_active_provider_descending_tranches_v2"
MAX_PARTITIONS_PER_TRANCHE = 5
MAX_TRANCHE_RAW_SNAPSHOT_ROWS = 250000
MAX_TRANCHE_RAW_LOGICAL_BYTES = 150 * 1024 * 1024
QUEUE_ORDER = "slate_date_descending_then_propline_before_therundown"
ORDERING_PROOF_PATH = (
    "data/research/retention/"
    "prepared-snapshot-descending-order-proof-2026-09-04.json"
)
ORDERING_PROOF_SHA256 = (
    "0432ab48bec69875f5e67a6a645899cef378340d93bcc425c9ce6448c0e14584"
)
ORDERING_PROOF_SCOPE_ID = "prepared_active_provider_descending_order_proof_v1"
ORDERING_PROOF_QUERY_PATH = "scripts/supabase_prepared_snapshot_ordering_proof.sql"
ORDERING_PROOF_QUERY_SHA256 = (
    "af23d219250180df26ddef31bdbc5135bfda71ca5e6e85197b012db3333587c3"
)
CONFIRMED_COMPLETIONS = (
    {
        "provider": "propline",
        "slate_date": "2026-06-12",
        "deleted_rows": 11888,
        "raw_logical_bytes": 5111272,
        "compact_group_count": 218,
        "result_path": (
            "data/research/retention/"
            "prepared-delete-result-propline-2026-06-12-2026-09-04-cli.json"
        ),
        "result_sha256": (
            "379021fcb78aa4eff3b25aae3fc633bf0963cb1273ecda11cd9084a14fee5dd3"
        ),
    },
    {
        "provider": "therundown",
        "slate_date": "2026-06-12",
        "deleted_rows": 10104,
        "raw_logical_bytes": 5163024,
        "compact_group_count": 456,
        "result_path": (
            "data/research/retention/prepared-tranche-001-2026-09-04/"
            "result-01-therundown-2026-06-12.json"
        ),
        "result_sha256": (
            "74ed85cb904eb9a6a2d74421f3f8dbf4d80aecc6af05468d0011ccba5b8ccde3"
        ),
    },
    {
        "provider": "propline",
        "slate_date": "2026-06-13",
        "deleted_rows": 8866,
        "raw_logical_bytes": 4028458,
        "compact_group_count": 192,
        "result_path": (
            "data/research/retention/prepared-tranche-001-2026-09-04/"
            "result-02-propline-2026-06-13.json"
        ),
        "result_sha256": (
            "205bd4549ff319dc2a41538f303166152549fb5aa7666f54aa89e7c82075878f"
        ),
    },
)
ORIGINAL_PARTITION_COUNT = 82
ORIGINAL_RAW_SNAPSHOT_ROWS = 1816265
ORIGINAL_RAW_LOGICAL_BYTES = 947935885


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_confirmed_completions() -> None:
    keys: list[tuple[str, str]] = []
    for completion in CONFIRMED_COMPLETIONS:
        path = _load_path(str(completion["result_path"]))
        if not path.is_file() or sha256_file(path) != completion["result_sha256"]:
            raise ValueError("confirmed completion result is missing or changed")
        try:
            result = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise ValueError("confirmed completion result is invalid") from exc
        expected = {
            "provider": completion["provider"],
            "slate_date": completion["slate_date"],
            "deleted_rows": completion["deleted_rows"],
            "status": "confirmed",
            "mutation_error": None,
            "postcheck_error": None,
            "automatic_retry_attempted": False,
            "vacuum_attempted": False,
        }
        if any(result.get(field) != value for field, value in expected.items()):
            raise ValueError("confirmed completion result is invalid")
        postcheck = result.get("postcheck")
        if not isinstance(postcheck, dict) or any((
            postcheck.get("provider") != completion["provider"],
            postcheck.get("slate_date") != completion["slate_date"],
            postcheck.get("raw_snapshot_rows") != 0,
            postcheck.get("compact_group_count")
            != completion["compact_group_count"],
            postcheck.get("represented_snapshot_rows")
            != completion["deleted_rows"],
        )):
            raise ValueError("confirmed completion result is invalid")
        keys.append((completion["provider"], completion["slate_date"]))
    if len(keys) != len(set(keys)):
        raise ValueError("confirmed completion results are duplicated")


def load_ordering_proof() -> dict[str, Any]:
    path = _load_path(ORDERING_PROOF_PATH)
    if not path.is_file() or sha256_file(path) != ORDERING_PROOF_SHA256:
        raise ValueError("ordering proof is missing or changed")
    try:
        proof = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError("ordering proof is invalid") from exc
    if not isinstance(proof, dict):
        raise ValueError("ordering proof is invalid")
    return proof


def validate_ordering_proof(proof: dict[str, Any]) -> None:
    if (
        proof.get("proof_version") != 1
        or proof.get("scope_id") != ORDERING_PROOF_SCOPE_ID
        or proof.get("query_path") != ORDERING_PROOF_QUERY_PATH
        or proof.get("query_sha256") != ORDERING_PROOF_QUERY_SHA256
        or proof.get("ordering_safe") is not True
        or proof.get("deletion_approved") is not False
        or proof.get("retention_execution_closed") is not True
    ):
        raise ValueError("ordering proof is invalid")
    query_path = _load_path(ORDERING_PROOF_QUERY_PATH)
    if (
        not query_path.is_file()
        or sha256_file(query_path) != ORDERING_PROOF_QUERY_SHA256
    ):
        raise ValueError("ordering proof is invalid")
    executor.parse_timestamp(str(proof.get("queried_at") or ""), "queried_at")
    providers = proof.get("providers")
    if not isinstance(providers, list) or [
        item.get("provider") for item in providers if isinstance(item, dict)
    ] != ["propline", "therundown"]:
        raise ValueError("ordering proof is invalid")
    count_fields = (
        "remaining_raw_rows",
        "rows_observed_before_run_date",
        "rows_observed_on_run_date",
        "rows_observed_after_run_date",
    )
    for item in providers:
        if any(
            isinstance(item.get(field), bool)
            or not isinstance(item.get(field), int)
            or item[field] < 0
            for field in count_fields
        ):
            raise ValueError("ordering proof is invalid")
        if item["remaining_raw_rows"] != (
            item["rows_observed_before_run_date"]
            + item["rows_observed_on_run_date"]
            + item["rows_observed_after_run_date"]
        ):
            raise ValueError("ordering proof is invalid")
        if (
            item["rows_observed_before_run_date"] != 0
            or item.get("min_day_offset") != 0
            or item.get("max_day_offset") != 1
        ):
            raise ValueError("ordering proof is invalid")
    for field in count_fields:
        if proof.get(field) != sum(item[field] for item in providers):
            raise ValueError("ordering proof is invalid")
    if (
        proof["remaining_raw_rows"]
        != ORIGINAL_RAW_SNAPSHOT_ROWS
        - sum(item["deleted_rows"] for item in CONFIRMED_COMPLETIONS)
        or proof["rows_observed_before_run_date"] != 0
        or proof.get("min_day_offset") != 0
        or proof.get("max_day_offset") != 1
    ):
        raise ValueError("ordering proof is invalid")


def _remaining_partitions() -> list[tuple[str, str]]:
    completed = {
        (item["provider"], item["slate_date"])
        for item in CONFIRMED_COMPLETIONS
    }
    values: list[tuple[str, str]] = []
    for slate_date in sorted(executor.PREPARED_DATES, reverse=True):
        for provider in executor.PREPARED_PROVIDERS:
            key = (provider, slate_date.isoformat())
            if key not in completed:
                values.append(key)
    return values


def _tranche_definitions() -> list[dict[str, Any]]:
    remaining = _remaining_partitions()
    result: list[dict[str, Any]] = []
    for offset in range(0, len(remaining), MAX_PARTITIONS_PER_TRANCHE):
        number = offset // MAX_PARTITIONS_PER_TRANCHE + 1
        result.append(
            {
                "tranche_id": f"tranche-v2-{number:03d}",
                "partitions": [
                    {"provider": provider, "slate_date": slate_date}
                    for provider, slate_date in remaining[
                        offset : offset + MAX_PARTITIONS_PER_TRANCHE
                    ]
                ],
            }
        )
    return result


def _queue_basis() -> dict[str, Any]:
    return {
        "queue_version": QUEUE_VERSION,
        "scope_id": TRANCHE_SCOPE_ID,
        "source_scope_id": executor.SCOPE_ID,
        "queue_order": QUEUE_ORDER,
        "maximum_partitions_per_tranche": MAX_PARTITIONS_PER_TRANCHE,
        "maximum_raw_snapshot_rows_per_tranche": MAX_TRANCHE_RAW_SNAPSHOT_ROWS,
        "maximum_raw_logical_bytes_per_tranche": MAX_TRANCHE_RAW_LOGICAL_BYTES,
        "ordering_proof_path": ORDERING_PROOF_PATH,
        "ordering_proof_sha256": ORDERING_PROOF_SHA256,
        "original_partition_count": ORIGINAL_PARTITION_COUNT,
        "completed_partitions": list(CONFIRMED_COMPLETIONS),
        "remaining_partition_count": len(_remaining_partitions()),
        "remaining_expected_raw_snapshot_rows": (
            ORIGINAL_RAW_SNAPSHOT_ROWS
            - sum(item["deleted_rows"] for item in CONFIRMED_COMPLETIONS)
        ),
        "remaining_expected_raw_logical_bytes": (
            ORIGINAL_RAW_LOGICAL_BYTES
            - sum(item["raw_logical_bytes"] for item in CONFIRMED_COMPLETIONS)
        ),
        "tranches": _tranche_definitions(),
    }


def build_queue_manifest(*, generated_at: datetime | None = None) -> dict[str, Any]:
    _validate_confirmed_completions()
    validate_ordering_proof(load_ordering_proof())
    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    basis = _queue_basis()
    return {
        **basis,
        "generated_at": generated.isoformat(),
        "queue_sha256": executor.canonical_sha256(basis),
        "deletion_approved": False,
        "retention_execution_closed": True,
        "automatic_execution_enabled": False,
        "vacuum_allowed": False,
    }


def expected_tranche(tranche_id: str) -> list[tuple[str, str]]:
    for batch in _tranche_definitions():
        if batch["tranche_id"] == tranche_id:
            return [
                (item["provider"], item["slate_date"])
                for item in batch["partitions"]
            ]
    raise ValueError("unknown tranche")


def _stored_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def _load_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _execution_command(entry: dict[str, Any]) -> str:
    return " ".join(
        [
            f"{executor.DELETE_ALLOW_ENV}=true",
            f"{executor.DELETE_TOKEN_ENV}={entry['preview_approval_token']}",
            "python3",
            "scripts/retire_prepared_market_snapshots.py",
            "execute",
            "--preview-report",
            shlex.quote(entry["preview_report_path"]),
            "--output",
            shlex.quote(entry["result_path"]),
            "--execute",
            "--run-linked-delete",
        ]
    )


def _tranche_approval_basis(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "tranche_version": report.get("tranche_version"),
        "scope_id": report.get("scope_id"),
        "source_scope_id": report.get("source_scope_id"),
        "queue_sha256": report.get("queue_sha256"),
        "tranche_id": report.get("tranche_id"),
        "partitions": report.get("partitions"),
        "partition_count": report.get("partition_count"),
        "total_raw_snapshot_rows": report.get("total_raw_snapshot_rows"),
        "total_raw_logical_bytes": report.get("total_raw_logical_bytes"),
        "total_compact_groups": report.get("total_compact_groups"),
        "backup_completed_at": report.get("backup_completed_at"),
        "generated_at": report.get("generated_at"),
        "approval_expires_at": report.get("approval_expires_at"),
        "proposed_commands": report.get("proposed_commands"),
    }


def prepare_tranche(
    tranche_id: str,
    *,
    backup_completed_at: str,
    output_dir: Path,
    query_runner: executor.QueryRunner = executor._run_cli_query,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    partitions = expected_tranche(tranche_id)
    if output_dir.exists():
        raise ValueError("output directory already exists")

    payloads: list[dict[str, Any]] = []
    for provider, slate_date in partitions:
        payloads.append(
            executor._read_preview_payload(
                provider,
                slate_date,
                query_runner,
            )
        )

    generated = (generated_at or datetime.now(timezone.utc)).astimezone(timezone.utc)
    preview_reports = [
        executor.build_preview_report(
            payload,
            provider=provider,
            slate_date=slate_date,
            backup_completed_at=backup_completed_at,
            generated_at=generated,
        )
        for payload, (provider, slate_date) in zip(payloads, partitions)
    ]
    total_rows = sum(
        report["source_state"]["raw_snapshot_rows"] for report in preview_reports
    )
    total_bytes = sum(
        report["source_state"]["raw_logical_bytes"] for report in preview_reports
    )
    if total_rows > MAX_TRANCHE_RAW_SNAPSHOT_ROWS:
        raise ValueError("tranche exceeds the raw row safety cap")
    if total_bytes > MAX_TRANCHE_RAW_LOGICAL_BYTES:
        raise ValueError("tranche exceeds the logical byte safety cap")

    entries: list[dict[str, Any]] = []
    for ordinal, report in enumerate(preview_reports, start=1):
        provider = report["provider"]
        slate_date = report["slate_date"]
        preview_path = output_dir / (
            f"preview-{ordinal:02d}-{provider}-{slate_date}.json"
        )
        result_path = output_dir / (
            f"result-{ordinal:02d}-{provider}-{slate_date}.json"
        )
        executor._write_new_json(preview_path, report)
        state = report["source_state"]
        entries.append(
            {
                "ordinal": ordinal,
                "provider": provider,
                "slate_date": slate_date,
                "raw_snapshot_rows": state["raw_snapshot_rows"],
                "raw_logical_bytes": state["raw_logical_bytes"],
                "compact_group_count": state["compact_group_count"],
                "preview_report_path": _stored_path(preview_path),
                "preview_report_sha256": sha256_file(preview_path),
                "preview_approval_token": report["approval_token"],
                "delete_sql_sha256": report["delete_sql_sha256"],
                "result_path": _stored_path(result_path),
            }
        )

    queue = build_queue_manifest(generated_at=generated)
    report = {
        "tranche_version": TRANCHE_VERSION,
        "scope_id": TRANCHE_SCOPE_ID,
        "source_scope_id": executor.SCOPE_ID,
        "queue_sha256": queue["queue_sha256"],
        "tranche_id": tranche_id,
        "partitions": entries,
        "partition_count": len(entries),
        "total_raw_snapshot_rows": total_rows,
        "total_raw_logical_bytes": total_bytes,
        "total_compact_groups": sum(
            item["compact_group_count"] for item in entries
        ),
        "backup_completed_at": preview_reports[0]["backup_completed_at"],
        "generated_at": generated.isoformat(),
        "approval_expires_at": preview_reports[0]["approval_expires_at"],
        "proposed_commands": [],
        "deletion_approved": False,
        "retention_execution_closed": True,
        "automatic_execution_enabled": False,
        "vacuum_allowed": False,
    }
    report["proposed_commands"] = [_execution_command(item) for item in entries]
    report["approval_token"] = executor.canonical_sha256(
        _tranche_approval_basis(report)
    )
    executor._write_new_json(output_dir / "tranche-report.json", report)
    return report


def validate_tranche_report(
    report: dict[str, Any], *, now: datetime | None = None,
) -> None:
    if report.get("tranche_version") != TRANCHE_VERSION:
        raise ValueError("tranche version is invalid")
    if report.get("scope_id") != TRANCHE_SCOPE_ID:
        raise ValueError("tranche scope is invalid")
    if report.get("source_scope_id") != executor.SCOPE_ID:
        raise ValueError("source scope is invalid")
    if report.get("deletion_approved") is not False:
        raise ValueError("tranche cannot approve deletion")
    if report.get("retention_execution_closed") is not True:
        raise ValueError("tranche execution gate is invalid")
    if report.get("automatic_execution_enabled") is not False:
        raise ValueError("automatic execution must remain disabled")
    if report.get("vacuum_allowed") is not False:
        raise ValueError("vacuum must remain disabled")
    expected_token = executor.canonical_sha256(_tranche_approval_basis(report))
    if report.get("approval_token") != expected_token:
        raise ValueError("tranche approval token is invalid")

    tranche_id = str(report.get("tranche_id") or "")
    expected = expected_tranche(tranche_id)
    entries = report.get("partitions")
    if not isinstance(entries, list) or not entries:
        raise ValueError("tranche partitions are invalid")
    if len(entries) > MAX_PARTITIONS_PER_TRANCHE:
        raise ValueError("tranche is too large")
    actual = [(item.get("provider"), item.get("slate_date")) for item in entries]
    if actual != expected or len(actual) != len(set(actual)):
        raise ValueError("tranche partitions are invalid")

    queue = build_queue_manifest(generated_at=now)
    if report.get("queue_sha256") != queue["queue_sha256"]:
        raise ValueError("queue hash is invalid")

    preview_reports: list[dict[str, Any]] = []
    for entry in entries:
        preview_path = _load_path(str(entry.get("preview_report_path") or ""))
        if not preview_path.is_file() or sha256_file(preview_path) != entry.get(
            "preview_report_sha256"
        ):
            raise ValueError("preview report hash is invalid")
        loaded = json.loads(preview_path.read_text(encoding="utf-8"))
        executor.validate_preview_report(loaded, now=now)
        if (
            loaded.get("provider") != entry.get("provider")
            or loaded.get("slate_date") != entry.get("slate_date")
            or loaded.get("approval_token") != entry.get("preview_approval_token")
            or loaded.get("delete_sql_sha256") != entry.get("delete_sql_sha256")
        ):
            raise ValueError("preview report binding is invalid")
        state = loaded["source_state"]
        if any(
            entry.get(field) != state.get(field)
            for field in (
                "raw_snapshot_rows",
                "raw_logical_bytes",
                "compact_group_count",
            )
        ):
            raise ValueError("preview source state binding is invalid")
        preview_reports.append(loaded)

    if len({item["backup_completed_at"] for item in preview_reports}) != 1:
        raise ValueError("tranche backup binding is invalid")
    if report.get("backup_completed_at") != preview_reports[0]["backup_completed_at"]:
        raise ValueError("tranche backup binding is invalid")
    if report.get("approval_expires_at") != preview_reports[0]["approval_expires_at"]:
        raise ValueError("tranche expiry binding is invalid")
    if report.get("partition_count") != len(entries):
        raise ValueError("tranche totals are invalid")
    totals = {
        "total_raw_snapshot_rows": sum(item["raw_snapshot_rows"] for item in entries),
        "total_raw_logical_bytes": sum(item["raw_logical_bytes"] for item in entries),
        "total_compact_groups": sum(item["compact_group_count"] for item in entries),
    }
    if any(report.get(field) != value for field, value in totals.items()):
        raise ValueError("tranche totals are invalid")
    expected_commands = [_execution_command(item) for item in entries]
    if report.get("proposed_commands") != expected_commands:
        raise ValueError("tranche commands are invalid")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build SELECT-only prepared snapshot cleanup packets.",
    )
    commands = parser.add_subparsers(dest="command", required=True)

    queue = commands.add_parser("queue", help="Write the fixed remaining queue")
    queue.add_argument("--output", required=True, type=Path)

    preview = commands.add_parser(
        "preview", help="Run exact SELECT-only previews for one fixed tranche"
    )
    preview.add_argument("--tranche-id", required=True)
    preview.add_argument("--backup-completed-at", required=True)
    preview.add_argument("--output-dir", required=True, type=Path)
    preview.add_argument("--run-linked-read", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.command == "queue":
            manifest = build_queue_manifest()
            executor._write_new_json(args.output, manifest)
            print(
                "prepared_market_snapshot_queue "
                f"remaining={manifest['remaining_partition_count']} "
                f"tranches={len(manifest['tranches'])} "
                f"queue_sha256={manifest['queue_sha256']}"
            )
        else:
            if not args.run_linked_read:
                raise ValueError("linked read acknowledgement is required")
            report = prepare_tranche(
                args.tranche_id,
                backup_completed_at=args.backup_completed_at,
                output_dir=args.output_dir,
            )
            validate_tranche_report(report)
            print(
                "prepared_market_snapshot_tranche "
                f"tranche_id={report['tranche_id']} "
                f"partitions={report['partition_count']} "
                f"rows={report['total_raw_snapshot_rows']} "
                f"approval_token={report['approval_token']}"
            )
    except (json.JSONDecodeError, OSError, ValueError):
        print("error: validation_or_execution_failed", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
