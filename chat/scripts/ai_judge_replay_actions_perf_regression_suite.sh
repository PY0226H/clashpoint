#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASELINE_SCRIPT="${SCRIPT_DIR}/ai_judge_replay_actions_explain_baseline.sh"
COMPARE_SCRIPT="${SCRIPT_DIR}/ai_judge_replay_actions_explain_compare.sh"

BEFORE_DB_URL=""
AFTER_DB_URL=""
ROUNDS=3
OUTPUT_DIR=""
FROM_TS=""
TO_TS=""
LIMIT_VALUE=50
OFFSET_VALUE=0
DRY_RUN=0

usage() {
  cat <<'USAGE'
Usage:
  bash chat/scripts/ai_judge_replay_actions_perf_regression_suite.sh [options]

Options:
  --before-db-url <url>    Baseline database url before optimization
  --after-db-url <url>     Baseline database url after optimization
  --rounds <n>             Sampling rounds per scenario/profile (default: 3)
  --output-dir <path>      Output directory (default: /tmp/replay_perf_suite_<ts>)
  --from <iso8601>         Optional created_at lower bound
  --to <iso8601>           Optional created_at upper bound
  --limit <1..500>         Query limit passed to baseline sampler (default: 50)
  --offset <>=0>           Query offset passed to baseline sampler (default: 0)
  --dry-run                Do not connect database; only generate structure and summary skeleton
  -h, --help               Show this help

Scenarios (fixed in script):
  A: scope=phase, previous=failed, new=queued
  B: A + reason_keyword=ops_ui_manual_replay
  C: A + trace_keyword=trace-old-phase
USAGE
}

require_integer() {
  local value="$1"
  local field="$2"
  if [[ ! "$value" =~ ^[0-9]+$ ]]; then
    echo "${field} must be a non-negative integer: ${value}" >&2
    exit 1
  fi
}

extract_metric() {
  local file="$1"
  local section="$2"
  local metric="$3"
  awk -v target_section="${section}" -v target_metric="${metric}" '
    /^--- COUNT query plan ---$/ {
      section = "COUNT";
      next;
    }
    /^--- LIST query plan ---$/ {
      section = "LIST";
      next;
    }
    /^=== baseline finished ===$/ {
      section = "";
    }
    section == target_section && index($0, target_metric ":") == 1 {
      print $3;
      exit;
    }
  ' "${file}"
}

extract_total_execution_ms() {
  local file="$1"
  local count_exec
  local list_exec
  count_exec="$(extract_metric "${file}" "COUNT" "Execution Time")"
  list_exec="$(extract_metric "${file}" "LIST" "Execution Time")"
  if [[ -z "${count_exec}" || -z "${list_exec}" ]]; then
    echo ""
    return 0
  fi
  awk -v c="${count_exec}" -v l="${list_exec}" 'BEGIN { printf "%.6f", c + l }'
}

calc_avg_from_file() {
  local input_file="$1"
  awk '
    BEGIN { sum = 0; count = 0; }
    { sum += $1; count += 1; }
    END {
      if (count == 0) {
        printf "";
      } else {
        printf "%.6f", sum / count;
      }
    }
  ' "${input_file}"
}

calc_delta() {
  local before="$1"
  local after="$2"
  if [[ -z "${before}" || -z "${after}" ]]; then
    echo "N/A"
    return 0
  fi
  awk -v b="${before}" -v a="${after}" 'BEGIN { printf "%.3f", a - b }'
}

calc_delta_pct() {
  local before="$1"
  local after="$2"
  if [[ -z "${before}" || -z "${after}" ]]; then
    echo "N/A"
    return 0
  fi
  awk -v b="${before}" -v a="${after}" '
    BEGIN {
      if (b == 0) {
        printf "N/A";
      } else {
        printf "%.2f%%", ((a - b) / b) * 100;
      }
    }
  '
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --before-db-url)
      BEFORE_DB_URL="${2:-}"
      shift 2
      ;;
    --after-db-url)
      AFTER_DB_URL="${2:-}"
      shift 2
      ;;
    --rounds)
      ROUNDS="${2:-}"
      shift 2
      ;;
    --output-dir)
      OUTPUT_DIR="${2:-}"
      shift 2
      ;;
    --from)
      FROM_TS="${2:-}"
      shift 2
      ;;
    --to)
      TO_TS="${2:-}"
      shift 2
      ;;
    --limit)
      LIMIT_VALUE="${2:-}"
      shift 2
      ;;
    --offset)
      OFFSET_VALUE="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
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

if [[ -z "${BEFORE_DB_URL}" || -z "${AFTER_DB_URL}" ]]; then
  echo "--before-db-url and --after-db-url are required" >&2
  usage
  exit 1
fi

require_integer "${ROUNDS}" "rounds"
if (( ROUNDS < 1 )); then
  echo "rounds must be >= 1" >&2
  exit 1
fi

require_integer "${LIMIT_VALUE}" "limit"
require_integer "${OFFSET_VALUE}" "offset"
if (( LIMIT_VALUE < 1 || LIMIT_VALUE > 500 )); then
  echo "limit must be in range [1, 500]: ${LIMIT_VALUE}" >&2
  exit 1
fi

if [[ ! -x "${BASELINE_SCRIPT}" ]]; then
  echo "baseline script is not executable: ${BASELINE_SCRIPT}" >&2
  exit 1
fi
if [[ ! -x "${COMPARE_SCRIPT}" ]]; then
  echo "compare script is not executable: ${COMPARE_SCRIPT}" >&2
  exit 1
fi

if [[ -z "${OUTPUT_DIR}" ]]; then
  OUTPUT_DIR="/tmp/replay_perf_suite_$(date +%Y%m%d_%H%M%S)"
fi
mkdir -p "${OUTPUT_DIR}"

summary_tsv="${OUTPUT_DIR}/samples.tsv"
echo -e "scenario\tprofile\tround\tlog_path\ttotal_execution_ms" > "${summary_tsv}"

# scenario_id|scope|previous_status|new_status|reason_keyword|trace_keyword
SCENARIOS=(
  "A|phase|failed|queued||"
  "B|phase|failed|queued|ops_ui_manual_replay|"
  "C|phase|failed|queued||trace-old-phase"
)

run_one_capture() {
  local scenario_id="$1"
  local profile="$2"
  local db_url="$3"
  local round="$4"
  local scope="$5"
  local previous_status="$6"
  local new_status="$7"
  local reason_keyword="$8"
  local trace_keyword="$9"

  local output_log="${OUTPUT_DIR}/${profile}/${scenario_id}/round_${round}.log"
  mkdir -p "$(dirname "${output_log}")"

  if (( DRY_RUN == 1 )); then
    cat > "${output_log}" <<EOF
=== ai_judge_replay_actions query plan baseline ===
--- COUNT query plan ---
Planning Time: 0.000 ms
Execution Time: 0.000 ms
--- LIST query plan ---
Planning Time: 0.000 ms
Execution Time: 0.000 ms
=== baseline finished ===
EOF
    echo -e "${scenario_id}\t${profile}\t${round}\t${output_log}\t0.000000" >> "${summary_tsv}"
    return 0
  fi

  local cmd=(
    bash "${BASELINE_SCRIPT}"
    --db-url "${db_url}"
    --scope "${scope}"
    --previous-status "${previous_status}"
    --new-status "${new_status}"
    --limit "${LIMIT_VALUE}"
    --offset "${OFFSET_VALUE}"
    --output "${output_log}"
  )

  if [[ -n "${FROM_TS}" ]]; then
    cmd+=(--from "${FROM_TS}")
  fi
  if [[ -n "${TO_TS}" ]]; then
    cmd+=(--to "${TO_TS}")
  fi
  if [[ -n "${reason_keyword}" ]]; then
    cmd+=(--reason-keyword "${reason_keyword}")
  fi
  if [[ -n "${trace_keyword}" ]]; then
    cmd+=(--trace-keyword "${trace_keyword}")
  fi

  "${cmd[@]}"

  local total_exec
  total_exec="$(extract_total_execution_ms "${output_log}")"
  echo -e "${scenario_id}\t${profile}\t${round}\t${output_log}\t${total_exec}" >> "${summary_tsv}"
}

echo "[suite] start replay actions performance regression suite"
echo "[suite] output dir: ${OUTPUT_DIR}"
if (( DRY_RUN == 1 )); then
  echo "[suite] mode: dry-run"
fi

for row in "${SCENARIOS[@]}"; do
  IFS='|' read -r scenario_id scope previous_status new_status reason_keyword trace_keyword <<< "${row}"
  for ((round = 1; round <= ROUNDS; round += 1)); do
    run_one_capture "${scenario_id}" "before" "${BEFORE_DB_URL}" "${round}" "${scope}" "${previous_status}" "${new_status}" "${reason_keyword}" "${trace_keyword}"
    run_one_capture "${scenario_id}" "after" "${AFTER_DB_URL}" "${round}" "${scope}" "${previous_status}" "${new_status}" "${reason_keyword}" "${trace_keyword}"
  done
done

report_md="${OUTPUT_DIR}/summary.md"
{
  echo "# Replay Actions Performance Regression Suite"
  echo
  echo "- Output Dir: \`${OUTPUT_DIR}\`"
  echo "- Rounds: \`${ROUNDS}\`"
  echo "- Limit: \`${LIMIT_VALUE}\`, Offset: \`${OFFSET_VALUE}\`"
  if [[ -n "${FROM_TS}" ]]; then
    echo "- From: \`${FROM_TS}\`"
  fi
  if [[ -n "${TO_TS}" ]]; then
    echo "- To: \`${TO_TS}\`"
  fi
  echo
  echo "## Sample Matrix"
  echo
  echo "| Scenario | Profile | Round | Total Execution (ms) | Log |"
  echo "|---|---|---:|---:|---|"

  awk -F'\t' 'NR > 1 {
    total = ($5 == "" ? "N/A" : sprintf("%.3f", $5 + 0));
    printf "| %s | %s | %s | %s | `%s` |\n", $1, $2, $3, total, $4;
  }' "${summary_tsv}"

  echo
  echo "## Scenario Summary"
  echo
  echo "| Scenario | Before Avg(ms) | After Avg(ms) | Delta(ms) | Delta% |"
  echo "|---|---:|---:|---:|---:|"

  for scenario in A B C; do
    before_file="${OUTPUT_DIR}/tmp_before_${scenario}.txt"
    after_file="${OUTPUT_DIR}/tmp_after_${scenario}.txt"
    awk -F'\t' -v s="${scenario}" '$1 == s && $2 == "before" && $5 != "" { print $5 }' "${summary_tsv}" > "${before_file}"
    awk -F'\t' -v s="${scenario}" '$1 == s && $2 == "after" && $5 != "" { print $5 }' "${summary_tsv}" > "${after_file}"

    before_avg="$(calc_avg_from_file "${before_file}")"
    after_avg="$(calc_avg_from_file "${after_file}")"
    delta="$(calc_delta "${before_avg}" "${after_avg}")"
    delta_pct="$(calc_delta_pct "${before_avg}" "${after_avg}")"

    before_fmt="N/A"
    after_fmt="N/A"
    if [[ -n "${before_avg}" ]]; then
      before_fmt="$(awk -v v="${before_avg}" 'BEGIN { printf "%.3f", v + 0 }')"
    fi
    if [[ -n "${after_avg}" ]]; then
      after_fmt="$(awk -v v="${after_avg}" 'BEGIN { printf "%.3f", v + 0 }')"
    fi

    echo "| ${scenario} | ${before_fmt} | ${after_fmt} | ${delta} | ${delta_pct} |"

    rm -f "${before_file}" "${after_file}"
  done
} > "${report_md}"

# Generate a detailed comparison markdown for round 1 of each scenario.
for scenario in A B C; do
  before_log="${OUTPUT_DIR}/before/${scenario}/round_1.log"
  after_log="${OUTPUT_DIR}/after/${scenario}/round_1.log"
  compare_output="${OUTPUT_DIR}/compare_${scenario}_round1.md"
  bash "${COMPARE_SCRIPT}" \
    --before "${before_log}" \
    --after "${after_log}" \
    --label-before "before" \
    --label-after "after" \
    --output "${compare_output}" >/dev/null
done

echo "[suite] finished"
echo "[suite] summary report: ${report_md}"
