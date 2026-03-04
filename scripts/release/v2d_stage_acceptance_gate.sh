#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage:
  v2d_stage_acceptance_gate.sh [options]

Options:
  --regression-evidence <path>  Regression evidence env file
                                default: docs/loadtest/evidence/v2d_regression.env
  --load-summary <path>         Pre-prod load summary env file
                                default: docs/loadtest/evidence/v2d_preprod_summary.env
  --report-out <path>           Markdown report output path
                                default: docs/dev_plan/V2-D阶段验收报告-<YYYY-MM-DD>.md
  --root <path>                 Repo root path (default: git top-level or cwd)
  --allow-missing-scenarios     Do not fail when L1/L2/L3/L4/SOAK/SPIKE are incomplete
  -h, --help                    Show this help

Evidence file format (KEY=VALUE):
  Regression evidence keys:
    REGRESSION_CHAT_TEST_DEBATE_MVP_SIGNOFF=pass|fail
    REGRESSION_CHAT_SERVER_NEXTEST=pass|fail
    REGRESSION_NOTIFY_SERVER_NEXTEST=pass|fail
    REGRESSION_LAST_RUN_AT=2026-03-04T04:20:00Z

  Load summary keys:
    LOADTEST_STAGE=preprod
    LOAD_SCENARIOS=L1,L2,L3,L4,SOAK,SPIKE
    L1_RESULT=pass
    L2_RESULT=pass
    L3_RESULT=pass
    L4_RESULT=pass
    SOAK_RESULT=pass
    SPIKE_RESULT=pass
    REALTIME_MESSAGE_SUCCESS_RATE=99.6
    REALTIME_MESSAGE_P95_MS=280
    WS_BROADCAST_P95_MS=900
    PIN_CHAIN_SUCCESS_RATE=99.92
    PIN_CHAIN_P95_MS=420
    AI_JUDGE_P95_SECONDS=240
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

compare_lt() {
  local value="$1"
  local threshold="$2"
  awk -v a="$value" -v b="$threshold" 'BEGIN { exit !(a + 0 < b + 0) }'
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
LOAD_SUMMARY=""
REPORT_OUT=""
STRICT_SCENARIO="true"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --regression-evidence)
      REGRESSION_EVIDENCE="$2"
      shift 2
      ;;
    --load-summary)
      LOAD_SUMMARY="$2"
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
  REGRESSION_EVIDENCE="$ROOT/docs/loadtest/evidence/v2d_regression.env"
fi
if [[ -z "$LOAD_SUMMARY" ]]; then
  LOAD_SUMMARY="$ROOT/docs/loadtest/evidence/v2d_preprod_summary.env"
fi
if [[ -z "$REPORT_OUT" ]]; then
  REPORT_OUT="$ROOT/docs/dev_plan/V2-D阶段验收报告-$(date +%F).md"
fi

mkdir -p "$(dirname "$REPORT_OUT")"

echo "== V2-D stage acceptance gate =="
echo "root: $ROOT"
echo "regression_evidence: $REGRESSION_EVIDENCE"
echo "load_summary: $LOAD_SUMMARY"
echo "report_out: $REPORT_OUT"
echo

if [[ ! -f "$REGRESSION_EVIDENCE" ]]; then
  mark_fail "regression evidence not found: $REGRESSION_EVIDENCE"
fi
if [[ ! -f "$LOAD_SUMMARY" ]]; then
  mark_fail "load summary not found: $LOAD_SUMMARY"
fi

if [[ "$FAIL_COUNT" -eq 0 ]]; then
  regress_keys=(
    "REGRESSION_CHAT_TEST_DEBATE_MVP_SIGNOFF"
    "REGRESSION_CHAT_SERVER_NEXTEST"
    "REGRESSION_NOTIFY_SERVER_NEXTEST"
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

  stage_value="$(to_lower "$(trim "$(read_env_value "LOADTEST_STAGE" "$LOAD_SUMMARY" || true)")")"
  if [[ -z "$stage_value" ]]; then
    mark_fail "load summary missing LOADTEST_STAGE"
  elif [[ "$stage_value" != "preprod" && "$stage_value" != "staging" ]]; then
    mark_warn "LOADTEST_STAGE=$stage_value (expected preprod/staging)"
  else
    mark_pass "LOADTEST_STAGE=$stage_value"
  fi

  required_scenarios=("L1" "L2" "L3" "L4" "SOAK" "SPIKE")
  scenario_csv="$(to_lower "$(read_env_value "LOAD_SCENARIOS" "$LOAD_SUMMARY" || true)")"

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
    scenario_result="$(read_env_value "$scenario_key" "$LOAD_SUMMARY" || true)"
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
    "REALTIME_MESSAGE_SUCCESS_RATE|99.5|ge|实时消息成功率 >= 99.5"
    "REALTIME_MESSAGE_P95_MS|300|lt|实时消息 P95 < 300ms"
    "WS_BROADCAST_P95_MS|1000|lt|WS 广播 P95 < 1000ms"
    "PIN_CHAIN_SUCCESS_RATE|99.9|ge|置顶链路成功率 >= 99.9"
    "PIN_CHAIN_P95_MS|500|lt|置顶链路 P95 < 500ms"
    "AI_JUDGE_P95_SECONDS|300|le|AI 判决 P95 <= 300s"
  )

  for spec in "${threshold_checks[@]}"; do
    IFS='|' read -r key threshold op label <<<"$spec"
    value="$(read_env_value "$key" "$LOAD_SUMMARY" || true)"
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
      lt)
        if compare_lt "$value" "$threshold"; then
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
fi

{
  echo "# V2-D 阶段验收报告"
  echo
  echo "- 生成时间: $(date '+%Y-%m-%d %H:%M:%S %z')"
  echo "- 回归证据: $REGRESSION_EVIDENCE"
  echo "- 压测汇总: $LOAD_SUMMARY"
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
  echo "V2-D stage acceptance result: FAILED ($FAIL_COUNT issue(s))"
  exit 1
fi

echo "V2-D stage acceptance result: PASSED"
