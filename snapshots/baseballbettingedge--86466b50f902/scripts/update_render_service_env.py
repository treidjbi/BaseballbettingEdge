"""Dry-run-first, full-list Render environment updater for approved Alt Picks keys."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Callable, TextIO
from urllib.parse import urlencode
from urllib.request import Request, urlopen


API_ROOT = "https://api.render.com/v1"
APPROVED_KEYS = frozenset({
    "ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION",
    "ALTERNATIVE_PICK_SELECTION_MODE",
})
APPROVED_VALUES = {
    "ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION": frozenset({"v1", "v2"}),
    "ALTERNATIVE_PICK_SELECTION_MODE": frozenset({"off", "record"}),
}


def _decode_response(response: Any) -> Any:
    body = response.read()
    return json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)


def _page_items(payload: Any) -> tuple[list[dict[str, str]], str | None]:
    if isinstance(payload, list):
        raw_items = payload
        cursor = None
        for item in raw_items:
            if isinstance(item, dict) and item.get("cursor") not in {None, ""}:
                cursor = str(item["cursor"])
    elif isinstance(payload, dict):
        raw_items = payload.get("envVars") or payload.get("items") or []
        cursor = str(payload["cursor"]) if payload.get("cursor") not in {None, ""} else None
    else:
        raise ValueError("Render environment page is not a list or object")
    items: list[dict[str, str]] = []
    for item in raw_items:
        value = item.get("envVar") if isinstance(item, dict) and isinstance(item.get("envVar"), dict) else item
        if not isinstance(value, dict) or not isinstance(value.get("key"), str) or not isinstance(value.get("value"), str):
            raise ValueError("Render environment page contains an invalid entry")
        items.append({"key": value["key"], "value": value["value"]})
    if len(items) >= 100 and not cursor:
        raise ValueError("Render environment pagination is incomplete")
    return items, cursor


def fetch_complete_environment(
    *, service_id: str, api_key: str, opener: Callable[..., Any] = urlopen,
) -> tuple[dict[str, str], int]:
    environment: dict[str, str] = {}
    cursor: str | None = None
    seen_cursors: set[str] = set()
    pages = 0
    while True:
        query = {"limit": "100"}
        if cursor:
            query["cursor"] = cursor
        request = Request(
            f"{API_ROOT}/services/{service_id}/env-vars?{urlencode(query)}",
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            method="GET",
        )
        with opener(request, timeout=20) as response:
            payload = _decode_response(response)
        pages += 1
        items, next_cursor = _page_items(payload)
        for item in items:
            if item["key"] in environment:
                raise ValueError(f"duplicate Render environment key: {item['key']}")
            environment[item["key"]] = item["value"]
        if not next_cursor:
            return environment, pages
        if next_cursor in seen_cursors:
            raise ValueError("Render environment pagination repeated a cursor")
        seen_cursors.add(next_cursor)
        cursor = next_cursor


def _operation(set_value: str | None, unset_key: str | None) -> tuple[str, str | None]:
    if bool(set_value) == bool(unset_key):
        raise ValueError("provide exactly one --set or --unset operation")
    if set_value:
        if "=" not in set_value:
            raise ValueError("--set must use KEY=VALUE")
        key, value = set_value.split("=", 1)
        if key not in APPROVED_KEYS:
            raise ValueError("environment key is not approved")
        if value not in APPROVED_VALUES[key]:
            raise ValueError("environment value is not approved")
        return key, value
    key = str(unset_key)
    if key not in APPROVED_KEYS:
        raise ValueError("environment key is not approved")
    return key, None


def update_environment(
    *, service_id: str, set_value: str | None, unset_key: str | None,
    execute: bool, api_key: str, opener: Callable[..., Any] = urlopen,
    output: TextIO = sys.stdout,
) -> dict[str, Any]:
    if not service_id.strip() or not api_key:
        raise ValueError("service ID and API key are required")
    key, target = _operation(set_value, unset_key)
    original, pages = fetch_complete_environment(
        service_id=service_id, api_key=api_key, opener=opener,
    )
    original_state = "present" if key in original else "absent"
    expected = dict(original)
    if target is None:
        expected.pop(key, None)
    else:
        expected[key] = target
    print(
        f"key_count={len(original)} page_count={pages} changed_key={key} "
        f"original_state={original_state} mode={'execute' if execute else 'dry_run'}",
        file=output,
    )
    if execute:
        rows = [{"key": item, "value": expected[item]} for item in sorted(expected)]
        request = Request(
            f"{API_ROOT}/services/{service_id}/env-vars",
            data=json.dumps(rows, separators=(",", ":")).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="PUT",
        )
        with opener(request, timeout=20) as response:
            response.read()
        verified, verify_pages = fetch_complete_environment(
            service_id=service_id, api_key=api_key, opener=opener,
        )
        if set(verified) != set(expected):
            raise RuntimeError("Render environment key set drifted after PUT")
        if verified != expected:
            raise RuntimeError("Render environment target verification failed")
        print(
            f"verified_key_count={len(verified)} page_count={verify_pages} "
            f"changed_key={key} verification=passed",
            file=output,
        )
    return {
        "environment": expected,
        "original_state": original_state,
        "key_count": len(original),
        "page_count": pages,
        "executed": execute,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--service-id", required=True)
    operations = parser.add_mutually_exclusive_group(required=True)
    operations.add_argument("--set", dest="set_value")
    operations.add_argument("--unset", dest="unset_key")
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args(argv)
    api_key = os.environ.get("RENDER_API_KEY", "")
    if not api_key:
        print("error=RENDER_API_KEY_required", file=sys.stderr)
        return 2
    try:
        update_environment(
            service_id=args.service_id, set_value=args.set_value,
            unset_key=args.unset_key, execute=args.execute, api_key=api_key,
        )
    except Exception as error:
        print(f"error={type(error).__name__}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
