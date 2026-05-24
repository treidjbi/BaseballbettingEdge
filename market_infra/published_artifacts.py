from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


ARTIFACT_PATHS = [
    Path("dashboard/data/processed/today.json"),
    Path("dashboard/data/processed/index.json"),
    Path("dashboard/data/processed/steam.json"),
    Path("dashboard/data/performance.json"),
    Path("data/params.json"),
    Path("data/preview_lines.json"),
    Path("data/picks_history.json"),
]


def artifact_type_from_path(path: Path) -> str:
    text = path.as_posix()
    name = path.name
    if text.endswith("dashboard/data/processed/today.json"):
        return "today"
    if text.endswith("dashboard/data/processed/index.json"):
        return "index"
    if text.endswith("dashboard/data/processed/steam.json"):
        return "steam"
    if text.endswith("dashboard/data/performance.json"):
        return "performance"
    if text.endswith("data/params.json"):
        return "params"
    if text.endswith("data/preview_lines.json"):
        return "preview_lines"
    if text.endswith("data/picks_history.json"):
        return "picks_history"
    if text.startswith("dashboard/data/processed/") and name.endswith(".json"):
        return "dated_slate"
    raise ValueError(f"Unsupported artifact path: {path}")


def artifact_key(artifact_type: str, slate_date: str | None) -> str:
    if artifact_type == "dated_slate":
        if not slate_date:
            raise ValueError("dated_slate artifacts require slate_date")
        return f"dated_slate:{slate_date}"
    return artifact_type


def canonical_payload_sha256(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _slate_date_from_path_or_payload(path: Path, payload: dict[str, Any]) -> str | None:
    if artifact_type_from_path(path) == "dated_slate":
        return path.stem
    value = payload.get("date")
    return str(value) if value else None


def _generated_at(payload: dict[str, Any]) -> str | None:
    value = payload.get("generated_at") or payload.get("fetched_at") or payload.get("updated_at")
    return str(value) if value else None


def build_artifact_row(
    *,
    root: Path,
    path: Path,
    source: str,
    source_run_id: str | None = None,
    source_commit_sha: str | None = None,
) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    relative_path = path.relative_to(root) if path.is_absolute() else path
    artifact_type = artifact_type_from_path(relative_path)
    slate_date = _slate_date_from_path_or_payload(relative_path, payload)
    return {
        "artifact_key": artifact_key(artifact_type, slate_date),
        "artifact_type": artifact_type,
        "slate_date": slate_date,
        "payload": payload,
        "payload_sha256": canonical_payload_sha256(payload),
        "generated_at": _generated_at(payload),
        "source": source,
        "source_run_id": source_run_id,
        "source_commit_sha": source_commit_sha,
        "metadata": {"artifact_path": relative_path.as_posix()},
    }
