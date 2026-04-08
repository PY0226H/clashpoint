#!/usr/bin/env bash
set -euo pipefail

MODE="dry-run"
DAYS=180
CHUNK_SIZE=5000
MAX_BATCHES=20

usage() {
  cat <<'USAGE'
Usage:
  bash chat/scripts/ops_rbac_audits_retention.sh [options]

Options:
  --days <n>          Retention days, keep data in [now-n days, now] (default: 180)
  --chunk-size <n>    Delete chunk size per batch in apply mode (default: 5000)
  --max-batches <n>   Max delete batches per run in apply mode (default: 20)
  --apply             Apply deletion, default is dry-run
  -h, --help          Show help

Environment:
  DATABASE_URL must be set for psql connection.

Examples:
  bash chat/scripts/ops_rbac_audits_retention.sh --days 180
  bash chat/scripts/ops_rbac_audits_retention.sh --days 180 --apply --chunk-size 10000
USAGE
}

is_positive_int() {
  local value="$1"
  [[ "${value}" =~ ^[0-9]+$ ]] && (( value > 0 ))
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --days)
      DAYS="${2:-}"
      shift 2
      ;;
    --chunk-size)
      CHUNK_SIZE="${2:-}"
      shift 2
      ;;
    --max-batches)
      MAX_BATCHES="${2:-}"
      shift 2
      ;;
    --apply)
      MODE="apply"
      shift
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

if ! is_positive_int "${DAYS}"; then
  echo "--days must be positive integer" >&2
  exit 1
fi

if ! is_positive_int "${CHUNK_SIZE}"; then
  echo "--chunk-size must be positive integer" >&2
  exit 1
fi

if ! is_positive_int "${MAX_BATCHES}"; then
  echo "--max-batches must be positive integer" >&2
  exit 1
fi

echo "[info] mode=${MODE} retention_days=${DAYS} chunk_size=${CHUNK_SIZE} max_batches=${MAX_BATCHES}"

echo "[info] current table status (rows older than retention window)"
psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -P pager=off \
  -v "days=${DAYS}" \
  -c "
SELECT
  COUNT(*)::BIGINT AS to_delete_rows,
  MIN(created_at) AS oldest_row_at,
  MAX(created_at) AS newest_row_at
FROM ops_rbac_audits
WHERE created_at < NOW() - make_interval(days => :'days'::INT);
"

if [[ "${MODE}" == "dry-run" ]]; then
  echo "[info] dry-run only (pass --apply to delete old rows)"
  exit 0
fi

echo "[info] applying retention cleanup in batches..."
total_deleted=0

for ((batch=1; batch<=MAX_BATCHES; batch++)); do
  deleted_rows="$(
    psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -At \
      -v "days=${DAYS}" \
      -v "chunk_size=${CHUNK_SIZE}" \
      -c "
WITH candidate AS (
  SELECT id
  FROM ops_rbac_audits
  WHERE created_at < NOW() - make_interval(days => :'days'::INT)
  ORDER BY created_at ASC, id ASC
  LIMIT :'chunk_size'::INT
),
deleted AS (
  DELETE FROM ops_rbac_audits a
  USING candidate c
  WHERE a.id = c.id
  RETURNING a.id
)
SELECT COUNT(*)::BIGINT
FROM deleted;
"
  )"

  deleted_rows="${deleted_rows:-0}"
  total_deleted=$(( total_deleted + deleted_rows ))
  echo "[info] batch=${batch} deleted_rows=${deleted_rows} total_deleted=${total_deleted}"

  if (( deleted_rows < CHUNK_SIZE )); then
    break
  fi
done

echo "[info] retention cleanup done total_deleted=${total_deleted}"
