#!/usr/bin/env bash
set -euo pipefail

ROOT=""
BENCHMARK_ENV=""
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

MAX_DRAW_RATE="0.30"
MAX_SIDE_BIAS_DELTA="0.08"
MAX_APPEAL_OVERTURN_RATE="0.12"

usage() {
  cat <<'USAGE'
用法:
  ai_judge_fairness_benchmark_freeze.sh \
    [--root <repo-root>] \
    [--benchmark-env <path>] \
    [--env-marker <path>] \
    [--output-doc <path>] \
    [--output-env <path>] \
    [--allow-local-reference] \
    [--max-draw-rate <float>] \
    [--max-side-bias-delta <float>] \
    [--max-appeal-overturn-rate <float>] \
    [--emit-json <path>] \
    [--emit-md <path>]

说明:
  - 冻结 fairness benchmark 的阈值口径与当前观测值。
  - 默认优先真实环境；开启 --allow-local-reference 时允许本机参考冻结。
  - 输出状态可能为 pass/local_reference_frozen/pending_data/threshold_violation/env_blocked。
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

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --root)
        ROOT="${2:-}"
        shift 2
        ;;
      --benchmark-env)
        BENCHMARK_ENV="${2:-}"
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
      --max-draw-rate)
        MAX_DRAW_RATE="${2:-}"
        shift 2
        ;;
      --max-side-bias-delta)
        MAX_SIDE_BIAS_DELTA="${2:-}"
        shift 2
        ;;
      --max-appeal-overturn-rate)
        MAX_APPEAL_OVERTURN_RATE="${2:-}"
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
  local policy_version="$1"
  local threshold_decision="$2"
  local needs_real_reconfirm="$3"
  local needs_remediation="$4"
  local sample_size="$5"
  local draw_rate="$6"
  local side_bias_delta="$7"
  local appeal_overturn_rate="$8"
  local draw_ok="$9"
  local side_ok="${10}"
  local appeal_ok="${11}"
  local freeze_evidence_ref="${12}"
  local dataset_ref="${13}"

  cat >"$OUTPUT_ENV" <<EOF_ENV
FAIRNESS_BENCHMARK_FREEZE_STATUS=$STATUS
FREEZE_UPDATED_AT=$FINISHED_AT
FREEZE_ENV_MODE=$ENV_MODE
FREEZE_POLICY_VERSION=$policy_version
FAIRNESS_BENCHMARK_EVIDENCE=$freeze_evidence_ref
FREEZE_DATASET_REF=$dataset_ref
THRESHOLD_DECISION=$threshold_decision
NEEDS_REAL_ENV_RECONFIRM=$needs_real_reconfirm
NEEDS_REMEDIATION=$needs_remediation

DRAW_RATE_MAX=$MAX_DRAW_RATE
SIDE_BIAS_DELTA_MAX=$MAX_SIDE_BIAS_DELTA
APPEAL_OVERTURN_RATE_MAX=$MAX_APPEAL_OVERTURN_RATE

OBS_SAMPLE_SIZE=$sample_size
OBS_DRAW_RATE=$draw_rate
OBS_SIDE_BIAS_DELTA=$side_bias_delta
OBS_APPEAL_OVERTURN_RATE=$appeal_overturn_rate

COMPLIANCE_DRAW_RATE=$draw_ok
COMPLIANCE_SIDE_BIAS_DELTA=$side_ok
COMPLIANCE_APPEAL_OVERTURN_RATE=$appeal_ok
EOF_ENV
}

write_freeze_doc() {
  local today="$1"
  local policy_version="$2"
  local threshold_decision="$3"
  local needs_real_reconfirm="$4"
  local needs_remediation="$5"
  local sample_size="$6"
  local draw_rate="$7"
  local side_bias_delta="$8"
  local appeal_overturn_rate="$9"
  local draw_ok="${10}"
  local side_ok="${11}"
  local appeal_ok="${12}"
  local freeze_evidence_ref="${13}"
  local dataset_ref="${14}"
  local missing_keys="${15}"
  local note="${16}"

  cat >"$OUTPUT_DOC" <<EOF_DOC
# AI Judge Fairness Benchmark 冻结口径

更新时间：$today
状态：$STATUS

## 1. 冻结结论

1. environment_mode: \`$ENV_MODE\`
2. threshold_decision: \`$threshold_decision\`
3. policy_version: \`$policy_version\`
4. needs_real_env_reconfirm: \`$needs_real_reconfirm\`
5. needs_remediation: \`$needs_remediation\`

## 2. 阈值与观测值

| 指标 | 冻结阈值（max） | 当前观测值 | 是否达标 |
| --- | --- | --- | --- |
| draw_rate | $MAX_DRAW_RATE | $draw_rate | $draw_ok |
| side_bias_delta | $MAX_SIDE_BIAS_DELTA | $side_bias_delta | $side_ok |
| appeal_overturn_rate | $MAX_APPEAL_OVERTURN_RATE | $appeal_overturn_rate | $appeal_ok |

## 3. 数据来源

1. benchmark_env: \`$BENCHMARK_ENV\`
2. env_marker: \`$ENV_MARKER\`
3. fairness_benchmark_evidence: \`$freeze_evidence_ref\`
4. dataset_ref: \`$dataset_ref\`
5. sample_size: \`$sample_size\`

## 4. 风险与说明

1. missing_keys: \`${missing_keys:-（无）}\`
2. note: \`${note}\`
3. 当前冻结仅用于工程口径治理；真实环境冻结结论仍以 \`status=pass\` 为准。
EOF_DOC
}

write_json_summary() {
  local policy_version="$1"
  local threshold_decision="$2"
  local needs_real_reconfirm="$3"
  local needs_remediation="$4"
  local sample_size="$5"
  local draw_rate="$6"
  local side_bias_delta="$7"
  local appeal_overturn_rate="$8"
  local draw_ok="$9"
  local side_ok="${10}"
  local appeal_ok="${11}"
  local missing_keys="${12}"
  local note="${13}"

  {
    printf '{\n'
    printf '  "run_id": "%s",\n' "$(json_escape "$RUN_ID")"
    printf '  "status": "%s",\n' "$(json_escape "$STATUS")"
    printf '  "root": "%s",\n' "$(json_escape "$ROOT")"
    printf '  "benchmark_env": "%s",\n' "$(json_escape "$BENCHMARK_ENV")"
    printf '  "env_marker": "%s",\n' "$(json_escape "$ENV_MARKER")"
    printf '  "environment_mode": "%s",\n' "$(json_escape "$ENV_MODE")"
    printf '  "allow_local_reference": %s,\n' "$([[ "$ALLOW_LOCAL_REFERENCE" == "true" ]] && echo "true" || echo "false")"
    printf '  "policy_version": "%s",\n' "$(json_escape "$policy_version")"
    printf '  "threshold_decision": "%s",\n' "$(json_escape "$threshold_decision")"
    printf '  "needs_real_env_reconfirm": %s,\n' "$([[ "$needs_real_reconfirm" == "true" ]] && echo "true" || echo "false")"
    printf '  "needs_remediation": %s,\n' "$([[ "$needs_remediation" == "true" ]] && echo "true" || echo "false")"
    printf '  "metrics": {\n'
    printf '    "sample_size": "%s",\n' "$(json_escape "$sample_size")"
    printf '    "draw_rate": "%s",\n' "$(json_escape "$draw_rate")"
    printf '    "side_bias_delta": "%s",\n' "$(json_escape "$side_bias_delta")"
    printf '    "appeal_overturn_rate": "%s",\n' "$(json_escape "$appeal_overturn_rate")"
    printf '    "draw_rate_ok": %s,\n' "$([[ "$draw_ok" == "true" ]] && echo "true" || echo "false")"
    printf '    "side_bias_delta_ok": %s,\n' "$([[ "$side_ok" == "true" ]] && echo "true" || echo "false")"
    printf '    "appeal_overturn_rate_ok": %s\n' "$([[ "$appeal_ok" == "true" ]] && echo "true" || echo "false")"
    printf '  },\n'
    printf '  "thresholds": {\n'
    printf '    "draw_rate_max": "%s",\n' "$(json_escape "$MAX_DRAW_RATE")"
    printf '    "side_bias_delta_max": "%s",\n' "$(json_escape "$MAX_SIDE_BIAS_DELTA")"
    printf '    "appeal_overturn_rate_max": "%s"\n' "$(json_escape "$MAX_APPEAL_OVERTURN_RATE")"
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
    printf '# AI Judge Fairness Benchmark Freeze\n\n'
    printf -- '- run_id: `%s`\n' "$RUN_ID"
    printf -- '- status: `%s`\n' "$STATUS"
    printf -- '- environment_mode: `%s`\n' "$ENV_MODE"
    printf -- '- threshold_decision: `%s`\n' "$threshold_decision"
    printf -- '- benchmark_env: `%s`\n' "$BENCHMARK_ENV"
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

  if [[ -z "$BENCHMARK_ENV" ]]; then
    BENCHMARK_ENV="$ROOT/docs/loadtest/evidence/ai_judge_p5_fairness_benchmark.env"
  else
    BENCHMARK_ENV="$(abs_path "$BENCHMARK_ENV")"
  fi
  if [[ -z "$ENV_MARKER" ]]; then
    ENV_MARKER="$ROOT/docs/loadtest/evidence/ai_judge_p5_real_env.env"
  else
    ENV_MARKER="$(abs_path "$ENV_MARKER")"
  fi
  if [[ -z "$OUTPUT_ENV" ]]; then
    OUTPUT_ENV="$ROOT/docs/loadtest/evidence/ai_judge_fairness_benchmark_thresholds.env"
  else
    OUTPUT_ENV="$(abs_path "$OUTPUT_ENV")"
  fi
  if [[ -z "$OUTPUT_DOC" ]]; then
    OUTPUT_DOC="$ROOT/docs/dev_plan/AI_Judge_Fairness_Benchmark_冻结口径-$(date_cn).md"
  else
    OUTPUT_DOC="$(abs_path "$OUTPUT_DOC")"
  fi

  RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)-ai-judge-fairness-benchmark-freeze"
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

  local required_base required_real required_local
  required_base="CALIBRATION_STATUS;WINDOW_FROM;WINDOW_TO;SAMPLE_SIZE;DRAW_RATE;SIDE_BIAS_DELTA;APPEAL_OVERTURN_RATE"
  required_real="REAL_ENV_EVIDENCE;CALIBRATED_AT;CALIBRATED_BY;DATASET_REF"
  required_local="LOCAL_ENV_EVIDENCE;LOCAL_ENV_PROFILE;CALIBRATED_AT;CALIBRATED_BY"

  local threshold_decision="pending"
  local needs_real_reconfirm="false"
  local needs_remediation="false"
  local sample_size=""
  local draw_rate=""
  local side_bias_delta=""
  local appeal_overturn_rate=""
  local draw_ok="false"
  local side_ok="false"
  local appeal_ok="false"
  local freeze_evidence_ref=""
  local dataset_ref=""
  local note=""
  local missing_keys=""

  local policy_version="fairness-benchmark-v1"

  if [[ ! -f "$BENCHMARK_ENV" ]]; then
    STATUS="evidence_missing"
    note="fairness benchmark evidence file missing"
  elif [[ "$ENV_MODE" == "blocked" ]]; then
    STATUS="env_blocked"
    note="environment not ready for fairness benchmark freeze"
  else
    local calibration_status missing_base missing_mode
    calibration_status="$(trim "$(read_env_value "$BENCHMARK_ENV" "CALIBRATION_STATUS")")"
    missing_base="$(collect_missing_keys "$BENCHMARK_ENV" "$required_base")"
    if [[ "$ENV_MODE" == "real" ]]; then
      missing_mode="$(collect_missing_keys "$BENCHMARK_ENV" "$required_real")"
    else
      missing_mode="$(collect_missing_keys "$BENCHMARK_ENV" "$required_local")"
    fi
    missing_keys="${missing_base}${missing_base:+;}${missing_mode}"

    sample_size="$(trim "$(read_env_value "$BENCHMARK_ENV" "SAMPLE_SIZE")")"
    draw_rate="$(trim "$(read_env_value "$BENCHMARK_ENV" "DRAW_RATE")")"
    side_bias_delta="$(trim "$(read_env_value "$BENCHMARK_ENV" "SIDE_BIAS_DELTA")")"
    appeal_overturn_rate="$(trim "$(read_env_value "$BENCHMARK_ENV" "APPEAL_OVERTURN_RATE")")"
    freeze_evidence_ref="$(trim "$(read_env_value "$BENCHMARK_ENV" "REAL_ENV_EVIDENCE")")"
    if [[ "$ENV_MODE" == "local_reference" || -z "$freeze_evidence_ref" ]]; then
      freeze_evidence_ref="$(trim "$(read_env_value "$BENCHMARK_ENV" "LOCAL_ENV_EVIDENCE")")"
    fi
    dataset_ref="$(trim "$(read_env_value "$BENCHMARK_ENV" "DATASET_REF")")"
    if [[ "$ENV_MODE" == "local_reference" && -z "$dataset_ref" ]]; then
      dataset_ref="local_reference_dataset"
    fi

    if [[ "$calibration_status" != "validated" ]]; then
      STATUS="pending_data"
      note="calibration_status is ${calibration_status:-missing}"
    elif [[ -n "$missing_keys" ]]; then
      STATUS="pending_data"
      note="missing required keys: $missing_keys"
    elif ! is_number "$draw_rate" || ! is_number "$side_bias_delta" || ! is_number "$appeal_overturn_rate"; then
      STATUS="pending_data"
      note="fairness metrics must be numeric"
    else
      draw_ok="true"
      side_ok="true"
      appeal_ok="true"
      if float_gt "$draw_rate" "$MAX_DRAW_RATE"; then
        draw_ok="false"
      fi
      if float_gt "$side_bias_delta" "$MAX_SIDE_BIAS_DELTA"; then
        side_ok="false"
      fi
      if float_gt "$appeal_overturn_rate" "$MAX_APPEAL_OVERTURN_RATE"; then
        appeal_ok="false"
      fi
      if [[ "$draw_ok" == "false" || "$side_ok" == "false" || "$appeal_ok" == "false" ]]; then
        STATUS="threshold_violation"
        threshold_decision="violated"
        needs_remediation="true"
        note="observed metrics exceed frozen thresholds"
      elif [[ "$ENV_MODE" == "real" ]]; then
        STATUS="pass"
        threshold_decision="accepted"
        note="real environment fairness benchmark frozen successfully"
      else
        STATUS="local_reference_frozen"
        threshold_decision="accepted"
        needs_real_reconfirm="true"
        note="local reference fairness benchmark frozen; waiting real environment reconfirmation"
      fi
    fi
  fi

  FINISHED_AT="$(iso_now)"
  write_threshold_env \
    "$policy_version" \
    "$threshold_decision" \
    "$needs_real_reconfirm" \
    "$needs_remediation" \
    "$sample_size" \
    "$draw_rate" \
    "$side_bias_delta" \
    "$appeal_overturn_rate" \
    "$draw_ok" \
    "$side_ok" \
    "$appeal_ok" \
    "$freeze_evidence_ref" \
    "$dataset_ref"
  write_freeze_doc \
    "$(date_cn)" \
    "$policy_version" \
    "$threshold_decision" \
    "$needs_real_reconfirm" \
    "$needs_remediation" \
    "$sample_size" \
    "$draw_rate" \
    "$side_bias_delta" \
    "$appeal_overturn_rate" \
    "$draw_ok" \
    "$side_ok" \
    "$appeal_ok" \
    "$freeze_evidence_ref" \
    "$dataset_ref" \
    "$missing_keys" \
    "$note"
  write_json_summary \
    "$policy_version" \
    "$threshold_decision" \
    "$needs_real_reconfirm" \
    "$needs_remediation" \
    "$sample_size" \
    "$draw_rate" \
    "$side_bias_delta" \
    "$appeal_overturn_rate" \
    "$draw_ok" \
    "$side_ok" \
    "$appeal_ok" \
    "$missing_keys" \
    "$note"
  write_md_summary "$threshold_decision" "$note"

  echo "ai_judge_fairness_benchmark_freeze_status: $STATUS"
  echo "environment_mode: $ENV_MODE"
  echo "allow_local_reference: $ALLOW_LOCAL_REFERENCE"
  echo "output_env: $OUTPUT_ENV"
  echo "output_doc: $OUTPUT_DOC"
  echo "summary_json: $EMIT_JSON"
  echo "summary_md: $EMIT_MD"
}

main "$@"
