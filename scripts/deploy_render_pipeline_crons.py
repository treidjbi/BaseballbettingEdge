"""Deploy the Render pipeline cron service group explicitly.

This helper keeps Render auto-deploy disabled while making the approved manual
cron deploy path repeatable after pipeline code is merged to main.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from typing import Any


TARGET_SERVICE_NAMES = (
    "bbe-pipeline-preview",
    "bbe-pipeline-grading",
    "bbe-pipeline-full",
    "bbe-pipeline-refresh-day",
    "bbe-pipeline-refresh-evening",
    "bbe-pipeline-refresh-final",
    "bbe-pipeline-lock",
)


def build_deploy_command(render_bin: str, service_id: str, *, wait: bool = True) -> list[str]:
    command = [render_bin, "deploys", "create", service_id]
    if wait:
        command.append("--wait")
    command.extend(["--confirm", "--output", "json"])
    return command


def build_services_command(render_bin: str) -> list[str]:
    return [render_bin, "services", "--output", "json"]


def _coerce_service_item(item: Mapping[str, Any]) -> Mapping[str, Any]:
    service = item.get("service")
    if isinstance(service, Mapping):
        return service
    return item


def _service_items(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, list):
        return [_coerce_service_item(item) for item in payload if isinstance(item, Mapping)]
    if isinstance(payload, Mapping):
        for key in ("services", "data", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return [_coerce_service_item(item) for item in value if isinstance(item, Mapping)]
    raise ValueError("Render services JSON did not contain a service list")


def list_render_services(render_bin: str) -> list[Mapping[str, Any]]:
    completed = subprocess.run(
        build_services_command(render_bin),
        check=True,
        capture_output=True,
        text=True,
    )
    return _service_items(json.loads(completed.stdout))


def resolve_target_services(
    services: Sequence[Mapping[str, Any]],
    target_names: Iterable[str] = TARGET_SERVICE_NAMES,
) -> dict[str, str]:
    by_name: dict[str, Mapping[str, Any]] = {}
    duplicates: set[str] = set()

    for service in services:
        name = service.get("name")
        if not isinstance(name, str):
            continue
        if name in by_name:
            duplicates.add(name)
        by_name[name] = service

    requested_names = tuple(target_names)
    duplicate_targets = [name for name in requested_names if name in duplicates]
    if duplicate_targets:
        raise ValueError(f"Duplicate Render services found by name: {', '.join(duplicate_targets)}")

    missing = [name for name in requested_names if name not in by_name]
    if missing:
        raise ValueError(f"Missing Render pipeline cron services: {', '.join(missing)}")

    resolved: dict[str, str] = {}
    missing_ids: list[str] = []
    for name in requested_names:
        service_id = by_name[name].get("id")
        if isinstance(service_id, str) and service_id:
            resolved[name] = service_id
        else:
            missing_ids.append(name)

    if missing_ids:
        raise ValueError(f"Render services missing ids: {', '.join(missing_ids)}")

    return resolved


def _requested_service_names(raw_values: Sequence[str] | None) -> tuple[str, ...]:
    if not raw_values:
        return TARGET_SERVICE_NAMES

    requested: list[str] = []
    for value in raw_values:
        requested.extend(part.strip() for part in value.split(",") if part.strip())

    unknown = [name for name in requested if name not in TARGET_SERVICE_NAMES]
    if unknown:
        raise ValueError(f"Unknown pipeline cron service names: {', '.join(unknown)}")

    return tuple(dict.fromkeys(requested))


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Create Render deploys. Without this flag, the command only prints the plan.",
    )
    parser.add_argument(
        "--service",
        action="append",
        help="Limit to one service name. Repeat or comma-separate for multiple services.",
    )
    parser.add_argument(
        "--render-bin",
        default="render",
        help="Render CLI executable to call.",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Create deploys without waiting for completion.",
    )
    return parser.parse_args(argv)


def _print_plan(service_ids: Mapping[str, str], *, render_bin: str, wait: bool, execute: bool) -> None:
    mode = "EXECUTE" if execute else "DRY RUN"
    print(f"{mode}: Render pipeline cron deploy plan")
    for name, service_id in service_ids.items():
        command = " ".join(build_deploy_command(render_bin, service_id, wait=wait))
        print(f"- {name}: {service_id}")
        print(f"  {command}")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        requested_names = _requested_service_names(args.service)
        services = list_render_services(args.render_bin)
        service_ids = resolve_target_services(services, requested_names)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}")
        return 1

    wait = not args.no_wait
    _print_plan(service_ids, render_bin=args.render_bin, wait=wait, execute=args.execute)

    if not args.execute:
        print("No Render deploys created. Re-run with --execute after an approved main push.")
        return 0

    for name, service_id in service_ids.items():
        command = build_deploy_command(args.render_bin, service_id, wait=wait)
        print(f"Deploying {name}...")
        subprocess.run(command, check=True, capture_output=True, text=True)

    print("Render pipeline cron deploys completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
