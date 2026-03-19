#!/usr/bin/env bash
set -euo pipefail

BEFORE_LOG=""
AFTER_LOG=""
LABEL_BEFORE="before"
LABEL_AFTER="after"
OUTPUT_PATH=""

usage() {
  cat <<'USAGE'
Usage:
  bash chat/scripts/ai_judge_replay_actions_explain_compare.sh [options]

Options:
  --before <path>         Baseline log path before optimization
  --after <path>          Baseline log path after optimization
  --label-before <text>   Label for before baseline (default: before)
  --label-after <text>    Label for after baseline (default: after)
  --output <path>         Output markdown report path
  -h, --help              Show this help

Examples:
  bash chat/scripts/ai_judge_replay_actions_explain_compare.sh \
    --before /tmp/replay_before.log \
    --after /tmp/replay_after.log \
    --label-before no_trgm \
    --label-after with_trgm
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --before)
      BEFORE_LOG="${2:-}"
      shift 2
      ;;
    --after)
      AFTER_LOG="${2:-}"
      shift 2
      ;;
    --label-before)
      LABEL_BEFORE="${2:-}"
      shift 2
      ;;
    --label-after)
      LABEL_AFTER="${2:-}"
      shift 2
      ;;
    --output)
      OUTPUT_PATH="${2:-}"
      shift 2
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

if [[ -z "${BEFORE_LOG}" || -z "${AFTER_LOG}" ]]; then
  echo "--before and --after are required" >&2
  usage
  exit 1
fi

if [[ ! -f "${BEFORE_LOG}" ]]; then
  echo "before log not found: ${BEFORE_LOG}" >&2
  exit 1
fi

if [[ ! -f "${AFTER_LOG}" ]]; then
  echo "after log not found: ${AFTER_LOG}" >&2
  exit 1
fi

if [[ -z "${OUTPUT_PATH}" ]]; then
  OUTPUT_PATH="/tmp/ai_judge_replay_actions_explain_compare_$(date +%Y%m%d_%H%M%S).md"
fi

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

format_float() {
  local value="${1:-}"
  if [[ -z "${value}" ]]; then
    echo "N/A"
    return 0
  fi
  awk -v n="${value}" 'BEGIN { printf "%.3f", n + 0 }'
}

calc_delta() {
  local before="${1:-}"
  local after="${2:-}"
  if [[ -z "${before}" || -z "${after}" ]]; then
    echo "N/A"
    return 0
  fi
  awk -v b="${before}" -v a="${after}" 'BEGIN { printf "%.3f", a - b }'
}

calc_delta_pct() {
  local before="${1:-}"
  local after="${2:-}"
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

count_exec_before="$(extract_metric "${BEFORE_LOG}" "COUNT" "Execution Time")"
count_exec_after="$(extract_metric "${AFTER_LOG}" "COUNT" "Execution Time")"
list_exec_before="$(extract_metric "${BEFORE_LOG}" "LIST" "Execution Time")"
list_exec_after="$(extract_metric "${AFTER_LOG}" "LIST" "Execution Time")"
count_plan_before="$(extract_metric "${BEFORE_LOG}" "COUNT" "Planning Time")"
count_plan_after="$(extract_metric "${AFTER_LOG}" "COUNT" "Planning Time")"
list_plan_before="$(extract_metric "${BEFORE_LOG}" "LIST" "Planning Time")"
list_plan_after="$(extract_metric "${AFTER_LOG}" "LIST" "Planning Time")"

total_exec_before=""
if [[ -n "${count_exec_before}" && -n "${list_exec_before}" ]]; then
  total_exec_before="$(awk -v c="${count_exec_before}" -v l="${list_exec_before}" 'BEGIN { printf "%.6f", c + l }')"
fi

total_exec_after=""
if [[ -n "${count_exec_after}" && -n "${list_exec_after}" ]]; then
  total_exec_after="$(awk -v c="${count_exec_after}" -v l="${list_exec_after}" 'BEGIN { printf "%.6f", c + l }')"
fi

mkdir -p "$(dirname "${OUTPUT_PATH}")"

cat > "${OUTPUT_PATH}" <<EOF
# Replay Actions Explain Baseline Compare

- Before label: \`${LABEL_BEFORE}\`
- After label: \`${LABEL_AFTER}\`
- Before log: \`${BEFORE_LOG}\`
- After log: \`${AFTER_LOG}\`

| Metric | ${LABEL_BEFORE} | ${LABEL_AFTER} | Delta(after-before) | Delta% |
|---|---:|---:|---:|---:|
| COUNT Planning Time (ms) | $(format_float "${count_plan_before}") | $(format_float "${count_plan_after}") | $(calc_delta "${count_plan_before}" "${count_plan_after}") | $(calc_delta_pct "${count_plan_before}" "${count_plan_after}") |
| COUNT Execution Time (ms) | $(format_float "${count_exec_before}") | $(format_float "${count_exec_after}") | $(calc_delta "${count_exec_before}" "${count_exec_after}") | $(calc_delta_pct "${count_exec_before}" "${count_exec_after}") |
| LIST Planning Time (ms) | $(format_float "${list_plan_before}") | $(format_float "${list_plan_after}") | $(calc_delta "${list_plan_before}" "${list_plan_after}") | $(calc_delta_pct "${list_plan_before}" "${list_plan_after}") |
| LIST Execution Time (ms) | $(format_float "${list_exec_before}") | $(format_float "${list_exec_after}") | $(calc_delta "${list_exec_before}" "${list_exec_after}") | $(calc_delta_pct "${list_exec_before}" "${list_exec_after}") |
| TOTAL Execution Time (COUNT+LIST, ms) | $(format_float "${total_exec_before}") | $(format_float "${total_exec_after}") | $(calc_delta "${total_exec_before}" "${total_exec_after}") | $(calc_delta_pct "${total_exec_before}" "${total_exec_after}") |
EOF

echo "[compare] report written: ${OUTPUT_PATH}"
