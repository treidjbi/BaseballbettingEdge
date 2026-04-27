"""Read-only diagnostic for the upcoming pre-Phase-C SwStr confirmation gate."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parent.parent.parent
PICKS_HISTORY_PATH = ROOT / "data" / "picks_history.json"
TODAY_PATH = ROOT / "dashboard" / "data" / "processed" / "today.json"
GATE_DATE = date(2026, 4, 27)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_iso_date(value: Any) -> date | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def is_nonzero_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and abs(value) > 1e-9


def iter_fresh_rows(rows: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], int, int]:
    fresh_rows: list[dict[str, Any]] = []
    skipped_missing_date = 0
    skipped_bad_date = 0

    for row in rows:
        parsed = parse_iso_date(row.get("date"))
        if parsed is None:
            if row.get("date") in (None, ""):
                skipped_missing_date += 1
            else:
                skipped_bad_date += 1
            continue
        if parsed >= GATE_DATE:
            fresh_rows.append(row)

    return fresh_rows, skipped_missing_date, skipped_bad_date


def print_fresh_report(rows: list[dict[str, Any]], skipped_missing_date: int, skipped_bad_date: int) -> None:
    combo_counts = Counter(
        (
            row.get("date"),
            int(row.get("data_complete") == 1),
            int(row.get("career_swstr_pct") is None),
            int(not is_nonzero_number(row.get("swstr_delta_k9"))),
        )
        for row in rows
    )

    print(f"=== Fresh picks history since {GATE_DATE.isoformat()} ===")
    print(f"total fresh rows: {len(rows)}")
    print(f"non-null career_swstr_pct: {sum(1 for row in rows if row.get('career_swstr_pct') is not None)}")
    print(f"nonzero swstr_delta_k9: {sum(1 for row in rows if is_nonzero_number(row.get('swstr_delta_k9')))}")
    print(f"data_complete == 1: {sum(1 for row in rows if row.get('data_complete') == 1)}")
    print(f"skipped missing date: {skipped_missing_date}")
    print(f"skipped malformed date: {skipped_bad_date}")
    print("combo breakdown (date, data_complete, career_none, delta_zero):")
    if not combo_counts:
        print("  (no fresh rows)")
        return

    for combo, count in sorted(combo_counts.items()):
        print(f"  {combo}: {count}")


def print_live_snapshot(today_payload: dict[str, Any]) -> None:
    pitchers = today_payload.get("pitchers")
    if not isinstance(pitchers, list):
        print("\n=== Live today.json snapshot ===")
        print("pitchers list missing or not a list")
        return

    print("\n=== Live today.json snapshot ===")
    print(f"date: {today_payload.get('date')}")
    print(f"pitcher count: {len(pitchers)}")
    print(
        "non-null career_swstr_pct: "
        f"{sum(1 for pitcher in pitchers if pitcher.get('career_swstr_pct') is not None)}"
    )
    print(
        "nonzero swstr_delta_k9: "
        f"{sum(1 for pitcher in pitchers if is_nonzero_number(pitcher.get('swstr_delta_k9')))}"
    )


def main() -> None:
    if not PICKS_HISTORY_PATH.exists():
        raise SystemExit(f"ERROR: missing {PICKS_HISTORY_PATH}")

    rows = load_json(PICKS_HISTORY_PATH)
    if not isinstance(rows, list):
        raise SystemExit(f"ERROR: expected list in {PICKS_HISTORY_PATH}")

    fresh_rows, skipped_missing_date, skipped_bad_date = iter_fresh_rows(rows)
    print_fresh_report(fresh_rows, skipped_missing_date, skipped_bad_date)

    if TODAY_PATH.exists():
        today_payload = load_json(TODAY_PATH)
        if isinstance(today_payload, dict):
            print_live_snapshot(today_payload)
        else:
            print("\n=== Live today.json snapshot ===")
            print(f"unexpected payload type: {type(today_payload).__name__}")
    else:
        print(f"\nLive snapshot skipped: {TODAY_PATH} not found")


if __name__ == "__main__":
    main()
