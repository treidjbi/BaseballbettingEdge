"""Diagnose dormant SwStr signal in picks_history.json and live fetch_swstr().

Purpose:
  - Confirm whether stored picks are carrying neutral SwStr inputs
  - Distinguish "current SwStr missing" from "career baseline missing"
  - Probe the live fetch_swstr() contract on a small pitcher sample
"""
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HIST = ROOT / "data" / "picks_history.json"

if not HIST.exists():
    print(f"ERROR: {HIST} not found")
    raise SystemExit(1)

rows = json.loads(HIST.read_text(encoding="utf-8"))
cutoff_date = date(2026, 4, 8)
filtered_rows = []
skipped_missing_date = 0
skipped_malformed_date = 0

for row in rows:
    raw_date = row.get("date")
    if raw_date in (None, ""):
        skipped_missing_date += 1
        continue
    try:
        parsed_date = date.fromisoformat(raw_date)
    except ValueError:
        skipped_malformed_date += 1
        continue
    if parsed_date >= cutoff_date:
        row = dict(row)
        row["_parsed_date"] = parsed_date
        filtered_rows.append(row)

rows = filtered_rows

print("=== Stored picks since 2026-04-08 ===")
print("rows:", len(rows))
print("skipped missing date:", skipped_missing_date)
print("skipped malformed date:", skipped_malformed_date)
print("swstr_delta_k9 nonzero:", sum(1 for r in rows if abs((r.get("swstr_delta_k9") or 0.0)) > 1e-9))
print("swstr_pct is None:", sum(1 for r in rows if r.get("swstr_pct") is None))
print("career_swstr_pct is None:", sum(1 for r in rows if r.get("career_swstr_pct") is None))
print(
    "current==career:",
    sum(
        1 for r in rows
        if r.get("swstr_pct") is not None
        and r.get("career_swstr_pct") is not None
        and r.get("swstr_pct") == r.get("career_swstr_pct")
    ),
)

combo_counts = Counter(
    (r.get("swstr_pct"), r.get("career_swstr_pct"), r.get("swstr_delta_k9"))
    for r in rows
)
print("top stored combos:")
for combo, count in combo_counts.most_common(10):
    print(f"  {count:>4}  {combo}")

sys.path.insert(0, str(ROOT / "pipeline"))
from fetch_statcast import fetch_swstr  # noqa: E402

sample_pitchers = sorted({r["pitcher"] for r in rows if r.get("pitcher")})[:10]
if not sample_pitchers:
    print("No pitchers found in picks_history sample; stopping.")
    raise SystemExit(0)

probe_season = max(r["_parsed_date"].year for r in rows)

print("\n=== Live fetch_swstr() sample ===")
print("season:", probe_season)
print("pitchers:", sample_pitchers)
result = fetch_swstr(probe_season, sample_pitchers)
for name in sample_pitchers:
    print(name, "->", result.get(name))
