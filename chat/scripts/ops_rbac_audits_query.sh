#!/usr/bin/env bash
set -euo pipefail

FROM_TS=""
TO_TS=""
OPERATOR_USER_ID=""
TARGET_USER_ID=""
EVENT_TYPE=""
DECISION=""
LIMIT=200
SUMMARY=false
JSONL_OUT=""

usage() {
  cat <<'USAGE'
Usage:
  bash chat/scripts/ops_rbac_audits_query.sh [options]

Options:
  --from <timestamptz>           Start time (inclusive), e.g. 2026-04-08T00:00:00Z
  --to <timestamptz>             End time (exclusive)
  --operator-user-id <u64>       Filter by operator user id
  --target-user-id <u64>         Filter by target user id
  --event-type <type>            One of: roles_list_read|rbac_me_read|role_upsert|role_revoke
  --decision <type>              One of: success|failed|rate_limited_user|rate_limited_ip
  --limit <n>                    Max rows to query (default: 200, max: 1000)
  --summary                      Print event/decision aggregate summary after detail rows
  --jsonl-out <file>             Export result rows as JSONL
  -h, --help                     Show help

Behavior:
  - If --from is not provided, defaults to "now() - 24h".
  - If --to is not provided, defaults to "now() + 1s".
  - Detail rows are ordered by created_at DESC, id DESC.

Environment:
  DATABASE_URL must be set for psql connection.
USAGE
}

validate_u64() {
  local value="$1"
  [[ "${value}" =~ ^[0-9]+$ ]]
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from)
      FROM_TS="${2:-}"
      shift 2
      ;;
    --to)
      TO_TS="${2:-}"
      shift 2
      ;;
    --operator-user-id)
      OPERATOR_USER_ID="${2:-}"
      shift 2
      ;;
    --target-user-id)
      TARGET_USER_ID="${2:-}"
      shift 2
      ;;
    --event-type)
      EVENT_TYPE="${2:-}"
      shift 2
      ;;
    --decision)
      DECISION="${2:-}"
      shift 2
      ;;
    --limit)
      LIMIT="${2:-}"
      shift 2
      ;;
    --summary)
      SUMMARY=true
      shift
      ;;
    --jsonl-out)
      JSONL_OUT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required" >&2
  exit 1
fi

if [[ -n "${OPERATOR_USER_ID}" ]] && ! validate_u64 "${OPERATOR_USER_ID}"; then
  echo "--operator-user-id must be unsigned integer" >&2
  exit 1
fi

if [[ -n "${TARGET_USER_ID}" ]] && ! validate_u64 "${TARGET_USER_ID}"; then
  echo "--target-user-id must be unsigned integer" >&2
  exit 1
fi

case "${EVENT_TYPE}" in
  ""|roles_list_read|rbac_me_read|role_upsert|role_revoke) ;;
  *)
    echo "--event-type invalid: ${EVENT_TYPE}" >&2
    exit 1
    ;;
esac

case "${DECISION}" in
  ""|success|failed|rate_limited_user|rate_limited_ip) ;;
  *)
    echo "--decision invalid: ${DECISION}" >&2
    exit 1
    ;;
esac

if ! [[ "${LIMIT}" =~ ^[0-9]+$ ]]; then
  echo "--limit must be integer" >&2
  exit 1
fi
if (( LIMIT <= 0 || LIMIT > 1000 )); then
  echo "--limit must be between 1 and 1000" >&2
  exit 1
fi

echo "[info] querying ops_rbac_audits..."
echo "[info] filters from='${FROM_TS:-<default-24h>}' to='${TO_TS:-<default-now+1s>}' operator='${OPERATOR_USER_ID:-*}' target='${TARGET_USER_ID:-*}' event='${EVENT_TYPE:-*}' decision='${DECISION:-*}' limit=${LIMIT}"

DETAIL_SQL='
WITH filtered AS (
  SELECT
    id,
    event_type,
    operator_user_id,
    target_user_id,
    request_id,
    decision,
    result_count,
    role,
    removed,
    created_at
  FROM ops_rbac_audits
  WHERE created_at >= COALESCE(NULLIF(:'"'"'from_ts'"'"', '"'"''"'"')::timestamptz, NOW() - INTERVAL '"'"''"'"'24 hours'"'"''"'"')
    AND created_at < COALESCE(NULLIF(:'"'"'to_ts'"'"', '"'"''"'"')::timestamptz, NOW() + INTERVAL '"'"''"'"'1 second'"'"''"'"')
    AND (NULLIF(:'"'"'operator_user_id'"'"', '"'"''"'"') IS NULL OR operator_user_id = NULLIF(:'"'"'operator_user_id'"'"', '"'"''"'"')::BIGINT)
    AND (NULLIF(:'"'"'target_user_id'"'"', '"'"''"'"') IS NULL OR target_user_id = NULLIF(:'"'"'target_user_id'"'"', '"'"''"'"')::BIGINT)
    AND (NULLIF(:'"'"'event_type'"'"', '"'"''"'"') IS NULL OR event_type = NULLIF(:'"'"'event_type'"'"', '"'"''"'"'))
    AND (NULLIF(:'"'"'decision'"'"', '"'"''"'"') IS NULL OR decision = NULLIF(:'"'"'decision'"'"', '"'"''"'"'))
  ORDER BY created_at DESC, id DESC
  LIMIT :'"'"'limit'"'"'::INT
)
SELECT
  id,
  to_char(created_at AT TIME ZONE ''UTC'', ''YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'') AS created_at_utc,
  event_type,
  decision,
  operator_user_id,
  COALESCE(target_user_id::text, ''-'') AS target_user_id,
  COALESCE(request_id, ''-'') AS request_id,
  COALESCE(result_count::text, ''-'') AS result_count,
  COALESCE(role, ''-'') AS role,
  COALESCE(removed::text, ''-'') AS removed
FROM filtered
ORDER BY created_at DESC, id DESC;
'

psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -P pager=off \
  -v "from_ts=${FROM_TS}" \
  -v "to_ts=${TO_TS}" \
  -v "operator_user_id=${OPERATOR_USER_ID}" \
  -v "target_user_id=${TARGET_USER_ID}" \
  -v "event_type=${EVENT_TYPE}" \
  -v "decision=${DECISION}" \
  -v "limit=${LIMIT}" \
  -c "${DETAIL_SQL}"

if [[ "${SUMMARY}" == "true" ]]; then
  SUMMARY_SQL='
WITH filtered AS (
  SELECT event_type, decision, created_at
  FROM ops_rbac_audits
  WHERE created_at >= COALESCE(NULLIF(:'"'"'from_ts'"'"', '"'"''"'"')::timestamptz, NOW() - INTERVAL '"'"''"'"'24 hours'"'"''"'"')
    AND created_at < COALESCE(NULLIF(:'"'"'to_ts'"'"', '"'"''"'"')::timestamptz, NOW() + INTERVAL '"'"''"'"'1 second'"'"''"'"')
    AND (NULLIF(:'"'"'operator_user_id'"'"', '"'"''"'"') IS NULL OR operator_user_id = NULLIF(:'"'"'operator_user_id'"'"', '"'"''"'"')::BIGINT)
    AND (NULLIF(:'"'"'target_user_id'"'"', '"'"''"'"') IS NULL OR target_user_id = NULLIF(:'"'"'target_user_id'"'"', '"'"''"'"')::BIGINT)
    AND (NULLIF(:'"'"'event_type'"'"', '"'"''"'"') IS NULL OR event_type = NULLIF(:'"'"'event_type'"'"', '"'"''"'"'))
    AND (NULLIF(:'"'"'decision'"'"', '"'"''"'"') IS NULL OR decision = NULLIF(:'"'"'decision'"'"', '"'"''"'"'))
  ORDER BY created_at DESC
  LIMIT :'"'"'limit'"'"'::INT
)
SELECT
  event_type,
  decision,
  COUNT(*)::BIGINT AS count,
  MIN(created_at) AS first_seen_at,
  MAX(created_at) AS last_seen_at
FROM filtered
GROUP BY event_type, decision
ORDER BY event_type, decision;
'
  echo
  echo "[info] summary (event_type, decision)"
  psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -P pager=off \
    -v "from_ts=${FROM_TS}" \
    -v "to_ts=${TO_TS}" \
    -v "operator_user_id=${OPERATOR_USER_ID}" \
    -v "target_user_id=${TARGET_USER_ID}" \
    -v "event_type=${EVENT_TYPE}" \
    -v "decision=${DECISION}" \
    -v "limit=${LIMIT}" \
    -c "${SUMMARY_SQL}"
fi

if [[ -n "${JSONL_OUT}" ]]; then
  mkdir -p "$(dirname "${JSONL_OUT}")"
  JSONL_SQL='
WITH filtered AS (
  SELECT
    id,
    event_type,
    operator_user_id,
    target_user_id,
    request_id,
    decision,
    result_count,
    role,
    removed,
    created_at
  FROM ops_rbac_audits
  WHERE created_at >= COALESCE(NULLIF(:'"'"'from_ts'"'"', '"'"''"'"')::timestamptz, NOW() - INTERVAL '"'"''"'"'24 hours'"'"''"'"')
    AND created_at < COALESCE(NULLIF(:'"'"'to_ts'"'"', '"'"''"'"')::timestamptz, NOW() + INTERVAL '"'"''"'"'1 second'"'"''"'"')
    AND (NULLIF(:'"'"'operator_user_id'"'"', '"'"''"'"') IS NULL OR operator_user_id = NULLIF(:'"'"'operator_user_id'"'"', '"'"''"'"')::BIGINT)
    AND (NULLIF(:'"'"'target_user_id'"'"', '"'"''"'"') IS NULL OR target_user_id = NULLIF(:'"'"'target_user_id'"'"', '"'"''"'"')::BIGINT)
    AND (NULLIF(:'"'"'event_type'"'"', '"'"''"'"') IS NULL OR event_type = NULLIF(:'"'"'event_type'"'"', '"'"''"'"'))
    AND (NULLIF(:'"'"'decision'"'"', '"'"''"'"') IS NULL OR decision = NULLIF(:'"'"'decision'"'"', '"'"''"'"'))
  ORDER BY created_at DESC, id DESC
  LIMIT :'"'"'limit'"'"'::INT
)
SELECT json_build_object(
  '"'"''"'"'id'"'"''"'"', id,
  '"'"''"'"'eventType'"'"''"'"', event_type,
  '"'"''"'"'operatorUserId'"'"''"'"', operator_user_id,
  '"'"''"'"'targetUserId'"'"''"'"', target_user_id,
  '"'"''"'"'requestId'"'"''"'"', request_id,
  '"'"''"'"'decision'"'"''"'"', decision,
  '"'"''"'"'resultCount'"'"''"'"', result_count,
  '"'"''"'"'role'"'"''"'"', role,
  '"'"''"'"'removed'"'"''"'"', removed,
  '"'"''"'"'createdAt'"'"''"'"', created_at
)::text
FROM filtered
ORDER BY created_at DESC, id DESC;
'

  psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -At \
    -v "from_ts=${FROM_TS}" \
    -v "to_ts=${TO_TS}" \
    -v "operator_user_id=${OPERATOR_USER_ID}" \
    -v "target_user_id=${TARGET_USER_ID}" \
    -v "event_type=${EVENT_TYPE}" \
    -v "decision=${DECISION}" \
    -v "limit=${LIMIT}" \
    -c "${JSONL_SQL}" \
    > "${JSONL_OUT}"

  echo "[info] wrote jsonl to ${JSONL_OUT}"
fi
