"""Shadow comparison for TheRundown vs BoltOdds + PropLine official-provider rows.

This diagnostic is analysis-only. It does not change live picks, locks,
thresholds, staking, provider order, notification sends, artifacts, or
calibration.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))

from pipeline.fetch_odds import _fetch_therundown_odds  # noqa: E402
from pipeline.fetch_provider_market_odds import (  # noqa: E402
    fetch_official_market_odds,
    official_market_writer_from_env,
)
from pipeline.fetch_stats import fetch_probable_starters  # noqa: E402
from pipeline.name_utils import normalize  # noqa: E402
from market_infra.official_market_lines import select_mainline_current_lines  # noqa: E402


OUTPUT_DIR = ROOT / "analytics" / "output"
SUPPORTED_ACTION_BOOKS = ("FanDuel", "DraftKings", "BetMGM", "BetRivers", "Caesars")
FD_DK_BOOKS = {"FanDuel", "DraftKings"}
PROPLINE_HOBBY_DAILY_REQUESTS = 5000
PROPLINE_USAGE_WARN_FRACTION = 0.70
REQUIRED_PROP_FIELDS = (
    "pitcher",
    "k_line",
    "best_over_book",
    "best_under_book",
    "best_over_odds",
    "best_under_odds",
    "opening_over_odds",
    "opening_under_odds",
    "opening_odds_source",
    "book_odds",
)


def _to_float(value: Any) -> float | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _pitcher_key(row: dict[str, Any]) -> str:
    return normalize(row.get("pitcher") or row.get("player_name") or "")


def _by_pitcher(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    keyed: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = _pitcher_key(row)
        if key:
            keyed.setdefault(key, row)
    return keyed


def _scheduled_by_pitcher(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    keyed: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = normalize(
            row.get("pitcher")
            or row.get("probable_pitcher")
            or row.get("player_name")
            or row.get("name")
            or ""
        )
        if key:
            keyed.setdefault(key, row)
    return keyed


def _book_odds(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    odds = row.get("book_odds") or {}
    return odds if isinstance(odds, dict) else {}


def _book_names(row: dict[str, Any]) -> set[str]:
    return set(_book_odds(row))


def _has_fd_or_dk(row: dict[str, Any]) -> bool:
    return bool(_book_names(row) & FD_DK_BOOKS)


def _has_book_odds(row: dict[str, Any]) -> bool:
    return bool(_book_odds(row))


def _has_line_conflict(row: dict[str, Any]) -> bool:
    reasons = row.get("provider_arbitration_reasons") or row.get("arbitration_reasons") or []
    flags = row.get("quality_flags") or []
    if isinstance(reasons, str):
        reasons = [reasons]
    if isinstance(flags, str):
        flags = [flags]
    text = {str(item) for item in [*reasons, *flags]}
    return "cross_book_line_conflict" in text or "line_conflict" in text


def _verdict(row: dict[str, Any], side: str) -> str | None:
    ev = row.get(f"ev_{side}") or {}
    if not isinstance(ev, dict):
        return None
    verdict = ev.get("verdict")
    return str(verdict) if verdict else None


def _is_fire(row: dict[str, Any]) -> bool:
    return str(_verdict(row, "over") or "").startswith("FIRE") or str(
        _verdict(row, "under") or ""
    ).startswith("FIRE")


def _gate(name: str, passed: bool | None, value: Any, threshold: Any, detail: str = "") -> dict[str, Any]:
    status = "unknown" if passed is None else ("pass" if passed else "fail")
    return {
        "name": name,
        "status": status,
        "value": value,
        "threshold": threshold,
        "detail": detail,
    }


def _rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 4)


def _odds_delta_rows(
    rundown_by_pitcher: dict[str, dict[str, Any]],
    provider_by_pitcher: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pitcher_key in sorted(set(rundown_by_pitcher) & set(provider_by_pitcher)):
        rundown = rundown_by_pitcher[pitcher_key]
        provider = provider_by_pitcher[pitcher_key]
        rundown_books = _book_odds(rundown)
        provider_books = _book_odds(provider)
        for book_name in sorted(set(rundown_books) & set(provider_books)):
            rundown_book = rundown_books.get(book_name) or {}
            provider_book = provider_books.get(book_name) or {}
            provider_line = _to_float(provider_book.get("line", provider.get("k_line")))
            rundown_line = _to_float(rundown_book.get("line", rundown.get("k_line")))
            rows.append({
                "pitcher": provider.get("pitcher") or rundown.get("pitcher"),
                "book": book_name,
                "same_line": provider_line == rundown_line,
                "rundown_line": rundown_line,
                "provider_line": provider_line,
                "over_delta": _delta(provider_book.get("over"), rundown_book.get("over")),
                "under_delta": _delta(provider_book.get("under"), rundown_book.get("under")),
                "provider": provider_book.get("provider"),
            })
    return rows


def _delta(provider_value: Any, rundown_value: Any) -> int | None:
    provider = _to_int(provider_value)
    rundown = _to_int(rundown_value)
    if provider is None or rundown is None:
        return None
    return provider - rundown


def _ref_book_changes(
    rundown_by_pitcher: dict[str, dict[str, Any]],
    provider_by_pitcher: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pitcher_key in sorted(set(rundown_by_pitcher) & set(provider_by_pitcher)):
        rundown = rundown_by_pitcher[pitcher_key]
        provider = provider_by_pitcher[pitcher_key]
        rundown_ref = rundown.get("ref_book") or rundown.get("best_over_book")
        provider_ref = provider.get("ref_book") or provider.get("best_over_book")
        if rundown_ref != provider_ref:
            rows.append({
                "pitcher": provider.get("pitcher") or rundown.get("pitcher"),
                "rundown_ref_book": rundown_ref,
                "provider_ref_book": provider_ref,
            })
    return rows


def _verdict_changes(
    rundown_by_pitcher: dict[str, dict[str, Any]],
    provider_by_pitcher: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pitcher_key in sorted(set(rundown_by_pitcher) & set(provider_by_pitcher)):
        rundown = rundown_by_pitcher[pitcher_key]
        provider = provider_by_pitcher[pitcher_key]
        for side in ("over", "under"):
            rundown_verdict = _verdict(rundown, side)
            provider_verdict = _verdict(provider, side)
            if rundown_verdict is None and provider_verdict is None:
                continue
            if rundown_verdict != provider_verdict:
                rows.append({
                    "pitcher": provider.get("pitcher") or rundown.get("pitcher"),
                    "side": side,
                    "rundown_verdict": rundown_verdict,
                    "provider_verdict": provider_verdict,
                })
    return rows


def _contract_missing_fields(row: dict[str, Any]) -> list[str]:
    missing = [field for field in REQUIRED_PROP_FIELDS if row.get(field) in (None, "")]
    if not isinstance(row.get("book_odds"), dict) or not row.get("book_odds"):
        if "book_odds" not in missing:
            missing.append("book_odds")
    return missing


def _schedule_first_coverage(
    scheduled_pitchers: list[dict[str, Any]],
    rundown_by_pitcher: dict[str, dict[str, Any]],
    provider_by_pitcher: dict[str, dict[str, Any]],
    current_line_coverage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    scheduled_by_pitcher = _scheduled_by_pitcher(scheduled_pitchers)
    scheduled_keys = set(scheduled_by_pitcher)
    provider_keys = set(provider_by_pitcher)
    rundown_keys = set(rundown_by_pitcher)
    provider_covered = scheduled_keys & provider_keys
    rundown_covered = scheduled_keys & rundown_keys
    fd_or_dk = {
        key for key in provider_covered
        if _book_names(provider_by_pitcher[key]) & FD_DK_BOOKS
    }
    draftkings = {
        key for key in provider_covered
        if "DraftKings" in _book_names(provider_by_pitcher[key])
    }
    fanduel = {
        key for key in provider_covered
        if "FanDuel" in _book_names(provider_by_pitcher[key])
    }
    book_counts = {
        key: len(_book_names(provider_by_pitcher[key]) & set(SUPPORTED_ACTION_BOOKS))
        for key in provider_covered
    }
    scheduled_count = len(scheduled_keys)
    coverage = {
        "available": bool(scheduled_pitchers),
        "scheduled_pitcher_count": scheduled_count,
        "rundown_covered_count": len(rundown_covered),
        "provider_covered_count": len(provider_covered),
        "provider_coverage_rate": _rate(len(provider_covered), scheduled_count),
        "provider_fd_or_dk_count": len(fd_or_dk),
        "provider_fd_or_dk_rate": _rate(len(fd_or_dk), scheduled_count),
        "provider_draftkings_count": len(draftkings),
        "provider_draftkings_rate": _rate(len(draftkings), scheduled_count),
        "provider_fanduel_count": len(fanduel),
        "provider_fanduel_rate": _rate(len(fanduel), scheduled_count),
        "provider_at_least_1_book_count": sum(1 for count in book_counts.values() if count >= 1),
        "provider_at_least_2_books_count": sum(1 for count in book_counts.values() if count >= 2),
        "provider_at_least_3_books_count": sum(1 for count in book_counts.values() if count >= 3),
        "zero_provider_book_count": scheduled_count - len(provider_covered),
        "missing_provider_pitchers": sorted(scheduled_keys - provider_keys),
        "missing_rundown_pitchers": sorted(scheduled_keys - rundown_keys),
        "extra_provider_pitchers_not_scheduled": sorted(provider_keys - scheduled_keys),
        "extra_rundown_pitchers_not_scheduled": sorted(rundown_keys - scheduled_keys),
    }
    if current_line_coverage:
        raw_keys = set(current_line_coverage.get("raw_pitcher_keys") or [])
        mainline_keys = set(current_line_coverage.get("mainline_pitcher_keys") or [])
        official_keys = provider_keys
        coverage.update({
            "provider_raw_covered_count": len(scheduled_keys & raw_keys),
            "provider_raw_coverage_rate": _rate(len(scheduled_keys & raw_keys), scheduled_count),
            "provider_mainline_ready_count": len(scheduled_keys & mainline_keys),
            "provider_mainline_ready_rate": _rate(len(scheduled_keys & mainline_keys), scheduled_count),
            "provider_official_ready_count": len(scheduled_keys & official_keys),
            "provider_official_ready_rate": _rate(len(scheduled_keys & official_keys), scheduled_count),
        })
    else:
        coverage.update({
            "provider_raw_covered_count": None,
            "provider_raw_coverage_rate": None,
            "provider_mainline_ready_count": None,
            "provider_mainline_ready_rate": None,
            "provider_official_ready_count": len(provider_covered),
            "provider_official_ready_rate": _rate(len(provider_covered), scheduled_count),
        })
    return coverage


def _current_line_coverage(
    provider_current_lines: list[dict[str, Any]],
    generated_at: datetime,
) -> dict[str, Any]:
    raw_pitcher_keys = {
        str(row.get("normalized_player_name") or normalize(row.get("player_name") or "")).strip()
        for row in provider_current_lines
        if str(row.get("normalized_player_name") or normalize(row.get("player_name") or "")).strip()
    }
    mainline_rows, mainline_metadata = select_mainline_current_lines(
        provider_current_lines,
        generated_at,
    )
    mainline_pitcher_keys = {
        str(row.get("normalized_player_name") or normalize(row.get("player_name") or "")).strip()
        for row in mainline_rows
        if str(row.get("normalized_player_name") or normalize(row.get("player_name") or "")).strip()
    }
    ambiguous_pitcher_keys = sorted(
        key[1]
        for key, metadata in mainline_metadata.items()
        if metadata.get("ambiguous_line_ids")
    )
    return {
        "available": True,
        "raw_pitcher_keys": sorted(raw_pitcher_keys),
        "mainline_pitcher_keys": sorted(mainline_pitcher_keys),
        "ambiguous_pitcher_keys": ambiguous_pitcher_keys,
        "raw_candidate_count": len(provider_current_lines),
        "mainline_candidate_count": len(mainline_rows),
    }


def compare_provider_cutover(
    *,
    date_str: str,
    rundown_props: list[dict[str, Any]],
    provider_props: list[dict[str, Any]],
    scheduled_pitchers: list[dict[str, Any]] | None = None,
    provider_current_lines: list[dict[str, Any]] | None = None,
    provider_usage: dict[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    generated = generated_at or datetime.now(timezone.utc)
    rundown_by_pitcher = _by_pitcher(rundown_props)
    provider_by_pitcher = _by_pitcher(provider_props)
    production_keys = set(rundown_by_pitcher)
    provider_keys = set(provider_by_pitcher)
    covered_keys = production_keys & provider_keys

    missing_provider = sorted(production_keys - provider_keys)
    extra_provider = sorted(provider_keys - production_keys)
    missing_dk = sorted(
        key for key in covered_keys if "DraftKings" not in _book_names(provider_by_pitcher[key])
    )
    fd_dk_keys = {key for key in covered_keys if _has_fd_or_dk(provider_by_pitcher[key])}
    line_conflict_keys = sorted(key for key in covered_keys if _has_line_conflict(provider_by_pitcher[key]))
    baseline_keys = {
        key
        for key in covered_keys
        if provider_by_pitcher[key].get("opening_over_odds") is not None
        and provider_by_pitcher[key].get("opening_under_odds") is not None
    }
    provider_contract_issues = [
        {
            "pitcher": row.get("pitcher"),
            "missing_fields": missing,
        }
        for row in provider_props
        if (missing := _contract_missing_fields(row))
    ]
    fire_missing_book_odds = sorted(
        key for key, row in provider_by_pitcher.items() if _is_fire(row) and not _has_book_odds(row)
    )

    production_count = len(production_keys)
    coverage_rate = _rate(len(covered_keys), production_count)
    fd_dk_rate = _rate(len(fd_dk_keys), production_count)
    conflict_rate = _rate(len(line_conflict_keys), production_count)
    current_line_coverage = (
        _current_line_coverage(provider_current_lines, generated)
        if provider_current_lines is not None
        else None
    )
    schedule_first = _schedule_first_coverage(
        scheduled_pitchers or [],
        rundown_by_pitcher,
        provider_by_pitcher,
        current_line_coverage,
    )
    prop_line_requests = None
    prop_line_usage_rate = None
    if provider_usage:
        prop_line_requests = _to_int(provider_usage.get("propline_requests"))
        if prop_line_requests is not None:
            prop_line_usage_rate = round(prop_line_requests / PROPLINE_HOBBY_DAILY_REQUESTS, 4)

    gates = [
        _gate(
            "pitcher_coverage_90",
            coverage_rate >= 0.90 if production_count else None,
            coverage_rate,
            ">=0.90",
            f"{len(covered_keys)}/{production_count}",
        ),
        _gate(
            "fd_or_dk_coverage_85",
            fd_dk_rate >= 0.85 if production_count else None,
            fd_dk_rate,
            ">=0.85",
            f"{len(fd_dk_keys)}/{production_count}",
        ),
        _gate(
            "line_conflict_rate_10",
            conflict_rate <= 0.10 if production_count else None,
            conflict_rate,
            "<=0.10",
            f"{len(line_conflict_keys)}/{production_count}",
        ),
        _gate(
            "today_contract_valid",
            len(provider_contract_issues) == 0 if provider_props else None,
            len(provider_contract_issues),
            "0 missing-field rows",
        ),
        _gate(
            "fire_picks_have_book_odds",
            len(fire_missing_book_odds) == 0,
            len(fire_missing_book_odds),
            "0 FIRE rows missing book_odds",
        ),
        _gate(
            "propline_usage_under_70pct_hobby",
            (
                prop_line_usage_rate <= PROPLINE_USAGE_WARN_FRACTION
                if prop_line_usage_rate is not None
                else None
            ),
            prop_line_usage_rate,
            f"<={PROPLINE_USAGE_WARN_FRACTION}",
            f"{prop_line_requests or 'unknown'}/{PROPLINE_HOBBY_DAILY_REQUESTS}",
        ),
        _gate(
            "schedule_provider_coverage_90",
            (
                schedule_first["provider_coverage_rate"] >= 0.90
                if schedule_first["available"] and schedule_first["scheduled_pitcher_count"]
                else None
            ),
            schedule_first["provider_coverage_rate"],
            ">=0.90",
            f"{schedule_first['provider_covered_count']}/{schedule_first['scheduled_pitcher_count']}",
        ),
        _gate(
            "schedule_fd_or_dk_coverage_85",
            (
                schedule_first["provider_fd_or_dk_rate"] >= 0.85
                if schedule_first["available"] and schedule_first["scheduled_pitcher_count"]
                else None
            ),
            schedule_first["provider_fd_or_dk_rate"],
            ">=0.85",
            f"{schedule_first['provider_fd_or_dk_count']}/{schedule_first['scheduled_pitcher_count']}",
        ),
    ]
    readiness = {
        "overall_ready": all(gate["status"] == "pass" for gate in gates),
        "gates": gates,
    }

    book_coverage_counter = Counter()
    for key in covered_keys:
        book_coverage_counter.update(_book_names(provider_by_pitcher[key]) & set(SUPPORTED_ACTION_BOOKS))

    return {
        "date": date_str,
        "generated_at": generated.astimezone(timezone.utc).isoformat(),
        "summary": {
            "production_pitcher_count": production_count,
            "provider_pitcher_count": len(provider_keys),
            "covered_pitcher_count": len(covered_keys),
            "pitcher_coverage_rate": coverage_rate,
            "fd_or_dk_coverage_rate": fd_dk_rate,
            "line_conflict_rate": conflict_rate,
            "opening_baseline_rate": _rate(len(baseline_keys), production_count),
            "provider_contract_issue_count": len(provider_contract_issues),
            "missing_draftkings_count": len(missing_dk),
            "ref_book_change_count": len(_ref_book_changes(rundown_by_pitcher, provider_by_pitcher)),
            "verdict_change_count": len(_verdict_changes(rundown_by_pitcher, provider_by_pitcher)),
            "verdict_comparison_available": any(
                _verdict(row, "over") is not None or _verdict(row, "under") is not None
                for row in [*rundown_props, *provider_props]
            ),
        },
        "readiness": readiness,
        "schedule_first": schedule_first,
        "coverage": {
            "missing_provider_pitchers": missing_provider,
            "extra_provider_pitchers": extra_provider,
            "missing_draftkings_pitchers": missing_dk,
            "line_conflict_pitchers": line_conflict_keys,
            "ambiguous_mainline_pitchers": (
                current_line_coverage.get("ambiguous_pitcher_keys", [])
                if current_line_coverage
                else []
            ),
            "book_counts_for_covered_pitchers": dict(sorted(book_coverage_counter.items())),
        },
        "market_differences": {
            "ref_book_changes": _ref_book_changes(rundown_by_pitcher, provider_by_pitcher),
            "odds_deltas_by_book": _odds_delta_rows(rundown_by_pitcher, provider_by_pitcher),
            "verdict_changes": _verdict_changes(rundown_by_pitcher, provider_by_pitcher),
        },
        "artifact_contract": {
            "provider_contract_issues": provider_contract_issues,
            "fire_missing_book_odds": fire_missing_book_odds,
        },
        "mainline_selection": current_line_coverage or {"available": False},
        "provider_usage": provider_usage or {},
    }


def format_markdown_report(report: dict[str, Any]) -> str:
    summary = report["summary"]
    readiness = report["readiness"]
    schedule = report.get("schedule_first") or {}
    lines = [
        f"# Provider Cutover Shadow Compare - {report['date']}",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "## Summary",
        "",
        f"- Production pitchers: {summary['production_pitcher_count']}",
        f"- Provider pitchers: {summary['provider_pitcher_count']}",
        f"- Covered pitchers: {summary['covered_pitcher_count']} ({summary['pitcher_coverage_rate']:.1%})",
        f"- FD/DK coverage: {summary['fd_or_dk_coverage_rate']:.1%}",
        f"- Line conflict rate: {summary['line_conflict_rate']:.1%}",
        f"- Missing DraftKings: {summary['missing_draftkings_count']}",
        f"- Ref-book changes: {summary['ref_book_change_count']}",
        f"- Verdict changes: {summary['verdict_change_count']}",
        f"- Verdict comparison available: {summary['verdict_comparison_available']}",
        "",
        "## Schedule-First Coverage",
        "",
    ]
    if schedule.get("available"):
        lines.extend([
            f"- Scheduled probable starters: {schedule['scheduled_pitcher_count']}",
            f"- Provider covered starters: {schedule['provider_covered_count']} ({schedule['provider_coverage_rate']:.1%})",
            f"- Provider FD/DK starters: {schedule['provider_fd_or_dk_count']} ({schedule['provider_fd_or_dk_rate']:.1%})",
            f"- Provider DraftKings starters: {schedule['provider_draftkings_count']} ({schedule['provider_draftkings_rate']:.1%})",
            f"- Provider FanDuel starters: {schedule['provider_fanduel_count']} ({schedule['provider_fanduel_rate']:.1%})",
            f"- Provider 2+ supported books: {schedule['provider_at_least_2_books_count']}",
            f"- Provider 3+ supported books: {schedule['provider_at_least_3_books_count']}",
            f"- No provider book coverage: {schedule['zero_provider_book_count']}",
            f"- Missing provider starters: {len(schedule['missing_provider_pitchers'])}",
            f"- Missing TheRundown starters: {len(schedule['missing_rundown_pitchers'])}",
            "",
        ])
        if schedule.get("provider_raw_covered_count") is not None:
            lines.extend([
                f"- Raw provider coverage: {schedule['provider_raw_covered_count']} ({schedule['provider_raw_coverage_rate']:.1%})",
                f"- Mainline-ready coverage: {schedule['provider_mainline_ready_count']} ({schedule['provider_mainline_ready_rate']:.1%})",
                f"- Official-ready coverage: {schedule['provider_official_ready_count']} ({schedule['provider_official_ready_rate']:.1%})",
                "",
            ])
    else:
        lines.extend([
            "- Scheduled probable starters: unavailable",
            "- Schedule-first gates are unknown until MLB probable starters are fetched.",
            "",
        ])
    lines.extend([
        "## Readiness Gates",
        "",
    ])
    for gate in readiness["gates"]:
        lines.append(
            f"- {gate['name']}: **{gate['status']}** "
            f"(value={gate['value']}, threshold={gate['threshold']}, {gate['detail']})"
        )
    lines.extend([
        "",
        f"Overall ready: **{readiness['overall_ready']}**",
        "",
        "## Notes",
        "",
        "- This is shadow evidence only. It does not change provider order or live artifacts.",
        "- Unknown gates should be treated as not ready before a cutover decision.",
    ])
    return "\n".join(lines) + "\n"


def load_json_rows(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("pitchers", "props", "rows", "data", "items"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def write_report(report: dict[str, Any], output_dir: Path = OUTPUT_DIR) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = report["date"]
    json_path = output_dir / f"provider_cutover_shadow_compare_{date_str}.json"
    markdown_path = output_dir / f"provider_cutover_shadow_compare_{date_str}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(format_markdown_report(report), encoding="utf-8")
    return json_path, markdown_path


def _fetch_provider_current_lines(writer: Any, date_str: str) -> list[dict[str, Any]]:
    return writer.select_rows(
        "current_market_lines",
        {
            "slate_date": f"eq.{date_str}",
            "market_key": "eq.pitcher_strikeouts",
            "order": "updated_at.desc",
            "limit": "10000",
        },
    )


def _parse_usage(value: str | None) -> dict[str, Any] | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="Slate date in YYYY-MM-DD format.")
    parser.add_argument("--rundown-json", type=Path, help="Optional TheRundown prop/artifact JSON.")
    parser.add_argument("--provider-json", type=Path, help="Optional provider-mode prop/artifact JSON.")
    parser.add_argument("--provider-current-lines-json", type=Path, help="Optional current_market_lines JSON.")
    parser.add_argument("--schedule-json", type=Path, help="Optional schedule-first probable-starter JSON.")
    parser.add_argument("--no-schedule-first", action="store_true", help="Skip MLB probable-starter fetch.")
    parser.add_argument("--provider-min-props", type=int, default=1, help="Minimum provider rows when fetching from Supabase.")
    parser.add_argument("--provider-usage-json", help="Optional JSON object with provider usage counters.")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    scheduled_pitchers: list[dict[str, Any]] = []
    if args.schedule_json:
        scheduled_pitchers = load_json_rows(args.schedule_json)
    elif not args.no_schedule_first:
        try:
            scheduled_pitchers = fetch_probable_starters(args.date)
        except Exception as e:
            print(f"WARNING: schedule-first probable starter fetch failed: {type(e).__name__}: {e}")
    rundown_props = (
        load_json_rows(args.rundown_json)
        if args.rundown_json
        else _fetch_therundown_odds(args.date)
    )
    writer = None
    if not args.provider_json or not args.provider_current_lines_json:
        try:
            writer = official_market_writer_from_env()
        except Exception as e:
            print(f"WARNING: provider Supabase writer unavailable: {type(e).__name__}: {e}")
    provider_props = (
        load_json_rows(args.provider_json)
        if args.provider_json
        else fetch_official_market_odds(args.date, writer=writer, min_props=args.provider_min_props)
        if writer is not None
        else []
    )
    provider_current_lines = (
        load_json_rows(args.provider_current_lines_json)
        if args.provider_current_lines_json
        else _fetch_provider_current_lines(writer, args.date)
        if writer is not None
        else None
    )
    report = compare_provider_cutover(
        date_str=args.date,
        rundown_props=rundown_props,
        provider_props=provider_props,
        scheduled_pitchers=scheduled_pitchers,
        provider_current_lines=provider_current_lines,
        provider_usage=_parse_usage(args.provider_usage_json),
    )
    json_path, markdown_path = write_report(report, args.output_dir)
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
