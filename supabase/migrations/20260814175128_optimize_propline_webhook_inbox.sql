-- Apply only through a separately approved online migration step.
-- CONCURRENTLY avoids blocking the live webhook receiver while PostgreSQL builds the index.
create index concurrently if not exists idx_propline_webhook_deliveries_unprocessed_received_at
on public.propline_webhook_deliveries (received_at asc)
where processed is false;
