# PropLine Fallback And Model Signal Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make PropLine the first fallback after TheRundown, keep The Odds as second fallback, and add shadow diagnostics for source health, line movement, prior-model comparison, and seasonal K environment without changing live projection math yet.

**2026-05-05 execution note:** The provider fallback swap and same-pitcher duplicate line guard were implemented first. The broader shadow diagnostics in Tasks 2-5 remain deferred and should stay non-live until explicitly picked up.

**Architecture:** Keep TheRundown as the primary source and preserve current static JSON/dashboard contracts. Invert the fallback order inside `pipeline/fetch_odds.py`, continue merging source metadata into `book_odds` and `odds_source`, and add diagnostics that answer model questions from history before touching `lambda`, thresholds, or staking. Webhooks remain a later infrastructure option, not part of this implementation.

**Tech Stack:** Python 3.11, pytest, GitHub Actions, TheRundown API, PropLine API, The Odds API, committed JSON artifacts under `dashboard/data/processed/`, `data/picks_history.json`, diagnostics under `analytics/diagnostics/`.

---

## Current Read

As of the 2026-05-05 morning health check:

- The Odds fallback is unhealthy in production logs: `401` and/or zero remaining quota.
- PropLine is returning usable FanDuel/DraftKings coverage and should be tried before The Odds while this state persists.
- Current fallback order in `pipeline/fetch_odds.py` is:

```text
TheRundown primary -> The Odds fallback -> PropLine fallback
```

- Desired order is:

```text
TheRundown primary -> PropLine fallback -> The Odds fallback
```

- The project already captures some line movement through `opening_odds_source == "preview"` and `movement_conf`, but the current clean-window activation is sparse. This means movement is considered, but not deeply enough yet to trust it as a primary model/ranking driver.
- The old model may look better in all-history results, especially `FIRE 1u`, but that comparison is not clean because the system changed odds semantics, SwStr transport, quality gates, provider mix, and calibration boundary. We need a same-window replay before reverting.

---

## Non-Goals

- Do not make PropLine primary.
- Do not add PropLine webhooks yet.
- Do not change verdict thresholds.
- Do not change the staking ladder.
- Do not change `formula_change_date`.
- Do not hard-code month-level K averages into live lambda.
- Do not promote batter handedness splits into live projection in this plan.

---

## File Plan

Modify:

- `pipeline/fetch_odds.py` - invert fallback order, add shared fallback runner/status logging, keep source metadata.
- `tests/test_fetch_odds.py` - add tests proving PropLine is attempted before The Odds and The Odds only runs when PropLine still leaves fallback coverage missing.
- `AGENTS.md` - update provider fallback order and webhook note.

Create:

- `analytics/diagnostics/source_fallback_health.py` - summarize recent provider/source usage from artifacts and logs where available.
- `tests/test_source_fallback_health.py` - test artifact summarization behavior.
- `analytics/diagnostics/line_movement_shadow_audit.py` - analyze movement confidence, preview coverage, steam direction, and CLV-like outcomes from history/artifacts.
- `tests/test_line_movement_shadow_audit.py` - test movement bucket calculations.
- `analytics/diagnostics/model_replay_shadow_audit.py` - compare current clean-window results against a simple frozen-prior model shape without changing picks.
- `tests/test_model_replay_shadow_audit.py` - test replay summary helpers.
- `analytics/diagnostics/seasonal_k_environment_audit.py` - check whether league K/start environment has a meaningful month/week prior signal.
- `tests/test_seasonal_k_environment_audit.py` - test season bucket aggregation.

Write local-only outputs when run:

- `analytics/output/source_fallback_health.md`
- `analytics/output/line_movement_shadow_audit.md`
- `analytics/output/model_replay_shadow_audit.md`
- `analytics/output/seasonal_k_environment_audit.md`

---

## Task 1: Swap Provider Fallback Order

**Files:**

- Modify: `pipeline/fetch_odds.py`
- Modify: `tests/test_fetch_odds.py`

- [ ] **Step 1: Add a failing test for PropLine-first fallback**

Append this test to `TestPropLineFallback` in `tests/test_fetch_odds.py`:

```python
def test_fetch_odds_tries_propline_before_the_odds_when_coverage_missing(self):
    rundown_payload = {"events": [_make_event("Gerrit Cole", 7.5, -112, -108)]}
    propline = _parse_propline_event_props(self._propline_event())

    with patch.dict("os.environ", {"ODDS_API_KEY": "odds-key", "PROPLINE_API_KEY": "pl-key"}):
        with patch("fetch_odds.throttled_get", return_value=rundown_payload):
            with patch("fetch_odds._fetch_propline_fallback_props", return_value=propline) as mock_propline:
                with patch("fetch_odds._fetch_the_odds_fallback_props") as mock_the_odds:
                    result = fetch_odds("2026-05-01")

    mock_propline.assert_called_once_with("2026-05-01")
    mock_the_odds.assert_not_called()
    assert result[0]["book_odds"]["BetRivers"]["over"] == -115
    assert result[0]["odds_source"] == "therundown+propline"
```

- [ ] **Step 2: Add a failing test for The Odds second fallback**

Append this test to `TestPropLineFallback`:

```python
def test_fetch_odds_tries_the_odds_after_propline_still_missing_coverage(self):
    rundown_payload = {"events": [_make_event("Gerrit Cole", 7.5, -112, -108)]}
    the_odds = _parse_the_odds_event_props(TestTheOddsFallback()._the_odds_event())

    with patch.dict("os.environ", {"ODDS_API_KEY": "odds-key", "PROPLINE_API_KEY": "pl-key"}):
        with patch("fetch_odds.throttled_get", return_value=rundown_payload):
            with patch("fetch_odds._fetch_propline_fallback_props", return_value=[]) as mock_propline:
                with patch("fetch_odds._fetch_the_odds_fallback_props", return_value=the_odds) as mock_the_odds:
                    result = fetch_odds("2026-05-01")

    mock_propline.assert_called_once_with("2026-05-01")
    mock_the_odds.assert_called_once_with("2026-05-01")
    assert result[0]["ref_book"] == "FanDuel"
    assert result[0]["book_odds"]["DraftKings"]["over"] == 115
    assert result[0]["odds_source"] == "therundown+the_odds"
```

- [ ] **Step 3: Run the focused tests and verify they fail**

Run:

```bash
python -m pytest tests/test_fetch_odds.py::TestPropLineFallback -q
```

Expected:

```text
FAILED test_fetch_odds_tries_propline_before_the_odds_when_coverage_missing
FAILED test_fetch_odds_tries_the_odds_after_propline_still_missing_coverage
```

- [ ] **Step 4: Invert fallback order in `fetch_odds`**

Replace the fallback block in `pipeline/fetch_odds.py` with this implementation:

```python
    if _propline_key() and _needs_fallback_coverage(all_props):
        try:
            fallback_props = _fetch_propline_fallback_props(date_str)
            if fallback_props:
                all_props = _merge_propline_fallback_props(all_props, fallback_props)
        except Exception as e:
            log.warning("PropLine fallback failed for %s: %s", date_str, e)
    elif not _propline_key() and _needs_fallback_coverage(all_props):
        log.info("PropLine fallback skipped: PROPLINE_API_KEY not set")

    if _the_odds_key() and _needs_fallback_coverage(all_props):
        try:
            fallback_props = _fetch_the_odds_fallback_props(date_str)
            if fallback_props:
                all_props = _merge_the_odds_fallback_props(all_props, fallback_props)
        except Exception as e:
            log.warning("The Odds fallback failed for %s: %s", date_str, e)
    elif not _the_odds_key() and _needs_fallback_coverage(all_props):
        log.info("The Odds fallback skipped: ODDS_API_KEY not set")
```

- [ ] **Step 5: Update the existing The Odds error test**

The current test named `test_fetch_odds_falls_back_to_propline_when_the_odds_errors` describes the old order. Replace it with:

```python
def test_fetch_odds_continues_to_the_odds_when_propline_errors(self):
    import requests

    rundown_payload = {"events": [_make_event("Gerrit Cole", 7.5, -112, -108)]}
    the_odds = _parse_the_odds_event_props(TestTheOddsFallback()._the_odds_event())

    with patch.dict("os.environ", {"ODDS_API_KEY": "odds-key", "PROPLINE_API_KEY": "pl-key"}):
        with patch("fetch_odds.throttled_get", return_value=rundown_payload):
            with patch("fetch_odds._fetch_propline_fallback_props", side_effect=requests.HTTPError("429")):
                with patch("fetch_odds._fetch_the_odds_fallback_props", return_value=the_odds) as mock_the_odds:
                    result = fetch_odds("2026-05-01")

    mock_the_odds.assert_called_once_with("2026-05-01")
    assert result[0]["book_odds"]["FanDuel"]["over"] == 112
    assert result[0]["odds_source"] == "therundown+the_odds"
```

- [ ] **Step 6: Run focused and full odds tests**

Run:

```bash
python -m pytest tests/test_fetch_odds.py -q
```

Expected:

```text
passed
```

- [ ] **Step 7: Commit**

Run:

```bash
git add pipeline/fetch_odds.py tests/test_fetch_odds.py
git commit -m "fix: prefer propline before odds fallback"
```

---

## Task 2: Update Provider Docs And Source Health Notes

**Files:**

- Modify: `AGENTS.md`
- Create: `analytics/diagnostics/source_fallback_health.py`
- Create: `tests/test_source_fallback_health.py`

- [ ] **Step 1: Update AGENTS provider order**

In `AGENTS.md`, replace the current fallback order text with:

```markdown
Current fallback order: TheRundown primary -> PropLine fallback -> The Odds FD/DK fallback.

Use PropLine before The Odds while The Odds is quota-exhausted or unauthorized.
Do not treat this as a full provider migration. TheRundown remains primary,
and PropLine webhook adoption remains a later infrastructure decision after
polling coverage proves reliable.
```

- [ ] **Step 2: Create source fallback health diagnostic**

Create `analytics/diagnostics/source_fallback_health.py`:

```python
"""Summarize provider/source usage from dashboard artifacts."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "dashboard" / "data" / "processed"


def load_artifact(date_str: str) -> dict:
    return json.loads((DATA_DIR / f"{date_str}.json").read_text(encoding="utf-8"))


def summarize_artifact(artifact: dict) -> dict:
    pitchers = artifact.get("pitchers") or []
    source_counts = Counter(str(row.get("odds_source") or "unknown") for row in pitchers)
    book_counts = Counter(str(row.get("ref_book") or "unknown") for row in pitchers)
    opening_counts = Counter(str(row.get("opening_odds_source") or "unknown") for row in pitchers)
    warnings = artifact.get("data_warnings") or []
    return {
        "date": artifact.get("date"),
        "generated_at": artifact.get("generated_at"),
        "pitchers": len(pitchers),
        "tracked_picks": len(artifact.get("tracked_picks") or []),
        "source_counts": dict(sorted(source_counts.items())),
        "book_counts": dict(sorted(book_counts.items())),
        "opening_counts": dict(sorted(opening_counts.items())),
        "data_warnings": warnings if isinstance(warnings, list) else [str(warnings)],
    }


def render_summary(summary: dict) -> str:
    lines = [
        "# Source Fallback Health",
        "",
        f"- Date: {summary['date']}",
        f"- Generated at: {summary['generated_at']}",
        f"- Pitcher records: {summary['pitchers']}",
        f"- Tracked picks: {summary['tracked_picks']}",
        "",
        "## Odds Sources",
    ]
    for source, count in summary["source_counts"].items():
        lines.append(f"- `{source}`: {count}")
    lines.append("")
    lines.append("## Reference Books")
    for book, count in summary["book_counts"].items():
        lines.append(f"- `{book}`: {count}")
    lines.append("")
    lines.append("## Opening Sources")
    for source, count in summary["opening_counts"].items():
        lines.append(f"- `{source}`: {count}")
    lines.append("")
    lines.append("## Data Warnings")
    if summary["data_warnings"]:
        for warning in summary["data_warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("- none")
    return "\n".join(lines)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("date")
    args = parser.parse_args()
    print(render_summary(summarize_artifact(load_artifact(args.date))))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Create tests for source fallback health**

Create `tests/test_source_fallback_health.py`:

```python
from analytics.diagnostics.source_fallback_health import summarize_artifact


def test_summarize_artifact_counts_sources_books_and_openings():
    artifact = {
        "date": "2026-05-05",
        "generated_at": "2026-05-05T13:00:00Z",
        "data_warnings": ["sample warning"],
        "tracked_picks": [{"pitcher": "A"}],
        "pitchers": [
            {
                "pitcher": "A",
                "odds_source": "therundown",
                "ref_book": "BetMGM",
                "opening_odds_source": "preview",
            },
            {
                "pitcher": "B",
                "odds_source": "therundown+propline",
                "ref_book": "FanDuel",
                "opening_odds_source": "first_seen",
            },
        ],
    }

    summary = summarize_artifact(artifact)

    assert summary["pitchers"] == 2
    assert summary["tracked_picks"] == 1
    assert summary["source_counts"] == {
        "therundown": 1,
        "therundown+propline": 1,
    }
    assert summary["book_counts"] == {"BetMGM": 1, "FanDuel": 1}
    assert summary["opening_counts"] == {"first_seen": 1, "preview": 1}
    assert summary["data_warnings"] == ["sample warning"]
```

- [ ] **Step 4: Run source health tests**

Run:

```bash
python -m pytest tests/test_source_fallback_health.py -q
```

Expected:

```text
passed
```

- [ ] **Step 5: Generate the current source health note**

Run:

```bash
python analytics/diagnostics/source_fallback_health.py 2026-05-05 > analytics/output/source_fallback_health.md
```

Expected:

```text
analytics/output/source_fallback_health.md exists and shows PropLine/TheRundown source mix.
```

- [ ] **Step 6: Commit**

Run:

```bash
git add AGENTS.md analytics/diagnostics/source_fallback_health.py tests/test_source_fallback_health.py
git commit -m "chore: document provider fallback health"
```

---

## Task 3: Add Shadow Line Movement Audit

**Files:**

- Create: `analytics/diagnostics/line_movement_shadow_audit.py`
- Create: `tests/test_line_movement_shadow_audit.py`
- Read: `data/picks_history.json`
- Read: `dashboard/data/processed/steam.json`

- [ ] **Step 1: Create movement bucket helpers**

Create `analytics/diagnostics/line_movement_shadow_audit.py`:

```python
"""Shadow audit for line movement and movement_conf performance."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT / "data" / "picks_history.json"


def movement_bucket(row: dict) -> str:
    source = row.get("opening_odds_source") or "unknown"
    conf = row.get("movement_conf")
    if source != "preview":
        return "not_preview"
    if conf is None:
        return "preview_unknown"
    conf = float(conf)
    if conf < 0.50:
        return "preview_heavy_fade"
    if conf < 0.75:
        return "preview_some_fade"
    if conf < 1.00:
        return "preview_minor_fade"
    return "preview_no_fade"


def summarize_rows(rows: list[dict]) -> dict:
    buckets: dict[str, dict] = defaultdict(lambda: {"graded": 0, "wins": 0, "losses": 0, "pnl": 0.0})
    for row in rows:
        if row.get("result") not in {"win", "loss"}:
            continue
        bucket = movement_bucket(row)
        entry = buckets[bucket]
        entry["graded"] += 1
        entry["wins"] += 1 if row.get("result") == "win" else 0
        entry["losses"] += 1 if row.get("result") == "loss" else 0
        entry["pnl"] += float(row.get("pnl") or 0.0)
    return {key: {**value, "pnl": round(value["pnl"], 2)} for key, value in sorted(buckets.items())}


def render(summary: dict) -> str:
    lines = [
        "# Line Movement Shadow Audit",
        "",
        "This is diagnostic only. It does not change verdicts, EV, or calibration.",
        "",
        "## Movement Buckets",
    ]
    for bucket, row in summary.items():
        lines.append(
            f"- `{bucket}`: graded={row['graded']}, wins={row['wins']}, losses={row['losses']}, pnl={row['pnl']:+.2f}u"
        )
    return "\n".join(lines)


def main() -> None:
    rows = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    print(render(summarize_rows(rows)))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test movement bucket behavior**

Create `tests/test_line_movement_shadow_audit.py`:

```python
from analytics.diagnostics.line_movement_shadow_audit import movement_bucket, summarize_rows


def test_movement_bucket_ignores_first_seen_opening():
    assert movement_bucket({"opening_odds_source": "first_seen", "movement_conf": 0.2}) == "not_preview"


def test_movement_bucket_classifies_preview_fades():
    assert movement_bucket({"opening_odds_source": "preview", "movement_conf": 0.4}) == "preview_heavy_fade"
    assert movement_bucket({"opening_odds_source": "preview", "movement_conf": 0.6}) == "preview_some_fade"
    assert movement_bucket({"opening_odds_source": "preview", "movement_conf": 0.9}) == "preview_minor_fade"
    assert movement_bucket({"opening_odds_source": "preview", "movement_conf": 1.0}) == "preview_no_fade"


def test_summarize_rows_counts_results_by_bucket():
    rows = [
        {"opening_odds_source": "preview", "movement_conf": 1.0, "result": "win", "pnl": 0.91},
        {"opening_odds_source": "preview", "movement_conf": 0.6, "result": "loss", "pnl": -1.0},
        {"opening_odds_source": "first_seen", "movement_conf": 1.0, "result": "void", "pnl": 0.0},
    ]

    summary = summarize_rows(rows)

    assert summary["preview_no_fade"]["wins"] == 1
    assert summary["preview_some_fade"]["losses"] == 1
    assert "not_preview" not in summary
```

- [ ] **Step 3: Run tests and generate audit**

Run:

```bash
python -m pytest tests/test_line_movement_shadow_audit.py -q
python analytics/diagnostics/line_movement_shadow_audit.py > analytics/output/line_movement_shadow_audit.md
```

Expected:

```text
passed
analytics/output/line_movement_shadow_audit.md exists
```

- [ ] **Step 4: Decision rule for webhooks**

Use this rule in the generated note:

```text
Do not build webhooks until movement audit shows that better intraday history would change a real decision.
If preview coverage is sparse or movement_conf rarely activates, webhooks may improve evidence collection but should not alter live EV yet.
```

- [ ] **Step 5: Commit**

Run:

```bash
git add analytics/diagnostics/line_movement_shadow_audit.py tests/test_line_movement_shadow_audit.py
git commit -m "chore: add line movement shadow audit"
```

---

## Task 4: Add Prior-Model Replay Audit

**Files:**

- Create: `analytics/diagnostics/model_replay_shadow_audit.py`
- Create: `tests/test_model_replay_shadow_audit.py`
- Read: `data/picks_history.json`

- [ ] **Step 1: Create replay helpers**

Create `analytics/diagnostics/model_replay_shadow_audit.py`:

```python
"""Shadow comparison between current picks and simpler prior-model assumptions."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT / "data" / "picks_history.json"


def simple_projection(row: dict) -> float | None:
    values = [row.get("season_k9"), row.get("career_k9"), row.get("avg_ip")]
    if any(value is None for value in values):
        return None
    season_k9 = float(row["season_k9"])
    career_k9 = float(row["career_k9"])
    avg_ip = float(row["avg_ip"])
    blended_k9 = (0.60 * season_k9) + (0.40 * career_k9)
    return round((blended_k9 * avg_ip) / 9.0, 3)


def projection_residual(row: dict, projection: float | None) -> float | None:
    if projection is None or row.get("actual_ks") is None:
        return None
    return round(float(row["actual_ks"]) - projection, 3)


def summarize(rows: list[dict]) -> dict:
    current_residuals = []
    simple_residuals = []
    for row in rows:
        if row.get("date", "") < "2026-04-28" or row.get("result") not in {"win", "loss"}:
            continue
        if row.get("raw_lambda") is not None and row.get("actual_ks") is not None:
            current_residuals.append(float(row["actual_ks"]) - float(row["raw_lambda"]))
        simple = projection_residual(row, simple_projection(row))
        if simple is not None:
            simple_residuals.append(simple)
    return {
        "current_n": len(current_residuals),
        "current_mean_abs_residual": round(sum(abs(v) for v in current_residuals) / len(current_residuals), 3) if current_residuals else None,
        "simple_n": len(simple_residuals),
        "simple_mean_abs_residual": round(sum(abs(v) for v in simple_residuals) / len(simple_residuals), 3) if simple_residuals else None,
    }


def render(summary: dict) -> str:
    return "\n".join([
        "# Model Replay Shadow Audit",
        "",
        "This audit is diagnostic only. It does not change live lambda.",
        "",
        f"- Current model rows: {summary['current_n']}",
        f"- Current mean absolute residual: {summary['current_mean_abs_residual']}",
        f"- Simple replay rows: {summary['simple_n']}",
        f"- Simple replay mean absolute residual: {summary['simple_mean_abs_residual']}",
    ])


def main() -> None:
    rows = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    print(render(summarize(rows)))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test replay helpers**

Create `tests/test_model_replay_shadow_audit.py`:

```python
from analytics.diagnostics.model_replay_shadow_audit import simple_projection, projection_residual, summarize


def test_simple_projection_uses_season_career_and_ip():
    row = {"season_k9": 9.0, "career_k9": 8.0, "avg_ip": 6.0}
    assert simple_projection(row) == 5.733


def test_projection_residual_returns_actual_minus_projection():
    assert projection_residual({"actual_ks": 7}, 5.733) == 1.267


def test_summarize_compares_current_and_simple_clean_rows():
    rows = [
        {
            "date": "2026-05-01",
            "result": "win",
            "actual_ks": 6,
            "raw_lambda": 5,
            "season_k9": 9.0,
            "career_k9": 8.0,
            "avg_ip": 6.0,
        }
    ]
    result = summarize(rows)
    assert result["current_n"] == 1
    assert result["simple_n"] == 1
```

- [ ] **Step 3: Run tests and generate replay audit**

Run:

```bash
python -m pytest tests/test_model_replay_shadow_audit.py -q
python analytics/diagnostics/model_replay_shadow_audit.py > analytics/output/model_replay_shadow_audit.md
```

Expected:

```text
passed
analytics/output/model_replay_shadow_audit.md exists
```

- [ ] **Step 4: Interpret old-model concern**

Use this decision rule:

```text
If the simple replay beats current mean absolute residual and side residuals on the same 2026-04-28+ rows, consider a projection simplification plan.
If it only beats all-history ROI but not same-window replay, do not revert the model.
```

- [ ] **Step 5: Commit**

Run:

```bash
git add analytics/diagnostics/model_replay_shadow_audit.py tests/test_model_replay_shadow_audit.py
git commit -m "chore: add prior model replay audit"
```

---

## Task 5: Add Seasonal K Environment Shadow Audit

**Files:**

- Create: `analytics/diagnostics/seasonal_k_environment_audit.py`
- Create: `tests/test_seasonal_k_environment_audit.py`
- Read: `data/picks_history.json`

- [ ] **Step 1: Create season bucket helpers**

Create `analytics/diagnostics/seasonal_k_environment_audit.py`:

```python
"""Audit whether league K environment needs a shadow seasonal prior."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HISTORY_PATH = ROOT / "data" / "picks_history.json"


def month_bucket(date_str: str) -> str:
    return str(date_str)[:7]


def summarize_by_month(rows: list[dict]) -> dict:
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        if row.get("result") not in {"win", "loss"}:
            continue
        if row.get("actual_ks") is None:
            continue
        buckets[month_bucket(row["date"])].append(float(row["actual_ks"]))
    return {
        month: {
            "n": len(values),
            "avg_actual_ks": round(sum(values) / len(values), 3),
        }
        for month, values in sorted(buckets.items())
        if values
    }


def render(summary: dict) -> str:
    lines = [
        "# Seasonal K Environment Audit",
        "",
        "This is a shadow read. Do not apply month constants directly to live lambda.",
        "",
        "## Monthly Actual K Snapshot",
    ]
    for month, row in summary.items():
        lines.append(f"- `{month}`: n={row['n']}, avg_actual_ks={row['avg_actual_ks']}")
    lines.extend([
        "",
        "## Decision Rule",
        "",
        "- If a month/week environment signal is real, implement it as a shrunk prior or calibration feature, not a hard-coded calendar bump.",
        "- Compare against league-wide MLB K/start data before using app picks alone.",
    ])
    return "\n".join(lines)


def main() -> None:
    rows = json.loads(HISTORY_PATH.read_text(encoding="utf-8"))
    print(render(summarize_by_month(rows)))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test season bucket helpers**

Create `tests/test_seasonal_k_environment_audit.py`:

```python
from analytics.diagnostics.seasonal_k_environment_audit import month_bucket, summarize_by_month


def test_month_bucket_uses_year_month():
    assert month_bucket("2026-05-04") == "2026-05"


def test_summarize_by_month_uses_graded_actual_ks():
    rows = [
        {"date": "2026-04-30", "result": "win", "actual_ks": 4},
        {"date": "2026-04-29", "result": "loss", "actual_ks": 6},
        {"date": "2026-05-01", "result": "void", "actual_ks": None},
    ]
    summary = summarize_by_month(rows)
    assert summary["2026-04"] == {"n": 2, "avg_actual_ks": 5.0}
    assert "2026-05" not in summary
```

- [ ] **Step 3: Run tests and generate audit**

Run:

```bash
python -m pytest tests/test_seasonal_k_environment_audit.py -q
python analytics/diagnostics/seasonal_k_environment_audit.py > analytics/output/seasonal_k_environment_audit.md
```

Expected:

```text
passed
analytics/output/seasonal_k_environment_audit.md exists
```

- [ ] **Step 4: Decide what seasonal data is still missing**

Write this note into the output if using it for a live change later:

```text
App picks alone are selection-biased. A real seasonal K environment prior should be validated against MLB-wide starter K/start by week or month, not only our bet history.
```

- [ ] **Step 5: Commit**

Run:

```bash
git add analytics/diagnostics/seasonal_k_environment_audit.py tests/test_seasonal_k_environment_audit.py
git commit -m "chore: add seasonal k environment audit"
```

---

## Task 6: Run Verification Batch

**Files:**

- Read: all modified files

- [ ] **Step 1: Run focused provider tests**

Run:

```bash
python -m pytest tests/test_fetch_odds.py -q
```

Expected:

```text
passed
```

- [ ] **Step 2: Run new diagnostics tests**

Run:

```bash
python -m pytest tests/test_source_fallback_health.py tests/test_line_movement_shadow_audit.py tests/test_model_replay_shadow_audit.py tests/test_seasonal_k_environment_audit.py -q
```

Expected:

```text
passed
```

- [ ] **Step 3: Run existing evaluation diagnostics**

Run:

```bash
python analytics/diagnostics/e1_regime_map.py
python analytics/diagnostics/e3_projection_audit.py
python analytics/diagnostics/e4_bet_selection_audit.py
python analytics/diagnostics/e5_quality_gate_audit.py --since 2026-04-28
```

Expected:

```text
Each command exits 0 and prints markdown.
```

- [ ] **Step 4: Run a broader regression if time allows**

Run:

```bash
python -m pytest tests/ -q
```

Expected:

```text
passed
```

---

## Recommendation Notes

### Should We Revert Toward The Old Model?

Not yet.

The old model may look better, but the comparison is contaminated by:

- old EV semantics versus current ROI semantics
- dead or repaired SwStr transport
- different quality gates
- different provider mix
- different opening-line handling
- small clean-window sample

The right move is a same-window replay audit, not a rollback.

### Should We Consider Line Movement More?

Yes, but as shadow evidence first.

Current live logic only applies the movement haircut when `opening_odds_source == "preview"`. It ignores `first_seen` because same-day price deltas were previously too easy to misinterpret. That is conservative and probably correct, but it means movement is underused when preview coverage is thin or book/source shifts prevent preview matching.

Better movement use should come from:

- stronger opening baseline coverage
- `steam.json` trend analysis
- provider-specific movement reliability
- closing-line value audits
- later webhook/persistent storage if polling misses too much movement

### Would PropLine Webhooks Help?

Eventually, yes.

Webhooks would help with line-movement history, true opening capture, timestamped book changes, CLV, and provider comparison. They are not needed for the immediate fallback swap. Build webhooks only after polling proves PropLine is the right long-term feed and after we choose durable storage, likely Supabase or another append-only event store.

### Should We Use Previous-Year Or Month-Level K Averages?

Maybe, but do not hard-code simple calendar constants into lambda.

The useful version is a shrunk league environment prior:

```text
expected_k_environment = multi-season same-week/month MLB starter K/start baseline
live_environment_delta = current season MLB starter K/start minus baseline
lambda_environment_adj = heavily shrunk live_environment_delta
```

This should be validated on MLB-wide starter data first, because app pick history is selection-biased.

### Should We Just Let Lambda Heal?

Partly.

`lambda_bias` is already healing the global level. But the current issue is not only global level: clean diagnostics show over/under asymmetry and weak high-EV separation. Letting lambda heal is fine for broad bias, but we still need diagnostics for side conversion, high-lambda shape, and movement reliability before changing live math.

---

## Success Criteria

- PropLine is attempted before The Odds whenever fallback coverage is needed.
- The Odds still runs second if PropLine fails or leaves FanDuel/DraftKings coverage missing.
- `odds_source` continues to preserve merged provenance such as `therundown+propline`.
- No live model math changes ship in this plan.
- New diagnostics can answer:
  - whether PropLine is actually improving book coverage,
  - whether line movement deserves stronger live weighting,
  - whether a simpler prior model beats current logic on the same clean rows,
  - whether a seasonal K environment prior is plausible.
