#!/usr/bin/env bash
set -euo pipefail

# Deprecated emergency repair:
# Default local bootstrap must use formal migration replay (`cargo sqlx migrate run`).
# This script is kept only for temporary fallback in legacy/broken local DB states.

if [[ "${ECHOISLE_ALLOW_LEGACY_REPAIR:-0}" != "1" ]]; then
  echo "该脚本已降级为应急路径，不再作为默认初始化流程。" >&2
  echo "如确需执行，请显式设置 ECHOISLE_ALLOW_LEGACY_REPAIR=1。" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DB_NAME="${1:-chat}"
MIG_DIR="$ROOT/chat/migrations"

required_sql="SELECT to_regclass('public.debate_topics') IS NOT NULL,
                     to_regclass('public.debate_sessions') IS NOT NULL,
                     to_regclass('public.user_wallets') IS NOT NULL;"

existing="$(psql -d "$DB_NAME" -Atqc "$required_sql")"
if [[ "$existing" == "t|t|t" ]]; then
  echo "✓ 应急检查：运行时核心表已存在（debate_topics/debate_sessions/user_wallets）"
  exit 0
fi

echo "! 检测到运行时核心表缺失，开始执行应急修复（仅限本地临时兜底）..."

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
