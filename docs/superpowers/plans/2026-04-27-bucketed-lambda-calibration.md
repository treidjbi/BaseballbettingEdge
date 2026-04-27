# Bucketed Lambda Calibration — Follow-up to C4 Skip

**Spawned from:** 2026-04-16 model audit plan, C4.1 skip decision.

**Problem:** Phase B (B1/B2) showed that prediction bias is NOT uniform across
the lambda range. High-lambda picks underperform while low-lambda picks do not.
A global `lambda_bias` scalar will never close a bias that is bucket-shaped.

**Approach to design:** extend `calibrate.py` to fit a piecewise lambda_bias
(e.g., one value for lambda<5, another for 5-7, another for >7) with minimum
sample size per bucket (>=20) and a fallback to the global value when thin.

**Open questions to resolve before implementing:**
- Bucket boundaries (fixed or data-driven)?
- How to avoid bucket-boundary discontinuities in lambda?
- Does this interact with C1 opener detection (which removes high-variance picks)?

**Status:** placeholder — not scheduled for work. Revisit after Phase C1–C3 settle.
