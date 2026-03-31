#!/usr/bin/env bash
set -euo pipefail

# Return codes:
# 0: test changes present or no production changes detected
# 2: production changes detected but no test changes

ROOT=""
CHANGES=""

usage() {
  cat <<'USAGE'
用法:
  test_change_guard.sh [--root <path>] [--changes "a;b;c"]
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    --changes)
      CHANGES="$2"
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

if [[ -z "$CHANGES" ]]; then
  CHANGES="$(git -C "$ROOT" status --short 2>/dev/null | awk '{print $2}' | paste -sd ';' - || true)"
fi

if [[ -z "$CHANGES" ]]; then
  echo "未检测到改动文件，默认通过。"
  exit 0
fi

is_prod_file() {
  local f="$1"
  [[ -z "$f" ]] && return 1

  # Ignore docs/config only changes
  if [[ "$f" == docs/* || "$f" == skills/* || "$f" == *.md || "$f" == *.yml || "$f" == *.yaml ]]; then
    return 1
  fi

  # Rust production files in src
  if [[ "$f" == */src/* && "$f" == *.rs ]]; then
    return 0
  fi

  # Frontend production files
  if [[ "$f" == chatapp/src/* && ( "$f" == *.js || "$f" == *.ts || "$f" == *.vue ) ]]; then
    return 0
  fi

  return 1
}

is_test_file() {
  local f="$1"
  [[ -z "$f" ]] && return 1

  if [[ "$f" == *"/tests/"* || "$f" == */src/*/tests.rs || "$f" == *"_test."* || "$f" == *_tests.rs || "$f" == *.spec.ts || "$f" == *.test.ts || "$f" == *.test.js ]]; then
    return 0
  fi

  # Allow dedicated rust test crates
  if [[ "$f" == chat/chat_test/* ]]; then
    return 0
  fi

  return 1
}

has_inline_rust_tests() {
  local f="$1"
  [[ -z "$f" ]] && return 1
  [[ "$f" != *.rs ]] && return 1
  [[ "$f" != */src/* ]] && return 1
  [[ ! -f "$ROOT/$f" ]] && return 1
  grep -q "#\\[cfg(test)\\]" "$ROOT/$f"
}

prod_count=0
test_count=0
IFS=';' read -r -a files <<< "$CHANGES"
for f in "${files[@]}"; do
  f="${f## }"
  f="${f%% }"
  [[ -z "$f" ]] && continue
  if is_prod_file "$f"; then
    prod_count=$((prod_count + 1))
  fi
  if is_test_file "$f"; then
    test_count=$((test_count + 1))
    continue
  fi
  # Rust 项目常把测试内联在 src/*.rs 中，识别到 #[cfg(test)] 则视为有测试改动证据。
  if has_inline_rust_tests "$f"; then
    test_count=$((test_count + 1))
  fi
done

if [[ "${prod_count}" -gt 0 && "${test_count}" -eq 0 ]]; then
  echo "检测到模块代码改动 (${prod_count} 个)，但没有测试文件改动。"
  echo "请先补充测试，再继续执行测试门禁。"
  exit 2
fi

echo "测试改动检查通过（模块改动: ${prod_count}, 测试改动: ${test_count}）。"
exit 0
