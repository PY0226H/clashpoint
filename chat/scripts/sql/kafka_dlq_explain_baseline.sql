\pset pager off
\timing on

\echo '=== kafka_dlq query plan baseline ==='

WITH params AS (
    SELECT
        NULLIF(:'status', '')::varchar AS status_filter,
        NULLIF(:'event_type', '')::varchar AS event_type_filter,
        NULLIF(:'cursor_updated_at', '')::timestamptz AS cursor_updated_at_filter,
        NULLIF(:'cursor_id', '')::bigint AS cursor_id_filter,
        LEAST(100, GREATEST(1, COALESCE(NULLIF(:'limit', '')::bigint, 50))) AS row_limit,
        GREATEST(0, COALESCE(NULLIF(:'offset', '')::bigint, 0)) AS row_offset,
        COALESCE(NULLIF(:'cutoff_ts', '')::timestamptz, NOW() - INTERVAL '14 days') AS retention_cutoff,
        LEAST(10000, GREATEST(1, COALESCE(NULLIF(:'retention_batch_size', '')::bigint, 500))) AS retention_batch_size
)
SELECT
    status_filter AS status,
    event_type_filter AS event_type,
    cursor_updated_at_filter AS cursor_updated_at,
    cursor_id_filter AS cursor_id,
    row_limit,
    row_offset,
    retention_cutoff,
    retention_batch_size
FROM params;

\echo ''
\echo '--- LIST COUNT query plan (includeTotal=true path) ---'
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
WITH params AS (
    SELECT
        NULLIF(:'status', '')::varchar AS status_filter,
        NULLIF(:'event_type', '')::varchar AS event_type_filter
)
SELECT COUNT(1)::bigint
FROM kafka_dlq_events e, params p
WHERE (p.status_filter IS NULL OR e.status = p.status_filter)
  AND (p.event_type_filter IS NULL OR e.event_type = p.event_type_filter);

\echo ''
\echo '--- LIST OFFSET query plan ---'
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
WITH params AS (
    SELECT
        NULLIF(:'status', '')::varchar AS status_filter,
        NULLIF(:'event_type', '')::varchar AS event_type_filter,
        LEAST(100, GREATEST(1, COALESCE(NULLIF(:'limit', '')::bigint, 50))) AS row_limit,
        GREATEST(0, COALESCE(NULLIF(:'offset', '')::bigint, 0)) AS row_offset
)
SELECT
    e.id,
    e.status,
    e.event_type,
    e.updated_at
FROM kafka_dlq_events e, params p
WHERE (p.status_filter IS NULL OR e.status = p.status_filter)
  AND (p.event_type_filter IS NULL OR e.event_type = p.event_type_filter)
ORDER BY e.updated_at DESC, e.id DESC
LIMIT (SELECT row_limit FROM params)
OFFSET (SELECT row_offset FROM params);

\echo ''
\echo '--- LIST CURSOR query plan (keyset path) ---'
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
WITH params AS (
    SELECT
        NULLIF(:'status', '')::varchar AS status_filter,
        NULLIF(:'event_type', '')::varchar AS event_type_filter,
        NULLIF(:'cursor_updated_at', '')::timestamptz AS cursor_updated_at_filter,
        NULLIF(:'cursor_id', '')::bigint AS cursor_id_filter,
        LEAST(100, GREATEST(1, COALESCE(NULLIF(:'limit', '')::bigint, 50))) AS row_limit
)
SELECT
    e.id,
    e.status,
    e.event_type,
    e.updated_at
FROM kafka_dlq_events e, params p
WHERE (p.status_filter IS NULL OR e.status = p.status_filter)
  AND (p.event_type_filter IS NULL OR e.event_type = p.event_type_filter)
  AND (
        p.cursor_updated_at_filter IS NULL
        OR p.cursor_id_filter IS NULL
        OR (e.updated_at, e.id) < (p.cursor_updated_at_filter, p.cursor_id_filter)
      )
ORDER BY e.updated_at DESC, e.id DESC
LIMIT (SELECT row_limit FROM params);

\echo ''
\echo '--- RETENTION candidate scan plan ---'
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
WITH params AS (
    SELECT
        COALESCE(NULLIF(:'cutoff_ts', '')::timestamptz, NOW() - INTERVAL '14 days') AS retention_cutoff,
        LEAST(10000, GREATEST(1, COALESCE(NULLIF(:'retention_batch_size', '')::bigint, 500))) AS retention_batch_size
)
SELECT e.id
FROM kafka_dlq_events e, params p
WHERE e.status IN ('replayed', 'discarded')
  AND e.updated_at < p.retention_cutoff
ORDER BY e.updated_at ASC, e.id ASC
LIMIT (SELECT retention_batch_size FROM params)
FOR UPDATE SKIP LOCKED;

\echo ''
\echo '--- RETENTION cleanup plan (transaction rolled back) ---'
SELECT (to_regclass('public.kafka_dlq_event_actions') IS NOT NULL)::int AS has_actions_table
\gset

\if :has_actions_table
BEGIN;
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
WITH params AS (
    SELECT
        COALESCE(NULLIF(:'cutoff_ts', '')::timestamptz, NOW() - INTERVAL '14 days') AS retention_cutoff,
        LEAST(10000, GREATEST(1, COALESCE(NULLIF(:'retention_batch_size', '')::bigint, 500))) AS retention_batch_size
),
candidate AS (
    SELECT e.id
    FROM kafka_dlq_events e, params p
    WHERE e.status IN ('replayed', 'discarded')
      AND e.updated_at < p.retention_cutoff
    ORDER BY e.updated_at ASC, e.id ASC
    LIMIT (SELECT retention_batch_size FROM params)
    FOR UPDATE SKIP LOCKED
),
deleted_actions AS (
    DELETE FROM kafka_dlq_event_actions actions
    USING candidate c
    WHERE actions.dlq_event_id = c.id
    RETURNING actions.id
),
deleted_events AS (
    DELETE FROM kafka_dlq_events events
    USING candidate c
    WHERE events.id = c.id
    RETURNING events.id
)
SELECT
    COALESCE((SELECT COUNT(1)::bigint FROM deleted_events), 0) AS deleted_event_rows,
    COALESCE((SELECT COUNT(1)::bigint FROM deleted_actions), 0) AS deleted_action_rows;
ROLLBACK;
\else
\echo 'skip retention cleanup plan: kafka_dlq_event_actions table not found in current database'
\endif

\echo ''
\echo '=== baseline finished ==='
