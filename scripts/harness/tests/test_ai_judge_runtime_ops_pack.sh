#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/ai_judge_runtime_ops_pack.sh"
FAIRNESS_SCRIPT="$ROOT/scripts/harness/ai_judge_fairness_benchmark_freeze.sh"
RUNTIME_SLA_SCRIPT="$ROOT/scripts/harness/ai_judge_runtime_sla_freeze.sh"
REAL_CLOSURE_SCRIPT="$ROOT/scripts/harness/ai_judge_real_env_evidence_closure.sh"

for path in "$SCRIPT" "$FAIRNESS_SCRIPT" "$RUNTIME_SLA_SCRIPT" "$REAL_CLOSURE_SCRIPT"; do
  if [[ ! -x "$path" ]]; then
    chmod +x "$path"
  fi
done

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

seed_tracks_real() {
  local dir="$1"
  local fairness_draw="${2:-0.18}"
  local latency_p95="${3:-980}"
  local latency_p99="${4:-1860}"
  local fault_replay="${5:-true}"
  local trust_cov="${6:-0.995}"
  local trust_commit="${7:-0.985}"
  local trust_gap="${8:-0.003}"

  write_real_validated_file "$dir/ai_judge_p5_latency_baseline.env" \
    "WINDOW_FROM=2026-04-12T00:00:00Z" \
    "WINDOW_TO=2026-04-14T00:00:00Z" \
    "SAMPLE_SIZE=1200" \
    "P95_MS=$latency_p95" \
    "P99_MS=$latency_p99"

  write_real_validated_file "$dir/ai_judge_p5_cost_baseline.env" \
    "WINDOW_FROM=2026-04-12T00:00:00Z" \
    "WINDOW_TO=2026-04-14T00:00:00Z" \
    "TOKEN_INPUT_TOTAL=1000000" \
    "TOKEN_OUTPUT_TOTAL=350000" \
    "COST_USD_TOTAL=88.12" \
    "COST_USD_PER_1K=0.065"

  write_real_validated_file "$dir/ai_judge_p5_fairness_benchmark.env" \
    "WINDOW_FROM=2026-04-12T00:00:00Z" \
    "WINDOW_TO=2026-04-14T00:00:00Z" \
    "SAMPLE_SIZE=900" \
    "DRAW_RATE=$fairness_draw" \
    "SIDE_BIAS_DELTA=0.03" \
    "APPEAL_OVERTURN_RATE=0.06"

  write_real_validated_file "$dir/ai_judge_p5_fault_drill.env" \
    "DRILL_RUN_AT=2026-04-14T09:00:00Z" \
    "CALLBACK_FAILURE_RECOVERY_PASS=true" \
    "REPLAY_CONSISTENCY_PASS=$fault_replay" \
    "AUDIT_ALERT_DELIVERY_PASS=true"

  write_real_validated_file "$dir/ai_judge_p5_trust_attestation.env" \
    "TRACE_HASH_COVERAGE=$trust_cov" \
    "COMMITMENT_COVERAGE=$trust_commit" \
    "ATTESTATION_GAP=$trust_gap"
}

seed_tracks_local() {
  local dir="$1"

  write_local_validated_file "$dir/ai_judge_p5_latency_baseline.env" \
    "WINDOW_FROM=2026-04-12T00:00:00Z" \
    "WINDOW_TO=2026-04-14T00:00:00Z" \
    "SAMPLE_SIZE=720" \
    "P95_MS=920" \
    "P99_MS=1780"

  write_local_validated_file "$dir/ai_judge_p5_cost_baseline.env" \
    "WINDOW_FROM=2026-04-12T00:00:00Z" \
    "WINDOW_TO=2026-04-14T00:00:00Z" \
    "TOKEN_INPUT_TOTAL=600000" \
    "TOKEN_OUTPUT_TOTAL=210000" \
    "COST_USD_TOTAL=41.20" \
    "COST_USD_PER_1K=0.062"

  write_local_validated_file "$dir/ai_judge_p5_fairness_benchmark.env" \
    "WINDOW_FROM=2026-04-12T00:00:00Z" \
    "WINDOW_TO=2026-04-14T00:00:00Z" \
    "SAMPLE_SIZE=384" \
    "DRAW_RATE=0.20" \
    "SIDE_BIAS_DELTA=0.04" \
    "APPEAL_OVERTURN_RATE=0.07"

  write_local_validated_file "$dir/ai_judge_p5_fault_drill.env" \
    "DRILL_RUN_AT=2026-04-14T00:18:00Z" \
    "CALLBACK_FAILURE_RECOVERY_PASS=true" \
    "REPLAY_CONSISTENCY_PASS=true" \
    "AUDIT_ALERT_DELIVERY_PASS=true"

  write_local_validated_file "$dir/ai_judge_p5_trust_attestation.env" \
    "TRACE_HASH_COVERAGE=1.00" \
    "COMMITMENT_COVERAGE=0.99" \
    "ATTESTATION_GAP=0"
}

run_pack() {
  local work="$1"
  shift
  bash "$SCRIPT" \
    --root "$work" \
    --fairness-script "$FAIRNESS_SCRIPT" \
    --runtime-sla-script "$RUNTIME_SLA_SCRIPT" \
    --real-env-closure-script "$REAL_CLOSURE_SCRIPT" \
    "$@"
}

# 场景1：环境未就绪 -> env_blocked
WORK_BLOCKED="$TMP_DIR/blocked"
EVIDENCE_BLOCKED="$WORK_BLOCKED/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_BLOCKED"
seed_tracks_real "$EVIDENCE_BLOCKED"
cat >"$EVIDENCE_BLOCKED/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=false
EOF

BLOCKED_STDOUT="$TMP_DIR/blocked.stdout"
run_pack "$WORK_BLOCKED" >"$BLOCKED_STDOUT"
expect_contains "blocked status" "ai_judge_runtime_ops_pack_status: env_blocked" "$BLOCKED_STDOUT"
expect_contains "blocked fairness" "fairness_status: env_blocked" "$BLOCKED_STDOUT"
expect_contains "blocked runtime" "runtime_sla_status: env_blocked" "$BLOCKED_STDOUT"
expect_contains "blocked closure" "real_env_closure_status: env_blocked" "$BLOCKED_STDOUT"

# 场景2：local reference -> local_reference_ready
WORK_LOCAL="$TMP_DIR/local"
EVIDENCE_LOCAL="$WORK_LOCAL/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_LOCAL"
seed_tracks_local "$EVIDENCE_LOCAL"
cat >"$EVIDENCE_LOCAL/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=false
LOCAL_REFERENCE_ENV_READY=true
CALIBRATION_ENV_MODE=local_reference
EOF

LOCAL_STDOUT="$TMP_DIR/local.stdout"
run_pack "$WORK_LOCAL" --allow-local-reference >"$LOCAL_STDOUT"
expect_contains "local status" "ai_judge_runtime_ops_pack_status: local_reference_ready" "$LOCAL_STDOUT"
expect_contains "local fairness" "fairness_status: local_reference_frozen" "$LOCAL_STDOUT"
expect_contains "local runtime" "runtime_sla_status: local_reference_frozen" "$LOCAL_STDOUT"
expect_contains "local closure" "real_env_closure_status: local_reference_ready" "$LOCAL_STDOUT"

# 场景3：real pass -> pass
WORK_PASS="$TMP_DIR/pass"
EVIDENCE_PASS="$WORK_PASS/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_PASS"
seed_tracks_real "$EVIDENCE_PASS"
cat >"$EVIDENCE_PASS/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
EOF

PASS_STDOUT="$TMP_DIR/pass.stdout"
run_pack "$WORK_PASS" >"$PASS_STDOUT"
expect_contains "pass status" "ai_judge_runtime_ops_pack_status: pass" "$PASS_STDOUT"
expect_contains "pass fairness" "fairness_status: pass" "$PASS_STDOUT"
expect_contains "pass runtime" "runtime_sla_status: pass" "$PASS_STDOUT"
expect_contains "pass closure" "real_env_closure_status: pass" "$PASS_STDOUT"

# 场景4：real threshold violation -> threshold_violation
WORK_VIOLATION="$TMP_DIR/violation"
EVIDENCE_VIOLATION="$WORK_VIOLATION/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_VIOLATION"
seed_tracks_real "$EVIDENCE_VIOLATION" "0.45" "1600" "2900" "false" "0.90" "0.90" "0.12"
cat >"$EVIDENCE_VIOLATION/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
EOF

VIOLATION_STDOUT="$TMP_DIR/violation.stdout"
run_pack "$WORK_VIOLATION" >"$VIOLATION_STDOUT"
expect_contains "violation status" "ai_judge_runtime_ops_pack_status: threshold_violation" "$VIOLATION_STDOUT"
expect_contains "violation fairness" "fairness_status: threshold_violation" "$VIOLATION_STDOUT"
expect_contains "violation runtime" "runtime_sla_status: threshold_violation" "$VIOLATION_STDOUT"

echo "all ai-judge runtime ops pack tests passed"
