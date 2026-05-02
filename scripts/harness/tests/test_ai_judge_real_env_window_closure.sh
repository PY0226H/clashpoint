#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
SCRIPT="$ROOT/scripts/harness/ai_judge_real_env_window_closure.sh"
P5_SCRIPT="$ROOT/scripts/harness/ai_judge_p5_real_calibration_on_env.sh"
RUNTIME_OPS_SCRIPT="$ROOT/scripts/harness/ai_judge_runtime_ops_pack.sh"
FAIRNESS_SCRIPT="$ROOT/scripts/harness/ai_judge_fairness_benchmark_freeze.sh"
RUNTIME_SLA_SCRIPT="$ROOT/scripts/harness/ai_judge_runtime_sla_freeze.sh"
REAL_ENV_CLOSURE_SCRIPT="$ROOT/scripts/harness/ai_judge_real_env_evidence_closure.sh"
STAGE_CLOSURE_DRAFT_SCRIPT="$ROOT/scripts/harness/ai_judge_stage_closure_draft.sh"
STAGE_CLOSURE_EVIDENCE_SCRIPT="$ROOT/scripts/harness/ai_judge_stage_closure_evidence.sh"

for path in "$SCRIPT" "$P5_SCRIPT" "$RUNTIME_OPS_SCRIPT" "$FAIRNESS_SCRIPT" "$RUNTIME_SLA_SCRIPT" "$REAL_ENV_CLOSURE_SCRIPT" "$STAGE_CLOSURE_DRAFT_SCRIPT" "$STAGE_CLOSURE_EVIDENCE_SCRIPT"; do
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

seed_stage_closure_plan() {
  local file="$1"
  cat >"$file" <<'EOF_PLAN'
# 当前开发计划

### 已完成/未完成矩阵
| 阶段 | 目标 | 状态 | 说明 |
| --- | --- | --- | --- |
| ai-judge-runtime-ops-pack | P1 | 进行中（phase 已完成） | done |

## 5. 延后事项（不阻塞当前阶段）

1. 真实环境窗口校准待完成

### 下一开发模块建议

1. ai-judge-real-env-window-closure
EOF_PLAN
}

seed_release_readiness_summary() {
  local dir="$1"
  local decision="${2:-env_blocked}"
  mkdir -p "$dir"
  cat >"$dir/ai_judge_release_readiness_artifact_summary.json" <<EOF_JSON
{
  "version": "release-readiness-artifact-summary-v1",
  "artifactRef": "release-readiness-artifact-test",
  "manifestHash": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "evidenceVersion": "policy-release-readiness-evidence-v1",
  "decision": "$decision",
  "storageMode": "local_reference",
  "p41ControlPlaneStatus": "env_blocked",
  "p41RuntimeReadinessStatus": "ready",
  "p41ChatProxyStatus": "ready",
  "p41FrontendContractStatus": "ready",
  "p41CalibrationDecisionLogStatus": "ready",
  "p41PanelShadowCandidateStatus": "env_blocked",
  "p41RuntimeOpsPackStatus": "local_reference_ready",
  "redactionContract": {
    "storageUriVisible": false,
    "objectStorePathVisible": false
  }
}
EOF_JSON
}

write_artifact_store_healthcheck_evidence() {
  local file="$1"
  local ready="$2"
  local roundtrip_status="$3"
  local blocker_code="${4:-null}"
  local blocker_value="null"
  if [[ "$blocker_code" != "null" ]]; then
    blocker_value="\"$blocker_code\""
  fi
  cat >"$file" <<EOF_JSON
{
  "version": "artifact-store-healthcheck-evidence-v1",
  "provider": "s3_compatible",
  "status": "$([[ "$ready" == "true" ]] && echo "ready" || echo "blocked")",
  "productionReady": $ready,
  "roundtrip": {
    "status": "$roundtrip_status"
  },
  "realEnvWindow": {
    "productionArtifactStoreReady": $ready,
    "recommendedEnv": {
      "PRODUCTION_ARTIFACT_STORE_READY": "$ready"
    },
    "blockerCode": $blocker_value
  },
  "healthcheck": {
    "writeReadRoundtripStatus": "$roundtrip_status",
    "productionReady": $ready
  }
}
EOF_JSON
}

append_real_readiness_evidence_links() {
  local file="$1"
  cat >>"$file" <<'EOF'
REAL_SAMPLE_MANIFEST_EVIDENCE=https://example.com/evidence/sample-manifest
REAL_PROVIDER_EVIDENCE=https://example.com/evidence/provider-health
REAL_CALLBACK_EVIDENCE=https://example.com/evidence/callback-health
BENCHMARK_TARGETS_EVIDENCE=https://example.com/evidence/benchmark-targets
FAIRNESS_TARGETS_EVIDENCE=https://example.com/evidence/fairness-targets
RUNTIME_OPS_TARGETS_EVIDENCE=https://example.com/evidence/runtime-ops-targets
EOF
}

write_polluted_local_reference_artifact_store_evidence() {
  local file="$1"
  cat >"$file" <<'EOF_JSON'
{
  "version": "artifact-store-healthcheck-evidence-v1",
  "provider": "local",
  "status": "local_reference",
  "productionReady": true,
  "roundtrip": {
    "status": "pass"
  },
  "realEnvWindow": {
    "productionArtifactStoreReady": true,
    "recommendedEnv": {
      "PRODUCTION_ARTIFACT_STORE_READY": "true"
    },
    "blockerCode": null
  },
  "healthcheck": {
    "provider": "local",
    "status": "local_reference",
    "writeReadRoundtripStatus": "pass",
    "productionReady": true
  }
}
EOF_JSON
}

run_window_closure() {
  local work="$1"
  local plan_doc="$work/plan-stage-closure.md"
  mkdir -p "$work"
  seed_stage_closure_plan "$plan_doc"
  shift
  bash "$SCRIPT" \
    --root "$work" \
    --p5-script "$P5_SCRIPT" \
    --runtime-ops-script "$RUNTIME_OPS_SCRIPT" \
    --fairness-script "$FAIRNESS_SCRIPT" \
    --runtime-sla-script "$RUNTIME_SLA_SCRIPT" \
    --real-env-closure-script "$REAL_ENV_CLOSURE_SCRIPT" \
    --stage-closure-plan-doc "$plan_doc" \
    --stage-closure-draft-script "$STAGE_CLOSURE_DRAFT_SCRIPT" \
    --stage-closure-evidence-script "$STAGE_CLOSURE_EVIDENCE_SCRIPT" \
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
run_window_closure "$WORK_BLOCKED" >"$BLOCKED_STDOUT"
expect_contains "blocked status" "ai_judge_real_env_window_closure_status: env_blocked" "$BLOCKED_STDOUT"
expect_contains "blocked p5 status" "p5_status: env_blocked" "$BLOCKED_STDOUT"
expect_contains "blocked runtime pack status" "runtime_ops_pack_status: evidence_missing" "$BLOCKED_STDOUT"

# 场景2：真实环境通过 -> pass
WORK_PASS="$TMP_DIR/pass"
EVIDENCE_PASS="$WORK_PASS/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_PASS"
seed_tracks_real "$EVIDENCE_PASS"
seed_release_readiness_summary "$EVIDENCE_PASS" "allowed"
write_artifact_store_healthcheck_evidence "$EVIDENCE_PASS/ai_judge_artifact_store_healthcheck.json" "true" "pass"
cat >"$EVIDENCE_PASS/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
CALIBRATION_ENV_MODE=real
REAL_SAMPLE_MANIFEST=s3://echoisle-real-samples/p37/manifest.json
REAL_SAMPLE_MANIFEST_READY=true
REAL_PROVIDER_READY=true
REAL_CALLBACK_READY=true
BENCHMARK_TARGETS_READY=true
FAIRNESS_TARGETS_READY=true
RUNTIME_OPS_TARGETS_READY=true
REAL_EVIDENCE_LINK=https://example.com/evidence/window-pass
EOF
append_real_readiness_evidence_links "$EVIDENCE_PASS/ai_judge_p5_real_env.env"

PASS_STDOUT="$TMP_DIR/pass.stdout"
PASS_JSON="$TMP_DIR/pass.summary.json"
PASS_MD="$TMP_DIR/pass.summary.md"
run_window_closure "$WORK_PASS" --emit-json "$PASS_JSON" --emit-md "$PASS_MD" >"$PASS_STDOUT"
expect_contains "pass status" "ai_judge_real_env_window_closure_status: pass" "$PASS_STDOUT"
expect_contains "pass readiness status" "real_env_readiness_status: pass" "$PASS_STDOUT"
expect_contains "pass readiness input ready" "real_env_input_ready: true" "$PASS_STDOUT"
expect_contains "pass p5 status" "p5_status: pass" "$PASS_STDOUT"
expect_contains "pass runtime pack status" "runtime_ops_pack_status: pass" "$PASS_STDOUT"
expect_contains "pass real pass ready" "real_pass_ready: true" "$PASS_STDOUT"
expect_contains "pass artifact evidence ready" "production_artifact_store_evidence_status: ready" "$PASS_STDOUT"
expect_contains "pass artifact evidence roundtrip" "production_artifact_store_evidence_roundtrip_status: pass" "$PASS_STDOUT"
expect_contains "pass json" "\"status\": \"pass\"" "$PASS_JSON"
expect_contains "pass json readiness block" "\"readiness\"" "$PASS_JSON"
expect_contains "pass json readiness input" "\"input_ready\": true" "$PASS_JSON"
expect_contains "pass json artifact evidence status" "\"production_artifact_store_evidence_status\": \"ready\"" "$PASS_JSON"
expect_contains "pass json real pass ready" "\"ready\": true" "$PASS_JSON"
expect_contains "pass md title" "# ai-judge-real-env-window-closure" "$PASS_MD"
expect_contains "pass closure env real pass" "REAL_PASS_READY=true" "$EVIDENCE_PASS/ai_judge_real_env_window_closure.env"
expect_contains "pass closure env readiness" "REAL_ENV_READINESS_STATUS=pass" "$EVIDENCE_PASS/ai_judge_real_env_window_closure.env"
expect_contains "pass closure env artifact ready" "PRODUCTION_ARTIFACT_STORE_READY=true" "$EVIDENCE_PASS/ai_judge_real_env_window_closure.env"
expect_contains "pass closure env artifact evidence" "PRODUCTION_ARTIFACT_STORE_EVIDENCE_STATUS=ready" "$EVIDENCE_PASS/ai_judge_real_env_window_closure.env"

# 场景2a：preflight-only 只校验真实窗口输入，不执行 P5/runtime ops
WORK_PREFLIGHT="$TMP_DIR/preflight"
EVIDENCE_PREFLIGHT="$WORK_PREFLIGHT/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_PREFLIGHT"
write_artifact_store_healthcheck_evidence "$EVIDENCE_PREFLIGHT/ai_judge_artifact_store_healthcheck.json" "true" "pass"
cat >"$EVIDENCE_PREFLIGHT/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
CALIBRATION_ENV_MODE=real
REAL_SAMPLE_MANIFEST=s3://echoisle-real-samples/p37/manifest.json
REAL_SAMPLE_MANIFEST_READY=true
REAL_PROVIDER_READY=true
REAL_CALLBACK_READY=true
BENCHMARK_TARGETS_READY=true
FAIRNESS_TARGETS_READY=true
RUNTIME_OPS_TARGETS_READY=true
EOF
append_real_readiness_evidence_links "$EVIDENCE_PREFLIGHT/ai_judge_p5_real_env.env"

PREFLIGHT_STDOUT="$TMP_DIR/preflight.stdout"
PREFLIGHT_JSON="$TMP_DIR/preflight.summary.json"
run_window_closure "$WORK_PREFLIGHT" --preflight-only --emit-json "$PREFLIGHT_JSON" >"$PREFLIGHT_STDOUT"
expect_contains "preflight status ready" "ai_judge_real_env_window_closure_status: preflight_ready" "$PREFLIGHT_STDOUT"
expect_contains "preflight flag" "preflight_only: true" "$PREFLIGHT_STDOUT"
expect_contains "preflight input ready" "real_env_input_ready: true" "$PREFLIGHT_STDOUT"
expect_contains "preflight p5 not run" "p5_status: not_run" "$PREFLIGHT_STDOUT"
expect_contains "preflight runtime not run" "runtime_ops_pack_status: not_run" "$PREFLIGHT_STDOUT"
expect_contains "preflight env flag" "PREFLIGHT_ONLY=true" "$EVIDENCE_PREFLIGHT/ai_judge_real_env_window_closure.env"
expect_contains "preflight json flag" "\"preflight_only\": \"true\"" "$PREFLIGHT_JSON"

# 场景2a-0：preflight-only 不接受只有 READY=true、缺少对应 evidence 链接的输入
WORK_PREFLIGHT_MISSING_EVIDENCE_LINKS="$TMP_DIR/preflight-missing-evidence-links"
EVIDENCE_PREFLIGHT_MISSING_EVIDENCE_LINKS="$WORK_PREFLIGHT_MISSING_EVIDENCE_LINKS/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_PREFLIGHT_MISSING_EVIDENCE_LINKS"
write_artifact_store_healthcheck_evidence "$EVIDENCE_PREFLIGHT_MISSING_EVIDENCE_LINKS/ai_judge_artifact_store_healthcheck.json" "true" "pass"
cat >"$EVIDENCE_PREFLIGHT_MISSING_EVIDENCE_LINKS/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
CALIBRATION_ENV_MODE=real
REAL_SAMPLE_MANIFEST=s3://echoisle-real-samples/p37/manifest.json
REAL_SAMPLE_MANIFEST_READY=true
REAL_PROVIDER_READY=true
REAL_CALLBACK_READY=true
BENCHMARK_TARGETS_READY=true
FAIRNESS_TARGETS_READY=true
RUNTIME_OPS_TARGETS_READY=true
EOF

PREFLIGHT_MISSING_EVIDENCE_LINKS_STDOUT="$TMP_DIR/preflight-missing-evidence-links.stdout"
run_window_closure "$WORK_PREFLIGHT_MISSING_EVIDENCE_LINKS" --preflight-only >"$PREFLIGHT_MISSING_EVIDENCE_LINKS_STDOUT"
expect_contains "preflight missing links blocked" "ai_judge_real_env_window_closure_status: env_blocked" "$PREFLIGHT_MISSING_EVIDENCE_LINKS_STDOUT"
expect_contains "preflight missing sample evidence" "real_sample_manifest_evidence_missing" "$PREFLIGHT_MISSING_EVIDENCE_LINKS_STDOUT"
expect_contains "preflight missing provider evidence" "real_provider_evidence_missing" "$PREFLIGHT_MISSING_EVIDENCE_LINKS_STDOUT"
expect_contains "preflight missing runtime evidence" "runtime_ops_targets_evidence_missing" "$PREFLIGHT_MISSING_EVIDENCE_LINKS_STDOUT"

# 场景2a-1：preflight-only 不接受手工 artifact ready 替代 healthcheck evidence
WORK_PREFLIGHT_NO_EVIDENCE="$TMP_DIR/preflight-no-evidence"
EVIDENCE_PREFLIGHT_NO_EVIDENCE="$WORK_PREFLIGHT_NO_EVIDENCE/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_PREFLIGHT_NO_EVIDENCE"
cat >"$EVIDENCE_PREFLIGHT_NO_EVIDENCE/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
CALIBRATION_ENV_MODE=real
REAL_SAMPLE_MANIFEST=s3://echoisle-real-samples/p37/manifest.json
REAL_SAMPLE_MANIFEST_READY=true
REAL_PROVIDER_READY=true
REAL_CALLBACK_READY=true
PRODUCTION_ARTIFACT_STORE_READY=true
BENCHMARK_TARGETS_READY=true
FAIRNESS_TARGETS_READY=true
RUNTIME_OPS_TARGETS_READY=true
EOF
append_real_readiness_evidence_links "$EVIDENCE_PREFLIGHT_NO_EVIDENCE/ai_judge_p5_real_env.env"

PREFLIGHT_NO_EVIDENCE_STDOUT="$TMP_DIR/preflight-no-evidence.stdout"
run_window_closure "$WORK_PREFLIGHT_NO_EVIDENCE" --preflight-only >"$PREFLIGHT_NO_EVIDENCE_STDOUT"
expect_contains "preflight no evidence blocked" "ai_judge_real_env_window_closure_status: env_blocked" "$PREFLIGHT_NO_EVIDENCE_STDOUT"
expect_contains "preflight no evidence status" "production_artifact_store_evidence_status: not_provided" "$PREFLIGHT_NO_EVIDENCE_STDOUT"
expect_contains "preflight no evidence blocker" "production_artifact_store_evidence_not_provided" "$PREFLIGHT_NO_EVIDENCE_STDOUT"
expect_contains "preflight no evidence no p5" "p5_status: not_run" "$PREFLIGHT_NO_EVIDENCE_STDOUT"

# 场景2a-2：preflight-only 输入缺失时阻断，且不执行子阶段
WORK_PREFLIGHT_BLOCKED="$TMP_DIR/preflight-blocked"
EVIDENCE_PREFLIGHT_BLOCKED="$WORK_PREFLIGHT_BLOCKED/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_PREFLIGHT_BLOCKED"
write_artifact_store_healthcheck_evidence "$EVIDENCE_PREFLIGHT_BLOCKED/ai_judge_artifact_store_healthcheck.json" "false" "read_failed" "production_artifact_store_roundtrip_failed"
cat >"$EVIDENCE_PREFLIGHT_BLOCKED/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
CALIBRATION_ENV_MODE=real
REAL_PROVIDER_READY=true
REAL_CALLBACK_READY=true
BENCHMARK_TARGETS_READY=true
FAIRNESS_TARGETS_READY=true
RUNTIME_OPS_TARGETS_READY=true
EOF
append_real_readiness_evidence_links "$EVIDENCE_PREFLIGHT_BLOCKED/ai_judge_p5_real_env.env"

PREFLIGHT_BLOCKED_STDOUT="$TMP_DIR/preflight-blocked.stdout"
run_window_closure "$WORK_PREFLIGHT_BLOCKED" --preflight-only >"$PREFLIGHT_BLOCKED_STDOUT"
expect_contains "preflight blocked status" "ai_judge_real_env_window_closure_status: env_blocked" "$PREFLIGHT_BLOCKED_STDOUT"
expect_contains "preflight blocked no p5" "p5_status: not_run" "$PREFLIGHT_BLOCKED_STDOUT"
expect_contains "preflight blocked manifest" "real_sample_manifest_missing" "$PREFLIGHT_BLOCKED_STDOUT"
expect_contains "preflight blocked artifact" "production_artifact_store_roundtrip_failed" "$PREFLIGHT_BLOCKED_STDOUT"

# 场景2b：真实阶段数据齐全但 readiness 输入缺失 -> env_blocked，防止 fake pass
WORK_INPUT_BLOCKED="$TMP_DIR/input-blocked"
EVIDENCE_INPUT_BLOCKED="$WORK_INPUT_BLOCKED/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_INPUT_BLOCKED"
seed_tracks_real "$EVIDENCE_INPUT_BLOCKED"
seed_release_readiness_summary "$EVIDENCE_INPUT_BLOCKED"
cat >"$EVIDENCE_INPUT_BLOCKED/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
CALIBRATION_ENV_MODE=real
EOF

INPUT_BLOCKED_STDOUT="$TMP_DIR/input-blocked.stdout"
run_window_closure "$WORK_INPUT_BLOCKED" >"$INPUT_BLOCKED_STDOUT"
expect_contains "input blocked status" "ai_judge_real_env_window_closure_status: env_blocked" "$INPUT_BLOCKED_STDOUT"
expect_contains "input blocked readiness code" "real_sample_manifest_missing" "$INPUT_BLOCKED_STDOUT"

# 场景2c：对象存储 healthcheck 证据未通过 -> env_blocked，并保留具体 blocker
WORK_ARTIFACT_BLOCKED="$TMP_DIR/artifact-blocked"
EVIDENCE_ARTIFACT_BLOCKED="$WORK_ARTIFACT_BLOCKED/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_ARTIFACT_BLOCKED"
seed_tracks_real "$EVIDENCE_ARTIFACT_BLOCKED"
seed_release_readiness_summary "$EVIDENCE_ARTIFACT_BLOCKED"
write_artifact_store_healthcheck_evidence "$EVIDENCE_ARTIFACT_BLOCKED/ai_judge_artifact_store_healthcheck.json" "false" "put_failed" "production_artifact_store_roundtrip_failed"
cat >"$EVIDENCE_ARTIFACT_BLOCKED/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
CALIBRATION_ENV_MODE=real
REAL_SAMPLE_MANIFEST=s3://echoisle-real-samples/p37/manifest.json
REAL_SAMPLE_MANIFEST_READY=true
REAL_PROVIDER_READY=true
REAL_CALLBACK_READY=true
BENCHMARK_TARGETS_READY=true
FAIRNESS_TARGETS_READY=true
RUNTIME_OPS_TARGETS_READY=true
EOF
append_real_readiness_evidence_links "$EVIDENCE_ARTIFACT_BLOCKED/ai_judge_p5_real_env.env"

ARTIFACT_BLOCKED_STDOUT="$TMP_DIR/artifact-blocked.stdout"
run_window_closure "$WORK_ARTIFACT_BLOCKED" >"$ARTIFACT_BLOCKED_STDOUT"
expect_contains "artifact blocked status" "ai_judge_real_env_window_closure_status: env_blocked" "$ARTIFACT_BLOCKED_STDOUT"
expect_contains "artifact blocked evidence status" "production_artifact_store_evidence_status: blocked" "$ARTIFACT_BLOCKED_STDOUT"
expect_contains "artifact blocked readiness code" "production_artifact_store_roundtrip_failed" "$ARTIFACT_BLOCKED_STDOUT"

# 场景2d：显式 ready 与失败 evidence 冲突时，以 evidence 为准，避免 fake pass
WORK_ARTIFACT_CONFLICT="$TMP_DIR/artifact-conflict"
EVIDENCE_ARTIFACT_CONFLICT="$WORK_ARTIFACT_CONFLICT/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_ARTIFACT_CONFLICT"
seed_tracks_real "$EVIDENCE_ARTIFACT_CONFLICT"
seed_release_readiness_summary "$EVIDENCE_ARTIFACT_CONFLICT"
write_artifact_store_healthcheck_evidence "$EVIDENCE_ARTIFACT_CONFLICT/ai_judge_artifact_store_healthcheck.json" "false" "read_failed" "production_artifact_store_roundtrip_failed"
cat >"$EVIDENCE_ARTIFACT_CONFLICT/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
CALIBRATION_ENV_MODE=real
REAL_SAMPLE_MANIFEST=s3://echoisle-real-samples/p37/manifest.json
REAL_SAMPLE_MANIFEST_READY=true
REAL_PROVIDER_READY=true
REAL_CALLBACK_READY=true
PRODUCTION_ARTIFACT_STORE_READY=true
BENCHMARK_TARGETS_READY=true
FAIRNESS_TARGETS_READY=true
RUNTIME_OPS_TARGETS_READY=true
EOF
append_real_readiness_evidence_links "$EVIDENCE_ARTIFACT_CONFLICT/ai_judge_p5_real_env.env"

ARTIFACT_CONFLICT_STDOUT="$TMP_DIR/artifact-conflict.stdout"
run_window_closure "$WORK_ARTIFACT_CONFLICT" >"$ARTIFACT_CONFLICT_STDOUT"
expect_contains "artifact conflict status" "ai_judge_real_env_window_closure_status: env_blocked" "$ARTIFACT_CONFLICT_STDOUT"
expect_contains "artifact conflict evidence status" "production_artifact_store_evidence_status: blocked" "$ARTIFACT_CONFLICT_STDOUT"
expect_contains "artifact conflict ready overridden" "PRODUCTION_ARTIFACT_STORE_READY=false" "$EVIDENCE_ARTIFACT_CONFLICT/ai_judge_real_env_window_closure.env"

# 场景2e：污染的 local_reference healthcheck 即使写 productionReady=true 也不能通过
WORK_ARTIFACT_LOCAL_POLLUTED="$TMP_DIR/artifact-local-polluted"
EVIDENCE_ARTIFACT_LOCAL_POLLUTED="$WORK_ARTIFACT_LOCAL_POLLUTED/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_ARTIFACT_LOCAL_POLLUTED"
seed_tracks_real "$EVIDENCE_ARTIFACT_LOCAL_POLLUTED"
seed_release_readiness_summary "$EVIDENCE_ARTIFACT_LOCAL_POLLUTED"
write_polluted_local_reference_artifact_store_evidence "$EVIDENCE_ARTIFACT_LOCAL_POLLUTED/ai_judge_artifact_store_healthcheck.json"
cat >"$EVIDENCE_ARTIFACT_LOCAL_POLLUTED/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
CALIBRATION_ENV_MODE=real
REAL_SAMPLE_MANIFEST=s3://echoisle-real-samples/p37/manifest.json
REAL_SAMPLE_MANIFEST_READY=true
REAL_PROVIDER_READY=true
REAL_CALLBACK_READY=true
PRODUCTION_ARTIFACT_STORE_READY=true
BENCHMARK_TARGETS_READY=true
FAIRNESS_TARGETS_READY=true
RUNTIME_OPS_TARGETS_READY=true
EOF
append_real_readiness_evidence_links "$EVIDENCE_ARTIFACT_LOCAL_POLLUTED/ai_judge_p5_real_env.env"

ARTIFACT_LOCAL_POLLUTED_STDOUT="$TMP_DIR/artifact-local-polluted.stdout"
run_window_closure "$WORK_ARTIFACT_LOCAL_POLLUTED" --preflight-only >"$ARTIFACT_LOCAL_POLLUTED_STDOUT"
expect_contains "artifact polluted blocked" "ai_judge_real_env_window_closure_status: env_blocked" "$ARTIFACT_LOCAL_POLLUTED_STDOUT"
expect_contains "artifact polluted local blocker" "production_artifact_store_local_reference" "$ARTIFACT_LOCAL_POLLUTED_STDOUT"
expect_contains "artifact polluted ready overridden" "PRODUCTION_ARTIFACT_STORE_READY=false" "$EVIDENCE_ARTIFACT_LOCAL_POLLUTED/ai_judge_real_env_window_closure.env"
expect_contains "artifact polluted provider recorded" "PRODUCTION_ARTIFACT_STORE_EVIDENCE_PROVIDER=local" "$EVIDENCE_ARTIFACT_LOCAL_POLLUTED/ai_judge_real_env_window_closure.env"

# 场景3：阈值违反 -> threshold_violation
WORK_VIOLATION="$TMP_DIR/violation"
EVIDENCE_VIOLATION="$WORK_VIOLATION/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_VIOLATION"
seed_tracks_real "$EVIDENCE_VIOLATION" "0.45" "1600" "2900" "false" "0.90" "0.90" "0.12"
seed_release_readiness_summary "$EVIDENCE_VIOLATION" "blocked"
write_artifact_store_healthcheck_evidence "$EVIDENCE_VIOLATION/ai_judge_artifact_store_healthcheck.json" "true" "pass"
cat >"$EVIDENCE_VIOLATION/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
CALIBRATION_ENV_MODE=real
REAL_SAMPLE_MANIFEST=s3://echoisle-real-samples/p37/manifest.json
REAL_SAMPLE_MANIFEST_READY=true
REAL_PROVIDER_READY=true
REAL_CALLBACK_READY=true
PRODUCTION_ARTIFACT_STORE_READY=true
BENCHMARK_TARGETS_READY=true
FAIRNESS_TARGETS_READY=true
RUNTIME_OPS_TARGETS_READY=true
EOF
append_real_readiness_evidence_links "$EVIDENCE_VIOLATION/ai_judge_p5_real_env.env"

VIOLATION_STDOUT="$TMP_DIR/violation.stdout"
run_window_closure "$WORK_VIOLATION" >"$VIOLATION_STDOUT"
expect_contains "violation status" "ai_judge_real_env_window_closure_status: threshold_violation" "$VIOLATION_STDOUT"
expect_contains "violation runtime pack status" "runtime_ops_pack_status: threshold_violation" "$VIOLATION_STDOUT"

# 场景4：缺 real 证据键 -> pending_real_evidence
WORK_PENDING="$TMP_DIR/pending"
EVIDENCE_PENDING="$WORK_PENDING/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_PENDING"
seed_tracks_real "$EVIDENCE_PENDING"
seed_release_readiness_summary "$EVIDENCE_PENDING"
write_artifact_store_healthcheck_evidence "$EVIDENCE_PENDING/ai_judge_artifact_store_healthcheck.json" "true" "pass"
cat >"$EVIDENCE_PENDING/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=true
CALIBRATION_ENV_MODE=real
REAL_SAMPLE_MANIFEST=s3://echoisle-real-samples/p37/manifest.json
REAL_SAMPLE_MANIFEST_READY=true
REAL_PROVIDER_READY=true
REAL_CALLBACK_READY=true
PRODUCTION_ARTIFACT_STORE_READY=true
BENCHMARK_TARGETS_READY=true
FAIRNESS_TARGETS_READY=true
RUNTIME_OPS_TARGETS_READY=true
EOF
append_real_readiness_evidence_links "$EVIDENCE_PENDING/ai_judge_p5_real_env.env"
sed -i '' '/^REAL_ENV_EVIDENCE=/d' "$EVIDENCE_PENDING/ai_judge_p5_latency_baseline.env"

PENDING_STDOUT="$TMP_DIR/pending.stdout"
run_window_closure "$WORK_PENDING" >"$PENDING_STDOUT"
expect_contains "pending status" "ai_judge_real_env_window_closure_status: pending_real_evidence" "$PENDING_STDOUT"
expect_contains "pending p5 status" "p5_status: pending_real_data" "$PENDING_STDOUT"

# 场景5：本机参考窗口 -> local_reference_ready
WORK_LOCAL="$TMP_DIR/local"
EVIDENCE_LOCAL="$WORK_LOCAL/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_LOCAL"
seed_tracks_local "$EVIDENCE_LOCAL"
seed_release_readiness_summary "$EVIDENCE_LOCAL"
cat >"$EVIDENCE_LOCAL/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=false
LOCAL_REFERENCE_ENV_READY=true
CALIBRATION_ENV_MODE=local_reference
EOF

LOCAL_STDOUT="$TMP_DIR/local.stdout"
run_window_closure "$WORK_LOCAL" --allow-local-reference >"$LOCAL_STDOUT"
expect_contains "local status" "ai_judge_real_env_window_closure_status: local_reference_ready" "$LOCAL_STDOUT"
expect_contains "local p5 status" "p5_status: local_reference_pass" "$LOCAL_STDOUT"
expect_contains "local runtime pack status" "runtime_ops_pack_status: local_reference_ready" "$LOCAL_STDOUT"
expect_contains "local real pass not ready" "real_pass_ready: false" "$LOCAL_STDOUT"
expect_contains "local blocker includes marker" "real_pass_blocker_codes: real_env_marker_not_ready" "$LOCAL_STDOUT"

# 场景6：窗口脚本透传 fairness ingest 并成功
WORK_INGEST="$TMP_DIR/ingest"
EVIDENCE_INGEST="$WORK_INGEST/docs/loadtest/evidence"
mkdir -p "$EVIDENCE_INGEST"
seed_tracks_local "$EVIDENCE_INGEST"
seed_release_readiness_summary "$EVIDENCE_INGEST"
cat >"$EVIDENCE_INGEST/ai_judge_p5_real_env.env" <<'EOF'
REAL_CALIBRATION_ENV_READY=false
LOCAL_REFERENCE_ENV_READY=true
CALIBRATION_ENV_MODE=local_reference
EOF

MOCK_BIN_INGEST="$TMP_DIR/mock-bin-ingest"
mkdir -p "$MOCK_BIN_INGEST"
cat >"$MOCK_BIN_INGEST/curl" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
output_file=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -o)
      output_file="${2:-}"
      shift 2
      ;;
    *)
      shift 1
      ;;
  esac
done
if [[ -n "$output_file" ]]; then
  printf '{"ok":true}' >"$output_file"
fi
printf '200'
EOF
chmod +x "$MOCK_BIN_INGEST/curl"

INGEST_STDOUT="$TMP_DIR/ingest.stdout"
PATH="$MOCK_BIN_INGEST:$PATH" run_window_closure "$WORK_INGEST" \
  --allow-local-reference \
  --fairness-ingest-enabled \
  --fairness-ingest-base-url "http://127.0.0.1:8787" \
  --fairness-ingest-internal-key "test-key" >"$INGEST_STDOUT"
expect_contains "ingest closure status" "ai_judge_real_env_window_closure_status: local_reference_ready" "$INGEST_STDOUT"
expect_contains "ingest runtime status" "runtime_ops_pack_status: local_reference_ready" "$INGEST_STDOUT"
expect_contains "ingest runtime fairness ingest line" "runtime_ops_fairness_ingest_status: sent" "$INGEST_STDOUT"
expect_contains "ingest still real pass false" "real_pass_ready: false" "$INGEST_STDOUT"
expect_contains "ingest closure env persisted" "FAIRNESS_INGEST_STATUS=sent" "$EVIDENCE_INGEST/ai_judge_real_env_window_closure.env"

echo "all ai-judge real env window closure tests passed"
