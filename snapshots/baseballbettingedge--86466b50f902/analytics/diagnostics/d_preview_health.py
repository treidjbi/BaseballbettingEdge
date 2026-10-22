"""Classify preview health from local artifacts plus an optional live probe."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
PIPELINE_DIR = ROOT / "pipeline"
if str(PIPELINE_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINE_DIR))

from fetch_odds import BASE_URL, MARKET_ID, SPORT_ID, parse_k_props

PHOENIX = ZoneInfo("America/Phoenix")
PREVIEW_PATH = ROOT / "data" / "preview_lines.json"


@dataclass
class PreviewSnapshot:
    date: str | None
    fetched_at: str | None
    line_count: int
    exists: bool


@dataclass
class ProbeResult:
    status: str
    reason: str
    line_count: int = 0
    fetched_dates: tuple[str, ...] = ()


def expected_preview_date(day: date | None = None) -> str:
    if day is None:
        day = datetime.now(PHOENIX).date()
    return day.isoformat()


def preview_is_due(target_day: date, now_local: datetime | None = None) -> bool:
    if now_local is None:
        now_local = datetime.now(PHOENIX)
    return target_day <= now_local.date()


def load_preview_snapshot(path: Path = PREVIEW_PATH) -> PreviewSnapshot:
    if not path.exists():
        return PreviewSnapshot(date=None, fetched_at=None, line_count=0, exists=False)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return PreviewSnapshot(date=None, fetched_at=None, line_count=0, exists=True)
    lines = payload.get("lines") or {}
    return PreviewSnapshot(
        date=payload.get("date"),
        fetched_at=payload.get("fetched_at"),
        line_count=len(lines),
        exists=True,
    )


def _probe_headers() -> dict[str, str] | None:
    key = os.environ.get("RUNDOWN_API_KEY", "").strip()
    if not key:
        return None
    return {"X-TheRundown-Key": key, "Accept": "application/json"}


def probe_preview_source(target_date: str) -> ProbeResult:
    headers = _probe_headers()
    if headers is None:
        return ProbeResult(
            status="missing_api_key",
            reason="RUNDOWN_API_KEY is not set; skipped live TheRundown probe",
        )

    target_day = datetime.strptime(target_date, "%Y-%m-%d").date()
    fetched_dates = [target_date, (target_day + timedelta(days=1)).isoformat()]
    props: list[dict] = []

    for fetch_date in fetched_dates:
        try:
            response = requests.get(
                f"{BASE_URL}/sports/{SPORT_ID}/events/{fetch_date}",
                headers=headers,
                params={"market_ids": MARKET_ID},
                timeout=15,
            )
        except requests.RequestException as exc:
            return ProbeResult(
                status="upstream_failure",
                reason=f"request error for {fetch_date}: {type(exc).__name__}: {exc}",
                fetched_dates=tuple(fetched_dates),
            )

        if response.status_code in (401, 403):
            return ProbeResult(
                status="auth_failure",
                reason=f"{response.status_code} from TheRundown for {fetch_date}",
                fetched_dates=tuple(fetched_dates),
            )
        if response.status_code >= 400:
            return ProbeResult(
                status="upstream_failure",
                reason=f"HTTP {response.status_code} from TheRundown for {fetch_date}",
                fetched_dates=tuple(fetched_dates),
            )

        try:
            payload = response.json()
        except ValueError as exc:
            return ProbeResult(
                status="upstream_failure",
                reason=f"invalid JSON from TheRundown for {fetch_date}: {exc}",
                fetched_dates=tuple(fetched_dates),
            )

        props.extend(parse_k_props(payload))

    return ProbeResult(
        status="ok",
        reason="live TheRundown probe succeeded",
        line_count=len(props),
        fetched_dates=tuple(fetched_dates),
    )


def classify_preview_health(
    *,
    target_date: str,
    preview_due: bool,
    preview_date: str | None,
    preview_line_count: int,
    probe_status: str | None = None,
    probe_line_count: int = 0,
) -> dict:
    if preview_date == target_date and preview_line_count > 0:
        return {
            "status": "healthy",
            "reason": f"preview_lines.json already has {preview_line_count} lines for {target_date}",
        }

    if not preview_due:
        return {
            "status": "awaiting_preview_window",
            "reason": f"preview for {target_date} is not due yet in America/Phoenix",
        }

    if probe_status == "auth_failure":
        return {
            "status": "auth_failure",
            "reason": "401/403 from TheRundown while preview was due",
        }

    if probe_status == "upstream_failure":
        return {
            "status": "upstream_failure",
            "reason": "live probe hit a non-auth upstream failure while preview was due",
        }

    if probe_status == "ok" and probe_line_count == 0:
        return {
            "status": "no_preview_lines_yet",
            "reason": f"live probe found zero K props for {target_date}",
        }

    if probe_status == "ok" and probe_line_count > 0:
        stale_date = preview_date or "missing"
        return {
            "status": "stale_preview_artifact",
            "reason": (
                f"live probe found {probe_line_count} props for {target_date}, "
                f"but local preview snapshot is stale ({stale_date})"
            ),
        }

    return {
        "status": "indeterminate",
        "reason": "preview is due, but no live probe result was available to classify the failure mode",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        default=expected_preview_date(),
        help="Preview target date in America/Phoenix (YYYY-MM-DD). Defaults to today.",
    )
    parser.add_argument(
        "--skip-probe",
        action="store_true",
        help="Classify from local artifacts only; do not hit TheRundown.",
    )
    args = parser.parse_args()

    target_day = datetime.strptime(args.date, "%Y-%m-%d").date()
    snapshot = load_preview_snapshot()
    probe = ProbeResult(status="skipped", reason="live probe skipped by flag")
    if not args.skip_probe:
        probe = probe_preview_source(args.date)

    classification = classify_preview_health(
        target_date=args.date,
        preview_due=preview_is_due(target_day),
        preview_date=snapshot.date,
        preview_line_count=snapshot.line_count,
        probe_status=probe.status,
        probe_line_count=probe.line_count,
    )

    report = {
        "target_date": args.date,
        "classification": classification,
        "preview_snapshot": asdict(snapshot),
        "probe": asdict(probe),
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
