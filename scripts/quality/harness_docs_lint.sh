#!/usr/bin/env bash
set -euo pipefail

ROOT=""
JSON_OUT=""
MD_OUT=""

usage() {
  cat <<'USAGE'
用法:
  harness_docs_lint.sh \
    [--root <repo-root>] \
    [--json-out <report.json>] \
    [--md-out <report.md>]

说明:
  - 检查 EchoIsle harness 文档与计划文档的首版结构约束。
  - 默认输出 markdown 摘要到 stdout。
  - 如未显式指定输出路径，会自动在 /tmp 下生成 json + markdown 报告文件。
USAGE
}

trim() {
  local v="$1"
  v="${v#${v%%[![:space:]]*}}"
  v="${v%${v##*[![:space:]]}}"
  printf '%s' "$v"
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

resolve_path() {
  local path="$1"
  if [[ -z "$path" ]]; then
    echo ""
  elif [[ "$path" = /* ]]; then
    echo "$path"
  else
    echo "$ROOT/$path"
  fi
}

ensure_parent_dir() {
  local path="$1"
  mkdir -p "$(dirname "$path")"
}

first_nonblank_line() {
  local file="$1"
  awk 'NF {print; exit}' "$file" 2>/dev/null || true
}

add_issue() {
  local severity="$1"
  local code="$2"
  local target="$3"
  local message="$4"
  printf '%s\t%s\t%s\t%s\n' "$severity" "$code" "$target" "$message" >>"$FINDINGS_FILE"
}

add_check() {
  local name="$1"
  printf '%s\n' "$name" >>"$CHECKS_FILE"
}

has_literal() {
  local file="$1"
  local text="$2"
  grep -Fq -- "$text" "$file"
}

has_regex() {
  local file="$1"
  local pattern="$2"
  grep -Eq -- "$pattern" "$file"
}

check_required_literal() {
  local file="$1"
  local text="$2"
  local severity="$3"
  local code="$4"
  local message="$5"
  if ! has_literal "$file" "$text"; then
    add_issue "$severity" "$code" "$file" "$message"
  fi
}

check_required_regex() {
  local file="$1"
  local pattern="$2"
  local severity="$3"
  local code="$4"
  local message="$5"
  if ! has_regex "$file" "$pattern"; then
    add_issue "$severity" "$code" "$file" "$message"
  fi
}

check_harness_doc() {
  local file="$1"
  add_check "harness-doc:$file"
  check_required_regex "$file" '^# .+' "error" "harness_doc_missing_h1" "缺少一级标题。"
  check_required_literal "$file" '更新时间：' "error" "harness_doc_missing_updated_at" "缺少“更新时间：”字段。"
  check_required_literal "$file" '状态：' "error" "harness_doc_missing_status" "缺少“状态：”字段。"

  if has_literal "$file" '.codex/current-plan.txt'; then
    add_issue "error" "legacy_current_plan_pointer" "$file" "仍引用已废弃的 .codex/current-plan.txt。"
  fi
  if has_literal "$file" 'docs/dev_plan/当前开发文档.md'; then
    add_issue "error" "legacy_current_dev_doc" "$file" "仍引用已废弃的 docs/dev_plan/当前开发文档.md。"
  fi
}

check_todo_doc() {
  local file="$1"
  add_check "todo-doc:$file"

  if [[ ! -f "$file" ]]; then
    add_issue "error" "todo_missing" "$file" "缺少 docs/dev_plan/todo.md。"
    return
  fi

  check_required_regex "$file" '^# .+' "error" "todo_missing_h1" "todo.md 缺少一级标题。"
  if [[ "$(grep -c '^## ' "$file" || true)" -lt 2 ]]; then
    add_issue "warning" "todo_sections_too_few" "$file" "todo.md 的二级章节少于 2 个，建议检查长期待办结构。"
  fi
  check_required_literal "$file" '| 模块 | 当前阻塞 | 完成定义（DoD） | 验证方式 |' "error" "todo_missing_table_header" "todo.md 缺少长期待办表头。"
}

check_completed_doc() {
  local file="$1"
  add_check "completed-doc:$file"

  if [[ ! -f "$file" ]]; then
    add_issue "error" "completed_missing" "$file" "缺少 docs/dev_plan/completed.md。"
    return
  fi

  check_required_regex "$file" '^# .+' "error" "completed_missing_h1" "completed.md 缺少一级标题。"
  if [[ "$(grep -c '^## ' "$file" || true)" -lt 1 ]]; then
    add_issue "warning" "completed_sections_too_few" "$file" "completed.md 缺少二级章节，建议检查已完成模块结构。"
  fi
  check_required_literal "$file" '| 模块 | 结论 | 代码证据 | 来源 |' "error" "completed_missing_table_header" "completed.md 缺少已完成模块表头。"
}

collect_section_statuses() {
  local file="$1"
  local heading="$2"
  awk -v heading="$heading" '
    function trim(s) {
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", s)
      return s
    }
    BEGIN {
      in_section = 0
    }
    $0 == heading {
      in_section = 1
      next
    }
    in_section == 1 && ($0 ~ /^### / || $0 ~ /^## /) {
      in_section = 0
    }
    in_section == 1 && /^\|/ {
      if ($0 ~ /^\|[- ]+\|/) next
      n = split($0, parts, "|")
      if (n < 5) next
      first = trim(parts[2])
      status = trim(parts[4])
      if (first == "模块" || first == "阶段") next
      if (status == "" || status == "---") next
      printf "%d\t%s\n", NR, status
    }
  ' "$file"
}

validate_status_values() {
  local file="$1"
  local heading="$2"
  local code="$3"
  local allowed='^(待填充|未开始|待执行|进行中|已完成|阻塞|已归档|todo|doing|done)(（.*）)?$'
  local line_no status

  while IFS=$'\t' read -r line_no status; do
    [[ -z "$line_no" ]] && continue
    if [[ ! "$status" =~ $allowed ]]; then
      add_issue "warning" "$code" "$file:$line_no" "检测到未纳入首版状态词白名单的值：$status"
    fi
  done < <(collect_section_statuses "$file" "$heading")
}

check_dev_plan_shape() {
  local file="$1"
  local label="$2"
  add_check "dev-plan:$label:$file"

  check_required_regex "$file" '^# .+' "error" "dev_plan_missing_h1" "缺少一级标题。"
  check_required_literal "$file" '### 已完成/未完成矩阵' "error" "dev_plan_missing_matrix" "缺少“### 已完成/未完成矩阵”。"
  check_required_literal "$file" '### 下一开发模块建议' "error" "dev_plan_missing_next_steps" "缺少“### 下一开发模块建议”。"
  check_required_literal "$file" '### 模块完成同步历史' "error" "dev_plan_missing_history" "缺少“### 模块完成同步历史”。"
  validate_status_values "$file" '### 已完成/未完成矩阵' "dev_plan_unknown_status"
}

check_optimization_plan_shape() {
  local file="$1"
  local label="$2"
  add_check "optimization-plan:$label:$file"

  check_required_regex "$file" '^# .+' "error" "optimization_plan_missing_h1" "缺少一级标题。"
  check_required_literal "$file" '## 8. 优化执行矩阵' "error" "optimization_plan_missing_matrix" "缺少“## 8. 优化执行矩阵”。"
  check_required_literal "$file" '## 9. 下一步优化建议' "error" "optimization_plan_missing_next_steps" "缺少“## 9. 下一步优化建议”。"
  check_required_literal "$file" '## 10. 优化回写记录' "error" "optimization_plan_missing_history" "缺少“## 10. 优化回写记录”。"
  validate_status_values "$file" '## 8. 优化执行矩阵' "optimization_plan_unknown_status"
}

check_plan_file_shape() {
  local file="$1"
  local label="$2"

  if has_literal "$file" '### 已完成/未完成矩阵'; then
    check_dev_plan_shape "$file" "$label"
    return
  fi
  if has_literal "$file" '## 8. 优化执行矩阵'; then
    check_optimization_plan_shape "$file" "$label"
    return
  fi

  add_issue "error" "plan_shape_unknown" "$file" "$label 未匹配开发计划或优化计划的已知结构。"
}

check_slot_pointers() {
  local slots_dir="$ROOT/.codex/plan-slots"
  local pointer slot raw target target_rel
  local found_any=0

  add_check "slots-dir:$slots_dir"
  if [[ ! -d "$slots_dir" ]]; then
    add_issue "error" "slot_dir_missing" "$slots_dir" "缺少 .codex/plan-slots 目录。"
    return
  fi

  for pointer in "$slots_dir"/*.txt; do
    [[ -f "$pointer" ]] || continue
    found_any=1
    slot="$(basename "$pointer" .txt)"
    add_check "slot-pointer:$slot"

    raw="$(first_nonblank_line "$pointer")"
    if [[ -z "$raw" ]]; then
      if [[ "$slot" == "default" ]]; then
        add_issue "error" "default_slot_pointer_empty" "$pointer" "default slot 指针为空。"
      else
        add_issue "error" "slot_pointer_empty" "$pointer" "slot 指针为空。"
      fi
      continue
    fi

    target="$(resolve_path "$raw")"
    target_rel="$raw"

    if [[ "$slot" == "default" && "$target_rel" != "docs/dev_plan/当前开发计划.md" ]]; then
      add_issue "warning" "default_slot_target_drift" "$pointer" "default slot 当前未指向 docs/dev_plan/当前开发计划.md。"
    fi

    if [[ ! -f "$target" ]]; then
      add_issue "error" "slot_target_missing" "$pointer" "slot 指向的计划文档不存在: $target"
      continue
    fi

    if [[ "$target_rel" == "docs/dev_plan/todo.md" || "$target_rel" == "docs/dev_plan/completed.md" ]]; then
      add_issue "warning" "slot_points_to_long_term_doc" "$pointer" "slot 当前绑定到长期文档，建议改为活动计划文档。"
    fi

    check_plan_file_shape "$target" "slot:$slot"
  done

  if [[ "$found_any" -eq 0 ]]; then
    add_issue "error" "slot_pointer_missing" "$slots_dir" "未找到任何 slot 指针文件。"
  fi
}

build_json_report() {
  awk '
    BEGIN {
      error_count = 0
      warning_count = 0
      check_count = 0
      first_error = 1
      first_warning = 1
      print "{"
    }
    FNR == NR {
      checks[++check_count] = $0
      next
    }
    {
      sev = $1
      if (sev == "error") {
        errors[++error_count] = $0
      } else if (sev == "warning") {
        warnings[++warning_count] = $0
      }
    }
    END {
      printf "  \"ok\": %s,\n", (error_count == 0 ? "true" : "false")
      printf "  \"summary\": {\n"
      printf "    \"errors\": %d,\n", error_count
      printf "    \"warnings\": %d,\n", warning_count
      printf "    \"checks\": %d\n", check_count
      printf "  },\n"

      printf "  \"checked\": ["
      for (i = 1; i <= check_count; i++) {
        gsub(/\\/,"\\\\", checks[i]); gsub(/"/,"\\\"", checks[i])
        printf "%s\"%s\"", (i == 1 ? "" : ","), checks[i]
      }
      printf "],\n"

      printf "  \"errors\": ["
      for (i = 1; i <= error_count; i++) {
        split(errors[i], parts, "\t")
        code = parts[2]
        target = parts[3]
        message = parts[4]
        gsub(/\\/,"\\\\", code); gsub(/"/,"\\\"", code)
        gsub(/\\/,"\\\\", target); gsub(/"/,"\\\"", target)
        gsub(/\\/,"\\\\", message); gsub(/"/,"\\\"", message)
        printf "%s{\"code\":\"%s\",\"target\":\"%s\",\"message\":\"%s\"}", (i == 1 ? "" : ","), code, target, message
      }
      printf "],\n"

      printf "  \"warnings\": ["
      for (i = 1; i <= warning_count; i++) {
        split(warnings[i], parts, "\t")
        code = parts[2]
        target = parts[3]
        message = parts[4]
        gsub(/\\/,"\\\\", code); gsub(/"/,"\\\"", code)
        gsub(/\\/,"\\\\", target); gsub(/"/,"\\\"", target)
        gsub(/\\/,"\\\\", message); gsub(/"/,"\\\"", message)
        printf "%s{\"code\":\"%s\",\"target\":\"%s\",\"message\":\"%s\"}", (i == 1 ? "" : ","), code, target, message
      }
      printf "]\n"
      printf "}\n"
    }
  ' "$CHECKS_FILE" "$FINDINGS_FILE"
}

build_markdown_report() {
  local error_count warning_count check_count
  error_count="$(awk -F '\t' '$1 == "error" { c++ } END { print c + 0 }' "$FINDINGS_FILE")"
  warning_count="$(awk -F '\t' '$1 == "warning" { c++ } END { print c + 0 }' "$FINDINGS_FILE")"
  check_count="$(awk 'END { print NR + 0 }' "$CHECKS_FILE")"

  {
    echo "# Harness Docs Lint Report"
    echo
    echo "- root: \`$ROOT\`"
    echo "- checks: $check_count"
    echo "- errors: $error_count"
    echo "- warnings: $warning_count"
    echo "- status: $([[ "$error_count" -eq 0 ]] && echo PASS || echo FAIL)"
    echo
    echo "## Checked"
    if [[ "$check_count" -eq 0 ]]; then
      echo
      echo "- （无）"
    else
      echo
      awk '{ printf "- `%s`\n", $0 }' "$CHECKS_FILE"
    fi

    echo
    echo "## Findings"
    echo
    if [[ ! -s "$FINDINGS_FILE" ]]; then
      echo "- 无发现。"
    else
      awk -F '\t' '
        {
          printf "- [%s] `%s` `%s`: %s\n", toupper($1), $2, $3, $4
        }
      ' "$FINDINGS_FILE"
    fi
  }
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root)
      ROOT="$2"
      shift 2
      ;;
    --json-out)
      JSON_OUT="$2"
      shift 2
      ;;
    --md-out)
      MD_OUT="$2"
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

resolve_root
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
FINDINGS_FILE="$TMP_DIR/findings.tsv"
CHECKS_FILE="$TMP_DIR/checks.txt"
: >"$FINDINGS_FILE"
: >"$CHECKS_FILE"

JSON_OUT="$(resolve_path "$JSON_OUT")"
MD_OUT="$(resolve_path "$MD_OUT")"

if [[ -z "$JSON_OUT" ]]; then
  JSON_OUT="$(mktemp /tmp/harness_docs_lint.json.XXXXXX)"
fi
if [[ -z "$MD_OUT" ]]; then
  MD_OUT="$(mktemp /tmp/harness_docs_lint.md.XXXXXX)"
fi

ensure_parent_dir "$JSON_OUT"
ensure_parent_dir "$MD_OUT"

check_slot_pointers
check_todo_doc "$ROOT/docs/dev_plan/todo.md"
check_completed_doc "$ROOT/docs/dev_plan/completed.md"

CURRENT_PLAN="$ROOT/docs/dev_plan/当前开发计划.md"
if [[ -f "$CURRENT_PLAN" ]]; then
  check_plan_file_shape "$CURRENT_PLAN" "default-current-plan"
  if ! has_literal "$CURRENT_PLAN" '关联 slot：`default`'; then
    add_issue "warning" "current_plan_missing_default_slot_note" "$CURRENT_PLAN" "当前开发计划未声明关联 slot 为 default。"
  fi
else
  add_issue "error" "current_plan_missing" "$CURRENT_PLAN" "缺少 docs/dev_plan/当前开发计划.md。"
fi

HARNESS_DOC_FOUND=0
for harness_doc in "$ROOT"/docs/harness/*.md; do
  [[ -f "$harness_doc" ]] || continue
  HARNESS_DOC_FOUND=1
  check_harness_doc "$harness_doc"
done
if [[ "$HARNESS_DOC_FOUND" -eq 0 ]]; then
  add_issue "error" "harness_docs_missing" "$ROOT/docs/harness" "未找到 docs/harness/*.md。"
fi

build_json_report >"$JSON_OUT"
build_markdown_report >"$MD_OUT"
cat "$MD_OUT"
printf '\njson_report: %s\n' "$JSON_OUT"
printf 'markdown_report: %s\n' "$MD_OUT"

ERROR_COUNT="$(awk -F '\t' '$1 == "error" { c++ } END { print c + 0 }' "$FINDINGS_FILE")"
if [[ "$ERROR_COUNT" -gt 0 ]]; then
  exit 1
fi

exit 0
