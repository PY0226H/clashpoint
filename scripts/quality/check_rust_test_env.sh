#!/usr/bin/env bash
set -euo pipefail

ROOT=""

usage() {
  cat <<'USAGE'
用法:
  check_rust_test_env.sh [--root <path>]

说明:
  - 在运行 Rust nextest 前检查 Postgres 测试前置是否可达
  - chat 测试会创建临时数据库，必须能连到 maintenance DB `postgres`
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
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

if [[ "${RUST_TEST_ENV_SKIP_DB_CHECK:-0}" == "1" ]]; then
  echo "[SKIP] RUST_TEST_ENV_SKIP_DB_CHECK=1，跳过 Postgres 前置检查。"
  exit 0
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "[FAIL] 未找到 psql，请先安装 PostgreSQL 客户端。" >&2
  exit 1
fi

to_maintenance_db_url() {
  local url="$1"
  local base="${url%%\?*}"
  if [[ "$base" != *"/"* ]]; then
    printf '%s' "$url"
    return
  fi
  printf '%s/postgres' "${base%/*}"
}

can_connect() {
  local url="$1"
  psql "$url" -v ON_ERROR_STOP=1 -Atqc "select 1" >/dev/null 2>&1
}

declare -a candidates=()
if [[ -n "${DATABASE_URL:-}" ]]; then
  candidates+=("$(to_maintenance_db_url "$DATABASE_URL")")
fi
candidates+=("postgres://postgres:postgres@localhost:5432/postgres")
if [[ -n "${USER:-}" ]]; then
  candidates+=("postgres://${USER}@localhost:5432/postgres")
fi

declare -a uniq_candidates=()
for candidate in "${candidates[@]-}"; do
  skip=0
  for existing in "${uniq_candidates[@]-}"; do
    if [[ "$existing" == "$candidate" ]]; then
      skip=1
      break
    fi
  done
  if [[ "$skip" -eq 0 ]]; then
    uniq_candidates+=("$candidate")
  fi
done

for candidate in "${uniq_candidates[@]-}"; do
  if can_connect "$candidate"; then
    echo "[PASS] Rust nextest 前置通过，可连接 maintenance DB: $candidate"
    exit 0
  fi
done

echo "[FAIL] Rust nextest 前置失败：无法连接 maintenance DB（postgres）。" >&2
echo "尝试过的连接串:" >&2
for candidate in "${uniq_candidates[@]-}"; do
  echo "  - $candidate" >&2
done
cat >&2 <<'EOF'
建议:
1. 确认 PostgreSQL 已启动（例如: brew services start postgresql@14）。
2. 确认至少一个候选连接串可用（本机用户或 postgres:postgres）。
3. 若本机使用自定义连接串，设置 DATABASE_URL 后重试。
EOF
exit 1
