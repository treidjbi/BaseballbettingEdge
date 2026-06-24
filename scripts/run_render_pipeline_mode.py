"""Render-friendly wrapper for artifact pipeline scheduler rehearsals.

The wrapper mirrors GitHub's run-type and artifact-publish contract while
allowing Render rehearsal rows to publish under a shadow key prefix.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402
from scripts.publish_pipeline_artifacts_to_supabase import run as publish_artifacts  # noqa: E402

PHOENIX = ZoneInfo("America/Phoenix")
DEFAULT_ARTIFACT_API_URL = "https://baseballbettingedge.netlify.app/.netlify/functions/get-artifact"


@dataclass(frozen=True)
class PublishContract:
    pipeline_args: list[str]
    pipeline_run_type: str
    publish_date: str
    publish_scope: str


@dataclass(frozen=True)
class HydrationArtifact:
    artifact_type: str
    path: Path
    date: str | None = None
    required: bool = True


def _parse_date(date_text: str) -> datetime:
    return datetime.strptime(date_text, "%Y-%m-%d").replace(tzinfo=PHOENIX)


def resolve_slate_date(value: str | None) -> str:
    if value:
        _parse_date(value)
        return value
    return datetime.now(PHOENIX).strftime("%Y-%m-%d")


def build_publish_contract(mode: str, slate_date: str) -> PublishContract:
    if mode not in {"preview", "grading", "pipeline", "lock"}:
        raise ValueError(f"Unsupported render pipeline mode: {mode}")

    pipeline_args = [sys.executable, "pipeline/run_pipeline.py", slate_date]
    pipeline_run_type = "full"
    publish_date = slate_date
    publish_scope = "pipeline"

    if mode != "pipeline":
        pipeline_args.extend(["--run-type", mode])
        pipeline_run_type = mode

    if mode == "preview":
        publish_scope = "preview"

    if mode == "lock":
        publish_scope = "lock"

    if mode == "grading":
        publish_date = (_parse_date(slate_date) - timedelta(days=1)).strftime("%Y-%m-%d")
        publish_scope = "grading"

    return PublishContract(
        pipeline_args=pipeline_args,
        pipeline_run_type=pipeline_run_type,
        publish_date=publish_date,
        publish_scope=publish_scope,
    )


def resolve_artifact_key_prefix(
    contract: PublishContract,
    *,
    shadow_prefix: bool,
    explicit_prefix: str,
) -> str:
    if explicit_prefix:
        return explicit_prefix
    if shadow_prefix:
        return f"render_shadow:{contract.publish_date}:"
    return ""


def shadow_runtime_env_overrides(
    artifact_key_prefix: str,
    *,
    provider_rehearsal: bool = False,
) -> dict[str, str]:
    if not artifact_key_prefix:
        return {}
    overrides = {
        "BATTER_SPLIT_COLLECTION_MAX_NEW": "0",
        "ENABLE_SUPABASE_LOCK_CONSUMER": "false",
        "SUPABASE_LOCK_CONSUMER_STRICT": "false",
    }
    if provider_rehearsal:
        overrides.update(
            {
                "OFFICIAL_MARKET_SOURCE": "boltodds_propline",
                "ENABLE_BOLTODDS_PIPELINE_SOURCE": "true",
                "OFFICIAL_MARKET_STRICT": "true",
            }
        )
    else:
        overrides.update(
            {
                "OFFICIAL_MARKET_SOURCE": "therundown",
                "ENABLE_BOLTODDS_PIPELINE_SOURCE": "false",
            }
        )
    return overrides


def live_official_provider_env_overrides(mode: str, artifact_key_prefix: str) -> dict[str, str]:
    """Force the approved official market posture for live preview/full refreshes."""
    if artifact_key_prefix or mode not in {"preview", "pipeline"}:
        return {}
    return {
        "OFFICIAL_MARKET_SOURCE": "therundown_propline",
        "OFFICIAL_MARKET_SOURCE_FALLBACK": "therundown",
        "ENABLE_THERUNDOWN_PROPLINE_PIPELINE_SOURCE": "true",
        "ENABLE_BOLTODDS_PIPELINE_SOURCE": "false",
        "OFFICIAL_MARKET_STRICT": "false",
    }


def runtime_env_overrides(
    mode: str,
    artifact_key_prefix: str,
    *,
    provider_rehearsal: bool = False,
) -> dict[str, str]:
    overrides = shadow_runtime_env_overrides(
        artifact_key_prefix,
        provider_rehearsal=provider_rehearsal,
    )
    overrides.update(live_official_provider_env_overrides(mode, artifact_key_prefix))
    return overrides


def live_artifact_hydration_enabled(mode: str, artifact_key_prefix: str) -> bool:
    if artifact_key_prefix:
        return False
    value = os.environ.get("RENDER_PIPELINE_HYDRATE_ARTIFACTS", "true").strip().lower()
    if value in {"0", "false", "no", "off"}:
        return False
    return mode in {"grading", "pipeline", "lock"}


def artifact_api_url(artifact_type: str, date: str | None = None) -> str:
    base = os.environ.get("RENDER_PIPELINE_ARTIFACT_API_URL", "").strip() or DEFAULT_ARTIFACT_API_URL
    params = {"type": artifact_type}
    if date:
        params["date"] = date
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}{urlencode(params)}"


def hydration_artifacts(slate_date: str) -> list[HydrationArtifact]:
    return [
        HydrationArtifact("today", Path("dashboard/data/processed/today.json")),
        HydrationArtifact("dated_slate", Path("dashboard/data/processed") / f"{slate_date}.json", date=slate_date),
        HydrationArtifact("index", Path("dashboard/data/processed/index.json")),
        HydrationArtifact("steam", Path("dashboard/data/processed/steam.json")),
        HydrationArtifact("performance", Path("dashboard/data/performance.json")),
        HydrationArtifact("params", Path("data/params.json")),
        HydrationArtifact("preview_lines", Path("data/preview_lines.json")),
        HydrationArtifact("picks_history", Path("data/picks_history.json")),
        HydrationArtifact("fangraphs_cache", Path("data/fangraphs_cache.json"), required=False),
    ]


def hydrate_live_artifacts_from_api(*, root: Path, slate_date: str) -> int:
    hydrated = 0
    for artifact in hydration_artifacts(slate_date):
        response = requests.get(
            artifact_api_url(artifact.artifact_type, artifact.date),
            timeout=20,
        )
        if response.status_code == 404 and not artifact.required:
            continue
        response.raise_for_status()
        target = root / artifact.path
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8") as handle:
            json.dump(response.json(), handle, indent=2)
        hydrated += 1
    return hydrated


def _apply_env_overrides(overrides: dict[str, str]) -> dict[str, str | None]:
    previous = {key: os.environ.get(key) for key in overrides}
    for key, value in overrides.items():
        os.environ[key] = value
    return previous


def _restore_env(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def resolve_source_run_id(mode: str, publish_date: str) -> str:
    render_run_id = os.environ.get("RENDER_RUN_ID", "").strip()
    if render_run_id:
        return render_run_id
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"manual-render-{mode}-{publish_date}-{timestamp}"


def resolve_source_commit_sha() -> str | None:
    render_commit = os.environ.get("RENDER_GIT_COMMIT", "").strip()
    if render_commit:
        return render_commit
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip() or None


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _env_flag(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    return value not in {"0", "false", "no", "off"}


def validate_provider_rehearsal_allowed(*, provider_rehearsal: bool) -> None:
    if not provider_rehearsal:
        return
    if _env_flag("ALLOW_BOLTODDS_PROVIDER_REHEARSAL"):
        return
    raise ValueError(
        "BoltOdds provider rehearsal is retired; set "
        "ALLOW_BOLTODDS_PROVIDER_REHEARSAL=true only after Tyler opens a new "
        "provider trial."
    )


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("preview", "grading", "pipeline", "lock"), required=True)
    parser.add_argument("--date", help="Optional Phoenix slate date, YYYY-MM-DD.")
    parser.add_argument("--execute", action="store_true", help="Publish rows to Supabase after the pipeline run.")
    parser.add_argument(
        "--shadow-prefix",
        action="store_true",
        help="Publish rows under render_shadow:<publish-date>: keys for safe rehearsal.",
    )
    parser.add_argument(
        "--artifact-key-prefix",
        default="",
        help="Explicit artifact key prefix. Overrides --shadow-prefix.",
    )
    parser.add_argument(
        "--provider-rehearsal",
        action="store_true",
        help=(
            "Retired: with an explicit reopened-trial override, run shadow "
            "artifact keys against the historical BoltOdds/PropLine adapter."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    slate_date = resolve_slate_date(args.date)
    contract = build_publish_contract(args.mode, slate_date)
    artifact_key_prefix = resolve_artifact_key_prefix(
        contract,
        shadow_prefix=args.shadow_prefix,
        explicit_prefix=args.artifact_key_prefix,
    )
    if args.provider_rehearsal and not artifact_key_prefix:
        raise ValueError("--provider-rehearsal requires --shadow-prefix or --artifact-key-prefix")
    validate_provider_rehearsal_allowed(provider_rehearsal=args.provider_rehearsal)
    runtime_previous = _apply_env_overrides(
        runtime_env_overrides(
            args.mode,
            artifact_key_prefix,
            provider_rehearsal=args.provider_rehearsal,
        )
    )

    try:
        hydrated_artifacts = 0
        if live_artifact_hydration_enabled(args.mode, artifact_key_prefix):
            hydrated_artifacts = hydrate_live_artifacts_from_api(root=ROOT, slate_date=contract.publish_date)
            print(
                "render_pipeline_mode_hydration "
                f"mode={args.mode} slate_date={contract.publish_date} artifacts={hydrated_artifacts}"
            )
        subprocess.run(contract.pipeline_args, cwd=ROOT, check=True)

        writer = None
        if args.execute:
            writer = SupabaseMarketWriter(_env("SUPABASE_URL"), _env("SUPABASE_SERVICE_ROLE_KEY"))

        previous_run_type = os.environ.get("PIPELINE_RUN_TYPE")
        os.environ["PIPELINE_RUN_TYPE"] = contract.pipeline_run_type
        try:
            result = publish_artifacts(
                root=ROOT,
                writer=writer,
                slate_date=contract.publish_date,
                source="render_pipeline",
                source_run_id=resolve_source_run_id(args.mode, contract.publish_date),
                source_commit_sha=resolve_source_commit_sha(),
                execute=args.execute,
                scope=contract.publish_scope,
                artifact_key_prefix=artifact_key_prefix,
            )
        finally:
            if previous_run_type is None:
                os.environ.pop("PIPELINE_RUN_TYPE", None)
            else:
                os.environ["PIPELINE_RUN_TYPE"] = previous_run_type
    finally:
        _restore_env(runtime_previous)

    mode = "execute" if args.execute else "dry_run"
    print(
        "render_pipeline_mode "
        f"mode={args.mode} slate_date={slate_date} publish_date={contract.publish_date} "
        f"scope={contract.publish_scope} publish_mode={mode} artifacts={result['artifact_count']} "
        f"artifact_key_prefix={artifact_key_prefix or '<none>'} "
        f"provider_rehearsal={str(args.provider_rehearsal).lower()} "
        f"hydrated_artifacts={hydrated_artifacts}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
