\pset pager off
\timing on

\echo '=== ai_judge_replay_actions query plan baseline ==='

WITH params AS (
    SELECT
        NULLIF(:'from_ts', '')::timestamptz AS from_ts,
        NULLIF(:'to_ts', '')::timestamptz AS to_ts,
        NULLIF(:'scope', '')::varchar AS scope_filter,
        NULLIF(:'session_id', '')::bigint AS session_id_filter,
        NULLIF(:'job_id', '')::bigint AS job_id_filter,
        NULLIF(:'requested_by', '')::bigint AS requested_by_filter,
        NULLIF(:'previous_status', '')::varchar AS previous_status_filter,
        NULLIF(:'new_status', '')::varchar AS new_status_filter,
        NULLIF(:'reason_keyword', '')::varchar AS reason_keyword_filter,
        NULLIF(:'trace_keyword', '')::varchar AS trace_keyword_filter,
        LEAST(500, GREATEST(1, COALESCE(NULLIF(:'limit', '')::bigint, 50))) AS row_limit,
        GREATEST(0, COALESCE(NULLIF(:'offset', '')::bigint, 0)) AS row_offset
)
SELECT
    from_ts,
    to_ts,
    scope_filter AS scope,
    session_id_filter AS session_id,
    job_id_filter AS job_id,
    requested_by_filter AS requested_by,
    previous_status_filter AS previous_status,
    new_status_filter AS new_status,
    reason_keyword_filter AS reason_keyword,
    trace_keyword_filter AS trace_keyword,
    row_limit,
    row_offset
FROM params;

\echo ''
\echo '--- COUNT query plan ---'
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
WITH params AS (
    SELECT
        NULLIF(:'from_ts', '')::timestamptz AS from_ts,
        NULLIF(:'to_ts', '')::timestamptz AS to_ts,
        NULLIF(:'scope', '')::varchar AS scope_filter,
        NULLIF(:'session_id', '')::bigint AS session_id_filter,
        NULLIF(:'job_id', '')::bigint AS job_id_filter,
        NULLIF(:'requested_by', '')::bigint AS requested_by_filter,
        NULLIF(:'previous_status', '')::varchar AS previous_status_filter,
        NULLIF(:'new_status', '')::varchar AS new_status_filter,
        NULLIF(:'reason_keyword', '')::varchar AS reason_keyword_filter,
        NULLIF(:'trace_keyword', '')::varchar AS trace_keyword_filter
)
SELECT COUNT(*)::bigint
FROM judge_replay_actions a, params p
WHERE (p.from_ts IS NULL OR a.created_at >= p.from_ts)
  AND (p.to_ts IS NULL OR a.created_at <= p.to_ts)
  AND (p.scope_filter IS NULL OR a.scope = p.scope_filter)
  AND (p.session_id_filter IS NULL OR a.session_id = p.session_id_filter)
  AND (p.job_id_filter IS NULL OR a.job_id = p.job_id_filter)
  AND (p.requested_by_filter IS NULL OR a.requested_by = p.requested_by_filter)
  AND (p.previous_status_filter IS NULL OR a.previous_status = p.previous_status_filter)
  AND (p.new_status_filter IS NULL OR a.new_status = p.new_status_filter)
  AND (
        p.reason_keyword_filter IS NULL
        OR a.reason ILIKE ('%' || p.reason_keyword_filter || '%')
      )
  AND (
        p.trace_keyword_filter IS NULL
        OR a.previous_trace_id ILIKE ('%' || p.trace_keyword_filter || '%')
        OR a.new_trace_id ILIKE ('%' || p.trace_keyword_filter || '%')
      );

\echo ''
\echo '--- LIST query plan ---'
EXPLAIN (ANALYZE, BUFFERS, VERBOSE)
WITH params AS (
    SELECT
        NULLIF(:'from_ts', '')::timestamptz AS from_ts,
        NULLIF(:'to_ts', '')::timestamptz AS to_ts,
        NULLIF(:'scope', '')::varchar AS scope_filter,
        NULLIF(:'session_id', '')::bigint AS session_id_filter,
        NULLIF(:'job_id', '')::bigint AS job_id_filter,
        NULLIF(:'requested_by', '')::bigint AS requested_by_filter,
        NULLIF(:'previous_status', '')::varchar AS previous_status_filter,
        NULLIF(:'new_status', '')::varchar AS new_status_filter,
        NULLIF(:'reason_keyword', '')::varchar AS reason_keyword_filter,
        NULLIF(:'trace_keyword', '')::varchar AS trace_keyword_filter,
        LEAST(500, GREATEST(1, COALESCE(NULLIF(:'limit', '')::bigint, 50))) AS row_limit,
        GREATEST(0, COALESCE(NULLIF(:'offset', '')::bigint, 0)) AS row_offset
)
SELECT
    a.id AS audit_id,
    a.scope,
    a.job_id,
    a.session_id,
    a.requested_by,
    a.reason,
    a.previous_status,
    a.new_status,
    a.previous_trace_id,
    a.new_trace_id,
    a.previous_idempotency_key,
    a.new_idempotency_key,
    a.created_at
FROM judge_replay_actions a, params p
WHERE (p.from_ts IS NULL OR a.created_at >= p.from_ts)
  AND (p.to_ts IS NULL OR a.created_at <= p.to_ts)
  AND (p.scope_filter IS NULL OR a.scope = p.scope_filter)
  AND (p.session_id_filter IS NULL OR a.session_id = p.session_id_filter)
  AND (p.job_id_filter IS NULL OR a.job_id = p.job_id_filter)
  AND (p.requested_by_filter IS NULL OR a.requested_by = p.requested_by_filter)
  AND (p.previous_status_filter IS NULL OR a.previous_status = p.previous_status_filter)
  AND (p.new_status_filter IS NULL OR a.new_status = p.new_status_filter)
  AND (
        p.reason_keyword_filter IS NULL
        OR a.reason ILIKE ('%' || p.reason_keyword_filter || '%')
      )
  AND (
        p.trace_keyword_filter IS NULL
        OR a.previous_trace_id ILIKE ('%' || p.trace_keyword_filter || '%')
        OR a.new_trace_id ILIKE ('%' || p.trace_keyword_filter || '%')
      )
ORDER BY a.created_at DESC, a.id DESC
LIMIT (SELECT row_limit FROM params)
OFFSET (SELECT row_offset FROM params);

\echo ''
\echo '=== baseline finished ==='
