"""
run_pipeline.py
Orchestrates: fetch_odds -> fetch_stats -> fetch_umpires -> build_features -> write today.json
Run: python pipeline/run_pipeline.py 2026-04-01
Reads RUNDOWN_API_KEY from Windows User Environment Variables (set once via sysdm.cpl).
GitHub Actions reads it from repository secrets.
"""
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow running from project root or from pipeline/ directory
sys.path.insert(0, os.path.dirname(__file__))

from fetch_odds     import fetch_odds
from fetch_stats    import fetch_stats
from fetch_umpires  import fetch_umpires
from build_features import build_pitcher_record

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "processed" / "today.json"


def run(date_str: str) -> None:
    log.info("=== Pipeline start for %s ===", date_str)

    # 1. Fetch odds (TheRundown)
    try:
        props = fetch_odds(date_str)
    except EnvironmentError as e:
        log.error("Environment error: %s", e)
        sys.exit(1)
    except Exception as e:
        log.error("fetch_odds failed: %s", e)
        _write_output(date_str, [], props_available=False)
        return

    if not props:
        log.warning("No K props returned — props may not be posted yet")
        _write_output(date_str, [], props_available=False)
        return

    # 2. Fetch stats (MLB Stats API)
    pitcher_names = [p["pitcher"] for p in props]
    try:
        stats_map = fetch_stats(date_str, pitcher_names)
    except Exception as e:
        log.error("fetch_stats failed: %s", e)
        _write_output(date_str, [], props_available=False)
        return

    # 3. Fetch umpire adjustments (ump.news — graceful fallback built in)
    try:
        ump_map = fetch_umpires(props)
    except Exception as e:
        log.warning("fetch_umpires failed: %s — using neutral adj for all", e)
        ump_map = {p["pitcher"]: 0.0 for p in props}

    # 4. Build records — per-pitcher error isolation
    records = []
    for odds in props:
        name  = odds["pitcher"]
        stats = stats_map.get(name)
        if not stats:
            log.warning("No stats for %s — skipping", name)
            continue
        try:
            record = build_pitcher_record(odds, stats, ump_map.get(name, 0.0))
            records.append(record)
            log.info("Built record for %s: λ=%.2f verdict=%s",
                     name, record["lambda"], record["ev_over"]["verdict"])
        except Exception as e:
            log.warning("build_pitcher_record failed for %s: %s — skipping", name, e)

    log.info("Built %d pitcher records out of %d props", len(records), len(props))
    _write_output(date_str, records, props_available=True)
    log.info("=== Pipeline complete ===")


def _write_output(date_str: str, records: list, props_available: bool) -> None:
    output = {
        "generated_at":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date":           date_str,
        "props_available": props_available,
        "pitchers":       records,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)
    log.info("Wrote %s (%d pitchers)", OUTPUT_PATH, len(records))


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    run(date)
