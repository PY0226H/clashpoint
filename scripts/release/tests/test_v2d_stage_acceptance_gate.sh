#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/release/v2d_stage_acceptance_gate.sh"

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
REPORT_OK="$TMP_DIR/report.ok.md"

cat >"$REG_OK" <<'REGEOF'
REGRESSION_CHAT_TEST_DEBATE_MVP_SIGNOFF=pass
REGRESSION_CHAT_SERVER_NEXTEST=pass
REGRESSION_NOTIFY_SERVER_NEXTEST=pass
REGRESSION_LAST_RUN_AT=2026-03-04T12:00:00Z
REGEOF

cat >"$LOAD_OK" <<'LOADEOF'
LOADTEST_STAGE=preprod
LOAD_SCENARIOS=L1,L2,L3,L4,SOAK,SPIKE
L1_RESULT=pass
L2_RESULT=pass
L3_RESULT=pass
L4_RESULT=pass
SOAK_RESULT=pass
SPIKE_RESULT=pass
REALTIME_MESSAGE_SUCCESS_RATE=99.7
REALTIME_MESSAGE_P95_MS=280
WS_BROADCAST_P95_MS=920
PIN_CHAIN_SUCCESS_RATE=99.93
PIN_CHAIN_P95_MS=450
AI_JUDGE_P95_SECONDS=260
LOADEOF

expect_pass "all thresholds and evidence should pass" \
  "$SCRIPT" \
  --root "$ROOT" \
  --regression-evidence "$REG_OK" \
  --load-summary "$LOAD_OK" \
  --report-out "$REPORT_OK"

if [[ ! -f "$REPORT_OK" ]]; then
  echo "[FAIL] pass case should generate report"
  exit 1
fi

LOAD_BAD="$TMP_DIR/load.bad.env"
REPORT_BAD="$TMP_DIR/report.bad.md"

cat >"$LOAD_BAD" <<'LOADEOF'
LOADTEST_STAGE=preprod
LOAD_SCENARIOS=L1,L2
L1_RESULT=pass
L2_RESULT=fail
REALTIME_MESSAGE_SUCCESS_RATE=98.8
REALTIME_MESSAGE_P95_MS=350
WS_BROADCAST_P95_MS=1100
PIN_CHAIN_SUCCESS_RATE=99.1
PIN_CHAIN_P95_MS=560
AI_JUDGE_P95_SECONDS=340
LOADEOF

expect_fail "threshold breach should fail" \
  "$SCRIPT" \
  --root "$ROOT" \
  --regression-evidence "$REG_OK" \
  --load-summary "$LOAD_BAD" \
  --report-out "$REPORT_BAD"

if [[ ! -f "$REPORT_BAD" ]]; then
  echo "[FAIL] fail case should still generate report"
  exit 1
fi

echo "all v2d acceptance gate tests passed"
