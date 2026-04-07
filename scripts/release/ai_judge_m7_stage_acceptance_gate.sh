#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  ai_judge_m7_stage_acceptance_gate.sh [options]

Options:
  --regression-evidence <path>  AI Judge regression evidence env file
                                default: docs/loadtest/evidence/ai_judge_m7_regression.env
  --preprod-summary <path>      AI Judge preprod load summary env file
                                default: docs/loadtest/evidence/ai_judge_m7_preprod_summary.env
  --fault-matrix <path>         AI Judge fault injection matrix env file
                                default: docs/loadtest/evidence/ai_judge_m7_fault_matrix.env
  --report-out <path>           Markdown report output path
                                default: docs/loadtest/evidence/AI裁判M7阶段验收报告-<YYYY-MM-DD>.md
  --root <path>                 Repo root path (default: git top-level or cwd)
  --allow-missing-scenarios     Do not fail when SOAK/SPIKE scenario key is missing
  -h, --help                    Show this help

Evidence file format (KEY=VALUE):
  Regression evidence keys:
    REGRESSION_AI_JUDGE_M7_ACCEPTANCE=pass|fail
    REGRESSION_AI_JUDGE_M7_GATE=pass|fail
    REGRESSION_AI_JUDGE_UNITTEST_ALL=pass|fail
    REGRESSION_LAST_RUN_AT=2026-03-05T02:20:00Z

  Preprod summary keys:
    LOADTEST_STAGE=preprod
    LOAD_SCENARIOS=SOAK,SPIKE
    SOAK_RESULT=pass
    SPIKE_RESULT=pass
    AI_JUDGE_SUCCESS_RATE=98.6
    AI_JUDGE_P95_SECONDS=240

  Fault matrix keys:
    FAULT_SCENARIOS=provider_timeout,provider_overload,rag_unavailable,model_overload,consistency_conflict
    FI_PROVIDER_TIMEOUT=pass
    FI_PROVIDER_OVERLOAD=pass
    FI_RAG_UNAVAILABLE=pass
    FI_MODEL_OVERLOAD=pass
    FI_CONSISTENCY_CONFLICT=pass
    FI_LAST_RUN_AT=2026-03-05T03:00:00Z
USAGE
}

trim() {
  local value="$1"
  value="${value#${value%%[![:space:]]*}}"
  value="${value%${value##*[![:space:]]}}"
  printf '%s' "$value"
}

to_lower() {
  printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

is_truthy() {
  local value
  value="$(to_lower "$(trim "$1")")"
  [[ "$value" == "true" || "$value" == "1" || "$value" == "yes" || "$value" == "pass" || "$value" == "ok" ]]
}

read_env_value() {
  local key="$1"
  local env_file="$2"
  if [[ ! -f "$env_file" ]]; then
    return 1
  fi
  awk -v key="$key" '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*$/ { next }
    {
      line = $0
      sub(/^[[:space:]]+/, "", line)
      if (index(line, key "=") == 1) {
        value = substr(line, length(key) + 2)
        sub(/[[:space:]]+#.*/, "", value)
        gsub(/^[[:space:]]+|[[:space:]]+$/, "", value)
        if (value ~ /^".*"$/ || value ~ /^'\''.*'\''$/) {
          value = substr(value, 2, length(value) - 2)
        }
        print value
        exit
      }
    }
  ' "$env_file"
}

is_number() {
  local value
  value="$(trim "$1")"
  [[ "$value" =~ ^-?[0-9]+([.][0-9]+)?$ ]]
}

compare_ge() {
  local value="$1"
  local threshold="$2"
  awk -v a="$value" -v b="$threshold" 'BEGIN { exit !(a + 0 >= b + 0) }'
}

compare_le() {
  local value="$1"
  local threshold="$2"
  awk -v a="$value" -v b="$threshold" 'BEGIN { exit !(a + 0 <= b + 0) }'
}

PASS_ITEMS=()
FAIL_ITEMS=()
WARN_ITEMS=()
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

mark_pass() {
  PASS_ITEMS+=("$1")
  PASS_COUNT=$((PASS_COUNT + 1))
}

mark_fail() {
  FAIL_ITEMS+=("$1")
  FAIL_COUNT=$((FAIL_COUNT + 1))
}

mark_warn() {
  WARN_ITEMS+=("$1")
  WARN_COUNT=$((WARN_COUNT + 1))
}

ROOT=""
REGRESSION_EVIDENCE=""
PREPROD_SUMMARY=""
FAULT_MATRIX=""
REPORT_OUT=""
STRICT_SCENARIO="true"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --regression-evidence)
      REGRESSION_EVIDENCE="$2"
      shift 2
      ;;
    --preprod-summary)
      PREPROD_SUMMARY="$2"
      shift 2
      ;;
    --fault-matrix)
      FAULT_MATRIX="$2"
      shift 2
      ;;
    --report-out)
      REPORT_OUT="$2"
      shift 2
      ;;
    --root)
      ROOT="$2"
      shift 2
      ;;
    --allow-missing-scenarios)
      STRICT_SCENARIO="false"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$ROOT" ]]; then
  if git rev-parse --show-toplevel >/dev/null 2>&1; then
    ROOT="$(git rev-parse --show-toplevel)"
  else
    ROOT="$(pwd)"
  fi
fi

if [[ -z "$REGRESSION_EVIDENCE" ]]; then
  REGRESSION_EVIDENCE="$ROOT/docs/loadtest/evidence/ai_judge_m7_regression.env"
fi
if [[ -z "$PREPROD_SUMMARY" ]]; then
  PREPROD_SUMMARY="$ROOT/docs/loadtest/evidence/ai_judge_m7_preprod_summary.env"
fi
if [[ -z "$FAULT_MATRIX" ]]; then
  FAULT_MATRIX="$ROOT/docs/loadtest/evidence/ai_judge_m7_fault_matrix.env"
fi
if [[ -z "$REPORT_OUT" ]]; then
  REPORT_OUT="$ROOT/docs/loadtest/evidence/AI裁判M7阶段验收报告-$(date +%F).md"
fi

mkdir -p "$(dirname "$REPORT_OUT")"

echo "== AI Judge M7 stage acceptance gate =="
echo "root: $ROOT"
echo "regression_evidence: $REGRESSION_EVIDENCE"
echo "preprod_summary: $PREPROD_SUMMARY"
echo "fault_matrix: $FAULT_MATRIX"
echo "report_out: $REPORT_OUT"
echo

if [[ ! -f "$REGRESSION_EVIDENCE" ]]; then
  mark_fail "regression evidence not found: $REGRESSION_EVIDENCE"
fi
if [[ ! -f "$PREPROD_SUMMARY" ]]; then
  mark_fail "preprod summary not found: $PREPROD_SUMMARY"
fi
if [[ ! -f "$FAULT_MATRIX" ]]; then
  mark_fail "fault matrix not found: $FAULT_MATRIX"
fi

if [[ "$FAIL_COUNT" -eq 0 ]]; then
  regress_keys=(
    "REGRESSION_AI_JUDGE_M7_ACCEPTANCE"
    "REGRESSION_AI_JUDGE_M7_GATE"
    "REGRESSION_AI_JUDGE_UNITTEST_ALL"
  )
  for key in "${regress_keys[@]}"; do
    value="$(read_env_value "$key" "$REGRESSION_EVIDENCE" || true)"
    if [[ -z "$value" ]]; then
      mark_fail "regression key missing: $key"
      continue
    fi
    if is_truthy "$value"; then
      mark_pass "$key=$value"
    else
      mark_fail "$key=$value"
    fi
  done

  regression_last_run_at="$(read_env_value "REGRESSION_LAST_RUN_AT" "$REGRESSION_EVIDENCE" || true)"
  if [[ -z "$regression_last_run_at" ]]; then
    mark_warn "REGRESSION_LAST_RUN_AT is empty"
  else
    mark_pass "REGRESSION_LAST_RUN_AT=$regression_last_run_at"
  fi

  stage_value="$(to_lower "$(trim "$(read_env_value "LOADTEST_STAGE" "$PREPROD_SUMMARY" || true)")")"
  if [[ -z "$stage_value" ]]; then
    mark_fail "preprod summary missing LOADTEST_STAGE"
  elif [[ "$stage_value" != "preprod" && "$stage_value" != "staging" ]]; then
    mark_warn "LOADTEST_STAGE=$stage_value (expected preprod/staging)"
  else
    mark_pass "LOADTEST_STAGE=$stage_value"
  fi

  required_scenarios=("SOAK" "SPIKE")
  scenario_csv="$(to_lower "$(read_env_value "LOAD_SCENARIOS" "$PREPROD_SUMMARY" || true)")"
  for scenario in "${required_scenarios[@]}"; do
    scenario_lower="$(to_lower "$scenario")"
    if [[ "$scenario_csv" != *"$scenario_lower"* ]]; then
      if [[ "$STRICT_SCENARIO" == "true" ]]; then
        mark_fail "LOAD_SCENARIOS missing $scenario"
      else
        mark_warn "LOAD_SCENARIOS missing $scenario"
      fi
    else
      mark_pass "LOAD_SCENARIOS includes $scenario"
    fi

    scenario_key="${scenario}_RESULT"
    scenario_result="$(read_env_value "$scenario_key" "$PREPROD_SUMMARY" || true)"
    if [[ -z "$scenario_result" ]]; then
      if [[ "$STRICT_SCENARIO" == "true" ]]; then
        mark_fail "$scenario_key missing"
      else
        mark_warn "$scenario_key missing"
      fi
      continue
    fi
    if is_truthy "$scenario_result"; then
      mark_pass "$scenario_key=$scenario_result"
    else
      mark_fail "$scenario_key=$scenario_result"
    fi
  done

  declare -a threshold_checks=(
    "AI_JUDGE_SUCCESS_RATE|98|ge|AI 判决可用率 >= 98"
    "AI_JUDGE_P95_SECONDS|300|le|AI 判决 P95 <= 300s"
  )

  for spec in "${threshold_checks[@]}"; do
    IFS='|' read -r key threshold op label <<<"$spec"
    value="$(read_env_value "$key" "$PREPROD_SUMMARY" || true)"
    if [[ -z "$value" ]]; then
      mark_fail "$key missing"
      continue
    fi
    if ! is_number "$value"; then
      mark_fail "$key=$value is not numeric"
      continue
    fi

    passed="false"
    case "$op" in
      ge)
        if compare_ge "$value" "$threshold"; then
          passed="true"
        fi
        ;;
      le)
        if compare_le "$value" "$threshold"; then
          passed="true"
        fi
        ;;
      *)
        mark_fail "invalid threshold op for $key: $op"
        continue
        ;;
    esac

    if [[ "$passed" == "true" ]]; then
      mark_pass "$label (actual=$value, threshold=$op $threshold)"
    else
      mark_fail "$label (actual=$value, threshold=$op $threshold)"
    fi
  done

  required_faults=(
    "provider_timeout|FI_PROVIDER_TIMEOUT"
    "provider_overload|FI_PROVIDER_OVERLOAD"
    "rag_unavailable|FI_RAG_UNAVAILABLE"
    "model_overload|FI_MODEL_OVERLOAD"
    "consistency_conflict|FI_CONSISTENCY_CONFLICT"
  )
  fault_csv="$(to_lower "$(read_env_value "FAULT_SCENARIOS" "$FAULT_MATRIX" || true)")"
  for pair in "${required_faults[@]}"; do
    IFS='|' read -r scenario key <<<"$pair"
    if [[ "$fault_csv" != *"$scenario"* ]]; then
      mark_fail "FAULT_SCENARIOS missing $scenario"
    else
      mark_pass "FAULT_SCENARIOS includes $scenario"
    fi

    value="$(read_env_value "$key" "$FAULT_MATRIX" || true)"
    if [[ -z "$value" ]]; then
      mark_fail "$key missing"
      continue
    fi
    if is_truthy "$value"; then
      mark_pass "$key=$value"
    else
      mark_fail "$key=$value"
    fi
  done

  fault_last_run_at="$(read_env_value "FI_LAST_RUN_AT" "$FAULT_MATRIX" || true)"
  if [[ -z "$fault_last_run_at" ]]; then
    mark_warn "FI_LAST_RUN_AT is empty"
  else
    mark_pass "FI_LAST_RUN_AT=$fault_last_run_at"
  fi
fi

{
  echo "# AI裁判 M7 阶段验收报告"
  echo
  echo "- 生成时间: $(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "- 回归证据: $REGRESSION_EVIDENCE"
  echo "- 预发压测汇总: $PREPROD_SUMMARY"
  echo "- 故障注入矩阵: $FAULT_MATRIX"
  echo "- 结果: $([[ "$FAIL_COUNT" -eq 0 ]] && echo "PASSED" || echo "FAILED")"
  echo
  echo "## 通过项 ($PASS_COUNT)"
  if [[ "$PASS_COUNT" -eq 0 ]]; then
    echo "- (none)"
  else
    for item in "${PASS_ITEMS[@]-}"; do
      [[ -z "$item" ]] && continue
      echo "- $item"
    done
  fi
  echo
  echo "## 警告项 ($WARN_COUNT)"
  if [[ "$WARN_COUNT" -eq 0 ]]; then
    echo "- (none)"
  else
    for item in "${WARN_ITEMS[@]-}"; do
      [[ -z "$item" ]] && continue
      echo "- $item"
    done
  fi
  echo
  echo "## 失败项 ($FAIL_COUNT)"
  if [[ "$FAIL_COUNT" -eq 0 ]]; then
    echo "- (none)"
  else
    for item in "${FAIL_ITEMS[@]-}"; do
      [[ -z "$item" ]] && continue
      echo "- $item"
    done
  fi
} >"$REPORT_OUT"

echo "---- PASS ----"
for item in "${PASS_ITEMS[@]-}"; do
  [[ -z "$item" ]] && continue
  echo "[PASS] $item"
done
[[ "$PASS_COUNT" -eq 0 ]] && echo "(none)"

echo
echo "---- WARN ----"
for item in "${WARN_ITEMS[@]-}"; do
  [[ -z "$item" ]] && continue
  echo "[WARN] $item"
done
[[ "$WARN_COUNT" -eq 0 ]] && echo "(none)"

echo
echo "---- FAIL ----"
for item in "${FAIL_ITEMS[@]-}"; do
  [[ -z "$item" ]] && continue
  echo "[FAIL] $item"
done
[[ "$FAIL_COUNT" -eq 0 ]] && echo "(none)"

echo
if [[ "$FAIL_COUNT" -gt 0 ]]; then
  echo "AI Judge M7 stage acceptance result: FAILED ($FAIL_COUNT issue(s))"
  exit 1
fi

echo "AI Judge M7 stage acceptance result: PASSED"
