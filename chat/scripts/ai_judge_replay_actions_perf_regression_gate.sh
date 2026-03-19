#!/usr/bin/env bash
set -euo pipefail

SUITE_OUTPUT_DIR=""
OUTPUT_DIR=""
REPORT_FILE=""
JSON_FILE=""
EXPECTED_ROUNDS=""
MIN_EFFECTIVE_IMPROVE_PCT="-20"
MAX_REGRESSION_PCT="10"
FAIL_ON_WARN=0

usage() {
  cat <<'USAGE'
Usage:
  bash chat/scripts/ai_judge_replay_actions_perf_regression_gate.sh [options]

Options:
  --suite-output-dir <path>         Suite output directory that contains samples.tsv
  --output-dir <path>               Output directory for gate artifacts (default: suite dir)
  --report-file <path>              Markdown gate report path (default: <output-dir>/gate_report.md)
  --json-file <path>                JSON gate result path (default: <output-dir>/gate_result.json)
  --expected-rounds <n>             Expected rounds for each scenario/profile pair
  --min-effective-improve-pct <n>   Effective improvement threshold in percent (default: -20)
  --max-regression-pct <n>          Regression risk threshold in percent (default: 10)
  --fail-on-warn                    Return non-zero when overall status is WARN
  -h, --help                        Show this help

Status semantics:
  PASS: Delta% <= min-effective-improve-pct
  WARN: Delta% is between thresholds, or before average is zero
  FAIL: Delta% > max-regression-pct, missing/incomplete samples, or parse failures
USAGE
}

require_integer() {
  local value="$1"
  local field="$2"
  if [[ ! "${value}" =~ ^[0-9]+$ ]]; then
    echo "${field} must be a non-negative integer: ${value}" >&2
    exit 1
  fi
}

require_number() {
  local value="$1"
  local field="$2"
  if [[ ! "${value}" =~ ^-?[0-9]+([.][0-9]+)?$ ]]; then
    echo "${field} must be a number: ${value}" >&2
    exit 1
  fi
}

is_numeric() {
  [[ "$1" =~ ^-?[0-9]+([.][0-9]+)?$ ]]
}

json_escape() {
  local value="$1"
  value="${value//\\/\\\\}"
  value="${value//\"/\\\"}"
  value="${value//$'\n'/ }"
  printf '%s' "${value}"
}

count_rows() {
  local samples_file="$1"
  local scenario="$2"
  local profile="$3"
  awk -F'\t' -v s="${scenario}" -v p="${profile}" '
    NR > 1 && $1 == s && $2 == p { count += 1 }
    END { print count + 0 }
  ' "${samples_file}"
}

avg_total_execution_ms() {
  local samples_file="$1"
  local scenario="$2"
  local profile="$3"
  awk -F'\t' -v s="${scenario}" -v p="${profile}" '
    NR > 1 && $1 == s && $2 == p {
      if ($5 ~ /^-?[0-9]+(\.[0-9]+)?$/) {
        sum += $5
        count += 1
      }
    }
    END {
      if (count == 0) {
        printf ""
      } else {
        printf "%.6f", sum / count
      }
    }
  ' "${samples_file}"
}

calc_delta_ms() {
  local before="$1"
  local after="$2"
  if [[ -z "${before}" || -z "${after}" ]]; then
    printf "N/A"
    return 0
  fi
  awk -v b="${before}" -v a="${after}" 'BEGIN { printf "%.3f", a - b }'
}

calc_delta_pct() {
  local before="$1"
  local after="$2"
  if [[ -z "${before}" || -z "${after}" ]]; then
    printf "N/A"
    return 0
  fi
  awk -v b="${before}" -v a="${after}" '
    BEGIN {
      if (b == 0) {
        printf "N/A"
      } else {
        printf "%.2f", ((a - b) / b) * 100
      }
    }
  '
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --suite-output-dir)
      SUITE_OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --report-file)
      REPORT_FILE="${2:-}"
      shift 2
      ;;
    --json-file)
      JSON_FILE="${2:-}"
      shift 2
      ;;
    --expected-rounds)
      EXPECTED_ROUNDS="${2:-}"
      shift 2
      ;;
    --min-effective-improve-pct)
      MIN_EFFECTIVE_IMPROVE_PCT="${2:-}"
      shift 2
      ;;
    --max-regression-pct)
      MAX_REGRESSION_PCT="${2:-}"
      shift 2
      ;;
    --fail-on-warn)
      FAIL_ON_WARN=1
      shift 1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "${SUITE_OUTPUT_DIR}" ]]; then
  echo "--suite-output-dir is required" >&2
  usage
  exit 1
fi

samples_tsv="${SUITE_OUTPUT_DIR%/}/samples.tsv"
if [[ ! -f "${samples_tsv}" ]]; then
  echo "samples.tsv not found: ${samples_tsv}" >&2
  exit 1
fi

if [[ -n "${EXPECTED_ROUNDS}" ]]; then
  require_integer "${EXPECTED_ROUNDS}" "expected-rounds"
  if (( EXPECTED_ROUNDS < 1 )); then
    echo "expected-rounds must be >= 1" >&2
    exit 1
  fi
fi

require_number "${MIN_EFFECTIVE_IMPROVE_PCT}" "min-effective-improve-pct"
require_number "${MAX_REGRESSION_PCT}" "max-regression-pct"

if [[ -z "${OUTPUT_DIR}" ]]; then
  OUTPUT_DIR="${SUITE_OUTPUT_DIR%/}"
fi
mkdir -p "${OUTPUT_DIR}"

if [[ -z "${REPORT_FILE}" ]]; then
  REPORT_FILE="${OUTPUT_DIR%/}/gate_report.md"
fi
if [[ -z "${JSON_FILE}" ]]; then
  JSON_FILE="${OUTPUT_DIR%/}/gate_result.json"
fi

scenarios=(A B C)
before_counts=()
after_counts=()
before_avgs=()
after_avgs=()
delta_ms_values=()
delta_pct_values=()
scenario_statuses=()
scenario_notes=()

pass_count=0
warn_count=0
fail_count=0

for i in "${!scenarios[@]}"; do
  scenario="${scenarios[$i]}"

  before_count="$(count_rows "${samples_tsv}" "${scenario}" "before")"
  after_count="$(count_rows "${samples_tsv}" "${scenario}" "after")"
  before_avg="$(avg_total_execution_ms "${samples_tsv}" "${scenario}" "before")"
  after_avg="$(avg_total_execution_ms "${samples_tsv}" "${scenario}" "after")"

  before_counts[$i]="${before_count}"
  after_counts[$i]="${after_count}"
  before_avgs[$i]="${before_avg}"
  after_avgs[$i]="${after_avg}"

  status="PASS"
  note=""

  if (( before_count == 0 || after_count == 0 )); then
    status="FAIL"
    note="missing samples"
  elif [[ -n "${EXPECTED_ROUNDS}" && ( "${before_count}" != "${EXPECTED_ROUNDS}" || "${after_count}" != "${EXPECTED_ROUNDS}" ) ]]; then
    status="FAIL"
    note="round mismatch (expected=${EXPECTED_ROUNDS}, before=${before_count}, after=${after_count})"
  elif [[ "${before_count}" != "${after_count}" ]]; then
    status="FAIL"
    note="before/after sample count mismatch"
  elif [[ -z "${before_avg}" || -z "${after_avg}" ]]; then
    status="FAIL"
    note="unable to parse total_execution_ms"
  fi

  delta_ms="N/A"
  delta_pct="N/A"

  if [[ "${status}" != "FAIL" ]]; then
    delta_ms="$(calc_delta_ms "${before_avg}" "${after_avg}")"
    delta_pct="$(calc_delta_pct "${before_avg}" "${after_avg}")"

    if [[ "${delta_pct}" == "N/A" ]]; then
      status="WARN"
      note="before average is zero, delta percent unavailable"
    elif awk -v d="${delta_pct}" -v threshold="${MAX_REGRESSION_PCT}" 'BEGIN { exit !(d > threshold) }'; then
      status="FAIL"
      note="regression risk exceeds threshold"
    elif awk -v d="${delta_pct}" -v threshold="${MIN_EFFECTIVE_IMPROVE_PCT}" 'BEGIN { exit !(d <= threshold) }'; then
      status="PASS"
      note="effective improvement meets threshold"
    else
      status="WARN"
      note="stable but below effective improvement threshold"
    fi
  fi

  scenario_statuses[$i]="${status}"
  scenario_notes[$i]="${note}"
  delta_ms_values[$i]="${delta_ms}"
  delta_pct_values[$i]="${delta_pct}"

  case "${status}" in
    PASS)
      pass_count=$((pass_count + 1))
      ;;
    WARN)
      warn_count=$((warn_count + 1))
      ;;
    FAIL)
      fail_count=$((fail_count + 1))
      ;;
    *)
      ;;
  esac
done

overall_status="PASS"
exit_code=0
if (( fail_count > 0 )); then
  overall_status="FAIL"
  exit_code=2
elif (( warn_count > 0 )); then
  overall_status="WARN"
  if (( FAIL_ON_WARN == 1 )); then
    exit_code=1
  fi
fi

{
  echo "# Replay Actions Regression Gate Report"
  echo
  echo "- suite_output_dir: \`${SUITE_OUTPUT_DIR}\`"
  echo "- samples_tsv: \`${samples_tsv}\`"
  echo "- min_effective_improve_pct: \`${MIN_EFFECTIVE_IMPROVE_PCT}\`"
  echo "- max_regression_pct: \`${MAX_REGRESSION_PCT}\`"
  if [[ -n "${EXPECTED_ROUNDS}" ]]; then
    echo "- expected_rounds: \`${EXPECTED_ROUNDS}\`"
  else
    echo "- expected_rounds: \`(not set)\`"
  fi
  echo
  echo "## Completeness"
  echo
  echo "| Scenario | Before Count | After Count | Status |"
  echo "|---|---:|---:|---|"

  for i in "${!scenarios[@]}"; do
    completeness_status="OK"
    if [[ "${scenario_statuses[$i]}" == "FAIL" && "${scenario_notes[$i]}" == *"sample"* ]]; then
      completeness_status="FAIL"
    elif [[ "${scenario_statuses[$i]}" == "FAIL" && "${scenario_notes[$i]}" == *"round mismatch"* ]]; then
      completeness_status="FAIL"
    elif [[ "${scenario_statuses[$i]}" == "FAIL" && "${scenario_notes[$i]}" == *"count mismatch"* ]]; then
      completeness_status="FAIL"
    fi

    echo "| ${scenarios[$i]} | ${before_counts[$i]} | ${after_counts[$i]} | ${completeness_status} |"
  done

  echo
  echo "## Performance Assessment"
  echo
  echo "| Scenario | Before Avg(ms) | After Avg(ms) | Delta(ms) | Delta(%) | Status | Note |"
  echo "|---|---:|---:|---:|---:|---|---|"

  for i in "${!scenarios[@]}"; do
    before_fmt="N/A"
    after_fmt="N/A"
    if [[ -n "${before_avgs[$i]}" ]]; then
      before_fmt="$(awk -v v="${before_avgs[$i]}" 'BEGIN { printf "%.3f", v + 0 }')"
    fi
    if [[ -n "${after_avgs[$i]}" ]]; then
      after_fmt="$(awk -v v="${after_avgs[$i]}" 'BEGIN { printf "%.3f", v + 0 }')"
    fi

    delta_pct_fmt="${delta_pct_values[$i]}"
    if is_numeric "${delta_pct_fmt}"; then
      delta_pct_fmt="$(awk -v v="${delta_pct_fmt}" 'BEGIN { printf "%.2f%%", v + 0 }')"
    fi

    echo "| ${scenarios[$i]} | ${before_fmt} | ${after_fmt} | ${delta_ms_values[$i]} | ${delta_pct_fmt} | ${scenario_statuses[$i]} | ${scenario_notes[$i]} |"
  done

  echo
  echo "## Overall"
  echo
  echo "- overall_status: **${overall_status}**"
  echo "- scenario_pass_warn_fail: \`${pass_count}/${warn_count}/${fail_count}\`"
  echo "- fail_on_warn: \`${FAIL_ON_WARN}\`"
  echo "- exit_code: \`${exit_code}\`"
} > "${REPORT_FILE}"

{
  echo "{"
  echo "  \"generatedAt\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\","
  echo "  \"suiteOutputDir\": \"$(json_escape "${SUITE_OUTPUT_DIR}")\","
  echo "  \"samplesTsv\": \"$(json_escape "${samples_tsv}")\","
  echo "  \"thresholds\": {"
  echo "    \"minEffectiveImprovePct\": ${MIN_EFFECTIVE_IMPROVE_PCT},"
  echo "    \"maxRegressionPct\": ${MAX_REGRESSION_PCT},"
  if [[ -n "${EXPECTED_ROUNDS}" ]]; then
    echo "    \"expectedRounds\": ${EXPECTED_ROUNDS}"
  else
    echo "    \"expectedRounds\": null"
  fi
  echo "  },"
  echo "  \"overall\": {"
  echo "    \"status\": \"${overall_status}\","
  echo "    \"pass\": ${pass_count},"
  echo "    \"warn\": ${warn_count},"
  echo "    \"fail\": ${fail_count},"
  echo "    \"failOnWarn\": ${FAIL_ON_WARN},"
  echo "    \"exitCode\": ${exit_code}"
  echo "  },"
  echo "  \"scenarios\": ["

  for i in "${!scenarios[@]}"; do
    before_avg_json="null"
    after_avg_json="null"
    delta_pct_json="null"

    if [[ -n "${before_avgs[$i]}" ]]; then
      before_avg_json="${before_avgs[$i]}"
    fi
    if [[ -n "${after_avgs[$i]}" ]]; then
      after_avg_json="${after_avgs[$i]}"
    fi
    if is_numeric "${delta_pct_values[$i]}"; then
      delta_pct_json="${delta_pct_values[$i]}"
    fi

    if (( i > 0 )); then
      echo ","
    fi

    printf '    {\"scenario\":\"%s\",\"beforeCount\":%s,\"afterCount\":%s,\"beforeAvgMs\":%s,\"afterAvgMs\":%s,\"deltaMs\":\"%s\",\"deltaPct\":%s,\"status\":\"%s\",\"note\":\"%s\"}' \
      "${scenarios[$i]}" \
      "${before_counts[$i]}" \
      "${after_counts[$i]}" \
      "${before_avg_json}" \
      "${after_avg_json}" \
      "$(json_escape "${delta_ms_values[$i]}")" \
      "${delta_pct_json}" \
      "${scenario_statuses[$i]}" \
      "$(json_escape "${scenario_notes[$i]}")"
  done

  echo
  echo "  ]"
  echo "}"
} > "${JSON_FILE}"

echo "[gate] report: ${REPORT_FILE}"
echo "[gate] json: ${JSON_FILE}"
echo "[gate] overall: ${overall_status}"

exit "${exit_code}"
