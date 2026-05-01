#!/usr/bin/env bash
set -euo pipefail

ROOT=""
EVIDENCE_DIR=""
ENV_MARKER=""
P5_SCRIPT=""
RUNTIME_OPS_SCRIPT=""
FAIRNESS_SCRIPT=""
RUNTIME_SLA_SCRIPT=""
REAL_ENV_CLOSURE_SCRIPT=""
STAGE_CLOSURE_PLAN_DOC=""
STAGE_CLOSURE_DRAFT_SCRIPT=""
STAGE_CLOSURE_EVIDENCE_SCRIPT=""
ALLOW_LOCAL_REFERENCE="${AI_JUDGE_ALLOW_LOCAL_REFERENCE:-false}"
OUTPUT_DOC=""
OUTPUT_ENV=""
EMIT_JSON=""
EMIT_MD=""
RUN_ID=""
STARTED_AT=""
FINISHED_AT=""
STATUS="unknown"

P5_EXIT_CODE=0
RUNTIME_OPS_EXIT_CODE=0
P5_STATUS="unknown"
RUNTIME_OPS_STATUS="unknown"
FAIRNESS_STATUS="unknown"
FAIRNESS_INGEST_STATUS="unknown"
RUNTIME_SLA_STATUS="unknown"
REAL_ENV_CLOSURE_STATUS="unknown"
STAGE_CLOSURE_EVIDENCE_STATUS="unknown"
MARKER_READY="false"
ENV_MODE="blocked"
REAL_ENV_INPUT_READY="false"
REAL_ENV_READINESS_STATUS="env_blocked"
REAL_ENV_READINESS_BLOCKER_CODES=""
REAL_ENV_READINESS_BLOCKER_HINTS=""
REAL_SAMPLE_MANIFEST=""
REAL_PROVIDER_READY="false"
REAL_CALLBACK_READY="false"
PRODUCTION_ARTIFACT_STORE_READY="false"
PRODUCTION_ARTIFACT_STORE_EVIDENCE_JSON=""
PRODUCTION_ARTIFACT_STORE_EVIDENCE_STATUS="not_provided"
PRODUCTION_ARTIFACT_STORE_EVIDENCE_ROUNDTRIP_STATUS=""
PRODUCTION_ARTIFACT_STORE_EVIDENCE_BLOCKER_CODE=""
BENCHMARK_TARGETS_READY="false"
FAIRNESS_TARGETS_READY="false"
RUNTIME_OPS_TARGETS_READY="false"
LOCAL_REFERENCE_EVIDENCE_LINK=""
REAL_EVIDENCE_LINK=""
REAL_PASS_READY="false"
REAL_PASS_BLOCKER_CODES=""
REAL_PASS_BLOCKER_HINTS=""

FAIRNESS_INGEST_ENABLED="${AI_JUDGE_FAIRNESS_INGEST_ENABLED:-false}"
FAIRNESS_INGEST_BASE_URL="${AI_JUDGE_FAIRNESS_INGEST_BASE_URL:-}"
FAIRNESS_INGEST_PATH="${AI_JUDGE_FAIRNESS_INGEST_PATH:-/internal/judge/fairness/benchmark-runs}"
FAIRNESS_INGEST_INTERNAL_KEY="${AI_JUDGE_FAIRNESS_INGEST_INTERNAL_KEY:-${AI_JUDGE_INTERNAL_KEY:-}}"
FAIRNESS_INGEST_TIMEOUT_SECS="${AI_JUDGE_FAIRNESS_INGEST_TIMEOUT_SECS:-8}"
FAIRNESS_INGEST_REQUIRE_SUCCESS="${AI_JUDGE_FAIRNESS_INGEST_REQUIRE_SUCCESS:-false}"
FAIRNESS_INGEST_REPORTED_BY="${AI_JUDGE_FAIRNESS_INGEST_REPORTED_BY:-harness}"

usage() {
  cat <<'USAGE'
用法:
  ai_judge_real_env_window_closure.sh \
    [--root <repo-root>] \
    [--evidence-dir <path>] \
    [--env-marker <path>] \
    [--p5-script <path>] \
    [--runtime-ops-script <path>] \
    [--fairness-script <path>] \
    [--runtime-sla-script <path>] \
    [--real-env-closure-script <path>] \
    [--stage-closure-plan-doc <path>] \
    [--stage-closure-draft-script <path>] \
    [--stage-closure-evidence-script <path>] \
    [--allow-local-reference] \
    [--fairness-ingest-enabled] \
    [--fairness-ingest-base-url <url>] \
    [--fairness-ingest-path <path>] \
    [--fairness-ingest-internal-key <key>] \
    [--fairness-ingest-timeout-secs <int>] \
    [--fairness-ingest-require-success] \
    [--fairness-ingest-reported-by <actor>] \
    [--output-doc <path>] \
    [--output-env <path>] \
    [--emit-json <path>] \
    [--emit-md <path>]

说明:
  - 真实环境窗口收口总控：
    1) 执行 P5 real calibration on env
    2) 执行 runtime ops pack（含 stage closure evidence 联动）
  - 输出统一状态：
    pass/local_reference_ready/threshold_violation/pending_real_evidence/env_blocked/evidence_missing/stage_failed/mixed
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

read_input_value() {
  local key="$1"
  local value=""
  if [[ -f "$ENV_MARKER" ]]; then
    value="$(trim "$(read_env_value "$ENV_MARKER" "$key")")"
  fi
  if [[ -z "$value" ]]; then
    value="$(trim "$(printenv "$key" 2>/dev/null || true)")"
  fi
  printf '%s' "$value"
}

read_json_status() {
  local file="$1"
  local line
  line="$(grep -E '"status"[[:space:]]*:[[:space:]]*"' "$file" | head -n 1 || true)"
  if [[ -z "$line" ]]; then
    printf '%s' ""
    return
  fi
  printf '%s' "$line" | sed -E 's/.*"status"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/'
}

read_json_string_value() {
  local file="$1"
  local key="$2"
  local line
  line="$(grep -E "\"${key}\"[[:space:]]*:[[:space:]]*\"" "$file" | head -n 1 || true)"
  if [[ -z "$line" ]]; then
    printf '%s' ""
    return
  fi
  printf '%s' "$line" | sed -E "s/.*\"${key}\"[[:space:]]*:[[:space:]]*\"([^\"]+)\".*/\1/"
}

read_json_nullable_string_value() {
  local file="$1"
  local key="$2"
  local line
  line="$(grep -E "\"${key}\"[[:space:]]*:" "$file" | head -n 1 || true)"
  if [[ -z "$line" || "$line" =~ :[[:space:]]*null[,[:space:]]*$ ]]; then
    printf '%s' ""
    return
  fi
  printf '%s' "$line" | sed -E "s/.*\"${key}\"[[:space:]]*:[[:space:]]*\"([^\"]+)\".*/\1/"
}

read_json_bool_value() {
  local file="$1"
  local key="$2"
  local line
  line="$(grep -E "\"${key}\"[[:space:]]*:[[:space:]]*(true|false)" "$file" | head -n 1 || true)"
  if [[ -z "$line" ]]; then
    printf '%s' ""
    return
  fi
  printf '%s' "$line" | sed -E "s/.*\"${key}\"[[:space:]]*:[[:space:]]*(true|false).*/\1/"
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
      --p5-script)
        P5_SCRIPT="${2:-}"
        shift 2
        ;;
      --runtime-ops-script)
        RUNTIME_OPS_SCRIPT="${2:-}"
        shift 2
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
      --stage-closure-plan-doc)
        STAGE_CLOSURE_PLAN_DOC="${2:-}"
        shift 2
        ;;
      --stage-closure-draft-script)
        STAGE_CLOSURE_DRAFT_SCRIPT="${2:-}"
        shift 2
        ;;
      --stage-closure-evidence-script)
        STAGE_CLOSURE_EVIDENCE_SCRIPT="${2:-}"
        shift 2
        ;;
      --allow-local-reference)
        ALLOW_LOCAL_REFERENCE="true"
        shift 1
        ;;
      --fairness-ingest-enabled)
        FAIRNESS_INGEST_ENABLED="true"
        shift 1
        ;;
      --fairness-ingest-base-url)
        FAIRNESS_INGEST_BASE_URL="${2:-}"
        shift 2
        ;;
      --fairness-ingest-path)
        FAIRNESS_INGEST_PATH="${2:-}"
        shift 2
        ;;
      --fairness-ingest-internal-key)
        FAIRNESS_INGEST_INTERNAL_KEY="${2:-}"
        shift 2
        ;;
      --fairness-ingest-timeout-secs)
        FAIRNESS_INGEST_TIMEOUT_SECS="${2:-}"
        shift 2
        ;;
      --fairness-ingest-require-success)
        FAIRNESS_INGEST_REQUIRE_SUCCESS="true"
        shift 1
        ;;
      --fairness-ingest-reported-by)
        FAIRNESS_INGEST_REPORTED_BY="${2:-}"
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
  local stage_json="$2"
  local stage_md="$3"
  local stage_stdout="$4"
  local stage_exit_var="$5"

  local -a cmd
  if [[ "$stage" == "p5" ]]; then
    cmd=(bash "$P5_SCRIPT" --root "$ROOT" --evidence-dir "$EVIDENCE_DIR" --env-marker "$ENV_MARKER" --emit-json "$stage_json" --emit-md "$stage_md")
  else
    cmd=(bash "$RUNTIME_OPS_SCRIPT" --root "$ROOT" --evidence-dir "$EVIDENCE_DIR" --env-marker "$ENV_MARKER" --fairness-script "$FAIRNESS_SCRIPT" --runtime-sla-script "$RUNTIME_SLA_SCRIPT" --real-env-closure-script "$REAL_ENV_CLOSURE_SCRIPT" --stage-closure-plan-doc "$STAGE_CLOSURE_PLAN_DOC" --stage-closure-draft-script "$STAGE_CLOSURE_DRAFT_SCRIPT" --stage-closure-evidence-script "$STAGE_CLOSURE_EVIDENCE_SCRIPT" --emit-json "$stage_json" --emit-md "$stage_md")
    if [[ "$FAIRNESS_INGEST_ENABLED" == "true" ]]; then
      cmd+=(--fairness-ingest-enabled)
    fi
    if [[ -n "$FAIRNESS_INGEST_BASE_URL" ]]; then
      cmd+=(--fairness-ingest-base-url "$FAIRNESS_INGEST_BASE_URL")
    fi
    if [[ -n "$FAIRNESS_INGEST_PATH" ]]; then
      cmd+=(--fairness-ingest-path "$FAIRNESS_INGEST_PATH")
    fi
    if [[ -n "$FAIRNESS_INGEST_INTERNAL_KEY" ]]; then
      cmd+=(--fairness-ingest-internal-key "$FAIRNESS_INGEST_INTERNAL_KEY")
    fi
    if [[ -n "$FAIRNESS_INGEST_TIMEOUT_SECS" ]]; then
      cmd+=(--fairness-ingest-timeout-secs "$FAIRNESS_INGEST_TIMEOUT_SECS")
    fi
    if [[ "$FAIRNESS_INGEST_REQUIRE_SUCCESS" == "true" ]]; then
      cmd+=(--fairness-ingest-require-success)
    fi
    if [[ -n "$FAIRNESS_INGEST_REPORTED_BY" ]]; then
      cmd+=(--fairness-ingest-reported-by "$FAIRNESS_INGEST_REPORTED_BY")
    fi
  fi

  if [[ "$ALLOW_LOCAL_REFERENCE" == "true" ]]; then
    cmd+=(--allow-local-reference)
  fi

  if "${cmd[@]}" >"$stage_stdout" 2>&1; then
    printf -v "$stage_exit_var" '%s' "0"
  else
    local code="$?"
    printf -v "$stage_exit_var" '%s' "$code"
  fi
}

resolve_env_mode() {
  MARKER_READY="false"
  ENV_MODE="blocked"
  if [[ ! -f "$ENV_MARKER" ]]; then
    return
  fi
  local marker_real marker_local marker_mode
  marker_real="$(trim "$(read_env_value "$ENV_MARKER" "REAL_CALIBRATION_ENV_READY")")"
  marker_local="$(trim "$(read_env_value "$ENV_MARKER" "LOCAL_REFERENCE_ENV_READY")")"
  marker_mode="$(trim "$(read_env_value "$ENV_MARKER" "CALIBRATION_ENV_MODE")")"
  if is_truthy "$marker_real"; then
    MARKER_READY="true"
    ENV_MODE="real"
    return
  fi
  if [[ "$ALLOW_LOCAL_REFERENCE" == "true" ]] && (is_truthy "$marker_local" || [[ "$marker_mode" == "local_reference" || "$marker_mode" == "local" ]]); then
    ENV_MODE="local_reference"
    return
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

join_with_delim() {
  local delim="$1"
  shift
  if [[ $# -eq 0 ]]; then
    printf '%s' ""
    return
  fi
  local out="$1"
  shift
  local part
  for part in "$@"; do
    out+="$delim$part"
  done
  printf '%s' "$out"
}

resolve_artifact_store_evidence_ready() {
  local evidence_path ready

  PRODUCTION_ARTIFACT_STORE_EVIDENCE_JSON="$(trim "$(read_input_value "PRODUCTION_ARTIFACT_STORE_EVIDENCE_JSON")")"
  if [[ -z "$PRODUCTION_ARTIFACT_STORE_EVIDENCE_JSON" ]]; then
    PRODUCTION_ARTIFACT_STORE_EVIDENCE_JSON="$(trim "$(read_input_value "AI_JUDGE_ARTIFACT_STORE_HEALTHCHECK_EVIDENCE_JSON")")"
  fi
  if [[ -z "$PRODUCTION_ARTIFACT_STORE_EVIDENCE_JSON" && -f "$EVIDENCE_DIR/ai_judge_artifact_store_healthcheck.json" ]]; then
    PRODUCTION_ARTIFACT_STORE_EVIDENCE_JSON="$EVIDENCE_DIR/ai_judge_artifact_store_healthcheck.json"
  fi
  if [[ -z "$PRODUCTION_ARTIFACT_STORE_EVIDENCE_JSON" ]]; then
    PRODUCTION_ARTIFACT_STORE_EVIDENCE_STATUS="not_provided"
    return
  fi

  evidence_path="$(abs_path "$PRODUCTION_ARTIFACT_STORE_EVIDENCE_JSON")"
  PRODUCTION_ARTIFACT_STORE_EVIDENCE_JSON="$evidence_path"
  if [[ ! -f "$evidence_path" ]]; then
    PRODUCTION_ARTIFACT_STORE_EVIDENCE_STATUS="missing"
    PRODUCTION_ARTIFACT_STORE_EVIDENCE_BLOCKER_CODE="production_artifact_store_evidence_missing"
    PRODUCTION_ARTIFACT_STORE_READY="false"
    return
  fi

  ready="$(read_json_bool_value "$evidence_path" "productionArtifactStoreReady")"
  if [[ -z "$ready" ]]; then
    ready="$(read_json_bool_value "$evidence_path" "productionReady")"
  fi
  PRODUCTION_ARTIFACT_STORE_EVIDENCE_ROUNDTRIP_STATUS="$(read_json_string_value "$evidence_path" "writeReadRoundtripStatus")"
  if [[ -z "$PRODUCTION_ARTIFACT_STORE_EVIDENCE_ROUNDTRIP_STATUS" ]]; then
    PRODUCTION_ARTIFACT_STORE_EVIDENCE_ROUNDTRIP_STATUS="$(read_json_string_value "$evidence_path" "status")"
  fi
  PRODUCTION_ARTIFACT_STORE_EVIDENCE_BLOCKER_CODE="$(read_json_nullable_string_value "$evidence_path" "blockerCode")"

  if [[ "$ready" == "true" ]]; then
    PRODUCTION_ARTIFACT_STORE_EVIDENCE_STATUS="ready"
    PRODUCTION_ARTIFACT_STORE_READY="true"
    return
  fi
  if [[ "$ready" == "false" ]]; then
    PRODUCTION_ARTIFACT_STORE_EVIDENCE_STATUS="blocked"
    if [[ -z "$PRODUCTION_ARTIFACT_STORE_EVIDENCE_BLOCKER_CODE" ]]; then
      PRODUCTION_ARTIFACT_STORE_EVIDENCE_BLOCKER_CODE="production_artifact_store_not_ready"
    fi
    PRODUCTION_ARTIFACT_STORE_READY="false"
    return
  fi

  PRODUCTION_ARTIFACT_STORE_EVIDENCE_STATUS="invalid"
  PRODUCTION_ARTIFACT_STORE_EVIDENCE_BLOCKER_CODE="production_artifact_store_evidence_invalid"
  PRODUCTION_ARTIFACT_STORE_READY="false"
}

derive_readiness_inputs() {
  local -a blocker_codes=()
  local -a blocker_hints=()

  REAL_SAMPLE_MANIFEST="$(trim "$(read_input_value "REAL_SAMPLE_MANIFEST")")"
  REAL_PROVIDER_READY="$(trim "$(read_input_value "REAL_PROVIDER_READY")")"
  REAL_CALLBACK_READY="$(trim "$(read_input_value "REAL_CALLBACK_READY")")"
  PRODUCTION_ARTIFACT_STORE_READY="$(trim "$(read_input_value "PRODUCTION_ARTIFACT_STORE_READY")")"
  resolve_artifact_store_evidence_ready
  BENCHMARK_TARGETS_READY="$(trim "$(read_input_value "BENCHMARK_TARGETS_READY")")"
  FAIRNESS_TARGETS_READY="$(trim "$(read_input_value "FAIRNESS_TARGETS_READY")")"
  RUNTIME_OPS_TARGETS_READY="$(trim "$(read_input_value "RUNTIME_OPS_TARGETS_READY")")"
  LOCAL_REFERENCE_EVIDENCE_LINK="$(trim "$(read_input_value "LOCAL_REFERENCE_EVIDENCE_LINK")")"
  REAL_EVIDENCE_LINK="$(trim "$(read_input_value "REAL_EVIDENCE_LINK")")"

  if [[ -z "$LOCAL_REFERENCE_EVIDENCE_LINK" ]]; then
    LOCAL_REFERENCE_EVIDENCE_LINK="$EVIDENCE_DIR/ai_judge_p5_local_reference_notes.md"
  fi
  if [[ -z "$REAL_EVIDENCE_LINK" ]]; then
    REAL_EVIDENCE_LINK="$OUTPUT_DOC"
  fi

  if [[ "$MARKER_READY" != "true" ]]; then
    blocker_codes+=("real_env_marker_not_ready")
    blocker_hints+=("设置 REAL_CALIBRATION_ENV_READY=true 并确认 CALIBRATION_ENV_MODE=real")
  fi
  if [[ -z "$REAL_SAMPLE_MANIFEST" ]]; then
    blocker_codes+=("real_sample_manifest_missing")
    blocker_hints+=("在 ai_judge_p5_real_env.env 或环境变量中设置 REAL_SAMPLE_MANIFEST")
  fi
  if ! is_truthy "$REAL_PROVIDER_READY"; then
    blocker_codes+=("real_provider_not_ready")
    blocker_hints+=("设置 REAL_PROVIDER_READY=true，确认真实模型/provider 服务可用")
  fi
  if ! is_truthy "$REAL_CALLBACK_READY"; then
    blocker_codes+=("real_callback_not_ready")
    blocker_hints+=("设置 REAL_CALLBACK_READY=true，确认真实 callback/回写服务可用")
  fi
  if ! is_truthy "$PRODUCTION_ARTIFACT_STORE_READY"; then
    local artifact_blocker_code="production_artifact_store_not_ready"
    if [[ -n "$PRODUCTION_ARTIFACT_STORE_EVIDENCE_BLOCKER_CODE" ]]; then
      artifact_blocker_code="$PRODUCTION_ARTIFACT_STORE_EVIDENCE_BLOCKER_CODE"
    fi
    blocker_codes+=("$artifact_blocker_code")
    blocker_hints+=("运行 artifact_store_healthcheck.py --enable-roundtrip 并确认 productionReady=true；或设置 PRODUCTION_ARTIFACT_STORE_READY=true")
  fi
  if ! is_truthy "$BENCHMARK_TARGETS_READY"; then
    blocker_codes+=("benchmark_targets_not_ready")
    blocker_hints+=("设置 BENCHMARK_TARGETS_READY=true，确认 benchmark 阈值与样本口径已冻结")
  fi
  if ! is_truthy "$FAIRNESS_TARGETS_READY"; then
    blocker_codes+=("fairness_targets_not_ready")
    blocker_hints+=("设置 FAIRNESS_TARGETS_READY=true，确认 fairness 目标阈值已冻结")
  fi
  if ! is_truthy "$RUNTIME_OPS_TARGETS_READY"; then
    blocker_codes+=("runtime_ops_targets_not_ready")
    blocker_hints+=("设置 RUNTIME_OPS_TARGETS_READY=true，确认 runtime ops/SLA 目标阈值已冻结")
  fi

  if [[ ${#blocker_codes[@]} -eq 0 ]]; then
    REAL_ENV_INPUT_READY="true"
    REAL_ENV_READINESS_STATUS="readiness_ready"
    REAL_ENV_READINESS_BLOCKER_CODES=""
    REAL_ENV_READINESS_BLOCKER_HINTS=""
    return
  fi

  REAL_ENV_INPUT_READY="false"
  REAL_ENV_READINESS_STATUS="env_blocked"
  REAL_ENV_READINESS_BLOCKER_CODES="$(join_with_delim "," "${blocker_codes[@]}")"
  REAL_ENV_READINESS_BLOCKER_HINTS="$(join_with_delim " || " "${blocker_hints[@]}")"
}

derive_status() {
  if [[ "$P5_EXIT_CODE" != "0" || "$RUNTIME_OPS_EXIT_CODE" != "0" ]]; then
    STATUS="stage_failed"
    return
  fi

  if [[ "$ENV_MODE" != "local_reference" && "$REAL_ENV_INPUT_READY" != "true" ]]; then
    STATUS="env_blocked"
    return
  fi

  if [[ "$P5_STATUS" == "pass" && "$RUNTIME_OPS_STATUS" == "pass" ]]; then
    if [[ "$REAL_ENV_INPUT_READY" != "true" ]]; then
      STATUS="env_blocked"
      return
    fi
    STATUS="pass"
    return
  fi
  if [[ "$ALLOW_LOCAL_REFERENCE" == "true" && "$P5_STATUS" == "local_reference_pass" && "$RUNTIME_OPS_STATUS" == "local_reference_ready" ]]; then
    STATUS="local_reference_ready"
    return
  fi

  if is_in_set "$RUNTIME_OPS_STATUS" "threshold_violation"; then
    STATUS="threshold_violation"
    return
  fi
  if is_in_set "$P5_STATUS" "evidence_missing" || is_in_set "$RUNTIME_OPS_STATUS" "evidence_missing"; then
    STATUS="evidence_missing"
    return
  fi
  if is_in_set "$P5_STATUS" "env_blocked" || is_in_set "$RUNTIME_OPS_STATUS" "env_blocked"; then
    STATUS="env_blocked"
    return
  fi
  if is_in_set "$P5_STATUS" "pending_real_data" "local_reference_pending" || is_in_set "$RUNTIME_OPS_STATUS" "pending_data" "local_reference_ready" "mixed"; then
    STATUS="pending_real_evidence"
    return
  fi

  STATUS="mixed"
}

derive_real_pass_readiness() {
  local -a blocker_codes=()
  local -a blocker_hints=()

  if [[ "$MARKER_READY" != "true" ]]; then
    blocker_codes+=("real_env_marker_not_ready")
    blocker_hints+=("设置 docs/loadtest/evidence/ai_judge_p5_real_env.env 中 REAL_CALIBRATION_ENV_READY=true")
  fi
  if [[ "$P5_STATUS" != "pass" ]]; then
    blocker_codes+=("p5_status_not_pass")
    blocker_hints+=("P5 real calibration 当前为 '$P5_STATUS'，需提升到 pass")
  fi
  if [[ "$RUNTIME_OPS_STATUS" != "pass" ]]; then
    blocker_codes+=("runtime_ops_status_not_pass")
    blocker_hints+=("runtime ops pack 当前为 '$RUNTIME_OPS_STATUS'，需提升到 pass")
  fi
  if [[ "$FAIRNESS_STATUS" != "pass" ]]; then
    blocker_codes+=("fairness_status_not_pass")
    blocker_hints+=("fairness freeze 当前为 '$FAIRNESS_STATUS'，需提升到 pass")
  fi
  if [[ "$RUNTIME_SLA_STATUS" != "pass" ]]; then
    blocker_codes+=("runtime_sla_status_not_pass")
    blocker_hints+=("runtime SLA freeze 当前为 '$RUNTIME_SLA_STATUS'，需提升到 pass")
  fi
  if [[ "$REAL_ENV_CLOSURE_STATUS" != "pass" ]]; then
    blocker_codes+=("real_env_closure_status_not_pass")
    blocker_hints+=("real env evidence closure 当前为 '$REAL_ENV_CLOSURE_STATUS'，需提升到 pass")
  fi
  if [[ "$STAGE_CLOSURE_EVIDENCE_STATUS" != "pass" ]]; then
    blocker_codes+=("stage_closure_evidence_not_pass")
    blocker_hints+=("stage closure evidence 当前为 '$STAGE_CLOSURE_EVIDENCE_STATUS'，需为 pass")
  fi
  if [[ "$FAIRNESS_INGEST_REQUIRE_SUCCESS" == "true" && "$FAIRNESS_INGEST_STATUS" != "sent" ]]; then
    blocker_codes+=("fairness_ingest_not_sent")
    blocker_hints+=("fairness ingest 要求成功，但当前为 '$FAIRNESS_INGEST_STATUS'")
  fi
  if [[ "$REAL_ENV_INPUT_READY" != "true" ]]; then
    if [[ -n "$REAL_ENV_READINESS_BLOCKER_CODES" ]]; then
      IFS=',' read -r -a readiness_codes <<< "$REAL_ENV_READINESS_BLOCKER_CODES"
      local code
      for code in "${readiness_codes[@]}"; do
        [[ -z "$code" ]] && continue
        if [[ ${#blocker_codes[@]} -eq 0 ]] || ! is_in_set "$code" "${blocker_codes[@]}"; then
          blocker_codes+=("$code")
        fi
      done
    else
      blocker_codes+=("real_env_readiness_inputs_not_ready")
    fi
    if [[ -n "$REAL_ENV_READINESS_BLOCKER_HINTS" ]]; then
      blocker_hints+=("$REAL_ENV_READINESS_BLOCKER_HINTS")
    else
      blocker_hints+=("真实环境 readiness 输入未全部满足")
    fi
  fi

  if [[ ${#blocker_codes[@]} -eq 0 ]]; then
    REAL_PASS_READY="true"
    REAL_PASS_BLOCKER_CODES=""
    REAL_PASS_BLOCKER_HINTS=""
    return
  fi

  REAL_PASS_READY="false"
  REAL_PASS_BLOCKER_CODES="$(join_with_delim "," "${blocker_codes[@]}")"
  REAL_PASS_BLOCKER_HINTS="$(join_with_delim " || " "${blocker_hints[@]}")"
}

derive_readiness_status() {
  if [[ "$STATUS" == "pass" ]]; then
    REAL_ENV_READINESS_STATUS="pass"
    return
  fi
  if [[ "$STATUS" == "stage_failed" || "$STATUS" == "threshold_violation" ]]; then
    REAL_ENV_READINESS_STATUS="failed"
    return
  fi
  if [[ "$REAL_ENV_INPUT_READY" == "true" ]]; then
    REAL_ENV_READINESS_STATUS="readiness_ready"
    return
  fi
  REAL_ENV_READINESS_STATUS="env_blocked"
}

write_output_env() {
  cat >"$OUTPUT_ENV" <<EOF_ENV
AI_JUDGE_REAL_ENV_WINDOW_CLOSURE_STATUS=$STATUS
UPDATED_AT=$FINISHED_AT
RUN_ID=$RUN_ID
REAL_CALIBRATION_ENV_READY=$MARKER_READY
ENVIRONMENT_MODE=$ENV_MODE
ALLOW_LOCAL_REFERENCE=$ALLOW_LOCAL_REFERENCE
REAL_ENV_READINESS_STATUS=$REAL_ENV_READINESS_STATUS
REAL_ENV_INPUT_READY=$REAL_ENV_INPUT_READY
REAL_ENV_READINESS_BLOCKER_CODES=$REAL_ENV_READINESS_BLOCKER_CODES
REAL_ENV_READINESS_BLOCKER_HINTS=$REAL_ENV_READINESS_BLOCKER_HINTS
REAL_SAMPLE_MANIFEST=$REAL_SAMPLE_MANIFEST
REAL_PROVIDER_READY=$REAL_PROVIDER_READY
REAL_CALLBACK_READY=$REAL_CALLBACK_READY
PRODUCTION_ARTIFACT_STORE_READY=$PRODUCTION_ARTIFACT_STORE_READY
PRODUCTION_ARTIFACT_STORE_EVIDENCE_JSON=$PRODUCTION_ARTIFACT_STORE_EVIDENCE_JSON
PRODUCTION_ARTIFACT_STORE_EVIDENCE_STATUS=$PRODUCTION_ARTIFACT_STORE_EVIDENCE_STATUS
PRODUCTION_ARTIFACT_STORE_EVIDENCE_ROUNDTRIP_STATUS=$PRODUCTION_ARTIFACT_STORE_EVIDENCE_ROUNDTRIP_STATUS
PRODUCTION_ARTIFACT_STORE_EVIDENCE_BLOCKER_CODE=$PRODUCTION_ARTIFACT_STORE_EVIDENCE_BLOCKER_CODE
BENCHMARK_TARGETS_READY=$BENCHMARK_TARGETS_READY
FAIRNESS_TARGETS_READY=$FAIRNESS_TARGETS_READY
RUNTIME_OPS_TARGETS_READY=$RUNTIME_OPS_TARGETS_READY
LOCAL_REFERENCE_EVIDENCE_LINK=$LOCAL_REFERENCE_EVIDENCE_LINK
REAL_EVIDENCE_LINK=$REAL_EVIDENCE_LINK
REAL_PASS_READY=$REAL_PASS_READY
REAL_PASS_BLOCKER_CODES=$REAL_PASS_BLOCKER_CODES
REAL_PASS_BLOCKER_HINTS=$REAL_PASS_BLOCKER_HINTS
P5_REAL_CALIBRATION_STATUS=$P5_STATUS
RUNTIME_OPS_PACK_STATUS=$RUNTIME_OPS_STATUS
FAIRNESS_STATUS=$FAIRNESS_STATUS
FAIRNESS_INGEST_STATUS=$FAIRNESS_INGEST_STATUS
RUNTIME_SLA_STATUS=$RUNTIME_SLA_STATUS
REAL_ENV_CLOSURE_STATUS=$REAL_ENV_CLOSURE_STATUS
STAGE_CLOSURE_EVIDENCE_STATUS=$STAGE_CLOSURE_EVIDENCE_STATUS
P5_EXIT_CODE=$P5_EXIT_CODE
RUNTIME_OPS_EXIT_CODE=$RUNTIME_OPS_EXIT_CODE
EOF_ENV
}

write_output_doc() {
  cat >"$OUTPUT_DOC" <<EOF_MD
# AI Judge Real Env Window Closure 摘要

1. 生成日期：$(date_cn)
2. 运行窗口：$STARTED_AT -> $FINISHED_AT
3. 统一状态：\`$STATUS\`
4. environment_mode：\`$ENV_MODE\`
5. marker_ready：\`$MARKER_READY\`
6. allow_local_reference：\`$ALLOW_LOCAL_REFERENCE\`
7. real_env_readiness_status：\`$REAL_ENV_READINESS_STATUS\`

## 子阶段状态

| 子阶段 | 状态 | 退出码 |
| --- | --- | --- |
| p5_real_calibration_on_env | \`$P5_STATUS\` | \`$P5_EXIT_CODE\` |
| runtime_ops_pack | \`$RUNTIME_OPS_STATUS\` | \`$RUNTIME_OPS_EXIT_CODE\` |

## runtime ops 子状态

1. fairness_status：\`$FAIRNESS_STATUS\`
2. fairness_ingest_status：\`$FAIRNESS_INGEST_STATUS\`
3. runtime_sla_status：\`$RUNTIME_SLA_STATUS\`
4. real_env_closure_status：\`$REAL_ENV_CLOSURE_STATUS\`
5. stage_closure_evidence_status：\`$STAGE_CLOSURE_EVIDENCE_STATUS\`

## Real Pass 就绪检查

1. real_pass_ready：\`$REAL_PASS_READY\`
2. blocker_codes：\`${REAL_PASS_BLOCKER_CODES:-（无）}\`
3. blocker_hints：\`${REAL_PASS_BLOCKER_HINTS:-（无）}\`

## Real Env Readiness 输入

| 输入 | 当前值 |
| --- | --- |
| real_sample_manifest | \`${REAL_SAMPLE_MANIFEST:-（缺失）}\` |
| real_provider_ready | \`$REAL_PROVIDER_READY\` |
| real_callback_ready | \`$REAL_CALLBACK_READY\` |
| production_artifact_store_ready | \`$PRODUCTION_ARTIFACT_STORE_READY\` |
| production_artifact_store_evidence_status | \`$PRODUCTION_ARTIFACT_STORE_EVIDENCE_STATUS\` |
| production_artifact_store_evidence_roundtrip_status | \`${PRODUCTION_ARTIFACT_STORE_EVIDENCE_ROUNDTRIP_STATUS:-（无）}\` |
| benchmark_targets_ready | \`$BENCHMARK_TARGETS_READY\` |
| fairness_targets_ready | \`$FAIRNESS_TARGETS_READY\` |
| runtime_ops_targets_ready | \`$RUNTIME_OPS_TARGETS_READY\` |

1. readiness_blocker_codes：\`${REAL_ENV_READINESS_BLOCKER_CODES:-（无）}\`
2. readiness_blocker_hints：\`${REAL_ENV_READINESS_BLOCKER_HINTS:-（无）}\`
3. local_reference_evidence_link：\`$LOCAL_REFERENCE_EVIDENCE_LINK\`
4. real_evidence_link：\`$REAL_EVIDENCE_LINK\`
5. production_artifact_store_evidence_json：\`${PRODUCTION_ARTIFACT_STORE_EVIDENCE_JSON:-（无）}\`
6. production_artifact_store_evidence_blocker_code：\`${PRODUCTION_ARTIFACT_STORE_EVIDENCE_BLOCKER_CODE:-（无）}\`

## 输出工件

1. closure env：\`$OUTPUT_ENV\`
2. closure doc：\`$OUTPUT_DOC\`
3. summary json：\`$EMIT_JSON\`
4. summary md：\`$EMIT_MD\`
EOF_MD
}

write_json_summary() {
  cat >"$EMIT_JSON" <<EOF_JSON
{
  "module": "ai-judge-real-env-window-closure",
  "status": "$(json_escape "$STATUS")",
  "run_id": "$(json_escape "$RUN_ID")",
  "started_at": "$(json_escape "$STARTED_AT")",
  "finished_at": "$(json_escape "$FINISHED_AT")",
  "environment_mode": "$(json_escape "$ENV_MODE")",
  "marker_ready": "$MARKER_READY",
  "allow_local_reference": "$ALLOW_LOCAL_REFERENCE",
  "readiness": {
    "status": "$(json_escape "$REAL_ENV_READINESS_STATUS")",
    "input_ready": $([[ "$REAL_ENV_INPUT_READY" == "true" ]] && echo "true" || echo "false"),
    "blocker_codes": "$(json_escape "$REAL_ENV_READINESS_BLOCKER_CODES")",
    "blocker_hints": "$(json_escape "$REAL_ENV_READINESS_BLOCKER_HINTS")",
    "inputs": {
      "real_sample_manifest": "$(json_escape "$REAL_SAMPLE_MANIFEST")",
      "real_provider_ready": "$(json_escape "$REAL_PROVIDER_READY")",
      "real_callback_ready": "$(json_escape "$REAL_CALLBACK_READY")",
      "production_artifact_store_ready": "$(json_escape "$PRODUCTION_ARTIFACT_STORE_READY")",
      "production_artifact_store_evidence_status": "$(json_escape "$PRODUCTION_ARTIFACT_STORE_EVIDENCE_STATUS")",
      "production_artifact_store_evidence_roundtrip_status": "$(json_escape "$PRODUCTION_ARTIFACT_STORE_EVIDENCE_ROUNDTRIP_STATUS")",
      "production_artifact_store_evidence_blocker_code": "$(json_escape "$PRODUCTION_ARTIFACT_STORE_EVIDENCE_BLOCKER_CODE")",
      "benchmark_targets_ready": "$(json_escape "$BENCHMARK_TARGETS_READY")",
      "fairness_targets_ready": "$(json_escape "$FAIRNESS_TARGETS_READY")",
      "runtime_ops_targets_ready": "$(json_escape "$RUNTIME_OPS_TARGETS_READY")"
    },
    "links": {
      "local_reference_evidence": "$(json_escape "$LOCAL_REFERENCE_EVIDENCE_LINK")",
      "real_evidence": "$(json_escape "$REAL_EVIDENCE_LINK")",
      "production_artifact_store_evidence": "$(json_escape "$PRODUCTION_ARTIFACT_STORE_EVIDENCE_JSON")"
    }
  },
  "stages": [
    {
      "stage": "p5_real_calibration_on_env",
      "status": "$(json_escape "$P5_STATUS")",
      "exit_code": $P5_EXIT_CODE
    },
    {
      "stage": "runtime_ops_pack",
      "status": "$(json_escape "$RUNTIME_OPS_STATUS")",
      "exit_code": $RUNTIME_OPS_EXIT_CODE
    }
  ],
  "runtime_ops": {
    "fairness_status": "$(json_escape "$FAIRNESS_STATUS")",
    "fairness_ingest_status": "$(json_escape "$FAIRNESS_INGEST_STATUS")",
    "runtime_sla_status": "$(json_escape "$RUNTIME_SLA_STATUS")",
    "real_env_closure_status": "$(json_escape "$REAL_ENV_CLOSURE_STATUS")",
    "stage_closure_evidence_status": "$(json_escape "$STAGE_CLOSURE_EVIDENCE_STATUS")"
  },
  "real_pass": {
    "ready": $([[ "$REAL_PASS_READY" == "true" ]] && echo "true" || echo "false"),
    "blocker_codes": "$(json_escape "$REAL_PASS_BLOCKER_CODES")",
    "blocker_hints": "$(json_escape "$REAL_PASS_BLOCKER_HINTS")"
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
# ai-judge-real-env-window-closure

- status: \`$STATUS\`
- run_id: \`$RUN_ID\`
- started_at: \`$STARTED_AT\`
- finished_at: \`$FINISHED_AT\`
- environment_mode: \`$ENV_MODE\`
- marker_ready: \`$MARKER_READY\`
- allow_local_reference: \`$ALLOW_LOCAL_REFERENCE\`
- real_env_readiness_status: \`$REAL_ENV_READINESS_STATUS\`
- real_env_input_ready: \`$REAL_ENV_INPUT_READY\`
- real_pass_ready: \`$REAL_PASS_READY\`
- real_pass_blocker_codes: \`${REAL_PASS_BLOCKER_CODES:-（无）}\`

## stages

1. p5_real_calibration_on_env: \`$P5_STATUS\` (exit=\`$P5_EXIT_CODE\`)
2. runtime_ops_pack: \`$RUNTIME_OPS_STATUS\` (exit=\`$RUNTIME_OPS_EXIT_CODE\`)

## runtime_ops

1. fairness_status: \`$FAIRNESS_STATUS\`
2. fairness_ingest_status: \`$FAIRNESS_INGEST_STATUS\`
3. runtime_sla_status: \`$RUNTIME_SLA_STATUS\`
4. real_env_closure_status: \`$REAL_ENV_CLOSURE_STATUS\`
5. stage_closure_evidence_status: \`$STAGE_CLOSURE_EVIDENCE_STATUS\`

## real_pass_hints

1. \`${REAL_PASS_BLOCKER_HINTS:-（无）}\`

## real_env_readiness_inputs

1. real_sample_manifest: \`${REAL_SAMPLE_MANIFEST:-（缺失）}\`
2. real_provider_ready: \`$REAL_PROVIDER_READY\`
3. real_callback_ready: \`$REAL_CALLBACK_READY\`
4. production_artifact_store_ready: \`$PRODUCTION_ARTIFACT_STORE_READY\`
5. production_artifact_store_evidence_status: \`$PRODUCTION_ARTIFACT_STORE_EVIDENCE_STATUS\`
6. production_artifact_store_evidence_roundtrip_status: \`${PRODUCTION_ARTIFACT_STORE_EVIDENCE_ROUNDTRIP_STATUS:-（无）}\`
7. benchmark_targets_ready: \`$BENCHMARK_TARGETS_READY\`
8. fairness_targets_ready: \`$FAIRNESS_TARGETS_READY\`
9. runtime_ops_targets_ready: \`$RUNTIME_OPS_TARGETS_READY\`
10. readiness_blocker_codes: \`${REAL_ENV_READINESS_BLOCKER_CODES:-（无）}\`
11. local_reference_evidence_link: \`$LOCAL_REFERENCE_EVIDENCE_LINK\`
12. real_evidence_link: \`$REAL_EVIDENCE_LINK\`
13. production_artifact_store_evidence_json: \`${PRODUCTION_ARTIFACT_STORE_EVIDENCE_JSON:-（无）}\`
EOF_MD
}

main() {
  parse_args "$@"
  resolve_root

  if is_truthy "$ALLOW_LOCAL_REFERENCE"; then
    ALLOW_LOCAL_REFERENCE="true"
  else
    ALLOW_LOCAL_REFERENCE="false"
  fi

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
  if [[ -z "$P5_SCRIPT" ]]; then
    P5_SCRIPT="$ROOT/scripts/harness/ai_judge_p5_real_calibration_on_env.sh"
  else
    P5_SCRIPT="$(abs_path "$P5_SCRIPT")"
  fi
  if [[ -z "$RUNTIME_OPS_SCRIPT" ]]; then
    RUNTIME_OPS_SCRIPT="$ROOT/scripts/harness/ai_judge_runtime_ops_pack.sh"
  else
    RUNTIME_OPS_SCRIPT="$(abs_path "$RUNTIME_OPS_SCRIPT")"
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
  if [[ -z "$STAGE_CLOSURE_EVIDENCE_SCRIPT" ]]; then
    STAGE_CLOSURE_EVIDENCE_SCRIPT="$ROOT/scripts/harness/ai_judge_stage_closure_evidence.sh"
  else
    STAGE_CLOSURE_EVIDENCE_SCRIPT="$(abs_path "$STAGE_CLOSURE_EVIDENCE_SCRIPT")"
  fi
  if [[ -z "$OUTPUT_DOC" ]]; then
    OUTPUT_DOC="$EVIDENCE_DIR/ai_judge_real_env_window_closure.md"
  else
    OUTPUT_DOC="$(abs_path "$OUTPUT_DOC")"
  fi
  if [[ -z "$OUTPUT_ENV" ]]; then
    OUTPUT_ENV="$EVIDENCE_DIR/ai_judge_real_env_window_closure.env"
  else
    OUTPUT_ENV="$(abs_path "$OUTPUT_ENV")"
  fi

  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ai-judge-real-env-window-closure"
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

  resolve_env_mode
  derive_readiness_inputs

  local p5_json p5_md p5_stdout
  p5_json="$run_dir/p5.summary.json"
  p5_md="$run_dir/p5.summary.md"
  p5_stdout="$run_dir/p5.stdout.log"
  run_stage "p5" "$p5_json" "$p5_md" "$p5_stdout" "P5_EXIT_CODE"
  P5_STATUS="$(trim "$(read_json_status "$p5_json")")"
  if [[ -z "$P5_STATUS" ]]; then
    P5_STATUS="$(trim "$(grep -E '^ai_judge_p5_real_calibration_status:' "$p5_stdout" | tail -n 1 | awk -F ':' '{print $2}' || true)")"
  fi
  [[ -z "$P5_STATUS" ]] && P5_STATUS="unknown"

  local runtime_json runtime_md runtime_stdout
  runtime_json="$run_dir/runtime_ops_pack.summary.json"
  runtime_md="$run_dir/runtime_ops_pack.summary.md"
  runtime_stdout="$run_dir/runtime_ops_pack.stdout.log"
  run_stage "runtime_ops" "$runtime_json" "$runtime_md" "$runtime_stdout" "RUNTIME_OPS_EXIT_CODE"

  RUNTIME_OPS_STATUS="$(trim "$(read_json_status "$runtime_json")")"
  if [[ -z "$RUNTIME_OPS_STATUS" ]]; then
    RUNTIME_OPS_STATUS="$(trim "$(read_env_value "$EVIDENCE_DIR/ai_judge_runtime_ops_pack.env" "AI_JUDGE_RUNTIME_OPS_PACK_STATUS")")"
  fi
  [[ -z "$RUNTIME_OPS_STATUS" ]] && RUNTIME_OPS_STATUS="unknown"

  local runtime_env
  runtime_env="$EVIDENCE_DIR/ai_judge_runtime_ops_pack.env"
  FAIRNESS_STATUS="$(trim "$(read_env_value "$runtime_env" "FAIRNESS_STATUS")")"
  FAIRNESS_INGEST_STATUS="$(trim "$(read_env_value "$runtime_env" "FAIRNESS_INGEST_STATUS")")"
  RUNTIME_SLA_STATUS="$(trim "$(read_env_value "$runtime_env" "RUNTIME_SLA_STATUS")")"
  REAL_ENV_CLOSURE_STATUS="$(trim "$(read_env_value "$runtime_env" "REAL_ENV_CLOSURE_STATUS")")"
  STAGE_CLOSURE_EVIDENCE_STATUS="$(trim "$(read_env_value "$runtime_env" "STAGE_CLOSURE_EVIDENCE_STATUS")")"
  [[ -z "$FAIRNESS_STATUS" ]] && FAIRNESS_STATUS="unknown"
  [[ -z "$FAIRNESS_INGEST_STATUS" ]] && FAIRNESS_INGEST_STATUS="unknown"
  [[ -z "$RUNTIME_SLA_STATUS" ]] && RUNTIME_SLA_STATUS="unknown"
  [[ -z "$REAL_ENV_CLOSURE_STATUS" ]] && REAL_ENV_CLOSURE_STATUS="unknown"
  [[ -z "$STAGE_CLOSURE_EVIDENCE_STATUS" ]] && STAGE_CLOSURE_EVIDENCE_STATUS="unknown"

  derive_status
  derive_real_pass_readiness
  derive_readiness_status
  FINISHED_AT="$(iso_now)"
  write_output_env
  write_output_doc
  write_json_summary
  write_md_summary

  echo "ai_judge_real_env_window_closure_status: $STATUS"
  echo "environment_mode: $ENV_MODE (marker_ready=$MARKER_READY)"
  echo "real_env_readiness_status: $REAL_ENV_READINESS_STATUS"
  echo "real_env_input_ready: $REAL_ENV_INPUT_READY"
  echo "real_env_readiness_blocker_codes: ${REAL_ENV_READINESS_BLOCKER_CODES:-none}"
  echo "production_artifact_store_evidence_status: $PRODUCTION_ARTIFACT_STORE_EVIDENCE_STATUS"
  echo "production_artifact_store_evidence_roundtrip_status: ${PRODUCTION_ARTIFACT_STORE_EVIDENCE_ROUNDTRIP_STATUS:-none}"
  echo "p5_status: $P5_STATUS (exit=$P5_EXIT_CODE)"
  echo "runtime_ops_pack_status: $RUNTIME_OPS_STATUS (exit=$RUNTIME_OPS_EXIT_CODE)"
  echo "runtime_ops_fairness_status: $FAIRNESS_STATUS"
  echo "runtime_ops_fairness_ingest_status: $FAIRNESS_INGEST_STATUS"
  echo "runtime_ops_runtime_sla_status: $RUNTIME_SLA_STATUS"
  echo "runtime_ops_real_env_closure_status: $REAL_ENV_CLOSURE_STATUS"
  echo "runtime_ops_stage_closure_evidence_status: $STAGE_CLOSURE_EVIDENCE_STATUS"
  echo "real_pass_ready: $REAL_PASS_READY"
  echo "real_pass_blocker_codes: ${REAL_PASS_BLOCKER_CODES:-none}"
  echo "real_pass_blocker_hints: ${REAL_PASS_BLOCKER_HINTS:-none}"
  echo "output_env: $OUTPUT_ENV"
  echo "output_doc: $OUTPUT_DOC"
  echo "summary_json: $EMIT_JSON"
  echo "summary_md: $EMIT_MD"
}

main "$@"
