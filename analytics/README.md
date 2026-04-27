# analytics/ — local deep-dive tools

A place for ad-hoc slicing of `data/picks_history.json` that goes beyond the
Netlify performance tab. Not part of the pipeline — nothing here runs in
GitHub Actions, nothing here affects picks or calibration.

## Setup (once)

```bash
pip install -r analytics/requirements.txt
```

## Usage

```bash
# Full report over all picks
python analytics/performance.py

# Only picks since the ROI-era formula change
python analytics/performance.py --since 2026-04-28

# Only FIRE-tier EV ROI (6%+)
python analytics/performance.py --min-ev 0.06
```

Prints summary tables to the console and saves three plots to
`analytics/output/`:

- **calibration.png** — predicted λ vs actual K (scatter + residual histogram).
  Tells you if the model is systematically over/under-predicting.
- **rolling_pnl.png** — cumulative + 7/14-day rolling PnL. Spots cold/hot streaks.
- **ev_vs_actual.png** — predicted EV ROI bucket vs realized win rate. The single
  most important view: if the model's edge is real, higher EV ROI buckets should
  show monotonically higher realized win rates above breakeven.

## Console tables

- **Overall** — volume, graded count, date range
- **By verdict tier** — LEAN / FIRE 1u / FIRE 2u separated
- **By side** — over vs under performance
- **By pitcher handedness** — vs RHP vs LHP
- **By EV ROI bucket** — does higher predicted EV ROI → higher realized ROI?
- **By movement confidence** — does line-move-against-us predict losses?
- **By umpire adjustment sign** — does the ump factor actually help?
- **By lineup availability** — do lineup-aware picks outperform team-K% picks?

## Extending

It's one file (`performance.py`), standalone, no pipeline imports. Edit
freely. Add a new function, call it from `main()`, commit it. If something
grows past ~400 lines, split into a module.

## Output folder

`analytics/output/` is gitignored — regenerate whenever you want fresh plots.
