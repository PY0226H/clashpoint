#!/usr/bin/env bash
set -euo pipefail

MODE="dry-run"
AUDIT_OUT=""

usage() {
  cat <<'USAGE'
Usage:
  bash chat/scripts/debate_sessions_count_reconcile.sh [--apply]

Options:
  --apply     Apply reconciliation to debate_sessions.pro_count/con_count
  --audit-out Write drift audit JSONL to file path
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
    --audit-out)
      AUDIT_OUT="${2:-}"
      if [[ -z "${AUDIT_OUT}" ]]; then
        echo "--audit-out requires a file path" >&2
        exit 1
      fi
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

if [[ -n "${AUDIT_OUT}" ]]; then
  mkdir -p "$(dirname "${AUDIT_OUT}")"
  psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -At <<SQL > "${AUDIT_OUT}"
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
SELECT json_build_object(
  'mode', '${MODE}',
  'action', 'drift_detected',
  'capturedAt', NOW(),
  'sessionId', session_id,
  'storedProCount', stored_pro_count,
  'storedConCount', stored_con_count,
  'actualProCount', actual_pro_count,
  'actualConCount', actual_con_count
)::text
FROM diff
ORDER BY session_id;
SQL
  echo "[info] wrote drift audit to ${AUDIT_OUT}"
fi

if [[ "${MODE}" == "apply" ]]; then
  echo "[info] applying reconciliation..."
  UPDATED_ROWS="$(psql "${DATABASE_URL}" -v ON_ERROR_STOP=1 -At <<'SQL'
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
)"
  echo "updated_rows=${UPDATED_ROWS}"
  if [[ -n "${AUDIT_OUT}" ]]; then
    printf '%s\n' \
      "{\"mode\":\"${MODE}\",\"action\":\"reconcile_applied\",\"capturedAt\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"updatedRows\":${UPDATED_ROWS}}" \
      >> "${AUDIT_OUT}"
    echo "[info] appended apply summary to ${AUDIT_OUT}"
  fi
else
  echo "[info] dry-run only (pass --apply to persist fixes)"
fi
