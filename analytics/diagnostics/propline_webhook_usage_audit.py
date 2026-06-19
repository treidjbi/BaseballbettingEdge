"""Read-only audit of PropLine webhook decision value.

This diagnostic does not change official odds source, model inputs, staking,
automatic bet triggers, locks, notifications, retention, or dashboard source of
truth. Webhooks are movement/timing evidence only unless a later promotion plan
approves a narrower use.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "analytics" / "output"

BLOCKED_USES = [
    "official_odds_source",
    "model_input",
    "staking_input",
    "automatic_bet_trigger",
]


def summarize_webhook_usage(
    *,
    deliveries: list[dict[str, Any]],
    movement_events: list[dict[str, Any]],
    notification_events: list[dict[str, Any]],
    market_pick_evidence: list[dict[str, Any]],
    accepted_bets: list[dict[str, Any]],
) -> dict[str, Any]:
    delivery_payloads = [_payload(row) for row in deliveries]
    webhook_movements = [row for row in movement_events if _is_webhook_source(row)]
    polling_confirmed = [row for row in webhook_movements if _polling_confirmed(row)]
    dedupe_counts = Counter(
        str(row.get("dedupe_key"))
        for row in movement_events
        if str(row.get("dedupe_key") or "").strip()
    )

    summary = {
        "deliveries": len(deliveries),
        "signed_deliveries": sum(1 for row in deliveries if row.get("signature_valid") is True),
        "processed_deliveries": sum(1 for row in deliveries if row.get("processed") is True),
        "unsupported_deliveries": sum(1 for row in deliveries if _is_unsupported_delivery(row)),
        "with_bookmaker_key": sum(1 for payload in delivery_payloads if _has_value(payload.get("bookmaker_key"))),
        "with_stable_market_ids": sum(
            1
            for payload in delivery_payloads
            if _has_value(payload.get("market_id")) and _has_value(payload.get("outcome_id"))
        ),
        "line_movement_events": len(movement_events),
        "webhook_notification_events": sum(1 for row in notification_events if _is_webhook_notification(row)),
        "duplicate_dedupe_keys": sum(1 for count in dedupe_counts.values() if count > 1),
        "post_start_or_stale_events": sum(1 for row in webhook_movements if _is_post_start_or_stale(row)),
        "webhook_only_movement_events": len(webhook_movements) - len(polling_confirmed),
        "polling_confirmed_movement_events": len(polling_confirmed),
        "accepted_bet_overlap_count": sum(1 for row in accepted_bets if _has_webhook_context(row)),
        "recommended_uses": [],
        "blocked_uses": list(BLOCKED_USES),
    }
    summary["recommended_uses"] = _recommended_uses(summary, market_pick_evidence)
    return summary


def _payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = row.get("payload")
    return payload if isinstance(payload, dict) else {}


def _metadata(row: dict[str, Any]) -> dict[str, Any]:
    metadata = row.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _has_value(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _is_unsupported_delivery(row: dict[str, Any]) -> bool:
    error = str(row.get("processing_error") or "").strip()
    return bool(error) and error != "None"


def _source(row: dict[str, Any]) -> str:
    metadata = _metadata(row)
    payload = _payload(row)
    return str(
        row.get("source")
        or metadata.get("source")
        or payload.get("source")
        or payload.get("provider")
        or ""
    )


def _is_webhook_source(row: dict[str, Any]) -> bool:
    return _source(row) == "propline_webhook"


def _polling_confirmed(row: dict[str, Any]) -> bool:
    metadata = _metadata(row)
    return bool(
        row.get("polling_confirmed")
        or metadata.get("polling_confirmed")
        or metadata.get("propline_polling_confirmed")
        or metadata.get("polling_confirmation_count")
    )


def _is_post_start_or_stale(row: dict[str, Any]) -> bool:
    metadata = _metadata(row)
    freshness = str(row.get("freshness_status") or metadata.get("freshness_status") or "").lower()
    return freshness == "stale" or bool(
        row.get("post_start")
        or metadata.get("post_start")
        or metadata.get("after_game_start")
        or metadata.get("post_start_event")
    )


def _is_webhook_notification(row: dict[str, Any]) -> bool:
    if _is_webhook_source(row):
        return True
    payload = _payload(row)
    metadata = _metadata(row)
    event_type = str(row.get("event_type") or row.get("type") or "").lower()
    return (
        str(payload.get("source") or metadata.get("source") or "") == "propline_webhook"
        or "propline_webhook" in event_type
    )


def _has_webhook_context(row: dict[str, Any]) -> bool:
    if _is_webhook_source(row):
        return True
    metadata = _metadata(row)
    payload = _payload(row)
    return bool(
        row.get("propline_webhook_confirmed")
        or metadata.get("propline_webhook_confirmed")
        or payload.get("propline_webhook_confirmed")
        or metadata.get("propline_webhook_count")
        or payload.get("propline_webhook_count")
    )


def _recommended_uses(summary: dict[str, Any], market_pick_evidence: list[dict[str, Any]]) -> list[str]:
    uses: set[str] = set()
    if summary["webhook_only_movement_events"] > 0:
        uses.add("dashboard_webhook_confirmed_badge")
        uses.add("movement_strength_label")
        uses.add("provider_refresh_trigger_shadow")
    if summary["webhook_notification_events"] > 0:
        uses.add("notification_priority_boost")
    if summary["accepted_bet_overlap_count"] > 0:
        uses.add("accepted_bet_context_tag")
    if any(_has_webhook_context(row) for row in market_pick_evidence):
        uses.add("movement_strength_label")
        uses.add("accepted_bet_context_tag")
    return sorted(uses)


def run_audit(target_date: date, lookback_days: int, limit: int) -> dict[str, Any]:
    start_date = target_date - timedelta(days=max(lookback_days, 1) - 1)
    start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(target_date, time.max, tzinfo=timezone.utc)
    read_result = _read_supabase_rows(start_dt=start_dt, end_dt=end_dt, limit=limit)
    summary = summarize_webhook_usage(
        deliveries=read_result["deliveries"],
        movement_events=read_result["movement_events"],
        notification_events=read_result["notification_events"],
        market_pick_evidence=read_result["market_pick_evidence"],
        accepted_bets=read_result["accepted_bets"],
    )
    return {
        "date": target_date.isoformat(),
        "lookback_days": lookback_days,
        "window_start": start_dt.isoformat(),
        "window_end": end_dt.isoformat(),
        "access_status": read_result["access_status"],
        "access_issues": read_result["access_issues"],
        "row_counts": read_result["row_counts"],
        "summary": summary,
    }


def _read_supabase_rows(*, start_dt: datetime, end_dt: datetime, limit: int) -> dict[str, Any]:
    result = {
        "deliveries": [],
        "movement_events": [],
        "notification_events": [],
        "market_pick_evidence": [],
        "accepted_bets": [],
        "access_status": "complete",
        "access_issues": [],
        "row_counts": {},
    }
    supabase_url = os.environ.get("SUPABASE_URL", "").strip()
    service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not supabase_url or not service_role_key:
        result["access_status"] = "blocked"
        result["access_issues"].append(
            "SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY unavailable; emitted partial zero-row audit."
        )
        return result

    from market_infra.supabase_writer import SupabaseMarketWriter

    writer = SupabaseMarketWriter(supabase_url, service_role_key)
    date_start = start_dt.date().isoformat()
    date_end = end_dt.date().isoformat()
    queries = {
        "deliveries": (
            "propline_webhook_deliveries",
            {
                "and": _between_filter("received_at", start_dt.isoformat(), end_dt.isoformat()),
                "order": "received_at.desc",
                "limit": str(limit),
            },
        ),
        "movement_events": (
            "line_movement_events",
            {
                "and": _between_filter("slate_date", date_start, date_end),
                "metadata->>source": "eq.propline_webhook",
                "order": "observed_at.desc",
                "limit": str(limit),
            },
        ),
        "notification_events": (
            "notification_events",
            {
                "and": _between_filter("slate_date", date_start, date_end),
                "order": "created_at.desc",
                "limit": str(limit),
            },
        ),
        "market_pick_evidence": (
            "market_pick_evidence",
            {
                "and": _between_filter("slate_date", date_start, date_end),
                "order": "observed_at.desc",
                "limit": str(limit),
            },
        ),
        "accepted_bets": (
            "accepted_bets",
            {
                "and": _between_filter("accepted_at", start_dt.isoformat(), end_dt.isoformat()),
                "order": "accepted_at.desc",
                "limit": str(limit),
            },
        ),
    }
    for result_key, (table, query) in queries.items():
        try:
            rows = writer.select_rows(table, query)
        except requests.HTTPError as error:
            if _is_missing_optional_table(error) and table == "accepted_bets":
                result["access_status"] = "partial"
                result["access_issues"].append("accepted_bets table unavailable; skipped optional overlap read.")
                rows = []
            else:
                result["access_status"] = "partial"
                result["access_issues"].append(f"{table} read failed: {_safe_http_error(error)}")
                rows = []
        result[result_key] = rows
        result["row_counts"][table] = len(rows)
    return result


def _between_filter(field: str, start_value: str, end_value: str) -> str:
    return f"({field}.gte.{start_value},{field}.lte.{end_value})"


def _is_missing_optional_table(error: requests.HTTPError) -> bool:
    response = getattr(error, "response", None)
    return bool(response is not None and response.status_code in {404, 406})


def _safe_http_error(error: requests.HTTPError) -> str:
    response = getattr(error, "response", None)
    if response is None:
        return error.__class__.__name__
    return f"HTTP {response.status_code}"


def build_markdown_report(result: dict[str, Any]) -> str:
    summary = result["summary"]
    lines = [
        f"# PropLine Webhook Usage Audit - {result['date']}",
        "",
        "Read-only diagnostic. PropLine webhooks are not a full odds source and this report does not change production behavior.",
        "",
        f"- Access status: `{result['access_status']}`",
        f"- Window UTC: `{result['window_start']}` through `{result['window_end']}`",
        f"- Deliveries: {summary['deliveries']} signed={summary['signed_deliveries']} processed={summary['processed_deliveries']} unsupported={summary['unsupported_deliveries']}",
        f"- Book metadata: bookmaker_key={summary['with_bookmaker_key']} stable_market_ids={summary['with_stable_market_ids']}",
        f"- Movement events: {summary['line_movement_events']} webhook_only={summary['webhook_only_movement_events']} polling_confirmed={summary['polling_confirmed_movement_events']}",
        f"- Notification events: {summary['webhook_notification_events']}",
        f"- Duplicate dedupe keys: {summary['duplicate_dedupe_keys']}",
        f"- Post-start or stale events: {summary['post_start_or_stale_events']}",
        f"- Accepted-bet overlap: {summary['accepted_bet_overlap_count']}",
        "",
        "## Recommended Uses",
        "",
    ]
    if summary["recommended_uses"]:
        lines.extend(f"- `{use}`" for use in summary["recommended_uses"])
    else:
        lines.append("- None from available evidence.")
    lines.extend([
        "",
        "## Blocked Uses",
        "",
    ])
    lines.extend(f"- `{use}`" for use in summary["blocked_uses"])
    if result["access_issues"]:
        lines.extend(["", "## Access Issues", ""])
        lines.extend(f"- {issue}" for issue in result["access_issues"])
    return "\n".join(lines) + "\n"


def write_outputs(result: dict[str, Any], output_dir: Path = OUTPUT_DIR) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"propline_webhook_usage_audit_{result['date']}"
    json_path = output_dir / f"{stem}.json"
    md_path = output_dir / f"{stem}.md"
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(build_markdown_report(result), encoding="utf-8")
    return md_path, json_path


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, type=date.fromisoformat, help="Audit date, YYYY-MM-DD")
    parser.add_argument("--lookback-days", type=int, default=3, help="Inclusive UTC lookback window in days")
    parser.add_argument("--limit", type=int, default=1000, help="Maximum rows per Supabase table")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    result = run_audit(args.date, args.lookback_days, max(args.limit, 1))
    md_path, json_path = write_outputs(result)
    print(f"wrote {md_path.relative_to(ROOT)}")
    print(f"wrote {json_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
