"""Lightweight helpers for pipeline observability and unresolved-prop health."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def format_stage_summary(stage: str, elapsed_seconds: float, **metrics: object) -> str:
    """Return a stable key=value log line for one pipeline stage."""
    elapsed_ms = max(0, int(round(elapsed_seconds * 1000)))
    parts = [f"stage={stage}", f"ms={elapsed_ms}"]
    for key, value in metrics.items():
        if value is None:
            continue
        parts.append(f"{key}={value}")
    return " ".join(parts)


def build_connection_health(
    props: list[dict],
    stats_map: dict,
    records: list[dict],
    build_failures: list[str] | None = None,
    sample_size: int = 3,
) -> dict:
    """Summarize props that survived intake but never became usable records."""
    record_names = {
        record.get("pitcher")
        for record in records
        if record.get("pitcher")
    }
    build_failure_names = set(build_failures or [])
    sample_unresolved_pitchers: list[str] = []
    sample_intake_filtered_pitchers: list[str] = []
    sample_feature_build_failures: list[str] = []
    missing_stats_count = 0
    feature_build_failures_count = 0

    for prop in props:
        name = (prop.get("pitcher") or "").strip()
        if not name or name in record_names:
            continue
        if name in build_failure_names:
            feature_build_failures_count += 1
            if len(sample_feature_build_failures) < sample_size:
                sample_feature_build_failures.append(name)
        else:
            missing_stats_count += 1
            if len(sample_intake_filtered_pitchers) < sample_size:
                sample_intake_filtered_pitchers.append(name)
        if len(sample_unresolved_pitchers) < sample_size:
            sample_unresolved_pitchers.append(name)

    unresolved_count = missing_stats_count + feature_build_failures_count
    model_candidate_count = sum(
        1
        for prop in props
        if stats_map.get((prop.get("pitcher") or "").strip())
    )
    return {
        "props_seen": len(props),
        "stats_resolved": model_candidate_count,
        "records_built": len(records),
        "unresolved_count": unresolved_count,
        "model_candidate_count": model_candidate_count,
        "intake_filtered_count": missing_stats_count,
        "missing_stats_count": missing_stats_count,
        "unresolved_after_stats_count": feature_build_failures_count,
        "feature_build_failures_count": feature_build_failures_count,
        "degraded": unresolved_count > 0,
        "sample_intake_filtered_pitchers": sample_intake_filtered_pitchers,
        "sample_feature_build_failures": sample_feature_build_failures,
        "sample_unresolved_pitchers": sample_unresolved_pitchers,
    }


def format_integrity_warning(connection_health: dict) -> str | None:
    """Return a concise warning when the slate has unresolved props."""
    if not connection_health.get("degraded"):
        return None
    sample = ", ".join(connection_health.get("sample_unresolved_pitchers", [])) or "-"
    return (
        "Slate integrity warning: "
        f"unresolved_props={connection_health['unresolved_count']} "
        f"missing_stats={connection_health['missing_stats_count']} "
        f"build_failures={connection_health['feature_build_failures_count']} "
        f"sample={sample}"
    )


def _default_today_path() -> Path:
    return Path(__file__).resolve().parents[2] / "dashboard" / "data" / "processed" / "today.json"


def main(argv: list[str] | None = None) -> int:
    argv = list(argv or sys.argv[1:])
    target = Path(argv[0]) if argv else _default_today_path()
    if not target.exists():
        print(f"ERROR: {target} not found")
        return 1

    payload = json.loads(target.read_text())
    print(json.dumps(payload.get("connection_health", {}), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
