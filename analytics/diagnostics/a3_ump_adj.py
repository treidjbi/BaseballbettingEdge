"""Diagnose ump_k_adj zero-distribution in picks_history.json.

Context (2026-04-17):
  The model-audit analytics report that 100% of 145 staked post-4/8 picks show
  ump_k_adj = 0. Candidate explanations:
    (a) ump data legitimately has near-zero adjustment for every game,
    (b) name-matching (ump.news -> career_k_rates.json) is silently failing,
    (c) scrape_hp_assignments() returns an empty dict because ump.news hasn't
        posted yet at 6am PT pipeline run time,
    (d) fetch_umpires() is silently erroring out upstream.

This script prints four things:
  1. Distribution of ump_k_adj across picks_history (zero / null / nonzero).
  2. Live scrape_hp_assignments() output (assignments dict + size).
  3. Size + sample of _load_career_rates() lookup table.
  4. End-to-end fetch_umpires() result on today's actual props if
     dashboard/data/processed/today.json exists; otherwise a synthetic 3-game
     props list to sanity-check the team-name matching path.

Note: the original plan draft called fetch_umpires("2026-04-16") which is
wrong — the real signature is fetch_umpires(props: list).
"""
import json
import logging
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HIST = ROOT / "data" / "picks_history.json"

# Global policy P2: fail loud if picks_history is missing.
if not HIST.exists():
    print(f"ERROR: {HIST} not found. Run the pipeline at least once to generate it.")
    raise SystemExit(1)

# Route pipeline log.info / log.warning to the console so we can see what
# fetch_umpires is actually logging at diagnostic time.
logging.basicConfig(level=logging.INFO, format="[%(name)s %(levelname)s] %(message)s")

picks = json.loads(HIST.read_text())

# ---- 1. Distribution across picks_history ---------------------------------
print("=" * 70)
print("1. ump_k_adj distribution across picks_history.json")
print("=" * 70)
vals = [p.get("ump_k_adj") for p in picks]
nonzero = [v for v in vals if v is not None and abs(v) > 1e-6]
zero = [v for v in vals if v == 0.0]
null = [v for v in vals if v is None]

print(f"Total picks:     {len(vals)}")
print(f"  exactly 0.0:   {len(zero)}")
print(f"  null/missing:  {len(null)}")
print(f"  nonzero:       {len(nonzero)}")
if nonzero:
    print(f"  nonzero range: {min(nonzero):+.4f} .. {max(nonzero):+.4f}")
    print(f"  nonzero mean:  {sum(nonzero) / len(nonzero):+.4f}")

# Breakdown by date — did nonzero ever exist historically?
by_date_nonzero = Counter()
by_date_total = Counter()
for p in picks:
    d = p.get("date", "unknown")
    by_date_total[d] += 1
    v = p.get("ump_k_adj")
    if v is not None and abs(v) > 1e-6:
        by_date_nonzero[d] += 1

print("\nDates with any nonzero ump_k_adj (sorted):")
any_nonzero_dates = sorted(d for d, n in by_date_nonzero.items() if n > 0)
if not any_nonzero_dates:
    print("  (none — ump_k_adj has been 0 for every pick in history)")
else:
    for d in any_nonzero_dates:
        print(f"  {d}  {by_date_nonzero[d]}/{by_date_total[d]} nonzero")

# ---- 2. Live MLB Stats API officials fetch --------------------------------
print()
print("=" * 70)
print("2. Live fetch_hp_assignments() output (MLB Stats API /schedule?hydrate=officials)")
print("=" * 70)
sys.path.insert(0, str(ROOT / "pipeline"))
from fetch_umpires import (  # noqa: E402
    fetch_hp_assignments,
    _load_career_rates,
    fetch_umpires,
    ABBR_TO_NAME_SUBSTR,
)

from datetime import date as _date  # noqa: E402

_today_str = _date.today().strftime("%Y-%m-%d")
try:
    assignments = fetch_hp_assignments(_today_str)
except Exception as exc:
    print(f"fetch_hp_assignments() raised: {exc!r}")
    assignments = {}

print(f"Assignments returned: {len(assignments)}")
for k, v in sorted(assignments.items()):
    mapped = ABBR_TO_NAME_SUBSTR.get(k.upper())
    flag = "" if mapped else "  <-- NO ABBR MAP"
    print(f"  {k:>5} -> {v}{flag}")

unmapped = [k for k in assignments if k.upper() not in ABBR_TO_NAME_SUBSTR]
if unmapped:
    print(f"\nWARNING: {len(unmapped)} abbreviation(s) not in ABBR_TO_NAME_SUBSTR: {unmapped}")

# ---- 3. Career rates lookup ----------------------------------------------
print()
print("=" * 70)
print("3. _load_career_rates() lookup")
print("=" * 70)
try:
    career = _load_career_rates()
    print(f"Career rates loaded: {len(career)} umpires")
    sample_items = list(career.items())[:5]
    print("Sample (first 5, normalized keys):")
    for k, v in sample_items:
        print(f"  {k!r:40} -> {v:+.4f}")
    # Summary stats
    all_vals = list(career.values())
    if all_vals:
        print(f"Career rate range: {min(all_vals):+.4f} .. {max(all_vals):+.4f}")
        print(f"Career rate mean:  {sum(all_vals) / len(all_vals):+.4f}")
        near_zero = sum(1 for v in all_vals if abs(v) < 0.005)
        print(f"Umpires with |adj| < 0.005 (near-zero): {near_zero}/{len(all_vals)}")
except Exception as exc:
    print(f"_load_career_rates() raised: {exc!r}")
    career = {}

# Cross-check: of the umpires ump.news is currently assigning, how many are
# present in the career-rates table?
if assignments and career:
    print("\nAssignment -> career-rates lookup check:")
    from name_utils import normalize as _normalize  # noqa: E402

    hit = miss = 0
    for abbr, ump in sorted(assignments.items()):
        key = _normalize(ump)
        in_table = key in career
        hit += int(in_table)
        miss += int(not in_table)
        status = f"HIT  {career[key]:+.4f}" if in_table else "MISS"
        print(f"  {abbr:>5}  {ump:25} -> {status}")
    print(f"  Totals: {hit} hits / {miss} misses (of {len(assignments)} assignments)")

# ---- 4. End-to-end fetch_umpires on real or synthetic props --------------
print()
print("=" * 70)
print("4. End-to-end fetch_umpires() smoke test")
print("=" * 70)
TODAY_JSON = ROOT / "dashboard" / "data" / "processed" / "today.json"
used_today = False
if TODAY_JSON.exists():
    try:
        today_data = json.loads(TODAY_JSON.read_text())
        today_cards = today_data.get("pitchers", []) or today_data.get("cards", [])
        # Build a minimal props list from today.json fields.
        synth_props = []
        for c in today_cards:
            pitcher = c.get("pitcher") or c.get("name")
            team = c.get("team") or c.get("team_name")
            opp = c.get("opp_team") or c.get("opponent") or c.get("opp")
            if pitcher and team and opp:
                synth_props.append({"pitcher": pitcher, "team": team, "opp_team": opp})
        if synth_props:
            print(f"Using {len(synth_props)} props from today.json")
            used_today = True
    except Exception as exc:
        print(f"WARNING: failed to parse today.json ({exc!r}) — falling back to synthetic")
else:
    print(f"WARNING: {TODAY_JSON} not found — using synthetic props")

if not used_today:
    synth_props = [
        {"pitcher": "Pitcher A", "team": "New York Yankees", "opp_team": "Boston Red Sox"},
        {"pitcher": "Pitcher B", "team": "Los Angeles Dodgers", "opp_team": "San Francisco Giants"},
        {"pitcher": "Pitcher C", "team": "Houston Astros", "opp_team": "Texas Rangers"},
    ]
    print(f"Synthetic props: {len(synth_props)} (pairs: NYY/BOS, LAD/SF, HOU/TEX)")

result = fetch_umpires(synth_props, _today_str)
print(f"\nfetch_umpires() returned {len(result)} entries")
rnonzero = [(k, v) for k, v in result.items() if abs(v) > 1e-6]
rzero = [(k, v) for k, v in result.items() if v == 0.0]
print(f"  nonzero: {len(rnonzero)}")
print(f"  zero:    {len(rzero)}")
for k, v in sorted(result.items()):
    print(f"    {k:30} -> {v:+.4f}")

# Diagnosis summary -------------------------------------------------------
print()
print("=" * 70)
print("Diagnosis summary")
print("=" * 70)
if not assignments:
    print("-> scrape_hp_assignments returned EMPTY dict. Check the WARNING log above.")
    print("   Known state (2026-04-17): ump.news is NXDOMAIN — the domain no longer")
    print("   resolves. If that's still the failure mode, path A3.5 applies: document")
    print("   + keep the warn-and-degrade contract (see pipeline/fetch_umpires.py header).")
    print("   Other possibilities if ump.news comes back: site HTML changed (update the")
    print("   selector) or pre-10am-ET timing (assignments not posted yet).")
elif assignments and not rnonzero:
    print("-> Scrape returned assignments but fetch_umpires produced all zeros.")
    print("   Likely a name-matching / abbreviation-mapping problem. Path A3.4.")
elif assignments and rnonzero:
    print("-> Scrape + lookup both work TODAY. If historical picks are all zero, the")
    print("   outage was transient (domain returned, or pipeline ran before ~10am ET")
    print("   posting). Path A3.5 (document).")
