#!/usr/bin/env bash
set -euo pipefail

ROOT=""
BASE_URL="${AI_JUDGE_OPS_READ_MODEL_BASE_URL:-}"
PACK_PATH="${AI_JUDGE_OPS_READ_MODEL_PATH:-/internal/judge/ops/read-model/pack}"
INTERNAL_KEY="${AI_JUDGE_OPS_READ_MODEL_INTERNAL_KEY:-${AI_JUDGE_INTERNAL_KEY:-}}"
REQUEST_TIMEOUT_SECS="${AI_JUDGE_OPS_READ_MODEL_TIMEOUT_SECS:-8}"

DISPATCH_TYPE="${AI_JUDGE_OPS_READ_MODEL_DISPATCH_TYPE:-final}"
POLICY_VERSION="${AI_JUDGE_OPS_READ_MODEL_POLICY_VERSION:-}"
WINDOW_DAYS="${AI_JUDGE_OPS_READ_MODEL_WINDOW_DAYS:-7}"
TOP_LIMIT="${AI_JUDGE_OPS_READ_MODEL_TOP_LIMIT:-10}"
CASE_SCAN_LIMIT="${AI_JUDGE_OPS_READ_MODEL_CASE_SCAN_LIMIT:-200}"
INCLUDE_CASE_TRUST="${AI_JUDGE_OPS_READ_MODEL_INCLUDE_CASE_TRUST:-true}"
TRUST_CASE_LIMIT="${AI_JUDGE_OPS_READ_MODEL_TRUST_CASE_LIMIT:-5}"
DEPENDENCY_LIMIT="${AI_JUDGE_OPS_READ_MODEL_DEPENDENCY_LIMIT:-200}"
USAGE_PREVIEW_LIMIT="${AI_JUDGE_OPS_READ_MODEL_USAGE_PREVIEW_LIMIT:-20}"
RELEASE_LIMIT="${AI_JUDGE_OPS_READ_MODEL_RELEASE_LIMIT:-50}"
AUDIT_LIMIT="${AI_JUDGE_OPS_READ_MODEL_AUDIT_LIMIT:-100}"
CALIBRATION_RISK_LIMIT="${AI_JUDGE_OPS_READ_MODEL_CALIBRATION_RISK_LIMIT:-50}"
CALIBRATION_BENCHMARK_LIMIT="${AI_JUDGE_OPS_READ_MODEL_CALIBRATION_BENCHMARK_LIMIT:-200}"
CALIBRATION_SHADOW_LIMIT="${AI_JUDGE_OPS_READ_MODEL_CALIBRATION_SHADOW_LIMIT:-200}"
PANEL_PROFILE_SCAN_LIMIT="${AI_JUDGE_OPS_READ_MODEL_PANEL_PROFILE_SCAN_LIMIT:-600}"
PANEL_GROUP_LIMIT="${AI_JUDGE_OPS_READ_MODEL_PANEL_GROUP_LIMIT:-50}"
PANEL_ATTENTION_LIMIT="${AI_JUDGE_OPS_READ_MODEL_PANEL_ATTENTION_LIMIT:-20}"

OUTPUT_JSON=""
OUTPUT_MD=""
OUTPUT_ENV=""
EMIT_JSON=""
EMIT_MD=""
RUN_ID=""
STARTED_AT=""
FINISHED_AT=""
STATUS="unknown"
HTTP_CODE=""
REQUEST_ERROR=""
REQUIRED_KEYS_MISSING=""

FAIRNESS_TOTAL_MATCHED="0"
REGISTRY_INVALID_COUNT="0"
TRUST_ITEM_COUNT="0"
TRUST_ERROR_COUNT="0"
ADAPTIVE_RECOMMENDED_ACTION_COUNT="0"
ADAPTIVE_PANEL_ATTENTION_GROUP_COUNT="0"
ADAPTIVE_CALIBRATION_HIGH_RISK_COUNT="0"
OPS_COURTROOM_SAMPLE_COUNT="0"
OPS_COURTROOM_QUEUE_COUNT="0"
OPS_REVIEW_QUEUE_COUNT="0"
OPS_REVIEW_HIGH_RISK_COUNT="0"
OPS_REVIEW_TRUST_PRIORITY_COUNT="0"
OPS_REVIEW_UNIFIED_HIGH_PRIORITY_COUNT="0"
OPS_TRUST_CHALLENGE_QUEUE_COUNT="0"
OPS_TRUST_CHALLENGE_HIGH_PRIORITY_COUNT="0"
OPS_POLICY_SIM_BLOCKED_COUNT="0"

usage() {
  cat <<'USAGE'
用法:
  ai_judge_ops_read_model_export.sh \
    [--root <repo-root>] \
    --base-url <url> \
    --internal-key <key> \
    [--pack-path <path>] \
    [--timeout-secs <int>] \
    [--dispatch-type <phase|final>] \
    [--policy-version <version>] \
    [--window-days <int>] \
    [--top-limit <int>] \
    [--case-scan-limit <int>] \
    [--include-case-trust <true|false>] \
    [--trust-case-limit <int>] \
    [--dependency-limit <int>] \
    [--usage-preview-limit <int>] \
    [--release-limit <int>] \
    [--audit-limit <int>] \
    [--calibration-risk-limit <int>] \
    [--calibration-benchmark-limit <int>] \
    [--calibration-shadow-limit <int>] \
    [--panel-profile-scan-limit <int>] \
    [--panel-group-limit <int>] \
    [--panel-attention-limit <int>] \
    [--output-json <path>] \
    [--output-md <path>] \
    [--output-env <path>] \
    [--emit-json <path>] \
    [--emit-md <path>]
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

append_query_param() {
  local url="$1"
  local key="$2"
  local value="$3"
  if [[ -z "$value" ]]; then
    printf '%s' "$url"
    return
  fi
  if [[ "$url" == *"?"* ]]; then
    printf '%s&%s=%s' "$url" "$key" "$value"
  else
    printf '%s?%s=%s' "$url" "$key" "$value"
  fi
}

extract_first_number() {
  local file="$1"
  local key="$2"
  local value
  value="$(sed -n "s/.*\"${key}\":[[:space:]]*\\([0-9][0-9]*\\).*/\\1/p" "$file" | head -n 1 || true)"
  printf '%s' "${value:-0}"
}

count_token() {
  local file="$1"
  local token="$2"
  local count
  count="$(grep -o "$token" "$file" 2>/dev/null | wc -l | tr -d ' ' || true)"
  printf '%s' "${count:-0}"
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --root)
        ROOT="${2:-}"
        shift 2
        ;;
      --base-url)
        BASE_URL="${2:-}"
        shift 2
        ;;
      --pack-path)
        PACK_PATH="${2:-}"
        shift 2
        ;;
      --internal-key)
        INTERNAL_KEY="${2:-}"
        shift 2
        ;;
      --timeout-secs)
        REQUEST_TIMEOUT_SECS="${2:-}"
        shift 2
        ;;
      --dispatch-type)
        DISPATCH_TYPE="${2:-}"
        shift 2
        ;;
      --policy-version)
        POLICY_VERSION="${2:-}"
        shift 2
        ;;
      --window-days)
        WINDOW_DAYS="${2:-}"
        shift 2
        ;;
      --top-limit)
        TOP_LIMIT="${2:-}"
        shift 2
        ;;
      --case-scan-limit)
        CASE_SCAN_LIMIT="${2:-}"
        shift 2
        ;;
      --include-case-trust)
        INCLUDE_CASE_TRUST="${2:-}"
        shift 2
        ;;
      --trust-case-limit)
        TRUST_CASE_LIMIT="${2:-}"
        shift 2
        ;;
      --dependency-limit)
        DEPENDENCY_LIMIT="${2:-}"
        shift 2
        ;;
      --usage-preview-limit)
        USAGE_PREVIEW_LIMIT="${2:-}"
        shift 2
        ;;
      --release-limit)
        RELEASE_LIMIT="${2:-}"
        shift 2
        ;;
      --audit-limit)
        AUDIT_LIMIT="${2:-}"
        shift 2
        ;;
      --calibration-risk-limit)
        CALIBRATION_RISK_LIMIT="${2:-}"
        shift 2
        ;;
      --calibration-benchmark-limit)
        CALIBRATION_BENCHMARK_LIMIT="${2:-}"
        shift 2
        ;;
      --calibration-shadow-limit)
        CALIBRATION_SHADOW_LIMIT="${2:-}"
        shift 2
        ;;
      --panel-profile-scan-limit)
        PANEL_PROFILE_SCAN_LIMIT="${2:-}"
        shift 2
        ;;
      --panel-group-limit)
        PANEL_GROUP_LIMIT="${2:-}"
        shift 2
        ;;
      --panel-attention-limit)
        PANEL_ATTENTION_LIMIT="${2:-}"
        shift 2
        ;;
      --output-json)
        OUTPUT_JSON="${2:-}"
        shift 2
        ;;
      --output-md)
        OUTPUT_MD="${2:-}"
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

write_output_env() {
  local request_url="$1"
  cat >"$OUTPUT_ENV" <<EOF
AI_JUDGE_OPS_READ_MODEL_EXPORT_STATUS=$STATUS
OPS_READ_MODEL_REQUEST_URL=$request_url
OPS_READ_MODEL_HTTP_CODE=${HTTP_CODE:-000}
OPS_READ_MODEL_ERROR=$REQUEST_ERROR
OPS_READ_MODEL_REQUIRED_KEYS_MISSING=$REQUIRED_KEYS_MISSING
OPS_READ_MODEL_FAIRNESS_TOTAL_MATCHED=$FAIRNESS_TOTAL_MATCHED
OPS_READ_MODEL_REGISTRY_INVALID_COUNT=$REGISTRY_INVALID_COUNT
OPS_READ_MODEL_TRUST_ITEM_COUNT=$TRUST_ITEM_COUNT
OPS_READ_MODEL_TRUST_ERROR_COUNT=$TRUST_ERROR_COUNT
OPS_READ_MODEL_ADAPTIVE_RECOMMENDED_ACTION_COUNT=$ADAPTIVE_RECOMMENDED_ACTION_COUNT
OPS_READ_MODEL_ADAPTIVE_PANEL_ATTENTION_GROUP_COUNT=$ADAPTIVE_PANEL_ATTENTION_GROUP_COUNT
OPS_READ_MODEL_ADAPTIVE_CALIBRATION_HIGH_RISK_COUNT=$ADAPTIVE_CALIBRATION_HIGH_RISK_COUNT
OPS_READ_MODEL_COURTROOM_SAMPLE_COUNT=$OPS_COURTROOM_SAMPLE_COUNT
OPS_READ_MODEL_COURTROOM_QUEUE_COUNT=$OPS_COURTROOM_QUEUE_COUNT
OPS_READ_MODEL_REVIEW_QUEUE_COUNT=$OPS_REVIEW_QUEUE_COUNT
OPS_READ_MODEL_REVIEW_HIGH_RISK_COUNT=$OPS_REVIEW_HIGH_RISK_COUNT
OPS_READ_MODEL_REVIEW_TRUST_PRIORITY_COUNT=$OPS_REVIEW_TRUST_PRIORITY_COUNT
OPS_READ_MODEL_REVIEW_UNIFIED_HIGH_PRIORITY_COUNT=$OPS_REVIEW_UNIFIED_HIGH_PRIORITY_COUNT
OPS_READ_MODEL_TRUST_CHALLENGE_QUEUE_COUNT=$OPS_TRUST_CHALLENGE_QUEUE_COUNT
OPS_READ_MODEL_TRUST_CHALLENGE_HIGH_PRIORITY_COUNT=$OPS_TRUST_CHALLENGE_HIGH_PRIORITY_COUNT
OPS_READ_MODEL_POLICY_SIM_BLOCKED_COUNT=$OPS_POLICY_SIM_BLOCKED_COUNT
OPS_READ_MODEL_UPDATED_AT=$FINISHED_AT
EOF
}

write_output_md() {
  local request_url="$1"
  cat >"$OUTPUT_MD" <<EOF
# AI Judge Ops Read Model 导出快照

- 状态：\`$STATUS\`
- 请求：\`$request_url\`
- HTTP：\`${HTTP_CODE:-000}\`
- 更新时间：\`$FINISHED_AT\`

## 摘要

1. fairness_total_matched：\`$FAIRNESS_TOTAL_MATCHED\`
2. registry_invalid_count：\`$REGISTRY_INVALID_COUNT\`
3. trust_item_count：\`$TRUST_ITEM_COUNT\`
4. trust_error_count：\`$TRUST_ERROR_COUNT\`
5. adaptive_recommended_action_count：\`$ADAPTIVE_RECOMMENDED_ACTION_COUNT\`
6. adaptive_panel_attention_group_count：\`$ADAPTIVE_PANEL_ATTENTION_GROUP_COUNT\`
7. adaptive_calibration_high_risk_count：\`$ADAPTIVE_CALIBRATION_HIGH_RISK_COUNT\`
8. courtroom_sample_count：\`$OPS_COURTROOM_SAMPLE_COUNT\`
9. courtroom_queue_count：\`$OPS_COURTROOM_QUEUE_COUNT\`
10. review_queue_count：\`$OPS_REVIEW_QUEUE_COUNT\`
11. review_high_risk_count：\`$OPS_REVIEW_HIGH_RISK_COUNT\`
12. review_trust_priority_count：\`$OPS_REVIEW_TRUST_PRIORITY_COUNT\`
13. review_unified_high_priority_count：\`$OPS_REVIEW_UNIFIED_HIGH_PRIORITY_COUNT\`
14. trust_challenge_queue_count：\`$OPS_TRUST_CHALLENGE_QUEUE_COUNT\`
15. trust_challenge_high_priority_count：\`$OPS_TRUST_CHALLENGE_HIGH_PRIORITY_COUNT\`
16. policy_sim_blocked_count：\`$OPS_POLICY_SIM_BLOCKED_COUNT\`
17. required_keys_missing：\`${REQUIRED_KEYS_MISSING:-none}\`
EOF
}

write_summary_json() {
  local request_url="$1"
  cat >"$EMIT_JSON" <<EOF
{
  "run_id": "$(json_escape "$RUN_ID")",
  "started_at": "$(json_escape "$STARTED_AT")",
  "finished_at": "$(json_escape "$FINISHED_AT")",
  "status": "$(json_escape "$STATUS")",
  "request_url": "$(json_escape "$request_url")",
  "http_code": "$(json_escape "${HTTP_CODE:-000}")",
  "error": "$(json_escape "$REQUEST_ERROR")",
  "required_keys_missing": "$(json_escape "$REQUIRED_KEYS_MISSING")",
  "metrics": {
    "fairness_total_matched": $FAIRNESS_TOTAL_MATCHED,
    "registry_invalid_count": $REGISTRY_INVALID_COUNT,
    "trust_item_count": $TRUST_ITEM_COUNT,
    "trust_error_count": $TRUST_ERROR_COUNT,
    "adaptive_recommended_action_count": $ADAPTIVE_RECOMMENDED_ACTION_COUNT,
    "adaptive_panel_attention_group_count": $ADAPTIVE_PANEL_ATTENTION_GROUP_COUNT,
    "adaptive_calibration_high_risk_count": $ADAPTIVE_CALIBRATION_HIGH_RISK_COUNT,
    "courtroom_sample_count": $OPS_COURTROOM_SAMPLE_COUNT,
    "courtroom_queue_count": $OPS_COURTROOM_QUEUE_COUNT,
    "review_queue_count": $OPS_REVIEW_QUEUE_COUNT,
    "review_high_risk_count": $OPS_REVIEW_HIGH_RISK_COUNT,
    "review_trust_priority_count": $OPS_REVIEW_TRUST_PRIORITY_COUNT,
    "review_unified_high_priority_count": $OPS_REVIEW_UNIFIED_HIGH_PRIORITY_COUNT,
    "trust_challenge_queue_count": $OPS_TRUST_CHALLENGE_QUEUE_COUNT,
    "trust_challenge_high_priority_count": $OPS_TRUST_CHALLENGE_HIGH_PRIORITY_COUNT,
    "policy_sim_blocked_count": $OPS_POLICY_SIM_BLOCKED_COUNT
  },
  "artifacts": {
    "output_json": "$(json_escape "$OUTPUT_JSON")",
    "output_md": "$(json_escape "$OUTPUT_MD")",
    "output_env": "$(json_escape "$OUTPUT_ENV")"
  }
}
EOF
}

write_summary_md() {
  local request_url="$1"
  cat >"$EMIT_MD" <<EOF
# AI Judge Ops Read Model Export

- run_id: \`$RUN_ID\`
- status: \`$STATUS\`
- request_url: \`$request_url\`
- http_code: \`${HTTP_CODE:-000}\`
- error: \`${REQUEST_ERROR:-none}\`

## Metrics

1. fairness_total_matched: \`$FAIRNESS_TOTAL_MATCHED\`
2. registry_invalid_count: \`$REGISTRY_INVALID_COUNT\`
3. trust_item_count: \`$TRUST_ITEM_COUNT\`
4. trust_error_count: \`$TRUST_ERROR_COUNT\`
5. adaptive_recommended_action_count: \`$ADAPTIVE_RECOMMENDED_ACTION_COUNT\`
6. adaptive_panel_attention_group_count: \`$ADAPTIVE_PANEL_ATTENTION_GROUP_COUNT\`
7. adaptive_calibration_high_risk_count: \`$ADAPTIVE_CALIBRATION_HIGH_RISK_COUNT\`
8. courtroom_sample_count: \`$OPS_COURTROOM_SAMPLE_COUNT\`
9. courtroom_queue_count: \`$OPS_COURTROOM_QUEUE_COUNT\`
10. review_queue_count: \`$OPS_REVIEW_QUEUE_COUNT\`
11. review_high_risk_count: \`$OPS_REVIEW_HIGH_RISK_COUNT\`
12. review_trust_priority_count: \`$OPS_REVIEW_TRUST_PRIORITY_COUNT\`
13. review_unified_high_priority_count: \`$OPS_REVIEW_UNIFIED_HIGH_PRIORITY_COUNT\`
14. trust_challenge_queue_count: \`$OPS_TRUST_CHALLENGE_QUEUE_COUNT\`
15. trust_challenge_high_priority_count: \`$OPS_TRUST_CHALLENGE_HIGH_PRIORITY_COUNT\`
16. policy_sim_blocked_count: \`$OPS_POLICY_SIM_BLOCKED_COUNT\`
17. required_keys_missing: \`${REQUIRED_KEYS_MISSING:-none}\`
EOF
}

main() {
  parse_args "$@"
  resolve_root

  if [[ -z "$OUTPUT_JSON" ]]; then
    OUTPUT_JSON="$ROOT/docs/loadtest/evidence/ai_judge_ops_read_model_export.json"
  fi
  if [[ -z "$OUTPUT_MD" ]]; then
    OUTPUT_MD="$ROOT/docs/dev_plan/AI_Judge_Ops_Read_Model_快照-$(date_cn).md"
  fi
  if [[ -z "$OUTPUT_ENV" ]]; then
    OUTPUT_ENV="$ROOT/docs/loadtest/evidence/ai_judge_ops_read_model_export.env"
  fi
  if [[ -z "$EMIT_JSON" ]]; then
    EMIT_JSON="$ROOT/artifacts/harness/ai_judge_ops_read_model_export.summary.json"
  fi
  if [[ -z "$EMIT_MD" ]]; then
    EMIT_MD="$ROOT/artifacts/harness/ai_judge_ops_read_model_export.summary.md"
  fi

  OUTPUT_JSON="$(abs_path "$OUTPUT_JSON")"
  OUTPUT_MD="$(abs_path "$OUTPUT_MD")"
  OUTPUT_ENV="$(abs_path "$OUTPUT_ENV")"
  EMIT_JSON="$(abs_path "$EMIT_JSON")"
  EMIT_MD="$(abs_path "$EMIT_MD")"

  ensure_parent_dir "$OUTPUT_JSON"
  ensure_parent_dir "$OUTPUT_MD"
  ensure_parent_dir "$OUTPUT_ENV"
  ensure_parent_dir "$EMIT_JSON"
  ensure_parent_dir "$EMIT_MD"

  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ai-judge-ops-read-model-export"
  STARTED_AT="$(iso_now)"

  local request_url
  request_url="$(trim "$BASE_URL")"
  if [[ -z "$request_url" || -z "$(trim "$INTERNAL_KEY")" ]]; then
    STATUS="config_missing"
    REQUEST_ERROR="base_url_or_internal_key_missing"
    HTTP_CODE="000"
    FINISHED_AT="$(iso_now)"
    write_output_env ""
    write_output_md ""
    write_summary_json ""
    write_summary_md ""
    echo "ai_judge_ops_read_model_export_status: $STATUS"
    echo "ops_read_model_error: $REQUEST_ERROR"
    exit 1
  fi

  local normalized_path
  normalized_path="${PACK_PATH:-/internal/judge/ops/read-model/pack}"
  if [[ "$normalized_path" != /* ]]; then
    normalized_path="/$normalized_path"
  fi
  request_url="${request_url%/}${normalized_path}"
  request_url="$(append_query_param "$request_url" "dispatch_type" "$DISPATCH_TYPE")"
  request_url="$(append_query_param "$request_url" "policy_version" "$POLICY_VERSION")"
  request_url="$(append_query_param "$request_url" "window_days" "$WINDOW_DAYS")"
  request_url="$(append_query_param "$request_url" "top_limit" "$TOP_LIMIT")"
  request_url="$(append_query_param "$request_url" "case_scan_limit" "$CASE_SCAN_LIMIT")"
  request_url="$(append_query_param "$request_url" "include_case_trust" "$INCLUDE_CASE_TRUST")"
  request_url="$(append_query_param "$request_url" "trust_case_limit" "$TRUST_CASE_LIMIT")"
  request_url="$(append_query_param "$request_url" "dependency_limit" "$DEPENDENCY_LIMIT")"
  request_url="$(append_query_param "$request_url" "usage_preview_limit" "$USAGE_PREVIEW_LIMIT")"
  request_url="$(append_query_param "$request_url" "release_limit" "$RELEASE_LIMIT")"
  request_url="$(append_query_param "$request_url" "audit_limit" "$AUDIT_LIMIT")"
  request_url="$(append_query_param "$request_url" "calibration_risk_limit" "$CALIBRATION_RISK_LIMIT")"
  request_url="$(append_query_param "$request_url" "calibration_benchmark_limit" "$CALIBRATION_BENCHMARK_LIMIT")"
  request_url="$(append_query_param "$request_url" "calibration_shadow_limit" "$CALIBRATION_SHADOW_LIMIT")"
  request_url="$(append_query_param "$request_url" "panel_profile_scan_limit" "$PANEL_PROFILE_SCAN_LIMIT")"
  request_url="$(append_query_param "$request_url" "panel_group_limit" "$PANEL_GROUP_LIMIT")"
  request_url="$(append_query_param "$request_url" "panel_attention_limit" "$PANEL_ATTENTION_LIMIT")"

  local timeout_secs
  timeout_secs="$(trim "$REQUEST_TIMEOUT_SECS")"
  if ! [[ "$timeout_secs" =~ ^[0-9]+$ ]] || [[ "$timeout_secs" -le 0 ]]; then
    timeout_secs="8"
  fi

  local stderr_file
  stderr_file="$ROOT/artifacts/harness/${RUN_ID}.curl.stderr.log"
  set +e
  HTTP_CODE="$(curl \
    -sS \
    -o "$OUTPUT_JSON" \
    -w "%{http_code}" \
    --connect-timeout "$timeout_secs" \
    --max-time "$timeout_secs" \
    -H "x-ai-internal-key: $INTERNAL_KEY" \
    "$request_url" \
    2>"$stderr_file")"
  local curl_code="$?"
  set -e

  if [[ "$curl_code" -ne 0 ]]; then
    STATUS="request_failed"
    REQUEST_ERROR="curl_exit_${curl_code}"
  elif ! [[ "$HTTP_CODE" =~ ^2[0-9][0-9]$ ]]; then
    STATUS="request_failed"
    REQUEST_ERROR="http_${HTTP_CODE:-000}"
  else
    STATUS="pass"
  fi

  if [[ "$STATUS" == "pass" ]]; then
    local required_key
    for required_key in "\"fairnessDashboard\"" "\"fairnessCalibrationAdvisor\"" "\"panelRuntimeReadiness\"" "\"registryGovernance\"" "\"courtroomReadModel\"" "\"courtroomQueue\"" "\"reviewQueue\"" "\"reviewTrustPriority\"" "\"trustChallengeQueue\"" "\"policyGateSimulation\"" "\"adaptiveSummary\"" "\"trustOverview\"" "\"filters\""; do
      if ! grep -Fq "$required_key" "$OUTPUT_JSON"; then
        REQUIRED_KEYS_MISSING="${REQUIRED_KEYS_MISSING:+$REQUIRED_KEYS_MISSING;}${required_key}"
      fi
    done
    if [[ -n "$REQUIRED_KEYS_MISSING" ]]; then
      STATUS="payload_invalid"
      REQUEST_ERROR="required_keys_missing"
    fi
  fi

  if [[ -f "$OUTPUT_JSON" ]]; then
    FAIRNESS_TOTAL_MATCHED="$(extract_first_number "$OUTPUT_JSON" "totalMatched")"
    REGISTRY_INVALID_COUNT="$(extract_first_number "$OUTPUT_JSON" "invalidCount")"
    TRUST_ITEM_COUNT="$(count_token "$OUTPUT_JSON" "\"verdictVerified\"")"
    TRUST_ERROR_COUNT="$(extract_first_number "$OUTPUT_JSON" "errorCount")"
    ADAPTIVE_RECOMMENDED_ACTION_COUNT="$(extract_first_number "$OUTPUT_JSON" "recommendedActionCount")"
    ADAPTIVE_PANEL_ATTENTION_GROUP_COUNT="$(extract_first_number "$OUTPUT_JSON" "panelAttentionGroupCount")"
    ADAPTIVE_CALIBRATION_HIGH_RISK_COUNT="$(extract_first_number "$OUTPUT_JSON" "calibrationHighRiskCount")"
    OPS_COURTROOM_SAMPLE_COUNT="$(extract_first_number "$OUTPUT_JSON" "courtroomSampleCount")"
    OPS_COURTROOM_QUEUE_COUNT="$(extract_first_number "$OUTPUT_JSON" "courtroomQueueCount")"
    OPS_REVIEW_QUEUE_COUNT="$(extract_first_number "$OUTPUT_JSON" "reviewQueueCount")"
    OPS_REVIEW_HIGH_RISK_COUNT="$(extract_first_number "$OUTPUT_JSON" "reviewHighRiskCount")"
    OPS_REVIEW_TRUST_PRIORITY_COUNT="$(extract_first_number "$OUTPUT_JSON" "reviewTrustPriorityCount")"
    OPS_REVIEW_UNIFIED_HIGH_PRIORITY_COUNT="$(extract_first_number "$OUTPUT_JSON" "reviewUnifiedHighPriorityCount")"
    OPS_TRUST_CHALLENGE_QUEUE_COUNT="$(extract_first_number "$OUTPUT_JSON" "trustChallengeQueueCount")"
    OPS_TRUST_CHALLENGE_HIGH_PRIORITY_COUNT="$(extract_first_number "$OUTPUT_JSON" "trustChallengeHighPriorityCount")"
    OPS_POLICY_SIM_BLOCKED_COUNT="$(extract_first_number "$OUTPUT_JSON" "policySimulationBlockedCount")"
  fi

  FINISHED_AT="$(iso_now)"
  write_output_env "$request_url"
  write_output_md "$request_url"
  write_summary_json "$request_url"
  write_summary_md "$request_url"

  echo "ai_judge_ops_read_model_export_status: $STATUS"
  echo "ops_read_model_request_url: $request_url"
  echo "ops_read_model_http_code: ${HTTP_CODE:-000}"
  echo "required_keys_missing: ${REQUIRED_KEYS_MISSING:-none}"
  echo "output_json: $OUTPUT_JSON"
  echo "output_md: $OUTPUT_MD"
  echo "output_env: $OUTPUT_ENV"
  echo "summary_json: $EMIT_JSON"
  echo "summary_md: $EMIT_MD"

  if [[ "$STATUS" != "pass" ]]; then
    exit 1
  fi
}

main "$@"
