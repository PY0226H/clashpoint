#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/release/ai_judge_m7_stage_acceptance_gate.sh"

if [[ ! -x "$SCRIPT" ]]; then
  chmod +x "$SCRIPT"
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

expect_fail() {
  local name="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "[FAIL] $name: expected failure but passed"
    exit 1
  fi
  echo "[PASS] $name"
}

expect_pass() {
  local name="$1"
  shift
  if "$@" >/dev/null 2>&1; then
    echo "[PASS] $name"
    return
  fi
  echo "[FAIL] $name: expected pass but failed"
  exit 1
}

REG_OK="$TMP_DIR/reg.ok.env"
LOAD_OK="$TMP_DIR/load.ok.env"
FAULT_OK="$TMP_DIR/fault.ok.env"
REPORT_OK="$TMP_DIR/report.ok.md"

cat >"$REG_OK" <<'REGEOF'
REGRESSION_AI_JUDGE_M7_ACCEPTANCE=pass
REGRESSION_AI_JUDGE_M7_GATE=pass
REGRESSION_AI_JUDGE_UNITTEST_ALL=pass
REGRESSION_LAST_RUN_AT=2026-03-05T02:20:00Z
REGEOF

cat >"$LOAD_OK" <<'LOADEOF'
LOADTEST_STAGE=preprod
LOAD_SCENARIOS=SOAK,SPIKE
SOAK_RESULT=pass
SPIKE_RESULT=pass
AI_JUDGE_SUCCESS_RATE=98.6
AI_JUDGE_P95_SECONDS=245
LOADEOF

cat >"$FAULT_OK" <<'FAULTEOF'
FAULT_SCENARIOS=provider_timeout,provider_overload,rag_unavailable,model_overload,consistency_conflict
FI_PROVIDER_TIMEOUT=pass
FI_PROVIDER_OVERLOAD=pass
FI_RAG_UNAVAILABLE=pass
FI_MODEL_OVERLOAD=pass
FI_CONSISTENCY_CONFLICT=pass
FI_LAST_RUN_AT=2026-03-05T03:00:00Z
FAULTEOF

expect_pass "all m7 acceptance evidence should pass" \
  "$SCRIPT" \
  --root "$ROOT" \
  --regression-evidence "$REG_OK" \
  --preprod-summary "$LOAD_OK" \
  --fault-matrix "$FAULT_OK" \
  --report-out "$REPORT_OK"

if [[ ! -f "$REPORT_OK" ]]; then
  echo "[FAIL] pass case should generate report"
  exit 1
fi

LOAD_BAD="$TMP_DIR/load.bad.env"
FAULT_BAD="$TMP_DIR/fault.bad.env"
REPORT_BAD="$TMP_DIR/report.bad.md"

cat >"$LOAD_BAD" <<'LOADEOF'
LOADTEST_STAGE=preprod
LOAD_SCENARIOS=SOAK,SPIKE
SOAK_RESULT=pass
SPIKE_RESULT=fail
AI_JUDGE_SUCCESS_RATE=96.4
AI_JUDGE_P95_SECONDS=341
LOADEOF

cat >"$FAULT_BAD" <<'FAULTEOF'
FAULT_SCENARIOS=provider_timeout,rag_unavailable
FI_PROVIDER_TIMEOUT=pass
FI_PROVIDER_OVERLOAD=fail
FI_RAG_UNAVAILABLE=pass
FI_MODEL_OVERLOAD=fail
FI_CONSISTENCY_CONFLICT=pass
FAULTEOF

expect_fail "metric and fault matrix breach should fail" \
  "$SCRIPT" \
  --root "$ROOT" \
  --regression-evidence "$REG_OK" \
  --preprod-summary "$LOAD_BAD" \
  --fault-matrix "$FAULT_BAD" \
  --report-out "$REPORT_BAD"

if [[ ! -f "$REPORT_BAD" ]]; then
  echo "[FAIL] fail case should still generate report"
  exit 1
fi

echo "all ai_judge m7 acceptance gate tests passed"
