#!/usr/bin/env bash
set -euo pipefail

ROOT=""
LATENCY_ENV=""
FAULT_ENV=""
TRUST_ENV=""
ENV_MARKER=""
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

MAX_P95_MS="1200"
MAX_P99_MS="2200"
MIN_TRACE_HASH_COVERAGE="0.99"
MIN_COMMITMENT_COVERAGE="0.98"
MAX_ATTESTATION_GAP="0.01"

usage() {
  cat <<'USAGE'
用法:
  ai_judge_runtime_sla_freeze.sh \
    [--root <repo-root>] \
    [--latency-env <path>] \
    [--fault-env <path>] \
    [--trust-env <path>] \
    [--env-marker <path>] \
    [--output-doc <path>] \
    [--output-env <path>] \
    [--allow-local-reference] \
    [--max-p95-ms <int>] \
    [--max-p99-ms <int>] \
    [--min-trace-hash-coverage <float>] \
    [--min-commitment-coverage <float>] \
    [--max-attestation-gap <float>] \
    [--emit-json <path>] \
    [--emit-md <path>]

说明:
  - 冻结 AI Judge runtime SLA 阈值（时延 + 稳定性 + 可验证信任）。
  - 默认优先真实环境；开启 --allow-local-reference 时允许本机参考冻结。
  - 输出状态：pass/local_reference_frozen/pending_data/threshold_violation/env_blocked/evidence_missing。
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

is_number() {
  local value="$1"
  awk -v v="$value" 'BEGIN { if (v ~ /^-?[0-9]+([.][0-9]+)?$/) exit 0; exit 1 }'
}

float_gt() {
  local a="$1"
  local b="$2"
  awk -v left="$a" -v right="$b" 'BEGIN { exit !(left > right) }'
}

float_lt() {
  local a="$1"
  local b="$2"
  awk -v left="$a" -v right="$b" 'BEGIN { exit !(left < right) }'
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --root)
        ROOT="${2:-}"
        shift 2
        ;;
      --latency-env)
        LATENCY_ENV="${2:-}"
        shift 2
        ;;
      --fault-env)
        FAULT_ENV="${2:-}"
        shift 2
        ;;
      --trust-env)
        TRUST_ENV="${2:-}"
        shift 2
        ;;
      --env-marker)
        ENV_MARKER="${2:-}"
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
      --allow-local-reference)
        ALLOW_LOCAL_REFERENCE="true"
        shift 1
        ;;
      --max-p95-ms)
        MAX_P95_MS="${2:-}"
        shift 2
        ;;
      --max-p99-ms)
        MAX_P99_MS="${2:-}"
        shift 2
        ;;
      --min-trace-hash-coverage)
        MIN_TRACE_HASH_COVERAGE="${2:-}"
        shift 2
        ;;
      --min-commitment-coverage)
        MIN_COMMITMENT_COVERAGE="${2:-}"
        shift 2
        ;;
      --max-attestation-gap)
        MAX_ATTESTATION_GAP="${2:-}"
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

resolve_environment_mode() {
  if [[ ! -f "$ENV_MARKER" ]]; then
    ENV_MODE="blocked"
    return
  fi

  local real_ready local_ready local_mode_marker
  real_ready="$(trim "$(read_env_value "$ENV_MARKER" "REAL_CALIBRATION_ENV_READY")")"
  if is_truthy "$real_ready"; then
    ENV_MODE="real"
    return
  fi

  local_ready="$(trim "$(read_env_value "$ENV_MARKER" "LOCAL_REFERENCE_ENV_READY")")"
  local_mode_marker="$(trim "$(read_env_value "$ENV_MARKER" "CALIBRATION_ENV_MODE")")"
  if [[ "$local_mode_marker" == "local_reference" || "$local_mode_marker" == "local" ]]; then
    local_ready="true"
  fi

  if [[ "$ALLOW_LOCAL_REFERENCE" == "true" ]] && is_truthy "$local_ready"; then
    ENV_MODE="local_reference"
  else
    ENV_MODE="blocked"
  fi
}

write_threshold_env() {
  local threshold_decision="$1"
  local needs_real_reconfirm="$2"
  local needs_remediation="$3"
  local sample_size="$4"
  local p95_ms="$5"
  local p99_ms="$6"
  local callback_recovery_pass="$7"
  local replay_consistency_pass="$8"
  local audit_delivery_pass="$9"
  local trace_hash_coverage="${10}"
  local commitment_coverage="${11}"
  local attestation_gap="${12}"
  local data_source="${13}"
  local dataset_ref="${14}"
  local p95_ok="${15}"
  local p99_ok="${16}"
  local fault_ok="${17}"
  local trace_ok="${18}"
  local commitment_ok="${19}"
  local gap_ok="${20}"

  cat >"$OUTPUT_ENV" <<EOF_ENV
RUNTIME_SLA_FREEZE_STATUS=$STATUS
FREEZE_UPDATED_AT=$FINISHED_AT
FREEZE_ENV_MODE=$ENV_MODE
SLA_POLICY_VERSION=runtime-sla-v1
RUNTIME_SLA_EVIDENCE=$data_source
FREEZE_DATASET_REF=$dataset_ref
THRESHOLD_DECISION=$threshold_decision
NEEDS_REAL_ENV_RECONFIRM=$needs_real_reconfirm
NEEDS_REMEDIATION=$needs_remediation

P95_MS_MAX=$MAX_P95_MS
P99_MS_MAX=$MAX_P99_MS
TRACE_HASH_COVERAGE_MIN=$MIN_TRACE_HASH_COVERAGE
COMMITMENT_COVERAGE_MIN=$MIN_COMMITMENT_COVERAGE
ATTESTATION_GAP_MAX=$MAX_ATTESTATION_GAP

OBS_SAMPLE_SIZE=$sample_size
OBS_P95_MS=$p95_ms
OBS_P99_MS=$p99_ms
OBS_CALLBACK_FAILURE_RECOVERY_PASS=$callback_recovery_pass
OBS_REPLAY_CONSISTENCY_PASS=$replay_consistency_pass
OBS_AUDIT_ALERT_DELIVERY_PASS=$audit_delivery_pass
OBS_TRACE_HASH_COVERAGE=$trace_hash_coverage
OBS_COMMITMENT_COVERAGE=$commitment_coverage
OBS_ATTESTATION_GAP=$attestation_gap

COMPLIANCE_P95_MS=$p95_ok
COMPLIANCE_P99_MS=$p99_ok
COMPLIANCE_FAULT_DRILL=$fault_ok
COMPLIANCE_TRACE_HASH_COVERAGE=$trace_ok
COMPLIANCE_COMMITMENT_COVERAGE=$commitment_ok
COMPLIANCE_ATTESTATION_GAP=$gap_ok
EOF_ENV
}

write_freeze_doc() {
  local threshold_decision="$1"
  local needs_real_reconfirm="$2"
  local needs_remediation="$3"
  local sample_size="$4"
  local p95_ms="$5"
  local p99_ms="$6"
  local callback_recovery_pass="$7"
  local replay_consistency_pass="$8"
  local audit_delivery_pass="$9"
  local trace_hash_coverage="${10}"
  local commitment_coverage="${11}"
  local attestation_gap="${12}"
  local data_source="${13}"
  local dataset_ref="${14}"
  local missing_keys="${15}"
  local note="${16}"
  local p95_ok="${17}"
  local p99_ok="${18}"
  local fault_ok="${19}"
  local trace_ok="${20}"
  local commitment_ok="${21}"
  local gap_ok="${22}"

  cat >"$OUTPUT_DOC" <<EOF_DOC
# AI Judge Runtime SLA 冻结口径

更新时间：$(date_cn)
状态：$STATUS

## 1. 冻结结论

1. environment_mode: \`$ENV_MODE\`
2. threshold_decision: \`$threshold_decision\`
3. policy_version: \`runtime-sla-v1\`
4. needs_real_env_reconfirm: \`$needs_real_reconfirm\`
5. needs_remediation: \`$needs_remediation\`

## 2. 阈值与观测值

| 指标 | 冻结阈值 | 当前观测值 | 是否达标 |
| --- | --- | --- | --- |
| p95_ms | <= $MAX_P95_MS | $p95_ms | $p95_ok |
| p99_ms | <= $MAX_P99_MS | $p99_ms | $p99_ok |
| fault_drill (callback/replay/audit) | all true | $callback_recovery_pass/$replay_consistency_pass/$audit_delivery_pass | $fault_ok |
| trace_hash_coverage | >= $MIN_TRACE_HASH_COVERAGE | $trace_hash_coverage | $trace_ok |
| commitment_coverage | >= $MIN_COMMITMENT_COVERAGE | $commitment_coverage | $commitment_ok |
| attestation_gap | <= $MAX_ATTESTATION_GAP | $attestation_gap | $gap_ok |

## 3. 数据来源

1. latency_env: \`$LATENCY_ENV\`
2. fault_env: \`$FAULT_ENV\`
3. trust_env: \`$TRUST_ENV\`
4. env_marker: \`$ENV_MARKER\`
5. runtime_sla_evidence: \`$data_source\`
6. dataset_ref: \`$dataset_ref\`
7. sample_size: \`$sample_size\`

## 4. 风险与说明

1. missing_keys: \`${missing_keys:-（无）}\`
2. note: \`$note\`
3. 当前冻结仅用于工程口径治理；真实环境冻结结论仍以 \`status=pass\` 为准。
EOF_DOC
}

write_json_summary() {
  local threshold_decision="$1"
  local needs_real_reconfirm="$2"
  local needs_remediation="$3"
  local sample_size="$4"
  local p95_ms="$5"
  local p99_ms="$6"
  local callback_recovery_pass="$7"
  local replay_consistency_pass="$8"
  local audit_delivery_pass="$9"
  local trace_hash_coverage="${10}"
  local commitment_coverage="${11}"
  local attestation_gap="${12}"
  local missing_keys="${13}"
  local note="${14}"
  local p95_ok="${15}"
  local p99_ok="${16}"
  local fault_ok="${17}"
  local trace_ok="${18}"
  local commitment_ok="${19}"
  local gap_ok="${20}"

  {
    printf '{\n'
    printf '  "run_id": "%s",\n' "$(json_escape "$RUN_ID")"
    printf '  "status": "%s",\n' "$(json_escape "$STATUS")"
    printf '  "root": "%s",\n' "$(json_escape "$ROOT")"
    printf '  "latency_env": "%s",\n' "$(json_escape "$LATENCY_ENV")"
    printf '  "fault_env": "%s",\n' "$(json_escape "$FAULT_ENV")"
    printf '  "trust_env": "%s",\n' "$(json_escape "$TRUST_ENV")"
    printf '  "env_marker": "%s",\n' "$(json_escape "$ENV_MARKER")"
    printf '  "environment_mode": "%s",\n' "$(json_escape "$ENV_MODE")"
    printf '  "allow_local_reference": %s,\n' "$([[ "$ALLOW_LOCAL_REFERENCE" == "true" ]] && echo "true" || echo "false")"
    printf '  "policy_version": "runtime-sla-v1",\n'
    printf '  "threshold_decision": "%s",\n' "$(json_escape "$threshold_decision")"
    printf '  "needs_real_env_reconfirm": %s,\n' "$([[ "$needs_real_reconfirm" == "true" ]] && echo "true" || echo "false")"
    printf '  "needs_remediation": %s,\n' "$([[ "$needs_remediation" == "true" ]] && echo "true" || echo "false")"
    printf '  "metrics": {\n'
    printf '    "sample_size": "%s",\n' "$(json_escape "$sample_size")"
    printf '    "p95_ms": "%s",\n' "$(json_escape "$p95_ms")"
    printf '    "p99_ms": "%s",\n' "$(json_escape "$p99_ms")"
    printf '    "callback_failure_recovery_pass": %s,\n' "$([[ "$callback_recovery_pass" == "true" ]] && echo "true" || echo "false")"
    printf '    "replay_consistency_pass": %s,\n' "$([[ "$replay_consistency_pass" == "true" ]] && echo "true" || echo "false")"
    printf '    "audit_alert_delivery_pass": %s,\n' "$([[ "$audit_delivery_pass" == "true" ]] && echo "true" || echo "false")"
    printf '    "trace_hash_coverage": "%s",\n' "$(json_escape "$trace_hash_coverage")"
    printf '    "commitment_coverage": "%s",\n' "$(json_escape "$commitment_coverage")"
    printf '    "attestation_gap": "%s",\n' "$(json_escape "$attestation_gap")"
    printf '    "p95_ok": %s,\n' "$([[ "$p95_ok" == "true" ]] && echo "true" || echo "false")"
    printf '    "p99_ok": %s,\n' "$([[ "$p99_ok" == "true" ]] && echo "true" || echo "false")"
    printf '    "fault_ok": %s,\n' "$([[ "$fault_ok" == "true" ]] && echo "true" || echo "false")"
    printf '    "trace_ok": %s,\n' "$([[ "$trace_ok" == "true" ]] && echo "true" || echo "false")"
    printf '    "commitment_ok": %s,\n' "$([[ "$commitment_ok" == "true" ]] && echo "true" || echo "false")"
    printf '    "gap_ok": %s\n' "$([[ "$gap_ok" == "true" ]] && echo "true" || echo "false")"
    printf '  },\n'
    printf '  "thresholds": {\n'
    printf '    "p95_ms_max": "%s",\n' "$(json_escape "$MAX_P95_MS")"
    printf '    "p99_ms_max": "%s",\n' "$(json_escape "$MAX_P99_MS")"
    printf '    "trace_hash_coverage_min": "%s",\n' "$(json_escape "$MIN_TRACE_HASH_COVERAGE")"
    printf '    "commitment_coverage_min": "%s",\n' "$(json_escape "$MIN_COMMITMENT_COVERAGE")"
    printf '    "attestation_gap_max": "%s"\n' "$(json_escape "$MAX_ATTESTATION_GAP")"
    printf '  },\n'
    printf '  "missing_keys": "%s",\n' "$(json_escape "$missing_keys")"
    printf '  "note": "%s",\n' "$(json_escape "$note")"
    printf '  "started_at": "%s",\n' "$(json_escape "$STARTED_AT")"
    printf '  "finished_at": "%s",\n' "$(json_escape "$FINISHED_AT")"
    printf '  "outputs": {\n'
    printf '    "threshold_env": "%s",\n' "$(json_escape "$OUTPUT_ENV")"
    printf '    "freeze_doc": "%s",\n' "$(json_escape "$OUTPUT_DOC")"
    printf '    "json": "%s",\n' "$(json_escape "$EMIT_JSON")"
    printf '    "markdown": "%s"\n' "$(json_escape "$EMIT_MD")"
    printf '  }\n'
    printf '}\n'
  } >"$EMIT_JSON"
}

write_md_summary() {
  local threshold_decision="$1"
  local note="$2"

  {
    printf '# AI Judge Runtime SLA Freeze\n\n'
    printf -- '- run_id: `%s`\n' "$RUN_ID"
    printf -- '- status: `%s`\n' "$STATUS"
    printf -- '- environment_mode: `%s`\n' "$ENV_MODE"
    printf -- '- threshold_decision: `%s`\n' "$threshold_decision"
    printf -- '- latency_env: `%s`\n' "$LATENCY_ENV"
    printf -- '- output_env: `%s`\n' "$OUTPUT_ENV"
    printf -- '- output_doc: `%s`\n' "$OUTPUT_DOC"
    printf -- '- started_at: `%s`\n' "$STARTED_AT"
    printf -- '- finished_at: `%s`\n' "$FINISHED_AT"
    printf '\n## Note\n\n'
    printf '1. %s\n' "$note"
  } >"$EMIT_MD"
}

main() {
  parse_args "$@"
  resolve_root

  if [[ -z "$LATENCY_ENV" ]]; then
    LATENCY_ENV="$ROOT/docs/loadtest/evidence/ai_judge_p5_latency_baseline.env"
  else
    LATENCY_ENV="$(abs_path "$LATENCY_ENV")"
  fi
  if [[ -z "$FAULT_ENV" ]]; then
    FAULT_ENV="$ROOT/docs/loadtest/evidence/ai_judge_p5_fault_drill.env"
  else
    FAULT_ENV="$(abs_path "$FAULT_ENV")"
  fi
  if [[ -z "$TRUST_ENV" ]]; then
    TRUST_ENV="$ROOT/docs/loadtest/evidence/ai_judge_p5_trust_attestation.env"
  else
    TRUST_ENV="$(abs_path "$TRUST_ENV")"
  fi
  if [[ -z "$ENV_MARKER" ]]; then
    ENV_MARKER="$ROOT/docs/loadtest/evidence/ai_judge_p5_real_env.env"
  else
    ENV_MARKER="$(abs_path "$ENV_MARKER")"
  fi
  if [[ -z "$OUTPUT_ENV" ]]; then
    OUTPUT_ENV="$ROOT/docs/loadtest/evidence/ai_judge_runtime_sla_thresholds.env"
  else
    OUTPUT_ENV="$(abs_path "$OUTPUT_ENV")"
  fi
  if [[ -z "$OUTPUT_DOC" ]]; then
    OUTPUT_DOC="$ROOT/docs/dev_plan/AI_Judge_Runtime_SLA_冻结口径-$(date_cn).md"
  else
    OUTPUT_DOC="$(abs_path "$OUTPUT_DOC")"
  fi

  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ai-judge-runtime-sla-freeze"
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

  ensure_parent_dir "$OUTPUT_ENV"
  ensure_parent_dir "$OUTPUT_DOC"
  ensure_parent_dir "$EMIT_JSON"
  ensure_parent_dir "$EMIT_MD"

  resolve_environment_mode

  local required_latency required_fault required_trust required_real required_local
  required_latency="CALIBRATION_STATUS;WINDOW_FROM;WINDOW_TO;SAMPLE_SIZE;P95_MS;P99_MS"
  required_fault="CALIBRATION_STATUS;DRILL_RUN_AT;CALLBACK_FAILURE_RECOVERY_PASS;REPLAY_CONSISTENCY_PASS;AUDIT_ALERT_DELIVERY_PASS"
  required_trust="CALIBRATION_STATUS;TRACE_HASH_COVERAGE;COMMITMENT_COVERAGE;ATTESTATION_GAP"
  required_real="REAL_ENV_EVIDENCE;CALIBRATED_AT;CALIBRATED_BY;DATASET_REF"
  required_local="LOCAL_ENV_EVIDENCE;LOCAL_ENV_PROFILE;CALIBRATED_AT;CALIBRATED_BY"

  local threshold_decision="pending"
  local needs_real_reconfirm="false"
  local needs_remediation="false"
  local sample_size=""
  local p95_ms=""
  local p99_ms=""
  local callback_recovery_pass="false"
  local replay_consistency_pass="false"
  local audit_delivery_pass="false"
  local trace_hash_coverage=""
  local commitment_coverage=""
  local attestation_gap=""
  local note=""
  local missing_keys=""
  local data_source=""
  local dataset_ref=""

  local p95_ok="false"
  local p99_ok="false"
  local fault_ok="false"
  local trace_ok="false"
  local commitment_ok="false"
  local gap_ok="false"

  if [[ ! -f "$LATENCY_ENV" || ! -f "$FAULT_ENV" || ! -f "$TRUST_ENV" ]]; then
    STATUS="evidence_missing"
    note="required evidence files are missing"
  elif [[ "$ENV_MODE" == "blocked" ]]; then
    STATUS="env_blocked"
    note="environment not ready for runtime sla freeze"
  else
    local missing_latency missing_fault missing_trust missing_mode
    missing_latency="$(collect_missing_keys "$LATENCY_ENV" "$required_latency")"
    missing_fault="$(collect_missing_keys "$FAULT_ENV" "$required_fault")"
    missing_trust="$(collect_missing_keys "$TRUST_ENV" "$required_trust")"
    if [[ "$ENV_MODE" == "real" ]]; then
      missing_mode="${missing_mode:+${missing_mode};}$(collect_missing_keys "$LATENCY_ENV" "$required_real")"
      missing_mode="${missing_mode:+${missing_mode};}$(collect_missing_keys "$FAULT_ENV" "$required_real")"
      missing_mode="${missing_mode:+${missing_mode};}$(collect_missing_keys "$TRUST_ENV" "$required_real")"
    else
      missing_mode="${missing_mode:+${missing_mode};}$(collect_missing_keys "$LATENCY_ENV" "$required_local")"
      missing_mode="${missing_mode:+${missing_mode};}$(collect_missing_keys "$FAULT_ENV" "$required_local")"
      missing_mode="${missing_mode:+${missing_mode};}$(collect_missing_keys "$TRUST_ENV" "$required_local")"
    fi

    missing_keys="${missing_latency}${missing_latency:+;}${missing_fault}${missing_fault:+;}${missing_trust}${missing_trust:+;}${missing_mode}"
    # 清理可能出现的首尾分号
    missing_keys="$(printf '%s' "$missing_keys" | sed 's/^;//; s/;$//; s/;;*/;/g')"

    local latency_status fault_status trust_status
    latency_status="$(trim "$(read_env_value "$LATENCY_ENV" "CALIBRATION_STATUS")")"
    fault_status="$(trim "$(read_env_value "$FAULT_ENV" "CALIBRATION_STATUS")")"
    trust_status="$(trim "$(read_env_value "$TRUST_ENV" "CALIBRATION_STATUS")")"

    sample_size="$(trim "$(read_env_value "$LATENCY_ENV" "SAMPLE_SIZE")")"
    p95_ms="$(trim "$(read_env_value "$LATENCY_ENV" "P95_MS")")"
    p99_ms="$(trim "$(read_env_value "$LATENCY_ENV" "P99_MS")")"
    callback_recovery_pass="$(trim "$(read_env_value "$FAULT_ENV" "CALLBACK_FAILURE_RECOVERY_PASS")" | tr '[:upper:]' '[:lower:]')"
    replay_consistency_pass="$(trim "$(read_env_value "$FAULT_ENV" "REPLAY_CONSISTENCY_PASS")" | tr '[:upper:]' '[:lower:]')"
    audit_delivery_pass="$(trim "$(read_env_value "$FAULT_ENV" "AUDIT_ALERT_DELIVERY_PASS")" | tr '[:upper:]' '[:lower:]')"
    trace_hash_coverage="$(trim "$(read_env_value "$TRUST_ENV" "TRACE_HASH_COVERAGE")")"
    commitment_coverage="$(trim "$(read_env_value "$TRUST_ENV" "COMMITMENT_COVERAGE")")"
    attestation_gap="$(trim "$(read_env_value "$TRUST_ENV" "ATTESTATION_GAP")")"

    data_source="$(trim "$(read_env_value "$LATENCY_ENV" "REAL_ENV_EVIDENCE")")"
    if [[ "$ENV_MODE" == "local_reference" || -z "$data_source" ]]; then
      data_source="$(trim "$(read_env_value "$LATENCY_ENV" "LOCAL_ENV_EVIDENCE")")"
    fi
    dataset_ref="$(trim "$(read_env_value "$LATENCY_ENV" "DATASET_REF")")"
    if [[ "$ENV_MODE" == "local_reference" && -z "$dataset_ref" ]]; then
      dataset_ref="local_reference_dataset"
    fi

    if [[ "$latency_status" != "validated" || "$fault_status" != "validated" || "$trust_status" != "validated" ]]; then
      STATUS="pending_data"
      note="calibration_status must be validated for latency/fault/trust tracks"
    elif [[ -n "$missing_keys" ]]; then
      STATUS="pending_data"
      note="missing required keys: $missing_keys"
    elif ! is_number "$p95_ms" || ! is_number "$p99_ms" || ! is_number "$trace_hash_coverage" || ! is_number "$commitment_coverage" || ! is_number "$attestation_gap"; then
      STATUS="pending_data"
      note="numeric fields are invalid in evidence files"
    elif [[ -z "$sample_size" ]]; then
      STATUS="pending_data"
      note="sample_size is missing"
    else
      p95_ok="true"
      p99_ok="true"
      trace_ok="true"
      commitment_ok="true"
      gap_ok="true"
      fault_ok="true"

      if float_gt "$p95_ms" "$MAX_P95_MS"; then
        p95_ok="false"
      fi
      if float_gt "$p99_ms" "$MAX_P99_MS"; then
        p99_ok="false"
      fi
      if float_lt "$trace_hash_coverage" "$MIN_TRACE_HASH_COVERAGE"; then
        trace_ok="false"
      fi
      if float_lt "$commitment_coverage" "$MIN_COMMITMENT_COVERAGE"; then
        commitment_ok="false"
      fi
      if float_gt "$attestation_gap" "$MAX_ATTESTATION_GAP"; then
        gap_ok="false"
      fi
      if ! is_truthy "$callback_recovery_pass" || ! is_truthy "$replay_consistency_pass" || ! is_truthy "$audit_delivery_pass"; then
        fault_ok="false"
      fi

      if [[ "$p95_ok" == "false" || "$p99_ok" == "false" || "$fault_ok" == "false" || "$trace_ok" == "false" || "$commitment_ok" == "false" || "$gap_ok" == "false" ]]; then
        STATUS="threshold_violation"
        threshold_decision="violated"
        needs_remediation="true"
        note="observed metrics exceed frozen runtime sla thresholds"
      elif [[ "$ENV_MODE" == "real" ]]; then
        STATUS="pass"
        threshold_decision="accepted"
        note="real environment runtime sla frozen successfully"
      else
        STATUS="local_reference_frozen"
        threshold_decision="accepted"
        needs_real_reconfirm="true"
        note="local reference runtime sla frozen; waiting real environment reconfirmation"
      fi
    fi
  fi

  FINISHED_AT="$(iso_now)"
  write_threshold_env \
    "$threshold_decision" \
    "$needs_real_reconfirm" \
    "$needs_remediation" \
    "$sample_size" \
    "$p95_ms" \
    "$p99_ms" \
    "$callback_recovery_pass" \
    "$replay_consistency_pass" \
    "$audit_delivery_pass" \
    "$trace_hash_coverage" \
    "$commitment_coverage" \
    "$attestation_gap" \
    "$data_source" \
    "$dataset_ref" \
    "$p95_ok" \
    "$p99_ok" \
    "$fault_ok" \
    "$trace_ok" \
    "$commitment_ok" \
    "$gap_ok"
  write_freeze_doc \
    "$threshold_decision" \
    "$needs_real_reconfirm" \
    "$needs_remediation" \
    "$sample_size" \
    "$p95_ms" \
    "$p99_ms" \
    "$callback_recovery_pass" \
    "$replay_consistency_pass" \
    "$audit_delivery_pass" \
    "$trace_hash_coverage" \
    "$commitment_coverage" \
    "$attestation_gap" \
    "$data_source" \
    "$dataset_ref" \
    "$missing_keys" \
    "$note" \
    "$p95_ok" \
    "$p99_ok" \
    "$fault_ok" \
    "$trace_ok" \
    "$commitment_ok" \
    "$gap_ok"
  write_json_summary \
    "$threshold_decision" \
    "$needs_real_reconfirm" \
    "$needs_remediation" \
    "$sample_size" \
    "$p95_ms" \
    "$p99_ms" \
    "$callback_recovery_pass" \
    "$replay_consistency_pass" \
    "$audit_delivery_pass" \
    "$trace_hash_coverage" \
    "$commitment_coverage" \
    "$attestation_gap" \
    "$missing_keys" \
    "$note" \
    "$p95_ok" \
    "$p99_ok" \
    "$fault_ok" \
    "$trace_ok" \
    "$commitment_ok" \
    "$gap_ok"
  write_md_summary "$threshold_decision" "$note"

  echo "ai_judge_runtime_sla_freeze_status: $STATUS"
  echo "environment_mode: $ENV_MODE"
  echo "allow_local_reference: $ALLOW_LOCAL_REFERENCE"
  echo "output_env: $OUTPUT_ENV"
  echo "output_doc: $OUTPUT_DOC"
  echo "summary_json: $EMIT_JSON"
  echo "summary_md: $EMIT_MD"
}

main "$@"
