#!/usr/bin/env bash
set -euo pipefail

ROOT=""
MAINTENANCE_URL="${CHAT_MIGRATION_MAINTENANCE_URL:-}"
DB_NAME=""
KEEP_DB="false"

usage() {
  cat <<'USAGE'
用法:
  verify_chat_migrations_fresh.sh [options]

选项:
  --root <path>              仓库根目录（默认: git top-level 或当前目录）
  --maintenance-url <url>    PostgreSQL maintenance URL（默认读取 CHAT_MIGRATION_MAINTENANCE_URL）
  --db-name <name>           指定临时数据库名（默认自动生成）
  --keep-db                  失败时保留临时数据库便于排查
  -h, --help                 显示帮助

说明:
  该脚本用于 W4/W6 验收，验证 chat/migrations 在“全新数据库”上的回放能力，
  并附加检查 ws_id 列是否已物理删除。
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    --maintenance-url)
      MAINTENANCE_URL="$2"
      shift 2
      ;;
    --db-name)
      DB_NAME="$2"
      shift 2
      ;;
    --keep-db)
      KEEP_DB="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$ROOT" ]]; then
  if git rev-parse --show-toplevel >/dev/null 2>&1; then
    ROOT="$(git rev-parse --show-toplevel)"
  else
    ROOT="$(pwd)"
  fi
fi

if [[ -z "$MAINTENANCE_URL" ]]; then
  echo "缺少 maintenance URL，请设置 CHAT_MIGRATION_MAINTENANCE_URL 或传入 --maintenance-url。" >&2
  exit 2
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "未找到 psql，无法执行迁移回放验收。" >&2
  exit 2
fi

if [[ -z "$DB_NAME" ]]; then
  DB_NAME="echoisle_migrate_verify_$(date +%Y%m%d_%H%M%S)_$$"
fi

base_no_query="${MAINTENANCE_URL%%\?*}"
query_suffix=""
if [[ "$MAINTENANCE_URL" == *\?* ]]; then
  query_suffix="?${MAINTENANCE_URL#*\?}"
fi
target_prefix="${base_no_query%/*}"
TARGET_URL="${target_prefix}/${DB_NAME}${query_suffix}"

MIG_DIR="$ROOT/chat/migrations"
if [[ ! -d "$MIG_DIR" ]]; then
  echo "未找到迁移目录: $MIG_DIR" >&2
  exit 1
fi

cleanup() {
  if [[ "$KEEP_DB" == "true" ]]; then
    echo "保留临时数据库: $DB_NAME"
    return
  fi
  psql "$MAINTENANCE_URL" -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS \"$DB_NAME\";" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if ! psql "$MAINTENANCE_URL" -v ON_ERROR_STOP=1 -c "SELECT 1;" >/dev/null 2>&1; then
  echo "无法连接 PostgreSQL maintenance URL: $MAINTENANCE_URL" >&2
  exit 2
fi

psql "$MAINTENANCE_URL" -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS \"$DB_NAME\";" >/dev/null
psql "$MAINTENANCE_URL" -v ON_ERROR_STOP=1 -c "CREATE DATABASE \"$DB_NAME\";" >/dev/null

echo "开始回放迁移到临时数据库: $DB_NAME"
for f in "$MIG_DIR"/*.sql; do
  echo "  -> $(basename "$f")"
  psql "$TARGET_URL" -v ON_ERROR_STOP=1 -f "$f" >/dev/null
done

echo "开始执行 schema 校验..."
ws_id_count="$(psql "$TARGET_URL" -Atqc \
  "SELECT COUNT(1) FROM information_schema.columns WHERE table_schema='public' AND column_name='ws_id';")"
if [[ "$ws_id_count" != "0" ]]; then
  echo "校验失败：仍存在 ws_id 列，数量=$ws_id_count" >&2
  exit 1
fi

workspace_table_exists="$(psql "$TARGET_URL" -Atqc \
  "SELECT to_regclass('public.workspaces') IS NOT NULL;")"
if [[ "$workspace_table_exists" != "f" ]]; then
  echo "校验失败：仍存在 legacy workspaces 表" >&2
  exit 1
fi

required_tables=(
  users
  chats
  debate_topics
  debate_sessions
  judge_jobs
  judge_reports
  auth_refresh_sessions
)

for t in "${required_tables[@]}"; do
  exists="$(psql "$TARGET_URL" -Atqc "SELECT to_regclass('public.${t}') IS NOT NULL;")"
  if [[ "$exists" != "t" ]]; then
    echo "校验失败：缺少核心表 $t" >&2
    exit 1
  fi
done

echo "迁移回放验收通过：fresh DB 无 ws_id 列、无 workspaces 表且核心表完整。"
