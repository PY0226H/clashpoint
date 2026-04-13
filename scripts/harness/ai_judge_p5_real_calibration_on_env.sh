#!/usr/bin/env bash
set -euo pipefail

ROOT=""
EVIDENCE_DIR=""
ENV_MARKER_FILE=""
EMIT_JSON=""
EMIT_MD=""
RUN_ID=""
STARTED_AT=""
FINISHED_AT=""
STATUS="pass"
ENV_READY="false"

# 与 calibration_prep 保持一致的五类轨道。
declare -a TRACK_IDS=(
  "latency_baseline"
  "cost_baseline"
  "fairness_benchmark"
  "fault_drill"
  "trust_attestation"
)

usage() {
  cat <<'USAGE'
用法:
  ai_judge_p5_real_calibration_on_env.sh \
    [--root <repo-root>] \
    [--evidence-dir <path>] \
    [--env-marker <path>] \
    [--emit-json <path>] \
    [--emit-md <path>]

说明:
  - 执行 P5 真实环境校准门禁检查。
  - 若真实环境未就绪，返回 env_blocked；
  - 仅当环境就绪且五类轨道均满足 real calibration 证据键时返回 pass。
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

track_title() {
  case "$1" in
    latency_baseline) printf '%s' "Latency Baseline" ;;
    cost_baseline) printf '%s' "Cost Baseline" ;;
    fairness_benchmark) printf '%s' "Fairness Benchmark" ;;
    fault_drill) printf '%s' "Fault Drill" ;;
    trust_attestation) printf '%s' "Trust Attestation" ;;
    *) printf '%s' "$1" ;;
  esac
}

track_file_name() {
  case "$1" in
    latency_baseline) printf '%s' "ai_judge_p5_latency_baseline.env" ;;
    cost_baseline) printf '%s' "ai_judge_p5_cost_baseline.env" ;;
    fairness_benchmark) printf '%s' "ai_judge_p5_fairness_benchmark.env" ;;
    fault_drill) printf '%s' "ai_judge_p5_fault_drill.env" ;;
    trust_attestation) printf '%s' "ai_judge_p5_trust_attestation.env" ;;
    *) printf '%s' "ai_judge_p5_${1}.env" ;;
  esac
}

track_required_keys() {
  case "$1" in
    latency_baseline)
      printf '%s' "CALIBRATION_STATUS;WINDOW_FROM;WINDOW_TO;SAMPLE_SIZE;P95_MS;P99_MS"
      ;;
    cost_baseline)
      printf '%s' "CALIBRATION_STATUS;WINDOW_FROM;WINDOW_TO;TOKEN_INPUT_TOTAL;TOKEN_OUTPUT_TOTAL;COST_USD_TOTAL;COST_USD_PER_1K"
      ;;
    fairness_benchmark)
      printf '%s' "CALIBRATION_STATUS;WINDOW_FROM;WINDOW_TO;SAMPLE_SIZE;DRAW_RATE;SIDE_BIAS_DELTA;APPEAL_OVERTURN_RATE"
      ;;
    fault_drill)
      printf '%s' "CALIBRATION_STATUS;DRILL_RUN_AT;CALLBACK_FAILURE_RECOVERY_PASS;REPLAY_CONSISTENCY_PASS;AUDIT_ALERT_DELIVERY_PASS"
      ;;
    trust_attestation)
      printf '%s' "CALIBRATION_STATUS;TRACE_HASH_COVERAGE;COMMITMENT_COVERAGE;ATTESTATION_GAP"
      ;;
    *)
      printf '%s' "CALIBRATION_STATUS"
      ;;
  esac
}

track_real_required_keys() {
  printf '%s' "REAL_ENV_EVIDENCE;CALIBRATED_AT;CALIBRATED_BY;DATASET_REF"
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

is_truthy() {
  local value
  value="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  [[ "$value" == "1" || "$value" == "true" || "$value" == "yes" || "$value" == "on" ]]
}

collect_missing_keys() {
  local file="$1"
  local required="$2"
  local key val missing=""

  while IFS= read -r key || [[ -n "$key" ]]; do
    key="$(trim "$key")"
    [[ -z "$key" ]] && continue
    val="$(trim "$(read_env_value "$file" "$key")")"
    if [[ -z "$val" ]]; then
      missing="${missing:+${missing};}${key}"
    fi
  done < <(printf '%s' "$required" | tr ';' '\n')

  printf '%s' "$missing"
}

resolve_environment_ready() {
  if [[ ! -f "$ENV_MARKER_FILE" ]]; then
    ENV_READY="false"
    return
  fi

  local value
  value="$(trim "$(read_env_value "$ENV_MARKER_FILE" "REAL_CALIBRATION_ENV_READY")")"
  if is_truthy "$value"; then
    ENV_READY="true"
  else
    ENV_READY="false"
  fi
}

collect_track_result() {
  local track_id="$1"
  local title="$2"
  local file="$3"
  local required="$4"
  local real_required="$5"
  local out_file="$6"

  local status="pass"
  local note="validated"
  local missing_base=""
  local missing_real=""
  local missing_base_out="（无）"
  local missing_real_out="（无）"

  if [[ ! -f "$file" ]]; then
    status="evidence_missing"
    note="evidence file missing"
  else
    local calibration_status
    calibration_status="$(trim "$(read_env_value "$file" "CALIBRATION_STATUS")")"

    missing_base="$(collect_missing_keys "$file" "$required")"
    missing_real="$(collect_missing_keys "$file" "$real_required")"

    if [[ "$ENV_READY" != "true" ]]; then
      status="env_blocked"
      note="real environment not ready"
    elif [[ "$calibration_status" == "blocked" ]]; then
      status="env_blocked"
      note="calibration explicitly blocked"
    elif [[ "$calibration_status" != "validated" ]]; then
      status="pending_real_data"
      note="calibration_status is ${calibration_status:-missing}"
    elif [[ -n "$missing_base" || -n "$missing_real" ]]; then
      status="pending_real_data"
      note="missing keys: ${missing_base}${missing_base:+;}${missing_real}"
    else
      status="pass"
      note="validated with real env evidence"
    fi
  fi

  missing_base_out="${missing_base:-（无）}"
  missing_real_out="${missing_real:-（无）}"

  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$track_id" \
    "$title" \
    "$status" \
    "$file" \
    "$missing_base_out" \
    "$missing_real_out" \
    "$note" >>"$out_file"
}

update_overall_status() {
  local records="$1"
  local line track_status

  if [[ "$ENV_READY" != "true" ]]; then
    STATUS="env_blocked"
  else
    STATUS="pass"
  fi

  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" ]] && continue
    track_status="$(printf '%s' "$line" | awk -F '\t' '{print $3}')"

    case "$track_status" in
      fail)
        STATUS="fail"
        return
        ;;
      env_blocked)
        if [[ "$STATUS" != "fail" ]]; then
          STATUS="env_blocked"
        fi
        ;;
      evidence_missing)
        if [[ "$STATUS" == "pass" || "$STATUS" == "pending_real_data" ]]; then
          STATUS="evidence_missing"
        fi
        ;;
      pending_real_data)
        if [[ "$STATUS" == "pass" ]]; then
          STATUS="pending_real_data"
        fi
        ;;
      *)
        ;;
    esac
  done <"$records"
}

write_json() {
  local records="$1"

  local total=0
  local pass_total=0
  local pending_total=0
  local missing_total=0
  local blocked_total=0
  local fail_total=0
  local line track_status

  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" ]] && continue
    track_status="$(printf '%s' "$line" | awk -F '\t' '{print $3}')"
    total=$((total + 1))
    case "$track_status" in
      pass) pass_total=$((pass_total + 1)) ;;
      pending_real_data) pending_total=$((pending_total + 1)) ;;
      evidence_missing) missing_total=$((missing_total + 1)) ;;
      env_blocked) blocked_total=$((blocked_total + 1)) ;;
      fail) fail_total=$((fail_total + 1)) ;;
      *) ;;
    esac
  done <"$records"

  {
    printf '{\n'
    printf '  "run_id": "%s",\n' "$(json_escape "$RUN_ID")"
    printf '  "root": "%s",\n' "$(json_escape "$ROOT")"
    printf '  "status": "%s",\n' "$(json_escape "$STATUS")"
    printf '  "environment_ready": %s,\n' "$([[ "$ENV_READY" == "true" ]] && echo true || echo false)"
    printf '  "env_marker_file": "%s",\n' "$(json_escape "$ENV_MARKER_FILE")"
    printf '  "evidence_dir": "%s",\n' "$(json_escape "$EVIDENCE_DIR")"
    printf '  "started_at": "%s",\n' "$(json_escape "$STARTED_AT")"
    printf '  "finished_at": "%s",\n' "$(json_escape "$FINISHED_AT")"
    printf '  "outputs": {\n'
    printf '    "json": "%s",\n' "$(json_escape "$EMIT_JSON")"
    printf '    "markdown": "%s"\n' "$(json_escape "$EMIT_MD")"
    printf '  },\n'
    printf '  "counts": {\n'
    printf '    "total": %s,\n' "$total"
    printf '    "pass_total": %s,\n' "$pass_total"
    printf '    "pending_real_data_total": %s,\n' "$pending_total"
    printf '    "evidence_missing_total": %s,\n' "$missing_total"
    printf '    "env_blocked_total": %s,\n' "$blocked_total"
    printf '    "fail_total": %s\n' "$fail_total"
    printf '  },\n'
    printf '  "tracks": [\n'

    local first=1
    local track_id title status file missing_base missing_real note
    while IFS=$'\t' read -r track_id title status file missing_base missing_real note; do
      [[ -z "${track_id:-}" ]] && continue
      printf '    %s{"track_id":"%s","title":"%s","status":"%s","evidence_file":"%s","missing_base_keys":"%s","missing_real_keys":"%s","note":"%s"}\n' \
        "$([[ "$first" -eq 1 ]] && echo "" || echo ",")" \
        "$(json_escape "$track_id")" \
        "$(json_escape "$title")" \
        "$(json_escape "$status")" \
        "$(json_escape "$file")" \
        "$(json_escape "$missing_base")" \
        "$(json_escape "$missing_real")" \
        "$(json_escape "$note")"
      first=0
    done <"$records"

    printf '  ]\n'
    printf '}\n'
  } >"$EMIT_JSON"
}

write_markdown() {
  local records="$1"

  {
    printf '# AI Judge P5 Real Calibration (On Env)\n\n'
    printf -- '- run_id: `%s`\n' "$RUN_ID"
    printf -- '- status: `%s`\n' "$STATUS"
    printf -- '- environment_ready: `%s`\n' "$ENV_READY"
    printf -- '- env_marker_file: `%s`\n' "$ENV_MARKER_FILE"
    printf -- '- evidence_dir: `%s`\n' "$EVIDENCE_DIR"
    printf -- '- started_at: `%s`\n' "$STARTED_AT"
    printf -- '- finished_at: `%s`\n' "$FINISHED_AT"
    printf -- '- output_json: `%s`\n' "$EMIT_JSON"
    printf -- '- output_md: `%s`\n' "$EMIT_MD"

    printf '\n## Track Status\n\n'
    printf '| Track | Status | Missing Base Keys | Missing Real Keys | Note |\n'
    printf '|---|---|---|---|---|\n'

    local track_id title status file missing_base missing_real note
    while IFS=$'\t' read -r track_id title status file missing_base missing_real note; do
      [[ -z "${track_id:-}" ]] && continue
      printf '| %s | %s | %s | %s | %s |\n' "$title" "$status" "${missing_base:-（无）}" "${missing_real:-（无）}" "$note"
    done <"$records"
  } >"$EMIT_MD"
}

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
      ENV_MARKER_FILE="${2:-}"
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

resolve_root

if [[ -z "$EVIDENCE_DIR" ]]; then
  EVIDENCE_DIR="$ROOT/docs/loadtest/evidence"
else
  EVIDENCE_DIR="$(abs_path "$EVIDENCE_DIR")"
fi

if [[ -z "$ENV_MARKER_FILE" ]]; then
  ENV_MARKER_FILE="$EVIDENCE_DIR/ai_judge_p5_real_env.env"
else
  ENV_MARKER_FILE="$(abs_path "$ENV_MARKER_FILE")"
fi

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ai-judge-p5-real-calibration-on-env"
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

resolve_environment_ready

records_file="$(mktemp)"

for track_id in "${TRACK_IDS[@]}"; do
  title="$(track_title "$track_id")"
  file="$EVIDENCE_DIR/$(track_file_name "$track_id")"
  required="$(track_required_keys "$track_id")"
  real_required="$(track_real_required_keys)"
  collect_track_result "$track_id" "$title" "$file" "$required" "$real_required" "$records_file"
done

update_overall_status "$records_file"
FINISHED_AT="$(iso_now)"

write_json "$records_file"
write_markdown "$records_file"

printf 'ai_judge_p5_real_calibration_status: %s\n' "$STATUS"
printf 'ai_judge_p5_real_calibration_json: %s\n' "$EMIT_JSON"
printf 'ai_judge_p5_real_calibration_md: %s\n' "$EMIT_MD"
printf 'environment_ready: %s\n' "$ENV_READY"

rm -f "$records_file"
