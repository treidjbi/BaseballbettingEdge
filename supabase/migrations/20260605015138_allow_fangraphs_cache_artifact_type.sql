alter table public.published_pipeline_artifacts
  drop constraint if exists published_pipeline_artifacts_artifact_type_check;

alter table public.published_pipeline_artifacts
  add constraint published_pipeline_artifacts_artifact_type_check
  check (
    artifact_type in (
      'today',
      'dated_slate',
      'index',
      'steam',
      'performance',
      'params',
      'preview_lines',
      'picks_history',
      'fangraphs_cache'
    )
  );
