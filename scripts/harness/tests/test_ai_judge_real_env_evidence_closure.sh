#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/ai_judge_real_env_evidence_closure.sh"

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
    printf 'CALIBRATED_AT=2026-04-14T10:00:00Z\n'
    printf 'CALIBRATED_BY=qa-bot\n'
    printf 'DATASET_REF=dataset-2026-04-14\n'
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
    printf 'LOCAL_ENV_EVIDENCE=file:///tmp/local-reference/%s\n' "$(basename "$file")"
    printf 'LOCAL_ENV_PROFILE=macbookpro2021_m1pro_16gb_10core\n'
    printf 'CALIBRATED_AT=2026-04-14T10:00:00Z\n'
    printf 'CALIBRATED_BY=qa-bot-local\n'
    while [[ $# -gt 0 ]]; do
      printf '%s\n' "$1"
      shift
    done
  } >"$file"
}

write_runtime_sla_real_file() {
  local file="$1"
  cat >"$file" <<'EOF'
RUNTIME_SLA_FREEZE_STATUS=pass
FREEZE_UPDATED_AT=2026-04-14T10:00:00Z
RUNTIME_SLA_EVIDENCE=https://example.com/evidence/runtime-sla
FREEZE_DATASET_REF=runtime-sla-dataset-2026-04-14
THRESHOLD_DECISION=accepted
OBS_P95_MS=850
OBS_P99_MS=1600
COMPLIANCE_P95_MS=true
COMPLIANCE_P99_MS=true
COMPLIANCE_FAULT_DRILL=true
COMPLIANCE_TRACE_HASH_COVERAGE=true
COMPLIANCE_COMMITMENT_COVERAGE=true
COMPLIANCE_ATTESTATION_GAP=true
EOF
}

write_runtime_sla_local_file() {
  local file="$1"
  cat >"$file" <<'EOF'
RUNTIME_SLA_FREEZE_STATUS=local_reference_frozen
FREEZE_UPDATED_AT=2026-04-14T10:00:00Z
RUNTIME_SLA_EVIDENCE=file:///tmp/local-reference/runtime-sla
FREEZE_DATASET_REF=runtime-sla-local-dataset-2026-04-14
FREEZE_ENV_MODE=local_reference
THRESHOLD_DECISION=accepted
OBS_P95_MS=850
OBS_P99_MS=1600
COMPLIANCE_P95_MS=true
COMPLIANCE_P99_MS=true
COMPLIANCE_FAULT_DRILL=true
COMPLIANCE_TRACE_HASH_COVERAGE=true
COMPLIANCE_COMMITMENT_COVERAGE=true
COMPLIANCE_ATTESTATION_GAP=true
EOF
}

write_track_files() {
  local dir="$1"
  local mode="${2:-real}"

  local write_p5_file_fn="write_real_validated_file"
  if [[ "$mode" == "local" ]]; then
    write_p5_file_fn="write_local_validated_file"
  fi

  "$write_p5_file_fn" "$dir/ai_judge_p5_latency_baseline.env" \
    "WINDOW_FROM=2026-04-12T00:00:00Z" \
    "WINDOW_TO=2026-04-14T00:00:00Z" \
    "SAMPLE_SIZE=1200" \
    "P95_MS=850" \
    "P99_MS=1600"

  "$write_p5_file_fn" "$dir/ai_judge_p5_cost_baseline.env" \
    "WINDOW_FROM=2026-04-12T00:00:00Z" \
    "WINDOW_TO=2026-04-14T00:00:00Z" \
    "TOKEN_INPUT_TOTAL=1000000" \
    "TOKEN_OUTPUT_TOTAL=350000" \
    "COST_USD_TOTAL=88.12" \
    "COST_USD_PER_1K=0.065"

  "$write_p5_file_fn" "$dir/ai_judge_p5_fairness_benchmark.env" \
    "WINDOW_FROM=2026-04-12T00:00:00Z" \
    "WINDOW_TO=2026-04-14T00:00:00Z" \
    "SAMPLE_SIZE=900" \
    "DRAW_RATE=0.18" \
    "SIDE_BIAS_DELTA=0.03" \
    "APPEAL_OVERTURN_RATE=0.06"

  "$write_p5_file_fn" "$dir/ai_judge_p5_fault_drill.env" \
    "DRILL_RUN_AT=2026-04-14T09:00:00Z" \
    "CALLBACK_FAILURE_RECOVERY_PASS=true" \
    "REPLAY_CONSISTENCY_PASS=true" \
    "AUDIT_ALERT_DELIVERY_PASS=true"

  "$write_p5_file_fn" "$dir/ai_judge_p5_trust_attestation.env" \
    "TRACE_HASH_COVERAGE=1.00" \
    "COMMITMENT_COVERAGE=1.00" \
    "ATTESTATION_GAP=0"

  if [[ "$mode" == "local" ]]; then
    write_runtime_sla_local_file "$dir/ai_judge_runtime_sla_thresholds.env"
  else
    write_runtime_sla_real_file "$dir/ai_judge_runtime_sla_thresholds.env"
  fi
}

# 场景1：marker 未就绪 -> env_blocked
WORK_BLOCKED="$TMP_DIR/blocked"
EVIDENCE_BLOCKED="$WORK_BLOCKED/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_BLOCKED" "$WORK_BLOCKED/artifacts/harness"
write_track_files "$EVIDENCE_BLOCKED"
cat >"$EVIDENCE_BLOCKED/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=false
EOF

BLOCKED_STDOUT="$TMP_DIR/blocked.stdout"
bash "$SCRIPT" --root "$WORK_BLOCKED" >"$BLOCKED_STDOUT"
expect_contains "blocked status" "ai_judge_real_env_evidence_closure_status: env_blocked" "$BLOCKED_STDOUT"
expect_contains "blocked marker" "real_env_marker_ready: false" "$BLOCKED_STDOUT"

# 场景2：本机参考预检通过 -> local_reference_ready
WORK_LOCAL="$TMP_DIR/local"
EVIDENCE_LOCAL="$WORK_LOCAL/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_LOCAL" "$WORK_LOCAL/artifacts/harness"
write_track_files "$EVIDENCE_LOCAL" "local"
cat >"$EVIDENCE_LOCAL/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=false
LOCAL_REFERENCE_ENV_READY=true
CALIBRATION_ENV_MODE=local_reference
EOF

LOCAL_STDOUT="$TMP_DIR/local.stdout"
LOCAL_ENV="$TMP_DIR/local.closure.env"
bash "$SCRIPT" \
  --root "$WORK_LOCAL" \
  --allow-local-reference \
  --output-env "$LOCAL_ENV" >"$LOCAL_STDOUT"

expect_contains "local status" "ai_judge_real_env_evidence_closure_status: local_reference_ready" "$LOCAL_STDOUT"
expect_contains "local env mode" "environment_mode: local_reference" "$LOCAL_STDOUT"
expect_contains "local env status" "AI_JUDGE_REAL_ENV_CLOSURE_STATUS=local_reference_ready" "$LOCAL_ENV"
expect_contains "local env ready tracks" "READY_TRACKS=6" "$LOCAL_ENV"

# 场景3：marker 就绪但缺 real 键 -> pending_real_evidence
WORK_PENDING="$TMP_DIR/pending"
EVIDENCE_PENDING="$WORK_PENDING/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_PENDING" "$WORK_PENDING/artifacts/harness"
write_track_files "$EVIDENCE_PENDING"
cat >"$EVIDENCE_PENDING/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
EOF
sed -i '' '/^REAL_ENV_EVIDENCE=/d' "$EVIDENCE_PENDING/ai_judge_p5_fairness_benchmark.env"

PENDING_STDOUT="$TMP_DIR/pending.stdout"
PENDING_DOC="$TMP_DIR/pending.checklist.md"
PENDING_ENV="$TMP_DIR/pending.closure.env"
bash "$SCRIPT" \
  --root "$WORK_PENDING" \
  --output-doc "$PENDING_DOC" \
  --output-env "$PENDING_ENV" >"$PENDING_STDOUT"

expect_contains "pending status" "ai_judge_real_env_evidence_closure_status: pending_real_evidence" "$PENDING_STDOUT"
expect_contains "pending marker true" "real_env_marker_ready: true" "$PENDING_STDOUT"
expect_contains "pending env status" "AI_JUDGE_REAL_ENV_CLOSURE_STATUS=pending_real_evidence" "$PENDING_ENV"
expect_contains "pending doc missing key" "REAL_ENV_EVIDENCE" "$PENDING_DOC"

# 场景4：全部齐备 -> pass
WORK_PASS="$TMP_DIR/pass"
EVIDENCE_PASS="$WORK_PASS/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_PASS" "$WORK_PASS/artifacts/harness"
write_track_files "$EVIDENCE_PASS"
cat >"$EVIDENCE_PASS/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
EOF

PASS_STDOUT="$TMP_DIR/pass.stdout"
PASS_ENV="$TMP_DIR/pass.closure.env"
bash "$SCRIPT" \
  --root "$WORK_PASS" \
  --output-env "$PASS_ENV" >"$PASS_STDOUT"

expect_contains "pass status" "ai_judge_real_env_evidence_closure_status: pass" "$PASS_STDOUT"
expect_contains "pass ready tracks" "READY_TRACKS=6" "$PASS_ENV"
expect_contains "pass pending tracks" "PENDING_TRACKS=0" "$PASS_ENV"

echo "all ai-judge real env evidence closure tests passed"
