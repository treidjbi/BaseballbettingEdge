"""Diagnose pitcher_throws null pattern in picks_history.json.

Findings (2026-04-16):
  - 307 / 447 history rows have pitcher_throws = None (~69%).
  - All nulls are dated 2026-03-25 .. 2026-04-10. Last null date == first
    non-null date == 2026-04-10 (mid-day cutover).
  - Post-cutover (2026-04-11 onward), 100% of rows have pitcher_throws == "R".
  - Spot check: known LHPs (Patrick Corbin, Max Fried, Shota Imanaga,
    Robbie Ray) all show "R" post-cutover. So the cutover only stopped
    None values from being written; it did NOT actually start populating
    real handedness.

Root cause (live bug, not historical-only):
  pipeline/fetch_stats.py:177 reads
      throws = pitcher.get("pitchHand", {}).get("code", "R")
  off the MLB /schedule endpoint with hydrate="probablePitcher,team".
  That hydrate level returns only {id, fullName, link} on probablePitcher
  — pitchHand is NEVER present — so throws always defaults to "R".

  pipeline/build_features.py:346 then does
      stats.get("throws", "R")
  which inherits the same wrong value.

  The 4/10 cutover that stopped writing None was the addition of the
  ", R" default to that line; before then the .get returned None on the
  bug path. The default papered over the symptom but didn't fix the bug.

Fix path (A1.4 → A1.6): fetch the real handedness from /people/{id} (which
DOES return pitchHand reliably) inside fetch_pitcher_stats and propagate
the value back to fetch_stats. Then build_features inherits a correct
"R"/"L" instead of always "R".

Backfill path (A1.8): for the 307 historical None rows, look up the real
hand via /people lookup and patch the JSON in place. Per global policy P1
this is safe — pitcher_throws only feeds the platoon delta forward of
write time, so backfilling does not retroactively change graded outcomes.
"""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HIST = ROOT / "data" / "picks_history.json"
if not HIST.exists():  # global policy P2
    print(f"ERROR: {HIST} not found. Run the pipeline at least once to generate it.")
    raise SystemExit(1)
picks = json.loads(HIST.read_text())

null_rows = [p for p in picks if p.get("pitcher_throws") is None]
non_null = [p for p in picks if p.get("pitcher_throws") is not None]

print(f"Total: {len(picks)}  null pitcher_throws: {len(null_rows)}")
print(f"Null by date:")
by_date = Counter(p.get("date", "unknown") for p in null_rows)
for d, n in sorted(by_date.items()):
    print(f"  {d}  n={n}")

print(f"\nFirst non-null date: {min((p.get('date', 'unknown') for p in non_null), default='none')}")
print(f"Last null date:      {max((p.get('date', 'unknown') for p in null_rows), default='none')}")

# Is there a pitcher pattern?
print("\nTop-10 pitchers with null pitcher_throws:")
for pitcher, n in Counter(p.get("pitcher", "unknown") for p in null_rows).most_common(10):
    print(f"  {pitcher:<30} n={n}")
