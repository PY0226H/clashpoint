#!/usr/bin/env bash
set -euo pipefail

MODE="full"
ROOT=""

usage() {
  cat <<'USAGE'
用法:
  run_test_gate.sh [--mode quick|full] [--root <path>]

说明:
  quick: 快速门禁（fmt/check/nextest）
  full: 完整门禁（fmt/check/clippy/nextest）
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="$2"
      shift 2
      ;;
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

if [[ "$MODE" != "quick" && "$MODE" != "full" ]]; then
  echo "--mode 仅支持 quick 或 full" >&2
  exit 1
fi

if [[ -z "$ROOT" ]]; then
  if git rev-parse --show-toplevel >/dev/null 2>&1; then
    ROOT="$(git rev-parse --show-toplevel)"
  else
    ROOT="$(pwd)"
  fi
fi

SUBDIRS=("chat" "swiftide-pgvector" "chatapp/src-tauri")

run_in_dir() {
  local dir="$1"
  local cmd="$2"
  echo "[${dir}] $cmd"
  if (cd "$ROOT/$dir" && eval "$cmd"); then
    return 0
  fi

  cat <<'EOF_HINT'
命令执行失败。若日志中包含 `utoipa-swagger-ui` 且出现 `Could not resolve host: github.com`，
这是构建阶段需要下载 Swagger UI 资源但当前环境无外网导致的失败，不一定是业务改动引入的问题。
可在有网络环境重试，或预置 Swagger UI 资源后再执行门禁。
EOF_HINT
  return 1
}

for dir in "${SUBDIRS[@]}"; do
  run_in_dir "$dir" "cargo fmt --all -- --check"
  run_in_dir "$dir" "cargo check --all"

  if [[ "$MODE" == "full" ]]; then
    run_in_dir "$dir" "cargo clippy --all-targets --all-features --tests --benches -- -D warnings"
  fi

  run_in_dir "$dir" "cargo nextest run --all-features"
done

echo "测试门禁通过（mode=$MODE）。"
