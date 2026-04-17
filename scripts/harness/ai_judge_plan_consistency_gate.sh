#!/usr/bin/env bash
set -euo pipefail

ROOT=""
PLAN_DOC=""
ARCH_DOC=""
EMIT_JSON=""
EMIT_MD=""
RUN_ID=""
STARTED_AT=""
FINISHED_AT=""
STATUS="pass"

CONSISTENCY_SECTION_FOUND="false"
ARCH_CHECKLIST_FOUND="true"

ROLE_STATUS="missing"
DATA_STATUS="missing"
GATE_STATUS="missing"
BOUNDARY_STATUS="missing"
CROSSLAYER_STATUS="missing"
CLOSURE_STATUS="missing"

ROLE_ANSWER=""
DATA_ANSWER=""
GATE_ANSWER=""
BOUNDARY_ANSWER=""
CROSSLAYER_ANSWER=""
CLOSURE_ANSWER=""

MISSING_ITEMS=()
EMPTY_ITEMS=()
PLACEHOLDER_ITEMS=()
ARCH_MISSING_ITEMS=()

CONSISTENCY_LABELS=(
  "角色一致性"
  "数据一致性"
  "门禁一致性"
  "边界一致性"
  "跨层一致性"
  "收口一致性"
)

usage() {
  cat <<'USAGE'
用法:
  ai_judge_plan_consistency_gate.sh \
    [--root <repo-root>] \
    [--plan-doc <path>] \
    [--arch-doc <path>] \
    [--emit-json <path>] \
    [--emit-md <path>]

说明:
  - 校验“下一阶段开发计划”是否包含架构方案第13章要求的6项一致性回答。
  - 6项一致性：角色/数据/门禁/边界/跨层/收口。
  - 任一缺失、空值或占位答案会导致 gate 失败（status=fail）。
USAGE
}

iso_now() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
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

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --root)
        ROOT="${2:-}"
        shift 2
        ;;
      --plan-doc)
        PLAN_DOC="${2:-}"
        shift 2
        ;;
      --arch-doc)
        ARCH_DOC="${2:-}"
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
        usage
        exit 2
        ;;
    esac
  done
}

is_placeholder_answer() {
  local answer cleaned lowered
  answer="$(trim "${1:-}")"
  cleaned="${answer//\`/}"
  cleaned="${cleaned//\"/}"
  cleaned="$(trim "$cleaned")"
  lowered="$(printf '%s' "$cleaned" | tr '[:upper:]' '[:lower:]')"

  case "$lowered" in
    ""|"-"|"--"|"---"|"tbd"|"todo"|"n/a"|"na"|"..."|"待补充"|"待确认"|"待填写"|"未填写")
      return 0
      ;;
  esac

  if [[ "$cleaned" == *"待补充"* || "$cleaned" == *"待确认"* || "$cleaned" == *"未填写"* ]]; then
    return 0
  fi
  return 1
}

extract_consistency_section() {
  local source_file="$1"
  local out_file="$2"

  awk '
    BEGIN {
      in_section = 0
      found = 0
    }
    /^##[[:space:]]+/ {
      if (in_section == 1) {
        exit
      }
      if ($0 ~ /一致性校验|一致性检查清单|一致性检查/) {
        in_section = 1
        found = 1
        print
        next
      }
    }
    in_section == 1 {
      print
    }
    END {
      if (found == 0) {
        exit 3
      }
    }
  ' "$source_file" >"$out_file"
}

extract_answer_line() {
  local section_file="$1"
  local label="$2"
  grep -E "^[[:space:]]*[0-9]+\\.[[:space:]]*(\\*\\*)?${label}(\\*\\*)?[：:]" "$section_file" | head -n 1 || true
}

strip_answer_prefix() {
  local line="$1"
  local label="$2"
  printf '%s' "$line" | sed -E "s/^[[:space:]]*[0-9]+\\.[[:space:]]*(\\*\\*)?${label}(\\*\\*)?[：:][[:space:]]*//"
}

record_result() {
  local label="$1"
  local line="$2"
  local answer
  answer="$(trim "$(strip_answer_prefix "$line" "$label")")"

  local answer_status="pass"
  if [[ -z "$line" ]]; then
    answer_status="missing"
    MISSING_ITEMS+=("$label")
  elif [[ -z "$answer" ]]; then
    answer_status="empty"
    EMPTY_ITEMS+=("$label")
  elif is_placeholder_answer "$answer"; then
    answer_status="placeholder"
    PLACEHOLDER_ITEMS+=("$label")
  fi

  case "$label" in
    "角色一致性")
      ROLE_STATUS="$answer_status"
      ROLE_ANSWER="$answer"
      ;;
    "数据一致性")
      DATA_STATUS="$answer_status"
      DATA_ANSWER="$answer"
      ;;
    "门禁一致性")
      GATE_STATUS="$answer_status"
      GATE_ANSWER="$answer"
      ;;
    "边界一致性")
      BOUNDARY_STATUS="$answer_status"
      BOUNDARY_ANSWER="$answer"
      ;;
    "跨层一致性")
      CROSSLAYER_STATUS="$answer_status"
      CROSSLAYER_ANSWER="$answer"
      ;;
    "收口一致性")
      CLOSURE_STATUS="$answer_status"
      CLOSURE_ANSWER="$answer"
      ;;
  esac
}

check_arch_checklist() {
  local label
  for label in "${CONSISTENCY_LABELS[@]}"; do
    if ! grep -Fq "$label" "$ARCH_DOC"; then
      ARCH_MISSING_ITEMS+=("$label")
    fi
  done
  if (( ${#ARCH_MISSING_ITEMS[@]} > 0 )); then
    ARCH_CHECKLIST_FOUND="false"
  fi
}

join_or_none() {
  if (( $# == 0 )); then
    printf '%s' "none"
    return
  fi
  local IFS=", "
  printf '%s' "$*"
}

print_json_string_list() {
  local first=1
  local item
  for item in "$@"; do
    if [[ $first -eq 0 ]]; then
      printf ', '
    fi
    printf '"%s"' "$(json_escape "$item")"
    first=0
  done
}

write_json_summary() {
  {
    printf '{\n'
    printf '  "run_id": "%s",\n' "$(json_escape "$RUN_ID")"
    printf '  "status": "%s",\n' "$(json_escape "$STATUS")"
    printf '  "root": "%s",\n' "$(json_escape "$ROOT")"
    printf '  "plan_doc": "%s",\n' "$(json_escape "$PLAN_DOC")"
    printf '  "arch_doc": "%s",\n' "$(json_escape "$ARCH_DOC")"
    printf '  "consistency_section_found": %s,\n' "$CONSISTENCY_SECTION_FOUND"
    printf '  "arch_checklist_found": %s,\n' "$ARCH_CHECKLIST_FOUND"
    printf '  "checks": [\n'
    printf '    {"label":"%s","status":"%s","answer":"%s"},\n' "角色一致性" "$ROLE_STATUS" "$(json_escape "$ROLE_ANSWER")"
    printf '    {"label":"%s","status":"%s","answer":"%s"},\n' "数据一致性" "$DATA_STATUS" "$(json_escape "$DATA_ANSWER")"
    printf '    {"label":"%s","status":"%s","answer":"%s"},\n' "门禁一致性" "$GATE_STATUS" "$(json_escape "$GATE_ANSWER")"
    printf '    {"label":"%s","status":"%s","answer":"%s"},\n' "边界一致性" "$BOUNDARY_STATUS" "$(json_escape "$BOUNDARY_ANSWER")"
    printf '    {"label":"%s","status":"%s","answer":"%s"},\n' "跨层一致性" "$CROSSLAYER_STATUS" "$(json_escape "$CROSSLAYER_ANSWER")"
    printf '    {"label":"%s","status":"%s","answer":"%s"}\n' "收口一致性" "$CLOSURE_STATUS" "$(json_escape "$CLOSURE_ANSWER")"
    printf '  ],\n'
    printf '  "missing_items": ['
    print_json_string_list ${MISSING_ITEMS[@]+"${MISSING_ITEMS[@]}"}
    printf '],\n'
    printf '  "empty_items": ['
    print_json_string_list ${EMPTY_ITEMS[@]+"${EMPTY_ITEMS[@]}"}
    printf '],\n'
    printf '  "placeholder_items": ['
    print_json_string_list ${PLACEHOLDER_ITEMS[@]+"${PLACEHOLDER_ITEMS[@]}"}
    printf '],\n'
    printf '  "arch_missing_items": ['
    print_json_string_list ${ARCH_MISSING_ITEMS[@]+"${ARCH_MISSING_ITEMS[@]}"}
    printf '],\n'
    printf '  "started_at": "%s",\n' "$(json_escape "$STARTED_AT")"
    printf '  "finished_at": "%s",\n' "$(json_escape "$FINISHED_AT")"
    printf '  "outputs": {\n'
    printf '    "json": "%s",\n' "$(json_escape "$EMIT_JSON")"
    printf '    "markdown": "%s"\n' "$(json_escape "$EMIT_MD")"
    printf '  }\n'
    printf '}\n'
  } >"$EMIT_JSON"
}

write_md_summary() {
  {
    printf '# ai-judge-plan-consistency-gate\n\n'
    printf -- '- run_id: `%s`\n' "$RUN_ID"
    printf -- '- status: `%s`\n' "$STATUS"
    printf -- '- plan_doc: `%s`\n' "$PLAN_DOC"
    printf -- '- arch_doc: `%s`\n' "$ARCH_DOC"
    printf -- '- consistency_section_found: `%s`\n' "$CONSISTENCY_SECTION_FOUND"
    printf -- '- arch_checklist_found: `%s`\n' "$ARCH_CHECKLIST_FOUND"
    printf -- '- missing_items: `%s`\n' "$(join_or_none ${MISSING_ITEMS[@]+"${MISSING_ITEMS[@]}"})"
    printf -- '- empty_items: `%s`\n' "$(join_or_none ${EMPTY_ITEMS[@]+"${EMPTY_ITEMS[@]}"})"
    printf -- '- placeholder_items: `%s`\n' "$(join_or_none ${PLACEHOLDER_ITEMS[@]+"${PLACEHOLDER_ITEMS[@]}"})"
    printf -- '- arch_missing_items: `%s`\n' "$(join_or_none ${ARCH_MISSING_ITEMS[@]+"${ARCH_MISSING_ITEMS[@]}"})"
    printf -- '- started_at: `%s`\n' "$STARTED_AT"
    printf -- '- finished_at: `%s`\n' "$FINISHED_AT"
    printf '\n## 6项一致性检查结果\n\n'
    printf '1. 角色一致性：`%s`（%s）\n' "$ROLE_STATUS" "$(trim "$ROLE_ANSWER")"
    printf '2. 数据一致性：`%s`（%s）\n' "$DATA_STATUS" "$(trim "$DATA_ANSWER")"
    printf '3. 门禁一致性：`%s`（%s）\n' "$GATE_STATUS" "$(trim "$GATE_ANSWER")"
    printf '4. 边界一致性：`%s`（%s）\n' "$BOUNDARY_STATUS" "$(trim "$BOUNDARY_ANSWER")"
    printf '5. 跨层一致性：`%s`（%s）\n' "$CROSSLAYER_STATUS" "$(trim "$CROSSLAYER_ANSWER")"
    printf '6. 收口一致性：`%s`（%s）\n' "$CLOSURE_STATUS" "$(trim "$CLOSURE_ANSWER")"
  } >"$EMIT_MD"
}

main() {
  parse_args "$@"
  resolve_root

  if [[ -z "$PLAN_DOC" ]]; then
    PLAN_DOC="$ROOT/docs/dev_plan/当前开发计划.md"
  else
    PLAN_DOC="$(abs_path "$PLAN_DOC")"
  fi
  if [[ -z "$ARCH_DOC" ]]; then
    ARCH_DOC="$ROOT/docs/dev_plan/AI_Judge_Service-架构与技术栈决策方案-2026-04-13.md"
  else
    ARCH_DOC="$(abs_path "$ARCH_DOC")"
  fi

  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ai-judge-plan-consistency-gate"
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
  [[ -f "$ARCH_DOC" ]] || { echo "架构文档不存在: $ARCH_DOC" >&2; exit 1; }

  local section_file
  section_file="$(mktemp)"
  if extract_consistency_section "$PLAN_DOC" "$section_file"; then
    CONSISTENCY_SECTION_FOUND="true"
  else
    CONSISTENCY_SECTION_FOUND="false"
  fi

  local label line
  for label in "${CONSISTENCY_LABELS[@]}"; do
    line=""
    if [[ "$CONSISTENCY_SECTION_FOUND" == "true" ]]; then
      line="$(extract_answer_line "$section_file" "$label")"
    fi
    record_result "$label" "$line"
  done

  check_arch_checklist

  if [[ "$CONSISTENCY_SECTION_FOUND" != "true" ]]; then
    STATUS="fail"
  fi
  if [[ "$ARCH_CHECKLIST_FOUND" != "true" ]]; then
    STATUS="fail"
  fi
  if (( ${#MISSING_ITEMS[@]} > 0 || ${#EMPTY_ITEMS[@]} > 0 || ${#PLACEHOLDER_ITEMS[@]} > 0 )); then
    STATUS="fail"
  fi

  FINISHED_AT="$(iso_now)"
  write_json_summary
  write_md_summary

  echo "ai_judge_plan_consistency_gate_status: $STATUS"
  echo "summary_json: $EMIT_JSON"
  echo "summary_md: $EMIT_MD"
  echo "consistency_section_found: $CONSISTENCY_SECTION_FOUND"
  echo "arch_checklist_found: $ARCH_CHECKLIST_FOUND"
  echo "missing_items: $(join_or_none ${MISSING_ITEMS[@]+"${MISSING_ITEMS[@]}"})"
  echo "empty_items: $(join_or_none ${EMPTY_ITEMS[@]+"${EMPTY_ITEMS[@]}"})"
  echo "placeholder_items: $(join_or_none ${PLACEHOLDER_ITEMS[@]+"${PLACEHOLDER_ITEMS[@]}"})"
  echo "arch_missing_items: $(join_or_none ${ARCH_MISSING_ITEMS[@]+"${ARCH_MISSING_ITEMS[@]}"})"

  rm -f "$section_file"

  if [[ "$STATUS" != "pass" ]]; then
    exit 1
  fi
}

main "$@"
