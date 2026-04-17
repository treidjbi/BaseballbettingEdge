"""Rewrite wrongly-defaulted pitcher_throws on post-cutover picks_history.json rows.

Run: 2026-04-17
Scope: rows where date >= 2026-04-11 AND pitcher_throws == "R"
Date range covered: 2026-04-11 .. 2026-04-17 (the bug contamination window)
Expected affected rows: ~133 across ~128 unique pitchers (pre-run audit)

## Context

Task A1 fixed a bug in pipeline/fetch_stats.py (commit 0407846) where the MLB
/schedule?hydrate=probablePitcher endpoint silently failed to return pitchHand,
causing every pitcher's pitcher_throws to be forced to the "R" default.

The historical None-rows backfill (commit 517f473, a1_backfill_throws.py) only
touched rows with pitcher_throws IS None. It deliberately skipped the
post-cutover window (2026-04-11 onward) where the same bug wrote literal "R"
values, citing a conservative P1 (calibration integrity) concern.

## Why this rewrite is safe (P1 re-evaluation)

The calibrator reads the STORED `lambda` field (the model's output at decision
time), not `pitcher_throws` (an input metadata field). Re-labeling handedness
on these rows changes zero calibration math:
  residual = actual_Ks - stored_lambda
is independent of pitcher_throws. The stored lambda for these rows will
correctly continue to reflect the R-assumed platoon delta that was live at
decision time — this script does NOT recompute lambda.

## What this script does (and does not) mutate

Per global policy P4: this script ONLY mutates the pitcher_throws field on
existing rows. It preserves dict order, formatting (indent=2), row order, and
every other field on every row. Verify with:
    git diff HEAD -- data/picks_history.json | \
        grep -E "^[+-]" | grep -v "^[+-]{3}" | grep -v "pitcher_throws"
should be empty.

## Lookup strategy

picks_history.json rows do not carry pitcher_id, so this script uses
MLB /people/search?names=<full name> (same as a1_backfill_throws.py). Returns
pitchHand.code ('R' / 'L' / 'S'). Rows where the lookup fails OR returns a
value other than "L" are left UNCHANGED — we only overwrite when we have
positive evidence the pitcher is left-handed. Switch-hitters ("S") are not
expected for pitchers; if encountered, the row is left as-is and logged.
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
CUTOVER_DATE = "2026-04-11"


def lookup_pitch_hand_by_name(name: str) -> str | None:
    """Return 'R'/'L'/'S' for a pitcher name, or None on miss/error."""
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


def lookup_pitch_hand_by_id(pid: int) -> str | None:
    """Return 'R'/'L'/'S' by MLB person id, or None on miss/error."""
    try:
        resp = requests.get(f"{MLB_BASE}/people/{pid}", timeout=15)
        resp.raise_for_status()
        people = resp.json().get("people") or []
    except Exception as e:
        print(f"  WARN: id lookup failed for id={pid}: {e}", file=sys.stderr)
        return None
    if not people:
        return None
    code = (people[0].get("pitchHand") or {}).get("code")
    return code if code in ("R", "L", "S") else None


def main() -> int:
    if not HIST.exists():  # global policy P2
        print(f"ERROR: {HIST} not found.", file=sys.stderr)
        return 1

    picks = json.loads(HIST.read_text())

    # Step 2: candidate rows
    candidate_rows = [
        p
        for p in picks
        if p.get("date", "") >= CUTOVER_DATE and p.get("pitcher_throws") == "R"
    ]
    if not candidate_rows:
        print("No candidate rows — nothing to rewrite.")
        return 0

    unique_pitchers: dict[str, int | None] = {}
    for r in candidate_rows:
        name = r["pitcher"]
        pid = r.get("pitcher_id")
        # Prefer an id if any row for this pitcher has one.
        if name not in unique_pitchers or (unique_pitchers[name] is None and pid):
            unique_pitchers[name] = pid

    print(
        f"Candidate rows (date >= {CUTOVER_DATE} AND pitcher_throws == \"R\"): "
        f"{len(candidate_rows)}"
    )
    print(f"Unique pitchers in candidates: {len(unique_pitchers)}")

    # Step 3-4: resolve actual handedness per unique pitcher
    actual_hand_by_pitcher: dict[str, str | None] = {}
    attempted = 0
    succeeded = 0
    failed = 0
    for i, (name, pid) in enumerate(sorted(unique_pitchers.items()), 1):
        attempted += 1
        hand = lookup_pitch_hand_by_id(pid) if pid else None
        if hand is None:
            hand = lookup_pitch_hand_by_name(name)
        if hand is None:
            failed += 1
            print(
                f"  [{i:3d}/{len(unique_pitchers)}] {name!r}: LOOKUP FAILED "
                f"— leaving rows as R",
                file=sys.stderr,
            )
        else:
            succeeded += 1
            print(f"  [{i:3d}/{len(unique_pitchers)}] {name!r}: {hand}")
        actual_hand_by_pitcher[name] = hand
        time.sleep(THROTTLE_S)

    # Step 5: count updates before writing
    to_rewrite = 0
    unchanged_actual_r = 0
    skipped_lookup_failed = 0
    for r in candidate_rows:
        hand = actual_hand_by_pitcher.get(r["pitcher"])
        if hand == "L":
            to_rewrite += 1
        elif hand == "R":
            unchanged_actual_r += 1
        else:
            # None (failed) or "S" (unexpected) — leave as is.
            skipped_lookup_failed += 1

    print()
    print(f"Lookups attempted: {attempted} / succeeded: {succeeded} / failed: {failed}")
    print(f"Rows rewritten R -> L: {to_rewrite}")
    print(f"Rows unchanged (actually R): {unchanged_actual_r}")
    print(f"Rows skipped (lookup failed, left as R): {skipped_lookup_failed}")

    if to_rewrite == 0:
        print("No rows to rewrite — not writing file.")
        return 0

    # Step 5 (continued): mutate ONLY pitcher_throws on L-confirmed rows
    rewritten = 0
    for p in picks:
        if p.get("date", "") < CUTOVER_DATE:
            continue
        if p.get("pitcher_throws") != "R":
            continue
        hand = actual_hand_by_pitcher.get(p["pitcher"])
        if hand == "L":
            p["pitcher_throws"] = "L"
            rewritten += 1
    assert rewritten == to_rewrite, (
        f"Internal inconsistency: rewrote {rewritten} but planned {to_rewrite}"
    )

    # Step 7: atomic write
    tmp = HIST.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(picks, indent=2))
    tmp.replace(HIST)  # atomic on both Windows and POSIX
    print(f"Wrote {HIST} (atomic)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
