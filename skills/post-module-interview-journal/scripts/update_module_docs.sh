#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
用法:
  update_module_docs.sh --module <name> --summary <text> [options]

参数:
  --module <name>       模块标识（必填）
  --summary <text>      改动内容与原因（必填）
  --changes <list>      改动文件列表，分号分隔
  --tests <text>        验证命令与结果
  --issues <list>       问题=>修复，分号分隔
  --learnings <list>    面试知识点，分号分隔
  --root <path>         仓库根目录（默认 git 根目录或当前目录）
USAGE
}

trim() {
  local v="$1"
  v="${v#${v%%[![:space:]]*}}"
  v="${v%${v##*[![:space:]]}}"
  printf '%s' "$v"
}

emit_bullets() {
  local raw="$1"
  local delim=';'
  IFS="$delim" read -r -a items <<< "$raw"
  local emitted=0
  for item in "${items[@]}"; do
    item="$(trim "$item")"
    if [[ -n "$item" ]]; then
      printf -- "- %s\n" "$item"
      emitted=1
    fi
  done
  if [[ "$emitted" -eq 0 ]]; then
    printf -- "- （无）\n"
  fi
}

emit_issue_pairs() {
  local raw="$1"
  local delim=';'
  IFS="$delim" read -r -a items <<< "$raw"
  local emitted=0
  for item in "${items[@]}"; do
    item="$(trim "$item")"
    [[ -z "$item" ]] && continue
    if [[ "$item" == *"=>"* ]]; then
      local lhs rhs
      lhs="$(trim "${item%%=>*}")"
      rhs="$(trim "${item#*=>}")"
      printf -- "- 现象/根因: %s\n" "${lhs:-未知}"
      printf -- "  修复: %s\n" "${rhs:-未知}"
    else
      printf -- "- %s\n" "$item"
    fi
    emitted=1
  done

  if [[ "$emitted" -eq 0 ]]; then
    printf -- "- （本模块无重大问题记录）\n"
  fi
}

ensure_file() {
  local file="$1"
  local title="$2"
  if [[ ! -f "$file" ]]; then
    cat > "$file" <<EOF_HEADER
# ${title}

EOF_HEADER
  fi
}

MODULE=""
SUMMARY=""
CHANGES=""
TESTS=""
ISSUES=""
LEARNINGS=""
ROOT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --module)
      MODULE="$2"
      shift 2
      ;;
    --summary)
      SUMMARY="$2"
      shift 2
      ;;
    --changes)
      CHANGES="$2"
      shift 2
      ;;
    --tests)
      TESTS="$2"
      shift 2
      ;;
    --issues)
      ISSUES="$2"
      shift 2
      ;;
    --learnings)
      LEARNINGS="$2"
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

if [[ -z "$MODULE" || -z "$SUMMARY" ]]; then
  echo "--module 和 --summary 为必填参数" >&2
  usage
  exit 1
fi

if [[ -z "$ROOT" ]]; then
  if git rev-parse --show-toplevel >/dev/null 2>&1; then
    ROOT="$(git rev-parse --show-toplevel)"
  else
    ROOT="$(pwd)"
  fi
fi

if [[ -z "$CHANGES" ]]; then
  CHANGES="$(git status --short 2>/dev/null | awk '{print $2}' | paste -sd ';' - || true)"
fi
if [[ -z "$CHANGES" ]]; then
  CHANGES="（未提供改动文件）"
fi

if [[ -z "$TESTS" ]]; then
  TESTS="（未提供验证信息）"
fi

DOC_DIR="$ROOT/docs/interview"
mkdir -p "$DOC_DIR"

DEV_LOG="$DOC_DIR/01-development-log.md"
ISSUE_LOG="$DOC_DIR/02-troubleshooting-log.md"
QA_LOG="$DOC_DIR/03-interview-qa-log.md"

ensure_file "$DEV_LOG" "开发过程记录"
ensure_file "$ISSUE_LOG" "问题与修复记录"
ensure_file "$QA_LOG" "面试问答记录"

TIMESTAMP="$(date '+%Y-%m-%d %H:%M:%S %z')"
BRANCH="$(git -C "$ROOT" symbolic-ref --short HEAD 2>/dev/null || echo detached-or-unborn)"
if HEAD_SHA="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null)"; then
  :
else
  HEAD_SHA="uncommitted"
fi

{
  printf '## %s | %s\n' "$MODULE" "$TIMESTAMP"
  printf -- '- 分支: `%s`\n' "$BRANCH"
  printf -- '- 提交: `%s`\n' "$HEAD_SHA"
  printf -- '- 改动概述:\n'
  printf -- '- %s\n' "$SUMMARY"
  printf -- '- 改动文件:\n'
  emit_bullets "$CHANGES"
  printf -- '- 验证结果:\n'
  printf -- '- %s\n' "$TESTS"
  printf '\n'
} >> "$DEV_LOG"

{
  printf '## %s | %s\n' "$MODULE" "$TIMESTAMP"
  printf -- '- 改动概述: %s\n' "$SUMMARY"
  printf -- '- 问题 -> 修复:\n'
  emit_issue_pairs "$ISSUES"
  printf -- '- 验证结果:\n'
  printf -- '- %s\n' "$TESTS"
  printf '\n'
} >> "$ISSUE_LOG"

{
  printf '## %s | %s\n' "$MODULE" "$TIMESTAMP"
  printf '### 面试叙事（STAR）\n'
  printf -- '- Situation（背景）: 该模块在正确性/安全性/产品可用性方面需要提升。\n'
  printf -- '- Task（任务）: 在不引入回归的前提下完成模块改造，并保证上线风险可控。\n'
  printf -- '- Action（行动）: %s\n' "$SUMMARY"
  printf -- '- Result（结果）: 已通过列出的验证，并沉淀了关键取舍与风险控制点。\n'
  printf '\n'
  printf '### 高频面试问题\n'
  printf -- '- 为什么采用这个方案，而不是其他替代方案？\n'
  printf -- '- 实现过程中遇到过哪些失败/故障，如何定位并修复？\n'
  printf -- '- 如何证明这次改动没有引入回归？\n'
  printf -- '- 如果流量增长 10 倍，最先优化哪一层，为什么？\n'
  printf '\n'
  printf '### 面试知识点\n'
  emit_bullets "$LEARNINGS"
  printf '\n'
} >> "$QA_LOG"

printf '已更新:\n- %s\n- %s\n- %s\n' "$DEV_LOG" "$ISSUE_LOG" "$QA_LOG"
