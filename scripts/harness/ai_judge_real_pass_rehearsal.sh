#!/usr/bin/env bash
set -euo pipefail

ROOT=""
WORKSPACE_ROOT=""
OUTPUT_DOC=""
OUTPUT_ENV=""
EMIT_JSON=""
EMIT_MD=""
RUN_ID=""
STARTED_AT=""
FINISHED_AT=""
STATUS="unknown"

WINDOW_EXIT_CODE=0
WINDOW_STATUS="unknown"
WINDOW_REAL_PASS_READY="false"
WINDOW_REAL_PASS_BLOCKER_CODES=""
WINDOW_REAL_PASS_BLOCKER_HINTS=""
WINDOW_OUTPUT_ENV=""
WINDOW_OUTPUT_DOC=""
WINDOW_SUMMARY_JSON=""
WINDOW_SUMMARY_MD=""
WINDOW_STDOUT_LOG=""

usage() {
  cat <<'USAGE'
用法:
  ai_judge_real_pass_rehearsal.sh \
    [--root <repo-root>] \
    [--workspace-root <path>] \
    [--output-doc <path>] \
    [--output-env <path>] \
    [--emit-json <path>] \
    [--emit-md <path>]

说明:
  - 生成最小 real 证据模板并在隔离工作区执行一次 real-pass 演练。
  - 本脚本用于“流程演练”，不代表真实环境校准结论。
  - 默认不改动主仓库 docs/loadtest/evidence，而是在 workspace 下产出演练证据。
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

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --root)
        ROOT="${2:-}"
        shift 2
        ;;
      --workspace-root)
        WORKSPACE_ROOT="${2:-}"
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

seed_stage_closure_plan() {
  local file="$1"
  cat >"$file" <<'EOF_PLAN'
# 当前开发计划（演练工作区）

### 已完成/未完成矩阵
| 阶段 | 目标 | 状态 | 说明 |
| --- | --- | --- | --- |
| ai-judge-runtime-ops-pack | P1 | 进行中（phase 已完成） | rehearsal seed |

### 下一开发模块建议

1. ai-judge-real-env-window-closure
EOF_PLAN
}

seed_rehearsal_evidence() {
  local evidence_dir="$1"
  mkdir -p "$evidence_dir"

  cat >"$evidence_dir/ai_judge_p5_real_env.env" <<'EOF_ENV_MARKER'
REAL_CALIBRATION_ENV_READY=true
LOCAL_REFERENCE_ENV_READY=false
CALIBRATION_ENV_MODE=real
EOF_ENV_MARKER

  cat >"$evidence_dir/ai_judge_p5_latency_baseline.env" <<'EOF_LATENCY'
CALIBRATION_STATUS=validated
WINDOW_FROM=2026-04-12T00:00:00Z
WINDOW_TO=2026-04-14T00:00:00Z
SAMPLE_SIZE=1200
P95_MS=980
P99_MS=1860
REAL_ENV_EVIDENCE=https://example.com/evidence/latency-baseline
CALIBRATED_AT=2026-04-14T10:00:00Z
CALIBRATED_BY=qa-bot
DATASET_REF=dataset-2026-04-14
EOF_LATENCY

  cat >"$evidence_dir/ai_judge_p5_cost_baseline.env" <<'EOF_COST'
CALIBRATION_STATUS=validated
WINDOW_FROM=2026-04-12T00:00:00Z
WINDOW_TO=2026-04-14T00:00:00Z
TOKEN_INPUT_TOTAL=1000000
TOKEN_OUTPUT_TOTAL=350000
COST_USD_TOTAL=88.12
COST_USD_PER_1K=0.065
REAL_ENV_EVIDENCE=https://example.com/evidence/cost-baseline
CALIBRATED_AT=2026-04-14T10:00:00Z
CALIBRATED_BY=qa-bot
DATASET_REF=dataset-2026-04-14
EOF_COST

  cat >"$evidence_dir/ai_judge_p5_fairness_benchmark.env" <<'EOF_FAIRNESS'
CALIBRATION_STATUS=validated
WINDOW_FROM=2026-04-12T00:00:00Z
WINDOW_TO=2026-04-14T00:00:00Z
SAMPLE_SIZE=900
DRAW_RATE=0.18
SIDE_BIAS_DELTA=0.03
APPEAL_OVERTURN_RATE=0.06
REAL_ENV_EVIDENCE=https://example.com/evidence/fairness-benchmark
CALIBRATED_AT=2026-04-14T10:00:00Z
CALIBRATED_BY=qa-bot
DATASET_REF=dataset-2026-04-14
EOF_FAIRNESS

  cat >"$evidence_dir/ai_judge_p5_fault_drill.env" <<'EOF_FAULT'
CALIBRATION_STATUS=validated
DRILL_RUN_AT=2026-04-14T09:00:00Z
CALLBACK_FAILURE_RECOVERY_PASS=true
REPLAY_CONSISTENCY_PASS=true
AUDIT_ALERT_DELIVERY_PASS=true
REAL_ENV_EVIDENCE=https://example.com/evidence/fault-drill
CALIBRATED_AT=2026-04-14T10:00:00Z
CALIBRATED_BY=qa-bot
DATASET_REF=dataset-2026-04-14
EOF_FAULT

  cat >"$evidence_dir/ai_judge_p5_trust_attestation.env" <<'EOF_TRUST'
CALIBRATION_STATUS=validated
TRACE_HASH_COVERAGE=0.995
COMMITMENT_COVERAGE=0.985
ATTESTATION_GAP=0.003
REAL_ENV_EVIDENCE=https://example.com/evidence/trust-attestation
CALIBRATED_AT=2026-04-14T10:00:00Z
CALIBRATED_BY=qa-bot
DATASET_REF=dataset-2026-04-14
EOF_TRUST
}

write_output_env() {
  cat >"$OUTPUT_ENV" <<EOF_ENV
AI_JUDGE_REAL_PASS_REHEARSAL_STATUS=$STATUS
UPDATED_AT=$FINISHED_AT
RUN_ID=$RUN_ID
WORKSPACE_ROOT=$WORKSPACE_ROOT
WINDOW_EXIT_CODE=$WINDOW_EXIT_CODE
WINDOW_CLOSURE_STATUS=$WINDOW_STATUS
WINDOW_REAL_PASS_READY=$WINDOW_REAL_PASS_READY
WINDOW_REAL_PASS_BLOCKER_CODES=$WINDOW_REAL_PASS_BLOCKER_CODES
WINDOW_REAL_PASS_BLOCKER_HINTS=$WINDOW_REAL_PASS_BLOCKER_HINTS
WINDOW_OUTPUT_ENV=$WINDOW_OUTPUT_ENV
WINDOW_OUTPUT_DOC=$WINDOW_OUTPUT_DOC
WINDOW_SUMMARY_JSON=$WINDOW_SUMMARY_JSON
WINDOW_SUMMARY_MD=$WINDOW_SUMMARY_MD
WINDOW_STDOUT_LOG=$WINDOW_STDOUT_LOG
EOF_ENV
}

write_output_doc() {
  cat >"$OUTPUT_DOC" <<EOF_MD
# AI Judge Real Pass Rehearsal 摘要

1. 生成日期：$(date_cn)
2. 运行窗口：$STARTED_AT -> $FINISHED_AT
3. 演练状态：\`$STATUS\`
4. workspace：\`$WORKSPACE_ROOT\`

## Window Closure 结果

1. exit_code：\`$WINDOW_EXIT_CODE\`
2. window_status：\`$WINDOW_STATUS\`
3. window_real_pass_ready：\`$WINDOW_REAL_PASS_READY\`
4. blocker_codes：\`${WINDOW_REAL_PASS_BLOCKER_CODES:-（无）}\`
5. blocker_hints：\`${WINDOW_REAL_PASS_BLOCKER_HINTS:-（无）}\`

## 工件

1. window_env：\`$WINDOW_OUTPUT_ENV\`
2. window_doc：\`$WINDOW_OUTPUT_DOC\`
3. window_json：\`$WINDOW_SUMMARY_JSON\`
4. window_md：\`$WINDOW_SUMMARY_MD\`
5. window_stdout_log：\`$WINDOW_STDOUT_LOG\`

## 说明

1. 本脚本只用于验证收口链路可达 \`pass\`，不代表真实环境证据。
2. 若需真实收口，请在真实环境下重新采样并回写正式证据后，运行 \`ai_judge_real_env_window_closure.sh\`。
EOF_MD
}

write_json_summary() {
  cat >"$EMIT_JSON" <<EOF_JSON
{
  "module": "ai-judge-real-pass-rehearsal",
  "status": "$(json_escape "$STATUS")",
  "run_id": "$(json_escape "$RUN_ID")",
  "started_at": "$(json_escape "$STARTED_AT")",
  "finished_at": "$(json_escape "$FINISHED_AT")",
  "workspace_root": "$(json_escape "$WORKSPACE_ROOT")",
  "window": {
    "exit_code": $WINDOW_EXIT_CODE,
    "status": "$(json_escape "$WINDOW_STATUS")",
    "real_pass_ready": "$(json_escape "$WINDOW_REAL_PASS_READY")",
    "blocker_codes": "$(json_escape "$WINDOW_REAL_PASS_BLOCKER_CODES")",
    "blocker_hints": "$(json_escape "$WINDOW_REAL_PASS_BLOCKER_HINTS")",
    "output_env": "$(json_escape "$WINDOW_OUTPUT_ENV")",
    "output_doc": "$(json_escape "$WINDOW_OUTPUT_DOC")",
    "summary_json": "$(json_escape "$WINDOW_SUMMARY_JSON")",
    "summary_md": "$(json_escape "$WINDOW_SUMMARY_MD")",
    "stdout_log": "$(json_escape "$WINDOW_STDOUT_LOG")"
  },
  "outputs": {
    "output_doc": "$(json_escape "$OUTPUT_DOC")",
    "output_env": "$(json_escape "$OUTPUT_ENV")",
    "summary_json": "$(json_escape "$EMIT_JSON")",
    "summary_md": "$(json_escape "$EMIT_MD")"
  }
}
EOF_JSON
}

write_md_summary() {
  cat >"$EMIT_MD" <<EOF_MD
# ai-judge-real-pass-rehearsal

- status: \`$STATUS\`
- run_id: \`$RUN_ID\`
- workspace_root: \`$WORKSPACE_ROOT\`
- started_at: \`$STARTED_AT\`
- finished_at: \`$FINISHED_AT\`

## window

1. exit_code: \`$WINDOW_EXIT_CODE\`
2. status: \`$WINDOW_STATUS\`
3. real_pass_ready: \`$WINDOW_REAL_PASS_READY\`
4. blocker_codes: \`${WINDOW_REAL_PASS_BLOCKER_CODES:-（无）}\`
5. blocker_hints: \`${WINDOW_REAL_PASS_BLOCKER_HINTS:-（无）}\`
EOF_MD
}

main() {
  parse_args "$@"
  resolve_root

  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ai-judge-real-pass-rehearsal"
  STARTED_AT="$(iso_now)"

  if [[ -z "$WORKSPACE_ROOT" ]]; then
    WORKSPACE_ROOT="$ROOT/artifacts/harness/$RUN_ID/workspace"
  else
    WORKSPACE_ROOT="$(abs_path "$WORKSPACE_ROOT")"
  fi

  if [[ -z "$OUTPUT_DOC" ]]; then
    OUTPUT_DOC="$ROOT/artifacts/harness/${RUN_ID}.summary.doc.md"
  else
    OUTPUT_DOC="$(abs_path "$OUTPUT_DOC")"
  fi
  if [[ -z "$OUTPUT_ENV" ]]; then
    OUTPUT_ENV="$ROOT/artifacts/harness/${RUN_ID}.summary.env"
  else
    OUTPUT_ENV="$(abs_path "$OUTPUT_ENV")"
  fi
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

  ensure_parent_dir "$OUTPUT_DOC"
  ensure_parent_dir "$OUTPUT_ENV"
  ensure_parent_dir "$EMIT_JSON"
  ensure_parent_dir "$EMIT_MD"
  mkdir -p "$WORKSPACE_ROOT"

  local workspace_evidence_dir workspace_plan_doc
  workspace_evidence_dir="$WORKSPACE_ROOT/docs/loadtest/evidence"
  workspace_plan_doc="$WORKSPACE_ROOT/docs/dev_plan/当前开发计划.md"
  mkdir -p "$workspace_evidence_dir"
  ensure_parent_dir "$workspace_plan_doc"

  seed_rehearsal_evidence "$workspace_evidence_dir"
  seed_stage_closure_plan "$workspace_plan_doc"

  WINDOW_OUTPUT_ENV="$workspace_evidence_dir/ai_judge_real_env_window_closure.env"
  WINDOW_OUTPUT_DOC="$workspace_evidence_dir/ai_judge_real_env_window_closure.md"
  WINDOW_SUMMARY_JSON="$WORKSPACE_ROOT/artifacts/harness/${RUN_ID}.window.summary.json"
  WINDOW_SUMMARY_MD="$WORKSPACE_ROOT/artifacts/harness/${RUN_ID}.window.summary.md"
  WINDOW_STDOUT_LOG="$WORKSPACE_ROOT/artifacts/harness/${RUN_ID}.window.stdout.log"
  ensure_parent_dir "$WINDOW_SUMMARY_JSON"
  ensure_parent_dir "$WINDOW_SUMMARY_MD"
  ensure_parent_dir "$WINDOW_STDOUT_LOG"

  local window_script
  window_script="$ROOT/scripts/harness/ai_judge_real_env_window_closure.sh"
  local p5_script runtime_ops_script fairness_script runtime_sla_script real_env_closure_script stage_closure_draft_script stage_closure_evidence_script
  p5_script="$ROOT/scripts/harness/ai_judge_p5_real_calibration_on_env.sh"
  runtime_ops_script="$ROOT/scripts/harness/ai_judge_runtime_ops_pack.sh"
  fairness_script="$ROOT/scripts/harness/ai_judge_fairness_benchmark_freeze.sh"
  runtime_sla_script="$ROOT/scripts/harness/ai_judge_runtime_sla_freeze.sh"
  real_env_closure_script="$ROOT/scripts/harness/ai_judge_real_env_evidence_closure.sh"
  stage_closure_draft_script="$ROOT/scripts/harness/ai_judge_stage_closure_draft.sh"
  stage_closure_evidence_script="$ROOT/scripts/harness/ai_judge_stage_closure_evidence.sh"
  if bash "$window_script" \
    --root "$WORKSPACE_ROOT" \
    --p5-script "$p5_script" \
    --runtime-ops-script "$runtime_ops_script" \
    --fairness-script "$fairness_script" \
    --runtime-sla-script "$runtime_sla_script" \
    --real-env-closure-script "$real_env_closure_script" \
    --stage-closure-plan-doc "$workspace_plan_doc" \
    --stage-closure-draft-script "$stage_closure_draft_script" \
    --stage-closure-evidence-script "$stage_closure_evidence_script" \
    --emit-json "$WINDOW_SUMMARY_JSON" \
    --emit-md "$WINDOW_SUMMARY_MD" >"$WINDOW_STDOUT_LOG" 2>&1; then
    WINDOW_EXIT_CODE=0
  else
    WINDOW_EXIT_CODE=$?
  fi

  WINDOW_STATUS="$(trim "$(read_env_value "$WINDOW_OUTPUT_ENV" "AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS")")"
  WINDOW_REAL_PASS_READY="$(trim "$(read_env_value "$WINDOW_OUTPUT_ENV" "REAL_PASS_READY")")"
  WINDOW_REAL_PASS_BLOCKER_CODES="$(trim "$(read_env_value "$WINDOW_OUTPUT_ENV" "REAL_PASS_BLOCKER_CODES")")"
  WINDOW_REAL_PASS_BLOCKER_HINTS="$(trim "$(read_env_value "$WINDOW_OUTPUT_ENV" "REAL_PASS_BLOCKER_HINTS")")"
  [[ -z "$WINDOW_STATUS" ]] && WINDOW_STATUS="unknown"
  [[ -z "$WINDOW_REAL_PASS_READY" ]] && WINDOW_REAL_PASS_READY="false"

  if [[ "$WINDOW_EXIT_CODE" != "0" ]]; then
    STATUS="stage_failed"
  elif [[ "$WINDOW_STATUS" == "pass" && "$WINDOW_REAL_PASS_READY" == "true" ]]; then
    STATUS="pass"
  else
    STATUS="not_pass"
  fi

  FINISHED_AT="$(iso_now)"
  write_output_env
  write_output_doc
  write_json_summary
  write_md_summary

  echo "ai_judge_real_pass_rehearsal_status: $STATUS"
  echo "workspace_root: $WORKSPACE_ROOT"
  echo "window_exit_code: $WINDOW_EXIT_CODE"
  echo "window_status: $WINDOW_STATUS"
  echo "window_real_pass_ready: $WINDOW_REAL_PASS_READY"
  echo "window_real_pass_blocker_codes: ${WINDOW_REAL_PASS_BLOCKER_CODES:-none}"
  echo "window_real_pass_blocker_hints: ${WINDOW_REAL_PASS_BLOCKER_HINTS:-none}"
  echo "output_env: $OUTPUT_ENV"
  echo "output_doc: $OUTPUT_DOC"
  echo "summary_json: $EMIT_JSON"
  echo "summary_md: $EMIT_MD"
}

main "$@"
