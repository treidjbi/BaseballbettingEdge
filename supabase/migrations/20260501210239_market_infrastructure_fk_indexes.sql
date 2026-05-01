create index if not exists idx_market_snapshots_run_id
  on public.market_snapshots (run_id);

create index if not exists idx_provider_coverage_audits_run_id
  on public.provider_coverage_audits (run_id);
