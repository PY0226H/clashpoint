#!/usr/bin/env bash
set -euo pipefail

ROOT=""
ARTIFACTS_DIR=""
KEEP_LATEST="15"
APPLY_DELETE="false"
EMIT_JSON=""
EMIT_MD=""

RUN_ID=""
STARTED_AT=""
FINISHED_AT=""
STATUS="unknown"

PRUNE_FILES=()
PRUNE_DIRS=()

usage() {
  cat <<'USAGE'
用法:
  ai_judge_artifact_prune.sh \
    [--root <repo-root>] \
    [--artifacts-dir <path>] \
    [--keep-latest <int>] \
    [--apply] \
    [--emit-json <path>] \
    [--emit-md <path>]

说明:
  1. 默认 dry-run，仅输出候选清单，不删除文件。
  2. 仅处理时间戳命名产物：
     - 文件：YYYYMMDDTHHMMSSZ-<module>.summary.json/.md
     - 目录：YYYYMMDDTHHMMSSZ-<module>/
  3. 非时间戳命名的 summary 文件不会被处理。
USAGE
}

iso_now() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

json_escape() {
  local value="${1:-}"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/\\n}"
  value="${value//$'\r'/\\r}"
  value="${value//$'\t'/\\t}"
  printf '%s' "$value"
}

resolve_root() {
  if [[ -n "$ROOT" ]]; then
    return
  fi
  if git rev-parse --show-toplevel >/dev/null 2>&1; then
    ROOT="$(git rev-parse --show-toplevel)"
  else
    ROOT="$(pwd)"
  fi
}

abs_path() {
  local path="${1:-}"
  if [[ -z "$path" ]]; then
    printf '%s' ""
    return
  fi
  if [[ "$path" = /* ]]; then
    printf '%s' "$path"
  else
    printf '%s' "$ROOT/$path"
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --root)
        ROOT="${2:-}"
        shift 2
        ;;
      --artifacts-dir)
        ARTIFACTS_DIR="${2:-}"
        shift 2
        ;;
      --keep-latest)
        KEEP_LATEST="${2:-}"
        shift 2
        ;;
      --apply)
        APPLY_DELETE="true"
        shift 1
        ;;
      --emit-json)
        EMIT_JSON="${2:-}"
        shift 2
        ;;
      --emit-md)
        EMIT_MD="${2:-}"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        echo "未知参数: $1" >&2
        usage
        exit 2
        ;;
    esac
  done
}

collect_prune_candidates() {
  local file base module key idx
  local tmp_json tmp_dirs tmp_modules_json tmp_modules_dirs
  tmp_json="$(mktemp)"
  tmp_dirs="$(mktemp)"
  tmp_modules_json="$(mktemp)"
  tmp_modules_dirs="$(mktemp)"

  # macOS 默认 bash 3.2 不支持关联数组，这里改为临时文件聚合。
  while IFS= read -r file; do
    base="$(basename "$file")"
    if [[ "$base" =~ ^([0-9]{8}T[0-9]{6}Z)-(.+)\.summary\.json$ ]]; then
      key="${BASH_REMATCH[1]}-${BASH_REMATCH[2]}"
      module="${BASH_REMATCH[2]}"
      printf '%s|%s|%s\n' "$module" "$key" "$file" >>"$tmp_json"
      printf '%s\n' "$module" >>"$tmp_modules_json"
    fi
  done < <(find "$ARTIFACTS_DIR" -maxdepth 1 -type f -name "*.summary.json" -print 2>/dev/null)

  while IFS= read -r file; do
    base="$(basename "$file")"
    if [[ "$base" =~ ^([0-9]{8}T[0-9]{6}Z)-(.+)$ ]]; then
      key="${BASH_REMATCH[1]}-${BASH_REMATCH[2]}"
      module="${BASH_REMATCH[2]}"
      printf '%s|%s|%s\n' "$module" "$key" "$file" >>"$tmp_dirs"
      printf '%s\n' "$module" >>"$tmp_modules_dirs"
    fi
  done < <(find "$ARTIFACTS_DIR" -maxdepth 1 -mindepth 1 -type d -print 2>/dev/null)

  if [[ -s "$tmp_modules_json" ]]; then
    while IFS= read -r module; do
      [[ -z "$module" ]] && continue
      idx=0
      while IFS= read -r key; do
        [[ -z "$key" ]] && continue
        idx=$((idx + 1))
        if (( idx > KEEP_LATEST )); then
          file="$(awk -F'|' -v m="$module" -v k="$key" '$1==m && $2==k { print $3; exit }' "$tmp_json")"
          if [[ -n "$file" && -f "$file" ]]; then
            PRUNE_FILES+=("$file")
          fi
          file="$ARTIFACTS_DIR/$key.summary.md"
          if [[ -f "$file" ]]; then
            PRUNE_FILES+=("$file")
          fi
        fi
      done < <(awk -F'|' -v m="$module" '$1==m { print $2 }' "$tmp_json" | sort -r | uniq)
    done < <(sort -u "$tmp_modules_json")
  fi

  if [[ -s "$tmp_modules_dirs" ]]; then
    while IFS= read -r module; do
      [[ -z "$module" ]] && continue
      idx=0
      while IFS= read -r key; do
        [[ -z "$key" ]] && continue
        idx=$((idx + 1))
        if (( idx > KEEP_LATEST )); then
          file="$ARTIFACTS_DIR/$key"
          if [[ -d "$file" ]]; then
            PRUNE_DIRS+=("$file")
          fi
        fi
      done < <(awk -F'|' -v m="$module" '$1==m { print $2 }' "$tmp_dirs" | sort -r | uniq)
    done < <(sort -u "$tmp_modules_dirs")
  fi

  rm -f "$tmp_json" "$tmp_dirs" "$tmp_modules_json" "$tmp_modules_dirs"
}

apply_delete() {
  local item
  for item in "${PRUNE_FILES[@]}"; do
    if [[ -f "$item" ]]; then
      rm -f "$item"
    fi
  done
  for item in "${PRUNE_DIRS[@]}"; do
    if [[ -d "$item" ]]; then
      rm -rf "$item"
    fi
  done
}

write_summary_json() {
  local files_total dirs_total
  files_total="${#PRUNE_FILES[@]}"
  dirs_total="${#PRUNE_DIRS[@]}"
  {
    printf '{\n'
    printf '  "run_id": "%s",\n' "$(json_escape "$RUN_ID")"
    printf '  "started_at": "%s",\n' "$(json_escape "$STARTED_AT")"
    printf '  "finished_at": "%s",\n' "$(json_escape "$FINISHED_AT")"
    printf '  "status": "%s",\n' "$(json_escape "$STATUS")"
    printf '  "artifacts_dir": "%s",\n' "$(json_escape "$ARTIFACTS_DIR")"
    printf '  "keep_latest": %s,\n' "$KEEP_LATEST"
    printf '  "apply": %s,\n' "$APPLY_DELETE"
    printf '  "prune_files_count": %s,\n' "$files_total"
    printf '  "prune_dirs_count": %s,\n' "$dirs_total"
    printf '  "prune_files": [\n'
    local idx=0
    for item in "${PRUNE_FILES[@]}"; do
      idx=$((idx + 1))
      printf '    "%s"%s\n' "$(json_escape "$item")" "$([[ $idx -lt $files_total ]] && echo "," || true)"
    done
    printf '  ],\n'
    printf '  "prune_dirs": [\n'
    idx=0
    for item in "${PRUNE_DIRS[@]}"; do
      idx=$((idx + 1))
      printf '    "%s"%s\n' "$(json_escape "$item")" "$([[ $idx -lt $dirs_total ]] && echo "," || true)"
    done
    printf '  ]\n'
    printf '}\n'
  } >"$EMIT_JSON"
}

write_summary_md() {
  {
    printf '# AI Judge Artifact Prune\n\n'
    printf -- '- status: `%s`\n' "$STATUS"
    printf -- '- artifacts_dir: `%s`\n' "$ARTIFACTS_DIR"
    printf -- '- keep_latest: `%s`\n' "$KEEP_LATEST"
    printf -- '- apply: `%s`\n' "$APPLY_DELETE"
    printf -- '- prune_files_count: `%s`\n' "${#PRUNE_FILES[@]}"
    printf -- '- prune_dirs_count: `%s`\n' "${#PRUNE_DIRS[@]}"
    printf '\n## Prune Files\n\n'
    if [[ ${#PRUNE_FILES[@]} -eq 0 ]]; then
      printf -- '- （无）\n'
    else
      for item in "${PRUNE_FILES[@]}"; do
        printf -- '- `%s`\n' "$item"
      done
    fi
    printf '\n## Prune Dirs\n\n'
    if [[ ${#PRUNE_DIRS[@]} -eq 0 ]]; then
      printf -- '- （无）\n'
    else
      for item in "${PRUNE_DIRS[@]}"; do
        printf -- '- `%s`\n' "$item"
      done
    fi
  } >"$EMIT_MD"
}

main() {
  parse_args "$@"
  resolve_root

  if [[ -z "$ARTIFACTS_DIR" ]]; then
    ARTIFACTS_DIR="$ROOT/artifacts/harness"
  fi
  ARTIFACTS_DIR="$(abs_path "$ARTIFACTS_DIR")"

  if ! [[ "$KEEP_LATEST" =~ ^[0-9]+$ ]] || [[ "$KEEP_LATEST" -lt 1 ]]; then
    echo "keep-latest 必须是正整数: $KEEP_LATEST" >&2
    exit 2
  fi

  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ai-judge-artifact-prune"
  STARTED_AT="$(iso_now)"

  if [[ -z "$EMIT_JSON" ]]; then
    EMIT_JSON="$ARTIFACTS_DIR/${RUN_ID}.summary.json"
  fi
  if [[ -z "$EMIT_MD" ]]; then
    EMIT_MD="$ARTIFACTS_DIR/${RUN_ID}.summary.md"
  fi
  EMIT_JSON="$(abs_path "$EMIT_JSON")"
  EMIT_MD="$(abs_path "$EMIT_MD")"
  mkdir -p "$(dirname "$EMIT_JSON")" "$(dirname "$EMIT_MD")"

  collect_prune_candidates
  if [[ "$APPLY_DELETE" == "true" ]]; then
    apply_delete
    STATUS="pass_applied"
  else
    STATUS="pass_dry_run"
  fi

  FINISHED_AT="$(iso_now)"
  write_summary_json
  write_summary_md

  echo "ai_judge_artifact_prune_status: $STATUS"
  echo "artifacts_dir: $ARTIFACTS_DIR"
  echo "keep_latest: $KEEP_LATEST"
  echo "apply: $APPLY_DELETE"
  echo "prune_files_count: ${#PRUNE_FILES[@]}"
  echo "prune_dirs_count: ${#PRUNE_DIRS[@]}"
  echo "summary_json: $EMIT_JSON"
  echo "summary_md: $EMIT_MD"
}

main "$@"
