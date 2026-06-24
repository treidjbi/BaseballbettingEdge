"""Read-only audit of mainline movement notification patterns.

This diagnostic uses processed movement evidence, not the raw PropLine webhook
inbox. It does not change official odds source, model inputs, staking, locks,
notifications, retention, or dashboard source of truth.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from statistics import median
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from market_infra.live_events import PROPLINE_WEBHOOK_NOTIFICATION_BOOKS


OUTPUT_DIR = ROOT / "analytics" / "output"

BLOCKED_USES = [
    "official_odds_source",
    "model_input",
    "staking_input",
    "automatic_bet_trigger",
]


def summarize_mainline_movement_patterns(
    *,
    movement_events: list[dict[str, Any]],
    notification_events: list[dict[str, Any]],
    market_pick_evidence: list[dict[str, Any]],
    compact_market_movements: list[dict[str, Any]],
) -> dict[str, Any]:
    evidence_by_key = _evidence_by_key(market_pick_evidence)
    notifications_by_key = {
        str(row.get("dedupe_key")): row
        for row in notification_events
        if str(row.get("dedupe_key") or "").strip()
    }

    by_source: Counter[str] = Counter()
    by_book: Counter[str] = Counter()
    by_kind: Counter[str] = Counter()
    by_market_direction: Counter[str] = Counter()
    by_bet_value_direction: Counter[str] = Counter()
    by_line_class: Counter[str] = Counter()
    pattern_counts: dict[tuple[str, ...], dict[str, Any]] = {}
    normalized_rows: list[dict[str, Any]] = []

    supported_rows = 0
    alert_rows = 0
    sent_alert_rows = 0

    for row in movement_events:
        normalized = _normalize_movement_row(row, evidence_by_key, notifications_by_key)
        normalized_rows.append(normalized)
        by_source[normalized["source"]] += 1
        by_book[normalized["bookmaker_key"]] += 1
        by_kind[normalized["movement_kind"]] += 1
        by_market_direction[normalized["market_direction"]] += 1
        by_bet_value_direction[normalized["bet_value_direction"]] += 1
        by_line_class[normalized["line_class"]] += 1
        if normalized["supported_book"]:
            supported_rows += 1
        if normalized["alert_created"]:
            alert_rows += 1
        if normalized["alert_sent"]:
            sent_alert_rows += 1

        pattern_key = (
            normalized["source"],
            normalized["bookmaker_key"],
            normalized["movement_kind"],
            normalized["market_direction"],
            normalized["bet_value_direction"],
            normalized["line_class"],
            normalized["alert_event_type"],
        )
        bucket = pattern_counts.setdefault(
            pattern_key,
            {
                "source": normalized["source"],
                "bookmaker_key": normalized["bookmaker_key"],
                "movement_kind": normalized["movement_kind"],
                "market_direction": normalized["market_direction"],
                "bet_value_direction": normalized["bet_value_direction"],
                "line_class": normalized["line_class"],
                "alert_event_type": normalized["alert_event_type"],
                "count": 0,
                "alert_count": 0,
                "sent_count": 0,
                "supported_count": 0,
            },
        )
        bucket["count"] += 1
        bucket["alert_count"] += int(normalized["alert_created"])
        bucket["sent_count"] += int(normalized["alert_sent"])
        bucket["supported_count"] += int(normalized["supported_book"])

    all_patterns = sorted(
        pattern_counts.values(),
        key=lambda item: (
            -int(item["count"]),
            -int(item["sent_count"]),
            str(item["source"]),
            str(item["bookmaker_key"]),
        ),
    )
    top_patterns = all_patterns[:15]

    return {
        "movement_events": len(movement_events),
        "notification_events": len(notification_events),
        "market_pick_evidence_rows": len(market_pick_evidence),
        "compact_market_movement_rows": len(compact_market_movements),
        "by_source": dict(sorted(by_source.items())),
        "by_book": dict(sorted(by_book.items())),
        "by_movement_kind": dict(sorted(by_kind.items())),
        "by_market_direction": dict(sorted(by_market_direction.items())),
        "by_bet_value_direction": dict(sorted(by_bet_value_direction.items())),
        "by_line_class": dict(sorted(by_line_class.items())),
        "same_line_price_moves": by_line_class["same_line_price_move"],
        "line_moves_touching_pick_line": by_line_class["line_move_touches_pick_line"],
        "different_line_moves": by_line_class["line_move_different_line"],
        "supported_book_rows": supported_rows,
        "unsupported_book_rows": len(movement_events) - supported_rows,
        "alert_rows": alert_rows,
        "sent_alert_rows": sent_alert_rows,
        "webhook_vs_polling_timing": _webhook_vs_polling_timing(normalized_rows),
        "top_patterns": top_patterns,
        "candidate_alert_patterns": _candidate_alert_patterns(all_patterns),
        "compact_activity": _compact_activity(compact_market_movements),
        "recommendation": _recommendation(
            movement_count=len(movement_events),
            alert_rows=alert_rows,
            sent_alert_rows=sent_alert_rows,
            timing=_webhook_vs_polling_timing(normalized_rows),
        ),
        "blocked_uses": list(BLOCKED_USES),
    }


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("payload")
    return payload if isinstance(payload, dict) else {}


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed


def _source(row: dict[str, Any]) -> str:
    metadata = _metadata(row)
    dedupe_key = str(row.get("dedupe_key") or "")
    explicit = str(row.get("source") or metadata.get("source") or "").strip()
    if explicit == "propline_webhook" or "propline_webhook" in dedupe_key:
        return "propline_webhook"
    return "mainline_polling"


def _row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("slate_date") or "").strip(),
        str(row.get("normalized_pitcher") or row.get("pitcher") or "").strip().lower(),
        str(row.get("side") or "").strip().lower(),
    )


def _evidence_by_key(rows: list[dict[str, Any]]) -> dict[tuple[str, str, str], dict[str, Any]]:
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        key = _row_key(row)
        if not all(key):
            continue
        result.setdefault(key, row)
    return result


def _line_class(row: dict[str, Any], pick_line: float | None) -> str:
    previous_line = _float(row.get("previous_line"))
    current_line = _float(row.get("current_line"))
    if previous_line is None or current_line is None:
        return "unknown_line"
    if abs(previous_line - current_line) < 0.001:
        return "same_line_price_move"
    if pick_line is None:
        return "line_move_unknown_pick_line"
    if abs(previous_line - pick_line) < 0.001 or abs(current_line - pick_line) < 0.001:
        return "line_move_touches_pick_line"
    return "line_move_different_line"


def _normalize_movement_row(
    row: dict[str, Any],
    evidence_by_key: dict[tuple[str, str, str], dict[str, Any]],
    notifications_by_key: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    metadata = _metadata(row)
    evidence = evidence_by_key.get(_row_key(row), {})
    notification = notifications_by_key.get(str(row.get("dedupe_key") or ""))
    book = str(row.get("bookmaker_key") or "").strip().lower() or "<blank>"
    pick_line = _float(row.get("k_line") or evidence.get("k_line"))
    alert_event_type = str(
        (notification or {}).get("event_type")
        or metadata.get("event_type")
        or "no_alert"
    )
    return {
        "dedupe_key": str(row.get("dedupe_key") or ""),
        "slate_date": str(row.get("slate_date") or ""),
        "normalized_pitcher": str(row.get("normalized_pitcher") or row.get("pitcher") or "").lower(),
        "side": str(row.get("side") or "").lower(),
        "bookmaker_key": book,
        "source": _source(row),
        "movement_kind": str(row.get("movement_kind") or "unknown"),
        "market_direction": str(
            row.get("market_direction")
            or metadata.get("market_direction")
            or _payload(notification or {}).get("market_direction")
            or "unknown"
        ),
        "bet_value_direction": str(
            row.get("bet_value_direction")
            or metadata.get("bet_value_direction")
            or _payload(notification or {}).get("bet_value_direction")
            or "unknown"
        ),
        "line_class": _line_class(row, pick_line),
        "alert_event_type": alert_event_type,
        "alert_created": notification is not None,
        "alert_sent": bool((notification or {}).get("sent_at")),
        "supported_book": book in PROPLINE_WEBHOOK_NOTIFICATION_BOOKS,
        "previous_line": _float(row.get("previous_line")),
        "current_line": _float(row.get("current_line")),
        "previous_odds": _float(row.get("previous_odds")),
        "current_odds": _float(row.get("current_odds")),
        "observed_at": _parse_datetime(row.get("observed_at")),
    }


def _movement_signature(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["slate_date"],
        row["normalized_pitcher"],
        row["side"],
        row["bookmaker_key"],
        row["previous_line"],
        row["current_line"],
        row["previous_odds"],
        row["current_odds"],
        row["movement_kind"],
    )


def _webhook_vs_polling_timing(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[Any, ...], dict[str, list[datetime]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        observed_at = row.get("observed_at")
        if not isinstance(observed_at, datetime):
            continue
        grouped[_movement_signature(row)][row["source"]].append(observed_at)

    leads: list[float] = []
    webhook_first = 0
    polling_first = 0
    ties = 0
    for sources in grouped.values():
        webhook_times = sources.get("propline_webhook") or []
        polling_times = sources.get("mainline_polling") or []
        if not webhook_times or not polling_times:
            continue
        webhook_time = min(webhook_times)
        polling_time = min(polling_times)
        delta = (polling_time - webhook_time).total_seconds()
        leads.append(delta)
        if delta > 0:
            webhook_first += 1
        elif delta < 0:
            polling_first += 1
        else:
            ties += 1

    return {
        "matched_movements": len(leads),
        "webhook_first": webhook_first,
        "polling_first": polling_first,
        "ties": ties,
        "median_webhook_lead_seconds": median(leads) if leads else None,
    }


def _candidate_alert_patterns(top_patterns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    for pattern in top_patterns:
        if int(pattern["supported_count"]) <= 0:
            continue
        if pattern["line_class"] not in {"same_line_price_move", "line_move_touches_pick_line"}:
            continue
        if pattern["alert_event_type"] not in {"line_moved_against_us", "line_moved_with_us"}:
            continue
        candidates.append(pattern)
    return sorted(
        candidates,
        key=lambda item: (
            -int(item["sent_count"]),
            -int(item["alert_count"]),
            -int(item["count"]),
            str(item["source"]),
            str(item["bookmaker_key"]),
        ),
    )[:10]


def _compact_activity(rows: list[dict[str, Any]]) -> dict[str, Any]:
    provider_counts: Counter[str] = Counter()
    book_counts: Counter[str] = Counter()
    high_activity = []
    for row in rows:
        provider_counts[str(row.get("provider") or "<blank>")] += 1
        book_counts[str(row.get("book_key") or row.get("bookmaker_key") or "<blank>").lower()] += 1
        move_count = int(_float(row.get("odds_move_count")) or 0)
        if move_count >= 3:
            high_activity.append({
                "slate_date": row.get("slate_date"),
                "pitcher": row.get("player_name"),
                "side": row.get("side"),
                "provider": row.get("provider"),
                "book": row.get("book_key") or row.get("bookmaker_key"),
                "line": row.get("line"),
                "odds_move_count": move_count,
                "snapshot_count": row.get("snapshot_count"),
            })
    return {
        "rows": len(rows),
        "by_provider": dict(sorted(provider_counts.items())),
        "by_book": dict(sorted(book_counts.items())),
        "high_activity_rows": sorted(
            high_activity,
            key=lambda item: -int(item.get("odds_move_count") or 0),
        )[:15],
    }


def _recommendation(
    *,
    movement_count: int,
    alert_rows: int,
    sent_alert_rows: int,
    timing: dict[str, Any],
) -> str:
    if movement_count == 0:
        return "collect_more_evidence_no_recent_processed_movements"
    if alert_rows == 0:
        return "keep_collecting_before_notification_pattern_review"
    if timing.get("matched_movements") and timing.get("webhook_first"):
        return "review_supported_same_line_and_touching_pick_line_alert_patterns"
    if sent_alert_rows:
        return "review_sent_alert_patterns_against_operator_value"
    return "observe_more_before_expanding_alert_classes"


def run_audit(target_date: date, lookback_days: int, limit: int) -> dict[str, Any]:
    safe_lookback = max(int(lookback_days), 1)
    start_date = target_date - timedelta(days=safe_lookback - 1)
    read_result = _read_supabase_rows(start_date=start_date, end_date=target_date, limit=max(int(limit), 1))
    summary = summarize_mainline_movement_patterns(
        movement_events=read_result["movement_events"],
        notification_events=read_result["notification_events"],
        market_pick_evidence=read_result["market_pick_evidence"],
        compact_market_movements=read_result["compact_market_movements"],
    )
    return {
        "date": target_date.isoformat(),
        "lookback_days": safe_lookback,
        "window_start_date": start_date.isoformat(),
        "window_end_date": target_date.isoformat(),
        "access_status": read_result["access_status"],
        "access_issues": read_result["access_issues"],
        "row_counts": read_result["row_counts"],
        "summary": summary,
    }


CliRunner = Callable[[list[str]], Any]


def _read_supabase_rows(
    *,
    start_date: date,
    end_date: date,
    limit: int,
    cli_runner: CliRunner | None = None,
) -> dict[str, Any]:
    result = {
        "movement_events": [],
        "notification_events": [],
        "market_pick_evidence": [],
        "compact_market_movements": [],
        "access_status": "complete",
        "access_issues": [],
        "row_counts": {},
    }
    runner = cli_runner or _run_linked_supabase_cli
    successful_reads = 0
    for result_key, spec in _linked_cli_queries(start_date=start_date, end_date=end_date, limit=limit).items():
        table = spec["table"]
        try:
            payload = runner(["npx", "supabase", "db", "query", "--linked", "-o", "json", _compact_sql(spec["sql"])])
            rows = _extract_cli_rows(payload)
            successful_reads += 1
        except Exception as error:  # noqa: BLE001 - report should be non-fatal.
            rows = []
            result["access_status"] = "partial"
            result["access_issues"].append(f"{table} linked CLI read failed: {_safe_cli_error(error)}")
        result[result_key] = rows
        result["row_counts"][table] = len(rows)

    if successful_reads == 0:
        result["access_status"] = "blocked"
        result["access_issues"] = [
            "Linked Supabase CLI read failed for all movement tables; output does not prove no movement exists."
        ]
        result["row_counts"] = {}
    return result


def _linked_cli_queries(*, start_date: date, end_date: date, limit: int) -> dict[str, dict[str, Any]]:
    start = _sql_literal(start_date.isoformat())
    end = _sql_literal(end_date.isoformat())
    safe_limit = max(int(limit), 1)
    return {
        "movement_events": {
            "table": "line_movement_events",
            "sql": f"""
                select
                  id,
                  slate_date,
                  normalized_pitcher,
                  pitcher,
                  side,
                  bookmaker_key,
                  previous_line,
                  current_line,
                  previous_odds,
                  current_odds,
                  movement_direction,
                  movement_kind,
                  observed_at,
                  dedupe_key,
                  metadata,
                  created_at
                from public.line_movement_events
                where slate_date >= {start}
                  and slate_date <= {end}
                order by observed_at desc
                limit {safe_limit};
            """,
        },
        "notification_events": {
            "table": "notification_events",
            "sql": f"""
                select
                  id,
                  slate_date,
                  event_type,
                  severity,
                  dedupe_key,
                  payload,
                  occurred_at,
                  sent_at,
                  created_at
                from public.notification_events
                where slate_date >= {start}
                  and slate_date <= {end}
                  and event_type in ('line_moved_with_us', 'line_moved_against_us')
                order by created_at desc
                limit {safe_limit};
            """,
        },
        "market_pick_evidence": {
            "table": "market_pick_evidence",
            "sql": f"""
                select
                  id,
                  slate_date,
                  pitcher,
                  normalized_pitcher,
                  side,
                  provider,
                  current_verdict,
                  k_line,
                  current_odds,
                  current_book,
                  observed_at,
                  market_consensus,
                  bet_value_consensus,
                  time_window,
                  dedupe_key,
                  metadata
                from public.market_pick_evidence
                where slate_date >= {start}
                  and slate_date <= {end}
                order by observed_at desc
                limit {safe_limit};
            """,
        },
        "compact_market_movements": {
            "table": "compact_market_line_movements",
            "sql": f"""
                select
                  id,
                  slate_date,
                  provider,
                  book_key,
                  market_key,
                  player_name,
                  normalized_player_name,
                  side,
                  line,
                  first_odds,
                  last_odds,
                  min_odds,
                  max_odds,
                  odds_move_count,
                  snapshot_count,
                  first_seen_at,
                  last_seen_at
                from public.compact_market_line_movements
                where slate_date >= {start}
                  and slate_date <= {end}
                order by last_seen_at desc
                limit {safe_limit};
            """,
        },
    }


def _run_linked_supabase_cli(command: list[str]) -> Any:
    resolved_command = list(command)
    if resolved_command and resolved_command[0] == "npx":
        resolved_command[0] = shutil.which("npx") or shutil.which("npx.cmd") or resolved_command[0]
    completed = subprocess.run(
        resolved_command,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return json.loads(completed.stdout)


def _extract_cli_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict):
        rows = payload.get("rows")
    else:
        rows = payload
    if not isinstance(rows, list):
        raise ValueError("linked CLI JSON rows is not a list")
    if any(not isinstance(row, dict) for row in rows):
        raise ValueError("linked CLI JSON rows must contain objects")
    return rows


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _compact_sql(sql: str) -> str:
    return " ".join(sql.split())


def _safe_cli_error(error: Exception) -> str:
    if isinstance(error, subprocess.CalledProcessError):
        stderr = (error.stderr or "").strip()
        if stderr:
            return stderr.splitlines()[-1][:180]
        return f"exit {error.returncode}"
    message = str(error).strip()
    return message[:180] if message else error.__class__.__name__


def build_markdown_report(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        f"# Mainline Movement Pattern Audit - {result['date']}",
        "",
        "Read-only diagnostic. This report evaluates movement-notification patterns; it does not change production behavior.",
        "",
        f"- Access status: `{result['access_status']}`",
        f"- Window: `{result['window_start_date']}` through `{result['window_end_date']}`",
        f"- Movement events: {summary['movement_events']} alerts={summary['alert_rows']} sent={summary['sent_alert_rows']}",
        f"- Sources: `{json.dumps(summary['by_source'], sort_keys=True)}`",
        f"- Line classes: `{json.dumps(summary['by_line_class'], sort_keys=True)}`",
        f"- Supported-book rows: {summary['supported_book_rows']} unsupported={summary['unsupported_book_rows']}",
        f"- Webhook/polling timing: `{json.dumps(summary['webhook_vs_polling_timing'], sort_keys=True)}`",
        f"- Recommendation: `{summary['recommendation']}`",
        "",
        "## Candidate Alert Patterns",
        "",
    ]
    candidates = summary["candidate_alert_patterns"]
    if candidates:
        lines.extend(_format_pattern(pattern) for pattern in candidates)
    else:
        lines.append("- None with current evidence.")
    lines.extend(["", "## Top Patterns", ""])
    if summary["top_patterns"]:
        lines.extend(_format_pattern(pattern) for pattern in summary["top_patterns"])
    else:
        lines.append("- No processed movement rows.")
    lines.extend(["", "## Blocked Uses", ""])
    lines.extend(f"- `{use}`" for use in summary["blocked_uses"])
    if result["access_issues"]:
        lines.extend(["", "## Access Issues", ""])
        lines.extend(f"- {issue}" for issue in result["access_issues"])
    return "\n".join(lines) + "\n"


def _format_pattern(pattern: dict[str, Any]) -> str:
    return (
        f"- {pattern['source']} / {pattern['bookmaker_key']} / {pattern['movement_kind']} / "
        f"{pattern['market_direction']} / {pattern['bet_value_direction']} / "
        f"{pattern['line_class']} / {pattern['alert_event_type']}: "
        f"count={pattern['count']} alerts={pattern['alert_count']} sent={pattern['sent_count']}"
    )


def write_outputs(result: dict[str, Any], output_dir: Path = OUTPUT_DIR) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"mainline_movement_pattern_audit_{result['date']}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(build_markdown_report(result), encoding="utf-8")
    return md_path, json_path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, type=date.fromisoformat, help="Audit end date, YYYY-MM-DD")
    parser.add_argument("--lookback-days", type=int, default=7, help="Inclusive lookback window in days")
    parser.add_argument("--limit", type=int, default=2000, help="Maximum rows per Supabase table")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    result = run_audit(args.date, args.lookback_days, args.limit)
    md_path, json_path = write_outputs(result)
    print(f"wrote {md_path.relative_to(ROOT)}")
    print(f"wrote {json_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
