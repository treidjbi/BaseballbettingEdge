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
from zoneinfo import ZoneInfo
from pathlib import Path

# Allow running from project root or from pipeline/ directory
sys.path.insert(0, os.path.dirname(__file__))

from fetch_odds      import fetch_odds
from fetch_stats     import fetch_stats
from fetch_statcast  import fetch_swstr, LEAGUE_AVG_SWSTR
from fetch_umpires   import fetch_umpires
from build_features  import build_pitcher_record

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

OUTPUT_PATH = Path(__file__).parent.parent / "dashboard" / "data" / "processed" / "today.json"


def _game_date_et(game_time_str: str, fallback: str) -> str:
    """Convert a UTC ISO game_time string to an ET calendar date (YYYY-MM-DD).
    Falls back to `fallback` if the string is missing or unparseable."""
    if not game_time_str:
        return fallback
    try:
        dt_utc = datetime.fromisoformat(game_time_str.replace("Z", "+00:00"))
        return dt_utc.astimezone(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception as e:
        log.warning("_game_date_et: could not parse %r — falling back to %r (%s)", game_time_str, fallback, e)
        return fallback


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
        # Stats API down: continue with empty map so per-pitcher isolation still runs.
        # Pitchers with no stats are skipped individually; props_available stays True.
        log.error("fetch_stats failed entirely: %s — all pitchers will be skipped", e)
        stats_map = {}

    # 3. Fetch SwStr% (FanGraphs via PyBaseball — graceful fallback to neutral)
    try:
        swstr_map = fetch_swstr(int(date_str[:4]), pitcher_names)
    except Exception as e:
        log.warning("fetch_swstr failed: %s — using neutral SwStr%% for all", e)
        swstr_map = {name: LEAGUE_AVG_SWSTR for name in pitcher_names}

    # 4. Fetch umpire adjustments (ump.news — graceful fallback built in)
    try:
        ump_map = fetch_umpires(props)
    except Exception as e:
        log.warning("fetch_umpires failed: %s — using neutral adj for all", e)
        ump_map = {p["pitcher"]: 0.0 for p in props}

    # 5. Build records — per-pitcher error isolation
    records = []
    for odds in props:
        name  = odds["pitcher"]
        stats = stats_map.get(name)
        if not stats:
            log.warning("No stats for %s — skipping", name)
            continue
        try:
            record = build_pitcher_record(
                odds, stats, ump_map.get(name, 0.0),
                swstr_pct=swstr_map.get(name, LEAGUE_AVG_SWSTR)
            )
            records.append(record)
            log.info("Built record for %s: λ=%.2f verdict=%s",
                     name, record["lambda"], record["ev_over"]["verdict"])
        except Exception as e:
            log.warning("build_pitcher_record failed for %s: %s — skipping", name, e)

    log.info("Built %d/%d pitcher records (lambda v2: variable IP + SwStr%%)", len(records), len(props))
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

    # Archive dated copy + update index
    _write_archive(output, date_str)


def _write_archive(output: dict, run_date_str: str) -> None:
    """
    Groups pitchers by their ET game date and writes one YYYY-MM-DD.json per
    game date. Rebuilds index.json from all dated files in the directory.
    Failures are logged but do not affect today.json or crash the pipeline.
    """
    base_dir = OUTPUT_PATH.parent

    # 1. Group pitchers by ET game date
    buckets: dict[str, list] = {}
    for p in output.get("pitchers", []):
        gd = _game_date_et(p.get("game_time", ""), run_date_str)
        buckets.setdefault(gd, []).append(p)

    if not buckets:
        # No pitchers (props not yet posted or all skipped) — still write a dated
        # placeholder so this date appears in the dashboard's date selector.
        # Using run_date_str is correct here: pipeline runs after midnight ET are
        # uncommon and the date always matches the game slate date.
        buckets[run_date_str] = []

    # 2. Write one archive file per game date
    any_written = False
    for game_date, pitchers in buckets.items():
        dated_output = {**output, "date": game_date, "pitchers": pitchers}
        dated_path = base_dir / f"{game_date}.json"
        try:
            with open(dated_path, "w") as f:
                json.dump(dated_output, f, indent=2)
            log.info("Wrote archive: %s (%d pitchers)", dated_path, len(pitchers))
            any_written = True
        except Exception as e:
            log.warning("Failed to write dated archive %s: %s", dated_path, e)

    if not any_written:
        return

    # 3. Rebuild index.json from all dated files (glob for YYYY-MM-DD.json)
    index_path = base_dir / "index.json"
    all_dates = sorted(
        {p.stem for p in base_dir.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].json")},
        reverse=True
    )[:60]
    try:
        with open(index_path, "w") as f:
            json.dump({"dates": all_dates}, f, indent=2)
        log.info("Updated index.json (%d entries)", len(all_dates))
    except Exception as e:
        log.warning("Failed to write index.json: %s", e)


if __name__ == "__main__":
    date = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    run(date)
