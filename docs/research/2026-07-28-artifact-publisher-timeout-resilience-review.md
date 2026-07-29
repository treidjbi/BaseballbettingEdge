# Artifact Publisher Timeout Resilience Review

Date: 2026-07-28

Status: **Implementation merged 2026-07-29; pending separate production activation.**

This is a read-only diagnosis. It does not authorize a pipeline deploy,
Supabase setting change, manual repair, provider change, lock change, artifact
contract change, or GitHub rollback run.

## July 29 implementation update

Tyler approved the publisher-only resilience implementation after a fifth
matching timeout occurred on the July 28 `14:07` Phoenix refresh. That refresh
finished its pipeline work, failed on the `published_pipeline_artifacts`
`57014` upsert, and recovered on the next scheduled refresh without stale
served artifacts, missed locks, grading divergence, or betting impact.

`main` commit `a1019485` now contains the narrow reviewed contract:

- `published_pipeline_artifacts` requests `return=minimal`; other Supabase
  upserts retain `return=representation` by default;
- only that publisher supplies a two-attempt budget;
- retry eligibility requires both a transient HTTP status and exact database
  code `57014`;
- the second failure and every non-selected database error fail normally;
- the artifact set, conflict key, timeout, cadence, source-of-truth behavior,
  lock behavior, and publication-run ledger contract are unchanged.

Focused TDD verification is `30 passed`; full merged-tree verification is
`1,911 passed`, and the all-scope publisher dry run collected the expected
seven artifacts. Production activation remains a separate gate because Render
pipeline crons keep autoDeploy off. If Tyler approves activation, redeploy the
validated pipeline cron group together and verify hashes plus the next natural
lock publication.

## Executive decision

Five Render pipeline runs have now failed on the same Supabase PostgREST
statement timeout: four `bbe-pipeline-lock` runs on July 23 at `02:32`
Phoenix, July 25 at `11:42`, and July 27 at `00:32` and `05:32`, plus the July
28 `14:07` refresh. Every failure was the artifact upsert and every next
scheduled cycle recovered.

No stale served artifact, missed due lock, duplicate lock, wrong-date lock, or
grading impact was found. Do not run a repair today. Tyler approved the
test-first publisher-resilience implementation and it is now merged to `main`;
production activation remains a separate decision.

## Confirmed failure pattern

| Failed at (UTC) | Phoenix time | Request | Database error | Adjacent recovery |
| --- | --- | --- | --- | --- |
| `2026-07-23T09:32:47Z` | Jul 23 `02:32` | 3-row `published_pipeline_artifacts` upsert | `57014`, statement timeout | Jul 23 `02:42` |
| `2026-07-25T18:42:42Z` | Jul 25 `11:42` | same | same | Jul 25 `11:52` |
| `2026-07-27T07:32:40Z` | Jul 27 `00:32` | same | same | Jul 27 `00:42` |
| `2026-07-27T12:32:41Z` | Jul 27 `05:32` | same | same | Jul 27 `05:42` |

Successful lock-publication counts were `143`, `144`, `143`, `144`, and
`142` for July 23 through July 27. The missing intervals correspond exactly to
the four Render errors above. Failed calls are absent from
`pipeline_artifact_publication_runs` because the run-ledger insert occurs only
after the artifact upsert succeeds.

## Impact check

- The July 23 and both July 27 failures occurred before any lock was due.
- The July 25 failure re-read one already-consumed external lock; the prior
  `11:32` Phoenix cycle had already published the lock state.
- Each next scheduled cycle published successfully.
- All due operational locks on the affected slates were eventually unique,
  consumed, and linked to the remote `get-artifact` path.
- No GitHub rollback or manual Render run is justified by this evidence.

## Root-cause chain

Confidence is **high** on the resilience failure mechanism and **medium** on
the transient load that makes a particular cycle cross the ceiling.

1. Lock scope collects `today`, the full `picks_history`, and the dated slate.
2. The publisher sends all three rows in one idempotent upsert keyed by
   `artifact_key`.
3. The shared writer requests `return=representation`, although this publisher
   ignores the returned rows. At the July 28 size, the logical row
   representation is about `5.9 MiB`; `picks_history` alone is about `5.3 MiB`
   and contains `2,704` picks.
4. Supabase's PostgREST authenticator role has an `8s` statement timeout while
   the Python HTTP timeout is `20s`.
5. The artifact upsert has no transient retry. A single `57014` therefore
   fails the Render cron even though the same payload succeeds on the next
   cycle.

The table itself does not show a structural explanation for the failures: it
has about `117` live rows, `36` dead rows, recent autovacuum/autoanalyze, no
custom triggers, four ordinary indexes, and about `10 MB` total relation size.
That does not exclude brief shared-database load, but it makes table growth,
trigger work, or index sprawl an unlikely primary cause.

## Separately gated resilience options

Preferred scope for a later implementation plan:

1. Use a publisher-specific minimal-return upsert because the publisher does
   not consume returned row bodies.
2. Add one bounded retry for an idempotent artifact-key upsert only when the
   failure is a transient HTTP status and the database body is `57014`.
3. Add payload-byte and upsert-duration logging so the next timeout can be
   compared without reconstructing timing from buffered Render logs.
4. Preserve the three-artifact consistency contract and verify served hashes
   after the next natural lock publication.

Do not increase a global Supabase role timeout, split the artifact set, skip
`picks_history`, change lock cadence, or weaken source-of-truth rules without a
separate design review. Those approaches have broader consistency or cost
effects than the observed problem warrants.

## Decision gate

Recommended next decision: review the tested branch, then approve or decline
merge and production activation as separate steps. Until activation, keep
ordinary observation. After activation, verify served hashes and the next
natural lock publication. Escalate to `Broken` and use the approved
stale-artifact repair path only if a timeout causes a stale served artifact, a
due lock to remain unpublished, or grading/history artifacts to diverge.
