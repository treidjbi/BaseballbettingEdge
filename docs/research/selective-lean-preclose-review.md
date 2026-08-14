# Selective LEAN Prospective Review

Date: 2026-08-14
Decision: `continue_research`
Production gate: closed

## Confirmed facts

- The frozen research candidate is
  `expand_lean_low_line_capped_model_fade`: displayed LEAN, K-line bucket
  `2.5-3.5`, model fades the market favorite, and quality is capped.
- Fingerprint:
  `4e00a180e35fe75dc8889d47065a25c4351cb37ac55664eb42f01b77c07fd13a`.
- The locked historical nomination through 2026-08-12 is 103 rows, 55-48,
  +11.415935 units (+11.08% ROI). The current-provider slice is 56 rows,
  28-28, +2.999676 units (+5.36% ROI).
- The fresh review dataset reconciles both locked baselines exactly. The
  checked-in local Gate C copy is older and correctly trips
  `blocked_baseline_drift`; the post-grading runner rebuilds Gate C before the
  audit runs.
- August 13-14 are excluded as a freeze gap. Formal prospective credit starts
  2026-08-15 at `0/75`; no historical or freeze-gap row can be back-credited.

## Implemented counter

`analytics/diagnostics/selective_lean_prospective_audit.py` reads Gate C after
grading and writes ignored Markdown/JSON research outputs. The existing
post-grading research runner invokes it by default and provides independent
output flags plus `--skip-selective-lean-prospective-audit`.

Prospective candidates fail closed unless they are unique tracked win/loss
rows with exact `pre_30` timing, a lock timestamp, consumed operational-lock
identifier/time/source-artifact proof, provider attribution, market-agreement
attribution, and complete side/price/K-line/quality/Path B/workload/pre-close
proxy/final-CLV fields. The current Gate C schema does not yet carry the three
consumed-ledger proof fields, so future matching rows will be reported as
blocked until a separate dataset-enrichment step is approved and implemented.

## Review gate

A separate review is allowed only after all of these hold:

- 75 eligible graded rows;
- 20 UNDER rows and 10 plus-price rows;
- positive prospective and latest-14-slate PnL;
- complete provider and market-agreement attribution;
- no negative mandatory slice at 10 or more rows; and
- positive leave-one-slate-out minimum PnL.

The mandatory inventory covers side, price, K-line, quality, timing,
model/market, Path B, workload, pre-close proxy, final CLV, provider,
market agreement, and rolling windows.

## Recommendation

Keep the counter research-only. The next useful implementation decision is a
separate Gate C enrichment for consumed-lock linkage; do not infer that work
from this counter or weaken the fail-closed requirement. Passing the 75-row
gate would authorize only a new yes/no review, never an automatic live model,
threshold, staking, provider, notification, lock, UI, history, or artifact
change.
