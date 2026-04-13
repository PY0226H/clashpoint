#!/usr/bin/env bash
set -euo pipefail

ROOT=""
ARTIFACTS_DIR=""
EMIT_JSON=""
EMIT_MD=""
RUN_ID=""
STARTED_AT=""
FINISHED_AT=""
STATUS="pass"

declare -a REQUIRED_MODULES=(
  "ai-judge-p2-judge-mainline-migration"
  "ai-judge-p2-phase-mainline-migration"
  "ai-judge-p3-replay-audit-ops-convergence"
  "ai-judge-p4-agent-runtime-shell"
  "ai-judge-runtime-verify-closure"
)

usage() {
  cat <<'USAGE'
用法:
  ai_judge_evidence_closure.sh \
    [--root <repo-root>] \
    [--artifacts-dir <path>] \
    [--emit-json <path>] \
    [--emit-md <path>]

说明:
  - 收口 ai_judge P2/P3/P4 模块证据，输出统一 JSON/Markdown 摘要。
  - 默认在 artifacts/harness 中查找 `*.summary.json` 证据文件。
USAGE
}

trim() {
  local value="${1:-}"
  value="${value#${value%%[![:space:]]*}}"
  value="${value%${value##*[![:space:]]}}"
  printf '%s' "$value"
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

iso_now() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
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
  elif [[ "$path" = /* ]]; then
    printf '%s' "$path"
  else
    printf '%s' "$ROOT/$path"
  fi
}

ensure_parent_dir() {
  local path="$1"
  mkdir -p "$(dirname "$path")"
}

init_run() {
  local ts
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  RUN_ID="${ts}-ai-judge-p2p3p4-evidence-closure"
  STARTED_AT="$(iso_now)"

  if [[ -z "$ARTIFACTS_DIR" ]]; then
    ARTIFACTS_DIR="$ROOT/artifacts/harness"
  else
    ARTIFACTS_DIR="$(abs_path "$ARTIFACTS_DIR")"
  fi
  mkdir -p "$ARTIFACTS_DIR"

  if [[ -z "$EMIT_JSON" ]]; then
    EMIT_JSON="$ARTIFACTS_DIR/${RUN_ID}.summary.json"
  else
    EMIT_JSON="$(abs_path "$EMIT_JSON")"
  fi
  if [[ -z "$EMIT_MD" ]]; then
    EMIT_MD="$ARTIFACTS_DIR/${RUN_ID}.summary.md"
  else
    EMIT_MD="$(abs_path "$EMIT_MD")"
  fi

  ensure_parent_dir "$EMIT_JSON"
  ensure_parent_dir "$EMIT_MD"
}

collect_latest_summary_json() {
  local module="$1"
  local latest=""
  local file
  while IFS= read -r file; do
    latest="$file"
    break
  done < <(find "$ARTIFACTS_DIR" -maxdepth 1 -type f -name "*-${module}.summary.json" -print 2>/dev/null | sort -r)
  printf '%s' "$latest"
}

build_result_files() {
  local modules_file="$1"
  local missing_file="$2"
  local covered=0
  local missing=0
  local module summary_json summary_md status note

  for module in "${REQUIRED_MODULES[@]}"; do
    summary_json="$(collect_latest_summary_json "$module")"
    summary_md=""
    status="pass"
    note="模块证据已找到"

    if [[ -z "$summary_json" ]]; then
      status="evidence_missing"
      note="缺少模块 summary.json 证据"
      summary_json="（缺失）"
      summary_md="（缺失）"
    else
      summary_md="${summary_json%.summary.json}.summary.md"
      if [[ ! -f "$summary_md" ]]; then
        status="evidence_missing"
        note="summary.json 已找到，但缺少同 run 的 summary.md"
        summary_md="（缺失）"
      fi
    fi

    if [[ "$status" == "pass" ]]; then
      covered=$((covered + 1))
    else
      missing=$((missing + 1))
      printf '%s\n' "$module" >>"$missing_file"
    fi

    printf '%s\t%s\t%s\t%s\t%s\n' \
      "$module" \
      "$status" \
      "$summary_json" \
      "$summary_md" \
      "$note" >>"$modules_file"
  done

  if [[ "$missing" -gt 0 ]]; then
    STATUS="evidence_missing"
  fi
}

write_json() {
  local modules_file="$1"
  local missing_file="$2"
  local total=0
  local covered=0
  local missing=0
  local module status summary_json summary_md note

  while IFS=$'\t' read -r module status summary_json summary_md note; do
    [[ -z "${module:-}" ]] && continue
    total=$((total + 1))
    if [[ "$status" == "pass" ]]; then
      covered=$((covered + 1))
    else
      missing=$((missing + 1))
    fi
  done <"$modules_file"

  FINISHED_AT="$(iso_now)"

  {
    printf '{\n'
    printf '  "run_id": "%s",\n' "$(json_escape "$RUN_ID")"
    printf '  "root": "%s",\n' "$(json_escape "$ROOT")"
    printf '  "artifacts_dir": "%s",\n' "$(json_escape "$ARTIFACTS_DIR")"
    printf '  "status": "%s",\n' "$(json_escape "$STATUS")"
    printf '  "started_at": "%s",\n' "$(json_escape "$STARTED_AT")"
    printf '  "finished_at": "%s",\n' "$(json_escape "$FINISHED_AT")"
    printf '  "outputs": {\n'
    printf '    "json": "%s",\n' "$(json_escape "$EMIT_JSON")"
    printf '    "markdown": "%s"\n' "$(json_escape "$EMIT_MD")"
    printf '  },\n'
    printf '  "counts": {\n'
    printf '    "required_total": %s,\n' "$total"
    printf '    "covered_total": %s,\n' "$covered"
    printf '    "missing_total": %s\n' "$missing"
    printf '  },\n'
    printf '  "required_modules": ['
    local idx=0
    local required
    for required in "${REQUIRED_MODULES[@]}"; do
      if [[ "$idx" -gt 0 ]]; then
        printf ','
      fi
      printf '"%s"' "$(json_escape "$required")"
      idx=$((idx + 1))
    done
    printf '],\n'
    printf '  "modules": [\n'
    local first=1
    while IFS=$'\t' read -r module status summary_json summary_md note; do
      [[ -z "${module:-}" ]] && continue
      printf '    %s{"module":"%s","status":"%s","summary_json":"%s","summary_md":"%s","note":"%s"}\n' \
        "$([[ "$first" -eq 1 ]] && echo "" || echo ",")" \
        "$(json_escape "$module")" \
        "$(json_escape "$status")" \
        "$(json_escape "$summary_json")" \
        "$(json_escape "$summary_md")" \
        "$(json_escape "$note")"
      first=0
    done <"$modules_file"
    printf '  ],\n'
    printf '  "missing_modules": ['
    first=1
    while IFS= read -r module; do
      module="$(trim "$module")"
      [[ -z "$module" ]] && continue
      printf '%s"%s"' "$([[ "$first" -eq 1 ]] && echo "" || echo ",")" "$(json_escape "$module")"
      first=0
    done <"$missing_file"
    printf ']\n'
    printf '}\n'
  } >"$EMIT_JSON"
}

write_markdown() {
  local modules_file="$1"
  local missing_file="$2"

  {
    printf '# AI Judge Evidence Closure Summary\n\n'
    printf -- '- run_id: `%s`\n' "$RUN_ID"
    printf -- '- status: `%s`\n' "$STATUS"
    printf -- '- started_at: `%s`\n' "$STARTED_AT"
    printf -- '- finished_at: `%s`\n' "$FINISHED_AT"
    printf -- '- artifacts_dir: `%s`\n' "$ARTIFACTS_DIR"
    printf -- '- output_json: `%s`\n' "$EMIT_JSON"
    printf -- '- output_md: `%s`\n' "$EMIT_MD"
    printf '\n## Module Coverage\n\n'
    printf '| Module | Status | Summary JSON | Summary MD | Note |\n'
    printf '|---|---|---|---|---|\n'
    local module status summary_json summary_md note
    while IFS=$'\t' read -r module status summary_json summary_md note; do
      [[ -z "${module:-}" ]] && continue
      printf '| %s | %s | %s | %s | %s |\n' \
        "$module" \
        "$status" \
        "$summary_json" \
        "$summary_md" \
        "$note"
    done <"$modules_file"

    printf '\n## Missing Modules\n\n'
    local has_missing=0
    while IFS= read -r module; do
      module="$(trim "$module")"
      [[ -z "$module" ]] && continue
      has_missing=1
      printf -- '- %s\n' "$module"
    done <"$missing_file"
    if [[ "$has_missing" -eq 0 ]]; then
      printf -- '- （无）\n'
    fi
  } >"$EMIT_MD"
}

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
      usage >&2
      exit 2
      ;;
  esac
done

resolve_root
ROOT="$(abs_path "$ROOT")"
init_run

modules_file="$(mktemp)"
missing_file="$(mktemp)"
trap 'rm -f "$modules_file" "$missing_file"' EXIT

build_result_files "$modules_file" "$missing_file"
write_json "$modules_file" "$missing_file"
write_markdown "$modules_file" "$missing_file"

printf 'ai_judge_evidence_status: %s\n' "$STATUS"
printf 'ai_judge_evidence_json: %s\n' "$EMIT_JSON"
printf 'ai_judge_evidence_md: %s\n' "$EMIT_MD"
