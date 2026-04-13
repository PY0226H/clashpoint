#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/ai_judge_calibration_prep.sh"

if [[ ! -x "$SCRIPT" ]]; then
  chmod +x "$SCRIPT"
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

expect_contains() {
  local name="$1"
  local pattern="$2"
  local file="$3"
  if grep -Fq -- "$pattern" "$file"; then
    echo "[PASS] $name"
    return
  fi
  echo "[FAIL] $name: missing pattern '$pattern'"
  echo "--- output ---"
  cat "$file"
  exit 1
}

write_validated_file() {
  local file="$1"
  shift
  {
    printf 'CALIBRATION_STATUS=validated\n'
    while [[ $# -gt 0 ]]; do
      printf '%s\n' "$1"
      shift
    done
  } >"$file"
}

WORK_BOOTSTRAP="$TMP_DIR/bootstrap-root"
mkdir -p "$WORK_BOOTSTRAP/docs/loadtest/evidence"

BOOT_STDOUT="$TMP_DIR/bootstrap.stdout"
BOOT_JSON="$TMP_DIR/bootstrap.summary.json"
BOOT_MD="$TMP_DIR/bootstrap.summary.md"

bash "$SCRIPT" \
  --root "$WORK_BOOTSTRAP" \
  --emit-json "$BOOT_JSON" \
  --emit-md "$BOOT_MD" >"$BOOT_STDOUT"

expect_contains "bootstrap status pending" "ai_judge_calibration_status: pending_real_data" "$BOOT_STDOUT"
expect_contains "bootstrap json pending status" "\"status\": \"pending_real_data\"" "$BOOT_JSON"
expect_contains "bootstrap markdown table" "## Track Status" "$BOOT_MD"
expect_contains "bootstrap latency template generated" "CALIBRATION_STATUS=template" "$WORK_BOOTSTRAP/docs/loadtest/evidence/ai_judge_p5_latency_baseline.env"

WORK_VALIDATED="$TMP_DIR/validated-root"
EVIDENCE_DIR="$WORK_VALIDATED/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_DIR"

write_validated_file "$EVIDENCE_DIR/ai_judge_p5_latency_baseline.env" \
  "WINDOW_FROM=2026-04-01T00:00:00Z" \
  "WINDOW_TO=2026-04-07T00:00:00Z" \
  "SAMPLE_SIZE=1200" \
  "P95_MS=850" \
  "P99_MS=1600"

write_validated_file "$EVIDENCE_DIR/ai_judge_p5_cost_baseline.env" \
  "WINDOW_FROM=2026-04-01T00:00:00Z" \
  "WINDOW_TO=2026-04-07T00:00:00Z" \
  "TOKEN_INPUT_TOTAL=1000000" \
  "TOKEN_OUTPUT_TOTAL=350000" \
  "COST_USD_TOTAL=88.12" \
  "COST_USD_PER_1K=0.065"

write_validated_file "$EVIDENCE_DIR/ai_judge_p5_fairness_benchmark.env" \
  "WINDOW_FROM=2026-04-01T00:00:00Z" \
  "WINDOW_TO=2026-04-07T00:00:00Z" \
  "SAMPLE_SIZE=900" \
  "DRAW_RATE=0.18" \
  "SIDE_BIAS_DELTA=0.03" \
  "APPEAL_OVERTURN_RATE=0.06"

write_validated_file "$EVIDENCE_DIR/ai_judge_p5_fault_drill.env" \
  "DRILL_RUN_AT=2026-04-12T12:00:00Z" \
  "CALLBACK_FAILURE_RECOVERY_PASS=true" \
  "REPLAY_CONSISTENCY_PASS=true" \
  "AUDIT_ALERT_DELIVERY_PASS=true"

write_validated_file "$EVIDENCE_DIR/ai_judge_p5_trust_attestation.env" \
  "TRACE_HASH_COVERAGE=1.00" \
  "COMMITMENT_COVERAGE=1.00" \
  "ATTESTATION_GAP=0"

VAL_STDOUT="$TMP_DIR/validated.stdout"
VAL_JSON="$TMP_DIR/validated.summary.json"
VAL_MD="$TMP_DIR/validated.summary.md"

bash "$SCRIPT" \
  --root "$WORK_VALIDATED" \
  --no-bootstrap-templates \
  --emit-json "$VAL_JSON" \
  --emit-md "$VAL_MD" >"$VAL_STDOUT"

expect_contains "validated status pass" "ai_judge_calibration_status: pass" "$VAL_STDOUT"
expect_contains "validated json pass status" "\"status\": \"pass\"" "$VAL_JSON"
expect_contains "validated json pass count" "\"pass_total\": 5" "$VAL_JSON"
expect_contains "validated markdown pass row" "| Fairness Benchmark | pass |" "$VAL_MD"

echo "all ai-judge calibration prep tests passed"
