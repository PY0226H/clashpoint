#!/usr/bin/env bash
set -euo pipefail

ROOT=""
THRESHOLD="700"
BASELINE=""

usage() {
  cat <<'USAGE'
用法:
  check_oversized_backend_files.sh [--root <path>] [--threshold <lines>] [--baseline <file>]

说明:
  - 仅检查后端代码：
    1) chat/*/src/**/*.rs
    2) ai_judge_service/app/**/*.py
  - 当文件行数 > threshold:
    - 若不在 baseline 中：失败（新增巨型文件）
    - 若在 baseline 中但超出 baseline 上限：失败（巨型文件继续膨胀）
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    --threshold)
      THRESHOLD="$2"
      shift 2
      ;;
    --baseline)
      BASELINE="$2"
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

if [[ -z "$BASELINE" ]]; then
  BASELINE="$ROOT/scripts/quality/oversized_backend_baseline.txt"
fi

if [[ ! "$THRESHOLD" =~ ^[0-9]+$ ]]; then
  echo "--threshold 必须是整数" >&2
  exit 1
fi

if [[ ! -f "$BASELINE" ]]; then
  echo "baseline 文件不存在: $BASELINE" >&2
  exit 1
fi

validate_baseline_line() {
  local line="$1"
  local path_part max_part
  path_part="$(echo "$line" | cut -d'|' -f1)"
  max_part="$(echo "$line" | cut -d'|' -f2)"

  if [[ -z "$path_part" || -z "$max_part" ]]; then
    echo "baseline 格式错误（应为 path|max_lines|note）: $line" >&2
    exit 1
  fi
  if [[ ! "$max_part" =~ ^[0-9]+$ ]]; then
    echo "baseline max_lines 非整数: $line" >&2
    exit 1
  fi
}

while IFS= read -r raw_line; do
  line="$(echo "$raw_line" | sed 's/[[:space:]]*$//')"
  [[ -z "$line" ]] && continue
  [[ "${line#\#}" != "$line" ]] && continue
  validate_baseline_line "$line"
done < "$BASELINE"

baseline_lookup_max() {
  local rel_path="$1"
  awk -F'|' -v p="$rel_path" '
    $0 !~ /^[[:space:]]*#/ && $1 == p { print $2; exit }
  ' "$BASELINE"
}

collect_targets() {
  find "$ROOT/chat" -type f -path "*/src/*.rs" 2>/dev/null
  find "$ROOT/ai_judge_service/app" -type f -name "*.py" 2>/dev/null
}

new_oversized=0
grown_oversized=0
allowed_oversized=0
checked_files=0

while IFS= read -r abs_path; do
  [[ -z "$abs_path" ]] && continue
  rel_path="${abs_path#"$ROOT"/}"
  checked_files=$((checked_files + 1))

  line_count="$(wc -l < "$abs_path" | tr -d ' ')"
  if (( line_count <= THRESHOLD )); then
    continue
  fi

  baseline_max="$(baseline_lookup_max "$rel_path")"
  if [[ -n "$baseline_max" ]]; then
    if (( line_count > baseline_max )); then
      grown_oversized=$((grown_oversized + 1))
      echo "[FAIL] 巨型文件继续膨胀: $rel_path (${line_count} > baseline ${baseline_max})"
    else
      allowed_oversized=$((allowed_oversized + 1))
      echo "[ALLOW] 基线内巨型文件: $rel_path (${line_count}, baseline ${baseline_max})"
    fi
  else
    new_oversized=$((new_oversized + 1))
    echo "[FAIL] 新增巨型文件: $rel_path (${line_count} > threshold ${THRESHOLD})"
  fi
done < <(collect_targets | sort)

echo
echo "检查摘要:"
echo "- 扫描文件数: ${checked_files}"
echo "- 阈值: ${THRESHOLD}"
echo "- 基线内巨型文件: ${allowed_oversized}"
echo "- 新增巨型文件: ${new_oversized}"
echo "- 继续膨胀文件: ${grown_oversized}"

if (( new_oversized > 0 || grown_oversized > 0 )); then
  cat <<'EOF'
结果: FAIL
处理建议:
1. 新增巨型文件请拆分模块，或补充拆分计划后再合并。
2. 既有巨型文件禁止继续膨胀，先拆分后扩展。
EOF
  exit 1
fi

echo "结果: PASS"
