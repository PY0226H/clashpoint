#!/usr/bin/env bash
set -euo pipefail

ROOT=""
BASE_URL="${AI_JUDGE_FAIRNESS_DASHBOARD_BASE_URL:-}"
DASHBOARD_PATH="${AI_JUDGE_FAIRNESS_DASHBOARD_PATH:-/internal/judge/fairness/dashboard}"
INTERNAL_KEY="${AI_JUDGE_FAIRNESS_DASHBOARD_INTERNAL_KEY:-${AI_JUDGE_INTERNAL_KEY:-}}"
REQUEST_TIMEOUT_SECS="${AI_JUDGE_FAIRNESS_DASHBOARD_TIMEOUT_SECS:-8}"

DISPATCH_TYPE="final"
STATUS_FILTER=""
WINNER_FILTER=""
POLICY_VERSION=""
CHALLENGE_STATE=""
WINDOW_DAYS="7"
TOP_LIMIT="10"
CASE_SCAN_LIMIT="200"

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
TOTAL_MATCHED="0"
SHADOW_BREACH_COUNT="0"
TOP_RISK_COUNT="0"
CASE_DAILY_POINTS="0"

usage() {
  cat <<'USAGE'
用法:
  ai_judge_fairness_dashboard_export.sh \
    [--root <repo-root>] \
    [--base-url <url>] \
    [--dashboard-path <path>] \
    [--internal-key <key>] \
    [--timeout-secs <int>] \
    [--dispatch-type <final|phase>] \
    [--status <value>] \
    [--winner <pro|con|draw>] \
    [--policy-version <value>] \
    [--challenge-state <value>] \
    [--window-days <1-30>] \
    [--top-limit <1-50>] \
    [--case-scan-limit <20-1000>] \
    [--output-json <path>] \
    [--output-md <path>] \
    [--output-env <path>] \
    [--emit-json <path>] \
    [--emit-md <path>]

说明:
  - 调用 AI Judge fairness dashboard 聚合接口并导出本地证据。
  - 目标键位: overview / trends / topRiskCases / gateDistribution。
  - 成功时输出 status=pass；请求失败或结构缺失时返回非 0。
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
      --dashboard-path)
        DASHBOARD_PATH="${2:-}"
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
      --status)
        STATUS_FILTER="${2:-}"
        shift 2
        ;;
      --winner)
        WINNER_FILTER="${2:-}"
        shift 2
        ;;
      --policy-version)
        POLICY_VERSION="${2:-}"
        shift 2
        ;;
      --challenge-state)
        CHALLENGE_STATE="${2:-}"
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
  cat >"$OUTPUT_ENV" <<EOF_ENV
AI_JUDGE_FAIRNESS_DASHBOARD_EXPORT_STATUS=$STATUS
FAIRNESS_DASHBOARD_REQUEST_URL=$request_url
FAIRNESS_DASHBOARD_HTTP_CODE=$HTTP_CODE
FAIRNESS_DASHBOARD_ERROR=$REQUEST_ERROR
FAIRNESS_DASHBOARD_REQUIRED_KEYS_MISSING=$REQUIRED_KEYS_MISSING
FAIRNESS_DASHBOARD_TOTAL_MATCHED=$TOTAL_MATCHED
FAIRNESS_DASHBOARD_SHADOW_BREACH_COUNT=$SHADOW_BREACH_COUNT
FAIRNESS_DASHBOARD_TOP_RISK_COUNT=$TOP_RISK_COUNT
FAIRNESS_DASHBOARD_CASE_DAILY_POINTS=$CASE_DAILY_POINTS
FAIRNESS_DASHBOARD_UPDATED_AT=$FINISHED_AT
EOF_ENV
}

write_output_md() {
  local request_url="$1"
  cat >"$OUTPUT_MD" <<EOF_MD
# AI Judge Fairness Dashboard 导出快照

更新时间：$(date_cn)
状态：$STATUS

## 1. 请求信息

1. request_url: \`$request_url\`
2. http_code: \`${HTTP_CODE:-（无）}\`
3. request_error: \`${REQUEST_ERROR:-（无）}\`

## 2. 核心概览

1. total_matched: \`$TOTAL_MATCHED\`
2. shadow_breach_count: \`$SHADOW_BREACH_COUNT\`
3. top_risk_count: \`$TOP_RISK_COUNT\`
4. case_daily_points: \`$CASE_DAILY_POINTS\`

## 3. 结构校验

1. required_keys_missing: \`${REQUIRED_KEYS_MISSING:-（无）}\`
2. expected_keys: \`overview / trends / topRiskCases / gateDistribution\`

## 4. 输出位置

1. output_json: \`$OUTPUT_JSON\`
2. output_env: \`$OUTPUT_ENV\`
3. summary_json: \`$EMIT_JSON\`
4. summary_md: \`$EMIT_MD\`
EOF_MD
}

write_summary_json() {
  local request_url="$1"
  {
    printf '{\n'
    printf '  "run_id": "%s",\n' "$(json_escape "$RUN_ID")"
    printf '  "status": "%s",\n' "$(json_escape "$STATUS")"
    printf '  "root": "%s",\n' "$(json_escape "$ROOT")"
    printf '  "request_url": "%s",\n' "$(json_escape "$request_url")"
    printf '  "http_code": "%s",\n' "$(json_escape "$HTTP_CODE")"
    printf '  "request_error": "%s",\n' "$(json_escape "$REQUEST_ERROR")"
    printf '  "required_keys_missing": "%s",\n' "$(json_escape "$REQUIRED_KEYS_MISSING")"
    printf '  "metrics": {\n'
    printf '    "total_matched": %s,\n' "$(json_escape "$TOTAL_MATCHED")"
    printf '    "shadow_breach_count": %s,\n' "$(json_escape "$SHADOW_BREACH_COUNT")"
    printf '    "top_risk_count": %s,\n' "$(json_escape "$TOP_RISK_COUNT")"
    printf '    "case_daily_points": %s\n' "$(json_escape "$CASE_DAILY_POINTS")"
    printf '  },\n'
    printf '  "filters": {\n'
    printf '    "dispatch_type": "%s",\n' "$(json_escape "$DISPATCH_TYPE")"
    printf '    "status": "%s",\n' "$(json_escape "$STATUS_FILTER")"
    printf '    "winner": "%s",\n' "$(json_escape "$WINNER_FILTER")"
    printf '    "policy_version": "%s",\n' "$(json_escape "$POLICY_VERSION")"
    printf '    "challenge_state": "%s",\n' "$(json_escape "$CHALLENGE_STATE")"
    printf '    "window_days": "%s",\n' "$(json_escape "$WINDOW_DAYS")"
    printf '    "top_limit": "%s",\n' "$(json_escape "$TOP_LIMIT")"
    printf '    "case_scan_limit": "%s"\n' "$(json_escape "$CASE_SCAN_LIMIT")"
    printf '  },\n'
    printf '  "started_at": "%s",\n' "$(json_escape "$STARTED_AT")"
    printf '  "finished_at": "%s",\n' "$(json_escape "$FINISHED_AT")"
    printf '  "outputs": {\n'
    printf '    "dashboard_json": "%s",\n' "$(json_escape "$OUTPUT_JSON")"
    printf '    "dashboard_md": "%s",\n' "$(json_escape "$OUTPUT_MD")"
    printf '    "dashboard_env": "%s",\n' "$(json_escape "$OUTPUT_ENV")"
    printf '    "summary_json": "%s",\n' "$(json_escape "$EMIT_JSON")"
    printf '    "summary_md": "%s"\n' "$(json_escape "$EMIT_MD")"
    printf '  }\n'
    printf '}\n'
  } >"$EMIT_JSON"
}

write_summary_md() {
  local request_url="$1"
  {
    printf '# AI Judge Fairness Dashboard Export\n\n'
    printf -- '- run_id: `%s`\n' "$RUN_ID"
    printf -- '- status: `%s`\n' "$STATUS"
    printf -- '- request_url: `%s`\n' "$request_url"
    printf -- '- http_code: `%s`\n' "$HTTP_CODE"
    printf -- '- request_error: `%s`\n' "$REQUEST_ERROR"
    printf -- '- required_keys_missing: `%s`\n' "${REQUIRED_KEYS_MISSING:-none}"
    printf -- '- total_matched: `%s`\n' "$TOTAL_MATCHED"
    printf -- '- shadow_breach_count: `%s`\n' "$SHADOW_BREACH_COUNT"
    printf -- '- top_risk_count: `%s`\n' "$TOP_RISK_COUNT"
    printf -- '- case_daily_points: `%s`\n' "$CASE_DAILY_POINTS"
    printf -- '- output_json: `%s`\n' "$OUTPUT_JSON"
    printf -- '- output_md: `%s`\n' "$OUTPUT_MD"
    printf -- '- output_env: `%s`\n' "$OUTPUT_ENV"
    printf -- '- started_at: `%s`\n' "$STARTED_AT"
    printf -- '- finished_at: `%s`\n' "$FINISHED_AT"
  } >"$EMIT_MD"
}

main() {
  parse_args "$@"
  resolve_root

  if [[ -z "$OUTPUT_JSON" ]]; then
    OUTPUT_JSON="$ROOT/docs/loadtest/evidence/ai_judge_fairness_dashboard_export.json"
  else
    OUTPUT_JSON="$(abs_path "$OUTPUT_JSON")"
  fi
  if [[ -z "$OUTPUT_MD" ]]; then
    OUTPUT_MD="$ROOT/docs/dev_plan/AI_Judge_Fairness_Dashboard_快照-$(date_cn).md"
  else
    OUTPUT_MD="$(abs_path "$OUTPUT_MD")"
  fi
  if [[ -z "$OUTPUT_ENV" ]]; then
    OUTPUT_ENV="$ROOT/docs/loadtest/evidence/ai_judge_fairness_dashboard_export.env"
  else
    OUTPUT_ENV="$(abs_path "$OUTPUT_ENV")"
  fi

  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ai-judge-fairness-dashboard-export"
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

  ensure_parent_dir "$OUTPUT_JSON"
  ensure_parent_dir "$OUTPUT_MD"
  ensure_parent_dir "$OUTPUT_ENV"
  ensure_parent_dir "$EMIT_JSON"
  ensure_parent_dir "$EMIT_MD"

  local normalized_path
  normalized_path="${DASHBOARD_PATH:-/internal/judge/fairness/dashboard}"
  if [[ "${normalized_path:0:1}" != "/" ]]; then
    normalized_path="/$normalized_path"
  fi
  local request_url
  request_url="${BASE_URL%/}${normalized_path}"
  request_url="$(append_query_param "$request_url" "dispatch_type" "$DISPATCH_TYPE")"
  request_url="$(append_query_param "$request_url" "status" "$STATUS_FILTER")"
  request_url="$(append_query_param "$request_url" "winner" "$WINNER_FILTER")"
  request_url="$(append_query_param "$request_url" "policy_version" "$POLICY_VERSION")"
  request_url="$(append_query_param "$request_url" "challenge_state" "$CHALLENGE_STATE")"
  request_url="$(append_query_param "$request_url" "window_days" "$WINDOW_DAYS")"
  request_url="$(append_query_param "$request_url" "top_limit" "$TOP_LIMIT")"
  request_url="$(append_query_param "$request_url" "case_scan_limit" "$CASE_SCAN_LIMIT")"

  if [[ -z "$BASE_URL" || -z "$INTERNAL_KEY" ]]; then
    STATUS="misconfigured"
    REQUEST_ERROR="missing_base_url_or_internal_key"
    FINISHED_AT="$(iso_now)"
    write_output_env "$request_url"
    write_output_md "$request_url"
    write_summary_json "$request_url"
    write_summary_md "$request_url"
    echo "ai_judge_fairness_dashboard_export_status: $STATUS"
    echo "dashboard_request_url: $request_url"
    echo "dashboard_http_code: ${HTTP_CODE:-000}"
    echo "required_keys_missing: ${REQUIRED_KEYS_MISSING:-none}"
    echo "summary_json: $EMIT_JSON"
    echo "summary_md: $EMIT_MD"
    exit 1
  fi

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
    for required_key in "\"overview\"" "\"trends\"" "\"topRiskCases\"" "\"gateDistribution\""; do
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
    TOTAL_MATCHED="$(extract_first_number "$OUTPUT_JSON" "totalMatched")"
    SHADOW_BREACH_COUNT="$(extract_first_number "$OUTPUT_JSON" "shadowBreachCount")"
    TOP_RISK_COUNT="$(count_token "$OUTPUT_JSON" "\"riskScore\"")"
    CASE_DAILY_POINTS="$(count_token "$OUTPUT_JSON" "\"date\"")"
  fi

  FINISHED_AT="$(iso_now)"
  write_output_env "$request_url"
  write_output_md "$request_url"
  write_summary_json "$request_url"
  write_summary_md "$request_url"

  echo "ai_judge_fairness_dashboard_export_status: $STATUS"
  echo "dashboard_request_url: $request_url"
  echo "dashboard_http_code: ${HTTP_CODE:-000}"
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
