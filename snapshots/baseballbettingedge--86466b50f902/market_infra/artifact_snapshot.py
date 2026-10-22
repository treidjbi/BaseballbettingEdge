from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

DATED_SLATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.json$")


def artifact_kind(path: str | Path) -> str:
    name = Path(path).name
    if name == "today.json":
        return "today"
    if name == "steam.json":
        return "steam"
    if name == "picks_history.json":
        return "picks_history"
    if name == "preview_lines.json":
        return "preview_lines"
    if name == "params.json":
        return "params"
    if name == "performance.json":
        return "performance"
    if DATED_SLATE_RE.match(name):
        return "dated_slate"
    return "other"


def slate_date_from_path(path: str | Path) -> str | None:
    name = Path(path).name
    if DATED_SLATE_RE.match(name):
        return name.removesuffix(".json")
    return None


def artifact_snapshot_row(
    path: str | Path,
    *,
    repo_root: str | Path,
    source_commit: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifact_path = Path(path)
    root = Path(repo_root)
    raw = artifact_path.read_bytes()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{artifact_path} is not valid JSON") from exc

    try:
        rel_path = artifact_path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        rel_path = artifact_path.as_posix()

    return {
        "artifact_path": rel_path,
        "artifact_kind": artifact_kind(artifact_path),
        "slate_date": slate_date_from_path(artifact_path),
        "source_commit": source_commit,
        "content_sha256": hashlib.sha256(raw).hexdigest(),
        "size_bytes": len(raw),
        "payload": payload,
        "metadata": metadata or {},
    }
