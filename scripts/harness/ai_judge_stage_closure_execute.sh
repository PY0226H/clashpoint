#!/usr/bin/env bash
set -euo pipefail

ROOT=""
PLAN_DOC=""
COMPLETED_DOC=""
TODO_DOC=""
ARCHIVE_DIR=""
EMIT_JSON=""
EMIT_MD=""
RUN_ID=""
STARTED_AT=""
FINISHED_AT=""
STATUS="pass"

usage() {
  cat <<'USAGE'
用法:
  ai_judge_stage_closure_execute.sh \
    [--root <repo-root>] \
    [--plan-doc <path>] \
    [--completed-doc <path>] \
    [--todo-doc <path>] \
    [--archive-dir <path>] \
    [--emit-json <path>] \
    [--emit-md <path>]

说明:
  - 执行 AI judge 阶段收口：
    1) 从当前活动计划提取已完成模块并写入 completed.md
    2) 将明确延后项写入 todo.md
    3) 归档当前活动计划并重置为下一轮模板
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

date_cn() {
  date -u +"%Y-%m-%d"
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

next_section_index() {
  local file="$1"
  local prefix="$2"
  local max

  max="$((
    $(awk -v p="$prefix" '
      BEGIN { max = 0 }
      $0 ~ /^### / {
        if (match($0, "^### " p "([0-9]+)\\.")) {
          value = substr($0, RSTART + 4 + length(p), RLENGTH - 5 - length(p))
          num = value + 0
          if (num > max) {
            max = num
          }
        }
      }
      END { print max }
    ' "$file")
  ))"

  printf '%s' "$((max + 1))"
}

collect_ai_judge_rows() {
  local plan_file="$1"
  local out_file="$2"

  awk '
    function trim(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      return s
    }
    BEGIN {
      in_matrix = 0
    }
    /^### 已完成\/未完成矩阵/ {
      in_matrix = 1
      next
    }
    in_matrix == 1 && /^### / {
      in_matrix = 0
    }
    in_matrix == 1 && /^## / {
      in_matrix = 0
    }
    in_matrix == 1 && /^\|/ {
      n = split($0, parts, "|")
      if (n < 5) next
      c1 = trim(parts[2])
      c2 = trim(parts[3])
      c3 = trim(parts[4])
      c4 = trim(parts[5])
      if (c1 == "阶段" || c1 == "---" || c1 == "") next
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

contains_completed_module() {
  local module="$1"
  grep -Fq -- "| ${module} |" "$COMPLETED_DOC"
}

contains_todo_debt() {
  local debt="$1"
  grep -Fq -- "| ${debt} |" "$TODO_DOC"
}

append_completed_section() {
  local rows_file="$1"
  local section_idx="$2"
  local out_file="$3"

  local appended=0
  local skipped=0
  local module lane status note linked_todo

  {
    printf '\n### B%s. AI Judge 平台化重构阶段收口（来源：当前开发计划）\n' "$section_idx"
    printf '| 模块 | 结论 | 代码证据 | 验证结论 | 归档来源 | 关联待办 |\n'
    printf '|---|---|---|---|---|---|\n'

    while IFS=$'\t' read -r module lane status note; do
      [[ -z "${module:-}" ]] && continue
      if [[ "$status" != *"已完成"* ]]; then
        continue
      fi
      if contains_completed_module "$module"; then
        skipped=$((skipped + 1))
        continue
      fi

      linked_todo="（待收口映射）"

      printf '| %s | %s | %s | %s | %s | %s |\n' \
        "$module" \
        "AI judge 平台化重构阶段主体已完成（${status}）" \
        "artifacts/harness/*-${module}.summary.json（或执行增量）" \
        "见当前开发计划执行增量中的门禁记录" \
        "AI_judge_service 平台化重构阶段收口（$(date_cn)）" \
        "$linked_todo"

      printf '%s\t%s\n' "$module" "appended" >>"$out_file"
      appended=$((appended + 1))
    done <"$rows_file"

    if [[ "$appended" -eq 0 ]]; then
      printf '| （无新增） | 当前模块均已归档或尚未达到完成态 | （无） | （无） | AI_judge_service 平台化重构阶段收口（%s） | （无） |\n' "$(date_cn)"
    fi
  } >>"$COMPLETED_DOC"

  printf '%s\t%s\n' "$appended" "$skipped" >>"$out_file"
}

append_todo_section() {
  local delayed_file="$1"
  local next_steps_file="$2"
  local section_idx="$3"
  local out_file="$4"

  local appended=0
  local skipped=0
  local idx=0
  local item debt

  {
    printf '\n### C%s. AI Judge 平台化重构阶段收口（来源：当前开发计划）\n' "$section_idx"
    printf '| 债务项 | 来源模块 | 债务类型 | 当前不做原因 | 触发时机 | 完成定义（DoD） | 验证方式 |\n'
    printf '|---|---|---|---|---|---|---|\n'

    while IFS= read -r item || [[ -n "$item" ]]; do
      item="$(trim "$item")"
      [[ -z "$item" ]] && continue
      idx=$((idx + 1))
      debt="ai-judge-stage-closure-deferred-$(printf '%02d' "$idx")"

      if contains_todo_debt "$debt"; then
        skipped=$((skipped + 1))
        continue
      fi

      printf '| %s | %s | %s | %s | %s | %s | %s |\n' \
        "$debt" \
        "ai-judge-stage-closure-execute" \
        "环境依赖" \
        "$item" \
        "获得真实环境或上线前收口" \
        "将该延后项转为可执行模块并产出证据" \
        "对应脚本或报告工件归档"

      printf '%s\t%s\n' "$debt" "appended" >>"$out_file"
      appended=$((appended + 1))
    done <"$delayed_file"

    while IFS= read -r item || [[ -n "$item" ]]; do
      item="$(trim "$item")"
      [[ -z "$item" ]] && continue
      if [[ "$item" != *"on-env"* && "$item" != *"real-env"* ]]; then
        continue
      fi
      debt="$item"
      if contains_todo_debt "$debt"; then
        skipped=$((skipped + 1))
        continue
      fi
      printf '| %s | %s | %s | %s | %s | %s | %s |\n' \
        "$debt" \
        "ai-judge-stage-closure-execute" \
        "环境依赖" \
        "当前计划建议包含真实环境模块，需在环境窗口就绪后执行收口" \
        "REAL_CALIBRATION_ENV_READY=true 且具备可用真实样本后" \
        "完成该模块并产出 real-env 证据工件，状态达到 pass" \
        "执行对应模块脚本并归档 artifacts/harness 与 docs/loadtest/evidence"
      printf '%s\t%s\n' "$debt" "appended" >>"$out_file"
      appended=$((appended + 1))
    done <"$next_steps_file"

    if [[ "$appended" -eq 0 ]]; then
      printf '| （无新增） | 当前延后项已写入技术债池 | （无） | （无） | （无） | （无） | （无） |\n'
    fi
  } >>"$TODO_DOC"

  printf '%s\t%s\n' "$appended" "$skipped" >>"$out_file"
}

reset_plan_doc() {
  local archive_path="$1"

  cat >"$PLAN_DOC" <<PLAN
# 当前开发计划

关联 slot：\`default\`  
更新时间：$(date_cn)  
当前主线：\`AI_judge_service 下一阶段（待规划）\`  
当前状态：阶段收口后待下一轮

---

## 1. 计划定位

1. 本文档已由阶段收口流程重置，用于承接下一轮活动计划。
2. 本轮完整执行细节已归档到：\`$archive_path\`。
3. 长期沉淀已同步到：\`docs/dev_plan/completed.md\` 与 \`docs/dev_plan/todo.md\`。

---

### 已完成/未完成矩阵

| 阶段 | 目标 | 状态 | 说明 |
| --- | --- | --- | --- |
| \`ai-judge-stage-closure-execute\` | AI judge 当前阶段收口执行 | 已完成 | 活动计划已归档并重置，长期文档已同步 |

### 下一开发模块建议

1. ai-judge-next-iteration-planning
2. ai-judge-runtime-ops-pack（phase2：与 stage closure 联动自动回填）

### 模块完成同步历史

- $(date_cn)：推进 \`ai-judge-stage-closure-execute\`；完成阶段收口：completed/todo 同步、活动计划归档并重置。
PLAN
}

write_json() {
  local archive_path="$1"
  local completed_stats="$2"
  local todo_stats="$3"

  local completed_appended completed_skipped
  local todo_appended todo_skipped

  completed_appended="$(printf '%s' "$completed_stats" | awk -F '\t' '{print $1}')"
  completed_skipped="$(printf '%s' "$completed_stats" | awk -F '\t' '{print $2}')"
  todo_appended="$(printf '%s' "$todo_stats" | awk -F '\t' '{print $1}')"
  todo_skipped="$(printf '%s' "$todo_stats" | awk -F '\t' '{print $2}')"

  {
    printf '{\n'
    printf '  "run_id": "%s",\n' "$(json_escape "$RUN_ID")"
    printf '  "status": "%s",\n' "$(json_escape "$STATUS")"
    printf '  "root": "%s",\n' "$(json_escape "$ROOT")"
    printf '  "plan_doc": "%s",\n' "$(json_escape "$PLAN_DOC")"
    printf '  "completed_doc": "%s",\n' "$(json_escape "$COMPLETED_DOC")"
    printf '  "todo_doc": "%s",\n' "$(json_escape "$TODO_DOC")"
    printf '  "archive_path": "%s",\n' "$(json_escape "$archive_path")"
    printf '  "started_at": "%s",\n' "$(json_escape "$STARTED_AT")"
    printf '  "finished_at": "%s",\n' "$(json_escape "$FINISHED_AT")"
    printf '  "outputs": {\n'
    printf '    "json": "%s",\n' "$(json_escape "$EMIT_JSON")"
    printf '    "markdown": "%s"\n' "$(json_escape "$EMIT_MD")"
    printf '  },\n'
    printf '  "counts": {\n'
    printf '    "completed_appended": %s,\n' "$completed_appended"
    printf '    "completed_skipped_existing": %s,\n' "$completed_skipped"
    printf '    "todo_appended": %s,\n' "$todo_appended"
    printf '    "todo_skipped_existing": %s\n' "$todo_skipped"
    printf '  }\n'
    printf '}\n'
  } >"$EMIT_JSON"
}

write_markdown() {
  local archive_path="$1"
  local completed_stats="$2"
  local todo_stats="$3"

  local completed_appended completed_skipped
  local todo_appended todo_skipped

  completed_appended="$(printf '%s' "$completed_stats" | awk -F '\t' '{print $1}')"
  completed_skipped="$(printf '%s' "$completed_stats" | awk -F '\t' '{print $2}')"
  todo_appended="$(printf '%s' "$todo_stats" | awk -F '\t' '{print $1}')"
  todo_skipped="$(printf '%s' "$todo_stats" | awk -F '\t' '{print $2}')"

  {
    printf '# AI Judge Stage Closure Execute\n\n'
    printf -- '- run_id: `%s`\n' "$RUN_ID"
    printf -- '- status: `%s`\n' "$STATUS"
    printf -- '- started_at: `%s`\n' "$STARTED_AT"
    printf -- '- finished_at: `%s`\n' "$FINISHED_AT"
    printf -- '- plan_doc: `%s`\n' "$PLAN_DOC"
    printf -- '- completed_doc: `%s`\n' "$COMPLETED_DOC"
    printf -- '- todo_doc: `%s`\n' "$TODO_DOC"
    printf -- '- archive_path: `%s`\n' "$archive_path"
    printf -- '- completed_appended: `%s`\n' "$completed_appended"
    printf -- '- completed_skipped_existing: `%s`\n' "$completed_skipped"
    printf -- '- todo_appended: `%s`\n' "$todo_appended"
    printf -- '- todo_skipped_existing: `%s`\n' "$todo_skipped"
    printf '\n## Summary\n\n'
    printf -- '1. 已将 AI judge 完成态模块追加到 `completed.md`。\n'
    printf -- '2. 已将阶段延后项与环境阻塞项追加到 `todo.md`。\n'
    printf -- '3. 已归档并重置活动计划文档。\n'
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
      --completed-doc)
        COMPLETED_DOC="$2"
        shift 2
        ;;
      --todo-doc)
        TODO_DOC="$2"
        shift 2
        ;;
      --archive-dir)
        ARCHIVE_DIR="$2"
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
  if [[ -z "$COMPLETED_DOC" ]]; then
    COMPLETED_DOC="$ROOT/docs/dev_plan/completed.md"
  else
    COMPLETED_DOC="$(abs_path "$COMPLETED_DOC")"
  fi
  if [[ -z "$TODO_DOC" ]]; then
    TODO_DOC="$ROOT/docs/dev_plan/todo.md"
  else
    TODO_DOC="$(abs_path "$TODO_DOC")"
  fi
  if [[ -z "$ARCHIVE_DIR" ]]; then
    ARCHIVE_DIR="$ROOT/docs/dev_plan/archive"
  else
    ARCHIVE_DIR="$(abs_path "$ARCHIVE_DIR")"
  fi

  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ai-judge-stage-closure-execute"
  STARTED_AT="$(iso_now)"

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

  [[ -f "$PLAN_DOC" ]] || { echo "计划文档不存在: $PLAN_DOC" >&2; exit 1; }
  [[ -f "$COMPLETED_DOC" ]] || { echo "completed 文档不存在: $COMPLETED_DOC" >&2; exit 1; }
  [[ -f "$TODO_DOC" ]] || { echo "todo 文档不存在: $TODO_DOC" >&2; exit 1; }

  mkdir -p "$ARCHIVE_DIR"
  local archive_path
  archive_path="$ARCHIVE_DIR/${RUN_ID}.md"
  cp "$PLAN_DOC" "$archive_path"

  local rows_file delayed_file next_steps_file completed_meta todo_meta
  rows_file="$(mktemp)"
  delayed_file="$(mktemp)"
  next_steps_file="$(mktemp)"
  completed_meta="$(mktemp)"
  todo_meta="$(mktemp)"

  collect_ai_judge_rows "$PLAN_DOC" "$rows_file"
  collect_delayed_items "$PLAN_DOC" "$delayed_file"
  collect_next_step_items "$PLAN_DOC" "$next_steps_file"

  local completed_section_idx todo_section_idx
  completed_section_idx="$(next_section_index "$COMPLETED_DOC" "B")"
  todo_section_idx="$(next_section_index "$TODO_DOC" "C")"

  append_completed_section "$rows_file" "$completed_section_idx" "$completed_meta"
  append_todo_section "$delayed_file" "$next_steps_file" "$todo_section_idx" "$todo_meta"

  reset_plan_doc "$archive_path"

  FINISHED_AT="$(iso_now)"

  local completed_stats todo_stats
  completed_stats="$(tail -n 1 "$completed_meta" || echo '0\t0')"
  todo_stats="$(tail -n 1 "$todo_meta" || echo '0\t0')"

  write_json "$archive_path" "$completed_stats" "$todo_stats"
  write_markdown "$archive_path" "$completed_stats" "$todo_stats"

  echo "ai_judge_stage_closure_execute_status: $STATUS"
  echo "summary_json: $EMIT_JSON"
  echo "summary_md: $EMIT_MD"
  echo "archive_path: $archive_path"

  rm -f "$rows_file" "$delayed_file" "$next_steps_file" "$completed_meta" "$todo_meta"
}

main "$@"
