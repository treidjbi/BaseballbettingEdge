-- Runtime hardening for BoltOdds/PropLine provider-readiness reads.
--
-- These indexes target the weekend failure mode where live/provider builders
-- repeatedly read recent market rows and heartbeats while raw snapshot volume
-- was growing. They do not change provider order, model math, retention, or
-- production artifacts.

create index if not exists idx_market_snapshots_provider_observed
  on public.market_snapshots (provider, observed_at desc);

create index if not exists idx_market_snapshots_run_observed
  on public.market_snapshots (run_id, observed_at desc);

create index if not exists idx_market_feed_heartbeats_slate_provider_observed
  on public.market_feed_heartbeats (slate_date, provider, observed_at desc);

create index if not exists idx_market_provider_runs_slate_provider_created
  on public.market_provider_runs (slate_date, provider, created_at desc);
