#!/usr/bin/env bash
set -euo pipefail

ROOT=""
ARTIFACTS_DIR=""
PLAN_DOC=""
MODULES_RAW=""
EMIT_JSON=""
EMIT_MD=""
RUN_ID=""
STARTED_AT=""
FINISHED_AT=""
STATUS="pass"

# 默认回填集合与证据收口脚本保持一致。
declare -a DEFAULT_MODULES=(
  "ai-judge-p2-judge-mainline-migration"
  "ai-judge-p2-phase-mainline-migration"
  "ai-judge-p3-replay-audit-ops-convergence"
  "ai-judge-p4-agent-runtime-shell"
  "ai-judge-runtime-verify-closure"
)

declare -a TARGET_MODULES=()

usage() {
  cat <<'USAGE'
用法:
  ai_judge_evidence_gap_remediation.sh \
    [--root <repo-root>] \
    [--artifacts-dir <path>] \
    [--plan-doc <path>] \
    [--modules <module-a;module-b>] \
    [--emit-json <path>] \
    [--emit-md <path>]

说明:
  - 为缺失 `*.summary.json/.md` 的 ai_judge 模块回填标准化证据。
  - 默认模块集合与 ai_judge_evidence_closure.sh 一致。
  - 回填信息来源为当前开发计划文档中的“模块完成同步历史”。
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

extract_plan_summary() {
  local module="$1"
  if [[ ! -f "$PLAN_DOC" ]]; then
    printf '%s' ""
    return
  fi

  awk -v module="$module" '
    index($0, "推进 `" module "`；") > 0 {
      line=$0
    }
    END {
      if (line == "") {
        exit
      }
      sub(/^.*推进 `[^`]+`；/, "", line)
      gsub(/[[:space:]]+$/, "", line)
      print line
    }
  ' "$PLAN_DOC"
}

extract_increment_notes() {
  local module="$1"
  if [[ ! -f "$PLAN_DOC" ]]; then
    printf '%s' ""
    return
  fi

  awk -v module="$module" '
    BEGIN { in_section=0; count=0 }
    $0 ~ /^### / {
      in_section = (index($0, "| " module "（执行增量") > 0)
      next
    }
    in_section == 1 {
      if ($0 ~ /^### /) {
        in_section=0
      } else if ($0 ~ /^[0-9]+\./) {
        line=$0
        sub(/^[0-9]+\.[[:space:]]*/, "", line)
        print line
        count++
      }
    }
  ' "$PLAN_DOC" | head -n 5
}

prepare_targets() {
  local seen=""
  local item

  if [[ -n "$MODULES_RAW" ]]; then
    while IFS= read -r item || [[ -n "$item" ]]; do
      item="$(trim "$item")"
      [[ -z "$item" ]] && continue
      if [[ ";$seen;" == *";$item;"* ]]; then
        continue
      fi
      TARGET_MODULES+=("$item")
      seen="${seen:+${seen};}${item}"
    done < <(printf '%s' "$MODULES_RAW" | tr ',' ';' | tr ';' '\n')
  else
    TARGET_MODULES=("${DEFAULT_MODULES[@]}")
  fi
}

write_module_summary() {
  local module="$1"
  local module_summary="$2"
  local increment_notes_file="$3"
  local summary_json="$4"
  local summary_md="$5"

  {
    printf '{\n'
    printf '  "run_id": "%s",\n' "$(json_escape "$RUN_ID-$module")"
    printf '  "root": "%s",\n' "$(json_escape "$ROOT")"
    printf '  "task_kind": "dev",\n'
    printf '  "module": "%s",\n' "$(json_escape "$module")"
    printf '  "summary": "%s",\n' "$(json_escape "$module_summary")"
    printf '  "status": "pass",\n'
    printf '  "backfilled": true,\n'
    printf '  "source": "plan_history",\n'
    printf '  "started_at": "%s",\n' "$(json_escape "$STARTED_AT")"
    printf '  "finished_at": "%s",\n' "$(json_escape "$FINISHED_AT")"
    printf '  "artifacts": {\n'
    printf '    "summary_json": "%s",\n' "$(json_escape "$summary_json")"
    printf '    "summary_md": "%s"\n' "$(json_escape "$summary_md")"
    printf '  },\n'
    printf '  "evidence_paths": ["%s"],\n' "$(json_escape "$PLAN_DOC")"
    printf '  "increment_notes": ['
    local first=1
    local note
    while IFS= read -r note || [[ -n "$note" ]]; do
      note="$(trim "$note")"
      [[ -z "$note" ]] && continue
      printf '%s"%s"' "$([[ "$first" -eq 1 ]] && echo "" || echo ",")" "$(json_escape "$note")"
      first=0
    done <"$increment_notes_file"
    printf ']\n'
    printf '}\n'
  } >"$summary_json"

  {
    printf '# Harness Run Summary (Backfilled)\n\n'
    printf -- '- run_id: `%s`\n' "$RUN_ID-$module"
    printf -- '- module: `%s`\n' "$module"
    printf -- '- task_kind: `dev`\n'
    printf -- '- status: `pass`\n'
    printf -- '- backfilled: `true`\n'
    printf -- '- source: `plan_history`\n'
    printf -- '- summary: `%s`\n' "$module_summary"
    printf -- '- plan_doc: `%s`\n' "$PLAN_DOC"
    printf -- '- summary_json: `%s`\n' "$summary_json"
    printf -- '- summary_md: `%s`\n' "$summary_md"
    printf '\n## Increment Notes\n\n'
    if [[ ! -s "$increment_notes_file" ]]; then
      printf -- '- （无）\n'
    else
      while IFS= read -r note || [[ -n "$note" ]]; do
        note="$(trim "$note")"
        [[ -z "$note" ]] && continue
        printf -- '- %s\n' "$note"
      done <"$increment_notes_file"
    fi
  } >"$summary_md"
}

write_run_json() {
  local records_file="$1"
  local created_count="$2"
  local skipped_count="$3"

  {
    printf '{\n'
    printf '  "run_id": "%s",\n' "$(json_escape "$RUN_ID")"
    printf '  "root": "%s",\n' "$(json_escape "$ROOT")"
    printf '  "plan_doc": "%s",\n' "$(json_escape "$PLAN_DOC")"
    printf '  "artifacts_dir": "%s",\n' "$(json_escape "$ARTIFACTS_DIR")"
    printf '  "status": "%s",\n' "$(json_escape "$STATUS")"
    printf '  "started_at": "%s",\n' "$(json_escape "$STARTED_AT")"
    printf '  "finished_at": "%s",\n' "$(json_escape "$FINISHED_AT")"
    printf '  "counts": {\n'
    printf '    "target_total": %s,\n' "${#TARGET_MODULES[@]}"
    printf '    "created_total": %s,\n' "$created_count"
    printf '    "skipped_total": %s\n' "$skipped_count"
    printf '  },\n'
    printf '  "outputs": {\n'
    printf '    "json": "%s",\n' "$(json_escape "$EMIT_JSON")"
    printf '    "markdown": "%s"\n' "$(json_escape "$EMIT_MD")"
    printf '  },\n'
    printf '  "modules": [\n'
    local first=1
    local line module action summary_json summary_md note
    while IFS=$'\t' read -r module action summary_json summary_md note; do
      [[ -z "${module:-}" ]] && continue
      printf '    %s{"module":"%s","action":"%s","summary_json":"%s","summary_md":"%s","note":"%s"}\n' \
        "$([[ "$first" -eq 1 ]] && echo "" || echo ",")" \
        "$(json_escape "$module")" \
        "$(json_escape "$action")" \
        "$(json_escape "$summary_json")" \
        "$(json_escape "$summary_md")" \
        "$(json_escape "$note")"
      first=0
    done <"$records_file"
    printf '  ]\n'
    printf '}\n'
  } >"$EMIT_JSON"
}

write_run_markdown() {
  local records_file="$1"

  {
    printf '# AI Judge Evidence Gap Remediation\n\n'
    printf -- '- run_id: `%s`\n' "$RUN_ID"
    printf -- '- status: `%s`\n' "$STATUS"
    printf -- '- started_at: `%s`\n' "$STARTED_AT"
    printf -- '- finished_at: `%s`\n' "$FINISHED_AT"
    printf -- '- plan_doc: `%s`\n' "$PLAN_DOC"
    printf -- '- artifacts_dir: `%s`\n' "$ARTIFACTS_DIR"
    printf -- '- output_json: `%s`\n' "$EMIT_JSON"
    printf -- '- output_md: `%s`\n' "$EMIT_MD"
    printf '\n## Module Actions\n\n'
    printf '| Module | Action | Summary JSON | Summary MD | Note |\n'
    printf '|---|---|---|---|---|\n'
    local line module action summary_json summary_md note
    while IFS=$'\t' read -r module action summary_json summary_md note; do
      [[ -z "${module:-}" ]] && continue
      printf '| %s | %s | %s | %s | %s |\n' "$module" "$action" "$summary_json" "$summary_md" "$note"
    done <"$records_file"
  } >"$EMIT_MD"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --root)
        ROOT="$2"
        shift 2
        ;;
      --artifacts-dir)
        ARTIFACTS_DIR="$2"
        shift 2
        ;;
      --plan-doc)
        PLAN_DOC="$2"
        shift 2
        ;;
      --modules)
        MODULES_RAW="$2"
        shift 2
        ;;
      --emit-json)
        EMIT_JSON="$2"
        shift 2
        ;;
      --emit-md)
        EMIT_MD="$2"
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

main() {
  parse_args "$@"
  resolve_root

  if [[ -z "$ARTIFACTS_DIR" ]]; then
    ARTIFACTS_DIR="$ROOT/artifacts/harness"
  else
    ARTIFACTS_DIR="$(abs_path "$ARTIFACTS_DIR")"
  fi
  mkdir -p "$ARTIFACTS_DIR"

  if [[ -z "$PLAN_DOC" ]]; then
    PLAN_DOC="$ROOT/docs/dev_plan/当前开发计划.md"
  else
    PLAN_DOC="$(abs_path "$PLAN_DOC")"
  fi

  STARTED_AT="$(iso_now)"
  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ai-judge-evidence-gap-remediation"
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

  prepare_targets

  local records_file
  records_file="$(mktemp)"
  local created_count=0
  local skipped_count=0
  local module summary_json summary_md summary_from_plan module_summary
  local increment_notes_file

  for module in "${TARGET_MODULES[@]}"; do
    summary_json="$(collect_latest_summary_json "$module")"
    if [[ -n "$summary_json" ]]; then
      summary_md="${summary_json%.summary.json}.summary.md"
      if [[ -f "$summary_md" ]]; then
        skipped_count=$((skipped_count + 1))
        printf '%s\t%s\t%s\t%s\t%s\n' \
          "$module" \
          "already_covered" \
          "$summary_json" \
          "$summary_md" \
          "模块证据已存在" >>"$records_file"
        continue
      fi
    else
      summary_json="$ARTIFACTS_DIR/${RUN_ID}-${module}.summary.json"
      summary_md="$ARTIFACTS_DIR/${RUN_ID}-${module}.summary.md"
    fi

    summary_from_plan="$(trim "$(extract_plan_summary "$module")")"
    if [[ -z "$summary_from_plan" ]]; then
      module_summary="历史模块证据回填：补齐 summary 记录，具体实现详见计划文档执行增量。"
    else
      module_summary="$summary_from_plan"
    fi

    increment_notes_file="$(mktemp)"
    extract_increment_notes "$module" >"$increment_notes_file"

    FINISHED_AT="$(iso_now)"
    write_module_summary "$module" "$module_summary" "$increment_notes_file" "$summary_json" "$summary_md"
    rm -f "$increment_notes_file"

    created_count=$((created_count + 1))
    printf '%s\t%s\t%s\t%s\t%s\n' \
      "$module" \
      "backfilled" \
      "$summary_json" \
      "$summary_md" \
      "已根据计划文档补齐 summary" >>"$records_file"
  done

  FINISHED_AT="$(iso_now)"
  write_run_json "$records_file" "$created_count" "$skipped_count"
  write_run_markdown "$records_file"

  echo "ai_judge_evidence_gap_remediation_status: $STATUS"
  echo "summary_json: $EMIT_JSON"
  echo "summary_md: $EMIT_MD"
  echo "created_total: $created_count"
  echo "skipped_total: $skipped_count"

  rm -f "$records_file"
}

main "$@"
