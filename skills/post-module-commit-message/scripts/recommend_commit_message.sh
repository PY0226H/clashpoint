#!/usr/bin/env bash
set -euo pipefail

ROOT=""
TASK_KIND=""
MODULE=""
SUMMARY=""
TITLE_ONLY=0

usage() {
  cat <<'USAGE'
用法:
  recommend_commit_message.sh \
    --root <repo-root> \
    --task-kind <dev|refactor|non-dev> \
    --module <module-id> \
    --summary <summary> \
    [--title-only]

说明:
  根据当前 Git 改动与任务参数生成 Conventional Commits 标题建议。
USAGE
}

lower_ascii() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

sanitize_scope() {
  local value="$1"
  value="$(printf '%s' "$value" | sed -E 's/[^a-zA-Z0-9]+/-/g; s/^-+//; s/-+$//')"
  value="$(lower_ascii "$value")"
  [[ -z "$value" ]] && value="repo"
  printf '%s' "$value"
}

collect_changed_files() {
  {
    git -C "$ROOT" diff --name-only 2>/dev/null || true
    git -C "$ROOT" diff --cached --name-only 2>/dev/null || true
    git -C "$ROOT" ls-files --others --exclude-standard 2>/dev/null || true
  } | awk 'NF' | sort -u
}

detect_type() {
  local files="$1"
  local non_docs_count

  case "$TASK_KIND" in
    refactor) echo "refactor"; return 0 ;;
    non-dev) echo "docs"; return 0 ;;
  esac

  if [[ -n "$files" ]]; then
    if ! printf '%s\n' "$files" | grep -qvE '^(docs/|AGENTS\.md$|README\.md$|.*\.md$)'; then
      echo "docs"
      return 0
    fi
    if printf '%s\n' "$files" | grep -qE '^(\.github/|.*\.ya?ml$)' &&
       ! printf '%s\n' "$files" | grep -qvE '^(\.github/|.*\.ya?ml$)'; then
      echo "ci"
      return 0
    fi
    if printf '%s\n' "$files" | grep -qE '(^|/)(Cargo\.toml|Cargo\.lock|package\.json|pnpm-lock\.yaml)$'; then
      non_docs_count="$(printf '%s\n' "$files" | grep -cvE '^(docs/|.*\.md$)' || true)"
      if [[ "$non_docs_count" -le 2 ]]; then
        echo "build"
        return 0
      fi
    fi
  fi

  echo "feat"
}

build_subject() {
  local scope="$1"
  local summary_lower
  summary_lower="$(lower_ascii "$SUMMARY")"

  if [[ "$scope" == *"harness"* ]]; then
    echo "advance ${scope} orchestration"
  elif [[ "$summary_lower" == *"文档"* || "$summary_lower" == *"docs"* ]]; then
    echo "update ${scope} docs"
  elif [[ "$summary_lower" == *"lint"* ]]; then
    echo "tighten ${scope} lint rules"
  elif [[ "$summary_lower" == *"重构"* || "$summary_lower" == *"refactor"* ]]; then
    echo "refactor ${scope} workflow"
  else
    echo "advance ${scope} workflow"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    --task-kind)
      TASK_KIND="$2"
      shift 2
      ;;
    --module)
      MODULE="$2"
      shift 2
      ;;
    --summary)
      SUMMARY="$2"
      shift 2
      ;;
    --title-only)
      TITLE_ONLY=1
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
  ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
fi

scope="$(sanitize_scope "$MODULE")"
changed_files="$(collect_changed_files)"
type="$(detect_type "$changed_files")"
subject="$(build_subject "$scope")"
title="${type}(${scope}): ${subject}"

if [[ "$TITLE_ONLY" -eq 1 ]]; then
  printf '%s\n' "$title"
  exit 0
fi

cat <<EOF_RECOMMEND
Recommended:
$title

Alternatives:
1. $type: ${subject}
2. chore(${scope}): sync module follow-up
EOF_RECOMMEND
