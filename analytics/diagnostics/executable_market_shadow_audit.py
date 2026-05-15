"""Shadow audit for best executable pitcher-K market candidates.

This diagnostic is analysis-only. It does not change live picks, locks,
thresholds, staking, provider order, notification sends, artifacts, or
calibration.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "pipeline"))

from scipy.stats import poisson  # noqa: E402

from market_infra.official_market_lines import select_mainline_current_lines  # noqa: E402
from pipeline.build_features import calc_edge, calc_ev, calc_verdict  # noqa: E402
from pipeline.fetch_provider_market_odds import official_market_writer_from_env  # noqa: E402
from pipeline.name_utils import normalize  # noqa: E402


OUTPUT_DIR = ROOT / "analytics" / "output"
SUPPORTED_BOOK_KEYS = {"fanduel", "draftkings", "betmgm", "betrivers", "caesars"}
MAX_LAMBDA_LINE_GAP = 2.5


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


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _pitcher_key(row: dict[str, Any]) -> str:
    return normalize(row.get("pitcher") or row.get("player_name") or "")


def _model_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        for key in ("pitchers", "props", "rows", "data", "items"):
            rows = payload.get(key)
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
    return []


def _projection(row: dict[str, Any], params: dict[str, Any] | None) -> tuple[float | None, str]:
    raw_lambda = _to_float(row.get("raw_lambda"))
    lambda_bias = _to_float((params or {}).get("lambda_bias"))
    if raw_lambda is not None and lambda_bias is not None:
        return max(0.01, raw_lambda + lambda_bias), "raw_lambda_plus_bias"
    for field in ("applied_lambda", "lambda", "projected_ks"):
        value = _to_float(row.get(field))
        if value is not None:
            return max(0.01, value), field
    return None, "missing"


def _capped_projection(projection: float, line: float) -> float:
    return min(max(projection, line - MAX_LAMBDA_LINE_GAP), line + MAX_LAMBDA_LINE_GAP)


def _win_probability(side: str, line: float, projection: float) -> float:
    capped = _capped_projection(projection, line)
    if side == "over":
        return float(1 - poisson.cdf(math.floor(line), capped))
    return float(poisson.cdf(math.ceil(line) - 1, capped))


def _freshness_seconds(row: dict[str, Any], generated_at: datetime) -> int | None:
    existing = _to_int(row.get("freshness_seconds"))
    if existing is not None:
        return existing
    last_seen = _parse_datetime(row.get("last_seen_at"))
    if last_seen is None:
        return None
    return max(0, int((generated_at - last_seen).total_seconds()))


def _is_eligible_line(row: dict[str, Any], generated_at: datetime, stale_after_seconds: int) -> bool:
    if str(row.get("book_key") or "").strip().lower() not in SUPPORTED_BOOK_KEYS:
        return False
    if row.get("is_complete") is not True:
        return False
    if _to_float(row.get("line")) is None:
        return False
    freshness = _freshness_seconds(row, generated_at)
    return freshness is not None and freshness <= stale_after_seconds


def _line_value_vs_official(side: str, candidate_line: float, official_line: float | None) -> str:
    if official_line is None:
        return "unknown"
    if candidate_line == official_line:
        return "same_as_official"
    if side == "over":
        return "better_than_official" if candidate_line < official_line else "worse_than_official"
    return "better_than_official" if candidate_line > official_line else "worse_than_official"


def _conflict_type(rows: list[dict[str, Any]], official_line: float | None) -> str:
    lines = [_to_float(row.get("line")) for row in rows]
    line_counts = Counter(line for line in lines if line is not None)
    if len(line_counts) <= 1:
        return "none"
    most_common = line_counts.most_common()
    top_line, top_count = most_common[0]
    next_count = most_common[1][1] if len(most_common) > 1 else 0
    has_unique_majority = top_count > next_count and top_count >= 2
    if has_unique_majority and official_line is not None and top_line != official_line:
        return "ref_vs_majority"
    if has_unique_majority and any(count == 1 for _line, count in most_common[1:]):
        return "single_book_outlier"
    return "line_split"


def _current_best_side(row: dict[str, Any]) -> dict[str, Any] | None:
    options: list[dict[str, Any]] = []
    for side in ("over", "under"):
        ev_row = row.get(f"ev_{side}") or {}
        if not isinstance(ev_row, dict):
            continue
        ev = _to_float(ev_row.get("adj_ev"))
        if ev is None:
            ev = _to_float(ev_row.get("ev"))
        if ev is None:
            continue
        options.append({
            "side": side,
            "line": _to_float(row.get("k_line")),
            "book": row.get(f"best_{side}_book"),
            "odds": _to_int(row.get(f"best_{side}_odds")),
            "ev": round(ev, 4),
            "verdict": ev_row.get("verdict"),
        })
    return max(options, key=lambda item: item["ev"]) if options else None


def _score_candidate(
    *,
    model_row: dict[str, Any],
    market_line: dict[str, Any],
    side: str,
    projection: float,
    projection_source: str,
    generated_at: datetime,
) -> dict[str, Any] | None:
    line = _to_float(market_line.get("line"))
    odds = _to_int(market_line.get(f"{side}_odds"))
    if line is None or odds is None:
        return None
    win_prob = _win_probability(side, line, projection)
    ev = calc_ev(win_prob, odds)
    edge = calc_edge(win_prob, odds)
    official_line = _to_float(model_row.get("k_line"))
    return {
        "pitcher": model_row.get("pitcher") or market_line.get("player_name"),
        "normalized_pitcher": _pitcher_key(model_row),
        "side": side,
        "book_key": str(market_line.get("book_key") or "").strip().lower(),
        "book_name": market_line.get("book_name"),
        "provider": market_line.get("provider"),
        "line": line,
        "official_line": official_line,
        "line_value_vs_official": _line_value_vs_official(side, line, official_line),
        "odds": odds,
        "projection": round(projection, 4),
        "projection_source": projection_source,
        "capped_projection": round(_capped_projection(projection, line), 4),
        "win_prob": round(win_prob, 4),
        "edge": round(edge, 4),
        "ev": round(ev, 4),
        "shadow_verdict": calc_verdict(ev),
        "freshness_seconds": _freshness_seconds(market_line, generated_at),
        "current_market_line_id": market_line.get("id"),
    }


def build_executable_market_shadow(
    *,
    date_str: str,
    model_rows: list[dict[str, Any]],
    current_market_lines: list[dict[str, Any]],
    params: dict[str, Any] | None = None,
    generated_at: datetime | None = None,
    stale_after_seconds: int = 900,
) -> dict[str, Any]:
    generated = generated_at or datetime.now(timezone.utc)
    mainline_rows, mainline_metadata = select_mainline_current_lines(current_market_lines, generated)
    eligible_rows = [
        row for row in mainline_rows
        if _is_eligible_line(row, generated, stale_after_seconds)
    ]
    rows_by_pitcher: dict[str, list[dict[str, Any]]] = {}
    for row in eligible_rows:
        key = str(row.get("normalized_player_name") or normalize(row.get("player_name") or "")).strip()
        if key:
            rows_by_pitcher.setdefault(key, []).append(row)

    candidates: list[dict[str, Any]] = []
    by_pitcher: list[dict[str, Any]] = []
    for model_row in model_rows:
        key = _pitcher_key(model_row)
        if not key:
            continue
        market_rows = rows_by_pitcher.get(key, [])
        projection, projection_source = _projection(model_row, params)
        current_best = _current_best_side(model_row)
        pitcher_candidates: list[dict[str, Any]] = []
        if projection is not None:
            for market_row in market_rows:
                for side in ("over", "under"):
                    candidate = _score_candidate(
                        model_row=model_row,
                        market_line=market_row,
                        side=side,
                        projection=projection,
                        projection_source=projection_source,
                        generated_at=generated,
                    )
                    if candidate:
                        pitcher_candidates.append(candidate)
        candidates.extend(pitcher_candidates)
        best_candidate = max(pitcher_candidates, key=lambda item: item["ev"]) if pitcher_candidates else None
        conflict = _conflict_type(market_rows, _to_float(model_row.get("k_line")))
        by_pitcher.append({
            "pitcher": model_row.get("pitcher"),
            "normalized_pitcher": key,
            "official_line": _to_float(model_row.get("k_line")),
            "projection": round(projection, 4) if projection is not None else None,
            "projection_source": projection_source,
            "eligible_book_count": len({row.get("book_key") for row in market_rows}),
            "line_count": len({_to_float(row.get("line")) for row in market_rows}),
            "conflict_type": conflict,
            "current_best": current_best,
            "best_candidate": best_candidate,
            "changed_from_current_best": _changed_from_current(current_best, best_candidate),
        })

    best_candidates = sorted(candidates, key=lambda item: item["ev"], reverse=True)
    conflict_counts = Counter(row["conflict_type"] for row in by_pitcher)
    summary = {
        "model_pitcher_count": len([row for row in model_rows if _pitcher_key(row)]),
        "current_market_line_count": len(current_market_lines),
        "mainline_market_line_count": len(mainline_rows),
        "eligible_market_line_count": len(eligible_rows),
        "pitchers_with_candidates": sum(1 for row in by_pitcher if row["best_candidate"]),
        "total_candidate_count": len(candidates),
        "positive_ev_candidate_count": sum(1 for row in candidates if row["ev"] > 0),
        "shadow_fire_candidate_count": sum(1 for row in candidates if str(row["shadow_verdict"]).startswith("FIRE")),
        "best_candidate_changed_count": sum(1 for row in by_pitcher if row["changed_from_current_best"]),
        "best_candidate_better_line_count": sum(
            1
            for row in by_pitcher
            if row["best_candidate"]
            and row["best_candidate"].get("line_value_vs_official") == "better_than_official"
        ),
        "ref_vs_majority_conflict_count": conflict_counts.get("ref_vs_majority", 0),
        "single_book_outlier_count": conflict_counts.get("single_book_outlier", 0),
        "line_split_count": conflict_counts.get("line_split", 0),
        "ambiguous_mainline_count": sum(
            1 for metadata in mainline_metadata.values() if metadata.get("ambiguous_line_ids")
        ),
    }
    return {
        "date": date_str,
        "generated_at": generated.astimezone(timezone.utc).isoformat(),
        "stale_after_seconds": stale_after_seconds,
        "summary": summary,
        "by_pitcher": by_pitcher,
        "candidates": best_candidates,
        "best_candidates": best_candidates[:25],
        "mainline_metadata": {
            str(key): value for key, value in mainline_metadata.items()
            if value.get("ambiguous_line_ids")
        },
        "guardrails": [
            "shadow_only",
            "uses_mainline_current_market_lines_only",
            "requires_fresh_complete_supported_book_rows",
            "does_not_change_provider_order_thresholds_staking_or_artifacts",
        ],
    }


def _changed_from_current(current_best: dict[str, Any] | None, candidate: dict[str, Any] | None) -> bool:
    if not current_best or not candidate:
        return False
    return (
        current_best.get("side") != candidate.get("side")
        or _to_float(current_best.get("line")) != _to_float(candidate.get("line"))
        or str(current_best.get("book") or "") != str(candidate.get("book_name") or "")
    )


def format_markdown_report(report: dict[str, Any], top_n: int = 15) -> str:
    summary = report["summary"]
    lines = [
        f"# Best Executable Market Shadow Audit - {report['date']}",
        "",
        f"Generated: `{report['generated_at']}`",
        "",
        "## Summary",
        "",
        f"- Model pitchers: {summary['model_pitcher_count']}",
        f"- Current market lines: {summary['current_market_line_count']}",
        f"- Mainline market lines: {summary['mainline_market_line_count']}",
        f"- Eligible fresh supported lines: {summary['eligible_market_line_count']}",
        f"- Pitchers with executable candidates: {summary['pitchers_with_candidates']}",
        f"- Candidate side/book/line rows scored: {summary['total_candidate_count']}",
        f"- Positive-EV candidates: {summary['positive_ev_candidate_count']}",
        f"- Shadow FIRE candidates: {summary['shadow_fire_candidate_count']}",
        f"- Best candidate changed from current best side/line/book: {summary['best_candidate_changed_count']}",
        f"- Best candidate uses a better line than official: {summary['best_candidate_better_line_count']}",
        f"- Ref-vs-majority conflicts: {summary['ref_vs_majority_conflict_count']}",
        f"- Single-book outlier conflicts: {summary['single_book_outlier_count']}",
        f"- Line-split conflicts: {summary['line_split_count']}",
        f"- Ambiguous mainline groups: {summary['ambiguous_mainline_count']}",
        "",
        "## Top Shadow Candidates",
        "",
        "| Pitcher | Side | Book | Line | Odds | EV | Verdict | Line Value |",
        "| --- | --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in report["candidates"][:top_n]:
        lines.append(
            "| {pitcher} | {side} | {book_name} | {line:g} | {odds:+d} | {ev:.1%} | {verdict} | {value} |".format(
                pitcher=row.get("pitcher"),
                side=str(row.get("side") or "").upper(),
                book_name=row.get("book_name"),
                line=float(row.get("line")),
                odds=int(row.get("odds")),
                ev=float(row.get("ev")),
                verdict=row.get("shadow_verdict"),
                value=row.get("line_value_vs_official"),
            )
        )
    if not report["candidates"]:
        lines.append("| none | - | - | - | - | - | - | - |")
    lines.extend([
        "",
        "## Monday cutover check",
        "",
        "- Review this beside `provider_cutover_shadow_compare` before any provider-source cutover.",
        "- Treat `single_book_outlier` differently from `ref_vs_majority` line splits.",
        "- Do not promote best-executable selection unless shadow candidates improve CLV/outcomes over enough graded rows.",
        "",
        "## Guardrail",
        "",
        "This is shadow-only evidence. It does not change live picks, thresholds, staking, provider order, notifications, dashboard artifacts, or calibration.",
    ])
    return "\n".join(lines) + "\n"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_json_url(url: str) -> Any:
    with urlopen(url, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def load_params(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = load_json(path)
    return payload if isinstance(payload, dict) else {}


def default_model_json_path(date_str: str) -> Path:
    dated = ROOT / "dashboard" / "data" / "processed" / f"{date_str}.json"
    if dated.exists():
        return dated
    return ROOT / "dashboard" / "data" / "processed" / "today.json"


def fetch_current_market_lines(date_str: str) -> list[dict[str, Any]]:
    writer = official_market_writer_from_env()
    rows = writer.select_rows(
        "current_market_lines",
        {
            "slate_date": f"eq.{date_str}",
            "market_key": "eq.pitcher_strikeouts",
            "order": "updated_at.desc",
            "limit": "10000",
        },
    )
    return [row for row in rows if isinstance(row, dict)]


def write_report(report: dict[str, Any], output_dir: Path = OUTPUT_DIR) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    date_str = report["date"]
    json_path = output_dir / f"executable_market_shadow_audit_{date_str}.json"
    markdown_path = output_dir / f"executable_market_shadow_audit_{date_str}.md"
    json_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    markdown_path.write_text(format_markdown_report(report), encoding="utf-8")
    return json_path, markdown_path


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True, help="Slate date in YYYY-MM-DD format.")
    parser.add_argument("--model-json", type=Path, help="Optional today/archive JSON with built model rows.")
    parser.add_argument("--model-json-url", help="Optional URL for built model rows, such as GitHub raw today.json.")
    parser.add_argument("--current-lines-json", type=Path, help="Optional exported current_market_lines JSON.")
    parser.add_argument("--params-json", type=Path, default=ROOT / "data" / "params.json")
    parser.add_argument("--stale-after-seconds", type=int, default=900)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--top", type=int, default=15)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv or sys.argv[1:])
    if args.model_json_url:
        model_payload = load_json_url(args.model_json_url)
    else:
        model_payload = load_json(args.model_json or default_model_json_path(args.date))
    current_lines = (
        _model_rows(load_json(args.current_lines_json))
        if args.current_lines_json
        else fetch_current_market_lines(args.date)
    )
    report = build_executable_market_shadow(
        date_str=args.date,
        model_rows=_model_rows(model_payload),
        current_market_lines=current_lines,
        params=load_params(args.params_json),
        stale_after_seconds=args.stale_after_seconds,
    )
    json_path, markdown_path = write_report(report, args.output_dir)
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    print(format_markdown_report(report, top_n=args.top))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
