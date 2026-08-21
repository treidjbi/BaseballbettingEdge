"""Build the durable shadow-only Gate C pitcher K research artifact.

This script packages the existing compact outcome dataset into committed
research artifacts. It does not change live picks, locks, thresholds, staking,
provider order, notifications, calibration, or dashboard behavior.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from analytics.diagnostics import pitcher_k_outcome_dataset as dataset  # noqa: E402


DEFAULT_OUTPUT_DIR = ROOT / "data" / "research" / "gate_c"
DEFAULT_ARTIFACT_API_URL = dataset.DEFAULT_ARTIFACT_API_URL
DEFAULT_WORKLOAD_NO_VIG_AUDIT_OUTPUT = ROOT / "analytics" / "output" / "workload_no_vig_ev_audit.md"
DEFAULT_MARKET_ANCHORED_REBUILD_OUTPUT = (
    ROOT / "analytics" / "output" / "market_anchored_k_shadow_rebuild.md"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _manifest_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _source_kwargs(
    *,
    artifact_source: str,
    artifact_api_url: str | None,
) -> dict[str, Any]:
    if artifact_source in {"hybrid", "production"}:
        return {"artifact_api_url": artifact_api_url or DEFAULT_ARTIFACT_API_URL}
    return {"artifact_api_url": None}


def _loaded_slate_dates(rows: list[dict[str, Any]]) -> set[str]:
    return {
        str(row.get("slate_date") or "").strip()
        for row in rows
        if str(row.get("slate_date") or "").strip()
    }


def _graded_history_dates(
    *,
    start_date: str,
    end_date: str | None,
    history_path: Path = dataset.PICKS_HISTORY,
    artifact_api_url: str | None = None,
) -> list[str]:
    try:
        if artifact_api_url:
            history = dataset._load_remote_json(
                dataset.artifact_api_url(artifact_api_url, "picks_history")
            )
        else:
            history = json.loads(history_path.read_text(encoding="utf-8"))
    except Exception:
        return []

    dates = {
        str(pick.get("date") or "").strip()
        for pick in history
        if str(pick.get("date") or "").strip()
        and str(pick.get("date") or "").strip() >= start_date
        and (not end_date or str(pick.get("date") or "").strip() <= end_date)
        and pick.get("result") in {"win", "loss"}
    }
    return sorted(dates)


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("dataset_key") or "").strip()
        if key and key not in deduped:
            deduped[key] = row
    return list(deduped.values())


def _build_rows(
    *,
    artifact_source: str,
    artifact_api_url: str | None,
    start_date: str,
    end_date: str | None,
    lineup_handedness_backfill_path: Path,
    actual_opportunity_backfill_path: Path,
    market_agreement_tracker_path: Path | None,
    live_market_display_path: Path | None,
    picks_history_path: Path | None = None,
) -> tuple[list[dict[str, Any]], list[str], dict[str, int]]:
    history_kwargs = (
        {"picks_history_path": picks_history_path}
        if picks_history_path is not None
        else {}
    )
    if artifact_source in {"local", "production"}:
        source_kwargs = _source_kwargs(
            artifact_source=artifact_source,
            artifact_api_url=artifact_api_url,
        )
        diagnostics: dict[str, Any] = {}
        return (
            dataset.build_dataset(
                start_date=start_date,
                end_date=end_date,
                lineup_handedness_backfill_path=lineup_handedness_backfill_path,
                actual_opportunity_backfill_path=actual_opportunity_backfill_path,
                market_agreement_tracker_path=market_agreement_tracker_path,
                live_market_display_path=live_market_display_path,
                diagnostics=diagnostics,
                **history_kwargs,
                **source_kwargs,
            ),
            [],
            dict(
                diagnostics.get("archive_outcome_reconciliation")
                or {"recovered_markets": 0, "ambiguous_markets": 0}
            ),
        )

    local_diagnostics: dict[str, Any] = {}
    local_rows = dataset.build_dataset(
        start_date=start_date,
        end_date=end_date,
        lineup_handedness_backfill_path=lineup_handedness_backfill_path,
        actual_opportunity_backfill_path=actual_opportunity_backfill_path,
        market_agreement_tracker_path=market_agreement_tracker_path,
        live_market_display_path=live_market_display_path,
        artifact_api_url=None,
        diagnostics=local_diagnostics,
        **history_kwargs,
    )
    archive_outcome_reconciliation = dict(
        local_diagnostics.get("archive_outcome_reconciliation")
        or {"recovered_markets": 0, "ambiguous_markets": 0}
    )
    local_dates = _loaded_slate_dates(local_rows)
    production_fill_dates = [
        date
        for date in _graded_history_dates(
            start_date=start_date,
            end_date=end_date,
            history_path=picks_history_path or dataset.PICKS_HISTORY,
            artifact_api_url=(
                None
                if picks_history_path is not None
                else artifact_api_url or DEFAULT_ARTIFACT_API_URL
            ),
        )
        if date not in local_dates
    ]
    production_rows: list[dict[str, Any]] = []
    for date in production_fill_dates:
        production_diagnostics: dict[str, Any] = {}
        production_rows.extend(
            dataset.build_dataset(
                start_date=date,
                end_date=date,
                lineup_handedness_backfill_path=lineup_handedness_backfill_path,
                actual_opportunity_backfill_path=actual_opportunity_backfill_path,
                market_agreement_tracker_path=market_agreement_tracker_path,
                live_market_display_path=live_market_display_path,
                artifact_api_url=artifact_api_url or DEFAULT_ARTIFACT_API_URL,
                diagnostics=production_diagnostics,
                **history_kwargs,
            )
        )
        production_outcome_counts = (
            production_diagnostics.get("archive_outcome_reconciliation") or {}
        )
        for key in ("recovered_markets", "ambiguous_markets"):
            archive_outcome_reconciliation[key] = int(
                archive_outcome_reconciliation.get(key, 0)
            ) + int(production_outcome_counts.get(key, 0))
    return (
        _dedupe_rows([*local_rows, *production_rows]),
        production_fill_dates,
        archive_outcome_reconciliation,
    )


def _manifest(
    *,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    reconciliation: dict[str, Any],
    artifact_source: str,
    artifact_api_url: str | None,
    start_date: str,
    end_date: str | None,
    jsonl_path: Path,
    summary_path: Path,
    market_agreement_tracker_path: Path | None,
    live_market_display_path: Path | None,
    picks_history_path: Path | None = None,
    production_fill_dates: list[str] | None = None,
    archive_outcome_reconciliation: dict[str, int] | None = None,
) -> dict[str, Any]:
    return {
        "artifact": "gate_c_pitcher_k_outcome_dataset",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "shadow_only": True,
        "guardrails": [
            "does_not_change_live_picks",
            "does_not_change_locks",
            "does_not_change_thresholds",
            "does_not_change_staking",
            "does_not_change_provider_order",
            "does_not_change_notifications",
            "does_not_change_calibration",
            "does_not_change_dashboard_behavior",
        ],
        "source": {
            "artifact_source": artifact_source,
            "artifact_api_url": artifact_api_url if artifact_source in {"hybrid", "production"} else None,
            "start_date": start_date,
            "end_date": end_date,
            "production_fill_dates": production_fill_dates or [],
            "market_agreement_tracker_path": _manifest_path(market_agreement_tracker_path),
            "live_market_display_path": _manifest_path(live_market_display_path),
            **(
                {"picks_history_path": _manifest_path(picks_history_path)}
                if picks_history_path is not None
                else {}
            ),
        },
        "row_count": len(rows),
        "tracked_pick_rows": int(summary.get("tracked_pick_rows", 0)),
        "duplicate_dataset_keys": int(summary.get("duplicate_dataset_keys", 0)),
        "loaded_slate_dates": sorted(_loaded_slate_dates(rows)),
        "summary_counts": summary,
        "reconciliation": reconciliation,
        "archive_outcome_reconciliation": archive_outcome_reconciliation
        or {"recovered_markets": 0, "ambiguous_markets": 0},
        "files": {
            "jsonl": _manifest_path(jsonl_path),
            "summary": _manifest_path(summary_path),
        },
        "jsonl_sha256": _sha256(jsonl_path),
        "summary_sha256": _sha256(summary_path),
    }


def build_research_artifact(
    *,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    artifact_source: str = "hybrid",
    artifact_api_url: str | None = DEFAULT_ARTIFACT_API_URL,
    start_date: str = dataset.CLEAN_WINDOW_START,
    end_date: str | None = None,
    lineup_handedness_backfill_path: Path = dataset.LINEUP_HANDEDNESS_BACKFILL,
    actual_opportunity_backfill_path: Path = dataset.ACTUAL_OPPORTUNITY_BACKFILL,
    market_agreement_tracker_path: Path | None = dataset.MARKET_AGREEMENT_TRACKER,
    live_market_display_path: Path | None = dataset.LIVE_MARKET_DISPLAY,
    picks_history_path: Path | None = None,
) -> dict[str, Any]:
    if artifact_source not in {"hybrid", "local", "production"}:
        raise ValueError("artifact_source must be hybrid, local, or production")

    source_kwargs = _source_kwargs(
        artifact_source=artifact_source,
        artifact_api_url=artifact_api_url,
    )
    rows, production_fill_dates, archive_outcome_reconciliation = _build_rows(
        artifact_source=artifact_source,
        artifact_api_url=artifact_api_url,
        start_date=start_date,
        end_date=end_date,
        lineup_handedness_backfill_path=lineup_handedness_backfill_path,
        actual_opportunity_backfill_path=actual_opportunity_backfill_path,
        market_agreement_tracker_path=market_agreement_tracker_path,
        live_market_display_path=live_market_display_path,
        picks_history_path=picks_history_path,
    )
    validation_errors = [
        (row.get("dataset_key"), errors)
        for row in rows
        if (errors := dataset.validate_dataset_row(row))
    ]
    if validation_errors:
        raise SystemExit(f"Dataset validation failed: {validation_errors[:5]}")

    summary = dataset.build_summary(rows)
    summary["archive_outcome_reconciliation"] = archive_outcome_reconciliation
    reconciliation = dataset.reconcile_picks_history(
        rows,
        start_date=start_date,
        history_path=picks_history_path or dataset.PICKS_HISTORY,
        artifact_api_url=(
            None if picks_history_path is not None else source_kwargs["artifact_api_url"]
        ),
        included_slate_dates=(
            _loaded_slate_dates(rows)
            if source_kwargs["artifact_api_url"] or picks_history_path is not None
            else None
        ),
    )
    summary_for_report = dict(summary)
    summary_for_report.update(reconciliation)

    jsonl_path = output_dir / "pitcher_k_outcome_dataset.jsonl"
    summary_path = output_dir / "pitcher_k_outcome_dataset_summary.md"
    manifest_path = output_dir / "pitcher_k_outcome_dataset_manifest.json"

    dataset.write_jsonl(rows, jsonl_path)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(dataset.render_summary(summary_for_report), encoding="utf-8")
    manifest = _manifest(
        rows=rows,
        summary=summary,
        reconciliation=reconciliation,
        artifact_source=artifact_source,
        artifact_api_url=source_kwargs["artifact_api_url"],
        start_date=start_date,
        end_date=end_date,
        jsonl_path=jsonl_path,
        summary_path=summary_path,
        market_agreement_tracker_path=market_agreement_tracker_path,
        live_market_display_path=live_market_display_path,
        picks_history_path=picks_history_path,
        production_fill_dates=production_fill_dates,
        archive_outcome_reconciliation=archive_outcome_reconciliation,
    )
    _write_json(manifest_path, manifest)

    return {
        "jsonl_path": jsonl_path,
        "summary_path": summary_path,
        "manifest_path": manifest_path,
        "manifest": manifest,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build durable shadow-only Gate C research artifacts.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--artifact-source",
        choices=("hybrid", "local", "production"),
        default="hybrid",
    )
    parser.add_argument(
        "--artifact-api-url",
        default=os.environ.get("BBE_ARTIFACT_API_URL", "").strip() or DEFAULT_ARTIFACT_API_URL,
    )
    parser.add_argument(
        "--picks-history",
        type=Path,
        help="Optional staged picks_history.json; avoids oversized remote history reads.",
    )
    parser.add_argument("--start-date", default=dataset.CLEAN_WINDOW_START)
    parser.add_argument("--end-date")
    parser.add_argument(
        "--lineup-handedness-backfill",
        type=Path,
        default=dataset.LINEUP_HANDEDNESS_BACKFILL,
    )
    parser.add_argument(
        "--actual-opportunity-backfill",
        type=Path,
        default=dataset.ACTUAL_OPPORTUNITY_BACKFILL,
    )
    parser.add_argument(
        "--market-agreement-tracker",
        type=Path,
        default=dataset.MARKET_AGREEMENT_TRACKER,
        help="Optional JSONL export from market_agreement_tracker used to enrich Gate C rows.",
    )
    parser.add_argument(
        "--live-market-display",
        type=Path,
        default=dataset.LIVE_MARKET_DISPLAY,
        help="Optional JSON export from live_market_display_state used for book-board confidence fields.",
    )
    parser.add_argument(
        "--run-workload-no-vig-audit",
        action="store_true",
        help="After writing the Gate C dataset, rebuild the shadow workload/no-vig audit report.",
    )
    parser.add_argument(
        "--run-market-anchored-rebuild",
        action="store_true",
        help="After writing the Gate C dataset, rebuild the shadow market-anchored K report.",
    )
    parser.add_argument(
        "--market-anchored-rebuild-output",
        type=Path,
        default=DEFAULT_MARKET_ANCHORED_REBUILD_OUTPUT,
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    build_kwargs = dict(
        output_dir=args.output_dir,
        artifact_source=args.artifact_source,
        artifact_api_url=args.artifact_api_url,
        start_date=args.start_date,
        end_date=args.end_date,
        lineup_handedness_backfill_path=args.lineup_handedness_backfill,
        actual_opportunity_backfill_path=args.actual_opportunity_backfill,
        market_agreement_tracker_path=args.market_agreement_tracker,
        live_market_display_path=args.live_market_display,
    )
    if args.picks_history is not None:
        build_kwargs["picks_history_path"] = args.picks_history
    result = build_research_artifact(**build_kwargs)
    if args.run_workload_no_vig_audit:
        from analytics.diagnostics import workload_no_vig_ev_audit  # noqa: WPS433

        workload_no_vig_ev_audit.main([
            "--input",
            str(args.output_dir / "pitcher_k_outcome_dataset.jsonl"),
            "--output",
            str(DEFAULT_WORKLOAD_NO_VIG_AUDIT_OUTPUT),
        ])
    if args.run_market_anchored_rebuild:
        from analytics.diagnostics import market_anchored_k_shadow_rebuild  # noqa: WPS433

        market_anchored_k_shadow_rebuild.main([
            "--input",
            str(args.output_dir / "pitcher_k_outcome_dataset.jsonl"),
            "--output",
            str(args.market_anchored_rebuild_output),
        ])
    manifest = result["manifest"]
    print(
        "Gate C research artifact written: "
        f"rows={manifest['row_count']} "
        f"tracked={manifest['tracked_pick_rows']} "
        f"duplicates={manifest['duplicate_dataset_keys']} "
        f"matched={manifest['reconciliation'].get('matched_pick_rows', 0)}/"
        f"{manifest['reconciliation'].get('graded_pick_rows', 0)} "
        f"output_dir={Path(result['manifest_path']).parent}"
    )


if __name__ == "__main__":
    main()
