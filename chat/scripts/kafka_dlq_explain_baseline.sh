#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SQL_FILE="${SCRIPT_DIR}/sql/kafka_dlq_explain_baseline.sql"

if [[ ! -f "${SQL_FILE}" ]]; then
  echo "missing sql template: ${SQL_FILE}" >&2
  exit 1
fi

DB_URL="${DATABASE_URL:-}"
STATUS=""
EVENT_TYPE=""
CURSOR_UPDATED_AT=""
CURSOR_ID=""
LIMIT_VALUE="50"
OFFSET_VALUE="0"
CUTOFF_TS=""
RETENTION_BATCH_SIZE="500"
OUTPUT_PATH=""

usage() {
  cat <<'USAGE'
Usage:
  bash chat/scripts/kafka_dlq_explain_baseline.sh [options]

Options:
  --db-url <url>              Postgres connection url (fallback: DATABASE_URL)
  --status <text>             Optional status filter (pending/replayed/discarded)
  --event-type <text>         Optional event_type exact match filter
  --cursor-updated-at <ts>    Optional keyset cursor updated_at (RFC3339)
  --cursor-id <id>            Optional keyset cursor id (must be > 0 with cursor-updated-at)
  --limit <1..100>            List query limit (default: 50)
  --offset <>=0>              Offset query offset (default: 0)
  --cutoff <iso8601>          Retention cleanup cutoff (default: now()-14d)
  --retention-batch-size <n>  Retention batch size (default: 500, range 1..10000)
  --output <path>             Output file (default: /tmp/kafka_dlq_explain_<ts>.log)
  -h, --help                  Show this help

Examples:
  bash chat/scripts/kafka_dlq_explain_baseline.sh \
    --db-url "$DATABASE_URL" \
    --status pending \
    --event-type DebateMessageCreated \
    --limit 50 \
    --offset 0

  bash chat/scripts/kafka_dlq_explain_baseline.sh \
    --status replayed \
    --cursor-updated-at 2026-04-11T00:00:00Z \
    --cursor-id 1200 \
    --cutoff 2026-03-20T00:00:00Z \
    --retention-batch-size 500
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
    --status)
      STATUS="${2:-}"
      shift 2
      ;;
    --event-type)
      EVENT_TYPE="${2:-}"
      shift 2
      ;;
    --cursor-updated-at)
      CURSOR_UPDATED_AT="${2:-}"
      shift 2
      ;;
    --cursor-id)
      CURSOR_ID="${2:-}"
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
    --cutoff)
      CUTOFF_TS="${2:-}"
      shift 2
      ;;
    --retention-batch-size)
      RETENTION_BATCH_SIZE="${2:-}"
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
if (( LIMIT_VALUE < 1 || LIMIT_VALUE > 100 )); then
  echo "limit must be in range [1, 100]: ${LIMIT_VALUE}" >&2
  exit 1
fi

require_integer "${OFFSET_VALUE}" "offset"

require_integer "${RETENTION_BATCH_SIZE}" "retention-batch-size"
if (( RETENTION_BATCH_SIZE < 1 || RETENTION_BATCH_SIZE > 10000 )); then
  echo "retention-batch-size must be in range [1, 10000]: ${RETENTION_BATCH_SIZE}" >&2
  exit 1
fi

if [[ -n "${CURSOR_UPDATED_AT}" || -n "${CURSOR_ID}" ]]; then
  if [[ -z "${CURSOR_UPDATED_AT}" || -z "${CURSOR_ID}" ]]; then
    echo "cursor-updated-at and cursor-id must be provided together" >&2
    exit 1
  fi
  require_integer "${CURSOR_ID}" "cursor-id"
  if (( CURSOR_ID <= 0 )); then
    echo "cursor-id must be > 0: ${CURSOR_ID}" >&2
    exit 1
  fi
fi

if [[ -z "${OUTPUT_PATH}" ]]; then
  OUTPUT_PATH="/tmp/kafka_dlq_explain_$(date +%Y%m%d_%H%M%S).log"
fi
mkdir -p "$(dirname "${OUTPUT_PATH}")"

echo "[baseline] start kafka dlq explain analyze"
echo "[baseline] output: ${OUTPUT_PATH}"

psql "${DB_URL}" \
  -v ON_ERROR_STOP=1 \
  -v status="${STATUS}" \
  -v event_type="${EVENT_TYPE}" \
  -v cursor_updated_at="${CURSOR_UPDATED_AT}" \
  -v cursor_id="${CURSOR_ID}" \
  -v limit="${LIMIT_VALUE}" \
  -v offset="${OFFSET_VALUE}" \
  -v cutoff_ts="${CUTOFF_TS}" \
  -v retention_batch_size="${RETENTION_BATCH_SIZE}" \
  -f "${SQL_FILE}" \
  > "${OUTPUT_PATH}"

echo "[baseline] finished"
