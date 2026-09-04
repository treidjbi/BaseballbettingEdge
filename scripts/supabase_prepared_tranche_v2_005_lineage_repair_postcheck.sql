-- Independent SELECT-only postcheck for the approved v2-005 lineage repair.

with approved_late_rows as (
  select
    ms.id,
    ms.observed_at,
    mpr.slate_date,
    lower(trim(mpr.provider)) as provider,
    lower(trim(ms.bookmaker_key)) as book_key,
    trim(ms.normalized_player_name) as normalized_player_name,
    coalesce(nullif(trim(ms.market_key), ''), 'pitcher_strikeouts') as market_key,
    lower(trim(ms.side)) as side,
    ms.line::numeric as line
  from public.market_snapshots ms
  join public.market_provider_runs mpr on mpr.id = ms.run_id
  where mpr.provider = 'therundown'
    and mpr.slate_date = date '2026-07-15'
    and ms.provider = 'therundown'
    and ms.observed_at = timestamptz '2026-07-16T13:10:41.076339Z'
), affected_keys as (
  select distinct
    slate_date,
    provider,
    book_key,
    normalized_player_name,
    market_key,
    side,
    line
  from approved_late_rows
), raw_rows as (
  select
    affected_keys.slate_date,
    affected_keys.provider,
    affected_keys.book_key,
    affected_keys.normalized_player_name,
    coalesce(
      nullif(trim(ms.player_name), ''),
      nullif(trim(ms.normalized_player_name), ''),
      'unknown'
    ) as player_name,
    affected_keys.market_key,
    affected_keys.side,
    affected_keys.line,
    ms.observed_at,
    ms.american_odds::integer as american_odds,
    ms.id
  from affected_keys
  join public.market_provider_runs mpr
    on mpr.slate_date = affected_keys.slate_date
   and lower(trim(mpr.provider)) = affected_keys.provider
  join public.market_snapshots ms
    on ms.run_id = mpr.id
   and lower(trim(ms.provider)) = affected_keys.provider
   and lower(trim(ms.bookmaker_key)) = affected_keys.book_key
   and trim(ms.normalized_player_name) = affected_keys.normalized_player_name
   and coalesce(nullif(trim(ms.market_key), ''), 'pitcher_strikeouts')
       = affected_keys.market_key
   and lower(trim(ms.side)) = affected_keys.side
   and ms.line::numeric = affected_keys.line
), windowed_rows as (
  select
    raw_rows.*,
    first_value(american_odds) over (
      partition by slate_date, provider, book_key, normalized_player_name,
                   market_key, side, line
      order by observed_at asc, id asc
      rows between unbounded preceding and unbounded following
    ) as first_odds,
    first_value(american_odds) over (
      partition by slate_date, provider, book_key, normalized_player_name,
                   market_key, side, line
      order by observed_at desc, id desc
      rows between unbounded preceding and unbounded following
    ) as last_odds,
    lag(american_odds) over (
      partition by slate_date, provider, book_key, normalized_player_name,
                   market_key, side, line
      order by observed_at asc, id asc
    ) as previous_odds
  from raw_rows
), rebuilt as (
  select
    slate_date,
    provider,
    book_key,
    normalized_player_name,
    min(player_name) as player_name,
    market_key,
    side,
    line,
    min(observed_at) as first_seen_at,
    max(observed_at) as last_seen_at,
    min(first_odds) as first_odds,
    min(last_odds) as last_odds,
    min(american_odds) as min_odds,
    max(american_odds) as max_odds,
    count(*) filter (
      where previous_odds is not null
        and american_odds is not null
        and previous_odds <> american_odds
    )::integer as odds_move_count,
    count(*)::integer as snapshot_count,
    jsonb_agg(id order by observed_at asc, id asc) as source_snapshot_ids
  from windowed_rows
  group by
    slate_date,
    provider,
    book_key,
    normalized_player_name,
    market_key,
    side,
    line
), comparison as (
  select
    rebuilt.*,
    cmlm.id as existing_id,
    cmlm.player_name as current_player_name,
    cmlm.first_seen_at as current_first_seen_at,
    cmlm.last_seen_at as current_last_seen_at,
    cmlm.first_odds as current_first_odds,
    cmlm.last_odds as current_last_odds,
    cmlm.min_odds as current_min_odds,
    cmlm.max_odds as current_max_odds,
    cmlm.odds_move_count as current_odds_move_count,
    cmlm.snapshot_count as current_snapshot_count,
    cmlm.source_snapshot_ids as current_source_snapshot_ids
  from rebuilt
  left join public.compact_market_line_movements cmlm
    on cmlm.slate_date = rebuilt.slate_date
   and cmlm.provider = rebuilt.provider
   and cmlm.book_key = rebuilt.book_key
   and cmlm.normalized_player_name = rebuilt.normalized_player_name
   and cmlm.market_key = rebuilt.market_key
   and cmlm.side = rebuilt.side
   and cmlm.line::numeric = rebuilt.line
), post_state as (
  select
    (select count(*)::bigint from approved_late_rows) as late_source_rows,
    (select count(*)::bigint from approved_late_rows late
      where exists (
        select 1
        from public.compact_market_line_movements cmlm
        where cmlm.slate_date = late.slate_date
          and cmlm.provider = late.provider
          and cmlm.book_key = late.book_key
          and cmlm.normalized_player_name = late.normalized_player_name
          and cmlm.market_key = late.market_key
          and cmlm.side = late.side
          and cmlm.line::numeric = late.line
          and jsonb_typeof(cmlm.source_snapshot_ids) = 'array'
          and cmlm.source_snapshot_ids ? late.id::text
          and late.observed_at between cmlm.first_seen_at and cmlm.last_seen_at
      )) as preserved_late_source_rows,
    (select count(*)::bigint from affected_keys) as affected_group_count,
    (select count(*)::bigint from raw_rows) as source_rows_in_affected_groups,
    count(*)::bigint as rebuilt_group_count,
    count(*) filter (where existing_id is not null)::bigint as existing_group_count,
    coalesce(sum(snapshot_count), 0)::bigint as rebuilt_represented_rows,
    coalesce(sum(current_snapshot_count), 0)::bigint as current_represented_rows,
    count(*) filter (
      where existing_id is null
         or current_player_name is distinct from player_name
         or current_first_seen_at is distinct from first_seen_at
         or current_last_seen_at is distinct from last_seen_at
         or current_first_odds is distinct from first_odds
         or current_last_odds is distinct from last_odds
         or current_min_odds is distinct from min_odds
         or current_max_odds is distinct from max_odds
         or current_odds_move_count is distinct from odds_move_count
         or current_snapshot_count is distinct from snapshot_count
         or current_source_snapshot_ids is distinct from source_snapshot_ids
    )::bigint as mismatched_groups,
    encode(extensions.digest(coalesce((
      select string_agg(
        jsonb_build_array(
          slate_date, provider, book_key, normalized_player_name, player_name,
          market_key, side, line, first_seen_at, last_seen_at, first_odds,
          last_odds, min_odds, max_odds, odds_move_count, snapshot_count,
          source_snapshot_ids
        )::text,
        E'\n' order by slate_date, provider, book_key, normalized_player_name,
          market_key, side, line
      )
      from rebuilt
    ), ''), 'sha256'), 'hex') as rebuilt_rows_sha256,
    encode(extensions.digest(coalesce((
      select string_agg(
        jsonb_build_array(
          slate_date, provider, book_key, normalized_player_name,
          current_player_name, market_key, side, line, current_first_seen_at,
          current_last_seen_at, current_first_odds, current_last_odds,
          current_min_odds, current_max_odds, current_odds_move_count,
          current_snapshot_count, current_source_snapshot_ids
        )::text,
        E'\n' order by slate_date, provider, book_key, normalized_player_name,
          market_key, side, line
      )
      from comparison
    ), ''), 'sha256'), 'hex') as current_rows_sha256
  from comparison
)
select jsonb_build_object(
  'provider', 'therundown',
  'source_slate_date', '2026-07-15',
  'late_source_rows', late_source_rows,
  'preserved_late_source_rows', preserved_late_source_rows,
  'affected_group_count', affected_group_count,
  'source_rows_in_affected_groups', source_rows_in_affected_groups,
  'rebuilt_group_count', rebuilt_group_count,
  'existing_group_count', existing_group_count,
  'rebuilt_represented_rows', rebuilt_represented_rows,
  'current_represented_rows', current_represented_rows,
  'mismatched_groups', mismatched_groups,
  'rebuilt_rows_sha256', rebuilt_rows_sha256,
  'current_rows_sha256', current_rows_sha256,
  'all_confirmed',
    late_source_rows = 17
    and preserved_late_source_rows = 17
    and affected_group_count = 17
    and source_rows_in_affected_groups = 1323
    and rebuilt_group_count = 17
    and existing_group_count = 17
    and rebuilt_represented_rows = 1323
    and current_represented_rows = 1323
    and mismatched_groups = 0
    and rebuilt_rows_sha256
        = 'debd07cfce0c8ab203dbc590f75c0582ba18675750c76861cca16b124c3863be'
    and current_rows_sha256 = rebuilt_rows_sha256
) as prepared_lineage_repair_postcheck
from post_state;
