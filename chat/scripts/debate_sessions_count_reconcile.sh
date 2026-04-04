#!/usr/bin/env bash
set -euo pipefail

MODE="dry-run"

usage() {
  cat <<'USAGE'
Usage:
  bash chat/scripts/debate_sessions_count_reconcile.sh [--apply]

Options:
  --apply     Apply reconciliation to debate_sessions.pro_count/con_count
  -h, --help  Show help

Environment:
  DATABASE_URL must be set for psql connection.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
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

echo "[info] mode=${MODE}"
echo "[info] checking participant count drift..."

psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 <<'SQL'
WITH actual AS (
  SELECT
    session_id,
    COUNT(*) FILTER (WHERE side = 'pro')::int AS actual_pro_count,
    COUNT(*) FILTER (WHERE side = 'con')::int AS actual_con_count
  FROM session_participants
  GROUP BY session_id
),
diff AS (
  SELECT
    s.id AS session_id,
    s.pro_count AS stored_pro_count,
    s.con_count AS stored_con_count,
    COALESCE(a.actual_pro_count, 0) AS actual_pro_count,
    COALESCE(a.actual_con_count, 0) AS actual_con_count
  FROM debate_sessions s
  LEFT JOIN actual a ON a.session_id = s.id
  WHERE s.pro_count <> COALESCE(a.actual_pro_count, 0)
     OR s.con_count <> COALESCE(a.actual_con_count, 0)
)
SELECT * FROM diff ORDER BY session_id;
SQL

if [[ "${MODE}" == "apply" ]]; then
  echo "[info] applying reconciliation..."
  psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 <<'SQL'
WITH actual AS (
  SELECT
    session_id,
    COUNT(*) FILTER (WHERE side = 'pro')::int AS actual_pro_count,
    COUNT(*) FILTER (WHERE side = 'con')::int AS actual_con_count
  FROM session_participants
  GROUP BY session_id
),
target AS (
  SELECT
    s.id,
    COALESCE(a.actual_pro_count, 0) AS next_pro_count,
    COALESCE(a.actual_con_count, 0) AS next_con_count
  FROM debate_sessions s
  LEFT JOIN actual a ON a.session_id = s.id
  WHERE s.pro_count <> COALESCE(a.actual_pro_count, 0)
     OR s.con_count <> COALESCE(a.actual_con_count, 0)
),
updated AS (
  UPDATE debate_sessions s
  SET
    pro_count = t.next_pro_count,
    con_count = t.next_con_count,
    updated_at = NOW()
  FROM target t
  WHERE s.id = t.id
  RETURNING s.id
)
SELECT COUNT(*)::int AS updated_rows FROM updated;
SQL
else
  echo "[info] dry-run only (pass --apply to persist fixes)"
fi
