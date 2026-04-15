#!/usr/bin/env bash
set -euo pipefail

ROOT=""
PLAN_DOC=""
EMIT_JSON=""
EMIT_MD=""
RUN_ID=""
STARTED_AT=""
FINISHED_AT=""
STATUS="pass"

usage() {
  cat <<'USAGE'
用法:
  ai_judge_stage_closure_draft.sh \
    [--root <repo-root>] \
    [--plan-doc <path>] \
    [--emit-json <path>] \
    [--emit-md <path>]

说明:
  - 从当前开发计划提取 AI judge 阶段收口草案。
  - 输出 completed/todo 候选项，不直接改写 completed.md / todo.md。
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

slugify() {
  local value="$1"
  value="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')"
  value="$(printf '%s' "$value" | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')"
  printf '%s' "$value"
}

collect_ai_judge_rows() {
  local plan_file="$1"
  local out_file="$2"

  awk '
    function trim(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      return s
    }
    /^\|/ {
      line = $0
      n = split(line, parts, "|")
      if (n < 5) next
      c1 = trim(parts[2])
      c2 = trim(parts[3])
      c3 = trim(parts[4])
      c4 = trim(parts[5])
      if (c1 == "阶段" || c1 == "模块" || c1 == "---" || c1 == "") next
      gsub(/^`|`$/, "", c1)
      if (c1 !~ /^ai-judge-/) next
      print c1 "\t" c2 "\t" c3 "\t" c4
    }
  ' "$plan_file" >"$out_file"
}

collect_delayed_items() {
  local plan_file="$1"
  local out_file="$2"

  awk '
    BEGIN {
      in_section = 0
    }
    /^## 5\. 延后事项/ {
      in_section = 1
      next
    }
    in_section == 1 && /^## / {
      in_section = 0
    }
    in_section == 1 && /^### / {
      in_section = 0
    }
    in_section == 1 && /^[0-9]+\. / {
      line = $0
      sub(/^[0-9]+\.[[:space:]]*/, "", line)
      gsub(/[[:space:]]+$/, "", line)
      print line
    }
  ' "$plan_file" >"$out_file"
}

collect_next_step_items() {
  local plan_file="$1"
  local out_file="$2"

  awk '
    BEGIN {
      in_section = 0
    }
    /^### 下一开发模块建议/ {
      in_section = 1
      next
    }
    in_section == 1 && /^### / {
      in_section = 0
    }
    in_section == 1 && /^## / {
      in_section = 0
    }
    in_section == 1 && /^[0-9]+\. / {
      line = $0
      sub(/^[0-9]+\.[[:space:]]*/, "", line)
      gsub(/[[:space:]]+$/, "", line)
      print line
    }
  ' "$plan_file" >"$out_file"
}

build_completed_candidates() {
  local rows_file="$1"
  local out_file="$2"
  local module lane status note linked_todo

  while IFS=$'\t' read -r module lane status note; do
    [[ -z "${module:-}" ]] && continue
    if [[ "$status" != *"已完成"* ]]; then
      continue
    fi
    linked_todo="（待收口映射）"

    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$module" \
      "阶段收口草案：模块主体已完成（${status}）" \
      "artifacts/harness/*-${module}.summary.json（或执行增量）" \
      "见模块执行增量中的测试门禁记录" \
      "当前开发计划阶段收口草案（${RUN_ID}）" \
      "$linked_todo" >>"$out_file"
  done <"$rows_file"
}

build_todo_candidates() {
  local delayed_file="$1"
  local next_steps_file="$2"
  local out_file="$3"
  local idx=0
  local item debt_id

  while IFS= read -r item || [[ -n "$item" ]]; do
    item="$(trim "$item")"
    [[ -z "$item" ]] && continue
    idx=$((idx + 1))
    debt_id="ai-judge-stage-closure-deferred-$(printf '%02d' "$idx")"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$debt_id" \
      "ai-judge-stage-closure-draft" \
      "环境依赖" \
      "$item" \
      "获得真实环境或上线前收口" \
      "将该延后项转为可执行模块并产出证据" \
      "对应脚本或报告工件归档" >>"$out_file"
  done <"$delayed_file"

  while IFS= read -r item || [[ -n "$item" ]]; do
    item="$(trim "$item")"
    [[ -z "$item" ]] && continue
    if [[ "$item" != *"on-env"* ]]; then
      continue
    fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$item" \
      "ai-judge-stage-closure-draft" \
      "环境依赖" \
      "当前计划建议包含真实环境模块，需在环境窗口就绪后执行收口" \
      "REAL_CALIBRATION_ENV_READY=true 且具备可用真实样本后" \
      "完成该模块并产出 real-env 证据工件，状态达到 pass" \
      "执行对应模块脚本并归档 artifacts/harness 与 docs/loadtest/evidence" >>"$out_file"
  done <"$next_steps_file"
}

count_records() {
  local file="$1"
  if [[ ! -s "$file" ]]; then
    printf '0'
    return
  fi
  wc -l <"$file" | tr -d ' '
}

write_json() {
  local completed_file="$1"
  local todo_file="$2"

  local completed_total
  local todo_total
  completed_total="$(count_records "$completed_file")"
  todo_total="$(count_records "$todo_file")"

  {
    printf '{\n'
    printf '  "run_id": "%s",\n' "$(json_escape "$RUN_ID")"
    printf '  "root": "%s",\n' "$(json_escape "$ROOT")"
    printf '  "plan_doc": "%s",\n' "$(json_escape "$PLAN_DOC")"
    printf '  "status": "%s",\n' "$(json_escape "$STATUS")"
    printf '  "started_at": "%s",\n' "$(json_escape "$STARTED_AT")"
    printf '  "finished_at": "%s",\n' "$(json_escape "$FINISHED_AT")"
    printf '  "outputs": {\n'
    printf '    "json": "%s",\n' "$(json_escape "$EMIT_JSON")"
    printf '    "markdown": "%s"\n' "$(json_escape "$EMIT_MD")"
    printf '  },\n'
    printf '  "counts": {\n'
    printf '    "completed_candidates_total": %s,\n' "$completed_total"
    printf '    "todo_candidates_total": %s\n' "$todo_total"
    printf '  },\n'

    printf '  "completed_candidates": [\n'
    local first=1
    local module conclusion evidence verify source linked
    while IFS=$'\t' read -r module conclusion evidence verify source linked; do
      [[ -z "${module:-}" ]] && continue
      printf '    %s{"module":"%s","conclusion":"%s","code_evidence":"%s","verification":"%s","archive_source":"%s","linked_todo":"%s"}\n' \
        "$([[ "$first" -eq 1 ]] && echo "" || echo ",")" \
        "$(json_escape "$module")" \
        "$(json_escape "$conclusion")" \
        "$(json_escape "$evidence")" \
        "$(json_escape "$verify")" \
        "$(json_escape "$source")" \
        "$(json_escape "$linked")"
      first=0
    done <"$completed_file"
    printf '  ],\n'

    printf '  "todo_candidates": [\n'
    first=1
    local debt source_module debt_type reason trigger dod verify_way
    while IFS=$'\t' read -r debt source_module debt_type reason trigger dod verify_way; do
      [[ -z "${debt:-}" ]] && continue
      printf '    %s{"debt":"%s","source_module":"%s","debt_type":"%s","reason":"%s","trigger":"%s","dod":"%s","verify":"%s"}\n' \
        "$([[ "$first" -eq 1 ]] && echo "" || echo ",")" \
        "$(json_escape "$debt")" \
        "$(json_escape "$source_module")" \
        "$(json_escape "$debt_type")" \
        "$(json_escape "$reason")" \
        "$(json_escape "$trigger")" \
        "$(json_escape "$dod")" \
        "$(json_escape "$verify_way")"
      first=0
    done <"$todo_file"
    printf '  ]\n'
    printf '}\n'
  } >"$EMIT_JSON"
}

write_markdown() {
  local completed_file="$1"
  local todo_file="$2"

  local completed_total
  local todo_total
  completed_total="$(count_records "$completed_file")"
  todo_total="$(count_records "$todo_file")"

  {
    printf '# AI Judge Stage Closure Draft\n\n'
    printf -- '- run_id: `%s`\n' "$RUN_ID"
    printf -- '- status: `%s`\n' "$STATUS"
    printf -- '- started_at: `%s`\n' "$STARTED_AT"
    printf -- '- finished_at: `%s`\n' "$FINISHED_AT"
    printf -- '- plan_doc: `%s`\n' "$PLAN_DOC"
    printf -- '- completed_candidates_total: `%s`\n' "$completed_total"
    printf -- '- todo_candidates_total: `%s`\n' "$todo_total"
    printf '\n## completed.md Candidate Rows\n\n'
    printf '| 模块 | 结论 | 代码证据 | 验证结论 | 归档来源 | 关联待办 |\n'
    printf '|---|---|---|---|---|---|\n'
    local module conclusion evidence verify source linked
    while IFS=$'\t' read -r module conclusion evidence verify source linked; do
      [[ -z "${module:-}" ]] && continue
      printf '| %s | %s | %s | %s | %s | %s |\n' "$module" "$conclusion" "$evidence" "$verify" "$source" "$linked"
    done <"$completed_file"

    printf '\n## todo.md Candidate Rows\n\n'
    printf '| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |\n'
    printf '|---|---|---|---|---|---|---|\n'
    local debt source_module debt_type reason trigger dod verify_way
    while IFS=$'\t' read -r debt source_module debt_type reason trigger dod verify_way; do
      [[ -z "${debt:-}" ]] && continue
      printf '| %s | %s | %s | %s | %s | %s | %s |\n' "$debt" "$source_module" "$debt_type" "$reason" "$trigger" "$dod" "$verify_way"
    done <"$todo_file"

    printf '\n## Next Action\n\n'
    printf -- '1. 审核草案后，再按 `stage-closure` 流程写入 `docs/dev_plan/completed.md` 与 `docs/dev_plan/todo.md`。\n'
    printf -- '2. 写入完成后执行 `bash scripts/quality/harness_docs_lint.sh` 校验长期文档结构。\n'
  } >"$EMIT_MD"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --root)
        ROOT="$2"
        shift 2
        ;;
      --plan-doc)
        PLAN_DOC="$2"
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

  if [[ -z "$PLAN_DOC" ]]; then
    PLAN_DOC="$ROOT/docs/dev_plan/当前开发计划.md"
  else
    PLAN_DOC="$(abs_path "$PLAN_DOC")"
  fi

  if [[ ! -f "$PLAN_DOC" ]]; then
    echo "计划文档不存在: $PLAN_DOC" >&2
    exit 1
  fi

  STARTED_AT="$(iso_now)"
  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ai-judge-stage-closure-draft"

  if [[ -z "$EMIT_JSON" ]]; then
    EMIT_JSON="$ROOT/artifacts/harness/${RUN_ID}.summary.json"
  else
    EMIT_JSON="$(abs_path "$EMIT_JSON")"
  fi
  if [[ -z "$EMIT_MD" ]]; then
    EMIT_MD="$ROOT/artifacts/harness/${RUN_ID}.summary.md"
  else
    EMIT_MD="$(abs_path "$EMIT_MD")"
  fi
  ensure_parent_dir "$EMIT_JSON"
  ensure_parent_dir "$EMIT_MD"

  local matrix_rows_file delayed_file next_steps_file completed_file todo_file
  matrix_rows_file="$(mktemp)"
  delayed_file="$(mktemp)"
  next_steps_file="$(mktemp)"
  completed_file="$(mktemp)"
  todo_file="$(mktemp)"

  collect_ai_judge_rows "$PLAN_DOC" "$matrix_rows_file"
  collect_delayed_items "$PLAN_DOC" "$delayed_file"
  collect_next_step_items "$PLAN_DOC" "$next_steps_file"

  build_completed_candidates "$matrix_rows_file" "$completed_file"
  build_todo_candidates "$delayed_file" "$next_steps_file" "$todo_file"

  FINISHED_AT="$(iso_now)"
  write_json "$completed_file" "$todo_file"
  write_markdown "$completed_file" "$todo_file"

  echo "ai_judge_stage_closure_draft_status: $STATUS"
  echo "summary_json: $EMIT_JSON"
  echo "summary_md: $EMIT_MD"
  echo "completed_candidates_total: $(count_records "$completed_file")"
  echo "todo_candidates_total: $(count_records "$todo_file")"

  rm -f "$matrix_rows_file" "$delayed_file" "$next_steps_file" "$completed_file" "$todo_file"
}

main "$@"
