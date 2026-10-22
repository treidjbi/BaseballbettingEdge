alter table public.alternative_pick_selection_state
  add column if not exists evaluation_proof jsonb not null default '{}'::jsonb;

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

alter table public.alternative_pick_selection_state
  add constraint alternative_pick_selection_state_evaluation_proof_object_check
    check (jsonb_typeof(evaluation_proof) = 'object'),
  add constraint alternative_pick_selection_state_evaluation_proof_size_check
    check (octet_length(evaluation_proof::text) <= 32768),
  add constraint alternative_pick_selection_state_v2_evaluation_proof_check
    check (
      (
        bundle_id <> 'pregame_alternative_pick_methodology_v2'
        or (
          evaluation_proof ?& array[
            'schema_version', 'bundle_id', 'selector_fingerprint', 'candidate',
            'artifact', 'preclose', 'decision'
          ]
          and (evaluation_proof #> '{candidate}') ?& array[
            'candidate_identity', 'slate_date', 'normalized_pitcher', 'side',
            'model_k_line', 'game_time', 'line_source_provider', 'official_binding_key'
          ]
          and (evaluation_proof #> '{artifact}') ?& array[
            'source_artifact_path', 'source_artifact_generated_at',
            'source_artifact_sha256', 'source_artifact_byte_sha256'
          ]
          and (evaluation_proof #> '{normalized_inputs}') ?& array[
            'pitcher', 'side', 'game_time', 'k_line', 'odds',
            'official_book', 'official_verdict'
          ]
          and (evaluation_proof #> '{preclose}') ?& array[
            'decisive_observation_tokens', 'qualifying_observation_count',
            'first_observed_at', 'last_observed_at', 'freshness_status'
          ]
          and (evaluation_proof #> '{decision}') ?& array[
            'family_states', 'family_count', 'selection_status', 'selected_lane'
          ]
          and evaluation_proof ->> 'schema_version' = 'v2'
          and evaluation_proof ->> 'bundle_id' = bundle_id
          and evaluation_proof ->> 'selector_fingerprint' = selector_fingerprint
          and evaluation_proof #>> '{candidate,candidate_identity}' = candidate_identity
          and evaluation_proof #>> '{candidate,slate_date}' = slate_date::text
          and evaluation_proof #>> '{candidate,normalized_pitcher}' = normalized_pitcher
          and evaluation_proof #>> '{candidate,side}' = side
          and (evaluation_proof #>> '{candidate,model_k_line}')::numeric = model_k_line
          and (evaluation_proof #>> '{candidate,game_time}')::timestamptz = game_time
          and evaluation_proof #>> '{normalized_inputs,pitcher}' = normalized_pitcher
          and evaluation_proof #>> '{normalized_inputs,side}' = side
          and (evaluation_proof #>> '{normalized_inputs,game_time}')::timestamptz = game_time
          and (evaluation_proof #>> '{normalized_inputs,k_line}')::numeric = model_k_line
          and (evaluation_proof #>> '{normalized_inputs,odds}')::integer is not distinct from official_odds
          and lower(nullif(trim(evaluation_proof #>> '{normalized_inputs,official_book}'), ''))
            is not distinct from lower(nullif(trim(official_book), ''))
          and nullif(trim(evaluation_proof #>> '{normalized_inputs,official_verdict}'), '')
            is not distinct from nullif(trim(official_verdict), '')
          and evaluation_proof #>> '{artifact,source_artifact_path}' = source_artifact_path
          and (evaluation_proof #>> '{artifact,source_artifact_generated_at}')::timestamptz
            is not distinct from source_artifact_generated_at
          and evaluation_proof #>> '{artifact,source_artifact_sha256}' = source_artifact_sha256
          and evaluation_proof #>> '{artifact,source_artifact_byte_sha256}' = source_artifact_byte_sha256
          and evaluation_proof #> '{decision,family_states}' = family_states
          and (evaluation_proof #>> '{decision,family_count}')::integer = family_count
          and jsonb_array_length(jsonb_path_query_array(
            evaluation_proof #> '{decision,family_states}',
            '$.* ? (@.state == "agree")'
          )) = family_count
          and evaluation_proof #> '{preclose,decisive_observation_tokens}' = evidence_observation_ids
          and (evaluation_proof #>> '{preclose,qualifying_observation_count}')::integer = evidence_observation_count
          and (evaluation_proof #>> '{preclose,first_observed_at}')::timestamptz is not distinct from evidence_first_observed_at
          and (evaluation_proof #>> '{preclose,last_observed_at}')::timestamptz is not distinct from evidence_last_observed_at
          and evaluation_proof #>> '{preclose,freshness_status}' = evidence_freshness_status
          and evaluation_proof #>> '{decision,selection_status}' = selection_status
          and evaluation_proof #>> '{decision,selected_lane}' is not distinct from lane
          and (
            (
              evaluation_proof #>> '{decision,selected_lane}' = 'consensus_core'
              and selector_id = 'no_drag_distinct_family_consensus_core_v2'
            )
            or (
              evaluation_proof #>> '{decision,selected_lane}' = 'reentry_expansion'
              and selector_id = 'moderate_edge_quality_reentry_expansion_v2'
            )
            or (
              evaluation_proof #>> '{decision,selected_lane}' is null and selector_id is null
            )
          )
        )
      ) is true
    );
