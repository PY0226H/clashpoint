#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/ai_judge_runtime_sla_freeze.sh"

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

write_local_latency_env() {
  local file="$1"
  local p95="$2"
  local p99="$3"
  cat >"$file" <<EOF
CALIBRATION_STATUS=validated
WINDOW_FROM=2026-04-12T00:00:00Z
WINDOW_TO=2026-04-14T00:00:00Z
SAMPLE_SIZE=720
P95_MS=$p95
P99_MS=$p99
LOCAL_ENV_EVIDENCE=file://local/latency
LOCAL_ENV_PROFILE=macbookpro2021_m1pro_16gb_10core
CALIBRATED_AT=2026-04-14T00:18:00Z
CALIBRATED_BY=local-dev-bot
TRACK_ID=latency_baseline
EOF
}

write_real_latency_env() {
  local file="$1"
  local p95="$2"
  local p99="$3"
  cat >"$file" <<EOF
CALIBRATION_STATUS=validated
WINDOW_FROM=2026-04-12T00:00:00Z
WINDOW_TO=2026-04-14T00:00:00Z
SAMPLE_SIZE=1320
P95_MS=$p95
P99_MS=$p99
REAL_ENV_EVIDENCE=https://example.com/runtime-latency-report
CALIBRATED_AT=2026-04-14T10:00:00Z
CALIBRATED_BY=qa-bot
DATASET_REF=runtime-latency-dataset-2026-04-14
TRACK_ID=latency_baseline
EOF
}

write_local_fault_env() {
  local file="$1"
  local callback_ok="$2"
  local replay_ok="$3"
  local audit_ok="$4"
  cat >"$file" <<EOF
CALIBRATION_STATUS=validated
DRILL_RUN_AT=2026-04-14T00:18:00Z
CALLBACK_FAILURE_RECOVERY_PASS=$callback_ok
REPLAY_CONSISTENCY_PASS=$replay_ok
AUDIT_ALERT_DELIVERY_PASS=$audit_ok
LOCAL_ENV_EVIDENCE=file://local/fault
LOCAL_ENV_PROFILE=macbookpro2021_m1pro_16gb_10core
CALIBRATED_AT=2026-04-14T00:18:00Z
CALIBRATED_BY=local-dev-bot
TRACK_ID=fault_drill
EOF
}

write_real_fault_env() {
  local file="$1"
  local callback_ok="$2"
  local replay_ok="$3"
  local audit_ok="$4"
  cat >"$file" <<EOF
CALIBRATION_STATUS=validated
DRILL_RUN_AT=2026-04-14T09:30:00Z
CALLBACK_FAILURE_RECOVERY_PASS=$callback_ok
REPLAY_CONSISTENCY_PASS=$replay_ok
AUDIT_ALERT_DELIVERY_PASS=$audit_ok
REAL_ENV_EVIDENCE=https://example.com/runtime-fault-report
CALIBRATED_AT=2026-04-14T10:00:00Z
CALIBRATED_BY=qa-bot
DATASET_REF=runtime-fault-dataset-2026-04-14
TRACK_ID=fault_drill
EOF
}

write_local_trust_env() {
  local file="$1"
  local trace_cov="$2"
  local commitment_cov="$3"
  local gap="$4"
  cat >"$file" <<EOF
CALIBRATION_STATUS=validated
TRACE_HASH_COVERAGE=$trace_cov
COMMITMENT_COVERAGE=$commitment_cov
ATTESTATION_GAP=$gap
LOCAL_ENV_EVIDENCE=file://local/trust
LOCAL_ENV_PROFILE=macbookpro2021_m1pro_16gb_10core
CALIBRATED_AT=2026-04-14T00:18:00Z
CALIBRATED_BY=local-dev-bot
TRACK_ID=trust_attestation
EOF
}

write_real_trust_env() {
  local file="$1"
  local trace_cov="$2"
  local commitment_cov="$3"
  local gap="$4"
  cat >"$file" <<EOF
CALIBRATION_STATUS=validated
TRACE_HASH_COVERAGE=$trace_cov
COMMITMENT_COVERAGE=$commitment_cov
ATTESTATION_GAP=$gap
REAL_ENV_EVIDENCE=https://example.com/runtime-trust-report
CALIBRATED_AT=2026-04-14T10:00:00Z
CALIBRATED_BY=qa-bot
DATASET_REF=runtime-trust-dataset-2026-04-14
TRACK_ID=trust_attestation
EOF
}

# 场景1：环境未就绪 -> env_blocked
WORK_BLOCKED="$TMP_DIR/blocked"
mkdir -p "$WORK_BLOCKED/docs/loadtest/evidence" "$WORK_BLOCKED/docs/dev_plan" "$WORK_BLOCKED/artifacts/harness"
write_local_latency_env "$WORK_BLOCKED/docs/loadtest/evidence/ai_judge_p5_latency_baseline.env" "920" "1780"
write_local_fault_env "$WORK_BLOCKED/docs/loadtest/evidence/ai_judge_p5_fault_drill.env" "true" "true" "true"
write_local_trust_env "$WORK_BLOCKED/docs/loadtest/evidence/ai_judge_p5_trust_attestation.env" "1.00" "0.99" "0"

BLOCKED_STDOUT="$TMP_DIR/blocked.stdout"
bash "$SCRIPT" --root "$WORK_BLOCKED" >"$BLOCKED_STDOUT"
expect_contains "blocked status" "ai_judge_runtime_sla_freeze_status: env_blocked" "$BLOCKED_STDOUT"
expect_contains "blocked mode" "environment_mode: blocked" "$BLOCKED_STDOUT"

# 场景2：local reference 就绪并达标 -> local_reference_frozen
WORK_LOCAL="$TMP_DIR/local"
mkdir -p "$WORK_LOCAL/docs/loadtest/evidence" "$WORK_LOCAL/docs/dev_plan" "$WORK_LOCAL/artifacts/harness"
cat >"$WORK_LOCAL/docs/loadtest/evidence/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=false
LOCAL_REFERENCE_ENV_READY=true
CALIBRATION_ENV_MODE=local_reference
EOF
write_local_latency_env "$WORK_LOCAL/docs/loadtest/evidence/ai_judge_p5_latency_baseline.env" "920" "1780"
write_local_fault_env "$WORK_LOCAL/docs/loadtest/evidence/ai_judge_p5_fault_drill.env" "true" "true" "true"
write_local_trust_env "$WORK_LOCAL/docs/loadtest/evidence/ai_judge_p5_trust_attestation.env" "1.00" "0.99" "0"

LOCAL_STDOUT="$TMP_DIR/local.stdout"
LOCAL_ENV_OUT="$TMP_DIR/local.runtime_sla.env"
bash "$SCRIPT" \
  --root "$WORK_LOCAL" \
  --allow-local-reference \
  --output-env "$LOCAL_ENV_OUT" >"$LOCAL_STDOUT"
expect_contains "local status" "ai_judge_runtime_sla_freeze_status: local_reference_frozen" "$LOCAL_STDOUT"
expect_contains "local mode" "environment_mode: local_reference" "$LOCAL_STDOUT"
expect_contains "local accepted" "THRESHOLD_DECISION=accepted" "$LOCAL_ENV_OUT"
expect_contains "local reconfirm true" "NEEDS_REAL_ENV_RECONFIRM=true" "$LOCAL_ENV_OUT"
expect_contains "local p95 ok" "COMPLIANCE_P95_MS=true" "$LOCAL_ENV_OUT"

# 场景3：real 环境且达标 -> pass
WORK_REAL_PASS="$TMP_DIR/real-pass"
mkdir -p "$WORK_REAL_PASS/docs/loadtest/evidence" "$WORK_REAL_PASS/docs/dev_plan" "$WORK_REAL_PASS/artifacts/harness"
cat >"$WORK_REAL_PASS/docs/loadtest/evidence/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
EOF
write_real_latency_env "$WORK_REAL_PASS/docs/loadtest/evidence/ai_judge_p5_latency_baseline.env" "980" "1860"
write_real_fault_env "$WORK_REAL_PASS/docs/loadtest/evidence/ai_judge_p5_fault_drill.env" "true" "true" "true"
write_real_trust_env "$WORK_REAL_PASS/docs/loadtest/evidence/ai_judge_p5_trust_attestation.env" "0.995" "0.985" "0.003"

REAL_PASS_STDOUT="$TMP_DIR/real-pass.stdout"
REAL_PASS_ENV_OUT="$TMP_DIR/real-pass.runtime_sla.env"
bash "$SCRIPT" \
  --root "$WORK_REAL_PASS" \
  --output-env "$REAL_PASS_ENV_OUT" >"$REAL_PASS_STDOUT"
expect_contains "real pass status" "ai_judge_runtime_sla_freeze_status: pass" "$REAL_PASS_STDOUT"
expect_contains "real pass mode" "environment_mode: real" "$REAL_PASS_STDOUT"
expect_contains "real pass accepted" "THRESHOLD_DECISION=accepted" "$REAL_PASS_ENV_OUT"
expect_contains "real pass reconfirm false" "NEEDS_REAL_ENV_RECONFIRM=false" "$REAL_PASS_ENV_OUT"

# 场景4：real 环境阈值超限 -> threshold_violation
WORK_REAL_VIOLATION="$TMP_DIR/real-violation"
mkdir -p "$WORK_REAL_VIOLATION/docs/loadtest/evidence" "$WORK_REAL_VIOLATION/docs/dev_plan" "$WORK_REAL_VIOLATION/artifacts/harness"
cat >"$WORK_REAL_VIOLATION/docs/loadtest/evidence/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
EOF
write_real_latency_env "$WORK_REAL_VIOLATION/docs/loadtest/evidence/ai_judge_p5_latency_baseline.env" "1600" "2900"
write_real_fault_env "$WORK_REAL_VIOLATION/docs/loadtest/evidence/ai_judge_p5_fault_drill.env" "true" "false" "true"
write_real_trust_env "$WORK_REAL_VIOLATION/docs/loadtest/evidence/ai_judge_p5_trust_attestation.env" "0.90" "0.90" "0.12"

REAL_VIOLATION_STDOUT="$TMP_DIR/real-violation.stdout"
REAL_VIOLATION_ENV_OUT="$TMP_DIR/real-violation.runtime_sla.env"
bash "$SCRIPT" \
  --root "$WORK_REAL_VIOLATION" \
  --output-env "$REAL_VIOLATION_ENV_OUT" >"$REAL_VIOLATION_STDOUT"
expect_contains "real violation status" "ai_judge_runtime_sla_freeze_status: threshold_violation" "$REAL_VIOLATION_STDOUT"
expect_contains "real violation decision" "THRESHOLD_DECISION=violated" "$REAL_VIOLATION_ENV_OUT"
expect_contains "real violation remediation true" "NEEDS_REMEDIATION=true" "$REAL_VIOLATION_ENV_OUT"
expect_contains "real violation p95 false" "COMPLIANCE_P95_MS=false" "$REAL_VIOLATION_ENV_OUT"
expect_contains "real violation fault false" "COMPLIANCE_FAULT_DRILL=false" "$REAL_VIOLATION_ENV_OUT"

echo "all ai-judge runtime sla freeze tests passed"
