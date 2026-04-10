#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SQL_FILE="$ROOT_DIR/scripts/sql/ai_judge_rejudge_run_versioning_verify.sql"

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required"
  echo "example: DATABASE_URL=postgres://user@localhost:5432/chat $0"
  exit 1
fi

if [[ ! -f "$SQL_FILE" ]]; then
  echo "verify sql not found: $SQL_FILE"
  exit 1
fi

echo "[api067] running run/version migration verifier ..."
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$SQL_FILE"
echo "[api067] verifier passed."
