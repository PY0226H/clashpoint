#!/usr/bin/env bash
set -euo pipefail

ROOT=""
CHANGES=""

usage() {
  cat <<'USAGE'
用法:
  suggest_test_targets.sh [--root <path>] [--changes "a;b;c"]
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
  echo "未检测到改动文件。"
  exit 0
fi

echo "建议测试落点："
IFS=';' read -r -a files <<< "$CHANGES"
for f in "${files[@]}"; do
  [[ -z "$f" ]] && continue

  if [[ "$f" == */src/* && "$f" == *.rs ]]; then
    crate_dir="${f%%/src/*}"
    base_name="$(basename "$f" .rs)"
    echo "- Rust 模块: $f"
    echo "  - 优先补充: ${f} 内的 #[cfg(test)] 单元测试"
    echo "  - 备选补充: ${crate_dir}/tests/${base_name}_test.rs 集成测试"
    continue
  fi

  if [[ "$f" == chatapp/src/* && "$f" == *.vue ]]; then
    comp="$(basename "$f" .vue | tr '[:upper:]' '[:lower:]')"
    echo "- 前端组件: $f"
    echo "  - 建议补充 E2E: e2e/tests/${comp}.spec.ts"
    continue
  fi

  if [[ "$f" == chatapp/src/* && ( "$f" == *.js || "$f" == *.ts ) ]]; then
    mod="$(basename "$f" | sed 's/\.[^.]*$//' | tr '[:upper:]' '[:lower:]')"
    echo "- 前端逻辑: $f"
    echo "  - 建议补充 E2E: e2e/tests/${mod}.spec.ts"
    continue
  fi
done
