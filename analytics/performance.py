"""
analytics/performance.py — local deep-dive into picks_history.json.

Prints summary tables to stdout and saves plots to analytics/output/.
Covers overall record, verdict-tier ROI, calibration (predicted lambda vs
actual K), EV-bucket realized edge, line-movement impact, umpire impact,
and lineup-availability impact.

Usage:
    pip install -r analytics/requirements.txt   # first time only
    python analytics/performance.py
    python analytics/performance.py --since 2026-04-08   # filter by date
    python analytics/performance.py --min-ev 0.03        # only FIRE tier EV

The script is intentionally standalone — no pipeline imports, no tests,
no notebook. Edit it freely to answer whatever question comes up next.
"""
import argparse
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PICKS_PATH = ROOT / "data" / "picks_history.json"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"

# LEAN picks are tracked but not staked (per CLAUDE.md EV thresholds).
VERDICT_UNITS = {"LEAN": 0.0, "FIRE 1u": 1.0, "FIRE 2u": 2.0}

# Pre-Option-B (commit 8b272b6, 2026-04-21 09:54 PT) _select_ref_book fell back
# to f"Book{book_id}" for untracked books. 49 historical rows carry those
# placeholders (Book25, Book3, Book2, Book12). The UPDATE path doesn't touch
# ref_book, so they're permanently grandfathered. Collapse them into one
# "<untracked-legacy>" bucket in the per-book slice so the table stays readable
# without rewriting history.
_BOOKN_PLACEHOLDER_RE = re.compile(r"^Book\d+$")


def _normalize_ref_book(val):
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "<unknown>"
    if _BOOKN_PLACEHOLDER_RE.match(str(val)):
        return "<untracked-legacy>"
    return val


# -- Load --------------------------------------------------------------------

def load_picks(since: str | None = None, min_ev: float | None = None) -> pd.DataFrame:
    with open(PICKS_PATH) as f:
        records = json.load(f)
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["units_risked"] = df["verdict"].map(VERDICT_UNITS).fillna(0.0)
    if since:
        df = df[df["date"] >= pd.Timestamp(since)]
    if min_ev is not None:
        df = df[df["ev"].fillna(0) >= min_ev]
    return df


def graded(df: pd.DataFrame) -> pd.DataFrame:
    """Picks with a decided result (win/loss). Excludes push/cancelled/void/ungraded."""
    return df[df["result"].isin(["win", "loss"])].copy()


def staked(df: pd.DataFrame) -> pd.DataFrame:
    """FIRE picks only (where we actually risked units). Excludes LEAN."""
    return df[df["verdict"].isin(["FIRE 1u", "FIRE 2u"])].copy()


# -- Tables ------------------------------------------------------------------

def _row(label: str, sub: pd.DataFrame) -> str:
    g = graded(sub)
    n = len(g)
    wins = (g["result"] == "win").sum()
    losses = (g["result"] == "loss").sum()
    wr_str = f"{wins / n:>6.1%}" if n else "   -- "
    pnl = g["pnl"].sum()
    units = g["units_risked"].sum()
    roi_str = f"{pnl / units:+7.2%}" if units > 0 else "    -- "
    return (f"  {label:<28} n={n:<4} W-L={wins}-{losses}  "
            f"WR={wr_str}  PnL={pnl:+7.2f}u  ROI={roi_str}")


def summary(df: pd.DataFrame) -> None:
    total = len(df)
    g = graded(df)
    print("\n-- Overall -----------------------------------------------------------")
    print(f"  Total picks (all tiers):  {total}")
    print(f"  Graded W/L:               {len(g)}")
    print(f"  Date range:               {df['date'].min().date()} -> {df['date'].max().date()}")
    print(_row("All graded (FIRE+LEAN)", df))
    print(_row("Staked only (FIRE 1u/2u)", staked(df)))


def by_verdict(df: pd.DataFrame) -> None:
    print("\n-- By verdict tier --------------------------------------------------")
    for v in ["LEAN", "FIRE 1u", "FIRE 2u"]:
        print(_row(v, df[df["verdict"] == v]))


def by_side(df: pd.DataFrame) -> None:
    print("\n-- By over/under side (staked only) ---------------------------------")
    s = staked(df)
    for side in ["over", "under"]:
        print(_row(f"side = {side}", s[s["side"] == side]))


def by_throws(df: pd.DataFrame) -> None:
    print("\n-- By pitcher handedness (staked only) ------------------------------")
    s = staked(df)
    for t in ["R", "L"]:
        print(_row(f"throws = {t}", s[s["pitcher_throws"] == t]))
    unknown = s[s["pitcher_throws"].isna()]
    if len(unknown):
        print(_row("throws = unknown", unknown))


def by_ev_bucket(df: pd.DataFrame) -> None:
    """Does higher predicted EV actually produce higher realized ROI?"""
    print("\n-- By EV bucket (staked only) ---------------------------------------")
    s = staked(df).copy()
    bins = [-1, 0.03, 0.05, 0.07, 0.09, 0.15, 1]
    labels = ["<3%", "3-5%", "5-7%", "7-9%", "9-15%", ">15%"]
    s["ev_bucket"] = pd.cut(s["ev"], bins=bins, labels=labels)
    for lbl in labels:
        print(_row(f"EV {lbl}", s[s["ev_bucket"] == lbl]))


def by_movement(df: pd.DataFrame) -> None:
    """Does line movement against our side predict losses?"""
    print("\n-- By movement confidence (staked only) -----------------------------")
    s = staked(df).copy()
    bins = [-0.01, 0.5, 0.75, 0.99, 1.01]
    labels = ["0-0.5 (heavy fade)", "0.5-0.75 (some fade)", "0.75-0.99 (minor fade)", "1.0 (no move)"]
    s["mc_bucket"] = pd.cut(s["movement_conf"].fillna(1.0), bins=bins, labels=labels)
    for lbl in labels:
        print(_row(lbl, s[s["mc_bucket"] == lbl]))


def by_umpire_adj(df: pd.DataFrame) -> None:
    """Does picking with vs against umpire K tendency affect win rate?"""
    print("\n-- By umpire K adjustment sign (staked only) ------------------------")
    s = staked(df).copy()
    # 'side helps' = ump adjusts lambda in direction of our bet
    # over + positive ump_k_adj, or under + negative ump_k_adj -> ump helps
    def ump_align(row):
        adj = row["ump_k_adj"] or 0.0
        if abs(adj) < 0.01:
            return "neutral"
        if row["side"] == "over":
            return "with" if adj > 0 else "against"
        else:
            return "with" if adj < 0 else "against"
    s["ump_align"] = s.apply(ump_align, axis=1)
    for lbl in ["with", "neutral", "against"]:
        print(_row(f"ump {lbl} side", s[s["ump_align"] == lbl]))


def by_lineup(df: pd.DataFrame) -> None:
    """Do picks with confirmed lineup data perform better?"""
    print("\n-- By lineup availability (staked only) -----------------------------")
    s = staked(df)
    print(_row("lineup_used = True", s[s["lineup_used"] == 1]))
    print(_row("lineup_used = False", s[s["lineup_used"] == 0]))


def by_bookmaker(df: pd.DataFrame) -> None:
    """Per-reference-book performance. Which book's line is most/least predictive?

    Pre-Option-B rows with 'BookN' placeholder labels are collapsed into a
    single '<untracked-legacy>' bucket — they're frozen history and can't be
    re-resolved to real sportsbook names.
    """
    print("\n-- By reference book (staked only) -----------------------------------")
    s = staked(df)
    if "ref_book" not in s.columns:
        print("  skip: ref_book column missing from picks_history.json")
        return
    normalized = s["ref_book"].map(_normalize_ref_book)
    books = normalized.value_counts().index.tolist()
    for book in books:
        sub = s[normalized == book]
        print(_row(f"book = {book}", sub))


# -- Plots -------------------------------------------------------------------

def plot_calibration(df: pd.DataFrame) -> None:
    """Predicted lambda vs actual K — scatter + residual histogram."""
    d = df.dropna(subset=["applied_lambda", "actual_ks"])
    d = d[d["result"].isin(["win", "loss"])]
    if len(d) < 20:
        print("  skip calibration plot: n<20")
        return
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    ax = axes[0]
    ax.scatter(d["applied_lambda"], d["actual_ks"], alpha=0.35, s=18)
    lo = min(d["applied_lambda"].min(), d["actual_ks"].min()) - 0.5
    hi = max(d["applied_lambda"].max(), d["actual_ks"].max()) + 0.5
    ax.plot([lo, hi], [lo, hi], "k--", alpha=0.5, label="perfect")
    ax.set_xlabel("Applied lambda (predicted K)")
    ax.set_ylabel("Actual K")
    ax.set_title(f"Calibration (n={len(d)})")
    ax.legend()
    ax.grid(alpha=0.3)

    ax = axes[1]
    resid = d["actual_ks"] - d["applied_lambda"]
    ax.hist(resid, bins=30, edgecolor="black", alpha=0.7)
    ax.axvline(0, color="black", linestyle="--")
    ax.axvline(resid.mean(), color="red", linestyle="-",
               label=f"mean={resid.mean():+.2f}")
    ax.set_xlabel("Residual (actual - predicted)")
    ax.set_ylabel("Count")
    ax.set_title("Prediction residuals")
    ax.legend()
    ax.grid(alpha=0.3)

    out = OUTPUT_DIR / "calibration.png"
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    print(f"  saved {out.relative_to(ROOT)}")


def plot_rolling_roi(df: pd.DataFrame) -> None:
    """7- and 14-day rolling PnL for staked picks."""
    s = graded(staked(df)).sort_values("date")
    if len(s) < 10:
        print("  skip rolling ROI plot: n<10")
        return
    daily = s.groupby(s["date"].dt.date).agg(pnl=("pnl", "sum"),
                                             units=("units_risked", "sum"))
    daily.index = pd.to_datetime(daily.index)
    daily["cum_pnl"] = daily["pnl"].cumsum()
    daily["r7_pnl"] = daily["pnl"].rolling(7, min_periods=1).sum()
    daily["r14_pnl"] = daily["pnl"].rolling(14, min_periods=1).sum()

    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    axes[0].plot(daily.index, daily["cum_pnl"], marker="o", markersize=3)
    axes[0].axhline(0, color="black", linestyle="--", alpha=0.5)
    axes[0].set_ylabel("Cumulative PnL (units)")
    axes[0].set_title("Staked PnL over time")
    axes[0].grid(alpha=0.3)

    axes[1].bar(daily.index, daily["pnl"], alpha=0.5, label="daily")
    axes[1].plot(daily.index, daily["r7_pnl"], color="orange", label="7d rolling", linewidth=2)
    axes[1].plot(daily.index, daily["r14_pnl"], color="red", label="14d rolling", linewidth=2)
    axes[1].axhline(0, color="black", linestyle="--", alpha=0.5)
    axes[1].set_ylabel("PnL (units)")
    axes[1].set_xlabel("Date")
    axes[1].legend()
    axes[1].grid(alpha=0.3)

    out = OUTPUT_DIR / "rolling_pnl.png"
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    print(f"  saved {out.relative_to(ROOT)}")


def plot_ev_vs_actual(df: pd.DataFrame) -> None:
    """Predicted EV vs realized win rate — the most important calibration view."""
    s = graded(staked(df)).copy()
    if len(s) < 20:
        print("  skip EV-vs-actual plot: n<20")
        return
    bins = [0.03, 0.05, 0.07, 0.09, 0.12, 0.20, 1.0]
    s["ev_bucket"] = pd.cut(s["ev"], bins=bins)
    agg = s.groupby("ev_bucket", observed=True).agg(
        n=("ev", "size"),
        wins=("result", lambda x: (x == "win").sum()),
    )
    agg["wr"] = agg["wins"] / agg["n"]
    if agg.empty:
        print("  skip EV-vs-actual plot: no bucketed data")
        return

    fig, ax = plt.subplots(figsize=(10, 5))
    x = [str(i) for i in agg.index]
    ax.bar(x, agg["wr"], alpha=0.7, edgecolor="black")
    ax.axhline(0.5238, color="red", linestyle="--", label="breakeven @ -110")
    for i, (wr, n) in enumerate(zip(agg["wr"], agg["n"])):
        ax.text(i, wr + 0.01, f"n={n}", ha="center", fontsize=9)
    ax.set_ylabel("Realized win rate")
    ax.set_xlabel("Predicted EV bucket")
    ax.set_title("Does higher predicted EV produce higher realized win rate?")
    ax.legend()
    ax.grid(alpha=0.3, axis="y")
    ax.set_ylim(0, max(0.8, agg["wr"].max() + 0.1))

    out = OUTPUT_DIR / "ev_vs_actual.png"
    fig.tight_layout()
    fig.savefig(out, dpi=120)
    plt.close(fig)
    print(f"  saved {out.relative_to(ROOT)}")


# -- Main --------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--since", help="Filter to picks on/after this date (YYYY-MM-DD)")
    ap.add_argument("--min-ev", type=float, help="Filter to picks with EV >= this value")
    args = ap.parse_args()

    OUTPUT_DIR.mkdir(exist_ok=True)
    df = load_picks(since=args.since, min_ev=args.min_ev)
    if df.empty:
        print("No picks matched filters.")
        return

    summary(df)
    by_verdict(df)
    by_side(df)
    by_throws(df)
    by_ev_bucket(df)
    by_movement(df)
    by_umpire_adj(df)
    by_lineup(df)
    by_bookmaker(df)

    print("\n-- Plots -------------------------------------------------------------")
    plot_calibration(df)
    plot_rolling_roi(df)
    plot_ev_vs_actual(df)
    print()


if __name__ == "__main__":
    main()
