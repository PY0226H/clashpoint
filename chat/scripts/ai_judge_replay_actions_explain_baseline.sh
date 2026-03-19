#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_FILE="${SCRIPT_DIR}/sql/ai_judge_replay_actions_explain_baseline.sql"

if [[ ! -f "${SQL_FILE}" ]]; then
  echo "missing sql template: ${SQL_FILE}" >&2
  exit 1
fi

DB_URL="${DATABASE_URL:-}"
FROM_TS=""
TO_TS=""
SCOPE=""
SESSION_ID=""
JOB_ID=""
REQUESTED_BY=""
PREVIOUS_STATUS=""
NEW_STATUS=""
REASON_KEYWORD=""
TRACE_KEYWORD=""
LIMIT_VALUE="50"
OFFSET_VALUE="0"
OUTPUT_PATH=""

usage() {
  cat <<'USAGE'
Usage:
  bash chat/scripts/ai_judge_replay_actions_explain_baseline.sh [options]

Options:
  --db-url <url>            Postgres connection url (fallback: DATABASE_URL)
  --from <iso8601>          Optional filter lower bound (created_at >= from)
  --to <iso8601>            Optional filter upper bound (created_at <= to)
  --scope <phase|final>     Optional scope filter
  --session-id <id>         Optional session_id filter
  --job-id <id>             Optional job_id filter
  --requested-by <id>       Optional requested_by filter
  --previous-status <text>  Optional previous_status filter
  --new-status <text>       Optional new_status filter
  --reason-keyword <text>   Optional reason keyword (ILIKE contains)
  --trace-keyword <text>    Optional trace keyword (ILIKE contains on prev/new trace)
  --limit <1..500>          List query limit (default: 50)
  --offset <>=0>            List query offset (default: 0)
  --output <path>           Output file path (default: /tmp/ai_judge_replay_actions_explain_<ts>.log)
  -h, --help                Show this help

Examples:
  bash chat/scripts/ai_judge_replay_actions_explain_baseline.sh \
    --db-url "$DATABASE_URL" \
    --scope phase \
    --previous-status failed \
    --new-status queued \
    --reason-keyword ops_ui_manual_replay

  bash chat/scripts/ai_judge_replay_actions_explain_baseline.sh \
    --trace-keyword trace-old-phase \
    --limit 100 \
    --offset 0
USAGE
}

require_integer() {
  local value="$1"
  local field="$2"
  if [[ ! "$value" =~ ^[0-9]+$ ]]; then
    echo "${field} must be a non-negative integer: ${value}" >&2
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --db-url)
      DB_URL="${2:-}"
      shift 2
      ;;
    --from)
      FROM_TS="${2:-}"
      shift 2
      ;;
    --to)
      TO_TS="${2:-}"
      shift 2
      ;;
    --scope)
      SCOPE="${2:-}"
      shift 2
      ;;
    --session-id)
      SESSION_ID="${2:-}"
      shift 2
      ;;
    --job-id)
      JOB_ID="${2:-}"
      shift 2
      ;;
    --requested-by)
      REQUESTED_BY="${2:-}"
      shift 2
      ;;
    --previous-status)
      PREVIOUS_STATUS="${2:-}"
      shift 2
      ;;
    --new-status)
      NEW_STATUS="${2:-}"
      shift 2
      ;;
    --reason-keyword)
      REASON_KEYWORD="${2:-}"
      shift 2
      ;;
    --trace-keyword)
      TRACE_KEYWORD="${2:-}"
      shift 2
      ;;
    --limit)
      LIMIT_VALUE="${2:-}"
      shift 2
      ;;
    --offset)
      OFFSET_VALUE="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT_PATH="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${DB_URL}" ]]; then
  echo "db url is required, set --db-url or DATABASE_URL" >&2
  exit 1
fi

require_integer "${LIMIT_VALUE}" "limit"
require_integer "${OFFSET_VALUE}" "offset"
if (( LIMIT_VALUE < 1 || LIMIT_VALUE > 500 )); then
  echo "limit must be in range [1, 500]: ${LIMIT_VALUE}" >&2
  exit 1
fi

if [[ -n "${SESSION_ID}" ]]; then
  require_integer "${SESSION_ID}" "session-id"
fi
if [[ -n "${JOB_ID}" ]]; then
  require_integer "${JOB_ID}" "job-id"
fi
if [[ -n "${REQUESTED_BY}" ]]; then
  require_integer "${REQUESTED_BY}" "requested-by"
fi

if [[ -n "${SCOPE}" && "${SCOPE}" != "phase" && "${SCOPE}" != "final" ]]; then
  echo "scope must be one of: phase, final" >&2
  exit 1
fi

if [[ -z "${OUTPUT_PATH}" ]]; then
  OUTPUT_PATH="/tmp/ai_judge_replay_actions_explain_$(date +%Y%m%d_%H%M%S).log"
fi

mkdir -p "$(dirname "${OUTPUT_PATH}")"

echo "[baseline] start replay actions explain analyze"
echo "[baseline] output: ${OUTPUT_PATH}"

psql "${DB_URL}" \
  -v ON_ERROR_STOP=1 \
  -v from_ts="${FROM_TS}" \
  -v to_ts="${TO_TS}" \
  -v scope="${SCOPE}" \
  -v session_id="${SESSION_ID}" \
  -v job_id="${JOB_ID}" \
  -v requested_by="${REQUESTED_BY}" \
  -v previous_status="${PREVIOUS_STATUS}" \
  -v new_status="${NEW_STATUS}" \
  -v reason_keyword="${REASON_KEYWORD}" \
  -v trace_keyword="${TRACE_KEYWORD}" \
  -v limit="${LIMIT_VALUE}" \
  -v offset="${OFFSET_VALUE}" \
  -f "${SQL_FILE}" \
  > "${OUTPUT_PATH}"

echo "[baseline] finished"
