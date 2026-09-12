-- Tyler approved the webhook-inbox-only cleanup on September 12, 2026.
-- Archive SHA256: f2b58a1f331e2ccd2f98cf520ba7a71bc5b73e424e2a49ec15a3758ba05e7f0e
-- Restored locally: 727311 rows, fingerprint sum 419543915638217971468961.
-- One execution only. Never retry an uncertain result; inspect table state first.
BEGIN;
SET LOCAL lock_timeout = '2s';
SET LOCAL statement_timeout = '30s';
SET LOCAL timezone = 'UTC';
DO $$
DECLARE
  actual_count bigint;
  actual_fingerprint text;
BEGIN
  LOCK TABLE ONLY public.propline_webhook_deliveries IN ACCESS EXCLUSIVE MODE;
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE contype='f'
             AND confrelid='public.propline_webhook_deliveries'::regclass)
     OR EXISTS (SELECT 1 FROM pg_trigger
                WHERE tgrelid='public.propline_webhook_deliveries'::regclass AND NOT tgisinternal)
     OR EXISTS (SELECT 1 FROM pg_depend d JOIN pg_rewrite r ON r.oid=d.objid
                WHERE d.refobjid='public.propline_webhook_deliveries'::regclass)
  THEN RAISE EXCEPTION 'Dependency gate changed; cleanup aborted'; END IF;
  SELECT count(*),sum(('x'||substr(md5(row_to_json(w)::text),1,15))::bit(60)::bigint::numeric)::text
    INTO actual_count,actual_fingerprint
    FROM public.propline_webhook_deliveries w;
  IF actual_count <> 727311 OR actual_fingerprint IS DISTINCT FROM '419543915638217971468961'
  THEN RAISE EXCEPTION 'Archive scope changed; cleanup aborted'; END IF;
  TRUNCATE TABLE ONLY public.propline_webhook_deliveries CONTINUE IDENTITY RESTRICT;
END $$;
COMMIT;
SELECT now() AS checked_at,count(*) AS remaining_rows,
       pg_total_relation_size('public.propline_webhook_deliveries') AS inbox_bytes,
       pg_database_size(current_database()) AS database_bytes
FROM public.propline_webhook_deliveries;
