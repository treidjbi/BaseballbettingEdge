"""Read-only exact-artifact preflight for prospective Alt Picks V2 activation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.request import urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_infra.alternative_pick_recording_v2 import (
    ACTIVE_POSTURES,
    ACTIVE_PROVIDERS,
    extract_alternative_pick_candidates_v2,
)
from market_infra.alternative_pick_selector import display_verdict
from market_infra.published_artifacts import canonical_payload_sha256


PHOENIX = ZoneInfo("America/Phoenix")
MAX_ARTIFACT_AGE = timedelta(minutes=90)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _utc(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(_text(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def _artifact_candidate_contract_valid(payload: dict[str, Any]) -> bool:
    for pitcher in payload.get("pitchers") or []:
        if not isinstance(pitcher, dict):
            continue
        tracked = pitcher.get("tracked_picks")
        if not isinstance(tracked, list):
            continue
        relevant = [pick for pick in tracked if isinstance(pick, dict) and display_verdict(pick).upper() != "PASS"]
        if not relevant:
            continue
        mode = _text(pitcher.get("market_source_mode")).lower().replace("+", "_")
        source = _text(pitcher.get("odds_source")).lower().replace("+", "_")
        posture = mode or source
        if posture not in ACTIVE_POSTURES or source not in ACTIVE_POSTURES or (mode and mode != source):
            return False
        if _text(pitcher.get("line_source_provider")).lower() not in ACTIVE_PROVIDERS:
            return False
        for pick in relevant:
            if _utc(pick.get("game_time") or pitcher.get("game_time")) is None:
                return False
    return True


def evaluate_activation_window(
    *, payload: dict[str, Any], raw_bytes: bytes, observed_at: datetime,
) -> dict[str, Any]:
    observed = observed_at.astimezone(timezone.utc)
    artifact_sha = hashlib.sha256(raw_bytes).hexdigest()
    payload_sha = canonical_payload_sha256(payload) if isinstance(payload, dict) else ""
    generated = _utc(payload.get("generated_at")) if isinstance(payload, dict) else None
    slate_date = observed.astimezone(PHOENIX).date().isoformat()
    base = {
        "artifact_sha256": artifact_sha,
        "payload_sha256": payload_sha,
        "artifact_generated_at": generated.isoformat() if generated else None,
        "candidate_count": 0,
        "first_t30": None,
        "release_evidence": False,
    }
    if (
        not isinstance(payload, dict)
        or _text(payload.get("date")) != slate_date
        or generated is None
        or generated > observed + timedelta(minutes=5)
        or observed - generated > MAX_ARTIFACT_AGE
        or not _artifact_candidate_contract_valid(payload)
    ):
        return {**base, "ok": False, "status": "invalid_artifact"}
    candidates = extract_alternative_pick_candidates_v2(slate_date=slate_date, payload=payload)
    if not candidates:
        return {**base, "ok": True, "status": "no_candidates"}
    t30s = [
        game_time - timedelta(minutes=30)
        for candidate, _, _ in candidates
        if (game_time := _utc(candidate.get("game_time"))) is not None
    ]
    if len(t30s) != len(candidates):
        return {**base, "ok": False, "status": "invalid_artifact"}
    first_t30 = min(t30s)
    too_late = any(observed >= t30 for t30 in t30s)
    return {
        **base,
        "ok": not too_late,
        "status": "too_late" if too_late else "clean",
        "candidate_count": len(candidates),
        "first_t30": first_t30.isoformat(),
        "release_evidence": False,
    }


def fetch_artifact_once(
    artifact_url: str, *, opener: Callable[..., Any] = urlopen,
) -> tuple[dict[str, Any], bytes]:
    with opener(artifact_url, timeout=20) as response:
        raw = response.read()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("artifact is not an object")
    return payload, raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-url", required=True)
    args = parser.parse_args(argv)
    try:
        payload, raw = fetch_artifact_once(args.artifact_url)
        result = evaluate_activation_window(
            payload=payload, raw_bytes=raw, observed_at=datetime.now(timezone.utc),
        )
    except Exception:
        print("status=invalid_artifact", file=sys.stderr)
        return 1
    print(
        f"artifact_sha256={result['artifact_sha256']} "
        f"payload_sha256={result['payload_sha256']} "
        f"artifact_generated_at={result['artifact_generated_at']} "
        f"candidate_count={result['candidate_count']} "
        f"first_t30={result['first_t30']} status={result['status']}"
    )
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
