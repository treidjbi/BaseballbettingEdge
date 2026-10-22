"""Read-only exact-artifact preflight for prospective Alt Picks V2 activation."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_infra.alternative_pick_recording_v2 import (
    PHOENIX,
    assess_alternative_pick_artifact_v2,
)
from market_infra.published_artifacts import canonical_payload_sha256


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
    assessment = assess_alternative_pick_artifact_v2(
        slate_date=slate_date, payload=payload, observed_at=observed,
        require_before_t30=True,
    )
    if assessment["reason"] not in {"clean", "no_candidates", "too_late"}:
        return {**base, "ok": False, "status": "invalid_artifact"}
    candidates = assessment["candidates"]
    if assessment["reason"] == "no_candidates":
        return {**base, "ok": True, "status": "no_candidates"}
    t30s = list(assessment["candidate_t30"].values())
    first_t30 = min(t30s)
    too_late = assessment["reason"] == "too_late"
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
