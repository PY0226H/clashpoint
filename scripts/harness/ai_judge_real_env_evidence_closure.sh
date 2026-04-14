#!/usr/bin/env bash
set -euo pipefail

ROOT=""
EVIDENCE_DIR=""
ENV_MARKER_FILE=""
OUTPUT_DOC=""
OUTPUT_ENV=""
EMIT_JSON=""
EMIT_MD=""
RUN_ID=""
STARTED_AT=""
FINISHED_AT=""
STATUS="pass"
ENV_MODE="blocked"
ALLOW_LOCAL_REFERENCE="${AI_JUDGE_ALLOW_LOCAL_REFERENCE:-false}"

declare -a TRACK_IDS=(
  "latency_baseline"
  "cost_baseline"
  "fairness_benchmark"
  "fault_drill"
  "trust_attestation"
  "runtime_sla_freeze"
)

usage() {
  cat <<'USAGE'
用法:
  ai_judge_real_env_evidence_closure.sh \
    [--root <repo-root>] \
    [--evidence-dir <path>] \
    [--env-marker <path>] \
    [--allow-local-reference] \
    [--output-doc <path>] \
    [--output-env <path>] \
    [--emit-json <path>] \
    [--emit-md <path>]

说明:
  - 对 ai_judge P5/P6 六轨道执行 real-env 证据收口检查。
  - 输出 real-env 缺口清单（按轨道列出缺失键）与统一状态：
    pass/local_reference_ready/local_reference_pending/env_blocked/pending_real_evidence/evidence_missing。
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

track_title() {
  case "$1" in
    latency_baseline) printf '%s' "Latency Baseline" ;;
    cost_baseline) printf '%s' "Cost Baseline" ;;
    fairness_benchmark) printf '%s' "Fairness Benchmark" ;;
    fault_drill) printf '%s' "Fault Drill" ;;
    trust_attestation) printf '%s' "Trust Attestation" ;;
    runtime_sla_freeze) printf '%s' "Runtime SLA Freeze" ;;
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
    runtime_sla_freeze) printf '%s' "ai_judge_runtime_sla_thresholds.env" ;;
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
    runtime_sla_freeze)
      printf '%s' "RUNTIME_SLA_FREEZE_STATUS;THRESHOLD_DECISION;OBS_P95_MS;OBS_P99_MS;COMPLIANCE_P95_MS;COMPLIANCE_P99_MS;COMPLIANCE_FAULT_DRILL;COMPLIANCE_TRACE_HASH_COVERAGE;COMPLIANCE_COMMITMENT_COVERAGE;COMPLIANCE_ATTESTATION_GAP"
      ;;
    *)
      printf '%s' "CALIBRATION_STATUS"
      ;;
  esac
}

track_real_required_keys() {
  case "$1" in
    runtime_sla_freeze)
      printf '%s' "RUNTIME_SLA_EVIDENCE;FREEZE_UPDATED_AT;FREEZE_DATASET_REF"
      ;;
    *)
      printf '%s' "REAL_ENV_EVIDENCE;CALIBRATED_AT;CALIBRATED_BY;DATASET_REF"
      ;;
  esac
}

track_local_required_keys() {
  case "$1" in
    runtime_sla_freeze)
      printf '%s' "RUNTIME_SLA_EVIDENCE;FREEZE_UPDATED_AT;FREEZE_DATASET_REF;FREEZE_ENV_MODE"
      ;;
    *)
      printf '%s' "LOCAL_ENV_EVIDENCE;LOCAL_ENV_PROFILE;CALIBRATED_AT;CALIBRATED_BY"
      ;;
  esac
}

track_calibration_key() {
  case "$1" in
    runtime_sla_freeze) printf '%s' "RUNTIME_SLA_FREEZE_STATUS" ;;
    *) printf '%s' "CALIBRATION_STATUS" ;;
  esac
}

track_ready_value() {
  case "$1" in
    runtime_sla_freeze) printf '%s' "pass" ;;
    *) printf '%s' "validated" ;;
  esac
}

track_local_ready_value() {
  case "$1" in
    runtime_sla_freeze) printf '%s' "local_reference_frozen" ;;
    *) printf '%s' "validated" ;;
  esac
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

resolve_environment_mode() {
  if [[ ! -f "$ENV_MARKER_FILE" ]]; then
    ENV_MODE="blocked"
    return
  fi

  local real_ready
  real_ready="$(trim "$(read_env_value "$ENV_MARKER_FILE" "REAL_CALIBRATION_ENV_READY")")"
  if is_truthy "$real_ready"; then
    ENV_MODE="real"
    return
  fi

  local local_ready local_mode_marker
  local_ready="$(trim "$(read_env_value "$ENV_MARKER_FILE" "LOCAL_REFERENCE_ENV_READY")")"
  local_mode_marker="$(trim "$(read_env_value "$ENV_MARKER_FILE" "CALIBRATION_ENV_MODE")")"
  if [[ "$local_mode_marker" == "local_reference" || "$local_mode_marker" == "local" ]]; then
    local_ready="true"
  fi

  if [[ "$ALLOW_LOCAL_REFERENCE" == "true" ]] && is_truthy "$local_ready"; then
    ENV_MODE="local_reference"
  else
    ENV_MODE="blocked"
  fi
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
        ENV_MARKER_FILE="${2:-}"
        shift 2
        ;;
      --allow-local-reference)
        ALLOW_LOCAL_REFERENCE="true"
        shift 1
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

write_json_summary() {
  local total="$1"
  local ready_total="$2"
  local blocked_total="$3"
  local pending_total="$4"
  local missing_total="$5"
  local details_file="$6"

  {
    printf '{\n'
    printf '  "run_id": "%s",\n' "$(json_escape "$RUN_ID")"
    printf '  "status": "%s",\n' "$(json_escape "$STATUS")"
    printf '  "root": "%s",\n' "$(json_escape "$ROOT")"
    printf '  "evidence_dir": "%s",\n' "$(json_escape "$EVIDENCE_DIR")"
    printf '  "env_marker_file": "%s",\n' "$(json_escape "$ENV_MARKER_FILE")"
    printf '  "environment_mode": "%s",\n' "$(json_escape "$ENV_MODE")"
    printf '  "local_reference_enabled": "%s",\n' "$(json_escape "$ALLOW_LOCAL_REFERENCE")"
    printf '  "started_at": "%s",\n' "$(json_escape "$STARTED_AT")"
    printf '  "finished_at": "%s",\n' "$(json_escape "$FINISHED_AT")"
    printf '  "counts": {\n'
    printf '    "total": %s,\n' "$total"
    printf '    "ready_total": %s,\n' "$ready_total"
    printf '    "blocked_total": %s,\n' "$blocked_total"
    printf '    "pending_total": %s,\n' "$pending_total"
    printf '    "evidence_missing_total": %s\n' "$missing_total"
    printf '  },\n'
    printf '  "tracks": [\n'
    local first=1
    while IFS=$'\t' read -r track_id title track_status file calibration_status missing_base missing_real missing_local note; do
      [[ -z "$track_id" ]] && continue
      if [[ $first -eq 0 ]]; then
        printf ',\n'
      fi
      first=0
      printf '    {"track_id":"%s","title":"%s","status":"%s","evidence_file":"%s","calibration_status":"%s","missing_base_keys":"%s","missing_real_keys":"%s","missing_local_keys":"%s","note":"%s"}' \
        "$(json_escape "$track_id")" \
        "$(json_escape "$title")" \
        "$(json_escape "$track_status")" \
        "$(json_escape "$file")" \
        "$(json_escape "$calibration_status")" \
        "$(json_escape "$missing_base")" \
        "$(json_escape "$missing_real")" \
        "$(json_escape "$missing_local")" \
        "$(json_escape "$note")"
    done <"$details_file"
    printf '\n  ],\n'
    printf '  "outputs": {\n'
    printf '    "output_doc": "%s",\n' "$(json_escape "$OUTPUT_DOC")"
    printf '    "output_env": "%s",\n' "$(json_escape "$OUTPUT_ENV")"
    printf '    "json": "%s",\n' "$(json_escape "$EMIT_JSON")"
    printf '    "markdown": "%s"\n' "$(json_escape "$EMIT_MD")"
    printf '  }\n'
    printf '}\n'
  } >"$EMIT_JSON"
}

write_md_summary() {
  local total="$1"
  local ready_total="$2"
  local blocked_total="$3"
  local pending_total="$4"
  local missing_total="$5"
  local details_file="$6"

  {
    printf '# AI Judge Real Env Evidence Closure\n\n'
    printf -- '- run_id: `%s`\n' "$RUN_ID"
    printf -- '- status: `%s`\n' "$STATUS"
    printf -- '- env_marker_file: `%s`\n' "$ENV_MARKER_FILE"
    printf -- '- evidence_dir: `%s`\n' "$EVIDENCE_DIR"
    printf -- '- environment_mode: `%s`\n' "$ENV_MODE"
    printf -- '- local_reference_enabled: `%s`\n' "$ALLOW_LOCAL_REFERENCE"
    printf -- '- started_at: `%s`\n' "$STARTED_AT"
    printf -- '- finished_at: `%s`\n' "$FINISHED_AT"
    printf '\n## Counts\n\n'
    printf '1. total: %s\n' "$total"
    printf '2. ready_total: %s\n' "$ready_total"
    printf '3. blocked_total: %s\n' "$blocked_total"
    printf '4. pending_total: %s\n' "$pending_total"
    printf '5. evidence_missing_total: %s\n' "$missing_total"
    printf '\n## Tracks\n\n'
    printf '| Track | Status | Missing Base Keys | Missing Real Keys | Missing Local Keys | Note |\n'
    printf '| --- | --- | --- | --- | --- | --- |\n'
    while IFS=$'\t' read -r _track_id title track_status _file _calibration_status missing_base missing_real missing_local note; do
      [[ -z "$title" ]] && continue
      printf '| %s | %s | %s | %s | %s | %s |\n' "$title" "$track_status" "$missing_base" "$missing_real" "$missing_local" "$note"
    done <"$details_file"
  } >"$EMIT_MD"
}

write_output_doc() {
  local marker_ready="$1"
  local details_file="$2"
  local closure_rule
  local local_rule

  if [[ "$ENV_MODE" == "real" ]]; then
    closure_rule='收口原则：`REAL_CALIBRATION_ENV_READY=true` 且六轨道 real 键齐备，判定 `pass`。'
  elif [[ "$ENV_MODE" == "local_reference" ]]; then
    closure_rule='收口原则：本机参考模式启用，六轨道满足 local 预检后判定 `local_reference_ready`（不替代 real pass）。'
  else
    closure_rule='收口原则：默认只接受 real 环境；若未启用本机参考，结果保持 `env_blocked`。'
  fi
  if [[ "$ALLOW_LOCAL_REFERENCE" == "true" ]]; then
    local_rule='本机参考开关：已启用（`--allow-local-reference`）。'
  else
    local_rule='本机参考开关：未启用（可使用 `--allow-local-reference` 进行本机预检）。'
  fi

  {
    printf '# AI Judge P5 Real Env 证据收口清单\n\n'
    printf '更新时间：%s\n' "$(date_cn)"
    printf '状态：%s\n\n' "$STATUS"
    printf '## 1. 当前判定\n\n'
    printf '1. marker_ready: `%s`\n' "$marker_ready"
    printf '2. env_marker: `%s`\n' "$ENV_MARKER_FILE"
    printf '3. evidence_dir: `%s`\n' "$EVIDENCE_DIR"
    printf '4. environment_mode: `%s`\n' "$ENV_MODE"
    printf '5. %s\n' "$local_rule"
    printf '6. %s\n' "$closure_rule"
    printf '\n## 2. 轨道缺口明细\n\n'
    printf '| 轨道 | 状态 | 校准状态 | 缺失基础键 | 缺失 real 键 | 缺失 local 键 | 说明 |\n'
    printf '| --- | --- | --- | --- | --- | --- | --- |\n'
    while IFS=$'\t' read -r _track_id title track_status _file calibration_status missing_base missing_real missing_local note; do
      [[ -z "$title" ]] && continue
      printf '| %s | %s | %s | %s | %s | %s | %s |\n' \
        "$title" \
        "$track_status" \
        "$calibration_status" \
        "$missing_base" \
        "$missing_real" \
        "$missing_local" \
        "$note"
    done <"$details_file"
    printf '\n## 3. 执行建议\n\n'
    printf '1. 真实环境收口：先设置 marker `REAL_CALIBRATION_ENV_READY=true`。\n'
    printf '2. P5 轨道补齐 real 键：`REAL_ENV_EVIDENCE`、`CALIBRATED_AT`、`CALIBRATED_BY`、`DATASET_REF`。\n'
    printf '3. Runtime SLA 补齐 real 键：`RUNTIME_SLA_EVIDENCE`、`FREEZE_UPDATED_AT`、`FREEZE_DATASET_REF`，且 `RUNTIME_SLA_FREEZE_STATUS=pass`。\n'
    printf '4. 若仅做本机预检：启用 `--allow-local-reference`，并补齐 local 键（`LOCAL_ENV_EVIDENCE`、`LOCAL_ENV_PROFILE` 等），Runtime SLA 需 `RUNTIME_SLA_FREEZE_STATUS=local_reference_frozen`。\n'
    printf '5. 复跑：`bash scripts/harness/ai_judge_runtime_sla_freeze.sh`（real）或 `bash scripts/harness/ai_judge_runtime_sla_freeze.sh --allow-local-reference`（local）。\n'
    printf '6. 复跑：`bash scripts/harness/ai_judge_p5_real_calibration_on_env.sh`（real）或 `bash scripts/harness/ai_judge_p5_real_calibration_on_env.sh --allow-local-reference`（local）。\n'
  } >"$OUTPUT_DOC"
}

write_output_env() {
  local marker_ready="$1"
  local total="$2"
  local ready_total="$3"
  local blocked_total="$4"
  local pending_total="$5"
  local missing_total="$6"

  cat >"$OUTPUT_ENV" <<EOF_ENV
AI_JUDGE_REAL_ENV_CLOSURE_STATUS=$STATUS
UPDATED_AT=$FINISHED_AT
REAL_ENV_MARKER_READY=$marker_ready
ENVIRONMENT_MODE=$ENV_MODE
LOCAL_REFERENCE_ENABLED=$ALLOW_LOCAL_REFERENCE
TOTAL_TRACKS=$total
READY_TRACKS=$ready_total
BLOCKED_TRACKS=$blocked_total
PENDING_TRACKS=$pending_total
EVIDENCE_MISSING_TRACKS=$missing_total
EOF_ENV
}

main() {
  parse_args "$@"
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
  if [[ -z "$OUTPUT_DOC" ]]; then
    OUTPUT_DOC="$EVIDENCE_DIR/ai_judge_p5_real_env_closure_checklist.md"
  else
    OUTPUT_DOC="$(abs_path "$OUTPUT_DOC")"
  fi
  if [[ -z "$OUTPUT_ENV" ]]; then
    OUTPUT_ENV="$EVIDENCE_DIR/ai_judge_p5_real_env_closure.env"
  else
    OUTPUT_ENV="$(abs_path "$OUTPUT_ENV")"
  fi

  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ai-judge-real-env-evidence-closure"
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

  ensure_parent_dir "$OUTPUT_DOC"
  ensure_parent_dir "$OUTPUT_ENV"
  ensure_parent_dir "$EMIT_JSON"
  ensure_parent_dir "$EMIT_MD"

  local marker_ready="false"
  if [[ -f "$ENV_MARKER_FILE" ]]; then
    marker_ready="$(trim "$(read_env_value "$ENV_MARKER_FILE" "REAL_CALIBRATION_ENV_READY")")"
  fi
  if is_truthy "$marker_ready"; then
    marker_ready="true"
  else
    marker_ready="false"
  fi
  resolve_environment_mode

  local details_file
  details_file="$(mktemp)"

  local total=0 ready_total=0 blocked_total=0 pending_total=0 missing_total=0

  local track_id title file required_base required_real required_local missing_base missing_real missing_local calibration_status track_status note calibration_key ready_value local_ready_value
  for track_id in "${TRACK_IDS[@]}"; do
    total=$((total + 1))
    title="$(track_title "$track_id")"
    file="$EVIDENCE_DIR/$(track_file_name "$track_id")"
    required_base="$(track_required_keys "$track_id")"
    required_real="$(track_real_required_keys "$track_id")"
    required_local="$(track_local_required_keys "$track_id")"
    calibration_key="$(track_calibration_key "$track_id")"
    ready_value="$(track_ready_value "$track_id")"
    local_ready_value="$(track_local_ready_value "$track_id")"

    if [[ ! -f "$file" ]]; then
      track_status="evidence_missing"
      calibration_status="missing"
      missing_base="(file_missing)"
      missing_real="(file_missing)"
      missing_local="(file_missing)"
      note="evidence file missing"
      missing_total=$((missing_total + 1))
    elif [[ "$ENV_MODE" == "blocked" ]]; then
      track_status="env_blocked"
      calibration_status="$(trim "$(read_env_value "$file" "$calibration_key")")"
      missing_base="$(collect_missing_keys "$file" "$required_base")"
      missing_real="$(collect_missing_keys "$file" "$required_real")"
      missing_local="$(collect_missing_keys "$file" "$required_local")"
      note="environment blocked (real marker not ready)"
      blocked_total=$((blocked_total + 1))
    else
      calibration_status="$(trim "$(read_env_value "$file" "$calibration_key")")"
      missing_base="$(collect_missing_keys "$file" "$required_base")"
      missing_real="$(collect_missing_keys "$file" "$required_real")"
      missing_local="$(collect_missing_keys "$file" "$required_local")"

      if [[ "$ENV_MODE" == "real" ]]; then
        if [[ "$calibration_status" != "$ready_value" ]]; then
          track_status="pending_real_evidence"
          note="${calibration_key} is ${calibration_status:-missing}"
          pending_total=$((pending_total + 1))
        elif [[ -n "$missing_base" || -n "$missing_real" ]]; then
          track_status="pending_real_evidence"
          note="missing required real keys"
          pending_total=$((pending_total + 1))
        else
          track_status="ready"
          note="real env evidence ready"
          ready_total=$((ready_total + 1))
        fi
      else
        if [[ "$calibration_status" != "$local_ready_value" ]]; then
          track_status="local_reference_pending"
          note="${calibration_key} is ${calibration_status:-missing}"
          pending_total=$((pending_total + 1))
        elif [[ -n "$missing_base" || -n "$missing_local" ]]; then
          track_status="local_reference_pending"
          note="missing required local keys"
          pending_total=$((pending_total + 1))
        else
          track_status="local_reference_ready"
          note="local reference evidence ready (not real pass)"
          ready_total=$((ready_total + 1))
        fi
      fi
    fi

    [[ -z "$missing_base" ]] && missing_base="（无）"
    [[ -z "$missing_real" ]] && missing_real="（无）"
    [[ -z "$missing_local" ]] && missing_local="（无）"
    [[ -z "$calibration_status" ]] && calibration_status="missing"
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$track_id" \
      "$title" \
      "$track_status" \
      "$file" \
      "$calibration_status" \
      "$missing_base" \
      "$missing_real" \
      "$missing_local" \
      "$note" >>"$details_file"
  done

  if [[ "$missing_total" -gt 0 ]]; then
    STATUS="evidence_missing"
  elif [[ "$ENV_MODE" == "blocked" ]]; then
    STATUS="env_blocked"
  elif [[ "$pending_total" -gt 0 ]]; then
    if [[ "$ENV_MODE" == "real" ]]; then
      STATUS="pending_real_evidence"
    else
      STATUS="local_reference_pending"
    fi
  else
    if [[ "$ENV_MODE" == "real" ]]; then
      STATUS="pass"
    else
      STATUS="local_reference_ready"
    fi
  fi

  FINISHED_AT="$(iso_now)"
  write_output_doc "$marker_ready" "$details_file"
  write_output_env "$marker_ready" "$total" "$ready_total" "$blocked_total" "$pending_total" "$missing_total"
  write_json_summary "$total" "$ready_total" "$blocked_total" "$pending_total" "$missing_total" "$details_file"
  write_md_summary "$total" "$ready_total" "$blocked_total" "$pending_total" "$missing_total" "$details_file"

  rm -f "$details_file"

  echo "ai_judge_real_env_evidence_closure_status: $STATUS"
  echo "real_env_marker_ready: $marker_ready"
  echo "environment_mode: $ENV_MODE"
  echo "local_reference_enabled: $ALLOW_LOCAL_REFERENCE"
  echo "output_doc: $OUTPUT_DOC"
  echo "output_env: $OUTPUT_ENV"
  echo "summary_json: $EMIT_JSON"
  echo "summary_md: $EMIT_MD"
}

main "$@"
