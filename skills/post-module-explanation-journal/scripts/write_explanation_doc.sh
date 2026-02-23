#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
用法:
  write_explanation_doc.sh --module <name> --summary <text> [options]

参数:
  --module <name>       模块标识（必填）
  --summary <text>      改动摘要（必填）
  --changes <list>      改动文件列表，分号分隔
  --body-file <path>    讲解正文 markdown 文件路径
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
    printf -- "- （未检测到改动文件）\n"
  fi
}

MODULE=""
SUMMARY=""
CHANGES=""
BODY_FILE=""
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
    --body-file)
      BODY_FILE="$2"
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
  CHANGES="$(git -C "$ROOT" status --short 2>/dev/null | awk '{print $2}' | paste -sd ';' - || true)"
fi

if [[ -z "$CHANGES" ]]; then
  CHANGES="（未提供改动文件）"
fi

BRANCH="$(git -C "$ROOT" symbolic-ref --short HEAD 2>/dev/null || echo detached-or-unborn)"
if HEAD_SHA="$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null)"; then
  :
else
  HEAD_SHA="uncommitted"
fi

DOC_DIR="$ROOT/docs/explanation"
mkdir -p "$DOC_DIR"

slug="$(printf '%s' "$MODULE" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')"
if [[ -z "$slug" ]]; then
  slug="module"
fi

STAMP_FILE="$(date '+%Y%m%d-%H%M%S')"
STAMP_HUMAN="$(date '+%Y-%m-%d %H:%M:%S %z')"
OUT_FILE="$DOC_DIR/${STAMP_FILE}-${slug}.md"

{
  printf '# 模块深度讲解：%s\n\n' "$MODULE"
  printf '## 元信息\n'
  printf -- '- 生成时间: `%s`\n' "$STAMP_HUMAN"
  printf -- '- 分支: `%s`\n' "$BRANCH"
  printf -- '- 提交: `%s`\n' "$HEAD_SHA"
  printf -- '- 讲解规范: `%s`\n' 'docs/explanation/00-讲解规范.md'
  printf -- '- 改动摘要: %s\n' "$SUMMARY"
  printf -- '- 改动文件:\n'
  emit_bullets "$CHANGES"
  printf '\n## 讲解正文\n\n'
} > "$OUT_FILE"

if [[ -n "$BODY_FILE" && -f "$BODY_FILE" ]]; then
  cat "$BODY_FILE" >> "$OUT_FILE"
else
  cat "$ROOT/skills/post-module-explanation-journal/assets/explanation-template.md" >> "$OUT_FILE"
fi

printf '已生成讲解文档:\n%s\n' "$OUT_FILE"
