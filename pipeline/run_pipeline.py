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
_SWSTR_NEUTRAL = {"swstr_pct": LEAGUE_AVG_SWSTR, "career_swstr_pct": None}
from fetch_umpires   import fetch_umpires
from build_features  import build_pitcher_record

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

OUTPUT_PATH   = Path(__file__).parent.parent / "dashboard" / "data" / "processed" / "today.json"
PREVIEW_PATH  = Path(__file__).parent.parent / "data" / "preview_lines.json"


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


def _run_preview(tomorrow_str: str) -> None:
    """7pm run: fetch next-day lines and store to preview_lines.json.
    Does not seed picks to the DB — the 6am run treats these as opening lines
    so any sharp movement overnight is captured by the movement confidence haircut."""
    log.info("=== Preview run: fetching lines for %s ===", tomorrow_str)
    try:
        props = fetch_odds(tomorrow_str)
    except Exception as e:
        log.error("fetch_odds failed in preview run: %s", e)
        return

    if not props:
        log.warning("No K props posted yet for %s — preview skipped", tomorrow_str)
        return

    preview = {
        "date":       tomorrow_str,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "lines": {
            p["pitcher"]: {
                "k_line":     p["k_line"],
                "over_odds":  p["best_over_odds"],
                "under_odds": p["best_under_odds"],
            }
            for p in props
        },
    }
    PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PREVIEW_PATH, "w") as f:
        json.dump(preview, f, indent=2)
    log.info("Preview: stored %d pitcher lines for %s", len(preview["lines"]), tomorrow_str)


def _load_preview_lines(date_str: str) -> dict:
    """Load 7pm preview lines if they exist and match today's date.
    Returns {pitcher_name: {k_line, over_odds, under_odds}} or empty dict."""
    try:
        with open(PREVIEW_PATH) as f:
            preview = json.load(f)
        if preview.get("date") == date_str:
            lines = preview.get("lines", {})
            log.info("Loaded %d preview lines from 7pm run (%s)", len(lines), preview.get("fetched_at", ""))
            return lines
        log.info("Preview file is for %s, not %s — ignoring", preview.get("date"), date_str)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {}


def _apply_preview_openings(props: list, preview_lines: dict) -> None:
    """Override opening odds with 7pm preview lines where available and the
    k_line hasn't shifted. This lets the movement confidence haircut detect
    sharp action that came in between the 7pm and 6am runs."""
    applied = 0
    for prop in props:
        name = prop["pitcher"]
        prev = preview_lines.get(name)
        if not prev:
            continue
        # Only apply if the line itself hasn't moved — a shifted k_line means
        # the market repriced completely and the old opening is misleading.
        if prev.get("k_line") != prop.get("k_line"):
            log.info("Line shifted for %s (preview %.1f → now %.1f) — skipping opening override",
                     name, prev.get("k_line"), prop.get("k_line"))
            continue
        prop["opening_over_odds"]  = prev["over_odds"]
        prop["opening_under_odds"] = prev["under_odds"]
        applied += 1
    log.info("Applied 7pm preview openings to %d/%d pitchers", applied, len(props))


def _run_grading_steps() -> None:
    """Run result fetching and calibration. Called for evening and grading-only runs."""
    log.info("=== Grading steps: fetch_results + calibrate ===")
    try:
        from fetch_results import run as run_results
        run_results()
    except Exception as e:
        log.error("fetch_results failed: %s", e)
    try:
        from calibrate import run as run_calibrate
        run_calibrate()
    except Exception as e:
        log.error("calibrate failed: %s", e)


def _has_valid_output(date_str: str) -> bool:
    """Return True if today.json already has valid props for date_str. Prevents a
    failed/empty API call from overwriting a good earlier run's output."""
    try:
        with open(OUTPUT_PATH) as f:
            existing = json.load(f)
        return (existing.get("date") == date_str
                and existing.get("props_available") is True
                and len(existing.get("pitchers", [])) > 0)
    except Exception:
        return False


def run(date_str: str, run_type: str = "full") -> None:
    log.info("=== Pipeline start for %s (run_type=%s) ===", date_str, run_type)

    if run_type == "grading":
        log.info("Grading-only run — skipping odds/stats pipeline")
        _run_grading_steps()
        return

    if run_type == "preview":
        _run_preview(date_str)
        return

    # Full run: load 7pm preview lines to use as opening baseline for movement detection
    preview_lines = _load_preview_lines(date_str)

    # 1. Fetch odds (TheRundown)
    try:
        props = fetch_odds(date_str)
    except EnvironmentError as e:
        log.error("Environment error: %s", e)
        sys.exit(1)
    except Exception as e:
        log.error("fetch_odds failed: %s", e)
        if not _has_valid_output(date_str):
            _write_output(date_str, [], props_available=False)
        return

    if not props:
        log.warning("No K props returned — props may not be posted yet")
        if not _has_valid_output(date_str):
            _write_output(date_str, [], props_available=False)
        return

    # Overlay 7pm preview lines as opening odds so movement between 7pm and
    # 6am is captured by the movement confidence haircut in build_features.
    if preview_lines:
        _apply_preview_openings(props, preview_lines)

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
    # Returns {name: {"swstr_pct": float, "career_swstr_pct": float | None}}
    try:
        swstr_map = fetch_swstr(int(date_str[:4]), pitcher_names)
    except Exception as e:
        log.warning("fetch_swstr failed: %s — using neutral SwStr%% for all", e)
        swstr_map = {name: _SWSTR_NEUTRAL for name in pitcher_names}

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
                swstr_data=swstr_map.get(name, _SWSTR_NEUTRAL)
            )
            records.append(record)
            log.info("Built record for %s: λ=%.2f verdict=%s",
                     name, record["lambda"], record["ev_over"]["verdict"])
        except Exception as e:
            log.warning("build_pitcher_record failed for %s: %s — skipping", name, e)

    log.info("Built %d/%d pitcher records", len(records), len(props))
    _write_output(date_str, records, props_available=True)

    # Seed picks at every run so the first-seen line (earliest in the day) is locked in.
    # INSERT OR IGNORE in seed_picks means subsequent runs never overwrite the initial line.
    # Immediately export to history (including open picks) so they survive the next
    # ephemeral GitHub Actions runner — without this, open picks would be lost between runs.
    # Must init DB and load history first so export doesn't overwrite historical closed picks.
    try:
        from fetch_results import init_db, load_history_into_db, seed_picks, export_db_to_history
        init_db()
        load_history_into_db()
        seeded = seed_picks()
        log.info("Seeded %d new picks from today.json", seeded)
        if seeded > 0:
            export_db_to_history()
            log.info("Persisted open picks to history")
    except Exception as e:
        log.warning("seed_picks failed: %s", e)

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

    # 1b. Re-write today.json with ONLY ET-today pitchers (strip out any
    #     tomorrow games the API returned alongside today's slate).
    today_pitchers = buckets.get(run_date_str, [])
    today_output = {**output, "date": run_date_str, "pitchers": today_pitchers}
    try:
        with open(OUTPUT_PATH, "w") as f:
            json.dump(today_output, f, indent=2)
        log.info("Re-wrote today.json with %d ET-today pitchers (stripped %d other-date)",
                 len(today_pitchers), len(output.get("pitchers", [])) - len(today_pitchers))
    except Exception as e:
        log.warning("Failed to re-write today.json: %s", e)

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
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("date", nargs="?",
                        default=datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d"),
                        help="Game date YYYY-MM-DD")
    parser.add_argument("--run-type", choices=["full", "grading", "preview"], default="full",
                        help="'grading' grades previous day + calibrates; 'preview' fetches next-day lines without seeding picks")
    args = parser.parse_args()
    run(args.date, run_type=args.run_type)
