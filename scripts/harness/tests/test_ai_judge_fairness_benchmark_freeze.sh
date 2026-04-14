#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/ai_judge_fairness_benchmark_freeze.sh"

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

write_local_benchmark_env() {
  local file="$1"
  local draw_rate="$2"
  local side_bias_delta="$3"
  local overturn="$4"
  cat >"$file" <<EOF
CALIBRATION_STATUS=validated
WINDOW_FROM=2026-04-12T00:00:00Z
WINDOW_TO=2026-04-14T00:00:00Z
SAMPLE_SIZE=384
DRAW_RATE=$draw_rate
SIDE_BIAS_DELTA=$side_bias_delta
APPEAL_OVERTURN_RATE=$overturn
LOCAL_ENV_EVIDENCE=file://local/fairness
LOCAL_ENV_PROFILE=macbookpro2021_m1pro_16gb_10core
CALIBRATED_AT=2026-04-14T00:18:00Z
CALIBRATED_BY=local-dev-bot
TRACK_ID=fairness_benchmark
EOF
}

write_real_benchmark_env() {
  local file="$1"
  local draw_rate="$2"
  local side_bias_delta="$3"
  local overturn="$4"
  cat >"$file" <<EOF
CALIBRATION_STATUS=validated
WINDOW_FROM=2026-04-12T00:00:00Z
WINDOW_TO=2026-04-14T00:00:00Z
SAMPLE_SIZE=912
DRAW_RATE=$draw_rate
SIDE_BIAS_DELTA=$side_bias_delta
APPEAL_OVERTURN_RATE=$overturn
REAL_ENV_EVIDENCE=https://example.com/fairness-benchmark-report
CALIBRATED_AT=2026-04-14T10:00:00Z
CALIBRATED_BY=qa-bot
DATASET_REF=fairness-dataset-2026-04-14
TRACK_ID=fairness_benchmark
EOF
}

# 场景1：环境未就绪 -> env_blocked
WORK_BLOCKED="$TMP_DIR/blocked"
mkdir -p "$WORK_BLOCKED/docs/loadtest/evidence" "$WORK_BLOCKED/docs/dev_plan" "$WORK_BLOCKED/artifacts/harness"
write_local_benchmark_env "$WORK_BLOCKED/docs/loadtest/evidence/ai_judge_p5_fairness_benchmark.env" "0.20" "0.04" "0.07"

BLOCKED_STDOUT="$TMP_DIR/blocked.stdout"
bash "$SCRIPT" \
  --root "$WORK_BLOCKED" >"$BLOCKED_STDOUT"

expect_contains "blocked status" "ai_judge_fairness_benchmark_freeze_status: env_blocked" "$BLOCKED_STDOUT"
expect_contains "blocked mode" "environment_mode: blocked" "$BLOCKED_STDOUT"

# 场景2：local reference 就绪并达标 -> local_reference_frozen
WORK_LOCAL="$TMP_DIR/local"
mkdir -p "$WORK_LOCAL/docs/loadtest/evidence" "$WORK_LOCAL/docs/dev_plan" "$WORK_LOCAL/artifacts/harness"
cat >"$WORK_LOCAL/docs/loadtest/evidence/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=false
LOCAL_REFERENCE_ENV_READY=true
CALIBRATION_ENV_MODE=local_reference
EOF
write_local_benchmark_env "$WORK_LOCAL/docs/loadtest/evidence/ai_judge_p5_fairness_benchmark.env" "0.20" "0.04" "0.07"

LOCAL_STDOUT="$TMP_DIR/local.stdout"
LOCAL_ENV_OUT="$TMP_DIR/local.thresholds.env"
LOCAL_DOC_OUT="$TMP_DIR/local.freeze.md"
bash "$SCRIPT" \
  --root "$WORK_LOCAL" \
  --allow-local-reference \
  --output-env "$LOCAL_ENV_OUT" \
  --output-doc "$LOCAL_DOC_OUT" >"$LOCAL_STDOUT"

expect_contains "local status" "ai_judge_fairness_benchmark_freeze_status: local_reference_frozen" "$LOCAL_STDOUT"
expect_contains "local mode" "environment_mode: local_reference" "$LOCAL_STDOUT"
expect_contains "local decision accepted" "THRESHOLD_DECISION=accepted" "$LOCAL_ENV_OUT"
expect_contains "local reconfirm true" "NEEDS_REAL_ENV_RECONFIRM=true" "$LOCAL_ENV_OUT"
expect_contains "local draw compliance" "COMPLIANCE_DRAW_RATE=true" "$LOCAL_ENV_OUT"

# 场景3：real 环境且达标 -> pass
WORK_REAL_PASS="$TMP_DIR/real-pass"
mkdir -p "$WORK_REAL_PASS/docs/loadtest/evidence" "$WORK_REAL_PASS/docs/dev_plan" "$WORK_REAL_PASS/artifacts/harness"
cat >"$WORK_REAL_PASS/docs/loadtest/evidence/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
EOF
write_real_benchmark_env "$WORK_REAL_PASS/docs/loadtest/evidence/ai_judge_p5_fairness_benchmark.env" "0.18" "0.03" "0.05"

REAL_PASS_STDOUT="$TMP_DIR/real-pass.stdout"
REAL_PASS_ENV_OUT="$TMP_DIR/real-pass.thresholds.env"
bash "$SCRIPT" \
  --root "$WORK_REAL_PASS" \
  --output-env "$REAL_PASS_ENV_OUT" >"$REAL_PASS_STDOUT"

expect_contains "real pass status" "ai_judge_fairness_benchmark_freeze_status: pass" "$REAL_PASS_STDOUT"
expect_contains "real pass mode" "environment_mode: real" "$REAL_PASS_STDOUT"
expect_contains "real pass accepted" "THRESHOLD_DECISION=accepted" "$REAL_PASS_ENV_OUT"
expect_contains "real pass reconfirm false" "NEEDS_REAL_ENV_RECONFIRM=false" "$REAL_PASS_ENV_OUT"

# 场景4：real 环境但阈值超限 -> threshold_violation
WORK_REAL_VIOLATION="$TMP_DIR/real-violation"
mkdir -p "$WORK_REAL_VIOLATION/docs/loadtest/evidence" "$WORK_REAL_VIOLATION/docs/dev_plan" "$WORK_REAL_VIOLATION/artifacts/harness"
cat >"$WORK_REAL_VIOLATION/docs/loadtest/evidence/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
EOF
write_real_benchmark_env "$WORK_REAL_VIOLATION/docs/loadtest/evidence/ai_judge_p5_fairness_benchmark.env" "0.45" "0.03" "0.05"

REAL_VIOLATION_STDOUT="$TMP_DIR/real-violation.stdout"
REAL_VIOLATION_ENV_OUT="$TMP_DIR/real-violation.thresholds.env"
bash "$SCRIPT" \
  --root "$WORK_REAL_VIOLATION" \
  --output-env "$REAL_VIOLATION_ENV_OUT" >"$REAL_VIOLATION_STDOUT"

expect_contains "real violation status" "ai_judge_fairness_benchmark_freeze_status: threshold_violation" "$REAL_VIOLATION_STDOUT"
expect_contains "real violation decision" "THRESHOLD_DECISION=violated" "$REAL_VIOLATION_ENV_OUT"
expect_contains "real violation remediation" "NEEDS_REMEDIATION=true" "$REAL_VIOLATION_ENV_OUT"
expect_contains "real violation draw compliance false" "COMPLIANCE_DRAW_RATE=false" "$REAL_VIOLATION_ENV_OUT"

echo "all ai-judge fairness benchmark freeze tests passed"
