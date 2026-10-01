# October 1 branch closeout review

## Decision

Shutdown is complete. This is an offline branch/content review, not permission
to restart collection, deploy branch code, merge experiments or delete branches.
Reviewed canonical Mac clone at `f8163e37`, freshly pulled from origin. GitHub
has 16 heads including main, 15 non-main branches, and no open pull requests.
No uncommitted files, stashes or additional worktrees were present at review.

Eight remote branches are ancestors of main; three more are patch-equivalent;
one has a newer equivalent implementation. Thus 12 of 15 remote branches have
no outstanding merge work. The remaining three contain historical receipts,
a stopped research experiment, and one small real reader defect. Branch count
is not the outstanding-work count.

## Complete remote inventory

| Branch | Reviewed tip | Disposition | Evidence / action |
| --- | --- | --- | --- |
| `codex/aug20-history-repair` | `904f459b` | Superseded | Staged-history override is on main at 1ff69ed5 with bounded-date handling and updated tests. Do not cherry-pick the older patch. |
| `codex/compaction-alt-failure-isolation` | `2278c249` | Fully merged | Tip is an ancestor of main; no unique commits. Eligible for branch cleanup. |
| `codex/daily-compaction-finalizer-design` | `ddfb075d` | Fully merged | Tip is an ancestor of main; no unique commits. Eligible for branch cleanup. |
| `codex/daily-compaction-finalizer-implementation` | `efaba988` | Fully merged | Tip is an ancestor of main; no unique commits. Eligible for branch cleanup. |
| `codex/gate-c-official-source-attribution` | `ab1b428f` | Fully merged | Tip is an ancestor of main; no unique commits. Eligible for branch cleanup. |
| `codex/no-drag-strict-runtime-decision` | `5ae7a5af` | Integrated, patch-equivalent | git cherry reports equivalence; PR 47 merged. No merge needed. |
| `codex/research-decision-time-adapter` | `f63e0b1a` | Split disposition | Extract signed-score reader repair with regression tests; archive offline evidence/prototypes. Hosted capture is deferred, not a March prerequisite. |
| `codex/retention-active-provider-finalizer` | `643c8c10` | Fully merged | Tip is an ancestor of main; no unique commits. Eligible for branch cleanup. |
| `codex/retention-nine-partition-repair` | `f6d278dd` | Code superseded; preserve receipt | Main has keyset paging, reviewed date allowlist and cross-boundary counts, plus newer v5 fingerprints/75-page ceiling/exact verifier. Preserve August 24 execution overlay; do not downgrade code or repeat repairs. |
| `codex/retire-propline-webhooks` | `7ee1669f` | Fully merged | Tip is an ancestor of main; no unique commits. Eligible for branch cleanup. |
| `codex/season-end-empty-day-contracts` | `760bd616` | Fully merged | Tip is an ancestor of main; no unique commits. Eligible for branch cleanup. |
| `codex/season-end-runbook` | `37ce5a74` | Historical; no pending implementation | September preflight/shutdown proposal is superseded by October 1 freeze and dormancy. The eq.false webhook proposal is obsolete after webhook retirement. Preserve as historical evidence, not a restart checklist. |
| `codex/strict-runtime-model-market-slice` | `16ce80a4` | Integrated, patch-equivalent | git cherry reports equivalence; PR 48 merged. No merge needed. |
| `codex/supabase-pressure-repairs` | `77e968fc` | Integrated, patch-equivalent | Hydration cache fix is on main at eb3169c9. No merge needed. |
| `polish/ux-fixes-sep10` | `e44ca09b` | Fully merged | Tip is an ancestor of main; no unique commits. Eligible for branch cleanup. |

The local-only `test/local-cloud-setup` at `aa22a28e` is also an ancestor of
main; its remote was previously removed. The other five local branches are
main and four branches listed above. No local branch is ahead of its upstream.

## Actual finding: signed Preclose score rejected

Main's Python `_preclose_state_valid` and JavaScript `precloseContractValid`
include `score` among counts that must be nonnegative. A legitimate negative
score is not a negative count. The branch's bounded repair at `b08284fd`
validates score as an integer independently, preserving count and semantic gates.

Current-main offline reproduction against the branch's preserved synthetic
witnesses returned:

| Witness | Score | Main validation |
| --- | ---: | --- |
| negative | -1 | Rejected: evaluation_proof_preclose_state_invalid |
| zero | 0 | Accepted |
| positive | 7 | Accepted |

This is a format/reader defect, not proof of profitable selection. The branch
also changes the live Netlify reader, so do not merge the entire eight-commit
branch as a research-document cleanup. Recommended next change: port only the
paired reader fix and self-contained negative/zero/positive, malformed-count,
noninteger/nonfinite and builder/endpoint regressions onto current main. Keep
all collectors, schedules, model rules and promotion gates closed. Validate
both languages on current main; branch-recorded test results are historical.
Review any later deployment separately from the offline code repair.

## Preserve without reviving

- Retention branch `f6d278dd`: its August 24 execution overlay documents 2,038
  repaired compact rows across nine dates. This receipt is absent from main's
  dated plan. Preserve that exact historical section before deleting the branch.
  Do not copy its old pending-backup instruction into today's checklist: main
  records a newer August 25 completed backup. No repair or retention run follows.
- Runbook `37ce5a74`: keep September 8 preflight and September 12 IO investigation
  as historical snapshots if archived. Their pending shutdown and webhook-fix
  recommendations are superseded. October 1 controls the current posture.
- Research `f63e0b1a`: preserve adapters, validators, frozen fixtures, source
  hashes and reproducible acceptance packets. Latest passive-receipt decision
  stops hosted capture: completed reads occur after the timestamp used for the
  lock, and original seed continuity is unproven. Zero formal prospective credit.
  Reopen only for new qualifying source evidence or an explicitly commissioned
  design. More historical runs do not resolve this barrier.

## March restart requirements, separate from old branches

1. Decide the 2027 model/selection protocol from frozen offline comparisons;
   no 2026 retrospective winner is automatically a live rule.
2. Resolve the signed-score reader defect before reusing Alt/research proofs.
3. Inventory exact deployed revisions and service settings before any restart.
   Five pipeline jobs were left at a12fa988 with auto-deploy off; merged
   empty-preview/steam code must be deliberately deployed and verified then.
4. Explicitly choose which services resume, restore notification scheduling
   only if approved, and check empty-slate, grading, locks, source freshness,
   supported books, cost ceilings and rollback before normal operation.
5. Actual accepted-bet/account PnL reconciliation remains an analysis gap;
   preserve the distinction from published model exposure.

Hosted capture, the retired webhook reader repair, old retention execution,
and historical runbook checkboxes are not automatic restart prerequisites.

## Validation and cleanup boundary

- Fresh pull and GitHub branch/PR inventory; ancestry, patch-equivalence,
  individual diffs and current-main implementations reviewed.
- 82 focused current-main history/dataset/partition-repair tests passed locally.
  Tests use fixtures/mocks; no data collection, grading or database writes run.
- Negative-score defect reproduced on current main with retained branch bytes.
- No experimental code merged, no deployment performed, no branch deleted.

Recommended cleanup after the bounded repair: preserve the three historical
branch tips with named archive tags and verify those tags remotely, then remove
obsolete working branch names. This review itself preserves all branch refs;
physical cleanup is a separate explicit action, not evidence that more model
work must be completed. Do not squash away the frozen evidence history.
