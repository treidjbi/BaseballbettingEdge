"""Diagnose opening_*_odds null pattern."""
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
HIST = ROOT / "data" / "picks_history.json"
if not HIST.exists():  # global policy P2
    print(f"ERROR: {HIST} not found. Run the pipeline at least once to generate it.")
    raise SystemExit(1)
picks = json.loads(HIST.read_text())

# Split by population status (use `is not None` — 0 is a legal numeric but not a legal American odds value)
def _set(p, k): return p.get(k) is not None
has_both    = [p for p in picks if _set(p, "opening_over_odds") and _set(p, "opening_under_odds")]
has_neither = [p for p in picks if not _set(p, "opening_over_odds") and not _set(p, "opening_under_odds")]
partial     = [p for p in picks if _set(p, "opening_over_odds") != _set(p, "opening_under_odds")]

print(f"Total: {len(picks)}")
print(f"  Both opening odds set: {len(has_both)}")
print(f"  Neither:               {len(has_neither)}")
print(f"  Partial (one, not other): {len(partial)}")

print("\nPopulated-vs-null by date:")
dates = sorted({p["date"] for p in picks if p.get("date")})
for d in dates:
    day = [p for p in picks if p.get("date") == d]
    pop = sum(1 for p in day if p.get("opening_over_odds") is not None)
    print(f"  {d}  populated={pop}/{len(day)}")

print("\nPopulated-vs-null by fetched_at hour (UTC):")
by_hour = Counter()
pop_by_hour = Counter()
for p in picks:
    ts = p.get("fetched_at", "") or ""
    hour = ts[11:13] if len(ts) >= 13 else "??"
    by_hour[hour] += 1
    if p.get("opening_over_odds") is not None:
        pop_by_hour[hour] += 1
for h in sorted(by_hour):
    print(f"  {h}  populated={pop_by_hour[h]}/{by_hour[h]}")

# Partition null-opening picks by whether best_*_odds are also null.
# If ALL null-opening rows also have null best_*_odds, they are pre-column-migration
# legacy rows (the `best_*_odds` / `opening_*_odds` columns were added mid-season
# via ALTER TABLE ADD COLUMN, which backfills NULL, and those rows were already
# locked/graded by the time the migration ran, so the UPDATE path in seed_picks
# never got a chance to fill them).
null_op = [p for p in picks if p.get("opening_over_odds") is None]
null_op_best_null = [p for p in null_op if p.get("best_over_odds") is None and p.get("best_under_odds") is None]
null_op_best_set  = [p for p in null_op if p.get("best_over_odds") is not None or p.get("best_under_odds") is not None]
print(f"\nNull-opening partition:")
print(f"  null opening AND null best (pre-migration legacy):   {len(null_op_best_null)}")
print(f"  null opening BUT best set (real live-code bug, if >0): {len(null_op_best_set)}")

# Post-migration subset: picks where best_*_odds is populated (i.e., rows that
# were live under the current schema). This is the ONLY cohort that can expose
# a current-code bug in opening-odds propagation.
post_mig = [p for p in picks if p.get("best_over_odds") is not None]
post_mig_pop = [p for p in post_mig if p.get("opening_over_odds") is not None]
print(f"\nPost-migration cohort (best_over_odds set): {len(post_mig)}")
print(f"  opening populated: {len(post_mig_pop)}/{len(post_mig)}")


# Root cause (A2.3):
# The 306 null-opening rows are ALL legacy pre-column-migration picks — every
# one of them also has `best_over_odds=None` and `best_under_odds=None`, which
# is only possible for rows seeded before commits cd67d83 / 7bf6c95 / 1b71882
# (late March 2026) added the `best_*_odds` and `opening_*_odds` columns to
# pipeline/fetch_results.py:92-118 via ALTER TABLE ADD COLUMN. SQLite backfills
# NULL on those migrations, and by the time the migration ran those picks were
# already graded (result IS NOT NULL), so the `seed_picks` UPDATE path at
# pipeline/fetch_results.py:183-210 — which only targets `locked_at IS NULL AND
# result IS NULL` — never touched them. On the 141-pick post-migration cohort,
# opening odds are populated 141/141 (100%) and movement_conf != 1.0 fires on
# 13/141 (9.2%), so movement_conf is NOT silently dormant on live code; the
# appearance of dormancy in the Phase-A analysis was an artifact of counting
# against the full 447-row history (306 legacy NULLs dilute the denominator).
# The production code paths (fetch_odds.py:181-196 always computes opening from
# price_delta; run_pipeline.py:324-343 overrides from preview_lines when line
# unchanged; fetch_results.py:142-174 INSERT captures it, UPDATE preserves it
# via COALESCE) are correct.
#
# One residual gap remains but it is a different bug: when `run_pipeline._apply_preview_openings`
# (pipeline/run_pipeline.py:324-343) skips preview override because `prev["k_line"] != prop["k_line"]`
# (line shifted overnight), the opening falls back to fetch_odds's `best - price_delta`, which
# is a within-day opening (start of current trading day), not the overnight 7pm baseline.
# That is a spec question (which opening should we compare to?), not a null-bug, and is out of
# scope for A2.
#
# A2.4 target: tests/test_fetch_results.py — mirror the existing `TestSeedPicks`
# fixture pattern (search for `def test_seed_picks_inserts_new_pick` and the
# `_make_today_json` helper). Add a failing test `test_seed_picks_update_preserves_opening_odds`
# that (1) inserts a pick with opening_over_odds=-110, (2) calls seed_picks again
# with today.json showing opening_over_odds=None (simulating a mid-day refresh
# where fetch_odds returned delta=0 so opening==best and equals best, or a preview-only
# scenario), (3) asserts the DB row's opening_over_odds is still -110 (COALESCE
# preserved it). The current code SHOULD pass this test — it's a regression guard,
# not a bug-exposing test. If Phase A wants a bug-exposing test, the target is
# the `prev["k_line"] != prop["k_line"]` branch in _apply_preview_openings (but
# see note above — this is a spec/design question, not a defect).

