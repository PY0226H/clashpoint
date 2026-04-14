#!/usr/bin/env bash
set -euo pipefail

ROOT=""
EVIDENCE_DIR=""
ENV_MARKER=""
OUTPUT_DOC=""
OUTPUT_ENV=""
EMIT_JSON=""
EMIT_MD=""
RUN_ID=""
STARTED_AT=""
FINISHED_AT=""
STATUS="unknown"
ALLOW_LOCAL_REFERENCE="${AI_JUDGE_ALLOW_LOCAL_REFERENCE:-false}"

FAIRNESS_SCRIPT=""
RUNTIME_SLA_SCRIPT=""
REAL_ENV_CLOSURE_SCRIPT=""
STAGE_CLOSURE_EVIDENCE_SCRIPT=""
STAGE_CLOSURE_PLAN_DOC=""
STAGE_CLOSURE_DRAFT_SCRIPT=""

FAIRNESS_EXIT_CODE=0
RUNTIME_SLA_EXIT_CODE=0
REAL_ENV_CLOSURE_EXIT_CODE=0
STAGE_CLOSURE_EVIDENCE_EXIT_CODE=0

FAIRNESS_STATUS=""
RUNTIME_SLA_STATUS=""
REAL_ENV_CLOSURE_STATUS=""
STAGE_CLOSURE_EVIDENCE_STATUS=""

FAIRNESS_THRESHOLD_DECISION=""
RUNTIME_SLA_THRESHOLD_DECISION=""

usage() {
  cat <<'USAGE'
用法:
  ai_judge_runtime_ops_pack.sh \
    [--root <repo-root>] \
    [--evidence-dir <path>] \
    [--env-marker <path>] \
    [--allow-local-reference] \
    [--fairness-script <path>] \
    [--runtime-sla-script <path>] \
    [--real-env-closure-script <path>] \
    [--stage-closure-evidence-script <path>] \
    [--stage-closure-plan-doc <path>] \
    [--stage-closure-draft-script <path>] \
    [--output-doc <path>] \
    [--output-env <path>] \
    [--emit-json <path>] \
    [--emit-md <path>]

说明:
  - 一键执行 AI Judge runtime 收口包：
    1) fairness benchmark freeze
    2) runtime SLA freeze
    3) real-env evidence closure
    4) stage closure evidence（草案联动）
  - 产出统一 pack 摘要，固定输出到 docs/loadtest/evidence（可覆盖）。
  - 输出状态：
    pass/local_reference_ready/threshold_violation/pending_data/env_blocked/evidence_missing/stage_failed/mixed。
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

is_truthy() {
  local value
  value="$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]')"
  [[ "$value" == "1" || "$value" == "true" || "$value" == "yes" || "$value" == "on" ]]
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

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --root)
        ROOT="${2:-}"
        shift 2
        ;;
      --evidence-dir)
        EVIDENCE_DIR="${2:-}"
        shift 2
        ;;
      --env-marker)
        ENV_MARKER="${2:-}"
        shift 2
        ;;
      --allow-local-reference)
        ALLOW_LOCAL_REFERENCE="true"
        shift 1
        ;;
      --fairness-script)
        FAIRNESS_SCRIPT="${2:-}"
        shift 2
        ;;
      --runtime-sla-script)
        RUNTIME_SLA_SCRIPT="${2:-}"
        shift 2
        ;;
      --real-env-closure-script)
        REAL_ENV_CLOSURE_SCRIPT="${2:-}"
        shift 2
        ;;
      --stage-closure-evidence-script)
        STAGE_CLOSURE_EVIDENCE_SCRIPT="${2:-}"
        shift 2
        ;;
      --stage-closure-plan-doc)
        STAGE_CLOSURE_PLAN_DOC="${2:-}"
        shift 2
        ;;
      --stage-closure-draft-script)
        STAGE_CLOSURE_DRAFT_SCRIPT="${2:-}"
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

run_stage() {
  local stage="$1"
  local script="$2"
  local stage_json="$3"
  local stage_md="$4"
  local stage_stdout="$5"
  local stage_exit_var="$6"

  local -a cmd
  cmd=(bash "$script" --root "$ROOT" --emit-json "$stage_json" --emit-md "$stage_md")
  if [[ "$stage" == "real_env_closure" ]]; then
    cmd+=(--evidence-dir "$EVIDENCE_DIR")
  fi
  if [[ "$stage" == "stage_closure_evidence" ]]; then
    cmd+=(--evidence-dir "$EVIDENCE_DIR" --plan-doc "$STAGE_CLOSURE_PLAN_DOC" --draft-script "$STAGE_CLOSURE_DRAFT_SCRIPT" --runtime-ops-env "$OUTPUT_ENV" --runtime-ops-doc "$OUTPUT_DOC")
  fi
  if [[ "$ALLOW_LOCAL_REFERENCE" == "true" && "$stage" != "stage_closure_evidence" ]]; then
    cmd+=(--allow-local-reference)
  fi

  if "${cmd[@]}" >"$stage_stdout" 2>&1; then
    printf -v "$stage_exit_var" '%s' "0"
  else
    local code="$?"
    printf -v "$stage_exit_var" '%s' "$code"
  fi
}

is_in_set() {
  local value="$1"
  shift
  local item
  for item in "$@"; do
    if [[ "$value" == "$item" ]]; then
      return 0
    fi
  done
  return 1
}

derive_pack_status() {
  if [[ "$FAIRNESS_EXIT_CODE" != "0" || "$RUNTIME_SLA_EXIT_CODE" != "0" || "$REAL_ENV_CLOSURE_EXIT_CODE" != "0" || "$STAGE_CLOSURE_EVIDENCE_EXIT_CODE" != "0" ]]; then
    STATUS="stage_failed"
    return
  fi

  local -a statuses
  statuses=("$FAIRNESS_STATUS" "$RUNTIME_SLA_STATUS" "$REAL_ENV_CLOSURE_STATUS" "$STAGE_CLOSURE_EVIDENCE_STATUS")

  local status
  for status in "${statuses[@]}"; do
    if [[ -z "$status" || "$status" == "unknown" ]]; then
      STATUS="mixed"
      return
    fi
  done

  for status in "${statuses[@]}"; do
    if [[ "$status" == "threshold_violation" ]]; then
      STATUS="threshold_violation"
      return
    fi
  done
  for status in "${statuses[@]}"; do
    if [[ "$status" == "evidence_missing" ]]; then
      STATUS="evidence_missing"
      return
    fi
  done
  for status in "${statuses[@]}"; do
    if [[ "$status" == "env_blocked" ]]; then
      STATUS="env_blocked"
      return
    fi
  done
  for status in "${statuses[@]}"; do
    if is_in_set "$status" "pending_data" "pending_real_evidence" "local_reference_pending"; then
      STATUS="pending_data"
      return
    fi
  done

  if [[ "$FAIRNESS_STATUS" == "pass" && "$RUNTIME_SLA_STATUS" == "pass" && "$REAL_ENV_CLOSURE_STATUS" == "pass" ]]; then
    STATUS="pass"
    return
  fi

  local all_local_or_pass="true"
  local has_local="false"
  for status in "${statuses[@]}"; do
    if is_in_set "$status" "local_reference_frozen" "local_reference_ready"; then
      has_local="true"
      continue
    fi
    if [[ "$status" == "pass" ]]; then
      continue
    fi
    all_local_or_pass="false"
    break
  done
  if [[ "$all_local_or_pass" == "true" && "$has_local" == "true" ]]; then
    STATUS="local_reference_ready"
    return
  fi

  STATUS="mixed"
}

write_output_env() {
  local marker_ready local_ready env_mode
  marker_ready="false"
  local_ready="false"
  env_mode=""
  if [[ -f "$ENV_MARKER" ]]; then
    marker_ready="$(trim "$(read_env_value "$ENV_MARKER" "REAL_CALIBRATION_ENV_READY")")"
    local_ready="$(trim "$(read_env_value "$ENV_MARKER" "LOCAL_REFERENCE_ENV_READY")")"
    env_mode="$(trim "$(read_env_value "$ENV_MARKER" "CALIBRATION_ENV_MODE")")"
  fi
  if is_truthy "$marker_ready"; then
    marker_ready="true"
  else
    marker_ready="false"
  fi
  if is_truthy "$local_ready"; then
    local_ready="true"
  else
    local_ready="false"
  fi

  cat >"$OUTPUT_ENV" <<EOF_ENV
AI_JUDGE_RUNTIME_OPS_PACK_STATUS=$STATUS
UPDATED_AT=$FINISHED_AT
RUN_ID=$RUN_ID
ALLOW_LOCAL_REFERENCE=$ALLOW_LOCAL_REFERENCE
ENVIRONMENT_MODE=$env_mode
REAL_CALIBRATION_ENV_READY=$marker_ready
LOCAL_REFERENCE_ENV_READY=$local_ready
FAIRNESS_STATUS=$FAIRNESS_STATUS
RUNTIME_SLA_STATUS=$RUNTIME_SLA_STATUS
REAL_ENV_CLOSURE_STATUS=$REAL_ENV_CLOSURE_STATUS
STAGE_CLOSURE_EVIDENCE_STATUS=$STAGE_CLOSURE_EVIDENCE_STATUS
FAIRNESS_THRESHOLD_DECISION=$FAIRNESS_THRESHOLD_DECISION
RUNTIME_SLA_THRESHOLD_DECISION=$RUNTIME_SLA_THRESHOLD_DECISION
FAIRNESS_EXIT_CODE=$FAIRNESS_EXIT_CODE
RUNTIME_SLA_EXIT_CODE=$RUNTIME_SLA_EXIT_CODE
REAL_ENV_CLOSURE_EXIT_CODE=$REAL_ENV_CLOSURE_EXIT_CODE
STAGE_CLOSURE_EVIDENCE_EXIT_CODE=$STAGE_CLOSURE_EVIDENCE_EXIT_CODE
EOF_ENV
}

write_output_doc() {
  cat >"$OUTPUT_DOC" <<EOF_MD
# AI Judge Runtime Ops Pack 收口摘要

1. 生成日期：$(date_cn)
2. 运行窗口：$STARTED_AT -> $FINISHED_AT
3. 统一状态：\`$STATUS\`
4. allow_local_reference：\`$ALLOW_LOCAL_REFERENCE\`
5. evidence_dir：\`$EVIDENCE_DIR\`

## 子模块状态

| 子模块 | 状态 | 阈值决策 | 退出码 |
| --- | --- | --- | --- |
| fairness benchmark freeze | \`$FAIRNESS_STATUS\` | \`$FAIRNESS_THRESHOLD_DECISION\` | \`$FAIRNESS_EXIT_CODE\` |
| runtime SLA freeze | \`$RUNTIME_SLA_STATUS\` | \`$RUNTIME_SLA_THRESHOLD_DECISION\` | \`$RUNTIME_SLA_EXIT_CODE\` |
| real-env evidence closure | \`$REAL_ENV_CLOSURE_STATUS\` | \`-\` | \`$REAL_ENV_CLOSURE_EXIT_CODE\` |
| stage closure evidence | \`$STAGE_CLOSURE_EVIDENCE_STATUS\` | \`-\` | \`$STAGE_CLOSURE_EVIDENCE_EXIT_CODE\` |

## 输出工件

1. pack env: \`$OUTPUT_ENV\`
2. pack doc: \`$OUTPUT_DOC\`
3. pack json: \`$EMIT_JSON\`
4. pack md: \`$EMIT_MD\`
EOF_MD
}

write_json_summary() {
  cat >"$EMIT_JSON" <<EOF_JSON
{
  "module": "ai-judge-runtime-ops-pack",
  "status": "$(json_escape "$STATUS")",
  "run_id": "$(json_escape "$RUN_ID")",
  "started_at": "$(json_escape "$STARTED_AT")",
  "finished_at": "$(json_escape "$FINISHED_AT")",
  "allow_local_reference": "$(json_escape "$ALLOW_LOCAL_REFERENCE")",
  "evidence_dir": "$(json_escape "$EVIDENCE_DIR")",
  "stages": [
    {
      "stage": "fairness_benchmark_freeze",
      "status": "$(json_escape "$FAIRNESS_STATUS")",
      "threshold_decision": "$(json_escape "$FAIRNESS_THRESHOLD_DECISION")",
      "exit_code": $FAIRNESS_EXIT_CODE
    },
    {
      "stage": "runtime_sla_freeze",
      "status": "$(json_escape "$RUNTIME_SLA_STATUS")",
      "threshold_decision": "$(json_escape "$RUNTIME_SLA_THRESHOLD_DECISION")",
      "exit_code": $RUNTIME_SLA_EXIT_CODE
    },
    {
      "stage": "real_env_evidence_closure",
      "status": "$(json_escape "$REAL_ENV_CLOSURE_STATUS")",
      "threshold_decision": "",
      "exit_code": $REAL_ENV_CLOSURE_EXIT_CODE
    },
    {
      "stage": "stage_closure_evidence",
      "status": "$(json_escape "$STAGE_CLOSURE_EVIDENCE_STATUS")",
      "threshold_decision": "",
      "exit_code": $STAGE_CLOSURE_EVIDENCE_EXIT_CODE
    }
  ]
}
EOF_JSON
}

write_md_summary() {
  cat >"$EMIT_MD" <<EOF_MD
# ai-judge-runtime-ops-pack

- status: \`$STATUS\`
- run_id: \`$RUN_ID\`
- started_at: \`$STARTED_AT\`
- finished_at: \`$FINISHED_AT\`
- allow_local_reference: \`$ALLOW_LOCAL_REFERENCE\`
- evidence_dir: \`$EVIDENCE_DIR\`

## stages

1. fairness_benchmark_freeze: \`$FAIRNESS_STATUS\` (threshold=\`$FAIRNESS_THRESHOLD_DECISION\`, exit=\`$FAIRNESS_EXIT_CODE\`)
2. runtime_sla_freeze: \`$RUNTIME_SLA_STATUS\` (threshold=\`$RUNTIME_SLA_THRESHOLD_DECISION\`, exit=\`$RUNTIME_SLA_EXIT_CODE\`)
3. real_env_evidence_closure: \`$REAL_ENV_CLOSURE_STATUS\` (exit=\`$REAL_ENV_CLOSURE_EXIT_CODE\`)
4. stage_closure_evidence: \`$STAGE_CLOSURE_EVIDENCE_STATUS\` (exit=\`$STAGE_CLOSURE_EVIDENCE_EXIT_CODE\`)
EOF_MD
}

main() {
  parse_args "$@"
  resolve_root

  if [[ -z "$EVIDENCE_DIR" ]]; then
    EVIDENCE_DIR="$ROOT/docs/loadtest/evidence"
  else
    EVIDENCE_DIR="$(abs_path "$EVIDENCE_DIR")"
  fi
  if [[ -z "$ENV_MARKER" ]]; then
    ENV_MARKER="$EVIDENCE_DIR/ai_judge_p5_real_env.env"
  else
    ENV_MARKER="$(abs_path "$ENV_MARKER")"
  fi
  if [[ -z "$OUTPUT_DOC" ]]; then
    OUTPUT_DOC="$EVIDENCE_DIR/ai_judge_runtime_ops_pack.md"
  else
    OUTPUT_DOC="$(abs_path "$OUTPUT_DOC")"
  fi
  if [[ -z "$OUTPUT_ENV" ]]; then
    OUTPUT_ENV="$EVIDENCE_DIR/ai_judge_runtime_ops_pack.env"
  else
    OUTPUT_ENV="$(abs_path "$OUTPUT_ENV")"
  fi

  if [[ -z "$FAIRNESS_SCRIPT" ]]; then
    FAIRNESS_SCRIPT="$ROOT/scripts/harness/ai_judge_fairness_benchmark_freeze.sh"
  else
    FAIRNESS_SCRIPT="$(abs_path "$FAIRNESS_SCRIPT")"
  fi
  if [[ -z "$RUNTIME_SLA_SCRIPT" ]]; then
    RUNTIME_SLA_SCRIPT="$ROOT/scripts/harness/ai_judge_runtime_sla_freeze.sh"
  else
    RUNTIME_SLA_SCRIPT="$(abs_path "$RUNTIME_SLA_SCRIPT")"
  fi
  if [[ -z "$REAL_ENV_CLOSURE_SCRIPT" ]]; then
    REAL_ENV_CLOSURE_SCRIPT="$ROOT/scripts/harness/ai_judge_real_env_evidence_closure.sh"
  else
    REAL_ENV_CLOSURE_SCRIPT="$(abs_path "$REAL_ENV_CLOSURE_SCRIPT")"
  fi
  if [[ -z "$STAGE_CLOSURE_EVIDENCE_SCRIPT" ]]; then
    STAGE_CLOSURE_EVIDENCE_SCRIPT="$ROOT/scripts/harness/ai_judge_stage_closure_evidence.sh"
  else
    STAGE_CLOSURE_EVIDENCE_SCRIPT="$(abs_path "$STAGE_CLOSURE_EVIDENCE_SCRIPT")"
  fi
  if [[ -z "$STAGE_CLOSURE_PLAN_DOC" ]]; then
    STAGE_CLOSURE_PLAN_DOC="$ROOT/docs/dev_plan/当前开发计划.md"
  else
    STAGE_CLOSURE_PLAN_DOC="$(abs_path "$STAGE_CLOSURE_PLAN_DOC")"
  fi
  if [[ -z "$STAGE_CLOSURE_DRAFT_SCRIPT" ]]; then
    STAGE_CLOSURE_DRAFT_SCRIPT="$ROOT/scripts/harness/ai_judge_stage_closure_draft.sh"
  else
    STAGE_CLOSURE_DRAFT_SCRIPT="$(abs_path "$STAGE_CLOSURE_DRAFT_SCRIPT")"
  fi

  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ai-judge-runtime-ops-pack"
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

  local fairness_stdout runtime_stdout closure_stdout
  fairness_stdout="$run_dir/fairness.stdout.log"
  runtime_stdout="$run_dir/runtime_sla.stdout.log"
  closure_stdout="$run_dir/real_env_closure.stdout.log"

  run_stage \
    "fairness" \
    "$FAIRNESS_SCRIPT" \
    "$run_dir/fairness.summary.json" \
    "$run_dir/fairness.summary.md" \
    "$fairness_stdout" \
    "FAIRNESS_EXIT_CODE"
  run_stage \
    "runtime_sla" \
    "$RUNTIME_SLA_SCRIPT" \
    "$run_dir/runtime_sla.summary.json" \
    "$run_dir/runtime_sla.summary.md" \
    "$runtime_stdout" \
    "RUNTIME_SLA_EXIT_CODE"
  run_stage \
    "real_env_closure" \
    "$REAL_ENV_CLOSURE_SCRIPT" \
    "$run_dir/real_env_closure.summary.json" \
    "$run_dir/real_env_closure.summary.md" \
    "$closure_stdout" \
    "REAL_ENV_CLOSURE_EXIT_CODE"

  local fairness_env runtime_env closure_env
  fairness_env="$EVIDENCE_DIR/ai_judge_fairness_benchmark_thresholds.env"
  runtime_env="$EVIDENCE_DIR/ai_judge_runtime_sla_thresholds.env"
  closure_env="$EVIDENCE_DIR/ai_judge_p5_real_env_closure.env"

  FAIRNESS_STATUS="$(trim "$(read_env_value "$fairness_env" "FAIRNESS_BENCHMARK_FREEZE_STATUS")")"
  RUNTIME_SLA_STATUS="$(trim "$(read_env_value "$runtime_env" "RUNTIME_SLA_FREEZE_STATUS")")"
  REAL_ENV_CLOSURE_STATUS="$(trim "$(read_env_value "$closure_env" "AI_JUDGE_REAL_ENV_CLOSURE_STATUS")")"
  FAIRNESS_THRESHOLD_DECISION="$(trim "$(read_env_value "$fairness_env" "THRESHOLD_DECISION")")"
  RUNTIME_SLA_THRESHOLD_DECISION="$(trim "$(read_env_value "$runtime_env" "THRESHOLD_DECISION")")"

  if [[ -z "$FAIRNESS_STATUS" ]]; then
    FAIRNESS_STATUS="unknown"
  fi
  if [[ -z "$RUNTIME_SLA_STATUS" ]]; then
    RUNTIME_SLA_STATUS="unknown"
  fi
  if [[ -z "$REAL_ENV_CLOSURE_STATUS" ]]; then
    REAL_ENV_CLOSURE_STATUS="unknown"
  fi

  # 先基于前三阶段生成 pack 快照，供 stage closure evidence 回读关联。
  STAGE_CLOSURE_EVIDENCE_STATUS="pass"
  STAGE_CLOSURE_EVIDENCE_EXIT_CODE=0
  derive_pack_status
  FINISHED_AT="$(iso_now)"
  write_output_env
  write_output_doc

  local stage_closure_stdout
  stage_closure_stdout="$run_dir/stage_closure_evidence.stdout.log"
  run_stage \
    "stage_closure_evidence" \
    "$STAGE_CLOSURE_EVIDENCE_SCRIPT" \
    "$run_dir/stage_closure_evidence.summary.json" \
    "$run_dir/stage_closure_evidence.summary.md" \
    "$stage_closure_stdout" \
    "STAGE_CLOSURE_EVIDENCE_EXIT_CODE"

  local stage_closure_env
  stage_closure_env="$EVIDENCE_DIR/ai_judge_stage_closure_evidence.env"
  STAGE_CLOSURE_EVIDENCE_STATUS="$(trim "$(read_env_value "$stage_closure_env" "AI_JUDGE_STAGE_CLOSURE_EVIDENCE_STATUS")")"
  if [[ -z "$STAGE_CLOSURE_EVIDENCE_STATUS" ]]; then
    if [[ "$STAGE_CLOSURE_EVIDENCE_EXIT_CODE" == "0" ]]; then
      STAGE_CLOSURE_EVIDENCE_STATUS="pass"
    else
      STAGE_CLOSURE_EVIDENCE_STATUS="stage_failed"
    fi
  fi

  derive_pack_status
  FINISHED_AT="$(iso_now)"
  write_output_env
  write_output_doc
  write_json_summary
  write_md_summary

  echo "ai_judge_runtime_ops_pack_status: $STATUS"
  echo "fairness_status: $FAIRNESS_STATUS (exit=$FAIRNESS_EXIT_CODE)"
  echo "runtime_sla_status: $RUNTIME_SLA_STATUS (exit=$RUNTIME_SLA_EXIT_CODE)"
  echo "real_env_closure_status: $REAL_ENV_CLOSURE_STATUS (exit=$REAL_ENV_CLOSURE_EXIT_CODE)"
  echo "stage_closure_evidence_status: $STAGE_CLOSURE_EVIDENCE_STATUS (exit=$STAGE_CLOSURE_EVIDENCE_EXIT_CODE)"
  echo "allow_local_reference: $ALLOW_LOCAL_REFERENCE"
  echo "output_env: $OUTPUT_ENV"
  echo "output_doc: $OUTPUT_DOC"
  echo "summary_json: $EMIT_JSON"
  echo "summary_md: $EMIT_MD"
}

main "$@"
