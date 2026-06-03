# Gate C Pitcher K Research Artifact

Shadow-only compact research data for Gate C. These files do not change live
picks, locks, thresholds, staking, provider order, notifications, calibration,
dashboard behavior, or source-of-truth rules.

Regenerate from the repo root:

```bash
python scripts/build_pitcher_k_outcome_dataset.py --artifact-source hybrid --output-dir data/research/gate_c
```

`hybrid` mode uses local committed dated archives as the historical base and
fills graded dates missing or incomplete locally from production Netlify
`get-artifact` dated slates and `picks_history`.
