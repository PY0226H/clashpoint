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

write_sample_manifest_env() {
  local file="$1"
  cat >"$file" <<'EOF'
SAMPLE_MANIFEST_VERSION=fairness-real-sample-manifest-v1
SAMPLE_ID=fairness-sample-001
TOPIC_DOMAIN=public_policy
PRO_TRANSCRIPT_REF=s3://echoisle-real-samples/fairness/pro-001.redacted.txt
CON_TRANSCRIPT_REF=s3://echoisle-real-samples/fairness/con-001.redacted.txt
EXPECTED_REVIEW_HINTS_REF=s3://echoisle-real-samples/fairness/review-hints-001.json
PRIVACY_REDACTION_STATUS=redacted
SOURCE_EVIDENCE_LINK=https://example.com/evidence/fairness-real-sample-001
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

# 场景3：real 环境但缺真实样本 manifest -> pending_real_samples
WORK_REAL_MISSING_SAMPLES="$TMP_DIR/real-missing-samples"
mkdir -p "$WORK_REAL_MISSING_SAMPLES/docs/loadtest/evidence" "$WORK_REAL_MISSING_SAMPLES/docs/dev_plan" "$WORK_REAL_MISSING_SAMPLES/artifacts/harness"
cat >"$WORK_REAL_MISSING_SAMPLES/docs/loadtest/evidence/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
EOF
write_real_benchmark_env "$WORK_REAL_MISSING_SAMPLES/docs/loadtest/evidence/ai_judge_p5_fairness_benchmark.env" "0.18" "0.03" "0.05"

REAL_MISSING_SAMPLES_STDOUT="$TMP_DIR/real-missing-samples.stdout"
REAL_MISSING_SAMPLES_ENV_OUT="$TMP_DIR/real-missing-samples.thresholds.env"
bash "$SCRIPT" \
  --root "$WORK_REAL_MISSING_SAMPLES" \
  --output-env "$REAL_MISSING_SAMPLES_ENV_OUT" >"$REAL_MISSING_SAMPLES_STDOUT"

expect_contains "real missing samples status" "ai_judge_fairness_benchmark_freeze_status: pending_real_samples" "$REAL_MISSING_SAMPLES_STDOUT"
expect_contains "real missing samples manifest status" "real_sample_manifest_status: missing" "$REAL_MISSING_SAMPLES_STDOUT"
expect_contains "real missing samples env status" "FAIRNESS_BENCHMARK_FREEZE_STATUS=pending_real_samples" "$REAL_MISSING_SAMPLES_ENV_OUT"

# 场景4：real 环境且达标 -> pass
WORK_REAL_PASS="$TMP_DIR/real-pass"
mkdir -p "$WORK_REAL_PASS/docs/loadtest/evidence" "$WORK_REAL_PASS/docs/dev_plan" "$WORK_REAL_PASS/artifacts/harness"
REAL_PASS_SAMPLE_MANIFEST="$WORK_REAL_PASS/docs/loadtest/evidence/fairness_real_sample_manifest.env"
write_sample_manifest_env "$REAL_PASS_SAMPLE_MANIFEST"
cat >"$WORK_REAL_PASS/docs/loadtest/evidence/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
EOF
write_real_benchmark_env "$WORK_REAL_PASS/docs/loadtest/evidence/ai_judge_p5_fairness_benchmark.env" "0.18" "0.03" "0.05"

REAL_PASS_STDOUT="$TMP_DIR/real-pass.stdout"
REAL_PASS_ENV_OUT="$TMP_DIR/real-pass.thresholds.env"
bash "$SCRIPT" \
  --root "$WORK_REAL_PASS" \
  --sample-manifest "$REAL_PASS_SAMPLE_MANIFEST" \
  --output-env "$REAL_PASS_ENV_OUT" >"$REAL_PASS_STDOUT"

expect_contains "real pass status" "ai_judge_fairness_benchmark_freeze_status: pass" "$REAL_PASS_STDOUT"
expect_contains "real pass mode" "environment_mode: real" "$REAL_PASS_STDOUT"
expect_contains "real pass manifest validated" "real_sample_manifest_status: validated" "$REAL_PASS_STDOUT"
expect_contains "real pass release gate ready" "registry_release_gate_input_ready: true" "$REAL_PASS_STDOUT"
expect_contains "real pass accepted" "THRESHOLD_DECISION=accepted" "$REAL_PASS_ENV_OUT"
expect_contains "real pass reconfirm false" "NEEDS_REAL_ENV_RECONFIRM=false" "$REAL_PASS_ENV_OUT"
expect_contains "real pass manifest env" "REAL_SAMPLE_MANIFEST_STATUS=validated" "$REAL_PASS_ENV_OUT"
expect_contains "real pass gate env" "FAIRNESS_REGISTRY_RELEASE_GATE_INPUT_READY=true" "$REAL_PASS_ENV_OUT"

# 场景5：real 环境但阈值超限 -> threshold_violation
WORK_REAL_VIOLATION="$TMP_DIR/real-violation"
mkdir -p "$WORK_REAL_VIOLATION/docs/loadtest/evidence" "$WORK_REAL_VIOLATION/docs/dev_plan" "$WORK_REAL_VIOLATION/artifacts/harness"
cat >"$WORK_REAL_VIOLATION/docs/loadtest/evidence/fairness_real_sample_manifest.env" <<'EOF'
SAMPLE_MANIFEST_VERSION=fairness-real-sample-manifest-v1
SAMPLE_ID=fairness-sample-violation
TOPIC_DOMAIN=public_policy
PRO_TRANSCRIPT_REF=s3://echoisle-real-samples/fairness/pro-violation.redacted.txt
CON_TRANSCRIPT_REF=s3://echoisle-real-samples/fairness/con-violation.redacted.txt
EXPECTED_REVIEW_HINTS_REF=s3://echoisle-real-samples/fairness/review-hints-violation.json
PRIVACY_REDACTION_STATUS=redacted
SOURCE_EVIDENCE_LINK=https://example.com/evidence/fairness-real-sample-violation
EOF
cat >"$WORK_REAL_VIOLATION/docs/loadtest/evidence/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
REAL_SAMPLE_MANIFEST=docs/loadtest/evidence/fairness_real_sample_manifest.env
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

# 场景6：ingest 启用且上报成功（mock curl） -> ingest_status=sent
WORK_INGEST_SENT="$TMP_DIR/ingest-sent"
mkdir -p "$WORK_INGEST_SENT/docs/loadtest/evidence" "$WORK_INGEST_SENT/docs/dev_plan" "$WORK_INGEST_SENT/artifacts/harness"
cat >"$WORK_INGEST_SENT/docs/loadtest/evidence/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
REAL_SAMPLE_MANIFEST=s3://echoisle-real-samples/fairness/manifest.json
REAL_SAMPLE_MANIFEST_READY=true
EOF
write_real_benchmark_env "$WORK_INGEST_SENT/docs/loadtest/evidence/ai_judge_p5_fairness_benchmark.env" "0.19" "0.03" "0.05"

MOCK_BIN_SENT="$TMP_DIR/mock-bin-sent"
mkdir -p "$MOCK_BIN_SENT"
cat >"$MOCK_BIN_SENT/curl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
output_file=""
data_payload=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o)
      output_file="${2:-}"
      shift 2
      ;;
    --data)
      data_payload="${2:-}"
      shift 2
      ;;
    *)
      shift 1
      ;;
  esac
done
if [[ -n "${MOCK_CURL_CAPTURE:-}" ]]; then
  printf '%s' "$data_payload" >"$MOCK_CURL_CAPTURE"
fi
if [[ -n "$output_file" ]]; then
  printf '{"ok":true}' >"$output_file"
fi
printf '200'
EOF
chmod +x "$MOCK_BIN_SENT/curl"

INGEST_SENT_STDOUT="$TMP_DIR/ingest-sent.stdout"
INGEST_SENT_ENV_OUT="$TMP_DIR/ingest-sent.thresholds.env"
INGEST_CAPTURE="$TMP_DIR/ingest.sent.payload.json"
PATH="$MOCK_BIN_SENT:$PATH" MOCK_CURL_CAPTURE="$INGEST_CAPTURE" bash "$SCRIPT" \
  --root "$WORK_INGEST_SENT" \
  --output-env "$INGEST_SENT_ENV_OUT" \
  --ingest-enabled \
  --ingest-base-url "http://127.0.0.1:8787" \
  --ingest-internal-key "test-key" >"$INGEST_SENT_STDOUT"

expect_contains "ingest sent stdout" "ingest_status: sent" "$INGEST_SENT_STDOUT"
expect_contains "ingest sent env status" "FAIRNESS_INGEST_STATUS=sent" "$INGEST_SENT_ENV_OUT"
expect_contains "ingest sent env code" "FAIRNESS_INGEST_HTTP_CODE=200" "$INGEST_SENT_ENV_OUT"
expect_contains "ingest sent payload run id" "\"run_id\"" "$INGEST_CAPTURE"
expect_contains "ingest sent payload manifest" "\"realSampleManifest\"" "$INGEST_CAPTURE"

# 场景7：ingest 启用且要求成功，但上报失败 -> 退出非 0
WORK_INGEST_FAIL="$TMP_DIR/ingest-fail"
mkdir -p "$WORK_INGEST_FAIL/docs/loadtest/evidence" "$WORK_INGEST_FAIL/docs/dev_plan" "$WORK_INGEST_FAIL/artifacts/harness"
cat >"$WORK_INGEST_FAIL/docs/loadtest/evidence/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
REAL_SAMPLE_MANIFEST=s3://echoisle-real-samples/fairness/manifest.json
REAL_SAMPLE_MANIFEST_READY=true
EOF
write_real_benchmark_env "$WORK_INGEST_FAIL/docs/loadtest/evidence/ai_judge_p5_fairness_benchmark.env" "0.18" "0.03" "0.05"

MOCK_BIN_FAIL="$TMP_DIR/mock-bin-fail"
mkdir -p "$MOCK_BIN_FAIL"
cat >"$MOCK_BIN_FAIL/curl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '000'
exit 7
EOF
chmod +x "$MOCK_BIN_FAIL/curl"

INGEST_FAIL_STDOUT="$TMP_DIR/ingest-fail.stdout"
INGEST_FAIL_ENV_OUT="$TMP_DIR/ingest-fail.thresholds.env"
set +e
PATH="$MOCK_BIN_FAIL:$PATH" bash "$SCRIPT" \
  --root "$WORK_INGEST_FAIL" \
  --output-env "$INGEST_FAIL_ENV_OUT" \
  --ingest-enabled \
  --ingest-base-url "http://127.0.0.1:8787" \
  --ingest-internal-key "test-key" \
  --ingest-require-success >"$INGEST_FAIL_STDOUT" 2>&1
INGEST_FAIL_CODE="$?"
set -e
if [[ "$INGEST_FAIL_CODE" -eq 0 ]]; then
  echo "[FAIL] ingest require success should fail"
  cat "$INGEST_FAIL_STDOUT"
  exit 1
fi
expect_contains "ingest fail stdout" "ingest_status: failed" "$INGEST_FAIL_STDOUT"
expect_contains "ingest fail error line" "ingest_required_but_not_sent" "$INGEST_FAIL_STDOUT"
expect_contains "ingest fail env status" "FAIRNESS_INGEST_STATUS=failed" "$INGEST_FAIL_ENV_OUT"

echo "all ai-judge fairness benchmark freeze tests passed"
