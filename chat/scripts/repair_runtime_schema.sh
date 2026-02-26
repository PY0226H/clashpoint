#!/usr/bin/env bash
set -euo pipefail

# Dev compatibility repair:
# When _sqlx_migrations history diverges from current files, `cargo sqlx migrate run`
# may be blocked by "applied but missing". For local runtime bootstrap, we patch
# missing 2026 domain tables directly from migration SQL files.

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DB_NAME="${1:-chat}"
MIG_DIR="$ROOT/chat/migrations"

required_sql="SELECT to_regclass('public.debate_topics') IS NOT NULL,
                     to_regclass('public.debate_sessions') IS NOT NULL,
                     to_regclass('public.user_wallets') IS NOT NULL;"

existing="$(psql -d "$DB_NAME" -Atqc "$required_sql")"
if [[ "$existing" == "t|t|t" ]]; then
  echo "✓ 运行时核心表已存在（debate_topics/debate_sessions/user_wallets）"
  exit 0
fi

echo "! 检测到运行时核心表缺失，开始应用 2026 业务域 SQL（仅开发环境修复）..."

shopt -s nullglob
files=("$MIG_DIR"/202602*.sql)
if [[ ${#files[@]} -eq 0 ]]; then
  echo "✗ 未找到 202602 迁移文件，无法自动修复" >&2
  exit 1
fi

for f in "${files[@]}"; do
  echo "  -> apply $(basename "$f")"
  psql -d "$DB_NAME" -v ON_ERROR_STOP=1 -f "$f" >/dev/null
done

after="$(psql -d "$DB_NAME" -Atqc "$required_sql")"
if [[ "$after" != "t|t|t" ]]; then
  echo "✗ 修复后仍缺少核心表: $after" >&2
  exit 1
fi

echo "✓ 运行时核心表修复完成"

