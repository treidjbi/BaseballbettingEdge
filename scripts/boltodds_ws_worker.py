"""Shadow-only BoltOdds WebSocket worker.

This script records market observations to Supabase sidecar tables. It must not
modify production pipeline artifacts or dashboard data.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from typing import Any
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from market_infra.boltodds_client import (  # noqa: E402
    BOLTODDS_WS_URL,
    build_subscribe_message,
    get_json,
    market_aliases_from_env,
    target_books_from_env,
)
from market_infra.boltodds_snapshot import snapshots_from_boltodds_message  # noqa: E402
from market_infra.live_feed_health import (  # noqa: E402
    append_raw_sample,
    build_heartbeat_row,
    should_flush_batch,
)
from market_infra.provider_audit import build_provider_coverage_audit  # noqa: E402
from market_infra.supabase_writer import SupabaseMarketWriter  # noqa: E402
from pipeline.name_utils import normalize  # noqa: E402
from scripts.probe_boltodds_markets import build_probe_summary  # noqa: E402


WORKER_PATH = "scripts/boltodds_ws_worker.py"
DEFAULT_PRODUCTION_ARTIFACT_URL = (
    "https://raw.githubusercontent.com/treidjbi/BaseballBettingEdge/"
    "main/dashboard/data/processed/today.json"
)


@dataclass(frozen=True)
class ProductionContext:
    slate_date: str
    production_payload: dict | None
    production_path: str | None
    production_pitcher_names: set[str]
    rotated: bool = False


def _env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise EnvironmentError(f"{name} is required")
    return value


def _optional_env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _optional_int_env(name: str, default: int) -> int:
    return int(_optional_env(name, str(default)) or str(default))


def _optional_float_env(name: str, default: float) -> float:
    return float(_optional_env(name, str(default)) or str(default))


def _batch_size_from_env(default: int = 100) -> int:
    value = _optional_env("BOLTODDS_BATCH_SIZE")
    if value:
        return int(value)
    return _optional_int_env("BOLTODDS_WS_BATCH_SIZE", default)


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_production_artifact(
    slate_date: str | None = None,
    root: Path = ROOT,
    artifact_url: str | None = None,
) -> tuple[dict | None, str | None]:
    if artifact_url:
        try:
            with urlopen(artifact_url, timeout=20) as response:
                return json.loads(response.read().decode("utf-8")), artifact_url
        except Exception as error:
            print(
                f"Warning: remote artifact fetch failed ({error}); falling back to local artifact",
                file=sys.stderr,
            )

    candidates: list[Path] = []
    if slate_date:
        candidates.append(Path("dashboard") / "data" / "processed" / f"{slate_date}.json")
    candidates.append(Path("dashboard") / "data" / "processed" / "today.json")

    for relative_path in candidates:
        path = root / relative_path
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8")), relative_path.as_posix()
    return None, None


def _production_pitcher_names(production_payload: dict | None) -> set[str]:
    names: set[str] = set()
    for row in (production_payload or {}).get("pitchers") or []:
        if not isinstance(row, dict):
            continue
        name = str(row.get("pitcher") or "").strip()
        if name:
            names.add(normalize(name))
    return names


def load_production_context(
    *,
    slate_date_override: str | None,
    artifact_url: str | None,
) -> ProductionContext:
    production_payload, production_path = _load_production_artifact(
        slate_date_override,
        artifact_url=artifact_url or None,
    )
    slate_date = slate_date_override or str(
        (production_payload or {}).get("date") or ""
    ).strip()
    if not slate_date:
        raise EnvironmentError("SLATE_DATE is required when today.json has no date")
    return ProductionContext(
        slate_date=slate_date,
        production_payload=production_payload,
        production_path=production_path,
        production_pitcher_names=_production_pitcher_names(production_payload),
    )


def refresh_production_context_if_advanced(
    current: ProductionContext,
    *,
    slate_date_override: str | None,
    artifact_url: str | None,
) -> ProductionContext:
    if slate_date_override:
        return current
    try:
        refreshed = load_production_context(
            slate_date_override=None,
            artifact_url=artifact_url,
        )
    except Exception as error:
        print(
            f"Warning: production artifact refresh failed ({error}); keeping {current.slate_date}",
            file=sys.stderr,
        )
        return current
    if refreshed.slate_date <= current.slate_date:
        return current
    return ProductionContext(
        slate_date=refreshed.slate_date,
        production_payload=refreshed.production_payload,
        production_path=refreshed.production_path,
        production_pitcher_names=refreshed.production_pitcher_names,
        rotated=True,
    )


def build_run_rows(
    slate_date: str,
    status: str,
    request_count: int,
    books_seen: set[str] | list[str],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    row = {
        "provider": "boltodds",
        "mode": "shadow_stream",
        "slate_date": slate_date,
        "status": status,
        "request_count": request_count,
        "books_seen": sorted(str(book) for book in books_seen if str(book).strip()),
        "metadata": metadata,
    }
    if status in {"completed", "failed"}:
        row["completed_at"] = _now_utc()
    return row


def finalize_run(
    writer: SupabaseMarketWriter,
    *,
    run_id: str,
    slate_date: str,
    status: str,
    request_count: int,
    books_seen: set[str] | list[str],
    metadata: dict[str, Any],
    error_message: str = "",
) -> dict[str, Any]:
    row = build_run_rows(
        slate_date,
        status=status,
        request_count=request_count,
        books_seen=books_seen,
        metadata=metadata,
    )
    row["id"] = run_id
    if error_message:
        row["error_message"] = error_message[:1000]
    writer.upsert_rows("market_provider_runs", [row], on_conflict="id")
    return row


def write_heartbeat(
    writer: SupabaseMarketWriter,
    *,
    run_id: str | None,
    slate_date: str,
    event: str,
    observed_at: str | None = None,
    books_seen: set[str] | list[str] | None = None,
    last_message_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    row = build_heartbeat_row(
        provider="boltodds",
        mode="shadow_stream",
        slate_date=slate_date,
        run_id=run_id,
        observed_at=observed_at or _now_utc(),
        event=event,
        books_seen=books_seen or [],
        last_message_at=last_message_at,
        metadata=metadata,
    )
    try:
        writer.insert_rows("market_feed_heartbeats", [row])
    except Exception:
        pass
    return row


def _coverage_audit_row(
    *,
    run_id: str,
    slate_date: str,
    snapshots: list[dict[str, Any]],
    production_payload: dict | None,
    books_seen: set[str] | list[str],
    target_event_count: int,
    target_books: dict[str, str] | None = None,
) -> dict[str, Any]:
    audit = build_provider_coverage_audit(
        snapshots,
        production_payload,
        target_books=target_books,
    )
    metadata = {
        **audit["metadata"],
        "snapshot_rows": len(snapshots),
        "worker": WORKER_PATH,
    }
    return {
        "run_id": run_id,
        "slate_date": slate_date,
        "provider": "boltodds",
        "target_books": audit["target_books"],
        "books_seen": sorted(str(book) for book in books_seen if str(book).strip()),
        "target_event_count": target_event_count,
        "parsed_pitcher_prop_count": audit["parsed_pitcher_prop_count"],
        "complete_pitcher_line_groups": audit["complete_pitcher_line_groups"],
        "same_line_overlap_count": audit["same_line_overlap_count"],
        "line_conflict_count": audit["line_conflict_count"],
        "missing_target_books": audit["missing_target_books"],
        "metadata": metadata,
    }


def write_snapshot_batch(
    writer: SupabaseMarketWriter,
    run_id: str,
    slate_date: str,
    snapshots: list[dict[str, Any]],
    production_payload: dict | None,
    books_seen: set[str] | list[str],
    target_event_count: int,
    target_books: dict[str, str] | None = None,
) -> dict[str, int]:
    if not snapshots:
        return {"snapshot_count": 0}

    for snapshot in snapshots:
        snapshot["run_id"] = run_id

    writer.upsert_rows("market_snapshots", snapshots, on_conflict="dedupe_key")
    writer.insert_rows("provider_coverage_audits", [
        _coverage_audit_row(
            run_id=run_id,
            slate_date=slate_date,
            snapshots=snapshots,
            production_payload=production_payload,
            books_seen=books_seen,
            target_event_count=target_event_count,
            target_books=target_books,
        )
    ])
    return {"snapshot_count": len(snapshots)}


def _message_payload(raw_message: Any) -> dict[str, Any] | None:
    payloads = _message_payloads(raw_message)
    return payloads[0] if payloads else None


def _message_payloads(raw_message: Any) -> list[dict[str, Any]]:
    if isinstance(raw_message, bytes):
        raw_message = raw_message.decode("utf-8")
    if not isinstance(raw_message, str):
        return []
    if raw_message.strip().lower() == "ping":
        return [{"action": "ping"}]
    try:
        payload = json.loads(raw_message)
    except json.JSONDecodeError:
        return []
    if isinstance(payload, dict):
        return [payload]
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _message_book(payload: dict[str, Any]) -> str | None:
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    book = str(data.get("sportsbook") or "").strip().lower()
    return book or None


def _message_event_id(payload: dict[str, Any]) -> str | None:
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    info = data.get("info")
    if not isinstance(info, dict):
        return None
    event_id = str(info.get("id") or "").strip()
    return event_id or None


def _load_websockets_connect():
    try:
        import websockets
    except ImportError as exc:
        raise RuntimeError(
            "websockets is required for the BoltOdds live worker; install "
            "the isolated live dependencies with `pip install -r "
            "requirements-live.txt`."
        ) from exc

    return websockets.connect


async def _connect_websocket(url: str):
    return _load_websockets_connect()(url)


async def run_worker() -> dict[str, Any]:
    api_key = _env("BOLTODDS_API_KEY")
    supabase_url = _env("SUPABASE_URL")
    service_role_key = _env("SUPABASE_SERVICE_ROLE_KEY")
    writer = SupabaseMarketWriter(supabase_url, service_role_key)

    slate_date_override = _optional_env("SLATE_DATE") or None
    artifact_url = (
        _optional_env("BOLTODDS_ARTIFACT_URL")
        or _optional_env("LIVE_ARTIFACT_URL")
        or ("" if slate_date_override else DEFAULT_PRODUCTION_ARTIFACT_URL)
    )
    context = load_production_context(
        slate_date_override=slate_date_override,
        artifact_url=artifact_url or None,
    )

    target_books = target_books_from_env()
    aliases = market_aliases_from_env()
    request_count = 0

    started_rows = writer.insert_rows("market_provider_runs", [
        build_run_rows(
            context.slate_date,
            status="started",
            request_count=request_count,
            books_seen=[],
            metadata={
                "worker": WORKER_PATH,
                "production_artifact_path": context.production_path,
                "production_artifact_date": context.slate_date,
                "production_pitcher_count": len(context.production_pitcher_names),
            },
        )
    ])
    run_id = started_rows[0]["id"]
    write_heartbeat(
        writer,
        run_id=run_id,
        slate_date=context.slate_date,
        event="started",
        metadata={
            "worker": WORKER_PATH,
            "production_artifact_path": context.production_path,
            "production_artifact_date": context.slate_date,
            "production_pitcher_count": len(context.production_pitcher_names),
        },
    )

    books_seen: set[str] = set()
    event_ids: set[str] = set()
    snapshots: list[dict[str, Any]] = []
    raw_payload_samples: list[Any] = []
    total_snapshots = 0
    message_count = 0
    last_message_at: str | None = None
    status = "completed"
    error_message = ""
    probe_summary: dict[str, Any] | None = None
    last_flush_monotonic = monotonic()
    last_message_heartbeat_monotonic = last_flush_monotonic
    last_artifact_refresh_monotonic = last_flush_monotonic
    artifact_refresh_seconds = _optional_float_env(
        "BOLTODDS_ARTIFACT_REFRESH_SECONDS",
        300.0,
    )

    def refresh_context_if_due(now_monotonic: float) -> None:
        nonlocal context, last_artifact_refresh_monotonic
        if artifact_refresh_seconds <= 0:
            return
        if (now_monotonic - last_artifact_refresh_monotonic) < artifact_refresh_seconds:
            return
        last_artifact_refresh_monotonic = now_monotonic
        refreshed_context = refresh_production_context_if_advanced(
            context,
            slate_date_override=slate_date_override,
            artifact_url=artifact_url or None,
        )
        if not refreshed_context.rotated:
            return
        context = refreshed_context
        write_heartbeat(
            writer,
            run_id=run_id,
            slate_date=context.slate_date,
            event="slate_rotated",
            books_seen=books_seen,
            last_message_at=last_message_at,
            metadata={
                "production_artifact_path": context.production_path,
                "production_artifact_date": context.slate_date,
                "production_pitcher_count": len(context.production_pitcher_names),
            },
        )

    async def flush() -> None:
        nonlocal snapshots, total_snapshots, last_flush_monotonic
        result = write_snapshot_batch(
            writer,
            run_id,
            context.slate_date,
            snapshots,
            context.production_payload,
            books_seen,
            len(event_ids),
            target_books,
        )
        snapshot_count = result["snapshot_count"]
        total_snapshots += snapshot_count
        snapshots = []
        last_flush_monotonic = monotonic()
        if snapshot_count:
            write_heartbeat(
                writer,
                run_id=run_id,
                slate_date=context.slate_date,
                event="flush",
                books_seen=books_seen,
                last_message_at=last_message_at,
                metadata={
                    "message_count": message_count,
                    "snapshot_count": snapshot_count,
                    "total_snapshot_rows": total_snapshots,
                },
            )

    try:
        info = get_json("get_info", api_key=api_key)
        request_count += 1
        markets = get_json(
            "get_markets",
            api_key=api_key,
            params={"sports": "MLB", "sportsbooks": ",".join(target_books)},
        )
        request_count += 1
        probe_summary = build_probe_summary(info, markets, target_books, aliases)
        if not probe_summary["starter_ready"]:
            raise RuntimeError(
                "BoltOdds starter probe is not ready: "
                + "; ".join(probe_summary["blocking_reasons"])
            )

        selected_markets = probe_summary["selected_markets"]
        subscribe_message = build_subscribe_message(
            sports=["MLB"],
            sportsbooks=list(target_books),
            markets=selected_markets,
        )
        allowed_markets = {market.casefold() for market in selected_markets}
        batch_size = _batch_size_from_env(100)
        flush_seconds = _optional_float_env("BOLTODDS_FLUSH_SECONDS", 30.0)
        raw_sample_limit = _optional_int_env("BOLTODDS_RAW_SAMPLE_LIMIT", 5)
        # Render keeps this worker open; set BOLTODDS_WS_MAX_MESSAGES for manual bounded runs.
        max_messages = _optional_int_env("BOLTODDS_WS_MAX_MESSAGES", 0)
        ws_url = f"{_optional_env('BOLTODDS_WS_URL', BOLTODDS_WS_URL)}?key={api_key}"

        async with await _connect_websocket(ws_url) as websocket:
            await websocket.send(json.dumps(subscribe_message))
            write_heartbeat(
                writer,
                run_id=run_id,
                slate_date=context.slate_date,
                event="ready",
                metadata={
                    "selected_markets": selected_markets,
                    "target_books": list(target_books),
                    "flush_seconds": flush_seconds,
                    "batch_size": batch_size,
                    "raw_sample_limit": raw_sample_limit,
                    "artifact_refresh_seconds": artifact_refresh_seconds,
                    "production_artifact_path": context.production_path,
                    "production_artifact_date": context.slate_date,
                    "production_pitcher_count": len(context.production_pitcher_names),
                },
            )
            while True:
                if max_messages and message_count >= max_messages:
                    break
                try:
                    raw_message = await asyncio.wait_for(
                        websocket.recv(),
                        timeout=flush_seconds if flush_seconds > 0 else None,
                    )
                except asyncio.TimeoutError:
                    now_monotonic = monotonic()
                    refresh_context_if_due(now_monotonic)
                    if should_flush_batch(
                        pending_count=len(snapshots),
                        batch_size=batch_size,
                        last_flush_monotonic=last_flush_monotonic,
                        now_monotonic=now_monotonic,
                        flush_seconds=flush_seconds,
                    ):
                        await flush()
                    continue

                for payload in _message_payloads(raw_message):
                    message_count += 1
                    if payload.get("action") == "ping":
                        continue

                    last_message_at = _now_utc()
                    raw_payload_samples = append_raw_sample(
                        raw_payload_samples,
                        payload,
                        limit=raw_sample_limit,
                    )
                    book = _message_book(payload)
                    if book:
                        books_seen.add(book)
                    event_id = _message_event_id(payload)
                    if event_id:
                        event_ids.add(event_id)

                    now_monotonic = monotonic()
                    refresh_context_if_due(now_monotonic)
                    rows = snapshots_from_boltodds_message(
                        payload,
                        observed_at=_now_utc(),
                        allowed_markets=allowed_markets,
                        target_books=target_books,
                        allowed_player_names=context.production_pitcher_names,
                    )
                    snapshots.extend(rows)
                    if (now_monotonic - last_message_heartbeat_monotonic) >= flush_seconds:
                        write_heartbeat(
                            writer,
                            run_id=run_id,
                            slate_date=context.slate_date,
                            event="message",
                            books_seen=books_seen,
                            last_message_at=last_message_at,
                            metadata={
                                "message_count": message_count,
                                "pending_snapshot_rows": len(snapshots),
                            },
                        )
                        last_message_heartbeat_monotonic = now_monotonic
                    if should_flush_batch(
                        pending_count=len(snapshots),
                        batch_size=batch_size,
                        last_flush_monotonic=last_flush_monotonic,
                        now_monotonic=now_monotonic,
                        flush_seconds=flush_seconds,
                    ):
                        await flush()
    except Exception as exc:
        status = "failed"
        error_message = str(exc)[:1000]
        raise
    finally:
        active_exception = sys.exc_info()[1]
        final_flush_error = None
        try:
            await flush()
        except Exception as exc:
            status = "failed"
            final_flush_error = exc
            if not error_message:
                error_message = str(exc)[:1000]
        write_heartbeat(
            writer,
            run_id=run_id,
            slate_date=context.slate_date,
            event=status,
            books_seen=books_seen,
            last_message_at=last_message_at,
            metadata={
                "message_count": message_count,
                "snapshot_rows": total_snapshots,
                "error_message": error_message,
            },
        )
        metadata = {
            "worker": WORKER_PATH,
            "message_count": message_count,
            "target_event_count": len(event_ids),
            "snapshot_rows": total_snapshots,
            "production_artifact_path": context.production_path,
            "production_artifact_date": context.slate_date,
            "production_pitcher_count": len(context.production_pitcher_names),
            "raw_payload_samples": raw_payload_samples,
        }
        if probe_summary is not None:
            metadata["probe_summary"] = probe_summary
        finalize_run(
            writer,
            run_id=run_id,
            slate_date=context.slate_date,
            status=status,
            request_count=request_count,
            books_seen=books_seen,
            metadata=metadata,
            error_message=error_message,
        )
        if final_flush_error is not None and active_exception is None:
            raise final_flush_error

    return {
        "run_id": run_id,
        "slate_date": context.slate_date,
        "snapshot_count": total_snapshots,
        "books_seen": sorted(books_seen),
        "target_event_count": len(event_ids),
        "request_count": request_count,
    }


def main() -> int:
    asyncio.run(run_worker())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
