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
from fetch_umpires      import fetch_umpires
from fetch_lineups      import fetch_lineups
from fetch_batter_stats import fetch_batter_stats
from build_features     import build_pitcher_record
from name_utils         import normalize as _normalize_name
from fetch_results      import (init_db, load_history_into_db, seed_picks,
                                export_db_to_history, lock_due_picks, get_db)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

OUTPUT_PATH    = Path(__file__).parent.parent / "dashboard" / "data" / "processed" / "today.json"
STEAM_PATH     = Path(__file__).parent.parent / "dashboard" / "data" / "processed" / "steam.json"
HISTORY_PATH   = Path(__file__).parent.parent / "data" / "picks_history.json"

_batter_stats_cache: dict | None = None


def fetch_batter_stats_cached(season: int) -> dict:
    global _batter_stats_cache
    if _batter_stats_cache is None:
        try:
            _batter_stats_cache = fetch_batter_stats(season)
        except Exception as e:
            log.warning("fetch_batter_stats failed: %s — using empty dict", e)
            _batter_stats_cache = {}
    return _batter_stats_cache


def fetch_lineups_for_pitcher(date_str: str, team: str) -> list[dict] | None:
    try:
        return fetch_lineups(date_str, team)
    except Exception as e:
        log.warning("fetch_lineups failed for %s: %s", team, e)
        return None
PREVIEW_PATH  = Path(__file__).parent.parent / "data" / "preview_lines.json"


def _merge_with_locked_snapshots(fresh_records: list, date_str: str, now: datetime) -> list:
    """
    For games that have already started, preserve the last pre-game snapshot from
    the existing today.json instead of overwriting with fresh (post-start) data.

    Rules:
    - Started pitchers (game_time <= now) in existing today.json → carry snapshot forward
    - Upcoming pitchers (game_time > now) → use fresh data from current run
    - New pitchers not seen in any prior run today whose game has already started → suppress
    """
    try:
        with open(OUTPUT_PATH) as f:
            existing = json.load(f)
        if existing.get("date") != date_str:
            return fresh_records  # Different date — no snapshots to preserve
        existing_pitchers: dict[str, dict] = {
            p["pitcher"]: p for p in existing.get("pitchers", [])
        }
    except Exception:
        return fresh_records  # No existing file yet — nothing to preserve

    # Identify which existing pitchers' games have already started
    started_names: set[str] = set()
    for name, p in existing_pitchers.items():
        game_time_str = p.get("game_time")
        if not game_time_str:
            continue
        try:
            game_time = datetime.fromisoformat(game_time_str.replace("Z", "+00:00"))
            if now >= game_time:
                started_names.add(name)
        except (ValueError, TypeError) as e:
            # Don't silently swallow: if game_time is malformed the pick is stuck
            # in "not started" forever and carries stale data across runs.
            log.warning("Unparseable game_time %r for %s: %s — treating as not started",
                        game_time_str, name, e)

    result: list = []
    fresh_names: set[str] = {r["pitcher"] for r in fresh_records}

    # Preserve locked snapshots for started games (carry exact pre-game data forward)
    for name in started_names:
        result.append(existing_pitchers[name])

    # Add fresh records for upcoming games only
    for r in fresh_records:
        name = r["pitcher"]
        if name in started_names:
            continue  # Game started — use locked snapshot (already added above)
        if name in existing_pitchers:
            # Known pitcher, game not yet started — use fresh data
            result.append(r)
        else:
            # New pitcher not seen in any prior run today.
            # If their game has already started, suppress them to avoid confusion.
            game_time_str = r.get("game_time")
            is_started = False
            if game_time_str:
                try:
                    gt = datetime.fromisoformat(game_time_str.replace("Z", "+00:00"))
                    is_started = now >= gt
                except Exception:
                    pass
            if not is_started:
                result.append(r)

    # Carry forward existing upcoming picks that the current odds batch is missing.
    # TheRundown removes props 20-30 min before first pitch, so a run close to
    # game time may return fewer pitchers than were present earlier in the day.
    # Without this, a manual refresh near game time would wipe valid earlier picks.
    for name, p in existing_pitchers.items():
        if name in started_names or name in fresh_names:
            continue  # Already handled above
        game_time_str = p.get("game_time")
        if not game_time_str:
            continue
        try:
            gt = datetime.fromisoformat(game_time_str.replace("Z", "+00:00"))
            if now < gt:  # Game hasn't started — preserve the pick
                result.append(p)
        except Exception:
            pass

    return result


def _annotate_game_states(records: list, now: datetime) -> None:
    """
    Add/update the `game_state` field on every record based on current time.
    Values: 'pregame' | 'in_progress' | 'final'
    Final is approximated as 4 hours after scheduled game time.
    Called after merging so locked snapshots get their state refreshed correctly.
    """
    for r in records:
        game_time_str = r.get("game_time")
        if not game_time_str:
            r["game_state"] = "pregame"
            continue
        try:
            game_time = datetime.fromisoformat(game_time_str.replace("Z", "+00:00"))
            elapsed = (now - game_time).total_seconds()
            if elapsed < 0:
                r["game_state"] = "pregame"
            elif elapsed < 4 * 3600:
                r["game_state"] = "in_progress"
            else:
                r["game_state"] = "final"
        except Exception:
            r["game_state"] = "pregame"


def _restamp_starter_mismatch(records: list, probables_by_team: dict) -> None:
    """A7 post-merge re-stamp: flag `starter_mismatch` on every record (fresh
    AND locked) whenever MLB's current probablePitcher for the record's team
    disagrees with the odds pitcher name we have on file.

    Rationale: `build_pitcher_record` sets `starter_mismatch` at build time
    using `stats["probable_name"]`, but fetch_stats's name-filter drops
    entries entirely when the TheRundown pitcher doesn't match MLB's probable
    — so freshly-built records can't see that divergence. Locked snapshots
    from an earlier pre-swap run carry a stale `starter_mismatch=False` until
    re-stamped. This helper is the single authority for both cases.

    Safe default: when probables_by_team has no entry for a record's team
    (e.g. early preview where MLB's probable is `null`, or team-name mismatch),
    leave the existing flag alone rather than false-positive-clearing it.
    """
    if not probables_by_team:
        return
    for r in records:
        team = r.get("team")
        if not team or team not in probables_by_team:
            continue
        probable = probables_by_team.get(team)
        if not probable:
            # MLB hasn't posted a probable yet for this team — don't flag.
            continue
        r["starter_mismatch"] = (
            _normalize_name(probable) != _normalize_name(r.get("pitcher", ""))
        )


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


def _write_dated_archive_only(records: list, date_str: str, props_available: bool) -> None:
    """Write a dated archive file for date_str without touching today.json.
    Used by the preview run so the dashboard shows tomorrow's lines before the 6am run."""
    base_dir = OUTPUT_PATH.parent
    base_dir.mkdir(parents=True, exist_ok=True)
    output = {
        "generated_at":    datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date":            date_str,
        "props_available": props_available,
        "pitchers":        records,
    }
    dated_path = base_dir / f"{date_str}.json"
    try:
        with open(dated_path, "w") as f:
            json.dump(output, f, indent=2)
        log.info("Wrote preview archive: %s (%d pitchers)", dated_path, len(records))
    except Exception as e:
        log.warning("Failed to write preview archive %s: %s", dated_path, e)
        return

    # Rebuild index so the date shows up in the dashboard's date selector
    index_path = base_dir / "index.json"
    all_dates = sorted(
        {p.stem for p in base_dir.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].json")},
        reverse=True,
    )[:60]
    results_by_date = _date_results_from_history()
    date_entries = [{"date": d, **results_by_date.get(d, {"wins": 0, "losses": 0})} for d in all_dates]
    try:
        with open(index_path, "w") as f:
            json.dump({"dates": date_entries}, f, indent=2)
        log.info("Updated index.json for preview (%d entries)", len(all_dates))
    except Exception as e:
        log.warning("Failed to write index.json: %s", e)


def _run_preview(tomorrow_str: str) -> None:
    """7pm run: fetch next-day lines, store to preview_lines.json, and write a full
    set of pitcher records to the dated dashboard archive so the dashboard shows
    tomorrow's lines starting from the 7pm snapshot.

    Pick seeding is intentionally skipped — the 6am full run seeds picks and applies
    these 7pm lines as opening odds for overnight movement detection."""
    log.info("=== Preview run: fetching lines for %s ===", tomorrow_str)
    try:
        props = fetch_odds(tomorrow_str)
    except Exception as e:
        log.error("fetch_odds failed in preview run: %s", e)
        return

    if not props:
        log.warning("No K props posted yet for %s — preview skipped", tomorrow_str)
        return

    # 1. Save opening-baseline snapshot used by tomorrow's 6am full run
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

    # 2. Build full pitcher records for tomorrow so the dashboard shows them tonight.
    #    The 6am full run will overwrite this archive with fresher data and will apply
    #    the 7pm preview lines above as opening odds for movement detection.
    pitcher_names = [p["pitcher"] for p in props]

    try:
        stats_map, probables_by_team = fetch_stats(tomorrow_str, pitcher_names)
    except Exception as e:
        log.error("Preview: fetch_stats failed: %s — writing props-only archive", e)
        _write_dated_archive_only([], tomorrow_str, props_available=True)
        return

    try:
        swstr_map = fetch_swstr(int(tomorrow_str[:4]), pitcher_names)
        swstr_map.pop("__meta__", None)
    except Exception as e:
        log.warning("Preview: fetch_swstr failed: %s — using neutral SwStr%%", e)
        swstr_map = {name: _SWSTR_NEUTRAL for name in pitcher_names}

    try:
        ump_map, _ump_diag = fetch_umpires(props, tomorrow_str)
    except Exception as e:
        log.warning("Preview: fetch_umpires failed: %s — using neutral adj", e)
        ump_map = {p["pitcher"]: 0.0 for p in props}

    batter_stats = fetch_batter_stats_cached(int(tomorrow_str[:4]))

    records = []
    for odds in props:
        name  = odds["pitcher"]
        stats = stats_map.get(name)
        if not stats:
            log.warning("Preview: no stats for %s — skipping", name)
            continue
        try:
            lineup = fetch_lineups_for_pitcher(tomorrow_str, stats.get("team", ""))
            record = build_pitcher_record(
                odds, stats, ump_map.get(name, 0.0),
                swstr_data=swstr_map.get(name, _SWSTR_NEUTRAL),
                lineup=lineup,
                batter_stats=batter_stats if lineup else None,
            )
            records.append(record)
            log.info("Preview: built record for %s: λ=%.2f verdict=%s",
                     name, record["lambda"], record["ev_over"]["verdict"])
        except Exception as e:
            log.warning("Preview: build_pitcher_record failed for %s: %s — skipping", name, e)

    now_utc = datetime.now(timezone.utc)
    _annotate_game_states(records, now_utc)
    _write_dated_archive_only(records, tomorrow_str, props_available=True)
    log.info("Preview: wrote %d/%d pitcher records for %s", len(records), len(props), tomorrow_str)


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
        # Promote source so calc_movement_confidence trusts this as a true
        # overnight baseline. On skip paths above (no match / k_line shift),
        # source stays whatever fetch_odds tagged ("first_seen"), which gates
        # movement_conf to a no-op haircut.
        prop["opening_odds_source"] = "preview"
        applied += 1
    log.info("Applied 7pm preview openings to %d/%d pitchers", applied, len(props))


def _import_fetch_results_run():
    from fetch_results import run as _r
    return _r

def _import_calibrate_run():
    from calibrate import run as _r
    return _r

# Module-level aliases used for patching in tests
def fetch_results_run():
    _import_fetch_results_run()()

def calibrate_run():
    _import_calibrate_run()()


def _run_lock_only(date_str: str) -> None:
    """Lock picks within T-30min of game time. No odds/stats fetch."""
    log.info("=== Lock-only run for %s ===", date_str)
    try:
        init_db()
        load_history_into_db()
        conn = get_db()
        try:
            locked = lock_due_picks(conn, datetime.now(timezone.utc), lock_all_past=False)
        finally:
            conn.close()
        if locked > 0:
            export_db_to_history()
            log.info("Lock-only: locked %d picks", locked)
        else:
            log.info("Lock-only: no picks due for locking yet")
    except Exception as e:
        log.error("Lock-only run failed: %s", e)


def _write_steam(pitchers: list, run_date_str: str) -> None:
    """Append a per-book odds snapshot to steam.json. Resets on a new day.

    Only pitchers that have book_odds data (at least one tracked book) are
    included in each snapshot. Called on full/refresh runs only — not during
    preview or grading runs where live odds aren't being re-fetched.
    """
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    existing: dict = {}
    try:
        with open(STEAM_PATH) as f:
            existing = json.load(f)
    except Exception:
        pass

    if existing.get("date") != run_date_str:
        existing = {"date": run_date_str, "snapshots": []}

    pitcher_snap: dict = {}
    for p in pitchers:
        book_odds = p.get("book_odds")
        if not book_odds:
            continue
        pitcher_snap[p["pitcher"]] = {"k_line": p.get("k_line"), **book_odds}

    if pitcher_snap:
        existing["snapshots"].append({"t": now_iso, "pitchers": pitcher_snap})

    existing["updated_at"] = now_iso

    try:
        STEAM_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(STEAM_PATH, "w") as f:
            json.dump(existing, f, indent=2)
        log.info("Wrote steam.json (%d snapshot(s), %d pitcher(s))",
                 len(existing["snapshots"]), len(pitcher_snap))
    except Exception as e:
        log.warning("Failed to write steam.json: %s", e)


def _verdict_stake(verdict) -> float:
    """Units staked for a verdict string. LEAN = 0 (tracked, not staked)."""
    if verdict and "2u" in verdict:
        return 2.0
    if verdict and ("1u" in verdict or verdict.startswith("FIRE")):
        return 1.0
    return 0.0


def _build_result_obj(pick) -> dict:
    """Build the v2 result object from a pick row (sqlite3.Row or dict)."""
    v = pick["locked_verdict"] or pick["verdict"]
    units_risked = _verdict_stake(v)
    pnl = pick["pnl"] if pick["pnl"] is not None else 0.0
    line_at_bet = pick["locked_k_line"] if pick["locked_k_line"] is not None else pick["k_line"]
    odds_at_bet = pick["locked_odds"] if pick["locked_odds"] is not None else pick["odds"]
    return {
        "final_k": pick["actual_ks"],
        "side_taken": pick["side"],
        "line_at_bet": line_at_bet,
        "odds_at_bet": odds_at_bet,
        "outcome": pick["result"],
        "units_won": round(pnl * units_risked, 4),
        "units_risked": units_risked,
    }


def _enrich_archives_with_results() -> None:
    """Inject grading results into dated archive files so the dashboard can
    display W/L on past dates and v2 can render the FINAL state detail sheet."""
    try:
        conn = get_db()
        try:
            rows = conn.execute("""
                SELECT date, pitcher, side, result, actual_ks,
                       locked_k_line, k_line, locked_odds, odds,
                       locked_verdict, verdict, pnl
                FROM picks
                WHERE result IN ('win', 'loss', 'push')
            """).fetchall()
        finally:
            conn.close()
    except Exception as e:
        log.warning("_enrich_archives_with_results: DB read failed: %s", e)
        return

    if not rows:
        return

    by_date: dict[str, list] = {}
    for row in rows:
        by_date.setdefault(row["date"], []).append(row)

    base_dir = OUTPUT_PATH.parent
    enriched = 0
    for date_str, picks in by_date.items():
        archive_path = base_dir / f"{date_str}.json"
        if not archive_path.exists():
            continue

        try:
            with open(archive_path) as f:
                archive = json.load(f)
        except Exception:
            continue

        lookup: dict[str, dict] = {}
        for pick in picks:
            lookup.setdefault(pick["pitcher"], {})[pick["side"]] = pick

        modified = False
        for p in archive.get("pitchers", []):
            name = p["pitcher"]
            if name not in lookup:
                continue

            pick_data = lookup[name]
            any_pick = next(iter(pick_data.values()))
            if any_pick["actual_ks"] is not None:
                p["actual_ks"] = any_pick["actual_ks"]
                modified = True

            for side_key in ("over", "under"):
                if side_key in pick_data and pick_data[side_key]["result"]:
                    ev_key = f"ev_{side_key}"
                    if ev_key in p:
                        p[ev_key]["result"] = pick_data[side_key]["result"]
                        modified = True

            # Embed top-level result object for v2 FINAL state detail sheet.
            # Primary pick = highest-staked; ties broken by wins over losses.
            primary = max(
                pick_data.values(),
                key=lambda pk: (
                    _verdict_stake(pk["locked_verdict"] or pk["verdict"]),
                    pk["result"] == "win",
                ),
            )
            p["result"] = _build_result_obj(primary)
            modified = True

        if modified:
            try:
                with open(archive_path, "w") as f:
                    json.dump(archive, f, indent=2)
                enriched += 1
            except Exception as e:
                log.warning("Failed to enrich archive %s: %s", date_str, e)

    if enriched:
        log.info("Enriched %d archive(s) with grading results", enriched)


def backfill_result_embeds() -> int:
    """Backfill result objects into historical archive files from picks_history.json.

    Reads directly from picks_history.json (no DB required) so it can be run
    standalone to update archives without waiting for the next grading run.
    Safe to re-run — overwrites the result key only on pitchers with graded picks.
    """
    try:
        with open(HISTORY_PATH) as f:
            picks = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError) as e:
        log.warning("backfill_result_embeds: could not read picks_history.json: %s", e)
        return 0

    by_date: dict[str, dict] = {}
    for p in picks:
        if p.get("result") not in ("win", "loss", "push"):
            continue
        date, pitcher, side = p.get("date"), p.get("pitcher"), p.get("side")
        if not all([date, pitcher, side]):
            continue
        by_date.setdefault(date, {}).setdefault(pitcher, {})[side] = p

    base_dir = OUTPUT_PATH.parent
    enriched = 0
    for date_str, pitcher_picks in by_date.items():
        archive_path = base_dir / f"{date_str}.json"
        if not archive_path.exists():
            continue
        try:
            with open(archive_path) as f:
                archive = json.load(f)
        except Exception:
            continue

        modified = False
        for p in archive.get("pitchers", []):
            name = p["pitcher"]
            if name not in pitcher_picks:
                continue
            pick_data = pitcher_picks[name]

            any_pick = next(iter(pick_data.values()))
            if any_pick.get("actual_ks") is not None:
                p["actual_ks"] = any_pick["actual_ks"]

            for side_key, pick in pick_data.items():
                ev_key = f"ev_{side_key}"
                if ev_key in p and pick.get("result"):
                    p[ev_key]["result"] = pick["result"]

            primary = max(
                pick_data.values(),
                key=lambda pk: (
                    _verdict_stake(pk.get("locked_verdict") or pk.get("verdict")),
                    pk.get("result") == "win",
                ),
            )
            p["result"] = _build_result_obj(primary)
            modified = True

        if modified:
            try:
                with open(archive_path, "w") as f:
                    json.dump(archive, f, indent=2)
                enriched += 1
            except Exception as e:
                log.warning("backfill_result_embeds: failed to write %s: %s", archive_path, e)

    log.info("backfill_result_embeds: updated %d archive(s)", enriched)
    return enriched


def _run_grading_steps() -> None:
    """Run result fetching and calibration. Called for evening and grading-only runs."""
    log.info("=== Grading steps: fetch_results + calibrate ===")

    # Lock all open picks before grading so we grade with final lines
    try:
        conn = get_db()
        try:
            locked = lock_due_picks(conn, datetime.now(timezone.utc), lock_all_past=True)
        finally:
            conn.close()
        if locked > 0:
            export_db_to_history()
            log.info("Pre-grading lock: locked %d picks", locked)
    except Exception as e:
        log.warning("lock_due_picks in grading run failed: %s", e)

    try:
        fetch_results_run()
    except Exception as e:
        log.error("fetch_results failed: %s", e)
    try:
        _enrich_archives_with_results()
    except Exception as e:
        log.warning("Archive enrichment failed: %s", e)
    try:
        calibrate_run()
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

    if run_type == "lock":
        _run_lock_only(date_str)
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
        stats_map, probables_by_team = fetch_stats(date_str, pitcher_names)
    except Exception as e:
        # Stats API down: continue with empty map so per-pitcher isolation still runs.
        # Pitchers with no stats are skipped individually; props_available stays True.
        log.error("fetch_stats failed entirely: %s — all pitchers will be skipped", e)
        stats_map = {}
        probables_by_team = {}

    # 3. Fetch SwStr% (FanGraphs via PyBaseball — graceful fallback to neutral)
    # Returns {name: {"swstr_pct": float, "career_swstr_pct": float | None}}
    swstr_ok = True
    try:
        swstr_map = fetch_swstr(int(date_str[:4]), pitcher_names)
        swstr_meta = swstr_map.pop("__meta__", {})
        swstr_ok = bool(swstr_meta.get("current_usable", True) and swstr_meta.get("career_usable", True))
    except Exception as e:
        log.warning("fetch_swstr failed: %s — using neutral SwStr%% for all", e)
        swstr_map = {name: _SWSTR_NEUTRAL for name in pitcher_names}
        swstr_ok = False

    # 4. Fetch umpire adjustments (MLB Stats API officials hydrate — graceful fallback built in)
    # Source (2026-04-17 cutover): statsapi.mlb.com /schedule?hydrate=officials
    # replaces the dead ump.news scrape. Pre-game on game-day, officials often
    # aren't posted yet — that returns an empty map and the 30-min refresh loop
    # picks them up before T-30 lock. See pipeline/fetch_umpires.py for details.
    #
    # Backfill team/opp_team onto props from stats_map BEFORE fetch_umpires runs.
    # fetch_odds leaves these as empty strings because TheRundown's participant
    # list has no per-pitcher home/away flag (commit 79bf3dc, 2026-04-01 —
    # "resolve team/opp_team from MLB schedule instead of odds API"). fetch_stats
    # resolves them via the MLB schedule side loop. Without this backfill,
    # fetch_umpires team-matches on empty strings and every pitcher silently
    # hits ump_k_adj=0.0 — dead-signal window 2026-04-01 → 2026-04-23 (601/601
    # stored picks had ump_k_adj=0; see docs/data-caveats.md + re-audit finding
    # in docs/superpowers/plans/2026-04-16-model-audit-and-gaps.md, Task A3.7).
    for prop in props:
        s = stats_map.get(prop["pitcher"])
        if s:
            prop["team"] = s.get("team") or prop.get("team", "")
            prop["opp_team"] = s.get("opp_team") or prop.get("opp_team", "")
    try:
        ump_map, ump_diagnostics = fetch_umpires(props, date_str)
    except Exception as e:
        log.warning("fetch_umpires failed: %s — using neutral adj for all", e)
        ump_map = {p["pitcher"]: 0.0 for p in props}
        # Sentinel values so the diagnostic surfaces the "fetch_umpires blew
        # up entirely" branch distinctly from "HPs not posted yet" (0/0) and
        # "HPs posted but nothing matched" (>0/0). The error field carries
        # the exception type + message into today.json so the failure mode
        # is readable without CI log access — observed 2026-04-24 when the
        # first diagnostic run surfaced hp_count_fetched=-1 but swallowed
        # the root cause in log.warning.
        ump_diagnostics = {
            "hp_count_fetched":      -1,
            "pitcher_nonzero_count": 0,
            "error":                 f"{type(e).__name__}: {e}",
        }
    # ump_ok is True only when at least one pitcher got a real (nonzero)
    # adjustment. An empty map or all-zero map means officials weren't
    # posted yet OR none of today's HP umps are in career_k_rates.json —
    # either way, ump signal is effectively absent and data_complete should
    # reflect that going forward. Historical data_complete=True rows are
    # NOT rewritten (see docs/data-caveats.md).
    ump_ok = len(ump_map) > 0 and any(v != 0.0 for v in ump_map.values())
    log.info(
        "Ump diagnostics: hp_count_fetched=%s, pitcher_nonzero_count=%s, ump_ok=%s",
        ump_diagnostics["hp_count_fetched"],
        ump_diagnostics["pitcher_nonzero_count"],
        ump_ok,
    )

    # 5. Fetch batter stats (FanGraphs — cached, graceful fallback to {})
    batter_stats = fetch_batter_stats_cached(int(date_str[:4]))

    # 6. Build records — per-pitcher error isolation
    records = []
    for odds in props:
        name  = odds["pitcher"]
        stats = stats_map.get(name)
        if not stats:
            log.warning("No stats for %s — skipping", name)
            continue
        try:
            lineup = fetch_lineups_for_pitcher(date_str, stats.get("team", ""))
            record = build_pitcher_record(
                odds, stats, ump_map.get(name, 0.0),
                swstr_data=swstr_map.get(name, _SWSTR_NEUTRAL),
                lineup=lineup,
                batter_stats=batter_stats if lineup else None,
            )
            # Mark whether all external data APIs returned real data.
            # Picks with data_complete=False are excluded from calibration so
            # a bad-API run doesn't skew lambda_bias / ump_scale / swstr_k9_scale.
            record["data_complete"] = swstr_ok and ump_ok
            records.append(record)
            log.info("Built record for %s: λ=%.2f verdict=%s",
                     name, record["lambda"], record["ev_over"]["verdict"])
        except Exception as e:
            log.warning("build_pitcher_record failed for %s: %s — skipping", name, e)

    log.info("Built %d/%d pitcher records", len(records), len(props))

    # Preserve locked snapshots: once a game has started, freeze its card data so
    # post-game-start odds movements don't change what the dashboard displays.
    # New pitchers appearing after game start are suppressed.
    now_utc = datetime.now(timezone.utc)
    records = _merge_with_locked_snapshots(records, date_str, now_utc)
    _annotate_game_states(records, now_utc)

    # A7: phantom-starter re-stamp (post-merge). `build_pitcher_record` already
    # set `starter_mismatch` for freshly-built records using stats.probable_name,
    # but locked snapshots from earlier runs predate any swap and may now carry
    # a stale False. Re-check each record against MLB's current probable for
    # the record's team — when they differ, flag so the dashboard can warn.
    # Example: Chad Patrick / Martin Perez (2026-04-22) were seeded FIRE 2u at
    # 6am, scratched mid-day, and graded void. Void kept calibration safe;
    # this flag lets v2 hide or down-rank the card the moment MLB's probable
    # flips, rather than silently serving a dead pick to the user.
    _restamp_starter_mismatch(records, probables_by_team)

    # Guard: if the stats API failed entirely and produced 0 records, don't
    # silently wipe out a previously good today.json.  Locked snapshots from
    # _merge_with_locked_snapshots ensure started games are still present, so
    # a non-empty records list here means at least some data is valid.
    if records or not _has_valid_output(date_str):
        _write_output(date_str, records, props_available=True,
                      ump_diagnostics=ump_diagnostics)
        _write_steam(records, date_str)
    else:
        log.warning(
            "Stats pipeline returned 0 records despite %d odds entries — "
            "keeping existing today.json to avoid losing valid picks data", len(props)
        )

    # Seed picks at every run so the first-seen line (earliest in the day) is locked in.
    # INSERT OR IGNORE in seed_picks means subsequent runs never overwrite the initial line.
    # Immediately export to history (including open picks) so they survive the next
    # ephemeral GitHub Actions runner — without this, open picks would be lost between runs.
    # Must init DB and load history first so export doesn't overwrite historical closed picks.
    try:
        init_db()
        load_history_into_db()
        # Lock before seeding: picks arriving within T-30min will miss this lock window
        # but will be caught by the grading run's lock_all_past=True pass.
        conn = get_db()
        try:
            locked = lock_due_picks(conn, datetime.now(timezone.utc), lock_all_past=False)
        finally:
            conn.close()
        seeded = seed_picks()
        log.info("Seeded %d new picks, locked %d picks from today.json", seeded, locked)
        # Always export: captures newly inserted picks, intra-day odds/lineup
        # updates to unlocked picks, and freshly locked snapshots.  The git
        # commit step skips an empty commit when nothing changed, so this is
        # safe to call unconditionally and prevents a "seeded==0 && locked==0"
        # run from leaving picks_history.json stale after a runner reset.
        export_db_to_history()
        log.info("Persisted open/locked picks to history")
    except Exception as e:
        log.warning("seed_picks failed: %s", e)

    log.info("=== Pipeline complete ===")


def _write_output(date_str: str, records: list, props_available: bool,
                  ump_diagnostics: dict | None = None) -> None:
    output = {
        "generated_at":   datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "date":           date_str,
        "props_available": props_available,
        "pitchers":       records,
    }
    # Surface fetch_umpires diagnostic counts at the top level so the user can
    # tell, from today.json alone, whether a zero ump_k_adj slate is "MLB API
    # returned no officials" (hp_count_fetched==0), "fetch_umpires threw"
    # (==-1), or "we fetched assignments but matching dropped them"
    # (hp_count_fetched>0 and pitcher_nonzero_count==0). Added 2026-04-24 in
    # response to a soak-day production/local divergence. Schema is nullable
    # on read so v1/v2 dashboards remain unaffected (neither reads it).
    if ump_diagnostics is not None:
        output["ump_diagnostics"] = ump_diagnostics
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    # today.json is written exactly once inside _write_archive, filtered to
    # ET-today pitchers only.  Writing it here first (with all records including
    # possible tomorrow games) would create a brief dirty window and risk leaving
    # a mixed-date file behind if _write_archive throws before its own write.
    _write_archive(output, date_str)


def _date_results_from_history() -> dict:
    """Return {date_str: {"wins": N, "losses": N}} from picks_history.json.
    Only graded FIRE picks count (staked picks). Fails silently → empty dict."""
    try:
        with open(HISTORY_PATH) as f:
            history = json.load(f)
    except Exception:
        return {}
    by_date: dict[str, dict] = {}
    for pick in history:
        date = pick.get("date")
        result = pick.get("result")
        verdict = pick.get("verdict", "")
        if not date or result not in ("win", "loss") or not verdict.startswith("FIRE"):
            continue
        entry = by_date.setdefault(date, {"wins": 0, "losses": 0})
        if result == "win":
            entry["wins"] += 1
        else:
            entry["losses"] += 1
    return by_date


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

    # 1b. Write today.json with ONLY ET-today pitchers (strip out any
    #     tomorrow games the API returned alongside today's slate).
    #     This is the single write of today.json — _write_output intentionally
    #     skips an early write so we never have a dirty mixed-date version on disk.
    today_pitchers = buckets.get(run_date_str, [])
    today_output = {**output, "date": run_date_str, "pitchers": today_pitchers}
    try:
        with open(OUTPUT_PATH, "w") as f:
            json.dump(today_output, f, indent=2)
        log.info("Wrote today.json with %d ET-today pitchers (stripped %d other-date)",
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
    results_by_date = _date_results_from_history()
    date_entries = [{"date": d, **results_by_date.get(d, {"wins": 0, "losses": 0})} for d in all_dates]
    try:
        with open(index_path, "w") as f:
            json.dump({"dates": date_entries}, f, indent=2)
        log.info("Updated index.json (%d entries)", len(all_dates))
    except Exception as e:
        log.warning("Failed to write index.json: %s", e)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("date", nargs="?",
                        default=datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d"),
                        help="Game date YYYY-MM-DD")
    parser.add_argument("--run-type", choices=["full", "grading", "preview", "lock"], default="full",
                        help="'grading' grades previous day + calibrates; 'preview' fetches next-day lines without seeding picks")
    args = parser.parse_args()
    run(args.date, run_type=args.run_type)
