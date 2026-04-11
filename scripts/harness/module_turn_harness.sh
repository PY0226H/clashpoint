#!/usr/bin/env bash
set -euo pipefail

ROOT=""
TASK_KIND=""
MODULE=""
SUMMARY=""
PLAN=""
SLOT=""
PRD_MODE="auto"
KNOWLEDGE_PACK_MODE="auto"
STAGE=""
PRIORITY="P1"
STATUS_TEXT=""
NOTE=""
NEXT_STEPS=""
ISSUES=""
LEARNINGS=""
DRY_RUN=0
STRICT=0
RUN_STARTED_AT=""
RUN_FINISHED_AT=""
HARNESS_RUN_ID=""
HARNESS_ARTIFACT_DIR=""
HARNESS_JSONL=""
HARNESS_SUMMARY_JSON=""
HARNESS_SUMMARY_MD=""
STEP_RECORDS_FILE=""
COMMIT_RECOMMENDATION_BLOCK=""
COMMIT_RECOMMENDATION_TITLE=""

usage() {
  cat <<'USAGE'
用法:
  module_turn_harness.sh \
    --task-kind <dev|refactor|non-dev> \
    --module <module-id> \
    --summary <summary> \
    [--plan <plan-path>] \
    [--slot <slot-name>] \
    [--prd-mode <auto|summary|full>] \
    [--knowledge-pack <auto|skip|force>] \
    [--stage <stage-id>] \
    [--priority <P0|P1|P2|...>] \
    [--status-text <status-text>] \
    [--note <matrix-note>] \
    [--next-steps "建议1;建议2"] \
    [--issues "问题=>修复;问题2=>修复2"] \
    [--learnings "点1;点2"] \
    [--root <repo-root>] \
    [--dry-run] \
    [--strict]

说明:
  - dev: 触发当前模块级开发 hook 链
  - refactor: 触发当前模块级重构/优化 hook 链
  - non-dev: 轻量模式，不触发模块级 hooks
  - dry-run: 只展示即将执行的步骤
  - strict: 任一步失败即停止
USAGE
}

trim() {
  local v="$1"
  v="${v#${v%%[![:space:]]*}}"
  v="${v%${v##*[![:space:]]}}"
  printf '%s' "$v"
}

lower_ascii() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

contains_keyword() {
  local haystack="$1"
  local keyword="$2"
  [[ "$haystack" == *"$keyword"* ]]
}

match_first_keyword() {
  local haystack="$1"
  shift
  local keyword
  for keyword in "$@"; do
    if contains_keyword "$haystack" "$keyword"; then
      printf '%s' "$keyword"
      return 0
    fi
  done
  return 1
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
  local path="$1"
  if [[ -z "$path" ]]; then
    echo ""
  elif [[ "$path" = /* ]]; then
    echo "$path"
  else
    echo "$ROOT/$path"
  fi
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

sanitize_id() {
  local value="$1"
  value="$(printf '%s' "$value" | tr '[:upper:]' '[:lower:]')"
  value="$(printf '%s' "$value" | sed -E 's/[^a-z0-9._-]+/-/g; s/^-+//; s/-+$//')"
  [[ -z "$value" ]] && value="run"
  printf '%s' "$value"
}

ensure_parent_dir() {
  local path="$1"
  mkdir -p "$(dirname "$path")"
}

resolve_plan_evidence_path() {
  local pointer raw
  if [[ -n "$PLAN" ]]; then
    printf '%s' "$PLAN"
    return 0
  fi

  if [[ -n "$SLOT" ]]; then
    pointer="$ROOT/.codex/plan-slots/$SLOT.txt"
    if [[ -f "$pointer" ]]; then
      raw="$(awk 'NF {print; exit}' "$pointer" 2>/dev/null || true)"
      [[ -n "$raw" ]] && printf '%s' "$(abs_path "$raw")" && return 0
    fi
  fi

  pointer="$ROOT/.codex/plan-slots/default.txt"
  if [[ -f "$pointer" ]]; then
    raw="$(awk 'NF {print; exit}' "$pointer" 2>/dev/null || true)"
    [[ -n "$raw" ]] && printf '%s' "$(abs_path "$raw")" && return 0
  fi

  if [[ -f "$ROOT/docs/dev_plan/当前开发计划.md" ]]; then
    printf '%s' "$ROOT/docs/dev_plan/当前开发计划.md"
    return 0
  fi

  return 1
}

read_prd_guard_metadata() {
  local metadata_file="$1"
  local key="$2"
  [[ -f "$metadata_file" ]] || return 1
  awk -v key="$key" '
    index($0, "=") > 0 {
      current_key = substr($0, 1, index($0, "=") - 1)
      if (current_key == key) {
        print substr($0, index($0, "=") + 1)
        exit
      }
    }
  ' "$metadata_file"
}

evidence_to_json_array() {
  local raw="$1"
  local first=1
  local item
  printf '['
  while IFS=';' read -r item; do
    item="$(trim "$item")"
    [[ -z "$item" ]] && continue
    printf '%s"%s"' "$([[ "$first" -eq 1 ]] && echo "" || echo ",")" "$(json_escape "$item")"
    first=0
  done <<< "$raw"
  printf ']'
}

record_jsonl_event() {
  local event_type="$1"
  local step_id="$2"
  local description="$3"
  local status="$4"
  local started_at="$5"
  local finished_at="$6"
  local exit_code="$7"
  local evidence_paths="$8"
  local command="$9"

  cat >>"$HARNESS_JSONL" <<EOF_EVENT
{"event":"$(json_escape "$event_type")","run_id":"$(json_escape "$HARNESS_RUN_ID")","task_kind":"$(json_escape "$TASK_KIND")","module":"$(json_escape "$MODULE")","step_id":"$(json_escape "$step_id")","description":"$(json_escape "$description")","status":"$(json_escape "$status")","started_at":"$(json_escape "$started_at")","finished_at":"$(json_escape "$finished_at")","exit_code":$exit_code,"evidence_paths":$(evidence_to_json_array "$evidence_paths"),"command":"$(json_escape "$command")"}
EOF_EVENT
}

append_step_record() {
  local step_id="$1"
  local description="$2"
  local status="$3"
  local started_at="$4"
  local finished_at="$5"
  local exit_code="$6"
  local evidence_paths="$7"
  local command="$8"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$step_id" "$description" "$status" "$started_at" "$finished_at" "$exit_code" "$evidence_paths" "$command" >>"$STEP_RECORDS_FILE"
}

log_step_result() {
  local step_id="$1"
  local description="$2"
  local status="$3"
  local started_at="$4"
  local finished_at="$5"
  local exit_code="$6"
  local evidence_paths="$7"
  local command="$8"
  append_step_record "$step_id" "$description" "$status" "$started_at" "$finished_at" "$exit_code" "$evidence_paths" "$command"
  record_jsonl_event "step" "$step_id" "$description" "$status" "$started_at" "$finished_at" "$exit_code" "$evidence_paths" "$command"
}

init_harness_artifacts() {
  local ts module_id
  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  module_id="$(sanitize_id "$MODULE")"
  HARNESS_RUN_ID="${ts}-${module_id}"
  HARNESS_ARTIFACT_DIR="$ROOT/artifacts/harness"
  mkdir -p "$HARNESS_ARTIFACT_DIR"
  HARNESS_JSONL="$HARNESS_ARTIFACT_DIR/${HARNESS_RUN_ID}.jsonl"
  HARNESS_SUMMARY_JSON="$HARNESS_ARTIFACT_DIR/${HARNESS_RUN_ID}.summary.json"
  HARNESS_SUMMARY_MD="$HARNESS_ARTIFACT_DIR/${HARNESS_RUN_ID}.summary.md"
  : >"$HARNESS_JSONL"
  STEP_RECORDS_FILE="$(mktemp)"
  RUN_STARTED_AT="$(iso_now)"

  record_jsonl_event "run_started" "run" "module-turn-harness run" "$([[ "$DRY_RUN" -eq 1 ]] && echo dry-run || echo started)" "$RUN_STARTED_AT" "$RUN_STARTED_AT" 0 "$HARNESS_JSONL;$HARNESS_SUMMARY_JSON;$HARNESS_SUMMARY_MD" "module_turn_harness.sh"
}

write_summary_files() {
  local overall_status="$1"
  local failed_steps_trimmed
  failed_steps_trimmed="$(trim "$FAILED_STEPS")"
  RUN_FINISHED_AT="$(iso_now)"

  {
    printf '{\n'
    printf '  "run_id": "%s",\n' "$(json_escape "$HARNESS_RUN_ID")"
    printf '  "root": "%s",\n' "$(json_escape "$ROOT")"
    printf '  "task_kind": "%s",\n' "$(json_escape "$TASK_KIND")"
    printf '  "module": "%s",\n' "$(json_escape "$MODULE")"
    printf '  "summary": "%s",\n' "$(json_escape "$SUMMARY")"
    printf '  "status": "%s",\n' "$(json_escape "$overall_status")"
    printf '  "dry_run": %s,\n' "$([[ "$DRY_RUN" -eq 1 ]] && echo true || echo false)"
    printf '  "strict": %s,\n' "$([[ "$STRICT" -eq 1 ]] && echo true || echo false)"
    printf '  "started_at": "%s",\n' "$(json_escape "$RUN_STARTED_AT")"
    printf '  "finished_at": "%s",\n' "$(json_escape "$RUN_FINISHED_AT")"
    printf '  "failure_count": %s,\n' "$FAILURES"
    printf '  "failed_steps": %s,\n' "$(evidence_to_json_array "${failed_steps_trimmed// /;}")"
    printf '  "artifacts": {\n'
    printf '    "jsonl": "%s",\n' "$(json_escape "$HARNESS_JSONL")"
    printf '    "summary_json": "%s",\n' "$(json_escape "$HARNESS_SUMMARY_JSON")"
    printf '    "summary_md": "%s"\n' "$(json_escape "$HARNESS_SUMMARY_MD")"
    printf '  },\n'
    printf '  "steps": [\n'
    awk -F '\t' '
      BEGIN { first = 1 }
      {
        gsub(/\\/,"\\\\",$1); gsub(/"/,"\\\"",$1)
        gsub(/\\/,"\\\\",$2); gsub(/"/,"\\\"",$2)
        gsub(/\\/,"\\\\",$3); gsub(/"/,"\\\"",$3)
        gsub(/\\/,"\\\\",$4); gsub(/"/,"\\\"",$4)
        gsub(/\\/,"\\\\",$5); gsub(/"/,"\\\"",$5)
        gsub(/\\/,"\\\\",$7); gsub(/"/,"\\\"",$7)
        gsub(/\\/,"\\\\",$8); gsub(/"/,"\\\"",$8)
        split($7, evidence, ";")
        evidence_json = "["
        efirst = 1
        for (i in evidence) {
          if (evidence[i] == "") continue
          gsub(/\\/,"\\\\",evidence[i]); gsub(/"/,"\\\"",evidence[i])
          evidence_json = evidence_json (efirst ? "" : ",") "\"" evidence[i] "\""
          efirst = 0
        }
        evidence_json = evidence_json "]"
        printf "    %s{\"step_id\":\"%s\",\"description\":\"%s\",\"status\":\"%s\",\"started_at\":\"%s\",\"finished_at\":\"%s\",\"exit_code\":%s,\"evidence_paths\":%s,\"command\":\"%s\"}\n", (first ? "" : ","), $1, $2, $3, $4, $5, $6, evidence_json, $8
        first = 0
      }
    ' "$STEP_RECORDS_FILE"
    printf '  ]\n'
    printf '}\n'
  } >"$HARNESS_SUMMARY_JSON"

  {
    printf '# Harness Run Summary\n\n'
    printf -- '- run_id: `%s`\n' "$HARNESS_RUN_ID"
    printf -- '- module: `%s`\n' "$MODULE"
    printf -- '- task_kind: `%s`\n' "$TASK_KIND"
    printf -- '- status: `%s`\n' "$overall_status"
    printf -- '- started_at: `%s`\n' "$RUN_STARTED_AT"
    printf -- '- finished_at: `%s`\n' "$RUN_FINISHED_AT"
    printf -- '- jsonl: `%s`\n' "$HARNESS_JSONL"
    printf -- '- summary_json: `%s`\n' "$HARNESS_SUMMARY_JSON"
    printf -- '- summary_md: `%s`\n' "$HARNESS_SUMMARY_MD"
    printf '\n## Steps\n\n'
    printf '| Step | Status | Exit | Evidence |\n'
    printf '|---|---|---|---|\n'
    awk -F '\t' '
      function evidence_text(raw) {
        gsub(/;/, "<br>", raw)
        return raw == "" ? "（无）" : raw
      }
      {
        printf "| %s | %s | %s | %s |\n", $1, $3, $6, evidence_text($7)
      }
    ' "$STEP_RECORDS_FILE"
  } >"$HARNESS_SUMMARY_MD"

  record_jsonl_event "run_finished" "run" "module-turn-harness run" "$overall_status" "$RUN_STARTED_AT" "$RUN_FINISHED_AT" "$FAILURES" "$HARNESS_JSONL;$HARNESS_SUMMARY_JSON;$HARNESS_SUMMARY_MD" "module_turn_harness.sh"
}

collect_changes() {
  {
    git -C "$ROOT" diff --name-only 2>/dev/null || true
    git -C "$ROOT" diff --cached --name-only 2>/dev/null || true
    git -C "$ROOT" ls-files --others --exclude-standard 2>/dev/null || true
  } | awk 'NF' | sort -u | paste -sd ';' - || true
}

step_header() {
  printf '\n[%s] %s\n' "$1" "$2"
}

record_test_result() {
  local text="$1"
  if [[ -z "${TEST_RESULTS:-}" ]]; then
    TEST_RESULTS="$text"
  else
    TEST_RESULTS="${TEST_RESULTS}; ${text}"
  fi
}

run_cmd() {
  local step_id="$1"
  local desc="$2"
  local evidence_paths="$3"
  shift 3
  local cmd=( "$@" )
  local command_text started_at finished_at

  step_header "$step_id" "$desc"
  command_text="$(printf '%s ' "${cmd[@]}" | sed 's/[[:space:]]*$//')"
  printf 'command: %s\n' "$command_text"
  started_at="$(iso_now)"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    finished_at="$(iso_now)"
    log_step_result "$step_id" "$desc" "dry_run" "$started_at" "$finished_at" 0 "$evidence_paths" "$command_text"
    return 0
  fi

  if "${cmd[@]}"; then
    finished_at="$(iso_now)"
    log_step_result "$step_id" "$desc" "pass" "$started_at" "$finished_at" 0 "$evidence_paths" "$command_text"
    return 0
  fi

  local rc=$?
  finished_at="$(iso_now)"
  printf '[FAIL] %s (exit=%s)\n' "$step_id" "$rc" >&2
  FAILURES=$((FAILURES + 1))
  FAILED_STEPS="${FAILED_STEPS}${step_id} "
  log_step_result "$step_id" "$desc" "fail" "$started_at" "$finished_at" "$rc" "$evidence_paths" "$command_text"
  if [[ "$STRICT" -eq 1 ]]; then
    write_summary_files "fail"
    exit "$rc"
  fi
  return 0
}

run_prd_gate() {
  local script="$ROOT/skills/pre-module-prd-goal-guard/scripts/run_prd_goal_guard.sh"
  local metadata_file started_at finished_at status rc evidence_paths
  local command_text reason effective_mode
  local cmd

  metadata_file="$(mktemp)"
  cmd=( bash "$script" --root "$ROOT" --task-kind "$TASK_KIND" --module "$MODULE" --summary "$SUMMARY" --mode "$PRD_MODE" --metadata-out "$metadata_file" )
  [[ "$DRY_RUN" -eq 1 ]] && cmd+=( --dry-run )
  command_text="$(printf '%s ' "${cmd[@]}" | sed 's/[[:space:]]*$//')"

  step_header "pre-prd" "PRD 对齐"
  started_at="$(iso_now)"

  set +e
  "${cmd[@]}"
  rc=$?
  set -e

  finished_at="$(iso_now)"
  evidence_paths="$(read_prd_guard_metadata "$metadata_file" "evidence_paths" || true)"
  effective_mode="$(read_prd_guard_metadata "$metadata_file" "effective_mode" || true)"
  reason="$(read_prd_guard_metadata "$metadata_file" "reason" || true)"
  rm -f "$metadata_file"

  [[ -z "$effective_mode" ]] && effective_mode="$([[ "$PRD_MODE" == "full" ]] && echo full || echo summary)"
  [[ -z "$evidence_paths" ]] && evidence_paths="$ROOT/docs/harness/product-goals.md"

  printf 'effective_mode_recorded: %s\n' "$effective_mode"
  [[ -n "$reason" ]] && printf 'effective_mode_reason: %s\n' "$reason"

  if [[ "$rc" -eq 0 ]]; then
    status="$([[ "$DRY_RUN" -eq 1 ]] && echo dry_run || echo pass)"
    log_step_result "pre-prd" "PRD 对齐" "$status" "$started_at" "$finished_at" 0 "$evidence_paths" "$command_text"
    return 0
  fi

  printf '[FAIL] pre-prd (exit=%s)\n' "$rc" >&2
  FAILURES=$((FAILURES + 1))
  FAILED_STEPS="${FAILED_STEPS}pre-prd "
  log_step_result "pre-prd" "PRD 对齐" "fail" "$started_at" "$finished_at" "$rc" "$evidence_paths" "$command_text"
  if [[ "$STRICT" -eq 1 ]]; then
    write_summary_files "fail"
    exit "$rc"
  fi
  return 0
}

run_test_guard_chain() {
  local changes started_at finished_at
  changes="$(collect_changes)"
  local test_guard="$ROOT/skills/post-module-test-guard/scripts/test_change_guard.sh"
  local suggest="$ROOT/skills/post-module-test-guard/scripts/suggest_test_targets.sh"
  local gate="$ROOT/skills/post-module-test-guard/scripts/run_test_gate.sh"
  started_at="$(iso_now)"

  step_header "post-test-guard" "测试变更检查与测试门禁"
  printf 'changes: %s\n' "${changes:-（未检测到改动文件）}"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    printf 'would_run: %s --root %s --changes "%s"\n' "$test_guard" "$ROOT" "$changes"
    printf 'would_run: %s --root %s --changes "%s" (only when missing tests)\n' "$suggest" "$ROOT" "$changes"
    printf 'would_run: %s --root %s --mode full\n' "$gate" "$ROOT"
    finished_at="$(iso_now)"
    log_step_result "post-test-guard" "测试变更检查与测试门禁" "dry_run" "$started_at" "$finished_at" 0 "" "bash $test_guard --root $ROOT --changes \"$changes\"; bash $gate --root $ROOT --mode full"
    return 0
  fi

  set +e
  bash "$test_guard" --root "$ROOT" --changes "$changes"
  local rc=$?
  set -e

  if [[ "$rc" -eq 2 ]]; then
    bash "$suggest" --root "$ROOT" --changes "$changes" || true
    printf '[FAIL] post-test-guard: 检测到模块改动但缺少测试改动，请先补测。\n' >&2
    FAILURES=$((FAILURES + 1))
    FAILED_STEPS="${FAILED_STEPS}post-test-guard "
    finished_at="$(iso_now)"
    log_step_result "post-test-guard" "测试变更检查与测试门禁" "fail" "$started_at" "$finished_at" 2 "" "bash $test_guard --root $ROOT --changes \"$changes\""
    if [[ "$STRICT" -eq 1 ]]; then
      write_summary_files "fail"
      exit 2
    fi
    return 0
  elif [[ "$rc" -ne 0 ]]; then
    printf '[FAIL] post-test-guard: test_change_guard.sh 失败 (exit=%s)\n' "$rc" >&2
    FAILURES=$((FAILURES + 1))
    FAILED_STEPS="${FAILED_STEPS}post-test-guard "
    finished_at="$(iso_now)"
    log_step_result "post-test-guard" "测试变更检查与测试门禁" "fail" "$started_at" "$finished_at" "$rc" "" "bash $test_guard --root $ROOT --changes \"$changes\""
    if [[ "$STRICT" -eq 1 ]]; then
      write_summary_files "fail"
      exit "$rc"
    fi
    return 0
  fi

  bash "$gate" --root "$ROOT" --mode full
  record_test_result 'bash skills/post-module-test-guard/scripts/run_test_gate.sh --mode full => pass'
  finished_at="$(iso_now)"
  log_step_result "post-test-guard" "测试变更检查与测试门禁" "pass" "$started_at" "$finished_at" 0 "" "bash $test_guard --root $ROOT --changes \"$changes\"; bash $gate --root $ROOT --mode full"
}

build_explanation_body() {
  local body_file="$1"
  local changes="$2"
  cat >"$body_file" <<EOF_BODY
### 1. 这次改动解决了什么问题

- 模块：\`$MODULE\`
- 任务类型：\`$TASK_KIND\`
- 摘要：$SUMMARY

### 2. 改动文件地图

$(printf '%s' "$changes" | tr ';' '\n' | sed 's/^/- /')

### 3. 当前执行链路

1. 通过 \`module-turn-harness\` 进入统一模块级入口。
2. 按 \`task-kind\` 分发当前 hook matrix。
3. 在当前阶段复用既有 post-module scripts，而不是重写全部能力。

### 4. 设计取舍

- 优先把“入口统一”落地，再继续推进结构化日志、runtime verify 与 docs lint。
- 当前 PRD gate 已切换为“product-goals 摘要优先 + 高风险全文兜底”。
- explanation/interview 已切换为 knowledge pack 策略触发，不再默认阻塞普通小回合。

### 5. 测试与验证

- 当前至少验证了 harness 自身参数分发与 dry-run 语义。
- 更完整的 runtime verify 与结构化执行日志属于后续阶段。

### 6. 风险与后续

- 当前 orchestrator 仍是“统一入口 + 复用既有脚本”的薄包装。
- 后续应继续补齐：runtime verify、knowledge pack 周期补写、CI 分层。
EOF_BODY
}

emit_commit_message_recommendation() {
  if [[ -n "$COMMIT_RECOMMENDATION_BLOCK" ]]; then
    printf '%s' "$COMMIT_RECOMMENDATION_BLOCK"
    return 0
  fi

  local script title
  script="$ROOT/skills/post-module-commit-message/scripts/recommend_commit_message.sh"
  if [[ -f "$script" ]]; then
    COMMIT_RECOMMENDATION_BLOCK="$(bash "$script" --root "$ROOT" --task-kind "$TASK_KIND" --module "$MODULE" --summary "$SUMMARY")"
    COMMIT_RECOMMENDATION_TITLE="$(printf '%s\n' "$COMMIT_RECOMMENDATION_BLOCK" | awk 'found == 1 && NF { print; exit } /^Recommended:$/ { found = 1 }')"
    if [[ -z "$COMMIT_RECOMMENDATION_TITLE" ]]; then
      COMMIT_RECOMMENDATION_TITLE="$(bash "$script" --root "$ROOT" --task-kind "$TASK_KIND" --module "$MODULE" --summary "$SUMMARY" --title-only)"
    fi
    printf '%s' "$COMMIT_RECOMMENDATION_BLOCK"
    return 0
  fi

  local type scope subject
  case "$TASK_KIND" in
    dev) type="feat" ;;
    refactor) type="refactor" ;;
    non-dev) type="docs" ;;
    *) type="chore" ;;
  esac

  scope="$(printf '%s' "$MODULE" | sed -E 's/[^a-zA-Z0-9]+/-/g; s/^-+//; s/-+$//')"
  scope="$(lower_ascii "$scope")"
  [[ -z "$scope" ]] && scope="repo"

  subject="advance ${scope} workflow"
  if [[ "$MODULE" == *"harness"* ]]; then
    subject="advance ${scope} orchestration"
  fi

  COMMIT_RECOMMENDATION_TITLE="$(printf '%s(%s): %s' "$type" "$scope" "$subject")"
  COMMIT_RECOMMENDATION_BLOCK="$(cat <<EOF_RECOMMEND
Recommended:
$COMMIT_RECOMMENDATION_TITLE

Alternatives:
1. $type: update $scope workflow
2. chore($scope): sync harness docs
EOF_RECOMMEND
)"

  printf '%s' "$COMMIT_RECOMMENDATION_BLOCK"
}

announce_commit_message_preview() {
  emit_commit_message_recommendation >/dev/null
  printf '\ncommit_message_preview:\n'
  printf 'recommended_commit_title: %s\n' "$COMMIT_RECOMMENDATION_TITLE"
  printf '%s\n' "$COMMIT_RECOMMENDATION_BLOCK"
}

run_interview_journal() {
  local changes="$1"
  local tests="${TEST_RESULTS:-（未提供验证信息）}"
  local script="$ROOT/skills/post-module-interview-journal/scripts/update_module_docs.sh"
  run_cmd \
    "post-interview-journal" \
    "更新 interview 文档" \
    "$ROOT/docs/interview/01-development-log.md;$ROOT/docs/interview/02-troubleshooting-log.md;$ROOT/docs/interview/03-interview-qa-log.md" \
    bash "$script" \
      --root "$ROOT" \
      --module "$MODULE" \
      --summary "$SUMMARY" \
      --changes "$changes" \
      --tests "$tests" \
      --issues "${ISSUES:-（当前回合无额外问题记录）}" \
      --learnings "${LEARNINGS:-module-turn-harness;task classification;post-hook orchestration}"
}

run_explanation_journal() {
  local changes="$1"
  local body_file
  body_file="$(mktemp)"
  build_explanation_body "$body_file" "$changes"
  local script="$ROOT/skills/post-module-explanation-journal/scripts/write_explanation_doc.sh"
  run_cmd \
    "post-explanation-journal" \
    "生成 explanation 文档" \
    "$ROOT/docs/explanation" \
    bash "$script" \
      --root "$ROOT" \
      --module "$MODULE" \
      --summary "$SUMMARY" \
      --changes "$changes" \
      --body-file "$body_file"
  rm -f "$body_file"
}

should_enable_knowledge_pack() {
  local context matched=""
  context="$(lower_ascii "$MODULE $SUMMARY ${ISSUES:-}")"

  if [[ "$KNOWLEDGE_PACK_MODE" == "force" ]]; then
    KNOWLEDGE_PACK_EFFECTIVE="run"
    KNOWLEDGE_PACK_REASON="显式指定 --knowledge-pack force"
    return 0
  fi

  if [[ "$KNOWLEDGE_PACK_MODE" == "skip" ]]; then
    KNOWLEDGE_PACK_EFFECTIVE="skip"
    KNOWLEDGE_PACK_REASON="显式指定 --knowledge-pack skip"
    return 1
  fi

  local security_keywords=(security auth signin sign-in signup sign-up login password token jwt session sms phone email oauth wechat permission role csrf secret wallet payment billing iap receipt recharge charge)
  local reliability_keywords=(reliability retry retention cleanup reconcile reconciliation consistency replay failover recovery incident outbox dlq queue backoff redis kafka durable)
  local architecture_keywords=(architecture boundary contract adapter orchestration harness migration service-boundary refactor)
  local cross_service_keywords=(cross-service websocket ws kafka redis notify analytics gateway integration bridge outbox)
  local release_keywords=(release preflight appstore review supply-chain sbom attestation allowlist chaos)

  if matched="$(match_first_keyword "$context" "${security_keywords[@]}")"; then
    KNOWLEDGE_PACK_EFFECTIVE="run"
    KNOWLEDGE_PACK_REASON="auto 命中 security 关键词: $matched"
    return 0
  elif matched="$(match_first_keyword "$context" "${reliability_keywords[@]}")"; then
    KNOWLEDGE_PACK_EFFECTIVE="run"
    KNOWLEDGE_PACK_REASON="auto 命中 reliability 关键词: $matched"
    return 0
  elif matched="$(match_first_keyword "$context" "${architecture_keywords[@]}")"; then
    KNOWLEDGE_PACK_EFFECTIVE="run"
    KNOWLEDGE_PACK_REASON="auto 命中 architecture 关键词: $matched"
    return 0
  elif matched="$(match_first_keyword "$context" "${cross_service_keywords[@]}")"; then
    KNOWLEDGE_PACK_EFFECTIVE="run"
    KNOWLEDGE_PACK_REASON="auto 命中 cross-service 关键词: $matched"
    return 0
  elif matched="$(match_first_keyword "$context" "${release_keywords[@]}")"; then
    KNOWLEDGE_PACK_EFFECTIVE="run"
    KNOWLEDGE_PACK_REASON="auto 命中 release 关键词: $matched"
    return 0
  elif [[ -n "${ISSUES:-}" && "${ISSUES:-}" != "（当前回合无额外问题记录）" && "${ISSUES:-}" == *"=>"* ]]; then
    KNOWLEDGE_PACK_EFFECTIVE="run"
    KNOWLEDGE_PACK_REASON="auto 命中复杂故障修复过程"
    return 0
  fi

  KNOWLEDGE_PACK_EFFECTIVE="skip"
  KNOWLEDGE_PACK_REASON="auto 判定为普通小回合，跳过 knowledge pack"
  return 1
}

record_knowledge_pack_decision() {
  local started_at finished_at status changes="$1"
  should_enable_knowledge_pack "$changes" || true
  step_header "knowledge-pack" "knowledge pack 决策"
  printf 'requested_mode: %s\n' "$KNOWLEDGE_PACK_MODE"
  printf 'effective_mode: %s\n' "$KNOWLEDGE_PACK_EFFECTIVE"
  printf 'reason: %s\n' "$KNOWLEDGE_PACK_REASON"
  started_at="$(iso_now)"
  finished_at="$(iso_now)"

  if [[ "$DRY_RUN" -eq 1 ]]; then
    status="dry_run"
  elif [[ "$KNOWLEDGE_PACK_EFFECTIVE" == "run" ]]; then
    status="pass"
  else
    status="skip"
  fi

  log_step_result "knowledge-pack" "knowledge pack 决策" "$status" "$started_at" "$finished_at" 0 "$ROOT/docs/interview;$ROOT/docs/explanation" "knowledge_pack_mode=$KNOWLEDGE_PACK_MODE"
}

run_knowledge_pack() {
  local changes="$1"
  record_knowledge_pack_decision "$changes"

  if [[ "$KNOWLEDGE_PACK_EFFECTIVE" != "run" ]]; then
    return 0
  fi

  run_interview_journal "$changes"
  run_explanation_journal "$changes"
}

record_commit_message_step() {
  local started_at finished_at
  started_at="$(iso_now)"
  step_header "post-commit-message" "Conventional Commits 推荐"
  emit_commit_message_recommendation
  printf '\n'
  finished_at="$(iso_now)"
  log_step_result "post-commit-message" "Conventional Commits 推荐" "$([[ "$DRY_RUN" -eq 1 ]] && echo dry_run || echo pass)" "$started_at" "$finished_at" 0 "$ROOT/skills/post-module-commit-message/SKILL.md" "post-module-commit-message recommend_commit_message.sh"
}

run_plan_sync() {
  local changes="$1"
  local effective_note effective_status effective_next_steps
  effective_note="${NOTE:-通过 module-turn-harness 统一当前模块级 hook 顺序；改动文件：${changes:-（未检测到改动文件）}}"
  effective_next_steps="${NEXT_STEPS:-继续补齐 current-plan pointer;继续补齐 docs lint;继续补齐 runtime verify}"
  effective_status="${STATUS_TEXT:-进行中（phase 已完成）}"

  if [[ "$TASK_KIND" == "dev" ]]; then
    local script="$ROOT/skills/post-module-plan-sync/scripts/post_module_plan_sync.sh"
    local cmd=( bash "$script" --root "$ROOT" --module "$MODULE" --summary "$SUMMARY" --priority "$PRIORITY" --status "$effective_status" --note "$effective_note" --next-steps "$effective_next_steps" )
    [[ -n "$PLAN" ]] && cmd+=( --plan "$PLAN" )
    [[ -n "$SLOT" ]] && cmd+=( --slot "$SLOT" )
    run_cmd "post-plan-sync" "同步开发计划文档" "$(resolve_plan_evidence_path || true)" "${cmd[@]}"
  elif [[ "$TASK_KIND" == "refactor" ]]; then
    local stage="${STAGE:-$MODULE}"
    local script="$ROOT/skills/post-optimization-plan-sync/scripts/post_optimization_plan_sync.sh"
    local cmd=( bash "$script" --root "$ROOT" --stage "$stage" --module "$MODULE" --summary "$SUMMARY" --status "done" )
    [[ -n "$PLAN" ]] && cmd+=( --plan "$PLAN" )
    [[ -n "$SLOT" ]] && cmd+=( --slot "$SLOT" )
    run_cmd "post-optimization-plan-sync" "同步优化计划文档" "$(resolve_plan_evidence_path || true)" "${cmd[@]}"
  fi
}

run_non_dev_mode() {
  step_header "non-dev" "轻量模式"
  printf 'task-kind: non-dev\n'
  printf 'module: %s\n' "$MODULE"
  printf 'summary: %s\n' "$SUMMARY"
  printf 'current_behavior: 不触发模块级 pre/post hooks，优先执行 docs lint 等轻量检查。\n'

  local lint_script="$ROOT/scripts/quality/harness_docs_lint.sh"
  if [[ -f "$lint_script" ]]; then
    local lint_json="$HARNESS_ARTIFACT_DIR/${HARNESS_RUN_ID}.docs-lint.json"
    local lint_md="$HARNESS_ARTIFACT_DIR/${HARNESS_RUN_ID}.docs-lint.md"
    run_cmd "docs-lint" "文档结构检查" "$lint_json;$lint_md" bash "$lint_script" --root "$ROOT" --json-out "$lint_json" --md-out "$lint_md"
  else
    printf 'docs_lint: 未找到 %s，跳过。\n' "$lint_script"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
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
    --plan)
      PLAN="$2"
      shift 2
      ;;
    --slot)
      SLOT="$2"
      shift 2
      ;;
    --prd-mode)
      PRD_MODE="$2"
      shift 2
      ;;
    --knowledge-pack)
      KNOWLEDGE_PACK_MODE="$2"
      shift 2
      ;;
    --stage)
      STAGE="$2"
      shift 2
      ;;
    --priority)
      PRIORITY="$2"
      shift 2
      ;;
    --status-text)
      STATUS_TEXT="$2"
      shift 2
      ;;
    --note)
      NOTE="$2"
      shift 2
      ;;
    --next-steps)
      NEXT_STEPS="$2"
      shift 2
      ;;
    --issues)
      ISSUES="$2"
      shift 2
      ;;
    --learnings)
      LEARNINGS="$2"
      shift 2
      ;;
    --root)
      ROOT="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --strict)
      STRICT=1
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

if [[ -z "$TASK_KIND" || -z "$MODULE" || -z "$SUMMARY" ]]; then
  echo "--task-kind、--module、--summary 为必填参数" >&2
  usage
  exit 1
fi

case "$TASK_KIND" in
  dev|refactor|non-dev) ;;
  *)
    echo "--task-kind 仅支持 dev|refactor|non-dev" >&2
    exit 1
    ;;
esac

case "$PRD_MODE" in
  auto|summary|full) ;;
  *)
    echo "--prd-mode 仅支持 auto|summary|full" >&2
    exit 1
    ;;
esac

case "$KNOWLEDGE_PACK_MODE" in
  auto|skip|force) ;;
  *)
    echo "--knowledge-pack 仅支持 auto|skip|force" >&2
    exit 1
    ;;
esac

resolve_root
PLAN="$(abs_path "$PLAN")"
FAILURES=0
FAILED_STEPS=""
TEST_RESULTS=""
init_harness_artifacts

printf 'module-turn-harness\n'
printf 'root: %s\n' "$ROOT"
printf 'task-kind: %s\n' "$TASK_KIND"
printf 'module: %s\n' "$MODULE"
printf 'summary: %s\n' "$SUMMARY"
if [[ -n "$SLOT" ]]; then
  printf 'slot: %s\n' "$SLOT"
fi
if [[ "$TASK_KIND" != "non-dev" ]]; then
  printf 'prd-mode: %s\n' "$PRD_MODE"
  printf 'knowledge-pack: %s\n' "$KNOWLEDGE_PACK_MODE"
fi
printf 'mode: %s%s\n' "$([[ "$DRY_RUN" -eq 1 ]] && echo dry-run || echo execute)" "$([[ "$STRICT" -eq 1 ]] && echo ' + strict' || true)"
printf 'artifact_jsonl: %s\n' "$HARNESS_JSONL"
printf 'artifact_summary_json: %s\n' "$HARNESS_SUMMARY_JSON"
printf 'artifact_summary_md: %s\n' "$HARNESS_SUMMARY_MD"
announce_commit_message_preview

if [[ "$TASK_KIND" == "non-dev" ]]; then
  run_non_dev_mode
  record_commit_message_step
  write_summary_files "$([[ "$DRY_RUN" -eq 1 ]] && echo dry_run || ([[ "$FAILURES" -eq 0 ]] && echo pass || echo fail))"
  exit "$([[ "$FAILURES" -eq 0 ]] && echo 0 || echo 1)"
fi

run_prd_gate
run_test_guard_chain
CHANGES_NOW="$(collect_changes)"
record_commit_message_step
run_plan_sync "$CHANGES_NOW"
run_knowledge_pack "$CHANGES_NOW"

printf '\nsummary:\n'
write_summary_files "$([[ "$DRY_RUN" -eq 1 ]] && echo dry_run || ([[ "$FAILURES" -eq 0 ]] && echo pass || echo fail))"
if [[ "$FAILURES" -eq 0 ]]; then
  printf 'status: pass\n'
  exit 0
fi

printf 'status: fail\n'
printf 'failed_steps: %s\n' "$(trim "$FAILED_STEPS")"
exit 1
