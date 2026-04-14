#!/usr/bin/env bash
set -euo pipefail

ROOT=""
PLAN_DOC=""
EVIDENCE_DIR=""
DRAFT_SCRIPT=""
RUNTIME_OPS_ENV=""
RUNTIME_OPS_DOC=""
OUTPUT_DOC=""
OUTPUT_ENV=""
EMIT_JSON=""
EMIT_MD=""
RUN_ID=""
STARTED_AT=""
FINISHED_AT=""
STATUS="unknown"

DRAFT_EXIT_CODE=0
DRAFT_STATUS="unknown"
DRAFT_COMPLETED_TOTAL=0
DRAFT_TODO_TOTAL=0
DRAFT_SUMMARY_JSON=""
DRAFT_SUMMARY_MD=""

RUNTIME_OPS_PACK_LINKED="false"
RUNTIME_OPS_PACK_STATUS="unknown"

usage() {
  cat <<'USAGE'
用法:
  ai_judge_stage_closure_evidence.sh \
    [--root <repo-root>] \
    [--plan-doc <path>] \
    [--evidence-dir <path>] \
    [--draft-script <path>] \
    [--runtime-ops-env <path>] \
    [--runtime-ops-doc <path>] \
    [--output-doc <path>] \
    [--output-env <path>] \
    [--emit-json <path>] \
    [--emit-md <path>]

说明:
  - 生成 AI judge 阶段收口证据摘要：
    1) 执行 stage closure draft 并抽取 completed/todo 候选统计
    2) 检查 runtime ops pack 证据是否已就绪并建立关联
  - 输出状态：
    pass/pending_data/evidence_missing/stage_failed
USAGE
}

iso_now() {
  date -u +"%Y-%m-%dT%H:%M:%SZ"
}

date_cn() {
  date -u +"%Y-%m-%d"
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

read_env_value() {
  local file="$1"
  local key="$2"
  local line
  line="$(grep -E "^${key}=" "$file" | head -n 1 || true)"
  if [[ -z "$line" ]]; then
    printf '%s' ""
    return
  fi
  printf '%s' "${line#*=}"
}

read_json_number() {
  local file="$1"
  local key="$2"
  local raw
  raw="$(grep -E "\"${key}\"[[:space:]]*:[[:space:]]*[0-9]+" "$file" | head -n 1 || true)"
  if [[ -z "$raw" ]]; then
    printf '0'
    return
  fi
  printf '%s' "$raw" | sed -E "s/.*\"${key}\"[[:space:]]*:[[:space:]]*([0-9]+).*/\\1/"
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
      --evidence-dir)
        EVIDENCE_DIR="${2:-}"
        shift 2
        ;;
      --draft-script)
        DRAFT_SCRIPT="${2:-}"
        shift 2
        ;;
      --runtime-ops-env)
        RUNTIME_OPS_ENV="${2:-}"
        shift 2
        ;;
      --runtime-ops-doc)
        RUNTIME_OPS_DOC="${2:-}"
        shift 2
        ;;
      --output-doc)
        OUTPUT_DOC="${2:-}"
        shift 2
        ;;
      --output-env)
        OUTPUT_ENV="${2:-}"
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

run_draft_stage() {
  local run_dir="$1"
  local draft_stdout="$run_dir/stage_closure_draft.stdout.log"

  DRAFT_SUMMARY_JSON="$run_dir/stage_closure_draft.summary.json"
  DRAFT_SUMMARY_MD="$run_dir/stage_closure_draft.summary.md"

  local -a cmd
  cmd=(
    bash "$DRAFT_SCRIPT"
    --root "$ROOT"
    --plan-doc "$PLAN_DOC"
    --emit-json "$DRAFT_SUMMARY_JSON"
    --emit-md "$DRAFT_SUMMARY_MD"
  )

  if "${cmd[@]}" >"$draft_stdout" 2>&1; then
    DRAFT_EXIT_CODE=0
  else
    DRAFT_EXIT_CODE="$?"
  fi

  DRAFT_STATUS="$(grep -E '^ai_judge_stage_closure_draft_status:' "$draft_stdout" | tail -n 1 | awk -F ':' '{print $2}' || true)"
  DRAFT_STATUS="$(trim "$DRAFT_STATUS")"
  if [[ -z "$DRAFT_STATUS" ]]; then
    if [[ "$DRAFT_EXIT_CODE" == "0" ]]; then
      DRAFT_STATUS="pass"
    else
      DRAFT_STATUS="stage_failed"
    fi
  fi

  if [[ -f "$DRAFT_SUMMARY_JSON" ]]; then
    DRAFT_COMPLETED_TOTAL="$(read_json_number "$DRAFT_SUMMARY_JSON" "completed_candidates_total")"
    DRAFT_TODO_TOTAL="$(read_json_number "$DRAFT_SUMMARY_JSON" "todo_candidates_total")"
  else
    DRAFT_COMPLETED_TOTAL=0
    DRAFT_TODO_TOTAL=0
  fi
}

detect_runtime_ops_link() {
  if [[ -f "$RUNTIME_OPS_ENV" && -f "$RUNTIME_OPS_DOC" ]]; then
    RUNTIME_OPS_PACK_LINKED="true"
    RUNTIME_OPS_PACK_STATUS="$(trim "$(read_env_value "$RUNTIME_OPS_ENV" "AI_JUDGE_RUNTIME_OPS_PACK_STATUS")")"
    if [[ -z "$RUNTIME_OPS_PACK_STATUS" ]]; then
      RUNTIME_OPS_PACK_STATUS="unknown"
    fi
  else
    RUNTIME_OPS_PACK_LINKED="false"
    RUNTIME_OPS_PACK_STATUS="unknown"
  fi
}

derive_status() {
  if [[ "$DRAFT_EXIT_CODE" != "0" || "$DRAFT_STATUS" != "pass" ]]; then
    STATUS="stage_failed"
    return
  fi

  if [[ "$DRAFT_COMPLETED_TOTAL" == "0" && "$DRAFT_TODO_TOTAL" == "0" ]]; then
    STATUS="evidence_missing"
    return
  fi

  if [[ "$RUNTIME_OPS_PACK_LINKED" != "true" || "$RUNTIME_OPS_PACK_STATUS" == "unknown" ]]; then
    STATUS="pending_data"
    return
  fi

  STATUS="pass"
}

write_output_env() {
  cat >"$OUTPUT_ENV" <<EOF_ENV
AI_JUDGE_STAGE_CLOSURE_EVIDENCE_STATUS=$STATUS
UPDATED_AT=$FINISHED_AT
RUN_ID=$RUN_ID
PLAN_DOC=$PLAN_DOC
DRAFT_STATUS=$DRAFT_STATUS
DRAFT_EXIT_CODE=$DRAFT_EXIT_CODE
DRAFT_COMPLETED_CANDIDATES=$DRAFT_COMPLETED_TOTAL
DRAFT_TODO_CANDIDATES=$DRAFT_TODO_TOTAL
DRAFT_SUMMARY_JSON=$DRAFT_SUMMARY_JSON
DRAFT_SUMMARY_MD=$DRAFT_SUMMARY_MD
RUNTIME_OPS_PACK_LINKED=$RUNTIME_OPS_PACK_LINKED
RUNTIME_OPS_PACK_STATUS=$RUNTIME_OPS_PACK_STATUS
RUNTIME_OPS_PACK_ENV=$RUNTIME_OPS_ENV
RUNTIME_OPS_PACK_DOC=$RUNTIME_OPS_DOC
EOF_ENV
}

write_output_doc() {
  cat >"$OUTPUT_DOC" <<EOF_MD
# AI Judge Stage Closure Evidence 摘要

1. 生成日期：$(date_cn)
2. 运行窗口：$STARTED_AT -> $FINISHED_AT
3. 统一状态：\`$STATUS\`
4. plan_doc：\`$PLAN_DOC\`
5. draft_script：\`$DRAFT_SCRIPT\`

## 收口草案统计

1. draft_status：\`$DRAFT_STATUS\`
2. completed_candidates_total：\`$DRAFT_COMPLETED_TOTAL\`
3. todo_candidates_total：\`$DRAFT_TODO_TOTAL\`
4. draft_summary_json：\`$DRAFT_SUMMARY_JSON\`
5. draft_summary_md：\`$DRAFT_SUMMARY_MD\`

## runtime ops pack 关联

1. runtime_ops_pack_linked：\`$RUNTIME_OPS_PACK_LINKED\`
2. runtime_ops_pack_status：\`$RUNTIME_OPS_PACK_STATUS\`
3. runtime_ops_pack_env：\`$RUNTIME_OPS_ENV\`
4. runtime_ops_pack_doc：\`$RUNTIME_OPS_DOC\`

## 输出工件

1. stage closure env：\`$OUTPUT_ENV\`
2. stage closure doc：\`$OUTPUT_DOC\`
3. summary json：\`$EMIT_JSON\`
4. summary md：\`$EMIT_MD\`
EOF_MD
}

write_json_summary() {
  cat >"$EMIT_JSON" <<EOF_JSON
{
  "module": "ai-judge-stage-closure-evidence",
  "status": "$(json_escape "$STATUS")",
  "run_id": "$(json_escape "$RUN_ID")",
  "started_at": "$(json_escape "$STARTED_AT")",
  "finished_at": "$(json_escape "$FINISHED_AT")",
  "plan_doc": "$(json_escape "$PLAN_DOC")",
  "draft": {
    "status": "$(json_escape "$DRAFT_STATUS")",
    "exit_code": $DRAFT_EXIT_CODE,
    "completed_candidates_total": $DRAFT_COMPLETED_TOTAL,
    "todo_candidates_total": $DRAFT_TODO_TOTAL,
    "summary_json": "$(json_escape "$DRAFT_SUMMARY_JSON")",
    "summary_md": "$(json_escape "$DRAFT_SUMMARY_MD")"
  },
  "runtime_ops_pack": {
    "linked": $([[ "$RUNTIME_OPS_PACK_LINKED" == "true" ]] && echo "true" || echo "false"),
    "status": "$(json_escape "$RUNTIME_OPS_PACK_STATUS")",
    "env": "$(json_escape "$RUNTIME_OPS_ENV")",
    "doc": "$(json_escape "$RUNTIME_OPS_DOC")"
  },
  "outputs": {
    "output_env": "$(json_escape "$OUTPUT_ENV")",
    "output_doc": "$(json_escape "$OUTPUT_DOC")",
    "summary_json": "$(json_escape "$EMIT_JSON")",
    "summary_md": "$(json_escape "$EMIT_MD")"
  }
}
EOF_JSON
}

write_md_summary() {
  cat >"$EMIT_MD" <<EOF_MD
# ai-judge-stage-closure-evidence

- status: \`$STATUS\`
- run_id: \`$RUN_ID\`
- started_at: \`$STARTED_AT\`
- finished_at: \`$FINISHED_AT\`
- plan_doc: \`$PLAN_DOC\`

## draft

1. status: \`$DRAFT_STATUS\`
2. completed_candidates_total: \`$DRAFT_COMPLETED_TOTAL\`
3. todo_candidates_total: \`$DRAFT_TODO_TOTAL\`
4. summary_json: \`$DRAFT_SUMMARY_JSON\`
5. summary_md: \`$DRAFT_SUMMARY_MD\`

## runtime_ops_pack

1. linked: \`$RUNTIME_OPS_PACK_LINKED\`
2. status: \`$RUNTIME_OPS_PACK_STATUS\`
3. env: \`$RUNTIME_OPS_ENV\`
4. doc: \`$RUNTIME_OPS_DOC\`
EOF_MD
}

main() {
  parse_args "$@"
  resolve_root

  if [[ -z "$PLAN_DOC" ]]; then
    PLAN_DOC="$ROOT/docs/dev_plan/当前开发计划.md"
  else
    PLAN_DOC="$(abs_path "$PLAN_DOC")"
  fi
  if [[ -z "$EVIDENCE_DIR" ]]; then
    EVIDENCE_DIR="$ROOT/docs/loadtest/evidence"
  else
    EVIDENCE_DIR="$(abs_path "$EVIDENCE_DIR")"
  fi
  if [[ -z "$DRAFT_SCRIPT" ]]; then
    DRAFT_SCRIPT="$ROOT/scripts/harness/ai_judge_stage_closure_draft.sh"
  else
    DRAFT_SCRIPT="$(abs_path "$DRAFT_SCRIPT")"
  fi
  if [[ -z "$RUNTIME_OPS_ENV" ]]; then
    RUNTIME_OPS_ENV="$EVIDENCE_DIR/ai_judge_runtime_ops_pack.env"
  else
    RUNTIME_OPS_ENV="$(abs_path "$RUNTIME_OPS_ENV")"
  fi
  if [[ -z "$RUNTIME_OPS_DOC" ]]; then
    RUNTIME_OPS_DOC="$EVIDENCE_DIR/ai_judge_runtime_ops_pack.md"
  else
    RUNTIME_OPS_DOC="$(abs_path "$RUNTIME_OPS_DOC")"
  fi
  if [[ -z "$OUTPUT_DOC" ]]; then
    OUTPUT_DOC="$EVIDENCE_DIR/ai_judge_stage_closure_evidence.md"
  else
    OUTPUT_DOC="$(abs_path "$OUTPUT_DOC")"
  fi
  if [[ -z "$OUTPUT_ENV" ]]; then
    OUTPUT_ENV="$EVIDENCE_DIR/ai_judge_stage_closure_evidence.env"
  else
    OUTPUT_ENV="$(abs_path "$OUTPUT_ENV")"
  fi

  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ai-judge-stage-closure-evidence"
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

  local run_dir
  run_dir="$ROOT/artifacts/harness/$RUN_ID"
  mkdir -p "$run_dir"
  ensure_parent_dir "$OUTPUT_DOC"
  ensure_parent_dir "$OUTPUT_ENV"
  ensure_parent_dir "$EMIT_JSON"
  ensure_parent_dir "$EMIT_MD"

  if [[ ! -f "$PLAN_DOC" ]]; then
    echo "计划文档不存在: $PLAN_DOC" >&2
    exit 1
  fi
  if [[ ! -x "$DRAFT_SCRIPT" ]]; then
    echo "stage closure draft 脚本不可执行: $DRAFT_SCRIPT" >&2
    exit 1
  fi

  run_draft_stage "$run_dir"
  detect_runtime_ops_link
  derive_status

  FINISHED_AT="$(iso_now)"
  write_output_env
  write_output_doc
  write_json_summary
  write_md_summary

  echo "ai_judge_stage_closure_evidence_status: $STATUS"
  echo "draft_status: $DRAFT_STATUS (exit=$DRAFT_EXIT_CODE)"
  echo "draft_completed_candidates: $DRAFT_COMPLETED_TOTAL"
  echo "draft_todo_candidates: $DRAFT_TODO_TOTAL"
  echo "runtime_ops_pack_linked: $RUNTIME_OPS_PACK_LINKED"
  echo "runtime_ops_pack_status: $RUNTIME_OPS_PACK_STATUS"
  echo "output_env: $OUTPUT_ENV"
  echo "output_doc: $OUTPUT_DOC"
  echo "summary_json: $EMIT_JSON"
  echo "summary_md: $EMIT_MD"
}

main "$@"
