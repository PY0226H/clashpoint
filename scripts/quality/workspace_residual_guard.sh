#!/usr/bin/env bash
set -euo pipefail

ROOT=""

usage() {
  cat <<'USAGE'
用法:
  workspace_residual_guard.sh [--root <path>]

说明:
  仅检查当前改动新增行是否引入以下残留标识:
  - ws_id
  - workspace_id
  - workspaces
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

if ! git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "workspace residual guard: 非 git 仓库，跳过。"
  exit 0
fi

is_residual_line() {
  local line="$1"
  [[ "$line" =~ (^|[^A-Za-z0-9_])ws_id([^A-Za-z0-9_]|$) ]] && return 0
  [[ "$line" =~ workspace_id ]] && return 0
  [[ "$line" =~ (^|[^A-Za-z0-9_])workspaces([^A-Za-z0-9_]|$) ]] && return 0
  return 1
}

is_allowed_line() {
  local file="$1"
  local line="$2"

  # Guard script itself contains pattern definitions.
  if [[ "$file" == "scripts/quality/workspace_residual_guard.sh" ]] ||
     [[ "$file" == "scripts/quality/verify_chat_migrations_fresh.sh" ]]; then
    return 0
  fi

  # W4 删除迁移允许出现 ws_id 的 DROP 语句。
  if [[ "$file" =~ ^chat/migrations/[0-9]{14}_workspace_removal_.*\.sql$ ]] &&
     [[ "$line" =~ DROP[[:space:]]+COLUMN[[:space:]]+IF[[:space:]]+EXISTS[[:space:]]+ws_id\; ]]; then
    return 0
  fi

  return 1
}

check_diff_stream() {
  local stream="$1"
  local current_file=""
  local has_violation=0

  while IFS='' read -r line || [[ -n "$line" ]]; do
    if [[ "$line" =~ ^\+\+\+[[:space:]]b/(.+)$ ]]; then
      current_file="${BASH_REMATCH[1]}"
      continue
    fi

    if [[ "$line" =~ ^\+\+\+ ]]; then
      continue
    fi

    if [[ -z "$current_file" ]]; then
      continue
    fi

    if [[ ! "$line" =~ ^\+ ]]; then
      continue
    fi

    local added="${line:1}"
    if is_residual_line "$added" && ! is_allowed_line "$current_file" "$added"; then
      echo "workspace 残留命中: $current_file :: $added" >&2
      has_violation=1
    fi
  done <"$stream"

  return "$has_violation"
}

tmp_work="$(mktemp)"
tmp_index="$(mktemp)"
trap 'rm -f "$tmp_work" "$tmp_index"' EXIT

git -C "$ROOT" diff --unified=0 --no-color >"$tmp_work" || true
git -C "$ROOT" diff --cached --unified=0 --no-color >"$tmp_index" || true

has_violation=0
check_diff_stream "$tmp_work" || has_violation=1
check_diff_stream "$tmp_index" || has_violation=1

# Untracked files are not included in git diff output.
while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  [[ ! -f "$ROOT/$f" ]] && continue
  while IFS='' read -r line || [[ -n "$line" ]]; do
    if is_residual_line "$line" && ! is_allowed_line "$f" "$line"; then
      echo "workspace 残留命中: $f :: $line" >&2
      has_violation=1
    fi
  done <"$ROOT/$f"
done < <(git -C "$ROOT" ls-files --others --exclude-standard)

if [[ "$has_violation" -ne 0 ]]; then
  cat <<'EOF' >&2
workspace residual guard 失败：检测到新增残留标识（ws_id/workspace_id/workspaces）。
请改为 scope/platform 单租户语义，或将删除迁移语句放入 workspace_removal 迁移文件并使用 DROP COLUMN IF EXISTS ws_id。
EOF
  exit 1
fi

echo "workspace residual guard 通过（未发现新增残留标识）。"
