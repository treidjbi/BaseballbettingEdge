"""Backfill pitcher_throws on historical picks_history.json rows.

Run: 2026-04-16
Scope: rows where pitcher_throws IS None
Date range covered: 2026-03-25 .. 2026-04-10 (cutover boundary; nulls only
  exist on/before 2026-04-10 — see a1_pitcher_throws.py for the audit)
Rows updated this run: 307 (across 149 unique pitchers)

Companion to the A1 fix in pipeline/fetch_stats.py. The bug there caused
~69% of historical rows to have pitcher_throws=None, plus the post-cutover
rows to be wrongly defaulted to "R". This script fixes ONLY the None rows
— per global policy P1 we don't retroactively rewrite the post-cutover "R"
values, because doing so would change the platoon delta that informed the
already-graded calibration loss for those picks.

Per global policy P4: this script ONLY mutates the pitcher_throws field on
existing rows. It preserves dict order, formatting (indent=2), and every
other field on every row. Verify with:
    git diff -- data/picks_history.json
should show ONLY pitcher_throws line changes on existing rows.

Lookup source: MLB /people/search?names=<full name>. Returns pitchHand.code
('R' / 'L' / 'S'). Falls back to "R" only if the search returns zero hits
(very rare — typically a misspelling or retired player).
"""
import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
HIST = ROOT / "data" / "picks_history.json"
MLB_BASE = "https://statsapi.mlb.com/api/v1"
THROTTLE_S = 0.4  # be polite to MLB Stats API


def lookup_pitch_hand(name: str) -> str | None:
    """Return 'R'/'L'/'S' for a pitcher name, or None if no match."""
    try:
        resp = requests.get(
            f"{MLB_BASE}/people/search",
            params={"names": name},
            timeout=15,
        )
        resp.raise_for_status()
        people = resp.json().get("people") or []
    except Exception as e:
        print(f"  WARN: lookup failed for {name!r}: {e}", file=sys.stderr)
        return None
    # Prefer pitchers; fall back to first hit.
    pitchers = [p for p in people if (p.get("primaryPosition") or {}).get("code") == "1"]
    candidate = (pitchers or people or [None])[0]
    if not candidate:
        return None
    code = (candidate.get("pitchHand") or {}).get("code")
    return code if code in ("R", "L", "S") else None


def main() -> int:
    if not HIST.exists():  # global policy P2
        print(f"ERROR: {HIST} not found.", file=sys.stderr)
        return 1

    picks = json.loads(HIST.read_text())
    null_rows = [p for p in picks if p.get("pitcher_throws") is None]
    if not null_rows:
        print("No null pitcher_throws rows — nothing to backfill.")
        return 0

    unique_names = sorted({p["pitcher"] for p in null_rows})
    print(f"{len(null_rows)} null rows across {len(unique_names)} unique pitchers")

    hand_by_name: dict[str, str] = {}
    for i, name in enumerate(unique_names, 1):
        hand = lookup_pitch_hand(name)
        if hand is None:
            print(f"  [{i:3d}/{len(unique_names)}] {name!r}: no match — defaulting to R")
            hand = "R"
        else:
            print(f"  [{i:3d}/{len(unique_names)}] {name!r}: {hand}")
        hand_by_name[name] = hand
        time.sleep(THROTTLE_S)

    # Mutate ONLY the pitcher_throws field (policy P4).
    updated = 0
    for p in picks:
        if p.get("pitcher_throws") is None:
            new_hand = hand_by_name.get(p["pitcher"], "R")
            p["pitcher_throws"] = new_hand
            updated += 1

    tmp = HIST.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(picks, indent=2))
    tmp.replace(HIST)   # atomic on both Windows and POSIX
    print(f"\nUpdated {updated} rows. Wrote {HIST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
