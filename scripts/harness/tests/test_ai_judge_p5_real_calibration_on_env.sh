#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/ai_judge_p5_real_calibration_on_env.sh"

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

write_real_validated_file() {
  local file="$1"
  shift
  {
    printf 'CALIBRATION_STATUS=validated\n'
    printf 'REAL_ENV_EVIDENCE=https://example.com/evidence/%s\n' "$(basename "$file")"
    printf 'CALIBRATED_AT=2026-04-13T20:00:00Z\n'
    printf 'CALIBRATED_BY=qa-bot\n'
    printf 'DATASET_REF=dataset-2026-04-13\n'
    while [[ $# -gt 0 ]]; do
      printf '%s\n' "$1"
      shift
    done
  } >"$file"
}

write_local_validated_file() {
  local file="$1"
  shift
  {
    printf 'CALIBRATION_STATUS=validated\n'
    printf 'LOCAL_ENV_EVIDENCE=file://local/%s\n' "$(basename "$file")"
    printf 'LOCAL_ENV_PROFILE=macbookpro2021_m1pro_16gb_10core\n'
    printf 'CALIBRATED_AT=2026-04-13T21:00:00Z\n'
    printf 'CALIBRATED_BY=local-dev-bot\n'
    while [[ $# -gt 0 ]]; do
      printf '%s\n' "$1"
      shift
    done
  } >"$file"
}

# 场景1：真实环境未就绪 -> env_blocked
WORK_BLOCKED="$TMP_DIR/blocked-root"
EVIDENCE_BLOCKED="$WORK_BLOCKED/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_BLOCKED"

write_real_validated_file "$EVIDENCE_BLOCKED/ai_judge_p5_latency_baseline.env" \
  "WINDOW_FROM=2026-04-01T00:00:00Z" \
  "WINDOW_TO=2026-04-07T00:00:00Z" \
  "SAMPLE_SIZE=1200" \
  "P95_MS=850" \
  "P99_MS=1600"

BLOCKED_STDOUT="$TMP_DIR/blocked.stdout"
BLOCKED_JSON="$TMP_DIR/blocked.summary.json"
BLOCKED_MD="$TMP_DIR/blocked.summary.md"

bash "$SCRIPT" \
  --root "$WORK_BLOCKED" \
  --emit-json "$BLOCKED_JSON" \
  --emit-md "$BLOCKED_MD" >"$BLOCKED_STDOUT"

expect_contains "blocked status" "ai_judge_p5_real_calibration_status: env_blocked" "$BLOCKED_STDOUT"
expect_contains "blocked env ready false" "environment_ready: false" "$BLOCKED_STDOUT"
expect_contains "blocked json env false" '"environment_ready": false' "$BLOCKED_JSON"

# 场景2：真实环境就绪 + 五轨道证据完整 -> pass
WORK_PASS="$TMP_DIR/pass-root"
EVIDENCE_PASS="$WORK_PASS/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_PASS"

cat >"$EVIDENCE_PASS/ai_judge_p5_real_env.env" <<'ENV'
REAL_CALIBRATION_ENV_READY=true
ENV

write_real_validated_file "$EVIDENCE_PASS/ai_judge_p5_latency_baseline.env" \
  "WINDOW_FROM=2026-04-01T00:00:00Z" \
  "WINDOW_TO=2026-04-07T00:00:00Z" \
  "SAMPLE_SIZE=1200" \
  "P95_MS=850" \
  "P99_MS=1600"

write_real_validated_file "$EVIDENCE_PASS/ai_judge_p5_cost_baseline.env" \
  "WINDOW_FROM=2026-04-01T00:00:00Z" \
  "WINDOW_TO=2026-04-07T00:00:00Z" \
  "TOKEN_INPUT_TOTAL=1000000" \
  "TOKEN_OUTPUT_TOTAL=350000" \
  "COST_USD_TOTAL=88.12" \
  "COST_USD_PER_1K=0.065"

write_real_validated_file "$EVIDENCE_PASS/ai_judge_p5_fairness_benchmark.env" \
  "WINDOW_FROM=2026-04-01T00:00:00Z" \
  "WINDOW_TO=2026-04-07T00:00:00Z" \
  "SAMPLE_SIZE=900" \
  "DRAW_RATE=0.18" \
  "SIDE_BIAS_DELTA=0.03" \
  "APPEAL_OVERTURN_RATE=0.06"

write_real_validated_file "$EVIDENCE_PASS/ai_judge_p5_fault_drill.env" \
  "DRILL_RUN_AT=2026-04-12T12:00:00Z" \
  "CALLBACK_FAILURE_RECOVERY_PASS=true" \
  "REPLAY_CONSISTENCY_PASS=true" \
  "AUDIT_ALERT_DELIVERY_PASS=true"

write_real_validated_file "$EVIDENCE_PASS/ai_judge_p5_trust_attestation.env" \
  "TRACE_HASH_COVERAGE=1.00" \
  "COMMITMENT_COVERAGE=1.00" \
  "ATTESTATION_GAP=0"

PASS_STDOUT="$TMP_DIR/pass.stdout"
PASS_JSON="$TMP_DIR/pass.summary.json"
PASS_MD="$TMP_DIR/pass.summary.md"

bash "$SCRIPT" \
  --root "$WORK_PASS" \
  --emit-json "$PASS_JSON" \
  --emit-md "$PASS_MD" >"$PASS_STDOUT"

expect_contains "pass status" "ai_judge_p5_real_calibration_status: pass" "$PASS_STDOUT"
expect_contains "pass env ready true" "environment_ready: true" "$PASS_STDOUT"
expect_contains "pass json pass count" '"pass_total": 5' "$PASS_JSON"
expect_contains "pass markdown row" "| Fairness Benchmark | pass |" "$PASS_MD"

# 场景3：真实环境就绪但real证据键缺失 -> pending_real_data
WORK_PENDING="$TMP_DIR/pending-root"
EVIDENCE_PENDING="$WORK_PENDING/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_PENDING"

cat >"$EVIDENCE_PENDING/ai_judge_p5_real_env.env" <<'ENV'
REAL_CALIBRATION_ENV_READY=true
ENV

write_real_validated_file "$EVIDENCE_PENDING/ai_judge_p5_latency_baseline.env" \
  "WINDOW_FROM=2026-04-01T00:00:00Z" \
  "WINDOW_TO=2026-04-07T00:00:00Z" \
  "SAMPLE_SIZE=1200" \
  "P95_MS=850" \
  "P99_MS=1600"

write_real_validated_file "$EVIDENCE_PENDING/ai_judge_p5_cost_baseline.env" \
  "WINDOW_FROM=2026-04-01T00:00:00Z" \
  "WINDOW_TO=2026-04-07T00:00:00Z" \
  "TOKEN_INPUT_TOTAL=1000000" \
  "TOKEN_OUTPUT_TOTAL=350000" \
  "COST_USD_TOTAL=88.12" \
  "COST_USD_PER_1K=0.065"

write_real_validated_file "$EVIDENCE_PENDING/ai_judge_p5_fairness_benchmark.env" \
  "WINDOW_FROM=2026-04-01T00:00:00Z" \
  "WINDOW_TO=2026-04-07T00:00:00Z" \
  "SAMPLE_SIZE=900" \
  "DRAW_RATE=0.18" \
  "SIDE_BIAS_DELTA=0.03" \
  "APPEAL_OVERTURN_RATE=0.06"

write_real_validated_file "$EVIDENCE_PENDING/ai_judge_p5_fault_drill.env" \
  "DRILL_RUN_AT=2026-04-12T12:00:00Z" \
  "CALLBACK_FAILURE_RECOVERY_PASS=true" \
  "REPLAY_CONSISTENCY_PASS=true" \
  "AUDIT_ALERT_DELIVERY_PASS=true"

write_real_validated_file "$EVIDENCE_PENDING/ai_judge_p5_trust_attestation.env" \
  "TRACE_HASH_COVERAGE=1.00" \
  "COMMITMENT_COVERAGE=1.00" \
  "ATTESTATION_GAP=0"

# 删除一个 real 证据键，制造 pending
sed -i '' '/^REAL_ENV_EVIDENCE=/d' "$EVIDENCE_PENDING/ai_judge_p5_latency_baseline.env"

PENDING_STDOUT="$TMP_DIR/pending.stdout"
PENDING_JSON="$TMP_DIR/pending.summary.json"
PENDING_MD="$TMP_DIR/pending.summary.md"

bash "$SCRIPT" \
  --root "$WORK_PENDING" \
  --emit-json "$PENDING_JSON" \
  --emit-md "$PENDING_MD" >"$PENDING_STDOUT"

expect_contains "pending status" "ai_judge_p5_real_calibration_status: pending_real_data" "$PENDING_STDOUT"
expect_contains "pending json missing real key" '"missing_real_keys":"REAL_ENV_EVIDENCE"' "$PENDING_JSON"
expect_contains "pending md note" "REAL_ENV_EVIDENCE" "$PENDING_MD"

# 场景4：开启 local reference，且本机参考证据完整 -> local_reference_pass
WORK_LOCAL_PASS="$TMP_DIR/local-pass-root"
EVIDENCE_LOCAL_PASS="$WORK_LOCAL_PASS/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_LOCAL_PASS"

cat >"$EVIDENCE_LOCAL_PASS/ai_judge_p5_real_env.env" <<'ENV'
LOCAL_REFERENCE_ENV_READY=true
CALIBRATION_ENV_MODE=local_reference
ENV

write_local_validated_file "$EVIDENCE_LOCAL_PASS/ai_judge_p5_latency_baseline.env" \
  "WINDOW_FROM=2026-04-01T00:00:00Z" \
  "WINDOW_TO=2026-04-07T00:00:00Z" \
  "SAMPLE_SIZE=400" \
  "P95_MS=920" \
  "P99_MS=1700"

write_local_validated_file "$EVIDENCE_LOCAL_PASS/ai_judge_p5_cost_baseline.env" \
  "WINDOW_FROM=2026-04-01T00:00:00Z" \
  "WINDOW_TO=2026-04-07T00:00:00Z" \
  "TOKEN_INPUT_TOTAL=220000" \
  "TOKEN_OUTPUT_TOTAL=82000" \
  "COST_USD_TOTAL=20.10" \
  "COST_USD_PER_1K=0.067"

write_local_validated_file "$EVIDENCE_LOCAL_PASS/ai_judge_p5_fairness_benchmark.env" \
  "WINDOW_FROM=2026-04-01T00:00:00Z" \
  "WINDOW_TO=2026-04-07T00:00:00Z" \
  "SAMPLE_SIZE=360" \
  "DRAW_RATE=0.21" \
  "SIDE_BIAS_DELTA=0.05" \
  "APPEAL_OVERTURN_RATE=0.08"

write_local_validated_file "$EVIDENCE_LOCAL_PASS/ai_judge_p5_fault_drill.env" \
  "DRILL_RUN_AT=2026-04-13T10:00:00Z" \
  "CALLBACK_FAILURE_RECOVERY_PASS=true" \
  "REPLAY_CONSISTENCY_PASS=true" \
  "AUDIT_ALERT_DELIVERY_PASS=true"

write_local_validated_file "$EVIDENCE_LOCAL_PASS/ai_judge_p5_trust_attestation.env" \
  "TRACE_HASH_COVERAGE=1.00" \
  "COMMITMENT_COVERAGE=1.00" \
  "ATTESTATION_GAP=0"

LOCAL_PASS_STDOUT="$TMP_DIR/local_pass.stdout"
LOCAL_PASS_JSON="$TMP_DIR/local_pass.summary.json"
LOCAL_PASS_MD="$TMP_DIR/local_pass.summary.md"

bash "$SCRIPT" \
  --root "$WORK_LOCAL_PASS" \
  --allow-local-reference \
  --emit-json "$LOCAL_PASS_JSON" \
  --emit-md "$LOCAL_PASS_MD" >"$LOCAL_PASS_STDOUT"

expect_contains "local pass status" "ai_judge_p5_real_calibration_status: local_reference_pass" "$LOCAL_PASS_STDOUT"
expect_contains "local pass mode" "environment_mode: local_reference" "$LOCAL_PASS_STDOUT"
expect_contains "local pass enable flag" "local_reference_enabled: true" "$LOCAL_PASS_STDOUT"
expect_contains "local pass json mode" '"environment_mode": "local_reference"' "$LOCAL_PASS_JSON"
expect_contains "local pass json count" '"local_reference_pass_total": 5' "$LOCAL_PASS_JSON"
expect_contains "local pass md row" "| Fairness Benchmark | local_reference_pass |" "$LOCAL_PASS_MD"

# 场景5：开启 local reference 但缺本机参考键 -> local_reference_pending
WORK_LOCAL_PENDING="$TMP_DIR/local-pending-root"
EVIDENCE_LOCAL_PENDING="$WORK_LOCAL_PENDING/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_LOCAL_PENDING"

cat >"$EVIDENCE_LOCAL_PENDING/ai_judge_p5_real_env.env" <<'ENV'
LOCAL_REFERENCE_ENV_READY=true
CALIBRATION_ENV_MODE=local_reference
ENV

write_local_validated_file "$EVIDENCE_LOCAL_PENDING/ai_judge_p5_latency_baseline.env" \
  "WINDOW_FROM=2026-04-01T00:00:00Z" \
  "WINDOW_TO=2026-04-07T00:00:00Z" \
  "SAMPLE_SIZE=400" \
  "P95_MS=920" \
  "P99_MS=1700"

write_local_validated_file "$EVIDENCE_LOCAL_PENDING/ai_judge_p5_cost_baseline.env" \
  "WINDOW_FROM=2026-04-01T00:00:00Z" \
  "WINDOW_TO=2026-04-07T00:00:00Z" \
  "TOKEN_INPUT_TOTAL=220000" \
  "TOKEN_OUTPUT_TOTAL=82000" \
  "COST_USD_TOTAL=20.10" \
  "COST_USD_PER_1K=0.067"

write_local_validated_file "$EVIDENCE_LOCAL_PENDING/ai_judge_p5_fairness_benchmark.env" \
  "WINDOW_FROM=2026-04-01T00:00:00Z" \
  "WINDOW_TO=2026-04-07T00:00:00Z" \
  "SAMPLE_SIZE=360" \
  "DRAW_RATE=0.21" \
  "SIDE_BIAS_DELTA=0.05" \
  "APPEAL_OVERTURN_RATE=0.08"

write_local_validated_file "$EVIDENCE_LOCAL_PENDING/ai_judge_p5_fault_drill.env" \
  "DRILL_RUN_AT=2026-04-13T10:00:00Z" \
  "CALLBACK_FAILURE_RECOVERY_PASS=true" \
  "REPLAY_CONSISTENCY_PASS=true" \
  "AUDIT_ALERT_DELIVERY_PASS=true"

write_local_validated_file "$EVIDENCE_LOCAL_PENDING/ai_judge_p5_trust_attestation.env" \
  "TRACE_HASH_COVERAGE=1.00" \
  "COMMITMENT_COVERAGE=1.00" \
  "ATTESTATION_GAP=0"

# 删除一个 local 参考键，制造 pending
sed -i '' '/^LOCAL_ENV_PROFILE=/d' "$EVIDENCE_LOCAL_PENDING/ai_judge_p5_latency_baseline.env"

LOCAL_PENDING_STDOUT="$TMP_DIR/local_pending.stdout"
LOCAL_PENDING_JSON="$TMP_DIR/local_pending.summary.json"
LOCAL_PENDING_MD="$TMP_DIR/local_pending.summary.md"

bash "$SCRIPT" \
  --root "$WORK_LOCAL_PENDING" \
  --allow-local-reference \
  --emit-json "$LOCAL_PENDING_JSON" \
  --emit-md "$LOCAL_PENDING_MD" >"$LOCAL_PENDING_STDOUT"

expect_contains "local pending status" "ai_judge_p5_real_calibration_status: local_reference_pending" "$LOCAL_PENDING_STDOUT"
expect_contains "local pending missing key json" '"missing_local_keys":"LOCAL_ENV_PROFILE"' "$LOCAL_PENDING_JSON"
expect_contains "local pending md note" "LOCAL_ENV_PROFILE" "$LOCAL_PENDING_MD"

echo "all ai-judge p5 real calibration on env tests passed"
