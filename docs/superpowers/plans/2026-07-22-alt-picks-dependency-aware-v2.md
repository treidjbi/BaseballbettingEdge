# Alt Picks Dependency-Aware V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a versioned, comparison-only Alt Picks V2 that can prove a lane while a nonessential family is pending, derives Preclose only from exact candidate-bound live evidence, and starts a new prospective ledger without changing any official BBE behavior.

**Architecture:** Preserve the deployed V1 selector and writer as an immutable compatibility path. Add a pure V2 selector, a separate exact-event evidence engine, a bounded evaluation-proof builder, and a separately gated V2 recorder that consumes the already-loaded artifact, market snapshots, provider heartbeats, current-line mappings, and operational locks. Add one JSONB column to the existing state table. Serve V1 or V2 through an explicit endpoint contract, then make only the isolated Alt Picks browser adapter request V2.

**Tech Stack:** Python 3.11, pytest, Supabase/Postgres/PostgREST, Node test runner, Netlify Functions, vanilla JavaScript, React JSX compiled with Babel, Render cron, Git.

## Global Constraints

- Read `AGENTS.md`, `docs/current-state.md`, and `docs/superpowers/specs/2026-07-22-alt-picks-dependency-aware-v2-design.md` before starting. The specification controls behavior; this plan controls implementation order.
- Start from an up-to-date `origin/main` and use branch `codex/alt-picks-dependency-aware-v2`.
- Do not edit `market_infra/alternative_pick_selector.py` or `market_infra/alternative_pick_selector_manifest_v1.json`. Their V1 IDs and fingerprint are frozen.
- V1 fingerprint remains `f8f7ccf652b8eda4860d07798bc4673920b0b9d727552bc7e2e6547d478b4579`.
- V2 fingerprint is frozen at `23bacff0fa923685ae52c5a9cfbadfb9f5902fb64d91759cfe9b4b1169a221c4` before any V2 row is written.
- `ALTERNATIVE_PICK_SELECTION_MODE=off` remains the code default and emergency stop. `ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION` is unset/default V1; exact `v1` and `v2` are valid. An explicitly invalid nonblank value fails that sidecar cycle closed as `invalid_bundle_version` rather than silently choosing a version.
- Keep the current five-second, one-attempt, fail-open sidecar boundary and its placement after notifications, live-state writes, operational locks, timing, and shadow-market work.
- V2 must never receive `market_pick_evidence_rows` or persisted `live_market_display_state` as a selection input. Those trackers continue unchanged for existing consumers.
- Native freshness is definition-preserving: fresh TheRundown/PropLine snapshots qualify by line age through `effective_book_freshness`; already-loaded heartbeat rows are passed through, but heartbeat extension remains limited to providers recognized by the existing helper. Do not change `WEBSOCKET_HOLD_PROVIDERS`, the heartbeat schema, or heartbeat writers.
- Add no provider request, provider, worker, service, polling interval, table, notification class, lock behavior, model input, model parameter, threshold, stake, accepted-bet action, retention rule, or dashboard source-of-truth change.
- BoltOdds remains excluded. Do not use historical BoltOdds rows as V2 evidence.
- A selected V2 row may contain a pending nonessential Preclose family. Missing evidence never becomes agreement or optimistic disagreement.
- V2 starts at zero. Do not backfill, reconstruct, convert, update, or delete V1 rows or missed V2 freezes.
- Database migration apply, V2-capable Render deploy, V2 recorder activation, and Netlify endpoint/UI deploy are separate production gates. Stop for Tyler approval at each mutation gate unless the active instruction explicitly authorizes that exact gate.
- Never print Supabase, Render, Netlify, provider, or service-role secrets. Render environment updates replace the whole environment list: fetch and preserve all existing entries, change exactly one named key, then verify a redacted key-only diff.
- Use `apply_patch` for source and documentation edits. Keep generated artifacts, local exports, and scratch files out of the repository unless this plan explicitly names them.

---

## Task 0: Create the isolated implementation branch and baseline proof

**Files:**

- No source files changed.

- [ ] **Step 1: Confirm the Windows clone, remote, branch, and cleanliness**

Run from `C:\Users\TylerReid\Desktop\Claude-Work\BaseballBettingEdge`:

```powershell
git rev-parse --show-toplevel
git remote -v
git branch --show-current
git status --short
git fetch origin
git rev-parse origin/main
```

Expected: the verified Windows repo, origin `https://github.com/treidjbi/BaseballbettingEdge.git`, and no unexplained changes.

- [ ] **Step 2: Fast-forward main and create the feature branch**

```powershell
git switch main
git pull --ff-only origin main
git switch -c codex/alt-picks-dependency-aware-v2
```

Expected: a new feature branch based exactly on current `origin/main`.

- [ ] **Step 3: Record the V1 compatibility baseline**

```powershell
git hash-object market_infra/alternative_pick_selector.py
git hash-object market_infra/alternative_pick_selector_manifest_v1.json
python -m pytest tests/test_alternative_pick_selector.py tests/test_alternative_pick_selection_state.py tests/test_alternative_pick_selection_schema.py tests/test_live_layer_worker.py -q
node --test tests/test_alternative_picks_function.mjs dashboard/v2-alt-picks.test.mjs dashboard/v2-app.test.mjs
```

Expected: all baseline tests pass. Save the two object hashes in the task handoff; they must match at final verification.

---

## Task 1: Freeze the V2 manifest and dependency-aware selector

**Files:**

- Create: `market_infra/alternative_pick_selector_manifest_v2.json`
- Create: `market_infra/alternative_pick_selector_v2.py`
- Create: `tests/test_alternative_pick_selector_v2.py`
- Verify unchanged: `market_infra/alternative_pick_selector.py`
- Verify unchanged: `market_infra/alternative_pick_selector_manifest_v1.json`

- [ ] **Step 1: Write failing identity, manifest, and truth-table tests**

Add tests named:

- `test_v2_manifest_has_new_bundle_and_selector_ids`
- `test_v2_manifest_fingerprint_is_frozen`
- `test_v2_manifest_preserves_v1_thresholds_weights_and_precedence`
- `test_v1_manifest_ids_and_fingerprint_are_unchanged`
- `test_tri_and_or_not_cover_all_three_valued_combinations`
- `test_absent_or_malformed_anchor_metadata_is_pending`
- `test_anchor_uses_strict_or_base_and_core_short_circuits`
- `test_preclose_uses_base_and_raw_preclose_short_circuits`
- `test_drag_core_is_true_on_any_confirmed_drag_and_false_only_when_all_are_false`
- `test_no_drag_uses_support_and_not_drag_with_three_valued_short_circuits`
- `test_consensus_selects_with_two_agreements_and_nonessential_pending`
- `test_consensus_is_false_when_maximum_possible_count_is_below_two`
- `test_reentry_selects_with_preclose_pending_when_no_drag_is_false`
- `test_pending_never_increments_family_count`
- `test_lanes_are_disjoint_for_every_family_truth_table_combination`
- `test_base_and_reentry_match_v1_for_complete_inputs`
- `test_forbidden_result_and_clv_fields_do_not_change_v2_output`
- `test_missing_v2_runtime_primitive_is_pending_not_false_or_zero`
- `test_explicit_false_and_zero_remain_distinct_from_missing`
- `test_selector_never_uses_v1_default_coercion_for_v2_decision`

Pin these identities in the tests:

```python
V2_BUNDLE_ID = "pregame_alternative_pick_methodology_v2"
V2_CONSENSUS_ID = "no_drag_distinct_family_consensus_core_v2"
V2_EXPANSION_ID = "moderate_edge_quality_reentry_expansion_v2"
V2_FINGERPRINT = "23bacff0fa923685ae52c5a9cfbadfb9f5902fb64d91759cfe9b4b1169a221c4"
```

- [ ] **Step 2: Run the selector tests and observe RED**

```powershell
python -m pytest tests/test_alternative_pick_selector_v2.py tests/test_alternative_pick_selector.py -q
```

Expected: V2 imports or assertions fail because the V2 files do not exist.

- [ ] **Step 3: Add the reviewed manifest**

Copy V1 thresholds, weights, serialization rules, field precedence, provider allow-list, and timing rules exactly. Change only the version identities and approved V2 contracts:

```json
{
  "bundle_id": "pregame_alternative_pick_methodology_v2",
  "selector_ids": {
    "consensus_core": "no_drag_distinct_family_consensus_core_v2",
    "reentry_expansion": "moderate_edge_quality_reentry_expansion_v2"
  },
  "dependency_resolution": {
    "truth_values": ["true", "false", "pending"],
    "anchor": "three_valued_or(market_anchor_strict, three_valued_and(base_support, market_anchor_core))",
    "preclose": "three_valued_and(base_support, strong_preclose_clv_proxy)",
    "no_drag": "three_valued_and(three_valued_or(base_support, market_anchor_strict), three_valued_not(drag_core))",
    "consensus_core": "true when no_drag=true and agree_count>=2; false when no_drag=false or max_possible_count<2; pending otherwise",
    "reentry_expansion": "three_valued_and(reentry_support, three_valued_not(no_drag))",
    "pending_votes_count_as_agreement": false
  },
  "evidence_contract": {
    "official_provider": "artifact.line_source_provider",
    "broad_market_pick_evidence": "forbidden",
    "optional_sidecar": "non_blocking_until_mature",
    "snapshot_identity": "provider_plus_id",
    "max_evaluation_proof_bytes": "32768"
  }
}
```

Also set `null_behavior.absent_anchor_metadata` to `pending` and set the Preclose predicate text to `base_support AND strong_preclose_clv_proxy AND exact_candidate_bound_evidence`. The complete file, not this excerpt, is hashed with the same canonical JSON procedure as V1.

- [ ] **Step 4: Implement the pure V2 selector**

Expose:

```python
TriBool = bool | None
FAMILY_ORDER = ("base", "anchor", "preclose", "reentry")

@dataclass(frozen=True)
class PredicateVote:
    state: Literal["true", "false", "pending"]
    reason_codes: tuple[str, ...]

@dataclass(frozen=True)
class LaneEvaluation:
    consensus_core: PredicateVote
    reentry_expansion: PredicateVote
    lane: Literal["consensus_core", "reentry_expansion"] | None
    selection_status: Literal["selected", "not_selected", "pending"]
    family_count: int
    maximum_family_count: int
    decisive_families: tuple[str, ...]

@dataclass(frozen=True)
class PrimitivePresence:
    values: dict[str, Any]
    missing: tuple[str, ...]
    malformed: tuple[str, ...]

def tri_and(*values: TriBool) -> TriBool: ...
def tri_or(*values: TriBool) -> TriBool: ...
def tri_not(value: TriBool) -> TriBool: ...
def validate_runtime_primitives_v2(
    *, pitcher: dict[str, Any], pick: dict[str, Any], exact_evidence: Any,
) -> PrimitivePresence: ...
def parse_anchor_primitives_v2(pick: dict[str, Any]) -> tuple[FamilyVote, FamilyVote]: ...
def compose_anchor_v2(base: FamilyVote, strict: FamilyVote, core: FamilyVote) -> FamilyVote: ...
def compose_preclose_v2(base: FamilyVote, raw_preclose: FamilyVote) -> FamilyVote: ...
def drag_core_v2(features: dict[str, Any]) -> PredicateVote: ...
def no_drag_v2(base: FamilyVote, strict_anchor: FamilyVote, drag_core: PredicateVote) -> PredicateVote: ...
def evaluate_lanes_v2(families: dict[str, FamilyVote], no_drag: PredicateVote) -> LaneEvaluation: ...
def evaluate_alternative_pick_v2(*, pitcher, pick, exact_evidence, slate_date,
                                 is_tracked, source_artifact_path,
                                 source_payload_sha256,
                                 source_artifact_byte_sha256,
                                 observed_at) -> AlternativePickEvaluationV2: ...
```

Run `validate_runtime_primitives_v2` before any V1 helper. It must distinguish an absent field from an explicit `false`, `0`, empty-but-valid collection, or neutral enum. Validate the raw fields actually required by each predicate, including verdict/side, edge and adjusted-EV status/value, K-line, anchor labels/metadata, skepticism/quality/relationship flags, and exact-evidence maturity. A missing or malformed primitive makes only its dependent vote pending unless three-valued short-circuiting already proves the outcome. It must never become a negative vote through `dict.get(..., False)`, numeric zero coercion, or a default enum.

Reuse only V1's complete-input helpers `derive_runtime_features`, `strong_base_strict_plus_selective`, `moderate_edge_quality_reentry`, and `preclose_proxy_score_from_row`, and call them only after the required raw primitive-presence checks succeed. Do not call V1 `preclose_strong`; V2 owns exact-evidence completeness before scoring.

Use these decisive rules:

```python
agree_count = sum(vote.state == "agree" for vote in families.values())
maximum_count = agree_count + sum(vote.state == "pending" for vote in families.values())
count_gate = True if agree_count >= 2 else False if maximum_count < 2 else None
consensus = tri_and(no_drag_value, count_gate)
expansion = tri_and(reentry_value, tri_not(no_drag_value))
```

- [ ] **Step 5: Prove selector behavior and V1 immutability**

```powershell
python -m pytest tests/test_alternative_pick_selector_v2.py tests/test_alternative_pick_selector.py tests/test_no_drag_composite_canary_audit.py -q
git diff --exit-code origin/main -- market_infra/alternative_pick_selector.py market_infra/alternative_pick_selector_manifest_v1.json
```

Expected: tests pass and the protected V1 files have no diff.

- [ ] **Step 6: Commit Task 1**

```powershell
git add market_infra/alternative_pick_selector_manifest_v2.json market_infra/alternative_pick_selector_v2.py tests/test_alternative_pick_selector_v2.py
git commit -m "feat: add dependency-aware alternative selector v2"
```

---

## Task 2: Build exact candidate bindings, movement, and the ephemeral ladder

**Files:**

- Create: `market_infra/alternative_pick_preclose_v2.py`
- Create: `tests/test_alternative_pick_preclose_v2.py`
- Modify: `market_infra/live_market_display.py`
- Modify: `tests/test_market_infra_live_market_display.py`
- Verify unchanged: `market_infra/market_evidence.py`
- Verify unchanged: `market_infra/provider_freshness.py`

- [ ] **Step 1: Write failing binding and evidence tests**

Add tests named:

- `test_v2_binding_uses_explicit_line_source_provider_and_current_line_mapping`
- `test_v2_does_not_infer_official_provider_from_combined_posture`
- `test_v2_binding_rejects_unbound_time_skew_wrong_event_line_and_side`
- `test_v2_payload_hash_change_alone_does_not_reset_the_window`
- `test_v2_official_binding_change_resets_the_candidate_window`
- `test_v2_sidecar_binding_change_resets_only_the_sidecar_window`
- `test_v2_exact_movement_requires_two_official_ids_and_timestamps`
- `test_v2_movement_excludes_adjacent_event_and_alternate_line`
- `test_v2_ladder_allows_only_same_exact_event_alternate_lines`
- `test_v2_optional_sidecar_absence_or_immaturity_does_not_block_official_evidence`
- `test_v2_mature_provider_book_disagreement_fails_closed`
- `test_v2_opposing_mature_provider_majorities_fail_closed`
- `test_v2_duplicate_provider_qualified_id_with_conflicting_content_fails_closed`
- `test_v2_future_post_start_and_stale_rows_are_excluded`
- `test_v2_missing_counts_or_best_is_off_market_never_reach_the_scorer`
- `test_v2_uses_native_snapshot_age_freshness_without_broad_trackers`
- `test_v2_preclose_interface_has_no_market_pick_evidence_or_persisted_display_argument`

- [ ] **Step 2: Run the evidence tests and observe RED**

```powershell
python -m pytest tests/test_alternative_pick_preclose_v2.py tests/test_market_infra_live_market_display.py -q
```

Expected: imports or assertions fail before the new engine and public ladder helper exist.

- [ ] **Step 3: Expose one exact-event ladder helper without changing broad display behavior**

Add this public wrapper in `market_infra/live_market_display.py`:

```python
def build_exact_event_book_ladder(
    *,
    slate_date: str,
    side: str,
    pick_line: float,
    exact_event_snapshots: list[dict[str, Any]],
    observed_at: datetime | str,
    provider_heartbeats: list[dict[str, Any]] | None = None,
    stale_after_seconds: int = DEFAULT_STALE_AFTER_SECONDS,
) -> dict[str, Any] | None: ...
```

The wrapper receives a prefiltered exact-event slice. Internally reuse `_book_row`, `_dedupe_book_rows`, `_main_line`, `_off_market_books`, and `_best_actionable`. Return an explicit Boolean `best_is_off_market`, the reconciled book rows, main line, best actionable book/line/odds, freshness fields, and no database identifiers not already present in the input. Existing `build_live_market_display_rows` output must remain byte-compatible in tests.

- [ ] **Step 4: Implement the exact binding/window engine**

Expose:

```python
@dataclass(frozen=True)
class ExactPrecloseResult:
    market_evidence: dict[str, Any]
    evidence_window: dict[str, Any]
    proof_fragment: dict[str, Any]

def artifact_current_line_ids_v2(pitcher: Mapping[str, Any]) -> tuple[str, ...]: ...

def resolve_candidate_bindings_v2(
    *, candidate: Mapping[str, Any], pitcher: Mapping[str, Any],
    current_lines_by_id: Mapping[str, Mapping[str, Any]],
    snapshot_rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]: ...

def resolve_candidate_windows_v2(
    *, candidate: Mapping[str, Any], bindings: Mapping[str, Any],
    existing_state_row: Mapping[str, Any] | None,
    observed_at: datetime | str,
) -> dict[str, Any]: ...

def build_exact_preclose_evidence_v2(
    *, candidate: Mapping[str, Any], bindings: Mapping[str, Any],
    windows: Mapping[str, Any], snapshot_rows: Sequence[Mapping[str, Any]],
    provider_heartbeats: Sequence[Mapping[str, Any]],
    observed_at: datetime | str, source_artifact_path: str,
    source_artifact_byte_sha256: str, stale_after_seconds: int = 900,
) -> ExactPrecloseResult: ...
```

Binding and evidence rules:

- Read official provider only from artifact `line_source_provider`.
- Translate `source_current_market_line_ids` and `source_line_ids`; accept numeric compatibility values in `source_snapshot_ids` as current-line IDs and UUID values as seed snapshots.
- Verify current-line slate, provider, event, pitcher, market, official model line, game time, and side-specific snapshot UUID.
- Use explicit provider-event/source-ID binding to tolerate provider start-time skew. Semantic pitcher/side similarity alone is insufficient.
- Keep the existing canonical candidate identity. Store and compare the official binding key in the prior V2 proof; an official binding change resets the whole evidence window. A sidecar binding change resets only that provider-local window.
- Use movement key `(provider, provider_event_id, normalized_pitcher, side, model_line, normalized_book)`.
- Deduplicate exact `(provider, snapshot_id)` tokens. Sort by `(observed_at, id)`.
- At a fixed line, a lower American price is toward the selected side, a higher price is away, and unchanged price is neutral.
- A reversal book is one whose consecutive non-neutral step directions change at least once. Preserve the runtime definition `volatile_book_count == reversal_book_count`; do not invent a new volatility threshold.
- Require at least two distinct official-provider IDs at two timestamps and one official-provider book with two checkpoints.
- Reconcile the same normalized book once across providers. Opposing non-neutral directions for the same book or opposing mature provider majorities make Preclose pending.
- Include an optional sidecar only after exact binding, maturity, and native freshness all pass. Absence or immaturity is diagnostic, not a veto.
- Exact-line movement excludes alternate lines. The ladder may include alternate lines only for the same verified provider event, pitcher, side, and checkpoint.
- Pass already-loaded heartbeat rows through existing freshness helpers. Do not modify heartbeat-hold provider policy.

- [ ] **Step 5: Prove exact-grain behavior and protected helper stability**

```powershell
python -m pytest tests/test_alternative_pick_preclose_v2.py tests/test_market_infra_live_market_display.py tests/test_market_infra_market_evidence.py -q
git diff --exit-code origin/main -- market_infra/market_evidence.py market_infra/provider_freshness.py
```

Expected: exact evidence tests pass; broad evidence and freshness modules are unchanged.

- [ ] **Step 6: Commit Task 2**

```powershell
git add market_infra/alternative_pick_preclose_v2.py market_infra/live_market_display.py tests/test_alternative_pick_preclose_v2.py tests/test_market_infra_live_market_display.py
git commit -m "feat: build exact alternative preclose evidence"
```

---

## Task 3: Add bounded V2 proof/state shaping and the unapplied migration

**Files:**

- Create: `market_infra/alternative_pick_evaluation_proof_v2.py`
- Create: `market_infra/alternative_pick_selection_v2.py`
- Create: `tests/test_alternative_pick_evaluation_proof_v2.py`
- Create: `tests/test_alternative_pick_selection_v2.py`
- Create: `tests/test_alternative_pick_selection_v2_schema.py`
- Create: `supabase/migrations/20260722230000_alternative_pick_v2_evaluation_proof.sql`
- Verify unchanged: `supabase/migrations/20260721222627_alternative_pick_selection_state.sql`

- [ ] **Step 1: Write failing proof, row, and schema tests**

Add tests named:

- `test_v2_proof_contains_recomputable_inputs_bindings_freshness_and_logic`
- `test_v2_proof_uses_bounded_decisive_tokens_and_full_token_digest`
- `test_v2_proof_is_under_the_application_working_ceiling`
- `test_v2_oversized_or_malformed_proof_forces_a_valid_pending_diagnostic`
- `test_v2_proof_rejects_bundle_fingerprint_candidate_or_artifact_mismatch`
- `test_v2_provisional_row_uses_only_v2_ids_and_valid_proof`
- `test_v2_selected_row_can_retain_pending_nonessential_preclose`
- `test_v2_frozen_row_preserves_evaluation_proof_exactly`
- `test_v1_row_remains_valid_with_empty_evaluation_proof`
- `test_v1_missing_evaluation_proof_is_defaulted_by_compatibility_trigger`
- `test_v2_missing_evaluation_proof_is_rejected_not_defaulted`
- `test_v2_migration_is_additive_bounded_and_v1_compatible`
- `test_v2_migration_preserves_unique_rls_grants_and_frozen_triggers`

- [ ] **Step 2: Run the proof/schema tests and observe RED**

```powershell
python -m pytest tests/test_alternative_pick_evaluation_proof_v2.py tests/test_alternative_pick_selection_v2.py tests/test_alternative_pick_selection_v2_schema.py tests/test_alternative_pick_selection_schema.py -q
```

Expected: new imports and migration assertions fail.

- [ ] **Step 3: Implement the bounded evaluation proof**

Expose:

```python
MAX_PROOF_DB_BYTES = 32_768
MAX_PROOF_APPLICATION_BYTES = 30_720

@dataclass(frozen=True)
class EvaluationProofBuild:
    proof: dict[str, Any]
    selection_safe: bool
    reason_codes: tuple[str, ...]

def build_evaluation_proof_v2(
    *, candidate, evaluation, exact_preclose: ExactPrecloseResult, artifact,
) -> EvaluationProofBuild: ...

def validate_evaluation_proof_v2(
    *, proof: Mapping[str, Any], row: Mapping[str, Any] | None = None,
) -> tuple[bool, tuple[str, ...]]: ...
```

Use this bounded top-level shape:

```text
schema_version: "v2"
bundle_id
selector_fingerprint
candidate
artifact
bindings
freshness
normalized_inputs
preclose
decision
```

`candidate` stores canonical identity, slate, normalized pitcher, side, model line, game time, `line_source_provider`, and official binding key. `bindings` stores bounded provider roles, event/current-line IDs, seed tokens, window starts, and maturity. `preclose` stores full qualifying count, decisive provider-qualified tokens, SHA-256 of the full ordered token list, exact aggregates, Boolean off-market status, score, label, and reasons. `decision` stores support, drag, no-drag, all family states, both lane states, selected lane/status, decisive families, and whether Preclose was required for the selected lane.

Do not truncate a selected proof. If construction or validation fails, emit a small valid diagnostic proof with `selection_status=pending`, no lane, and reason `evaluation_proof_invalid` or `evaluation_proof_oversized`.

- [ ] **Step 4: Implement V2 provisional/frozen row shaping**

Expose:

```python
def build_provisional_row_v2(
    *, candidate: dict[str, Any], evaluation: Any,
    exact_preclose: ExactPrecloseResult,
    proof_build: EvaluationProofBuild,
    artifact: dict[str, Any], observed_at: str,
) -> dict[str, Any] | None: ...
```

Reuse the V1 canonical row/lock helpers without changing them. It is acceptable to call the existing V1 provisional builder only for common canonical field shaping, then replace and fully revalidate bundle/selector identity and add `evaluation_proof`. Reuse `build_frozen_row`; its copy semantics must preserve the proof. A proof failure forces pending but must not suppress the row or affect V1.

Set row evidence fields from the same exact proof: `evidence_observation_ids` is the bounded decisive provider-qualified token list, `evidence_observation_count` is the full qualifying count, and first/last timestamps cover the full qualifying exact window. These fields must never be copied from the broad tracker.

- [ ] **Step 5: Add the one-column migration**

`supabase/migrations/20260722230000_alternative_pick_v2_evaluation_proof.sql` must:

```sql
alter table public.alternative_pick_selection_state
  add column if not exists evaluation_proof jsonb not null default '{}'::jsonb;
```

The existing V1 PostgREST upsert omits this new column. Add one narrow compatibility trigger so an omitted/null proof remains valid only for the frozen V1 bundle, even when PostgREST does not send `Prefer: missing=default`:

```sql
create or replace function public.default_alternative_pick_v1_evaluation_proof()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.bundle_id = 'pregame_alternative_pick_methodology_v1'
     and new.evaluation_proof is null then
    new.evaluation_proof := '{}'::jsonb;
  end if;
  return new;
end;
$$;

drop trigger if exists alternative_pick_selection_state_default_v1_proof
  on public.alternative_pick_selection_state;
create trigger alternative_pick_selection_state_default_v1_proof
before insert or update on public.alternative_pick_selection_state
for each row execute function public.default_alternative_pick_v1_evaluation_proof();
```

Do not change the shared writer's request headers globally. The V1 trigger is the migration-local compatibility boundary; a V2 null proof must still fail the non-null/V2 checks.

Add constraints that:

- `alternative_pick_selection_state_evaluation_proof_object_check`: `evaluation_proof` is a JSON object;
- `alternative_pick_selection_state_evaluation_proof_size_check`: `octet_length(evaluation_proof::text) <= 32768`;
- `alternative_pick_selection_state_v2_evaluation_proof_check`: V2 bundle/fingerprint/candidate/artifact/decision consistency;
- V1 rows may use `{}`;
- V2 rows require `schema_version='v2'`, the V2 bundle, matching row fingerprint, matching candidate identity, and matching source artifact payload/byte hashes.

Do not change existing uniqueness, RLS, grants, frozen triggers, V1 rows, or the applied V1 migration. The only new trigger is the named V1 proof-compatibility trigger above.

- [ ] **Step 6: Prove state and schema behavior**

```powershell
python -m pytest tests/test_alternative_pick_evaluation_proof_v2.py tests/test_alternative_pick_selection_v2.py tests/test_alternative_pick_selection_v2_schema.py tests/test_alternative_pick_selection_state.py tests/test_alternative_pick_selection_schema.py -q
git diff --exit-code origin/main -- supabase/migrations/20260721222627_alternative_pick_selection_state.sql
```

Expected: all tests pass; the applied V1 migration is unchanged.

- [ ] **Step 7: Commit Task 3**

```powershell
git add market_infra/alternative_pick_evaluation_proof_v2.py market_infra/alternative_pick_selection_v2.py tests/test_alternative_pick_evaluation_proof_v2.py tests/test_alternative_pick_selection_v2.py tests/test_alternative_pick_selection_v2_schema.py supabase/migrations/20260722230000_alternative_pick_v2_evaluation_proof.sql
git commit -m "feat: add bounded alternative v2 decision proof"
```

---

## Task 4: Add the separately gated V2 recorder and safe one-key activation helper

**Files:**

- Create: `market_infra/alternative_pick_recording_v2.py`
- Create: `tests/test_alternative_pick_live_layer_v2.py`
- Create: `scripts/update_render_service_env.py`
- Create: `tests/test_update_render_service_env.py`
- Create: `scripts/check_alternative_pick_v2_activation_window.py`
- Create: `tests/test_alternative_pick_v2_activation_window.py`
- Modify: `scripts/build_live_events_to_supabase.py`
- Modify: `tests/test_live_layer_worker.py`

- [ ] **Step 1: Write failing version-gate and integration tests**

Add tests named:

- `test_bundle_version_unset_or_blank_defaults_to_v1`
- `test_bundle_version_accepts_exact_v1_and_v2`
- `test_explicit_invalid_bundle_version_skips_sidecar_cycle`
- `test_v2_capable_deploy_with_default_gate_writes_zero_v2_rows`
- `test_v1_dispatch_retains_existing_arguments_and_output`
- `test_v2_writer_receives_existing_snapshots_and_heartbeats_without_new_provider_reads`
- `test_v2_writer_has_no_broad_market_evidence_or_persisted_display_dependency`
- `test_v2_writer_batches_existing_state_locks_and_current_lines_once_each`
- `test_v2_writer_uses_only_tracked_non_pass_current_artifact_candidates`
- `test_v2_selected_lane_with_pending_preclose_persists_selected`
- `test_v2_selected_lane_with_pending_preclose_freezes_selected_at_exact_lock`
- `test_v2_relevant_pending_dependency_freezes_pending`
- `test_v2_never_reconstructs_missed_or_existing_frozen_rows`
- `test_v2_proof_failure_is_sidecar_only_and_does_not_touch_other_tables`
- `test_v2_timeout_and_exception_return_bounded_failure_summary`
- `test_render_env_helper_dry_run_preserves_every_existing_key_and_value`
- `test_render_env_helper_execute_puts_complete_list_and_verifies_target`
- `test_render_env_helper_paginates_every_page_before_full_list_put`
- `test_render_env_helper_can_restore_original_absence_with_unset`
- `test_render_env_helper_never_prints_environment_values`
- `test_render_env_helper_rejects_more_than_one_change_or_unapproved_key`
- `test_activation_preflight_uses_exact_artifact_candidates_not_v1_state`
- `test_activation_preflight_fails_at_or_past_first_candidate_t30`
- `test_activation_preflight_rejects_stale_wrong_date_or_retired_source`
- `test_activation_preflight_zero_candidates_is_safe_but_not_release_evidence`

- [ ] **Step 2: Run the integration tests and observe RED**

```powershell
python -m pytest tests/test_alternative_pick_live_layer_v2.py tests/test_live_layer_worker.py tests/test_update_render_service_env.py tests/test_alternative_pick_v2_activation_window.py -q
```

Expected: V2 recorder imports/gate assertions fail.

- [ ] **Step 3: Implement the focused V2 recorder**

Expose from `market_infra/alternative_pick_recording_v2.py`:

```python
def record_alternative_pick_selection_v2(
    *, writer: SupabaseMarketWriter, slate_date: str, payload: dict[str, Any],
    snapshot_rows: list[dict[str, Any]],
    provider_heartbeats: list[dict[str, Any]],
    observed_at: datetime, artifact_source: str,
    source_payload_sha256: str, source_artifact_byte_sha256: str,
    operational_pick_locks: dict[str, Any],
    market_line_build: dict[str, Any],
    shadow_pipeline_timing: dict[str, Any],
    ready_to_bet_write: dict[str, Any],
    budget_seconds: float = 5.0,
) -> dict[str, Any]: ...
```

This module owns V2 candidate scanning, collision detection, bounded PostgREST reads, binding/window resolution, exact evidence, evaluation, proof, row shaping, and writes. It must not import the live-layer script and must not accept broad market-evidence/display arguments.

Within the five-second budget, issue at most one batch read each for:

1. current-slate V2 provisional/frozen rows including `evaluation_proof`;
2. exact operational lock rows for candidate dedupe keys; and
3. artifact-declared numeric `current_market_lines` IDs.

Upsert V2 provisional rows on the existing six-column uniqueness contract and insert-ignore frozen rows using the existing frozen conflict contract. Preserve one provisional and one frozen ceiling per eligible pick/bundle. Never update frozen rows.

- [ ] **Step 4: Add the runtime gate and narrow dispatch**

In `scripts/build_live_events_to_supabase.py`, add:

```python
def _alternative_pick_selection_bundle_version() -> str | None:
    raw = os.getenv("ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION")
    if raw is None or not raw.strip():
        return "v1"
    value = raw.strip().lower()
    return value if value in {"v1", "v2"} else None
```

Keep the current `_write_alternative_pick_selection_state` V1 body unchanged. At the existing post-lock sidecar call site:

- return `invalid_bundle_version` when mode is `record` and the explicit version is invalid;
- call the existing V1 writer for `v1` with its current broad arguments;
- call `record_alternative_pick_selection_v2` for `v2` with snapshots and the already-loaded `provider_heartbeats`, but without broad rows; and
- keep `off` behavior unchanged.

Do not apply V1's unconditional freeze downgrade (`evidence ready/fresh` check) to V2. V2 proof/lane dependencies decide whether a selected row may freeze with Preclose pending.

- [ ] **Step 5: Implement the dry-run-first Render environment helper**

Create `scripts/update_render_service_env.py` using the standard library only. Its exact operator interface is:

```powershell
python scripts/update_render_service_env.py --service-id crn-d7tpb19o3t8c739p3qig --set ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION=v2
python scripts/update_render_service_env.py --service-id crn-d7tpb19o3t8c739p3qig --set ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION=v2 --execute
python scripts/update_render_service_env.py --service-id crn-d7tpb19o3t8c739p3qig --unset ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION
```

The helper must:

1. read `RENDER_API_KEY` from the process environment and never print it;
2. GET `/v1/services/{serviceId}/env-vars?limit=100`, follow each page's sibling `cursor` to exhaustion, reject repeated cursors, and only then treat the service-level environment as complete;
3. preserve every existing key and value across every page in memory;
4. accept exactly one `--set` or `--unset` operation per invocation, limited to `ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION` or the emergency-stop key `ALTERNATIVE_PICK_SELECTION_MODE`;
5. show only total key count, page count, redacted changed-key name, and `original_state=present|absent` during dry run—never the original or target value;
6. perform the full-list PUT only with `--execute`;
7. paginate the post-PUT GET to exhaustion and verify the exact expected key set plus target presence/value in memory without printing any values; and
8. exit nonzero on HTTP error, incomplete pagination, repeated cursor, duplicate key, key-set drift, target mismatch, or an unapproved operation.

The `--unset` path must remove only the named key from the complete preserved list so Gate C can restore the exact original absence. The PUT is an environment mutation only; it does not count as deployment proof. Gate C still performs and verifies a separate deploy.

- [ ] **Step 6: Implement the exact-artifact activation preflight**

Create `scripts/check_alternative_pick_v2_activation_window.py` with this interface:

```powershell
python scripts/check_alternative_pick_v2_activation_window.py --artifact-url "https://baseballbettingedge.netlify.app/.netlify/functions/get-artifact?type=today"
```

The helper fetches the Netlify/Supabase `today` artifact once, applies the same current-slate/source/tracked-non-PASS candidate rules as the V2 recorder, and computes every candidate's T-30 from the artifact game time. It must fail nonzero for a stale or wrong-Phoenix-date artifact, retired/unapproved source posture, malformed candidate time, or any eligible candidate already at/past T-30. It reports only artifact hashes/timestamp, candidate count, first T-30, and one of `clean`, `no_candidates`, or `too_late`; V1 state is not an input. Reuse one pure candidate-extraction helper from `alternative_pick_recording_v2.py` so preflight and runtime cannot drift.

- [ ] **Step 7: Prove integration and protected behavior**

```powershell
python -m pytest tests/test_alternative_pick_live_layer_v2.py tests/test_live_layer_worker.py tests/test_notification_coordinator.py tests/test_operational_locks.py tests/test_market_infra_supabase_writer.py tests/test_update_render_service_env.py tests/test_alternative_pick_v2_activation_window.py -q
git diff --check
```

Expected: V1 and V2 dispatch tests pass; notification and lock tests remain green.

- [ ] **Step 8: Commit Task 4**

```powershell
git add market_infra/alternative_pick_recording_v2.py scripts/build_live_events_to_supabase.py scripts/update_render_service_env.py scripts/check_alternative_pick_v2_activation_window.py tests/test_alternative_pick_live_layer_v2.py tests/test_live_layer_worker.py tests/test_update_render_service_env.py tests/test_alternative_pick_v2_activation_window.py
git commit -m "feat: gate the alternative v2 recorder"
```

---

## Task 5: Freeze synthetic mature-Preclose and historical parity evidence

**Files:**

- Create: `analytics/diagnostics/alternative_pick_v2_historical_comparator.py`
- Create: `tests/test_alternative_pick_v2_historical_comparator.py`
- Create: `tests/fixtures/alternative_pick_selection_v2/synthetic_mature_preclose.json`
- Create: `tests/fixtures/alternative_pick_selection_v2/legacy_official_close_parity.json.gz`
- Create: `tests/fixtures/alternative_pick_selection_v2/manifest.json`
- Create: `tests/test_alternative_pick_selection_v2_fixtures.py`
- Modify: `docs/superpowers/specs/2026-07-22-alt-picks-dependency-aware-v2-design.md`
- Modify: `docs/superpowers/plans/2026-07-22-alt-picks-dependency-aware-v2.md`

- [ ] **Step 1: Preserve the approved provenance amendment**

The bounded read-only audit found 47 V1 state rows, including 10 rows at or
before 18:31Z with seven canonical and seven byte hashes, but zero matching
raw artifacts. `artifact_snapshots` has no 2026-07-22 capture under any kind,
path, or time; all 111 surviving `published_pipeline_artifacts` rows, the
repository, and local JSON archives also had zero exact hash matches. The
5,259 bounded tracker rows are not an admissible substitute.

Tyler approved replacing that unrecoverable historical fixture with the next
prospectively retained exact fixture. Task 5 continues with synthetic evidence
and the frozen historical comparator. Tasks 6-9 may proceed on held branches,
but the Prospective Capture Gate below blocks Task 10 and every production
migration, activation, endpoint/UI deployment, or source change.

The separate July 21 hybrid Gate C research corpus was recovered intact. Its
`3,106` source rows include all `1,621` tracked official-close rows through
`2026-07-20`; corpus SHA-256 is
`c59cc4fd2a03110ad492163240f5563a85e142d785c258eeb25914ad0273bda4`
and source-manifest SHA-256 is
`7f59abe7a4522e793e68a58bac92122585fbfea76658a63b0d09bb3195c85072`.
Freeze a compact exact-field projection of those tracked rows for historical
parity only. This does not repair or replace the missing prospective 18:31Z
artifact and does not open any production gate.

- [ ] **Step 2: Write failing synthetic-fixture and comparator tests**

Add tests named:

- `test_v2_fixture_manifest_hashes_match_raw_bytes`
- `test_v2_fixture_manifest_marks_prospective_capture_required`
- `test_v2_synthetic_fixture_contains_no_broad_tracker_or_hindsight_input`
- `test_v2_synthetic_fixture_resolves_affirmative_exact_preclose`
- `test_v2_replay_starts_prospective_ledger_at_zero`
- `test_legacy_official_close_comparator_reproduces_frozen_lane_anchors`
- `test_legacy_comparator_cutoff_is_2026_07_20_and_never_writes_prospective_state`

- [ ] **Step 3: Run replay tests and observe RED**

```powershell
python -m pytest tests/test_alternative_pick_selection_v2_fixtures.py tests/test_alternative_pick_v2_historical_comparator.py -q
```

Expected: synthetic fixture/comparator files or expected hashes are absent.

- [ ] **Step 4: Add the synthetic fixture and pending-capture manifest**

The synthetic fixture must independently prove mature official-provider exact-line movement and exact-event ladder calculation, including a permitted alternate line used only for off-market context.

The fixture manifest stores SHA-256 of each present fixture's raw bytes and a short source description. For the compressed historical fixture it also binds the recovered source-corpus, source-manifest, and source-summary hashes, the exact cutoff, row counts, and hindsight-only classification. It records `prospective_capture.status = "required_before_production_gate_a"` without inventing a filename, hash, candidates, or expected decisions. Hashes and capture status change only through explicit fixture review.

- [ ] **Step 5: Implement the frozen legacy official-close comparator**

Expose:

```python
def historical_family_flags(row: dict[str, Any]) -> dict[str, bool]: ...
def summarize_legacy_official_close(
    rows: list[dict[str, Any]], *, end_date: date = date(2026, 7, 20),
) -> dict[str, Any]: ...
```

Reuse the existing Gate C dataset and existing research predicate helpers. For the frozen historical comparator only:

```text
base = strong_base_strict_plus_selective
anchor = market_anchor_strict OR (base AND market_anchor_core)
preclose = base AND strong_preclose_clv_proxy
reentry = source_fire AND moderate_edge_quality_reentry
support = base OR market_anchor_strict
no_drag = support AND NOT drag_core
consensus = no_drag AND explicit_family_count >= 2
expansion = reentry AND NOT no_drag
```

Keep the two lanes disjoint and score flat one-unit official-close outcomes through the fixed 2026-07-20 cutoff. Preserve the published lab convention by rounding each row's PnL to three decimals before summing; do not hardcode lane membership or outcomes. Label this output hindsight-capable research; do not import it into runtime, proof, endpoint, UI, or prospective state.

- [ ] **Step 6: Prove deterministic replay and historical separation**

```powershell
python -m pytest tests/test_alternative_pick_selection_v2_fixtures.py tests/test_alternative_pick_v2_historical_comparator.py tests/test_alternative_pick_selector_v2.py tests/test_alternative_pick_preclose_v2.py -q
python analytics/diagnostics/alternative_pick_v2_historical_comparator.py --end-date 2026-07-20
python analytics/diagnostics/no_drag_composite_canary_audit.py
```

Expected: the synthetic exact-evidence decision matches the specification; the frozen comparator reports Consensus `106-46`, `+32.603u`, Expansion `42-38`, `+5.982u`, and disjoint combined `148-84`, `+38.585u`; the no-drag report remains a separate research tracker; the manifest keeps the prospective capture gate closed; and no V2 prospective result/PnL row is created.

- [ ] **Step 7: Commit Task 5**

```powershell
git add analytics/diagnostics/alternative_pick_v2_historical_comparator.py tests/test_alternative_pick_v2_historical_comparator.py tests/fixtures/alternative_pick_selection_v2/synthetic_mature_preclose.json tests/fixtures/alternative_pick_selection_v2/legacy_official_close_parity.json.gz tests/fixtures/alternative_pick_selection_v2/manifest.json tests/test_alternative_pick_selection_v2_fixtures.py docs/superpowers/specs/2026-07-22-alt-picks-dependency-aware-v2-design.md docs/superpowers/plans/2026-07-22-alt-picks-dependency-aware-v2.md
git commit -m "test: freeze alternative v2 synthetic evidence"
```

---

## Task 6: Version and sanitize the Netlify endpoint contract

**Files:**

- Modify: `netlify/functions/alternative-picks.mjs`
- Modify: `tests/test_alternative_picks_function.mjs`

- [ ] **Step 0: Fork a held web branch from the reviewed core branch**

```powershell
git switch codex/alt-picks-dependency-aware-v2
git switch -c codex/alt-picks-dependency-aware-v2-web
```

The core branch contains Tasks 1-5. Keep both the endpoint and browser switch on this held web branch until production V2 rows pass Task 12. This prevents an explicit public V2 contract or V2 browser request from deploying early.

- [ ] **Step 1: Write failing endpoint compatibility and proof tests**

Add Node tests named:

- `alternative-picks defaults an unversioned request to v1`
- `alternative-picks serves explicit bundle_version v1 and v2 independently`
- `alternative-picks rejects unsupported explicit bundle versions`
- `alternative-picks includes bundle and fingerprint on ready empty and unavailable payloads`
- `alternative-picks filters Supabase by the selected bundle`
- `alternative-picks rejects missing malformed oversized or cross-row v2 proof`
- `alternative-picks rejects mixed selector identity family logic and artifact hashes`
- `alternative-picks sanitizes v2 proof without provider identifiers`
- `alternative-picks allows selected v2 with pending nonessential preclose and zero observations`
- `alternative-picks keeps old client to new endpoint on the v1 contract`

- [ ] **Step 2: Run endpoint tests and observe RED**

```powershell
node --test tests/test_alternative_picks_function.mjs
```

Expected: new handshake/proof assertions fail against the V1-only endpoint.

- [ ] **Step 3: Implement an immutable contract map**

Use:

```javascript
const CONTRACTS = Object.freeze({
  v1: Object.freeze({
    bundleId: 'pregame_alternative_pick_methodology_v1',
    selectorFingerprint: 'f8f7ccf652b8eda4860d07798bc4673920b0b9d727552bc7e2e6547d478b4579',
    selectorIds: Object.freeze({
      consensus_core: 'no_drag_distinct_family_consensus_core_v1',
      reentry_expansion: 'moderate_edge_quality_reentry_expansion_v1',
    }),
    requiresProof: false,
  }),
  v2: Object.freeze({
    bundleId: 'pregame_alternative_pick_methodology_v2',
    selectorFingerprint: '23bacff0fa923685ae52c5a9cfbadfb9f5902fb64d91759cfe9b4b1169a221c4',
    selectorIds: Object.freeze({
      consensus_core: 'no_drag_distinct_family_consensus_core_v2',
      reentry_expansion: 'moderate_edge_quality_reentry_expansion_v2',
    }),
    requiresProof: true,
  }),
});
```

No `bundle_version`, blank, or exact `v1` serves V1. Exact `v2` serves V2. Any other explicit value returns unavailable with `unsupported_bundle_version` and the requested contract fields null.

Every non-HTTP-error payload includes top-level `bundle_id` and `selector_fingerprint`. Query the selected bundle only and include `evaluation_proof` in state selection. Suppress invalid rows before counts.

For V2, validate proof size, schema, bundle/fingerprint, candidate identity, artifact hashes, family states/count, lane states, selection status, selected lane, and decisive families. Expose only:

```javascript
decision_proof: {
  support,
  drag_core,
  no_drag,
  lane_states,
  decisive_families,
  preclose_required_for_selected_lane,
}
```

Never expose provider event IDs, current-line IDs, snapshot tokens, bindings, normalized raw inputs, or token hashes.

- [ ] **Step 4: Prove endpoint compatibility and sanitization**

```powershell
node --test tests/test_alternative_picks_function.mjs
node --check netlify/functions/alternative-picks.mjs
```

Expected: all endpoint tests pass and syntax is valid.

- [ ] **Step 5: Commit Task 6**

```powershell
git add netlify/functions/alternative-picks.mjs tests/test_alternative_picks_function.mjs
git commit -m "feat: serve versioned alternative pick contracts"
```

---

## Task 7: Make the isolated Alt Picks adapter/UI consume V2

**Files:**

- Modify: `dashboard/v2-alt-picks.js`
- Modify: `dashboard/v2-alt-picks.test.mjs`
- Modify: `dashboard/v2-app.jsx`
- Regenerate: `dashboard/v2-app.js`
- Modify: `dashboard/v2-app.test.mjs`
- Modify: `dashboard/v2.html`
- Modify: `tests/test_dashboard_alt_picks_ui.py`
- Verify unchanged behavior: `tests/test_dashboard_accepted_bet_log.py`

- [ ] **Step 0: Continue on the held web branch**

```powershell
git branch --show-current
```

Expected: `codex/alt-picks-dependency-aware-v2-web`. Do not switch the browser adapter on the core branch.

- [ ] **Step 1: Write failing adapter and selected-with-pending UI tests**

Add tests that prove:

- the adapter calls only `/.netlify/functions/alternative-picks?bundle_version=v2`;
- exact top-level V2 bundle and fingerprint are required before accepting rows or counts;
- missing/wrong handshake makes the whole Alt surface unavailable;
- any invalid V2 row makes the whole response unavailable rather than partially rendering;
- counts are recomputed from accepted rows and cannot trust inconsistent server counts;
- selected V2 with zero Preclose observations is accepted only when `decision_proof` proves a selected lane and marks Preclose nonessential/pending;
- a pending chip is neither counted nor styled as agreement/disagreement;
- card and sheet say `Selected with 2 confirmed families; Preclose still pending.` when applicable;
- lane, checkpoint, confirmed count, exact freshness, and comparison-only disclaimer remain visible;
- `dashboard/v2.html` loads both changed Alt assets with the exact new `2026-07-22-alt-picks-v2` cache token and no old V1 Alt token;
- no wager, stake, units, PnL, Log Bet, notification, or FIRE-red promotion control appears;
- Picks, Results, accepted-bet state, and official data promises are unchanged.

- [ ] **Step 2: Run adapter/UI tests and observe RED**

```powershell
node --test dashboard/v2-alt-picks.test.mjs dashboard/v2-app.test.mjs
python -m pytest tests/test_dashboard_alt_picks_ui.py tests/test_dashboard_accepted_bet_log.py -q
```

Expected: the V1 request and V1 response validation fail new assertions.

- [ ] **Step 3: Implement the V2-only browser handshake**

In `dashboard/v2-alt-picks.js`:

```javascript
const ENDPOINT = '/.netlify/functions/alternative-picks?bundle_version=v2';
const BUNDLE_ID = 'pregame_alternative_pick_methodology_v2';
const SELECTOR_FINGERPRINT = '23bacff0fa923685ae52c5a9cfbadfb9f5902fb64d91759cfe9b4b1169a221c4';
```

Require the exact response-level handshake before normalizing any row. Validate the sanitized decision proof against family/lane/status fields. Preserve isolated fetch/error state and do not add the request to `window.__v2DataPromise`.

- [ ] **Step 4: Add accurate selected-with-pending copy**

Add a pure helper used by both `AltPickCard` and `AltPickSheet`:

```javascript
function altSelectionProofCopy(row) {
  const pending = Object.entries(row.family_states)
    .filter(([, vote]) => vote.state === 'pending')
    .map(([name]) => name);
  if (row.selection_status === 'selected' && pending.length) {
    return `Selected with ${row.family_count} confirmed families; ${familyTitle(pending[0])} still pending.`;
  }
  return `Selected with ${row.family_count} confirmed families.`;
}
```

Render it only for selected rows. Keep supporting pending/not-selected rows in their existing collapsed section. Continue showing official pick fields as comparison context only.

- [ ] **Step 5: Bust both changed browser assets as one reviewed release**

In `dashboard/v2.html`, change exactly:

```html
<script src="v2-alt-picks.js?v=2026-07-22-alt-picks-v2"></script>
<script src="v2-app.js?v=2026-07-22-alt-picks-v2" defer></script>
```

The UI tests must reject the old `?v=2026-07-21-alt-picks` token for either file. This prevents a new adapter from running beside a cached V1 application bundle, or vice versa.

- [ ] **Step 6: Regenerate the checked-in JavaScript build**

```powershell
Set-Location dashboard
npx --yes -p @babel/core@7 -p @babel/cli@7 -p @babel/preset-react@7 babel v2-app.jsx --presets=@babel/preset-react -o v2-app.js
Set-Location ..
```

- [ ] **Step 7: Prove UI behavior and local responsive states**

```powershell
node --test dashboard/v2-alt-picks.test.mjs dashboard/v2-app.test.mjs dashboard/v2-data.test.mjs dashboard/v2-movement-helpers.test.mjs
node --check dashboard/v2-alt-picks.js
node --check dashboard/v2-app.js
python -m pytest tests/test_dashboard_alt_picks_ui.py tests/test_dashboard_accepted_bet_log.py -q
rg -n "v2-alt-picks.js\?v=2026-07-22-alt-picks-v2|v2-app.js\?v=2026-07-22-alt-picks-v2" dashboard/v2.html
```

Serve `dashboard/` locally with intercepted selected, selected-with-pending, pending-only, empty, mismatch, and unavailable responses. Inspect at `1280x900` and `390x844`. Expected: no horizontal overflow; identity/pick/lane/freeze precede detail; chips wrap; the sheet remains in the viewport; Picks and Results remain unchanged.

- [ ] **Step 8: Commit Task 7**

```powershell
git add dashboard/v2-alt-picks.js dashboard/v2-alt-picks.test.mjs dashboard/v2-app.jsx dashboard/v2-app.js dashboard/v2-app.test.mjs dashboard/v2.html tests/test_dashboard_alt_picks_ui.py
git commit -m "feat: show dependency-aware alternative picks v2"
git rev-parse HEAD
git switch codex/alt-picks-dependency-aware-v2
```

Record the web commit SHA. Do not cherry-pick or merge either Task 6 or Task 7 into the core branch yet.

---

## Task 8: Complete local verification, documentation, and independent review

**Files:**

- Modify: `docs/superpowers/specs/2026-07-22-alt-picks-dependency-aware-v2-design.md`
- Modify: `docs/superpowers/plans/2026-07-22-alt-picks-dependency-aware-v2.md`
- Modify: `docs/current-state.md`

- [ ] **Step 1: Verify the held web branch with all focused suites together**

```powershell
git switch codex/alt-picks-dependency-aware-v2-web
python -m pytest tests/test_alternative_pick_selector.py tests/test_alternative_pick_selector_v2.py tests/test_alternative_pick_preclose_v2.py tests/test_alternative_pick_evaluation_proof_v2.py tests/test_alternative_pick_selection_state.py tests/test_alternative_pick_selection_v2.py tests/test_alternative_pick_selection_schema.py tests/test_alternative_pick_selection_v2_schema.py tests/test_alternative_pick_live_layer_v2.py tests/test_alternative_pick_selection_v2_fixtures.py tests/test_alternative_pick_v2_historical_comparator.py tests/test_live_layer_worker.py tests/test_update_render_service_env.py tests/test_alternative_pick_v2_activation_window.py -q
node --test tests/test_alternative_picks_function.mjs dashboard/v2-alt-picks.test.mjs dashboard/v2-app.test.mjs
```

Expected: all pass.

- [ ] **Step 2: Run the full Python and Node suites**

```powershell
python -m pytest tests/ -q
node --test dashboard/*.test.mjs tests/*.mjs
node --check netlify/functions/alternative-picks.mjs
node --check dashboard/v2-alt-picks.js
node --check dashboard/v2-app.js
git diff --check
```

Expected: all commands exit zero.

- [ ] **Step 3: Prove protected behavior and V1 byte stability**

```powershell
git diff --exit-code origin/main -- market_infra/alternative_pick_selector.py market_infra/alternative_pick_selector_manifest_v1.json supabase/migrations/20260721222627_alternative_pick_selection_state.sql market_infra/market_evidence.py market_infra/provider_freshness.py
git diff origin/main...HEAD -- render.yaml netlify.toml .github/workflows data/params.json pipeline dashboard/data data/picks_history.json
git grep -n "ALTERNATIVE_PICK_SELECTION" -- . ':!docs'
git status --short
```

Expected: protected V1/evidence/freshness files unchanged; no provider/model/artifact/workflow/config mutation; mode defaults off; bundle defaults V1; only intentional feature/test/docs files are changed.

- [ ] **Step 4: Return to and verify the core branch independently**

```powershell
git switch codex/alt-picks-dependency-aware-v2
python -m pytest tests/test_alternative_pick_selector.py tests/test_alternative_pick_selector_v2.py tests/test_alternative_pick_preclose_v2.py tests/test_alternative_pick_evaluation_proof_v2.py tests/test_alternative_pick_selection_state.py tests/test_alternative_pick_selection_v2.py tests/test_alternative_pick_selection_schema.py tests/test_alternative_pick_selection_v2_schema.py tests/test_alternative_pick_live_layer_v2.py tests/test_alternative_pick_selection_v2_fixtures.py tests/test_alternative_pick_v2_historical_comparator.py tests/test_live_layer_worker.py tests/test_update_render_service_env.py tests/test_alternative_pick_v2_activation_window.py -q
node --test tests/test_alternative_picks_function.mjs
python -m pytest tests/ -q
node --test dashboard/*.test.mjs tests/*.mjs
git diff --check
```

Expected: the core branch passes without the held endpoint/UI commits. Production remains on the existing V1 endpoint and browser contract.

- [ ] **Step 5: Update the implementation handoff on the core branch**

Record:

- exact V2 fingerprint and migration filename;
- final test commands/results;
- V2-capable but unapplied/undeployed posture;
- migration, Render deploy, V2 activation, and Netlify deploy still closed;
- zero prospective V2 production rows; and
- immediate and dependency-ordered rollback.

Do not claim production readiness from local tests alone.

- [ ] **Step 6: Commit the implementation handoff**

```powershell
git add docs/superpowers/specs/2026-07-22-alt-picks-dependency-aware-v2-design.md docs/superpowers/plans/2026-07-22-alt-picks-dependency-aware-v2.md docs/current-state.md
git commit -m "docs: hand off default-v1 alternative picks v2"
```

- [ ] **Step 7: Run independent specification and code-quality review on both branches**

Use separate subagents for:

1. specification compliance against the approved V2 design; and
2. code quality/safety, especially exact evidence grain, proof validation, five-second failure handling, V1 preservation, query bounds, endpoint sanitization, and UI isolation.

Review the core branch first, then the held web diff against the core branch. Fix every Critical or Important finding. Rerun the focused suite after each fix and the full suite after all fixes. Commit review fixes to the branch that owns them.

---

## Task 9: Push the reviewed core and held web branches without merging

**Files:**

- Git history only.

- [ ] **Step 1: Push both reviewed branches**

```powershell
git switch codex/alt-picks-dependency-aware-v2
git push -u origin codex/alt-picks-dependency-aware-v2
git switch codex/alt-picks-dependency-aware-v2-web
git push -u origin codex/alt-picks-dependency-aware-v2-web
git switch codex/alt-picks-dependency-aware-v2
```

- [ ] **Step 2: Prepare two separate reviewed integration units**

Prepare:

- a core change set containing selector, exact evidence, proof/migration, recorder, the synthetic fixture plus pending-capture manifest, tests, and core handoff docs; and
- a held web change set from the core branch to `codex/alt-picks-dependency-aware-v2-web`, containing the backward-compatible endpoint plus V2 browser adapter/UI.

Do not merge either yet. Netlify deploys the production branch, so holding the web branch prevents both an early explicit V2 endpoint and an early browser switch.

- [ ] **Step 3: Confirm production remains on V1 before any mutation gate**

Read-only checks must show:

- `evaluation_proof` migration not yet applied unless separately approved;
- `bbe-live-layer` still on the prior reviewed deployment;
- `ALTERNATIVE_PICK_SELECTION_MODE=record` only on the existing live-layer service;
- bundle version absent or V1;
- zero V2 state rows; and
- Netlify still serving the reviewed V1 UI/endpoint deploy; and
- both reviewed branches exist on origin but `main` has not moved.

Stop and report before the Prospective Capture Gate.

---

## Prospective Capture Gate - required before Task 10

**Requires:** Tyler approval to perform the read-only capture on a future clean
normal slate. This gate authorizes no database write, migration, Render change,
provider request, model change, notification change, lock change, or UI deploy.

- [ ] **Step 1: Capture the exact current artifact before every eligible T-30**

Fetch the official Netlify/Supabase `get-artifact?type=today` response once.
Record the raw response bytes, Phoenix slate date, `generated_at`, source posture,
artifact path, raw-byte SHA-256, and canonical-payload SHA-256. In the same
checkpoint, read the contemporaneous `published_pipeline_artifacts` row and
require both hashes and the artifact path to match. If any eligible candidate
is at/past T-30, the slate/date/source is wrong or stale, or the hash pair does
not match, delete the temporary capture and defer to the next slate.

- [ ] **Step 2: Bind only artifact-declared exact evidence**

Read only the snapshot IDs and numeric current-line IDs declared in those exact
captured bytes. Require every snapshot observation and every admitted mutable
line `updated_at` to be no later than the capture checkpoint. Bind exact slate,
provider, event, pitcher, market, side, line, and supported book. Do not use a
broad tracker, later line, later artifact, official close, result, actual Ks,
PnL, CLV outcome, accepted bet, notification, or post-start observation.

- [ ] **Step 3: Sanitize, hash, replay, and review the prospective fixture**

Commit a date-stamped sanitized fixture and update `manifest.json` with its raw
SHA-256, official artifact hash pair, capture timestamp, maximum source
timestamp, source description, and `prospective_capture.status = "complete"`.
Add fixture-integrity tests for exact hashes, source timestamps, forbidden
fields, expected family/lane decisions, V1 non-mutation, and a zero-start V2
prospective ledger. Replay must pass deterministically and receive independent
task review before Task 10 may begin.

Until all three steps pass, the migration, V2 runtime activation, explicit V2
endpoint/browser request, Netlify UI deployment, merge, and every production
gate remain closed.

---

## Task 10: Production Gate A - apply and verify only the proof-column migration

**Requires:** Tyler approval for this exact database mutation.

**Files changed externally:** Supabase schema only.

- [ ] **Step 0: Use the reviewed core branch**

```powershell
git switch codex/alt-picks-dependency-aware-v2
git status --short
```

Expected: clean reviewed core branch containing the single unapplied migration.

- [ ] **Step 1: Dry-run the linked migration**

```powershell
npx supabase db push --linked --dry-run
```

Expected: only `20260722230000_alternative_pick_v2_evaluation_proof.sql` is pending. If any other migration appears, stop.

- [ ] **Step 2: Apply the migration**

```powershell
npx supabase db push --linked
```

Expected: the one approved migration applies successfully.

- [ ] **Step 3: Verify schema, privileges, and V1 preservation**

```powershell
npx supabase db query --linked -o json "select column_name, data_type, is_nullable, column_default from information_schema.columns where table_schema='public' and table_name='alternative_pick_selection_state' and column_name='evaluation_proof'; select conname, pg_get_constraintdef(oid) as definition from pg_constraint where conrelid='public.alternative_pick_selection_state'::regclass order by conname; select rolname, has_table_privilege(rolname, 'public.alternative_pick_selection_state', 'select') as can_select, has_table_privilege(rolname, 'public.alternative_pick_selection_state', 'insert') as can_insert, has_table_privilege(rolname, 'public.alternative_pick_selection_state', 'update') as can_update, has_table_privilege(rolname, 'public.alternative_pick_selection_state', 'delete') as can_delete from pg_roles where rolname in ('anon','authenticated','service_role') order by rolname; select tgname from pg_trigger where tgrelid='public.alternative_pick_selection_state'::regclass and not tgisinternal order by tgname; select bundle_id, count(*) as rows, count(*) filter (where evaluation_proof <> '{}'::jsonb) as nonempty_proofs from public.alternative_pick_selection_state group by bundle_id order by bundle_id;"
```

Expected:

- `evaluation_proof` is non-null JSONB with `{}` default;
- object/32KiB/V2 consistency checks exist;
- original uniqueness and both frozen triggers remain with exact names `alternative_pick_selection_state_reject_frozen_mutation` and `alternative_pick_selection_state_validate_frozen_link`;
- the only added trigger is `alternative_pick_selection_state_default_v1_proof`, and the migration tests prove an old-shape V1 insert/upsert that omits `evaluation_proof` receives `{}` while the same omission for V2 is rejected;
- anon/authenticated cannot read or write;
- service role retains select/insert/update and no delete;
- V1 row count is unchanged and V1 proofs remain `{}`;
- zero V2 rows.

- [ ] **Step 4: Wait for one normal V1 cycle**

Verify a fresh V1 provisional/frozen write still succeeds with `{}` proof, with no duplicate key, notification, or lock regression. Stop if it fails; do not deploy code.

---

## Task 11: Production Gate B - merge and deploy V2-capable core with V1 still active

**Requires:** Tyler approval for the core merge and its exact Render/Netlify deployment effects. Do not change any environment variable and do not merge the held web branch.

**Service:** `bbe-live-layer` (`crn-d7tpb19o3t8c739p3qig`)

- [ ] **Step 1: Confirm deployment triggers and environment posture before merging**

Read the `bbe-live-layer` auto-deploy setting and the Netlify production-branch setting. Verify `ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION` is absent or `v1`. Do not print environment values. The core branch contains no Netlify endpoint or browser change, so a Netlify build from this merge must remain functionally V1.

- [ ] **Step 2: Merge only the reviewed core branch**

Use the repository's normal reviewed merge path for `codex/alt-picks-dependency-aware-v2`. Do not merge `codex/alt-picks-dependency-aware-v2-web`.

```powershell
git switch main
git pull --ff-only origin main
git log -1 --oneline
git status --short
```

Expected: clean `main` at the reviewed core merge commit. Record the commit.

- [ ] **Step 3: Verify or create the Render deploy**

If the service auto-deployed the core merge, wait for that deployment and record its ID; do not create a duplicate. If auto-deploy is off, run:

```powershell
render deploys create crn-d7tpb19o3t8c739p3qig --wait --confirm
```

Expected: deploy succeeds on the reviewed commit. Record the deploy ID.

- [ ] **Step 4: Verify the held web contract did not deploy**

If Netlify built the core merge, verify its production bundle/function hashes for Alt Picks are unchanged from the reviewed V1 deployment. Verify the browser still requests the unversioned endpoint and receives normal V1 cards. Do not deploy or merge the held endpoint/browser branch.

- [ ] **Step 5: Wait for one clean scheduled cycle and verify default-V1 isolation**

Read-only SQL must prove:

- a fresh V1 cycle completed;
- `count(*)` for bundle `pregame_alternative_pick_methodology_v2` is zero;
- no alternative-pick notification event was inserted;
- operational lock due/inserted/consumed timing and duplicate counts are unchanged;
- official artifacts, provider posture, and accepted bets are unchanged; and
- live-layer metadata reports V1 dispatch, not V2.

If any V2 row appears, set mode off and redeploy; do not continue.

---

## Task 12: Production Gate C - activate only the V2 recorder on a clean prospective slate

**Requires:** Tyler approval to change exactly one Render environment key and redeploy. Activation must occur before the first relevant T-30 lock; otherwise defer to the next Phoenix slate.

- [ ] **Step 1: Prove this is still a clean prospective activation window**

Derive eligibility and T-30 directly from the current exact official artifact. V1 sidecar rows are comparison evidence only and cannot establish that the window is clean. Run:

```powershell
python scripts/check_alternative_pick_v2_activation_window.py --artifact-url "https://baseballbettingedge.netlify.app/.netlify/functions/get-artifact?type=today"
npx supabase db query --linked -o json "with phoenix as (select (now() at time zone 'America/Phoenix')::date as slate_date) select count(*) as current_slate_lock_rows, min(should_lock_at) as first_lock_at from public.operational_pick_locks, phoenix where operational_pick_locks.slate_date=phoenix.slate_date; with phoenix as (select (now() at time zone 'America/Phoenix')::date as slate_date) select checkpoint, count(*) as v1_rows, max(observed_at) as latest_v1_observed_at from public.alternative_pick_selection_state, phoenix where alternative_pick_selection_state.slate_date=phoenix.slate_date and bundle_id='pregame_alternative_pick_methodology_v1' group by checkpoint order by checkpoint;"
```

Proceed only when the artifact preflight exits zero with `clean` or `no_candidates` and `current_slate_lock_rows=0`. If the artifact exposes any eligible candidate at/past T-30, or any relevant lock already exists, leave V1 active and schedule Gate C before the first relevant lock on the next Phoenix slate. V2 never backfills missed checkpoints. A missing V1 row never overrides the artifact-derived cutoff.

If there are zero current eligible candidates, activation may safely occur, but a subsequent zero-row cycle is classified `no_candidates`, not a recorder failure and not sufficient evidence to unlock the V2 UI.

- [ ] **Step 2: Fetch the full Render environment and review the exact one-key dry run**

Use the reviewed helper from Task 4:

```powershell
python scripts/update_render_service_env.py --service-id crn-d7tpb19o3t8c739p3qig --set ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION=v2
```

Expected: a dry run reports all paginated pages, the complete preserved key count, only the changed key name, and whether that key was originally `present` or `absent`. It prints no values and performs no mutation. Gate B already proved a present key is exactly V1; record the presence state for exact rollback.

- [ ] **Step 3: PUT the complete preserved list, verify it, and redeploy**

```powershell
python scripts/update_render_service_env.py --service-id crn-d7tpb19o3t8c739p3qig --set ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION=v2 --execute
render deploys create crn-d7tpb19o3t8c739p3qig --wait --confirm
```

Expected: the helper's fully paginated post-PUT GET proves the exact expected key set and in-memory target value; then deployment succeeds on the reviewed core commit. Record the environment operation timestamp, original presence state, deploy ID, and commit.

If PUT verification or deployment fails, restore the exact original state before redeploying and stopping:

```powershell
# Use this pair only when the dry run recorded original_state=absent.
python scripts/update_render_service_env.py --service-id crn-d7tpb19o3t8c739p3qig --unset ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION
python scripts/update_render_service_env.py --service-id crn-d7tpb19o3t8c739p3qig --unset ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION --execute

# Use this pair only when the dry run recorded original_state=present (Gate B proved V1).
python scripts/update_render_service_env.py --service-id crn-d7tpb19o3t8c739p3qig --set ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION=v1
python scripts/update_render_service_env.py --service-id crn-d7tpb19o3t8c739p3qig --set ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION=v1 --execute

render deploys create crn-d7tpb19o3t8c739p3qig --wait --confirm
```

- [ ] **Step 4: Wait for one normal scheduled cycle before trusting rows**

Do not manually synthesize a checkpoint. Wait for the normal live-layer heartbeat and exact official artifact.

- [ ] **Step 5: Verify bounded V2 state and isolation**

```powershell
npx supabase db query --linked -o json "with phoenix as (select (now() at time zone 'America/Phoenix')::date as slate_date) select checkpoint, selection_status, lane, count(*) as rows, max(octet_length(evaluation_proof::text)) as max_proof_bytes from public.alternative_pick_selection_state, phoenix where alternative_pick_selection_state.slate_date=phoenix.slate_date and bundle_id='pregame_alternative_pick_methodology_v2' group by checkpoint, selection_status, lane order by checkpoint, selection_status, lane; with phoenix as (select (now() at time zone 'America/Phoenix')::date as slate_date) select slate_date, game_identity, normalized_pitcher, side, bundle_id, checkpoint, count(*) as duplicates from public.alternative_pick_selection_state, phoenix where alternative_pick_selection_state.slate_date=phoenix.slate_date and bundle_id='pregame_alternative_pick_methodology_v2' group by slate_date, game_identity, normalized_pitcher, side, bundle_id, checkpoint having count(*) > 1;"
```

Also verify:

- all V2 rows have exact bundle/fingerprint/proof consistency;
- no V2 row is retroactive to a missed lock or started game;
- selected-with-pending rows satisfy their persisted lane proof;
- V1 frozen rows, including Jake Bennett control evidence, are unchanged;
- zero alternative notification events;
- no lock timing/duplicate change;
- official artifact/pick counts, accepted bets, provider source, and model output unchanged; and
- row volume is bounded to at most one provisional and one frozen row per eligible pick for V2.

Classify the cycle before deciding:

- `complete_candidate_cycle`: every eligible candidate observed after activation has the expected provisional row and every due lock has its immutable frozen row;
- `no_candidates`: the exact artifact had no eligible tracked non-PASS candidates; this is not failure, but continue soaking and do not deploy the V2 UI yet;
- `prospective_partial`: candidates appeared only after an earlier missed checkpoint or activation could not cover the full slate; this is a legitimate no-backfill limitation, so defer UI release to the next clean slate rather than calling infrastructure broken; or
- `infrastructure_failure`: eligible prospective candidates were in scope but writes/proofs/locks were missing, malformed, duplicated, or errored.

Only `complete_candidate_cycle` may advance to Gate D. For `infrastructure_failure`, mark V2 unavailable and fix infrastructure first. For the other two non-complete states, keep the official app untouched and collect the next clean prospective slate.

---

## Task 13: Production Gate D - merge and deploy the held V2 endpoint/UI

**Requires:** Tyler approval after Task 12 production rows pass.

**Netlify site:** `47c15fdf-6278-4109-8877-545cc29eb418`

- [ ] **Step 1: Create a fresh path-scoped release branch from updated production core**

```powershell
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c codex/alt-picks-dependency-aware-v2-web-release
git restore --source origin/codex/alt-picks-dependency-aware-v2-web -- netlify/functions/alternative-picks.mjs tests/test_alternative_picks_function.mjs dashboard/v2-alt-picks.js dashboard/v2-alt-picks.test.mjs dashboard/v2-app.jsx dashboard/v2-app.js dashboard/v2-app.test.mjs dashboard/v2.html tests/test_dashboard_alt_picks_ui.py
git diff --name-status
git diff --exit-code origin/codex/alt-picks-dependency-aware-v2-web -- netlify/functions/alternative-picks.mjs tests/test_alternative_picks_function.mjs dashboard/v2-alt-picks.js dashboard/v2-alt-picks.test.mjs dashboard/v2-app.jsx dashboard/v2-app.js dashboard/v2-app.test.mjs dashboard/v2.html tests/test_dashboard_alt_picks_ui.py
node --test tests/test_alternative_picks_function.mjs dashboard/v2-alt-picks.test.mjs dashboard/v2-app.test.mjs
python -m pytest tests/test_dashboard_alt_picks_ui.py tests/test_dashboard_accepted_bet_log.py -q
node --check dashboard/v2-alt-picks.js
node --check dashboard/v2-app.js
git diff --check
git add netlify/functions/alternative-picks.mjs tests/test_alternative_picks_function.mjs dashboard/v2-alt-picks.js dashboard/v2-alt-picks.test.mjs dashboard/v2-app.jsx dashboard/v2-app.js dashboard/v2-app.test.mjs dashboard/v2.html tests/test_dashboard_alt_picks_ui.py
git commit -m "feat: release dependency-aware alternative picks v2 web"
git diff --name-only origin/main...HEAD
git push -u origin codex/alt-picks-dependency-aware-v2-web-release
```

Expected: the release branch starts from current `origin/main`, copies only the exact reviewed endpoint/UI paths from the held branch, and all V2 handshake/UI tests pass against production core. The final diff allow-list is exactly the nine paths above. Do not rebase, merge, or squash the held branch directly; its ancestry contains the pre-merge core work.

- [ ] **Step 2: Merge only the fresh web-release branch and verify the Netlify deploy**

Use the repository's normal reviewed merge path for `codex/alt-picks-dependency-aware-v2-web-release` at its recorded remote SHA. The merge itself may trigger Netlify production deployment. Wait for that deploy and record its ID/commit. If the connected-site deploy does not occur, use the separately approved fallback:

```powershell
git switch main
git pull --ff-only origin main
netlify deploy --prod --dir dashboard --functions netlify/functions --site 47c15fdf-6278-4109-8877-545cc29eb418
```

Do not issue the manual deploy when a healthy automatic deploy for the same commit is already running or complete.

- [ ] **Step 3: Verify the endpoint compatibility matrix**

Check:

- unversioned endpoint returns top-level V1 bundle/fingerprint;
- `?bundle_version=v1` returns V1;
- `?bundle_version=v2` returns exact V2 bundle/fingerprint;
- invalid version returns unavailable;
- no raw proof identifiers are exposed;
- stale/malformed/mixed rows are suppressed; and
- current artifact and exact lock validation still control visibility.

- [ ] **Step 4: Verify desktop and mobile Alt Picks UI**

Inspect `https://baseballbettingedge.netlify.app/?tab=alt` at `1280x900` and `390x844`.

Expected:

- selected cards appear before game time when V2 proof is valid;
- selected-with-pending copy is accurate;
- confirmed family count and pending chips agree with endpoint proof;
- no wager/Log Bet/stake/PnL/notification controls appear;
- comparison-only disclaimer is visible;
- Picks and Results counts/content remain unchanged; and
- accepted-bet behavior remains confined to official Picks.

- [ ] **Step 5: Update the production handoff**

Record exact Render and Netlify deploy IDs, first clean V2 cycle, row counts by lane/status/checkpoint, maximum proof size, zero duplicate/notification/lock regressions, and the next soak decision. Keep all official promotion gates closed.

---

## Task 14: Exercise and document rollback readiness

**Files:**

- Modify after evidence: `docs/current-state.md`
- Modify after evidence: `docs/superpowers/specs/2026-07-22-alt-picks-dependency-aware-v2-design.md`
- Modify after evidence: `docs/superpowers/plans/2026-07-22-alt-picks-dependency-aware-v2.md`

- [ ] **Step 1: Document immediate stop and dependency-ordered rollback**

Immediate recorder stop:

```powershell
python scripts/update_render_service_env.py --service-id crn-d7tpb19o3t8c739p3qig --set ALTERNATIVE_PICK_SELECTION_MODE=off
python scripts/update_render_service_env.py --service-id crn-d7tpb19o3t8c739p3qig --set ALTERNATIVE_PICK_SELECTION_MODE=off --execute
render deploys create crn-d7tpb19o3t8c739p3qig --wait --confirm
```

Review the dry-run key-only diff first, then execute and redeploy only `bbe-live-layer`.

Version rollback:

1. read the Gate C record of the original version-key presence;
2. if originally absent, dry-run then execute `--unset ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION`; if originally present, dry-run then execute `--set ALTERNATIVE_PICK_SELECTION_BUNDLE_VERSION=v1`;
3. redeploy live layer;
4. obtain one clean V1 cycle with zero new V2 rows; and
5. verify complete current-slate V1 coverage before restoring a V1 UI.

If V1 coverage is incomplete because V2 was active at a freeze, keep the Alt comparison unavailable until the next clean slate. Never reconstruct missed V1 or V2 rows.

Endpoint/UI rollback targets:

- immediate reviewed V1 endpoint deploy: `6a602de17d040836c1641df0`;
- pre-Alt UI deploy: `6a5e5bbef33863243b980d83`;
- reviewed V1 Alt UI deploy before V2: `6a60e7c06cebf50c3948c690`.

- [ ] **Step 2: Keep the promotion decision separate**

The first V2 slate proves plumbing and prospective capture only. The next decision is soak/observe. Do not use one slate to change official pick selection, model math, thresholds, staking, provider order, notifications, locks, accepted bets, artifact source, dashboard source of truth, or retention.

- [ ] **Step 3: Commit and push the final evidence handoff**

```powershell
git add docs/current-state.md docs/superpowers/specs/2026-07-22-alt-picks-dependency-aware-v2-design.md docs/superpowers/plans/2026-07-22-alt-picks-dependency-aware-v2.md
git commit -m "docs: record alternative picks v2 rollout evidence"
git push origin main
git status --short
```

Expected: `main` and `origin/main` match, the worktree is clean, and the documentation distinguishes confirmed production facts from future recommendations.
